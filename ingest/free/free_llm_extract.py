"""Strategy 3: Free LLM API drop-in replacement for Claude extraction.

Supports Google Gemini, Groq, Mistral, and OpenRouter free tiers.
Uses the same prompt and output format as ai_extract.py.
No new dependencies -- uses only `requests`.
"""

import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Provider configurations
# Rate limits from Google AI Studio (free tier, as of 2026-03):
#   gemini-2.5-flash-lite:  10 RPM, 250K TPM, 20 RPD
#   gemini-2.5-flash:        5 RPM, 250K TPM, 20 RPD
#   gemini-3-flash:          5 RPM, 250K TPM, 20 RPD
#   gemini-3.1-flash-lite:  15 RPM, 250K TPM, 500 RPD
#   Groq:                   30 RPM, 14.4K RPD
#   Mistral:                 1 RPS
#   OpenRouter:             20 RPM, 200 RPD
PROVIDERS = {
    'gemini': {
        'name': 'Gemini 2.5 Flash Lite',
        'env_key': 'GOOGLE_API_KEY',
        'env_key_alt': 'GOOGLE_GEMINI_API_KEY',
        'model': 'gemini-2.5-flash-lite',
        'rate_limit_sleep': 7.0,  # 10 RPM → 6s min, use 7s for safety
        'max_tokens': 4096,
        'rpd': 20,
    },
    'gemini-flash': {
        'name': 'Gemini 2.5 Flash',
        'env_key': 'GOOGLE_API_KEY',
        'env_key_alt': 'GOOGLE_GEMINI_API_KEY',
        'model': 'gemini-2.5-flash',
        'rate_limit_sleep': 13.0,  # 5 RPM → 12s min, use 13s for safety
        'max_tokens': 4096,
        'rpd': 20,
    },
    'gemini-3': {
        'name': 'Gemini 3 Flash',
        'env_key': 'GOOGLE_API_KEY',
        'env_key_alt': 'GOOGLE_GEMINI_API_KEY',
        'model': 'gemini-3-flash-preview',
        'rate_limit_sleep': 13.0,  # 5 RPM
        'max_tokens': 4096,
        'rpd': 20,
    },
    'gemini-3.1': {
        'name': 'Gemini 3.1 Flash Lite',
        'env_key': 'GOOGLE_API_KEY',
        'env_key_alt': 'GOOGLE_GEMINI_API_KEY',
        'model': 'gemini-3.1-flash-lite-preview',
        'rate_limit_sleep': 5.0,  # 15 RPM → 4s min, use 5s for safety
        'max_tokens': 4096,
        'rpd': 500,  # much higher daily limit
    },
    'groq': {
        'name': 'Groq',
        'env_key': 'GROQ_API_KEY',
        'base_url': 'https://api.groq.com/openai/v1/chat/completions',
        'model': 'llama-3.3-70b-versatile',
        'rate_limit_sleep': 2.0,  # 30 RPM
        'max_tokens': 4096,
        'rpd': 14400,
    },
    'mistral': {
        'name': 'Mistral',
        'env_key': 'MISTRAL_API_KEY',
        'base_url': 'https://api.mistral.ai/v1/chat/completions',
        'model': 'mistral-small-latest',
        'rate_limit_sleep': 1.0,  # 1 RPS
        'max_tokens': 4096,
        'rpd': None,  # unlimited
    },
    'openrouter': {
        'name': 'OpenRouter',
        'env_key': 'OPENROUTER_API_KEY',
        'base_url': 'https://openrouter.ai/api/v1/chat/completions',
        'model': 'deepseek/deepseek-chat:free',
        'rate_limit_sleep': 3.0,  # 20 RPM
        'max_tokens': 4096,
        'rpd': 200,
    },
}

# JSON Schema for structured output (used where supported)
LOCATION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "place_name": {"type": "string"},
            "date_start": {"type": "string"},
            "date_end": {"type": "string"},
            "date_precision": {"type": "string", "enum": ["day", "month", "season", "year", "decade", "approximate"]},
            "date_display": {"type": "string"},
            "description": {"type": "string"},
            "confidence": {"type": "string", "enum": ["certain", "probable", "possible", "speculative"]},
        },
        "required": ["place_name", "date_start", "date_end", "date_precision", "date_display", "description", "confidence"],
    },
}

