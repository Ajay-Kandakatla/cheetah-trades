"""Auto-entry behavior — fake broker + fake Mongo + stubbed sepa seams.

Locks trading/auto_entry.py (docs/sepa/auto_entry_methodology.md):

  Funnel    latest-scan rows with is_buyable + score >= AUTO_MIN_SCORE +
            rs_rank >= AUTO_MIN_RS (p.79 "80s or 90s") + entry_setup.pivot,
            read only from a TRUSTED scan (fresh + market-sized universe).
  Trigger   hybrid: (a) INTRADAY first-half pivot clear + projected RelVol >=
            AUTO_RELVOL_MIN + within MAX_EXTENSION_PCT of the pivot;
            (b) CLOSE-CONFIRM prev_day_close > pivot next morning.
  Vetoes    held / attempted-today / MAX_POSITIONS / daily cap / raw gauge
            risk_off / earnings <= 7d — cheap-first, snapshot every skip.
  Buys      ONLY via entries.enter (monkeypatched recorder here; the
            no-direct-submit invariant is in test_trading_contracts.py).
  Cap       sizing equity = min(Alpaca equity, trading_config.equity_cap)
            for ALL entries — asserted through real entries.preview math.

FakeColl/FakeBroker mirror tests/test_trading_engine.py (house pattern).

Host-runnable (py3.9, no pandas/numpy):
    cd backend && .venv/bin/python -m pytest tests/test_auto_entry.py -q
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.auto_entry as AE
import trading.entries as EN
import trading.exit_engine as EE
from trading.broker_alpaca import OPEN_STATUSES, BrokerError
from trading.risk_rules import DEFAULT_STOP_PCT, MAX_POSITIONS


# ── Fakes (pattern: tests/test_trading_engine.py) ────────────────────────────

class FakeCursor(list):
    def sort(self, *a, **k):
        return self

    def limit(self, n):
        return FakeCursor(self[:int(n)])


class FakeColl:
    def __init__(self, docs=None):
        self.rows = [dict(d) for d in (docs or [])]

    @staticmethod
    def _match(doc, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, q=None, *a, **k):
        for d in self.rows:
            if self._match(d, q):
                return dict(d)
        return None

    def find(self, q=None, *a, **k):
        return FakeCursor(dict(d) for d in self.rows if self._match(d, q))

    def insert_one(self, doc):
        self.rows.append(dict(doc))

    def update_one(self, q, update, upsert=False):
        for d in self.rows:
            if self._match(d, q):
                d.update(update.get("$set") or {})
                return
        if upsert:
            base = {k: v for k, v in (q or {}).items() if not isinstance(v, dict)}
            base.update(update.get("$set") or {})
            self.rows.append(base)


class FakeDB:
    def __init__(self, armed=True, auto=True, losses=0, equity_cap=100_000.0):
        self.trading_config = FakeColl([{
            "_id": "config", "armed": armed, "auto_entry": auto,
            "consecutive_losses": losses, "processed_order_ids": [],
            "equity_cap": equity_cap,
        }])
        self.trade_ledger = FakeColl()
        self.auto_entry_state = FakeColl()


class FakeBroker:
    """Reads only — auto_entry must never need a mutation method. Any
    submit_*/replace/cancel attempt raises AttributeError, which the tests
    would surface as an error in run()'s summary."""

    OPEN_STATUSES = OPEN_STATUSES
    BrokerError = BrokerError

    def __init__(self, positions=(), equity=100_000.0, market_open=True):
        self._positions = list(positions)
        self._equity = float(equity)
        self._market_open = bool(market_open)

    def configured(self):
        return True

    def clock(self):
        return {"is_open": self._market_open}

    def account(self):
        return {"equity": str(self._equity), "cash": str(self._equity),
                "buying_power": str(self._equity)}

    def positions(self):
        return [dict(p) for p in self._positions]

    def open_orders(self, symbol=None):
        return []

    def latest_trade(self, symbol):
        return None


def _position(symbol, qty=10, avg_entry=100.0, last=110.0):
    return {"symbol": symbol, "qty": str(qty),
            "avg_entry_price": str(avg_entry), "current_price": str(last)}


def _row(symbol="AAA", score=85.0, pivot=100.0, stop=95.0, buyable=True,
         rs_rank=90):
    return {"symbol": symbol, "score": score, "is_buyable": buyable,
            "rs_rank": rs_rank,
            "entry_setup": {"type": "VCP", "pivot": pivot, "stop": stop}}


