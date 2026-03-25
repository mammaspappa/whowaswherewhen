"""Unified CLI for all free (zero-cost) ingestion strategies.

Usage:
    python -m ingest.free_ingest wikidata --person "Leonardo da Vinci"
    python -m ingest.free_ingest ner --person "Leonardo da Vinci"
    python -m ingest.free_ingest llm --person "Nikola Tesla" --provider gemini
    python -m ingest.free_ingest category --person "Leonardo da Vinci"
    python -m ingest.free_ingest bulk --preset famous-historical --limit 100
    python -m ingest.free_ingest combined --person "Leonardo da Vinci"
"""

import argparse
import json
import os
import sys

# Auto-load .env file if present (for API keys)
_env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _, _val = _line.partition('=')
                os.environ.setdefault(_key.strip(), _val.strip().strip("'\""))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def cmd_wikidata(args):
    from ingest.free.wikidata_ingest import ingest_person
    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        for name in names:
            try:
                ingest_person(person_name=name, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error: {name}: {e}")
    else:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            wikidata_id=args.wikidata_id,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )


def cmd_ner(args):
    from ingest.free.spacy_ner import ingest_person
    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        for name in names:
            try:
                ingest_person(person_name=name, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error: {name}: {e}")
    else:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            text_file=getattr(args, 'text_file', None),
            json_out=args.json_out,
            dry_run=args.dry_run,
        )


def cmd_llm(args):
    from ingest.free.free_llm_extract import ingest_person
    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        for name in names:
            try:
                ingest_person(person_name=name, provider=args.provider, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error: {name}: {e}")
    else:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            provider=args.provider,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )


def cmd_category(args):
    from ingest.free.category_mining import ingest_person, discover_from_place, discover_from_category
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
    else:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )


def cmd_bulk(args):
    from ingest.free.bulk_discovery import bulk_ingest
    bulk_ingest(
        preset=args.preset,
        occupation=args.occupation,
        born_in=args.born_in,
        born_after=args.born_after,
        born_before=args.born_before,
        min_sitelinks=args.min_sitelinks,
        limit=args.limit,
        resume=args.resume,
        dry_run=args.dry_run,
        augment=args.augment,
    )


def cmd_archive(args):
    from ingest.free.internet_archive import ingest_person
    llm = getattr(args, 'llm', None)
    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        for name in names:
            try:
                ingest_person(person_name=name, max_texts=args.max_texts,
                              llm_provider=llm, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    else:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            max_texts=args.max_texts,
            llm_provider=llm,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )


def cmd_gutenberg(args):
    from ingest.free.gutenberg_free import ingest_person
    llm = getattr(args, 'llm', None)
    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        for name in names:
            try:
                ingest_person(person_name=name, max_books=args.max_books,
                              llm_provider=llm, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    else:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            gutenberg_url=args.gutenberg_url,
            max_books=args.max_books,
            llm_provider=llm,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )


def cmd_books(args):
    from ingest.free.google_books import ingest_person
    if args.batch_file:
        with open(args.batch_file) as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"Batch ingesting {len(names)} persons from Google Books...")
        for name in names:
            try:
                ingest_person(person_name=name, api_key=args.api_key,
                              max_books=args.max_books, dry_run=args.dry_run)
            except Exception as e:
                print(f"  Error processing {name}: {e}")
    else:
        ingest_person(
            person_name=args.person,
            wikipedia_url=args.wikipedia_url,
            api_key=args.api_key,
            max_books=args.max_books,
            json_out=args.json_out,
            dry_run=args.dry_run,
        )


