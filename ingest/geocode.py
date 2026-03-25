"""Geocode place names to lat/lon using Nominatim (OpenStreetMap) with caching."""

import json
import os
import time

import requests

CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'geocache.json')
_cache = None
_last_request_time = 0


def _load_cache():
    global _cache
    if _cache is not None:
        return
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            _cache = json.load(f)
    else:
        _cache = {}


def _save_cache():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(_cache, f, indent=2)


def geocode(place_name):
    """Return (lat, lon) for a place name, or None if not found."""
    global _last_request_time
    _load_cache()

    key = place_name.strip().lower()
    if key in _cache:
        return _cache[key]

    # Rate limit: 1 request per second
    now = time.time()
    wait = 1.0 - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.time()

    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': place_name, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'WhoWasWhereWhen/1.0'},
            timeout=10,
        )
        results = resp.json()
        if results:
            lat = float(results[0]['lat'])
            lon = float(results[0]['lon'])
            _cache[key] = [lat, lon]
            _save_cache()
            return [lat, lon]
    except Exception as e:
        print(f"  Geocoding error for '{place_name}': {e}")

    _cache[key] = None
    _save_cache()
    return None
