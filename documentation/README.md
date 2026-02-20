# Psychometric Scoring Skeleton

A fully instrument-agnostic Python package for psychometric assessment scoring, reporting, and RAG-based interpretation. Configure a new instrument entirely through JSON data files — no Python code changes required.

## What It Does

**Pipeline:** Load CSV responses → Validate → Calculate raw/T-scores → Generate reports (DOCX + interactive HTML) → Generate RAG-based clinical narratives

**Supports:**
- **Boolean instruments** (True/False) — e.g., MMPI-3, MMPI-2-RF, MMPI-A-RF
- **Likert-scale instruments** (weighted scoring) — e.g., PAI, NEO-PI-3, BDI-II
- **Interactive HTML reports** with ECharts profile graphs
- **Formatted DOCX reports** with embedded PNG charts (via Playwright)
- **RAG-based interpretive narratives** using ChromaDB + Anthropic Claude API

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

For DOCX chart embedding (optional):
```bash
playwright install chromium
```

### 2. Process a score file

```bash
# HTML report (interactive charts)
python main.py --score-file data/scores/test_001.csv --format html

# DOCX report
python main.py --score-file data/scores/test_001.csv --format docx

# Both formats
python main.py --score-file data/scores/test_001.csv --format both
```

### 3. Use a different instrument

```bash
python main.py --instrument-config my_instrument.json --score-file test.csv --format html
```

### 4. Generate interpretive reports (requires Anthropic API key)

```bash
# Set API key
export ANTHROPIC_API_KEY=your_key_here

# Ingest interpretation worksheets
python main.py --ingest-worksheets ./worksheets/

# Generate interpretive report with client demographics
python main.py --score-file test.csv --interpretive --client-info client.json --format html
```

## Project Structure

```
skeleton_assess/
├── psychometric_scoring/        # Core scoring package
│   ├── __init__.py
│   ├── instrument_config.py     # Config loader + helpers
│   ├── client_info.py           # Client demographics dataclass
│   ├── score_loader.py          # CSV loading (boolean + Likert)
│   ├── score_validator.py       # Response validation
│   ├── score_calculator.py      # Raw scores, T-scores, interpretive ranges
│   ├── chart_renderer.py        # ECharts config generation + PNG export
│   ├── report_generator.py      # DOCX report generation
│   ├── html_report_generator.py # Interactive HTML report generation
│   └── rag_interpreter.py       # RAG-based narrative generation
├── rag_core/                    # RAG engine (document loading, vector store, query)
│   ├── __init__.py
│   ├── config.py                # RAG configuration
│   ├── document_loader.py       # Document loading + chunking
│   ├── vector_store.py          # ChromaDB vector store wrapper
│   ├── query_engine.py          # RAG query orchestration
│   ├── output_formatter.py      # Response formatting
│   └── output_utils.py          # Output helpers
├── templates/
│   ├── formatting.json          # Chart colors, domain definitions, display settings
│   ├── mapping.json             # Item-to-scale keying directions
│   ├── scales.json              # Scale names, abbreviations, descriptions
│   ├── tscore_tables.json       # Raw-to-T-score normative conversion tables
│   └── actions/                 # RAG prompt templates
├── example_data/                # Sample boolean + Likert instruments
├── documentation/               # Design docs and audit history
│   ├── skeleton_assessment.md   # Original codebase reusability audit
│   └── implementation_plan.md   # Architecture and build plan
├── main.py                      # CLI entry point
├── config.yaml                  # RAG system configuration
├── instrument_config.json       # Instrument definition template (fill in for your instrument)
├── smoke_test.py                # End-to-end verification
└── requirements.txt
```

## Architecture

The project contains two Python packages:

- **`psychometric_scoring/`** — the instrument-agnostic scoring, validation, and reporting engine
- **`rag_core/`** — the RAG engine handling document loading, vector storage (ChromaDB), and query orchestration with the Anthropic Claude API

Both are included locally with no external package installation beyond `requirements.txt`.

## How It Works

Everything instrument-specific lives in **one JSON file**: `instrument_config.json`. This is the single source of truth for:

- Instrument name, item count, response type
- Item-to-scale mapping file paths
- Interpretive T-score cutoffs
- Scale categories and hierarchy
- Safety scales for flagging
- Chart formatting, colors, and domain definitions
- Validity subcategories
- Disclaimer text

The Python code reads this config and adapts automatically. See the [User Guide](userguide.md) for full details on creating configs for new instruments.

## Adding a New Instrument

No Python changes needed. Create these data files:

1. **`instrument_config.json`** — instrument definition (categories, cutoffs, formatting)
2. **`mapping.json`** — item-to-scale keying directions or scoring weights
3. **`tscore_tables.json`** — raw-to-T-score normative conversion tables
4. **`scales.json`** — scale names, abbreviations, descriptions
5. **Interpretation worksheets** (`.md`) — clinical guidance per category (for RAG reports)
6. **Prompt templates** — customized `interpretation.txt`, `integration.txt`, `treatment.txt`

See `example_data/` for working boolean and Likert sample instruments.

## Dependencies

| Package | Purpose |
|---------|---------|
| pandas | CSV loading and data handling |
| python-docx | DOCX report generation |
| pyyaml | Config file loading |
| python-dotenv | Environment variable management |
| tiktoken | Text chunking for RAG |
| anthropic | Claude API for narrative generation |
| chromadb | Vector store for RAG retrieval |
| playwright | PNG chart rendering for DOCX (optional) |

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

RAG Operations:
  --ingest                    Ingest documents from data directory
  --ingest-worksheets PATH    Ingest interpretation worksheets
  --clear                     Clear document collection
  --query TEXT                Query the document collection
  --interactive               Start interactive query mode
  --action {query,summarize,synthesize}
  --top-k N                   Number of results to retrieve (default: 10)
```

## Smoke Test

```bash
python smoke_test.py
```

Runs the full pipeline (load → validate → score → report) against the configured instrument to verify everything works end-to-end.