@pytest.fixture
def env(monkeypatch):
    """Wire auto_entry's seams; returns (fake_broker, fake_db, enter_calls)."""

    def build(rows=(), quotes=None, positions=(), armed=True, auto=True,
              equity=100_000.0, equity_cap=100_000.0, frac=0.3,
              relvols=None, gauge="constructive", earnings_days=None,
              market_open=True, enter_result=None, enter_raises=None,
              never_stop=False, scan_meta=None):
        # never_stop pinned FALSE by default: this suite tests the LIVE
        # guardrails (daily cap, risk-off halt). The paper-mode lift is
        # covered by tests/test_autoentry_never_stop.py. Without the pin the
        # fake broker resolves to sim mode and the cap silently lifts.
        fake = FakeBroker(positions, equity, market_open)
        db = FakeDB(armed=armed, auto=auto, equity_cap=equity_cap)
        enter_calls = []

        def fake_enter(symbol, limit_price=None, stop_pct=None,
                       allow_earnings=False):
            enter_calls.append({"symbol": symbol, "limit_price": limit_price,
                                "stop_pct": stop_pct,
                                "allow_earnings": allow_earnings})
            if enter_raises:
                raise enter_raises
            return enter_result or {"order_id": "o-%d" % len(enter_calls),
                                    "shares": 12}

        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(EN, "_db", lambda: db)
        monkeypatch.setattr(AE, "_db", lambda: db)
        monkeypatch.setattr(AE, "broker", fake)
        monkeypatch.setattr(EE, "broker", fake)
        monkeypatch.setattr(EN, "broker", fake)
        monkeypatch.setattr(EN, "regime", lambda: "normal")
        monkeypatch.setattr(AE, "_latest_scan_rows", lambda: list(rows))
        # Trusted scan by default — freshness/universe behavior is exercised
        # explicitly by the scan-trust tests via the scan_meta param.
        import time as _time
        meta = scan_meta if scan_meta is not None else {
            "generated_at": _time.time(), "universe_size": 3000}
        monkeypatch.setattr(AE, "_scan_meta", lambda: dict(meta))
        monkeypatch.setattr(AE, "_bulk_live",
                            lambda syms: {s: dict(quotes[s])
                                          for s in syms if s in (quotes or {})})
        monkeypatch.setattr(AE, "_session_fraction", lambda: frac)
        # relvols map -> the new _volume_live seam (projected only; tests
        # exercising the ACTUAL-volume fast path build their own dict).
        monkeypatch.setattr(AE, "_volume_live",
                            lambda sym: {"projected_relvol": (relvols or {}).get(sym),
                                         "today_volume": None, "avg_vol_50": None})
        monkeypatch.setattr(AE, "_gauge_state", lambda: gauge)
        monkeypatch.setattr(AE, "_never_auto_stop", lambda: never_stop)
        monkeypatch.setattr(AE, "_earnings_days",
                            lambda sym: earnings_days)
        pushes = []
        monkeypatch.setattr(AE, "_notify",
                            lambda k, t, d: pushes.append((k, t, d)))
        monkeypatch.setattr(AE.entries, "enter", fake_enter)
        # earnings stub for the real entries.preview path (equity-cap test)
        stub = types.ModuleType("sepa.earnings_watch")
        stub.next_event = lambda s: None
        monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
        return fake, db, enter_calls, pushes

    return build


def _kind_rows(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


def _state(db, symbol):
    return db.auto_entry_state.find_one({"symbol": symbol}) or {}


# ── Path a: intraday ─────────────────────────────────────────────────────────

def test_intraday_path_fires_once_with_structural_stop(env):
    """First-half clear (frac 0.3) + relvol 1.6 + live 101 > pivot 100 within
    the extension cap -> exactly ONE entries.enter call. The scan row's
    structure stop (95) is 5.94% below live — tighter than the 7% band
    default — so it is passed through as stop_pct."""
    _, db, enter_calls, pushes = env(
        rows=[_row("AAA", pivot=100.0, stop=95.0)],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 98.0}},
        frac=0.3, relvols={"AAA": 1.6})
    out = AE.run()

    assert out["ran"] is True
    assert len(enter_calls) == 1, enter_calls
    call = enter_calls[0]
    assert call["symbol"] == "AAA"
    assert call["allow_earnings"] is False        # NO override in auto mode
    expected = round((101.0 - 95.0) / 101.0 * 100.0, 2)
    assert expected < DEFAULT_STOP_PCT
    assert call["stop_pct"] == pytest.approx(expected, abs=0.01)

    rows = _kind_rows(db, "auto_entry")
    assert len(rows) == 1 and rows[0]["dry_run"] is False
    det = rows[0]["detail"]
    assert det["path"] == "intraday"
    assert det["pivot"] == 100.0 and det["live"] == 101.0
    assert det["relvol"] == 1.6
    assert det["cleared_at_frac"] == pytest.approx(0.3)
    assert "is_buyable" in rows[0]["cite"] and "score floor" in rows[0]["cite"]
    assert pushes and pushes[0][0] == "auto_entry" and pushes[0][1] == "AAA"


