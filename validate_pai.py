"""Validate PAI scoring system against PAR reference reports for two clients."""
import json
import sys
import os

# ── PAI response encoding: F=0, ST=1, MT=2, VT=3 ──
RESP_MAP = {'F': 0, 'ST': 1, 'MT': 2, 'VT': 3}

# ── Eve (737-Eve) item responses ──
# Parsed from 737-Y PAI.txt pages 8-9
EVE_RESPONSES = {}
_eve_raw = """
1:MT 2:MT 3:ST 4:ST 5:F 6:F 7:ST 8:MT 9:F 10:VT
11:MT 12:MT 13:ST 14:MT 15:F 16:MT 17:MT 18:VT 19:ST 20:F
21:F 22:ST 23:ST 24:MT 25:ST 26:ST 27:F 28:MT 29:F 30:ST
31:F 32:F 33:F 34:F 35:ST 36:ST 37:MT 38:F 39:ST 40:F
41:MT 42:F 43:F 44:F 45:ST 46:F 47:VT 48:ST 49:F 50:F
51:F 52:F 53:ST 54:F 55:F 56:MT 57:ST 58:F 59:ST 60:ST
61:F 62:F 63:ST 64:VT 65:ST 66:ST 67:F 68:MT 69:F 70:F
71:F 72:F 73:F 74:ST 75:F 76:VT 77:MT 78:ST 79:F 80:VT
81:VT 82:MT 83:F 84:F 85:VT 86:F 87:F 88:MT 89:F 90:F
91:ST 92:F 93:MT 94:ST 95:F 96:F 97:MT 98:F 99:MT 100:F
101:F 102:F 103:VT 104:ST 105:F 106:F 107:F 108:ST 109:MT 110:ST
111:F 112:MT 113:ST 114:F 115:ST 116:MT 117:ST 118:ST 119:ST 120:F
121:F 122:MT 123:F 124:VT 125:ST 126:F 127:MT 128:F 129:ST 130:F
131:F 132:F 133:ST 134:F 135:F 136:ST 137:F 138:F 139:VT 140:F
141:F 142:VT 143:ST 144:ST 145:F 146:ST 147:F 148:MT 149:F 150:F
151:ST 152:MT 153:F 154:ST 155:F 156:ST 157:F 158:F 159:F 160:ST
161:MT 162:ST 163:F 164:MT 165:ST 166:F 167:F 168:F 169:F 170:F
171:ST 172:F 173:MT 174:F 175:F 176:MT 177:F 178:VT 179:VT 180:F
181:F 182:F 183:F 184:ST 185:F 186:VT 187:F 188:ST 189:F 190:MT
191:F 192:F 193:F 194:ST 195:F 196:MT 197:MT 198:F 199:ST 200:F
201:VT 202:MT 203:F 204:F 205:MT 206:F 207:MT 208:F 209:F 210:F
211:F 212:F 213:MT 214:MT 215:F 216:ST 217:F 218:MT 219:MT 220:F
221:VT 222:F 223:F 224:ST 225:ST 226:VT 227:VT 228:F 229:VT 230:MT
231:MT 232:MT 233:F 234:F 235:MT 236:MT 237:ST 238:F 239:ST 240:ST
241:F 242:ST 243:F 244:F 245:MT 246:MT 247:F 248:MT 249:F 250:F
251:VT 252:VT 253:MT 254:F 255:F 256:ST 257:F 258:F 259:MT 260:F
261:F 262:F 263:ST 264:ST 265:F 266:F 267:VT 268:MT 269:ST 270:MT
271:F 272:F 273:F 274:F 275:F 276:MT 277:F 278:F 279:F 280:F
281:ST 282:MT 283:F 284:ST 285:ST 286:MT 287:MT 288:MT 289:F 290:VT
291:MT 292:MT 293:VT 294:MT 295:ST 296:ST 297:F 298:VT 299:VT 300:F
301:VT 302:F 303:F 304:MT 305:F 306:MT 307:MT 308:MT 309:F 310:MT
311:F 312:F 313:ST 314:ST 315:F 316:MT 317:MT 318:F 319:F 320:MT
321:F 322:ST 323:ST 324:F 325:F 326:ST 327:ST 328:F 329:F 330:MT
331:MT 332:MT 333:F 334:F 335:F 336:MT 337:MT 338:MT 339:ST 340:F
341:F 342:MT 343:ST 344:ST
"""
for token in _eve_raw.split():
    num, resp = token.split(':')
    EVE_RESPONSES[int(num)] = RESP_MAP[resp]

