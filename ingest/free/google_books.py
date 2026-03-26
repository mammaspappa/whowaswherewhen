"""Strategy 7: Google Books API — extract location data from book descriptions and snippets.

Searches Google Books for biographical works about a person, then extracts
place/date pairs from volume descriptions and text snippets. Each datapoint
is sourced back to the specific book.

Works without an API key (limited to ~100 req/day), or set
GOOGLE_BOOKS_API_KEY for 1,000 req/day.
"""

import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ingest.free.date_resolver import resolve_date
from ingest.wikipedia import fetch_page

BOOKS_API = 'https://www.googleapis.com/books/v1/volumes'
USER_AGENT = 'WhoWasWhereWhen/1.0'

_last_request_time = 0.0


def _rate_limit(min_interval=1.0):
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time = time.time()


# Biographical phrases that pair a place with context.
# Each tuple: (compiled_regex, confidence, description_template)
# {place} is replaced with the matched place name.
BIO_PATTERNS = [
    (re.compile(r'born (?:in|at|near) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Born in {place}'),
    (re.compile(r'died (?:in|at|near) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Died in {place}'),
    (re.compile(r'(?:raised|grew up) (?:in|at|near) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Raised in {place}'),
    (re.compile(r'(?:lived|resided|settled) (?:in|at|near) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Lived in {place}'),
    (re.compile(r'(?:moved|relocated|emigrated|immigrated) to ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Moved to {place}'),
    (re.compile(r'(?:studied|educated|enrolled) (?:in|at) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Studied in {place}'),
    (re.compile(r'(?:taught|professor|lectured) (?:in|at) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'possible', 'Worked in {place}'),
    (re.compile(r'(?:worked|employed|appointed) (?:in|at) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'possible', 'Worked in {place}'),
    (re.compile(r'(?:traveled|travelled|visited|toured) (?:to )?([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'possible', 'Visited {place}'),
    (re.compile(r'(?:exiled|banished|deported|fled) to ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Exiled to {place}'),
    (re.compile(r'(?:imprisoned|jailed|incarcerated) (?:in|at) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Imprisoned in {place}'),
    (re.compile(r'(?:buried|interred|entombed) (?:in|at) ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})', re.I),
     'probable', 'Buried in {place}'),
]

# Date pattern to find nearby dates in surrounding text
DATE_WINDOW = re.compile(
    r'(?:'
    r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}'
    r'|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'
    r'|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}'
    r'|circa\s+\d{3,4}|c\.\s*\d{3,4}'
    r'|\d{4}s'
    r'|\d{3,4}\s*(?:BC|BCE|AD|CE)'
    r'|\d{4}\s*[-–]\s*\d{2,4}'
    r'|\b[12]\d{3}\b'
    r')',
    re.I
)

# Places to ignore (too generic or not real places)
IGNORE_PLACES = {
    'the', 'his', 'her', 'their', 'this', 'that', 'which', 'where',
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'christian', 'jewish', 'muslim', 'catholic', 'protestant',
    'islam', 'buddhism', 'hinduism', 'christianity',
    'english', 'french', 'german', 'spanish', 'italian', 'russian',
    'american', 'british', 'european', 'african', 'asian',
    'new', 'old', 'great', 'south', 'north', 'east', 'west',
    'la', 'le', 'el', 'de', 'du', 'von', 'van', 'st', 'san',
    'chapter', 'part', 'volume', 'book', 'section', 'page',
    'life', 'death', 'war', 'battle', 'treaty', 'age', 'era',
    'rev', 'gen', 'col', 'dr', 'mr', 'mrs', 'sir', 'lord',
    'jos', 'des', 'les', 'con', 'pro',
    'congress', 'parliament', 'senate', 'house', 'court',
    'university', 'college', 'school', 'academy', 'institute',
    'autobiography', 'bibliography', 'biography',
}

# Phrases indicating posthumous/legacy context — not physical presence
POSTHUMOUS_INDICATORS = re.compile(
    r'\b(?:named after|statue|memorial|monument|museum|film|movie|play|'
    r'musical|opera|TV|television|series|documentary|biography|biopic|'
    r'novel about|book about|award|prize|honor|honour|commemorate|celebrate|'
    r'tribute|legacy|reputation|influence|inspired|adapted|portrayed|'
    r'depicted|remembered|posthumous|renamed|dedicated to|Pulitzer|Oscar|'
    r'Emmy|Tony|Nobel)\b',
    re.IGNORECASE
)


def _is_valid_place(place):
    """Check if extracted text looks like a real place name."""
    place = place.strip().rstrip('.,;:')
    if len(place) < 3 or len(place) > 80:
        return False
    if place.lower() in IGNORE_PLACES:
        return False
    if place[0].islower():
        return False
    if re.match(r'^\d+$', place):
        return False
    # Reject if contains OCR-like garbage or too many commas
    if re.search(r'[{}|\\<>]', place):
        return False
    # Reject "Place, trailing words that are clearly not place names"
    if re.search(r',\s*(?:and|or|that|this|which|where|she|he|they|was|were|the)\b', place, re.I):
        return False
    return True


def _clean_place(place):
    """Clean up an extracted place name."""
    place = place.strip().rstrip('.,;:')
    # Remove trailing words that aren't part of place names
    place = re.sub(
        r'\s+(?:and|or|but|the|where|which|when|while|during|on|in|at|to|from|for|of|by|with|as|is|was|were)\s*$',
        '', place, flags=re.I)
    return place.strip()


def search_books(person_name, api_key=None, max_results=10):
    """Search Google Books for biographical works about a person.

    Returns list of volume dicts with: title, authors, description,
    publishedDate, previewLink, textSnippet.
    """
    _rate_limit()

    params = {
        'q': f'"{person_name}" biography',
        'maxResults': min(max_results, 40),
        'printType': 'books',
        'langRestrict': 'en',
    }
    if api_key:
        params['key'] = api_key

    try:
        resp = requests.get(
            BOOKS_API,
            params=params,
            headers={'User-Agent': USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Google Books API error: {e}")
        return []

    volumes = []
    for item in data.get('items', []):
        info = item.get('volumeInfo', {})
        search_info = item.get('searchInfo', {})
        volumes.append({
            'title': info.get('title', ''),
            'authors': info.get('authors', []),
            'description': info.get('description', ''),
            'publishedDate': info.get('publishedDate', ''),
            'previewLink': info.get('previewLink', ''),
            'infoLink': info.get('infoLink', ''),
            'textSnippet': search_info.get('textSnippet', ''),
        })

    return volumes


def search_books_for_places(person_name, place_name, api_key=None):
    """Search Google Books for mentions of a person at a specific place.

    Returns list of volume dicts with snippets mentioning the place.
    """
    _rate_limit()

    params = {
        'q': f'"{person_name}" "{place_name}"',
        'maxResults': 5,
        'printType': 'books',
        'langRestrict': 'en',
    }
    if api_key:
        params['key'] = api_key

    try:
        resp = requests.get(
            BOOKS_API,
            params=params,
            headers={'User-Agent': USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Google Books place search error: {e}")
        return []

    volumes = []
    for item in data.get('items', []):
        info = item.get('volumeInfo', {})
        search_info = item.get('searchInfo', {})
        snippet = search_info.get('textSnippet', '')
        desc = info.get('description', '')
        # Only keep if the text actually mentions the place
        if place_name.lower() in (snippet + desc).lower():
            volumes.append({
                'title': info.get('title', ''),
                'authors': info.get('authors', []),
                'description': desc,
                'publishedDate': info.get('publishedDate', ''),
                'previewLink': info.get('previewLink', ''),
                'infoLink': info.get('infoLink', ''),
                'textSnippet': snippet,
            })

    return volumes


def _make_source(volume):
    """Build a source dict from a Google Books volume."""
    authors = ', '.join(volume.get('authors', [])) or None
    excerpt = volume.get('textSnippet') or volume.get('description', '')
    # Strip HTML tags from snippet
    excerpt = re.sub(r'<[^>]+>', '', excerpt)
    if len(excerpt) > 300:
        excerpt = excerpt[:297] + '...'
    return {
        'title': volume.get('title', 'Google Books'),
        'url': volume.get('infoLink') or volume.get('previewLink', ''),
        'author': authors,
        'excerpt': excerpt or None,
        'source_type': 'book',
    }


def _find_nearby_date(text, match_start, match_end, window=200):
    """Find the closest date string near a regex match in text.

    Searches within `window` characters before and after the match.
    Returns the closest date string, or None.
    """
    search_start = max(0, match_start - window)
    search_end = min(len(text), match_end + window)
    region = text[search_start:search_end]

    dates = []
    for m in DATE_WINDOW.finditer(region):
        # Distance from the place match to this date
        date_abs_start = search_start + m.start()
        dist = min(abs(date_abs_start - match_start), abs(date_abs_start - match_end))
        dates.append((dist, m.group()))

    if dates:
        dates.sort(key=lambda x: x[0])
        return dates[0][1]
    return None


def extract_locations_from_text(text, person_name):
    """Extract place/date pairs from text using biographical patterns.

    Returns list of datapoint dicts (without coordinates — those are added later).
    """
    if not text:
        return []

    datapoints = []
    seen = set()

    for pattern, confidence, desc_template in BIO_PATTERNS:
        for m in pattern.finditer(text):
            place = _clean_place(m.group(1))
            if not _is_valid_place(place):
                continue

            # Skip if surrounding text is about posthumous legacy
            ctx_start = max(0, m.start() - 100)
            ctx_end = min(len(text), m.end() + 100)
            context = text[ctx_start:ctx_end]
            if POSTHUMOUS_INDICATORS.search(context):
                continue

            # Find the nearest date in surrounding text
            date_str = _find_nearby_date(text, m.start(), m.end())
            if date_str:
                ds, de, prec, display = resolve_date(date_str)
            else:
                ds, de, prec, display = None, None, None, None

            # Skip if no date found
            if not ds:
                continue

            dedup_key = (place.lower(), ds)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            source_text = context.strip()

            datapoints.append({
                'place_name': place,
                'date_start': ds,
                'date_end': de or ds,
                'date_precision': prec or 'year',
                'date_display': display,
                'description': desc_template.format(place=place),
                'confidence': confidence,
                'source_text': source_text,
                'extraction_method': 'pattern',
                'created_by': 'system',
                'raw_date_text': date_str,
                'raw_place_text': m.group(1),
            })

    return datapoints


def extract_from_volumes(volumes, person_name):
    """Extract location datapoints from Google Books volume data.

    Processes both descriptions and text snippets from each volume.
    Returns list of (datapoint_dict, source_dict) tuples.
    """
    results = []
    seen = set()

    for vol in volumes:
        # Combine description and snippet for extraction
        text = (vol.get('description', '') + '\n' + vol.get('textSnippet', '')).strip()
        if not text:
            continue

        # Strip HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        locations = extract_locations_from_text(text, person_name)
        source = _make_source(vol)

        for loc in locations:
            dedup_key = (loc['place_name'].lower(), loc['date_start'])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            results.append((loc, source))

    return results


def _extract_wiki_places(wiki_body, person_name):
    """Extract place names mentioned in Wikipedia text for targeted book search.

    Uses biographical patterns and simple NER-like heuristics to find places.
    Returns list of unique place names.
    """
    places = set()

    # Use biographical patterns to find places
    for pattern, _, _ in BIO_PATTERNS:
        for m in pattern.finditer(wiki_body):
            place = _clean_place(m.group(1))
            if _is_valid_place(place):
                places.add(place)

    # Also extract "in <Place>" patterns (very common in biographical text)
    for m in re.finditer(r'\bin ([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,2})', wiki_body):
        place = _clean_place(m.group(1))
        if _is_valid_place(place):
            places.add(place)

    return list(places)


def ingest_person(person_name=None, wikipedia_url=None, api_key=None,
                  max_books=10, json_out=None, dry_run=False):
    """Full Google Books ingestion pipeline for a single person.

    Two-phase approach:
      Phase A — Extract new locations from general book search descriptions.
      Phase B — For places found in Wikipedia, search Books for corroborating
                book sources with date evidence.

    Returns the data dict (person + datapoints) or None on failure.
    """
    if not api_key:
        api_key = os.environ.get('GOOGLE_BOOKS_API_KEY')

    print(f"\n{'='*60}")
    print(f"Google Books Ingest: {person_name or wikipedia_url}")
    print(f"{'='*60}")

    # Step 1: Get person info from Wikipedia
    print("\n1. Fetching person info from Wikipedia...")
    wiki = fetch_page(person_name=person_name, url=wikipedia_url)
    if not wiki:
        print("   Could not fetch Wikipedia page.")
        return None

    name = wiki.get('name') or person_name
    print(f"   Name: {name}")

    # Build person data
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

    # Step 2: General book search — extract locations from descriptions
    print(f"\n2. Searching Google Books for '{name}'...")
    volumes = search_books(name, api_key=api_key, max_results=max_books)
    print(f"   Found {len(volumes)} volumes")

    # Log discoveries to book registry
    from ingest.free.book_registry import log_discovery, log_ingestion
    if volumes:
        for v in volumes[:5]:
            authors = ', '.join(v.get('authors', [])) or 'Unknown'
            print(f"   - {v['title']} ({authors})")
        for v in volumes:
            url = v.get('infoLink') or v.get('previewLink', '')
            log_discovery('google_books', name, v['title'],
                          ', '.join(v.get('authors', [])), url,
                          identifier=url)

    print("\n3. Extracting locations from book descriptions...")
    raw_results = extract_from_volumes(volumes, name)
    print(f"   Extracted {len(raw_results)} datapoints from descriptions")

    # Step 3: Place-targeted book search — find book sources for Wikipedia places
    wiki_places = _extract_wiki_places(wiki.get('body_text', ''), name)
    print(f"\n4. Searching books for {len(wiki_places)} places from Wikipedia...")

    seen_dedup = {(loc['place_name'].lower(), loc['date_start']) for loc, _ in raw_results}
    place_results = []

    for place in wiki_places[:15]:  # Cap API calls
        pvols = search_books_for_places(name, place, api_key=api_key)
        if not pvols:
            continue

        # Combine all text from place-specific volumes
        for vol in pvols:
            text = re.sub(r'<[^>]+>', '', (vol.get('description', '') + '\n' + vol.get('textSnippet', '')))
            if not text.strip():
                continue

            # Find dates near the place mention in this text
            for m in re.finditer(re.escape(place), text, re.I):
                date_str = _find_nearby_date(text, m.start(), m.end(), window=150)
                if not date_str:
                    continue
                ds, de, prec, display = resolve_date(date_str)
                if not ds:
                    continue

                dedup_key = (place.lower(), ds)
                if dedup_key in seen_dedup:
                    continue
                seen_dedup.add(dedup_key)

                source = _make_source(vol)
                loc = {
                    'place_name': place,
                    'date_start': ds,
                    'date_end': de or ds,
                    'date_precision': prec or 'year',
                    'date_display': display,
                    'description': f'{name} in {place}',
                    'confidence': 'possible',
                }
                place_results.append((loc, source))
                print(f"   {place} ({display}) — {vol['title']}")

    all_raw = raw_results + place_results
    print(f"\n   Total extracted: {len(all_raw)} datapoints")

    # Step 5: Geocode
    print("\n5. Geocoding locations...")
    from ingest.geocode import geocode
    all_datapoints = []

    for loc, source in all_raw:
        coords = geocode(loc['place_name'])
        if not coords:
            print(f"   Could not geocode: {loc['place_name']}")
            continue

        loc['latitude'] = coords[0]
        loc['longitude'] = coords[1]
        loc['sources'] = [source]
        all_datapoints.append(loc)

    # Final dedup
    seen = set()
    deduped = []
    for dp in all_datapoints:
        key = (dp['place_name'].lower(), dp['date_start'])
        if key not in seen:
            seen.add(key)
            deduped.append(dp)
    all_datapoints = deduped

    print(f"   Geocoded: {len(all_datapoints)} datapoints")

    # Update registry with results
    for v in volumes:
        url = v.get('infoLink') or v.get('previewLink', '')
        log_ingestion('google_books', identifier=url, method='pattern',
                      datapoints=len(all_datapoints), status='ingested')

    data = {'person': person_data, 'datapoints': all_datapoints}

    # Step 6: Export or import
    if json_out:
        print(f"\n6. Writing JSON to {json_out}...")
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, 'w') as f:
            json.dump(data, f, indent=2)
        print("   Done!")
    else:
        print("\n6. Importing into database...")
        from ingest.import_json import import_data
        import_data(data, dry_run=dry_run)

    return data


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ingest location data from Google Books API')
    parser.add_argument('--person', help='Person name to look up')
    parser.add_argument('--wikipedia-url', help='Wikipedia URL')
    parser.add_argument('--api-key', help='Google Books API key (or set GOOGLE_BOOKS_API_KEY)')
    parser.add_argument('--max-books', type=int, default=10, help='Max books to search (default 10)')
    parser.add_argument('--batch-file', help='Text file with one person name per line')
    parser.add_argument('--json-out', help='Export to JSON file instead of importing to DB')
    parser.add_argument('--dry-run', action='store_true', help='Validate without inserting')
    args = parser.parse_args()

    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"Batch ingesting {len(names)} persons from Google Books...")
        for name in names:
            try:
                ingest_person(person_name=name, api_key=args.api_key,
                              max_books=args.max_books, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    elif args.person or args.wikipedia_url:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            api_key=args.api_key,
            max_books=args.max_books,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )
    else:
        print("Specify --person or --wikipedia-url or --batch-file")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
