"""Index zones — SPY and QQQ supply/demand structure, computed overnight.

Ajay 2026-09-16: *"Can you create a SPY demand and supply zone please for me?
and also QQQ supply and demand zone and keep them always in the in demand zone
page. I need everything calculation overnight."*

WHAT THIS IS
------------
A PINNED context strip at the top of the Back in Demand tab: where SPY and QQQ
are standing inside their own supply/demand structure. It is read by the page,
never derived per request — the bands are drawn once overnight and stored.

WHAT THIS IS NOT
----------------
It gates nothing, alerts nothing, orders nothing, enters no lane and claims NO
edge. Every structural S/D read measured this month came back null
(band_structure no_signal, deep_levels no_signal, enterable no_signal), so the
copy on this strip states position and distance and stops there — no verdict,
no entry read, no target, no advice.

THE BASIS RULE
--------------
STRUCTURE IS READ OFF CLOSED BARS. `as_of` / `close` / `bands` / `ceiling` /
`floor` / `room_pct` / `drop_pct` / `sentence` / `bars` are all drawn from the
last CLOSED session and never move during the day. A live print says only WHERE
PRICE IS inside that structure and lands in its own keys via `with_live`:
`live_px`, `live_dist_pct`, `live_chg_pct`, `live_in_band`, `live_side`,
`price_basis`. This is the 2026-09-16 hot-sectors correction — a column
labelled with today that carried a snapshot was the worst bug of that week — so
nothing here is allowed to overwrite a stored number with a snapshot.

THE LIVE VOCABULARY, in one place (the FE renders these verbatim)
----------------------------------------------------------------
    live_side       one of LIVE_SIDES:
                      "in"      the print is inside a band -> `live_in_band`
                                is THAT band
                      "above"   above every band in the set
                      "below"   below every band in the set
                      "between" outside every band but not past the whole set
                                — the gap between two bands
    live_in_band    the band the print is in, and ONLY that. It is None for
                    every side except "in": there is no "the band it was last
                    in", and nothing downstream may invent one.
    live_dist_pct   distance from the LIVE print to the NEAREST BAND EDGE, as a
                    percent OF THE LIVE PRINT, magnitude only (0.0 when the
                    print is inside a band, None when there are no bands) —
                    the same convention every band `dist_pct` uses, with the
                    direction carried by `live_side`, never by a sign.
    live_chg_pct    the live print against the STORED CLOSE, signed. The day
                    move, not a structural distance.
    price_basis     "live" when a usable print was overlaid, "close" otherwise.

THE STALENESS BASIS
-------------------
`date` is the day the JOB ran (the doc `_id`). `as_of` is the day the BANDS are
drawn from — `zone_store` drops today's bar, so it is the prior session, and if
the underlying store failed for a week a re-run still stamps `date` today while
`as_of` stays a week back. Staleness is measured on `as_of`, never on `date`,
so a stale store is visible instead of masked.

WHERE THE BANDS COME FROM — TWO RESOLUTIONS
-------------------------------------------
Ajay 2026-09-16, after the first strip: *"I wanna see charts with multiple
zones"* / *"SPY only my bad"* -> SPY and QQQ, a CHART each, and more bands than
the seven the board geometry draws. So each index is served at BOTH existing
resolutions, neither of them a new number:

  "board"  `demand_reentry.zone_geom()` (swing 5 / merge 4% / half-width 1.75%)
           — the geometry every demand board, push and zone tile already runs
           on. Read straight out of the `zone_store` doc. MEASURED 2026-09-16:
           SPY 7 bands, QQQ 7, median band 3.0% / 2.8% wide.
  "fine"   `price_zones` MODULE DEFAULTS (swing 4 / merge 1.75% / half-width
           0.6%) — the geometry the per-ticker /zones page has run on since
           2026-06-09. Computed in `warm()` by calling
           `price_zones.compute(frame, max_zones=None)` with NO geometry
           kwargs: passing none IS the fine setting, and nothing here retypes
           a knob. MEASURED 2026-09-16: SPY 14 bands, QQQ 13, median ~1.1%.

`DEFAULT_RESOLUTION` is the fine set — "multiple zones" is what he asked for —
and the BOARD read stays at the top level of each index entry so every consumer
built against the first cut keeps reading the same keys.

Pankaj Kenjale's SPX note (the screenshot behind the ask) draws ~0.13%-wide
hand-marked intraday levels. We do NOT copy them: hand-drawn levels are
contaminated as a measurement here (gabbar_backtest_2026_08_31). We draw OUR
bands. His rule — *"when a demand zone is broken, it becomes a supply zone and
similarly when a supply zone is broken, it becomes a demand zone"* — is ALREADY
how this engine reads: a band's `kind` is its ORIGIN (colour), and `ceiling` /
`floor` are the nearest band above / below of EITHER kind. No code change was
made for it.

`zone_store` warms at 04:05 ET on weekdays and carries SPY, QQQ and IWM with
EVERY band uncapped (max_zones=None) in BOARD geometry, on closed bars with
today's bar dropped. This module READS that store for the board set; when it
has no doc for a symbol it falls back to `zone_store.build_doc` on
`sepa.prices.load_prices` — same engine, same geometry, same closed-bar rule —
and records which source it used:

    source: "zone_store" | "computed" | "unavailable"

A symbol that cannot be read at all is STORED as unavailable with a reason. It
is never silently dropped and never faked.

THE BARS
--------
Each index entry carries `bars`: CLOSED daily candles in the {t,o,h,l,c,v}
shape `chart_maps.board._frame_to_bars` already emits, windowed by that same
module's `_zone_window` / ZONE_BARS_MIN / ZONE_BARS_MAX / ZONE_BARS_PAD over
EVERY band in BOTH sets, so the oldest swing defining the widest band is on
screen. Today's bar is dropped (`zone_store.drop_today`) — `bars_basis` says
so on the wire.

STORED SHAPE (one doc per ET session date)
------------------------------------------
    {_id: "2026-09-16", date: "2026-09-16", computed_at: <ISO>,
     source: "index_zones",
     indexes: {"SPY": <index entry>, "QQQ": <index entry>}}

    <index entry> = <board read> + {resolutions: {"board": <read>,
                                                  "fine": <read>},
                                    bars: [...], bars_basis: "closed"}

Cron: after `zone_store` finishes its 04:05 ET warm (240s budget), weekdays.
`python -m supply_demand.index_zones` warms and reports.

Configured price-structure method, NOT a book method, no Minervini cites.
Context only — not a buy signal, not advice.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# His two. A named constant so a third index is one edit, not a rewrite.
INDEXES = ("SPY", "QQQ")
COLLECTION = "index_zones"
# What wrote the day doc. The PER-SYMBOL source (zone_store | computed |
# unavailable) lives on each read; this is the job tag.
DOC_SOURCE = "index_zones"

# The read's key set, pinned. A consumer that keys on one of these can rely on
# it being present on EVERY read, available or not.
READ_KEYS = ("symbol", "name", "source", "as_of", "close", "atr14", "high_252",
             "bands", "in_band", "ceiling", "floor", "room_pct", "drop_pct",
             "available", "reason", "sentence")
# The keys `with_live` is allowed to add. It writes nowhere else — see
# `test_NEGATIVE_with_live_never_touches_a_stored_key`.
LIVE_KEYS = ("live_px", "live_dist_pct", "live_chg_pct", "live_in_band",
             "live_side", "price_basis")
# The only values `live_side` can take. Documented in the module docstring,
# served as a constant so the FE has ONE place to read the vocabulary from.
LIVE_SIDES = ("in", "above", "below", "between")

BAND_KEYS = ("kind", "lo", "hi", "mid", "touches", "strength", "side",
             "dist_pct")

# The two geometries, by name. "board" = demand_reentry.zone_geom(), read out
# of the zone_store doc. "fine" = the price_zones MODULE DEFAULTS, computed by
# passing NO geometry kwargs. Neither is a new number.
RESOLUTION_BOARD = "board"
RESOLUTION_FINE = "fine"
RESOLUTIONS = (RESOLUTION_BOARD, RESOLUTION_FINE)
# He asked for MULTIPLE zones and the board set is seven; the fine set is ~14.
DEFAULT_RESOLUTION = RESOLUTION_FINE

# `bars` are CLOSED daily candles (zone_store.drop_today), stated on the wire
# so no surface has to assume which basis it is drawing.
BARS_BASIS = "closed"

# One index entry = the BOARD read at the top level (so every consumer built
# against the first cut keeps working) + both resolutions + the chart bars.
INDEX_KEYS = READ_KEYS + ("resolutions", "bars", "bars_basis")

# The served payload's key set, pinned.
PAYLOAD_KEYS = ("date", "as_of", "indexes", "stale_days", "stale_sessions",
                "default_resolution", "note")

DISCLAIMER = ("Index structure drawn on closed bars — context for where SPY "
              "and QQQ are standing. It gates nothing, is not a signal and is "
              "not advice.")


# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------
def _num(v) -> Optional[float]:
    """Finite float or None. Guards NaN/inf reaching JSON (board._num rule)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _r2(v) -> Optional[float]:
    f = _num(v)
    return None if f is None else round(f, 2)


