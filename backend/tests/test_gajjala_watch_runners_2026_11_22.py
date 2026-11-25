"""📅 ran last session + 📅 runs today — the ONE engine (spec watch_org rev 4 §3.2 / §3.4, WP-BE, 2026-11-22).

Ajay 2026-11-22, verbatim: "use that space between the parent tab of Gajjala and watch tab to be for previous day runners
but remove them if they don’t run the current day" · his answer: "+40% vs prior close (Recommended)" (the 09:30–20:00
high ≥ +40% over the prior close, the day's peak not premarket — his 11-21 winner rule).

Fixture numbers are copied from the read-only probe of 2026-11-22 (gajjala_scan / gajjala_reads, Fri 11-20 and Thu 11-19).
NEGATIVES: NXAT / INHD / SVRE 11-18 (premarket peaks) never count; 39.99 never prints "+40"; today 24.96 is
`not_running` and prints "+24.9%" [D5]; a not-read name is never counted as running [D4]; a stale pass stamp removes
nothing [D6]; junk numbers / another date's bars are ignored; every fault fails soft; the OFF switch reads nothing; no
look-ahead 🏆; source guards.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runners as RN
from chart_maps.gajjala_watch import tags as TG
from chart_maps.replays import constants as RC
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
FRI, THU, MON = date(2026, 11, 20), date(2026, 11, 19), date(2026, 11, 23)
FRI_ISO, THU_ISO = FRI.isoformat(), THU.isoformat()
B_WORD = re.compile("b" + "ounc", re.I)
SRC = Path(RN.__file__)


# ── fixtures ──────────────────────────────────────────────────────────────────────────────────────────────────────
def bar(day, hhmm, h, s=None, c=None):
    d = {"t": f"{day} {hhmm}", "o": h, "h": h, "l": h, "c": c if c is not None else h, "v": 1000.0}
    if s:
        d["s"] = s
    return d


def rdoc(day, sym, bars, *, at=None, shares=None):
    d = {"_id": ST.key(day, sym), "date": day, "symbol": sym, "tile": {"bars5": list(bars)}}
    if at is not None:
        d["at"] = at
    if shares is not None:
        d["ctx"] = {"float": {"shares": shares, "src": "float", "as_of": "2026-11-19"}}
    return d


def sdoc(day, sym, pc, *, day_c=None, tape="rth", held=False):
    return {"_id": ST.key(day, sym), "date": day, "symbol": sym, "held": held,
            "last": {"prev_close": pc, "day_c": day_c, "tape_session": tape}}


def run_bars(day, *, pm, hi, peak_t="13:00", peak_s=None, close=None):
    """A minimal session: a premarket bar at 09:00, regular bars at 09:35 / 16:00, the peak bar, an after-hours bar."""
    out = [bar(day, "09:00", pm, s=C.BAR_PRE), bar(day, "09:35", min(hi, pm) * 0.99 or hi),
           bar(day, "16:00", min(hi, close or hi), c=close)]
    out.append(bar(day, peak_t, hi, s=peak_s))
    out.append(bar(day, "20:00", min(hi, close or hi) * 0.98, s=C.BAR_AH))
    return out


# probe 2026-11-22 (Fri 11-20 / Thu 11-19)
MEDS_PC, MEDS_HI, MEDS_PM, MEDS_DAYC = 0.7277, 1.93, 1.22, 1.34


def meds_bars():
    return [bar(FRI_ISO, "09:00", MEDS_PM, s="pre"), bar(FRI_ISO, "09:35", 1.27),
            bar(FRI_ISO, "16:00", 1.40, c=1.325), bar(FRI_ISO, "17:45", MEDS_HI, s="ah"),
            bar(FRI_ISO, "20:00", 1.6, s="ah")]


def _ran(sym, pc, bars, *, day=FRI, day_c=None, tape="rth"):
    iso = day.isoformat()
    return RN.ran_of(sdoc(iso, sym, pc, day_c=day_c, tape=tape), rdoc(iso, sym, bars), day)


class Rec(FakeColl):
    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail=fail)
        self.finds, self.find_ones = [], []

    def find(self, q=None, projection=None):
        self.finds.append((q, projection))
        return super().find(q, projection)

    def find_one(self, q=None, projection=None):
        self.find_ones.append(q)
        return super().find_one(q, projection)


class World:
    def __init__(self, scan=(), reads=(), state=(), fail=()):
        self.c = {n: Rec(list(docs), fail=(n in fail))
                  for n, docs in ((ST.SCAN, scan), (ST.READS, reads), (ST.STATE, state))}
        self.st = ST.GajjalaStore(dict(self.c))

    def n(self, name):
        return len(self.c[name].finds) + len(self.c[name].find_ones)


def _utc(et_dt):
    return et_dt.astimezone(timezone.utc).replace(tzinfo=None)                      # naive UTC, as Mongo hands back


NOW_CUT = datetime(2026, 11, 20, 10, 5, tzinfo=ET)
NOW_PRE = datetime(2026, 11, 20, 9, 44, tzinfo=ET)
FRESH = _utc(NOW_CUT - timedelta(seconds=60))


def thu_world(*, today=True, at=FRESH, broker=("BRK",), extra_today=(), fail=()):
    """Thu 11-19 runners judged on Fri 11-20: RUNA runs again, RUNB does not, RUNC has no read today, BRK is 🚫,
    PMPK peaked premarket, LOW stayed under +40, NOBR has no bars, HELD is held."""
    scan = [sdoc(THU_ISO, "RUNA", 1.0, day_c=1.5, tape="afterhours"),
            sdoc(THU_ISO, "RUNB", 1.0, day_c=1.2, tape="afterhours"),
            sdoc(THU_ISO, "RUNC", 1.0, day_c=1.0, tape="afterhours"),
            sdoc(THU_ISO, "BRK", 1.0, day_c=2.0, tape="afterhours"),
            sdoc(THU_ISO, "PMPK", 1.0), sdoc(THU_ISO, "LOW", 1.0), sdoc(THU_ISO, "NOBR", 1.0),
            sdoc(THU_ISO, "HELD", 1.0, held=True)]
    reads = [rdoc(THU_ISO, "RUNA", run_bars(THU_ISO, pm=1.1, hi=2.0), shares=4_000_000),
             rdoc(THU_ISO, "RUNB", run_bars(THU_ISO, pm=1.1, hi=1.6)),
             rdoc(THU_ISO, "RUNC", run_bars(THU_ISO, pm=1.1, hi=1.45)),
             rdoc(THU_ISO, "BRK", run_bars(THU_ISO, pm=1.1, hi=3.0)),
             rdoc(THU_ISO, "PMPK", run_bars(THU_ISO, pm=3.0, hi=2.0)),
             rdoc(THU_ISO, "LOW", run_bars(THU_ISO, pm=1.1, hi=1.3)),
             rdoc(THU_ISO, "HELD", run_bars(THU_ISO, pm=1.1, hi=5.0))]
    if today:
        tb = lambda hi: [bar(FRI_ISO, "09:35", 1.0), bar(FRI_ISO, "09:45", hi), bar(FRI_ISO, "10:05", 1.0)]   # noqa: E731
        reads += [rdoc(FRI_ISO, "RUNA", tb(1.9), at=at, shares=4_100_000),          # +26.67 vs 1.5 → running
                  rdoc(FRI_ISO, "RUNB", tb(1.2), at=at),                            # +0 vs 1.2 → not running
                  rdoc(FRI_ISO, "BRK", tb(2.6), at=at)]                             # +30 vs 2.0 → running
        reads += list(extra_today)
    state = [{"_id": ST.BROKER_STATE_ID, "added": list(broker), "removed": []}]
    return World(scan=scan, reads=reads, state=state, fail=fail)


@pytest.fixture(autouse=True)
def no_replays_disk(monkeypatch):
    """No test reads the replays folder: the 🏆 index is handed in (`past=`) or empty."""
    from chart_maps.replays import store as RS
    monkeypatch.setattr(RS, "_past_index", lambda r: {})
    yield


# ── the 📅 rule ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_meds_counts_with_the_end_of_day_peak_words():
    r = _ran("MEDS", MEDS_PC, meds_bars(), day_c=MEDS_DAYC, tape="afterhours")
    assert r["counts"] is True and r["premarket_peak"] is False
    assert r["text"] == "📅 ran Fri +165% (🌙 end of day peak)"
    assert r["peak_et"] == "17:40" and r["timing"] == "eod" and r["timing_text"] == RC.WIN_TIMING_WORDS["eod"]
    assert r["run_pct"] == round((MEDS_HI / MEDS_PC - 1) * 100, C.RAN_PCT_ROUND)
    assert r["reg_close"] == MEDS_DAYC and r["date"] == FRI_ISO and r["day"] == "Fri"
    assert "+165.2%" in r["title"] and r["title"].endswith(C.ORG_NOTE) and "09:30–20:00" in r["title"]
    assert set(r) == {"date", "day", "prev_close", "high", "run_pct", "peak_et", "timing", "timing_text",
                      "pm_high_pct", "premarket_peak", "counts", "reg_close", "text", "title"}


def test_zjk_first_hour_akan_tie_labt_and_svre_after_the_close():
    zjk = _ran("ZJK", 0.7966, [bar(FRI_ISO, "09:00", 1.0, s="pre"), bar(FRI_ISO, "09:55", 1.6399)])
    assert zjk["counts"] and zjk["timing"] == "first_hour" and zjk["text"] == "📅 ran Fri +106% (🌅 first hour peak)"
    akan = _ran("AKAN", 3.43, [bar(FRI_ISO, "08:00", 5.6, s="pre"), bar(FRI_ISO, "10:50", 5.6)])
    assert akan["counts"] is True and akan["premarket_peak"] is False                 # a tie is NOT a premarket peak
    labt = _ran("LABT", 0.2129, [bar(FRI_ISO, "09:20", 0.2981, s="pre"), bar(FRI_ISO, "10:25", 0.3072)])
    assert labt["pm_high_pct"] >= 40 and labt["counts"] is True
    svre = _ran("SVRE", 0.8647, [bar(THU_ISO, "09:00", 0.96, s="pre"), bar(THU_ISO, "16:00", 1.12, c=1.115),
                                 bar(THU_ISO, "16:05", 1.28, s="ah")], day=THU, day_c=1.12, tape="afterhours")
    assert svre["counts"] and svre["peak_et"] == "16:00" and svre["timing"] == "eod"
    assert svre["text"] == "📅 ran Thu +48% (🌙 end of day peak)"


def test_azio_edge_counts_and_every_compare_is_at_the_scanner_rounding():
    azio = _ran("AZIO", 0.4015, [bar(FRI_ISO, "09:00", 0.4015, s="pre"), bar(FRI_ISO, "12:05", 0.5621)])
    assert azio["run_pct"] == 40.0 and azio["counts"] is True and azio["text"] == "📅 ran Fri +40% (☀️ intraday peak)"
    raw = (1.3999999999 / 1.0 - 1) * 100
    assert raw < C.RAN_MIN_PCT                                                          # raw float is under the bar …
    edge = _ran("EDGE", 1.0, [bar(FRI_ISO, "12:05", 1.3999999999)])
    assert edge["run_pct"] == 40.0 and edge["counts"] is True                          # … compared at RAN_PCT_ROUND


@pytest.mark.parametrize("stamp,start,bucket", [("10:30", "10:25", "first_hour"), ("10:35", "10:30", "intraday"),
                                               ("20:00", "19:55", "eod"), ("15:05", "15:00", "eod")])
def test_peak_minute_is_the_bar_start(stamp, start, bucket):
    r = _ran("X", 1.0, [bar(FRI_ISO, stamp, 2.0)])
    assert r["peak_et"] == start and r["timing"] == bucket


def test_bar_min_is_the_stored_frame_and_the_first_peak_bar_wins():
    from chart_maps.gajjala import variant as V
    tf, rule = V.GG5.rules[0]                                                           # the frame bars5 is built from
    assert tf == "5m" and rule == f"{C.BAR_MIN}min" and C.BAR_MIN == GC.LEDGER_TAPE_TF_MIN
    r = _ran("X", 1.0, [bar(FRI_ISO, "11:00", 2.0), bar(FRI_ISO, "14:00", 2.0)])
    assert r["peak_et"] == "10:55"


@pytest.mark.parametrize("x,out", [(24.96, "+24.9%"), (25.0, "+25.0%"), (39.96, "+39.9%"), (-3.45, "-3.5%"),
                                   (165.2193, "+165.2%"), (0.29, "+0.2%"), (0.0, "+0.0%")])
def test_pct_show_floors(x, out):
    assert RN.pct_show(x) == out


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "x", True])
def test_NEGATIVE_pct_show_junk_is_none(bad):
    assert RN.pct_show(bad) is None


def test_basis_of_day_c_first_then_the_last_regular_close():
    bars = [bar(FRI_ISO, "15:55", 0.18, c=0.175), bar(FRI_ISO, "16:00", 0.18, c=0.1767), bar(FRI_ISO, "18:50", 0.8373,
                                                                                            s="ah", c=0.5)]
    assert RN.basis_of(sdoc(FRI_ISO, "WETO", 0.4998, day_c=0.1584, tape="afterhours"), bars) == 0.1584
    assert RN.basis_of(sdoc(FRI_ISO, "WETO", 0.4998, day_c=0.1584, tape="rth"), bars) == 0.1767
    assert RN.basis_of(sdoc(FRI_ISO, "WETO", 0.4998, day_c=float("nan"), tape="afterhours"), bars) == 0.1767
    assert RN.basis_of(sdoc(FRI_ISO, "WETO", 0.4998), [bar(FRI_ISO, "18:50", 1.0, s="ah")]) is None


# ── NEGATIVES: the 📅 rule ─────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_nxat_premarket_peak_never_counts():
    r = _ran("NXAT", 0.2237, [bar(FRI_ISO, "08:00", 2.19, s="pre"), bar(FRI_ISO, "09:35", 0.82)],
             day_c=0.548, tape="afterhours")
    assert r["premarket_peak"] is True and r["counts"] is False and r["text"] is None
    assert r["title"].startswith(C.RAN_PM_PEAK_TITLE.split(":")[0].format(date="Fri 11-20"))
    assert "pumped pre market" in r["title"] and "+878.9%" in r["title"]


def test_NEGATIVE_inhd_and_svre_1118_premarket_peaks():
    inhd = _ran("INHD", 2.3, [bar(THU_ISO, "07:00", 4.4, s="pre"), bar(THU_ISO, "10:00", 3.46)], day=THU)
    assert inhd["run_pct"] > 40 and inhd["counts"] is False and inhd["text"] is None
    svre = _ran("SVRE", 0.4098, [bar("2026-11-18", "06:00", 3.1, s="pre"), bar("2026-11-18", "09:55", 1.15)],
                day=date(2026, 11, 18))
    assert svre["counts"] is False and svre["text"] is None
    assert "303" not in json.dumps(svre, ensure_ascii=False)


def test_NEGATIVE_39_99_never_prints_40():
    r = _ran("U", 1.0, [bar(FRI_ISO, "12:00", 1.3999)])
    assert r["run_pct"] == 39.99 and r["counts"] is False and r["text"] is None
    assert "+39.9%" in r["title"] and "+40.0%" not in r["title"] and "under +40%" in r["title"]


def test_NEGATIVE_a_promo_add_at_5_9_has_no_chip():
    r = _ran("STIM", 1.0, [bar(FRI_ISO, "10:00", 1.059)])
    assert r["counts"] is False and r["text"] is None


@pytest.mark.parametrize("pc", [0, -1, float("nan"), None, "x"])
def test_NEGATIVE_junk_prior_close_is_none(pc):
    assert _ran("X", pc, [bar(FRI_ISO, "12:00", 2.0)]) is None


def test_NEGATIVE_junk_bars_and_another_date_are_ignored():
    bars = [bar(FRI_ISO, "12:00", float("nan")), bar(THU_ISO, "12:00", 9.0), {"t": 5, "h": 9}, "junk",
            bar(FRI_ISO, "13:00", 1.5), dict(bar(FRI_ISO, "14:00", 9.0), l=0)]
    r = _ran("X", 1.0, bars)
    assert r["high"] == 1.5 and r["peak_et"] == "12:55"
    assert RN.bars_of({"tile": {"bars5": "junk"}}, FRI_ISO) == [] and RN.bars_of(None, FRI_ISO) == []
    assert _ran("X", 1.0, [bar(THU_ISO, "12:00", 2.0)]) is None                        # no bar of the day → None
    assert _ran("X", 1.0, [bar(FRI_ISO, "08:00", 2.0, s="pre")]) is None               # premarket only → None


def test_NEGATIVE_a_replays_fault_drops_the_peak_words_only(monkeypatch):
    monkeypatch.setattr(RN, "_replays", lambda: None)
    r = _ran("MEDS", MEDS_PC, meds_bars())
    assert r["counts"] and r["timing"] is None and r["text"] == "📅 ran Fri +165%"


# ── "runs today" ──────────────────────────────────────────────────────────────────────────────────────────────────
def _today(bars, *, at=FRESH, basis=1.0, now=NOW_CUT):
    return RN.today_of(rdoc(FRI_ISO, "X", bars, at=at), FRI, basis, RN.cut_at(FRI), now)


def test_today_of_judges_from_the_cut_on_a_fresh_read():
    r = _today([bar(FRI_ISO, "09:40", 1.1), bar(FRI_ISO, "09:45", 1.3)])
    assert r["state"] == "running" and r["today_pct"] == 30.0 and r["text"] == "today +30.0% since 09:30"
    assert r["at_et"] == "10:04"
    assert _today([bar(FRI_ISO, "09:45", 1.25)])["state"] == "running"                # +25.0 exactly → running
    assert _today([bar(FRI_ISO, "09:45", 1.1)])["state"] == "not_running"
    later = _today([bar(FRI_ISO, "09:45", 1.1), bar(FRI_ISO, "10:30", 1.3)])          # stateless: comes back
    assert later["state"] == "running"


def test_today_of_before_the_9_45_bar_judges_nothing():
    assert _today([bar(FRI_ISO, "09:35", 2.0), bar(FRI_ISO, "09:40", 2.0)])["state"] == "not_read"   # late pass: kept
    assert _today([bar(FRI_ISO, "09:30", 2.0, s="pre"), bar(FRI_ISO, "09:45", 1.0, s="pre")])["state"] == "not_read"


def test_NEGATIVE_D5_24_96_is_not_running_and_prints_24_9():
    r = _today([bar(FRI_ISO, "09:45", 1.2496)])
    assert r["state"] == "not_running" and r["today_pct"] == 24.96 and r["text"] == "today +24.9% since 09:30"
    near = _today([bar(FRI_ISO, "09:45", 1.249999)])                                   # 24.9999 at the scanner rounding
    assert near["today_pct"] == 24.9999 and near["state"] == "not_running"
    up = _today([bar(FRI_ISO, "09:45", 1.2499999)])                                    # 24.99999 rounds to 25.0
    assert up["today_pct"] == 25.0 and up["state"] == "running"


def test_NEGATIVE_D6_a_stale_or_missing_pass_stamp_judges_nothing():
    old = _utc(NOW_CUT - timedelta(seconds=C.RUNNERS_STALE_SEC + 1))
    assert _today([bar(FRI_ISO, "09:45", 1.0)], at=old)["state"] == "not_read"
    edge = _utc(NOW_CUT - timedelta(seconds=C.RUNNERS_STALE_SEC))
    assert _today([bar(FRI_ISO, "09:45", 1.0)], at=edge)["state"] == "not_running"
    nodoc = RN.today_of(None, FRI, 1.0, RN.cut_at(FRI), NOW_CUT)
    noat = RN.today_of(rdoc(FRI_ISO, "X", [bar(FRI_ISO, "09:45", 1.0)]), FRI, 1.0, RN.cut_at(FRI), NOW_CUT)
    junk = _today([bar(FRI_ISO, "09:45", 1.0)], at="yesterday")
    for r in (nodoc, noat, junk):
        assert r["state"] == "not_read" and r["text"] == C.RUNNERS_NOT_READ_TEXT and r["today_pct"] is None
    assert _today([bar(FRI_ISO, "09:45", 2.0)], basis=None)["state"] == "not_read"


def test_D6_a_fresh_stamp_with_no_new_bars_is_judged_on_the_bars_it_has():
    r = _today([bar(FRI_ISO, "09:45", 1.4)], at=_utc(NOW_CUT))                       # halted: no bar since 09:45
    assert r["state"] == "running"


# ── clocks ────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now,want", [
    (datetime(2026, 11, 23, 3, 59, tzinfo=ET), (FRI, None, False)),
    (datetime(2026, 11, 23, 4, 0, tzinfo=ET), (FRI, MON, True)),
    (datetime(2026, 11, 23, 20, 6, tzinfo=ET), (MON, None, False)),
    (datetime(2026, 11, 21, 12, 0, tzinfo=ET), (FRI, None, False)),                  # Saturday
    (datetime(2026, 11, 27, 10, 0, tzinfo=ET), (date(2026, 11, 25), date(2026, 11, 27), True)),   # after Thanksgiving
])
def test_runner_day(now, want):
    assert RN.runner_day(now) == want


def test_cut_and_constants_are_the_house_ones():
    assert RN.cut_at(FRI) == PT._mute_end(FRI) and RN.cut_at(FRI).strftime("%H:%M") == PT._mute_end_hhmm()
    assert C.RUNNERS_LEAVE_PCT == GC.SCAN_MIN_CHANGE_PCT
    assert C.RUNNERS_STALE_SEC == 2 * GC.PASS_CADENCE_SEC
    assert RN.clock_words()["stale_min"] == C.RUNNERS_STALE_SEC // 60
    # RE-PINNED 2026-11-24 (spec watchall §3.1, HIS CALL #5) — ✅ "rules" appended LAST; "ran" still never a section
    assert C.SECTION_KEYS == ("yours", "aplus", "auto", "rules") and "ran" not in C.SECTION_KEYS       # [D3]
    assert C.API_RUNNERS_PATH == C.API_PATH + "/runners"
    assert "at" in C.RUNNERS_READ_FIELDS and "tile.bars5" in C.RUNNERS_READ_FIELDS
    assert C.RUNNERS_FOLD_AT_PHONE == 3 and C.PCT_SHOW_PLACES == 1


# ── the strip ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_strip_before_the_cut_lists_by_gain_broker_last():
    w = thu_world()
    out = RN.strip(NOW_PRE, st=w.st)
    assert out["state"] == "ok" and out["cut_active"] is False and out["live"] is True
    assert [r["symbol"] for r in out["rows"]] == ["RUNA", "RUNB", "RUNC", "BRK"]        # 🚫 last, never dropped
    assert out["rows"][-1]["broker_text"] == tab.BROKER_FLAG_TEXT
    assert out["text"] == "4" and out["n"] == 4 and out["no_bars"] == 1 and out["removed"] == []
    assert all(r["today_state"] is None for r in out["rows"])
    assert out["title"] == "📅 Previous day runners — Thu 11-19" and out["day"] == THU_ISO
    assert out["refresh_sec"] == GC.PASS_CADENCE_SEC and out["fold_at"] == C.RUNNERS_FOLD_AT
    assert out["fold_at_phone"] == C.RUNNERS_FOLD_AT_PHONE and out["cut_at"] == "09:45"
    assert out["rows"][0]["run_text"] == "+100%" and out["rows"][0]["float_text"] == "Float 4.0M"
    assert out["as_of_et"] is None and out["stale"] is False
    assert w.n(ST.SCAN) == 1 and w.n(ST.READS) == 1 and w.n(ST.STATE) == 1          # 1 + 1 (+ broker 1)
    json.dumps(out, allow_nan=False)


def test_strip_after_the_cut_removes_the_names_that_do_not_run():
    w = thu_world()
    out = RN.strip(NOW_CUT, st=w.st)
    assert out["cut_active"] is True
    assert [r["symbol"] for r in out["rows"]] == ["RUNA", "RUNC", "BRK"]
    st = {r["symbol"]: r["today_state"] for r in out["rows"]}
    assert st == {"RUNA": "running", "RUNC": "not_read", "BRK": "running"}
    assert out["text"] == "2 running today of 4 · 1 not read yet"
    assert out["n"] == 4 and out["n_running"] == 2 and out["n_not_read"] == 1
    assert [x["symbol"] for x in out["removed"]] == ["RUNB"]
    assert out["removed_text"] == "1 not running today (under +25% since 09:30 ET)"
    assert out["as_of_et"] == "10:04" and out["stale"] is False
    assert out["rows"][0]["float_text"] == "Float 4.1M"                               # today's read first
    assert out["rows"][0]["title"].endswith(" · today +26.6% since 09:30")
    assert w.n(ST.SCAN) == 1 and w.n(ST.READS) == 2 and w.n(ST.STATE) == 1          # + 1 today find
    json.dumps(out, allow_nan=False)


def test_NEGATIVE_D4_a_not_read_name_is_never_counted_running():
    out = RN.strip(NOW_CUT, st=thu_world(today=False).st)
    assert out["n_running"] == 0 and out["n_not_read"] == 4 and out["removed"] == []
    assert out["text"].startswith("0 running today of 4 · 4 not read yet")
    assert "unread" not in out and all(r["today_state"] == "not_read" for r in out["rows"])


def test_NEGATIVE_D6_a_stale_read_removes_nothing():
    at = _utc(datetime(2026, 11, 20, 10, 2, tzinfo=ET))
    out = RN.strip(datetime(2026, 11, 20, 11, 0, tzinfo=ET), st=thu_world(at=at).st)
    assert out["removed"] == [] and all(r["today_state"] == "not_read" for r in out["rows"])
    assert out["stale"] is True and out["as_of_et"] == "10:02"
    assert out["text"] == "0 running today of 4 · 4 not read yet · today's read is from 10:02 ET — nothing removed"


def test_NEGATIVE_D6_one_stale_doc_only_that_name_is_kept_unread():
    old = _utc(NOW_CUT - timedelta(hours=1))
    w = thu_world()
    w.c[ST.READS].docs[ST.key(FRI_ISO, "RUNB")]["at"] = old
    out = RN.strip(NOW_CUT, st=w.st)
    st = {r["symbol"]: r["today_state"] for r in out["rows"]}
    assert st["RUNB"] == "not_read" and out["removed"] == [] and st["RUNA"] == "running"


def test_NEGATIVE_today_read_fault_removes_nothing(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(RN, "read_today", boom)
    out = RN.strip(NOW_CUT, st=thu_world().st)
    assert out["state"] == "ok" and out["removed"] == [] and out["n_not_read"] == 4 and out["stale"] is True


def test_NEGATIVE_scan_read_fault_is_error_with_the_words():
    out = RN.strip(NOW_PRE, st=thu_world(fail=(ST.SCAN,)).st)
    assert out["state"] == "error" and out["text"] == C.RUNNERS_ERROR_TEXT and "rows" not in out
    assert RN.strip(NOW_PRE, st=None)["state"] in ("error", "empty")


def test_NEGATIVE_broker_fault_tags_nobody_hides_nobody(monkeypatch):
    monkeypatch.setattr(ST, "broker_flags", lambda s: (["BRK"], True))
    out = RN.strip(NOW_PRE, st=thu_world().st)
    assert len(out["rows"]) == 4 and all(r["broker_text"] is None for r in out["rows"])
    assert [r["symbol"] for r in out["rows"]] == ["BRK", "RUNA", "RUNB", "RUNC"]        # by gain only


def test_NEGATIVE_replays_fault_no_trophy_no_bucket_strip_answers(monkeypatch):
    monkeypatch.setattr(RN, "_replays", lambda: None)
    out = RN.strip(NOW_PRE, st=thu_world().st)
    assert out["state"] == "ok" and len(out["rows"]) == 4
    assert all(r["timing"] is None and r["past_winner_text"] is None for r in out["rows"])


def test_trophy_only_from_wins_before_the_run_day():
    from chart_maps.replays import store as RS
    sub = RC.WINNER_SUB_KEYS[0]
    card = lambda sym, day, g, f: {"symbol": sym, "days": [day], "kind": "single_day", "close_gain_pct": g,   # noqa: E731
                                   "file": f, "sub": sub}
    idx = RS.past_winner_index([card("RUNA", THU_ISO, 300.0, "a.mp4"), card("RUNA", "2026-11-12", 97.0, "b.mp4"),
                                card("RUNB", FRI_ISO, 50.0, "c.mp4")])
    out = RN.strip(NOW_PRE, st=thu_world().st, past=idx)
    rows = {r["symbol"]: r for r in out["rows"]}
    assert rows["RUNA"]["past_winner_text"] == "🏆 11-12 +97%"
    assert rows["RUNA"]["past_winner_title"].startswith(RC.PAST_WIN_DAY_WORDS)
    assert "300" not in json.dumps(rows["RUNA"], ensure_ascii=False)                   # the run day itself: no
    assert rows["RUNB"]["past_winner_text"] is None                                    # after the run day: no


def test_strip_closed_day_shows_the_last_session_and_never_cuts():
    w = thu_world()
    out = RN.strip(datetime(2026, 11, 19, 21, 0, tzinfo=ET), st=w.st)                 # Thu after the pass close
    assert out["live"] is False and out["cut_active"] is False and out["refresh_sec"] == 0
    assert out["today"] is None and out["day"] == THU_ISO and w.n(ST.READS) == 1


def test_strip_empty_and_off():
    w = World(scan=[sdoc(THU_ISO, "LOW", 1.0)], reads=[rdoc(THU_ISO, "LOW", run_bars(THU_ISO, pm=1.1, hi=1.3))])
    out = RN.strip(NOW_PRE, st=w.st)
    assert out["state"] == "empty" and out["rows"] == [] and out["text"].startswith("No name on Gajjala's scanner Thu")
    none = World()
    RN.strip(NOW_PRE, st=none.st)
    assert none.n(ST.READS) == 0                                                        # no scan names → no reads find


def test_NEGATIVE_off_switch_reads_nothing(monkeypatch):
    monkeypatch.setattr(C, "RUNNERS_STRIP_ON", False)
    w = thu_world()
    assert RN.strip(NOW_CUT, st=w.st) == {"state": "off"}
    assert w.n(ST.SCAN) == w.n(ST.READS) == w.n(ST.STATE) == 0


def test_NEGATIVE_nan_fixture_serializes_strictly():
    w = thu_world()
    w.c[ST.READS].docs[ST.key(THU_ISO, "RUNA")]["tile"]["bars5"].append(bar(THU_ISO, "19:00", float("nan"), s="ah"))
    w.c[ST.SCAN].docs[ST.key(THU_ISO, "RUNB")]["last"]["day_c"] = float("nan")
    json.dumps(RN.strip(NOW_CUT, st=w.st), allow_nan=False)


# ── ran_for (the Watch's one read) ────────────────────────────────────────────────────────────────────────────────
def test_ran_for_is_one_scan_and_one_reads_find_keyed_by_fold():
    w = thu_world()
    out = RN.ran_for(["RUNA", "PMPK", "LOW", "ZZZ"], THU, st=w.st)
    assert set(out) == {"RUNA", "PMPK", "LOW"} and out["RUNA"]["counts"] and not out["PMPK"]["counts"]
    assert w.n(ST.SCAN) == 1 and w.n(ST.READS) == 1
    (q, proj), = w.c[ST.SCAN].finds
    assert q == {"date": {"$in": [THU_ISO]}, "symbol": {"$in": ["RUNA", "PMPK", "LOW", "ZZZ"]}}
    assert proj == C.RUNNERS_SCAN_FIELDS
    (rq, rproj), = w.c[ST.READS].finds
    assert rproj == C.RUNNERS_READ_FIELDS and "HELD" not in json.dumps(rq)
    w2 = thu_world()
    assert RN.ran_for([], THU, st=w2.st) == {} and w2.n(ST.SCAN) == w2.n(ST.READS) == 0


def test_ran_for_finds_a_class_ticker_under_either_spelling():
    """Review 11-22 finding 2: a row spelled BRK-B must find a scan doc stored as BRK.B, and the reverse."""
    for stored, asked in (("ABC.B", "ABC-B"), ("ABC-B", "ABC.B")):
        w = World(scan=[sdoc(THU_ISO, stored, 1.0, day_c=1.5, tape="afterhours")],
                  reads=[rdoc(THU_ISO, stored, run_bars(THU_ISO, pm=1.1, hi=2.0))])
        out = RN.ran_for([asked], THU, st=w.st)
        assert set(out) == {CO.fold(asked)} and out[CO.fold(asked)]["counts"] is True
        (q, _), = w.c[ST.SCAN].finds
        assert set(q["symbol"]["$in"]) == {"ABC.B", "ABC-B"}


def test_NEGATIVE_ran_for_no_double_spelling_for_a_plain_ticker():
    w = thu_world()
    RN.ran_for(["RUNA"], THU, st=w.st)
    (q, _), = w.c[ST.SCAN].finds
    assert q["symbol"]["$in"] == ["RUNA"]


def test_NEGATIVE_held_scan_doc_ignored_everywhere():
    w = thu_world()
    assert "HELD" not in RN.ran_for(["HELD"], THU, st=w.st)
    out = RN.strip(NOW_PRE, st=thu_world().st)
    assert "HELD" not in json.dumps(out) and out["no_bars"] == 1


def test_tags_finders_defaults_unchanged():
    w = World(scan=[sdoc(THU_ISO, "A", 1.0)], reads=[rdoc(THU_ISO, "A", [])])
    TG._find_scan(w.st, [THU_ISO], ["A"])
    TG._find_reads(w.st, [ST.key(THU_ISO, "A")])
    assert w.c[ST.SCAN].finds == [({"date": {"$in": [THU_ISO]}, "symbol": {"$in": ["A"]}}, TG.SCAN_TAG_FIELDS)]
    assert w.c[ST.READS].finds == [({"_id": {"$in": [ST.key(THU_ISO, "A")]}}, TG.TAGS_READ_FIELDS)]
    TG._find_scan(w.st, [THU_ISO], None, fields=C.RUNNERS_SCAN_FIELDS)
    assert w.c[ST.SCAN].finds[-1] == ({"date": {"$in": [THU_ISO]}}, C.RUNNERS_SCAN_FIELDS)
    params = inspect.signature(TG._find_scan).parameters
    assert params["fields"].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(TG._find_reads).parameters["fields"].kind is inspect.Parameter.KEYWORD_ONLY


# ── words + source guards ─────────────────────────────────────────────────────────────────────────────────────────
def test_rules_line_types_no_digit_and_carries_the_constants():
    tree = ast.parse(inspect.getsource(RN))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "rules_line")
    words = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [w for w in words if re.search(r"[0-9]", w)] == []
    line = RN.rules_line()
    for want in ("+40%", "+25%", "09:45", "09:30–20:00", "10 minutes", "UNMEASURED"):
        assert want in line
    from supply_demand import rules_info as RI
    assert line in RI._gajjala_section()["note"]


def test_NEGATIVE_rules_clause_survives_a_broken_module(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.setattr(RN, "rules_line", lambda: 1 / 0)
    assert RI._gg_watch_runners_clause() == ""
    assert "📅 Previous day runners" not in RI._gajjala_section()["note"]


def test_NEGATIVE_no_served_word_says_the_b_word():
    words = [v for k, v in vars(C).items() if k.isupper() and isinstance(v, str)]
    words += [v for k, v in vars(C).items() if k.isupper() and isinstance(v, dict) for v in v.values()
              if isinstance(v, str)]
    assert not any(B_WORD.search(w) for w in words) and not B_WORD.search(SRC.read_text())
    out = RN.strip(NOW_CUT, st=thu_world().st)
    assert not B_WORD.search(json.dumps(out, ensure_ascii=False))


def _imports(path: Path) -> list:
    tree = ast.parse(path.read_text())
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            out.append((n.module or "", [a.name for a in n.names], n.col_offset, n.level))
        elif isinstance(n, ast.Import):
            out += [(a.name, [], n.col_offset, 0) for a in n.names]
    return out


def test_source_guards_no_write_path_no_auto_lazy_replays():
    for mod in ("runners", "sections"):
        path = SRC.parent / f"{mod}.py"
        imps = _imports(path)
        names = [m for m, _n, _c, _l in imps] + [x for _m, ns, _c, _l in imps for x in ns]
        for bad in ("auto", "cross_alerts", "loop"):
            assert bad not in names, (mod, bad)
        src = path.read_text()
        for bad in ("insert_one", "update_one", "replace_one", "delete_", "upsert", "_replace(", "frames_for",
                    "load_intraday", "send("):
            assert bad not in src, (mod, bad)
    top = ast.parse(SRC.read_text()).body
    for n in top:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mod = n.module if isinstance(n, ast.ImportFrom) else n.names[0].name
            assert "replays" not in (mod or "")
    cpath = SRC.parent / "constants.py"
    assert "replays" not in cpath.read_text().split("# ── 🗂 sections")[0] + "".join(
        m for m, _n, _c, _l in _imports(cpath))


def test_NEGATIVE_caps_and_switches_unchanged():
    assert C.MAX_SYMBOLS == GC.GG_WATCH_N and C.AUTO_MAX_SYMBOLS == GC.GG_WATCH_N
    assert C.AUTO_MIN_VOLUME == GC.K11_MIN_SESSION_VOLUME
    # RE-PINNED 2026-11-24 — Ajay "ok remove EMA entry alerts and divergence alerts…": the 👀 cross push ships off
    assert C.AUTO_PUSH_MODE == "off" and C.PUSH_MODE == C.PUSH_MODES[0]
    assert C.AUTO_APLUS_STAYS is True and C.AUTO_APLUS_EVICTS is True
