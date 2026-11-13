"""📋 All strategies — the ranked table on 🚩 Gajjala's tab (SPEC 2026-11-13 REV 2 §3.2, WP-A). DISPLAY ORDER ONLY.

Ajay 2026-11-13, verbatim: "Hey can you build be a table like track record on Gajjals landing page.. Call all strategies.
I want this table to rank based how gajjals sees them.. He watches 18 stocks simultaneously I am unable to see that view
with car and tab lay out I will use this table format but I need tha track record like graph thoouhg So A+'s on top and
potental next and others close to strategies next liek EMA near kiss first, horizontal fade 9 EM Anad 25 EMA merge second
and VCP next reversal potental next with categories showing in the table"

WHAT. One row per (symbol, setup) for every card the five setup subs already list, built from those subs' OWN tiles
(tab.setup_tile — the stash still on them) and ranked in four tiers: 🎯 A+ (entry_marks.BREAK_STATES, newest break
first — tab._state_key) → 🧠 potential (potential.order_key, the ONE 🧠 engine) → forming, in his setup order
(constants.TABLE_SETUP_ORDER), each setup in its own sub's served order verbatim → a rule failed / stopped (same order).
The concatenation is cut at constants.TILE_LIMIT_MAX (tab._capped) FIRST; his 🚫 names then sit last IN THEIR TIER inside
the cut (tab.broker_bottom — the 2026-11-09 invariant: the list only reorders, it never pushes a row past the cut). The
first constants.GG_WATCH_N distinct names of the final order carry `in_watch` (a divider, never a cap).

Every row carries a lite spark of TODAY's bars (tab._tile_frame(doc, tf, v) — wide=False, never the 🎾 card's wide frame,
tab.py:1066 / 1431) in tape.LITE_KEYS shape, strided by catalysts.promo_tape.lite_payload, so the 🏁 mini draws it
preset with no per-row fetch. Tile bar session flags are support._SESSION_FLAG's ("pre" / "ah", chart_maps/support.py:1141;
an RTH bar carries none) — SPARK_SESSION inverts that map BY NAME into the tape's words (premarket / afterhours / rth).

PURE. No store, no fetch, no wall clock (`now` comes from tab.build). Every word the table prints is typed here and
nowhere else; every number is a served text from the tab's own formatters. Nothing here rings, gates, counts or
trades. UNMEASURED — no study says this order wins.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps import support as _SUP
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import entry_marks as EM
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import tape as TP
from chart_maps.gajjala import variant as V

log = logging.getLogger("chart_maps.gajjala.all_table")

ET = ZoneInfo("America/New_York")

# ── served words — the ONLY place the table's words are typed (the FE types none) ─────────────────────────────────
TIERS = ("aplus", "potential", "forming", "rest")                       # tier_key, rank order; tier = 1..4
TIER_WORDS = {"aplus": "🎯 A+", "potential": "🧠 potential",
              "forming": "forming — close to a setup", "rest": "a rule failed / stopped"}
HEADS = (("rank", "#"), ("symbol", "Ticker"), ("spark", "Tape"), ("category", "Category"), ("price", "Price"),
         ("plan", "Trigger / stop"), ("dist", "To trigger"), ("volume", "Volume"), ("float", "Float"))
TITLE = "📋 All strategies — every card on his five setups, ranked the way he watches"
ORDER_TEXT = ("🎯 A+ first (newest break on top) · 🧠 potential next (trigger armed before building, then highest volume) · "
              "then forming, closest to a setup: 💋 EMA Kiss & Fly → ➖ Horizontal Fade (9 and 21 EMA merging) → "
              "🌀 Intraday VCP → 🎾 Reversal Squeeze → 🚩 Bull Flag, each in its own sub's order · then a rule failed / "
              "stopped · your 🚫 names last in their group")
WATCH_TEXT = ("GG's {n} — the first {n} names ({rows} rows; a name on two setups is listed twice). He watches {n} charts "
              "at once (your word, 2026-11-13). Every row below is still listed.")
EMPTY_TEXT_OPEN = "No card on any of his five setups right now — the next pass is at most {mins} away."
EMPTY_TEXT_CLOSED = "No card on any of his five setups on the {label} list."
MORE_TEXT = "{n} more rows below the {cap}-row transport cap — not shown this read"
FAULT_TEXT = "{n} row(s) could not be built this read — skipped, never hidden by a rule"
HONESTY = "display order only — no gate, count or alert changes · UNMEASURED"
# tile bar flag → the tape's session word, read off chart_maps/support.py:1141 BY NAME; a bar without `s` → SPARK_RTH
SPARK_SESSION = {flag: word for word, flag in _SUP._SESSION_FLAG.items()}
SPARK_RTH = "rth"


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _et_of(t) -> Optional[datetime]:
    """An ET wall-clock bar stamp ("YYYY-MM-DD HH:MM", tab bars) → an aware ET datetime; an aware / naive ISO string is
    read the same way (naive = ET wall clock, the tile's own convention); anything else → None (never raises)."""
    if not isinstance(t, str) or len(t) < 16:
        return None
    try:
        d = datetime.strptime(t[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            d = datetime.fromisoformat(t.strip())
        except ValueError:
            return None
    return d.replace(tzinfo=ET) if d.tzinfo is None else d.astimezone(ET)


def tier_of(read: dict, is_potential: bool) -> str:
    """BREAK_STATES (entry_marks — aplus, triggered) → "aplus"; a 🧠 potential → "potential"; any other forming read →
    "forming"; everything else carded (partial, stopped) → "rest"."""
    st = (read or {}).get("state")
    if st in EM.BREAK_STATES:
        return TIERS[0]
    if is_potential:
        return TIERS[1]
    if st == "forming":
        return TIERS[2]
    return TIERS[3]


def spark_bars(doc: dict, tf: str, v=None) -> list:
    """TODAY's frame only — tab._tile_frame(doc, tf, v) with wide=False (the default; the 🎾 card's prior-session tail is
    never used here): [{t: epoch ms of the ET wall clock, c, s: premarket | afterhours | rth}]. A bar whose t / c does
    not parse is dropped."""
    out = []
    for b in GT._tile_frame(doc or {}, tf, v)["bars"]:
        if not isinstance(b, dict):
            continue
        d, c = _et_of(b.get("t")), GT._f(b.get("c"))
        if d is None or c is None:
            continue
        out.append({"t": int(d.timestamp() * 1000), "c": c, "s": SPARK_SESSION.get(b.get("s"), SPARK_RTH)})
    return out


def spark_of(tile: dict, *, doc: dict, read: dict, now: datetime, v=None, title: Optional[str] = None) -> dict:
    """The row's mini, tape.LITE_KEYS shape for GgEntryMiniTape (preset): `id` = "{SYM}|{setup}" (a row key, never a
    ledger id); bars = the Promo lite stride over spark_bars (t / c / s, every LITE_STRIDE-th + the last); ONE `alert`
    rule at the entry bar for a BREAK_STATES read whose entry bar parses, else none; tone = the tape composer's rule
    (the last close vs the trigger, tape.py) — None without a trigger or bars; `title` = the hover words."""
    from catalysts import promo_tape as PROMO
    read = read or {}
    g = tile.get("gajjala") or {}
    sym, setup = tile.get("symbol") or "", g.get("setup") or read.get("setup") or ""
    n = V.frame_minutes(tile.get("tf"), v)
    full = spark_bars(doc, tile.get("tf"), v)
    rules = []
    eb = _et_of(read.get("entry_bar_t"))
    if read.get("state") in EM.BREAK_STATES and eb is not None:
        rules.append({"key": "alert", "at": eb.isoformat(), "style": "solid", "tone": "alert",
                      "label": TP._w("alert", hhmm=eb.strftime("%H:%M"))})
    trig = GT._f(read.get("trigger"))
    tone = None
    if trig is not None and full:
        tone = "up" if full[-1]["c"] >= trig else "dn"
    return {"id": f"{sym}|{setup}", "ticker": sym, "tf": TP._w("tf", n=n), "lite": True,
            "bars": PROMO.lite_payload({"bars": full}, stride=PROMO.LITE_STRIDE)["bars"], "n_bars": len(full),
            "rules": rules, "title": title, "tone": tone, "note": None, "aria": TP._w("aria", sym=sym, n=n),
            "as_of": now.isoformat() if isinstance(now, datetime) else None}


def row_of(tile: dict, *, doc: dict, tier_key: str, pot_row: Optional[dict], scan_row: dict, now, v=None) -> dict:
    """One served row from the setup sub's OWN card (named keys only — never a "_"-prefixed stash, never bars/curves).
    state_word = the tile's served variant / grade label (long flag, near-kiss, VCP "B") else potential.state_word."""
    g = tile.get("gajjala") or {}
    sym = tile.get("symbol") or ""
    setup = g.get("setup") or ""
    read = ((doc or {}).get("setups") or {}).get(setup) or {}
    scan_row = scan_row or {}
    chips = g.get("chips") if isinstance(g.get("chips"), dict) else {}
    emoji, label = GT.SUB_META.get(setup, ("", setup))
    state = g.get("state")
    kind = pot_row.get("kind") if isinstance(pot_row, dict) else None
    state_word = g.get("variant_label") or g.get("grade_label") or PT.state_word(state, kind)
    category = f"{emoji} {label} · {state_word}"
    price = GT._f(g.get("_last"))
    price = price if price is not None else GT._f(scan_row.get("price"))
    change = GT._f(scan_row.get("change_pct"))
    volume = GT._f(chips.get("volume"))
    trig, stop = GT._f(g.get("trigger")), GT._f(g.get("stop"))
    dist = (trig - price) / price * 100 if (trig is not None and price is not None and trig > 0 and price > 0) else None
    fl = chips.get("float") if isinstance(chips.get("float"), dict) else None
    rv = next((s.get("v") for s in tile.get("stats") or [] if isinstance(s, dict) and s.get("k") == GT.RVOL_STAT_KEY),
              None)
    state_label = g.get("state_label")
    return {"rank": None, "tier": TIERS.index(tier_key) + 1, "tier_key": tier_key, "tier_label": TIER_WORDS[tier_key],
            "symbol": sym, "name": tile.get("name"), "setup": setup, "setup_emoji": emoji, "setup_label": label,
            "state": state, "state_word": state_word, "state_label": state_label, "category_text": category,
            "kind": kind, "kind_label": pot_row.get("kind_label") if isinstance(pot_row, dict) else None,
            "href": tile.get("href"), "card_href": PT.deep_link(sym, setup, v), "tf": tile.get("tf"),
            "price": price, "price_text": GT._px(price), "change_pct": change, "change_text": GT._pct(change),
            "volume": volume, "volume_text": GT._compact(volume), "rvol_text": rv if isinstance(rv, str) and rv else None,
            "float_text": (fl or {}).get("text") or None, "trigger": trig, "stop": stop,
            "risk_pct": GT._f(g.get("risk_pct")), "plan_text": g.get("plan_text"), "dist_pct": dist,
            "dist_text": GT._pct(dist), "entry_plan": GT.is_entry_plan(read), "in_watch": False,
            "vol_dried": chips.get("vol_dried") or None,
            "spark": spark_of(tile, doc=doc, read=read, now=now, v=v,
                              title=f"{category} · {state_label}" if state_label else category)}


def block(per_setup: dict, pots: list, *, reads_by: dict, flags, sess: dict, in_window: bool, now, v=None,
          scan_row: Callable, cad_min: int) -> dict:
    """The served `table` block (SPEC §3.2 steps 1–7): tiers → concat → cut (tab._capped) → his 🚫 names last per tier
    INSIDE the cut (tab.broker_bottom) → rank 1..N → `in_watch` over the first GG_WATCH_N distinct names. A raising
    row is skipped and counted (faults_n / fault_text), never silent."""
    reads_by = reads_by or {}
    pot_by = {(row["symbol"], row["setup"]): (key, row) for key, row, _d, _r in pots or []}
    tiers: dict = {k: [] for k in TIERS}
    faults = 0
    for setup in GC.TABLE_SETUP_ORDER:                              # his setup order — the stable input of every tier
        for idx, tile in enumerate(per_setup.get(setup) or []):
            try:
                sym = str(tile.get("symbol") or "").upper()
                doc = reads_by.get(sym) or {}
                read = (doc.get("setups") or {}).get(setup) or {}
                pot = pot_by.get((sym, setup))
                tk = tier_of(read, pot is not None)
                row = row_of(tile, doc=doc, tier_key=tk, pot_row=pot[1] if pot else None, scan_row=scan_row(sym),
                             now=now, v=v)
            except Exception as exc:                                # noqa: BLE001
                log.warning("gajjala all table: row %s/%s failed: %s", tile.get("symbol"), setup, exc)
                faults += 1
                continue
            if tk == TIERS[0]:
                k = GT._state_key(tile.get("gajjala") or {}, sym)
            elif tk == TIERS[1]:
                k = pot[0]
            else:
                k = (GC.TABLE_SETUP_ORDER.index(setup), idx)
            tiers[tk].append((k, row))
    rows = [r for t in TIERS for _k, r in sorted(tiers[t], key=lambda x: x[0])]
    n = len(rows)
    cut = GT._capped(rows)
    kept = cut["rows"]
    more_n = cut.get("more_n") or 0
    final = []
    for t in TIERS:                                                 # contiguous by construction
        final += GT.broker_bottom([r for r in kept if r["tier_key"] == t], flags)
    watch: list = []                                                # the first GG_WATCH_N DISTINCT names, final order
    for i, r in enumerate(final):
        r["rank"] = i + 1
        if r["symbol"] not in watch and len(watch) < GC.GG_WATCH_N:
            watch.append(r["symbol"])
        r["in_watch"] = r["symbol"] in watch
    watch_rows = sum(1 for r in final if r["in_watch"])
    empty = None
    if not final:
        empty = (EMPTY_TEXT_OPEN.format(mins=GT._mins(cad_min)) if in_window else
                 EMPTY_TEXT_CLOSED.format(label=(sess or {}).get("label")))
    return {"title": TITLE, "heads": [{"key": k, "label": lb} for k, lb in HEADS], "order_text": ORDER_TEXT,
            "watch": {"n": GC.GG_WATCH_N, "rows": watch_rows,
                      "text": WATCH_TEXT.format(n=GC.GG_WATCH_N, rows=watch_rows)},
            "rows": final, "n": n, "more_n": more_n,
            "more_text": MORE_TEXT.format(n=more_n, cap=GC.TILE_LIMIT_MAX) if more_n else None,
            "faults_n": faults, "fault_text": FAULT_TEXT.format(n=faults) if faults else None,
            "empty_text": empty, "honesty": HONESTY, "tape_head": TP.TAPE_HEAD}


def attach_live(rows: list, live: dict) -> None:
    """The route's ONE fan-out: a row whose symbol has a usable print (chart_maps.board._snapshot_print — the board's
    own rule) gains live_price (4 dp) + live_price_text (tab._px). Never raises, never reorders."""
    from chart_maps import board as board_mod
    for r in rows if isinstance(rows, list) else ():
        try:
            snap = (live or {}).get(str(r.get("symbol") or "").upper())
            px = board_mod._snapshot_print(snap) if snap else None
            if px is not None:
                r["live_price"] = round(px, 4)
                r["live_price_text"] = GT._px(px)
        except Exception as exc:                                    # noqa: BLE001
            log.debug("gajjala all table: live print failed: %s", exc)


__all__ = ["TIERS", "TIER_WORDS", "HEADS", "TITLE", "ORDER_TEXT", "WATCH_TEXT", "EMPTY_TEXT_OPEN", "EMPTY_TEXT_CLOSED",
           "MORE_TEXT", "FAULT_TEXT", "HONESTY", "SPARK_SESSION", "SPARK_RTH", "tier_of", "spark_bars", "spark_of",
           "row_of", "block", "attach_live"]