def test_structural_stop_wider_than_band_default_is_ignored(env):
    """Stop 12% below live is WIDER than the 7% band default -> not passed;
    entries falls back to the band default (stop_pct None)."""
    _, _, enter_calls, _ = env(
        rows=[_row("AAA", pivot=100.0, stop=89.0)],   # 11.9% below live 101
        quotes={"AAA": {"price": 101.0, "prev_day_close": 98.0}},
        frac=0.3, relvols={"AAA": 1.6})
    AE.run()
    assert len(enter_calls) == 1
    assert enter_calls[0]["stop_pct"] is None


def test_second_half_clear_blocks_intraday_path(env):
    """First observed pivot clear at frac 0.6 (> FIRST_HALF_FRACTION 0.5) ->
    no intraday entry; cleared_at_frac persisted for the day so a later tick
    cannot retro-qualify it."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA", pivot=100.0)],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 98.0}},
        frac=0.6, relvols={"AAA": 2.5})
    AE.run()
    assert enter_calls == []
    assert _state(db, "AAA").get("cleared_at_frac") == pytest.approx(0.6)
    checks = _state(db, "AAA")["last_eval"]["checks"]
    assert checks["cleared_first_half"]["pass"] is False


def test_relvol_below_min_skips(env):
    """Projected RelVol 1.2 < AUTO_RELVOL_MIN (1.5) -> no entry (and the
    prior close sits below the pivot, so close-confirm cannot rescue it)."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA", pivot=100.0)],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 98.0}},
        frac=0.3, relvols={"AAA": 1.2})
    AE.run()
    assert enter_calls == []
    checks = _state(db, "AAA")["last_eval"]["checks"]
    assert checks["volume_confirmed"]["pass"] is False
    assert checks["volume_confirmed"]["value"]["projected_relvol"] == 1.2
    assert checks["volume_confirmed"]["value"]["basis"] == "insufficient_volume"


def test_projection_untrusted_at_open_skips(env):
    """REGRESSION (2026-07-09 autopsy): at 9:31 (frac 0.003) even a monster
    PROJECTED RelVol must not trigger — the projection has no tape to stand
    on. This is the hole that let 12 of 18 entries fire in the first two
    minutes. Close-confirm stays available (prev close below pivot here)."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA", pivot=100.0)],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 98.0}},
        frac=0.003, relvols={"AAA": 9.9})
    AE.run()
    assert enter_calls == []
    checks = _state(db, "AAA")["last_eval"]["checks"]
    assert checks["volume_confirmed"]["pass"] is False
    assert checks["volume_confirmed"]["value"]["basis"] == "too_early_to_project"


def test_extended_past_cap_skips_both_paths(env):
    """Live more than MAX_EXTENSION_PCT above the pivot -> chasing; skipped
    on BOTH paths even with prev close above the pivot (book p.224 anchor —
    mirrors scanner BUYABLE_MAX_EXT_PCT)."""
    live = round(100.0 * (1 + AE.MAX_EXTENSION_PCT / 100.0) + 0.5, 2)
    _, db, enter_calls, _ = env(
        rows=[_row("AAA", pivot=100.0)],
        quotes={"AAA": {"price": live, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 3.0})
    AE.run()
    assert enter_calls == []
    checks = _state(db, "AAA")["last_eval"]["checks"]
    assert checks["not_extended"]["pass"] is False


# ── Path b: close-confirmation ───────────────────────────────────────────────

def test_close_confirm_enters_next_morning(env):
    """Not entered intraday (clear observed in the second half), but the
    prior close finished above the pivot -> next-morning entry on path b.
    No relvol requirement on this path (the close already confirmed)."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA", pivot=100.0)],
        quotes={"AAA": {"price": 101.5, "prev_day_close": 102.0}},
        frac=0.6, relvols={})                       # relvol unavailable
    AE.run()
    assert len(enter_calls) == 1
    det = _kind_rows(db, "auto_entry")[0]["detail"]
    assert det["path"] == "close_confirm"
    assert det["prev_day_close"] == 102.0