def _pct(delta: float, base: float) -> Optional[float]:
    """`delta` as a percentage of `base`, 2dp. None when base is unusable."""
    b = _num(base)
    d = _num(delta)
    if b is None or d is None or b <= 0:
        return None
    return round(d / b * 100.0, 2)


def _today_et(now: Optional[datetime] = None) -> date:
    return (now or datetime.now(ET)).astimezone(ET).date()


def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[COLLECTION] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("index_zones: no mongo: %s", exc)
        return None


def _unavailable(symbol: str, name: Optional[str], reason: str,
                 source: Optional[str] = None) -> dict:
    """The read for a symbol with no usable structure. Every READ_KEYS key is
    present so no consumer has to branch on shape — only on `available`."""
    sym = (symbol or "").upper()
    return {"symbol": sym, "name": name or sym, "source": source or "unavailable",
            "as_of": None, "close": None, "atr14": None, "high_252": None,
            "bands": [], "in_band": None, "ceiling": None, "floor": None,
            "room_pct": None, "drop_pct": None,
            "available": False, "reason": reason,
            "sentence": f"No stored structure for {sym} — {reason}."}


def _closed_basis(doc: dict) -> tuple[Optional[str], Optional[float]]:
    """(as_of, close) off ONE closed bar — always the same bar for both.

    `zone_store` stamps its doc with the SESSION date it warmed FOR and drops
    today's bar before computing, so the bands belong to the last row of
    `recent`, not to `date`.

    The pairing is the point (review 2026-09-16, B4): `recent_sessions` SKIPS a
    row whose low is NaN and `prev_close` does not, so reading the date from
    `recent[-1]` and the close from `prev_close` could pair one session's date
    with another session's close — a header dated Tuesday over Wednesday's
    price. So the date and the close are taken from the SAME `recent` row, the
    last one that carries both, and `prev_close` is used only when no row does
    — where the doc's own session stamp is the only date that exists, and
    `served()` shows it separately from the basis date it measures staleness
    on.
    """
    recent = doc.get("recent")
    if isinstance(recent, list):
        for row in reversed(recent):
            if not isinstance(row, dict):
                continue
            d, c = row.get("date"), _num(row.get("close"))
            if isinstance(d, str) and d and c is not None and c > 0:
                return d, c
    d = doc.get("date")
    return (d if isinstance(d, str) and d else None), _num(doc.get("prev_close"))


