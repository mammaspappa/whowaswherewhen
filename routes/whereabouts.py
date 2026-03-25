from flask import Blueprint, jsonify, request
from db import queries

bp = Blueprint('whereabouts', __name__)

COLORS = [
    '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
    '#1abc9c', '#e67e22', '#34495e', '#e91e63', '#00bcd4',
    '#8bc34a', '#ff5722'
]


@bp.route('/api/whereabouts')
def list_whereabouts():
    person_id = request.args.get('person_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    results = queries.get_whereabouts(person_id, date_from, date_to)
    return jsonify(results)


@bp.route('/api/whereabouts/<int:whereabout_id>')
def get_whereabout(whereabout_id):
    w = queries.get_whereabout(whereabout_id)
    if not w:
        return jsonify({'error': 'Not found'}), 404
    w['sources'] = queries.get_sources(whereabout_id)
    person = queries.get_person(w['person_id'])
    w['person_name'] = person['name'] if person else None
    return jsonify(w)


@bp.route('/api/whereabouts', methods=['POST'])
def create_whereabout():
    data = request.get_json()
    required = ('person_id', 'place_name', 'latitude', 'longitude', 'date_start', 'date_end')
    if not data or not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {", ".join(required)}'}), 400
    wid = queries.create_whereabout(data)
    return jsonify({'id': wid}), 201


@bp.route('/api/whereabouts/<int:whereabout_id>', methods=['PUT'])
def update_whereabout(whereabout_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if not queries.update_whereabout(whereabout_id, data):
        return jsonify({'error': 'Not found or no fields to update'}), 404
    return jsonify({'ok': True})


@bp.route('/api/whereabouts/at')
def whereabouts_at():
    date = request.args.get('date')
    person_ids_str = request.args.get('person_ids', '')
    if not date or not person_ids_str:
        return jsonify({'error': 'date and person_ids required'}), 400
    person_ids = [int(x) for x in person_ids_str.split(',') if x.strip()]
    results = queries.get_whereabouts_at_date(person_ids, date)
    return jsonify(results)


@bp.route('/api/map/timeline')
def map_timeline():
    person_ids_str = request.args.get('person_ids', '')
    if not person_ids_str:
        return jsonify({'error': 'person_ids required'}), 400
    person_ids = [int(x) for x in person_ids_str.split(',') if x.strip()]

    rows = queries.get_timeline_data(person_ids)

    # Group by person
    persons_map = {}
    for row in rows:
        pid = row['person_id']
        if pid not in persons_map:
            person = queries.get_person(pid)
            idx = len(persons_map)
            persons_map[pid] = {
                'id': pid,
                'name': person['name'],
                'color': COLORS[idx % len(COLORS)],
                'whereabouts': []
            }
        persons_map[pid]['whereabouts'].append({
            'id': row['id'],
            'place_name': row['place_name'],
            'lat': row['latitude'],
            'lon': row['longitude'],
            'date_start': row['date_start'],
            'date_end': row['date_end'],
            'date_precision': row['date_precision'],
            'date_display': row['date_display'],
            'description': row['description'],
            'confidence': row['confidence'],
        })

    # Compute overall timeline range
    all_starts = [r['date_start'] for r in rows] if rows else ['0000-01-01']
    all_ends = [r['date_end'] for r in rows] if rows else ['0000-01-01']

    return jsonify({
        'persons': list(persons_map.values()),
        'timeline_range': {
            'start': min(all_starts),
            'end': max(all_ends),
        }
    })
