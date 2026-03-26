"""Import notable people from the cross-verified database (Nature Scientific Data).

Source: "A cross-verified database of notable people, 3500BC-2018AD"
        https://doi.org/10.1038/s41597-022-01369-4
        Download: https://data.sciencespo.fr (search for doi:10.21410/7E4/RDAG3O)

The dataset contains ~2.29M notable individuals with birth/death coordinates.
This script imports the top-N most notable people (by visibility ranking)
who aren't already in our database, creating birth and death whereabouts.

Usage:
    .venv/bin/python -m ingest.import_crossverified path/to/cross-verified-database.csv.gz --top 500
    .venv/bin/python -m ingest.import_crossverified data/cross-verified-database.csv.gz --top 1000 --dry-run
"""

import argparse
import csv
import gzip
import math
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'wwww.db')


def _parse_year(val):
    """Parse a year value (may be negative for BCE). Returns int or None."""
    if val is None or val == '' or (isinstance(val, float) and math.isnan(val)):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _year_to_iso(year):
    """Convert a year int to ISO date string."""
    if year is None:
        return None
    if year < 0:
        return f"-{abs(year):04d}-01-01"
    return f"{year:04d}-01-01"


def _year_to_display(year):
    """Convert a year int to human-readable string."""
    if year is None:
        return None
    if year < 0:
        return f"{abs(year)} BC"
    return str(year)


def _reverse_geocode_approx(lat, lon):
    """Rough reverse geocode using Nominatim. Returns place name or coords string."""
    import requests
    import time
    try:
        time.sleep(1.1)  # Rate limit
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lon, 'format': 'json', 'zoom': 10},
            headers={'User-Agent': 'WhoWasWhereWhen/1.0'},
            timeout=10,
        )
        data = resp.json()
        addr = data.get('address', {})
        city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('hamlet')
        country = addr.get('country')
        if city and country:
            return f"{city}, {country}"
        if country:
            return country
        return data.get('display_name', f"{lat:.2f}, {lon:.2f}")[:100]
    except Exception:
        return f"{lat:.2f}, {lon:.2f}"


