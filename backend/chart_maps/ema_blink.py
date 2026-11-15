"""🔀 ema_blink — the 9 / 21 EMA blinker's served words, card block, sort key and tab-dot counts (2026-11-15).

Ajay, verbatim (2026-11-15): "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9
crossing over 21 EMA please.." · WHERE "All Gajjala tabs" · FRAME "Each chart's own frame" · DURATION "Yes and I need
some sort of urgency or fast blink for the one are closer together than approaching with sort also aligned with it" ·
"Or atleast closing in on other tabs for me".

ONE engine: chart_maps.gajjala.ema_cross.blink_read (over a card's own stored 9 / 21 curves) and blink_from_bars (the
house EMA, bars._masked_ema, over a daily tile's bars) — this module computes no EMA of its own. Every number in a word
is a `{}` field filled from chart_maps.gajjala.constants (GC) at CALL time. Information only: no gate, push, alert, A+
rule, lane or default order reads it. UNMEASURED (eod-audits/research/2026-11-15_video_9x21_upcross/REPORT.md).

API:
  block(read, *, tf)                      -> the served card block | None
  block_from_curves(curves, bars, *, tf)  -> block over a card's served curves (EMA_TONES) + bars (t / c)
  block_from_bars(bars, *, tf="1d", **kw) -> block over daily bars (the other boards; pass through=daily_through())
  daily_through(now)                      -> the last date whose daily bar is CLOSED to keep, or None (keep all)
  sort_key(tile) / top_key(sym, block)    -> THE order (blinking first, tier, closeness, gap) — no symbol in sort_key
  tab_tier(blocks)                        -> the fastest tier among blinking blocks
  info() / title() / sort_label() / order_text() / rules_line() / sort_unavailable()  -> the served words
  in_window(now)                          -> the closed-day gate AND THE pass window (run.in_window)
  tab_counts(now, *, owner)               -> the tab-dot feed (GET /chart-maps/ema-blink)
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX

log = logging.getLogger("chart_maps.ema_blink")
ET = ZoneInfo("America/New_York")

DAILY_FRAME = "1d"
TEXT = {
    "fresh": "● {fast} EMA crossed over the {slow} EMA on this bar ({when})",
    "imminent": "◐ {fast} EMA closing in on the {slow} EMA · gap {gap}% · could cross on the next bar",
    "near": "◐ {fast} EMA closing in on the {slow} EMA · gap {gap}% · about {n} bars to the cross",
    "closing": "◔ {fast} EMA closing in on the {slow} EMA · gap {gap}% · about {n} bars to the cross",
    "up": "● {fast} EMA over the {slow} EMA since {when} · {n} bars",
}
GAP_PART = " · gap {gap}%"                       # dropped from a TEXT line when the read has no close (gap unknown)
TITLE = "🔀 {fast}/{slow} EMA blinker — information only, UNMEASURED (ℹ️ Rules has the read)"
INFO_TEXT = ("UNMEASURED — information, not an entry. The 2026-11-15 check of every replay video: a {fast}-over-{slow} cross on "
             "5-minute bars timed a runner well (+36.6% mean ride on the 38 video charts) but did not pick one — on 1,497 other "
             "names the same rule lost 2.0% net and won 27% of the time; on 1-minute bars it crossed about 12 times per chart "
             "on the video names. 'Closing in' = the gap is smaller than {narrow} closed bars ago; the bars-to-cross number is a "
             "straight-line projection, {max} bars at most. Cheetah's definition, not Gajjala's.")
SORT_LABEL = "🔀 closest to the {fast}/{slow} cross"
SORT_DEFAULT_LABEL = "↩ the board's own order"
ORDER_TEXT = ("🔀 closest to the {fast}/{slow} cross on top — just crossed, then about to cross by bars, then older "
              "up-crosses — the rest in the board's own order")
SORT_UNAVAILABLE = "No {fast}/{slow} read on this board's bars — the board is showing its default order."
RULES_LINE = (" 🔀 Blinker: a card's dot pulses while the {fast} EMA is over the {slow} EMA on its own closed frame (a cross on that frame), "
              "or faster the closer the {fast} is to crossing over (gap narrowing over {narrow} bars, projected within {max}); "
              "the tab button pulses when any card on it does. Information only — no gate, push or A+ rule reads it. UNMEASURED.")
TAB_TEXT = "{n} cards at or near the {fast}/{slow} cross · closest {sym}"
TAB_TEXT_ONE = "{sym} at or near the {fast}/{slow} cross"
N_MEANS = "symbols in the tab's store with a card at or near the cross on its primary frame, cut and 15-minute toggle aside"
EARLIER_BAR = "an earlier bar"

BLOCK_KEYS = ("state", "tier", "blink", "closeness", "bars_to_cross", "bars_since_cross", "gap_pct", "above",
              "cross_t", "t", "tf", "text", "title", "fast", "slow")
TAB_KEYS = ("gajjala", "gajjala_audited", "gajjala_1m", "luk", "gajjala_watch")


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _ema_pair() -> dict:
    return {"fast": GC.EMA_FAST, "slow": GC.EMA_SLOW}


def info() -> str:
    return INFO_TEXT.format(narrow=GC.BLINK_NARROW_BARS, max=GC.BLINK_MAX_BARS, **_ema_pair())


def title() -> str:
    return TITLE.format(**_ema_pair())


def sort_label() -> str:
    return SORT_LABEL.format(**_ema_pair())


def order_text() -> str:
    return ORDER_TEXT.format(**_ema_pair())


def sort_unavailable() -> str:
    return SORT_UNAVAILABLE.format(**_ema_pair())


def rules_line() -> str:
    return RULES_LINE.format(narrow=GC.BLINK_NARROW_BARS, max=GC.BLINK_MAX_BARS, **_ema_pair()).strip()


def _when(stamp, t) -> str:
    """An intraday stamp "YYYY-MM-DD HH:MM" → "HH:MM ET" on the read's own date, else "YYYY-MM-DD HH:MM ET" (a cross in
    the 🎾 card's prior-session tail keeps its date); a date-only stamp → the date; None → "an earlier bar"."""
    if not isinstance(stamp, str) or not stamp.strip():
        return EARLIER_BAR
    s = stamp.strip()
    if len(s) <= 10:
        return s
    hhmm = s[11:16]
    if isinstance(t, str) and s[:10] == t.strip()[:10]:
        return f"{hhmm} ET"
    return f"{s[:10]} {hhmm} ET"