def _band(raw, close: float) -> Optional[dict]:
    """One stored band as the served band, or None when its geometry is
    garbage (missing / non-finite / inverted / non-positive edges)."""
    if not isinstance(raw, dict):
        return None
    lo, hi = _num(raw.get("lo")), _num(raw.get("hi"))
    if lo is None or hi is None or lo <= 0 or hi < lo:
        return None
    kind = raw.get("kind")
    kind = kind if kind in ("supply", "demand") else None
    if kind is None:
        return None
    if close < lo:
        side, dist = "above", _pct(lo - close, close)
    elif close > hi:
        side, dist = "below", _pct(close - hi, close)
    else:
        side, dist = "in", 0.0
    try:
        touches = int(raw.get("touches") or 0)
    except (TypeError, ValueError):
        touches = 0
    return {"kind": kind, "lo": _r2(lo), "hi": _r2(hi),
            "mid": _r2((lo + hi) / 2.0), "touches": touches,
            "strength": _r2(raw.get("strength")) or 0.0,
            "side": side, "dist_pct": dist}


def _money(v) -> str:
    f = _num(v)
    return "—" if f is None else f"{f:,.2f}"


def _sentence(symbol: str, close: float, as_of: Optional[str],
              in_band: Optional[dict], ceiling: Optional[dict],
              floor: Optional[dict]) -> str:
    """ONE plain line naming where price sits, built from the numbers.

    Deliberately flat. No verdict, no entry read, no target, no advice, and
    the user-facing word for a turn is "reversal" — this sentence never says
    "bounce" (test_NEGATIVE_no_sentence_says_bounce_or_claims_an_edge).
    """
    when = f"at the {as_of} close" if as_of else "at the last close"
    sym = (symbol or "").upper()
    if in_band is not None:
        tested = f"{in_band['touches']}× tested" if in_band["touches"] else "untested"
        head = (f"{sym} {_money(close)} {when} is inside a {in_band['kind']} band "
                f"{_money(in_band['lo'])}–{_money(in_band['hi'])} ({tested})")
    else:
        head = f"{sym} {_money(close)} {when} is not inside a band"
    # The KIND is named on both (review 2026-09-16, B3): the band overhead can
    # be a DEMAND band price has fallen through, which is exactly the flip
    # Pankaj's note describes, and a line that only says "next band above"
    # cannot say it.
    if ceiling is not None:
        up = (f"next {ceiling['kind']} band above {_money(ceiling['lo'])}–"
              f"{_money(ceiling['hi'])} (+{ceiling['dist_pct']}%)")
    else:
        up = "no band above in the stored structure"
    if floor is not None:
        down = (f"next {floor['kind']} band below {_money(floor['lo'])}–"
                f"{_money(floor['hi'])} (−{floor['dist_pct']}%)")
    else:
        down = "no band below in the stored structure"
    return f"{head}; {up}; {down}."


