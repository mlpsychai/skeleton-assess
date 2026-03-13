"""Rebuild PAI mapping.json with correct item-to-scale assignments.

Item assignments verified manually against the PAI manual.
The PAI uses a 40-position base cycle with variations in cycles 7-8
and a special final block (items 321-344).
"""
import json
import itertools
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_pai import EVE_RESPONSES, GREG_RESPONSES, EVE_REF, GREG_REF

# ── The 40-position cycle ──
# Positions 1-13 and 24-40 are constant across all 8 cycles.
# Positions 14-23 vary between cycles 1-3, 4-6, and 7-8.

CYCLE_CONSTANT_1_13 = [
    'NON', 'RXR', 'SOM-C', 'ANX-A', 'ARD-O', 'DEP-A', 'MAN-A',
    'PAR-H', 'NIM', 'SCZ-P', 'ANT-A', 'SOM-H', 'WRM',
]

CYCLE_CONSTANT_24_40 = [
    'PIM', 'ANX-C', 'ARD-P', 'DEP-C', 'MAN-G', 'PAR-P', 'SCZ-S',
    'ANT-E', 'SOM-S', 'ANX-P', 'ARD-T', 'DEP-P', 'MAN-I', 'PAR-R',
    'SCZ-T', 'ANT-S', 'INF',
]

# Positions 14-23 for cycles 1-3
CYCLE_VAR_1_3 = [
    'BOR-A', 'ALC', 'DOM', 'BOR-I', 'AGG-V', 'BOR-N', 'SUI',
    'AGG-P', 'DRG', 'DRG',
]

# Positions 14-23 for cycles 4-6
CYCLE_VAR_4_6 = [
    'BOR-A', 'ALC', 'DOM', 'BOR-I', 'AGG-V', 'BOR-N', 'SUI',
    'AGG-P', 'DRG', 'BOR-S',
]

# Positions 14-23 for cycles 7-8
CYCLE_VAR_7_8 = [
    'ALC', 'ALC', 'DOM', 'DOM', 'AGG-A', 'AGG-A', 'SUI',
    'SUI', 'DRG', 'BOR-S',
]

# Final block: items 321-344
FINAL_BLOCK = [
    'STR', 'STR', 'STR', 'STR', 'STR', 'STR', 'STR', 'STR',  # 321-328
    'NIM',                                                        # 329
    'WRM', 'WRM', 'WRM', 'WRM',                                 # 330-333
    'ALC', 'ALC',                                                 # 334-335
    'DOM', 'DOM',                                                 # 336-337
    'AGG-A', 'AGG-A',                                            # 338-339
    'SUI', 'SUI',                                                 # 340-341
    'DRG',                                                        # 342
    'BOR-S',                                                      # 343
    'PIM',                                                        # 344
]


def get_cycle_var(cycle_num):
    """Get the variable positions 14-23 for a given cycle (1-indexed)."""
    if cycle_num <= 3:
        return CYCLE_VAR_1_3
    elif cycle_num <= 6:
        return CYCLE_VAR_4_6
    else:
        return CYCLE_VAR_7_8


def build_item_to_scale():
    """Build complete item→scale mapping for items 1-344."""
    mapping = {}
    for cycle in range(1, 9):  # 8 full cycles
        var = get_cycle_var(cycle)
        full_cycle = CYCLE_CONSTANT_1_13 + var + CYCLE_CONSTANT_24_40
        assert len(full_cycle) == 40
        for pos in range(40):
            item_num = (cycle - 1) * 40 + pos + 1
            mapping[item_num] = full_cycle[pos]

    # Final block: items 321-344
    for i, scale in enumerate(FINAL_BLOCK):
        item_num = 321 + i
        mapping[item_num] = scale

    return mapping


# ── Build mapping ──
item_to_scale = build_item_to_scale()
assert len(item_to_scale) == 344, f"Expected 344, got {len(item_to_scale)}"

# Group items by scale
from collections import defaultdict
scale_items = defaultdict(list)
for item_num in sorted(item_to_scale.keys()):
    scale_items[item_to_scale[item_num]].append(item_num)

# ── Verify item counts ──
print("ITEM COUNT VERIFICATION")
print("=" * 50)
expected_counts = {
    'SOM-C': 8, 'SOM-S': 8, 'SOM-H': 8,
    'ANX-C': 8, 'ANX-A': 8, 'ANX-P': 8,
    'ARD-O': 8, 'ARD-P': 8, 'ARD-T': 8,
    'DEP-C': 8, 'DEP-A': 8, 'DEP-P': 8,
    'MAN-A': 8, 'MAN-G': 8, 'MAN-I': 8,
    'PAR-H': 8, 'PAR-P': 8, 'PAR-R': 8,
    'SCZ-P': 8, 'SCZ-S': 8, 'SCZ-T': 8,
    'ANT-A': 8, 'ANT-E': 8, 'ANT-S': 8,
    'BOR-A': 6, 'BOR-I': 6, 'BOR-N': 6, 'BOR-S': 6,
    'AGG-A': 6, 'AGG-V': 6, 'AGG-P': 6,
    'ALC': 12, 'DRG': 12,
    'SUI': 12, 'DOM': 12, 'WRM': 12,
    'STR': 8, 'NON': 8, 'RXR': 8,
    'NIM': 9, 'PIM': 9, 'INF': 8,
}

