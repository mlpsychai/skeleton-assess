"""
Instrument Configuration Loader

Loads instrument_config.json which serves as the single source of truth
for all instrument-specific values (scale lists, formatting, cutoffs, etc.).
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set


def load_instrument_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load instrument configuration from JSON file.

    Args:
        config_path: Path to instrument_config.json.
                     Defaults to project root instrument_config.json.

    Returns:
        Dictionary containing all instrument configuration.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "instrument_config.json"

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Instrument config not found: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Resolve file paths relative to project root (not config file location)
    project_root = Path(__file__).parent.parent

    # Auto-populate categories from scales.json if not defined in config
    if not config.get('categories'):
        config['categories'] = _build_categories_from_scales(config, project_root)

    # Auto-populate formatting from formatting.json if referenced
    _merge_formatting_file(config, project_root)

    return config


def _build_categories_from_scales(config: Dict[str, Any], project_root: Path) -> List[Dict]:
    """
    Build the categories list from the scales.json file referenced in config.

    Maps scale_categories from scales.json into the categories format
    expected by the rest of the pipeline.
    """
    scales_rel = config.get('files', {}).get('scales')
    if not scales_rel:
        return []

    scales_path = project_root / scales_rel
    if not scales_path.exists():
        return []

    with open(scales_path, 'r') as f:
        scales_data = json.load(f)

    categories = []
    validity_keywords = {'validity'}

    for sc in scales_data.get('scale_categories', []):
        cat_name = sc.get('category', '')
        key = re.sub(r'[^a-z0-9]+', '_', cat_name.lower()).strip('_')

        # Collect all scale abbreviations (handle flat, subcategory, and domain layouts)
        scale_abbrs = []
        if 'scales' in sc:
            for s in sc['scales']:
                if 'abbreviation' in s:
                    scale_abbrs.append(s['abbreviation'])
        if 'subcategories' in sc:
            for sub in sc['subcategories']:
                for s in sub.get('scales', []):
                    if 'abbreviation' in s:
                        scale_abbrs.append(s['abbreviation'])
        if 'domains' in sc:
            for domain in sc['domains']:
                for s in domain.get('scales', []):
                    if 'abbreviation' in s:
                        scale_abbrs.append(s['abbreviation'])

        cat_entry = {
            'key': key,
            'title': cat_name,
            'scales': scale_abbrs,
        }

        # Detect validity category
        if any(kw in cat_name.lower() for kw in validity_keywords):
            cat_entry['is_validity'] = True

        categories.append(cat_entry)

    return categories


def _merge_formatting_file(config: Dict[str, Any], project_root: Path) -> None:
    """
    Merge formatting values from an external formatting.json file.

    Loads the file referenced by config['files']['formatting'] and merges
    ALL keys into config['formatting']. The external file is the single
    source of truth for formatting/chart settings. Config-level values
    (if any) act as overrides — they take precedence over the file.
    Also merges top-level keys like 'validity_subcategories'.
    """
    fmt_rel = config.get('files', {}).get('formatting')
    if not fmt_rel:
        return

    fmt_path = project_root / fmt_rel
    if not fmt_path.exists():
        return

    with open(fmt_path, 'r') as f:
        fmt_data = json.load(f)

    formatting = config.setdefault('formatting', {})

    # Deep-merge all keys from the file into config['formatting'].
    # Config values override file values (so instrument-specific tweaks work).
    for key, value in fmt_data.items():
        if key == 'validity_subcategories':
            # This lives at config top-level, not under formatting
            continue
        existing = formatting.get(key)
        if existing is None or existing == {} or existing == [] or existing == '':
            # No override in config — use the file value
            formatting[key] = value
        elif isinstance(existing, dict) and isinstance(value, dict):
            # Dict merge: file values fill in gaps the config doesn't set
            for sub_key, sub_val in value.items():
                if sub_key not in existing or existing[sub_key] in (None, {}, [], ''):
                    existing[sub_key] = sub_val

    # Merge top-level keys (validity_subcategories)
    if 'validity_subcategories' in fmt_data and not config.get('validity_subcategories'):
        config['validity_subcategories'] = fmt_data['validity_subcategories']


def get_category_by_key(config: Dict[str, Any], key: str) -> Optional[Dict]:
    """Look up a category by its key."""
    for cat in config.get('categories', []):
        if cat['key'] == key:
            return cat
    return None


def get_validity_category(config: Dict[str, Any]) -> Optional[Dict]:
    """Get the validity category (marked with is_validity=true)."""
    for cat in config.get('categories', []):
        if cat.get('is_validity'):
            return cat
    return None


def get_substantive_categories(config: Dict[str, Any]) -> list:
    """Get all non-validity categories."""
    return [cat for cat in config.get('categories', []) if not cat.get('is_validity')]


# --- Interpretive range helpers ---

def get_elevated_labels(config: Dict[str, Any]) -> Set[str]:
    """Return the set of interpretive cutoff labels that count as elevated."""
    cutoffs = config.get('interpretive_cutoffs', [])
    has_explicit = any('elevated' in c for c in cutoffs)
    if has_explicit:
        return {c['label'] for c in cutoffs if c.get('elevated', False)}
    # Fallback: elevated if min_t >= 65
    return {c['label'] for c in cutoffs if c.get('min_t', 0) >= 65}


def get_normal_labels(config: Dict[str, Any]) -> Set[str]:
    """Return the set of interpretive cutoff labels that are NOT elevated."""
    cutoffs = config.get('interpretive_cutoffs', [])
    elevated = get_elevated_labels(config)
    return {c['label'] for c in cutoffs if c['label'] not in elevated}


def is_elevated(config: Dict[str, Any], range_label: str) -> bool:
    """Check if a given interpretive range label counts as elevated."""
    return range_label in get_elevated_labels(config)


def get_all_cutoff_labels(config: Dict[str, Any]) -> List[str]:
    """Return all interpretive cutoff labels in order from lowest to highest T-score range."""
    return [c['label'] for c in config.get('interpretive_cutoffs', [])]


def get_baseline_label(config: Dict[str, Any]) -> str:
    """Return the lowest/normal interpretive range label (first cutoff)."""
    cutoffs = config.get('interpretive_cutoffs', [])
    return cutoffs[0]['label'] if cutoffs else ''


def slugify_label(label: str) -> str:
    """Convert an interpretive range label to a CSS-safe slug."""
    return re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')


# --- Domain / hierarchy helpers ---

def get_hierarchy_levels(config: Dict[str, Any]) -> List[str]:
    """Get the ordered list of domain hierarchy level names from config."""
    fmt = config.get('formatting', {})
    explicit = fmt.get('hierarchy_levels')
    if explicit:
        return explicit
    domains = fmt.get('domain_definitions', {})
    levels = []
    for domain_def in domains.values():
        for key in domain_def:
            if key != 'color' and key not in levels:
                levels.append(key)
    return levels


def get_fallback_category(config: Dict[str, Any]) -> str:
    """Get the fallback category name for unassigned scales."""
    return config.get('formatting', {}).get('fallback_category', 'Other Scales')
