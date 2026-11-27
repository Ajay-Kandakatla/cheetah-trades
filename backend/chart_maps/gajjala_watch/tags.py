"""🏷️ tags on 👀 Gajjala's Watch rows (2026-11-18, spec wtags §3.1, WP-A).

Ajay 2026-11-18 ~12:00 ET, verbatim: "Also add Short Interest tag and other tags on top of stock ticker information for
me to read, like here".

The 🚩 GG5 card's own served tags for a Watch name that is CARDED ON TODAY'S GG5 BOARD — stored docs only, by symbol,
projected; never a scan, never a bar fetch, never a clock. Display only. UNMEASURED.

"Carded" = the 🚩 board's own card rule (tab.py:1905): a reads doc of THIS session with a setup whose state is in
tab.TILE_STATES and that passes the 🌀 D3 count (tab._vcp_listed). A 🧠 tracker doc is NOT a card (C2): a potential that
died this session (read now none / invalid) has no card on his board and no tags here; the tracker docs feed the 🧭
stages only.

Reads, in order (`blocks`; every read a Mongo find, nothing else):
  1. ONE projected `_id $in` find on the GG5 reads (TAGS_READ_FIELDS — never the tile bars). No carded name → stop here.
  2. the tracker docs of the listing window (SC._window — ONE find per session; a fault → [] for the stages);
  3. the alert rows of the window through tab._entry_times — the tri-state kept RAW for tab._rang / state_label (D10:
     a proven no-ring `triggered` read says tab.NO_RING_TEXT; an unknown keeps today's words); `or {}` ONLY for
     SG.by_symbol (tab._stage_tag's own recipe, C1);
  4. the broker state doc (store.broker_flags — a fault serves broker_text None, never the seed guess);
  5. ONE projected scan find (SCAN_TAG_FIELDS) of the carded names over the window → 📌 / 🎪 source tags.

The session and is_today are `payload._build`'s own clock answer, handed in (C5) — this module reads no clock.
Every served string is tab's / stages' / trader_names' / promo_names' own: no word is typed here except this
docstring and the log lines.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

log = logging.getLogger("chart_maps.gajjala_watch.tags")

TAGS_READ_FIELDS = {"symbol": 1, "setups": 1, "ctx.float": 1, "gg_like": 1}   # never the tile bars (🧘 gg_like 11-27)
SCAN_TAG_FIELDS = {"symbol": 1, "date": 1, "held": 1, "last.trader": 1, "last.promo": 1, "last.promo_text": 1}
TAGS_KEYS = ("on_board", "setups", "stages", "float", "broker_text", "trader_text", "promo_text")


def _store():
    """The 🚩 five-minute tab's store (tests replace this function — the payload._aplus_stores pattern). 🧪 and the
    one-minute page are not sources (HIS CALL)."""
    from chart_maps.gajjala import store as ST
    return ST.default()


def _find_reads(st, ids: list, *, fields: dict = TAGS_READ_FIELDS) -> dict:
    """{SYM: read doc} — ONE projected find on the reads collection. RAISES on no handle / a fault (the caller serves
    nothing — an unknown read is never "not carded"). `fields` (keyword, spec watch_org): the projection —
    the default is the tags block's own, byte for byte; 📅 runners.py hands its own (`C.RUNNERS_READ_FIELDS`)."""
    from chart_maps.gajjala import store as ST
    c = st.coll(ST.READS) if st is not None else None
    if c is None:
        raise LookupError("no reads handle")
    want = set(ids)
    out: dict = {}
    for d in c.find({"_id": {"$in": list(ids)}}, fields):
        if isinstance(d, dict) and d.get("_id") in want and isinstance(d.get("symbol"), str):
            out[d["symbol"].upper()] = d
    return out


def _find_scan(st, days_iso: list, names: Optional[list], *, fields: dict = SCAN_TAG_FIELDS) -> list:
    """The carded names' scan docs of the window — ONE projected find; a held doc is dropped (store.scan_docs' rule).
    RAISES on no handle / a fault. Keywords (spec watch_org, 📅 runners.py): `names` None drops the symbol
    clause (every non-held doc of the days); `fields` = the projection. The defaults = the tags query byte for byte."""
    from chart_maps.gajjala import store as ST
    c = st.coll(ST.SCAN) if st is not None else None
    if c is None:
        raise LookupError("no scan handle")
    q = {"date": {"$in": list(days_iso)}}
    if names is not None:
        q["symbol"] = {"$in": list(names)}
    return [d for d in c.find(q, fields) if isinstance(d, dict) and not d.get("held")]