def _text(read: dict) -> Optional[str]:
    tier = read.get("tier")
    tpl = TEXT.get(tier) if isinstance(tier, str) else None
    if tpl is None or read.get("state") == EX.BLINK_NONE:
        return None
    gap = EX.finite(read.get("gap_pct"))
    if gap is None:
        tpl = tpl.replace(GAP_PART, "")
    n = read.get("bars_to_cross") if read.get("state") == EX.BLINK_IN else read.get("bars_since_cross")
    return tpl.format(gap=f"{gap:.2f}" if gap is not None else "", n=n,
                      when=_when(read.get("cross_t"), read.get("t")), **_ema_pair())


# ── the card block ───────────────────────────────────────────────────────────────────────────────────────────────
def block(read, *, tf) -> Optional[dict]:
    """The served card block of one blink_read (None → None). NaN-free: every float through EX.finite."""
    if not isinstance(read, dict) or read.get("state") not in EX.BLINK_STATES:
        return None
    state = read["state"]
    gap = EX.finite(read.get("gap_pct"))

    def _i(v):
        return v if isinstance(v, int) and not isinstance(v, bool) else None

    return {"state": state, "tier": read.get("tier") if state != EX.BLINK_NONE else None,
            "blink": state != EX.BLINK_NONE, "closeness": _i(read.get("closeness")),
            "bars_to_cross": _i(read.get("bars_to_cross")), "bars_since_cross": _i(read.get("bars_since_cross")),
            "gap_pct": round(gap, 2) if gap is not None else None, "above": bool(read.get("above")),
            "cross_t": read.get("cross_t") if isinstance(read.get("cross_t"), str) else None,
            "t": read.get("t") if isinstance(read.get("t"), str) else None, "tf": tf,
            "text": _text(read), "title": title(), "fast": GC.EMA_FAST, "slow": GC.EMA_SLOW}