# ── Greg (737-Greg) item responses ──
# Parsed from Greg PAI.txt pages 9-10
GREG_RESPONSES = {}
_greg_raw = """
1:F 2:ST 3:F 4:F 5:F 6:MT 7:F 8:F 9:F 10:F
11:F 12:F 13:F 14:ST 15:F 16:F 17:F 18:F 19:MT 20:ST
21:VT 22:F 23:F 24:VT 25:F 26:F 27:ST 28:MT 29:VT 30:VT
31:MT 32:ST 33:F 34:ST 35:MT 36:VT 37:F 38:F 39:VT 40:F
41:F 42:ST 43:F 44:F 45:ST 46:VT 47:F 48:VT 49:ST 50:F
51:VT 52:MT 53:F 54:VT 55:F 56:F 57:VT 58:VT 59:VT 60:ST
61:VT 62:F 63:VT 64:VT 65:MT 66:F 67:VT 68:ST 69:MT 70:MT
71:MT 72:VT 73:F 74:ST 75:F 76:ST 77:MT 78:F 79:MT 80:ST
81:F 82:ST 83:F 84:F 85:F 86:MT 87:F 88:F 89:VT 90:F
91:VT 92:F 93:F 94:ST 95:F 96:F 97:F 98:VT 99:VT 100:F
101:MT 102:F 103:VT 104:F 105:F 106:F 107:MT 108:F 109:F 110:VT
111:ST 112:F 113:F 114:ST 115:F 116:F 117:ST 118:F 119:MT 120:F
121:VT 122:F 123:F 124:MT 125:ST 126:VT 127:F 128:F 129:F 130:F
131:VT 132:F 133:F 134:ST 135:F 136:F 137:F 138:VT 139:F 140:F
141:VT 142:VT 143:ST 144:ST 145:F 146:MT 147:ST 148:F 149:VT 150:VT
151:MT 152:ST 153:MT 154:ST 155:F 156:F 157:MT 158:F 159:F 160:VT
161:F 162:ST 163:F 164:F 165:F 166:VT 167:F 168:VT 169:VT 170:MT
171:VT 172:ST 173:VT 174:F 175:F 176:MT 177:VT 178:F 179:MT 180:F
181:VT 182:F 183:F 184:MT 185:F 186:F 187:VT 188:F 189:VT 190:F
191:VT 192:VT 193:ST 194:F 195:ST 196:VT 197:F 198:F 199:F 200:VT
201:F 202:ST 203:F 204:MT 205:MT 206:MT 207:F 208:VT 209:F 210:F
211:F 212:F 213:VT 214:VT 215:F 216:F 217:F 218:F 219:F 220:VT
221:F 222:F 223:F 224:F 225:F 226:VT 227:F 228:ST 229:F 230:F
231:VT 232:F 233:F 234:ST 235:MT 236:MT 237:F 238:F 239:MT 240:MT
241:F 242:F 243:F 244:ST 245:F 246:F 247:F 248:MT 249:F 250:F
251:F 252:F 253:F 254:F 255:F 256:MT 257:F 258:VT 259:F 260:F
261:ST 262:F 263:F 264:F 265:F 266:VT 267:F 268:F 269:VT 270:F
271:VT 272:F 273:F 274:F 275:ST 276:VT 277:F 278:F 279:F 280:F
281:VT 282:VT 283:F 284:ST 285:ST 286:F 287:ST 288:VT 289:VT 290:VT
291:F 292:F 293:F 294:VT 295:VT 296:F 297:MT 298:F 299:F 300:F
301:F 302:F 303:MT 304:ST 305:F 306:VT 307:F 308:VT 309:F 310:F
311:ST 312:F 313:F 314:ST 315:VT 316:VT 317:F 318:VT 319:F 320:VT
321:VT 322:VT 323:F 324:F 325:VT 326:F 327:VT 328:F 329:F 330:F
331:F 332:VT 333:F 334:F 335:F 336:F 337:VT 338:VT 339:VT 340:F
341:F 342:VT 343:ST 344:F
"""
for token in _greg_raw.split():
    num, resp = token.split(':')
    GREG_RESPONSES[int(num)] = RESP_MAP[resp]

# ── PAR reference scores from profile pages ──
# Format: (raw_score, t_score)

