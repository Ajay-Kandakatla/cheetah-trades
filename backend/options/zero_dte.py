"""0DTE — same-day-expiry options, as a decision board.

Ajay 2026-08-24:

> *"I need a new tab for ODTE type of options calls. Where its short or
> calling.. but like day trade. Quick return type of trading.. Look to see of
> we have all the data for this... I think this will require a lot of accuracy
> and much better data like order book or so to some degree"*

He asked for the data audit first. It ran before a line of this was written and
it decided the design, so it is recorded here.

WHAT WE HAVE (verified live 2026-08-24)
---------------------------------------
* Same-day chains, real: SPY had 358 contracts expiring that day, and the
  `expiration_date` filter was confirmed honoured (NVDA/TSLA/AAPL/MU/AVGO all
  returned only 2026-08-24 contracts).
* `"timeframe": "REAL-TIME"` on both `last_quote` and `last_trade`. Not delayed.
* Per contract: delta, gamma, theta, vega, IV, open interest, day volume/VWAP.
* NBBO top of book with bid/ask SIZES and exchange ids.
* Dealer gamma, walls and max pain already computed by `options/opex.py`.
* 4,163 daily GEX snapshots in `gex_history` going back to 2026-07-06.

WHAT WE DO NOT HAVE — and it shapes every claim this module makes
-----------------------------------------------------------------
* **No order-book DEPTH.** He asked for it specifically. Massive sells top of
  book; there is no level 2 for options on this plan. Everything here uses NBBO
  and the size at the touch, and says so rather than implying more.
* **No intraday option price history.** So a 0DTE rule CANNOT be backtested
  here. `zone_backtest` exists for demand zones because daily equity bars exist;
  the equivalent for 0DTE does not.
* Therefore **no measured edge**. Every threshold below is a house value chosen
  from the live chain's own shape, not from a study.

That last point is why he chose "suggest a strike AND record every call": the
ledger (`zero_dte_history.py`) is how this earns a track record instead of
claiming one. Until it has months of resolved rows, the board says so.

THE NUMBER THAT MATTERS, AND WHY IT IS NOT THE SPREAD
-----------------------------------------------------
Measured on SPY's own 0DTE chain at the close, 2026-08-24, spot 763.71:

    strike   bid   ask  spread%   delta   theta   day volume
      763   0.68  0.76    11.1    0.623   -1.65      369,356
      764   0.09  0.10    10.5    0.214   -0.78      808,305
      765   0.01  0.02    66.7    0.039   -0.26      828,288
      766   0.00  0.01   200.0    0.028   -0.30      457,143

Two things jump out and both are in the tiles:

1. **The most-traded strikes are the ones expiring worthless.** 828,288
   contracts changed hands on a strike worth one cent with minutes to run.
2. **Theta dwarfs the premium.** The 764 call decays $0.78/day against a $0.10
   ask — 7.8x its entire value. On 0DTE the position does not erode, it
   evaporates. `theta_burn_pct` leads the tile for that reason; spread is
   second.

The counterweight, and the reason he wants this at all, is `double_move_pct`:
that same 764 call doubles on a 0.06% move in SPY. Both numbers are true and
the tile shows them side by side, because either one alone is propaganda.

NOT A BOOK METHOD. Nothing in Minervini covers 0DTE. No page is cited because
none applies. Decision support, not a signal, and explicitly not advice.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("options.zero_dte")

# ── the universe ─────────────────────────────────────────────────────────────
# Daily expiries do not exist for most names. Verified 2026-08-24: of 18 liquid
# tickers probed, 13 had a same-day chain and PLTR / SMCI / COIN / MSTR / NFLX
# did not. The list is curated rather than discovered because discovery costs
# one API call per name per day to learn a fact that changes rarely — and
# `board()` drops any name whose chain comes back empty anyway, so a ticker
# losing its dailies degrades to absent rather than to wrong.
UNIVERSE: tuple[str, ...] = (
    "SPY", "QQQ", "IWM",
    "NVDA", "TSLA", "AAPL", "AMD", "META", "MSFT", "AMZN", "GOOGL", "AVGO", "MU",
)

# ── strike selection — HOUSE VALUES, no study behind them ────────────────────
# Chosen from the shape of the live chain, which is the only evidence available:
# spread% is flat-ish from ~0.20 delta up and explodes below it (66% at 0.039
# delta, 200% at 0.028). So the tradeable band has a floor set by the spread,
# not by a theory of moneyness.
MIN_DELTA = 0.20          # below this the spread eats the trade
MAX_DELTA = 0.70          # above this you are paying mostly intrinsic
TARGET_DELTA = 0.35       # enough gamma to move, not a lottery ticket
MAX_SPREAD_PCT = 25.0     # refuse a contract that costs a quarter of premium to cross
MIN_DAY_VOLUME = 500      # it has to have actually traded today

# A 0DTE contract with no bid cannot be exited. Not a preference — a hard floor.
MIN_BID = 0.01

# A gamma flip further than this many expected session moves away is in the
# tail, not on the board. One sigma: the underlying reaching it today is
# already the ~16% case, and beyond that it is not a level, it is trivia.
FLIP_RELEVANT_SIGMAS = 1.0

DISCLAIMER = (
    "0DTE is same-day-expiry options. Every threshold here is a house value "
    "with NO measured edge behind it — there is no intraday option history to "
    "backtest against, so nothing has been validated. Suggestions are recorded "
    "and graded so a track record can accrue. Decision support, not a signal, "
    "and not advice."
)


def today_et() -> str:
    """Today's date in ET, as the chain labels it. ET because expiry is an
    exchange date: at 20:00 UTC it is still the same trading day in New York,
    and asking UTC for the date would roll the expiry over at 8pm ET."""
    return (datetime.now(timezone.utc) - timedelta(hours=4)).date().isoformat()


def _f(v) -> Optional[float]:
    """Finite float or None. Guards NaN reaching JSON and arithmetic."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def contract_metrics(c: dict, spot: Optional[float]) -> Optional[dict]:
    """The honest cost picture for ONE contract. PURE.

    Everything a 0DTE decision turns on, computed from the snapshot row and
    nothing else. Returns None when the row cannot support the arithmetic —
    never a partially-filled dict, because a missing delta silently defaulting
    to something would corrupt every derived number below it.
    """
    d = (c or {}).get("details") or {}
    q = (c or {}).get("last_quote") or {}
    g = (c or {}).get("greeks") or {}
    day = (c or {}).get("day") or {}

    strike = _f(d.get("strike_price"))
    bid, ask = _f(q.get("bid")), _f(q.get("ask"))
    delta, spot = _f(g.get("delta")), _f(spot)
    if None in (strike, bid, ask, delta, spot) or spot <= 0 or ask <= 0:
        return None
    if ask < bid:                       # a crossed book is bad data, not a trade
        return None

    mid = (bid + ask) / 2.0
    spread = ask - bid
    adelta = abs(delta)
    theta = _f(g.get("theta"))

    return {
        "ticker": d.get("ticker"),
        "side": d.get("contract_type"),
        "strike": round(strike, 2),
        "bid": round(bid, 2),
        "ask": round(ask, 2),
        "mid": round(mid, 4),
        "bid_size": _f(q.get("bid_size")),
        "ask_size": _f(q.get("ask_size")),
        "spread": round(spread, 4),
        # What crossing the spread costs, as a share of what you pay.
        "spread_pct": round(100.0 * spread / mid, 1) if mid > 0 else None,
        "delta": round(delta, 4),
        "gamma": _f(g.get("gamma")),
        "theta": theta,
        "iv": _f(c.get("implied_volatility")),
        "open_interest": _f(c.get("open_interest")),
        "day_volume": _f(day.get("volume")),
        # How far the UNDERLYING must move just to get back to what you paid.
        # spread / delta converts option dollars into underlying dollars.
        "breakeven_move_pct": (round(100.0 * spread / (adelta * spot), 3)
                               if adelta > 0 else None),
        # How far it must move to DOUBLE. This is the number that makes 0DTE
        # attractive and it belongs next to the one that makes it lethal.
        "double_move_pct": (round(100.0 * ask / (adelta * spot), 3)
                            if adelta > 0 else None),
        # Theta as a share of the whole premium. At 0DTE this routinely exceeds
        # 100%: the SPY 764 call decayed 7.8x its own ask. That is the headline
        # risk and it is why this leads the tile.
        "theta_burn_pct": (round(100.0 * abs(theta) / ask, 0)
                           if theta is not None and ask > 0 else None),
    }