def block_from_curves(curves, bars, *, tf, **kw) -> Optional[dict]:
    """The block of a card frame: the fast / slow series read by tone (bars.EMA_TONES) off its served `curves`, the
    stamps and closes off its `bars` (a bar without `c` → close None; the stamps still flow). None when the curves or
    bars are missing or ragged (a curve longer / shorter than the bars). `kw` = blink_read's thresholds."""
    try:
        from chart_maps.gajjala.bars import EMA_TONES
        bl = [b for b in (bars or []) if isinstance(b, dict)] if isinstance(bars, list) else []
        if len(bl) < 2 or not isinstance(curves, list):
            return None
        by = {c.get("tone"): c.get("values") for c in curves if isinstance(c, dict)}
        (fast_tone, _fl, _fp), (slow_tone, _sl, _sp) = EMA_TONES
        fv, sv = by.get(fast_tone), by.get(slow_tone)
        if not isinstance(fv, list) or not isinstance(sv, list) or len(fv) != len(bl) or len(sv) != len(bl):
            return None
        ts = [b.get("t") if isinstance(b.get("t"), str) else None for b in bl]
        closes = [b.get("c") for b in bl]
        return block(EX.blink_read(fv, sv, ts, closes, **kw), tf=tf)
    except Exception as exc:                                        # noqa: BLE001 — a card never breaks on it
        log.debug("ema_blink: block_from_curves failed: %s", exc)
        return None


def block_from_bars(bars, *, tf=DAILY_FRAME, **kw) -> Optional[dict]:
    """The block over daily bars through the house EMA (EX.blink_from_bars). The daily boards pass
    `through=daily_through(now)` (the forming bar dropped) and `up_max_bars=GC.BLINK_DAILY_UP_MAX_BARS`."""
    try:
        return block(EX.blink_from_bars(bars, **kw), tf=tf)
    except Exception as exc:                                        # noqa: BLE001
        log.debug("ema_blink: block_from_bars failed: %s", exc)
        return None


# ── the clock ────────────────────────────────────────────────────────────────────────────────────────────────────
def _et(now: Optional[datetime]) -> datetime:
    now = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ET)


def daily_through(now: Optional[datetime] = None) -> Optional[str]:
    """The `through` stamp for a daily tile: None when today's daily bar is CLOSED (a market day at or after
    rth_close_time — the house clock, half days included), else yesterday's ISO date, so the engine drops every bar
    stamped today (the forming RTH bar, the synthetic pre-market bar). A raising calendar → drop today (the safe side)."""
    et = _et(now)
    today = et.date()
    try:
        from catalysts.medical.reaction import is_market_day, rth_close_time
        closed = bool(is_market_day(today)) and et.time() >= rth_close_time(today)
    except Exception as exc:                                        # noqa: BLE001
        log.debug("ema_blink: daily clock failed: %s", exc)
        closed = False
    return None if closed else (today - timedelta(days=1)).isoformat()


def in_window(now: Optional[datetime] = None) -> bool:
    """The tab-dot feed re-reads only while the market is open today (market_hours.gate.closed_reason) AND THE pass
    window holds (chart_maps.gajjala.run.in_window: PASS_OPEN_ET–PASS_CLOSE_ET on a market day) — the on-open's
    `_closed` shape. A raising gate → False (never a hot loop on a bad calendar)."""
    try:
        from market_hours.gate import closed_reason
        from chart_maps.gajjala import run as RUN
        et = _et(now)
        if closed_reason(et) is not None:
            return False
        return bool(RUN.in_window(et))
    except Exception as exc:                                        # noqa: BLE001
        log.warning("ema_blink: window check failed: %s", exc)
        return False