EVE_REF = {
    # Full scales (page 3)
    'ICN': (9, 61), 'INF': (5, 59), 'NIM': (1, 47), 'PIM': (13, 45),
    'SOM': (12, 51), 'ANX': (19, 52), 'ARD': (21, 51), 'DEP': (10, 45),
    'MAN': (35, 63), 'PAR': (22, 54), 'SCZ': (14, 50), 'BOR': (29, 61),
    'ANT': (17, 54), 'ALC': (6, 52), 'DRG': (5, 52), 'AGG': (5, 38),
    'SUI': (4, 51), 'STR': (5, 48), 'NON': (4, 48), 'RXR': (14, 51),
    'DOM': (18, 45), 'WRM': (17, 38),
    # Subscales (page 4)
    'SOM-C': (1, 46), 'SOM-S': (4, 49), 'SOM-H': (7, 57),
    'ANX-C': (7, 52), 'ANX-A': (6, 49), 'ANX-P': (6, 55),
    'ARD-O': (12, 57), 'ARD-P': (5, 45), 'ARD-T': (4, 50),
    'DEP-C': (1, 40), 'DEP-A': (2, 44), 'DEP-P': (7, 53),
    'MAN-A': (9, 57), 'MAN-G': (11, 56), 'MAN-I': (15, 67),
    'PAR-H': (10, 57), 'PAR-P': (2, 45), 'PAR-R': (10, 58),
    'SCZ-P': (3, 46), 'SCZ-S': (6, 51), 'SCZ-T': (5, 52),
    'BOR-A': (9, 63), 'BOR-I': (8, 59), 'BOR-N': (8, 59), 'BOR-S': (4, 53),
    'ANT-A': (7, 55), 'ANT-E': (3, 49), 'ANT-S': (7, 56),
    'AGG-A': (4, 45), 'AGG-V': (1, 34), 'AGG-P': (0, 42),
}

GREG_REF = {
    # Full scales (page 3)
    'ICN': (8, 58), 'INF': (6, 63), 'NIM': (10, 81), 'PIM': (14, 48),
    'SOM': (19, 58), 'ANX': (24, 57), 'ARD': (19, 49), 'DEP': (54, 92),
    'MAN': (21, 48), 'PAR': (62, 100), 'SCZ': (25, 64), 'BOR': (43, 75),
    'ANT': (53, 94), 'ALC': (3, 47), 'DRG': (0, 42), 'AGG': (53, 95),
    'SUI': (12, 68), 'STR': (15, 71), 'NON': (21, 94), 'RXR': (18, 59),
    'DOM': (21, 51), 'WRM': (0, 30),
    # Subscales (page 4)
    'SOM-C': (0, 43), 'SOM-S': (12, 70), 'SOM-H': (7, 57),
    'ANX-C': (8, 55), 'ANX-A': (9, 57), 'ANX-P': (7, 58),
    'ARD-O': (6, 41), 'ARD-P': (7, 51), 'ARD-T': (6, 55),
    'DEP-C': (19, 93), 'DEP-A': (21, 96), 'DEP-P': (14, 69),
    'MAN-A': (2, 35), 'MAN-G': (4, 40), 'MAN-I': (15, 67),
    'PAR-H': (23, 95), 'PAR-P': (20, 98), 'PAR-R': (19, 83),
    'SCZ-P': (2, 43), 'SCZ-S': (23, 94), 'SCZ-T': (0, 37),
    'BOR-A': (13, 75), 'BOR-I': (9, 62), 'BOR-N': (16, 84), 'BOR-S': (5, 57),
    'ANT-A': (24, 93), 'ANT-E': (17, 95), 'ANT-S': (12, 70),
    'AGG-A': (18, 84), 'AGG-V': (18, 82), 'AGG-P': (17, 100),
}


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def score_scale(scale_abbr, mapping, responses):
    """Score a PAI scale given item mapping and responses.

    PAI uses 4-point Likert: F=0, ST=1, MT=2, VT=3.
    Reverse-keyed (keyed="False") items: score = 3 - response.
    ICN (paired items) is skipped here — scored separately.
    """
    if scale_abbr not in mapping:
        return None

    scale = mapping[scale_abbr]
    items = scale.get('items', [])
    raw = 0

    for entry in items:
        item_num = entry['item']
        keyed = entry.get('keyed', 'True')
        resp = responses.get(item_num)

        if resp is None:
            continue

        if keyed == 'paired':
            # ICN: skip individual scoring — handled separately
            continue
        elif keyed == 'False':
            raw += (3 - resp)
        else:
            raw += resp

    return raw


def lookup_t(scale_abbr, raw, tscore_tables):
    """Look up T-score from conversion tables."""
    if scale_abbr not in tscore_tables:
        return None

    table = tscore_tables[scale_abbr]['raw_to_t']
    raw_key = str(raw)

    if raw_key in table:
        val = table[raw_key]
        return int(val) if val is not None else None

    # Clamp to nearest available key
    keys = sorted([int(k) for k in table.keys() if table[k] is not None])
    if not keys:
        return None
    if raw <= keys[0]:
        return int(table[str(keys[0])])
    if raw >= keys[-1]:
        return int(table[str(keys[-1])])
    return None


