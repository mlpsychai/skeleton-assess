"""
Score Calculator

Calculates raw scores for all scales using item-to-scale mappings,
looks up T-scores from normative tables, and assigns interpretive ranges.
All instrument-specific values are read from instrument_config.json.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .instrument_config import load_instrument_config, is_elevated


class ScoreCalculator:
    """Calculates raw scores and applies interpretive ranges."""

    def __init__(self, instrument_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the calculator.

        Args:
            instrument_config: Instrument configuration dict.
                               Loaded from instrument_config.json if not provided.
        """
        if instrument_config is None:
            instrument_config = load_instrument_config()

        self.config = instrument_config
        base_path = Path(__file__).parent.parent

        # Resolve file paths from config
        mapping_file = base_path / self.config['files']['mapping']
        scales_file = base_path / self.config['files']['scales']
        tscore_file = base_path / self.config['files']['tscore_tables']

        # Load mapping
        with open(mapping_file, 'r') as f:
            self.mapping_data = json.load(f)

        # Load scale descriptions
        with open(scales_file, 'r') as f:
            self.scales_data = json.load(f)

        # Load T-score lookup tables
        self.tscore_tables = {}
        if tscore_file.exists():
            with open(tscore_file, 'r') as f:
                tscore_data = json.load(f)
            self.tscore_tables = tscore_data.get('scales', {})

        # Build scale definitions
        self.scales = self.mapping_data.get('scales', {})

        # Build interpretive cutoffs from config
        self.interpretive_cutoffs = self.config['interpretive_cutoffs']

        # Build scale-to-category lookup from config
        self._category_lookup = {}
        for cat in self.config.get('categories', []):
            for scale_abbr in cat.get('scales', []):
                self._category_lookup[scale_abbr] = cat['title']

    def calculate_raw_scores(self, responses: Dict[int, Any]) -> Dict[str, Any]:
        """
        Calculate raw scores for all scales.

        Supports both boolean (keyed True/False) and Likert (scoring_weights)
        item formats. The format is detected per-item from the mapping data.

        Args:
            responses: Dictionary mapping item numbers to responses
                       (bool for boolean, int for Likert)

        Returns:
            Dictionary containing raw scores and metadata for all scales
        """
        scale_scores = {}

        for scale_abbr, scale_info in self.scales.items():
            # Handle pair-based validity scales (CRIN, VRIN, TRIN)
            if scale_info.get('scale_type') == 'item_pairs':
                pair_result = self._calculate_pair_score(scale_info, responses)
                raw_score = pair_result['raw_score']
                total_pairs = pair_result['total_pairs']

                # Look up T-score and interpretive range
                t_score, t_display = self._lookup_t_score(scale_abbr, raw_score)
                interpretive_range = self._get_interpretive_range_from_t(t_score)

                scale_scores[scale_abbr] = {
                    'scale_name': scale_info['scale_name'],
                    'abbreviation': scale_abbr,
                    'raw_score': raw_score,
                    'total_items': total_pairs,
                    'items_scored': pair_result['pairs_scored'],
                    'proportion_scored': pair_result['pairs_scored'] / total_pairs if total_pairs > 0 else 0,
                    'missing_items': [],
                    'interpretive_range': interpretive_range,
                    't_score': t_score,
                    't_score_display': t_display
                }
                continue

            # Calculate raw score for this scale
            raw_score = 0
            items_scored = 0
            missing_items = []

            for item_info in scale_info['items']:
                item_num = item_info['item']

                if item_num not in responses:
                    missing_items.append(item_num)
                    continue

                response = responses[item_num]

                if response is None:
                    missing_items.append(item_num)
                    continue

                # Likert scoring: uses scoring_weights dict
                if 'scoring_weights' in item_info:
                    weight = item_info['scoring_weights'].get(str(response), 0)
                    raw_score += weight
                    items_scored += 1
                # Keyed scoring: boolean or Likert forward/reverse
                elif 'keyed' in item_info:
                    keyed_direction = item_info['keyed']  # "True" or "False" string
                    if isinstance(response, (int, float)):
                        # Likert: forward = raw value, reverse = max - value
                        max_val = self.config.get('response_options', {}).get('max_value', 3)
                        if keyed_direction == "True":
                            raw_score += int(response)
                        else:
                            raw_score += max_val - int(response)
                    else:
                        # Boolean: keyed match scores 1
                        if keyed_direction == "True" and response is True:
                            raw_score += 1
                        elif keyed_direction == "False" and response is False:
                            raw_score += 1
                    items_scored += 1
                else:
                    items_scored += 1

            total_items = scale_info['item_count']
            proportion_scored = items_scored / total_items if total_items > 0 else 0

            # Look up T-score and interpretive range
            t_score, t_display = self._lookup_t_score(scale_abbr, raw_score)
            interpretive_range = self._get_interpretive_range_from_t(t_score)

            scale_scores[scale_abbr] = {
                'scale_name': scale_info['scale_name'],
                'abbreviation': scale_abbr,
                'raw_score': raw_score,
                'total_items': total_items,
                'items_scored': items_scored,
                'proportion_scored': proportion_scored,
                'missing_items': missing_items,
                'interpretive_range': interpretive_range,
                't_score': t_score,
                't_score_display': t_display
            }

        return scale_scores

    def _calculate_pair_score(self, scale_info: Dict[str, Any],
                              responses: Dict[int, Any]) -> Dict[str, Any]:
        """
        Calculate score for pair-based validity scales (CRIN, VRIN, TRIN).

        Args:
            scale_info: Scale definition containing pair arrays
            responses: Dictionary mapping item numbers to responses

        Returns:
            Dictionary with raw_score, pairs_scored, pairs_missing, total_pairs
        """
        raw_score = scale_info.get('base_score', 0)
        pairs_scored = 0
        pairs_missing = 0

        # Discordant pairs: +1 when both items match their keys
        for pair in scale_info.get('discordant_pairs', []):
            resp1 = responses.get(pair['item1'])
            resp2 = responses.get(pair['item2'])

            if resp1 is None or resp2 is None:
                pairs_missing += 1
                continue

            pairs_scored += 1
            key1_match = (pair['key1'] == 'T' and resp1 is True) or \
                         (pair['key1'] == 'F' and resp1 is False)
            key2_match = (pair['key2'] == 'T' and resp2 is True) or \
                         (pair['key2'] == 'F' and resp2 is False)

            if key1_match and key2_match:
                raw_score += 1

        # Keyed true-true pairs: +1 when both items answered True
        for pair in scale_info.get('keyed_true_true', []):
            resp1 = responses.get(pair['item1'])
            resp2 = responses.get(pair['item2'])

            if resp1 is None or resp2 is None:
                pairs_missing += 1
                continue

            pairs_scored += 1
            if resp1 is True and resp2 is True:
                raw_score += 1

        # Keyed false-false pairs
        # Bidirectional scales (base_score > 0): -1 when both False
        # Unidirectional scales (base_score = 0): +1 when both False
        is_bidirectional = scale_info.get('base_score', 0) > 0
        for pair in scale_info.get('keyed_false_false', []):
            resp1 = responses.get(pair['item1'])
            resp2 = responses.get(pair['item2'])

            if resp1 is None or resp2 is None:
                pairs_missing += 1
                continue

            pairs_scored += 1
            if resp1 is False and resp2 is False:
                raw_score += -1 if is_bidirectional else 1

        total_pairs = pairs_scored + pairs_missing

        return {
            'raw_score': raw_score,
            'pairs_scored': pairs_scored,
            'pairs_missing': pairs_missing,
            'total_pairs': total_pairs
        }

    def _lookup_t_score(self, scale_abbr: str, raw_score: int) -> Tuple[Optional[int], Optional[str]]:
        """
        Look up T-score from official normative tables.

        Args:
            scale_abbr: Scale abbreviation
            raw_score: Raw score for the scale

        Returns:
            Tuple of (t_score_numeric, t_score_display).
            t_score_display includes direction suffix for TRIN (e.g. "54T").
            Returns (None, None) if scale not in tables.
        """
        if scale_abbr not in self.tscore_tables:
            return (None, None)

        table = self.tscore_tables[scale_abbr]['raw_to_t']
        raw_key = str(raw_score)

        if raw_key in table:
            value = table[raw_key]
            if isinstance(value, str):
                t_numeric = int(value[:-1])
                return (t_numeric, value)
            else:
                return (int(value), str(int(value)))

        # Raw score beyond table range — clamp to nearest entry
        raw_keys = sorted([int(k) for k in table.keys()])
        if raw_score < raw_keys[0]:
            clamped = raw_keys[0]
        else:
            clamped = raw_keys[-1]

        value = table[str(clamped)]
        if isinstance(value, str):
            t_numeric = int(value[:-1])
            return (t_numeric, value)
        else:
            return (int(value), str(int(value)))

    def _get_interpretive_range_from_t(self, t_score: Optional[int]) -> str:
        """
        Determine interpretive range from a T-score using config-driven cutoffs.

        Args:
            t_score: Numeric T-score

        Returns:
            String describing interpretive range
        """
        if t_score is None:
            return "Unable to score"

        for cutoff in self.interpretive_cutoffs:
            min_t = cutoff.get('min_t', 0)
            max_t = cutoff.get('max_t', 999)
            if min_t <= t_score <= max_t:
                return cutoff['label']

        # Fallback for scores beyond defined ranges
        return self.interpretive_cutoffs[-1]['label']

    def calculate(self, score_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate scores from loaded score data.

        Args:
            score_data: Dictionary from ScoreLoader

        Returns:
            Complete scoring results including:
                - test_id, test_date, examinee_id
                - scale_scores: Dictionary of scale scores
                - summary: Overall summary statistics
        """
        responses = score_data['responses']

        scale_scores = self.calculate_raw_scores(responses)

        elevated_scales = {
            abbr: scores for abbr, scores in scale_scores.items()
            if is_elevated(self.config, scores['interpretive_range'])
        }

        summary = {
            'total_scales': len(scale_scores),
            'scales_scored': sum(1 for s in scale_scores.values() if s['items_scored'] > 0),
            'elevated_scales_count': len(elevated_scales),
            'elevated_scales': list(elevated_scales.keys())
        }

        return {
            'test_id': score_data['test_id'],
            'test_date': score_data['test_date'],
            'examinee_id': score_data['examinee_id'],
            'scale_scores': scale_scores,
            'summary': summary
        }

    def get_scale_category(self, scale_abbr: str) -> str:
        """
        Get the category for a scale.

        Args:
            scale_abbr: Scale abbreviation

        Returns:
            Category title from instrument config
        """
        if scale_abbr in self._category_lookup:
            return self._category_lookup[scale_abbr]

        # Fallback: check scales JSON structure
        for category_info in self.scales_data.get('scale_categories', []):
            category = category_info.get('category', '')
            if 'scales' in category_info:
                for scale in category_info['scales']:
                    if scale.get('abbreviation') == scale_abbr:
                        return category
            if 'subcategories' in category_info:
                for subcat in category_info['subcategories']:
                    if 'scales' in subcat:
                        for scale in subcat['scales']:
                            if scale.get('abbreviation') == scale_abbr:
                                return category

        return "Other Scales"