# ── Vetoes (cheap-first) ─────────────────────────────────────────────────────

def test_daily_cap_two_entries_third_skipped(env):
    """Three triggering candidates, MAX_AUTO_ENTRIES_PER_DAY = 2 -> the two
    highest-score names enter, the third is skipped on the daily_cap check."""
    rows = [_row("AAA", score=90), _row("BBB", score=88), _row("CCC", score=86)]
    quotes = {s: {"price": 101.0, "prev_day_close": 102.0}
              for s in ("AAA", "BBB", "CCC")}
    _, db, enter_calls, _ = env(rows=rows, quotes=quotes, frac=0.3,
                                relvols={s: 2.0 for s in quotes})
    out = AE.run()
    assert [c["symbol"] for c in enter_calls] == ["AAA", "BBB"]
    assert out["entries_today"] == 2
    checks = _state(db, "CCC")["last_eval"]["checks"]
    assert checks["daily_cap"]["pass"] is False
    assert checks["daily_cap"]["value"] == 2


def test_max_positions_held_skips(env):
    held = [_position(s) for s in ("VVV", "WWW", "XXX", "YYY", "ZZZ")]
    assert len(held) == MAX_POSITIONS
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")], positions=held,
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    AE.run()
    assert enter_calls == []
    checks = _state(db, "AAA")["last_eval"]["checks"]
    assert checks["position_slots"]["pass"] is False


def test_already_held_symbol_skips(env):
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")], positions=[_position("AAA")],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    AE.run()
    assert enter_calls == []
    assert _state(db, "AAA")["last_eval"]["checks"]["not_already_held"]["pass"] is False


def test_earnings_within_shield_skips(env):
    """Earnings in 3 days -> vetoed; auto mode has NO allow_earnings hatch."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")], earnings_days=3,
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    AE.run()
    assert enter_calls == []
    checks = _state(db, "AAA")["last_eval"]["checks"]
    assert checks["earnings_shield"]["pass"] is False
    assert checks["earnings_shield"]["value"] == 3


def test_gauge_risk_off_skips(env):
    """RAW market-gauge state 'risk_off' vetoes every auto entry (this is
    the raw verdict, not the regime band mapping)."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")], gauge="risk_off",
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    AE.run()
    assert enter_calls == []
    checks = _state(db, "AAA")["last_eval"]["checks"]
    assert checks["gauge_not_risk_off"]["pass"] is False
    assert checks["gauge_not_risk_off"]["value"] == "risk_off"


def test_attempted_today_dedupes_second_tick(env):
    """A symbol entered this ET day is not re-attempted on the next tick."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    AE.run()
    AE.run()
    assert len(enter_calls) == 1, enter_calls


def test_unexpected_enter_error_ledgered_once_and_not_retried(env):
    """entries.enter dies with a NON-ValueError (unexpected bug / partial
    broker failure) -> the attempt is marked (no retry loop on later ticks)
    AND surfaced as ONE auto_entry_error ledger row — never silently dropped
    into the tick summary alone."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0},
        enter_raises=RuntimeError("connection reset mid-submit"))
    out1 = AE.run()
    out2 = AE.run()
    assert len(enter_calls) == 1, enter_calls       # bounded — no retry
    assert out1["errors"] and "connection reset" in out1["errors"][0]
    assert out2["errors"] == []
    errs = _kind_rows(db, "auto_entry_error")
    assert len(errs) == 1, errs
    assert "connection reset" in errs[0]["detail"]["error"]
    assert _state(db, "AAA")["attempted"] is True
    assert _state(db, "AAA")["last_eval"]["result"] == "error"
    assert _kind_rows(db, "auto_entry") == []


