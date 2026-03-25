"""Strategy 4: Wikipedia Category Mining.

Infers locations from Wikipedia categories like "People from Florence" or
"16th-century Italian painters". Zero AI, zero NLP, zero new dependencies.
Also supports reverse mode: discover people from a category.
"""

import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

MEDIAWIKI_API = 'https://en.wikipedia.org/w/api.php'
USER_AGENT = 'WhoWasWhereWhen/1.0 (https://github.com/whowaswherewhen; bot)'

# Regex patterns to extract location from category names
CATEGORY_PATTERNS = [
    # "People from Florence" -> Florence
    (r'^People from (.+)$', 'Resided in or associated with {place}'),
    # "People from the Province of Florence" -> Province of Florence
    (r'^People from the (.+)$', 'Associated with {place}'),
    # "Births in Florence" -> Florence
    (r'^Births in (.+)$', 'Born in {place}'),
    # "Deaths in Florence" -> Florence
    (r'^Deaths in (.+)$', 'Died in {place}'),
    # "Residents of Florence" -> Florence
    (r'^Residents of (.+)$', 'Resided in {place}'),
    # "University of Florence alumni" -> Florence
    (r'^University of (.+?) alumni$', 'Studied at University of {place}'),
    # "Alumni of the University of Oxford" -> Oxford
    (r'^Alumni of the University of (.+)$', 'Studied at University of {place}'),
    # "Alumni of (.+ University)" -> extract city from university name if possible
    (r'^Academics of the University of (.+)$', 'Worked at University of {place}'),
    # "People educated at Eton College" style (less useful but captures some)
    (r'^People educated in (.+)$', 'Educated in {place}'),
    # "Burials at/in X" -> death location
    (r'^Burials (?:at|in) (.+)$', 'Buried in {place}'),
    # "Prisoners in X" or "Prisoners and detainees of X"
    (r'^Prisoners (?:in|and detainees of) (.+)$', 'Imprisoned in {place}'),
    # "Painters from Florence", "Scientists from Berlin", etc.
    (r'^\w+ from (.+)$', 'Associated with {place}'),
    # "Writers from X", "Artists from X" (multi-word profession)
    (r'^[\w\s]+ from (.+)$', 'Associated with {place}'),
    # "Ambassadors of X"
    (r'^Ambassadors of (?:the )?(.+)$', 'Ambassador of {place}'),
    # "X-century people from Y"
    (r'^\d+(?:st|nd|rd|th)-century people from (?:the )?(.+)$', 'Associated with {place}'),
]

# Demonym -> country mapping for "Italian painters" style categories
DEMONYM_TO_COUNTRY = {
    'albanian': 'Albania', 'american': 'United States', 'argentine': 'Argentina',
    'armenian': 'Armenia', 'australian': 'Australia', 'austrian': 'Austria',
    'belgian': 'Belgium', 'bolivian': 'Bolivia', 'bosnian': 'Bosnia',
    'brazilian': 'Brazil', 'british': 'United Kingdom', 'bulgarian': 'Bulgaria',
    'burmese': 'Myanmar', 'cambodian': 'Cambodia', 'canadian': 'Canada',
    'chilean': 'Chile', 'chinese': 'China', 'colombian': 'Colombia',
    'croatian': 'Croatia', 'cuban': 'Cuba', 'czech': 'Czech Republic',
    'danish': 'Denmark', 'dutch': 'Netherlands', 'ecuadorian': 'Ecuador',
    'egyptian': 'Egypt', 'english': 'England', 'estonian': 'Estonia',
    'ethiopian': 'Ethiopia', 'filipino': 'Philippines', 'finnish': 'Finland',
    'flemish': 'Flanders', 'french': 'France', 'georgian': 'Georgia',
    'german': 'Germany', 'greek': 'Greece', 'guatemalan': 'Guatemala',
    'hungarian': 'Hungary', 'icelandic': 'Iceland', 'indian': 'India',
    'indonesian': 'Indonesia', 'iranian': 'Iran', 'iraqi': 'Iraq',
    'irish': 'Ireland', 'israeli': 'Israel', 'italian': 'Italy',
    'jamaican': 'Jamaica', 'japanese': 'Japan', 'kenyan': 'Kenya',
    'korean': 'Korea', 'latvian': 'Latvia', 'lebanese': 'Lebanon',
    'lithuanian': 'Lithuania', 'luxembourgish': 'Luxembourg',
    'macedonian': 'North Macedonia', 'malaysian': 'Malaysia',
    'mexican': 'Mexico', 'mongolian': 'Mongolia', 'moroccan': 'Morocco',
    'nepali': 'Nepal', 'nicaraguan': 'Nicaragua', 'nigerian': 'Nigeria',
    'norwegian': 'Norway', 'ottoman': 'Ottoman Empire',
    'pakistani': 'Pakistan', 'panamanian': 'Panama', 'paraguayan': 'Paraguay',
    'persian': 'Persia', 'peruvian': 'Peru', 'polish': 'Poland',
    'portuguese': 'Portugal', 'romanian': 'Romania', 'roman': 'Rome',
    'russian': 'Russia', 'scottish': 'Scotland', 'serbian': 'Serbia',
    'singaporean': 'Singapore', 'slovak': 'Slovakia', 'slovenian': 'Slovenia',
    'south african': 'South Africa', 'south korean': 'South Korea',
    'spanish': 'Spain', 'swedish': 'Sweden', 'swiss': 'Switzerland',
    'taiwanese': 'Taiwan', 'thai': 'Thailand', 'tunisian': 'Tunisia',
    'turkish': 'Turkey', 'ukrainian': 'Ukraine', 'uruguayan': 'Uruguay',
    'uzbek': 'Uzbekistan', 'venezuelan': 'Venezuela', 'vietnamese': 'Vietnam',
    'welsh': 'Wales',
}

