"""🚩 The tab live over `/events` (GG LIVE spec rev 2, §3.5 — P3, 2026-11-09).

Ajay 2026-11-09: "same for reuglar Gajjlas tab as well need it to be more live". Owner decision (§7 #16, Ajay): "I only
need this setup for myself the owner of the app".

ONE event type, `gajjala.update`, published through the existing bus (`events.publish`) — no new SSE endpoint, no
change to the bus, `SSE_HEADERS` or `quote.update`. Three payload kinds, keys FIXED (QUOTES_KEYS / QUOTE_KEYS /
PASS_KEYS / LANE_KEYS — a test pins them):

  quotes  {"kind", "variant", "quotes": {SYM: {"price", "as_of_epoch", "vs"}}} — per variant (the board's tab key:
          gajjala | gajjala_1m | gajjala_audited), at most one batch every GG_LIVE_QUOTE_BATCH_SEC, only the symbols
          with a new FILTERED print since that variant's last batch (the hub filters every print ONCE through
          `live_hub.PRINT_KINDS` and routes it here only for a variant with live interest). `vs` = the poll's OWN
          vs-words function (INJECTED by chart_maps/api.py through `set_vs_fn` — this module never imports the card
          module: the 2026-10-21 import guard keeps every chart_maps/gajjala file off it) called with THAT variant's
          level — the ONE engine of the poll's words, never a second formula; no level, or nothing injected → null.
  pass    {"kind", "variant", "pass_id", "finished_at_epoch"} — a data-free nudge: the board re-GETs.
  lane    {"kind", "day", "changed_at_epoch"} — a data-free nudge: NO symbol, qty, price or P&L key (the bus reaches
          every signed-in tab — the household included).

Delivery: the bus broadcasts every event to every connected `/events` tab (events/sse.py — no per-user queue). The
owner-only delivery Ajay asked for needs a bus change (a user tag on the subscriber queue) that the main session owns;
until then `gajjala.update` carries only public prices and data-free nudges (docs/gajjala/live_tab_2026_11_09.md).

Called by the hub (`backend/live_hub.py`, §3.2): `on_print` from the read loop (sync, O(1), never raises), `flush`
from the hub's 1 s loop, `on_pass` / `on_lane_change` on a pointer change. Display only: the pass, the store, the
pushes and the lane never read anything here. UNMEASURED — freshness, not a result.
"""
from __future__ import annotations

import logging
import math
import threading
from datetime import date, datetime, timezone
from typing import Callable, Optional

log = logging.getLogger("chart_maps.gajjala.live_events")

EVENT_TYPE = "gajjala.update"
GG_LIVE_QUOTE_BATCH_SEC = 1.0          # MINE — spec §3.5: one quotes batch per variant per second at most

KIND_QUOTES = "quotes"
KIND_PASS = "pass"
KIND_LANE = "lane"
KINDS = (KIND_QUOTES, KIND_PASS, KIND_LANE)
QUOTES_KEYS = ("kind", "variant", "quotes")
QUOTE_KEYS = ("price", "as_of_epoch", "vs")
PASS_KEYS = ("kind", "variant", "pass_id", "finished_at_epoch")
LANE_KEYS = ("kind", "day", "changed_at_epoch")

_lock = threading.Lock()
_vs_fn: Optional[Callable] = None      # the poll's vs-words function — set by chart_maps/api.py (set_vs_fn), never imported
_pending: dict = {}                    # variant → {SYM: {"price", "as_of_epoch", "level"}}
_last_batch: dict = {}                 # variant → epoch of its last published quotes batch


def reset() -> None:
    """Forget every pending print and batch clock (tests; an api restart starts empty anyway)."""
    with _lock:
        _pending.clear()
        _last_batch.clear()


def set_vs_fn(fn: Optional[Callable]) -> None:
    """Inject the poll's vs-words function `fn(price, level, now_et) -> {kind, text} | None` (chart_maps/api.py hands
    in the SAME function object its route uses). None / not callable → no `vs` words (null) until set."""
    global _vs_fn
    _vs_fn = fn if callable(fn) else None


def vs_fn() -> Optional[Callable]:
    """The injected vs-words function, or None."""
    return _vs_fn


# ── variants ─────────────────────────────────────────────────────────────────────────────────────────────────────
def variant_keys() -> tuple:
    """The board keys a `gajjala.update` names — each Variant's `tab` (variant.py), the FE's GgVariantKey. Never
    retyped here."""
    from . import variant as V
    return tuple(v.tab for v in V.VARIANTS)


