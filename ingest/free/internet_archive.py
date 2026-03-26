"""Strategy 8: Internet Archive — full-text extraction from public domain books.

Searches archive.org for biographical texts about a person, downloads
OCR full text, and extracts place/date pairs using biographical patterns.
No API key required. All texts are public domain.
"""

import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ingest.free.date_resolver import resolve_date
from ingest.free.google_books import (
    BIO_PATTERNS, DATE_WINDOW, IGNORE_PLACES, POSTHUMOUS_INDICATORS,
    _is_valid_place, _clean_place, _find_nearby_date,
)
from ingest.wikipedia import fetch_page

IA_SEARCH = 'https://archive.org/advancedsearch.php'
IA_METADATA = 'https://archive.org/metadata'
IA_DOWNLOAD = 'https://archive.org/download'
USER_AGENT = 'WhoWasWhereWhen/1.0'

# Cache directory for downloaded texts
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ia_cache')

_last_request_time = 0.0


def _rate_limit(min_interval=1.0):
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time = time.time()


def search_texts(person_name, max_results=10):
    """Search Internet Archive for texts about a person.

    Returns list of dicts with: identifier, title, creator, date, description.
    """
    _rate_limit()

    params = {
        'q': f'(title:("{person_name}") OR subject:("{person_name}")) AND mediatype:(texts) AND language:(eng)',
        'fl[]': ['identifier', 'title', 'creator', 'date', 'description', 'downloads'],
        'sort[]': 'downloads desc',
        'rows': min(max_results, 50),
        'output': 'json',
    }

    try:
        resp = requests.get(
            IA_SEARCH,
            params=params,
            headers={'User-Agent': USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Internet Archive search error: {e}")
        return []

    docs = data.get('response', {}).get('docs', [])
    return docs


def get_text_file_url(identifier):
    """Find the best plain text file for an Internet Archive item.

    Looks for _djvu.txt (OCR full text), then _hocr_searchtext.txt.gz,
    then any .txt file.
    """
    _rate_limit(0.5)

    try:
        resp = requests.get(
            f'{IA_METADATA}/{identifier}/files',
            headers={'User-Agent': USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
        files = resp.json().get('result', [])
    except Exception as e:
        print(f"  Metadata error for {identifier}: {e}")
        return None

    # Prefer plain text formats in order of quality
    preferred_suffixes = ['_djvu.txt', '.txt']

    for suffix in preferred_suffixes:
        for f in files:
            name = f.get('name', '')
            if name.endswith(suffix) and f.get('format') != 'Metadata':
                return f'{IA_DOWNLOAD}/{identifier}/{name}'

    return None


def download_text(identifier, url):
    """Download and cache full text from Internet Archive."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f'{identifier}.txt')

    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return f.read()

    _rate_limit()
    try:
        resp = requests.get(
            url,
            headers={'User-Agent': USER_AGENT},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        print(f"  Download error: {e}")
        return None

    with open(cache_path, 'w') as f:
        f.write(text)

    return text


def _clean_ocr_text(text):
    """Clean OCR artifacts from Internet Archive text.

    Collapses multi-space runs, removes line-break hyphenation,
    and normalizes whitespace while preserving paragraph breaks.
    """
    # Fix hyphenated line breaks (e.g., "Napo-\nle-\non" → "Napoleon")
    text = re.sub(r'-\s*\n\s*', '', text)
    # Collapse lines within paragraphs (single newlines → space)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text


def extract_locations_from_fulltext(text, person_name, max_chars=50000):
    """Extract place/date pairs from full book text using biographical patterns.

    Processes up to max_chars of text (books can be very large).
    Returns list of datapoint dicts (without coordinates).
    """
    if not text:
        return []

    # Clean OCR artifacts
    text = _clean_ocr_text(text)

    # Truncate very long texts
    if len(text) > max_chars:
        text = text[:max_chars]

    datapoints = []
    seen = set()

    # Phase 1: Biographical phrase patterns
    for pattern, confidence, desc_template in BIO_PATTERNS:
        for m in pattern.finditer(text):
            place = _clean_place(m.group(1))
            if not _is_valid_place(place):
                continue

            # Skip posthumous/legacy context
            ctx_start = max(0, m.start() - 100)
            ctx_end = min(len(text), m.end() + 100)
            context = text[ctx_start:ctx_end]
            if POSTHUMOUS_INDICATORS.search(context):
                continue

            date_str = _find_nearby_date(text, m.start(), m.end(), window=200)
            if not date_str:
                continue

            ds, de, prec, display = resolve_date(date_str)
            if not ds:
                continue

            dedup_key = (place.lower(), ds)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            datapoints.append({
                'place_name': place,
                'date_start': ds,
                'date_end': de or ds,
                'date_precision': prec or 'year',
                'date_display': display,
                'description': desc_template.format(place=place),
                'confidence': confidence,
                'source_text': text[ctx_start:ctx_end].strip(),
                'extraction_method': 'pattern',
                'created_by': 'system',
                'raw_date_text': date_str,
                'raw_place_text': m.group(1),
            })

    # Phase 2: "in <Place>" + nearby date co-occurrence
    for m in re.finditer(r'\bin ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,2})', text):
        place = _clean_place(m.group(1))
        if not _is_valid_place(place):
            continue

        # Skip posthumous/legacy context
        ctx_start = max(0, m.start() - 80)
        ctx_end = min(len(text), m.end() + 80)
        context = text[ctx_start:ctx_end]
        if POSTHUMOUS_INDICATORS.search(context):
            continue

        date_str = _find_nearby_date(text, m.start(), m.end(), window=100)
        if not date_str:
            continue

        ds, de, prec, display = resolve_date(date_str)
        if not ds:
            continue

        dedup_key = (place.lower(), ds)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        datapoints.append({
            'place_name': place,
            'date_start': ds,
            'date_end': de or ds,
            'date_precision': prec or 'year',
            'date_display': display,
            'description': f'{person_name} in {place}',
            'confidence': 'possible',
            'source_text': text[ctx_start:ctx_end].strip(),
            'extraction_method': 'pattern',
            'created_by': 'system',
            'raw_date_text': date_str,
            'raw_place_text': m.group(1),
        })

    return datapoints


def _make_source(identifier, title, creator=None):
    """Build a source dict from an Internet Archive item."""
    return {
        'title': title or identifier,
        'url': f'https://archive.org/details/{identifier}',
        'author': creator,
        'source_type': 'book',
    }


def ingest_person(person_name=None, wikipedia_url=None, max_texts=5,
                  llm_provider=None, json_out=None, dry_run=False):
    """Full Internet Archive ingestion pipeline for a single person.

    Returns the data dict (person + datapoints) or None on failure.
    """
    print(f"\n{'='*60}")
    print(f"Internet Archive Ingest: {person_name or wikipedia_url}")
    print(f"{'='*60}")

    # Step 1: Get person info from Wikipedia
    print("\n1. Fetching person info from Wikipedia...")
    wiki = fetch_page(person_name=person_name, url=wikipedia_url)
    if not wiki:
        print("   Could not fetch Wikipedia page.")
        return None

    name = wiki.get('name') or person_name
    print(f"   Name: {name}")

    person_data = {
        'name': name,
        'description': wiki.get('description'),
        'wikipedia_url': wiki.get('wikipedia_url'),
        'image_url': wiki.get('image_url'),
    }

    for field, raw_key in [('birth', 'birth_date_raw'), ('death', 'death_date_raw')]:
        raw = wiki.get(raw_key)
        if raw:
            ds, de, prec, display = resolve_date(raw)
            if ds:
                person_data[f'{field}_date_start'] = ds
                person_data[f'{field}_date_end'] = de or ds
                person_data[f'{field}_date_display'] = display

    # Step 2: Search Internet Archive
    print(f"\n2. Searching Internet Archive for '{name}'...")
    items = search_texts(name, max_results=max_texts * 2)
    print(f"   Found {len(items)} items")

    # Step 2b: Filter items by relevance (if using LLM)
    if llm_provider and len(items) > 1:
        from ingest.free.free_llm_extract import filter_books_by_relevance
        print(f"\n   Filtering texts for relevance...")
        items = filter_books_by_relevance(name, [
            {'title': it.get('title', ''), 'author': it.get('creator', ''), **it}
            for it in items
        ], provider=llm_provider)

    # Step 3: Download and extract from each text
    print(f"\n3. Processing texts (up to {max_texts})...")
    all_datapoints = []
    seen_global = set()
    texts_processed = 0

    for item in items:
        if texts_processed >= max_texts:
            break

        identifier = item.get('identifier', '')
        title = item.get('title', '')
        creator = item.get('creator', '')
        if isinstance(creator, list):
            creator = ', '.join(creator)

        print(f"\n   --- {title} ---")

        # Log discovery
        from ingest.free.book_registry import log_discovery, log_ingestion
        book_url = f'https://archive.org/details/{identifier}'
        log_discovery('archive', name, title, creator, book_url, identifier)

        # Find text file URL
        text_url = get_text_file_url(identifier)
        if not text_url:
            print(f"   No text file available, skipping")
            log_ingestion('archive', identifier, method='', datapoints=0,
                          status='skipped', notes='no text file')
            continue

        # Download text
        text = download_text(identifier, text_url)
        if not text:
            print(f"   Download failed, skipping")
            log_ingestion('archive', identifier, method='', datapoints=0,
                          status='failed', notes='download failed')
            continue

        print(f"   Downloaded {len(text):,} chars")
        texts_processed += 1

        # Extract locations
        method = llm_provider or 'pattern'
        if llm_provider:
            from ingest.free.free_llm_extract import extract_locations_from_chunks
            locations = extract_locations_from_chunks(name, text, provider=llm_provider)
        else:
            locations = extract_locations_from_fulltext(text, name)
        source = _make_source(identifier, title, creator)

        new_count = 0
        for loc in locations:
            dedup_key = (loc['place_name'].lower(), loc['date_start'])
            if dedup_key in seen_global:
                continue
            seen_global.add(dedup_key)
            loc['sources'] = [source]
            all_datapoints.append(loc)
            new_count += 1

        print(f"   Extracted {new_count} new datapoints")
        log_ingestion('archive', identifier, method=method,
                      datapoints=new_count, status='ingested')

    print(f"\n   Total: {len(all_datapoints)} datapoints from {texts_processed} texts")

    # Step 4: Geocode
    print("\n4. Geocoding locations...")
    from ingest.geocode import geocode
    geocoded = []

    for dp in all_datapoints:
        coords = geocode(dp['place_name'])
        if coords:
            dp['latitude'] = coords[0]
            dp['longitude'] = coords[1]
            geocoded.append(dp)
        else:
            print(f"   Could not geocode: {dp['place_name']}")

    all_datapoints = geocoded
    print(f"   Geocoded: {len(all_datapoints)} datapoints")

    data = {'person': person_data, 'datapoints': all_datapoints}

    # Step 5: Export or import
    if json_out:
        print(f"\n5. Writing JSON to {json_out}...")
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, 'w') as f:
            json.dump(data, f, indent=2)
        print("   Done!")
    else:
        print("\n5. Importing into database...")
        from ingest.import_json import import_data
        import_data(data, dry_run=dry_run)

    return data


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ingest from Internet Archive full texts')
    parser.add_argument('--person', help='Person name to look up')
    parser.add_argument('--wikipedia-url', help='Wikipedia URL')
    parser.add_argument('--max-texts', type=int, default=5, help='Max texts to process (default 5)')
    parser.add_argument('--batch-file', help='Text file with one person name per line')
    parser.add_argument('--json-out', help='Export to JSON file instead of importing to DB')
    parser.add_argument('--dry-run', action='store_true', help='Validate without inserting')
    args = parser.parse_args()

    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"Batch ingesting {len(names)} persons from Internet Archive...")
        for name in names:
            try:
                ingest_person(person_name=name, max_texts=args.max_texts,
                              dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    elif args.person or args.wikipedia_url:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            max_texts=args.max_texts,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )
    else:
        print("Specify --person or --wikipedia-url or --batch-file")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