def is_tradeable(m: Optional[dict]) -> bool:
    """Does this contract clear the house floors? PURE.

    A contract failing this is not shown as a suggestion. It may still exist on
    the chain and be wildly traded — the 765 call above did 828,288 contracts at
    a 66% spread — which is exactly why the floor is applied rather than trusting
    volume as a proxy for tradeability.
    """
    if not m:
        return False
    d = m.get("delta")
    sp = m.get("spread_pct")
    v = m.get("day_volume")
    b = m.get("bid")
    if d is None or sp is None or b is None:
        return False
    return bool(
        MIN_DELTA <= abs(d) <= MAX_DELTA
        and sp <= MAX_SPREAD_PCT
        and b >= MIN_BID
        and (v or 0) >= MIN_DAY_VOLUME
    )


def pick_contract(metrics: list[dict], side: str) -> Optional[dict]:
    """The suggested contract for one side. PURE.

    Nearest to TARGET_DELTA among those that clear the floors, tie-broken on the
    tighter spread. Not the cheapest and not the most traded: on 0DTE both of
    those select for the strikes that expire worthless.
    """
    want = "call" if side == "call" else "put"
    ok = [m for m in metrics if m.get("side") == want and is_tradeable(m)]
    if not ok:
        return None
    return min(ok, key=lambda m: (round(abs(abs(m["delta"]) - TARGET_DELTA), 3),
                                  m.get("spread_pct") or 9e9,
                                  m.get("strike") or 0.0))


