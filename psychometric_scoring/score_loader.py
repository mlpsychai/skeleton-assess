"""
Score Loader

Loads and parses psychometric test scores from CSV files.
Supports both boolean (True/False) and Likert-scale instruments.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List


class ScoreLoader:
    """Loads psychometric test scores from CSV files."""

    def __init__(self, num_items: int,
                 response_type: str = "boolean",
                 response_options: Optional[Dict[str, Any]] = None):
        """
        Initialize the score loader.

        Args:
            num_items: Number of items in the instrument.
            response_type: "boolean" or "likert".
            response_options: For boolean: {"true_values": [...], "false_values": [...]}.
                              For likert: {"min_value": 0, "max_value": 3}.
        """
        self.required_metadata_columns = ['test_id', 'test_date', 'examinee_id']
        self.num_items = num_items
        self.response_type = response_type
        self.response_options = response_options or {}

        # Validate that boolean instruments have response_options defined in config
        if self.response_type == "boolean" and not self.response_options:
            raise ValueError(
                "Boolean instruments require 'response_options' with 'true_values' "
                "and 'false_values' defined in instrument_config.json"
            )

    def load_csv(self, csv_path: str) -> Dict[str, Any]:
        """
        Load scores from a CSV file.

        Args:
            csv_path: Path to CSV file

        Returns:
            Dictionary containing:
                - test_id: Unique test identifier
                - test_date: Date of test administration
                - examinee_id: Examinee identifier
                - responses: Dict mapping item numbers to parsed responses
                - csv_path: Source file path

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If required columns are missing
        """
        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Load CSV
        df = pd.read_csv(csv_path)

        if len(df) == 0:
            raise ValueError(f"CSV file is empty: {csv_path}")

        # Check for required metadata columns
        missing_cols = [col for col in self.required_metadata_columns
                       if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Check for item columns
        item_cols = [f"item_{i}" for i in range(1, self.num_items + 1)]
        missing_items = [col for col in item_cols if col not in df.columns]
        if missing_items:
            raise ValueError(
                f"Missing {len(missing_items)} item columns. "
                f"Expected item_1 through item_{self.num_items}"
            )

        # Process first row (assuming single test per file)
        row = df.iloc[0]

        # Extract metadata
        metadata = {
            'test_id': str(row['test_id']),
            'test_date': str(row['test_date']),
            'examinee_id': str(row['examinee_id'])
        }

        # Extract item responses
        responses = {}
        for i in range(1, self.num_items + 1):
            col_name = f"item_{i}"
            value = row[col_name]

            if pd.isna(value) or value == '' or value == 'None':
                responses[i] = None
            elif self.response_type == "boolean":
                responses[i] = self._parse_boolean(value)
            elif self.response_type == "likert":
                responses[i] = self._parse_likert(value)
            else:
                responses[i] = value

        return {
            'test_id': metadata['test_id'],
            'test_date': metadata['test_date'],
            'examinee_id': metadata['examinee_id'],
            'responses': responses,
            'csv_path': str(csv_path)
        }

    def _parse_boolean(self, value) -> Optional[bool]:
        """Parse a value as boolean using configured true/false values."""
        str_val = str(value).strip()
        true_values = [v.lower() for v in self.response_options['true_values']]
        false_values = [v.lower() for v in self.response_options['false_values']]

        if str_val.lower() in true_values:
            return True
        elif str_val.lower() in false_values:
            return False
        else:
            # Keep as-is for validator to catch
            return value

    def _parse_likert(self, value) -> Optional[int]:
        """Parse a value as Likert integer."""
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            # Keep as-is for validator to catch
            return value

    def load_batch(self, directory: str) -> list:
        """
        Load all CSV files from a directory.

        Args:
            directory: Path to directory containing CSV files

        Returns:
            List of score data dictionaries
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # Find all CSV files
        csv_files = list(directory.glob("*.csv"))

        if not csv_files:
            raise ValueError(f"No CSV files found in: {directory}")

        results = []
        errors = []

        for csv_file in csv_files:
            try:
                data = self.load_csv(str(csv_file))
                results.append(data)
            except Exception as e:
                errors.append({
                    'file': str(csv_file),
                    'error': str(e)
                })

        if errors and not results:
            # All files failed
            error_msg = "All CSV files failed to load:\n"
            for err in errors:
                error_msg += f"  {err['file']}: {err['error']}\n"
            raise ValueError(error_msg)

        return results