def import_crossverified(csv_path, top_n=500, dry_run=False, reverse_geocode=False,
                         min_wiki_editions=5):
    """Import top-N most notable people from the cross-verified database.

    Args:
        csv_path: Path to cross-verified-database.csv.gz
        top_n: Number of people to import (by visibility ranking)
        dry_run: If True, don't actually insert
        reverse_geocode: If True, reverse-geocode coordinates to place names (slow!)
        min_wiki_editions: Minimum number of Wikipedia editions to consider
    """
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    # Get existing person names for dedup
    existing_names = {row[0].lower() for row in
                      db.execute("SELECT name FROM persons").fetchall()}
    print(f"Existing persons: {len(existing_names)}")

    # Read and sort by visibility ranking
    print(f"Reading {csv_path}...")
    people = []
    opener = gzip.open if csv_path.endswith('.gz') else open
    with opener(csv_path, 'rt', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        print(f"Columns: {len(columns)}")
        print(f"Column names: {', '.join(columns[:15])}...")

        # Check if place name columns exist
        has_place_names = 'birthplace_name' in columns

        for row in reader:
            # Must have a name
            name = (row.get('name') or '').strip()
            if not name:
                continue

            # Skip if already in our DB
            if name.lower() in existing_names:
                continue

            # Must have at least some geo data
            bpla = row.get('bpla1', '')
            bplo = row.get('bplo1', '')
            dpla = row.get('dpla1', '')
            dplo = row.get('dplo1', '')
            has_birth_geo = bpla and bplo and bpla != 'NA' and bplo != 'NA'
            has_death_geo = dpla and dplo and dpla != 'NA' and dplo != 'NA'
            if not has_birth_geo and not has_death_geo:
                continue

            # Filter by number of Wikipedia editions
            n_editions = _parse_year(row.get('number_wiki_editions', '0')) or 0
            if n_editions < min_wiki_editions:
                continue

            # Parse visibility ranking (lower = more notable)
            ranking = None
            try:
                ranking = float(row.get('ranking_visib_5criteria', '999999'))
            except (ValueError, TypeError):
                ranking = 999999

            people.append({
                'name': name,
                'wikidata_code': row.get('wikidata_code', ''),
                'birth': _parse_year(row.get('birth')),
                'death': _parse_year(row.get('death')),
                'gender': row.get('gender', ''),
                'occupation': row.get('level2_main_occ', '') or row.get('level1_main_occ', ''),
                'citizenship': row.get('citizenship_1_b', ''),
                'birth_lat': float(bpla) if has_birth_geo else None,
                'birth_lon': float(bplo) if has_birth_geo else None,
                'death_lat': float(dpla) if has_death_geo else None,
                'death_lon': float(dplo) if has_death_geo else None,
                'birthplace_name': row.get('birthplace_name', '') if has_place_names else '',
                'deathplace_name': row.get('deathplace_name', '') if has_place_names else '',
                'ranking': ranking,
                'n_editions': n_editions,
            })

    # Sort by ranking (most notable first)
    people.sort(key=lambda p: p['ranking'])
    total_available = len(people)
    people = people[:top_n]

    print(f"Found {total_available} importable people (not in DB, with geo data)")
    print(f"Importing top {len(people)} by visibility ranking")
    if people:
        print(f"  Most notable: {people[0]['name']} (ranking {people[0]['ranking']:.0f})")
        print(f"  Least notable: {people[-1]['name']} (ranking {people[-1]['ranking']:.0f})")
        print(f"  Has place names in CSV: {has_place_names}")

    inserted_persons = 0
    inserted_whereabouts = 0
    geocoded = 0

    for i, p in enumerate(people):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(people)}...")

        # Build description from occupation and citizenship
        desc_parts = []
        if p['occupation']:
            desc_parts.append(p['occupation'].replace('_', ' ').title())
        if p['citizenship']:
            desc_parts.append(p['citizenship'])
        description = '. '.join(desc_parts) if desc_parts else None

        # Build Wikipedia URL from wikidata code
        wiki_url = f"https://www.wikidata.org/wiki/{p['wikidata_code']}" if p['wikidata_code'] else None

        # Birth/death date handling
        birth_year = p['birth']
        death_year = p['death']
        birth_iso = _year_to_iso(birth_year)
        death_iso = _year_to_iso(death_year)
        birth_display = _year_to_display(birth_year)
        death_display = _year_to_display(death_year)

        if dry_run:
            print(f"  Would create: {p['name']} ({birth_display or '?'} - {death_display or '?'})")
            inserted_persons += 1
            continue

        # Create person
        cur = db.execute(
            "INSERT INTO persons (name, birth_date_start, birth_date_end, birth_date_display, "
            "death_date_start, death_date_end, death_date_display, description, wikipedia_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p['name'], birth_iso, birth_iso, birth_display,
             death_iso, death_iso, death_display,
             description, wiki_url)
        )
        person_id = cur.lastrowid
        inserted_persons += 1

        # Add birth whereabout
        if p['birth_lat'] is not None:
            place_name = p['birthplace_name']
            if not place_name and reverse_geocode:
                place_name = _reverse_geocode_approx(p['birth_lat'], p['birth_lon'])
                geocoded += 1
            if not place_name:
                place_name = f"Birthplace ({p['birth_lat']:.2f}, {p['birth_lon']:.2f})"

            db.execute(
                "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
                "date_start, date_end, date_precision, date_display, description, confidence, "
                "location_size, extraction_method, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (person_id, place_name, p['birth_lat'], p['birth_lon'],
                 birth_iso or '0001-01-01', birth_iso or '0001-01-01',
                 'year', birth_display,
                 f"Born in {place_name}", 'probable',
                 'city', 'crossverified', 'system')
            )
            inserted_whereabouts += 1

        # Add death whereabout
        if p['death_lat'] is not None and death_iso:
            place_name = p['deathplace_name']
            if not place_name and reverse_geocode:
                place_name = _reverse_geocode_approx(p['death_lat'], p['death_lon'])
                geocoded += 1
            if not place_name:
                place_name = f"Death location ({p['death_lat']:.2f}, {p['death_lon']:.2f})"

            db.execute(
                "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
                "date_start, date_end, date_precision, date_display, description, confidence, "
                "location_size, extraction_method, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (person_id, place_name, p['death_lat'], p['death_lon'],
                 death_iso, death_iso,
                 'year', death_display,
                 f"Died in {place_name}", 'probable',
                 'city', 'crossverified', 'system')
            )
            inserted_whereabouts += 1

    if not dry_run:
        db.commit()
    db.close()

    print(f"\nResults:")
    print(f"  Persons created: {inserted_persons}")
    print(f"  Whereabouts created: {inserted_whereabouts}")
    if geocoded:
        print(f"  Reverse-geocoded: {geocoded}")


def main():
    parser = argparse.ArgumentParser(
        description='Import from cross-verified database of notable people')
    parser.add_argument('csv_path', help='Path to cross-verified-database.csv.gz')
    parser.add_argument('--top', type=int, default=500,
                        help='Import top N most notable people (default: 500)')
    parser.add_argument('--min-editions', type=int, default=5,
                        help='Minimum Wikipedia editions to include (default: 5)')
    parser.add_argument('--reverse-geocode', action='store_true',
                        help='Reverse-geocode coordinates to place names (slow)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without inserting')
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"File not found: {args.csv_path}")
        sys.exit(1)

    import_crossverified(
        args.csv_path,
        top_n=args.top,
        dry_run=args.dry_run,
        reverse_geocode=args.reverse_geocode,
        min_wiki_editions=args.min_editions,
    )


if __name__ == '__main__':
    main()
