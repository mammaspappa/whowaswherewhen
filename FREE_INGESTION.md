# Free Data Ingestion

Zero-cost strategies to populate the database with historical figure locations. No paid APIs required.

## Quick Start

```bash
# Ingest one person from Wikidata (no API key needed)
.venv/bin/python -m ingest.free_ingest wikidata --person "Nikola Tesla"

# Bulk-load 50 famous historical figures
.venv/bin/python -m ingest.free_ingest bulk --preset famous-historical --limit 50

# Maximum coverage: Wikidata + NER + categories combined
.venv/bin/python -m ingest.free_ingest combined --person "Charles Darwin"
```

## Setup: API Keys

Store API keys in a `.env` file in the project root. It is auto-loaded by the CLI.

```bash
# .env
GOOGLE_GEMINI_API_KEY='your-key-here'
GOOGLE_BOOKS_API_KEY='your-key-here'
GROQ_API_KEY='your-key-here'
```

See [Getting a Google Gemini API key](#getting-a-google-gemini-api-key) and
[Getting a Google Books API key](#getting-a-google-books-api-key) below.

## Book Ingestion: Discover + Extract Workflow

The recommended way to ingest from books is a two-phase workflow. This lets you review and edit the book list before spending API quota on extraction.

### Phase 1: Discover

Search all book sources (Gutenberg, Internet Archive, Google Books), classify each book with the LLM, and save results to the book registry (`data/book_registry.csv`).

```bash
# Discover books for a person (with LLM classification)
.venv/bin/python -m ingest.free_ingest discover --person "Napoleon" --llm gemini-3.1

# Discover from specific sources only
.venv/bin/python -m ingest.free_ingest discover --person "Goethe" --sources gutenberg,archive --llm gemini-3.1

# Discover without LLM classification (all books stay pending)
.venv/bin/python -m ingest.free_ingest discover --person "Napoleon" --max-books 20
```

The LLM classifies each book using a historiographic source taxonomy (see [Source Classification](#source-classification) below). Fiction, authored works, and irrelevant texts are auto-rejected. Biographies, letters, memoirs, and reference works are kept as pending.

### Review the Registry

After discovery, review the book list. You can edit the CSV directly in a spreadsheet to change `rejected` to `pending` (or vice versa) before extraction.

```bash
# View summary
.venv/bin/python -m ingest.free_ingest registry summary

# List all books for a person
.venv/bin/python -m ingest.free_ingest registry list --person "Napoleon"

# List only pending books
.venv/bin/python -m ingest.free_ingest registry pending
```

### Phase 2: Extract

Process pending books from the registry. Downloads full text, extracts locations with the LLM, geocodes, and imports to the database.

```bash
# Extract from all pending books for a person
.venv/bin/python -m ingest.free_ingest extract --person "Napoleon" --llm gemini-3.1

# Extract from specific source only
.venv/bin/python -m ingest.free_ingest extract --person "Napoleon" --source gutenberg --llm gemini-3.1

# Limit number of books to process
.venv/bin/python -m ingest.free_ingest extract --person "Napoleon" --limit 3 --llm gemini-3.1

# Pattern matching (no API key needed, lower yield)
.venv/bin/python -m ingest.free_ingest extract --person "Napoleon"

# Dry run
.venv/bin/python -m ingest.free_ingest extract --person "Napoleon" --llm gemini-3.1 --dry-run
```

## Source Classification

When using `--llm` with the `discover` command, each book is classified into one of 16 categories based on historiographic source taxonomy. This determines whether it's useful for extracting real-life location data and what confidence level to assign.

### Useful categories (kept for extraction)

**Primary sources** (created at the time of events):

| Category | Description | Default confidence |
|---|---|---|
| `official_record` | Census, parish registers, court records, ship manifests, military records | certain |
| `diary_journal` | Day-by-day personal accounts, travel journals, ship logs | certain |
| `letter_correspondence` | Letters, dispatches, telegrams by or to the person | certain |
| `inscription_artifact` | Inscriptions, coins, tombstones, building dedications | probable |
| `newspaper_periodical` | Contemporary news reporting, magazine articles | possible |

**Secondary sources** (analysis by later scholars):

| Category | Description | Default confidence |
|---|---|---|
| `scholarly_biography` | Academic biography with footnotes and primary source research | probable |
| `academic_article` | Peer-reviewed journal article or scholarly essay | probable |
| `travel_geography` | Travel accounts, itineraries, geographic descriptions | probable |
| `autobiography_memoir` | First-person life account written after the fact | probable |
| `popular_biography` | Trade press biography for general readers | possible |

**Tertiary sources:**

| Category | Description | Default confidence |
|---|---|---|
| `reference_work` | Encyclopedias, biographical dictionaries, chronologies, study guides | possible |

### Rejected categories (auto-filtered)

| Category | Description | Why rejected |
|---|---|---|
| `historical_fiction` | Novels, plays, poems with historical characters | Locations are invented |
| `hagiography_legend` | Saints' lives, mythologized accounts | Mixes fact with legend |
| `authored_fiction` | Fiction/poetry written BY the person | Not about their real life |
| `authored_nonfiction` | Non-biographical works by the person (treatises, science, law) | No location data |
| `irrelevant` | Not about this person, or about someone else with the same name | Wrong subject |

## Individual Strategies

The discover/extract workflow is recommended, but you can also run individual strategies directly.

### Wikidata SPARQL (recommended starting point)

Pulls structured data directly from Wikidata. Coordinates included, no geocoding needed.

**Requirements:** None

```bash
.venv/bin/python -m ingest.free_ingest wikidata --person "Leonardo da Vinci"
.venv/bin/python -m ingest.free_ingest wikidata --wikidata-id Q762
.venv/bin/python -m ingest.free_ingest wikidata --batch-file names.txt
```

Typical yield: 3-8 locations per person.

### Bulk Discovery

Discovers hundreds of figures from Wikidata by preset or custom filters.

```bash
.venv/bin/python -m ingest.free_ingest bulk --preset famous-historical --limit 100
.venv/bin/python -m ingest.free_ingest bulk --preset explorers --limit 50
.venv/bin/python -m ingest.free_ingest bulk --occupation painter --born-in France --limit 30
.venv/bin/python -m ingest.free_ingest bulk --preset famous-historical --limit 100 --augment
```

Available presets: `famous-historical`, `explorers`, `scientists`, `artists`, `composers`, `writers`, `philosophers`, `military-leaders`, `monarchs`.

### Google Books API

Extracts locations from book descriptions and text snippets.

```bash
.venv/bin/python -m ingest.free_ingest books --person "Napoleon" --max-books 20
```

### Project Gutenberg

Downloads full text and extracts locations.

```bash
.venv/bin/python -m ingest.free_ingest gutenberg --person "Napoleon" --llm gemini-3.1
.venv/bin/python -m ingest.free_ingest gutenberg --person "Abraham Lincoln"  # pattern matching
```

### Internet Archive

Downloads full OCR text from archive.org and extracts locations.

```bash
.venv/bin/python -m ingest.free_ingest archive --person "Abraham Lincoln" --llm gemini-3.1
```

### Free LLM Extraction (from Wikipedia)

Extracts locations from Wikipedia biography text using free LLM providers.

```bash
.venv/bin/python -m ingest.free_ingest llm --person "Nikola Tesla" --provider gemini-3.1
```

Typical yield: 8-20 locations per person.

### Wikipedia Category Mining

Extracts locations from Wikipedia category names.

```bash
.venv/bin/python -m ingest.free_ingest category --person "Leonardo da Vinci"
.venv/bin/python -m ingest.free_ingest category --discover-from-place "Florence"
```

### spaCy NER

Local NLP extraction from Wikipedia text.

```bash
.venv/bin/pip install spacy
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python -m ingest.free_ingest ner --person "Charles Darwin"
```

### Combined Mode

Runs Wikidata + NER + Category Mining together with deduplication.

```bash
.venv/bin/python -m ingest.free_ingest combined --person "Charles Darwin"
```

## LLM Providers and Rate Limits

### Gemini Models

All Gemini models use the same API key (`GOOGLE_API_KEY` or `GOOGLE_GEMINI_API_KEY`).

| Flag | Model | RPM | RPD | Notes |
|---|---|---|---|---|
| `gemini` | Gemini 2.5 Flash Lite | 10 | 20 | Default. Quick tests only. |
| `gemini-flash` | Gemini 2.5 Flash | 5 | 20 | Higher quality, same daily limit. |
| `gemini-3` | Gemini 3 Flash | 5 | 20 | Latest generation. |
| `gemini-3.1` | Gemini 3.1 Flash Lite | 15 | **500** | Best for bulk work. |

**RPM** = requests per minute. **RPD** = requests per day.

**Recommendation:** Use `gemini-3.1` for any serious work. 25x more daily requests than other Gemini models.

### Other Providers

| Flag | Env Variable | RPM | RPD |
|---|---|---|---|
| `groq` | `GROQ_API_KEY` | 30 | 14,400 |
| `mistral` | `MISTRAL_API_KEY` | 60 | unlimited |
| `openrouter` | `OPENROUTER_API_KEY` | 20 | 200 |

### Daily Usage Tracking

Daily API usage is tracked in `data/llm_daily_usage.json` to avoid exceeding RPD limits. The script stops and reports remaining quota when limits are reached. Counter resets automatically each day.

## Book Registry

All book-based strategies log discoveries to `data/book_registry.csv`. This CSV is the central work queue for the discover/extract workflow.

```bash
.venv/bin/python -m ingest.free_ingest registry summary
.venv/bin/python -m ingest.free_ingest registry list --person "Napoleon"
.venv/bin/python -m ingest.free_ingest registry pending --source gutenberg
```

The CSV can be opened in any spreadsheet. Columns:

| Column | Description |
|---|---|
| `source` | Strategy (google_books, gutenberg, archive) |
| `person` | Who the book is about |
| `title` | Book title |
| `author` | Author(s) |
| `url` | Link to the book |
| `relevance` | Source classification (scholarly_biography, letter_correspondence, historical_fiction, etc.) |
| `status` | pending / approved / ingested / rejected / failed |
| `method` | Extraction method used (pattern, gemini-3.1, groq, etc.) |
| `datapoints` | Number of locations extracted |
| `notes` | Auto-rejection reason or other info |

### Editing the Registry

You can manually edit the CSV to:
- Change `rejected` to `pending` to include a book the LLM wrongly rejected
- Change `pending` to `rejected` to skip a book you don't want
- Add `approved` status to prioritize certain books
- Add notes for your own tracking

## Whereabout Metadata

Each whereabout record in the database includes provenance metadata:

| Field | Description |
|---|---|
| `source_text` | The exact quote from the source text supporting this location |
| `extraction_method` | How it was extracted (wikidata, pattern, gemini-3.1, ner, etc.) |
| `extraction_model` | Specific model (gemini-3.1-flash-lite-preview, llama-3.3-70b, etc.) |
| `extracted_at` | When the extraction happened |
| `created_by` | Who created it (system, user name) |
| `raw_date_text` | Original date string before parsing |
| `raw_place_text` | Original place string before geocoding |
| `geocode_source` | How coordinates were obtained (nominatim, wikidata, manual) |
| `verified` | Whether a human has verified this record |
| `notes` | Free-form notes |

All metadata is visible on the whereabout detail page in the web interface.

## Recommended Workflow

1. **Seed the database** with bulk discovery:
   ```bash
   .venv/bin/python -m ingest.free_ingest bulk --preset famous-historical --limit 200
   ```

2. **Enrich specific figures** with combined mode:
   ```bash
   .venv/bin/python -m ingest.free_ingest combined --person "Napoleon"
   ```

3. **Discover books** with LLM classification:
   ```bash
   .venv/bin/python -m ingest.free_ingest discover --person "Napoleon" --llm gemini-3.1
   ```

4. **Review** the book registry, edit if needed:
   ```bash
   .venv/bin/python -m ingest.free_ingest registry list --person "Napoleon"
   ```

5. **Extract** from approved books:
   ```bash
   .venv/bin/python -m ingest.free_ingest extract --person "Napoleon" --llm gemini-3.1
   ```

6. **Check results:**
   ```bash
   .venv/bin/python -m ingest.free_ingest registry summary
   ```

## Batch Files

Any strategy that accepts `--person` also accepts `--batch-file` with one name per line:

```bash
.venv/bin/python -m ingest.free_ingest wikidata --batch-file renaissance_italians.txt
```

## Options Available on All Strategies

| Flag | Description |
|------|-------------|
| `--json-out FILE` | Write JSON to a file instead of inserting into the database |
| `--dry-run` | Preview what would be inserted without changing the database |
| `--batch-file FILE` | Process multiple people from a text file |

## Getting a Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **Create API Key**
4. Copy the key and add it to your `.env` file:
   ```
   GOOGLE_GEMINI_API_KEY='your-key-here'
   ```

No billing or credit card required. Free tier limits apply (see rate limits above).

## Getting a Google Books API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project (or select an existing one)
3. Go to **APIs & Services > Library**, search for "Books API", and enable it
4. Go to **APIs & Services > Credentials**, click **Create Credentials > API Key**
5. Copy the key and add it to your `.env` file:
   ```
   GOOGLE_BOOKS_API_KEY='your-key-here'
   ```

Free tier: 1,000 requests/day. No billing required.