# ---------------------------------------------------------------------------
# read_doc — PURE
# ---------------------------------------------------------------------------
def read_doc(symbol: str, doc: Optional[dict], *, name: Optional[str] = None,
             source: Optional[str] = None) -> dict:
    """A `zone_store` doc -> the served read. PURE: no I/O, no clock, no
    provider. Never raises — a doc it cannot read comes back `available:
    False` with a reason, because a missing index strip must say WHY rather
    than disappear or 500 the board.

    `ceiling` / `floor` are the nearest band above / below of EITHER kind:
    broken support is resistance, and a lid that price has fallen through is
    the next shelf under it. `in_band` is the band price is standing in — the
    first one in the served high→low order when bands overlap.
    """
    sym = (symbol or "").upper()
    src = source or "zone_store"
    if not sym:
        return _unavailable(sym, name, "no symbol", source="unavailable")
    if not isinstance(doc, dict) or not doc:
        return _unavailable(sym, name, "nothing stored for it", source="unavailable")
    as_of, close = _closed_basis(doc)
    if close is None or close <= 0:
        return _unavailable(sym, name, "the stored doc carries no usable close",
                            source="unavailable")
    raw_bands = doc.get("bands")
    raw_bands = raw_bands if isinstance(raw_bands, list) else []
    bands = [b for b in (_band(r, close) for r in raw_bands) if b is not None]
    if not bands:
        return _unavailable(sym, name, "the stored doc carries no usable bands",
                            source="unavailable")
    # High -> low, the order every S/D surface draws bands in.
    bands.sort(key=lambda b: (-(b["mid"] or 0.0), -(b["hi"] or 0.0)))
    in_band = next((b for b in bands if b["side"] == "in"), None)
    above = [b for b in bands if b["side"] == "above"]
    below = [b for b in bands if b["side"] == "below"]
    ceiling = min(above, key=lambda b: b["lo"]) if above else None
    floor = max(below, key=lambda b: b["hi"]) if below else None
    return {"symbol": sym, "name": name or sym, "source": src,
            "as_of": as_of, "close": _r2(close),
            "atr14": _r2(doc.get("atr14")), "high_252": _r2(doc.get("high_252")),
            "bands": bands, "in_band": in_band,
            "ceiling": ceiling, "floor": floor,
            "room_pct": (ceiling or {}).get("dist_pct"),
            "drop_pct": (floor or {}).get("dist_pct"),
            "available": True, "reason": None,
            "sentence": _sentence(sym, close, as_of, in_band, ceiling, floor)}


# ---------------------------------------------------------------------------
# with_live — PURE
# ---------------------------------------------------------------------------
def _edge_dist_pct(bands: list, live: float) -> Optional[float]:
    """Distance from `live` to the NEAREST band edge, as a percent of `live`.

    Magnitude only — 0.0 inside a band, None with no readable band — because
    every `dist_pct` on this read is a magnitude and the DIRECTION is carried
    by `side` / `live_side`, never by a sign.
    """
    best = None
    for b in bands or []:
        lo, hi = _num((b or {}).get("lo")), _num((b or {}).get("hi"))
        if lo is None or hi is None:
            continue
        if live < lo:
            d = lo - live
        elif live > hi:
            d = live - hi
        else:
            d = 0.0
        if best is None or d < best:
            best = d
    return None if best is None else _pct(best, live)


