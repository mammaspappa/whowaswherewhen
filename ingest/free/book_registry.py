"""Book registry — tracks all books discovered and ingested across strategies.

Maintains a CSV file at data/book_registry.csv with one row per book.
Two-phase workflow:
  1. `discover` — search all sources, classify with LLM, populate registry
  2. `extract`  — process pending books from the registry

CSV columns:
  source        - Strategy that found it (google_books, gutenberg, archive)
  person        - Person the book is about
  title         - Book title
  author        - Author(s)
  url           - Link to the book
  identifier    - Source-specific ID (Gutenberg ebook ID, IA identifier, etc.)
  discovered_at - ISO timestamp when the book was first found
  relevance     - LLM classification: biography, reference, fiction, authored, irrelevant
  status        - pending | approved | ingested | skipped | failed | rejected
  method        - How it was ingested (pattern, gemini, groq, etc.) or why skipped
  datapoints    - Number of datapoints extracted (0 if not ingested)
  notes         - Any additional info
"""

import csv
import os
from datetime import datetime, timezone

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'book_registry.csv')

FIELDS = [
    'source', 'person', 'title', 'author', 'url', 'identifier',
    'discovered_at', 'relevance', 'score', 'status', 'method', 'datapoints', 'notes',
]

# Relevance categories that are useful for extraction.
# Import the canonical set from free_llm_extract if available, else use fallback.
try:
    from ingest.free.free_llm_extract import SOURCE_CATEGORIES_USEFUL as USEFUL_RELEVANCE
except ImportError:
    USEFUL_RELEVANCE = {
        'official_record', 'diary_journal', 'letter_correspondence',
        'autobiography_memoir', 'scholarly_biography', 'popular_biography',
        'travel_geography', 'reference_work', 'newspaper_periodical',
        'academic_article', 'inscription_artifact',
        # Legacy categories (backward compat)
        'biography', 'reference',
    }


def _ensure_file():
    """Create the CSV file with headers if it doesn't exist."""
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    if not os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()


def _read_all():
    """Read all rows from the registry."""
    _ensure_file()
    with open(REGISTRY_PATH, newline='') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # Handle old CSVs missing the relevance column
            for field in FIELDS:
                if field not in row:
                    row[field] = ''
            rows.append(row)
        return rows


def _write_all(rows):
    """Write all rows to the registry (full rewrite)."""
    _ensure_file()
    with open(REGISTRY_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, '') for k in FIELDS})


def _find_row(rows, source, identifier):
    """Find an existing row by source + identifier."""
    for i, row in enumerate(rows):
        if row['source'] == source and row['identifier'] == str(identifier):
            return i
    return None


def log_discovery(source, person, title, author, url, identifier,
                  relevance='', score='', notes=''):
    """Log a newly discovered book. Skips if already in the registry.

    Args:
        score: Usefulness score 1-10 from LLM (10 = most useful).
               Books with score 0 or empty are unscored.

    Returns True if this is a new discovery, False if already known.
    """
    rows = _read_all()
    idx = _find_row(rows, source, identifier)
    if idx is not None:
        # Update relevance/score if they were empty
        updated = False
        if relevance and not rows[idx].get('relevance'):
            rows[idx]['relevance'] = relevance
            if relevance not in USEFUL_RELEVANCE and rows[idx]['status'] == 'pending':
                rows[idx]['status'] = 'rejected'
                rows[idx]['notes'] = f'auto-rejected: {relevance}'
            updated = True
        if score and not rows[idx].get('score'):
            rows[idx]['score'] = str(score)
            updated = True
        if updated:
            _write_all(rows)
        return False

    # Auto-set status based on relevance
    if relevance and relevance not in USEFUL_RELEVANCE:
        status = 'rejected'
        notes = notes or f'auto-rejected: {relevance}'
    else:
        status = 'pending'

    rows.append({
        'source': source,
        'person': person,
        'title': title,
        'author': author or '',
        'url': url,
        'identifier': str(identifier),
        'discovered_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'relevance': relevance,
        'score': str(score) if score else '',
        'status': status,
        'method': '',
        'datapoints': '0',
        'notes': notes,
    })
    _write_all(rows)
    return True


