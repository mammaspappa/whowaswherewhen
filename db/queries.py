import json

from db import get_db


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


# --- Persons ---

def search_persons(query, limit=20, offset=0):
    db = get_db()
    if query:
        rows = db.execute(
            "SELECT p.* FROM persons p "
            "JOIN persons_fts f ON p.id = f.rowid "
            "WHERE persons_fts MATCH ? "
            "ORDER BY rank "
            "LIMIT ? OFFSET ?",
            (query, limit, offset)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM persons ORDER BY name LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    return _rows_to_dicts(rows)


def get_person(person_id):
    db = get_db()
    row = db.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    return _row_to_dict(row)


def create_person(data):
    db = get_db()
    cur = db.execute(
        "INSERT INTO persons (name, birth_date_start, birth_date_end, birth_date_display, "
        "death_date_start, death_date_end, death_date_display, description, wikipedia_url, image_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data['name'], data.get('birth_date_start'), data.get('birth_date_end'),
         data.get('birth_date_display'), data.get('death_date_start'), data.get('death_date_end'),
         data.get('death_date_display'), data.get('description'),
         data.get('wikipedia_url'), data.get('image_url'))
    )
    db.commit()
    return cur.lastrowid


def update_person(person_id, data):
    db = get_db()
    editor_name = data.pop('editor_name', None)
    edit_summary = data.pop('edit_summary', None)

    updatable = ('name', 'birth_date_start', 'birth_date_end', 'birth_date_display',
                 'death_date_start', 'death_date_end', 'death_date_display',
                 'description', 'wikipedia_url', 'image_url')
    fields = []
    values = []
    for key in updatable:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return False

    # Snapshot old values for revision
    old_row = _row_to_dict(db.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone())
    if not old_row:
        return False
    old_vals = {k: old_row[k] for k in data if k in updatable and old_row.get(k) != data[k]}
    new_vals = {k: data[k] for k in old_vals}

    fields.append("updated_at = datetime('now')")
    values.append(person_id)
    db.execute(f"UPDATE persons SET {', '.join(fields)} WHERE id = ?", values)

    # Create revision if anything actually changed
    if old_vals:
        db.execute(
            "INSERT INTO revisions (target_type, target_id, editor_name, edit_summary, old_values, new_values) "
            "VALUES ('person', ?, ?, ?, ?, ?)",
            (person_id, editor_name, edit_summary, json.dumps(old_vals), json.dumps(new_vals))
        )

    db.commit()
    return True


# --- Whereabouts ---

def get_whereabouts(person_id=None, date_from=None, date_to=None):
    db = get_db()
    sql = "SELECT * FROM whereabouts WHERE 1=1"
    params = []
    if person_id is not None:
        sql += " AND person_id = ?"
        params.append(person_id)
    if date_from:
        sql += " AND date_end >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date_start <= ?"
        params.append(date_to)
    sql += " ORDER BY date_start"
    return _rows_to_dicts(db.execute(sql, params).fetchall())


def get_whereabout(whereabout_id):
    db = get_db()
    row = db.execute("SELECT * FROM whereabouts WHERE id = ?", (whereabout_id,)).fetchone()
    return _row_to_dict(row)


def get_whereabouts_at_date(person_ids, date):
    """Find whereabouts whose date range contains the given date."""
    db = get_db()
    placeholders = ','.join('?' for _ in person_ids)
    rows = db.execute(
        f"SELECT * FROM whereabouts "
        f"WHERE person_id IN ({placeholders}) "
        f"AND date_start <= ? AND date_end >= ? "
        f"ORDER BY person_id, date_start",
        [*person_ids, date, date]
    ).fetchall()
    return _rows_to_dicts(rows)


def get_timeline_data(person_ids):
    """Get all whereabouts for given persons, grouped by person."""
    db = get_db()
    placeholders = ','.join('?' for _ in person_ids)
    rows = db.execute(
        f"SELECT w.*, p.name as person_name FROM whereabouts w "
        f"JOIN persons p ON w.person_id = p.id "
        f"WHERE w.person_id IN ({placeholders}) "
        f"ORDER BY w.person_id, w.date_start",
        person_ids
    ).fetchall()
    return _rows_to_dicts(rows)


