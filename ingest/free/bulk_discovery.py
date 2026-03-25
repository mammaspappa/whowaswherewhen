"""Strategy 5: Bulk discovery of historical figures via Wikidata SPARQL.

Discovers hundreds of historical figures matching criteria (era, place,
occupation, fame level) and ingests their location data via the Wikidata
strategy. Zero dependencies, zero API keys.
"""

import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ingest.free.wikidata_ingest import (
    SPARQL_ENDPOINT, USER_AGENT, ingest_person, _rate_limit
)

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'bulk_progress.json')

# Predefined SPARQL queries for discovering historical figures
PRESET_QUERIES = {
    # famous-historical uses a curated seed list (see FAMOUS_HISTORICAL_QIDS)
    # to avoid expensive wikibase:sitelinks queries that timeout on Wikidata.
    'famous-historical': None,

    'explorers': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 ?occ ;
                    wdt:P19 ?birthPlace .
            VALUES ?occ {{ wd:Q11900058 wd:Q1402561 wd:Q16271011 wd:Q3089225 }}
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,

    'scientists': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 ?occ ;
                    wdt:P569 ?birthDate ;
                    wdt:P19 ?birthPlace .
            VALUES ?occ {{ wd:Q901 wd:Q169470 wd:Q593644 wd:Q81096 }}
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            FILTER(YEAR(?birthDate) < 1950)
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,

    'artists': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 ?occ ;
                    wdt:P569 ?birthDate ;
                    wdt:P19 ?birthPlace .
            VALUES ?occ {{ wd:Q1028181 wd:Q33231 wd:Q1281618 }}
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            FILTER(YEAR(?birthDate) < 1950)
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,

    'composers': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 wd:Q36834 ;
                    wdt:P19 ?birthPlace .
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,

    'military-leaders': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 ?occ ;
                    wdt:P569 ?birthDate ;
                    wdt:P19 ?birthPlace .
            VALUES ?occ {{ wd:Q47064 wd:Q189290 wd:Q82955 }}
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            FILTER(YEAR(?birthDate) < 1950)
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,

    'philosophers': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 wd:Q4964182 ;
                    wdt:P19 ?birthPlace .
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,

    'writers': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 ?occ ;
                    wdt:P569 ?birthDate ;
                    wdt:P19 ?birthPlace .
            VALUES ?occ {{ wd:Q36180 wd:Q49757 wd:Q6625963 }}
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            FILTER(YEAR(?birthDate) < 1950)
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,

    'monarchs': """
        SELECT DISTINCT ?person ?personLabel ?article WHERE {{
            ?person wdt:P31 wd:Q5 ;
                    wdt:P106 ?occ ;
                    wdt:P19 ?birthPlace .
            VALUES ?occ {{ wd:Q116 wd:Q12097 wd:Q39018 }}
            ?article schema:about ?person ;
                     schema:isPartOf <https://en.wikipedia.org/> .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }}
        LIMIT {limit}
    """,
}

# Dynamic query for custom criteria (no sitelinks — use occupation + en-wiki as fame proxy)
CUSTOM_QUERY = """
    SELECT DISTINCT ?person ?personLabel ?article WHERE {{
        ?person wdt:P31 wd:Q5 .
        {occupation_filter}
        ?person wdt:P569 ?birthDate .
        ?person wdt:P19 ?birthPlace .
        {place_filter}
        ?article schema:about ?person ;
                 schema:isPartOf <https://en.wikipedia.org/> .
        {date_filter}
        SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
"""

# Map common occupation names to Wikidata QIDs
OCCUPATION_QIDS = {
    'explorer': 'wd:Q11900058',
    'scientist': 'wd:Q901',
    'physicist': 'wd:Q169470',
    'mathematician': 'wd:Q170790',
    'composer': 'wd:Q36834',
    'painter': 'wd:Q1028181',
    'sculptor': 'wd:Q1281618',
    'writer': 'wd:Q36180',
    'poet': 'wd:Q49757',
    'philosopher': 'wd:Q4964182',
    'architect': 'wd:Q42973',
    'general': 'wd:Q189290',
    'monarch': 'wd:Q116',
    'politician': 'wd:Q82955',
    'astronomer': 'wd:Q11063',
    'inventor': 'wd:Q205375',
}

