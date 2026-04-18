"""
Build MCMI-IV mapping.json and tscore_tables.json from extracted manual data.

Parses instrument_docs/MCMI_IV_extracted_data.md and generates:
  - templates/mcmi4/mapping.json   (item-to-scale keying with weights)
  - templates/mcmi4/tscore_tables.json  (raw-to-BR conversion tables)
"""

import json
import re


def parse_items(item_str):
    """Parse comma-separated item numbers from a string."""
    if not item_str or not item_str.strip():
        return []
    return [int(x.strip()) for x in item_str.split(',') if x.strip()]


def build_weighted_scale(scale_name, proto_true_str, nonp_true_str, nonp_false_str):
    """Build items list for a weighted scale (personality/clinical).

    MCMI-IV scoring:
      - Prototypal True items: keyed True, weight 2
      - Nonprototypal True items: keyed True, weight 1
      - Nonprototypal False items: keyed False, weight 1
    """
    items = []

    for item_num in parse_items(proto_true_str):
        items.append({"item": item_num, "scoring_weights": {"True": 2, "False": 0}})

    for item_num in parse_items(nonp_true_str):
        items.append({"item": item_num, "scoring_weights": {"True": 1, "False": 0}})

    for item_num in parse_items(nonp_false_str):
        items.append({"item": item_num, "scoring_weights": {"True": 0, "False": 1}})

    # Sort by item number
    items.sort(key=lambda x: x['item'])
    return items


def build_keyed_scale(true_items_str, false_items_str):
    """Build items list for a simple keyed scale (validity, facets, noteworthy)."""
    items = []

    for item_num in parse_items(true_items_str):
        items.append({"item": item_num, "keyed": "True"})

    for item_num in parse_items(false_items_str):
        items.append({"item": item_num, "keyed": "False"})

    items.sort(key=lambda x: x['item'])
    return items


def parse_w_pairs(pairs_str):
    """Parse W (Inconsistency) item pairs from format like (22-170),(125-143),..."""
    pairs = []
    for match in re.finditer(r'\((\d+)-(\d+)\)', pairs_str):
        pairs.append({"item1": int(match.group(1)), "item2": int(match.group(2))})
    return pairs