def test_triggered_but_vetoed_by_entries_ledgers_blocked_once(env):
    """Trigger fires but entries.enter refuses (its own checks re-apply) ->
    ONE auto_entry_blocked dry-run row for the day, not one per tick."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0},
        enter_raises=ValueError("portfolio full: 5/5 positions (p.312)"))
    AE.run()
    AE.run()
    blocked = _kind_rows(db, "auto_entry_blocked")
    assert len(blocked) == 1, blocked
    assert blocked[0]["dry_run"] is True
    assert "portfolio full" in blocked[0]["detail"]["reason"]
    assert _kind_rows(db, "auto_entry") == []


# ── Master gate ──────────────────────────────────────────────────────────────

def test_disabled_flag_noops_with_single_daily_ledger_row(env):
    """auto_entry=false -> no-op; exactly ONE auto_entry_disabled ledger row
    per ET day no matter how many ticks run."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")], auto=False,
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    out1 = AE.run()
    out2 = AE.run()
    assert out1["ran"] is False and out2["ran"] is False
    assert enter_calls == []
    assert len(_kind_rows(db, "auto_entry_disabled")) == 1
    assert db.auto_entry_state.rows == []         # never evaluated anything


def test_disarmed_places_no_orders(env):
    """armed=false NEVER places orders (house invariant) — the master gate
    refuses before any candidate is even evaluated."""
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")], armed=False,
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    out = AE.run()
    assert out["ran"] is False
    assert enter_calls == []
    assert _kind_rows(db, "auto_entry") == []


def test_market_closed_noops(env):
    _, _, enter_calls, _ = env(
        rows=[_row("AAA")], market_open=False,
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    out = AE.run()
    assert out["ran"] is False and enter_calls == []


# ── Funnel filter ────────────────────────────────────────────────────────────

def test_funnel_drops_non_buyable_low_score_and_no_pivot(env):
    rows = [
        _row("NOB", buyable=False),                       # not buyable
        _row("LOW", score=84.9),                          # score < 85 floor
        {"symbol": "NOP", "score": 90, "is_buyable": True,
         "entry_setup": {"type": "VCP", "stop": 95.0}},   # no pivot
        _row("YES", score=85.0),                          # exactly at the floor
    ]
    quotes = {s: {"price": 101.0, "prev_day_close": 102.0}
              for s in ("NOB", "LOW", "NOP", "YES")}
    _, _, enter_calls, _ = env(rows=rows, quotes=quotes, frac=0.3,
                               relvols={s: 2.0 for s in quotes})
    AE.run()
    assert [c["symbol"] for c in enter_calls] == ["YES"]


# ── Equity cap (the "assume you have 5k" rule) ───────────────────────────────

def test_equity_cap_sizes_off_min_of_equity_and_cap(env):
    """Alpaca paper equity 100k, equity_cap 5000 -> sizing equity is 5000:
    25% of 5000 at $50 = 25 shares (real entries.preview math, no order)."""
    env(equity=100_000.0, equity_cap=5_000.0)
    out = EN.preview("CAP", price=50.0)
    assert out["equity_cap"] == 5_000.0
    assert out["equity_used"] == 5_000.0
    assert out["shares"] == 25                     # int(5000 * 0.25 / 50)
    assert out["allocation"] == 1_250.0


def test_equity_cap_above_equity_uses_equity(env):
    """Cap higher than actual equity -> min() picks the real equity."""
    env(equity=3_000.0, equity_cap=5_000.0)
    out = EN.preview("CAP", price=50.0)
    assert out["equity_used"] == 3_000.0
    assert out["shares"] == 15                     # int(3000 * 0.25 / 50)


def test_config_default_equity_cap_is_5000(env):
    """A config doc with no equity_cap falls back to DEFAULT_EQUITY_CAP."""
    _, db, _, _ = env()
    db.trading_config.rows[0].pop("equity_cap")
    assert EE.get_config()["equity_cap"] == AE.DEFAULT_EQUITY_CAP == 5000.0


# ── Status block ─────────────────────────────────────────────────────────────

def test_status_block_shape_and_snapshots(env):
    _, db, _, _ = env(
        rows=[_row("AAA")],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0}, equity_cap=5_000.0)
    AE.run()
    blk = AE.status_block()
    assert blk["enabled"] is True
    assert blk["equity_cap"] == 5_000.0
    assert blk["entries_today"] == 1
    assert blk["max_per_day"] == AE.MAX_AUTO_ENTRIES_PER_DAY == 2
    snaps = blk["candidates"]
    assert len(snaps) == 1 and snaps[0]["symbol"] == "AAA"
    assert snaps[0]["last_eval"]["result"] == "entered"
    assert "checks" in snaps[0]["last_eval"]


