"""Formulas audit D10 (2026-11-11) — K11 words: a `triggered` read whose live A+ alert never rang no longer claims
"A+ on the HH:MM bar".

Ajay 2026-11-11 08:18 ET, verbatim: "Can you fix the defects please". The audit's demo (L3/k8_edges.py §8): the pass
that reads the entry bar sees 900,000 shares → K11 refuses (partial, no alert); the next pass sees 1,050,000 → the read
is re-judged A+ and served as `triggered` — the card said "A+ on the 10:20 bar" and the 🌙 recap "A+ (triggered)" for
an alert that never rang. Fix = words only (spec §3.7): the served fact "no alert rang" (store.alert_rows via
tab._entry_times — the 🏁's own read), on live-push pages only (🚩 GG5, 1-minute GG1), the SAME words for every reader.
NEGATIVES: key present / entries unknown (fault, no ledger) / 🧪 shadow / bare `_track_row` → today's bytes.
"""
from __future__ import annotations

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala.bars import Frame
from tests.test_gajjala_tab import NOW, PREV, S, latest, read_doc, scan_doc, store_with

RS = "reversal_squeeze"
SYM = "X"
FLOAT = {"shares": 5_000_000, "text": "5.0M float"}
UNM = GT.UNMEASURED


# ── the audit's §8 frames (L3/k8_edges.py), dated on the fixture session S ──────────────────────────────────────────
def _frame(bars, day=S, start=(9, 35), step=5):
    t = []
    for i in range(len(bars)):
        m = start[0] * 60 + start[1] + i * step
        t.append(f"{day.isoformat()} {m // 60:02d}:{m % 60:02d}")
    o, h, l, c, v = (list(x) for x in zip(*bars))
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v})
    return Frame(o=o, h=h, l=l, c=c, v=v, t=t, session=["rth"] * len(t), ema9=[None] * len(t),
                 ema21=[None] * len(t), today=range(0, len(t)), df=df, minutes={}, frame="5m")


HEAD = [
    (9.5, 10.0, 9.5, 9.6, 300_000),
    (9.6, 9.9, 9.3, 9.4, 200_000),
    (9.4, 9.4, 9.0, 9.1, 200_000),
    (9.1, 9.3, 9.0, 9.2, 100_000),
    (9.2, 9.4, 9.1, 9.3, 100_000),
    (9.3, 9.5, 9.2, 9.4, 100_000),
    (9.4, 11.0, 9.4, 10.9, 900_000),
]
BALL = (10.9, 10.95, 10.0, 10.85, 400_000)
BARS = HEAD + [BALL, (10.85, 10.9, 10.7, 10.8, 100_000), (10.8, 11.2, 10.75, 11.1, 500_000)]   # break bar 10:20
NEXT = BARS + [(11.1, 11.15, 11.0, 11.05, 150_000)]


def _read(bars, vol):
    return D.read_all({"5m": _frame(bars), "15m": None}, {"symbol": SYM, "float_read": FLOAT, D.K11_CTX_KEY: vol})[RS]


def refused_read():
    return _read(BARS, 900_000)


def triggered_read():
    return _read(NEXT, 1_050_000)


def stopped_read():
    r = triggered_read()
    return dict(r, state="stopped")


NO_RING_PILL = f"triggered 1 bar ago — broke on the 10:20 bar, no alert rang · {UNM}"
TODAY_PILL = f"triggered 1 bar ago — A+ on the 10:20 bar · {UNM}"


def alert_doc(d=S, sym=SYM, setup=RS):
    """A live A+ claim as alerts.py leaves it (the test_gajjala_potential_tab entry_doc shape): `GG:` id, pushed."""
    return {"_id": f"GG:{d.isoformat()}|{sym}|{setup}", "date": d.isoformat(), "symbol": sym, "setup": setup,
            "state": "pushed", "at": "2026-10-13T10:20:30-04:00", "mode": "live", "kind": GC.PUSH_KIND,
            "trigger": 10.95, "stop": 10.7}