def with_live(read: dict, px) -> dict:
    """A COPY of `read` with the live print in its OWN keys.

    The stored keys are returned byte-identical: a read built at 04:20 and one
    served at 15:00 differ only in LIVE_KEYS. A missing / zero / negative /
    non-numeric print leaves the read exactly as stored with
    `price_basis: "close"` — the closed-bar answer is always an acceptable
    answer, a snapshot that is not a price is not.

    `live_dist_pct` is the distance from the LIVE print to the NEAREST BAND
    EDGE of the read it is overlaid on, as a percent of the live print,
    magnitude only (review 2026-09-16, B6 — it was undefined, so the page
    refused to draw it). The day move against the stored close is a different
    number and has its own key, `live_chg_pct`, signed.

    `live_in_band` is set ONLY when the print is inside a band. Every other
    side leaves it None: there is no "the band it was last in" (B5).

    An index entry carrying `resolutions` gets the SAME overlay applied to each
    resolution, so the chart the page draws and the read beside it can never
    disagree about where the tape is.
    """
    if not isinstance(read, dict):
        return read
    out = dict(read)
    res = read.get("resolutions")
    if isinstance(res, dict) and res:
        out["resolutions"] = {k: with_live(v, px) for k, v in res.items()}
    live = _num(px)
    if live is None or live <= 0 or not read.get("available"):
        out.update({"live_px": None, "live_dist_pct": None, "live_chg_pct": None,
                    "live_in_band": None, "live_side": None,
                    "price_basis": "close"})
        return out
    close = _num(read.get("close"))
    bands = read.get("bands") or []
    in_band = next((b for b in bands
                    if _num(b.get("lo")) is not None and _num(b.get("hi")) is not None
                    and float(b["lo"]) <= live <= float(b["hi"])), None)
    if in_band is not None:
        side = "in"
    elif bands and all(live > float(b["hi"]) for b in bands):
        side = "above"
    elif bands and all(live < float(b["lo"]) for b in bands):
        side = "below"
    else:
        side = "between"
    out.update({"live_px": round(live, 2),
                "live_dist_pct": _edge_dist_pct(bands, live),
                "live_chg_pct": (None if close is None
                                 else _pct(live - close, close)),
                # Only "in" carries a band. Never the last one it was in.
                "live_in_band": in_band if side == "in" else None,
                "live_side": side, "price_basis": "live"})
    return out


# ---------------------------------------------------------------------------
# staleness — SERVED, not inferred by the frontend
# ---------------------------------------------------------------------------
def _sessions_between(stored: date, today: date) -> int:
    """Market days strictly after `stored` and on/before `today`. The holiday
    calendar is market_hours.reminder's — never a second copy."""
    try:
        from market_hours.reminder import is_market_day
    except Exception:                                           # noqa: BLE001
        return max(0, (today - stored).days)
    n, d = 0, stored + timedelta(days=1)
    while d <= today:
        if is_market_day(datetime(d.year, d.month, d.day)):
            n += 1
        d += timedelta(days=1)
    return n


def staleness(basis_date: Optional[str], today: Optional[date] = None,
              stored_date: Optional[str] = None) -> dict:
    """{stale_days, stale_sessions, note} measured on the BASIS date.

    `basis_date` is the session the BANDS are drawn from (`as_of`), NOT the day
    the job ran. Measuring on the job day was the review's B1: `zone_store`
    drops today's bar, so the doc day is always one session ahead of the
    structure, and a store that failed five days ago still re-stores its old
    bands under today — which read stale_days 0 while the bands were a week
    old. Staleness on the basis date makes that visible.

    `stale_days` is CALENDAR days, because that is what the contract serves;
    `stale_sessions` is market days (B2) and is what the page prints, so the
    word on screen and the number under it agree. The job runs weekdays and the
    bands are closed-bar, so a Saturday read of Friday's structure is the last
    close, not a stale one — nothing here cries stale over a weekend.

    `stored_date` (the job day) is named in the note only when it differs from
    the basis, so a re-stored stale doc says both dates instead of one.
    """
    today = today or _today_et()
    if not basis_date:
        return {"stale_days": None, "stale_sessions": None,
                "note": "No index structure stored yet — the overnight job has "
                        "not run. " + DISCLAIMER}
    try:
        d = date.fromisoformat(str(basis_date))
    except (TypeError, ValueError):
        return {"stale_days": None, "stale_sessions": None,
                "note": "The stored index doc carries an unreadable date. " + DISCLAIMER}
    days = max(0, (today - d).days)
    sessions = _sessions_between(d, today)
    if sessions <= 0:
        note = f"Bands drawn on closed bars, as of the {d.isoformat()} session. "
    else:
        s = "session" if sessions == 1 else "sessions"
        note = (f"Bands are {sessions} {s} old — drawn on closed bars as of "
                f"{d.isoformat()}. ")
    if stored_date and str(stored_date) != d.isoformat():
        note += f"Stored by the {stored_date} job run. "
    return {"stale_days": days, "stale_sessions": sessions, "note": note + DISCLAIMER}