def carded_setups(doc) -> list:
    """[setup] in GC.SETUPS order whose read is carded on the 🚩 board: state in tab.TILE_STATES and tab._vcp_listed
    (the board's own test). [] for no doc / no setups."""
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import tab
    setups = doc.get("setups") if isinstance(doc, dict) and isinstance(doc.get("setups"), dict) else {}
    out = []
    for s in GC.SETUPS:
        r = setups.get(s)
        if isinstance(r, dict) and r.get("state") in tab.TILE_STATES and tab._vcp_listed(s, r):
            out.append(s)
    return out


# 🧘 2026-11-27 (spec gglike §3.8, WP be-serve-watch) — no digit in a string here (the source guard).
def gg_like_of(doc, setup: str) -> Optional[dict]:
    """🧘 the card block of `setup` built from the block the 🚩 pass
    STORED on this read doc (`doc["gg_like"][setup]`): `gg_like.served(from_stamp(...))` when the stamp passes the shape
    guard AND names this setup; else None. The Watch never computes a block (no bars are read here) and never invents
    one; no `keep` is handed in — nothing is hidden on the Watch. A fault → None for this setup only, ONE log line."""
    try:
        from chart_maps.gajjala import gg_like as GL
        stored = doc.get("gg_like") if isinstance(doc, dict) else None
        blk = GL.from_stamp(stored.get(setup) if isinstance(stored, dict) else None)
        if not isinstance(blk, dict) or blk.get("setup") != setup:
            return None
        return GL.served(blk)
    except Exception as exc:                                            # noqa: BLE001
        log.warning("gajjala_watch: gg_like tag unavailable: %s", type(exc).__name__)
        return None


def on_board(doc) -> bool:
    """The 🚩 board's card rule, nothing else — a tracker doc never makes a name carded."""
    return bool(doc) and bool(carded_setups(doc))


def blocks(names, session: date, is_today: bool, *, st) -> dict:
    """STRICT core: {SYM: block} for the carded names only (an uncarded name is not a key). RAISES on a fault."""
    if not names:
        return {}
    from chart_maps.gajjala import promo_names as PN
    from chart_maps.gajjala import scanner as SC
    from chart_maps.gajjala import stages as SG
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import tab
    from chart_maps.gajjala import trader_names as TN
    from chart_maps.gajjala import variant as V
    siso = session.isoformat()[:10]
    reads = _find_reads(st, [ST.key(siso, s) for s in names])
    carded = {s: carded_setups(reads.get(str(s).upper())) for s in names}
    on = [s for s in names if carded[s]]
    if not on:
        return {}                                                       # ONE find for a board with no carded name
    win = SC._window(session)
    days = {d: (st.potentials(d) or []) for d in win}                   # a read fault (None) → [] for the stages only
    entries_raw = tab._entry_times(st, win, V.GG5)                      # tri-state RAW: None = unknown (D10, C1)
    entries = entries_raw or {}                                         # ONLY for SG.by_symbol (tab._stage_tag's recipe)
    flags, fault = ST.broker_flags(st)
    flags = None if fault else flags                                    # a fault serves None — never the seed guess
    scan = _find_scan(st, [d.isoformat() for d in win], on)
    tt, pt = TN.tag_map(scan), PN.tag_map(scan)
    by = SG.by_symbol(days, board_session=session, is_today=is_today, symbols=on, cadence_min=tab._cad(V.GG5),
                      borrowed=False, entries=entries)
    out: dict = {}
    for s in on:
        sym = str(s).upper()
        doc = reads[sym]
        setups = doc.get("setups") if isinstance(doc.get("setups"), dict) else {}
        out[s] = {
            "on_board": True,
            "setups": [{"setup": k, "label": tab._setup_label(k), "state": r.get("state"),
                        "state_label": tab.state_label(r, tab._rang(entries_raw, session, sym, k)),   # tab.py:1536
                        "gg_like": gg_like_of(doc, k)}                  # 🧘 2026-11-27 — the pass's stored block only
                       for k in carded[s] for r in [setups.get(k) or {}]],
            "stages": SG.for_tile(by[sym], None, session) if by.get(sym) else None,   # no `here`: no single card
            "float": tab._float_chip(tab._float_read(doc, None)),       # the read's own ctx.float (no daily doc)
            "broker_text": tab.broker_text_for(sym, flags),
            "trader_text": (tt.get(sym) or {}).get("trader_text"),
            "promo_text": (pt.get(sym) or {}).get("promo_text"),
        }
    return out


def section(names, session: date, is_today: bool) -> dict:
    """Fail-soft `blocks`: any fault → {} (every row serves null; the board answers) and ONE log line. `session` and
    `is_today` are the payload's own clock answer."""
    if not names:
        return {}
    try:
        return blocks(list(names), session, bool(is_today), st=_store())
    except Exception as exc:                                            # noqa: BLE001
        log.warning("gajjala_watch: tags unavailable: %s", type(exc).__name__)
        return {}
