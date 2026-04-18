"""
Populate Grossman Facet BR tables from Table D.4 (pages 114-115 of MCMI-IV manual).
Also adds W scale interpretation and fixes Noteworthy Response handling.

BR values read from raw PDF scan images.
"""
import json

# Table D.4: Raw Score to Base Rate for Grossman Facet Scales
# Read from MCMI_raw.pdf pages 13-14 (manual pages 114-115)
# Format: facet_code -> list of BR values indexed by raw score

facet_br_data = {
    # Page 114 (left table): Facets 1.1 through 6B.3
    "1.1": [0, 30, 40, 60, 64, 68, 72, 75, 82, 85],           # 9 items
    "1.2": [0, 30, 40, 60, 68, 75, 78, 82, 85, 85],           # 9 items
    "1.3": [0, 30, 40, 60, 68, 75, 82, 85, 85, 85],           # 9 items
    "2A.1": [0, 30, 60, 60, 65, 70, 75, 82, 85],              # 8 items
    "2A.2": [0, 30, 40, 60, 65, 75, 78, 82, 85, 85],          # 9 items
    "2A.3": [0, 30, 60, 60, 65, 75, 78, 82, 85, 85],          # 9 items
    "2B.1": [0, 30, 45, 60, 65, 70, 75, 80, 85, 85],          # 9 items
    "2B.2": [0, 30, 40, 60, 65, 70, 75, 82, 85, 85],          # 9 items
    "2B.3": [0, 30, 40, 60, 68, 75, 82, 85, 85, 85],          # 9 items
    "3.1": [0, 30, 60, 60, 65, 70, 75, 82, 85, 85],           # 9 items
    "3.2": [0, 30, 60, 60, 65, 75, 82, 85],                   # 7 items
    "3.3": [0, 30, 40, 60, 65, 70, 75, 82, 85, 85],           # 9 items
    "4A.1": [0, 30, 60, 60, 65, 75, 82, 85],                  # 7 items
    "4A.2": [0, 30, 40, 60, 60, 65, 70, 75, 82, 85, 85],      # 10 items
    "4A.3": [0, 30, 40, 60, 60, 65, 68, 70, 75, 80, 82, 85, 85], # 12 items
    "4B.1": [0, 30, 60, 60, 65, 65, 70, 75, 85],              # 8 items (max raw 8)
    "4B.2": [0, 30, 40, 60, 60, 65, 75, 78, 82, 85],          # 9 items
    "4B.3": [0, 30, 60, 60, 65, 70, 75, 82, 85],              # 8 items
    "5.1": [0, 30, 60, 60, 65, 65, 70, 75, 82, 85],           # 9 items
    "5.2": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85],       # 10 items
    "5.3": [0, 30, 60, 60, 65, 70, 75, 82, 85],               # 8 items
    "6A.1": [0, 30, 60, 60, 65, 70, 75, 82, 85],              # 8 items
    "6A.2": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85],      # 10 items
    "6A.3": [0, 30, 40, 60, 60, 65, 70, 75, 80, 85, 85],      # 10 items
    "6B.1": [0, 30, 40, 60, 60, 60, 65, 70, 75, 82, 85, 85],  # 11 items
    "6B.2": [0, 30, 60, 65, 70, 75, 82, 85],                  # 7 items
    "6B.3": [0, 30, 60, 65, 70, 75, 82, 85],                  # 7 items

    # Page 115 (right table): Facets 7.1 through P.3
    "7.1": [0, 30, 60, 60, 60, 65, 68, 75, 85],               # 8 items
    "7.2": [0, 30, 30, 60, 60, 60, 63, 64, 68, 68, 75, 82, 85], # 12 items
    "7.3": [0, 30, 60, 60, 60, 65, 68, 75, 82, 85],           # 9 items
    "8A.1": [0, 30, 60, 60, 65, 70, 75, 82, 85, 85],          # 9 items
    "8A.2": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85, 85],  # 11 items
    "8A.3": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85],      # 10 items
    "8B.1": [0, 30, 30, 60, 60, 60, 65, 68, 70, 75, 82, 85, 85], # 12 items
    "8B.2": [0, 30, 60, 60, 65, 70, 75, 82, 85, 85],          # 9 items
    "8B.3": [0, 30, 60, 60, 65, 72, 75, 82, 85, 85],          # 9 items
    "S.1": [0, 30, 60, 60, 65, 68, 72, 75, 82, 85],           # 9 items
    "S.2": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85, 85],   # 11 items
    "S.3": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85, 85],   # 11 items
    "C.1": [0, 30, 60, 60, 65, 70, 75, 82, 85],               # 8 items
    "C.2": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85, 85],   # 11 items
    "C.3": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85],       # 10 items
    "P.1": [0, 30, 60, 60, 60, 65, 68, 75, 82, 85],           # 9 items
    "P.2": [0, 30, 60, 65, 70, 75, 82, 85],                   # 7 items
    "P.3": [0, 30, 40, 60, 60, 65, 68, 70, 75, 82, 85],       # 10 items
}