# ── RS floor (TLSW p.79 criterion 8, 2026-07-12 low-RS audit) ────────────────

def test_rs_below_floor_is_filtered_and_at_floor_passes(env):
    env(rows=[_row("LOW", rs_rank=79), _row("EDGE", rs_rank=80),
              _row("HIGH", rs_rank=95)])
    syms = [r["symbol"] for r in AE._candidates()]
    assert "LOW" not in syms
    assert syms == ["EDGE", "HIGH"] or set(syms) == {"EDGE", "HIGH"}


def test_missing_rs_rank_fails_closed(env):
    env(rows=[_row("NORS", rs_rank=None)])
    assert AE._candidates() == []


def test_auto_min_rs_config_override(env):
    _, db, _, _ = env(rows=[_row("MID", rs_rank=75)])
    assert AE._candidates(min_rs=AE._min_rs()) == []
    EE.update_config(auto_min_rs=70)
    cands = AE._candidates(min_rs=AE._min_rs(EE.get_config()))
    assert [r["symbol"] for r in cands] == ["MID"]


def test_rs_floor_blocks_entry_end_to_end(env):
    _, db, enter_calls, _ = env(
        rows=[_row("WEAK", rs_rank=76)],
        quotes={"WEAK": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"WEAK": 2.0})
    out = AE.run()
    assert out["reason"] == "no_candidates"
    assert enter_calls == []


# ── Scan trust (freshness + universe size, 2026-07-12) ──────────────────────

def _epoch(y, m, d, hour=16):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime(y, m, d, hour, tzinfo=ZoneInfo("America/New_York")).timestamp()


def test_scan_trusted_fresh_and_sized():
    from datetime import date
    ok, det = AE.scan_trusted(
        {"generated_at": _epoch(2026, 7, 10), "universe_size": 3685},
        today=date(2026, 7, 13))
    assert ok and det["fresh"] and det["sized"]


def test_scan_trusted_friday_scan_ok_monday_but_not_tuesday():
    from datetime import date
    meta = {"generated_at": _epoch(2026, 7, 10), "universe_size": 3000}
    ok_mon, _ = AE.scan_trusted(meta, today=date(2026, 7, 13))
    ok_tue, det = AE.scan_trusted(meta, today=date(2026, 7, 14))
    assert ok_mon is True
    assert ok_tue is False and det["fresh"] is False


def test_scan_trusted_small_universe_fails():
    from datetime import date
    ok, det = AE.scan_trusted(
        {"generated_at": _epoch(2026, 7, 13), "universe_size": 120},
        today=date(2026, 7, 13))
    assert ok is False and det["sized"] is False and det["fresh"] is True


def test_scan_trusted_missing_meta_fails_closed():
    from datetime import date
    for meta in ({}, None, {"generated_at": None, "universe_size": None},
                 {"generated_at": "junk", "universe_size": "junk"}):
        ok, _ = AE.scan_trusted(meta, today=date(2026, 7, 13))
        assert ok is False


def test_untrusted_scan_sits_out_and_ledgers_once(env):
    _, db, enter_calls, _ = env(
        rows=[_row("AAA")],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0},
        scan_meta={"generated_at": _epoch(2026, 1, 2), "universe_size": 3000})
    out1 = AE.run()
    out2 = AE.run()
    assert out1["reason"] == out2["reason"] == "untrusted_scan"
    assert enter_calls == []
    assert len(_kind_rows(db, "auto_entry_skipped_scan")) == 1


def test_status_block_carries_rules_min_rs_and_scan(env):
    env(rows=[_row("AAA")],
        quotes={"AAA": {"price": 101.0, "prev_day_close": 102.0}},
        frac=0.3, relvols={"AAA": 2.0})
    blk = AE.status_block()
    assert blk["min_rs"] == AE.AUTO_MIN_RS == 80.0
    assert blk["scan"]["trusted"] is True
    rules = blk["rules"]
    assert isinstance(rules, list) and len(rules) >= 8
    assert all({"rule", "value", "source"} <= set(r) for r in rules)
    joined = " ".join(r["rule"] + r["source"] for r in rules)
    assert "80s or 90s" in joined
    assert "p.229" in joined
    assert "pp.291-315" in joined
