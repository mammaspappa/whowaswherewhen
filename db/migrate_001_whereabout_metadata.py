"""Migration 001: Add provenance metadata columns to whereabouts table.

Adds columns for tracking how, when, and by whom each whereabout was created,
plus the source text it was based on.

Run with:
    .venv/bin/python db/migrate_001_whereabout_metadata.py
"""

import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'wwww.db')

NEW_COLUMNS = [
    ("source_text",       "TEXT"),
    ("extraction_method", "TEXT"),
    ("extraction_model",  "TEXT"),
    ("extracted_at",      "TEXT"),
    ("created_by",        "TEXT"),
    ("raw_date_text",     "TEXT"),
    ("raw_place_text",    "TEXT"),
    ("geocode_source",    "TEXT"),
    ("verified",          "INTEGER NOT NULL DEFAULT 0"),
    ("verified_by",       "TEXT"),
    ("verified_at",       "TEXT"),
    ("notes",             "TEXT"),
]


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)

    # Check which columns already exist
    existing = {row[1] for row in db.execute("PRAGMA table_info(whereabouts)").fetchall()}

    added = 0
    for col_name, col_type in NEW_COLUMNS:
        if col_name in existing:
            print(f"  {col_name}: already exists, skipping")
            continue
        sql = f"ALTER TABLE whereabouts ADD COLUMN {col_name} {col_type}"
        db.execute(sql)
        print(f"  {col_name}: added")
        added += 1

    db.commit()
    db.close()

    if added:
        print(f"\nMigration complete: {added} columns added.")
    else:
        print("\nNothing to do — all columns already exist.")


if __name__ == '__main__':
    print("Migration 001: Adding provenance metadata to whereabouts\n")
    migrate()