def cmd_discover(args):
    """Discover books across all sources and populate the registry."""
    from ingest.free.book_registry import log_discovery, get_pending, get_summary
    from ingest.free.book_registry import USEFUL_RELEVANCE

    person_name = args.person
    if not person_name:
        print("--person is required for discover")
        return

    llm_provider = getattr(args, 'llm', None)
    sources_to_search = (args.sources or 'gutenberg,archive,google_books').split(',')

    print(f"\n{'='*60}")
    print(f"Book Discovery: {person_name}")
    print(f"Sources: {', '.join(sources_to_search)}")
    print(f"{'='*60}")

    all_books = []  # (source, title, author, url, identifier)

    # Search Gutenberg
    if 'gutenberg' in sources_to_search:
        print(f"\n--- Searching Project Gutenberg ---")
        try:
            from ingest.free.gutenberg_free import search_gutenberg
            books = search_gutenberg(person_name, max_results=args.max_books)
            print(f"  Found {len(books)} books")
            for b in books:
                authors = ', '.join(b.get('authors', []))
                book_id = str(b['id'])
                url = f"https://www.gutenberg.org/ebooks/{book_id}"
                all_books.append(('gutenberg', b['title'], authors, url, book_id))
                print(f"    {b['title']} ({authors or 'Unknown'})")
        except Exception as e:
            print(f"  Error: {e}")

    # Search Internet Archive
    if 'archive' in sources_to_search:
        print(f"\n--- Searching Internet Archive ---")
        try:
            from ingest.free.internet_archive import search_texts
            items = search_texts(person_name, max_results=args.max_books)
            print(f"  Found {len(items)} items")
            for it in items:
                identifier = it.get('identifier', '')
                title = it.get('title', '')
                creator = it.get('creator', '')
                if isinstance(creator, list):
                    creator = ', '.join(creator)
                url = f"https://archive.org/details/{identifier}"
                all_books.append(('archive', title, creator, url, identifier))
                print(f"    {title} ({creator or 'Unknown'})")
        except Exception as e:
            print(f"  Error: {e}")

    # Search Google Books
    if 'google_books' in sources_to_search:
        print(f"\n--- Searching Google Books ---")
        try:
            from ingest.free.google_books import search_books
            api_key = os.environ.get('GOOGLE_BOOKS_API_KEY')
            vols = search_books(person_name, api_key=api_key, max_results=args.max_books)
            print(f"  Found {len(vols)} volumes")
            for v in vols:
                authors = ', '.join(v.get('authors', []))
                url = v.get('infoLink') or v.get('previewLink', '')
                all_books.append(('google_books', v['title'], authors, url, url))
                print(f"    {v['title']} ({authors or 'Unknown'})")
        except Exception as e:
            print(f"  Error: {e}")

    if not all_books:
        print("\nNo books found across any source.")
        return

    # Classify with LLM if available
    classifications = {}
    if llm_provider:
        print(f"\n--- Classifying {len(all_books)} books with LLM ---")
        from ingest.free.free_llm_extract import classify_books, SOURCE_CATEGORIES_USEFUL
        book_dicts = [{'title': t, 'author': a} for _, t, a, _, _ in all_books]
        classifications = classify_books(person_name, book_dicts, provider=llm_provider)

        useful = sum(1 for c in classifications.values() if c in SOURCE_CATEGORIES_USEFUL)
        print(f"  Classified: {useful} useful, {len(classifications) - useful} rejected")
    else:
        from ingest.free.free_llm_extract import SOURCE_CATEGORIES_USEFUL

    # Log all discoveries to registry
    print(f"\n--- Saving to registry ---")
    new_count = 0
    for i, (source, title, author, url, identifier) in enumerate(all_books):
        relevance = classifications.get(i, '')
        is_new = log_discovery(source, person_name, title, author, url, identifier,
                               relevance=relevance)
        status_str = f"[{relevance}]" if relevance else ""
        if relevance and relevance not in SOURCE_CATEGORIES_USEFUL:
            status_str += " REJECTED"
        if is_new:
            new_count += 1
            print(f"  + {title} ({source}) {status_str}")
        else:
            print(f"  = {title} ({source}) already known {status_str}")

    # Summary
    pending = get_pending(person=person_name)
    print(f"\n{'='*60}")
    print(f"Discovery complete: {new_count} new books added")
    print(f"Pending extraction: {len(pending)} books")
    if pending:
        print(f"\nRun extraction with:")
        print(f"  .venv/bin/python -m ingest.free_ingest extract --person \"{person_name}\" --llm gemini-3.1")
    print(f"\nReview the registry:")
    print(f"  .venv/bin/python -m ingest.free_ingest registry list --person \"{person_name}\"")
    print(f"{'='*60}")


