"""Geocode place names to lat/lon using Nominatim (OpenStreetMap) with caching.

Includes a historical place name fallback to handle names that Nominatim
maps to wrong-continent locations (e.g., Athens → Georgia USA, Damascus
→ Oregon, Carthage → Texas, Prussia → Iowa).
"""

import json
import os
import time

import requests

from ingest.historical_places import HISTORICAL_PLACES

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


def _nominatim_search(query):
    """Raw Nominatim search. Returns (lat, lon) or None. Rate-limited."""
    global _last_request_time
    now = time.time()
    wait = 1.0 - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.time()

    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': query, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'WhoWasWhereWhen/1.0'},
            timeout=10,
        )
        results = resp.json()
        if results:
            return [float(results[0]['lat']), float(results[0]['lon'])]
    except Exception as e:
        print(f"  Geocoding error for '{query}': {e}")
    return None


def _check_historical(place_name):
    """Check the historical places lookup. Tries the full key, then
    progressively strips qualifiers like 'Roman Republic', 'Ottoman Empire'."""
    key = place_name.strip().lower()

    # Direct match
    if key in HISTORICAL_PLACES:
        return HISTORICAL_PLACES[key]

    # Try stripping common historical qualifiers from the end
    # "Cilicia, Roman Republic" → "cilicia"
    # "Athens, Ancient Greece" → "athens"
    parts = [p.strip() for p in key.split(',')]
    if len(parts) >= 2:
        # Try just the first part
        if parts[0] in HISTORICAL_PLACES:
            return HISTORICAL_PLACES[parts[0]]
        # Try first two parts
        if len(parts) >= 3:
            two = f"{parts[0]}, {parts[1]}"
            if two in HISTORICAL_PLACES:
                return HISTORICAL_PLACES[two]

    return None


def geocode(place_name):
    """Return [lat, lon] for a place name, or None if not found.

    Resolution order:
    1. Cache hit
    2. Historical places lookup (handles ancient/medieval names)
    3. Nominatim search (full name)
    4. Fallback: drop first comma-part for 3+ part names
    5. Fallback: drop building word for 2-part names
    """
    _load_cache()

    key = place_name.strip().lower()
    if key in _cache and _cache[key] is not None:
        return _cache[key]

    # Check historical places lookup (before Nominatim to avoid wrong-continent results)
    result = _check_historical(place_name)
    if result:
        _cache[key] = result
        _save_cache()
        return result

    # Try Nominatim with the full name
    result = _nominatim_search(place_name)
    if result:
        _cache[key] = result
        _save_cache()
        return result

    # Fallback: drop the first part and try again
    # "Okazaki Castle, Aichi, Japan" → "Aichi, Japan"
    parts = [p.strip() for p in place_name.split(',')]
    if len(parts) >= 3:
        shorter = ', '.join(parts[1:])
        result = _nominatim_search(shorter)
        if result:
            print(f"  Geocoded '{place_name}' via fallback '{shorter}'")
            _cache[key] = result
            _save_cache()
            return result

    # Fallback for 2-part names where the first part looks like a building
    _BUILDING_WORDS = {
        'castle', 'palace', 'abbey', 'church', 'cathedral', 'temple',
        'monastery', 'priory', 'fort', 'fortress', 'tower', 'mosque',
        'shrine', 'villa', 'estate', 'manor', 'hall', 'house',
        'basilica', 'chapel', 'citadel', 'convent', 'prison',
        'college', 'school', 'observatory',
    }
    if len(parts) == 2:
        first_lower = parts[0].lower()
        if any(word in first_lower for word in _BUILDING_WORDS):
            result = _nominatim_search(parts[1])
            if result:
                print(f"  Geocoded '{place_name}' via building fallback '{parts[1]}'")
                _cache[key] = result
                _save_cache()
                return result

    _cache[key] = None
    _save_cache()
    return None
