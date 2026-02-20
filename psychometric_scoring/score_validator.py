"""
Score Validator

Validates psychometric test response data for completeness and correctness.
Supports both boolean (True/False) and Likert-scale instruments.
"""

from typing import Dict, Any, List, Optional


class ScoreValidator:
    """Validates psychometric test responses."""

    def __init__(self, num_items: int,
                 max_missing_threshold: float,
                 instrument_name: str = "Instrument",
                 response_type: str = "boolean",
                 response_options: Optional[Dict[str, Any]] = None):
        """
        Initialize the validator.

        Args:
            num_items: Number of items in the instrument.
            max_missing_threshold: Maximum proportion of missing items allowed
                                   (from instrument_config.json).
            instrument_name: Name of the instrument (for messages).
            response_type: "boolean" or "likert".
            response_options: For likert: {"min_value": 0, "max_value": 3}.
        """
        self.num_items = num_items
        self.max_missing_threshold = max_missing_threshold
        self.instrument_name = instrument_name
        self.response_type = response_type
        self.response_options = response_options or {}

    def validate(self, score_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate score data.

        Args:
            score_data: Dictionary from ScoreLoader containing responses

        Returns:
            Validation report dictionary containing:
                - is_valid: Boolean indicating if protocol is valid
                - errors: List of error messages (critical issues)
                - warnings: List of warning messages (concerns)
                - completion_rate: Float 0-1 indicating % of items answered
                - invalid_responses: List of (item_num, value) tuples
                - missing_count: Number of unanswered items
        """
        responses = score_data['responses']
        errors = []
        warnings = []
        invalid_responses = []
        missing_count = 0

        # Check item count
        if len(responses) != self.num_items:
            errors.append(
                f"Expected {self.num_items} items, got {len(responses)}"
            )

        # Validate each response
        for item_num in range(1, self.num_items + 1):
            if item_num not in responses:
                errors.append(f"Missing item_{item_num}")
                continue

            value = responses[item_num]

            # Check if missing
            if value is None:
                missing_count += 1
                continue

            # Type-specific validation
            if self.response_type == "boolean":
                if not isinstance(value, bool):
                    invalid_responses.append((item_num, value))
                    errors.append(
                        f"Item {item_num} has invalid response: {value} "
                        f"(expected True/False or missing)"
                    )
            elif self.response_type == "likert":
                min_val = self.response_options.get('min_value', 0)
                max_val = self.response_options.get('max_value', 3)
                if not isinstance(value, int) or value < min_val or value > max_val:
                    invalid_responses.append((item_num, value))
                    errors.append(
                        f"Item {item_num} has invalid response: {value} "
                        f"(expected integer {min_val}-{max_val})"
                    )

        # Calculate completion rate
        completion_rate = (self.num_items - missing_count) / self.num_items

        # Check completion threshold
        if completion_rate < (1 - self.max_missing_threshold):
            warnings.append(
                f"Low completion rate: {completion_rate:.1%} "
                f"({missing_count} items unanswered). "
                f"{self.instrument_name} protocols with >{self.max_missing_threshold:.0%} missing items may be invalid."
            )

        # Determine overall validity
        is_valid = len(errors) == 0

        return {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'completion_rate': completion_rate,
            'missing_count': missing_count,
            'invalid_responses': invalid_responses,
            'test_id': score_data['test_id']
        }

    def get_validity_assessment(self, validation_report: Dict[str, Any]) -> str:
        """
        Get human-readable validity assessment.

        Args:
            validation_report: Report from validate()

        Returns:
            String describing validity status
        """
        if not validation_report['is_valid']:
            return "INVALID - Protocol has critical errors"

        completion_rate = validation_report['completion_rate']
        warnings = validation_report['warnings']

        if completion_rate < (1 - self.max_missing_threshold):
            return "QUESTIONABLE - Low completion rate may affect validity"

        if warnings:
            return "VALID - Minor concerns noted"

        return "VALID - Protocol meets all validity criteria"

    def format_validation_report(self, validation_report: Dict[str, Any]) -> str:
        """
        Format validation report as human-readable text.

        Args:
            validation_report: Report from validate()

        Returns:
            Formatted string report
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"{self.instrument_name} Validation Report: {validation_report['test_id']}")
        lines.append("=" * 60)

        # Overall status
        status = self.get_validity_assessment(validation_report)
        lines.append(f"\nStatus: {status}")

        # Completion info
        completion_rate = validation_report['completion_rate']
        missing_count = validation_report['missing_count']
        lines.append(
            f"Completion: {completion_rate:.1%} "
            f"({self.num_items - missing_count}/{self.num_items} items)"
        )

        # Errors
        if validation_report['errors']:
            lines.append(f"\nErrors ({len(validation_report['errors'])}):")
            for error in validation_report['errors']:
                lines.append(f"  - {error}")

        # Warnings
        if validation_report['warnings']:
            lines.append(f"\nWarnings ({len(validation_report['warnings'])}):")
            for warning in validation_report['warnings']:
                lines.append(f"  - {warning}")

        # Invalid responses
        if validation_report['invalid_responses']:
            lines.append(f"\nInvalid Responses:")
            for item_num, value in validation_report['invalid_responses'][:10]:
                lines.append(f"  - Item {item_num}: {value}")
            if len(validation_report['invalid_responses']) > 10:
                remaining = len(validation_report['invalid_responses']) - 10
                lines.append(f"  ... and {remaining} more")

        lines.append("=" * 60)

        return "\n".join(lines)