_last_request_time = 0

# Daily request tracking — persists to disk so we don't exceed RPD across runs
_RPD_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'llm_daily_usage.json')


def _load_daily_usage():
    """Load today's request counts per provider."""
    from datetime import date
    today = date.today().isoformat()
    if os.path.exists(_RPD_FILE):
        try:
            with open(_RPD_FILE) as f:
                data = json.load(f)
            if data.get('date') == today:
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {'date': today, 'counts': {}}


def _save_daily_usage(data):
    """Save today's request counts."""
    os.makedirs(os.path.dirname(_RPD_FILE), exist_ok=True)
    with open(_RPD_FILE, 'w') as f:
        json.dump(data, f)


def _increment_daily(provider):
    """Increment today's count for a provider. Returns the new count."""
    data = _load_daily_usage()
    data['counts'][provider] = data['counts'].get(provider, 0) + 1
    _save_daily_usage(data)
    return data['counts'][provider]


def _get_daily_remaining(provider):
    """How many requests remain today for this provider."""
    config = PROVIDERS.get(provider, {})
    rpd = config.get('rpd')
    if rpd is None:
        return float('inf')
    data = _load_daily_usage()
    used = data['counts'].get(provider, 0)
    return max(0, rpd - used)


def _build_prompt(person_name, body_text, birth_info='', death_info=''):
    """Build the extraction prompt (same as ai_extract.py)."""
    return f"""Given the following biographical text about {person_name} ({birth_info} - {death_info}), extract every location where this person is known or believed to have been.

For each location, provide:
- place_name: The name of the place (city, region, country as appropriate)
- date_start: ISO-8601 date (YYYY-MM-DD) for the start of their time there
- date_end: ISO-8601 date (YYYY-MM-DD) for the end of their time there
- date_precision: one of "day", "month", "season", "year", "decade", "approximate"
- date_display: human-readable date string
- description: brief description of what they were doing there (1-2 sentences)
- confidence: one of "certain", "probable", "possible", "speculative"

Return ONLY a JSON array sorted chronologically. Use negative years for BCE dates (e.g., -0043 for 44 BC). Be conservative with confidence levels. If dates are uncertain, use wider ranges and lower precision.

Biographical text:
{body_text[:8000]}"""


def _call_gemini(api_key, prompt, config):
    """Call Google Gemini API (native format, not OpenAI-compatible)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config['model']}:generateContent"
    headers = {'Content-Type': 'application/json'}
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'maxOutputTokens': config['max_tokens'],
        },
    }
    resp = requests.post(
        url, params={'key': api_key},
        headers=headers, json=payload, timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data['candidates'][0]['content']['parts'][0]['text']
    return text


def _call_openai_compatible(api_key, prompt, config):
    """Call an OpenAI-compatible API (Groq, Mistral, OpenRouter)."""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    payload = {
        'model': config['model'],
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': config['max_tokens'],
        'response_format': {'type': 'json_object'},
    }
    # OpenRouter wants extra headers
    if 'openrouter' in config.get('base_url', ''):
        headers['HTTP-Referer'] = 'https://whowaswherewhen.app'
        headers['X-Title'] = 'WhoWasWhereWhen'

    resp = requests.post(
        config['base_url'], headers=headers, json=payload, timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


def extract_locations(person_name, body_text, birth_info='', death_info='',
                      provider='gemini'):
    """Extract locations from biographical text using a free LLM API.

    Drop-in replacement for ai_extract.extract_locations().
    """
    global _last_request_time

    if provider not in PROVIDERS:
        print(f"  Unknown provider: {provider}")
        print(f"  Available: {', '.join(PROVIDERS.keys())}")
        return []

    config = PROVIDERS[provider]
    api_key = os.environ.get(config['env_key'], '') or os.environ.get(config.get('env_key_alt', ''), '')
    if not api_key:
        print(f"  Warning: {config['env_key']} not set, skipping {config['name']} extraction")
        return []

    # Check daily limit
    remaining = _get_daily_remaining(provider)
    if remaining <= 0:
        print(f"  Daily limit reached for {config['name']} ({config.get('rpd')} RPD). Try again tomorrow.")
        return []

    prompt = _build_prompt(person_name, body_text, birth_info, death_info)

    # Rate limiting (RPM)
    now = time.time()
    wait = config['rate_limit_sleep'] - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.time()

    # Call with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if provider.startswith('gemini'):
                text = _call_gemini(api_key, prompt, config)
            else:
                text = _call_openai_compatible(api_key, prompt, config)
            _increment_daily(provider)

            # Parse JSON from response
            text = text.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()

            # Handle responses wrapped in an object
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Some models wrap the array in an object
                for key in ('locations', 'data', 'results', 'items'):
                    if key in parsed and isinstance(parsed[key], list):
                        parsed = parsed[key]
                        break
                else:
                    # Try to find any list value
                    for v in parsed.values():
                        if isinstance(v, list):
                            parsed = v
                            break

            if isinstance(parsed, list):
                return parsed

            print(f"  Warning: {config['name']} response was not a JSON array")
            return []

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                backoff = config['rate_limit_sleep'] * (2 ** attempt)
                print(f"  Rate limited, waiting {backoff:.0f}s...")
                time.sleep(backoff)
                continue
            print(f"  HTTP error from {config['name']}: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"  Error parsing {config['name']} response as JSON: {e}")
            return []
        except Exception as e:
            print(f"  Error calling {config['name']}: {e}")
            return []

    print(f"  Max retries exceeded for {config['name']}")
    return []


def _build_chunk_prompt(person_name, chunk_text, chunk_num, total_chunks):
    """Build extraction prompt for a single text chunk."""
    return f"""You are extracting location data from a text about the real historical person {person_name}.
