"""Strategy 2: spaCy NER pipeline for location extraction.

Extracts (location, date) pairs from biographical text using named entity
recognition and sentence co-occurrence heuristics. Zero API cost.
Requires: spacy + en_core_web_md model.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ingest.free.date_resolver import resolve_date

# Biographical phrase patterns for high-confidence extraction
BIO_PATTERNS = [
    (r'born (?:in|at|near) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'certain', 'Born in {place}'),
    (r'died (?:in|at|near) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'certain', 'Died in {place}'),
    (r'(?:moved|relocated|emigrated|immigrated) to ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Moved to {place}'),
    (r'(?:traveled|travelled|journeyed|voyaged) to ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Traveled to {place}'),
    (r'(?:settled|resided|lived) (?:in|at) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Resided in {place}'),
    (r'(?:arrived|returned) (?:in|at|to) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Arrived in {place}'),
    (r'(?:fled|escaped|exiled) to ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Fled to {place}'),
    (r'(?:imprisoned|jailed|incarcerated) (?:in|at) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Imprisoned in {place}'),
    (r'(?:studied|enrolled|educated) (?:in|at) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Studied in {place}'),
    (r'(?:appointed|stationed|posted|assigned) (?:to|in|at) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'probable', 'Stationed in {place}'),
    (r'(?:buried|interred) (?:in|at) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'certain', 'Buried in {place}'),
    (r'(?:visited|toured) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', 'possible', 'Visited {place}'),
]

COMPILED_BIO_PATTERNS = [(re.compile(p, re.IGNORECASE), conf, desc) for p, conf, desc in BIO_PATTERNS]

# Places to ignore (too generic or commonly false positives)
IGNORE_PLACES = {
    'the', 'this', 'that', 'his', 'her', 'their', 'its',
    'first', 'second', 'third', 'new', 'old', 'great', 'early', 'late',
    'january', 'february', 'march', 'april', 'may', 'june', 'july',
    'august', 'september', 'october', 'november', 'december',
    'christian', 'catholic', 'protestant', 'jewish', 'muslim', 'buddhist',
    'european', 'asian', 'african', 'north', 'south', 'east', 'west',
}


def _load_spacy():
    """Load spaCy model, with helpful error if not installed."""
    try:
        import spacy
    except ImportError:
        print("  Error: spaCy not installed. Install with:")
        print("    pip install spacy")
        print("    python -m spacy download en_core_web_md")
        sys.exit(1)

    try:
        return spacy.load('en_core_web_md')
    except OSError:
        try:
            return spacy.load('en_core_web_sm')
        except OSError:
            print("  Error: No spaCy English model found. Install with:")
            print("    python -m spacy download en_core_web_md")
            sys.exit(1)


def extract_entities(text, nlp):
    """Extract location and date entities from text using spaCy NER.

    Returns list of dicts with: text, label, start_char, end_char, sent_idx
    """
    doc = nlp(text)
    entities = []

    for sent_idx, sent in enumerate(doc.sents):
        for ent in sent.ents:
            if ent.label_ in ('GPE', 'LOC', 'FAC', 'DATE', 'EVENT'):
                entities.append({
                    'text': ent.text,
                    'label': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char,
                    'sent_idx': sent_idx,
                    'sent_text': sent.text.strip(),
                })

    return entities


def _is_valid_place(text):
    """Check if extracted text looks like a real place name."""
    if not text or len(text) < 2:
        return False
    if text.lower() in IGNORE_PLACES:
        return False
    # Must start with uppercase
    if not text[0].isupper():
        return False
    # Skip if it's just a number
    if text.isdigit():
        return False
    return True


def extract_location_date_pairs(text, nlp):
    """Extract (location, date, confidence, description) tuples from text.

    Uses three approaches:
    1. Biographical phrase patterns (highest confidence)
    2. Sentence co-occurrence of NER entities (medium confidence)
    3. Remaining locations without dates (lowest confidence)
    """
    pairs = []
    seen = set()  # (place, date_start) dedup

    # Approach 1: Biographical phrase patterns
    sentences = text.split('.')
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        for pattern, confidence, desc_template in COMPILED_BIO_PATTERNS:
            match = pattern.search(sent)
            if not match:
                continue

            place = match.group(1).strip()
            if not _is_valid_place(place):
                continue

            # Try to find a date in the same sentence
            date_start, date_end, precision, display = resolve_date(sent)

            if date_start:
                key = (place.lower(), date_start)
                if key not in seen:
                    seen.add(key)
                    pairs.append({
                        'place_name': place,
                        'date_start': date_start,
                        'date_end': date_end or date_start,
                        'date_precision': precision or 'year',
                        'date_display': display or '',
                        'description': desc_template.format(place=place),
                        'confidence': confidence,
                        'sent': sent[:200],
                    })

    # Approach 2: Sentence co-occurrence via spaCy NER
    entities = extract_entities(text, nlp)

    # Group entities by sentence
    sent_groups = {}
    for ent in entities:
        idx = ent['sent_idx']
        if idx not in sent_groups:
            sent_groups[idx] = {'locations': [], 'dates': [], 'sent_text': ent['sent_text']}
        if ent['label'] in ('GPE', 'LOC', 'FAC'):
            sent_groups[idx]['locations'].append(ent['text'])
        elif ent['label'] == 'DATE':
            sent_groups[idx]['dates'].append(ent['text'])

    for idx, group in sent_groups.items():
        for loc in group['locations']:
            if not _is_valid_place(loc):
                continue
            for date_text in group['dates']:
                date_start, date_end, precision, display = resolve_date(date_text)
                if not date_start:
                    continue

                key = (loc.lower(), date_start)
                if key in seen:
                    continue
                seen.add(key)

                # Use sentence as description (trimmed)
                desc = group['sent_text']
                if len(desc) > 200:
                    desc = desc[:197] + '...'

                pairs.append({
                    'place_name': loc,
                    'date_start': date_start,
                    'date_end': date_end or date_start,
                    'date_precision': precision or 'year',
                    'date_display': display or '',
                    'description': desc,
                    'confidence': 'possible',
                    'sent': desc,
                })

    return pairs


def ingest_person(person_name=None, wikipedia_url=None, text_file=None,
                  json_out=None, dry_run=False):
    """Full NER pipeline: fetch text -> spaCy NER -> geocode -> DB import."""
    from ingest.geocode import geocode

    print(f"\n{'='*60}")
    print(f"spaCy NER Ingest: {person_name or wikipedia_url or text_file}")
    print(f"{'='*60}")

    # Step 1: Get text
    print("\n1. Loading text...")
    if text_file:
        with open(text_file) as f:
            body_text = f.read()
        page = {'name': person_name or 'Unknown', 'description': '', 'wikipedia_url': '', 'image_url': None}
    else:
        from ingest.wikipedia import fetch_page
        try:
            page = fetch_page(person_name=person_name, url=wikipedia_url)
        except Exception as e:
            print(f"   Error: {e}")
            return None
        body_text = page['body_text']

    print(f"   Name: {page['name']}")
    print(f"   Text: {len(body_text)} chars")

    # Step 2: Load spaCy and extract
    print("\n2. Running spaCy NER...")
    nlp = _load_spacy()
    pairs = extract_location_date_pairs(body_text, nlp)
    print(f"   Extracted {len(pairs)} location-date pairs")

    # Step 3: Geocode
    print("\n3. Geocoding...")
    datapoints = []
    for pair in pairs:
        place = pair['place_name']
        coords = geocode(place)
        if not coords:
            print(f"   Could not geocode: {place}")
            continue
        lat, lon = coords
        datapoints.append({
            'place_name': place,
            'latitude': lat,
            'longitude': lon,
            'date_start': pair['date_start'],
            'date_end': pair['date_end'],
            'date_precision': pair['date_precision'],
            'date_display': pair['date_display'],
            'description': pair['description'],
            'confidence': pair['confidence'],
            'sources': [{
                'title': f'NER extraction from Wikipedia: {page["name"]}',
                'url': page.get('wikipedia_url', ''),
                'source_type': 'other',
            }],
        })
        print(f"   + {place} ({pair['date_display']})")

    print(f"\n   {len(datapoints)} geocoded datapoints")

    data = {
        'person': {
            'name': page['name'],
            'description': page.get('description', ''),
            'wikipedia_url': page.get('wikipedia_url'),
            'image_url': page.get('image_url'),
        },
        'datapoints': datapoints,
    }

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
    parser = argparse.ArgumentParser(description='Extract locations using spaCy NER (free, local)')
    parser.add_argument('--person', help='Person name')
    parser.add_argument('--wikipedia-url', help='Wikipedia URL')
    parser.add_argument('--text-file', help='Plain text file to extract from')
    parser.add_argument('--person-name', help='Person name (when using --text-file)')
    parser.add_argument('--batch-file', help='Text file with one person name per line')
    parser.add_argument('--json-out', help='Export to JSON file')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        for name in names:
            try:
                ingest_person(person_name=name, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    elif args.text_file:
        ingest_person(text_file=args.text_file, person_name=args.person_name,
                      json_out=args.json_out, dry_run=args.dry_run)
    elif args.person:
        ingest_person(person_name=args.person, json_out=args.json_out, dry_run=args.dry_run)
    elif args.wikipedia_url:
        ingest_person(wikipedia_url=args.wikipedia_url, json_out=args.json_out, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