def board_store(read, *, alerts=()):
    return store_with(reads=[read_doc(SYM, {RS: read})], scans=[scan_doc(SYM)], passes=[latest()],
                      alerts=list(alerts))


def tile_label(out, sym=SYM):
    return next(t["gajjala"]["state_label"] for t in out["tiles"] if t["symbol"] == sym)


def recap_texts(out):
    return [r["text"] for r in out["postmarket"]["recap"]["rows"]]


# ── the demo itself ──────────────────────────────────────────────────────────────────────────────────────────────
def test_the_demo_frames_refuse_at_900k_and_trigger_at_1_05m():
    r = refused_read()
    assert r["state"] == "partial" and D.K11_KEY in r["missed"]
    t = triggered_read()
    assert t["state"] == "triggered" and t["bars_since_entry"] == 1 and t["entry_bar_t"].endswith("10:20")
    assert GT.state_label(t) == TODAY_PILL                                  # the defect, as the audit printed it


def test_state_label_says_no_alert_rang_only_on_a_proven_no_ring():
    t = triggered_read()
    assert GT.state_label(t, False) == NO_RING_PILL
    assert "A+" not in GT.state_label(t, False)


@pytest.mark.parametrize("rang", [None, True])
def test_NEGATIVE_state_label_unknown_or_rang_is_todays_bytes(rang):
    assert GT.state_label(triggered_read(), rang) == TODAY_PILL


def test_NEGATIVE_rang_false_moves_no_other_state():
    t = triggered_read()
    for st in ("aplus", "stopped", "partial", "forming", "invalid", "none"):
        r = dict(t, state=st)
        assert GT.state_label(r, False) == GT.state_label(r), st
    assert GT.state_label(refused_read(), False) == GT.state_label(refused_read())


def test_rang_is_tri_state():
    assert GT._rang(None, S, SYM, RS) is None
    assert GT._rang({}, S, SYM, RS) is False
    assert GT._rang({(S.isoformat(), SYM, RS): "10:20"}, S, SYM, RS) is True
    assert GT._rang({(S.isoformat(), SYM, "bull_flag"): "10:20"}, S, SYM, RS) is False
    assert GT._rang({(PREV.isoformat(), SYM, RS): "10:20"}, S, SYM, RS) is False


# ── the setup sub (🎾 card) ──────────────────────────────────────────────────────────────────────────────────────
def test_live_setup_card_without_the_alert_says_no_alert_rang():
    out = GT.build(RS, now=NOW, store=board_store(triggered_read()))
    assert tile_label(out) == NO_RING_PILL


def test_NEGATIVE_live_setup_card_with_its_alert_keeps_the_a_plus_words():
    out = GT.build(RS, now=NOW, store=board_store(triggered_read(), alerts=[alert_doc()]))
    assert tile_label(out) == TODAY_PILL


@pytest.mark.parametrize("other", [alert_doc(setup="bull_flag"), alert_doc(sym="OTHER"), alert_doc(d=PREV)],
                         ids=["other_setup", "other_symbol", "prev_session"])
def test_NEGATIVE_another_keys_alert_never_counts_as_this_cards_ring(other):
    out = GT.build(RS, now=NOW, store=board_store(triggered_read(), alerts=[other]))
    assert tile_label(out) == NO_RING_PILL


@pytest.mark.parametrize("fault", ["none", "raises", "no_ledger"])
def test_NEGATIVE_unknown_entries_keep_todays_bytes(monkeypatch, fault):
    st = board_store(triggered_read())
    if fault == "none":
        monkeypatch.setattr(st, "alert_rows", lambda sessions: None)
    elif fault == "raises":
        def boom(sessions):
            raise RuntimeError("mongo down")
        monkeypatch.setattr(st, "alert_rows", boom)
    else:
        monkeypatch.setattr(GT, "_ledger", lambda: None)
    out = GT.build(RS, now=NOW, store=st)
    assert tile_label(out) == TODAY_PILL


