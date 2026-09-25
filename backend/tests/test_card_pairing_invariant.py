"""📋 The pairs the Chart Maps entry ladder prints ONCE (2026-09-25).

Ajay 2026-09-24: "Can you organize the chips on the cards they very over
whelming ... I want them to categorized in a good way so I have enough info for
entry of a stock." The frontend ladder (frontend/src/lib/cardLadder.ts) drops a
stat when its chip carries the SAME served string, and moves the floor / knife
detail into the fold. That is only safe while the producers keep writing each
chip and its stat from ONE variable, on the same tile. TEST-ONLY: no runtime
change. What these pin, producer by producer:

  1. a 📌 pill  ⇒ its `On board` stat carries the same N (the FE D3 rule matches);
  2. a heat pill ⇒ its `Sector flow (5d)` value is a SUBSTRING of the pill (D4);
  3. 🔪 falling knife ⇔ the `Knife` stat;
  4. 🔪 band broken / 🎯 swept the stops ⇔ the `Band` stat;
  5. 🐆 / 🐘 ⇒ `Float/day` exists;
and, NEGATIVE, that a tile without the pill may carry the stat alone, never the
reverse orphan (a pill with no stat behind it).
"""
import importlib

import pytest

B = importlib.import_module("chart_maps.board")


def _badges(t):
    return [b["text"] for b in t.get("badges", [])]


def _stat(t, k):
    for s in t.get("stats", []):
        if s["k"] == k:
            return s["v"]
    return None


# ── 1. dwell ──────────────────────────────────────────────────────────────────
class _Coll:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q, proj=None):
        syms = set((q.get("symbol") or {}).get("$in") or [])
        return [d for d in self.docs if d["symbol"] in syms]


class _DB:
    def __init__(self, docs):
        self._c = _Coll(docs)

    def __getitem__(self, name):
        return self._c


@pytest.mark.parametrize("n", [2, 6, 13, 40])
def test_a_dwell_pill_and_its_on_board_stat_carry_the_same_n(monkeypatch, n):
    from supply_demand import demand_history as DH
    docs = [{"symbol": "AAA", "appearances": n, "first_seen": "2026-09-15", "last_seen": "2026-09-24"}]
    monkeypatch.setattr(DH, "_db", lambda: _DB(docs))
    t = {"symbol": "AAA"}
    assert B._dwell_decor([t]) == 1
    pill = next(x for x in _badges(t) if x.startswith("📌 "))
    v = _stat(t, B.DWELL_STAT_KEY)
    assert v == f"{n}d"
    # the exact frontend D3 rule: pill startsWith('📌 ' + v.slice(0,-1) + ' board day')
    assert pill.startswith("📌 " + v[:-1] + " board day")


def test_NEGATIVE_day_one_is_new_today_and_its_stat_still_rides_beside_it(monkeypatch):
    """🆕 is not a 📌 pill, so the frontend keeps `On board 1d` — both print."""
    from supply_demand import demand_history as DH
    docs = [{"symbol": "NEW", "appearances": 1, "first_seen": "2026-09-24", "last_seen": "2026-09-24"}]
    monkeypatch.setattr(DH, "_db", lambda: _DB(docs))
    t = {"symbol": "NEW"}
    B._dwell_decor([t])
    assert _badges(t) == [B.DWELL_NEW_TEXT]
    assert _stat(t, B.DWELL_STAT_KEY) == "1d"


def test_NEGATIVE_no_episode_means_neither_pill_nor_stat(monkeypatch):
    from supply_demand import demand_history as DH
    monkeypatch.setattr(DH, "_db", lambda: _DB([]))
    t = {"symbol": "NOEP"}
    assert B._dwell_decor([t]) == 0
    assert "badges" not in t and "stats" not in t


