# Validation Log

## Overview

All scoring output has been validated against Pearson-generated MMPI-3 Score Reports. Two independent cases were used, covering all 52 scales (Validity, Higher-Order, Restructured Clinical, Somatic/Cognitive, Internalizing, Externalizing, Interpersonal, and PSY-5). Both cases achieved a 52/52 match on raw scores and T-scores.

## Validation Cases

### Case 1: Greg G (TEST_001)

- **Pearson Reference:** `Greg G.pdf` (ID: 737-1, Date Assessed: 01/29/2026)
- **Input Data:** `example_data/test_scores_001.csv`
- **Generated Report:** `output/reports/TEST_001_report.html`
- **Result:** 52/52 scales match (raw scores and T-scores)

### Case 2: 737 Y

- **Pearson Reference:** `737-Y MMPI-3-Score-Report.pdf` (ID: 737 Y, Date Assessed: 02/28/2026)
- **Input Data:** `example_data/mmpi3_itemscores_SM.csv`
- **Generated Report:** `output/reports/737_Y_report.html`
- **Result:** 52/52 scales match (raw scores and T-scores)

## Scales Validated (52 total)

**Validity (10):** CRIN, VRIN, TRIN, F, Fp, Fs, FBS, RBS, L, K

**Higher-Order (3):** EID, THD, BXD

**Restructured Clinical (8):** RCd, RC1, RC2, RC4, RC6, RC7, RC8, RC9

**Somatic/Cognitive (4):** MLS, NUC, EAT, COG

**Internalizing (10):** SUI, HLP, SFD, NFC, STR, WRY, CMP, ARX, ANP, BRF

**Externalizing (7):** FML, JCP, SUB, IMP, ACT, AGG, CYN

**Interpersonal (5):** SFI, DOM, DSF, SAV, SHY

**PSY-5 (5):** AGGR, PSYC, DISC, NEGE, INTR

## Files Validated Against Ground Truth

| File | Description | Validated Against |
|------|-------------|-------------------|
| `templates/mapping.json` | Item-to-scale mappings and keyed directions | Pearson raw scores (both cases) |
| `templates/tscore_tables.json` | Raw-to-T-score conversion tables | Pearson T-scores (both cases) |
| `templates/scales.json` | Scale metadata and abbreviations | Pearson report scale listings |
| `output/reports/TEST_001_report.html` | Greg G generated report | `Greg G.pdf` |
| `output/reports/737_Y_report.html` | 737 Y generated report | `737-Y MMPI-3-Score-Report.pdf` |

## Issues Found and Resolved

1. **ARX abbreviation typo** — `scales.json` had `"AXR"` instead of `"ARX"`, causing the scale to be excluded from reports. Fixed 2026-03-12.
2. **SUB item error** — `mapping.json` had item 127 (keyed True) instead of item 237 (keyed False). This produced incorrect SUB scores for certain response patterns. Fixed 2026-03-12.

## Validation Date

2026-03-12