def create_whereabout(data):
    db = get_db()
    cur = db.execute(
        "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
        "date_start, date_end, date_precision, date_display, description, confidence, "
        "location_size, source_text, extraction_method, extraction_model, extracted_at, created_by, "
        "raw_date_text, raw_place_text, geocode_source, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data['person_id'], data['place_name'], data['latitude'], data['longitude'],
         data['date_start'], data['date_end'], data.get('date_precision', 'year'),
         data.get('date_display'), data.get('description'),
         data.get('confidence', 'probable'),
         data.get('location_size'),
         data.get('source_text'), data.get('extraction_method'),
         data.get('extraction_model'), data.get('extracted_at'),
         data.get('created_by', 'user'), data.get('raw_date_text'),
         data.get('raw_place_text'), data.get('geocode_source'),
         data.get('notes'))
    )
    db.commit()
    return cur.lastrowid


def update_whereabout(whereabout_id, data):
    db = get_db()
    editor_name = data.pop('editor_name', None)
    edit_summary = data.pop('edit_summary', None)

    updatable = ('place_name', 'latitude', 'longitude', 'date_start', 'date_end',
                 'date_precision', 'date_display', 'description', 'confidence',
                 'location_size')
    fields = []
    values = []
    for key in updatable:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return False

    old_row = _row_to_dict(db.execute("SELECT * FROM whereabouts WHERE id = ?", (whereabout_id,)).fetchone())
    if not old_row:
        return False
    old_vals = {k: old_row[k] for k in data if k in updatable and old_row.get(k) != data[k]}
    new_vals = {k: data[k] for k in old_vals}

    fields.append("updated_at = datetime('now')")
    values.append(whereabout_id)
    db.execute(f"UPDATE whereabouts SET {', '.join(fields)} WHERE id = ?", values)

    if old_vals:
        db.execute(
            "INSERT INTO revisions (target_type, target_id, editor_name, edit_summary, old_values, new_values) "
            "VALUES ('whereabout', ?, ?, ?, ?, ?)",
            (whereabout_id, editor_name, edit_summary, json.dumps(old_vals), json.dumps(new_vals))
        )

    db.commit()
    return True


# --- Sources ---

def get_sources(whereabout_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM sources WHERE whereabout_id = ? ORDER BY created_at",
        (whereabout_id,)
    ).fetchall()
    return _rows_to_dicts(rows)


def create_source(data):
    db = get_db()
    cur = db.execute(
        "INSERT INTO sources (whereabout_id, url, title, author, excerpt, source_type, accessed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data['whereabout_id'], data.get('url'), data['title'], data.get('author'),
         data.get('excerpt'), data.get('source_type', 'webpage'), data.get('accessed_at'))
    )
    db.commit()
    return cur.lastrowid


# --- Contributions ---

def create_contribution(data):
    db = get_db()
    cur = db.execute(
        "INSERT INTO contributions (contributor_name, contributor_email, person_name, person_id, "
        "place_name, latitude, longitude, date_start, date_end, date_precision, date_display, "
        "description, source_url, source_title, source_excerpt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data.get('contributor_name'), data.get('contributor_email'), data['person_name'],
         data.get('person_id'), data['place_name'], data.get('latitude'), data.get('longitude'),
         data['date_start'], data['date_end'], data.get('date_precision', 'year'),
         data.get('date_display'), data.get('description'),
         data.get('source_url'), data.get('source_title'), data.get('source_excerpt'))
    )
    db.commit()
    return cur.lastrowid


