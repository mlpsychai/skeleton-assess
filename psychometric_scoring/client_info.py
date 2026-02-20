"""
Psychometric Client Information Module

Handles client demographic data for interpretive reports.
Supports interactive CLI collection and JSON file loading.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class ClientInfo:
    """Client demographic and referral information for reports."""
    client_name: str = ""
    dob: str = ""
    age: Optional[int] = None
    sex: str = ""
    education: str = ""
    marital_status: str = ""
    referral_source: str = ""
    referral_question: str = ""
    background: str = ""
    examiner_name: str = ""
    examiner_credentials: str = ""
    supervisor_name: str = ""
    supervisor_credentials: str = ""
    setting: str = ""
    test_date: str = ""
    test_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_context_string(self) -> str:
        """Format client info as context string for RAG prompts."""
        parts = []
        if self.client_name:
            parts.append(f"Client: {self.client_name}")
        if self.age and self.sex:
            parts.append(f"Demographics: {self.age}-year-old {self.sex}")
        elif self.age:
            parts.append(f"Age: {self.age}")
        elif self.sex:
            parts.append(f"Sex: {self.sex}")
        if self.education:
            parts.append(f"Education: {self.education}")
        if self.marital_status:
            parts.append(f"Marital Status: {self.marital_status}")
        if self.referral_source:
            parts.append(f"Referral Source: {self.referral_source}")
        if self.referral_question:
            parts.append(f"Referral Question: {self.referral_question}")
        if self.background:
            parts.append(f"Background: {self.background}")
        if self.setting:
            parts.append(f"Setting: {self.setting}")
        return "\n".join(parts)


def load_client_info_json(json_path: str) -> ClientInfo:
    """
    Load client info from a JSON file.

    Supports both flat format and nested format with 'client_info' key.
    Also extracts test_info fields (test_id, test_date) if present.

    Args:
        json_path: Path to JSON file

    Returns:
        ClientInfo instance
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Support nested format
    client_data = {}

    if 'client_info' in data:
        client_data.update(data['client_info'])
    else:
        # Flat format — use all keys directly
        client_data.update(data)

    # Extract test_info if present
    if 'test_info' in data:
        test_info = data['test_info']
        if 'test_id' in test_info:
            client_data.setdefault('test_id', test_info['test_id'])
        if 'test_date' in test_info:
            client_data.setdefault('test_date', test_info['test_date'])

    # Build ClientInfo from matching fields
    info = ClientInfo()
    for field_name in ClientInfo.__dataclass_fields__:
        if field_name in client_data:
            setattr(info, field_name, client_data[field_name])

    return info


def collect_client_info_interactive(test_id: str = "", test_date: str = "") -> ClientInfo:
    """
    Collect client info interactively from CLI.

    Args:
        test_id: Pre-filled test ID
        test_date: Pre-filled test date

    Returns:
        ClientInfo instance
    """
    print("\n" + "=" * 60)
    print("Client Information Collection")
    print("Press Enter to skip any field")
    print("=" * 60)

    def ask(prompt, default=""):
        val = input(f"  {prompt}: ").strip()
        return val if val else default

    info = ClientInfo()
    info.test_id = test_id
    info.test_date = test_date

    info.client_name = ask("Client Name")
    info.dob = ask("Date of Birth (YYYY-MM-DD)")

    age_str = ask("Age")
    if age_str.isdigit():
        info.age = int(age_str)

    info.sex = ask("Sex (Male/Female)")
    info.education = ask("Education Level")
    info.marital_status = ask("Marital Status")
    info.referral_source = ask("Referral Source")
    info.referral_question = ask("Referral Question")
    info.background = ask("Background Summary")
    info.examiner_name = ask("Examiner Name")
    info.examiner_credentials = ask("Examiner Credentials")
    info.supervisor_name = ask("Supervisor Name")
    info.supervisor_credentials = ask("Supervisor Credentials")
    info.setting = ask("Setting")

    print("=" * 60 + "\n")
    return info