# Map country names to Wikidata QIDs for place filtering
COUNTRY_QIDS = {
    'italy': 'wd:Q38',
    'france': 'wd:Q142',
    'germany': 'wd:Q183',
    'england': 'wd:Q21',
    'united kingdom': 'wd:Q145',
    'spain': 'wd:Q29',
    'greece': 'wd:Q41',
    'china': 'wd:Q148',
    'japan': 'wd:Q17',
    'india': 'wd:Q668',
    'russia': 'wd:Q159',
    'egypt': 'wd:Q79',
    'turkey': 'wd:Q43',
    'netherlands': 'wd:Q55',
    'austria': 'wd:Q40',
    'poland': 'wd:Q36',
    'portugal': 'wd:Q45',
    'sweden': 'wd:Q34',
    'united states': 'wd:Q30',
}

# Curated seed list for 'famous-historical' — avoids expensive SPARQL sitelinks queries.
# Each person is ingested individually via their QID.
FAMOUS_HISTORICAL_QIDS = [
    # Ancient world
    ('Q859', 'Plato'), ('Q868', 'Aristotle'), ('Q913', 'Socrates'),
    ('Q8409', 'Alexander the Great'), ('Q635', 'Cleopatra'),
    ('Q1048', 'Julius Caesar'), ('Q1405', 'Augustus'),
    ('Q4604', 'Confucius'), ('Q8739', 'Archimedes'),
    ('Q8747', 'Euclid'), ('Q37151', 'Sun Tzu'), ('Q9333', 'Lao Tzu'),
    # Medieval & Renaissance
    ('Q720', 'Genghis Khan'), ('Q36724', 'Attila'),
    ('Q6101', 'Marco Polo'), ('Q762', 'Leonardo da Vinci'),
    ('Q5597', 'Raphael'), ('Q5598', 'Rembrandt'),
    ('Q5592', 'Michelangelo'), ('Q307', 'Galileo Galilei'),
    ('Q8958', 'Johannes Gutenberg'), ('Q692', 'William Shakespeare'),
    ('Q9554', 'Martin Luther'), ('Q619', 'Nicolaus Copernicus'),
    ('Q1067', 'Dante Alighieri'), ('Q7322', 'Christopher Columbus'),
    ('Q1399', 'Niccolò Machiavelli'), ('Q7226', 'Joan of Arc'),
    ('Q8474', 'Suleiman the Magnificent'),
    # Early modern
    ('Q935', 'Isaac Newton'), ('Q255', 'Ludwig van Beethoven'),
    ('Q254', 'Wolfgang Amadeus Mozart'), ('Q9068', 'Voltaire'),
    ('Q535', 'Victor Hugo'), ('Q5879', 'Johann Wolfgang von Goethe'),
    ('Q9312', 'Immanuel Kant'), ('Q9191', 'René Descartes'),
    ('Q517', 'Napoleon'), ('Q9439', 'Queen Victoria'),
    ('Q1035', 'Charles Darwin'), ('Q8750', 'Michael Faraday'),
    ('Q41264', 'Johannes Vermeer'), ('Q1339', 'Johann Sebastian Bach'),
    ('Q1268', 'Frédéric Chopin'), ('Q1511', 'Richard Wagner'),
    # 18th-19th century
    ('Q23', 'George Washington'), ('Q91', 'Abraham Lincoln'),
    ('Q34969', 'Benjamin Franklin'), ('Q7245', 'Mark Twain'),
    ('Q7243', 'Leo Tolstoy'), ('Q991', 'Fyodor Dostoevsky'),
    ('Q9036', 'Nikola Tesla'), ('Q5686', 'Charles Dickens'),
    ('Q7186', 'Marie Curie'), ('Q37103', 'Florence Nightingale'),
    ('Q9061', 'Karl Marx'), ('Q9215', 'Sigmund Freud'),
    ('Q8605', 'Simón Bolívar'), ('Q8743', 'Thomas Edison'),
    ('Q5582', 'Vincent van Gogh'), ('Q296', 'Claude Monet'),
    ('Q529', 'Louis Pasteur'), ('Q7315', 'Pyotr Ilyich Tchaikovsky'),
    ('Q1001', 'Mahatma Gandhi'), ('Q7241', 'Rabindranath Tagore'),
    ('Q8023', 'Nelson Mandela'),
]


