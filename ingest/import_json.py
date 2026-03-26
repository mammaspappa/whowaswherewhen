"""Import datapoints (whereabouts) from JSON files.

JSON format — a single person with their datapoints:

{
  "person": {
    "name": "Ernst Jünger",
    "birth_date_display": "March 29, 1895",
    "death_date_display": "February 17, 1998",
    "description": "German author and WWI officer.",
    "wikipedia_url": "https://en.wikipedia.org/wiki/Ernst_Jünger"
  },
  "datapoints": [
    {
      "place_name": "Heidelberg, Germany",
      "latitude": 49.3988,
      "longitude": 8.6724,
      "date_start": "1895-03-29",
      "date_end": "1907-12-31",
      "date_precision": "year",
      "date_display": "1895 - 1907",
      "description": "Born in Heidelberg; early childhood",
      "confidence": "certain",
      "sources": [
        {
          "title": "Storm of Steel",
          "url": "https://www.gutenberg.org/ebooks/34099",
          "source_type": "book"
        }
      ]
    }
  ]
}

If latitude/longitude are omitted, the place_name will be geocoded automatically.
If the person already exists (matched by name), datapoints are added to the existing person.
Duplicate datapoints (same place_name + date_start) are skipped.
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def get_db():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'wwww.db')
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def import_data(data, dry_run=False, validate_with_llm=None):
    """Import a person + datapoints dict into the database.

    data should have the shape: {"person": {...}, "datapoints": [...]}
    If validate_with_llm is set to a provider name (e.g. 'gemini-3.1'),
    the datapoints are sent to the LLM for validation before insertion.
    Returns (inserted_count, skipped_count) or (0, 0) on error.
    """
    person_data = data.get('person')
    datapoints = data.get('datapoints', [])

    if not person_data or not person_data.get('name'):
        print("Error: 'person.name' is required")
        return 0, 0

    print(f"\nImporting: {person_data['name']} ({len(datapoints)} datapoints)")

    if dry_run:
        print("  [DRY RUN] No changes will be made.")

    db = get_db()

    # Find or create person
    existing = db.execute(
        "SELECT id FROM persons WHERE name = ?", (person_data['name'],)
    ).fetchone()

    if existing:
        person_id = existing['id']
        print(f"  Person exists (id={person_id})")
    elif dry_run:
        person_id = None
        print(f"  Would create person: {person_data['name']}")
    else:
        cur = db.execute(
            "INSERT INTO persons (name, birth_date_start, birth_date_end, birth_date_display, "
            "death_date_start, death_date_end, death_date_display, description, wikipedia_url, image_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (person_data['name'],
             person_data.get('birth_date_start'), person_data.get('birth_date_end'),
             person_data.get('birth_date_display'),
             person_data.get('death_date_start'), person_data.get('death_date_end'),
             person_data.get('death_date_display'),
             person_data.get('description'),
             person_data.get('wikipedia_url'), person_data.get('image_url'))
        )
        person_id = cur.lastrowid
        print(f"  Created person (id={person_id})")

    # Check existing datapoints for dedup
    if person_id:
        existing_dp = {(r['place_name'], r['date_start']) for r in db.execute(
            "SELECT place_name, date_start FROM whereabouts WHERE person_id = ?", (person_id,)
        ).fetchall()}
    else:
        existing_dp = set()

    # Optional LLM validation pass
    if validate_with_llm and datapoints:
        try:
            from ingest.free.free_llm_extract import validate_datapoints
            print(f"  Validating {len(datapoints)} datapoints with {validate_with_llm}...")
            datapoints = validate_datapoints(
                person_data['name'], datapoints,
                provider=validate_with_llm,
                birth_info=person_data.get('birth_date_display', ''),
                death_info=person_data.get('death_date_display', ''),
            )
        except Exception as e:
            print(f"  Validation error: {e}, proceeding without validation")

    inserted = 0
    skipped = 0
    geocoded = 0
    errors = []

    for i, dp in enumerate(datapoints):
        place = dp.get('place_name', '').strip()
        if not place:
            errors.append(f"  Datapoint {i}: missing place_name")
            continue

        ds = dp.get('date_start', '')
        de = dp.get('date_end', ds)

        # Normalize dates: handle integers (1212 → "1212-01-01"),
        # year-only strings ("1212" → "1212-01-01"), and None
        for date_key in ('date_start', 'date_end'):
            val = dp.get(date_key)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                val = str(int(val))
            val = str(val).strip()
            if val and len(val) == 4 and val.lstrip('-').isdigit():
                val = f"{val}-01-01"
            dp[date_key] = val
        ds = dp.get('date_start', '')
        de = dp.get('date_end', ds)

        if not ds:
            errors.append(f"  Datapoint {i} ({place}): missing date_start")
            continue

        # Dedup check
        if (place, ds) in existing_dp:
            skipped += 1
            continue

        # Lifetime check: skip entries dated after death
        death = person_data.get('death_date_start', '')
        if death:
            if death.startswith('-') and not ds.startswith('-'):
                # Person died BCE but entry is CE — clearly wrong
                errors.append(f"  Datapoint {i} ({place}): date {ds} is CE but person died {death} BCE")
                continue
            elif not death.startswith('-') and not ds.startswith('-'):
                # Both CE — simple string comparison works
                if ds[:4] > death[:4]:
                    errors.append(f"  Datapoint {i} ({place}): date {ds} is after death {death}")
                    continue

        # Normalize location_size: map common LLM variants to valid values
        VALID_LOCATION_SIZES = {'building', 'district', 'city', 'region', 'country', 'supranational'}
        LOCATION_SIZE_ALIASES = {
            'landmark': 'building', 'monument': 'building', 'site': 'building',
            'structure': 'building', 'address': 'building', 'estate': 'building',
            'neighborhood': 'district', 'quarter': 'district', 'campus': 'district',
            'town': 'city', 'village': 'city', 'settlement': 'city',
            'province': 'region', 'state': 'region', 'county': 'region',
            'nation': 'country', 'empire': 'supranational', 'continent': 'supranational',
        }
        loc_size = dp.get('location_size')
        if loc_size and loc_size not in VALID_LOCATION_SIZES:
            mapped = LOCATION_SIZE_ALIASES.get(loc_size.lower())
            if mapped:
                dp['location_size'] = mapped
            else:
                dp['location_size'] = None  # Unknown, clear it

        # Vague location check: reject continents and broad regions
        VAGUE_LOCATIONS = {
            'europe', 'asia', 'africa', 'north america', 'south america',
            'central america', 'oceania', 'antarctica', 'middle east',
            'far east', 'western europe', 'eastern europe', 'central asia',
            'southeast asia', 'east asia', 'south asia', 'sub-saharan africa',
            'north africa', 'scandinavia', 'british isles', 'iberian peninsula',
            'mediterranean', 'the americas', 'new world', 'old world',
            'earth', 'world', 'globe',
            # Country abbreviations (too vague; the person was at a specific city)
            'u.s.', 'us', 'uk', 'ussr', 'u.k.', 'u.s.s.r.',
        }
        if place.lower() in VAGUE_LOCATIONS:
            errors.append(f"  Datapoint {i} ({place}): too vague (continent/region)")
            continue

        # Geocode if needed
        lat = dp.get('latitude')
        lon = dp.get('longitude')
        if lat is None or lon is None:
            from ingest.geocode import geocode
            coords = geocode(place)
            if coords:
                lat, lon = coords
                geocoded += 1
                if not dp.get('geocode_source'):
                    dp['geocode_source'] = 'nominatim'
            else:
                errors.append(f"  Datapoint {i} ({place}): could not geocode")
                continue

        if dry_run:
            print(f"  Would insert: {place} ({dp.get('date_display', ds)})")
            inserted += 1
            continue

        w_cur = db.execute(
            "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
            "date_start, date_end, date_precision, date_display, description, confidence, "
            "location_size, source_text, extraction_method, extraction_model, extracted_at, created_by, "
            "raw_date_text, raw_place_text, geocode_source, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (person_id, place, lat, lon, ds, de,
             dp.get('date_precision', 'year'),
             dp.get('date_display'),
             dp.get('description'),
             dp.get('confidence', 'probable'),
             dp.get('location_size'),
             dp.get('source_text'),
             dp.get('extraction_method'),
             dp.get('extraction_model'),
             dp.get('extracted_at'),
             dp.get('created_by', 'system'),
             dp.get('raw_date_text'),
             dp.get('raw_place_text'),
             dp.get('geocode_source'),
             dp.get('notes'))
        )
        whereabout_id = w_cur.lastrowid

        for src in dp.get('sources', []):
            db.execute(
                "INSERT INTO sources (whereabout_id, url, title, author, excerpt, source_type) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (whereabout_id, src.get('url'), src.get('title', 'Import'),
                 src.get('author'), src.get('excerpt'),
                 src.get('source_type', 'other'))
            )

        inserted += 1
        existing_dp.add((place, ds))

    if not dry_run:
        db.commit()
    db.close()

    print(f"\n  Results: {inserted} inserted, {skipped} duplicates skipped, {geocoded} geocoded")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for e in errors:
            print(f"    {e}")

    return inserted, skipped


def import_json(filepath, dry_run=False):
    """Import from a JSON file. Thin wrapper around import_data()."""
    with open(filepath) as f:
        data = json.load(f)
    return import_data(data, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description='Import datapoints from JSON files')
    parser.add_argument('files', nargs='+', help='JSON file(s) to import')
    parser.add_argument('--dry-run', action='store_true', help='Validate without inserting')
    args = parser.parse_args()

    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            continue
        import_json(filepath, dry_run=args.dry_run)

    print("\nDone!")


if __name__ == '__main__':
    main()
