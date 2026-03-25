"""Improved Gutenberg ingestion: downloads full text, splits into chunks,
extracts locations from each chunk separately, then deduplicates."""

import json
import os
import re
import sqlite3
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

CHUNK_SIZE = 4000  # characters per chunk (fits comfortably in a prompt)
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def get_db():
    db_path = os.path.join(DATA_DIR, 'wwww.db')
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def download_text(gutenberg_url):
    """Download and cache a Gutenberg plain text file."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Extract ebook ID from URL
    match = re.search(r'/(\d+)', gutenberg_url)
    if not match:
        raise ValueError(f"Cannot parse Gutenberg URL: {gutenberg_url}")
    ebook_id = match.group(1)

    cache_path = os.path.join(DATA_DIR, f'gutenberg_{ebook_id}.txt')
    if os.path.exists(cache_path):
        print(f"  Using cached text: {cache_path}")
        with open(cache_path) as f:
            return f.read()

    # Try plain text URL patterns
    urls = [
        f'https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.txt',
        f'https://www.gutenberg.org/files/{ebook_id}/{ebook_id}-0.txt',
    ]

    for url in urls:
        print(f"  Trying {url}...")
        resp = requests.get(url, headers={'User-Agent': 'WhoWasWhereWhen/1.0'}, timeout=30)
        if resp.status_code == 200:
            text = resp.text
            with open(cache_path, 'w') as f:
                f.write(text)
            print(f"  Downloaded {len(text)} chars, cached to {cache_path}")
            return text

    raise RuntimeError(f"Could not download Gutenberg ebook {ebook_id}")


def strip_gutenberg_header_footer(text):
    """Remove Project Gutenberg boilerplate."""
    start_markers = ['*** START OF', '***START OF']
    end_markers = ['*** END OF', '***END OF', 'End of the Project Gutenberg']

    start = 0
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            start = text.find('\n', idx) + 1
            break

    end = len(text)
    for marker in end_markers:
        idx = text.find(marker)
        if idx != -1:
            end = idx
            break

    return text[start:end].strip()


def split_into_chunks(text, chunk_size=CHUNK_SIZE):
    """Split text into chunks, breaking at paragraph boundaries."""
    paragraphs = text.split('\n\n')
    chunks = []
    current = ''

    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            current = para
        else:
            current += '\n\n' + para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def extract_locations_from_chunk(client, chunk_text, person_name, chunk_num, total_chunks):
    """Use Claude API to extract locations from a single text chunk."""
    prompt = f"""You are extracting location data from a biographical/diary text about {person_name}.

This is chunk {chunk_num} of {total_chunks}.

Extract EVERY location mentioned where {person_name} was present. For each location provide a JSON object with:
- "place_name": full place name with country/region (e.g. "Monchy-au-Bois, France")
- "date_start": ISO date YYYY-MM-DD (estimate if needed)
- "date_end": ISO date YYYY-MM-DD
- "date_precision": "day", "month", "season", "year", "decade", or "approximate"
- "date_display": human-readable date string
- "description": 1-2 sentence description of what happened there
- "confidence": "certain", "probable", "possible", or "speculative"

Return ONLY a JSON array. If no locations are found in this chunk, return [].
Do NOT skip any location, no matter how briefly mentioned. Include transit points, billets, hospitals, training camps, and battle positions.

