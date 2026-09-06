"""supply_demand/zone_bounce_alerts — touched a demand level intraday and is
already bouncing (Ajay 2026-09-03, the NTAP morning).

Behavioural tests on the verified NTAP fixture + synthetic names, and
source guards for the wiring (pref default, crontab lines, notifications
page, prefs type, demand_alerts payload kind).
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import zone_bounce_alerts as ZB  # noqa: E402
from supply_demand import demand_alerts as DA       # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 3, 9, 33, tzinfo=ET)          # the 09:33 print

# Verified forensics 2026-09-03: prev close 180.77, 09:30 low 161.00, 09:33 close
# 171.2. The shelf the low hit is a one-touch BROKEN-SUPPLY band 161.78-167.54
# (board geometry); the nearest demand bands sit below at 153.53-158.99.
NTAP_BANDS = [{"kind": "supply", "lo": 161.78, "hi": 167.54, "touches": 1, "strength": 18.0},
              {"kind": "supply", "lo": 173.87, "hi": 180.07, "touches": 1, "strength": 24.0},
              {"kind": "demand", "lo": 153.53, "hi": 158.99, "touches": 1, "strength": 15.0},
              {"kind": "demand", "lo": 146.66, "hi": 151.88, "touches": 1, "strength": 17.0}]
NTAP_SHELF = NTAP_BANDS[0]


class FakeColl:
    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def update_one(self, q, u, upsert=False):
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        d.update(u.get("$set", {}))


def _doc(sym, bands, atr14, prev_close, day="2026-09-03"):
    return {"_id": f"{sym}:{day}", "symbol": sym, "date": day, "geom": "board",
            "bands": bands, "atr14": atr14, "prev_close": prev_close}


def _snap(low, last, prev=None, *, now=NOW, age_sec=30):
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    return {"open": low + 1, "high": last, "low": low, "close": last, "volume": 1e6,
            "change_pct": 0.0, "last_trade_price": last, "last_trade_ts_ms": ts_ns,
            "prev_day_close": prev}


def _capture(monkeypatch, result=None):
    from push import sender
    sent = []

    def fake(owner, payload, kind=None):
        sent.append({"owner": owner, "kind_arg": kind, **payload})
        return result or {"sent": 1, "failed": 0, "total_targets": 1}
    monkeypatch.setattr(sender, "send_to_user", fake)
    return sent


class PassColl(FakeColl):
    """alert_pass_latest: one replace_one per pass."""

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


def _run(store, snapshot, caps, *, coll=None, now=NOW, push=True, names=None, low_times=None,
         pass_coll=None):
    return ZB.check_once(push=push, force=True, store=store, snapshot=snapshot, caps=caps,
                         names=names if names is not None else {}, coll=coll or FakeColl(),
                         owner="o@x", now=now, pass_coll=pass_coll,
                         low_times=low_times if low_times is not None else {})   # never the network


# ── the pure read: NTAP ──────────────────────────────────────────────────────
def test_ntap_low_touches_the_broken_supply_shelf_and_the_0933_print_is_a_bounce():
    hit = ZB.read(161.0, 171.2, 180.77, NTAP_SHELF, 4.5)
    assert hit is not None
    assert hit["bounce_pct"] == 6.34 and hit["floor_pct"] == 3.0
    assert hit["strong"] is True and hit["strong_pct"] == 5.59      # 2 x ATR% beats 5%
    assert hit["undercut_pct"] == 0.48                              # low 161 under the 161.78 floor
    assert hit["atr_x"] == 2.3


def test_ntap_demand_bands_below_were_never_touched_only_the_shelf_counts():
    hits = [b for b in NTAP_BANDS if ZB.read(161.0, 171.2, 180.77, b, 4.5)]
    assert hits == [NTAP_SHELF], "158.99 top + 1% = 160.58 < 161; 173.87-180.07 sits above the low"


def test_ntap_with_the_measured_atr_still_fires_but_rides_the_digest():
    # Measured in the container 2026-09-03: ATR14 as of the 09-02 close = 6.907
    # -> floor 4.29%, strong floor 8.58%. 6.34% clears the floor, not strong.
    hit = ZB.read(161.0, 171.2, 180.77, NTAP_SHELF, 6.907)
    assert hit and hit["floor_pct"] == 4.29 and hit["strong"] is False and hit["strong_pct"] == 8.58
    assert ZB.read(161.0, 178.38, 180.77, NTAP_SHELF, 6.907)["strong"] is True   # 09:42 print


# ── the pure read: negatives ─────────────────────────────────────────────────
def test_residence_never_fires_yesterday_must_have_closed_three_percent_above_the_top():
    assert ZB.read(161.0, 171.2, 165.0, NTAP_SHELF, 4.5) is None, "closed inside the band"
    assert ZB.read(161.0, 171.2, 170.0, NTAP_SHELF, 4.5) is None, "2.5% above = still residence"
    assert ZB.read(161.0, 171.2, 172.56, NTAP_SHELF, 4.5) is None, "167.54 x 1.03 = 172.566: not > 3%"
    assert ZB.read(161.0, 171.2, 172.57, NTAP_SHELF, 4.5) is not None


def test_gap_through_and_keep_falling_never_fires():
    assert ZB.read(161.0, 165.0, 180.77, NTAP_SHELF, 4.5) is None, "print still inside the band"
    assert ZB.read(161.0, 167.54, 180.77, NTAP_SHELF, 4.5) is None, "print on the top is not above it"
    assert ZB.read(159.5, 160.0, 180.77, NTAP_SHELF, 4.5) is None, "undercut and no recovery"
    assert ZB.read(150.0, 155.0, 180.77, NTAP_SHELF, 4.5) is None, "fell straight through (>1.5% under)"


def test_touch_needs_the_low_within_one_percent_above_or_one_and_a_half_under():
    band = {"kind": "demand", "lo": 100.0, "hi": 102.0, "touches": 3, "strength": 50.0}
    assert ZB.read(103.0, 108.0, 110.0, band, 0.5) is not None            # 0.98% above the top
    assert ZB.read(103.1, 108.0, 110.0, band, 0.5) is None                # 1.08% above: not a touch
    assert ZB.read(98.5, 108.0, 110.0, band, 0.5) is not None             # 1.5% under the floor
    assert ZB.read(98.4, 108.0, 110.0, band, 0.5) is None                 # 1.6% under: fell through


def test_bounce_below_three_percent_off_the_low_is_not_a_bounce():
    band = {"kind": "demand", "lo": 100.0, "hi": 101.0, "touches": 2, "strength": 40.0}
    assert ZB.read(100.5, 103.0, 110.0, band, 0.5) is None                # +2.49%
    hit = ZB.read(100.5, 103.6, 110.0, band, 0.5)
    assert hit and hit["bounce_pct"] == 3.08 and hit["strong"] is False


def test_atr_floor_raises_the_bar_for_a_volatile_name():
    band = {"kind": "demand", "lo": 99.0, "hi": 100.5, "touches": 2, "strength": 40.0}
    assert ZB.read(100.0, 105.0, 110.0, band, 0.5) is not None            # calm name: +5% is plenty
    assert ZB.read(100.0, 105.0, 110.0, band, 8.0) is None, "ATR 8 on a $100 name: +5% is noise"
    hit = ZB.read(100.0, 109.0, 110.0, band, 8.0)
    assert hit and hit["floor_pct"] == 8.0 and hit["strong"] is False and hit["strong_pct"] == 16.0
    assert ZB.read(100.0, 116.5, 120.0, band, 8.0)["strong"] is True


def test_supply_band_still_overhead_is_not_eligible_but_a_broken_one_is():
    overhead = {"kind": "supply", "lo": 101.0, "hi": 103.0, "touches": 1, "strength": 20.0}
    assert ZB.is_eligible(overhead, 100.0) is False
    assert ZB.is_eligible(overhead, 103.0) is False, "top equal to prev close is not broken"
    assert ZB.is_eligible(overhead, 110.0) is True
    assert ZB.is_eligible({"kind": "demand", "lo": 101.0, "hi": 103.0}, 100.0) is True
    assert ZB.is_eligible({"kind": "supply", "lo": None, "hi": 103.0}, 110.0) is False
    assert ZB.is_eligible({"kind": "demand", "lo": 105.0, "hi": 103.0}, 110.0) is False   # inverted
    # Same geometry, prev close BELOW the shelf: the low touches, the print is
    # above, the bounce is big — and it is still None, because it is resistance.
    assert ZB.read(101.5, 108.0, 100.0, overhead, 0.5) is None
    assert ZB.read(101.5, 108.0, 110.0, overhead, 0.5) is not None


def test_garbage_inputs_never_crash():
    assert ZB.read(None, 171.2, 180.77, NTAP_SHELF, 4.5) is None
    assert ZB.read(161.0, "x", 180.77, NTAP_SHELF, 4.5) is None
    assert ZB.read(161.0, 171.2, 0, NTAP_SHELF, 4.5) is None
    assert ZB.read(161.0, 171.2, 180.77, {}, 4.5) is None
    assert ZB.read(161.0, 171.2, 180.77, NTAP_SHELF, None) is not None, "no ATR = 3% floor"
    assert ZB.read(161.0, 171.2, 180.77, NTAP_SHELF, float("nan"))["floor_pct"] == 3.0


# ── the print ────────────────────────────────────────────────────────────────
def test_print_is_the_last_trade_only_while_fresh_ns_ms_and_seconds_all_understood():
    now_ts = NOW.timestamp()
    fresh_ns = int((now_ts - 30) * 1e9)
    assert ZB.print_from_snapshot({"last_trade_price": 171.2, "last_trade_ts_ms": fresh_ns}, now_ts) == (171.2, False)
    assert ZB.print_from_snapshot({"last_trade_price": 171.2, "last_trade_ts_ms": int((now_ts - 30) * 1e3)}, now_ts) == (171.2, False)
    assert ZB.print_from_snapshot({"last_trade_price": 171.2, "last_trade_ts_ms": now_ts - 30}, now_ts) == (171.2, False)
    stale_ns = int((now_ts - 3 * 3600) * 1e9)                    # the 13:13 Massive lag
    assert ZB.print_from_snapshot({"last_trade_price": 171.2, "last_trade_ts_ms": stale_ns}, now_ts) == (None, True)
    edge = int((now_ts - ZB.STALE_PRINT_SEC - 1) * 1e9)
    assert ZB.print_from_snapshot({"last_trade_price": 171.2, "last_trade_ts_ms": edge}, now_ts) == (None, True)
    assert ZB.print_from_snapshot({"last_trade_price": None, "last_trade_ts_ms": fresh_ns}, now_ts) == (None, True)
    assert ZB.print_from_snapshot({"last_trade_price": 171.2}, now_ts) == (None, True)


def test_stale_print_skips_the_bounce_leg_and_is_counted(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"NTAP": _doc("NTAP", NTAP_BANDS, 4.5, 180.77)}
    out = _run(store, {"NTAP": _snap(161.0, 171.2, 180.77, age_sec=1200)}, {"NTAP": 37.4e9})
    assert out["stale_print"] == 1 and out["priced"] == 0 and out["hits"] == [] and sent == []


# ── messages ─────────────────────────────────────────────────────────────────
def test_state_key_is_symbol_band_day():
    assert ZB.state_key("NTAP", NTAP_SHELF, "2026-09-03") == "NTAP:161.78-167.54:2026-09-03"


def test_digest_is_strongest_first_capped_at_six_with_a_more_line():
    items = [{"symbol": f"S{i}", "print": 100.0 + i, "day_low": 95.0, "cap": 2e9,
              "band": {"kind": "demand", "lo": 94.0, "hi": 96.0, "touches": 2},
              "hit": {"bounce_pct": 3.0 + i * 0.5, "strong": False}} for i in range(8)]
    m = ZB.digest_message(items)
    assert m["title"] == "🪃 Bouncing off demand levels — S7 +6.5% +7 more"
    lines = m["body"].split("\n")
    assert len(lines) == ZB.DIGEST_MAX + 1 and lines[-1] == "+2 more"
    assert lines[0] == "S7 $107 · +6.5% off $94-96 · room: clear runway · demand · $2.0B"
    assert m["kind"] == "zone_bounce_alert" and m["url"] == "/chart-maps?tab=zones"
    assert ZB.digest_message(items[:1])["title"] == "🪃 Bouncing off demand levels — S0 +3.0%"


# ── check_once end to end ────────────────────────────────────────────────────
def test_ntap_2026_09_03_fires_a_single_push_with_the_exact_title_body_url_kind(monkeypatch):
    """Since the phone gate (2026-09-05) the real 09:33 print (171.2, 2.2% above
    the shelf) only LISTS — see test_phone_gate_a_bounce_that_already_ran. The
    exact single is exercised with a print still inside the 1% window: low 160.6
    (0.73% under the floor), print 169.2 (0.99% above the top, +5.35% off the
    low), ATR 3.0 so STRONG (floor 5%) is reachable inside the window."""
    sent = _capture(monkeypatch)
    store = {"NTAP": _doc("NTAP", NTAP_BANDS, 3.0, 180.77)}
    coll = FakeColl()
    out = _run(store, {"NTAP": _snap(160.6, 169.2, 180.77)}, {"NTAP": 37.4e9}, coll=coll,
               names={"NTAP": "NetApp"})
    assert out["ran"] and out["singles"] == 1 and out["digest"] == 0 and out["pushed"] == 1
    assert len(sent) == 1
    m = sent[0]
    assert out["hits"][0]["hit"]["bounce_pct"] == 5.35 and out["hits"][0]["hit"]["strong"] is True
    assert m["title"] == "🪃 NTAP bounced +5.3% off support (old resistance) $161.78-167.54"
    # 173.87-180.07 closed under yesterday's 180.77 = broken = support, not a ceiling: clear runway
    assert m["body"] == ("$169.2 · low $160.6 -> +$8.6 · room: clear runway · broken supply -> support (tested 1x)"
                         " · 2.9x ATR · $37.4B · NetApp")
    assert m["url"] == "/sepa/NTAP?tab=supply" and m["data"]["url"] == m["url"]
    assert m["kind"] == "zone_bounce_alert" and m["kind_arg"] == "zone_bounce_alert"
    assert m["owner"] == "o@x"
    assert list(coll.docs) == ["NTAP:161.78-167.54:2026-09-03"]
    assert coll.docs["NTAP:161.78-167.54:2026-09-03"]["strong"] is True


def test_two_touched_bands_are_spelled_out_in_one_body():
    item = {"symbol": "ZZ", "print": 108.0, "day_low": 100.0, "cap": 5e9, "name": None,
            "band": {"kind": "supply", "lo": 100.5, "hi": 102.0, "touches": 1},
            "bands": [{"kind": "supply", "lo": 100.5, "hi": 102.0, "touches": 1},
                      {"kind": "demand", "lo": 99.0, "hi": 101.0, "touches": 3}],
            "hit": {"bounce_pct": 8.0, "strong": True, "atr_x": 1.4}}
    m = ZB.single_message(item)
    assert "broken supply -> support (tested 1x) | demand (tested 3x)" in m["body"]
    assert m["body"].endswith("1.4x ATR · $5.0B")


def test_residence_gap_through_and_flat_names_are_silent_end_to_end(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"RES": _doc("RES", NTAP_BANDS, 4.5, 165.0),          # slept inside the shelf
             "GAP": _doc("GAP", NTAP_BANDS, 4.5, 180.77),         # gapped through, still falling
             "FLAT": _doc("FLAT", NTAP_BANDS, 4.5, 180.77)}       # touched, barely off the low
    snap = {"RES": _snap(161.0, 171.2, 165.0), "GAP": _snap(150.0, 152.0, 180.77),
            "FLAT": _snap(161.0, 168.0, 180.77)}                  # +4.3% but < shelf top? no: 168 > 167.54
    caps = {s: 5e9 for s in store}
    out = _run(store, snap, caps)
    # FLAT: 168 > 167.54 and +4.35% >= 3% -> it IS a (weak) bounce -> digest of one.
    assert [h["symbol"] for h in out["hits"]] == ["FLAT"]
    assert out["singles"] == 0 and out["digest"] == 1 and len(sent) == 1
    assert sent[0]["title"] == "🪃 Bouncing off demand levels — FLAT +4.3%"


def test_unknown_cap_is_skipped_and_counted_small_cap_is_skipped(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"UNK": _doc("UNK", NTAP_BANDS, 4.5, 180.77), "SML": _doc("SML", NTAP_BANDS, 4.5, 180.77),
             "NTAP": _doc("NTAP", NTAP_BANDS, 4.5, 180.77)}
    snap = {s: _snap(161.0, 168.5, 180.77) for s in store}          # 0.57% above the top: inside the phone window
    out = _run(store, snap, {"UNK": None, "SML": 9e8, "NTAP": 37.4e9})
    assert len(out["hits"]) == 3 and out["unknown_cap"] == 1 and out["skipped_cap"] == 1
    assert len(sent) == 1 and "NTAP" in sent[0]["title"] and "UNK" not in sent[0]["body"]


def test_dedupe_is_once_per_band_per_day(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"NTAP": _doc("NTAP", NTAP_BANDS, 4.5, 180.77)}
    coll = FakeColl()
    snap = {"NTAP": _snap(161.0, 168.5, 180.77)}                       # inside the 1% window
    _run(store, snap, {"NTAP": 37.4e9}, coll=coll)
    later = NOW + timedelta(minutes=9)
    _run(store, {"NTAP": _snap(161.0, 168.9, 180.77, now=later)}, {"NTAP": 37.4e9}, coll=coll, now=later)
    assert len(sent) == 1, "the next print is the same fact on the same band"
    tomorrow = NOW + timedelta(days=1)
    _run({"NTAP": _doc("NTAP", NTAP_BANDS, 4.5, 180.77, day="2026-09-04")},
         {"NTAP": _snap(161.0, 168.5, 180.77, now=tomorrow)}, {"NTAP": 37.4e9}, coll=coll, now=tomorrow)
    assert len(sent) == 2 and len(coll.docs) == 2


def test_strong_gets_singles_capped_at_three_everything_else_one_digest(monkeypatch):
    sent = _capture(monkeypatch)
    # a 5.8%-wide band: STRONG (>= 5% off the low) is reachable while the print is still
    # within 1% above the top (the phone gate, 2026-09-05)
    band = [{"kind": "demand", "lo": 95.0, "hi": 100.5, "touches": 2, "strength": 40.0}]
    store, snap, caps = {}, {}, {}
    # five STRONG names (low 95.5 inside the band, prints 0.1-0.9% above the top: +5.3..+6.2%)
    for i, px in enumerate([100.6, 100.8, 101.0, 101.2, 101.4]):
        s = f"ST{i}"
        store[s] = _doc(s, band, 0.5, 110.0)
        snap[s] = _snap(95.5, px, 110.0)
        caps[s] = 5e9
    # two weak names (low 97.0, +3.7% / +4.0%)
    for i, px in enumerate([100.6, 100.9]):
        s = f"WK{i}"
        store[s] = _doc(s, band, 0.5, 110.0)
        snap[s] = _snap(97.0, px, 110.0)
        caps[s] = 5e9
    coll = FakeColl()
    out = _run(store, snap, caps, coll=coll)
    assert out["singles"] == 3 and out["digest"] == 4 and out["pushed"] == 4
    assert [s["title"] for s in sent[:3]] == [
        "🪃 ST4 bounced +6.2% off demand $95-100.5",
        "🪃 ST3 bounced +6.0% off demand $95-100.5",
        "🪃 ST2 bounced +5.8% off demand $95-100.5"]
    assert sent[3]["title"] == "🪃 Bouncing off demand levels — ST1 +5.5% +3 more"
    assert [l.split()[0] for l in sent[3]["body"].split("\n")] == ["ST1", "ST0", "WK1", "WK0"]
    assert all(s["kind"] == "zone_bounce_alert" for s in sent)
    assert len(coll.docs) == 7, "every pushed name is recorded, single or digest"


def test_transport_failure_is_retried_but_muted_pref_is_terminal(monkeypatch):
    store = {"NTAP": _doc("NTAP", NTAP_BANDS, 4.5, 180.77)}
    snap = {"NTAP": _snap(161.0, 168.5, 180.77)}                       # inside the 1% window
    coll = FakeColl()
    _capture(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    out = _run(store, snap, {"NTAP": 37.4e9}, coll=coll)
    assert out["pushed"] == 0 and coll.docs == {}, "a failed transport must retry next pass"
    _capture(monkeypatch, result={"sent": 0, "failed": 0, "total_targets": 0})
    out = _run(store, snap, {"NTAP": 37.4e9}, coll=coll)
    assert out["pushed"] == 1 and len(coll.docs) == 1, "nobody targeted = done for today"


def test_dry_run_reads_everything_and_records_nothing(monkeypatch):
    sent = _capture(monkeypatch)
    coll = FakeColl()
    out = _run({"NTAP": _doc("NTAP", NTAP_BANDS, 3.0, 180.77)}, {"NTAP": _snap(160.6, 169.2, 180.77)},
               {"NTAP": 37.4e9}, coll=coll, push=False)
    assert out["singles"] == 1 and out["pushed"] == 0 and sent == [] and coll.docs == {}


def test_empty_store_and_missing_snapshot_rows_are_quiet(monkeypatch):
    sent = _capture(monkeypatch)
    out = _run({}, {}, {})
    assert out["ran"] and out["candidates"] == 0 and out["pushed"] == 0
    out = _run({"NTAP": _doc("NTAP", NTAP_BANDS, 4.5, 180.77)}, {}, {"NTAP": 37.4e9})
    assert out["priced"] == 0 and out["hits"] == [] and sent == []


def test_unknown_prev_close_is_counted_not_guessed(monkeypatch):
    sent = _capture(monkeypatch)
    out = _run({"NTAP": _doc("NTAP", NTAP_BANDS, 4.5, None)}, {"NTAP": _snap(161.0, 171.2, None)},
               {"NTAP": 37.4e9})
    assert out["unknown_prev"] == 1 and out["hits"] == [] and sent == []


# ── the session gate ─────────────────────────────────────────────────────────
def test_session_gate_is_nine_thirty_three_to_four_weekdays():
    assert ZB.in_session(datetime(2026, 9, 3, 9, 32, tzinfo=ET)) is False
    assert ZB.in_session(datetime(2026, 9, 3, 9, 33, tzinfo=ET)) is True
    assert ZB.in_session(datetime(2026, 9, 3, 16, 0, tzinfo=ET)) is True
    assert ZB.in_session(datetime(2026, 9, 3, 16, 1, tzinfo=ET)) is False
    assert ZB.in_session(datetime(2026, 9, 5, 11, 0, tzinfo=ET)) is False     # Saturday


def test_check_once_refuses_outside_rth_unless_forced():
    out = ZB.check_once(store={}, now=datetime(2026, 9, 3, 7, 0, tzinfo=ET))
    assert out["ran"] is False and "RTH" in out["reason"]


# ── source guards: the wiring ────────────────────────────────────────────────
def test_kind_has_a_default_pref_and_both_cron_lines():
    assert ZB.KIND == "zone_bounce_alert"
    subs = (ROOT / "backend/push/subs.py").read_text()
    assert '"zone_bounce_alert": True' in subs
    cron = (ROOT / "backend/crontab").read_text().splitlines()
    bounce = [l for l in cron if "supply_demand.zone_bounce_alerts" in l and not l.startswith("#")]
    assert len(bounce) == 1 and bounce[0].split()[:5] == ["4-59/5", "9-16", "*", "*", "1-5"]
    store = [l for l in cron if "supply_demand.zone_store" in l and not l.startswith("#")]
    assert len(store) == 1 and store[0].split()[:5] == ["20", "9", "*", "*", "1-5"]


def test_notifications_page_and_prefs_type_know_the_kind():
    page = (ROOT / "frontend/src/pages/Notifications.tsx").read_text()
    assert "key: 'zone_bounce_alert'" in page
    assert page.index("key: 'demand_alert'") < page.index("key: 'zone_bounce_alert'") < \
        page.index("key: 'minervini_flashcards'"), "sits right after demand_alert"
    assert "zone_bounce_alert: true" in page, "essentials preset keeps it on"
    prefs = (ROOT / "frontend/src/hooks/useNotificationPrefs.ts").read_text()
    assert "zone_bounce_alert?: boolean" in prefs


def test_demand_alerts_payloads_now_carry_their_kind_for_push_history():
    band = {"lo": 180.0, "hi": 183.5, "touches": 4, "strength": 50.0}
    at = DA.at_message({"symbol": "NTAP", "last": 182.9, "band": band, "cap": 37e9,
                        "hit": {"tier": "at", "state": "in", "dist_pct": 0.0}})
    dg = DA.digest_message([{"symbol": "NTAP", "last": 186.0, "band": band, "cap": 37e9,
                             "hit": {"tier": "near", "state": "falling", "dist_pct": 1.3}}])
    assert at["kind"] == DA.KIND == "demand_alert" and dg["kind"] == "demand_alert"


def test_a_digest_item_upgrades_to_one_strong_single_later_never_a_third_push(monkeypatch):
    """A weak first read rides the digest; when the same band turns STRONG it gets
    ONE more push, as a single; after that the band is spent for the day. Since
    the phone gate (2026-09-05) the upgrade must still print within 1% above the
    top — NTAP's 09:42 leg (+10.8%, 6.5% above the shelf) now only lists — so
    the geometry here is a 5.8%-wide band: low 96.5, +4.2% at 100.6 (digest),
    +5.1% at 101.4 (strong, 0.9% above the top)."""
    sent = _capture(monkeypatch)
    band = [{"kind": "demand", "lo": 95.0, "hi": 100.5, "touches": 2, "strength": 40.0}]
    store = {"AAA": _doc("AAA", band, 1.0, 110.0)}
    caps = {"AAA": 5e9}
    coll = FakeColl()
    out1 = _run(store, {"AAA": _snap(96.5, 100.6, 110.0)}, caps, coll=coll)
    assert out1["pushed"] == 1 and sent[-1]["title"].startswith("🪃 Bouncing off demand levels — AAA")
    later = datetime(2026, 9, 3, 9, 43, tzinfo=ET)
    out2 = _run(store, {"AAA": _snap(96.5, 101.4, 110.0, now=later)}, caps, coll=coll, now=later)
    assert out2["pushed"] == 1 and sent[-1]["title"].startswith("🪃 AAA bounced +5.1% off demand")
    out3 = _run(store, {"AAA": _snap(96.5, 101.5, 110.0, now=later)}, caps, coll=coll, now=later)
    assert out3["pushed"] == 0 and len(sent) == 2
    # the NTAP 09:42 leg itself: strong, but 6.5% above the shelf = late = lists only
    ntap = {"NTAP": _doc("NTAP", NTAP_BANDS, 6.907, 180.77)}
    ncoll = FakeColl()
    _run(ntap, {"NTAP": _snap(161.0, 168.5, 180.77)}, {"NTAP": 37e9}, coll=ncoll)       # weak, digest
    n = len(sent)
    late = _run(ntap, {"NTAP": _snap(161.0, 178.38, 180.77, now=later)}, {"NTAP": 37e9}, coll=ncoll, now=later)
    assert late["hits"][0]["hit"]["strong"] is True and late["pushed"] == 0 and late["skipped_proximity"] == 1
    assert len(sent) == n
    # a name that was already STRONG on its first push never gets a second one
    store2 = {"DOCN": _doc("DOCN", band, 0.5, 110.0)}
    coll2 = FakeColl()
    _run(store2, {"DOCN": _snap(95.5, 101.0, 110.0)}, {"DOCN": 12e9}, coll=coll2)     # +5.8% strong
    n = len(sent)
    _run(store2, {"DOCN": _snap(95.5, 101.4, 110.0)}, {"DOCN": 12e9}, coll=coll2)
    assert len(sent) == n


# ── detail: touch clock + room to run (Ajay 2026-09-03: "It touched demand at
# 2:50 CDT ... And had room to grow 2.2") ──────────────────────────────────────
def _minute_frame():
    import pandas as pd
    idx = pd.to_datetime(["2026-09-03 13:25:00", "2026-09-03 13:30:00", "2026-09-03 13:31:00",
                          "2026-09-03 18:50:00", "2026-09-03 18:51:00"])   # UTC-naive like the fetcher
    return pd.DataFrame({"low": [160.0, 161.0, 165.0, 161.0, 166.0],
                         "session": ["premarket", "rth", "rth", "rth", "rth"]}, index=idx)


def test_low_time_is_the_first_rth_bar_at_the_day_low_in_et_clock():
    assert ZB.low_time_from_bars(_minute_frame(), 161.0) == "9:30a"
    assert ZB.low_time_from_bars(_minute_frame(), 160.99) == "9:30a", "off by a tick → lowest RTH bar"
    assert ZB.fmt_et_clock("2026-09-03 18:50:00") == "2:50p"
    assert ZB.low_time_from_bars(None, 161.0) is None
    import pandas as pd
    assert ZB.low_time_from_bars(pd.DataFrame({"low": []}), 161.0) is None


def test_room_is_measured_to_the_next_supply_floor_with_an_r_multiple():
    below_only = [b for b in NTAP_BANDS if not (b["kind"] == "supply" and b["lo"] > 171.2)]   # keep the touched shelf, drop overhead supply
    bands = below_only + [{"kind": "supply", "lo": 205.4, "hi": 212.72, "touches": 2, "strength": 30.0}]
    room = ZB.room_for(171.2, bands, NTAP_SHELF)
    assert room["target"] == 205.4 and room["room_pct"] == 20.0            # (205.4-171.2)/171.2
    assert room["rr"] == 3.6                                               # 20.0 / ((171.2-161.78)/171.2 = 5.5)
    assert ZB.room_for(171.2, below_only, NTAP_SHELF) is None, "no supply overhead = clear runway"
    real = ZB.room_for(171.2, NTAP_BANDS, NTAP_SHELF)                      # the reclaimed shelf above is overhead at 09:33
    assert real["target"] == 173.87 and real["room_pct"] == 1.6 and real["rr"] == 0.3
    assert ZB.room_for(171.2, bands + [{"kind": "supply", "lo": 150.0, "hi": 155.0}], NTAP_SHELF)["target"] == 205.4, \
        "a supply band BELOW the print is not overhead"
    assert ZB.room_for(0, bands, NTAP_SHELF) is None
    assert ZB.room_for(171.2, [{"kind": "supply", "lo": None}], NTAP_SHELF) is None
    assert ZB._room_txt(None) == "room: clear runway"
    assert ZB._room_txt(room) == "room +20% -> $205.4 (3.6R)"


def test_pushes_carry_the_touch_clock_and_the_room(monkeypatch):
    sent = _capture(monkeypatch)
    bands = [b for b in NTAP_BANDS if not (b["kind"] == "supply" and b["lo"] > 171.2)] + [{"kind": "supply", "lo": 205.4, "hi": 212.72, "touches": 2, "strength": 30.0}]
    store = {"NTAP": _doc("NTAP", bands, 3.0, 180.77)}
    out = _run(store, {"NTAP": _snap(160.6, 169.2, 180.77)}, {"NTAP": 37e9},     # inside the 1% window
               coll=FakeColl(), names={"NTAP": "NetApp"})
    assert out["pushed"] == 1
    body = sent[-1]["body"]
    assert "room +21.4% -> $205.4 (4.9R)" in body                    # (205.4-169.2)/169.2; risk to 161.78 = 4.39%
    assert "low $160.6" in body
    sent.clear()
    store2 = {"NTAP": _doc("NTAP", bands, 3.0, 180.77)}
    out2 = ZB.check_once(push=True, force=True, store=store2, snapshot={"NTAP": _snap(160.6, 169.2, 180.77)},
                         caps={"NTAP": 37e9}, names={"NTAP": "NetApp"}, coll=FakeColl(), owner="o@x",
                         now=NOW, low_times={"NTAP": "9:30a"})
    assert out2["pushed"] == 1 and "low $160.6 at 9:30a ET -> +$8.6" in sent[-1]["body"]
    assert out2["hits"][0]["low_time"] == "9:30a" and out2["hits"][0]["room"]["rr"] == 4.9


def test_digest_lines_carry_clock_and_room_too():
    items = [{"symbol": "AAA", "print": 110.0, "day_low": 100.0, "band": {"kind": "demand", "lo": 98.0, "hi": 101.0},
              "hit": {"bounce_pct": 10.0, "strong": False}, "cap": 2e9, "low_time": "2:50p",
              "room": {"room_pct": 2.2, "target": 112.4, "rr": 0.2}},
             {"symbol": "BBB", "print": 55.0, "day_low": 50.0, "band": {"kind": "supply", "lo": 49.0, "hi": 50.5},
              "hit": {"bounce_pct": 10.0, "strong": False}, "cap": 3e9, "low_time": None, "room": None}]
    m = ZB.digest_message(items)
    assert "AAA $110 · +10.0% off $98-101 (low 2:50p) · room +2.2% -> $112.4 (0.2R) · demand · $2.0B" in m["body"]
    assert "BBB $55 · +10.0% off $49-50.5 · room: clear runway · broken supply · $3.0B" in m["body"]


# ── fixes 2026-09-05 (review of the S/D zone logic; Ajay: "yes please fix the bugs") ──
def test_room_counts_the_band_that_contains_the_print_and_skips_a_broken_one():
    """room_for skipped a supply band CONTAINING the print and quoted the room to
    the band after it: '+8.6% (1.1R)' for a print sitting 2.9% under a top."""
    bands = [{"kind": "supply", "lo": 161.78, "hi": 167.54, "touches": 1, "strength": 18.0},
             {"kind": "supply", "lo": 173.87, "hi": 180.07, "touches": 1, "strength": 24.0},
             {"kind": "supply", "lo": 190.0, "hi": 195.0, "touches": 2, "strength": 30.0}]
    room = ZB.room_for(175.0, bands, bands[0])
    assert room["target"] == 180.07 and room["room_pct"] == 2.9 and room["state"] == "IN_BAND"
    assert room["rr"] == 0.4                                     # 2.9 / ((175-161.78)/175 = 7.55)
    # yesterday closed 181 > 180.07: that shelf is broken (support); the ceiling is 190
    room2 = ZB.room_for(175.0, bands, bands[0], prev_close=181.0)
    assert room2["target"] == 190.0 and room2["room_pct"] == 8.6 and room2["rr"] == 1.1 and room2["touches"] == 2
    # a demand band ABOVE the print is broken support = overhead too
    room3 = ZB.room_for(175.0, bands[:1] + [{"kind": "demand", "lo": 178.0, "hi": 179.0, "touches": 2}], bands[0])
    assert room3["target"] == 178.0 and room3["room_pct"] == 1.7
    assert ZB._room_txt(room) == "room +2.9% -> $180.07 (0.4R)"


def test_phone_gate_a_bounce_that_already_ran_lists_but_never_pushes(monkeypatch):
    """Ajay 2026-09-05: "<1% bounce from demand zone" — NTAP's 09:33 print was
    2.2% above the shelf top; by the time it reached the phone he was late.
    Listed in hits, counted (skipped_proximity), not pushed, not recorded."""
    sent = _capture(monkeypatch)
    store = {"NTAP": _doc("NTAP", NTAP_BANDS, 4.5, 180.77)}
    coll = FakeColl()
    out = _run(store, {"NTAP": _snap(161.0, 171.2, 180.77)}, {"NTAP": 37.4e9}, coll=coll)
    assert [h["symbol"] for h in out["hits"]] == ["NTAP"] and out["hits"][0]["hit"]["bounce_pct"] == 6.34
    assert out["pushed"] == 0 and sent == [] and coll.docs == {}
    assert out["skipped_proximity"] == 1 and out["skipped_room"] == 0
    # 168.5 = 0.57% above the top, +4.7% off the low; the 173.87-180.07 shelf is broken
    # (180.07 < prev 180.77) so nothing unbroken sits overhead: clear runway -> pushes
    out2 = _run(store, {"NTAP": _snap(161.0, 168.5, 180.77)}, {"NTAP": 37.4e9}, coll=coll)
    assert out2["pushed"] == 1 and out2["skipped_proximity"] == 0 and out2["skipped_room"] == 0
    assert sent[-1]["title"].startswith("🪃 Bouncing off demand levels — NTAP +4.7%")
    assert "room: clear runway" in sent[-1]["body"]
    assert list(coll.docs) == ["NTAP:161.78-167.54:2026-09-03"]


def test_phone_gate_needs_five_percent_room_to_the_first_unbroken_supply(monkeypatch):
    sent = _capture(monkeypatch)
    band = {"kind": "demand", "lo": 96.0, "hi": 100.0, "touches": 2, "strength": 40.0}
    lid = {"kind": "supply", "lo": 104.0, "hi": 106.0, "touches": 2, "strength": 20.0}   # 3.5% over a $100.5 print
    store = {"AAA": _doc("AAA", [band, lid], 0.5, 105.0)}          # prev 105: arrival (>103), lid unbroken (106 >= 105)
    out = _run(store, {"AAA": _snap(97.0, 100.5, 105.0)}, {"AAA": 5e9})   # +3.6% off the low, 0.5% above the top
    assert out["hits"] and out["hits"][0]["room"]["room_pct"] == 3.5
    assert out["pushed"] == 0 and sent == [] and out["skipped_room"] == 1 and out["skipped_proximity"] == 0
    store2 = {"AAA": _doc("AAA", [band, dict(lid, lo=106.0, hi=108.0)], 0.5, 105.0)}   # 5.47% over
    out2 = _run(store2, {"AAA": _snap(97.0, 100.5, 105.0)}, {"AAA": 5e9})
    assert out2["pushed"] == 1 and "room +5.5% -> $106" in sent[-1]["body"]


# ── the pass record for /alerts/status (2026-09-05) ──────────────────────────
def test_every_pass_records_its_counters_so_a_quiet_phone_is_explainable(monkeypatch):
    """Ajay 2026-09-05: "Do we have the same logic in back end demand for the ones
    that I get alerts" — the answer is no, so each pass leaves WHY it was quiet:
    {_id: kind, as_of, date, counts} in alert_pass_latest, replaced every pass."""
    sent = _capture(monkeypatch)
    pc = PassColl()
    store = {"NTAP": _doc("NTAP", NTAP_BANDS, 3.0, 180.77),
             "FAR": _doc("FAR", [{"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2}], 1.0, 100.0),
             "SML": _doc("SML", NTAP_BANDS, 3.0, 180.77)}
    snap = {"NTAP": _snap(160.6, 169.2, 180.77),            # the exact-single fixture: rings
            "FAR": _snap(91.5, 96.0, 100.0),                 # bounced 4.3% above the top: too far
            "SML": _snap(160.6, 169.2, 180.77)}              # same read, $0.5B: listed, not pushed
    out = _run(store, snap, {"NTAP": 30e9, "FAR": 5e9, "SML": 5e8}, pass_coll=pc)
    assert out["pushed"] == 1 and len(sent) == 1
    assert list(pc.docs) == ["zone_bounce_alert"]
    doc = pc.docs["zone_bounce_alert"]
    assert doc["_id"] == ZB.KIND and doc["as_of"] == NOW.isoformat() and doc["date"] == "2026-09-03"
    c = doc["counts"]
    assert c["candidates"] == 3 and c["priced"] == 3 and c["stale_print"] == 0
    assert c["hits"] == 3 and c["pushed"] == 1 and c["skipped_cap"] == 1 and c["unknown_cap"] == 0
    assert c["skipped_proximity"] == 1 and c["skipped_room"] == 0 and c["unknown_prev"] == 0
    assert set(c) >= {"candidates", "hits", "skipped_room", "skipped_proximity", "skipped_cap",
                      "unknown_cap", "pushed"}, "the /alerts/status contract keys"
    assert all(type(v) is int for v in c.values()) and "reason" not in doc
    # the next pass REPLACES the doc (nothing accumulates) and an empty store leaves a reason
    out2 = _run({}, {}, {}, pass_coll=pc)
    assert out2["ran"] and list(pc.docs) == ["zone_bounce_alert"]
    assert pc.docs["zone_bounce_alert"]["counts"]["candidates"] == 0
    assert pc.docs["zone_bounce_alert"]["reason"] == "zone store empty for today"


def test_pass_record_is_best_effort_and_never_written_outside_rth(monkeypatch):
    _capture(monkeypatch)

    class Broken(PassColl):
        def replace_one(self, q, doc, upsert=False):
            raise RuntimeError("mongo down")
    store = {"NTAP": _doc("NTAP", NTAP_BANDS, 3.0, 180.77)}
    snap = {"NTAP": _snap(160.6, 169.2, 180.77)}
    out = _run(store, snap, {"NTAP": 30e9}, pass_coll=Broken())
    assert out["pushed"] == 1, "a dead status coll never blocks the push"
    pc = PassColl()
    closed = ZB.check_once(store=store, now=datetime(2026, 9, 3, 7, 0, tzinfo=ET), coll=FakeColl(),
                           pass_coll=pc)
    assert closed == {"ran": False, "reason": "outside RTH"} and pc.docs == {}
    # no coll injected: the module resolver is used and (no Mongo in tests) records nothing — quietly
    assert _run(store, snap, {"NTAP": 30e9})["pushed"] == 1


def test_single_message_carries_the_ticker_for_push_history_2026_09_05():
    """/alerts page + alerted-today chips key on push_history.ticker."""
    from supply_demand import zone_bounce_alerts as ZB
    item = {"symbol": "NTAP", "print": 171.2, "day_low": 161.0, "prev_close": 180.77,
            "atr14": 4.0, "band": {"kind": "supply", "lo": 161.78, "hi": 167.54, "touches": 1},
            "hit": {"bounce_pct": 6.3, "floor_pct": 3.0, "strong": True, "strong_pct": 5.0,
                    "undercut_pct": 0.48, "atr_x": 2.5},
            "bands": [], "cap": 40e9, "name": "NetApp", "low_time": "09:30a", "room": None}
    msg = ZB.single_message(item)
    assert msg["ticker"] == "NTAP"
