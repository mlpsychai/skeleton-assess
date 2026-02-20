#!/usr/bin/env python3
"""
Smoke test: load → validate → score → report using the skeleton package.

Usage:
  python smoke_test.py --instrument-config <config.json> --score-file <responses.csv>
"""
import sys
import os
import argparse

# Add skeleton_assess to path
sys.path.insert(0, os.path.dirname(__file__))

from psychometric_scoring.instrument_config import load_instrument_config
from psychometric_scoring.score_loader import ScoreLoader
from psychometric_scoring.score_validator import ScoreValidator
from psychometric_scoring.score_calculator import ScoreCalculator
from psychometric_scoring.html_report_generator import HTMLReportGenerator
from psychometric_scoring.report_generator import ReportGenerator

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def main():
    parser = argparse.ArgumentParser(description="Skeleton smoke test")
    parser.add_argument('--instrument-config', type=str, default='instrument_config.json',
                        help='Path to instrument configuration JSON')
    parser.add_argument('--score-file', type=str, required=True,
                        help='Path to response CSV file')
    args = parser.parse_args()

    print("=" * 60)
    print("SKELETON SMOKE TEST")
    print("=" * 60)

    # 1. Load instrument config
    print("\n[1] Loading instrument config...")
    config = load_instrument_config(args.instrument_config)
    print(f"    Instrument: {config['instrument_name']}")
    print(f"    Items: {config['num_items']}")
    print(f"    Response type: {config['response_type']}")
    print(f"    Categories: {len(config['categories'])}")
    print(f"    Safety scales: {config['safety_scales']}")

    # 2. Load CSV
    print("\n[2] Loading CSV...")
    loader = ScoreLoader(
        num_items=config['num_items'],
        response_type=config['response_type'],
        response_options=config.get('response_options', {}),
    )
    score_data = loader.load_csv(args.score_file)
    print(f"    Test ID: {score_data['test_id']}")
    print(f"    Items loaded: {len(score_data['responses'])}")

    # 3. Validate
    print("\n[3] Validating responses...")
    validator = ScoreValidator(
        num_items=config['num_items'],
        max_missing_threshold=config.get('max_missing_threshold', 0.10),
        instrument_name=config['instrument_name'],
        response_type=config['response_type'],
        response_options=config.get('response_options', {}),
    )
    val_report = validator.validate(score_data)
    print(f"    Valid: {val_report['is_valid']}")
    print(f"    Completion: {val_report['completion_rate']:.1%}")
    print(f"    Missing: {val_report['missing_count']}")
    print(f"    Errors: {len(val_report['errors'])}")
    print(f"    Warnings: {len(val_report['warnings'])}")
    print(f"    Assessment: {validator.get_validity_assessment(val_report)}")

    # 4. Calculate scores
    print("\n[4] Calculating scale scores...")
    calculator = ScoreCalculator(instrument_config=config)
    calc_results = calculator.calculate(score_data)
    scale_scores = calc_results['scale_scores']
    print(f"    Scales scored: {len(scale_scores)}")
    print(f"    Elevated: {calc_results['summary']['elevated_scales_count']}")
    if calc_results['summary']['elevated_scales']:
        print(f"    Elevated list: {', '.join(calc_results['summary']['elevated_scales'])}")

    # Show a few sample scores
    print("\n    Sample scores:")
    for abbr in list(scale_scores.keys())[:8]:
        s = scale_scores[abbr]
        t = s.get('t_score_display', 'N/A')
        print(f"      {abbr:6s} ({s['scale_name']:30s}): Raw={s['raw_score']:3d}/{s['total_items']:2d}  T={t:>4s}  {s['interpretive_range']}")

    # 5. Generate HTML report
    print("\n[5] Generating HTML report...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_gen = HTMLReportGenerator(instrument_config=config)
    html_path = html_gen.generate_html_report(
        calc_results, val_report,
        os.path.join(OUTPUT_DIR, f"{score_data['test_id']}_smoke_test.html"),
    )
    print(f"    HTML report: {html_path}")

    # 6. Generate DOCX report
    print("\n[6] Generating DOCX report...")
    try:
        docx_gen = ReportGenerator(instrument_config=config)
        docx_path = docx_gen.generate_report(
            calc_results, val_report,
            os.path.join(OUTPUT_DIR, f"{score_data['test_id']}_smoke_test.docx"),
        )
        print(f"    DOCX report: {docx_path}")
    except Exception as e:
        print(f"    DOCX generation failed (expected if python-docx not installed): {e}")

    # 7. Verify category lookup
    print("\n[7] Verifying category lookups...")
    for cat in config['categories']:
        title = cat['title']
        scales_in_cat = [s for s in cat['scales'] if s in scale_scores]
        print(f"    {title}: {len(scales_in_cat)}/{len(cat['scales'])} scales scored")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