# Century pattern: "16th-century Italian painters" -> century + nationality
CENTURY_PATTERN = re.compile(r'^(\d+)(?:st|nd|rd|th)-century\s+(\w+)', re.IGNORECASE)


def _api_request(params):
    """Make a MediaWiki API request."""
    params['format'] = 'json'
    resp = requests.get(MEDIAWIKI_API, params=params,
                        headers={'User-Agent': USER_AGENT}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_categories(title):
    """Fetch all categories for a Wikipedia article."""
    categories = []
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'categories',
        'cllimit': '500',
        'clshow': '!hidden',
    }
    data = _api_request(params)
    pages = data.get('query', {}).get('pages', {})
    for page in pages.values():
        for cat in page.get('categories', []):
            # Remove "Category:" prefix
            cat_name = cat['title'].replace('Category:', '')
            categories.append(cat_name)
    return categories


def extract_locations_from_categories(categories):
    """Extract location information from category names.

    Returns list of dicts with: place_name, description, source (category name)
    """
    locations = []
    seen_places = set()

    for cat in categories:
        # Try specific patterns first
        for pattern, desc_template in CATEGORY_PATTERNS:
            match = re.match(pattern, cat)
            if match:
                place = match.group(1).strip()
                # Skip overly generic or non-place results
                if place.lower() in ('the', 'a', 'an', 'unknown'):
                    continue
                if place.lower() not in seen_places:
                    seen_places.add(place.lower())
                    locations.append({
                        'place_name': place,
                        'description': desc_template.format(place=place),
                        'category': cat,
                    })
                break

        # Try demonym pattern: "Italian painters", "French writers"
        century_match = CENTURY_PATTERN.match(cat)
        if century_match:
            century = int(century_match.group(1))
            demonym = century_match.group(2).lower()
            country = DEMONYM_TO_COUNTRY.get(demonym)
            if country and country.lower() not in seen_places:
                seen_places.add(country.lower())
                # Century to approximate year range
                start_year = (century - 1) * 100
                end_year = century * 100 - 1
                locations.append({
                    'place_name': country,
                    'description': f'Active in {country} ({century}th century)',
                    'category': cat,
                    'century_start': start_year,
                    'century_end': end_year,
                })
        else:
            # Simple demonym match: "Italian painters" without century
            words = cat.split()
            if len(words) >= 2:
                demonym = words[0].lower()
                country = DEMONYM_TO_COUNTRY.get(demonym)
                if country and country.lower() not in seen_places:
                    seen_places.add(country.lower())
                    locations.append({
                        'place_name': country,
                        'description': f'Associated with {country} (nationality)',
                        'category': cat,
                    })

    return locations


