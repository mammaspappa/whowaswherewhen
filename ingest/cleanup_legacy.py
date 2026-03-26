"""Cleanup script for legacy data issues in wwww.db.

Performs three cleanup steps:
1. Delete non-place entries (person names, book titles, planets, etc.)
2. Fix wrong-continent geocoding using historical_places module
3. Fix the Q1067 person (merge into Dante Alighieri)
"""

import sqlite3
import math
import os
import sys

# Add parent dir so we can import historical_places
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from historical_places import HISTORICAL_PLACES

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'wwww.db')


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def step1_delete_non_places(conn):
    """Delete whereabouts rows where place_name is not a geographic place."""
    print("=" * 60)
    print("STEP 1: Delete non-place entries")
    print("=" * 60)
    c = conn.cursor()

    # Define bad entries as (place_name, person_name_pattern) tuples.
    # person_name_pattern uses SQL LIKE. None means match any person.
    # For entries that should only be deleted for non-matching persons,
    # we use NOT LIKE patterns handled separately.
    bad_entries = [
        # Person names extracted as places
        ('Maffeo', 'Marco Polo'),
        ('Haydn', '%'),  # Mozart and Beethoven
        ('Wellington', 'Ludwig van Beethoven'),
        ('Principia', 'Isaac Newton'),
        ('Ammannati', 'Galileo Galilei'),
        ('Jupiter', '%'),  # Galileo, Kepler - not a place
        ('Venus', '%'),  # Shakespeare, Galileo - not a place
        ('Christ', 'Johannes Kepler'),
        ('Diego', 'Christopher Columbus'),
        ('Afonso', 'Christopher Columbus'),
        ('Bishop', 'Martin Luther'),
        ('Abbott', 'Michael Faraday'),
        ('Punch', 'Michael Faraday'),
        ('Phoenix', 'William Shakespeare'),
        ('Romeo', 'William Shakespeare'),
        ('Rienzi', 'Richard Wagner'),
        ('Tristan', 'Richard Wagner'),
        ('Olivia', 'Mark Twain'),
        ('Duchess', 'Catherine II of Russia'),
        ('Pugachev', 'Catherine II of Russia'),
        ('Roosevelt', 'Joseph Stalin'),
        ('Armada', 'Elizabeth I of England'),
        ('Philip', 'Elizabeth I of England'),
        ('Spanish', 'Elizabeth I of England'),
        ('Vedas', 'Voltaire'),
        ('Indus', '%'),  # Voltaire, Genghis Khan
        ('LeFort', 'Peter the Great'),
        ('Lefort', 'Peter the Great'),
        ('Strong', 'Peter the Great'),
        ('Roon', 'Otto von Bismarck'),
        ('Emperor', 'Otto von Bismarck'),
        ('Kamenev', 'Joseph Stalin'),
        ('Titia', 'Rembrandt'),
        ('Bathsheba', 'Rembrandt'),
        ('The Kingdom of God', 'Leo Tolstoy'),
        ('Zigmont', 'Leo Tolstoy'),
        ('Vergennes', 'Marie Antoinette'),
        ('Medici', '%'),  # Leonardo, Machiavelli, Marie Antoinette
        ('Marietta', 'Marie Antoinette'),
        ('Ellis', 'Charles Dickens'),
        ('Hall', 'Charles Dickens'),
        ('Blackmore', 'Charles Dickens'),
        ('Callisto', 'Galileo Galilei'),
        ('Field', 'Frédéric Chopin'),
        ('Caldara', 'Johann Sebastian Bach'),
        ('Inferno', '%'),  # Q1067/Dante
        ('Gemini', '%'),  # Q1067/Dante
        ('Antonia', '%'),  # Q1067/Dante
        ('Grand Alliance', 'Louis XIV of France'),
        ('Fagon', 'Louis XIV of France'),
        ('Spelling', 'Benjamin Franklin'),
        ('McClellan', 'Abraham Lincoln'),
        ('Aldebaran', 'Nicolaus Copernicus'),
        ('Ptolemy', 'Nicolaus Copernicus'),
        ('Psalm 130', 'Martin Luther'),
        ("Psalm 67's", 'Martin Luther'),
        ('Hebrews', 'Martin Luther'),
        ('Ludher', 'Martin Luther'),
        ("King Arthur's", 'Mark Twain'),
        ('The Alta California', 'Mark Twain'),
        ('New-York Tribune', 'Mark Twain'),
        ('Militaire de Saint-Louis', 'Louis XIV of France'),
        ('Bantum', 'Elizabeth I of England'),
        ('Murad III', 'Elizabeth I of England'),
        ('Mississippi', 'Louis XIV of France'),
        ('Brazil', 'Louis XIV of France'),
    ]

    # Handle "non-X persons" entries: Charlemagne, Ferdinand, Newton, Frederick
    # These should be deleted only when the person is NOT the named person
    non_self_entries = [
        ('Charlemagne', '%Charlemagne%'),
        ('Ferdinand', '%Ferdinand%'),
        ('Newton', '%Newton%'),
        ('Frederick', '%Frederick%'),
    ]

    # Also: Irene for Voltaire, Temujin for any
    bad_entries.append(('Irene', 'Voltaire'))
    bad_entries.append(('Temujin', '%'))

    # Also: 'Philip V. In' for Louis XIV
    bad_entries.append(('Philip V. In', 'Louis XIV of France'))

    # Count entries to delete
    total_to_delete = 0

    # Count standard bad entries
    for place_name, person_pattern in bad_entries:
        if person_pattern == '%':
            c.execute("SELECT COUNT(*) FROM whereabouts WHERE place_name = ?", (place_name,))
        else:
            c.execute("""
                SELECT COUNT(*) FROM whereabouts w
                JOIN persons p ON w.person_id = p.id
                WHERE w.place_name = ? AND p.name LIKE ?
            """, (place_name, person_pattern))
        count = c.fetchone()[0]
        if count > 0:
            print(f"  Will delete {count:3d} entries for place_name='{place_name}' (person LIKE '{person_pattern}')")
        total_to_delete += count

    # Count non-self entries
    for place_name, self_pattern in non_self_entries:
        c.execute("""
            SELECT COUNT(*) FROM whereabouts w
            JOIN persons p ON w.person_id = p.id
            WHERE w.place_name = ? AND p.name NOT LIKE ?
        """, (place_name, self_pattern))
        count = c.fetchone()[0]
        if count > 0:
            print(f"  Will delete {count:3d} entries for place_name='{place_name}' (person NOT LIKE '{self_pattern}')")
        total_to_delete += count

    # Count trailing garbage entries
    c.execute("""
        SELECT COUNT(*) FROM whereabouts
        WHERE place_name LIKE '% in'
           OR place_name LIKE '% on'
           OR place_name LIKE '% for'
           OR place_name LIKE '% between'
           OR place_name LIKE '% with'
           OR place_name LIKE '% during'
           OR place_name LIKE '% and'
    """)
    trailing_count = c.fetchone()[0]
    print(f"  Will delete {trailing_count:3d} entries with trailing garbage words")
    total_to_delete += trailing_count

    print(f"\n  TOTAL entries to delete: {total_to_delete}")

    # Now perform the deletes

    # Delete standard bad entries
    deleted_total = 0
    for place_name, person_pattern in bad_entries:
        if person_pattern == '%':
            # Delete sources first (CASCADE should handle it, but be explicit)
            c.execute("""
                DELETE FROM sources WHERE whereabout_id IN (
                    SELECT id FROM whereabouts WHERE place_name = ?
                )
            """, (place_name,))
            c.execute("DELETE FROM whereabouts WHERE place_name = ?", (place_name,))
        else:
            c.execute("""
                DELETE FROM sources WHERE whereabout_id IN (
                    SELECT w.id FROM whereabouts w
                    JOIN persons p ON w.person_id = p.id
                    WHERE w.place_name = ? AND p.name LIKE ?
                )
            """, (place_name, person_pattern))
            c.execute("""
                DELETE FROM whereabouts WHERE id IN (
                    SELECT w.id FROM whereabouts w
                    JOIN persons p ON w.person_id = p.id
                    WHERE w.place_name = ? AND p.name LIKE ?
                )
            """, (place_name, person_pattern))
        deleted_total += c.rowcount

    # Delete non-self entries
    for place_name, self_pattern in non_self_entries:
        c.execute("""
            DELETE FROM sources WHERE whereabout_id IN (
                SELECT w.id FROM whereabouts w
                JOIN persons p ON w.person_id = p.id
                WHERE w.place_name = ? AND p.name NOT LIKE ?
            )
        """, (place_name, self_pattern))
        c.execute("""
            DELETE FROM whereabouts WHERE id IN (
                SELECT w.id FROM whereabouts w
                JOIN persons p ON w.person_id = p.id
                WHERE w.place_name = ? AND p.name NOT LIKE ?
            )
        """, (place_name, self_pattern))
        deleted_total += c.rowcount

    # Delete trailing garbage entries
    c.execute("""
        DELETE FROM sources WHERE whereabout_id IN (
            SELECT id FROM whereabouts
            WHERE place_name LIKE '% in'
               OR place_name LIKE '% on'
               OR place_name LIKE '% for'
               OR place_name LIKE '% between'
               OR place_name LIKE '% with'
               OR place_name LIKE '% during'
               OR place_name LIKE '% and'
        )
    """)
    trailing_sources_deleted = c.rowcount
    c.execute("""
        DELETE FROM whereabouts
        WHERE place_name LIKE '% in'
           OR place_name LIKE '% on'
           OR place_name LIKE '% for'
           OR place_name LIKE '% between'
           OR place_name LIKE '% with'
           OR place_name LIKE '% during'
           OR place_name LIKE '% and'
    """)
    deleted_total += c.rowcount

    conn.commit()
    print(f"\n  DELETED {deleted_total} whereabouts entries (and associated sources)")
    return deleted_total