def test_entry_times_is_tri_state(monkeypatch):
    st = board_store(triggered_read())
    assert GT._entry_times(st, [S, PREV]) == {}
    monkeypatch.setattr(st, "alert_rows", lambda sessions: None)
    assert GT._entry_times(st, [S, PREV]) is None
    monkeypatch.setattr(GT, "_ledger", lambda: None)
    assert GT._entry_times(board_store(triggered_read()), [S, PREV]) is None


def test_NEGATIVE_audited_shadow_page_keeps_todays_bytes_with_no_key():
    assert V.push_mode(V.GGA) == "shadow"
    out = GT.build(RS, now=NOW, store=board_store(triggered_read()), variant=V.GGA)
    assert tile_label(out) == TODAY_PILL


def test_one_minute_live_page_says_no_alert_rang_too():
    assert V.push_mode(V.GG1) == "live"
    out = GT.build(RS, now=NOW, store=board_store(triggered_read()), variant=V.GG1)
    assert tile_label(out) == NO_RING_PILL


# ── the 🌙 recap ─────────────────────────────────────────────────────────────────────────────────────────────────
def _doc(read):
    return read_doc(SYM, {RS: read})


def test_recap_without_the_alert_says_broke_no_alert_rang():
    rows = GT.recap([_doc(triggered_read())], entries={})["rows"]
    assert len(rows) == 1 and "🎾 Reversal Squeeze broke (no alert rang) at 10:20" in rows[0]["text"]
    assert "A+" not in rows[0]["text"]
    rows = GT.recap([_doc(stopped_read())], entries={})["rows"]
    assert "broke, then stopped (no alert rang) at 10:20" in rows[0]["text"] and "A+" not in rows[0]["text"]


def test_NEGATIVE_recap_key_present_or_entries_none_is_todays_bytes():
    key = {(S.isoformat(), SYM, RS): "10:20"}
    for read, word in ((triggered_read(), "A+ (triggered)"), (stopped_read(), "A+, then stopped")):
        today = GT.recap([_doc(read)])
        assert word in today["rows"][0]["text"]
        assert GT.recap([_doc(read)], entries=key) == today
        assert GT.recap([_doc(read)], entries=None) == today


def test_NEGATIVE_recap_an_aplus_row_never_moves():
    a = dict(triggered_read(), state="aplus")
    assert GT.recap([_doc(a)], entries={}) == GT.recap([_doc(a)])


def test_postmarket_recap_through_build_live_and_shadow():
    out = GT.build("postmarket", now=NOW, store=board_store(triggered_read()))
    assert any("broke (no alert rang) at 10:20" in t for t in recap_texts(out))
    out = GT.build("postmarket", now=NOW, store=board_store(triggered_read(), alerts=[alert_doc()]))
    assert any("A+ (triggered) at 10:20" in t for t in recap_texts(out))                    # NEGATIVE: it rang
    out = GT.build("postmarket", now=NOW, store=board_store(triggered_read()), variant=V.GGA)
    assert not any("no alert rang" in t for t in recap_texts(out))                         # NEGATIVE: 🧪 shadow


# ── 🧠 sub: tile, track row, timeline ────────────────────────────────────────────────────────────────────────────
def tracker_doc(sym=SYM, setup=RS, last="triggered", day=S):
    return {"_id": f"{day.isoformat()}|{sym}|{setup}", "date": day.isoformat(), "symbol": sym, "setup": setup,
            "first_seen_et": "10:01", "first_kind": GC.POTENTIAL_KINDS[0], "first_px": 10.85, "first_trigger": 10.95,
            "first_stop": 10.7,
            "state_path": [{"at_et": "10:01", "state": GC.POTENTIAL_STATE, "kind": GC.POTENTIAL_KINDS[0]},
                           {"at_et": "10:21", "state": "triggered", "kind": None}],
            "last": {"state": last, "kind": None, "px": 11.05}, "push": {"state": "pushed", "at_et": "10:01"}}