def pass_variants(collection: str) -> tuple:
    """The board keys whose pass pointer lives in `collection`, off the store's own naming (GajjalaStore.physical —
    GGA BORROWS gajjala_passes, GG1 writes gajjala_1m_passes): "gajjala_passes" → ("gajjala", "gajjala_audited");
    "gajjala_1m_passes" → ("gajjala_1m",); anything else → ()."""
    from . import store as S
    from . import variant as V
    out = []
    for v in V.VARIANTS:
        try:
            phys = S.GajjalaStore(variant=v).physical(S.PASSES)
        except Exception as exc:                                    # noqa: BLE001 — a nudge never fails the hub
            log.debug("live events: pass collection of %s: %s", v.tab, exc)
            continue
        if phys == collection:
            out.append(v.tab)
    return tuple(out)


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _epoch(x) -> Optional[float]:
    """A stamp → epoch seconds: a datetime (naive = UTC, the Mongo client is not tz-aware), an ISO string (naive =
    UTC), or a finite number (epoch seconds). Anything else → None."""
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, str):
        try:
            x = datetime.fromisoformat(x.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(x, datetime):
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x.timestamp()
    return None


def _day(d) -> Optional[str]:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if isinstance(d, str) and len(d.strip()) >= 10:
        s = d.strip()[:10]
        try:
            return date.fromisoformat(s).isoformat()
        except ValueError:
            return None
    return None


def _price(p) -> Optional[float]:
    if isinstance(p, bool) or not isinstance(p, (int, float)):
        return None
    f = float(p)
    return f if math.isfinite(f) and f > 0 else None


def _print_epoch(pr: dict) -> Optional[float]:
    """The print's time: the SIP stamp (`t_ms`) when the feed carried one, else the receive time (`recv`)."""
    t = pr.get("t_ms")
    if isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(float(t)) and t > 0:
        return float(t) / 1000.0
    return _epoch(pr.get("recv"))


def _publish(payload: dict) -> None:
    from events import publish
    publish(EVENT_TYPE, payload)


# ── the hub's calls ──────────────────────────────────────────────────────────────────────────────────────────────
def on_print(variant: str, pr: dict, level) -> None:
    """One FILTERED print for a variant with live interest (the hub's routing). Latest wins per (variant, symbol) —
    an older print never replaces a newer one. Sync, O(1), never raises."""
    try:
        if not isinstance(pr, dict) or not isinstance(variant, str) or variant not in variant_keys():
            return
        sym = pr.get("sym")
        px = _price(pr.get("p"))
        at = _print_epoch(pr)
        if not isinstance(sym, str) or not sym.strip() or px is None or at is None:
            return
        sym = sym.strip().upper()
        with _lock:
            slot = _pending.setdefault(variant, {})
            prev = slot.get(sym)
            if prev is not None and prev["as_of_epoch"] > at:
                return
            slot[sym] = {"price": px, "as_of_epoch": at, "level": level if isinstance(level, dict) else None}
    except Exception as exc:                                        # noqa: BLE001 — the read loop never stops here
        log.debug("live events: on_print failed: %s", exc)


def flush(now, alive: Optional[Callable[[str, str], bool]] = None) -> list:
    """Publish the due quote batches: variants ascending, symbols ascending (§3.7); a variant whose last batch is
    younger than GG_LIVE_QUOTE_BATCH_SEC keeps its prints for the next call (latest wins). `alive(variant, sym)` —
    optional, the hub's interest check — drops a print whose interest expired before the batch. Returns the payloads
    published (tests). Never raises."""
    from chart_maps import board
    out: list = []
    try:
        now_s = _epoch(now)
        if now_s is None:
            return out
        now_et = datetime.fromtimestamp(now_s, tz=board.ET)
        due: dict = {}
        with _lock:
            for v in sorted(_pending):
                slot = _pending[v]
                if not slot:
                    continue
                last = _last_batch.get(v)
                if last is not None and now_s - last < GG_LIVE_QUOTE_BATCH_SEC:
                    continue
                due[v] = slot
                _pending[v] = {}
        for v in sorted(due):
            quotes: dict = {}
            for sym in sorted(due[v]):
                if alive is not None:
                    try:
                        if not alive(v, sym):
                            continue
                    except Exception:                               # noqa: BLE001 — a broken check publishes nothing
                        continue
                e = due[v][sym]
                fn = _vs_fn
                try:
                    vs = fn(e["price"], e["level"], now_et) if (fn is not None and e["level"] is not None) else None
                except Exception as exc:                            # noqa: BLE001 — display words never fail a quote
                    log.debug("live events: %s vs words failed: %s", sym, exc)
                    vs = None
                quotes[sym] = {"price": e["price"], "as_of_epoch": e["as_of_epoch"], "vs": vs}
            if not quotes:
                continue
            payload = {"kind": KIND_QUOTES, "variant": v, "quotes": quotes}
            with _lock:
                _last_batch[v] = now_s
            _publish(payload)
            out.append(payload)
    except Exception as exc:                                        # noqa: BLE001 — the hub loop never stops here
        log.debug("live events: flush failed: %s", exc)
    return out


def on_pass(variant: str, pass_id, finished_at) -> Optional[dict]:
    """A new pass pointer for one board key → the data-free `pass` nudge. Unknown variant / no id / no stamp →
    nothing. Never raises."""
    try:
        if not isinstance(variant, str) or variant not in variant_keys():
            return None
        if not isinstance(pass_id, str) or not pass_id.strip():
            return None
        fin = _epoch(finished_at)
        if fin is None:
            return None
        payload = {"kind": KIND_PASS, "variant": variant, "pass_id": pass_id, "finished_at_epoch": fin}
        _publish(payload)
        return payload
    except Exception as exc:                                        # noqa: BLE001
        log.debug("live events: on_pass failed: %s", exc)
        return None


def on_pass_pointer(collection: str, pass_id, finished_at) -> list:
    """One pass pointer moved in `collection` → one `pass` nudge per board key that reads it (`pass_variants`)."""
    out = []
    for v in pass_variants(collection):
        p = on_pass(v, pass_id, finished_at)
        if p is not None:
            out.append(p)
    return out


def on_lane_change(day, now) -> Optional[dict]:
    """The lane's docs changed today → the data-free `lane` nudge (day + time only). Never raises."""
    try:
        d = _day(day)
        at = _epoch(now)
        if d is None or at is None:
            return None
        payload = {"kind": KIND_LANE, "day": d, "changed_at_epoch": at}
        _publish(payload)
        return payload
    except Exception as exc:                                        # noqa: BLE001
        log.debug("live events: on_lane_change failed: %s", exc)
        return None