def build_mapping():
    """Build the complete mapping.json structure."""
    scales = {}

    # ─── Modifier Indices ───

    # V (Invalidity): 3 items, all True=1
    scales["V"] = {
        "scale_name": "Validity",
        "items": build_keyed_scale("49,98,160", ""),
        "item_count": 3
    }

    # W (Inconsistency): 25 item pairs
    w_pairs_str = "(22-170),(125-143),(47-157),(40-181),(81-116),(85-126),(76-150),(25-94),(44-121),(39-59),(17-184),(33-89),(78-164),(38-171),(74-115),(46-154),(26-99),(20-174),(32-122),(13-112),(55-110),(173-194),(95-127),(60-162),(15-149)"
    scales["W"] = {
        "scale_name": "Inconsistency",
        "scale_type": "item_pairs",
        "inconsistency_pairs": parse_w_pairs(w_pairs_str),
        "item_count": 25
    }

    # X (Disclosure): 121 items, all True=1
    x_items = "2,4,5,6,8,9,10,11,12,15,16,17,19,20,21,22,23,24,26,29,30,32,35,36,37,38,39,42,43,46,48,50,51,52,53,54,59,60,63,65,66,67,70,71,72,73,74,75,77,79,82,83,84,85,87,88,90,92,93,96,97,99,100,103,105,106,109,111,112,115,117,119,120,122,126,128,129,132,133,135,137,139,140,141,142,145,147,149,152,154,155,156,158,159,162,164,166,167,168,169,170,171,172,173,174,175,178,179,180,183,184,185,187,188,189,190,191,192,193,194,195"
    scales["X"] = {
        "scale_name": "Disclosure",
        "items": build_keyed_scale(x_items, ""),
        "item_count": 121
    }

    # Y (Desirability): 17 True + 7 False = 24 items
    scales["Y"] = {
        "scale_name": "Desirability",
        "items": build_keyed_scale(
            "2,3,8,20,30,46,67,73,75,84,154,155,158,173,174,185,188",
            "65,71,90,99,159,162,187"
        ),
        "item_count": 24
    }

    # Z (Debasement): 30 items, all True=1
    scales["Z"] = {
        "scale_name": "Debasement",
        "items": build_keyed_scale(
            "1,14,16,17,18,22,28,31,32,34,37,39,41,44,51,64,74,78,80,101,107,109,112,113,120,151,164,170,178,193",
            ""
        ),
        "item_count": 30
    }

    # ─── Clinical Personality Pattern Scales (weighted) ───

    personality_data = [
        ("1", "Schizoid", 15, "6,15,43,90,119,139,149,180", "17,24,70,92,190", "30,154"),
        ("2A", "Avoidant", 18, "5,12,26,99,135,195", "23,24,52,92,93,112,178,184,193", "46,67,154"),
        ("2B", "Melancholic", 19, "23,51,71,93,111,169,175,184,193", "17,22,39,59,70,90,126,170,178", "53"),
        ("3", "Dependent", 14, "4,42,60,77,109,133,162,173,194", "5,23,72,175", "67"),
        ("4A", "Histrionic", 17, "10,30,46,84,117,154,171", "8,75,155", "6,15,24,26,139,178,195"),
        ("4B", "Turbulent", 17, "8,20,53,75,129,155,174,185", "30,46,67,84,142,154", "26,120,178"),
        ("5", "Narcissistic", 16, "29,38,54,67,87,106,132,142,159,189", "10,19,83,117,171,191", ""),
        ("6A", "Antisocial", 14, "11,19,65,83,147,183,191", "36,38,105,152,159", "48,158"),
        ("6B", "Sadistic", 14, "9,50,66,97,103,115,141,152", "11,16,21,74,145,172", ""),
        ("7", "Compulsive", 13, "2,35,48,63,73,128,140,158,179,188", "", "83,147,152"),
        ("8A", "Negativistic", 18, "17,32,82,96,122,137,167,187", "21,37,52,79,88,97,100,168,172,184", ""),
        ("8B", "Masochistic", 18, "39,59,85,100,126,166,192", "4,12,23,70,93,156,164,178,195", "20,75"),
    ]

    for abbr, name, num_items, proto_t, nonp_t, nonp_f in personality_data:
        items = build_weighted_scale(name, proto_t, nonp_t, nonp_f)
        scales[abbr] = {
            "scale_name": name,
            "items": items,
            "item_count": num_items
        }

    # ─── Severe Personality Pathology Scales (weighted) ───

    severe_personality_data = [
        ("S", "Schizotypal", 21, "13,24,44,92,112,156,165,190", "18,58,70,90,93,121,123,126,148,163,167,172,195", ""),
        ("C", "Borderline", 20, "16,18,37,70,134,164,178", "4,59,80,82,93,100,111,126,137,156,166,192,193", ""),
        ("P", "Paranoid", 16, "21,52,79,88,104,136,153,172", "13,24,68,96,148,167,180,195", ""),
    ]

    for abbr, name, num_items, proto_t, nonp_t, nonp_f in severe_personality_data:
        items = build_weighted_scale(name, proto_t, nonp_t, nonp_f)
        scales[abbr] = {
            "scale_name": name,
            "items": items,
            "item_count": num_items
        }

    # ─── Clinical Syndrome Scales (weighted) ───

    clinical_data = [
        ("A", "Generalized Anxiety", 13, "31,72,89,113,123,143", "33,41,44,51,91,108,109", ""),
        ("H", "Somatic Symptom", 10, "7,28,41,120,146", "1,57,113,118", "20"),
        ("N", "Bipolar Spectrum", 13, "3,27,56,108,163,177", "37,50,54,82,83,105,155", ""),
        ("D", "Persistent Depression", 21, "14,34,64,118,151,170", "17,28,39,51,71,77,85,93,101,111,114,120,178,193", "75"),
        ("B", "Alcohol Use", 8, "25,45,94,130,161", "65,83,126", ""),
        ("T", "Drug Use", 11, "36,61,81,105,116,124,144", "11,65,152", "158"),
        ("R", "Post-Traumatic Stress", 14, "62,76,91,125,150", "44,47,57,74,89,110,113,143,157", ""),
    ]

    for abbr, name, num_items, proto_t, nonp_t, nonp_f in clinical_data:
        items = build_weighted_scale(name, proto_t, nonp_t, nonp_f)
        scales[abbr] = {
            "scale_name": name,
            "items": items,
            "item_count": num_items
        }

    # ─── Severe Clinical Syndrome Scales (weighted) ───

    severe_clinical_data = [
        ("SS", "Schizophrenic Spectrum", 21, "33,58,80,121,131,138", "18,24,52,82,89,92,95,104,123,136,148,156,165,172,182", ""),
        ("CC", "Major Depression", 17, "1,22,57,78,101,107,114", "28,41,59,64,70,80,111,118,120,170", ""),
        ("PP", "Delusional", 14, "68,95,127,148,182", "13,54,79,88,112,121,136,172,189", ""),
    ]

    for abbr, name, num_items, proto_t, nonp_t, nonp_f in severe_clinical_data:
        items = build_weighted_scale(name, proto_t, nonp_t, nonp_f)
        scales[abbr] = {
            "scale_name": name,
            "items": items,
            "item_count": num_items
        }

    # ─── Grossman Facet Scales (simple keyed, weight 1) ───

    facet_data = [
        ("1.1", "Interpersonally Unengaged", "12,15,24,104,149,180,190", "154,185"),
        ("1.2", "Meager Content", "26,99,139,175,178,195", "30,46,67"),
        ("1.3", "Temperamentally Apathetic", "6,17,43,70,90,92,111,118,119", ""),
        ("2A.1", "Interpersonally Aversive", "15,26,99,139", "30,46,84,154"),
        ("2A.2", "Alienated Self-Image", "23,58,111,135,156,178,192,193", "67"),
        ("2A.3", "Vexatious Content", "5,12,24,52,92,93,112,184,195", ""),
        ("2B.1", "Cognitively Fatalistic", "17,23,33,51,52,71,89,126,184", ""),
        ("2B.2", "Worthless Self-Image", "39,59,93,112,169,175,178,192,195", ""),
        ("2B.3", "Temperamentally Woeful", "22,70,90,101,107,111,170,193", "53"),
        ("3.1", "Expressively Puerile", "4,5,23,51,72,99,109,135,184", ""),
        ("3.2", "Interpersonally Submissive", "26,60,162,169,173,194", "185"),
        ("3.3", "Inept Self-Image", "42,77,85,93,133,151,175", "53,67"),
        ("4A.1", "Expressively Dramatic", "10,38,83,117,132,142,171", ""),
        ("4A.2", "Interpersonally Attention-Seeking", "30,46,84,154", "6,15,24,26,139,195"),
        ("4A.3", "Temperamentally Fickle", "8,20,27,53,67,75,155,174,185", "135,170,178"),
        ("4B.1", "Expressively Impetuous", "8,20,53,75,129,155,174,185", ""),
        ("4B.2", "Interpersonally High-Spirited", "10,30,46,84,117,154", "5,26,149"),
        ("4B.3", "Exalted Self-Image", "67,142", "14,93,120,156,175,178"),
        ("5.1", "Interpersonally Exploitive", "10,19,38,83,117,132,159,171,183", ""),
        ("5.2", "Cognitively Expansive", "8,67,75,142,154,155,174,185", "93,178"),
        ("5.3", "Admirable Self-Image", "29,54,79,87,106,180,189,191", ""),
        ("6A.1", "Interpersonally Irresponsible", "10,38,83,103,159,171,183", "188"),
        ("6A.2", "Autonomous Self-Image", "11,19,147,152,153,168,191", "48,73,158"),
        ("6A.3", "Acting-Out Dynamics", "25,36,61,65,85,105,126,130,144", "63"),
        ("6B.1", "Expressively Precipitate", "9,11,65,66,88,103,152,153,159,172,191", ""),
        ("6B.2", "Interpersonally Abrasive", "19,21,50,97,141,166,187", ""),
        ("6B.3", "Eruptive Architecture", "16,37,74,115,137,145,168", ""),
        ("7.1", "Expressively Disciplined", "2,20,35,63,174,188", "85,118"),
        ("7.2", "Cognitively Constricted", "23,44,51,52,99,128,131,135,137,140,169,179", ""),
        ("7.3", "Reliable Self-Image", "48,73,158", "19,83,147,152,183,191"),
        ("8A.1", "Expressively Embittered", "21,32,79,88,96,100,122,167,172", ""),
        ("8A.2", "Discontented Self-Image", "12,17,24,34,39,51,52,59,153,184", "75"),
        ("8A.3", "Temperamentally Irritable", "9,37,74,82,97,115,137,145,168,187", ""),
        ("8B.1", "Undeserving Self-Image", "4,12,23,39,52,59,70,93,164,178,192,195", ""),
        ("8B.2", "Inverted Architecture", "17,40,85,100,126,156,166,167,184", ""),
        ("8B.3", "Temperamentally Dysphoric", "92,107,170", "20,53,67,75,154,155"),
        ("S.1", "Cognitively Circumstantial", "18,33,44,89,92,121,123,131,163", ""),
        ("S.2", "Estranged Self-Image", "5,58,70,90,93,111,126,156,165,195", "154"),
        ("S.3", "Chaotic Content", "13,24,68,79,88,106,112,148,167,172,190", ""),
        ("C.1", "Uncertain Self-Image", "14,70,101,111,151,156,170,178", ""),
        ("C.2", "Split Architecture", "4,17,39,59,93,100,126,134,166,192,193", ""),
        ("C.3", "Temperamentally Labile", "16,18,37,74,80,82,115,137,164,187", ""),
        ("P.1", "Expressively Defensive", "12,15,21,24,104,149,153,180,195", ""),
        ("P.2", "Cognitively Mistrustful", "17,52,79,88,172,182,184", ""),
        ("P.3", "Projection Dynamics", "13,32,68,96,106,112,122,136,148,167", ""),
    ]

    for abbr, name, true_items, false_items in facet_data:
        items = build_keyed_scale(true_items, false_items)
        scales[abbr] = {
            "scale_name": name,
            "items": items,
            "item_count": len(items)
        }

    # ─── Noteworthy Responses (simple keyed, weight 1) ───

    noteworthy_data = [
        ("AD", "Adult ADHD", "56,77,82,92,108", "63"),
        ("AS", "Autism Spectrum", "92,119,138,163,165,179,190", ""),
        ("CA", "Childhood Abuse", "47,157", ""),
        ("EA", "Eating Disorder", "69,86,102,186", ""),
        ("EM", "Emotional Dyscontrol", "27,36,45,56,72,80,127,177", ""),
        ("EX", "Explosively Angry", "11,74,115,145,168,191", ""),
        ("HP", "Health Preoccupied", "7,41,57,113,120,146", ""),
        ("IA", "Interpersonally Alienated", "4,104,182,190", ""),
        ("PD", "Prescription Drug Abuse", "124,176", ""),
        ("SP", "Self-Destructive Potential", "14,32,34,39,59,78,101,107,114,126,151,164", ""),
        ("SB", "Self-Injurious Behavior/Tendency", "40,181", ""),
        ("TB", "Traumatic Brain Injury", "55,110", ""),
        ("VP", "Vengefully Prone", "22,37,100,103,111,136,167,178,192", ""),
    ]

    for abbr, name, true_items, false_items in noteworthy_data:
        items = build_keyed_scale(true_items, false_items)
        scales[abbr] = {
            "scale_name": name,
            "items": items,
            "item_count": len(items)
        }

    return {"scales": scales}