def step2_fix_geocoding(conn):
    """Fix wrong-continent geocoding using historical_places and specific corrections."""
    print("\n" + "=" * 60)
    print("STEP 2: Fix wrong-continent geocoding")
    print("=" * 60)
    c = conn.cursor()
    updated_total = 0

    # --- Fix using HISTORICAL_PLACES dict ---
    c.execute("SELECT id, place_name, latitude, longitude FROM whereabouts")
    all_rows = c.fetchall()
    hp_fixes = 0

    for row_id, place_name, lat, lon in all_rows:
        key = place_name.strip().lower()
        if key in HISTORICAL_PLACES:
            correct_lat, correct_lon = HISTORICAL_PLACES[key]
            dist = haversine_km(lat, lon, correct_lat, correct_lon)
            if dist > 500:
                c.execute(
                    "UPDATE whereabouts SET latitude = ?, longitude = ? WHERE id = ?",
                    (correct_lat, correct_lon, row_id)
                )
                hp_fixes += 1
                if hp_fixes <= 20:
                    print(f"  Fixed '{place_name}' (id={row_id}): "
                          f"({lat:.2f}, {lon:.2f}) -> ({correct_lat}, {correct_lon}) "
                          f"[{dist:.0f}km off]")

    if hp_fixes > 20:
        print(f"  ... and {hp_fixes - 20} more historical_places fixes")
    print(f"  Historical places fixes: {hp_fixes}")
    updated_total += hp_fixes

    # --- Fix specific known-bad entries ---

    # Prussia -> Berlin
    c.execute("""
        SELECT COUNT(*) FROM whereabouts
        WHERE place_name = 'Prussia'
        AND (ABS(latitude - 52.5) > 1 OR ABS(longitude - 13.4) > 1)
    """)
    prussia_count = c.fetchone()[0]
    c.execute("""
        UPDATE whereabouts SET latitude = 52.5, longitude = 13.4
        WHERE place_name = 'Prussia'
        AND (ABS(latitude - 52.5) > 1 OR ABS(longitude - 13.4) > 1)
    """)
    print(f"  Fixed {c.rowcount} Prussia entries -> (52.5, 13.4)")
    updated_total += c.rowcount

    # Russia with lat > 60 -> Moscow
    c.execute("SELECT COUNT(*) FROM whereabouts WHERE place_name = 'Russia' AND latitude > 60")
    russia_count = c.fetchone()[0]
    c.execute("""
        UPDATE whereabouts SET latitude = 55.75, longitude = 37.62
        WHERE place_name = 'Russia' AND latitude > 60
    """)
    print(f"  Fixed {c.rowcount} Russia entries (lat>60) -> (55.75, 37.62)")
    updated_total += c.rowcount

    # West Berlin with lon < -70 -> Berlin
    c.execute("""
        UPDATE whereabouts SET latitude = 52.52, longitude = 13.40
        WHERE place_name = 'West Berlin' AND longitude < -70
    """)
    print(f"  Fixed {c.rowcount} West Berlin entries -> (52.52, 13.40)")
    updated_total += c.rowcount

    # Georgia for Catherine II and Joseph Stalin -> country Georgia
    c.execute("""
        UPDATE whereabouts SET latitude = 42.0, longitude = 43.5
        WHERE place_name = 'Georgia'
        AND person_id IN (
            SELECT id FROM persons WHERE name IN ('Catherine II of Russia', 'Joseph Stalin')
        )
    """)
    print(f"  Fixed {c.rowcount} Georgia entries (Catherine II, Stalin) -> (42.0, 43.5)")
    updated_total += c.rowcount

    # Notre-Dame for Joan of Arc -> Paris
    c.execute("""
        UPDATE whereabouts SET latitude = 48.853, longitude = 2.349
        WHERE place_name = 'Notre-Dame'
        AND person_id IN (
            SELECT id FROM persons WHERE name = 'Joan of Arc'
        )
    """)
    print(f"  Fixed {c.rowcount} Notre-Dame entries (Joan of Arc) -> (48.853, 2.349)")
    updated_total += c.rowcount

    conn.commit()
    print(f"\n  TOTAL geocoding fixes: {updated_total}")
    return updated_total


