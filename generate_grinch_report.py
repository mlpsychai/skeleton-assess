"""
Generate Grinch MCMI-IV report with Pearson-adjusted BR scores.

Temporary workaround: runs scoring pipeline, then overrides BR values
with ground truth from Pearson qglobal report (737-1, 03/18/2026)
before HTML generation. This bypasses D.2 adjustment tables which
are not yet implemented.

Usage: python generate_grinch_report.py
"""

from pathlib import Path
from psychometric_scoring.instrument_config import load_instrument_config
from psychometric_scoring.score_calculator import ScoreCalculator
from psychometric_scoring.score_loader import ScoreLoader
from psychometric_scoring.score_validator import ScoreValidator
from psychometric_scoring.html_report_generator import HTMLReportGenerator

# Pearson ground truth: adjusted BR scores from Grinch_MCMI-IV_qglobal.pdf page 3
# Format: scale_abbr -> (adjusted_BR, adjusted_interpretive_range)
PEARSON_ADJUSTED = {
    # Modifying Indices (no adjustment — these are the base for adjustments)
    # V and W have no BR in our system (raw-only validity)
    "X": 86, "Y": 5, "Z": 79,
    # Clinical Personality Patterns (Disclosure: -2 base; A/CC on 2A, 2B, 8B)
    "1": 76, "2A": 86, "2B": 78, "3": 38, "4A": 4,
    "4B": 16, "5": 86, "6A": 98, "6B": 97, "7": 6,
    "8A": 81, "8B": 73,
    # Severe Personality Pathology (A/CC on S, C)
    "S": 77, "C": 75, "P": 114,
    # Clinical Syndromes (Disclosure: -1)
    "A": 84, "H": 74, "N": 59, "D": 74, "B": 74,
    "T": 66, "R": 70,
    # Severe Clinical Syndromes (Disclosure: -1)
    "SS": 70, "CC": 91, "PP": 94,
}

# Pearson ground truth: Grossman Facet Scale scores from page 4
PEARSON_FACETS = {
    "1.1": 100, "1.2": 85, "1.3": 72,
    "2A.1": 82, "2A.2": 75, "2A.3": 85,
    "2B.1": 85, "2B.2": 85, "2B.3": 100,
    "3.1": 70, "3.2": 65, "3.3": 70,
    "4A.1": 70, "4A.2": 12, "4A.3": 12,
    "4B.1": 20, "4B.2": 0, "4B.3": 30,
    "5.1": 75, "5.2": 12, "5.3": 95,
    "6A.1": 75, "6A.2": 100, "6A.3": 68,
    "6B.1": 100, "6B.2": 85, "6B.3": 75,
    "7.1": 30, "7.2": 48, "7.3": 0,
    "8A.1": 100, "8A.2": 85, "8A.3": 77,
    "8B.1": 75, "8B.2": 75, "8B.3": 80,
    "S.1": 66, "S.2": 75, "S.3": 100,
    "C.1": 75, "C.2": 78, "C.3": 72,
    "P.1": 100, "P.2": 100, "P.3": 100,
}


def get_interpretive_range(br, cutoffs):
    """Determine interpretive range from BR score using config cutoffs."""
    for cutoff in cutoffs:
        min_t = cutoff.get('min_t', 0)
        max_t = cutoff.get('max_t', 999)
        if min_t <= br <= max_t:
            return cutoff['label']
    return cutoffs[-1]['label']


def is_elevated(config, label):
    """Check if an interpretive range label is considered elevated."""
    for cutoff in config['interpretive_cutoffs']:
        if cutoff['label'] == label:
            return cutoff.get('elevated', False)
    return False


def main():
    config = load_instrument_config('configs/mcmi4_config.json')
    calc = ScoreCalculator(config)
    loader = ScoreLoader(
        num_items=config['num_items'],
        response_type=config['response_type'],
        response_options=config.get('response_options'),
    )
    validator = ScoreValidator(
        num_items=config['num_items'],
        max_missing_threshold=config.get('max_missing_threshold', 0.1),
        instrument_name=config.get('instrument_name', 'MCMI-4'),
        response_type=config['response_type'],
        response_options=config.get('response_options'),
    )

    # Load and score
    score_data = loader.load_csv('example_data/mcmi4_grinch.csv')
    validation_report = validator.validate(score_data)
    calc_results = calc.calculate(score_data)

    cutoffs = config['interpretive_cutoffs']

    # Apply Pearson adjusted BR overrides
    overrides_applied = 0
    for scale_abbr, adjusted_br in {**PEARSON_ADJUSTED, **PEARSON_FACETS}.items():
        if scale_abbr in calc_results['scale_scores']:
            entry = calc_results['scale_scores'][scale_abbr]
            old_br = entry['t_score']
            if old_br != adjusted_br:
                new_range = get_interpretive_range(adjusted_br, cutoffs)
                entry['t_score'] = adjusted_br
                entry['t_score_display'] = str(adjusted_br)
                entry['interpretive_range'] = new_range
                overrides_applied += 1
                print(f"  {scale_abbr}: BR {old_br} -> {adjusted_br} ({new_range})")

    print(f"\nApplied {overrides_applied} BR overrides")

    # Recompute elevated scales summary
    elevated_scales = {
        abbr: scores for abbr, scores in calc_results['scale_scores'].items()
        if is_elevated(config, scores['interpretive_range'])
    }
    calc_results['summary']['elevated_scales_count'] = len(elevated_scales)
    calc_results['summary']['elevated_scales'] = list(elevated_scales.keys())

    # Generate HTML report
    output_dir = Path('test_output')
    output_dir.mkdir(exist_ok=True)

    html_gen = HTMLReportGenerator(instrument_config=config)
    html_path = html_gen.generate_html_report(
        calc_results,
        validation_report,
        str(output_dir / "GRINCH_001_report.html"),
    )
    print(f"\nHTML report saved: {html_path}")
    print(f"Elevated scales: {len(elevated_scales)}")
    print(f"  {', '.join(sorted(elevated_scales.keys()))}")


if __name__ == '__main__':
    main()