def ingest_person(person_name=None, wikipedia_url=None,
                  json_out=None, dry_run=False):
    """Extract location data from Wikipedia categories for a person."""
    from ingest.wikipedia import fetch_page
    from ingest.geocode import geocode

    print(f"\n{'='*60}")
    print(f"Category Mining: {person_name or wikipedia_url}")
    print(f"{'='*60}")

    # Step 1: Fetch Wikipedia page (for infobox data and title)
    print("\n1. Fetching Wikipedia page...")
    try:
        page = fetch_page(person_name=person_name, url=wikipedia_url)
    except Exception as e:
        print(f"   Error: {e}")
        return None

    title = page['name']
    print(f"   Title: {title}")

    # Step 2: Fetch categories
    print("\n2. Fetching categories...")
    # Use underscore format for MediaWiki API
    wiki_title = title.replace(' ', '_')
    categories = fetch_categories(wiki_title)
    print(f"   Found {len(categories)} categories")

    # Step 3: Extract locations from categories
    print("\n3. Extracting locations from categories...")
    cat_locations = extract_locations_from_categories(categories)
    print(f"   Extracted {len(cat_locations)} locations from categories")
    for loc in cat_locations:
        print(f"   - {loc['place_name']} (from: {loc['category']})")

    # Step 4: Geocode and build datapoints
    print("\n4. Geocoding...")
    datapoints = []
    birth_date = page.get('birth_date_raw', '')
    death_date = page.get('death_date_raw', '')

    for loc in cat_locations:
        place = loc['place_name']
        coords = geocode(place)
        if not coords:
            print(f"   Could not geocode: {place}")
            continue
        lat, lon = coords

        # Use century dates if available, otherwise use life span
        if 'century_start' in loc:
            date_start = f"{loc['century_start']:04d}-01-01"
            date_end = f"{loc['century_end']:04d}-12-31"
            date_display = f"{loc['century_start']}s - {loc['century_end']}s"
            precision = 'approximate'
        else:
            # Default to life span
            date_start = ''
            date_end = ''
            date_display = 'Lifetime'
            precision = 'approximate'

        # Skip entries with no dates (can't insert without date_start)
        if not date_start:
            continue

        datapoints.append({
            'place_name': place,
            'latitude': lat,
            'longitude': lon,
            'date_start': date_start,
            'date_end': date_end or date_start,
            'date_precision': precision,
            'date_display': date_display,
            'description': loc['description'],
            'confidence': 'possible',
            'sources': [{
                'title': f'Wikipedia category: {loc["category"]}',
                'url': page.get('wikipedia_url', ''),
                'source_type': 'webpage',
            }],
        })

    print(f"   {len(datapoints)} geocoded datapoints")

    data = {
        'person': {
            'name': title,
            'description': page.get('description', ''),
            'wikipedia_url': page.get('wikipedia_url'),
            'image_url': page.get('image_url'),
        },
        'datapoints': datapoints,
    }

    if json_out:
        print(f"\n5. Writing JSON to {json_out}...")
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        print("\n5. Importing into database...")
        from ingest.import_json import import_data
        import_data(data, dry_run=dry_run)

    return data


def discover_from_category(category_name, limit=500):
    """Discover people from a Wikipedia category.

    Returns list of (title, url) tuples.
    """
    if not category_name.startswith('Category:'):
        category_name = f'Category:{category_name}'

    print(f"\nDiscovering people from: {category_name}")
    members = []
    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': category_name,
        'cmtype': 'page',
        'cmnamespace': '0',  # Main namespace only
        'cmlimit': str(min(limit, 500)),
    }

    data = _api_request(params)
    for member in data.get('query', {}).get('categorymembers', []):
        title = member['title']
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        members.append((title, url))

    print(f"   Found {len(members)} articles")
    return members


def discover_from_place(place_name, limit=500):
    """Discover people associated with a place via Wikipedia categories."""
    # Try common category patterns
    category_names = [
        f"Category:People from {place_name}",
        f"Category:People of {place_name}",
    ]

    all_members = []
    seen = set()

    for cat in category_names:
        try:
            members = discover_from_category(cat, limit=limit)
            for title, url in members:
                if title not in seen:
                    seen.add(title)
                    all_members.append((title, url))
        except Exception:
            continue

    return all_members[:limit]


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Mine Wikipedia categories for location data')
    parser.add_argument('--person', help='Person name')
    parser.add_argument('--wikipedia-url', help='Wikipedia URL')
    parser.add_argument('--discover-from-place', help='Discover people from a place')
    parser.add_argument('--discover-from-category', help='Discover people from a Wikipedia category')
    parser.add_argument('--limit', type=int, default=500, help='Max results for discovery')
    parser.add_argument('--json-out', help='Export to JSON file')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.discover_from_place:
        members = discover_from_place(args.discover_from_place, args.limit)
        print(f"\nPeople from {args.discover_from_place}:")
        for title, url in members:
            print(f"  - {title}")
        print(f"\nTotal: {len(members)}")
    elif args.discover_from_category:
        members = discover_from_category(args.discover_from_category, args.limit)
        print(f"\nPeople in category:")
        for title, url in members:
            print(f"  - {title}")
        print(f"\nTotal: {len(members)}")
    elif args.person:
        ingest_person(person_name=args.person, json_out=args.json_out, dry_run=args.dry_run)
    elif args.wikipedia_url:
        ingest_person(wikipedia_url=args.wikipedia_url, json_out=args.json_out, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
