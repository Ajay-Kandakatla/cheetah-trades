"""⏰ Time-window glow (2026-11-24) — chart_maps/gajjala/time_windows.py + GET /chart-maps/gajjala/time-windows.

Ajay 2026-11-24, verbatim: "We did some research yesterday about highest price action time 33% was after hours can you
add a reminder of that somwhere for me like radiating when we enter those timings".

Pins: every served number == the shipped study file (field for field) and == the study's report.md figures; the
additive per-sample keys agree with the original keys; a closed day → closed:true; a half day drops the ⏰ Second wave
and says so; a missing / corrupt / malformed file → the fault shape (never a raise, never a 500); GG's first-15 rule and
the 🧨 Divergence after-hours read come from their constants by name; the module types none of the study's numbers.
NEGATIVES throughout.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import time_windows as TW

ET = ZoneInfo("America/New_York")
TUE = datetime(2026, 11, 24, 10, 0, tzinfo=ET)        # a full session
HALF = datetime(2026, 11, 27, 10, 0, tzinfo=ET)       # the house calendar's half day (HALF_DAYS)
SAT = datetime(2026, 11, 28, 10, 0, tzinfo=ET)
THANKS = datetime(2026, 11, 26, 10, 0, tzinfo=ET)     # ALL_HOLIDAYS
ADMIN = "ajaykandakatla@gmail.com"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    TW._load.cache_clear()
    yield
    TW._load.cache_clear()


def _data() -> dict:
    return json.loads(TW.DATA_PATH.read_text(encoding="utf-8"))


def _row(tbl, bucket):
    return next(r for r in tbl if r["bucket"] == bucket)


def _write(tmp_path: Path, obj) -> Path:
    p = tmp_path / "winner_time_of_day_2026_11_22.json"
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return p


# ── the file ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_file_ships_with_its_script():
    assert TW.DATA_PATH.exists()
    script = Path(__file__).resolve().parents[1] / "scripts" / "winner_time_of_day_2026_11_22.py"
    src = script.read_text(encoding="utf-8")
    assert "burst_quarter_k" in src and "FLOAT_MAX_SHARES" in src and "W40_HIGH_MULT" in src


def test_the_additive_quarter_counts_agree_with_the_original_keys():
    """The script's added 15-minute counts re-add to the study's own bucket counts and hourly shares — every sample."""
    d = _data()
    for name, s in d.items():
        for key in ("burst", "peak"):
            q = s[f"{key}_quarter_k"]
            n = s[key][0]["n"]
            assert sum(q.values()) == n, (name, key)
            for r in s[key]:
                a, b = TW._clock(r["bucket"])
                assert TW._slot_sum(q, a, b) == r["k"], (name, key, r["bucket"])
            for hh, pct in s[f"{key}_hourly"].items():
                k = TW._slot_sum(q, TW._hm(hh), TW._hm(hh) + 60)
                assert round(100 * k / n, 1) == pct, (name, key, hh)


def test_NEGATIVE_a_moved_count_breaks_the_agreement():
    d = _data()
    q = dict(d[TW.SAMPLE]["burst_quarter_k"])
    q["09:30"] += 1
    a, b = TW._clock(TW.W1_BUCKET)
    assert TW._slot_sum(q, a, b) != _row(d[TW.SAMPLE]["burst"], TW.W1_BUCKET)["k"]


# ── the numbers == the file, field for field ─────────────────────────────────────────────────────────────────────────
def test_every_served_number_reads_the_file():
    d = _data()
    s = d[TW.SAMPLE]
    x = TW.numbers(d)
    b1 = _row(s["burst"], TW.W1_BUCKET)
    ah = _row(s["peak"], TW.AH_BUCKET)
    n = b1["n"]
    assert x["w1_burst_pct"] == b1["pct"]
    assert x["w1_clock_pct"] == b1["null_pct"]
    assert x["w1_multiple"] == round((b1["k"] / n) / (60 / 630), 1)
    assert x["first_pct"] == round(100 * s["burst_quarter_k"]["09:30"] / n, 1)
    assert x["w2_burst_pct"] == round(100 * sum(v for k, v in s["burst_quarter_k"].items() if "15:00" <= k < "17:00") / n, 1)
    assert x["busiest_hour"] == max(s["peak_hourly"], key=s["peak_hourly"].get)
    assert x["busiest_pct"] == s["peak_hourly"][x["busiest_hour"]]
    assert (x["ah_pct"], x["ah_clock_pct"], [x["ah_lo"], x["ah_hi"]]) == (ah["pct"], ah["null_pct"], ah["ci"])
    for k in ("n_days", "symbols", "first_day", "last_day", "float_max_shares", "min_high_gain_pct", "burst_window_min"):
        assert x[k] == s[k], k


def test_the_numbers_match_the_study_report():
    """report.md (eod-audits/research/2026-11-22_winner_time_of_day) — the figures the main session quoted."""
    x = TW.numbers(_data())
    assert (x["w1_burst_pct"], x["w1_multiple"], x["w1_clock_pct"]) == (33.8, 3.5, 9.5)
    assert x["first_pct"] == 20.8
    assert x["w2_burst_pct"] == 22.7
    assert (x["busiest_hour"], x["busiest_end"], x["busiest_pct"], x["busiest_in_w2"]) == ("16:00", "17:00", 15.0, True)
    assert (x["ah_pct"], x["ah_clock_pct"], x["ah_share"]) == (39.0, 38.1, "fair")
    assert (x["n_days"], x["symbols"], x["first_day"], x["last_day"]) == (1457, 413, "2026-05-28", "2026-11-16")
    assert (x["float_max_shares"], x["min_high_gain_pct"], x["burst_window_min"]) == (1e7, 40, 30)


def test_the_windows_and_sentences():
    p = TW.build(TUE)
    assert p["kind"] == "gajjala_time_windows" and p["date"] == "2026-11-24" and p["state"] == "ok"
    assert p["closed"] is False and p["half_day"] is False and p["note"] is None and p["fault_text"] is None
    w1, w2 = p["windows"]
    assert (w1["key"], w1["start"], w1["end"], w1["label"]) == ("burst_window", "09:30", "10:30", "⏰ Burst window")
    assert (w2["key"], w2["start"], w2["end"], w2["label"]) == ("second_wave", "15:00", "17:00", "⏰ Second wave")
    for frag in ("33.8%", "30-minute burst", "3.5×", "9.5%", "09:30–20:00", "20.8%", "09:30–09:45",
                 f"GG's first {GC.NO_TRADE_AFTER_OPEN_MIN} minutes"):
        assert frag in w1["text"], frag
    ah = GC.DIVERGENCE_IS["ah"]
    for frag in ("22.7%", "16:00–17:00 is the busiest hour", "15.0%", "39.0%", "38.1%", "about its fair share",
                 "🧨 Divergence", ah["word"], f"{ah['trades']} trades", "−8.93%", "[−15.60, −3.13]",
                 "2026-10-13 → 2026-11-13"):
        assert frag in w2["text"], frag
    src = p["source_text"]
    for frag in ("1,457 days / 413 names", "float ≤ 10M shares", "2026-05-28 → 2026-11-16", "+40%", TW.TAIL):
        assert frag in src, frag
    assert TW.TAIL == "Descriptive timing, not an entry rule. UNMEASURED as a trade signal. Not advice."


def test_NEGATIVE_no_b_word_and_no_admin_email_on_any_served_text():
    for now in (TUE, HALF, SAT):
        blob = json.dumps(TW.build(now), ensure_ascii=False)
        assert not re.search(r"bounce", blob, re.I)
        assert ADMIN not in blob


# ── constants by name ────────────────────────────────────────────────────────────────────────────────────────────────
def test_first_minutes_rule_reads_the_constant(monkeypatch):
    d = _data()
    q, n = d[TW.SAMPLE]["burst_quarter_k"], d[TW.SAMPLE]["burst"][0]["n"]
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 30)
    x = TW.numbers(d)
    assert x["first_pct"] == round(100 * (q["09:30"] + q["09:45"]) / n, 1) and x["first_end"] == "10:00"
    assert "GG's first 30 minutes" in TW._w1_text(x)


def test_NEGATIVE_first_minutes_off_the_slot_grid_drops_the_clause(monkeypatch):
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 20)
    x = TW.numbers(_data())
    assert x["first_pct"] is None
    assert "GG's first" not in TW._w1_text(x)


def test_the_divergence_line_reads_the_served_constant(monkeypatch):
    ah = dict(GC.DIVERGENCE_IS["ah"], word="MADE MONEY", trades=99)
    monkeypatch.setattr(GC, "DIVERGENCE_IS", {**GC.DIVERGENCE_IS, "ah": ah})
    t = TW.build(TUE)["windows"][1]["text"]
    assert "MADE MONEY" in t and "99 trades" in t and "LOST MONEY" not in t


def test_NEGATIVE_fair_share_word_follows_the_ci():
    d = _data()
    s = d[TW.SAMPLE]
    r = _row(s["peak"], TW.AH_BUCKET)
    r["ci"] = [r["null_pct"] + 1, r["null_pct"] + 5]
    x = TW.numbers(d)
    assert x["ah_share"] == "more" and "more than its share" in TW._ah_words(x)
    r["ci"] = [r["null_pct"] - 5, r["null_pct"] - 1]
    assert TW.numbers(d)["ah_share"] == "less"


def test_NEGATIVE_busiest_hour_outside_w2_drops_the_busiest_clause():
    d = _data()
    d[TW.SAMPLE]["peak_hourly"]["10:00"] = 99.0
    x = TW.numbers(d)
    assert x["busiest_in_w2"] is False
    assert "busiest hour" not in TW._w2_text(x)


# ── closed / half day ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now,reason", [(SAT, "weekend"), (THANKS, "holiday 2026-11-26")])
def test_closed_day_serves_closed_true(now, reason):
    p = TW.build(now)
    assert p["closed"] is True and p["closed_reason"] == reason
    assert len(p["windows"]) == 2                       # listed, never glowed (the FE reads `closed`)


def test_NEGATIVE_a_session_day_is_not_closed():
    p = TW.build(TUE)
    assert p["closed"] is False and p["closed_reason"] is None


def test_half_day_drops_the_second_wave_and_says_so():
    p = TW.build(HALF)
    assert p["half_day"] is True and p["closed"] is False
    assert [w["key"] for w in p["windows"]] == ["burst_window"]
    from catalysts.medical.reaction import rth_close_time
    close = rth_close_time(HALF.date()).strftime("%H:%M")
    assert close in p["note"] and "⏰ Second wave 15:00–17:00" in p["note"] and "not shown today" in p["note"]
    assert p["source_text"].endswith(p["note"])


def test_NEGATIVE_half_day_reads_the_house_calendar(monkeypatch):
    import supply_demand.timeframes as TF
    monkeypatch.setattr(TF, "HALF_DAYS", set())
    p = TW.build(HALF)
    assert p["half_day"] is False and len(p["windows"]) == 2 and p["note"] is None
    monkeypatch.setattr(TF, "HALF_DAYS", {"2026-11-24"})
    p = TW.build(TUE)
    assert p["half_day"] is True and [w["key"] for w in p["windows"]] == ["burst_window"]


# ── the fault shape ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("content", [None, "{not json", "[1, 2]", "{}", '{"B_w40_universe": {"burst": []}}'])
def test_NEGATIVE_missing_or_corrupt_file_serves_the_fault_shape(tmp_path, content):
    path = tmp_path / "absent.json" if content is None else _write(tmp_path, content)
    p = TW.build(TUE, path=path)
    assert p["state"] == "fault" and p["windows"] == [] and p["source_text"] is None
    assert p["fault_text"] == TW.FAULT_TEXT and p["kind"] == TW.KIND and p["date"] == "2026-11-24"


def test_NEGATIVE_a_dropped_additive_key_is_a_fault(tmp_path):
    d = _data()
    del d[TW.SAMPLE]["burst_quarter_k"]
    assert TW.build(TUE, path=_write(tmp_path, d))["state"] == "fault"


def test_the_file_is_read_once():
    TW.build(TUE)
    TW.build(SAT)
    TW.build(HALF)
    info = TW._load.cache_info()
    assert info.misses == 1 and info.hits == 2


# ── the route ────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as API
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def test_route_serves_the_block(client):
    r = client.get(TW.API_PATH)
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] == TW.KIND and isinstance(j["windows"], list) and set(j) >= {"date", "closed", "windows", "source_text"}
    if j["state"] == "ok" and not j["half_day"]:
        assert [w["key"] for w in j["windows"]] == [TW.W1_KEY, TW.W2_KEY]


def test_NEGATIVE_route_missing_file_is_200_fault(client, monkeypatch, tmp_path):
    monkeypatch.setattr(TW, "DATA_PATH", tmp_path / "gone.json")
    r = client.get(TW.API_PATH)
    assert r.status_code == 200 and r.json()["state"] == "fault" and r.json()["windows"] == []


def test_NEGATIVE_route_a_raising_build_is_200_fault(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(TW, "build", boom)
    r = client.get(TW.API_PATH)
    assert r.status_code == 200 and r.json()["state"] == "fault"


def test_route_path_literal_and_no_board_key():
    from chart_maps import api as API
    src = Path(API.__file__).read_text(encoding="utf-8")
    assert f'@router.get("{TW.API_PATH}")' in src
    tab_src = (Path(TW.__file__).parent / "tab.py").read_text(encoding="utf-8")
    assert "time_windows" not in tab_src                # NO new key on the board payload (goldens untouched)


# ── source guard: the module types none of the study's numbers ──────────────────────────────────────────────────────
STUDY_LITERALS = ["33.8", "3.5", "9.5", "20.8", "22.7", "15.0", "39.0", "38.1", "1457", "1,457", "413", "2026-05-28",
                  "2026-11-16", "8.93", "15.60", "3.13", "1e7", "10M", "+40", "630", "36.5", "41.5"]


def _hits(src: str) -> list:
    return [lit for lit in STUDY_LITERALS if lit in src]


def test_the_module_types_no_study_number():
    src = Path(TW.__file__).read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    code = re.sub(r'""".*?"""', "", code, flags=re.S)       # docstrings may quote the ask
    assert _hits(code) == []


def test_NEGATIVE_the_guard_catches_a_typed_number():
    assert _hits('t = "33.8% of bursts, 1,457 days"') == ["33.8", "1,457"]
