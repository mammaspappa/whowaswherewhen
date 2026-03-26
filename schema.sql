-- Historical figures
CREATE TABLE IF NOT EXISTS persons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    birth_date_start TEXT,
    birth_date_end  TEXT,
    birth_date_display TEXT,
    death_date_start TEXT,
    death_date_end  TEXT,
    death_date_display TEXT,
    description     TEXT,
    wikipedia_url   TEXT,
    image_url       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);

-- Whereabouts: a person was at a place during a time range
CREATE TABLE IF NOT EXISTS whereabouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id       INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    place_name      TEXT NOT NULL,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    date_start      TEXT NOT NULL,
    date_end        TEXT NOT NULL,
    date_precision  TEXT NOT NULL DEFAULT 'year'
                    CHECK(date_precision IN ('day','month','season','year','decade','approximate')),
    date_display    TEXT,
    description     TEXT,
    confidence      TEXT NOT NULL DEFAULT 'probable'
                    CHECK(confidence IN ('certain','probable','possible','speculative')),
    location_size   TEXT
                    CHECK(location_size IS NULL OR location_size IN
                        ('building','district','city','region','country','supranational')),
    -- Provenance: how and when this record was created
    source_text     TEXT,           -- excerpt from the original text this is based on
    extraction_method TEXT,         -- how it was extracted: wikidata, pattern, ner, category, manual
    extraction_model TEXT,          -- specific model used: gemini-3.1, llama-3.3-70b, claude-sonnet, etc.
    extracted_at    TEXT,            -- when the extraction happened (ISO datetime)
    created_by      TEXT,           -- who or what created it: system, user name, api
    raw_date_text   TEXT,           -- original date string before parsing (e.g. "spring 1498")
    raw_place_text  TEXT,           -- original place string before cleaning/geocoding
    geocode_source  TEXT,           -- how it was geocoded: nominatim, wikidata, manual, cached
    verified        INTEGER NOT NULL DEFAULT 0,   -- 0=unverified, 1=human-verified
    verified_by     TEXT,           -- who verified it
    verified_at     TEXT,           -- when it was verified (ISO datetime)
    notes           TEXT,           -- free-form notes
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_whereabouts_person ON whereabouts(person_id);
CREATE INDEX IF NOT EXISTS idx_whereabouts_dates ON whereabouts(date_start, date_end);
CREATE INDEX IF NOT EXISTS idx_whereabouts_location ON whereabouts(latitude, longitude);

-- Sources / references for whereabouts claims
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    whereabout_id   INTEGER NOT NULL REFERENCES whereabouts(id) ON DELETE CASCADE,
    url             TEXT,
    title           TEXT NOT NULL,
    author          TEXT,
    excerpt         TEXT,
    source_type     TEXT NOT NULL DEFAULT 'webpage'
                    CHECK(source_type IN ('webpage','book','article','diary','letter','ai_extracted','other')),
    accessed_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sources_whereabout ON sources(whereabout_id);

-- User contributions (pending review queue)
CREATE TABLE IF NOT EXISTS contributions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contributor_name TEXT,
    contributor_email TEXT,
    person_name     TEXT NOT NULL,
    person_id       INTEGER REFERENCES persons(id),
    place_name      TEXT NOT NULL,
    latitude        REAL,
    longitude       REAL,
    date_start      TEXT NOT NULL,
    date_end        TEXT NOT NULL,
    date_precision  TEXT NOT NULL DEFAULT 'year'
                    CHECK(date_precision IN ('day','month','season','year','decade','approximate')),
    date_display    TEXT,
    description     TEXT,
    source_url      TEXT,
    source_title    TEXT,
    source_excerpt  TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','rejected')),
    reviewer_notes  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_contributions_status ON contributions(status);

-- Full-text search virtual table for person names and descriptions
CREATE VIRTUAL TABLE IF NOT EXISTS persons_fts USING fts5(
    name,
    description,
    content='persons',
    content_rowid='id'
);

-- Discussions: Wikipedia talk-page style comments on persons or whereabouts
CREATE TABLE IF NOT EXISTS discussions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type     TEXT NOT NULL
                    CHECK(target_type IN ('person','whereabout')),
    target_id       INTEGER NOT NULL,
    parent_id       INTEGER REFERENCES discussions(id) ON DELETE CASCADE,
    author_name     TEXT,
    body            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_discussions_target ON discussions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_discussions_parent ON discussions(parent_id);

-- Revisions: edit history for persons and whereabouts
CREATE TABLE IF NOT EXISTS revisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type     TEXT NOT NULL
                    CHECK(target_type IN ('person','whereabout')),
    target_id       INTEGER NOT NULL,
    editor_name     TEXT,
    edit_summary    TEXT,
    old_values      TEXT,
    new_values      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_revisions_target ON revisions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_revisions_created ON revisions(created_at);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS persons_ai AFTER INSERT ON persons BEGIN
    INSERT INTO persons_fts(rowid, name, description) VALUES (new.id, new.name, new.description);
END;

CREATE TRIGGER IF NOT EXISTS persons_ad AFTER DELETE ON persons BEGIN
    INSERT INTO persons_fts(persons_fts, rowid, name, description) VALUES('delete', old.id, old.name, old.description);
END;

CREATE TRIGGER IF NOT EXISTS persons_au AFTER UPDATE ON persons BEGIN
    INSERT INTO persons_fts(persons_fts, rowid, name, description) VALUES('delete', old.id, old.name, old.description);
    INSERT INTO persons_fts(rowid, name, description) VALUES (new.id, new.name, new.description);
END;