def validate_client(name, responses, reference, mapping, tscore_tables):
    """Run validation for one client. Returns (matches, mismatches, details)."""
    print(f"\n{'=' * 70}")
    print(f"VALIDATION: {name}")
    print(f"{'=' * 70}")

    # Verify response count
    print(f"  Items loaded: {len(responses)}/344")

    matches = 0
    mismatches = 0
    raw_matches = 0
    raw_mismatches = 0
    t_matches = 0
    t_mismatches = 0
    details = []

    for scale_abbr, (ref_raw, ref_t) in sorted(reference.items()):
        # Skip ICN for now (pair-based scoring not implemented yet)
        if scale_abbr == 'ICN':
            our_raw = '—'
            our_t = '—'
            status = 'SKIP'
            details.append((scale_abbr, status, our_raw, our_t, ref_raw, ref_t, '(pair-based)'))
            continue

        our_raw = score_scale(scale_abbr, mapping, responses)

        if our_raw is None:
            details.append((scale_abbr, 'MISSING', '—', '—', ref_raw, ref_t, 'not in mapping'))
            mismatches += 1
            continue

        our_t = lookup_t(scale_abbr, our_raw, tscore_tables)

        raw_ok = (our_raw == ref_raw)
        t_ok = (our_t == ref_t) if our_t is not None else False

        if raw_ok:
            raw_matches += 1
        else:
            raw_mismatches += 1

        if t_ok:
            t_matches += 1
        else:
            t_mismatches += 1

        if raw_ok and t_ok:
            status = 'OK'
            matches += 1
            note = ''
        else:
            status = 'MISMATCH'
            mismatches += 1
            parts = []
            if not raw_ok:
                parts.append(f'raw diff={our_raw - ref_raw:+d}')
            if not t_ok:
                t_diff = f'{our_t - ref_t:+d}' if our_t is not None else 'N/A'
                parts.append(f'T diff={t_diff}')
            note = '; '.join(parts)

        details.append((scale_abbr, status, our_raw, our_t, ref_raw, ref_t, note))

    # Print results
    print(f"\n{'Scale':<8} {'Status':<10} {'Our Raw':>8} {'Our T':>8} {'Ref Raw':>8} {'Ref T':>8}  Note")
    print("-" * 78)
    for scale_abbr, status, our_raw, our_t, ref_raw, ref_t, note in details:
        marker = "  <<<" if status == 'MISMATCH' else ""
        print(f"{scale_abbr:<8} {status:<10} {str(our_raw):>8} {str(our_t):>8} {str(ref_raw):>8} {str(ref_t):>8}  {note}{marker}")

    total = matches + mismatches
    print(f"\n{'=' * 70}")
    print(f"RESULTS: {matches}/{total} perfect match (raw + T)")
    print(f"  Raw scores: {raw_matches}/{raw_matches + raw_mismatches} match")
    print(f"  T-scores:   {t_matches}/{t_matches + t_mismatches} match")
    print(f"{'=' * 70}")

    return matches, mismatches, details


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base, 'templates', 'pai')

    # Load PAI configuration files
    mapping = load_json(os.path.join(template_dir, 'mapping.json'))['scales']
    tscore_tables = load_json(os.path.join(template_dir, 'tscore_tables.json'))['scales']

    print("PAI VALIDATION SUITE")
    print(f"Mapping: {len(mapping)} scales")
    print(f"T-score tables: {len(tscore_tables)} scales")

    # Validate both clients
    eve_m, eve_mm, eve_d = validate_client(
        "Eve (737-Eve, 03/11/2026)", EVE_RESPONSES, EVE_REF, mapping, tscore_tables
    )
    greg_m, greg_mm, greg_d = validate_client(
        "Greg (737-Greg, 02/25/2026)", GREG_RESPONSES, GREG_REF, mapping, tscore_tables
    )

    # Summary
    total_m = eve_m + greg_m
    total_mm = eve_mm + greg_mm
    total = total_m + total_mm

    print(f"\n{'=' * 70}")
    print(f"OVERALL: {total_m}/{total} scales match across both clients")
    if total_mm > 0:
        print(f"  {total_mm} discrepancies found — review above for details")
        sys.exit(1)
    else:
        print("  All scales match PAR reference. Validation PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()
