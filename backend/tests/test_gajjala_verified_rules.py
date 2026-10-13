"""📓 Gajjala's Playbook data (WP7, 2026-10-13): `chart_maps/gajjala/verified_rules.json` is GG's method as verified
across sources (STRATEGY_SPEC §1.3) — one status per rule, every rule with a source, every video timestamp tied to its
video. The Playbook renders this file as served; nothing on the tab may claim more than the file says.

`_problems(doc)` is the whole contract and `_link_problems(doc, …)` ties it to constants.py both ways (every GG-tagged
constant has an item; every `used_by` names a real constant whose VALUE is the number the item prints); the real file
must have none, and each NEGATIVE below mutates a copy and proves the contract catches it. The JSON is hand-maintained
(the one-off builder is retired) — these tests are the guard. Ajay 2026-10-13: "Implement his full stategy do not assume anything. Look for other
sources too besides this for confimring his strategy".
"""
import ast
import copy
import io
import json
import math
import re
import tokenize
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC

_PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "gajjala"
_FILE = _PKG / "verified_rules.json"
_CONSTANTS = _PKG / "constants.py"

STATUSES = ("confirmed_first_hand", "confirmed_multi_source", "single_source", "contradicted", "unsupported")
_CODE = {"FH": "confirmed_first_hand", "MS": "confirmed_multi_source", "SS": "single_source",
         "CX": "contradicted", "UN": "unsupported"}
_WEAK_FIRST = ("CX", "UN", "SS", "MS", "FH")
_TS = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)(?:–(\d{1,2}:\d{2}(?::\d{2})?))?$")
_BRACKET_EDIT = re.compile(r"\[revers\w*\]", re.I)
_BANNED = re.compile(r"minervini|sepa\b|bonde|beginner", re.I)
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
# the GG-tagged constants on 2026-10-13 — a floor that proves the comment parser still finds them (WP1 may add more)
_GG_KNOWN = {"SCAN_MIN_PRICE", "SCAN_MAX_PRICE", "SCAN_MIN_VOLUME", "SCAN_MIN_CHANGE_PCT", "NO_TRADE_AFTER_OPEN_MIN",
             "BF_LEG_MIN_BARS", "KF_LEG_MIN_BARS", "SA_BIG_RUNNER_PCT", "SA_RUNNER_PCT", "SA_QUIET_BEST_PCT",
             "PSY_LEVELS", "RED_CLOSES_WAIT", "EMA_FAST", "EMA_SLOW"}

# Pinned on purpose — a re-verification changes these by hand, never silently.
PIN_TOTALS = {"rules": 107, "confirmed_first_hand": 55, "confirmed_multi_source": 23, "single_source": 19,
              "contradicted": 8, "unsupported": 2, "his_call": 68}
PIN_UPSTREAM = {"rules": 300, "topics": 33, "confirmed_first_hand": 113, "confirmed_multi_source": 72,
                "single_source": 88, "contradicted": 20, "unsupported": 7, "his_call": 202}