# ---------------------------------------------------------------------------
# warm — the OVERNIGHT job
# ---------------------------------------------------------------------------
def _name_for(symbol: str) -> Optional[str]:
    try:
        from sepa import company_names
        return company_names.name_for(symbol)
    except Exception:                                           # noqa: BLE001
        return None


def _fine_compute(frame):
    """The FINE band set: `price_zones.compute` with NO geometry kwargs.

    Passing none IS the fine setting — swing / merge / half-width all fall
    through to the module's own constants, the same ones the per-ticker /zones
    page has run on since 2026-06-09. Nothing here retypes a knob, so the two
    surfaces cannot drift. `max_zones=None` keeps EVERY band (the cap is a
    display cut, and the whole ask was more zones).
    """
    from supply_demand import price_zones
    return price_zones.compute(frame, max_zones=None)



def _as_of_of(doc) -> Optional[str]:
    """The CLOSED-bar session a stored doc was drawn from, or None.

    Reads the same `recent` row `_closed_basis` does, so the comparison in
    `warm()` is the comparison the served read will make."""
    if not isinstance(doc, dict):
        return None
    for row in reversed(doc.get("recent") or []):
        if isinstance(row, dict) and row.get("date") is not None:
            return str(row["date"])
    d = doc.get("date")
    return str(d) if d is not None else None


def _build_doc(ZS, sym: str, frame, today: date, compute=None) -> Optional[dict]:
    """`zone_store.build_doc`, never raising. Closed bars (it drops today's row
    itself). Never `price_zones.for_symbol` — that overlays a live bar and
    would move a band."""
    if frame is None:
        return None
    try:
        return ZS.build_doc(sym, frame, today, compute=compute)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("index_zones: compute failed for %s: %s", sym, exc)
        return None


def _bars(frame, today: date, docs: Iterable[Optional[dict]]) -> list:
    """CLOSED daily candles for the chart, in chart_maps' own bar shape.

    The window is `chart_maps.board._zone_window` over EVERY band in BOTH
    resolutions (the widest wins), so the oldest swing that defines any band on
    screen is on screen — the same ZONE_BARS_MIN / MAX / PAD rule the zone
    tiles already use, imported rather than re-derived. [] on any failure: a
    missing chart must not cost the read.
    """
    if frame is None:
        return []
    try:
        from chart_maps.board import _frame_to_bars, _norm_frame, _zone_window
        from supply_demand import zone_store as ZS

        df = _norm_frame(ZS.drop_today(frame, today))
        if df is None or not len(df):
            return []
        windows = [_zone_window(b) for d in docs if isinstance(d, dict)
                   for b in (d.get("bands") or []) if isinstance(b, dict)]
        return _frame_to_bars(df.tail(max(windows) if windows else _zone_window(None)))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("index_zones: bars failed: %s", exc)
        return []


def _entry(read: dict, resolutions: dict, bars: list) -> dict:
    """One index entry: the BOARD read at the top level (every consumer built
    against the first cut keeps reading the same keys), both resolutions, and
    the chart bars with their basis stated."""
    out = dict(read)
    out["resolutions"] = resolutions
    out["bars"] = bars or []
    out["bars_basis"] = BARS_BASIS
    return out


