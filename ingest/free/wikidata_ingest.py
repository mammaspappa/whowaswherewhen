"""Strategy 1: Ingest historical figure location data from Wikidata SPARQL.

Zero dependencies beyond `requests` (already installed). Zero API keys.
Queries structured properties (birth/death place, residence, work location,
education, employer) with coordinates already included -- skips geocoding.
"""

import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

SPARQL_ENDPOINT = 'https://query.wikidata.org/sparql'
MEDIAWIKI_API = 'https://en.wikipedia.org/w/api.php'
WIKIDATA_API = 'https://www.wikidata.org/w/api.php'
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'wikidata_cache')
USER_AGENT = 'WhoWasWhereWhen/1.0 (https://github.com/whowaswherewhen; bot)'

_last_request_time = 0


def _rate_limit(min_interval=1.5):
    """Ensure minimum interval between SPARQL requests."""
    global _last_request_time
    now = time.time()
    wait = min_interval - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.time()


def _sparql_query(query):
    """Execute a SPARQL query against Wikidata and return results."""
    _rate_limit()
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={'query': query, 'format': 'json'},
        headers={'User-Agent': USER_AGENT, 'Accept': 'application/sparql-results+json'},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get('results', {}).get('bindings', [])


def resolve_to_qid(person_name=None, wikipedia_url=None, wikidata_id=None):
    """Resolve a person name, Wikipedia URL, or Wikidata ID to a QID.

    Returns (qid, label) tuple, or (None, None) if not found.
    """
    if wikidata_id:
        # Already have QID, just fetch label
        results = _sparql_query(f"""
            SELECT ?label WHERE {{
                wd:{wikidata_id} rdfs:label ?label .
                FILTER(LANG(?label) = "en")
            }} LIMIT 1
        """)
        label = results[0]['label']['value'] if results else wikidata_id
        return wikidata_id, label

    if wikipedia_url:
        # Extract title from URL
        match = re.search(r'wikipedia\.org/wiki/(.+?)(?:#|$|\?)', wikipedia_url)
        if not match:
            print(f"  Could not parse Wikipedia URL: {wikipedia_url}")
            return None, None
        title = match.group(1).replace('_', ' ')
    elif person_name:
        title = person_name
    else:
        return None, None

    # Use MediaWiki API to resolve to Wikidata QID
    resp = requests.get(MEDIAWIKI_API, params={
        'action': 'query',
        'titles': title,
        'prop': 'pageprops',
        'ppprop': 'wikibase_item',
        'format': 'json',
        'redirects': 1,
    }, headers={'User-Agent': USER_AGENT}, timeout=15)
    resp.raise_for_status()

    pages = resp.json().get('query', {}).get('pages', {})
    for page in pages.values():
        qid = page.get('pageprops', {}).get('wikibase_item')
        if qid:
            return qid, page.get('title', title)

    # Fallback: search Wikidata directly
    resp = requests.get(WIKIDATA_API, params={
        'action': 'wbsearchentities',
        'search': person_name or title,
        'language': 'en',
        'type': 'item',
        'limit': 1,
        'format': 'json',
    }, headers={'User-Agent': USER_AGENT}, timeout=15)
    resp.raise_for_status()

    results = resp.json().get('search', [])
    if results:
        return results[0]['id'], results[0].get('label', person_name or title)

    return None, None


def _parse_coord(coord_str):
    """Parse a WKT Point string like 'Point(11.25 43.7833)' to (lat, lon)."""
    match = re.match(r'Point\(([-\d.]+)\s+([-\d.]+)\)', coord_str)
    if match:
        lon, lat = float(match.group(1)), float(match.group(2))
        return lat, lon
    return None, None