def build_tscore_tables():
    """Build the tscore_tables.json (BR score lookup tables)."""

    # Column order for Table D.1
    d1_columns = ["1", "2A", "2B", "3", "4A", "4B", "5", "6A", "6B", "7",
                   "8A", "8B", "S", "C", "P", "A", "H", "N", "D", "B",
                   "T", "R", "SS", "CC", "PP"]

    # Table D.1 data — raw score rows (from extracted data)
    d1_rows = [
        "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0",
        "1,9,9,8,10,6,6,12,20,15,4,10,12,12,10,15,15,10,12,7,60,60,20,9,12,60",
        "2,17,17,15,20,11,12,24,40,30,8,20,24,24,20,30,30,20,24,14,68,62,40,17,24,62",
        "3,25,25,22,30,16,18,36,60,45,13,30,36,36,30,45,45,30,36,20,75,65,60,25,36,64",
        "4,34,34,29,40,21,24,48,62,60,17,40,48,48,50,60,60,40,48,26,78,67,62,34,48,66",
        "5,43,43,37,50,26,30,60,64,61,21,50,60,60,60,62,75,50,60,33,82,69,64,43,60,68",
        "6,52,52,45,60,31,36,62,66,63,26,60,62,61,63,64,77,60,63,40,85,72,66,52,64,70",
        "7,60,60,53,64,37,42,65,69,65,30,62,65,63,66,66,80,64,66,47,89,75,69,60,68,72",
        "8,62,65,60,68,43,48,67,71,67,34,65,67,65,69,69,83,68,69,54,94,77,71,61,72,74",
        "9,64,70,65,72,49,54,69,73,69,39,67,69,66,69,71,85,72,72,60,98,80,73,63,75,75",
        "10,66,75,70,75,54,60,72,75,71,43,69,72,67,72,73,88,75,75,61,102,83,75,64,77,76",
        "11,69,76,75,76,60,61,75,77,73,47,72,75,68,75,75,91,78,78,63,106,85,78,65,79,78",
        "12,71,77,76,78,62,63,77,79,74,52,75,76,69,76,76,94,82,82,65,111,89,82,66,80,79",
        "13,73,78,77,79,65,65,79,81,75,56,76,77,71,77,78,97,85,85,67,115,94,85,67,81,81",
        "14,75,79,78,81,67,67,81,83,77,60,77,78,73,78,79,100,100,90,69,,98,90,68,83,82",
        "15,76,81,79,82,69,68,83,85,79,62,78,79,74,79,80,103,115,95,71,,102,95,69,85,84",
        "16,78,82,79,84,69,69,85,90,81,65,79,80,75,81,81,106,,100,73,,106,100,71,88,85",
        "17,79,83,80,85,72,71,88,95,83,67,80,80,76,82,82,109,,105,74,,111,105,73,92,95",
        "18,81,84,81,90,75,73,92,100,85,69,81,81,77,83,84,112,,110,75,,115,110,74,95,105",
        "19,82,85,82,95,77,74,95,105,92,72,82,82,78,84,85,115,,115,77,,,115,75,99,115",
        "20,84,91,83,100,80,75,99,110,99,75,83,83,79,85,91,,,, 80,,,,77,102,",
        "21,85,97,84,105,83,78,102,115,106,80,84,84,81,85,97,,,,83,,,,80,106,",
        "22,100,103,85,110,85,82,106,,115,85,85,85,82,89,103,,,,85,,,,83,109,",
        "23,115,109,91,115,90,85,109,,,100,92,95,83,94,109,,,,91,,,,85,112,",
        "24,,115,97,,95,93,111,,,,,105,84,98,115,,,,97,,,,92,115,",
        "25,,,103,,100,100,113,,,,,115,85,102,,,,,103,,,,99,,",
        "26,,,109,,,,,,,,,, 92,106,,,,,109,,,,106,,",
        "27,,,115,,,,,,,,,,99,111,,,,,115,,,,115,,",
        "28,,,,,,,,,,,,, 106,115,,,,,,,,,,,",
        "29,,,,,,,,,,,,, 115,,,,,,,,,,,,",
    ]

    scales = {}

    # Scale names for D.1
    d1_scale_names = {
        "1": "Schizoid", "2A": "Avoidant", "2B": "Melancholic", "3": "Dependent",
        "4A": "Histrionic", "4B": "Turbulent", "5": "Narcissistic",
        "6A": "Antisocial", "6B": "Sadistic", "7": "Compulsive",
        "8A": "Negativistic", "8B": "Masochistic",
        "S": "Schizotypal", "C": "Borderline", "P": "Paranoid",
        "A": "Generalized Anxiety", "H": "Somatic Symptom", "N": "Bipolar Spectrum",
        "D": "Persistent Depression", "B": "Alcohol Use", "T": "Drug Use",
        "R": "Post-Traumatic Stress",
        "SS": "Schizophrenic Spectrum", "CC": "Major Depression", "PP": "Delusional"
    }

    # Initialize all D.1 scales
    for col in d1_columns:
        scales[col] = {
            "scale_name": d1_scale_names[col],
            "raw_to_t": {}
        }

    # Parse D.1 rows
    for row_str in d1_rows:
        parts = row_str.split(',')
        raw_score = int(parts[0])
        for i, col in enumerate(d1_columns):
            val_str = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if val_str:
                scales[col]["raw_to_t"][str(raw_score)] = int(val_str)

    # ─── Table D.3: X, Y, Z ───

    # V (Validity): simple count 0-3, no BR transformation
    scales["V"] = {
        "scale_name": "Validity",
        "raw_to_t": {"0": 0, "1": 0, "2": 85, "3": 115}
    }

    # X (Disclosure) — has ranges like "45-46" → same BR
    x_data = {
        "7": 0, "8": 2, "9": 5, "10": 7, "11": 10, "12": 12,
        "13": 15, "14": 17, "15": 19, "16": 21, "17": 23,
        "18": 25, "19": 28, "20": 30, "21": 33, "22": 35,
        "23": 37, "24": 39, "25": 41, "26": 43, "27": 45,
        "28": 46, "29": 47, "30": 48, "31": 49, "32": 50,
        "33": 52, "34": 54, "35": 56, "36": 58, "37": 60,
        "38": 61, "39": 62, "40": 63, "41": 64, "42": 65,
        "43": 66, "44": 67, "45": 68, "46": 68, "47": 69,
        "48": 70, "49": 71, "50": 72, "51": 73, "52": 74,
        "53": 75, "54": 76, "55": 77, "56": 78, "57": 79,
        "58": 79, "59": 80, "60": 80, "61": 81, "62": 81,
        "63": 82, "64": 83, "65": 84, "66": 85, "67": 86,
        "68": 86, "69": 86, "70": 87, "71": 87, "72": 87,
        "73": 88, "74": 88, "75": 88, "76": 89, "77": 89,
        "78": 89, "79": 90, "80": 90, "81": 90, "82": 91,
        "83": 91, "84": 91, "85": 92, "86": 92, "87": 93,
        "88": 93, "89": 94, "90": 94, "91": 95, "92": 95,
        "93": 96, "94": 96, "95": 96, "96": 97, "97": 97,
        "98": 98, "99": 98, "100": 99, "101": 99, "102": 100,
        "103": 100, "104": 100, "105": 100, "106": 100, "107": 100,
        "108": 100, "109": 100, "110": 100, "111": 100, "112": 100,
        "113": 100, "114": 100
    }
    # Add scores 0-6 as 0
    for i in range(7):
        x_data[str(i)] = 0

    scales["X"] = {
        "scale_name": "Disclosure",
        "raw_to_t": x_data
    }

    # Y (Desirability)
    y_data = {}
    y_values = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 63, 66, 69,
                72, 75, 78, 81, 85, 89, 93, 97, 100]
    for i, val in enumerate(y_values):
        y_data[str(i)] = val
    scales["Y"] = {
        "scale_name": "Desirability",
        "raw_to_t": y_data
    }

    # Z (Debasement)
    z_data = {}
    z_values = [0, 35, 38, 41, 44, 47, 50, 53, 56, 60, 62, 64, 66, 68, 70, 72,
                74, 75, 77, 79, 80, 81, 83, 85, 88, 91, 93, 95, 97, 100, 100]
    for i, val in enumerate(z_values):
        z_data[str(i)] = val
    scales["Z"] = {
        "scale_name": "Debasement",
        "raw_to_t": z_data
    }

    # ─── Grossman Facet Scale BR Tables (from Section 8, partial) ───

    facet_br = {
        "1.1": {"scale_name": "Interpersonally Unengaged", "raw_to_t": {
            "0": 0, "1": 30, "2": 40, "3": 60, "4": 64, "5": 68, "6": 72, "7": 75, "8": 82, "9": 85
        }},
        "1.2": {"scale_name": "Meager Content", "raw_to_t": {
            "0": 0, "1": 30, "2": 40, "3": 60, "4": 68, "5": 75, "6": 78, "7": 82, "8": 85, "9": 85
        }},
        "1.3": {"scale_name": "Temperamentally Apathetic", "raw_to_t": {
            "0": 0, "1": 30, "2": 40, "3": 60, "4": 68, "5": 75, "6": 82, "7": 85, "8": 85, "9": 85
        }},
    }

    scales.update(facet_br)

    return {
        "instrument": "MCMI-IV",
        "score_type": "Base Rate (BR)",
        "source": "MCMI-IV Manual, Appendix D (Millon, Grossman, & Millon, 2015)",
        "scales": scales
    }


