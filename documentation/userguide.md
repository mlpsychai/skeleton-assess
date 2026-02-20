# User Guide: Psychometric Scoring Skeleton

This guide covers how to configure and use the skeleton for any psychometric instrument.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Instrument Configuration](#instrument-configuration)
3. [Creating a Mapping File](#creating-a-mapping-file)
4. [Creating T-Score Tables](#creating-t-score-tables)
5. [Creating a Scales File](#creating-a-scales-file)
6. [Preparing Response Data](#preparing-response-data)
7. [Running the Pipeline](#running-the-pipeline)
8. [Report Formats](#report-formats)
9. [Setting Up RAG Interpretation](#setting-up-rag-interpretation)
10. [Client Information](#client-information)
11. [Batch Processing](#batch-processing)
12. [Working Examples](#working-examples)
13. [Troubleshooting](#troubleshooting)

---

## Core Concepts

The skeleton follows a strict pipeline:

```
CSV responses → Load → Validate → Calculate → Report
                                              ↘ RAG Interpret (optional)
```

**Every instrument-specific value** is read from `instrument_config.json`. The Python code never contains hardcoded scale names, item counts, cutoffs, or category lists. To add a new instrument, you create data files — not code.

### Two Python Packages

The project includes two local packages (no external installation needed beyond `requirements.txt`):

- **`psychometric_scoring/`** — scoring, validation, chart rendering, and report generation
- **`rag_core/`** — document loading, ChromaDB vector storage, and RAG query orchestration

### Two Configuration Layers

1. **`instrument_config.json`** — defines the instrument (scales, items, cutoffs, formatting)
2. **`config.yaml`** — defines the RAG system (ChromaDB paths, collection names)

---

## Instrument Configuration

The `instrument_config.json` file is the single source of truth for your instrument. Here is a complete reference of every field.

### Top-Level Fields

```json
{
  "instrument_name": "MMPI-3",
  "instrument_full_name": "Minnesota Multiphasic Personality Inventory-3 (MMPI-3)",
  "instrument_reference": "Ben-Porath, Y. S., & Tellegen, A. (2020)",
  "instrument_description": "A 335-item self-report measure of personality and psychopathology...",
  "num_items": 335,
  "response_type": "boolean",
  "response_format": "True/False",
  "administration_format": "standard paper-and-pencil format",
  "norms": "combined-gender norms"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `instrument_name` | Yes | Short name used in report titles and code references |
| `instrument_full_name` | No | Full formal name for the "Test Administered" section |
| `instrument_reference` | No | Citation displayed in reports |
| `instrument_description` | No | Brief instrument description for reports |
| `num_items` | Yes | Total number of items on the instrument |
| `response_type` | Yes | `"boolean"` or `"likert"` |
| `response_format` | No | Human-readable format description (e.g., "True/False", "0-3 Likert scale") |
| `administration_format` | No | How the test is administered |
| `norms` | No | Normative reference group description |

### Response Options

For **boolean** instruments:

```json
"response_options": {
  "true_values": ["True", "1", "Yes", "T"],
  "false_values": ["False", "0", "No", "F"]
}
```

The loader recognizes any of these strings (case-insensitive) when parsing CSV responses.

For **Likert** instruments:

```json
"response_options": {
  "min_value": 0,
  "max_value": 3,
  "labels": ["Not at all", "A little", "Moderately", "Extremely"]
}
```

### File Paths

```json
"files": {
  "mapping": "templates/mapping.json",
  "scales": "templates/scales.json",
  "tscore_tables": "templates/tscore_tables.json",
  "formatting": "templates/formatting.json"
}
```

Paths are relative to the project root. These point to the data files that define your instrument's scoring logic and display formatting.

### Interpretive Cutoffs

```json
"interpretive_cutoffs": [
  {"label": "Within Normal Limits", "max_t": 59},
  {"label": "Slightly Elevated", "min_t": 60, "max_t": 64},
  {"label": "Moderately Elevated", "min_t": 65, "max_t": 79},
  {"label": "Clinically Significant", "min_t": 80}
]
```

Each cutoff defines a range. The calculator iterates this list to classify T-scores. You can define any number of ranges with any labels — the system is not limited to four.

### Safety Scales

```json
"safety_scales": ["SUI", "AGG"]
```

Scale abbreviations that trigger safety flagging in RAG-generated treatment recommendations. When these scales are elevated, the interpreter adds a prominent safety note. Set to `[]` if no safety scales apply.

### Categories

```json
"categories": [
  {
    "key": "validity",
    "title": "Protocol Validity",
    "scales": ["VRIN", "TRIN", "CRIN", "F", "Fp", "Fs", "FBS", "RBS", "L", "K"],
    "worksheet": "01_Protocol_Validity.md",
    "is_validity": true
  },
  {
    "key": "higher_order",
    "title": "Higher-Order Scales",
    "scales": ["EID", "THD", "BXD"],
    "worksheet": "02_Higher_Order_Scales.md"
  }
]
```

| Field | Required | Description |
|-------|----------|-------------|
| `key` | Yes | Internal identifier (used as narrative dict key) |
| `title` | Yes | Display title in reports |
| `scales` | Yes | Ordered list of scale abbreviations in this category |
| `worksheet` | No | Interpretation worksheet filename (for RAG) |
| `is_validity` | No | Set `true` for the validity category (affects report layout) |

Categories determine:
- Report section order (categories are rendered in array order)
- Scale table groupings
- RAG narrative sections
- Which scales appear in which chart groups

### Validity Subcategories

```json
"validity_subcategories": {
  "Content Non-Responsiveness": ["VRIN", "TRIN", "CRIN"],
  "Over-Reporting": ["F", "Fp", "Fs", "FBS", "RBS"],
  "Under-Reporting": ["L", "K"]
}
```

Groups validity scales into subcategories for separate chart rendering. Each subcategory gets its own validity chart in the HTML report.

### Formatting

```json
"formatting": {
  "font": "Times New Roman",
  "base_font_size": 12,
  "text_color": "#000",
  "html_max_width": "1280px",
  "docx_font": "Calibri",
  "docx_table_style": "Light Grid Accent 1",
  "chart_colors": {
    "Higher-Order Scales": "#2C3E50",
    "Restructured Clinical Scales": "#1A5276"
  },
  "validity_chart_colors": {
    "Content Non-Responsiveness": "#555555",
    "Over-Reporting": "#922B21",
    "Under-Reporting": "#1A5276"
  },
  "domain_definitions": {
    "Emotional Dysfunction": {
      "Higher_Order": ["EID"],
      "RC": ["RCd", "RC2", "RC7"],
      "Specific_Problems": ["SUI", "HLP", "SFD"],
      "PSY5": ["NEGE"],
      "color": "#1A5276"
    }
  },
  "chart": {
    "y_min": 25,
    "y_max": 95,
    "y_interval": 10,
    "reference_lines": [
      {"value": 60, "label": "75th %ile"},
      {"value": 70, "label": "90th %ile"}
    ],
    "line_styles": {
      "Higher_Order": {"width": 3.5, "symbol": "circle", "size": 10, "style": "solid"},
      "RC": {"width": 2.5, "symbol": "rect", "size": 8, "style": "solid"}
    },
    "height": "700px"
  }
}
```

- **`html_max_width`**: Maximum width of the HTML report display (default: `"1280px"`)
- **`docx_font`**: Font family for DOCX reports (default: `"Calibri"`)
- **`docx_table_style`**: Word table style name for DOCX reports
- **`chart_colors`**: Maps category titles to hex colors for the combined profile chart
- **`validity_chart_colors`**: Maps validity subcategory names to hex colors
- **`domain_definitions`**: Groups scales by clinical domain for domain-specific charts. Set to `{}` if your instrument doesn't use domain groupings
- **`chart`**: ECharts axis configuration, reference lines, and series styling
- **`line_styles`**: Maps scale hierarchy levels to visual styles (line width, marker shape/size)

### Disclaimer

```json
"disclaimer_text": "IMPORTANT DISCLAIMER:\nThis report was generated using..."
```

Displayed at the bottom of all generated reports. Supports `\n` for line breaks.

---

## Creating a Mapping File

The mapping file defines how items score on each scale.

### Boolean Instruments

Items use `keyed` to indicate which response direction scores a point:

```json
{
  "scales": {
    "ANX": {
      "scale_name": "Anxiety",
      "abbreviation": "ANX",
      "item_count": 5,
      "items": [
        {"item": 1, "keyed": "True"},
        {"item": 3, "keyed": "True"},
        {"item": 5, "keyed": "False"},
        {"item": 7, "keyed": "True"},
        {"item": 9, "keyed": "False"}
      ]
    }
  }
}
```

When `"keyed": "True"`, a True response on that item adds 1 to the raw score. When `"keyed": "False"`, a False response adds 1.

### Likert Instruments

Items use `scoring_weights` to define the point value for each response option:

```json
{
  "scales": {
    "ANX": {
      "scale_name": "Anxiety",
      "abbreviation": "ANX",
      "item_count": 5,
      "items": [
        {"item": 1, "scoring_weights": {"0": 0, "1": 1, "2": 2, "3": 3}},
        {"item": 3, "scoring_weights": {"0": 3, "1": 2, "2": 1, "3": 0}},
        {"item": 5, "scoring_weights": {"0": 0, "1": 1, "2": 2, "3": 3}}
      ]
    }
  }
}
```

- **Straight-scored items**: `{"0": 0, "1": 1, "2": 2, "3": 3}`
- **Reverse-scored items**: `{"0": 3, "1": 2, "2": 1, "3": 0}`

The calculator detects the format per-item, so you can even mix `keyed` and `scoring_weights` items within the same instrument if needed.

### Pair-Based Validity Scales

For validity scales that compare item pairs (e.g., VRIN, TRIN, CRIN):

```json
{
  "VRIN": {
    "scale_name": "Variable Response Inconsistency",
    "abbreviation": "VRIN",
    "scale_type": "item_pairs",
    "discordant_pairs": [
      [10, 46], [17, 63], [28, 82]
    ],
    "base_score": 4
  }
}
```

---

## Creating T-Score Tables

Normative conversion tables map raw scores to T-scores:

```json
{
  "scales": {
    "ANX": {
      "table": "Combined Gender Norms",
      "score_type": "linear",
      "raw_to_t": {
        "0": 33,
        "1": 36,
        "2": 40,
        "3": 44,
        "4": 48,
        "5": 52
      }
    }
  }
}
```

- Keys in `raw_to_t` are raw score values (as strings)
- Values are the corresponding T-scores
- `score_type`: `"linear"` for standard lookup, `"uniform"` for uniform T-score distributions
- If a scale has no T-score table, raw scores are reported without T-score conversion

---

## Creating a Scales File

The scales file provides descriptive metadata:

```json
{
  "categories": [
    {
      "category": "Validity Scales",
      "scales": [
        {
          "scale_name": "Variable Response Inconsistency",
          "abbreviation": "VRIN",
          "description": "Measures random or inconsistent responding..."
        }
      ]
    }
  ]
}
```

This file is used for display purposes and reference. The scoring logic relies on the mapping file, not this file.

---

## Preparing Response Data

Response data is provided as CSV files with this structure:

```csv
test_id,test_date,examinee_id,item_1,item_2,...,item_N
TEST001,2026-01-15,EX001,True,False,True,...,False
```

**Header row** must contain:
- `test_id` — unique identifier for this administration
- `test_date` — date of administration
- `examinee_id` — participant identifier
- `item_1` through `item_N` — one column per item

**Response values:**
- Boolean: any value from the configured `true_values`/`false_values` lists
- Likert: integer values within the configured `min_value`/`max_value` range
- Missing items: empty cell or blank string

---

## Running the Pipeline

### Single File Processing

```bash
# Basic score report (DOCX)
python main.py --score-file path/to/responses.csv

# HTML report with interactive charts
python main.py --score-file path/to/responses.csv --format html

# Both formats
python main.py --score-file path/to/responses.csv --format both

# Custom output directory
python main.py --score-file path/to/responses.csv --output-dir ./my_reports
```

### Using a Different Instrument

```bash
python main.py --instrument-config path/to/my_instrument.json --score-file test.csv
```

---

## Report Formats

### HTML Reports

Interactive standalone HTML files with:
- APA 7th Edition formatted text
- ECharts interactive profile graphs (hover, zoom, pan)
- Validity scale charts grouped by subcategory
- Domain-specific charts
- Combined profile graph with all scales
- Print-to-PDF button
- Responsive layout for different screen sizes

### DOCX Reports

Microsoft Word documents with:
- APA-formatted tables
- Embedded PNG chart images (requires Playwright + Chromium)
- Validity assessment with color-coded status
- Scale tables with highlighted elevations
- Summary section with elevated scale listing

If Playwright is not installed, DOCX reports generate without charts and include a note suggesting the HTML format for visualizations.

---

## Setting Up RAG Interpretation

RAG (Retrieval-Augmented Generation) interpretation generates clinical narrative text using your interpretation worksheets as source material.

### Prerequisites

- Anthropic API key set as `ANTHROPIC_API_KEY` environment variable
- Interpretation worksheet `.md` files for your instrument
- ChromaDB for vector storage

### Step 1: Create Interpretation Worksheets

Write Markdown files with clinical interpretation guidance for each scale category. Name them to match the `worksheet` field in your config:

```
worksheets/
├── 01_Protocol_Validity.md
├── 02_Higher_Order_Scales.md
├── 03_RC_Scales.md
└── ...
```

Each worksheet should contain scale-by-scale interpretation guidance including:
- What the scale measures
- What elevations mean clinically
- Relevant behavioral correlates
- Common code type patterns

### Step 2: Ingest Worksheets

```bash
python main.py --ingest-worksheets ./worksheets/
```

This chunks the worksheets, embeds them, and stores them in ChromaDB.

### Step 3: Generate Interpretive Reports

```bash
python main.py --score-file test.csv --interpretive --format html
```

With client demographics:

```bash
python main.py --score-file test.csv --interpretive --client-info client.json --format html
```

### Caching Narratives

Narrative generation uses API calls. To avoid repeated calls during development:

```bash
# First run generates and you can save the narratives
# Subsequent runs can use cached narratives:
python main.py --score-file test.csv --interpretive --cached-narratives narratives.json --format html
```

### Customizing Prompt Templates

Edit the templates in `templates/actions/`:

- **`interpretation.txt`** — per-category clinical narrative generation
- **`integration.txt`** — cross-scale profile integration
- **`treatment.txt`** — treatment recommendations
- **`query.txt`** — general RAG queries
- **`summarize.txt`** — document summarization
- **`synthesize.txt`** — cross-document synthesis

---

## Client Information

For interpretive reports, provide client demographics as JSON:

```json
{
  "client_name": "Jane Doe",
  "dob": "1990-05-15",
  "age": 35,
  "sex": "Female",
  "education": "Bachelor's degree",
  "marital_status": "Married",
  "referral_source": "Dr. Smith",
  "referral_question": "Evaluate for depression and anxiety symptoms",
  "background": "Client presents with a 6-month history of...",
  "examiner_name": "Dr. Johnson",
  "examiner_credentials": "Ph.D., Licensed Psychologist",
  "supervisor_name": "Dr. Williams",
  "supervisor_credentials": "Ph.D., ABPP",
  "setting": "Outpatient mental health clinic"
}
```

All fields are optional. When provided, they appear in the report header, inform RAG narratives, and populate the signature block.

Alternatively, run with `--interpretive` without `--client-info` and the system will prompt interactively for demographics.

---

## Batch Processing

Process all CSV files in a directory:

```bash
python main.py --score-dir path/to/csv_directory/ --format both --output-dir ./reports
```

This iterates all `.csv` files, generates reports for each, and provides a summary of successes and failures.

---

## Working Examples

The `example_data/` directory contains complete working examples for both response types.

### Boolean Example

```bash
python main.py \
  --instrument-config example_data/sample_boolean_config.json \
  --score-file example_data/sample_responses_boolean.csv \
  --format html
```

Files:
- `sample_boolean_config.json` — 10-item instrument with 5 scales
- `sample_boolean_mapping.json` — keyed item-to-scale mapping
- `sample_responses_boolean.csv` — sample response data

### Likert Example

```bash
python main.py \
  --instrument-config example_data/sample_likert_config.json \
  --score-file example_data/sample_responses_likert.csv \
  --format html
```

Files:
- `sample_likert_config.json` — 10-item instrument with 5 scales (0-3 range)
- `sample_likert_mapping.json` — scoring weights with straight and reverse items
- `sample_responses_likert.csv` — sample response data

### MMPI-3 (Default)

```bash
python main.py --score-file data/scores/test_001.csv --format both
```

Uses the default `instrument_config.json` which is pre-configured for MMPI-3.

---

## Troubleshooting

### Scale abbreviation mismatches

Scale abbreviations must be **identical** (case-sensitive) across all four files that reference them:
- `instrument_config.json` (categories, validity_subcategories, safety_scales, domain_definitions)
- Your mapping file (scale keys)
- Your T-score tables file (scale keys)
- Your scales file (abbreviation fields)

A mismatch like `AXR` vs `ARX` will cause silent failures — the scale will score correctly in one file but fail to look up in another. When adding a new instrument, pick one canonical abbreviation per scale and use it everywhere.

### "No scales available in this category"

The scale abbreviations in your `categories` config don't match the keys in your mapping file. Ensure the abbreviations match exactly (case-sensitive).

### T-scores showing "N/A"

The scale doesn't have an entry in the T-score tables file, or the raw score falls outside the range of the normative table. Check that your `tscore_tables.json` has an entry for the scale and covers the expected raw score range.

### DOCX reports missing charts

Playwright and Chromium are not installed. Install with:
```bash
pip install playwright
playwright install chromium
```

The DOCX report will still generate without charts and include a note about it.

### "No documents in collection" error

You need to ingest documents before querying. Run:
```bash
python main.py --ingest
```

For interpretive reports, also run:
```bash
python main.py --ingest-worksheets ./worksheets/
```

### Validation fails with "Protocol is invalid"

The response data has too many missing items (exceeds the `max_missing_threshold` in your config). Check your CSV for blank cells. The default threshold is 10%.

### Score file not loading

Verify your CSV has the correct header format:
```
test_id,test_date,examinee_id,item_1,item_2,...,item_N
```

Item columns must be numbered sequentially starting from `item_1` up to `item_N` where N matches `num_items` in your config.

### RAG narratives are generic or off-topic

- Ensure your interpretation worksheets contain detailed, scale-specific clinical content
- Verify worksheets are properly ingested (`--ingest-worksheets`)
- Check that worksheet filenames match the `worksheet` field in your config categories
- Try increasing `--top-k` for broader retrieval context

### Import errors for `rag_core`

The `rag_core` package is included locally in the project directory. Make sure you're running from the project root (`skeleton_assess/`) so Python can find it. If you see `ModuleNotFoundError: No module named 'rag_core'`, verify the `rag_core/` directory exists with its `__init__.py` file.