This is chunk {chunk_num} of {total_chunks}.

IMPORTANT: Only extract locations where the REAL person {person_name} actually was in real life.
Do NOT extract:
- Fictional locations from novels, plays, or poems
- Places where fictional characters went (even if the character is based on {person_name})
- Locations only mentioned in passing or as metaphors
- Places from works of fiction authored by {person_name}

For each real-life location where {person_name} was physically present, provide a JSON object with:
- "place_name": full place name with country/region (e.g. "Florence, Italy")
- "date_start": ISO date YYYY-MM-DD (estimate if needed)
- "date_end": ISO date YYYY-MM-DD
- "date_precision": "day", "month", "season", "year", "decade", or "approximate"
- "date_display": human-readable date string
- "description": 1-2 sentence description of what happened there
- "confidence": "certain", "probable", "possible", or "speculative"
- "source_text": the exact quote (1-2 sentences) from the text that supports this location claim

Return ONLY a JSON array. If no real-life locations found, return [].
Use negative years for BCE dates (e.g., -0044 for 44 BC).

Text:
{chunk_text}"""


def extract_locations_from_chunks(person_name, full_text, provider='gemini',
                                  chunk_size=6000, max_chunks=20):
    """Extract locations from a long text by splitting into chunks.

    Sends each chunk to the LLM separately, then merges and deduplicates.
    Respects daily request limits (RPD) — will stop early if the quota
    is exhausted and report how many requests remain.

    Returns list of location dicts (same format as extract_locations).
    """
    if not full_text:
        return []

    config = PROVIDERS.get(provider)
    if not config:
        print(f"  Unknown provider: {provider}")
        return []

    api_key = os.environ.get(config['env_key'], '') or os.environ.get(config.get('env_key_alt', ''), '')
    if not api_key:
        print(f"  {config['env_key']} not set — skipping LLM extraction")
        return []

    # Check daily limit before starting
    remaining = _get_daily_remaining(provider)
    rpd = config.get('rpd')
    if remaining <= 0:
        print(f"  Daily limit reached for {config['name']} ({rpd} RPD). Try again tomorrow.")
        return []

    # Split into chunks at paragraph boundaries
    paragraphs = full_text.split('\n\n')
    chunks = []
    current = ''
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            current = para
        else:
            current += '\n\n' + para
    if current.strip():
        chunks.append(current.strip())

    # Cap chunks to both max_chunks and remaining daily quota
    if len(chunks) > max_chunks:
        step = len(chunks) / max_chunks
        chunks = [chunks[int(i * step)] for i in range(max_chunks)]

    if rpd and len(chunks) > remaining:
        print(f"  Note: only {remaining} of {rpd} daily requests remain, "
              f"processing {remaining} of {len(chunks)} chunks")
        # Take evenly spaced subset to cover the text
        if remaining < len(chunks):
            step = len(chunks) / remaining
            chunks = [chunks[int(i * step)] for i in range(int(remaining))]

    total = len(chunks)
    print(f"  Processing {total} chunks with {config['name']} "
          f"({remaining} daily requests remaining)...")

    all_locations = []
    seen = set()

    for i, chunk in enumerate(chunks):
        # Re-check daily limit (may have been consumed by parallel runs)
        if _get_daily_remaining(provider) <= 0:
            print(f"    Daily limit reached after chunk {i}/{total}, stopping.")
            break

        prompt = _build_chunk_prompt(person_name, chunk, i + 1, total)

        # Rate limiting (RPM)
        global _last_request_time
        now = time.time()
        wait = config['rate_limit_sleep'] - (now - _last_request_time)
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.time()

        try:
            if provider.startswith('gemini'):
                text = _call_gemini(api_key, prompt, config)
            else:
                text = _call_openai_compatible(api_key, prompt, config)
            _increment_daily(provider)

            text = text.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()

            parsed = json.loads(text)
            if isinstance(parsed, dict):
                for key in ('locations', 'data', 'results', 'items'):
                    if key in parsed and isinstance(parsed[key], list):
                        parsed = parsed[key]
                        break
                else:
                    for v in parsed.values():
                        if isinstance(v, list):
                            parsed = v
                            break

            if isinstance(parsed, list):
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                new = 0
                for loc in parsed:
                    dedup_key = (loc.get('place_name', '').lower(), loc.get('date_start', ''))
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        # Add provenance metadata
                        loc['extraction_method'] = provider
                        loc['extraction_model'] = config['model']
                        loc['extracted_at'] = now_iso
                        loc['created_by'] = 'system'
                        all_locations.append(loc)
                        new += 1
                print(f"    Chunk {i+1}/{total}: {new} new locations")
            else:
                print(f"    Chunk {i+1}/{total}: no valid JSON array")

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                print(f"    Chunk {i+1}/{total}: rate limited by API, stopping.")
                break
            else:
                print(f"    Chunk {i+1}/{total}: HTTP error: {e}")
        except Exception as e:
            print(f"    Chunk {i+1}/{total}: error: {e}")

    remaining_after = _get_daily_remaining(provider)
    print(f"  Done. {remaining_after} daily requests remaining for {config['name']}.")
    return all_locations


# Source classification taxonomy (based on historiographic practice).
# Categories that contain real biographical location data:
SOURCE_CATEGORIES_USEFUL = {
    'official_record',       # Census, parish registers, court records, ship manifests
    'diary_journal',         # Day-by-day personal accounts, travel journals
    'letter_correspondence', # Personal/official letters, dispatches
    'autobiography_memoir',  # First-person life accounts written after the fact
    'scholarly_biography',   # Academic biographical studies with footnotes
    'popular_biography',     # Trade press biographies for general audience
    'travel_geography',      # Travel accounts, itineraries, route descriptions
    'reference_work',        # Encyclopedias, biographical dictionaries, chronologies
    'newspaper_periodical',  # Contemporary news reporting, magazine articles
    'academic_article',      # Peer-reviewed journal articles
    'inscription_artifact',  # Epigraphic/material evidence linking person to place
    # Legacy categories (backward compat with older registry entries)
    'biography', 'reference',
}

# Categories to reject (no reliable location data):
SOURCE_CATEGORIES_REJECT = {
    'historical_fiction',    # Novels, plays, poems with historical characters
    'hagiography_legend',    # Saints' lives, mythologized accounts
    'authored_fiction',      # Fiction/poetry written BY the person
    'authored_nonfiction',   # Non-biographical works written BY the person (treatises, science)
    'irrelevant',            # Not about this person at all
}

# Confidence mapping: source type → default confidence for extracted locations
SOURCE_CONFIDENCE = {
    'official_record': 'certain',
    'diary_journal': 'certain',
    'letter_correspondence': 'certain',
    'inscription_artifact': 'probable',
    'scholarly_biography': 'probable',
    'academic_article': 'probable',
    'travel_geography': 'probable',
    'autobiography_memoir': 'probable',
    'popular_biography': 'possible',
    'reference_work': 'possible',
    'newspaper_periodical': 'possible',
    'hagiography_legend': 'speculative',
}


def classify_books(person_name, books, provider='gemini'):
    """Ask the LLM to classify books using the historiographic source taxonomy.

    Args:
        person_name: The person we're researching
        books: List of dicts with at least 'title' and optionally 'authors'/'author'
        provider: LLM provider to use

    Returns:
        Dict mapping book index (0-based) to category string,
        or empty dict if LLM is unavailable.
    """
    if not books:
        return {}

    config = PROVIDERS.get(provider)
    if not config:
        return {}

    api_key = os.environ.get(config['env_key'], '') or os.environ.get(config.get('env_key_alt', ''), '')
    if not api_key:
        return {}

    remaining = _get_daily_remaining(provider)
    if remaining <= 0:
        return {}

    lines = []
    for i, b in enumerate(books):
        title = b.get('title', '?')
        author = b.get('author') or b.get('authors') or ''
        if isinstance(author, list):
            author = ', '.join(author)
        lines.append(f"{i+1}. \"{title}\" by {author}" if author else f"{i+1}. \"{title}\"")

    book_list = '\n'.join(lines)

    prompt = f"""I am building a database of real-life locations where the historical person {person_name} physically was during their lifetime.