# ── the order ────────────────────────────────────────────────────────────────────────────────────────────────────
def sort_key(tile) -> tuple:
    """THE order: blinking first, then the tier's rank (fresh → imminent → near → closing → up), then closeness in bars,
    then the gap %. NO symbol: every non-blinking tile keys alike, so a stable sort keeps the board's own order."""
    b = tile.get("ema_blink") if isinstance(tile, dict) else None
    b = b if isinstance(b, dict) else {}
    blinking = b.get("blink") is True
    c = b.get("closeness")
    g = EX.finite(b.get("gap_pct"))
    return (0 if blinking else 1, EX.tier_rank(b.get("tier")) if blinking else len(EX.TIERS),
            c if blinking and isinstance(c, int) and not isinstance(c, bool) else 0,
            g if blinking and g is not None else math.inf)


def top_key(sym, blk) -> tuple:
    """sort_key + the symbol — the tie-break lives ONLY in the tab counts' `top`."""
    return sort_key({"ema_blink": blk}) + (str(sym or ""),)


def tab_tier(blocks) -> Optional[str]:
    """The fastest tier (smallest tier_rank) among the blinking blocks, else None."""
    tiers = [b.get("tier") for b in (blocks or []) if isinstance(b, dict) and b.get("blink") is True
             and b.get("tier") in EX.TIERS]
    return min(tiers, key=EX.tier_rank) if tiers else None


# ── the tab-dot counts (GET /chart-maps/ema-blink) ───────────────────────────────────────────────────────────────
def _iso(d) -> Optional[str]:
    return d.isoformat()[:10] if isinstance(d, (date, datetime)) else None


def _tab_obj(blocks_by_sym: dict, frame: str, session=None) -> dict:
    """{n, crossed_up, closing_in, tier, frame, session, top, text} over {SYM: the symbol's top block}."""
    hot = {s: b for s, b in blocks_by_sym.items() if isinstance(b, dict) and b.get("blink") is True}
    n = len(hot)
    top = None
    if hot:
        sym, b = min(hot.items(), key=lambda kv: top_key(kv[0], kv[1]))
        top = {"symbol": sym, "tier": b.get("tier"), "closeness": b.get("closeness")}
    text = None
    if n == 1:
        text = TAB_TEXT_ONE.format(sym=top["symbol"], **_ema_pair())
    elif n > 1:
        text = TAB_TEXT.format(n=n, sym=top["symbol"], **_ema_pair())
    return {"n": n, "crossed_up": sum(1 for b in hot.values() if b.get("state") == EX.BLINK_UP),
            "closing_in": sum(1 for b in hot.values() if b.get("state") == EX.BLINK_IN),
            "tier": tab_tier(hot.values()), "frame": frame, "session": _iso(session), "top": top, "text": text}


def _best(blocks: list) -> Optional[dict]:
    """The symbol's top block (min by sort_key) — a blinking card wins over a quiet one."""
    bl = [b for b in blocks if isinstance(b, dict)]
    return min(bl, key=lambda b: sort_key({"ema_blink": b})) if bl else None


