"""📅 Long Term (2026-11-12) — served words: no trading verbs (one allowed sentence), never the
house's banned rebound word, no attribution words anywhere, numbers from engine dicts."""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path

from long_term_list import constants as C
from long_term_list import criteria as CR
from long_term_list import payload as P
from long_term_list import seed as SD
from long_term_list import words as W

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
FIX = Path(__file__).parent / "fixtures" / "long_term_list"
BANNED = re.compile(r"\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b", re.I)
REBOUND = re.compile("bou" + "nce", re.I)
ATTRIBUTION = re.compile("|".join(["g" + "hee", "jhun" + "jhunwala", "junjun" + "wala", "big " + "bull"]), re.I)


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def _served():
    seed = SD.load()
    base = json.loads((FIX / "baseline_mini.json").read_text(encoding="utf-8"))
    runs = json.loads((FIX / "runs_w46_w47.json").read_text(encoding="utf-8"))
    fwd = json.loads((FIX / "forward_w47.json").read_text(encoding="utf-8"))
    zones = {"TSM": {"close": 405.49, "date": "2026-11-20"}, "INTU": {"close": 340.17, "date": "2026-11-20"}}
    out = list(_strings(P.build_payload(seed, base, runs, fwd, zones, now=dt.datetime(2026, 11, 20, 18), owner=True)))
    out += list(_strings(P.build_payload(seed, base, [], [], zones, now=dt.datetime(2026, 11, 12, 22), owner=True)))
    out += list(_strings(P.build_payload(seed, base, [], [], zones, now=None, owner=False)))
    out += list(_strings(W.rules_lines(include_pankaj=True)))
    out += [v for k, v in vars(W).items() if k.isupper() and isinstance(v, str)]
    out += [W.caveat(c) for c in C.CATEGORY_KEYS] + [W.criteria_text(c) for c in C.CATEGORY_KEYS]
    out += [W.stage_drop_text("X", 4, None, "2026-11-12"), W.sales_drop_text("X", "strong", "declining", -3.0, "q"),
            W.fundamental_text("X", "hot", ["a"]), W.started_moving_text("X"), W.absent_text("X", ["scan"]),
            W.top_new_text("hot", ["X"]), W.digest_title("d", 1, 2, 3), W.more_text(3), W.pushed_text(),
            W.forward_too_early(3, "2026-11-13", 74), W.forward_counts(1, 2, 3, "b"), W.seed_only_status("d"),
            W.next_run_text(dt.date(2026, 11, 13)), W.zones_strip_title("2026-11-13"), W.TOP_PENDING_TEXT,
            W.forward_line("b", 22, 1.0, [0.5, 1.5], 74, 0.2, [-1.0, 1.0], 70.0, 0.3, 0.4)]
    out += _zone_served()
    for cat, kinds in CR.LEG_KINDS.items():
        for key in kinds:
            for v in (None, True, False, 1.5, -2.0, "strong", {"tier": "steady", "accelerating": True},
                      {"score": 75.0, "ranked": True}):
                out.append(W.leg_text(cat, key, v))
    return out


def _zone_served():
    """2026-11-12 (pkzone spec §3.6): every 🔔 sentence — a live-state payload with a stale line and one log row per
    blocked-push reason, the push body, the rules line and each helper's branches."""
    from long_term_list import zone_watch as ZW
    seed = SD.load()
    ent = SD.pankaj_entries(seed)["TSM"]
    session = "2026-11-17"
    reaches, results = {}, {}
    for i, (why, state) in enumerate([(k, None) for k in W.ZONE_LOG_NOT_SENT] + [(None, k) for k in W.ZONE_RESULT_TEXT]
                                     + [(None, None), (None, "dup")]):
        reaches[f"TSM|Agg{i}"] = {"symbol": "TSM", "zone": "Agg", "lo": 400.0, "hi": 410.0, "price": 405.0,
                                  "at_iso": f"t{i:02d}", "at_hhmm": "10:00", "tier": "A", "push_reason": why}
        if state:
            results[f"TSM|Agg{i}"] = {"state": state}
    day = {"session": session, "as_of_hhmm": "10:35", "reason": "no_snapshot", "n_stale": 3, "n_names": 40,
           "prev_session": "2026-11-16", "reaches": reaches, "results": results,
           "rows": {"TSM": {"basis": "live", "price": 406.0, "date": session, "in": ["Agg"]},
                    "META": {"basis": "close", "price": 623.6, "date": "2026-11-16", "in": ["C1"]}}}
    pl = P.build_payload(seed, {}, [], [], {}, now=dt.datetime(2026, 11, 17, 10, 36), owner=True, zone_live=day,
                         zone_day=day, log_session=session)
    alert = pl["zones"]["alert"]
    assert alert["stale_text"] and len(alert["log"]) == len(reaches)
    out = list(_strings(alert))
    out += list(W.ZONE_RESULT_TEXT.values()) + list(W.ZONE_LOG_NOT_SENT.values())
    out += [W.zone_reason_text(k, "10:35") or "" for k in ("no_snapshot", "window", "off", "kind", "no_hook",
                                                           "no_store")]
    out += [W.zone_alert_as_of(True, "10:35"), W.zone_alert_as_of(False, close_date="2026-11-16"),
            W.zone_alert_as_of(False), W.zone_now_text("live", 1.0, "10:00", "Agg", 1, 2, "A"),
            W.zone_now_text("close", 1.0, "2026-11-16", "Agg", 1, 2, None), W.zone_log_title(session),
            W.zone_log_text(1.0, "Agg", 1, 2, "A"), W.zone_log_empty(session), W.zone_push_text(),
            W.zone_stale_text(1, 40, "2026-11-16") or "", W.zone_push_title("TSM", "Agg"),
            W.zone_push_line("TSM", 1.0, "Agg", 1, 2, "A", "8.8", " · pre-mkt"), W.zone_rule_text(),
            W.pushed_text(rings=True), W.pushed_text(rings=False)]
    p = ZW.compose("TSM", dict(ent, action="Buy CL1"), "Agg", 405.0, session, "premarket")
    out += [p["title"], p["body"]]
    return out