def validate_mapping(mapping):
    """Validate the mapping data for consistency."""
    issues = []
    for abbr, scale in mapping['scales'].items():
        if scale.get('scale_type') == 'item_pairs':
            continue
        expected = scale.get('item_count', 0)
        actual = len(scale.get('items', []))
        if expected != actual:
            issues.append(f"  {abbr} ({scale['scale_name']}): expected {expected} items, got {actual}")

        # Check for duplicate items
        item_nums = [it['item'] for it in scale.get('items', [])]
        if len(item_nums) != len(set(item_nums)):
            dupes = [n for n in item_nums if item_nums.count(n) > 1]
            issues.append(f"  {abbr}: duplicate items {set(dupes)}")

    if issues:
        print("VALIDATION ISSUES:")
        for issue in issues:
            print(issue)
    else:
        print("All scales validated successfully.")

    return len(issues) == 0


def main():
    mapping = build_mapping()
    tscore_tables = build_tscore_tables()

    # Validate
    print("Validating mapping...")
    valid = validate_mapping(mapping)

    # Count stats
    total_scales = len(mapping['scales'])
    weighted_scales = sum(1 for s in mapping['scales'].values()
                         if any('scoring_weights' in it for it in s.get('items', [])))
    pair_scales = sum(1 for s in mapping['scales'].values()
                      if s.get('scale_type') == 'item_pairs')
    keyed_scales = total_scales - weighted_scales - pair_scales

    print(f"\nMapping stats:")
    print(f"  Total scales: {total_scales}")
    print(f"  Weighted scales (personality/clinical): {weighted_scales}")
    print(f"  Pair-based scales (W): {pair_scales}")
    print(f"  Simple keyed scales (validity/facets/noteworthy): {keyed_scales}")

    br_scale_count = len(tscore_tables['scales'])
    print(f"\nBR table stats:")
    print(f"  Scales with BR tables: {br_scale_count}")

    # Write files
    mapping_path = 'templates/mcmi4/mapping.json'
    tscore_path = 'templates/mcmi4/tscore_tables.json'

    with open(mapping_path, 'w') as f:
        json.dump(mapping, f, indent=2)
    print(f"\nWrote {mapping_path}")

    with open(tscore_path, 'w') as f:
        json.dump(tscore_tables, f, indent=2)
    print(f"Wrote {tscore_path}")


if __name__ == '__main__':
    main()