def _gg_counts(st, vv, now) -> dict:
    """A GG store (GG5 / GG1): ONE projected find of the session's read docs (stamps only, no closes, no $slice — the
    whole frame and the 🎾 `_prior` tail), names filtered to the scanner's listed set, every card a read in a
    tab.TILE_STATES state (the 🧠 cards included: potential.POTENTIAL_STATE is one of them) that the board would card
    (tab._vcp_listed), each through THE frame builder tab._tile_frame on the variant's PRIMARY frame (wide on 🎾)."""
    from chart_maps.gajjala import scanner as SC
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import tab as GT
    from chart_maps.gajjala import variant as V
    session = GT.session_for(now)[0]
    suf = V.frame_minutes(vv.primary, vv)
    proj = {"symbol": 1, f"tile.curves{suf}": 1, f"tile.bars{suf}.t": 1, f"tile.curves{suf}_prior": 1,
            f"tile.bars{suf}_prior.t": 1}
    for s in GC.SETUPS:
        proj[f"setups.{s}.state"] = 1
        proj[f"setups.{s}.cycles"] = 1                      # tab._vcp_listed reads it (the 🌀 listing rule)
    c = st.coll(ST.READS)
    docs = [d for d in c.find({"date": session.isoformat()}, proj) if isinstance(d, dict) and d.get("symbol")]
    try:
        listed = SC.listed_symbols(st, session)
    except Exception as exc:                                        # noqa: BLE001 — the board lists every read then too
        log.warning("ema_blink: listed read failed: %s", exc)
        listed = {}
    held = set()
    for s in GC.SETUPS:
        try:
            if GT._awaiting(s) is not None:                          # an unanswered placeholder cards nothing
                held.add(s)
        except Exception:                                           # noqa: BLE001
            pass
    by_sym: dict = {}
    for d in docs:
        sym = str(d["symbol"]).upper()
        if listed and sym not in listed:
            continue
        setups = d.get("setups") if isinstance(d.get("setups"), dict) else {}
        frames: dict = {}
        blocks = []
        for s in GC.SETUPS:
            r = setups.get(s) if isinstance(setups.get(s), dict) else {}
            if s in held or r.get("state") not in GT.TILE_STATES or not GT._vcp_listed(s, r):
                continue
            wide = s == "reversal_squeeze"
            if wide not in frames:
                fr = GT._tile_frame(d, vv.primary, vv, wide=wide)
                frames[wide] = block_from_curves(fr["curves"], fr["bars"], tf=fr["tf"])
            blocks.append(frames[wide])
        if blocks:
            by_sym[sym] = _best(blocks)
    return _tab_obj(by_sym, vv.primary, session)


def _luk_counts(st, now) -> dict:
    """🥇 Luk: ONE projected find of the session's reads; a symbol carded when any setup sits in luk.tab.TILE_STATES;
    the block over the 5-minute frame its card draws (tile.curves5 / bars5, LUK.primary)."""
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import variant as V
    from chart_maps.luk import tab as LT
    from chart_maps.luk.variant import LUK
    session = LT.session_for(now)[0]
    suf = V.frame_minutes(LUK.primary, LUK)
    proj = {"symbol": 1, f"tile.curves{suf}": 1, f"tile.bars{suf}.t": 1}
    for s in LT.SETUP_SUBS:
        proj[f"setups.{s}.state"] = 1
    c = st.coll(ST.READS)
    by_sym: dict = {}
    for d in c.find({"date": session.isoformat()}, proj):
        if not isinstance(d, dict) or not d.get("symbol"):
            continue
        setups = d.get("setups") if isinstance(d.get("setups"), dict) else {}
        if not any(isinstance(setups.get(s), dict) and setups[s].get("state") in LT.TILE_STATES
                   for s in LT.SETUP_SUBS):
            continue
        tile = d.get("tile") if isinstance(d.get("tile"), dict) else {}
        by_sym[str(d["symbol"]).upper()] = block_from_curves(tile.get(f"curves{suf}"), tile.get(f"bars{suf}"),
                                                             tf=LUK.primary)
    return _tab_obj(by_sym, LUK.primary, session)


