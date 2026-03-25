import time

from flask import Blueprint, jsonify, request

bp = Blueprint('search', __name__)

# Simple rate limiting for geocode proxy
_last_geocode_time = 0


@bp.route('/api/geocode')
def geocode():
    global _last_geocode_time
    import requests as http_requests

    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'q parameter required'}), 400

    # Rate limit: 1 request per second (Nominatim policy)
    now = time.time()
    wait = 1.0 - (now - _last_geocode_time)
    if wait > 0:
        time.sleep(wait)
    _last_geocode_time = time.time()

    resp = http_requests.get(
        'https://nominatim.openstreetmap.org/search',
        params={'q': q, 'format': 'json', 'limit': 5},
        headers={'User-Agent': 'WhoWasWhereWhen/1.0'},
        timeout=10
    )

    if resp.status_code != 200:
        return jsonify({'error': 'Geocoding failed'}), 502

    results = []
    for item in resp.json():
        results.append({
            'display_name': item.get('display_name'),
            'lat': float(item.get('lat', 0)),
            'lon': float(item.get('lon', 0)),
        })
    return jsonify(results)