def step3_fix_q1067(conn):
    """Fix the Q1067 person: merge into Dante Alighieri."""
    print("\n" + "=" * 60)
    print("STEP 3: Fix Q1067 person (merge into Dante Alighieri)")
    print("=" * 60)
    c = conn.cursor()

    # Find Q1067
    c.execute("SELECT id, name FROM persons WHERE name = 'Q1067'")
    q1067 = c.fetchone()
    if not q1067:
        print("  Q1067 person not found - skipping")
        return 0

    q1067_id = q1067[0]
    print(f"  Found Q1067 with person id={q1067_id}")

    # Check for Dante Alighieri
    c.execute("SELECT id, name FROM persons WHERE name = 'Dante Alighieri'")
    dante = c.fetchone()

    if dante:
        dante_id = dante[0]
        print(f"  Found Dante Alighieri with person id={dante_id}")

        # Count Q1067's whereabouts
        c.execute("SELECT COUNT(*) FROM whereabouts WHERE person_id = ?", (q1067_id,))
        q1067_whereabouts = c.fetchone()[0]
        print(f"  Q1067 has {q1067_whereabouts} whereabouts entries")

        # Merge: update Q1067's whereabouts to point to Dante's person_id
        c.execute(
            "UPDATE whereabouts SET person_id = ? WHERE person_id = ?",
            (dante_id, q1067_id)
        )
        merged = c.rowcount
        print(f"  Merged {merged} whereabouts from Q1067 (id={q1067_id}) into Dante (id={dante_id})")

        # Delete Q1067 person record
        c.execute("DELETE FROM persons WHERE id = ?", (q1067_id,))
        print(f"  Deleted Q1067 person record (id={q1067_id})")

        # Update FTS index
        try:
            c.execute("INSERT INTO persons_fts(persons_fts) VALUES('rebuild')")
            print("  Rebuilt FTS index")
        except Exception as e:
            print(f"  Warning: Could not rebuild FTS index: {e}")

    else:
        # Dante doesn't exist, just rename Q1067
        c.execute("UPDATE persons SET name = 'Dante Alighieri' WHERE id = ?", (q1067_id,))
        print(f"  Renamed Q1067 to 'Dante Alighieri' (id={q1067_id})")
        merged = 0

    conn.commit()

    # Verify
    c.execute("SELECT COUNT(*) FROM whereabouts WHERE person_id = ?", (dante_id if dante else q1067_id,))
    final_count = c.fetchone()[0]
    print(f"  Dante Alighieri now has {final_count} whereabouts entries")

    return merged


def main():
    print(f"Database: {os.path.abspath(DB_PATH)}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # Get initial counts
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM whereabouts")
    initial_whereabouts = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sources")
    initial_sources = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM persons")
    initial_persons = c.fetchone()[0]
    print(f"Initial counts: {initial_whereabouts} whereabouts, {initial_sources} sources, {initial_persons} persons\n")

    # Run cleanup steps
    deleted = step1_delete_non_places(conn)
    geocoding_fixes = step2_fix_geocoding(conn)
    merged = step3_fix_q1067(conn)

    # Final counts
    c.execute("SELECT COUNT(*) FROM whereabouts")
    final_whereabouts = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sources")
    final_sources = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM persons")
    final_persons = c.fetchone()[0]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Whereabouts: {initial_whereabouts} -> {final_whereabouts} (deleted {initial_whereabouts - final_whereabouts})")
    print(f"  Sources:     {initial_sources} -> {final_sources} (deleted {initial_sources - final_sources})")
    print(f"  Persons:     {initial_persons} -> {final_persons} (deleted {initial_persons - final_persons})")
    print(f"  Geocoding fixes: {geocoding_fixes}")
    print(f"  Q1067 whereabouts merged into Dante: {merged}")

    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