NO_RING_WORD = GT.NO_RING_RECAP["triggered"]


def test_track_row_live_without_the_key_says_broke_no_alert_rang():
    row = GT._track_row(tracker_doc(), entries={}, live=True)
    assert row["last_state_text"] == NO_RING_WORD == "broke (no alert rang)"
    assert f"now {NO_RING_WORD}" in row["text"]
    assert [x["text"] for x in row["timeline"]] == [f"10:01 {PT.KIND_LABEL[GC.POTENTIAL_KINDS[0]]}",
                                                    f"10:21 {NO_RING_WORD}"]


def test_NEGATIVE_track_row_key_present_or_unknown_or_not_live_is_todays_bytes():
    doc = tracker_doc()
    today = GT._track_row(doc)
    assert today["last_state_text"] == PT.STATE_WORDS["triggered"] == "A+ (triggered)"
    assert "now A+ (triggered)" in today["text"]
    assert GT._track_row(doc, entries={}) == today                                   # live False
    assert GT._track_row(doc, entries=None, live=True) == today                       # unknown
    key = {(S.isoformat(), SYM, RS): "10:20"}
    rang = GT._track_row(doc, entries=key, live=True)
    assert {k: v for k, v in rang.items() if k != "entry_text"} == {k: v for k, v in today.items() if k != "entry_text"}
    assert rang["entry_text"] == GT.ENTRY_SENT_TEXT.format(at="10:20")


def test_NEGATIVE_track_row_moves_only_triggered_words():
    for last in ("aplus", "stopped", GC.POTENTIAL_STATE):
        doc = dict(tracker_doc(last=last), state_path=[{"at_et": "10:01", "state": GC.POTENTIAL_STATE,
                                                        "kind": GC.POTENTIAL_KINDS[0]}])
        assert GT._track_row(doc, entries={}, live=True) == GT._track_row(doc), last


def test_state_words_untouched():
    assert PT.STATE_WORDS["triggered"] == "A+ (triggered)"
    assert PT.state_word("triggered", None) == "A+ (triggered)"


def potential_store(alerts=()):
    st = board_store(triggered_read(), alerts=alerts)
    st.coll(ST.POTENTIALS).docs[tracker_doc()["_id"]] = tracker_doc()
    return st


def _pot_row(out):
    return next(r for r in out["track"]["today"]["rows"] if (r["symbol"], r["setup"]) == (SYM, RS))


def test_potential_track_through_build_live():
    out = GT.build(GC.POTENTIAL_SUB, now=NOW, store=potential_store())
    row = _pot_row(out)
    assert row["last_state_text"] == NO_RING_WORD and row["timeline"][-1]["text"] == f"10:21 {NO_RING_WORD}"


def test_NEGATIVE_potential_track_through_build_key_present_fault_and_shadow(monkeypatch):
    row = _pot_row(GT.build(GC.POTENTIAL_SUB, now=NOW, store=potential_store(alerts=[alert_doc()])))
    assert row["last_state_text"] == "A+ (triggered)" and row["entry_text"] is not None
    st = potential_store()
    monkeypatch.setattr(st, "alert_rows", lambda sessions: None)
    row = _pot_row(GT.build(GC.POTENTIAL_SUB, now=NOW, store=st))
    assert row["last_state_text"] == "A+ (triggered)" and row["entry_text"] is None
    row = _pot_row(GT.build(GC.POTENTIAL_SUB, now=NOW, store=potential_store(), variant=V.GGA))
    assert row["last_state_text"] == "A+ (triggered)"