def warm(symbols: Iterable[str] = INDEXES, *, coll=None,
         store_docs: Optional[dict] = None, loader: Optional[Callable] = None,
         today: Optional[date] = None, now: Optional[datetime] = None,
         namer: Optional[Callable] = None) -> dict:
    """Read the structure ONCE and persist ONE doc for the day.

    BOTH resolutions and the chart bars are computed HERE, overnight. The
    endpoint and the board only read (`served`), and neither ever re-derives a
    band or reaches for a frame per request.

    Board set, preference order per symbol:
      1. the `zone_store` doc (it already warms at 04:05 ET with every band)
      2. `zone_store.build_doc` on `sepa.prices.load_prices` — the SAME engine
         and geometry, so a fallback band is the same band
      3. stored `unavailable` with a reason — never dropped, never faked

    Fine set: always computed here from the same frame, through the same
    `zone_store.build_doc` (so it is slimmed, dated and closed-bar exactly like
    the board doc) with `_fine_compute` — price_zones module defaults.

    Every input is injectable; the cron passes none.
    """
    from supply_demand import zone_store as ZS

    today = today or _today_et()
    syms = [str(s).upper() for s in symbols if s]
    namer = namer or _name_for
    if store_docs is None:
        try:
            _day, store_docs = ZS.load_latest(syms)
        except Exception as exc:                                # noqa: BLE001
            log.warning("index_zones: zone_store read failed: %s", exc)
            store_docs = {}
    store_docs = store_docs or {}
    if loader is None:
        from sepa import prices

        def loader(sym):
            return prices.load_prices(sym, period="2y")

    reads: dict = {}
    counts = {"zone_store": 0, "computed": 0, "unavailable": 0}
    for sym in syms:
        name = namer(sym)
        try:
            frame = loader(sym)
        except Exception as exc:                                # noqa: BLE001
            log.warning("index_zones: frame failed for %s: %s", sym, exc)
            frame = None
        board_doc, src = store_docs.get(sym), "zone_store"
        if not board_doc:
            src = "computed"
            board_doc = _build_doc(ZS, sym, frame, today)
        fine_doc = _build_doc(ZS, sym, frame, today, compute=_fine_compute)

        # ONE SESSION, ONE CLOSE, BOTH RESOLUTIONS (2026-09-16 review).
        # `zone_store.load_latest` hands back the latest doc <= today, so on a
        # day its 04:05 warm failed or timed out the BOARD doc is days old
        # while the FINE doc is built from today's frame. The card then dated
        # fine bands with the board's session and drew a close line from
        # another day over the candles — a 7% error in the reproduction, and
        # exactly the basis mixing this strip exists to prevent. When the two
        # disagree, rebuild the board set from the SAME frame: identical
        # engine, identical zone_geom(), so it is the same band, just current.
        if _as_of_of(board_doc) != _as_of_of(fine_doc):
            log.info("index_zones: %s board doc is %s, fine is %s — rebuilding "
                     "board from the same frame", sym,
                     _as_of_of(board_doc), _as_of_of(fine_doc))
            rebuilt = _build_doc(ZS, sym, frame, today)
            if rebuilt is not None:
                board_doc, src = rebuilt, "computed"

        read = read_doc(sym, board_doc, name=name, source=src)
        if not read.get("available"):
            read["source"] = "unavailable"
        fine = read_doc(sym, fine_doc, name=name, source="computed")
        if not fine.get("available"):
            fine["source"] = "unavailable"
        counts[read["source"]] = counts.get(read["source"], 0) + 1
        reads[sym] = _entry(read,
                            {RESOLUTION_BOARD: dict(read),
                             RESOLUTION_FINE: fine},
                            _bars(frame, today, (board_doc, fine_doc)))

    day = today.isoformat()
    out = {"_id": day, "date": day,
           "computed_at": (now or datetime.now(ET)).isoformat(),
           "source": DOC_SOURCE, "indexes": reads}
    coll = _coll(coll)
    written = False
    if coll is not None:
        try:
            coll.replace_one({"_id": day}, out, upsert=True)
            written = True
        except Exception as exc:                                # noqa: BLE001
            log.warning("index_zones: write failed: %s", exc)
    purge(coll=coll, today=today)
    return {"date": day, "symbols": syms, "written": written,
            "sources": counts, "doc": out}


