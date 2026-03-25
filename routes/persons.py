from flask import Blueprint, jsonify, request
from db import queries

bp = Blueprint('persons', __name__)


@bp.route('/api/persons')
def list_persons():
    q = request.args.get('q', '')
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    persons = queries.search_persons(q, limit, offset)
    return jsonify(persons)


@bp.route('/api/persons/<int:person_id>')
def get_person(person_id):
    person = queries.get_person(person_id)
    if not person:
        return jsonify({'error': 'Person not found'}), 404
    person['whereabouts'] = queries.get_whereabouts(person_id=person_id)
    return jsonify(person)


@bp.route('/api/persons', methods=['POST'])
def create_person():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'name is required'}), 400
    person_id = queries.create_person(data)
    return jsonify({'id': person_id}), 201


@bp.route('/api/persons/<int:person_id>', methods=['PUT'])
def update_person(person_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if not queries.update_person(person_id, data):
        return jsonify({'error': 'Person not found or no fields to update'}), 404
    return jsonify({'ok': True})


@bp.route('/api/persons/<int:person_id>/text')
def get_person_text(person_id):
    article = queries.get_person_article(person_id)
    if not article:
        return jsonify({'error': 'Person not found'}), 404
    return jsonify(article)


@bp.route('/api/persons/<int:person_id>/export')
def export_person(person_id):
    """Export a person and all their datapoints as importable JSON."""
    person = queries.get_person(person_id)
    if not person:
        return jsonify({'error': 'Person not found'}), 404

    whereabouts = queries.get_whereabouts(person_id=person_id)
    datapoints = []
    for w in whereabouts:
        sources = queries.get_sources(w['id'])
        dp = {
            'place_name': w['place_name'],
            'latitude': w['latitude'],
            'longitude': w['longitude'],
            'date_start': w['date_start'],
            'date_end': w['date_end'],
            'date_precision': w['date_precision'],
            'date_display': w['date_display'],
            'description': w['description'],
            'confidence': w['confidence'],
            'sources': [{'title': s['title'], 'url': s['url'],
                         'source_type': s['source_type'], 'author': s['author'],
                         'excerpt': s['excerpt']} for s in sources],
        }
        datapoints.append(dp)

    export = {
        'person': {
            'name': person['name'],
            'birth_date_start': person['birth_date_start'],
            'birth_date_end': person['birth_date_end'],
            'birth_date_display': person['birth_date_display'],
            'death_date_start': person['death_date_start'],
            'death_date_end': person['death_date_end'],
            'death_date_display': person['death_date_display'],
            'description': person['description'],
            'wikipedia_url': person['wikipedia_url'],
            'image_url': person['image_url'],
        },
        'datapoints': datapoints,
    }
    return jsonify(export)


@bp.route('/api/import', methods=['POST'])
def import_person():
    """Import a person and their datapoints from JSON. Same format as /export."""
    data = request.get_json()
    if not data or 'person' not in data or 'name' not in data['person']:
        return jsonify({'error': 'JSON with person.name and datapoints[] required'}), 400

    person_data = data['person']
    datapoints = data.get('datapoints', [])

    # Find or create person
    from db import get_db
    db = get_db()
    existing = db.execute(
        "SELECT id FROM persons WHERE name = ?", (person_data['name'],)
    ).fetchone()

    if existing:
        person_id = existing['id']
    else:
        person_id = queries.create_person(person_data)

    # Existing datapoints for dedup
    existing_dp = {(r['place_name'], r['date_start']) for r in db.execute(
        "SELECT place_name, date_start FROM whereabouts WHERE person_id = ?", (person_id,)
    ).fetchall()}

    inserted = 0
    skipped = 0
    errors = []

    for i, dp in enumerate(datapoints):
        place = dp.get('place_name', '').strip()
        ds = dp.get('date_start', '')
        if not place or not ds:
            errors.append(f"Datapoint {i}: missing place_name or date_start")
            continue

        if (place, ds) in existing_dp:
            skipped += 1
            continue

        lat = dp.get('latitude')
        lon = dp.get('longitude')
        if lat is None or lon is None:
            from ingest.geocode import geocode
            coords = geocode(place)
            if coords:
                lat, lon = coords
            else:
                errors.append(f"Datapoint {i}: could not geocode '{place}'")
                continue

        wid = queries.create_whereabout({
            'person_id': person_id,
            'place_name': place,
            'latitude': lat,
            'longitude': lon,
            'date_start': ds,
            'date_end': dp.get('date_end', ds),
            'date_precision': dp.get('date_precision', 'year'),
            'date_display': dp.get('date_display'),
            'description': dp.get('description'),
            'confidence': dp.get('confidence', 'probable'),
        })

        for src in dp.get('sources', []):
            queries.create_source({
                'whereabout_id': wid,
                'title': src.get('title', 'Import'),
                'url': src.get('url'),
                'author': src.get('author'),
                'excerpt': src.get('excerpt'),
                'source_type': src.get('source_type', 'other'),
            })

        inserted += 1
        existing_dp.add((place, ds))

    return jsonify({
        'person_id': person_id,
        'inserted': inserted,
        'skipped': skipped,
        'errors': errors,
    }), 201