def test_potential_tile_of_a_triggered_primary_read_gets_the_pill(monkeypatch):
    """potential_kind admits `forming` reads only, so a 🧠 tile never carries a triggered read today; the wiring is
    proven by admitting the triggered read as a potential (spec §3.7 [C4]: _potential_tiles hands `rang` on)."""
    real = PT.potential_kind
    monkeypatch.setattr(PT, "potential_kind",
                        lambda r: GC.POTENTIAL_KINDS[0] if isinstance(r, dict) and r.get("state") == "triggered"
                        else real(r))
    out = GT.build(GC.POTENTIAL_SUB, now=NOW, store=potential_store())
    assert tile_label(out) == NO_RING_PILL
    out = GT.build(GC.POTENTIAL_SUB, now=NOW, store=potential_store(alerts=[alert_doc()]))
    assert tile_label(out) == TODAY_PILL                                                 # NEGATIVE: it rang
    out = GT.build(GC.POTENTIAL_SUB, now=NOW, store=potential_store(), variant=V.GGA)
    assert tile_label(out) == TODAY_PILL                                                 # NEGATIVE: 🧪 shadow


# ── ONE read per build ───────────────────────────────────────────────────────────────────────────────────────────
def _count_reads(monkeypatch, st):
    calls = []
    real = st.alert_rows

    def counting(sessions):
        calls.append(list(sessions))
        return real(sessions)
    monkeypatch.setattr(st, "alert_rows", counting)
    return calls


@pytest.mark.parametrize("sub,variant,n", [
    (GC.POTENTIAL_SUB, None, 1), (RS, None, 1), ("bull_flag", None, 1), ("postmarket", None, 1),
    ("premarket", None, 1), ("playbook", None, 0),     # MOVED 2026-11-11 (🌅 day-2 list): GG5 ☀️ reads once
    ("premarket", V.GG1, 0), ("premarket", V.GGA, 0),  # NEGATIVE: no 🌅 off GG5 → no read
    (RS, V.GG1, 1),
    (RS, V.GGA, 0), ("postmarket", V.GGA, 0), (GC.POTENTIAL_SUB, V.GGA, 1),    # 🧪: only the 🧠 entry_text read
])
def test_alert_rows_is_read_at_most_once_per_build(monkeypatch, sub, variant, n):
    st = potential_store()
    calls = _count_reads(monkeypatch, st)
    GT.build(sub, now=NOW, store=st, variant=variant)
    assert len(calls) == n
    # MOVED 2026-11-11 (🧭 setup stages, review fix D10): the ONE read spans the listing window SC._window(S) (⊇ [S,
    # PREV]; PREV appended only if the window lacks it — tab.build's own rule) instead of [S, PREV]. The count pin is
    # unchanged (a ☀️ board WITH cards reads once for the stage tags — pinned in test_gajjala_potential_tab.py).
    from chart_maps.gajjala import scanner as SC
    win = list(SC._window(S))
    win += [PREV] if PREV not in win else []
    assert all(c == win for c in calls)


# ── readers [C5]: the same words for owner and non-owner ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("sub", [RS, "postmarket", GC.POTENTIAL_SUB])
def test_owner_and_non_owner_read_the_same_words(sub):
    a = GT.build(sub, now=NOW, store=potential_store(), owner=True)
    b = GT.build(sub, now=NOW, store=potential_store(), owner=False)
    if sub == RS:
        assert tile_label(a) == tile_label(b) == NO_RING_PILL
    elif sub == "postmarket":
        assert recap_texts(a) == recap_texts(b) and any("no alert rang" in t for t in recap_texts(a))
    else:
        assert _pot_row(a)["text"] == _pot_row(b)["text"] and _pot_row(a)["last_state_text"] == NO_RING_WORD
        assert _pot_row(a)["timeline"] == _pot_row(b)["timeline"]


def test_words_are_module_constants():
    assert GT.NO_RING_TEXT == "no alert rang"
    assert GT.NO_RING_RECAP == {"triggered": "broke (no alert rang)",
                                "stopped": "broke, then stopped (no alert rang)"}
    assert GT.NO_RING_TEXT in GT.state_label(triggered_read(), False)
