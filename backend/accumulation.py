"""Real-time accumulation / distribution tracker (phase 2).

Reads the live trade tape and classifies each print against the prevailing
NBBO — the **quote test**: a trade at/above the ask is buyer-initiated
(accumulation), at/below the bid is seller-initiated (distribution). Flow is
split by venue: off-exchange prints (flagged by the trade's ``trfi`` field —
FINRA TRF / ADF) are the **dark-pool** lane where institutions hide size, so a
rising dark-pool *buy* ratio is the proxy for stealth accumulation.

Fed from the SINGLE Massive WebSocket connection (the account allows only one
concurrent socket), which carries:
  - ``T.<sym>``  trades   — for every tracked symbol (price feed, phase 1)
  - ``Q.<sym>``  quotes   — for the bounded FOCUS set (portfolio + top-N)

``on_quote`` keeps the latest NBBO; ``on_trade`` classifies + accumulates into
a cumulative session tally plus a rolling time window. O(1) per event; one
bounded deque per focus symbol.

Decision read (what the card shows):
  signal          accumulation / neutral / distribution (session buy ratio)
  net_dollars     buyer $ minus seller $ (who's in control, in money)
  buy_ratio       buy_vol / (buy_vol + sell_vol)
  dark_pct        off-exchange share of volume
  dark_buy_ratio  dark buy_vol / dark classified vol  (stealth accumulation)
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import deque

# Buy-ratio thresholds for the session signal label. Conservative bands so a
# coin-flip tape reads "neutral" rather than flapping accumulation/distribution.
ACCUM_RATIO = float(os.getenv("ACCUM_SIGNAL_RATIO", "0.58"))
DISTRIB_RATIO = float(os.getenv("DISTRIB_SIGNAL_RATIO", "0.42"))
WINDOW_SEC = float(os.getenv("ACCUM_WINDOW_SEC", "900"))      # rolling 15 min
MAX_FOCUS = int(os.getenv("ACCUM_MAX_FOCUS", "40"))


def _new_session() -> dict:
    return dict(
        trades=0, vol=0.0,
        buy_vol=0.0, sell_vol=0.0, buy_dol=0.0, sell_dol=0.0,
        dark_vol=0.0, dark_dol=0.0, dark_buy_vol=0.0, dark_sell_vol=0.0,
    )


def _ratio(buy: float, sell: float):
    tot = buy + sell
    return (buy / tot) if tot else None


def _signal(buy_vol: float, sell_vol: float) -> str:
    r = _ratio(buy_vol, sell_vol)
    if r is None:
        return "neutral"
    if r >= ACCUM_RATIO:
        return "accumulation"
    if r <= DISTRIB_RATIO:
        return "distribution"
    return "neutral"


class AccumulationTracker:
    def __init__(self, window_sec: float = WINDOW_SEC, max_focus: int = MAX_FOCUS):
        self.window_sec = window_sec
        self.max_focus = max_focus
        self._nbbo: dict[str, tuple] = {}       # sym -> (bid, ask, ts)
        self._sess: dict[str, dict] = {}        # sym -> cumulative session stats
        self._roll: dict[str, deque] = {}       # sym -> deque[(ts, side, size, dollars, dark)]
        self._focus: set[str] = set()
        self._lock = asyncio.Lock()

    # ── focus set ────────────────────────────────────────────────────────
    def set_focus(self, symbols) -> set:
        """Replace the focus set (bounded). Returns the symbols newly added."""
        ordered = list(dict.fromkeys(s.upper() for s in symbols if s))[: self.max_focus]
        new = set(ordered)
        added = new - self._focus
        self._focus = new
        # Drop state for symbols no longer in focus so memory stays bounded.
        for sym in list(self._nbbo):
            if sym not in new:
                self._nbbo.pop(sym, None)
        return added

    def add_focus(self, sym: str) -> bool:
        """Add one symbol on demand (e.g. a card the user just opened). Returns
        True if newly added. Evicts an arbitrary symbol if already at capacity."""
        sym = sym.upper()
        if sym in self._focus:
            return False
        if len(self._focus) >= self.max_focus:
            self._focus.pop()
        self._focus.add(sym)
        return True

    @property
    def focus(self) -> set:
        return set(self._focus)

    def in_focus(self, sym: str) -> bool:
        return sym in self._focus

    # ── ingest ───────────────────────────────────────────────────────────
    def on_quote(self, sym: str, bid, ask, ts: float | None = None) -> None:
        if sym in self._focus and (bid or ask):
            self._nbbo[sym] = (bid, ask, ts or time.time())

    def _classify(self, sym: str, price: float) -> int:
        q = self._nbbo.get(sym)
        if not q:
            return 0
        bid, ask, _ = q
        if ask and price >= ask:
            return 1
        if bid and price <= bid:
            return -1
        if bid and ask:
            mid = (bid + ask) / 2
            return 1 if price > mid else (-1 if price < mid else 0)
        return 0

    async def on_trade(self, sym: str, price, size, is_dark: bool, ts: float | None = None) -> None:
        if sym not in self._focus or price is None:
            return
        size = float(size or 0)
        ts = ts or time.time()
        side = self._classify(sym, price)
        dollars = price * size
        async with self._lock:
            s = self._sess.setdefault(sym, _new_session())
            s["trades"] += 1
            s["vol"] += size
            if side > 0:
                s["buy_vol"] += size
                s["buy_dol"] += dollars
            elif side < 0:
                s["sell_vol"] += size
                s["sell_dol"] += dollars
            if is_dark:
                s["dark_vol"] += size
                s["dark_dol"] += dollars
                if side > 0:
                    s["dark_buy_vol"] += size
                elif side < 0:
                    s["dark_sell_vol"] += size
            dq = self._roll.setdefault(sym, deque())
            dq.append((ts, side, size, dollars, is_dark))
            cutoff = ts - self.window_sec
            while dq and dq[0][0] < cutoff:
                dq.popleft()

    # ── read ─────────────────────────────────────────────────────────────
    def snapshot(self, sym: str) -> dict | None:
        sym = sym.upper()
        s = self._sess.get(sym)
        if not s:
            return None
        # Roll up the live window from the deque on demand.
        wb = ws = wbd = wsd = wdv = wdbv = wdsv = wv = 0.0
        wt = 0
        for _ts, side, size, dollars, dark in self._roll.get(sym, ()):  # noqa: E501
            wt += 1
            wv += size
            if side > 0:
                wb += size
                wbd += dollars
            elif side < 0:
                ws += size
                wsd += dollars
            if dark:
                wdv += size
                if side > 0:
                    wdbv += size
                elif side < 0:
                    wdsv += size
        nbbo = self._nbbo.get(sym)
        return {
            "symbol": sym,
            "signal": _signal(s["buy_vol"], s["sell_vol"]),
            "session": {
                "trades": s["trades"],
                "volume": s["vol"],
                "buy_volume": s["buy_vol"],
                "sell_volume": s["sell_vol"],
                "buy_dollars": round(s["buy_dol"], 2),
                "sell_dollars": round(s["sell_dol"], 2),
                "net_dollars": round(s["buy_dol"] - s["sell_dol"], 2),
                "buy_ratio": _ratio(s["buy_vol"], s["sell_vol"]),
                "dark_volume": s["dark_vol"],
                "dark_pct": (s["dark_vol"] / s["vol"]) if s["vol"] else None,
                "dark_buy_ratio": _ratio(s["dark_buy_vol"], s["dark_sell_vol"]),
            },
            "window_sec": self.window_sec,
            "window": {
                "trades": wt,
                "volume": wv,
                "net_dollars": round(wbd - wsd, 2),
                "buy_ratio": _ratio(wb, ws),
                "dark_pct": (wdv / wv) if wv else None,
                "dark_buy_ratio": _ratio(wdbv, wdsv),
                "signal": _signal(wb, ws),
            },
            "nbbo": {"bid": nbbo[0], "ask": nbbo[1]} if nbbo else None,
        }

    def snapshot_all(self) -> dict:
        return {sym: self.snapshot(sym) for sym in self._focus if sym in self._sess}


# Process-wide singleton fed by the live WS consumer.
tracker = AccumulationTracker()