def purge(coll=None, today: Optional[date] = None) -> int:
    """Drop day docs older than `zone_store.KEEP_DAYS` — the store's own
    retention, imported so the two cannot drift."""
    from supply_demand.zone_store import KEEP_DAYS

    coll = _coll(coll)
    if coll is None:
        return 0
    cutoff = (today or _today_et()) - timedelta(days=KEEP_DAYS)
    try:
        res = coll.delete_many({"date": {"$lt": cutoff.isoformat()}})
        return int(getattr(res, "deleted_count", 0) or 0)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("index_zones: purge failed: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# load + serve
# ---------------------------------------------------------------------------
def load_latest(coll=None, today: Optional[date] = None
                ) -> tuple[Optional[str], dict]:
    """(date, {SYMBOL: read}) for the latest stored day <= today ET.
    (None, {}) when the store is cold. Reads only — it never warms."""
    coll = _coll(coll)
    if coll is None:
        return None, {}
    cutoff = (today or _today_et()).isoformat()
    try:
        doc = coll.find_one({"date": {"$lte": cutoff}}, sort=[("date", -1)])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("index_zones: load failed: %s", exc)
        return None, {}
    if not doc:
        return None, {}
    idx = doc.get("indexes")
    idx = idx if isinstance(idx, dict) else {}
    d = doc.get("date")
    return (d if isinstance(d, str) else None), idx


def live_prints(symbols: Iterable[str] = INDEXES) -> dict:
    """{SYMBOL: live print} through the SAME bulk snapshot the demand boards
    use (`demand_reentry._live_snapshots` / `_snapshot_print`), so the strip
    and the tiles can never disagree about the tape. {} on any failure — the
    closed-bar read then stands on its own."""
    try:
        from supply_demand import demand_reentry as D
        snaps = D._live_snapshots(list(symbols)) or {}
        return {k: D._snapshot_print(v) for k, v in snaps.items()}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("index_zones: live prints unavailable: %s", exc)
        return {}


def basis_date(reads: dict) -> Optional[str]:
    """The session the served BANDS are drawn from: the latest `as_of` across
    the available reads. None when nothing readable is stored.

    This — not the doc day — is what staleness is measured on (B1).
    """
    stamps = [r.get("as_of") for r in (reads or {}).values()
              if isinstance(r, dict) and r.get("available")
              and isinstance(r.get("as_of"), str) and r.get("as_of")]
    return max(stamps) if stamps else None


def empty_payload(note: Optional[str] = None) -> dict:
    """The served shape with nothing in it. ONE builder, so the endpoint, the
    board's failure branch and a cold store all degrade to the same keys."""
    return {"date": None, "as_of": None, "indexes": {}, "stale_days": None,
            "stale_sessions": None, "default_resolution": DEFAULT_RESOLUTION,
            "note": note or ("Index structure is unavailable right now. "
                             + DISCLAIMER)}


def served(live: Optional[dict] = None, coll=None,
           today: Optional[date] = None) -> dict:
    """The payload both the endpoint and the zones board serve: PAYLOAD_KEYS.

    `date` is the day the JOB ran; `as_of` is the session the BANDS are drawn
    from, and `stale_days` / `stale_sessions` / `note` are measured on `as_of`.

    READ ONLY — it never calls `warm()`. A cold store returns the empty shape
    with the reason in `note`, never a 500 and never an empty page with no
    explanation.
    """
    day, reads = load_latest(coll=coll, today=today)
    basis = basis_date(reads)
    if reads and basis is None:
        # The job ran and stored something, but nothing in it is readable. Say
        # that, rather than dating unreadable structure with the job day.
        st = {"stale_days": None, "stale_sessions": None,
              "note": f"The {day} index doc carries no readable structure. "
                      + DISCLAIMER}
    else:
        st = staleness(basis, today=today, stored_date=day)
    if live is None:
        live = live_prints(reads.keys() or INDEXES) if reads else {}
    live = live or {}
    out = {sym: with_live(r, live.get(sym)) for sym, r in reads.items()}
    return {"date": day, "as_of": basis, "indexes": out,
            "stale_days": st["stale_days"], "stale_sessions": st["stale_sessions"],
            "default_resolution": DEFAULT_RESOLUTION, "note": st["note"]}


def api_payload() -> dict:
    """`served` with every failure swallowed — a context strip must never be
    able to take down the endpoint or the board that pins it."""
    try:
        return served()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("index_zones: payload failed: %s", exc)
        return empty_payload()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    res = warm()
    log.info("INDEX-ZONES: date=%s symbols=%s written=%s sources=%s",
             res["date"], ",".join(res["symbols"]), res["written"],
             res["sources"])