Below is a list of texts found in a search. Classify each one into exactly one of these categories:

PRIMARY SOURCES (created at the time of events):
- "official_record" — government/institutional records: census, tax rolls, parish registers, court records, ship manifests, military service records
- "diary_journal" — day-by-day personal accounts written at the time: diaries, travel journals, ship logs
- "letter_correspondence" — personal or official letters, dispatches, telegrams written by or to {person_name}
- "inscription_artifact" — physical evidence: inscriptions, coins, tombstones, building dedications
- "newspaper_periodical" — contemporary news reporting, magazine articles from the person's era

SECONDARY SOURCES (analysis by later scholars):
- "scholarly_biography" — academic biography with footnotes and primary source research
- "popular_biography" — trade press biography for general readers, may lack footnotes
- "academic_article" — peer-reviewed journal article or scholarly essay
- "autobiography_memoir" — first-person life account written after the fact (memoirs, reminiscences)
- "travel_geography" — travel account, itinerary, or geographic description of a person's route

TERTIARY SOURCES:
- "reference_work" — encyclopedia, biographical dictionary, chronology, study guide

REJECT (not useful for real-life location extraction):
- "historical_fiction" — novel, play, poem, or creative work with historical characters
- "hagiography_legend" — saints' lives, mythologized/legendary accounts
- "authored_fiction" — fiction, poetry, or drama written BY {person_name} (not about their life)
- "authored_nonfiction" — non-biographical work written BY {person_name} (scientific treatise, philosophy, theory)
- "irrelevant" — not about {person_name}, or about a different person with the same name

