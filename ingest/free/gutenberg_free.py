"""Strategy 9: Project Gutenberg — free full-text extraction from public domain books.

Searches Gutenberg for books by/about a person, downloads plain text,
and extracts place/date pairs using biographical patterns.
No API key or LLM required. All texts are public domain.

Unlike the original gutenberg.py which requires the Claude API for extraction,
this module uses pattern-based extraction (same approach as google_books.py
and internet_archive.py).
"""

import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ingest.free.date_resolver import resolve_date
from ingest.free.internet_archive import extract_locations_from_fulltext, _make_source
from ingest.gutenberg import download_text, strip_gutenberg_header_footer
from ingest.wikipedia import fetch_page

GUTENBERG_SEARCH = 'https://gutendex.com/books'
USER_AGENT = 'WhoWasWhereWhen/1.0'

_last_request_time = 0.0


def _rate_limit(min_interval=1.5):
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time = time.time()


def search_gutenberg(person_name, max_results=10):
    """Search Project Gutenberg for books by or about a person.

    Uses the Gutendex API (free, no key needed).
    Returns list of dicts with: id, title, authors, text_url.
    """
    _rate_limit()

    results = []

    # Search by topic/subject
    try:
        resp = requests.get(
            GUTENBERG_SEARCH,
            params={'search': person_name, 'languages': 'en', 'mime_type': 'text/plain'},
            headers={'User-Agent': USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Gutenberg search error: {e}")
        return []

    for book in data.get('results', [])[:max_results]:
        book_id = book.get('id')
        title = book.get('title', '')
        authors = [a.get('name', '') for a in book.get('authors', [])]

        # Find plain text URL
        text_url = None
        for mime, url in book.get('formats', {}).items():
            if 'text/plain' in mime and 'utf-8' in mime.lower():
                text_url = url
                break
        if not text_url:
            for mime, url in book.get('formats', {}).items():
                if 'text/plain' in mime:
                    text_url = url
                    break

        if text_url:
            results.append({
                'id': book_id,
                'title': title,
                'authors': authors,
                'text_url': text_url,
            })

    return results


def _download_and_cache(book_id, text_url):
    """Download and cache a Gutenberg text file."""
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, f'gutenberg_{book_id}.txt')

    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return f.read()

    _rate_limit()
    try:
        resp = requests.get(
            text_url,
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


def ingest_person(person_name=None, wikipedia_url=None, gutenberg_url=None,
                  max_books=5, llm_provider=None, json_out=None, dry_run=False):
    """Full Gutenberg free ingestion pipeline for a single person.

    If gutenberg_url is provided, uses that specific book.
    Otherwise, searches Gutenberg for books about the person.

    Returns the data dict (person + datapoints) or None on failure.
    """
    print(f"\n{'='*60}")
    print(f"Gutenberg Free Ingest: {person_name or wikipedia_url or gutenberg_url}")
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

    # Step 2: Find books
    if gutenberg_url:
        print(f"\n2. Using provided URL: {gutenberg_url}")
        books = [{'id': 'manual', 'title': 'Manual entry', 'authors': [], 'text_url': gutenberg_url}]
    else:
        print(f"\n2. Searching Project Gutenberg for '{name}'...")
        books = search_gutenberg(name, max_results=max_books)
        print(f"   Found {len(books)} books")

    if not books:
        print("   No books found.")
        data = {'person': person_data, 'datapoints': []}
        if json_out:
            os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
            with open(json_out, 'w') as f:
                json.dump(data, f, indent=2)
        else:
            from ingest.import_json import import_data
            import_data(data, dry_run=dry_run)
        return data

    # Step 2b: Filter books by relevance (if using LLM)
    if llm_provider and len(books) > 1:
        from ingest.free.free_llm_extract import filter_books_by_relevance
        print(f"\n   Filtering books for relevance...")
        books = filter_books_by_relevance(name, [
            {'title': b['title'], 'authors': b.get('authors', []), **b}
            for b in books
        ], provider=llm_provider)

    # Step 3: Download and extract from each book
    print(f"\n3. Processing {len(books)} books...")
    all_datapoints = []
    seen_global = set()

    for book in books:
        title = book['title']
        authors = ', '.join(book.get('authors', [])) or 'Unknown'
        book_id = str(book['id'])
        book_url = f"https://www.gutenberg.org/ebooks/{book_id}" if book_id != 'manual' else gutenberg_url
        print(f"\n   --- {title} ({authors}) ---")

        # Log discovery
        from ingest.free.book_registry import log_discovery, log_ingestion
        log_discovery('gutenberg', name, title, authors, book_url, book_id)

        # Download
        if gutenberg_url:
            raw_text = download_text(gutenberg_url)
            text = strip_gutenberg_header_footer(raw_text) if raw_text else None
        else:
            raw_text = _download_and_cache(book['id'], book['text_url'])
            text = strip_gutenberg_header_footer(raw_text) if raw_text else None

        if not text:
            print(f"   Download failed, skipping")
            log_ingestion('gutenberg', book_id, method='', datapoints=0,
                          status='failed', notes='download failed')
            continue

        print(f"   Text: {len(text):,} chars")

        # Extract locations
        method = llm_provider or 'pattern'
        if llm_provider:
            from ingest.free.free_llm_extract import extract_locations_from_chunks
            locations = extract_locations_from_chunks(name, text, provider=llm_provider)
        else:
            locations = extract_locations_from_fulltext(text, name)
        source = {
            'title': title,
            'url': book_url,
            'author': ', '.join(book.get('authors', [])) or None,
            'source_type': 'book',
        }

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
        log_ingestion('gutenberg', book_id, method=method,
                      datapoints=new_count, status='ingested')

    print(f"\n   Total: {len(all_datapoints)} datapoints")

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
    parser = argparse.ArgumentParser(description='Ingest from Project Gutenberg (free, no API key)')
    parser.add_argument('--person', help='Person name to look up')
    parser.add_argument('--wikipedia-url', help='Wikipedia URL')
    parser.add_argument('--gutenberg-url', help='Specific Gutenberg ebook URL')
    parser.add_argument('--max-books', type=int, default=5, help='Max books to search (default 5)')
    parser.add_argument('--batch-file', help='Text file with one person name per line')
    parser.add_argument('--json-out', help='Export to JSON file instead of importing to DB')
    parser.add_argument('--dry-run', action='store_true', help='Validate without inserting')
    args = parser.parse_args()

    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"Batch ingesting {len(names)} persons from Gutenberg...")
        for name in names:
            try:
                ingest_person(person_name=name, max_books=args.max_books,
                              dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    elif args.person or args.wikipedia_url or args.gutenberg_url:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            gutenberg_url=args.gutenberg_url,
            max_books=args.max_books,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )
    else:
        print("Specify --person, --wikipedia-url, --gutenberg-url, or --batch-file")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