def _parse_date(date_str):
    """Parse a Wikidata date string to (iso_date, precision_int).

    Wikidata dates look like: +1452-04-15T00:00:00Z or -0043-03-15T00:00:00Z
    """
    if not date_str:
        return None, None
    match = re.match(r'([+-]?\d+)-(\d{2})-(\d{2})T', date_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        # Format as ISO: use negative years for BCE
        if year < 0:
            iso = f"{year:05d}-{month:02d}-{day:02d}"
        else:
            iso = f"{year:04d}-{month:02d}-{day:02d}"
        return iso, None
    return None, None


def _format_date_display(iso_date, precision='year'):
    """Create a human-readable date from ISO date string."""
    if not iso_date:
        return ''
    match = re.match(r'(-?\d+)-(\d{2})-(\d{2})', iso_date)
    if not match:
        return iso_date
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']

    if year < 0:
        year_str = f"{abs(year)} BC"
    else:
        year_str = str(year)

    if precision == 'day' and 1 <= month <= 12:
        return f"{months[month]} {day}, {year_str}"
    elif precision == 'month' and 1 <= month <= 12:
        return f"{months[month]} {year_str}"
    else:
        return year_str


def _wikidata_precision_to_app(wikidata_precision):
    """Map Wikidata time precision to app's precision enum.

    Wikidata: 7=century, 8=decade, 9=year, 10=month, 11=day
    App: day, month, season, year, decade, approximate
    """
    mapping = {
        11: 'day',
        10: 'month',
        9: 'year',
        8: 'decade',
        7: 'approximate',  # century -> approximate
    }
    return mapping.get(wikidata_precision, 'year')


def fetch_person_data(qid):
    """Fetch basic person data (name, dates, description, image, Wikipedia URL) from Wikidata."""
    query = f"""
    SELECT ?personLabel ?personDescription ?birthDate ?deathDate
           ?image ?article
    WHERE {{
        BIND(wd:{qid} AS ?person)
        OPTIONAL {{ ?person wdt:P569 ?birthDate . }}
        OPTIONAL {{ ?person wdt:P570 ?deathDate . }}
        OPTIONAL {{ ?person wdt:P18 ?image . }}
        OPTIONAL {{
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
        }}
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
        }}
    }} LIMIT 1
    """
    results = _sparql_query(query)
    if not results:
        return None

    r = results[0]
    name = r.get('personLabel', {}).get('value', '')
    description = r.get('personDescription', {}).get('value', '')
    birth_iso, _ = _parse_date(r.get('birthDate', {}).get('value', ''))
    death_iso, _ = _parse_date(r.get('deathDate', {}).get('value', ''))
    image_url = r.get('image', {}).get('value')
    wiki_url = r.get('article', {}).get('value')

    return {
        'name': name,
        'description': description,
        'birth_date_start': birth_iso,
        'birth_date_end': birth_iso,
        'birth_date_display': _format_date_display(birth_iso, 'year'),
        'death_date_start': death_iso,
        'death_date_end': death_iso,
        'death_date_display': _format_date_display(death_iso, 'year'),
        'image_url': image_url,
        'wikipedia_url': wiki_url,
    }


def fetch_birth_death_places(qid):
    """Fetch birth and death places with coordinates."""
    query = f"""
    SELECT ?birthPlaceLabel ?birthCoord ?birthDate
           ?deathPlaceLabel ?deathCoord ?deathDate
    WHERE {{
        BIND(wd:{qid} AS ?person)
        OPTIONAL {{
            ?person wdt:P19 ?birthPlace .
            ?birthPlace wdt:P625 ?birthCoord .
        }}
        OPTIONAL {{ ?person wdt:P569 ?birthDate . }}
        OPTIONAL {{
            ?person wdt:P20 ?deathPlace .
            ?deathPlace wdt:P625 ?deathCoord .
        }}
        OPTIONAL {{ ?person wdt:P570 ?deathDate . }}
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
        }}
    }} LIMIT 1
    """
    results = _sparql_query(query)
    if not results:
        return []

    datapoints = []
    r = results[0]

    # Birth place
    birth_coord = r.get('birthCoord', {}).get('value', '')
    birth_place = r.get('birthPlaceLabel', {}).get('value', '')
    birth_date_raw = r.get('birthDate', {}).get('value', '')
    if birth_coord and birth_place:
        lat, lon = _parse_coord(birth_coord)
        birth_iso, _ = _parse_date(birth_date_raw)
        if lat is not None and birth_iso:
            datapoints.append({
                'place_name': birth_place,
                'latitude': lat,
                'longitude': lon,
                'date_start': birth_iso,
                'date_end': birth_iso,
                'date_precision': 'year',
                'date_display': _format_date_display(birth_iso, 'year'),
                'description': f'Born in {birth_place}',
                'confidence': 'certain',
                'sources': [{'title': f'Wikidata: {qid}', 'url': f'https://www.wikidata.org/wiki/{qid}', 'source_type': 'webpage'}],
            })

    # Death place
    death_coord = r.get('deathCoord', {}).get('value', '')
    death_place = r.get('deathPlaceLabel', {}).get('value', '')
    death_date_raw = r.get('deathDate', {}).get('value', '')
    if death_coord and death_place:
        lat, lon = _parse_coord(death_coord)
        death_iso, _ = _parse_date(death_date_raw)
        if lat is not None and death_iso:
            datapoints.append({
                'place_name': death_place,
                'latitude': lat,
                'longitude': lon,
                'date_start': death_iso,
                'date_end': death_iso,
                'date_precision': 'year',
                'date_display': _format_date_display(death_iso, 'year'),
                'description': f'Died in {death_place}',
                'confidence': 'certain',
                'sources': [{'title': f'Wikidata: {qid}', 'url': f'https://www.wikidata.org/wiki/{qid}', 'source_type': 'webpage'}],
            })

    return datapoints


def fetch_residences(qid):
    """Fetch residences (P551) with coordinates and optional time qualifiers."""
    query = f"""
    SELECT ?placeLabel ?coord ?startDate ?endDate
    WHERE {{
        wd:{qid} p:P551 ?stmt .
        ?stmt ps:P551 ?place .
        ?place wdt:P625 ?coord .
        OPTIONAL {{ ?stmt pq:P580 ?startDate . }}
        OPTIONAL {{ ?stmt pq:P582 ?endDate . }}
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
        }}
    }}
    """
    return _process_location_results(_sparql_query(query), qid, 'Resided in')


def fetch_work_locations(qid):
    """Fetch work locations (P937) with coordinates and optional time qualifiers."""
    query = f"""
    SELECT ?placeLabel ?coord ?startDate ?endDate
    WHERE {{
        wd:{qid} p:P937 ?stmt .
        ?stmt ps:P937 ?place .
        ?place wdt:P625 ?coord .
        OPTIONAL {{ ?stmt pq:P580 ?startDate . }}
        OPTIONAL {{ ?stmt pq:P582 ?endDate . }}
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
        }}
    }}
    """
    return _process_location_results(_sparql_query(query), qid, 'Worked in')


def fetch_education_locations(qid):
    """Fetch education locations (P69 -> institution's coordinates)."""
    query = f"""
    SELECT ?institutionLabel ?coord ?startDate ?endDate
    WHERE {{
        wd:{qid} p:P69 ?stmt .
        ?stmt ps:P69 ?institution .
        ?institution wdt:P625 ?coord .
        OPTIONAL {{ ?stmt pq:P580 ?startDate . }}
        OPTIONAL {{ ?stmt pq:P582 ?endDate . }}
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
        }}
    }}
    """
    return _process_location_results(_sparql_query(query), qid, 'Studied at')


def fetch_employer_locations(qid):
    """Fetch employer locations (P108 -> employer's P625 or P159 HQ location)."""
    query = f"""
    SELECT ?employerLabel ?coord ?startDate ?endDate
    WHERE {{
        wd:{qid} p:P108 ?stmt .
        ?stmt ps:P108 ?employer .
        {{
            ?employer wdt:P625 ?coord .
        }} UNION {{
            ?employer wdt:P159 ?hq .
            ?hq wdt:P625 ?coord .
        }}
        OPTIONAL {{ ?stmt pq:P580 ?startDate . }}
        OPTIONAL {{ ?stmt pq:P582 ?endDate . }}
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
        }}
    }}
    """
    return _process_location_results(_sparql_query(query), qid, 'Employed at')


def _process_location_results(results, qid, description_prefix):
    """Convert SPARQL location results to datapoint dicts."""
    datapoints = []
    seen = set()

    for r in results:
        place = r.get('placeLabel', r.get('institutionLabel', r.get('employerLabel', {}))).get('value', '')
        coord = r.get('coord', {}).get('value', '')
        if not place or not coord:
            continue

        lat, lon = _parse_coord(coord)
        if lat is None:
            continue

        start_raw = r.get('startDate', {}).get('value', '')
        end_raw = r.get('endDate', {}).get('value', '')
        start_iso, _ = _parse_date(start_raw)
        end_iso, _ = _parse_date(end_raw)

        # Determine precision and display
        if start_iso and end_iso:
            precision = 'year'
            display = f"{_format_date_display(start_iso)} - {_format_date_display(end_iso)}"
        elif start_iso:
            precision = 'year'
            end_iso = start_iso
            display = _format_date_display(start_iso)
        elif end_iso:
            precision = 'year'
            start_iso = end_iso
            display = _format_date_display(end_iso)
        else:
            # No dates available -- use approximate
            precision = 'approximate'
            start_iso = ''
            end_iso = ''
            display = 'Unknown dates'

        # Skip if no dates at all (can't insert without date_start)
        if not start_iso:
            continue

        # Dedup within this query
        key = (place, start_iso)
        if key in seen:
            continue
        seen.add(key)

        datapoints.append({
            'place_name': place,
            'latitude': lat,
            'longitude': lon,
            'date_start': start_iso,
            'date_end': end_iso,
            'date_precision': precision,
            'date_display': display,
            'description': f'{description_prefix} {place}',
            'confidence': 'probable',
            'sources': [{'title': f'Wikidata: {qid}', 'url': f'https://www.wikidata.org/wiki/{qid}', 'source_type': 'webpage'}],
            'extraction_method': 'wikidata',
            'created_by': 'system',
            'raw_date_text': start_raw or end_raw or None,
            'raw_place_text': r.get('placeLabel', {}).get('value'),
            'geocode_source': 'wikidata',
        })

    return datapoints


def _load_cache(qid):
    """Load cached Wikidata results for a QID."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f'{qid}.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_cache(qid, data):
    """Cache Wikidata results for a QID."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f'{qid}.json')
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def ingest_person(person_name=None, wikipedia_url=None, wikidata_id=None,
                  json_out=None, dry_run=False):
    """Full Wikidata ingestion pipeline for a single person.

    Returns the data dict (person + datapoints) or None on failure.
    """
    print(f"\n{'='*60}")
    print(f"Wikidata Ingest: {person_name or wikipedia_url or wikidata_id}")
    print(f"{'='*60}")

    # Step 1: Resolve to QID
    print("\n1. Resolving to Wikidata QID...")
    qid, label = resolve_to_qid(person_name, wikipedia_url, wikidata_id)
    if not qid:
        print("   Could not resolve to a Wikidata entity.")
        return None
    print(f"   Found: {label} ({qid})")

    # Check cache
    cached = _load_cache(qid)
    if cached:
        print("   Using cached data.")
        data = cached
    else:
        # Step 2: Fetch person data
        print("\n2. Fetching person data...")
        person_data = fetch_person_data(qid)
        if not person_data:
            print("   Could not fetch person data.")
            return None
        print(f"   Name: {person_data['name']}")
        print(f"   Description: {(person_data.get('description') or '')[:100]}")

        # Step 3: Fetch all location properties
        print("\n3. Fetching locations...")
        all_datapoints = []

        print("   Querying birth/death places...")
        all_datapoints.extend(fetch_birth_death_places(qid))

        print("   Querying residences (P551)...")
        all_datapoints.extend(fetch_residences(qid))

        print("   Querying work locations (P937)...")
        all_datapoints.extend(fetch_work_locations(qid))

        print("   Querying education locations (P69)...")
        all_datapoints.extend(fetch_education_locations(qid))

        print("   Querying employer locations (P108)...")
        all_datapoints.extend(fetch_employer_locations(qid))

        print(f"\n   Total: {len(all_datapoints)} location datapoints")

        # Deduplicate across property groups
        seen = set()
        deduped = []
        for dp in all_datapoints:
            key = (dp['place_name'], dp['date_start'])
            if key not in seen:
                seen.add(key)
                deduped.append(dp)
        all_datapoints = deduped
        print(f"   After dedup: {len(all_datapoints)} unique datapoints")

        data = {'person': person_data, 'datapoints': all_datapoints}
        _save_cache(qid, data)

    # Step 4: Export or import
    if json_out:
        print(f"\n4. Writing JSON to {json_out}...")
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, 'w') as f:
            json.dump(data, f, indent=2)
        print("   Done!")
    else:
        print("\n4. Importing into database...")
        from ingest.import_json import import_data
        import_data(data, dry_run=dry_run)

    return data


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ingest from Wikidata SPARQL (free, no API key)')
    parser.add_argument('--person', help='Person name to look up')
    parser.add_argument('--wikipedia-url', help='Wikipedia URL')
    parser.add_argument('--wikidata-id', help='Wikidata QID (e.g. Q762)')
    parser.add_argument('--batch-file', help='Text file with one person name per line')
    parser.add_argument('--json-out', help='Export to JSON file instead of importing to DB')
    parser.add_argument('--dry-run', action='store_true', help='Validate without inserting')
    args = parser.parse_args()

    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"Batch ingesting {len(names)} persons from Wikidata...")
        for name in names:
            try:
                ingest_person(person_name=name, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    elif args.person:
        ingest_person(person_name=args.person, json_out=args.json_out, dry_run=args.dry_run)
    elif args.wikipedia_url:
        ingest_person(wikipedia_url=args.wikipedia_url, json_out=args.json_out, dry_run=args.dry_run)
    elif args.wikidata_id:
        ingest_person(wikidata_id=args.wikidata_id, json_out=args.json_out, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