def cmd_extract(args):
    """Extract locations from pending books in the registry."""
    from ingest.free.book_registry import get_pending, log_ingestion, log_discovery

    person_name = getattr(args, 'person', None)
    source_filter = getattr(args, 'source', None)
    llm_provider = getattr(args, 'llm', None)
    dry_run = getattr(args, 'dry_run', False)
    limit = getattr(args, 'limit', None)

    pending = get_pending(source=source_filter, person=person_name)
    if not pending:
        print("No pending books in registry. Run 'discover' first.")
        return

    if limit:
        pending = pending[:limit]

    print(f"\n{'='*60}")
    print(f"Book Extraction: {len(pending)} pending books")
    if llm_provider:
        print(f"Method: {llm_provider}")
    else:
        print(f"Method: pattern matching")
    print(f"{'='*60}")

    # Get person info from Wikipedia (once per person)
    from ingest.wikipedia import fetch_page
    from ingest.free.date_resolver import resolve_date
    from ingest.geocode import geocode
    from ingest.import_json import import_data

    person_cache = {}

    total_dp = 0
    for i, book in enumerate(pending):
        source = book['source']
        title = book['title']
        identifier = book['identifier']
        person = book['person']
        url = book['url']

        print(f"\n--- [{i+1}/{len(pending)}] {title} ---")
        print(f"    Source: {source} | Person: {person}")

        # Get person data (cached)
        if person not in person_cache:
            wiki = fetch_page(person_name=person)
            if wiki:
                pd = {
                    'name': wiki.get('name') or person,
                    'description': wiki.get('description'),
                    'wikipedia_url': wiki.get('wikipedia_url'),
                    'image_url': wiki.get('image_url'),
                }
                for field, raw_key in [('birth', 'birth_date_raw'), ('death', 'death_date_raw')]:
                    raw = wiki.get(raw_key)
                    if raw:
                        ds, de, prec, display = resolve_date(raw)
                        if ds:
                            pd[f'{field}_date_start'] = ds
                            pd[f'{field}_date_end'] = de or ds
                            pd[f'{field}_date_display'] = display
                person_cache[person] = pd
            else:
                person_cache[person] = {'name': person}

        person_data = person_cache[person]

        # Download text based on source
        text = None
        method = llm_provider or 'pattern'

        if source == 'gutenberg':
            from ingest.gutenberg import download_text, strip_gutenberg_header_footer
            from ingest.free.gutenberg_free import _download_and_cache
            try:
                if identifier.startswith('http'):
                    raw = download_text(identifier)
                else:
                    # Need to find the text URL from Gutendex
                    from ingest.free.gutenberg_free import search_gutenberg
                    books = search_gutenberg(person, max_results=20)
                    text_url = None
                    for b in books:
                        if str(b['id']) == identifier:
                            text_url = b.get('text_url')
                            break
                    if text_url:
                        raw = _download_and_cache(identifier, text_url)
                    else:
                        raw = None
                text = strip_gutenberg_header_footer(raw) if raw else None
            except Exception as e:
                print(f"    Download failed: {e}")

        elif source == 'archive':
            from ingest.free.internet_archive import get_text_file_url, download_text as ia_download
            try:
                text_url = get_text_file_url(identifier)
                if text_url:
                    text = ia_download(identifier, text_url)
            except Exception as e:
                print(f"    Download failed: {e}")

        elif source == 'google_books':
            # Google Books doesn't have full text — use snippet extraction
            print(f"    Google Books: snippet-based extraction")
            from ingest.free.google_books import search_books_for_places, _extract_wiki_places
            from ingest.free.google_books import extract_from_volumes, search_books
            wiki = fetch_page(person_name=person)
            if wiki:
                api_key = os.environ.get('GOOGLE_BOOKS_API_KEY')
                vols = search_books(person, api_key=api_key, max_results=5)
                raw_results = extract_from_volumes(vols, person)
                # Build datapoints directly
                datapoints = []
                for loc, src_dict in raw_results:
                    coords = geocode(loc['place_name'])
                    if coords:
                        loc['latitude'] = coords[0]
                        loc['longitude'] = coords[1]
                        loc['sources'] = [src_dict]
                        datapoints.append(loc)
                data = {'person': person_data, 'datapoints': datapoints}
                if not dry_run:
                    import_data(data, dry_run=False)
                else:
                    import_data(data, dry_run=True)
                log_ingestion(source, identifier, method='pattern',
                              datapoints=len(datapoints), status='ingested')
                total_dp += len(datapoints)
                print(f"    Extracted {len(datapoints)} datapoints")
                continue

        if not text:
            print(f"    No text available, skipping")
            log_ingestion(source, identifier, method='', datapoints=0,
                          status='failed', notes='no text available')
            continue

        print(f"    Text: {len(text):,} chars")

        # Extract locations
        if llm_provider:
            from ingest.free.free_llm_extract import extract_locations_from_chunks
            locations = extract_locations_from_chunks(person, text, provider=llm_provider)
        else:
            from ingest.free.internet_archive import extract_locations_from_fulltext
            locations = extract_locations_from_fulltext(text, person)

        # Geocode and build datapoints
        datapoints = []
        for loc in locations:
            place = loc.get('place_name', '').strip()
            if not place:
                continue
            lat = loc.get('latitude')
            lon = loc.get('longitude')
            if lat is None or lon is None:
                coords = geocode(place)
                if coords:
                    loc['latitude'] = coords[0]
                    loc['longitude'] = coords[1]
                    loc['geocode_source'] = 'nominatim'
                else:
                    continue
            loc['sources'] = [{
                'title': title,
                'url': url,
                'author': book.get('author'),
                'source_type': 'book',
            }]
            datapoints.append(loc)

        data = {'person': person_data, 'datapoints': datapoints}
        import_data(data, dry_run=dry_run)
        log_ingestion(source, identifier, method=method,
                      datapoints=len(datapoints), status='ingested')
        total_dp += len(datapoints)
        print(f"    Result: {len(datapoints)} datapoints")

    print(f"\n{'='*60}")
    print(f"Extraction complete: {total_dp} total datapoints from {len(pending)} books")
    print(f"{'='*60}")