# ── 2. sector heat ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tone,rel", [("hot", 2.14), ("cold", -2.1), ("neutral", -0.45), ("neutral", 0.0)])
def test_the_sector_flow_value_is_a_substring_of_its_heat_pill(tone, rel):
    from rotation import heat as RH
    h = {"tone": tone, "group": "Financial Services", RH.HEAT_KEY: rel,
         "benchmark": "RSP", "heat_window": RH.HEAT_WINDOW, "thin": False}
    t = {"symbol": "AAA", "_heat": h, "_heat_badge": RH.badge(h)}
    assert B._heat_decor([t]) == 1
    pill = _badges(t)[0]
    v = _stat(t, "Sector flow (%s)" % RH.HEAT_WINDOW)
    assert v is not None
    assert v in pill                      # the frontend D4 rule: pill.includes(stat.v)


def test_NEGATIVE_a_heat_pill_without_a_number_prints_the_pill_alone_never_a_bare_stat():
    t = {"symbol": "AAA", "_heat": {"group": "Energy"},
         "_heat_badge": {"text": "— sector flat Energy +0.0% vs RSP (5d)", "tone": "muted"}}
    B._heat_decor([t])
    assert len(_badges(t)) == 1
    assert not any(s["k"].startswith("Sector flow") for s in t.get("stats", []))
    bare = {"symbol": "BBB", "_heat": {"group": "Energy", "rel_5d": 1.0}}
    B._heat_decor([bare])
    assert "badges" not in bare and "stats" not in bare     # no pill → no stat either


# ── 3. falling knife ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("flag,expect", [(True, True), (False, False), (None, False), ("yes", False)])
def test_the_knife_pill_and_the_knife_stat_come_together_or_not_at_all(flag, expect):
    t = {"symbol": "AAA", "_knife": flag}
    B._knife_decor([t])
    assert (B.KNIFE_BADGE_TEXT in _badges(t)) is expect
    assert (_stat(t, B.KNIFE_STAT_KEY) is not None) is expect


# ── 4. sweep ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("state,text", [("swept", B.SWEPT_BADGE_TEXT), ("broken", B.BROKEN_BADGE_TEXT)])
def test_a_sweep_pill_always_has_its_band_stat(state, text):
    t = {"symbol": "AAA", "_sweep": state}
    B._sweep_decor([t])
    assert _badges(t) == [text]
    assert _stat(t, "Band") == state


@pytest.mark.parametrize("state", ["intact", None, "", "weird"])
def test_NEGATIVE_no_sweep_pill_means_no_band_stat(state):
    t = {"symbol": "AAA", "_sweep": state}
    B._sweep_decor([t])
    assert "badges" not in t and "stats" not in t


# ── 5. velocity ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("v", [2.66, 3.0, 0.31, 0.5, 2.0])
def test_a_fast_or_heavy_supply_pill_always_has_its_float_per_day_stat(v):
    t = {"symbol": "AAA", "_m": {"velocity": v}}
    B._velocity_decor([t])
    pills = [x for x in _badges(t) if x.startswith(("🐆", "🐘"))]
    assert len(pills) == 1
    assert _stat(t, "Float/day") is not None


def test_NEGATIVE_the_two_roundings_differ_so_the_frontend_keeps_both():
    """2.66 prints 2.7 on the pill and 2.66% on the stat. The frontend drops the
    stat only on a substring match — here there is none, so both stay in TAPE
    (HIS CALL #10: one rounding)."""
    t = {"symbol": "AAA", "_m": {"velocity": 2.66}}
    B._velocity_decor([t])
    assert _badges(t) == ["🐆 Fast supply — 2.7%/day"]
    assert _stat(t, "Float/day") == "2.66%"
    assert "2.66%" not in _badges(t)[0]


@pytest.mark.parametrize("v", [1.16, 0.84, 1.99])
def test_NEGATIVE_a_mid_velocity_carries_the_stat_alone(v):
    t = {"symbol": "AAA", "_m": {"velocity": v}}
    B._velocity_decor([t])
    assert _badges(t) == []
    assert _stat(t, "Float/day") == f"{v:.2f}%"


def test_NEGATIVE_no_velocity_means_neither():
    t = {"symbol": "AAA", "_m": {"velocity": None}}
    B._velocity_decor([t])
    assert "badges" not in t and "stats" not in t