# ── how far can it actually go today? ────────────────────────────────────────
# Every "it only needs to move 0.06%" is meaningless without the name's own
# scale. 3% is a crash in SPY and a Tuesday in TSLA, so a fixed threshold would
# be wrong on both. The chain prices its own answer: annualised IV divided by
# sqrt(252) is the one-session sigma the market is charging for.
TRADING_DAYS = 252


def expected_move_pct(metrics: list[dict], spot: Optional[float]) -> Optional[float]:
    """One-session sigma from ATM implied vol, in percent. PURE.

    Taken from the strike nearest spot, averaged across the call and the put so
    a single stale quote cannot set the scale for the whole row.
    """
    spot = _f(spot)
    if not spot or spot <= 0 or not metrics:
        return None
    with_iv = [m for m in metrics if _f(m.get("iv")) and _f(m.get("strike"))]
    if not with_iv:
        return None
    nearest = min(abs(_f(m["strike"]) - spot) for m in with_iv)
    atm = [_f(m["iv"]) for m in with_iv
           if abs(_f(m["strike"]) - spot) <= nearest + 1e-9]
    if not atm:
        return None
    iv = sum(atm) / len(atm)
    if iv <= 0:
        return None
    return round(100.0 * iv / (TRADING_DAYS ** 0.5), 3)


def moves_needed(contract: Optional[dict], expected: Optional[float]) -> Optional[float]:
    """`double_move_pct` expressed in the name's own daily sigmas. PURE.

    This is the number that compares ACROSS symbols. Raw `double_move_pct`
    cannot: SPY's 0.06% and TSLA's 0.94% are not on the same scale, and ranking
    a board by the raw figure would put SPY on top every single day for reasons
    that have nothing to do with the trade being better.
    """
    if not contract or not expected or expected <= 0:
        return None
    d = _f(contract.get("double_move_pct"))
    return round(d / expected, 2) if d is not None else None


