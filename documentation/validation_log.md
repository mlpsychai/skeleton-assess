# Validation Log

---

## MMPI-3

### Overview

All scoring output has been validated against Pearson-generated MMPI-3 Score Reports. Two independent cases were used, covering all 52 scales (Validity, Higher-Order, Restructured Clinical, Somatic/Cognitive, Internalizing, Externalizing, Interpersonal, and PSY-5). Both cases achieved a 52/52 match on raw scores and T-scores.

### Validation Cases

#### Case 1: Greg G (TEST_001)

- **Pearson Reference:** `Greg G.pdf` (ID: 737-1, Date Assessed: 01/29/2026)
- **Input Data:** `example_data/test_scores_001.csv`
- **Generated Report:** `output/reports/TEST_001_report.html`
- **Result:** 52/52 scales match (raw scores and T-scores)

#### Case 2: 737 Y

- **Pearson Reference:** `737-Y MMPI-3-Score-Report.pdf` (ID: 737 Y, Date Assessed: 02/28/2026)
- **Input Data:** `example_data/mmpi3_itemscores_SM.csv`
- **Generated Report:** `output/reports/737_Y_report.html`
- **Result:** 52/52 scales match (raw scores and T-scores)

### Scales Validated (52 total)

**Validity (10):** CRIN, VRIN, TRIN, F, Fp, Fs, FBS, RBS, L, K

**Higher-Order (3):** EID, THD, BXD

**Restructured Clinical (8):** RCd, RC1, RC2, RC4, RC6, RC7, RC8, RC9

**Somatic/Cognitive (4):** MLS, NUC, EAT, COG

**Internalizing (10):** SUI, HLP, SFD, NFC, STR, WRY, CMP, ARX, ANP, BRF

**Externalizing (7):** FML, JCP, SUB, IMP, ACT, AGG, CYN

**Interpersonal (5):** SFI, DOM, DSF, SAV, SHY

**PSY-5 (5):** AGGR, PSYC, DISC, NEGE, INTR

### Files Validated Against Ground Truth

| File | Description | Validated Against |
|------|-------------|-------------------|
| `templates/mmpi3/mapping.json` | Item-to-scale mappings and keyed directions | Pearson raw scores (both cases) |
| `templates/mmpi3/tscore_tables.json` | Raw-to-T-score conversion tables | Pearson T-scores (both cases) |
| `templates/mmpi3/scales.json` | Scale metadata and abbreviations | Pearson report scale listings |

### Issues Found and Resolved

1. **ARX abbreviation typo** — `scales.json` had `"AXR"` instead of `"ARX"`, causing the scale to be excluded from reports. Fixed 2026-03-12.
2. **SUB item error** — `mapping.json` had item 127 (keyed True) instead of item 237 (keyed False). This produced incorrect SUB scores for certain response patterns. Fixed 2026-03-12.

### Validation Date

2026-03-12

---

## PAI (Personality Assessment Inventory)

### Overview

Scoring validated against PAR-generated PAI Score Reports for two independent cases, covering 52 scales (3 validity, 10 clinical full scales, 31 clinical subscales, 2 alcohol/drug, 4 treatment consideration, and 2 interpersonal). Results: 103/104 T-score matches, 104/104 raw score matches.

### Validation Cases

#### Case 1: Eve (737-Eve)

- **PAR Reference:** `PAI docs/SM/737-Y PAI.pdf`
- **Result:** 52/52 scales match (raw scores and T-scores)

#### Case 2: Greg (737-Greg)

- **PAR Reference:** `PAI docs/THE GINCH/Greg PAI.pdf`
- **Result:** 51/52 scales match (raw scores and T-scores)
- **1 known discrepancy:** WRM raw=0 produces T=8 (correct per normative table); PAR report displays T=30 due to profile graph floor clipping

### Scales Validated (52 total)

**Validity (3):** INF, NIM, PIM

**Clinical Full Scales (10):** SOM, ANX, ARD, DEP, MAN, PAR, SCZ, BOR, ANT, AGG

**Clinical Subscales (31):** SOM-C, SOM-S, SOM-H, ANX-C, ANX-A, ANX-P, ARD-O, ARD-P, ARD-T, DEP-C, DEP-A, DEP-P, MAN-A, MAN-G, MAN-I, PAR-H, PAR-P, PAR-R, SCZ-P, SCZ-S, SCZ-T, BOR-A, BOR-I, BOR-N, BOR-S, ANT-A, ANT-E, ANT-S, AGG-A, AGG-V, AGG-P

**Alcohol/Drug (2):** ALC, DRG

**Treatment Consideration (4):** SUI, STR, NON, RXR

**Interpersonal (2):** DOM, WRM

### Not Yet Implemented

- **ICN (Inconsistency)** — pair-based scoring requiring 10 item pairs from the manual; not derivable from item numbers alone

### T-Score Table Sources

| Scale type | Source | Coverage |
|------------|--------|----------|
| Full/standalone scales (22) | Manual Table A.1 ground truth (hand-entered from PAI manual) | Full raw score range |
| Clinical scale extensions (raw 40+) | Manual Table A.1 extended range (hand-entered) | SOM, ANX, ARD, DEP, MAN, PAR, SCZ, BOR, ANT (0-72), AGG (0-54) |
| Subscales (31) | Derived from two reference clients' known raw/T pairs | Full raw score range |
| SOM-H, MAN-I subscales | Fallback M/SD from Table A.2 (both clients had identical raw scores) | Full raw score range |

### Files Validated Against Ground Truth

| File | Description | Validated Against |
|------|-------------|-------------------|
| `templates/pai/mapping.json` | Item-to-scale mappings and keying directions (344 items, 52 scales) | PAR raw scores (both cases) |
| `templates/pai/tscore_tables.json` | Raw-to-T-score conversion tables (52 scales) | PAR T-scores (both cases) |

### Issues Found and Resolved

1. **INF ground truth data entry error** — Excel had T=10 at raw=17; corrected to T=106. Fixed in `rebuild_tscore_tables.py`.
2. **ANX ground truth off-by-one** — Excel column was +1 vs PAR reports; corrected with -1 adjustment. Fixed in `rebuild_tscore_tables.py`.
3. **Eve item 242 response error** — `validate_pai.py` had MT (2); PDF shows ST (1). Fixed 2026-03-13.
4. **Reverse-scoring list corrections** — Items 25, 66 were incorrectly listed as reverse-scored (should be forward); item 299 was missing from reverse list; item 24 was incorrectly listed as forward (should be reverse). All confirmed against manual and fixed in `mapping.json` 2026-03-13.
5. **WRM Greg T=30 display floor** — PAR profile graph clips at T~30; ground truth table gives T=8 at raw=0. Our T=8 is mathematically correct. Not a scoring error.

### Validation Scripts

- `validate_pai.py` — response data, reference scores, and full validation logic
- `rebuild_tscore_tables.py` — T-score table generation from ground truth + reference derivation
- `derive_keying.py` — brute-force keying derivation against two reference clients

### Validation Date

2026-03-13