Return a JSON array with one object per book:
{{"number": 1, "category": "scholarly_biography"}}

Books:
{book_list}"""

    global _last_request_time
    now = time.time()
    wait = config['rate_limit_sleep'] - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.time()

    try:
        if provider.startswith('gemini'):
            text = _call_gemini(api_key, prompt, config)
        else:
            text = _call_openai_compatible(api_key, prompt, config)
        _increment_daily(provider)

        text = text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    parsed = v
                    break

        if not isinstance(parsed, list):
            print("  Could not parse classification response")
            return {}

        result = {}
        for item in parsed:
            num = item.get('number', 0)
            cat = item.get('category', 'irrelevant').lower()
            if 1 <= num <= len(books):
                result[num - 1] = cat  # 0-based index

        return result

    except Exception as e:
        print(f"  Classification error: {e}")
        return {}


def filter_books_by_relevance(person_name, books, provider='gemini'):
    """Classify books and return only the useful ones.

    Wrapper around classify_books() for backward compatibility.
    """
    classifications = classify_books(person_name, books, provider)
    if not classifications:
        return books

    filtered = []
    for i, b in enumerate(books):
        cat = classifications.get(i, '')
        if cat in SOURCE_CATEGORIES_USEFUL:
            filtered.append(b)
        else:
            title = b.get('title', '?')
            print(f"    Skipping #{i+1} \"{title}\" ({cat})")

    print(f"  Book filter: {len(filtered)} useful of {len(books)} "
          f"({len(books) - len(filtered)} filtered out)")
    return filtered


def ingest_person(person_name=None, wikipedia_url=None, provider='gemini',
                  json_out=None, dry_run=False):
    """Full pipeline: Wikipedia scrape -> Free LLM extraction -> geocode -> DB import."""
    from ingest.wikipedia import fetch_page
    from ingest.geocode import geocode

    print(f"\n{'='*60}")
    print(f"Free LLM Ingest ({PROVIDERS[provider]['name']}): {person_name or wikipedia_url}")
    print(f"{'='*60}")

    # Step 1: Scrape Wikipedia
    print("\n1. Fetching Wikipedia page...")
    try:
        page = fetch_page(person_name=person_name, url=wikipedia_url)
    except Exception as e:
        print(f"   Error: {e}")
        return None

    print(f"   Name: {page['name']}")
    print(f"   Body text: {len(page['body_text'])} chars")

    # Step 2: Extract locations with free LLM
    print(f"\n2. Extracting locations with {PROVIDERS[provider]['name']}...")
    locations = extract_locations(
        page['name'], page['body_text'],
        page.get('birth_date_raw', ''), page.get('death_date_raw', ''),
        provider=provider,
    )
    print(f"   Extracted {len(locations)} locations")

    # Step 3: Geocode and build data structure
    print("\n3. Geocoding locations...")
    datapoints = []
    for loc in locations:
        place = loc.get('place_name', '')
        if not place:
            continue

        coords = geocode(place)
        if not coords:
            print(f"   Could not geocode: {place}")
            continue

        lat, lon = coords
        datapoints.append({
            'place_name': place,
            'latitude': lat,
            'longitude': lon,
            'date_start': loc.get('date_start', ''),
            'date_end': loc.get('date_end', ''),
            'date_precision': loc.get('date_precision', 'year'),
            'date_display': loc.get('date_display', ''),
            'description': loc.get('description', ''),
            'confidence': loc.get('confidence', 'probable'),
            'sources': [{
                'title': f'{PROVIDERS[provider]["name"]} extraction from Wikipedia: {page["name"]}',
                'url': page['wikipedia_url'],
                'source_type': 'ai_extracted',
            }],
        })

    print(f"   Geocoded {len(datapoints)} locations")

    data = {
        'person': {
            'name': page['name'],
            'description': page.get('description', ''),
            'wikipedia_url': page.get('wikipedia_url'),
            'image_url': page.get('image_url'),
        },
        'datapoints': datapoints,
    }

    # Step 4: Export or import
    if json_out:
        print(f"\n4. Writing JSON to {json_out}...")
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        print("\n4. Importing into database...")
        from ingest.import_json import import_data
        import_data(data, dry_run=dry_run)

    return data


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Extract locations using free LLM APIs (drop-in replacement for Claude)')
    parser.add_argument('--person', help='Person name to look up on Wikipedia')
    parser.add_argument('--wikipedia-url', help='Direct Wikipedia URL')
    parser.add_argument('--provider', default='gemini',
                        choices=list(PROVIDERS.keys()),
                        help='LLM provider (default: gemini)')
    parser.add_argument('--batch-file', help='Text file with one person name per line')
    parser.add_argument('--json-out', help='Export to JSON file instead of importing to DB')
    parser.add_argument('--dry-run', action='store_true', help='Validate without inserting')
    args = parser.parse_args()

    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"Batch processing {len(names)} persons with {PROVIDERS[args.provider]['name']}...")
        for name in names:
            try:
                ingest_person(person_name=name, provider=args.provider, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    elif args.person:
        ingest_person(person_name=args.person, provider=args.provider,
                      json_out=args.json_out, dry_run=args.dry_run)
    elif args.wikipedia_url:
        ingest_person(wikipedia_url=args.wikipedia_url, provider=args.provider,
                      json_out=args.json_out, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