# ── the gamma regime — the banner over the whole board ───────────────────────
# Ajay chose "calls/puts inside a pinned/unpinned banner". The banner answers a
# question that comes BEFORE which strike: is today a day when buying premium
# can work at all?
REGIME_PINNED = "PINNED"
REGIME_AMPLIFYING = "AMPLIFYING"
REGIME_UNKNOWN = "UNKNOWN"


def regime_from_gex(gex: Optional[dict], spot: Optional[float],
                    expected_pct: Optional[float] = None) -> dict:
    """Read `opex.net_gex_and_walls` into a plain-language regime. PURE.

    The sign rule is NOT re-derived here, and neither is the verdict: `opex`
    publishes its own `regime` string ("pinning"/"amplifying") off the same
    numbers, so this consumes that rather than re-testing `net > 0`. One owner
    for the rule means the two can never disagree about a day.

    What this adds is the reading for someone BUYING premium, which is the
    opposite of what a pin means to someone selling it.
    """
    out = {"regime": REGIME_UNKNOWN, "net_gex": None, "call_wall": None,
           "put_wall": None, "flip_strike": None, "magnet": None,
           "inside_walls": None, "below_flip": None, "oi_coverage_pct": None,
           "flip_out_of_reach_pct": None, "net_vs_largest_node": None,
           "fragile": False, "note": None}
    if not gex:
        out["note"] = "No dealer-gamma read for today's chain."
        return out

    net = _f(gex.get("net_gex_dollars"))
    cw, pw = _f(gex.get("call_wall")), _f(gex.get("put_wall"))
    flip = _f(gex.get("flip_strike"))
    spot = _f(spot)
    out.update({"net_gex": net, "call_wall": cw, "put_wall": pw,
                "flip_strike": flip, "magnet": _f(gex.get("magnet_strike")),
                "oi_coverage_pct": _f(gex.get("oi_coverage_pct"))})

    src = (gex.get("regime") or "").lower()
    if src not in ("pinning", "amplifying"):
        out["note"] = "No dealer-gamma read for today's chain."
        return out

    if spot is not None and cw is not None and pw is not None and pw < cw:
        out["inside_walls"] = bool(pw <= spot <= cw)
    # Below the flip dealers are net SHORT gamma and hedge WITH the move — on a
    # 0DTE the most actionable line on the chain, WHEN the underlying can
    # plausibly reach it. Measured live 2026-08-24, the raw flip sat 29% from
    # spot on SPY and 53% on TSLA: walking strikes for a sign change finds one
    # in the far tail where a few contracts of OI decide it. A level today's
    # tape cannot touch is not a regime boundary, so it is suppressed rather
    # than drawn. The bound is the name's own expected session move, not a
    # fixed percentage, for the reason `expected_move_pct` exists at all.
    if spot is not None and flip is not None and expected_pct and expected_pct > 0:
        away = abs(100.0 * (flip - spot) / spot)
        if away <= FLIP_RELEVANT_SIGMAS * expected_pct:
            out["below_flip"] = bool(spot < flip)
        else:
            out["flip_strike"] = None
            out["flip_out_of_reach_pct"] = round(away, 1)

    if src == "pinning":
        out["regime"] = REGIME_PINNED
        out["note"] = (
            "Dealers are net LONG gamma — they sell strength and buy weakness, "
            "which suppresses movement. Buying 0DTE premium fights that, and "
            "theta is on the other side."
        )
        if out["inside_walls"]:
            out["note"] += (f" Spot sits between the put wall {pw} and the call "
                            f"wall {cw}, where the suppression is strongest.")
    else:
        out["regime"] = REGIME_AMPLIFYING
        out["note"] = (
            "Dealers are net SHORT gamma — they hedge WITH the move, which "
            "amplifies it. This is the regime where a directional 0DTE has "
            "room, and also the one where a move against you goes further."
        )
    if out["below_flip"] is True and flip is not None:
        out["note"] += (f" Spot is BELOW the gamma flip at {flip}: moves get "
                        f"amplified until it reclaims that level.")
    elif out["below_flip"] is False and flip is not None:
        out["note"] += (f" Spot is above the gamma flip at {flip}, the damped "
                        f"side of the profile.")

    # A net computed from a fraction of the open interest is a guess wearing a
    # number's clothes. opex measures the coverage; refusing to hide it is the
    # difference between a reading and a decoration.
    # A net that is SMALLER than one of its own constituents is decided by
    # near-cancellation, and its sign is not a fact about the day. Demonstrated
    # rather than assumed: TSLA read +3.3M then -48.7M on two calls seconds
    # apart on 2026-08-24 — the verdict flipped from PINNED to AMPLIFYING —
    # while its largest single node was 137M. The ratio is reported so the
    # banner can decline to be confident instead of picking a side.
    top = gex.get("top_nodes") or []
    biggest = max((abs(_f(n.get("gex_dollars")) or 0.0) for n in top), default=0.0)
    if biggest > 0 and net is not None:
        conf = abs(net) / biggest
        out["net_vs_largest_node"] = round(conf, 2)
        if conf < 1.0:
            out["fragile"] = True
            out["note"] += (
                f" The net is only {conf:.2f}x the largest single strike's gamma, "
                f"so the sign rests on near-cancellation and can invert on a "
                f"quote tick — read the regime as UNSETTLED, not as a verdict.")

    cov = out["oi_coverage_pct"]
    if cov is not None and cov < 80.0:
        out["note"] += (f" Gamma was priced on only {cov}% of open interest — "
                        f"treat the regime as low confidence.")
    return out