def test_NEGATIVE_no_buy_anywhere_in_the_zone_push_2026_11_12():
    from long_term_list import zone_watch as ZW
    ent = SD.pankaj_entries(SD.load())["TSM"]
    p = ZW.compose("TSM", dict(ent, action="Buy CL1"), "Agg", 405.0, "2026-11-17", "rth")
    assert not re.search("buy", p["title"] + p["body"], re.I) and W.NOT_A_SIGNAL not in p["body"]


def _strip_allowed(s: str) -> str:
    return s.replace(W.NOT_A_SIGNAL, "")


def test_negative_no_trading_verbs_in_served_strings():
    bad = [s for s in _served() if BANNED.search(_strip_allowed(s))]
    assert not bad, bad[:5]


def test_negative_no_trading_verbs_in_words_source():
    src = (BACKEND / "long_term_list" / "words.py").read_text(encoding="utf-8")
    src = src.replace('"' + W.NOT_A_SIGNAL + '"', "")
    assert not BANNED.search(src), BANNED.search(src)


def test_negative_never_the_rebound_word():
    assert not [s for s in _served() if REBOUND.search(s)]
    for f in (BACKEND / "long_term_list").glob("*.py"):
        assert not REBOUND.search(f.read_text(encoding="utf-8")), f.name


def test_negative_no_attribution_words_anywhere():
    files = list((BACKEND / "long_term_list").rglob("*.py")) + list((BACKEND / "long_term_list").rglob("*.json"))
    files += list(FIX.rglob("*.json")) + [Path(__file__).parent / "fixtures" / "long_term_list_payload_golden.json"]
    files += [REPO / "docs" / "chart_maps" / "long_term_criteria_2026_11_12.md"]
    files += list(Path(__file__).parent.glob("test_long_term_list_*.py"))
    assert any(f.name == "seed_2026_11_12.json" for f in files)
    for f in files:
        if f.exists():
            assert not ATTRIBUTION.search(f.read_text(encoding="utf-8")), f
    assert not [s for s in _served() if ATTRIBUTION.search(s)]


def test_regexes_are_live():
    assert BANNED.search("an entry here") and not BANNED.search(_strip_allowed(W.NOT_A_SIGNAL))
    assert ATTRIBUTION.search("Big " + "Bull") and REBOUND.search("a " + "bou" + "nce")


def test_bonde_caveat_follows_bonde_measured(monkeypatch):
    from sepa import bonde
    m = copy.deepcopy(bonde.MEASURED)
    assert f"{m['lift_21d']:+.2f}pp" in W.caveat("bonde")
    m["lift_21d"] = -9.99
    m["lift_ci"] = (-12.0, -8.0)
    monkeypatch.setattr(bonde, "MEASURED", m)
    txt = W.caveat("bonde")
    assert "-9.99pp" in txt and "CI -12.00…-8.00" in txt


def test_sales_text_dates_never_invented():
    assert W.sales_text(44.7, "strong", "2026-09-30", "2026-11-08") == \
        "Sales +44.7% y/y · tier strong · quarter ended 2026-09-30 · read 2026-11-08"
    t = W.sales_text(44.7, "strong", None, "2026-11-08")
    assert "quarter ended" not in t and t == "Sales +44.7% y/y · tier strong · read 2026-11-08"
    assert W.sales_text() == "—"
    assert W.sales_text(None, "steady") == "Tier steady"


def test_numbers_in_words_come_from_constants(monkeypatch):
    monkeypatch.setattr(C, "QUIET_MIN_PCT_BELOW_HIGH", 12.0)
    import importlib
    w2 = importlib.reload(W)
    try:
        assert "(needs ≥ 12%)" in w2.leg_text("quiet_strong", "pct_below_high", 8.2)
    finally:
        monkeypatch.undo()
        importlib.reload(W)


def test_liabilities_never_called_debt():
    t = W.leg_text("quiet_strong", "liab_to_equity", 0.9)
    assert t.startswith("Liabilities / equity") and "debt" not in t.lower()


def test_owner_only_text_and_note():
    assert W.OWNER_ONLY_TEXT == "📅 Long Term is a private list — shown to the account owner only."
    assert W.NOTE.endswith(W.NOT_A_SIGNAL) and "UNMEASURED" in W.NOTE
