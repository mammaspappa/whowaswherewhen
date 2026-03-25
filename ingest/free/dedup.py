"""Cross-strategy deduplication for combining results from multiple strategies.

Merges overlapping datapoints based on geographic proximity and date overlap.
"""

import math


def _haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two lat/lon points."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _dates_overlap(dp1, dp2):
    """Check if two datapoints have overlapping date ranges."""
    s1, e1 = dp1.get('date_start', ''), dp1.get('date_end', '')
    s2, e2 = dp2.get('date_start', ''), dp2.get('date_end', '')
    if not s1 or not s2:
        return False
    # Simple string comparison works for ISO dates
    return s1 <= e2 and s2 <= e1


CONFIDENCE_RANK = {'certain': 4, 'probable': 3, 'possible': 2, 'speculative': 1}


def _better_entry(dp1, dp2):
    """Return the better of two overlapping datapoints."""
    c1 = CONFIDENCE_RANK.get(dp1.get('confidence', 'speculative'), 0)
    c2 = CONFIDENCE_RANK.get(dp2.get('confidence', 'speculative'), 0)

    if c1 != c2:
        winner, loser = (dp1, dp2) if c1 > c2 else (dp2, dp1)
    else:
        # Prefer the one with a longer description
        d1 = len(dp1.get('description', ''))
        d2 = len(dp2.get('description', ''))
        winner, loser = (dp1, dp2) if d1 >= d2 else (dp2, dp1)

    # Merge sources from both
    merged = dict(winner)
    all_sources = list(winner.get('sources', []))
    for src in loser.get('sources', []):
        # Avoid duplicate sources
        existing_urls = {s.get('url') for s in all_sources}
        if src.get('url') not in existing_urls:
            all_sources.append(src)
    merged['sources'] = all_sources

    return merged


def deduplicate(datapoints, distance_threshold_km=25):
    """Deduplicate datapoints by geographic proximity and date overlap.

    Two datapoints are considered duplicates if:
    - They are within distance_threshold_km of each other, AND
    - Their date ranges overlap

    The higher-confidence, richer-description entry is kept, with sources merged.
    """
    if not datapoints:
        return []

    # Filter out entries missing coordinates
    valid = [dp for dp in datapoints if dp.get('latitude') is not None and dp.get('longitude') is not None]

    result = []
    used = set()

    for i, dp1 in enumerate(valid):
        if i in used:
            continue

        merged = dp1
        for j in range(i + 1, len(valid)):
            if j in used:
                continue

            dp2 = valid[j]

            # Check geographic proximity
            dist = _haversine_km(
                merged.get('latitude', 0), merged.get('longitude', 0),
                dp2.get('latitude', 0), dp2.get('longitude', 0),
            )

            if dist <= distance_threshold_km and _dates_overlap(merged, dp2):
                merged = _better_entry(merged, dp2)
                used.add(j)

        result.append(merged)

    return result