# ── the fetch — one chain per symbol, reusing opex's puller ──────────────────
def chain_for(symbol: str, expiry: Optional[str] = None) -> tuple[list[dict], Optional[float], Optional[str]]:
    """Today's contracts for one symbol. Returns (chain, spot, expiry).

    Reuses `opex._fetch_contracts` rather than opening a second door to the same
    endpoint — one place gets the pagination, key handling and failure mode
    right. Filtering to the same-day expiry happens here rather than trusting
    `compute_opex`'s "nearest": on a Wednesday the nearest expiry for a name
    without dailies is Friday, and silently showing a 2DTE chain on a board
    labelled 0DTE is the exact error this board must not make.
    """
    from . import opex

    want = expiry or today_et()
    try:
        contracts, spot = opex._fetch_contracts(symbol)
    except Exception as exc:                      # network/parse — degrade, never raise
        log.warning("%s: 0DTE chain fetch failed: %s", symbol, exc)
        return [], None, None
    chain = [c for c in (contracts or [])
             if ((c.get("details") or {}).get("expiration_date") == want)]
    if not chain:
        return [], spot, None
    return chain, spot, want


def _gex_for_chain(chain: list[dict], spot: Optional[float]) -> Optional[dict]:
    """Dealer gamma for the SAME-DAY chain only.

    `opex.compute_opex` computes this for the nearest expiry across the whole
    snapshot. Recomputing it here on the filtered chain is deliberate: on a
    0DTE board the regime that matters is the one expiring TODAY, and today's
    gamma is where the pinning actually bites. The sign rule and the scale are
    `opex`'s — only the input set differs.
    """
    from . import opex

    rows = []
    for c in chain:
        d = c.get("details") or {}
        k, typ = d.get("strike_price"), d.get("contract_type")
        if k is None or typ not in ("call", "put"):
            continue
        g = (c.get("greeks") or {}).get("gamma")
        if g is None:
            # Same BS fallback opex uses. dte=0 would divide by zero in the
            # model, so the floor of 1 day is passed — it only affects rows the
            # feed already failed to price, and a slightly-too-smooth gamma on
            # those is better than dropping them out of the net entirely.
            g = opex._bs_gamma(spot or 0, float(k), c.get("implied_volatility") or 0, 1)
        rows.append({"strike": k, "type": typ, "gamma": g,
                     "oi": int(c.get("open_interest") or 0)})
    if not rows:
        return None
    try:
        return opex.net_gex_and_walls(rows, spot)
    except Exception as exc:
        log.warning("0DTE gamma read failed: %s", exc)
        return None