def log_ingestion(source, identifier, method, datapoints, status='ingested', notes=''):
    """Update a book's ingestion status after processing."""
    rows = _read_all()
    idx = _find_row(rows, source, identifier)
    if idx is None:
        return

    rows[idx]['status'] = status
    rows[idx]['method'] = method
    rows[idx]['datapoints'] = str(datapoints)
    if notes:
        existing = rows[idx].get('notes', '')
        rows[idx]['notes'] = f"{existing}; {notes}" if existing else notes
    _write_all(rows)


def is_ingested(source, identifier):
    """Check if a book has already been ingested."""
    rows = _read_all()
    idx = _find_row(rows, source, identifier)
    if idx is None:
        return False
    return rows[idx]['status'] == 'ingested'


def get_pending(source=None, person=None, min_score=None):
    """Get all pending (not yet ingested, not rejected) books.

    Args:
        min_score: If set, only return books with score >= this value.
                   Books without a score are excluded when min_score is set.
    """
    rows = _read_all()
    pending = [r for r in rows if r['status'] in ('pending', 'approved')]
    if source:
        pending = [r for r in pending if r['source'] == source]
    if person:
        pending = [r for r in pending if r['person'].lower() == person.lower()]
    if min_score is not None:
        filtered = []
        for r in pending:
            try:
                s = int(r.get('score', 0) or 0)
            except (ValueError, TypeError):
                s = 0
            if s >= min_score:
                filtered.append(r)
        pending = filtered
    return pending


def get_summary():
    """Print a summary of the book registry."""
    rows = _read_all()
    if not rows:
        print("Book registry is empty.")
        return

    by_status = {}
    by_source = {}
    by_person = {}
    by_relevance = {}
    total_dp = 0

    for r in rows:
        status = r.get('status', 'pending')
        source = r.get('source', '?')
        person = r.get('person', '?')
        rel = r.get('relevance', '') or 'unclassified'
        dp = int(r.get('datapoints', 0) or 0)

        by_status[status] = by_status.get(status, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1
        by_person[person] = by_person.get(person, 0) + 1
        by_relevance[rel] = by_relevance.get(rel, 0) + 1
        total_dp += dp

    print(f"\n{'='*50}")
    print(f"Book Registry Summary ({len(rows)} books)")
    print(f"{'='*50}")
    print(f"\nBy status:")
    for s, c in sorted(by_status.items()):
        print(f"  {s}: {c}")
    print(f"\nBy relevance:")
    for s, c in sorted(by_relevance.items()):
        print(f"  {s}: {c}")
    print(f"\nBy source:")
    for s, c in sorted(by_source.items()):
        print(f"  {s}: {c}")
    print(f"\nBy person (top 10):")
    for p, c in sorted(by_person.items(), key=lambda x: -x[1])[:10]:
        print(f"  {p}: {c}")
    print(f"\nTotal datapoints extracted: {total_dp}")


def main_action(action='summary', source=None, person=None):
    """Called from free_ingest.py registry subcommand."""
    if action == 'summary':
        get_summary()
    elif action == 'list':
        rows = _read_all()
        if not rows:
            print("Registry is empty.")
            return
        if source:
            rows = [r for r in rows if r['source'] == source]
        if person:
            rows = [r for r in rows if r['person'].lower() == person.lower()]
        print(f"{'Status':<10} {'Score':>5} {'Relevance':<14} {'Source':<12} {'Person':<20} {'Title':<36} {'DP':>4} {'Method':<10}")
        print('-' * 115)
        for r in rows:
            title = r['title'][:34] + '..' if len(r['title']) > 36 else r['title']
            person_col = r['person'][:18] + '..' if len(r['person']) > 20 else r['person']
            rel = r.get('relevance', '') or '-'
            score = r.get('score', '') or '-'
            print(f"{r['status']:<10} {score:>5} {rel:<14} {r['source']:<12} {person_col:<20} {title:<36} {r.get('datapoints', '0'):>4} {r.get('method', ''):<10}")
    elif action == 'pending':
        pending = get_pending(source=source, person=person)
        if not pending:
            print("No pending books.")
            return
        for r in pending:
            rel = r.get('relevance', '') or '?'
            print(f"  [{r['source']}] ({rel}) {r['title']} — {r['person']} ({r['url']})")
