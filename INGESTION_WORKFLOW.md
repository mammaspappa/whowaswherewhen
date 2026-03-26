# Ingestion Workflow: Working Notes

How to add data to the database reliably. These notes are for both human operators and Claude Code sessions.

## Phase 1: Seed with Wikidata (fast, reliable, no API key)

```bash
.venv/bin/python -m ingest.free_ingest bulk --preset famous-historical --limit 50
```

This is the safest starting point. Wikidata gives structured, verified data with coordinates. Typical yield: 3-8 locations per person.

## Phase 2: Enrich with Combined Mode (NER + categories)

```bash
.venv/bin/python -m ingest.free_ingest combined --person "Napoleon"
```

This runs Wikidata + spaCy NER + category mining. NER extracts 10-80 locations per person from Wikipedia text, but produces some noise. After running combined mode, always check for:

### Quality Checks After NER Ingestion

1. **Posthumous entries** — NER extracts places from sentences about memorials, films, statues, posthumous honors. The import filter catches dates after death, but the NER doesn't know the person's death date when extracting.

   ```bash
   # Find and delete entries after death
   .venv/bin/python3 -c "
   import sqlite3
   db = sqlite3.connect('data/wwww.db')
   db.execute('PRAGMA foreign_keys = ON')
   cur = db.execute('''
       DELETE FROM whereabouts WHERE id IN (
           SELECT w.id FROM whereabouts w JOIN persons p ON w.person_id = p.id
           WHERE p.death_date_start IS NOT NULL
           AND p.death_date_start NOT LIKE \"-%%\"
           AND w.date_start NOT LIKE \"-%%\"
           AND w.date_start > SUBSTR(p.death_date_start, 1, 4) || '-12-31'
       )
   ''')
   print(f'Deleted {cur.rowcount} posthumous entries')
   db.commit()
   "
   ```

2. **Non-places** — NER sometimes extracts people's names, adjectives, or abstract nouns as places. Look for short or unusual place names:

   ```bash
   .venv/bin/python3 -c "
   import sqlite3
   db = sqlite3.connect('data/wwww.db')
   rows = db.execute('''
       SELECT w.id, p.name, w.place_name FROM whereabouts w
       JOIN persons p ON w.person_id = p.id
       WHERE LENGTH(w.place_name) <= 3
       OR w.place_name NOT LIKE '%% %%' AND LENGTH(w.place_name) < 5
   ''').fetchall()
   for wid, pname, place in rows:
       print(f'  #{wid} [{pname}] \"{place}\"')
   "
   ```

3. **Parent/ancestor events** — NER can't distinguish "Lincoln was born in Kentucky" from "Lincoln's father moved to Kentucky in 1806". These are hard to catch automatically.

4. **Duplicate persons** — Check for near-duplicates like "Cleopatra" vs "Cleopatra VII":

   ```bash
   .venv/bin/python -m ingest.free_ingest registry summary
   ```

## Phase 3: Book Discovery + Extraction (with LLM)

This is the richest source but costs API quota.

```bash
# Discover books (1 API call for classification)
.venv/bin/python -m ingest.free_ingest discover --person "Napoleon" --llm gemini-3.1

# Review the registry
.venv/bin/python -m ingest.free_ingest registry list --person "Napoleon"

# Extract from high-scoring books (20 API calls per book)
.venv/bin/python -m ingest.free_ingest extract --person "Napoleon" --llm gemini-3.1 --min-score 8
```

### API Quota Management

- `gemini-3.1` has 500 RPD (requests per day) — best for bulk work
- `groq` has 14,400 RPD — good for classification, extraction quality varies
- Check remaining quota: see `data/llm_daily_usage.json`
- One book extraction uses ~20 API calls (one per text chunk)
- Book discovery classification uses 1 API call per batch

### Groq vs Gemini for Classification

Groq sometimes uses non-standard category names (`primary_source`, `secondary_source` instead of `scholarly_biography`, `letter_correspondence`). These are accepted as aliases, but Gemini produces more precise classifications. Use Gemini for classification when possible, Groq for extraction.

## Batch Processing Pattern

Use batch files (not for loops) for multi-word names:

```bash
cat > /tmp/persons.txt << 'EOF'
Martin Luther King Jr.
Augustine of Hippo
William the Conqueror
EOF

# Wikidata seed (no API key)
.venv/bin/python -m ingest.free_ingest wikidata --batch-file /tmp/persons.txt

# LLM enrichment (with delays between calls)
.venv/bin/python -m ingest.free_ingest llm --batch-file /tmp/persons.txt --provider gemini-3.1
```

**IMPORTANT: Never use bash for loops** for multi-word names — `for person in "Augustine of Hippo"` will split into "Augustine", "of", "Hippo" and create junk records.

Then run the posthumous cleanup query above.

### Rate Limit Management

- **Don't run more than ~20 persons in a single batch.** Both Groq (30 RPM) and Gemini (15 RPM) will hit per-minute rate limits.
- **Add sleep between calls** if doing large batches: `sleep 5` between persons.
- **Gemini 3.1 has 500 RPD** but also has TPM (tokens per minute) limits. Large texts hit this quickly.
- **If you get all zeros**, the API is rate-limited. Wait 5-10 minutes before retrying.
- **Wikipedia LLM extraction** (single-shot, `llm` strategy) is the most efficient — 1 API call per person. Use this instead of NER for most persons.
- **NER is noisy** — skip it unless you specifically need the highest volume of extractions and plan to validate with `--validate`.

## Common Issues

| Problem | Cause | Fix |
|---|---|---|
| All zeros from LLM | Rate limited (RPM or TPM) | Wait 5-10 minutes, reduce batch size |
| Places after death date | NER extracts from legacy/memorial sections | Posthumous cleanup query |
| Person surname as place name | NER extracts "Newton", "Cortés" etc. | `_is_valid_place` now filters these |
| "War", "Sand", "O.S." as places | NER extracts nouns near dates | Added to IGNORE_PLACES |
| Multi-word names split | Bash for loop splits on spaces | Use --batch-file instead |
| Disambiguation page (e.g. "Victoria") | Short name resolves to wrong page | Use full name: "Queen Victoria" |
| Wrong person | Same-name confusion | Book classification catches this |
| Fiction characters' locations | Books by the person are ingested | Book classification catches this |
| Duplicate person records | Different name variants | Merge whereabouts, delete duplicate |

## Database Stats Check

```bash
.venv/bin/python3 -c "
import sqlite3
db = sqlite3.connect('data/wwww.db')
tp = db.execute('SELECT COUNT(*) FROM persons').fetchone()[0]
tw = db.execute('SELECT COUNT(*) FROM whereabouts').fetchone()[0]
ts = db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]
print(f'{tp} persons, {tw} whereabouts, {ts} sources')
"
```