def cmd_combined(args):
    """Run Wikidata + NER + dedup for maximum coverage."""
    from ingest.free.dedup import deduplicate

    person_name = args.person
    wikipedia_url = args.wikipedia_url

    print(f"\n{'='*60}")
    print(f"Combined Ingest: {person_name or wikipedia_url}")
    print(f"{'='*60}")

    all_datapoints = []
    person_data = None

    # Step 1: Wikidata (high-confidence structured data)
    print("\n--- Strategy 1: Wikidata SPARQL ---")
    try:
        from ingest.free.wikidata_ingest import ingest_person as wikidata_ingest
        result = wikidata_ingest(
            person_name=person_name,
            wikipedia_url=wikipedia_url,
            json_out=os.devnull,
        )
        if result:
            person_data = result['person']
            all_datapoints.extend(result.get('datapoints', []))
            print(f"   Wikidata: {len(result.get('datapoints', []))} datapoints")
    except Exception as e:
        print(f"   Wikidata error: {e}")

    # Step 2: spaCy NER (fills in travels/events)
    print("\n--- Strategy 2: spaCy NER ---")
    try:
        from ingest.free.spacy_ner import ingest_person as ner_ingest
        result = ner_ingest(
            person_name=person_name,
            wikipedia_url=wikipedia_url,
            json_out='/dev/null',
        )
        if result:
            if not person_data:
                person_data = result['person']
            all_datapoints.extend(result.get('datapoints', []))
            print(f"   NER: {len(result.get('datapoints', []))} datapoints")
    except Exception as e:
        print(f"   NER error: {e}")

    # Step 3: Category mining (supplemental)
    print("\n--- Strategy 3: Category Mining ---")
    try:
        from ingest.free.category_mining import ingest_person as cat_ingest
        result = cat_ingest(
            person_name=person_name,
            wikipedia_url=wikipedia_url,
            json_out='/dev/null',
        )
        if result:
            if not person_data:
                person_data = result['person']
            all_datapoints.extend(result.get('datapoints', []))
            print(f"   Categories: {len(result.get('datapoints', []))} datapoints")
    except Exception as e:
        print(f"   Category error: {e}")

    if not person_data:
        print("\n   No data from any strategy.")
        return

    # Step 4: Deduplicate
    print(f"\n--- Deduplication ---")
    print(f"   Raw total: {len(all_datapoints)} datapoints")
    deduped = deduplicate(all_datapoints)
    print(f"   After dedup: {len(deduped)} unique datapoints")

    data = {'person': person_data, 'datapoints': deduped}

    # Step 5: Export or import
    if args.json_out:
        print(f"\nWriting JSON to {args.json_out}...")
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        print("\nImporting into database...")
        from ingest.import_json import import_data
        import_data(data, dry_run=args.dry_run)