def _watch_counts(db, now) -> dict:
    """👀 the owner's watch: ONE projected find of his names' tile docs; every frame of gajjala_watch FRAMES."""
    from chart_maps.gajjala_watch import colls as CO
    from chart_maps.gajjala_watch import constants as WC
    cs = CO.colls(db)
    if cs is None:
        raise RuntimeError("no database")
    names = CO.owner_symbols(db, strict=True)
    tfs = [tf for tf, _rule in WC.FRAMES]
    by_sym: dict = {}
    if names:
        proj = {}
        for tf in tfs:
            proj[f"frames.{tf}.curves"] = 1
            proj[f"frames.{tf}.bars.t"] = 1
        for d in cs["tiles"].find({"_id": {"$in": list(names)}}, proj):
            if not isinstance(d, dict) or not d.get("_id"):
                continue
            frames = d.get("frames") if isinstance(d.get("frames"), dict) else {}
            blocks = []
            for tf in tfs:
                t = frames.get(tf) if isinstance(frames.get(tf), dict) else {}
                blocks.append(block_from_curves(t.get("curves"), t.get("bars"), tf=tf))
            by_sym[str(d["_id"]).upper()] = _best(blocks)
    return _tab_obj(by_sym, "/".join(tfs))


def tab_counts(now: Optional[datetime] = None, *, owner: bool = False, gg_store=None, gg1_store=None,
               luk_store=None, watch_db=None) -> dict:
    """The tab-dot feed. `n` = the number of SYMBOLS in the tab's store for its session with at least one card at or
    near the cross on the tab's PRIMARY frame — cards past the board's cut included, the 15-minute toggle excluded.
    Stored docs only (projected finds, no bar fetch). A failing tab → that tab None (never a raise); 👀 is served to the
    owner only (`owner is True`), else None. The stores are injectable (tests); None = the real ones."""
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import tab as GT
    from chart_maps.gajjala import variant as V
    now = _et(now)
    win = in_window(now)
    tabs: dict = {k: None for k in TAB_KEYS}

    def _soft(key, fn, *a):
        try:
            tabs[key] = fn(*a)
        except Exception as exc:                                    # noqa: BLE001 — one tab never takes the feed down
            log.warning("ema_blink: %s counts failed: %s", key, exc)
            tabs[key] = None

    gg = gg_store if gg_store is not None else ST.default()
    _soft(V.GG5.tab, _gg_counts, gg, V.GG5, now)
    tabs[V.GGA.tab] = dict(tabs[V.GG5.tab]) if isinstance(tabs[V.GG5.tab], dict) else None   # 🧪 = the same reads
    gg1 = gg1_store if gg1_store is not None else ST.for_variant(V.GG1)
    _soft(V.GG1.tab, _gg_counts, gg1, V.GG1, now)
    if luk_store is None:
        from chart_maps.luk import store as LS
        luk_store = LS.default()
    from chart_maps.luk.variant import LUK
    _soft(LUK.tab, _luk_counts, luk_store, now)
    from chart_maps.gajjala_watch import constants as WC
    if owner is True:
        _soft(WC.TAB, _watch_counts, watch_db, now)
    else:
        tabs[WC.TAB] = None
    try:
        session = _iso(GT.session_for(now)[0])
    except Exception:                                               # noqa: BLE001
        session = None
    return {"as_of": now.isoformat(), "session": session, "in_window": win,
            "refresh_sec": GC.BLINK_TAB_REFRESH_SEC if win else 0, "info": info(), "n_means": N_MEANS,
            "tabs": tabs}


__all__ = ["DAILY_FRAME", "TEXT", "TITLE", "INFO_TEXT", "SORT_LABEL", "SORT_DEFAULT_LABEL", "ORDER_TEXT",
           "SORT_UNAVAILABLE", "RULES_LINE", "TAB_TEXT", "TAB_TEXT_ONE", "N_MEANS", "BLOCK_KEYS", "TAB_KEYS", "info",
           "title", "sort_label", "order_text", "sort_unavailable", "rules_line", "block", "block_from_curves",
           "block_from_bars", "daily_through", "in_window", "sort_key", "top_key", "tab_tier", "tab_counts"]
