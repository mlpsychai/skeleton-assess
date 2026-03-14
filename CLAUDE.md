# CLAUDE.md - Project Instructions

## Git Workflow

- **Remote:** `git@github.com:mlpsychai/skeleton-assess.git`
- **Branch:** `master`
- **Push command:** `GIT_SSH_COMMAND="ssh -i C:/Users/sm4663/.ssh/id_ed25519" git push origin master`
- **Always commit AND push** when the user says "commit" or "update git" — local-only commits cause confusion.
- After generating reports, commit the output files too (HTML reports in `output/reports/`).

## Report Generation

- Always regenerate **both** Eve and Greg reports when making PAI changes:
  ```bash
  python main.py --instrument-config configs/pai_config.json --score-file example_data/pai_eve.csv --format html
  python main.py --instrument-config configs/pai_config.json --score-file example_data/pai_greg.csv --format html
  ```
- MMPI-3 config: `configs/mmpi_335_config.json`
- Output goes to `output/reports/pai/` and `output/reports/mmpi3/`

## Environment

- Python path: `/c/Users/sm4663/AppData/Local/Programs/Python/Python312/python`
- `python3` doesn't work — use full path above
- Always set `PYTHONIOENCODING=utf-8` to avoid cp1252 encoding errors

## Validation

- PAI validated against two PAR score reports: Eve (737-Eve) and Greg (737-Greg)
- 104/104 raw scores correct, 103/104 T-scores correct
- Known discrepancy: WRM Greg T=8 (ours) vs T=30 (PAR display floor) — not a bug
- ICN (Inconsistency) not implemented — needs item-pair data from manual
- Run `python validate_pai.py` to verify scoring against PAR references