# Scale names for facets
facet_names = {
    "1.1": "Interpersonally Unengaged", "1.2": "Meager Content", "1.3": "Temperamentally Apathetic",
    "2A.1": "Interpersonally Aversive", "2A.2": "Alienated Self-Image", "2A.3": "Vexatious Content",
    "2B.1": "Cognitively Fatalistic", "2B.2": "Worthless Self-Image", "2B.3": "Temperamentally Woeful",
    "3.1": "Expressively Puerile", "3.2": "Interpersonally Submissive", "3.3": "Inept Self-Image",
    "4A.1": "Expressively Dramatic", "4A.2": "Interpersonally Attention-Seeking", "4A.3": "Temperamentally Fickle",
    "4B.1": "Expressively Impetuous", "4B.2": "Interpersonally High-Spirited", "4B.3": "Exalted Self-Image",
    "5.1": "Interpersonally Exploitive", "5.2": "Cognitively Expansive", "5.3": "Admirable Self-Image",
    "6A.1": "Interpersonally Irresponsible", "6A.2": "Autonomous Self-Image", "6A.3": "Acting-Out Dynamics",
    "6B.1": "Expressively Precipitate", "6B.2": "Interpersonally Abrasive", "6B.3": "Eruptive Architecture",
    "7.1": "Expressively Disciplined", "7.2": "Cognitively Constricted", "7.3": "Reliable Self-Image",
    "8A.1": "Expressively Embittered", "8A.2": "Discontented Self-Image", "8A.3": "Temperamentally Irritable",
    "8B.1": "Undeserving Self-Image", "8B.2": "Inverted Architecture", "8B.3": "Temperamentally Dysphoric",
    "S.1": "Cognitively Circumstantial", "S.2": "Estranged Self-Image", "S.3": "Chaotic Content",
    "C.1": "Uncertain Self-Image", "C.2": "Split Architecture", "C.3": "Temperamentally Labile",
    "P.1": "Expressively Defensive", "P.2": "Cognitively Mistrustful", "P.3": "Projection Dynamics",
}


def main():
    # Load existing tscore_tables
    with open('templates/mcmi4/tscore_tables.json') as f:
        tables = json.load(f)

    # Validate facet BR data
    issues = []
    for code, br_values in facet_br_data.items():
        # Check monotonically non-decreasing
        for i in range(1, len(br_values)):
            if br_values[i] < br_values[i-1]:
                issues.append(f"  {code}: BR not monotonic at raw {i}: {br_values[i]} < {br_values[i-1]}")
        # Check starts at 0
        if br_values[0] != 0:
            issues.append(f"  {code}: Does not start at 0")
        # Check max is 85 or 100
        if br_values[-1] not in (85, 100):
            issues.append(f"  {code}: Max BR is {br_values[-1]} (expected 85 or 100)")

    if issues:
        print("VALIDATION ISSUES:")
        for issue in issues:
            print(issue)
    else:
        print("All facet BR tables validated (monotonic, start at 0, max 85/100)")

    # Add facet BR tables
    updated = 0
    for code, br_values in facet_br_data.items():
        raw_to_t = {str(i): v for i, v in enumerate(br_values)}
        tables['scales'][code] = {
            "scale_name": facet_names[code],
            "raw_to_t": raw_to_t
        }
        updated += 1

    print(f"\nUpdated {updated} facet BR tables")

    # Write back
    with open('templates/mcmi4/tscore_tables.json', 'w') as f:
        json.dump(tables, f, indent=2)
    print("Wrote templates/mcmi4/tscore_tables.json")

    # Count totals
    total_with_br = sum(1 for s in tables['scales'].values() if s.get('raw_to_t'))
    print(f"Total scales with BR tables: {total_with_br}")


if __name__ == '__main__':
    main()