def _load_progress():
    """Load bulk progress tracking file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {'processed': [], 'failed': []}


def _save_progress(progress):
    """Save bulk progress tracking file."""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def _run_sparql(query_text, timeout=90):
    """Execute a single SPARQL query and return bindings list, or None on error."""
    _rate_limit(2.0)
    try:
        resp = requests.get(
            SPARQL_ENDPOINT,
            params={'query': query_text, 'format': 'json'},
            headers={'User-Agent': USER_AGENT, 'Accept': 'application/sparql-results+json'},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get('results', {}).get('bindings', [])
    except Exception as e:
        print(f"  SPARQL query error: {e}")
        return None


def _parse_persons(results):
    """Extract (qid, label) pairs from SPARQL bindings."""
    persons = []
    seen = set()
    for r in results:
        person_uri = r.get('person', {}).get('value', '')
        qid = person_uri.split('/')[-1] if person_uri else ''
        label = r.get('personLabel', {}).get('value', '')
        if qid and qid.startswith('Q') and qid not in seen:
            seen.add(qid)
            persons.append((qid, label))
    return persons


def discover_persons(query_text, limit=100):
    """Run a SPARQL discovery query and return list of (qid, label) tuples.

    If the query times out, automatically retries with smaller century-based
    chunks to avoid Wikidata's query timeout limits.
    """
    results = _run_sparql(query_text, timeout=90)
    if results is not None:
        return _parse_persons(results)

    # Timeout or error — try chunked approach by century
    print("  Retrying with century-based chunking...")
    century_ranges = [
        (1800, 1900), (1700, 1800), (1600, 1700), (1500, 1600),
        (1400, 1500), (1200, 1400), (1000, 1200), (None, 1000),
    ]
    all_persons = []
    seen = set()
    remaining = limit

    for born_after, born_before in century_ranges:
        if remaining <= 0:
            break

        # Inject a narrower date filter into the query
        chunk_query = query_text
        if born_after is not None and born_before is not None:
            # Replace broad date filter with narrow century range
            chunk_query = _narrow_date_filter(query_text, born_after, born_before, remaining)
        elif born_before is not None:
            chunk_query = _narrow_date_filter(query_text, None, born_before, remaining)

        if chunk_query is None:
            continue

        label = f"{born_after or '???'}-{born_before}" if born_before else "all"
        print(f"    Chunk {label}...", end=" ", flush=True)
        results = _run_sparql(chunk_query, timeout=60)
        if results is None:
            print("timeout, skipping")
            continue

        chunk_persons = _parse_persons(results)
        new_count = 0
        for qid, name in chunk_persons:
            if qid not in seen:
                seen.add(qid)
                all_persons.append((qid, name))
                new_count += 1
                remaining -= 1
                if remaining <= 0:
                    break
        print(f"found {new_count}")

    return all_persons


import re

def _narrow_date_filter(query_text, born_after, born_before, limit):
    """Rewrite a SPARQL query to use a narrower date range and limit.

    Returns the rewritten query, or None if the query doesn't have a
    recognizable date filter to replace.
    """
    new_query = query_text

    # Replace existing YEAR filters on birthDate
    new_query = re.sub(
        r'FILTER\s*\(\s*YEAR\s*\(\s*\?birthDate\s*\)\s*[<>]=?\s*\d+\s*\)',
        '',
        new_query
    )

    # Build new date filters
    date_filters = []
    if born_after is not None:
        date_filters.append(f'FILTER(YEAR(?birthDate) >= {born_after})')
    if born_before is not None:
        date_filters.append(f'FILTER(YEAR(?birthDate) < {born_before})')

    # Insert before SERVICE clause
    if date_filters:
        filter_text = '\n            '.join(date_filters)
        new_query = re.sub(
            r'(SERVICE\s+wikibase:label)',
            filter_text + r'\n            \1',
            new_query
        )

    # Replace LIMIT
    new_query = re.sub(r'LIMIT\s+\d+', f'LIMIT {limit}', new_query)

    return new_query


def _get_existing_names(db_path=None):
    """Get set of person names already in the database."""
    import sqlite3
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'wwww.db')
    if not os.path.exists(db_path):
        return set()
    db = sqlite3.connect(db_path)
    names = {r[0].lower() for r in db.execute("SELECT name FROM persons").fetchall()}
    db.close()
    return names


def bulk_ingest(preset=None, occupation=None, born_in=None,
                born_after=None, born_before=None, min_sitelinks=20,
                limit=100, resume=False, dry_run=False, augment=False):
    """Discover and ingest multiple historical figures."""
    print(f"\n{'='*60}")
    print(f"Bulk Discovery")
    print(f"{'='*60}")

    # Build query or use seed list
    use_seed_list = False
    if preset:
        if preset not in PRESET_QUERIES:
            print(f"Unknown preset: {preset}")
            print(f"Available: {', '.join(sorted(PRESET_QUERIES.keys()))}")
            return
        print(f"\nPreset: {preset} (limit {limit})")
        if PRESET_QUERIES[preset] is None:
            # Seed-list based preset (e.g. famous-historical)
            use_seed_list = True
            query = None
        else:
            query = PRESET_QUERIES[preset].format(limit=limit)
    else:
        # Build custom query
        occupation_filter = ''
        if occupation:
            occ_qid = OCCUPATION_QIDS.get(occupation.lower())
            if occ_qid:
                occupation_filter = f'?person wdt:P106 {occ_qid} .'
            else:
                print(f"Unknown occupation: {occupation}")
                print(f"Available: {', '.join(sorted(OCCUPATION_QIDS.keys()))}")
                return

        place_filter = ''
        if born_in:
            country_qid = COUNTRY_QIDS.get(born_in.lower())
            if country_qid:
                place_filter = f'?birthPlace wdt:P131* {country_qid} .'
            else:
                print(f"Unknown country: {born_in}")
                print(f"Available: {', '.join(sorted(COUNTRY_QIDS.keys()))}")
                return

        date_filter = ''
        if born_after or born_before:
            parts = []
            if born_after:
                parts.append(f'FILTER(YEAR(?birthDate) > {born_after})')
            if born_before:
                parts.append(f'FILTER(YEAR(?birthDate) < {born_before})')
            date_filter = '\n        '.join(parts)

        query = CUSTOM_QUERY.format(
            occupation_filter=occupation_filter,
            place_filter=place_filter,
            date_filter=date_filter,
            limit=limit,
        )
        print(f"\nCustom query: occupation={occupation}, born_in={born_in}, "
              f"born_after={born_after}, born_before={born_before}")

    # Load progress
    progress = _load_progress() if resume else {'processed': [], 'failed': []}
    processed_qids = set(progress['processed'])

    # Discover persons
    if use_seed_list:
        print("\n1. Using curated seed list...")
        # Deduplicate the seed list and respect the limit
        seen = set()
        persons = []
        for qid, label in FAMOUS_HISTORICAL_QIDS:
            if qid not in seen:
                seen.add(qid)
                persons.append((qid, label))
            if len(persons) >= limit:
                break
        print(f"   {len(persons)} persons in seed list (limit {limit})")
    else:
        print("\n1. Discovering persons via SPARQL...")
        persons = discover_persons(query, limit)
        print(f"   Found {len(persons)} persons")

    if not persons:
        print("   No results. Try adjusting your criteria.")
        return

    # Filter out already-processed and optionally already-in-DB
    existing_names = _get_existing_names()
    to_process = []
    skipped_existing = 0
    skipped_processed = 0

    for qid, label in persons:
        if qid in processed_qids:
            skipped_processed += 1
            continue
        if not augment and label.lower() in existing_names:
            skipped_existing += 1
            continue
        to_process.append((qid, label))

    mode = "augment" if augment else "skip"
    print(f"   To process: {len(to_process)} (existing-in-DB: {skipped_existing} "
          f"{'skipped' if not augment else 're-processed'}, "
          f"{skipped_processed} already processed)")
    print(f"   Mode: {mode} existing persons")

    if dry_run:
        print("\n  [DRY RUN] Would process:")
        for qid, label in to_process[:20]:
            print(f"    - {label} ({qid})")
        if len(to_process) > 20:
            print(f"    ... and {len(to_process) - 20} more")
        return

    # Process each person
    print(f"\n2. Ingesting {len(to_process)} persons...")
    success = 0
    failed = 0

    for i, (qid, label) in enumerate(to_process):
        print(f"\n--- [{i+1}/{len(to_process)}] {label} ({qid}) ---")
        try:
            result = ingest_person(wikidata_id=qid)
            if result:
                success += 1
                progress['processed'].append(qid)
            else:
                failed += 1
                progress['failed'].append(qid)
        except Exception as e:
            print(f"  Error: {e}")
            failed += 1
            progress['failed'].append(qid)

        # Save progress periodically
        if (i + 1) % 5 == 0:
            _save_progress(progress)

    _save_progress(progress)

    print(f"\n{'='*60}")
    print(f"Bulk Discovery Complete")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print(f"  Skipped (existing): {skipped_existing}")
    print(f"  Progress saved to: {PROGRESS_FILE}")
    print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Bulk discover and ingest historical figures from Wikidata')
    parser.add_argument('--preset', choices=sorted(PRESET_QUERIES.keys()),
                        help='Use a predefined query preset')
    parser.add_argument('--occupation', help=f'Filter by occupation ({", ".join(sorted(OCCUPATION_QIDS.keys())[:5])}...)')
    parser.add_argument('--born-in', help=f'Filter by birth country ({", ".join(sorted(COUNTRY_QIDS.keys())[:5])}...)')
    parser.add_argument('--born-after', type=int, help='Born after year (e.g. 1400)')
    parser.add_argument('--born-before', type=int, help='Born before year (e.g. 1600)')
    parser.add_argument('--min-sitelinks', type=int, default=20,
                        help='Minimum Wikipedia sitelinks (fame threshold, default 20)')
    parser.add_argument('--limit', type=int, default=100, help='Max persons to discover (default 100)')
    parser.add_argument('--resume', action='store_true', help='Resume from last progress checkpoint')
    parser.add_argument('--augment', action='store_true',
                        help='Re-process persons already in DB to add new datapoints (default: skip)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without ingesting')
    args = parser.parse_args()

    if not args.preset and not args.occupation and not args.born_in:
        print("Specify --preset or at least one filter (--occupation, --born-in, --born-after, --born-before)")
        print(f"\nAvailable presets: {', '.join(sorted(PRESET_QUERIES.keys()))}")
        parser.print_help()
        sys.exit(1)

    bulk_ingest(
        preset=args.preset,
        occupation=args.occupation,
        born_in=args.born_in,
        born_after=args.born_after,
        born_before=args.born_before,
        min_sitelinks=args.min_sitelinks,
        limit=args.limit,
        resume=args.resume,
        dry_run=args.dry_run,
        augment=args.augment,
    )


if __name__ == '__main__':
    main()
