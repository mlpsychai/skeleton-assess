# Psychometric Scoring Skeleton

A fully instrument-agnostic Python package for psychometric assessment scoring, reporting, and RAG-based interpretation. Configure a new instrument entirely through JSON data files — no Python code changes required.

## What It Does

**Pipeline:** Load CSV responses → Validate → Calculate raw/T-scores → Generate reports (DOCX + interactive HTML) → Generate RAG-based clinical narratives

**Supports:**
- **Boolean instruments** (True/False) — e.g., MMPI-3, MMPI-2-RF, MMPI-A-RF
- **Likert-scale instruments** (weighted scoring) — e.g., PAI, NEO-PI-3, BDI-II
- **Interactive HTML reports** with ECharts profile graphs
- **Formatted DOCX reports** with embedded PNG charts (via Playwright)
- **RAG-based interpretive narratives** using Neon Postgres (pgvector) + Anthropic Claude API

## Quick Start

### 1. Clone and set up

```bash
git clone git@github.com:mlpsychai/skeleton-assess.git
cd skeleton-assess
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure environment

Create `.env` in project root:
```
DATABASE_URL=postgresql://...your_neon_connection_string...
ANTHROPIC_API_KEY=sk-ant-...your_key...
```

### 3. Process a score file

```bash
# HTML report (interactive charts)
python main.py --instrument-config configs/mmpi_335_config.json --score-file example_data/test_scores_001.csv --format html

# DOCX report
python main.py --instrument-config configs/mmpi_335_config.json --score-file example_data/test_scores_001.csv --format docx

# Both formats
python main.py --instrument-config configs/mmpi_335_config.json --score-file example_data/test_scores_001.csv --format both
```

### 4. Generate interpretive reports (requires Anthropic API key + Neon DB)

```bash
python main.py --instrument-config configs/mmpi_335_config.json \
  --score-file test.csv --interpretive --client-info client.json --format html
```

### 5. Web interface

```bash
python server.py
# Open http://localhost:5000
```

## Project Structure

```
skeleton-assess/
├── psychometric_scoring/           # Core scoring package
│   ├── instrument_config.py        # Config loader + helpers
│   ├── client_info.py              # Client demographics dataclass
│   ├── score_loader.py             # CSV loading (boolean + Likert)
│   ├── score_validator.py          # Response validation
│   ├── score_calculator.py         # Raw scores, T-scores, interpretive ranges
│   ├── chart_renderer.py           # ECharts config generation + PNG export
│   ├── report_generator.py         # DOCX report generation
│   ├── html_report_generator.py    # Interactive HTML report generation
│   └── rag_interpreter.py          # RAG-based narrative generation
├── db/                             # Database connection
│   └── connection.py               # Neon Postgres context manager
├── rag_core/                       # RAG engine
│   ├── config.py                   # Embedding model, Claude model settings
│   ├── vector_store.py             # Neon pgvector semantic search
│   └── query_engine.py             # RAG query orchestration
├── templates/
│   ├── mmpi3/                      # MMPI-3 instrument data
│   │   ├── mapping.json            # Item-to-scale keying directions
│   │   ├── scales.json             # Scale names, abbreviations, descriptions
│   │   ├── tscore_tables.json      # Raw-to-T-score normative tables
│   │   ├── formatting.json         # Chart colors, domain definitions
│   │   └── actions/                # MMPI-3 prompt templates
│   └── pai/                        # PAI instrument data (same structure)
├── configs/                        # Instrument config files
│   └── mmpi_335_config.json        # MMPI-3 configuration
├── example_data/                   # Sample data and client info templates
├── documentation/                  # Project documentation
├── main.py                         # CLI entry point
├── server.py                       # Flask web server
├── config.yaml                     # RAG query settings (top_k values)
├── instrument_config.json          # Blank instrument template
└── requirements.txt
```

## Architecture

- **`psychometric_scoring/`** — instrument-agnostic scoring, validation, and reporting
- **`rag_core/`** — vector search (Neon pgvector) and query orchestration (Anthropic Claude API)
- **`db/`** — Neon Postgres connection with per-instrument schema support

Each instrument gets its own Neon schema (`mmpi3`, `personality_assessment_inventory`) containing embedded textbook chunks for RAG context.

## Adding a New Instrument

No Python changes needed. Create these data files:

1. **`configs/<instrument>_config.json`** — instrument definition (categories, cutoffs, formatting, `db_schema`)
2. **`templates/<instrument>/mapping.json`** — item-to-scale keying directions or scoring weights
3. **`templates/<instrument>/tscore_tables.json`** — raw-to-T-score normative conversion tables
4. **`templates/<instrument>/scales.json`** — scale names, abbreviations, descriptions
5. **`templates/<instrument>/formatting.json`** — chart colors, domain definitions
6. **`templates/<instrument>/actions/`** — prompt templates (interpretation.txt, integration.txt, treatment.txt)
7. **Neon schema** — populate with embedded textbook chunks for RAG interpretation

## CLI Reference

```
python main.py [options]

Instrument:
  --instrument-config PATH    Instrument config JSON (default: instrument_config.json)

Score Processing:
  --score-file PATH           Process a single CSV file
  --score-dir PATH            Process all CSVs in a directory
  --output-dir PATH           Output directory (default: output/reports)
  --format {docx,html,both}   Report format (default: docx)

Interpretive Reports:
  --interpretive              Generate full interpretive report with RAG narratives
  --client-info PATH          Client demographics JSON file
  --cached-narratives PATH    Pre-generated narratives JSON (skip API calls)
```

## Dependencies

| Package | Purpose |
|---------|---------|
| pandas | CSV loading and data handling |
| python-docx | DOCX report generation |
| pyyaml | Config file loading |
| python-dotenv | Environment variable management |
| anthropic | Claude API for narrative generation |
| psycopg2-binary | Neon Postgres connection |
| sentence-transformers | Embedding generation for pgvector search |
| playwright | PNG chart rendering for DOCX (optional) |

## Git Workflow

### Repository

- **Remote:** `git@github.com:mlpsychai/skeleton-assess.git`
- **Branch:** `master`
- **Local:** `C:\Users\sm4663\skeleton-assess`

### SSH Key Setup

The SSH key is at `C:\Users\sm4663\.ssh\id_ed25519`. If git push fails with "Permission denied (publickey)", start the SSH agent and add the key:

```bash
eval "$(ssh-agent -s)"
ssh-add C:/Users/sm4663/.ssh/id_ed25519
```

Or use `GIT_SSH_COMMAND` for a one-off push:

```bash
GIT_SSH_COMMAND="ssh -i C:/Users/sm4663/.ssh/id_ed25519" git push origin master
```

### Pushing Changes

```bash
cd C:\Users\sm4663\skeleton-assess

# Check what's changed
git status
git diff

# Stage changes
git add <specific files>

# Commit
git commit -m "Description of changes"

# Push
GIT_SSH_COMMAND="ssh -i C:/Users/sm4663/.ssh/id_ed25519" git push origin master
```

### What NOT to commit

These are excluded via `.gitignore`:
- `venv/` — Python virtual environment
- `.env` — API keys and database credentials
- `output/*.png` — generated chart images (HTML reports are tracked)
- `PAI docs/` — copyrighted reference materials
- `archive/` — old diagnostic/validation scripts
- `*.png`, `*.pdf` — scan images and Pearson reference PDFs
