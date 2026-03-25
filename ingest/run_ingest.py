"""CLI entry point for the data ingestion pipeline."""

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ingest.wikipedia import fetch_page
from ingest.geocode import geocode


def get_db():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'wwww.db')
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def ingest_person(name=None, url=None, provider=None):
    """Full pipeline: scrape Wikipedia -> AI extract -> geocode -> insert into DB."""
    # Choose extraction backend
    extract_kwargs = {}
    if provider:
        from ingest.free.free_llm_extract import extract_locations
        extract_kwargs['provider'] = provider
        print(f"\n[Using free LLM provider: {provider}]")
    else:
        from ingest.ai_extract import extract_locations

    print(f"\n{'='*60}")
    print(f"Ingesting: {name or url}")
    print(f"{'='*60}")

    # Step 1: Scrape Wikipedia
    print("\n1. Fetching Wikipedia page...")
    try:
        page = fetch_page(person_name=name, url=url)
    except Exception as e:
        print(f"   Error fetching page: {e}")
        return False

    print(f"   Name: {page['name']}")
    print(f"   Description: {page['description'][:100]}...")
    print(f"   Body text: {len(page['body_text'])} chars")

    # Step 2: Insert/update person in DB
    print("\n2. Saving person to database...")
    db = get_db()

    existing = db.execute(
        "SELECT id FROM persons WHERE name = ? OR wikipedia_url = ?",
        (page['name'], page['wikipedia_url'])
    ).fetchone()

    if existing:
        person_id = existing['id']
        db.execute(
            "UPDATE persons SET description = ?, wikipedia_url = ?, image_url = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (page['description'], page['wikipedia_url'], page['image_url'], person_id)
        )
        print(f"   Updated existing person (id={person_id})")
    else:
        cur = db.execute(
            "INSERT INTO persons (name, description, wikipedia_url, image_url) VALUES (?, ?, ?, ?)",
            (page['name'], page['description'], page['wikipedia_url'], page['image_url'])
        )
        person_id = cur.lastrowid
        print(f"   Created new person (id={person_id})")

    db.commit()

    # Step 3: AI extraction
    print("\n3. Extracting locations with AI...")
    locations = extract_locations(
        page['name'], page['body_text'],
        page.get('birth_date_raw', ''), page.get('death_date_raw', ''),
        **extract_kwargs,
    )
    print(f"   Extracted {len(locations)} locations")

    # Step 4: Geocode and insert whereabouts
    print("\n4. Geocoding and saving whereabouts...")
    inserted = 0
    for loc in locations:
        place = loc.get('place_name', '')
        if not place:
            continue

        # Geocode
        coords = geocode(place)
        if not coords:
            print(f"   Could not geocode: {place}")
            continue

        lat, lon = coords

        # Check for duplicate
        dup = db.execute(
            "SELECT id FROM whereabouts WHERE person_id = ? AND place_name = ? AND date_start = ?",
            (person_id, place, loc.get('date_start', ''))
        ).fetchone()
        if dup:
            print(f"   Skipping duplicate: {place} ({loc.get('date_display', '')})")
            continue

        # Insert whereabout
        w_cur = db.execute(
            "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
            "date_start, date_end, date_precision, date_display, description, confidence, "
            "extraction_method, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (person_id, place, lat, lon,
             loc.get('date_start', ''), loc.get('date_end', ''),
             loc.get('date_precision', 'year'), loc.get('date_display', ''),
             loc.get('description', ''), loc.get('confidence', 'probable'),
             'claude', 'system')
        )

        # Add source
        db.execute(
            "INSERT INTO sources (whereabout_id, url, title, source_type) VALUES (?, ?, ?, 'ai_extracted')",
            (w_cur.lastrowid, page['wikipedia_url'], f"AI extraction from Wikipedia: {page['name']}")
        )

        inserted += 1
        print(f"   + {place} ({loc.get('date_display', '')})")

    db.commit()
    db.close()

    print(f"\n   Done! Inserted {inserted} whereabouts for {page['name']}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Ingest historical figure data')
    parser.add_argument('--person', help='Person name to look up on Wikipedia')
    parser.add_argument('--wikipedia-url', help='Direct Wikipedia URL')
    parser.add_argument('--batch-file', help='Text file with one person name per line')
    parser.add_argument('--provider', choices=['gemini', 'groq', 'mistral', 'openrouter'],
                        help='Use a free LLM provider instead of Claude (e.g. gemini, groq)')
    args = parser.parse_args()

    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"Batch ingesting {len(names)} persons...")
        for name in names:
            ingest_person(name=name, provider=args.provider)
    elif args.person:
        ingest_person(name=args.person, provider=args.provider)
    elif args.wikipedia_url:
        ingest_person(url=args.wikipedia_url, provider=args.provider)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