def _secs(ts):
    parts = [int(p) for p in ts.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def _expected_status(raw):
    codes = [p.strip().replace("†", "").split(" ")[0] for p in raw.split("/")]
    codes = [c for c in codes if c in _CODE]
    if codes == ["CX"]:
        return _CODE["CX"]
    return _CODE[min((c for c in codes if c != "CX"), key=_WEAK_FIRST.index)] if codes else None


def _rules(doc):
    return [r for t in doc["topics"] for r in t["verified"]]


def _ref_matches(sel, ref):
    return (sel.get("key") == ref.get("key") and all(sel[k] == ref.get(k) for k in ("ts", "post_id") if k in sel))


def _quote_problems(r, refs):
    """Each quote names the ref that said it (`quote_src[i]` = {key, ts?|post_id?}, matching exactly one of the rule's
    sources); on a "his words" rule that ref must be first-hand — a third-party line never reads as GG speaking."""
    rid, quotes, qsrc = r.get("id"), r.get("quotes") or [], r.get("quote_src")
    if not isinstance(qsrc, list) or len(qsrc) != len(quotes):
        return [f"{rid}: quote_src must name one source per quote"]
    out = []
    for i, sel in enumerate(qsrc):
        hits = [ref for ref in refs if isinstance(sel, dict) and _ref_matches(sel, ref)]
        if len(hits) != 1:
            out.append(f"{rid}: quote {i} source {sel!r} matches {len(hits)} of the rule's sources (needs exactly 1)")
        elif r.get("status") == "confirmed_first_hand" and hits[0].get("first_hand") is not True:
            out.append(f"{rid}: quote {i} is {hits[0]['key']}'s (third-party) on a 'his words' rule")
    return out


def _problems(doc):
    out = []
    reg = {s["key"]: s for s in doc["sources"]}
    vias = set(doc["via_labels"])
    if set(doc["status_labels"]) != set(STATUSES):
        out.append("status_labels must name exactly the five statuses")
    ids = [r.get("id") for r in _rules(doc)]
    if len(ids) != len(set(ids)):
        out.append("duplicate rule id")
    for r in _rules(doc):
        rid = r.get("id")
        if not (isinstance(r.get("rule"), str) and r["rule"].strip()):
            out.append(f"{rid}: empty rule")
        if r.get("status") not in STATUSES:
            out.append(f"{rid}: status {r.get('status')!r} not one of the five")
        if r.get("status") != _expected_status(r.get("status_raw", "")):
            out.append(f"{rid}: status does not follow status_raw {r.get('status_raw')!r}")
        if not isinstance(r.get("his_call"), bool) or r["his_call"] != ("†" in r.get("status_raw", "")):
            out.append(f"{rid}: his_call must be a bool equal to the † mark")
        if not (r.get("numbers") is None or isinstance(r["numbers"], str)):
            out.append(f"{rid}: numbers must be a string or null")
        if not all(isinstance(q, str) and q for q in r.get("quotes", [None])):
            out.append(f"{rid}: quotes must be non-empty strings")
        refs = r.get("sources") or []
        out += _quote_problems(r, refs)
        if not refs:
            out.append(f"{rid}: no source")
        for ref in refs:
            src = reg.get(ref.get("key"))
            if src is None:
                out.append(f"{rid}: unknown source key {ref.get('key')!r}")
                continue
            url = ref.get("url") or ""
            if ref["key"] == "S11":                 # one url per post: https://x.com/i/status/<post_id>
                if url != f"https://x.com/i/status/{ref.get('post_id')}" or not str(ref.get("post_id")).isdigit():
                    out.append(f"{rid}: X ref must carry its post id")
            elif url not in {src["url"], *src.get("urls", [])}:
                out.append(f"{rid}: {ref['key']} url {url!r} is not that source's")
            if ref.get("first_hand") is not src["first_hand"]:
                out.append(f"{rid}: {ref['key']} first_hand flag differs from the source's")
            if ref.get("via") not in vias:
                out.append(f"{rid}: via {ref.get('via')!r} unknown")
            ts = ref.get("ts")
            if ts is not None:
                m = _TS.match(ts)
                if not src.get("video_id") or src["video_id"] not in url:
                    out.append(f"{rid}: ts {ts} carries no video id ({ref['key']})")
                elif not m:
                    out.append(f"{rid}: ts {ts!r} malformed")
                else:
                    start, end = _secs(m.group(1)), _secs(m.group(2) or m.group(1))
                    if end < start or end > _secs(src["duration"]):
                        out.append(f"{rid}: ts {ts} outside {ref['key']} (length {src['duration']})")
        if r.get("status") == "confirmed_first_hand" and not any(ref.get("first_hand") for ref in refs):
            out.append(f"{rid}: 'his words' without a first-hand source")
        keys = {ref.get("key") for ref in refs}
        if r.get("status") == "confirmed_first_hand" and keys == {"S1"}:
            out.append(f"{rid}: cites only S1 (third-party) as his words")
        if "S17" in keys and r.get("status") != "contradicted":
            out.append(f"{rid}: the Dollar Wisdom rule must stay contradicted")
        if r.get("status") == "contradicted" and not r.get("contradiction"):
            out.append(f"{rid}: contradicted without saying what disagrees")
    text = json.dumps(doc, ensure_ascii=False)
    if re.search(r"bounc", _BRACKET_EDIT.sub("", text), re.I):
        out.append("'bounce' outside a bracketed [reverses] edit")
    if _BANNED.search(text):
        out.append("banned word (Minervini / SEPA / Bonde / beginner)")
    return out


@pytest.fixture(scope="module")
def doc():
    return json.loads(_FILE.read_text(encoding="utf-8"))


def test_the_committed_file_has_no_problems(doc):
    assert _problems(doc) == []


def test_schema_top_level(doc):
    assert doc["schema"] == "gajjala.verified_rules/2"
    assert {"sources", "topics", "totals", "upstream_totals", "status_labels", "via_labels", "decay"} <= set(doc)
    assert doc["status_labels"] == {"confirmed_first_hand": "his words", "confirmed_multi_source": "2+ sources",
                                    "single_source": "1 source", "contradicted": "sources disagree",
                                    "unsupported": "no source"}
    keys = [t["key"] for t in doc["topics"]]
    assert len(keys) == len(set(keys)) and all(t["verified"] for t in doc["topics"])


def test_totals_pin_and_the_file_counts_itself(doc):
    rules = _rules(doc)
    counted = {"rules": len(rules), "his_call": sum(r["his_call"] for r in rules)}
    counted.update({s: sum(r["status"] == s for r in rules) for s in STATUSES})
    assert counted == doc["totals"] == PIN_TOTALS


def _upstream_problems(doc):
    up = doc["upstream_totals"]
    out = [f"upstream {k} = {up.get(k)!r}, pinned {v}" for k, v in PIN_UPSTREAM.items() if up.get(k) != v]
    if sum(up.get(s, 0) for s in STATUSES) != up.get("rules"):
        out.append("upstream statuses do not sum to its rules")
    return out


def test_upstream_totals_are_the_verifiers_set(doc):
    assert _upstream_problems(doc) == []


def test_sources_registry_s1_is_third_party_and_videos_carry_ids(doc):
    reg = {s["key"]: s for s in doc["sources"]}
    assert [f"S{i}" for i in range(1, 19)] == list(reg)
    assert reg["S1"]["kind"] == "third-party" and reg["S1"]["first_hand"] is False
    assert reg["S1"]["url"] == "https://retailtradersrepository.substack.com/p/goverdhan-gajjala-a-deep-dive-into"
    assert reg["S8"]["video_id"] == "CI7mNvEQyms" and reg["S8"]["video_id"] in reg["S8"]["url"]
    assert reg["S9"]["video_id"] == "10pHBNVi4Jc" and reg["S9"]["video_id"] in reg["S9"]["url"]
    assert all(reg[k]["first_hand"] for k in ("S8", "S9", "S10", "S11"))
    assert not any(reg[k]["first_hand"] for k in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S12", "S16", "S17"))


def test_every_timestamp_carries_its_video(doc):
    ts_refs = [ref for r in _rules(doc) for ref in r["sources"] if "ts" in ref]
    assert ts_refs and {ref["key"] for ref in ts_refs} == {"S8", "S9"}
    # STRATEGY_SPEC §1.4: 1:54:46–2:02:40 is the TraderLion podcast (S9), never the webinar (S8, 1:50:36 long).
    assert not [ref for ref in ts_refs if ref["key"] == "S8" and _secs(ref["ts"].split("–")[0]) >= _secs("1:54:46")]


def test_dollar_wisdom_stays_contradicted(doc):
    dw = [r for r in _rules(doc) if any(ref["key"] == "S17" for ref in r["sources"])]
    assert [r["id"] for r in dw] == ["E10"] and dw[0]["status"] == "contradicted"


def test_scanner_floor_is_contradicted_and_names_his_latest(doc):
    u2 = next(r for r in _rules(doc) if r["id"] == "U2")
    assert u2["status"] == "contradicted" and u2["his_call"] is True
    assert "1753094531757838340" in {ref.get("post_id") for ref in u2["sources"]}
    assert "0.1$ and above" in u2["quotes"][0]


def test_risk_line_says_his_own_starting_risk(doc):
    e8 = next(r for r in _rules(doc) if r["id"] == "E8")
    assert "0.25%" in e8["rule"] and "his own starting risk" in e8["rule"]
    assert "AMBIGUOUS" in e8["contradiction"]


def test_expectancy_is_computed_from_his_own_numbers(doc):
    fy, h2 = doc["stats_inputs"]["full_year"], doc["stats_inputs"]["h2"]
    assert doc["expectancy_full_year_pct"] == round(0.31 * 8.55 - 0.68 * 4.06, 2) == -0.11
    assert doc["expectancy_h2_pct"] == round(0.28 * 13 - 0.72 * 4, 2) == 0.76
    assert (fy["win"], fy["loss"], fy["avg_win_pct"], fy["avg_loss_pct"]) == (0.31, 0.68, 8.55, 4.06)
    assert (h2["win"], h2["loss"], h2["avg_win_pct"], h2["avg_loss_pct"]) == (0.28, 0.72, 13.0, 4.0)


def test_reversal_quotes_are_bracket_edited_not_dropped(doc):
    rs2 = next(r for r in _rules(doc) if r["id"] == "RS2")
    assert any("[reverses]" in q for q in rs2["quotes"]) and any("[reversal]" in q for q in rs2["quotes"])


def _constant_names():
    """Every name constants.py defines or re-exports (top-level assigns + the import line)."""
    names = set()
    for node in ast.parse(_CONSTANTS.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            names |= {a.asname or a.name for a in node.names}
    return names


def _gg_constants():
    """The constants whose provenance comment says GG: a top-level assign whose trailing comment starts `# GG `, plus
    the names an import line re-exports when its comment carries `— GG ` (EMA_FAST / EMA_SLOW)."""
    src = _CONSTANTS.read_text(encoding="utf-8")
    comments = {tok.start[0]: tok.string for tok in tokenize.generate_tokens(io.StringIO(src).readline)
                if tok.type == tokenize.COMMENT}
    out = set()
    for node in ast.parse(src).body:
        c = comments.get(node.lineno, "")
        if isinstance(node, ast.Assign) and re.match(r"#\s*GG ", c):
            out |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.ImportFrom) and "— GG " in c:
            out |= {a.asname or a.name for a in node.names}
    return out


def _values(name):
    v = getattr(GC, name, None)
    vals = v if isinstance(v, (tuple, list, set, frozenset)) else (v,)
    return [float(x) for x in vals if isinstance(x, (int, float)) and not isinstance(x, bool)]


def _link_problems(doc, names, gg):
    out = []
    used = set()
    for r in _rules(doc):
        ub = r.get("used_by") or []
        used |= set(ub)
        for u in ub:
            if u not in names:
                out.append(f"{r['id']}: used_by {u} is not a constant")
        if not ub or not r.get("numbers"):
            continue
        allowed = [v for u in ub for v in _values(u)]
        for tok in _NUMBER.findall(_ISO_DATE.sub(" ", r["numbers"])):
            n = float(tok.replace(",", ""))
            if not any(math.isclose(n, v) for v in allowed):
                out.append(f"{r['id']}: number {tok} in `numbers` is no used_by constant's value ({', '.join(ub)})")
    for name in sorted(gg - used):
        out.append(f"{name}: GG-tagged constant with no Playbook item naming it in used_by")
    return out


def test_gg_comment_parser_still_finds_his_constants():
    assert _GG_KNOWN <= _gg_constants()
    assert not {"STAY_LISTED_SESSIONS", "PSY_NEAR_PCT", "HF_LEG_MIN_BARS", "K2_MAX_VOL_STEP"} & _gg_constants()


def test_used_by_and_constants_pin_both_ways(doc):
    """Every GG-tagged constant has an item; every used_by names a real constant; every number an item with used_by
    prints IS one of those constants' values (a re-tune in constants.py fails here until the item says the same)."""
    assert _link_problems(doc, _constant_names(), _gg_constants()) == []
    assert {u for r in _rules(doc) for u in r.get("used_by", [])}


# ── NEGATIVES: the contract catches each way the file could lie ─────────────────────────────────────────────────


def _mutate(doc, rid, fn):
    d = copy.deepcopy(doc)
    fn(next(r for r in _rules(d) if r["id"] == rid))
    return _problems(d)


def test_negative_rule_without_a_source_fails(doc):
    assert any("no source" in p for p in _mutate(doc, "U9", lambda r: r.update(sources=[])))


def test_negative_status_outside_the_five_fails(doc):
    assert any("not one of the five" in p for p in _mutate(doc, "U9", lambda r: r.update(status="probable")))


def test_negative_status_stronger_than_its_code_fails(doc):
    # R10 is "FH† / SS†" — served at the weaker part; promoting it to "his words" must fail.
    assert any("status_raw" in p for p in _mutate(doc, "R10", lambda r: r.update(status="confirmed_first_hand")))


def test_negative_his_call_not_bool_fails(doc):
    assert any("his_call" in p for p in _mutate(doc, "U9", lambda r: r.update(his_call="no")))


def test_negative_dollar_wisdom_promoted_fails(doc):
    probs = _mutate(doc, "E10", lambda r: r.update(status="single_source", status_raw="SS"))
    assert any("Dollar Wisdom" in p for p in probs)


def test_negative_only_s1_as_his_words_fails(doc):
    def fn(r):
        r.update(status="confirmed_first_hand", status_raw="FH", contradiction=None)
        r["sources"] = [{"key": "S1", "url": doc["sources"][0]["url"], "first_hand": False, "via": "spec"}]
    probs = _mutate(doc, "R1b", fn)
    assert any("only S1" in p for p in probs) and any("without a first-hand source" in p for p in probs)


def test_negative_timestamp_without_its_video_fails(doc):
    def fn(r):
        r["sources"][0]["ts"] = "14:41"          # an X post has no video
    assert any("carries no video id" in p for p in _mutate(doc, "R3", fn))


def test_negative_s9_timestamp_filed_under_s8_fails(doc):
    def fn(r):
        r["sources"][0].update(key="S8", url="https://www.youtube.com/watch?v=CI7mNvEQyms", ts="1:55:28")
    assert any("outside S8" in p for p in _mutate(doc, "X1", fn))


def test_negative_malformed_timestamp_fails(doc):
    def fn(r):
        r["sources"][0]["ts"] = "14m41"
    assert any("malformed" in p for p in _mutate(doc, "R4", fn))


def test_negative_wrong_url_for_a_key_fails(doc):
    def fn(r):
        r["sources"][0]["url"] = "https://example.com/not-his"
    assert any("is not that source's" in p for p in _mutate(doc, "U9", fn))


def test_negative_x_ref_without_its_post_id_fails(doc):
    def fn(r):
        r["sources"][0]["url"] = "https://x.com/gov_gajjala"
    assert any("post id" in p for p in _mutate(doc, "R3", fn))


def test_negative_first_hand_flag_flipped_on_a_third_party_ref_fails(doc):
    def fn(r):
        next(ref for ref in r["sources"] if ref["key"] == "S12")["first_hand"] = True
    assert any("first_hand flag" in p for p in _mutate(doc, "KF3", fn))


def test_negative_unbracketed_bounce_fails(doc):
    def fn(r):
        r["quotes"][0] = "whenever it hits the ground it bounces back hard"
    assert any("bounce" in p for p in _mutate(doc, "RS2", fn))


def test_negative_banned_attribution_fails(doc):
    assert any("banned word" in p
               for p in _mutate(doc, "E8", lambda r: r.update(rule=r["rule"] + " (a beginner figure)")))


def test_negative_contradicted_without_reason_fails(doc):
    assert any("without saying" in p for p in _mutate(doc, "U13", lambda r: r.pop("contradiction")))


def test_negative_quote_without_its_source_fails(doc):
    assert any("quote_src" in p for p in _mutate(doc, "U9", lambda r: r.update(quote_src=[])))


def test_negative_third_party_quote_on_his_words_rule_fails(doc):
    # mutation M8: Business Insider's line filed on FH rule U4, with BI added as a source so the selector resolves
    bi = "https://www.businessinsider.com/top-chart-indicators-trader-volatile-stocks-high-returns-in-2023-2024-1"

    def fn(r):
        r["sources"].append({"key": "S12", "url": bi, "first_hand": False, "via": "spec"})
        r["quotes"].append("exit a loser within five minutes")
        r["quote_src"].append({"key": "S12"})
    assert any("third-party" in p for p in _mutate(doc, "U4", fn))


def test_negative_quote_naming_a_source_the_rule_lacks_fails(doc):
    def fn(r):
        r["quote_src"][0] = {"key": "S8", "ts": "1:00:00"}
    assert any("matches 0" in p for p in _mutate(doc, "U9", fn))


def _link(d):
    return _link_problems(d, _constant_names(), _gg_constants())


def test_negative_retyped_number_drifting_from_its_constant_fails(doc):
    # mutation M5: U1 says +30% while SCAN_MIN_CHANGE_PCT is 25
    d = copy.deepcopy(doc)
    u1 = next(r for r in _rules(d) if r["id"] == "U1")
    u1["numbers"] = u1["numbers"].replace("+25%", "+30%")
    assert any("U1: number 30" in p for p in _link(d))


def test_negative_constant_retuned_without_the_item_fails(doc, monkeypatch):
    monkeypatch.setattr(GC, "SCAN_MIN_VOLUME", 2_000_000)
    assert any("U1: number 1,000,000" in p for p in _link(doc))
    monkeypatch.setattr(GC, "PSY_LEVELS", (1.0, 5.0, 20.0))
    assert any("T8: number 10" in p for p in _link(doc))


def test_negative_gg_constant_losing_its_item_fails(doc):
    # mutation M3: U2 no longer names SCAN_MIN_PRICE
    d = copy.deepcopy(doc)
    next(r for r in _rules(d) if r["id"] == "U2")["used_by"] = []
    assert any(p.startswith("SCAN_MIN_PRICE: GG-tagged") for p in _link(d))


def test_negative_every_used_by_stripped_but_one_fails(doc):
    # mutation M4: only T2 keeps its used_by
    d = copy.deepcopy(doc)
    for r in _rules(d):
        if r["id"] != "T2":
            r.pop("used_by", None)
    probs = _link(d)
    assert {p.split(":")[0] for p in probs} >= _GG_KNOWN - {"EMA_FAST", "EMA_SLOW"}


def test_negative_used_by_naming_no_constant_fails(doc):
    d = copy.deepcopy(doc)
    next(r for r in _rules(d) if r["id"] == "R4")["used_by"] = ["NO_TRADE_AFTER_OPEN_MINUTES"]
    assert any("is not a constant" in p for p in _link(d))


def test_negative_upstream_pin_catches_his_call_drift(doc):
    # mutation M10: upstream his_call 202 -> 1 (and the topic count, which the Playbook prints beside it)
    d = copy.deepcopy(doc)
    d["upstream_totals"].update(his_call=1)
    assert _upstream_problems(d) == ["upstream his_call = 1, pinned 202"]
    d["upstream_totals"].update(his_call=202, topics=32)
    assert _upstream_problems(d) == ["upstream topics = 32, pinned 33"]


def test_scan_count_contradiction_cites_both_sides(doc):
    u13 = next(r for r in _rules(doc) if r["id"] == "U13")
    assert {ref["key"] for ref in u13["sources"]} == {"S2", "S12"}


def test_screenshot_readings_carry_no_webinar_timestamp(doc):
    for rid in ("T3", "T4"):
        r = next(x for x in _rules(doc) if x["id"] == rid)
        assert not any("ts" in ref for ref in r["sources"])


def test_every_quote_today_is_his(doc):
    """docs/gajjala/sources_2026_10_13.md says all 45 quotes are GG's own (S8 / S9 / his X posts)."""
    reg = {s["key"]: s for s in doc["sources"]}
    keys = [sel["key"] for r in _rules(doc) for sel in r["quote_src"]]
    assert len(keys) == 45 and all(reg[k]["first_hand"] for k in keys) and set(keys) == {"S8", "S9", "S11"}