def _max_pain_for_chain(chain: list[dict], spot: Optional[float]):
    from . import opex

    call_oi: dict = {}
    put_oi: dict = {}
    for c in chain:
        d = c.get("details") or {}
        k, typ = d.get("strike_price"), d.get("contract_type")
        if k is None or typ not in ("call", "put"):
            continue
        oi = int(c.get("open_interest") or 0)
        (call_oi if typ == "call" else put_oi)[k] = \
            (call_oi if typ == "call" else put_oi).get(k, 0) + oi
    try:
        return opex.max_pain(call_oi, put_oi, spot)
    except Exception:
        return None


def read_symbol(symbol: str, expiry: Optional[str] = None) -> Optional[dict]:
    """One 0DTE row: both suggested contracts, the regime, and the cost truth.

    Returns None when the name has no same-day expiry — that is the ordinary
    case for most tickers and it degrades to absent from the board rather than
    to a row claiming something it cannot support.
    """
    sym = (symbol or "").upper()
    chain, spot, exp = chain_for(sym, expiry)
    if not chain or not exp:
        return None

    metrics = [m for m in (contract_metrics(c, spot) for c in chain) if m]
    if not metrics:
        return None

    call = pick_contract(metrics, "call")
    put = pick_contract(metrics, "put")
    exp_move = expected_move_pct(metrics, spot)
    gex = _gex_for_chain(chain, spot)
    reg = regime_from_gex(gex, spot, exp_move)
    mp = _max_pain_for_chain(chain, spot)

    # Attach the cross-symbol scale to each suggestion, so the tile can say
    # "needs 1.2 of today's expected move" instead of a bare percentage that
    # means something different on every row.
    for c in (call, put):
        if c:
            c["moves_needed"] = moves_needed(c, exp_move)

    tradeable = [m for m in metrics if is_tradeable(m)]
    mp = mp or {}
    return {
        "symbol": sym,
        "expiry": exp,
        "spot": round(spot, 2) if spot else None,
        "call": call,
        "put": put,
        "regime": reg,
        # What the chain itself says today is worth, in percent of spot. Every
        # move number on the row is only readable against this.
        "expected_move_pct": exp_move,
        "max_pain": mp.get("max_pain_strike"),
        # Distance to the pin, taken from `opex` rather than recomputed — it
        # already publishes `pct_from_spot` off the same strike, and a second
        # arithmetic path to one number is a second chance to disagree.
        "max_pain_pct": mp.get("pct_from_spot"),
        # An ambiguous pin is not a pin. `opex` flags the runner-up landing
        # within 1% of the minimum, and the banner must not draw a magnet the
        # OI grid does not actually support.
        "max_pain_tie": bool(mp.get("max_pain_tie")),
        "chain_size": len(chain),
        "priced": len(metrics),
        # Stated because it is the honest denominator: how few of a
        # 358-contract chain actually clear the cost floors.
        "tradeable": len(tradeable),
        # Single-name gamma can invert the sign rule outright. opex flags this
        # and the flag is carried, not dropped.
        "gex_reliability": "index" if sym in _index_like() else "single_name",
    }


def _index_like() -> frozenset:
    from . import opex
    return opex.INDEX_LIKE


# One board read is up to 13 symbols x 6 pages of chain. Cheap to cache and
# expensive not to: this key is shared with the SEPA scan and the demand board,
# and a page refresh loop that rate-limits it would break three features to
# speed up one. 60s because 0DTE greeks genuinely move that fast — anything
# longer would show a stale delta on a decaying contract.
CACHE_TTL_SEC = 60
_cache: dict = {}


