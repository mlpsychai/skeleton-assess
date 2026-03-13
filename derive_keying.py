"""Derive correct PAI item keying by brute-forcing against two reference clients."""
import json
import itertools
import sys
import os

# ── Load responses and references from validate_pai.py ──
# (importing to avoid duplication)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_pai import EVE_RESPONSES, GREG_RESPONSES, EVE_REF, GREG_REF

# Load mapping
with open(r'C:\Users\sm4663\skeleton-assess\templates\pai\mapping.json', encoding='utf-8') as f:
    full_mapping = json.load(f)
mapping = full_mapping['scales']


def score_with_keying(items, keying_bits, responses):
    """Score items with a given keying pattern (0=forward, 1=reverse)."""
    raw = 0
    for i, entry in enumerate(items):
        item_num = entry['item']
        resp = responses.get(item_num, 0)
        if keying_bits[i] == 1:  # reverse
            raw += (3 - resp)
        else:  # forward
            raw += resp
    return raw


# Subscales to derive (8 items each, 256 combinations)
subscales_8 = [
    'SOM-C', 'SOM-S', 'SOM-H', 'ANX-C', 'ANX-A', 'ANX-P',
    'ARD-O', 'ARD-P', 'ARD-T', 'DEP-C', 'DEP-A', 'DEP-P',
    'MAN-A', 'MAN-G', 'MAN-I', 'PAR-H', 'PAR-P', 'PAR-R',
    'SCZ-P', 'SCZ-S', 'SCZ-T', 'BOR-A', 'BOR-I', 'BOR-N', 'BOR-S',
    'ANT-A', 'ANT-E', 'ANT-S',
]

# Scales with different item counts
other_scales = ['STR', 'NON', 'RXR', 'DOM', 'WRM', 'SUI', 'INF', 'NIM', 'PIM']
# AGG subscales (variable items per the mapping)
agg_subscales = ['AGG-A', 'AGG-V', 'AGG-P']
# ALC and DRG have more items
alc_drg = ['ALC', 'DRG']

all_scales = subscales_8 + other_scales + agg_subscales + alc_drg

print("Deriving correct keying for PAI items...")
print(f"Using Eve (737-Eve) and Greg (737-Greg) as reference clients\n")

results = {}
ambiguous = []

for scale_abbr in all_scales:
    if scale_abbr not in mapping:
        print(f"  {scale_abbr}: NOT IN MAPPING — skipping")
        continue

    items = mapping[scale_abbr]['items']
    n_items = len(items)

    eve_ref_raw = EVE_REF.get(scale_abbr, (None, None))[0]
    greg_ref_raw = GREG_REF.get(scale_abbr, (None, None))[0]

    if eve_ref_raw is None or greg_ref_raw is None:
        print(f"  {scale_abbr}: no reference data — skipping")
        continue

    if n_items > 16:
        print(f"  {scale_abbr}: {n_items} items — too many for brute force (2^{n_items}), skipping")
        continue

    # Try all 2^n keying combinations
    found = []
    for bits in itertools.product([0, 1], repeat=n_items):
        eve_raw = score_with_keying(items, bits, EVE_RESPONSES)
        greg_raw = score_with_keying(items, bits, GREG_RESPONSES)

        if eve_raw == eve_ref_raw and greg_raw == greg_ref_raw:
            found.append(bits)

    if len(found) == 0:
        print(f"  {scale_abbr}: NO keying combination matches both clients!")
        ambiguous.append(scale_abbr)
    elif len(found) == 1:
        keying = found[0]
        results[scale_abbr] = keying
        changes = []
        for i, entry in enumerate(items):
            old_key = entry.get('keyed', 'True')
            new_key = 'False' if keying[i] == 1 else 'True'
            if old_key != new_key:
                changes.append(f"item {entry['item']}: {old_key}->{new_key}")
        if changes:
            print(f"  {scale_abbr}: UNIQUE solution, {len(changes)} keying changes: {', '.join(changes)}")
        else:
            print(f"  {scale_abbr}: UNIQUE solution, keying already correct!")
    else:
        print(f"  {scale_abbr}: {len(found)} possible solutions (ambiguous)")
        # Pick the one closest to current mapping
        results[scale_abbr] = found[0]
        ambiguous.append(scale_abbr)


# Apply corrections to mapping
print(f"\n{'=' * 60}")
print(f"Applying {len(results)} keying corrections to mapping.json...")

corrections = 0
for scale_abbr, keying in results.items():
    items = mapping[scale_abbr]['items']
    for i, entry in enumerate(items):
        new_key = 'False' if keying[i] == 1 else 'True'
        if entry.get('keyed') != new_key:
            entry['keyed'] = new_key
            corrections += 1

# Also update parent scales to match their subscale items
parent_map = {
    'SOM': ['SOM-C', 'SOM-S', 'SOM-H'],
    'ANX': ['ANX-C', 'ANX-A', 'ANX-P'],
    'ARD': ['ARD-O', 'ARD-P', 'ARD-T'],
    'DEP': ['DEP-C', 'DEP-A', 'DEP-P'],
    'MAN': ['MAN-A', 'MAN-G', 'MAN-I'],
    'PAR': ['PAR-H', 'PAR-P', 'PAR-R'],
    'SCZ': ['SCZ-P', 'SCZ-S', 'SCZ-T'],
    'BOR': ['BOR-A', 'BOR-I', 'BOR-N', 'BOR-S'],
    'ANT': ['ANT-A', 'ANT-E', 'ANT-S'],
    'AGG': ['AGG-A', 'AGG-V', 'AGG-P'],
}

# Build item->keying lookup from subscales
item_keying = {}
for scale_abbr, keying in results.items():
    items = mapping[scale_abbr]['items']
    for i, entry in enumerate(items):
        item_keying[entry['item']] = 'False' if keying[i] == 1 else 'True'

# Apply to parent scales
for parent, subs in parent_map.items():
    if parent in mapping:
        for entry in mapping[parent]['items']:
            if entry['item'] in item_keying:
                new_key = item_keying[entry['item']]
                if entry.get('keyed') != new_key:
                    entry['keyed'] = new_key
                    corrections += 1

print(f"Total corrections: {corrections}")

# Save updated mapping
output_path = r'C:\Users\sm4663\skeleton-assess\templates\pai\mapping.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(full_mapping, f, indent=2, ensure_ascii=False)
print(f"Saved to {output_path}")

if ambiguous:
    print(f"\nAMBIGUOUS scales (no unique solution or no solution): {', '.join(ambiguous)}")

print("\nDone. Re-run validate_pai.py to check results.")