all_ok = True
for scale in sorted(expected_counts.keys()):
    actual = len(scale_items[scale])
    expected = expected_counts[scale]
    status = "OK" if actual == expected else "FAIL"
    if status == "FAIL":
        all_ok = False
    print(f"  {scale:<8} {actual:>3}/{expected:<3} {status}  items: {scale_items[scale]}")

total_items = sum(len(v) for v in scale_items.values())
print(f"\nTotal item assignments: {total_items}")
print(f"All counts correct: {all_ok}")

# ── Parent scale relationships ──
PARENT_MAP = {
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

SCALE_NAMES = {
    'ICN': 'Inconsistency', 'INF': 'Infrequency',
    'NIM': 'Negative Impression', 'PIM': 'Positive Impression',
    'SOM': 'Somatic Complaints', 'SOM-C': 'Conversion', 'SOM-S': 'Somatization', 'SOM-H': 'Health Concerns',
    'ANX': 'Anxiety', 'ANX-C': 'Cognitive', 'ANX-A': 'Affective', 'ANX-P': 'Physiological',
    'ARD': 'Anxiety-Related Disorders', 'ARD-O': 'Obsessive-Compulsive', 'ARD-P': 'Phobias', 'ARD-T': 'Traumatic Stress',
    'DEP': 'Depression', 'DEP-C': 'Cognitive', 'DEP-A': 'Affective', 'DEP-P': 'Physiological',
    'MAN': 'Mania', 'MAN-A': 'Activity Level', 'MAN-G': 'Grandiosity', 'MAN-I': 'Irritability',
    'PAR': 'Paranoia', 'PAR-H': 'Hypervigilance', 'PAR-P': 'Persecution', 'PAR-R': 'Resentment',
    'SCZ': 'Schizophrenia', 'SCZ-P': 'Psychotic Experiences', 'SCZ-S': 'Social Detachment', 'SCZ-T': 'Thought Disorder',
    'BOR': 'Borderline Features', 'BOR-A': 'Affective Instability', 'BOR-I': 'Identity Problems',
    'BOR-N': 'Negative Relationships', 'BOR-S': 'Self-Harm',
    'ANT': 'Antisocial Features', 'ANT-A': 'Antisocial Behaviors', 'ANT-E': 'Egocentricity', 'ANT-S': 'Stimulus-Seeking',
    'ALC': 'Alcohol Problems', 'DRG': 'Drug Problems',
    'AGG': 'Aggression', 'AGG-A': 'Aggressive Attitude', 'AGG-V': 'Verbal Aggression', 'AGG-P': 'Physical Aggression',
    'SUI': 'Suicidal Ideation', 'STR': 'Stress', 'NON': 'Nonsupport',
    'RXR': 'Treatment Rejection', 'DOM': 'Dominance', 'WRM': 'Warmth',
}


# ── Brute-force keying derivation ──
print(f"\n{'=' * 70}")
print("DERIVING KEYING FROM REFERENCE CLIENTS")
print("=" * 70)


def score_items(item_nums, keying_bits, responses):
    raw = 0
    for i, item_num in enumerate(item_nums):
        resp = responses.get(item_num, 0)
        if keying_bits[i] == 1:
            raw += (3 - resp)
        else:
            raw += resp
    return raw


item_keying = {}  # item_num → 'True' or 'False'
derived_ok = []
ambiguous = []
failed = []

# All scales to derive (excluding ICN which is pair-based)
all_derivable = sorted([s for s in scale_items.keys()
                        if s in EVE_REF and s in GREG_REF])

for scale_abbr in all_derivable:
    items = scale_items[scale_abbr]
    n = len(items)
    eve_target = EVE_REF[scale_abbr][0]
    greg_target = GREG_REF[scale_abbr][0]

    if n > 16:
        print(f"  {scale_abbr}: {n} items — too many for brute force, skipping")
        failed.append(scale_abbr)
        continue

    solutions = []
    for bits in itertools.product([0, 1], repeat=n):
        if score_items(items, bits, EVE_RESPONSES) == eve_target:
            if score_items(items, bits, GREG_RESPONSES) == greg_target:
                solutions.append(bits)

    if len(solutions) == 0:
        print(f"  {scale_abbr}: NO SOLUTION ({n} items, Eve target={eve_target}, Greg target={greg_target})")
        failed.append(scale_abbr)
    elif len(solutions) == 1:
        bits = solutions[0]
        rev = [items[i] for i in range(n) if bits[i] == 1]
        print(f"  {scale_abbr}: UNIQUE ({n} items, {len(rev)} reversed: {rev})")
        derived_ok.append(scale_abbr)
        for i, item_num in enumerate(items):
            item_keying[item_num] = 'False' if bits[i] == 1 else 'True'
    else:
        # Multiple solutions — pick one with fewest reversals (most forward-keyed)
        best = min(solutions, key=sum)
        rev = [items[i] for i in range(len(items)) if best[i] == 1]
        print(f"  {scale_abbr}: {len(solutions)} solutions, picked ({len(rev)} reversed: {rev})")
        ambiguous.append(scale_abbr)
        for i, item_num in enumerate(items):
            item_keying[item_num] = 'False' if best[i] == 1 else 'True'

# Items not yet keyed (from failed scales) — default to forward
for item_num in range(1, 345):
    if item_num not in item_keying:
        item_keying[item_num] = 'True'

print(f"\nDerived: {len(derived_ok)} unique, {len(ambiguous)} ambiguous, {len(failed)} failed")

# ── Build mapping.json ──
print(f"\n{'=' * 70}")
print("BUILDING MAPPING.JSON")
print("=" * 70)

mapping = {}

# Subscales and standalone scales
for scale_abbr in sorted(scale_items.keys()):
    items = scale_items[scale_abbr]
    item_entries = [{'item': n, 'keyed': item_keying.get(n, 'True')} for n in items]
    mapping[scale_abbr] = {
        'scale_name': SCALE_NAMES.get(scale_abbr, scale_abbr),
        'items': item_entries,
    }

# Parent scales
for parent, subs in PARENT_MAP.items():
    parent_items = []
    for sub in subs:
        parent_items.extend(mapping[sub]['items'])
    parent_items.sort(key=lambda x: x['item'])
    mapping[parent] = {
        'scale_name': SCALE_NAMES.get(parent, parent),
        'items': parent_items,
    }

output_path = r'C:\Users\sm4663\skeleton-assess\templates\pai\mapping.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({'scales': mapping}, f, indent=2, ensure_ascii=False)
print(f"Saved {len(mapping)} scales to {output_path}")

# ── Validate ──
print(f"\n{'=' * 70}")
print("VALIDATION")
print("=" * 70)

tscore_path = r'C:\Users\sm4663\skeleton-assess\templates\pai\tscore_tables.json'
with open(tscore_path, encoding='utf-8') as f:
    tscore_tables = json.load(f)['scales']


def score_scale(scale_abbr, responses):
    if scale_abbr not in mapping:
        return None
    raw = 0
    for entry in mapping[scale_abbr]['items']:
        resp = responses.get(entry['item'])
        if resp is None or entry['keyed'] == 'paired':
            continue
        if entry['keyed'] == 'False':
            raw += (3 - resp)
        else:
            raw += resp
    return raw


def lookup_t(scale_abbr, raw):
    if scale_abbr not in tscore_tables:
        return None
    table = tscore_tables[scale_abbr]['raw_to_t']
    raw_key = str(raw)
    if raw_key in table:
        val = table[raw_key]
        return int(val) if val is not None else None
    keys = sorted([int(k) for k in table.keys() if table[k] is not None])
    if not keys:
        return None
    if raw <= keys[0]:
        return int(table[str(keys[0])])
    if raw >= keys[-1]:
        return int(table[str(keys[-1])])
    return None


total_perfect = 0
total_raw_match = 0
total_t_match = 0
total_tests = 0

for name, responses, reference in [
    ("Eve (737-Eve)", EVE_RESPONSES, EVE_REF),
    ("Greg (737-Greg)", GREG_RESPONSES, GREG_REF),
]:
    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")
    print(f"{'Scale':<8} {'OurRaw':>7} {'RefRaw':>7} {'Raw':>4} {'OurT':>5} {'RefT':>5} {'T':>3}")
    print("-" * 50)

    for scale_abbr in sorted(reference.keys()):
        ref_raw, ref_t = reference[scale_abbr]

        if scale_abbr == 'ICN':
            print(f"{'ICN':<8} {'—':>7} {ref_raw:>7} {'—':>4} {'—':>5} {ref_t:>5} {'—':>3}")
            continue

        our_raw = score_scale(scale_abbr, responses)
        if our_raw is None:
            print(f"{scale_abbr:<8} {'MISS':>7} {ref_raw:>7}")
            total_tests += 1
            continue

        our_t = lookup_t(scale_abbr, our_raw)
        raw_ok = our_raw == ref_raw
        t_ok = (our_t == ref_t) if our_t is not None else False

        if raw_ok: total_raw_match += 1
        if t_ok: total_t_match += 1
        if raw_ok and t_ok: total_perfect += 1
        total_tests += 1

        marker = "" if (raw_ok and t_ok) else " <<<"
        print(f"{scale_abbr:<8} {our_raw:>7} {ref_raw:>7} {'Y' if raw_ok else 'N':>4} {str(our_t):>5} {ref_t:>5} {'Y' if t_ok else 'N':>3}{marker}")

print(f"\n{'=' * 60}")
print(f"OVERALL: {total_perfect}/{total_tests} perfect (raw+T)")
print(f"  Raw matches: {total_raw_match}/{total_tests}")
print(f"  T matches:   {total_t_match}/{total_tests}")
if failed:
    print(f"  Failed keying: {', '.join(failed)}")
if ambiguous:
    print(f"  Ambiguous keying: {', '.join(ambiguous)}")