def session_state(now_et=None) -> dict:
    """Where in the trading day this read is happening.

    Not decoration. After the close on expiry day the chain is settled: every
    OTM strike is a penny with a 200% spread, and the delta band that defines a
    tradeable contract has collapsed to almost nothing. Measured on 2026-08-24
    after the bell, only 8 of 13 names had ANY contract clearing the floors. A
    board that thin is correct, but without this it looks broken — so the state
    is published and the UI says which one it is.
    """
    from datetime import datetime as _dt
    if now_et is None:
        now_et = _dt.now(timezone.utc) - timedelta(hours=4)
    mins = now_et.hour * 60 + now_et.minute
    weekday = now_et.weekday() < 5
    if not weekday:
        return {"state": "closed", "label": "Market closed — weekend.",
                "actionable": False}
    if mins < 9 * 60 + 30:
        return {"state": "pre", "label": "Before the open — quotes are indicative.",
                "actionable": False}
    if mins >= 16 * 60:
        return {"state": "post", "actionable": False,
                "label": ("After the close on expiry day — these contracts have "
                          "settled. Strikes still listed are pennies with wide "
                          "spreads; this is the day's record, not a live board.")}
    # The last hour is where 0DTE theta goes vertical. Worth saying out loud.
    if mins >= 15 * 60:
        return {"state": "power", "actionable": True,
                "label": ("Final hour — 0DTE decay is at its steepest and a "
                          "position that does not work immediately will not.")}
    return {"state": "open", "label": "Regular hours.", "actionable": True}


def board(symbols: Optional[list[str]] = None, expiry: Optional[str] = None,
          fresh: bool = False) -> dict:
    """Every name with a same-day chain, read in parallel.

    Threaded because each read is one network round trip and 13 of them
    serially is a page load nobody waits for. The pool is small: this shares an
    API budget with the SEPA scan and the demand board, and a burst that gets
    the key rate-limited would break three features to speed up one.
    """
    from concurrent.futures import ThreadPoolExecutor
    import time as _time

    syms = [s.upper() for s in (symbols or UNIVERSE) if s]
    ck = (tuple(syms), expiry or today_et())
    hit = _cache.get(ck)
    if hit and not fresh and (_time.time() - hit[0]) < CACHE_TTL_SEC:
        out = dict(hit[1])
        out["cached_age_sec"] = int(_time.time() - hit[0])
        return out

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for r in pool.map(lambda s: _safe_read(s, expiry), syms):
            if r:
                rows.append(r)

    rows.sort(key=sort_key)
    out = {
        "expiry": expiry or today_et(),
        "rows": rows,
        "asked": len(syms),
        "with_chain": len(rows),
        # How many rows carry at least one contract clearing the floors. The
        # honest headline: on a settled chain this is far below `with_chain`.
        "with_contract": sum(1 for r in rows if r.get("call") or r.get("put")),
        "session": session_state(),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "cached_age_sec": 0,
        "disclaimer": DISCLAIMER,
    }
    _cache[ck] = (_time.time(), out)
    return out


def _safe_read(sym: str, expiry: Optional[str]) -> Optional[dict]:
    """One bad symbol must not empty the board."""
    try:
        return read_symbol(sym, expiry)
    except Exception as exc:
        log.warning("%s: 0DTE read failed: %s", sym, exc)
        return None


def sort_key(r: dict):
    """Least work required first, in the name's own sigmas. PURE.

    Ranked on `moves_needed` — how many expected session moves the underlying
    must deliver for the position to double — NOT on raw `double_move_pct`.
    The raw figure is not comparable across symbols: SPY needed 0.06% and TSLA
    0.94% on 2026-08-24, and sorting on that puts the lowest-volatility name
    first every single day for a reason that has nothing to do with the trade.

    Rows with no tradeable contract sort LAST. A missing number must never look
    like the best one — the Into Supply board shipped exactly that bug once,
    and opened on an alphabetical list that looked ranked.
    """
    best = 9e9
    for side in ("call", "put"):
        c = r.get(side) or {}
        v = c.get("moves_needed")
        if v is not None and float(v) < best:
            best = float(v)
    return (0 if best < 9e9 else 1, best, r.get("symbol") or "")