Text chunk:
{chunk_text}"""

    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=4096,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = response.content[0].text.strip()

        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        locations = json.loads(text)
        return locations if isinstance(locations, list) else []
    except Exception as e:
        print(f"    Error on chunk {chunk_num}: {e}")
        return []


def deduplicate_locations(locations):
    """Merge duplicate locations by place name, keeping the one with most detail."""
    seen = {}
    for loc in locations:
        key = loc.get('place_name', '').lower().strip()
        if not key:
            continue
        if key not in seen or len(loc.get('description', '')) > len(seen[key].get('description', '')):
            seen[key] = loc
    return list(seen.values())


def ingest_from_gutenberg(gutenberg_url, person_info):
    """Full pipeline: download text, chunk it, extract from each chunk, geocode, insert.

    person_info should be a dict with keys:
        name, birth_start, birth_end, birth_display,
        death_start, death_end, death_display,
        description, wikipedia_url
    """
    import anthropic
    from ingest.geocode import geocode

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. This pipeline requires the Claude API.")
        print("Set it with: export ANTHROPIC_API_KEY=your_key")
        return

    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{'='*60}")
    print(f"Ingesting: {person_info['name']}")
    print(f"Source: {gutenberg_url}")
    print(f"{'='*60}")

    # Step 1: Download
    print("\n1. Downloading text...")
    raw_text = download_text(gutenberg_url)
    text = strip_gutenberg_header_footer(raw_text)
    print(f"   Clean text: {len(text)} chars")

    # Step 2: Chunk
    print("\n2. Splitting into chunks...")
    chunks = split_into_chunks(text)
    print(f"   {len(chunks)} chunks of ~{CHUNK_SIZE} chars each")

    # Step 3: Extract from each chunk
    print("\n3. Extracting locations from each chunk...")
    all_locations = []
    for i, chunk in enumerate(chunks):
        locs = extract_locations_from_chunk(client, chunk, person_info['name'], i + 1, len(chunks))
        if locs:
            print(f"   Chunk {i+1}/{len(chunks)}: {len(locs)} locations")
            all_locations.extend(locs)
        else:
            print(f"   Chunk {i+1}/{len(chunks)}: no locations")
        time.sleep(0.5)  # rate limit courtesy

    print(f"\n   Total raw: {len(all_locations)} locations")

    # Step 4: Deduplicate
    locations = deduplicate_locations(all_locations)
    print(f"   After dedup: {len(locations)} unique locations")

    # Step 5: Insert into database
    print("\n4. Geocoding and inserting...")
    db = get_db()

    # Upsert person
    existing = db.execute(
        "SELECT id FROM persons WHERE name = ?", (person_info['name'],)
    ).fetchone()
    if existing:
        person_id = existing['id']
        print(f"   Person exists (id={person_id})")
    else:
        cur = db.execute(
            "INSERT INTO persons (name, birth_date_start, birth_date_end, birth_date_display, "
            "death_date_start, death_date_end, death_date_display, description, wikipedia_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (person_info['name'], person_info.get('birth_start'), person_info.get('birth_end'),
             person_info.get('birth_display'), person_info.get('death_start'),
             person_info.get('death_end'), person_info.get('death_display'),
             person_info.get('description'), person_info.get('wikipedia_url'))
        )
        person_id = cur.lastrowid
        print(f"   Created person (id={person_id})")

    # Get existing to avoid duplicates
    existing_places = {r['place_name'].lower() for r in db.execute(
        "SELECT place_name FROM whereabouts WHERE person_id = ?", (person_id,)
    ).fetchall()}

    inserted = 0
    skipped = 0
    for loc in locations:
        place = loc.get('place_name', '').strip()
        if not place:
            continue
        if place.lower() in existing_places:
            skipped += 1
            continue

        coords = geocode(place)
        if not coords:
            print(f"   ! Could not geocode: {place}")
            continue

        lat, lon = coords
        w_cur = db.execute(
            "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
            "date_start, date_end, date_precision, date_display, description, confidence, "
            "extraction_method, extraction_model, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (person_id, place, lat, lon,
             loc.get('date_start', ''), loc.get('date_end', ''),
             loc.get('date_precision', 'year'), loc.get('date_display', ''),
             loc.get('description', ''), loc.get('confidence', 'probable'),
             'claude', 'claude-sonnet', 'system')
        )
        db.execute(
            "INSERT INTO sources (whereabout_id, url, title, source_type) VALUES (?, ?, ?, 'ai_extracted')",
            (w_cur.lastrowid, gutenberg_url, f"AI extraction from Project Gutenberg: {person_info['name']}")
        )
        inserted += 1
        existing_places.add(place.lower())
        print(f"   + {place} ({loc.get('date_display', '')})")

    db.commit()
    db.close()
    print(f"\n   Done! Inserted {inserted} new, skipped {skipped} duplicates")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Ingest from Project Gutenberg with chunked AI extraction')
    parser.add_argument('--url', required=True, help='Gutenberg ebook URL or plain text URL')
    parser.add_argument('--name', required=True, help='Person name')
    parser.add_argument('--birth', help='Birth date display string')
    parser.add_argument('--death', help='Death date display string')
    parser.add_argument('--description', help='Short person description')
    parser.add_argument('--wikipedia', help='Wikipedia URL')
    args = parser.parse_args()

    person_info = {
        'name': args.name,
        'birth_display': args.birth,
        'death_display': args.death,
        'description': args.description,
        'wikipedia_url': args.wikipedia,
    }

    ingest_from_gutenberg(args.url, person_info)
