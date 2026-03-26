"""Migration 002: Add location_size column to whereabouts table.

Classifies the geographic scale of each location:
  building     — specific structure, address, estate, or landmark
  district     — neighborhood, district, campus, small named area
  city         — city, town, or village
  region       — state, province, county, or sub-national region
  country      — country or nation
  supranational — multi-country area, subcontinent, or continent

Run with:
    .venv/bin/python db/migrate_002_location_size.py
"""

import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'wwww.db')


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)

    existing = {row[1] for row in db.execute("PRAGMA table_info(whereabouts)").fetchall()}

    if 'location_size' in existing:
        print("  location_size: already exists, skipping")
        print("\nNothing to do — column already exists.")
    else:
        db.execute("ALTER TABLE whereabouts ADD COLUMN location_size TEXT")
        print("  location_size: added")
        print("\nMigration complete: 1 column added.")

    db.commit()
    db.close()


if __name__ == '__main__':
    print("Migration 002: Adding location_size to whereabouts\n")
    migrate()