def main():
    parser = argparse.ArgumentParser(
        description='Free (zero-cost) data ingestion for WhoWasWhereWhen',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Strategies:
  wikidata    Structured data from Wikidata SPARQL (zero deps, zero API keys)
  ner         spaCy NER extraction from Wikipedia text (requires spacy)
  llm         Free LLM API extraction (Gemini/Groq/Mistral/OpenRouter)
  category    Wikipedia category mining (zero deps, zero API keys)
  discover    Find books across all sources, classify, populate registry
  extract     Process pending books from the registry
  registry    View/manage the book registry
  books       Google Books API — extract locations from book descriptions
  gutenberg   Project Gutenberg — full-text extraction (free, no API key)
  archive     Internet Archive — full-text extraction (free, no API key)
  bulk        Bulk discover hundreds of figures from Wikidata
  combined    Run wikidata + ner + category + dedup for max coverage
        """,
    )
    subparsers = parser.add_subparsers(dest='strategy', help='Ingestion strategy')

    # Common args
    def add_common_args(p):
        p.add_argument('--person', help='Person name')
        p.add_argument('--wikipedia-url', help='Wikipedia URL')
        p.add_argument('--batch-file', help='Text file with one name per line')
        p.add_argument('--json-out', help='Export to JSON instead of DB')
        p.add_argument('--dry-run', action='store_true', help='Validate without inserting')

    # Wikidata
    p_wiki = subparsers.add_parser('wikidata', help='Wikidata SPARQL ingestion')
    add_common_args(p_wiki)
    p_wiki.add_argument('--wikidata-id', help='Wikidata QID (e.g. Q762)')
    p_wiki.set_defaults(func=cmd_wikidata)

    # NER
    p_ner = subparsers.add_parser('ner', help='spaCy NER extraction')
    add_common_args(p_ner)
    p_ner.add_argument('--text-file', help='Plain text file to extract from')
    p_ner.set_defaults(func=cmd_ner)

    # Free LLM
    p_llm = subparsers.add_parser('llm', help='Free LLM API extraction')
    add_common_args(p_llm)
    p_llm.add_argument('--provider', default='gemini',
                       choices=['gemini', 'gemini-flash', 'gemini-3', 'gemini-3.1', 'groq', 'mistral', 'openrouter'],
                       help='LLM provider (default: gemini)')
    p_llm.set_defaults(func=cmd_llm)

    # Category
    p_cat = subparsers.add_parser('category', help='Wikipedia category mining')
    add_common_args(p_cat)
    p_cat.add_argument('--discover-from-place', help='Discover people from a place')
    p_cat.add_argument('--discover-from-category', help='Discover people from a category')
    p_cat.add_argument('--limit', type=int, default=500)
    p_cat.set_defaults(func=cmd_category)

    # Discover (phase 1: find books, classify, populate registry)
    p_disc = subparsers.add_parser('discover', help='Find books across all sources and populate registry')
    p_disc.add_argument('--person', required=True, help='Person name to search for')
    p_disc.add_argument('--sources', default='gutenberg,archive,google_books',
                        help='Comma-separated sources to search (default: all)')
    p_disc.add_argument('--max-books', type=int, default=10,
                        help='Max books per source (default 10)')
    p_disc.add_argument('--llm', choices=['gemini', 'gemini-flash', 'gemini-3', 'gemini-3.1', 'groq', 'mistral', 'openrouter'],
                        help='Use LLM to classify book relevance')
    p_disc.set_defaults(func=cmd_discover)

    # Extract (phase 2: process pending books from registry)
    p_ext = subparsers.add_parser('extract', help='Process pending books from the registry')
    p_ext.add_argument('--person', help='Only extract for this person')
    p_ext.add_argument('--source', help='Only extract from this source (gutenberg, archive, google_books)')
    p_ext.add_argument('--llm', choices=['gemini', 'gemini-flash', 'gemini-3', 'gemini-3.1', 'groq', 'mistral', 'openrouter'],
                       help='Use LLM for extraction (otherwise pattern matching)')
    p_ext.add_argument('--limit', type=int, help='Max books to process')
    p_ext.add_argument('--dry-run', action='store_true', help='Preview without inserting')
    p_ext.set_defaults(func=cmd_extract)

    # Book Registry (view/manage)
    p_reg = subparsers.add_parser('registry', help='View/manage the book registry')
    p_reg.add_argument('action', nargs='?', default='summary',
                       choices=['summary', 'list', 'pending'],
                       help='Action: summary (default), list, or pending')
    p_reg.add_argument('--source', help='Filter by source (google_books, gutenberg, archive)')
    p_reg.add_argument('--person', help='Filter by person name')
    p_reg.set_defaults(func=lambda args: __import__('ingest.free.book_registry', fromlist=['main']).main_action(args.action, args.source, args.person))

    # Google Books
    p_books = subparsers.add_parser('books', help='Google Books API extraction')
    add_common_args(p_books)
    p_books.add_argument('--api-key', help='Google Books API key (or set GOOGLE_BOOKS_API_KEY)')
    p_books.add_argument('--max-books', type=int, default=10, help='Max books to search (default 10)')
    p_books.set_defaults(func=cmd_books)

    # Gutenberg (free)
    p_gut = subparsers.add_parser('gutenberg', help='Project Gutenberg full-text extraction')
    add_common_args(p_gut)
    p_gut.add_argument('--gutenberg-url', help='Specific Gutenberg ebook URL')
    p_gut.add_argument('--max-books', type=int, default=5, help='Max books to search (default 5)')
    p_gut.add_argument('--llm', choices=['gemini', 'gemini-flash', 'gemini-3', 'gemini-3.1', 'groq', 'mistral', 'openrouter'],
                       help='Use LLM for extraction instead of pattern matching (set GOOGLE_API_KEY etc.)')
    p_gut.set_defaults(func=cmd_gutenberg)

    # Internet Archive
    p_ia = subparsers.add_parser('archive', help='Internet Archive full-text extraction')
    add_common_args(p_ia)
    p_ia.add_argument('--max-texts', type=int, default=5, help='Max texts to process (default 5)')
    p_ia.add_argument('--llm', choices=['gemini', 'gemini-flash', 'gemini-3', 'gemini-3.1', 'groq', 'mistral', 'openrouter'],
                      help='Use LLM for extraction instead of pattern matching (set GOOGLE_API_KEY etc.)')
    p_ia.set_defaults(func=cmd_archive)

    # Bulk
    p_bulk = subparsers.add_parser('bulk', help='Bulk discovery from Wikidata')
    p_bulk.add_argument('--preset', help='Predefined query preset')
    p_bulk.add_argument('--occupation', help='Filter by occupation')
    p_bulk.add_argument('--born-in', help='Filter by birth country')
    p_bulk.add_argument('--born-after', type=int)
    p_bulk.add_argument('--born-before', type=int)
    p_bulk.add_argument('--min-sitelinks', type=int, default=20)
    p_bulk.add_argument('--limit', type=int, default=100)
    p_bulk.add_argument('--resume', action='store_true')
    p_bulk.add_argument('--augment', action='store_true',
                        help='Re-process persons already in DB to add new datapoints (default: skip)')
    p_bulk.add_argument('--dry-run', action='store_true')
    p_bulk.set_defaults(func=cmd_bulk)

    # Combined
    p_combined = subparsers.add_parser('combined', help='Wikidata + NER + categories + dedup')
    add_common_args(p_combined)
    p_combined.set_defaults(func=cmd_combined)

    args = parser.parse_args()
    if not args.strategy:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