def get_contributions(status=None):
    db = get_db()
    if status:
        rows = db.execute(
            "SELECT * FROM contributions WHERE status = ? ORDER BY created_at DESC",
            (status,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM contributions ORDER BY created_at DESC"
        ).fetchall()
    return _rows_to_dicts(rows)


def approve_contribution(contribution_id, reviewer_notes=None):
    """Approve a contribution: copy data into whereabouts + sources tables."""
    db = get_db()
    contrib = _row_to_dict(db.execute(
        "SELECT * FROM contributions WHERE id = ? AND status = 'pending'",
        (contribution_id,)
    ).fetchone())
    if not contrib:
        return None

    # Resolve person_id: use existing or create new person
    person_id = contrib['person_id']
    if not person_id:
        cur = db.execute(
            "INSERT INTO persons (name) VALUES (?)",
            (contrib['person_name'],)
        )
        person_id = cur.lastrowid

    # Geocode if coordinates are missing
    lat = contrib['latitude']
    lon = contrib['longitude']
    if lat is None or lon is None:
        from ingest.geocode import geocode
        coords = geocode(contrib['place_name'])
        if coords:
            lat, lon = coords
        else:
            lat, lon = 0.0, 0.0  # fallback

    # Create whereabout
    w_cur = db.execute(
        "INSERT INTO whereabouts (person_id, place_name, latitude, longitude, "
        "date_start, date_end, date_precision, date_display, description, "
        "extraction_method, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (person_id, contrib['place_name'], lat, lon,
         contrib['date_start'], contrib['date_end'], contrib['date_precision'],
         contrib['date_display'], contrib['description'],
         'contribution', contrib.get('contributor_name', 'user'))
    )
    whereabout_id = w_cur.lastrowid

    # Create source if provided
    if contrib['source_title'] or contrib['source_url']:
        db.execute(
            "INSERT INTO sources (whereabout_id, url, title, excerpt, source_type) "
            "VALUES (?, ?, ?, ?, 'webpage')",
            (whereabout_id, contrib['source_url'],
             contrib['source_title'] or 'User contribution',
             contrib['source_excerpt'])
        )

    # Mark contribution as approved
    db.execute(
        "UPDATE contributions SET status = 'approved', reviewer_notes = ?, "
        "reviewed_at = datetime('now') WHERE id = ?",
        (reviewer_notes, contribution_id)
    )
    db.commit()
    return whereabout_id


def reject_contribution(contribution_id, reviewer_notes=None):
    db = get_db()
    db.execute(
        "UPDATE contributions SET status = 'rejected', reviewer_notes = ?, "
        "reviewed_at = datetime('now') WHERE id = ?",
        (reviewer_notes, contribution_id)
    )
    db.commit()


# --- Discussions ---

def get_discussions(target_type, target_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM discussions WHERE target_type = ? AND target_id = ? ORDER BY created_at ASC",
        (target_type, target_id)
    ).fetchall()
    items = _rows_to_dicts(rows)

    # Group into top-level with nested replies
    top_level = []
    by_id = {}
    for item in items:
        item['replies'] = []
        by_id[item['id']] = item
    for item in items:
        if item['parent_id'] and item['parent_id'] in by_id:
            by_id[item['parent_id']]['replies'].append(item)
        else:
            top_level.append(item)
    return top_level


def get_discussion(discussion_id):
    db = get_db()
    return _row_to_dict(db.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone())


def create_discussion(data):
    db = get_db()
    cur = db.execute(
        "INSERT INTO discussions (target_type, target_id, parent_id, author_name, body) "
        "VALUES (?, ?, ?, ?, ?)",
        (data['target_type'], data['target_id'], data.get('parent_id'),
         data.get('author_name'), data['body'])
    )
    db.commit()
    return cur.lastrowid


def update_discussion(discussion_id, data):
    db = get_db()
    db.execute(
        "UPDATE discussions SET body = ?, updated_at = datetime('now') WHERE id = ?",
        (data['body'], discussion_id)
    )
    db.commit()


# --- Revisions ---

def get_revisions(target_type, target_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM revisions WHERE target_type = ? AND target_id = ? ORDER BY created_at DESC",
        (target_type, target_id)
    ).fetchall()
    results = _rows_to_dicts(rows)
    for r in results:
        r['old_values'] = json.loads(r['old_values']) if r['old_values'] else None
        r['new_values'] = json.loads(r['new_values']) if r['new_values'] else None
    return results


def get_revision(revision_id):
    db = get_db()
    r = _row_to_dict(db.execute("SELECT * FROM revisions WHERE id = ?", (revision_id,)).fetchone())
    if r:
        r['old_values'] = json.loads(r['old_values']) if r['old_values'] else None
        r['new_values'] = json.loads(r['new_values']) if r['new_values'] else None
    return r


# --- Text View ---

def get_person_article(person_id):
    db = get_db()
    person = get_person(person_id)
    if not person:
        return None

    whereabouts = get_whereabouts(person_id=person_id)
    for w in whereabouts:
        w['sources'] = get_sources(w['id'])

    disc_count = db.execute(
        "SELECT COUNT(*) FROM discussions WHERE target_type = 'person' AND target_id = ?",
        (person_id,)
    ).fetchone()[0]

    rev_count = db.execute(
        "SELECT COUNT(*) FROM revisions WHERE target_type = 'person' AND target_id = ?",
        (person_id,)
    ).fetchone()[0]

    return {
        'person': person,
        'whereabouts': whereabouts,
        'discussion_count': disc_count,
        'revision_count': rev_count,
    }
