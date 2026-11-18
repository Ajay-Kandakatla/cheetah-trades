"""🌱 Diverging sub on 🚩 Gajjala's 5-minute tab — a FORMING read over the pass's stored 5-minute bars (2026-11-18,
SPEC §3.2–3.5, WP-A).

Ajay 2026-11-18 ~11:50 ET, verbatim: "For the divergence thing create a separate tab that are potentially diverging with
uptrend and volume breakout." · "Are you building that now?". His two picks, the option text VERBATIM = the rule:
  (1) "Fresh cross, gap widening": "The 9 EMA crossed above the 21 EMA and the gap between them has widened for 2+ bars
      in a row, but is not yet wide enough to make the 🧨 Divergence record." (5-min bars; uptrend = price above a
      rising 21 EMA)
  (2) "GG's day floor + bar spike": "The name has traded GG's daily volume floor (the same one his pushes use), and the
      latest 5-min bar's volume is at least 2× its last 20 bars' average."

UNMEASURED — nothing has measured this read. A forming read, not an entry: no alert, no gate, no record, no push, no
trade, no fetch. Computed ON THE GET from the stored `gajjala_reads` docs tab.build already holds (`reads_by`), through
the 🧨 engine (chart_maps.gajjala.divergence: from_tile, atr_series, r1_series, eligible, up_cross_before, _on) — never a
parallel EMA / cross / ATR / gap / window implementation. The window words are divergence_tab's (window_text /
WINDOW_WORDS — the ONE helper). Every number in a served sentence is a GC constant read at call time. A name that turns
down can reverse as easily as it ran — the surface says "reversal", never the other word.
"""
from __future__ import annotations

import logging
import statistics
from datetime import date, datetime
from typing import Callable, Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as DT          # the K11 parser + the ONE K11 criteria row
from chart_maps.gajjala import divergence as DV
from chart_maps.gajjala import divergence_tab as DVT
from chart_maps.gajjala import ema_cross as EX
from chart_maps.gajjala import variant as V

log = logging.getLogger("chart_maps.gajjala.diverging_tab")

FAULT_TEXT = "🌱 The diverging read could not be made this time — the next re-read tries again."
TITLE = ("🌱 Diverging — 9 EMA freshly over the 21 EMA, gap widening but under the 🧨 cut, bar volume spiking · a FORMING "
         "read, not an entry · UNMEASURED")
ASK_TEXT = ("Ajay 2026-11-18: “For the divergence thing create a separate tab that are potentially diverging with uptrend "
            "and volume breakout.” · “Are you building that now?”")
PICK_TEXTS = ("Your pick (1) “Fresh cross, gap widening”: “The 9 EMA crossed above the 21 EMA and the gap between them has "
              "widened for 2+ bars in a row, but is not yet wide enough to make the 🧨 Divergence record.”",
              "Your pick (2) “GG's day floor + bar spike”: “The name has traded GG's daily volume floor (the same one his "
              "pushes use), and the latest 5-min bar's volume is at least 2× its last 20 bars' average.”")
RULE_LABEL = "ⓘ what gets listed"
COHORT_TEXT = ("Names read: every name on this tab's stored 5-minute reads this session — the pass's own list, nothing "
               "new fetched.")
BARS_TEXT = ("Latest stored bar {hhmm} ET · {n} of {n_read} name(s) last read on an earlier bar — each card names its "
             "bar")
EMPTY_TODAY = "No name is diverging on its latest stored 5-minute bar."
EMPTY_SESSION = "No name was diverging at the last read of the {label} session."
FAULTS_TEXT = "{n} name(s) could not be read this time — the rest of the board stands"
ORDER_NOTE = "🌱 today's volume first (his word for every Gajjala card), then the wider gap"
CHARTLESS_TEXT = "🌱 {sym} diverging on the {hhmm} ET bar · chart not stored"
STATE = "diverging"
DASH = "—"


# ── formatting ──────────────────────────────────────────────────────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    try:
        return EX.finite(x)
    except Exception:                                   # noqa: BLE001 — a junk value is "unknown", never a raise
        return None


def _num(x, fmt: str) -> str:
    v = _f(x)
    return DASH if v is None else format(v, fmt)


def _hhmm(t) -> Optional[str]:
    return t[11:16] if isinstance(t, str) and len(t) >= 16 else None


def _windows() -> dict:
    return {k: (lo, hi) for k, lo, hi in GC.DIVERGENCE_WINDOWS}


def _rth_lo() -> str:
    return _windows()[GC.DIVERGENCE_WINDOWS[0][0]][0]


def _vol(x) -> str:
    from chart_maps.gajjala import tab as GT            # lazy — tab imports this module inside build
    v = _f(x)
    return (GT._compact(v) or DASH) if v is not None else DASH


def _px(x) -> str:
    from chart_maps.gajjala import tab as GT
    return GT._px(x) if _f(x) is not None else DASH


def _floor_text() -> str:
    return f"{int(GC.K11_MIN_SESSION_VOLUME):,}"


# ── the read (pure) ─────────────────────────────────────────────────────────────────────────────────────────────
def clock_of(session) -> datetime:
    """The 04:00 ET open of the session as aware UTC — divergence.units_today's `four` (the prior-date ring clock);
    every on-session closed bar closes after it, so eligible()'s clock gate is a no-op here by construction."""
    from daytrading.data import ET_PREMARKET_OPEN
    return datetime.combine(DV._as_date(session), ET_PREMARKET_OPEN, tzinfo=DV.ET).astimezone(DV.UTC)


def widen_run(R1: list, i: int) -> int:
    """How many closed bars in a row, ending at i, the gap widened: the largest k with R1[i-k..i] all finite and
    STRICTLY increasing (R1[j] > R1[j-1]). 0 when R1[i] is None or R1[i-1] is None / ≥ R1[i]. Ties = not widened."""
    if not isinstance(i, int) or i < 0 or i >= len(R1):
        return 0
    k, j = 0, i
    while j >= 1:
        a, p = _f(R1[j]), _f(R1[j - 1])
        if a is None or p is None or not a > p:
            break
        k += 1
        j -= 1
    return k


def pre_bars(b: DV.Bars5, i: int, L: int) -> int:
    """How many of the L bars before i closed before the RTH window opens — not on the session (the prior tail) or a
    stamp under GC.DIVERGENCE_WINDOWS[0][1] (09:35, the first RTH close). A FACT of the bars in hand, served on the
    card's bar-volume row — never a gate."""
    rth_lo = GC.DIVERGENCE_WINDOWS[0][1]
    return sum(1 for j in range(max(0, i - L), i) if not DV._on(b, j) or str(b.t[j])[11:16] < rth_lo)


def read_bars(b: DV.Bars5, session_volume, *, session) -> Optional[dict]:
    """ONE name's latest closed 5-min bar against the two picks. None = not listed. Cheapest checks first; the ATR
    (pandas) only for the survivors. Never raises on ragged input (finite() everywhere; a None EMA = not met).
      (a) session floor: today's volume ≥ GC.K11_MIN_SESSION_VOLUME (fail-closed, as K11)
      (b) bar spike:     the bar's volume ≥ GC.DIVERGING_BAR_VOL_MULT × the mean of the GC.DIVERGING_BAR_VOL_LOOKBACK
                         bars before it (fewer bars / a zero mean = never a listing); pre_bars = a fact, not a gate
      (c) uptrend:       9 > 21, close > 21, 21 above its value GC.DIVERGING_EMA21_RISE_BARS bar(s) earlier
      (d) fresh cross:   a 9-over-21 up cross ON the session (divergence.up_cross_before)
      (e) the gap:       eligible() in a GC.DIVERGENCE_WINDOWS window; widened on each of the last
                         GC.DIVERGING_WIDEN_BARS bars; under GC.DIVERGENCE_R1_LEVEL on EVERY bar since that cross (at or
                         over it once = 🧨's side by rule; a bar whose ATR is unknown cannot be judged and is skipped)."""
    n = len(b)
    if n == 0:
        return None
    i = n - 1
    sv = DT._k11_volume(session_volume)                                         # (a)
    if sv is None or sv < GC.K11_MIN_SESSION_VOLUME:
        return None
    L = GC.DIVERGING_BAR_VOL_LOOKBACK                                           # (b)
    if i < L:
        return None
    prior = [_f(x) for x in b.v[i - L:i]]
    bv = _f(b.v[i])
    if bv is None or any(x is None for x in prior):
        return None
    mean = statistics.fmean(prior)
    if not mean > 0:
        return None
    mult = bv / mean
    if mult < GC.DIVERGING_BAR_VOL_MULT:
        return None
    pb = pre_bars(b, i, L)
    rise = GC.DIVERGING_EMA21_RISE_BARS                                         # (c)
    f, s, c = _f(b.ema9[i]), _f(b.ema21[i]), _f(b.c[i])
    s0 = _f(b.ema21[i - rise]) if i - rise >= 0 else None
    if f is None or s is None or c is None or s0 is None or not (f > s and c > s and s > s0):
        return None
    up_t = DV.up_cross_before(b, i)                                             # (d)
    if up_t is None:
        return None
    cross_i = b.t.index(up_t)
    A = DV.atr_series(b)                                                        # (e)
    R1 = DV.r1_series(b, A)
    clock = clock_of(session)
    window = next((w for w in GC.DIVERGENCE_WINDOWS if DV.eligible(b, A, i, clock, w)), None)
    if window is None:
        return None
    k = widen_run(R1, i)
    if k < GC.DIVERGING_WIDEN_BARS:
        return None
    since = [R1[j] for j in range(cross_i, i + 1) if R1[j] is not None]
    if not since or any(x >= GC.DIVERGENCE_R1_LEVEL for x in since):
        return None
    return {"bar_t": b.t[i], "window": window[0], "gap_atr": R1[i], "gap_path": list(R1[i - k:i + 1]),
            "widen_bars": k, "gap_peak": max(since), "ema9": f, "ema21": s, "ema21_prev": s0, "close": c,
            "atr": A[i], "up_cross_t": up_t, "cross_i": cross_i, "bar_vol": bv, "bar_vol_mean": mean,
            "bar_vol_mult": mult, "bar_vol_n": L, "pre_bars": pb, "session_volume": sv}


def _bars_of(doc: dict, session) -> DV.Bars5:
    b = DV.from_tile(doc, session)
    if b is None:
        raise ValueError("malformed stored tile")
    return b


def read_doc(doc: dict, session_volume, *, session) -> Optional[dict]:
    """A stored gajjala_reads doc → read_bars(DV.from_tile(doc, session), …). A malformed tile raises ValueError so the
    caller's per-name fence counts a fault."""
    return read_bars(_bars_of(doc, session), session_volume, session=session)


def _order_key(row: dict):
    r = row["read"]
    sv = _f(r.get("session_volume"))
    g = _f(r.get("gap_atr"))
    return (sv is None, -(sv or 0.0), g is None, -(g or 0.0), row["symbol"])


def _empty_ev() -> dict:
    return {"rows": [], "faults": [], "n_read": 0, "latest_bar_t": None, "behind": []}


def evaluate(reads_by: dict, *, scan_row: Callable, session: date, v=None) -> dict:
    """ONE evaluation per build, shared by the chip and the block: {"rows": [{symbol, read, read_doc}], "faults": [SYM],
    "n_read", "latest_bar_t" (the max last-bar stamp over every tile that parsed, None when none), "behind" (sorted
    symbols whose tile's last stamp < latest_bar_t)}. Every name in its OWN try (a raising name → faults, never a
    listing, never the sub down); from_tile ONCE per name. GG5 only. Raises only when reads_by is not a dict."""
    if not isinstance(reads_by, dict):
        raise TypeError("reads_by is not a dict")
    if not V.is_gg5(V.of(v)):
        return _empty_ev()
    rows, faults, lasts = [], [], {}
    for sym, doc in reads_by.items():
        s = str(sym or "").upper()
        try:
            b = _bars_of(doc, session)
            lasts[s] = b.t[-1]
            row_ = scan_row(s) or {}
            r = read_bars(b, row_.get("volume"), session=session)
            if r is not None:
                rows.append({"symbol": s, "read": r, "read_doc": doc})
        except Exception as exc:                                    # noqa: BLE001 — one name never takes the sub down
            log.warning("gajjala diverging: read %s failed: %s", s, type(exc).__name__)
            lasts.pop(s, None)
            faults.append(s)
    rows.sort(key=_order_key)
    latest = max(lasts.values()) if lasts else None
    behind = sorted(s for s, t in lasts.items() if latest is not None and t < latest)
    return {"rows": rows, "faults": faults, "n_read": len(reads_by), "latest_bar_t": latest, "behind": behind}


# ── the panel words (pure over GC) ──────────────────────────────────────────────────────────────────────────────
def rule_text() -> str:
    w = _windows()
    (rth_lo, rth_hi), (ah_lo, ah_hi) = w["rth"], w["ah"]
    return ("Listed when a name's latest closed 5-minute bar (between %s and %s ET, or %s–%s after hours; never "
            "pre-market) has the %d EMA above the %d EMA after a bullish %d/%d cross today, the close above the %d EMA "
            "and the %d EMA higher than %d closed bar(s) earlier, the %d−%d gap in %d-bar ATRs wider on each of the "
            "last %d closed bars and under %.3f ATRs on every bar since that cross (at or over it once, the name "
            "belongs to 🧨 Divergence), the bar's volume at least %.1f× the mean of the %d bars before it, and today's "
            "volume at or above GG's %s-share floor — the floor his pushes use. Read off the stored 5-minute bars of "
            "this tab's pass; nothing is fetched, recorded or sent."
            % (rth_lo, rth_hi, ah_lo, ah_hi, GC.EMA_FAST, GC.EMA_SLOW, GC.EMA_FAST, GC.EMA_SLOW, GC.EMA_SLOW,
               GC.EMA_SLOW, GC.DIVERGING_EMA21_RISE_BARS, GC.EMA_FAST, GC.EMA_SLOW, GC.DIVERGENCE_ATR_PERIOD,
               GC.DIVERGING_WIDEN_BARS, GC.DIVERGENCE_R1_LEVEL, GC.DIVERGING_BAR_VOL_MULT,
               GC.DIVERGING_BAR_VOL_LOOKBACK, _floor_text()))


def honesty() -> str:
    is_from, is_to, n_sessions = GC.DIVERGENCE_IS_WINDOW
    return ("UNMEASURED — nothing has measured this read; it is a forming read, not an entry: no alert, no gate, no "
            "record, no trade. The 🧨 rule it leads into lost money in the 11-16 study (%d sessions, %s → %s). Early in "
            "the session the %d-bar volume mean is mostly pre-market bars, so most names clear %.1f× on the first bars "
            "— each card says how many of its mean bars closed before %s ET. A name here can reverse as easily as run."
            % (n_sessions, is_from, is_to, GC.DIVERGING_BAR_VOL_LOOKBACK, GC.DIVERGING_BAR_VOL_MULT, _rth_lo()))


# ── one listing's words ─────────────────────────────────────────────────────────────────────────────────────────
def _path_text(path) -> str:
    return " → ".join(_num(x, ".2f") for x in (path or [])) or DASH


def _pre_phrase(r: dict) -> Optional[str]:
    pb = r.get("pre_bars")
    if not isinstance(pb, int) or isinstance(pb, bool) or pb <= 0:
        return None
    return "%d of the %d bars in the mean closed before %s ET (pre-market or the prior session)" % (
        pb, int(r.get("bar_vol_n") or GC.DIVERGING_BAR_VOL_LOOKBACK), _rth_lo())


def state_label(r: dict) -> str:
    return ("🌱 diverging · gap %s ATRs on the %s ET bar · widening %d bars · bar volume %s×"
            % (_num(r.get("gap_atr"), ".2f"), _hhmm(r.get("bar_t")) or DASH, int(r.get("widen_bars") or 0),
               _num(r.get("bar_vol_mult"), ".1f")))


def criteria(r: dict) -> list:
    at = _hhmm(r.get("bar_t")) or DASH
    pre = _pre_phrase(r)
    bar_value = "%s = %s× the %d-bar mean %s" % (_vol(r.get("bar_vol")), _num(r.get("bar_vol_mult"), ".1f"),
                                                 int(r.get("bar_vol_n") or GC.DIVERGING_BAR_VOL_LOOKBACK),
                                                 _vol(r.get("bar_vol_mean")))
    if pre:
        bar_value += " · " + pre
    return [
        {"key": "gap", "label": "%d EMA over %d EMA, in ATRs" % (GC.EMA_FAST, GC.EMA_SLOW),
         "value": "%s ATRs on the %s ET bar · peak %s since the cross" % (_num(r.get("gap_atr"), ".2f"), at,
                                                                          _num(r.get("gap_peak"), ".2f")),
         "need": ("under %.3f ATRs on every bar since the cross — at or over it once, the name moves to 🧨 Divergence"
                  % GC.DIVERGENCE_R1_LEVEL), "ok": True},
        {"key": "widening", "label": "gap widening",
         "value": "%d closed bars in a row (%s)" % (int(r.get("widen_bars") or 0), _path_text(r.get("gap_path"))),
         "need": "≥ %d closed bars in a row, each wider than the one before" % GC.DIVERGING_WIDEN_BARS, "ok": True},
        {"key": "uptrend", "label": "uptrend",
         "value": ("%d EMA crossed above the %d at %s ET · close %s above the %d EMA %s · %d EMA rising"
                   % (GC.EMA_FAST, GC.EMA_SLOW, _hhmm(r.get("up_cross_t")) or DASH, _px(r.get("close")), GC.EMA_SLOW,
                      _px(r.get("ema21")), GC.EMA_SLOW)),
         "need": "a bullish %d/%d cross today; close above a rising %d EMA" % (GC.EMA_FAST, GC.EMA_SLOW, GC.EMA_SLOW),
         "ok": True},
        {"key": "bar_volume", "label": "bar volume spike", "value": bar_value,
         "need": "≥ %.1f× the mean of the %d bars before" % (GC.DIVERGING_BAR_VOL_MULT, GC.DIVERGING_BAR_VOL_LOOKBACK),
         "ok": True},
        DT.k11_criterion(r.get("session_volume")),
    ]


def record_words(r: dict) -> dict:
    """The read in words for the card (every value a string or None — no raw float served as words)."""
    w = r.get("window")
    pre = r.get("pre_bars")
    return {"bar_t": r.get("bar_t") if isinstance(r.get("bar_t"), str) else None,
            "at_text": "%s ET" % (_hhmm(r.get("bar_t")) or DASH),
            "window": w if w in DVT.WINDOW_WORDS else None, "window_text": DVT.WINDOW_WORDS.get(w),
            "gap_text": "%s ATRs" % _num(r.get("gap_atr"), ".2f"),
            "gap_peak_text": "peak %s ATRs since the cross" % _num(r.get("gap_peak"), ".2f"),
            "cut_text": "🧨 cut %.3f ATRs" % GC.DIVERGENCE_R1_LEVEL,
            "widen_text": "%d bars" % int(r.get("widen_bars") or 0),
            "bar_vol_text": "%s×" % _num(r.get("bar_vol_mult"), ".1f"),
            "pre_bars_text": ("%d of %d before %s ET" % (pre, int(r.get("bar_vol_n") or GC.DIVERGING_BAR_VOL_LOOKBACK),
                                                         _rth_lo())
                              if isinstance(pre, int) and not isinstance(pre, bool) and pre > 0 else None),
            "session_volume_text": _int_text(r.get("session_volume")),
            "up_cross_text": "%s ET" % (_hhmm(r.get("up_cross_t")) or DASH)}


def _int_text(x) -> Optional[str]:
    v = _f(x)
    return None if v is None else f"{int(v):,}"


# ── the card (the 🧨 card() recipe) ─────────────────────────────────────────────────────────────────────────────
def card(read_doc: dict, row: dict, *, scan_row: dict, sess: dict, halt_doc, listed_info, pass_at, v) -> dict:
    """One house card for one listed name. No buy marker, no ENTRY line, no plan — a forming read, not an entry.
    Raises on a malformed stored tile (the caller's per-name fence)."""
    from chart_maps.gajjala import tab as GT
    vv = V.of(v)
    tile = read_doc.get("tile")
    suf = str(V.frame_minutes(vv.primary, vv))
    if not isinstance(tile, dict) or not isinstance(tile.get(f"bars{suf}"), list):
        raise ValueError("malformed stored tile")
    fr = GT._tile_frame(read_doc, vv.primary, vv)
    sym = str(row.get("symbol") or "").upper()
    r = row["read"]
    markers = []
    cross = GT.ema_cross_block(fr)
    if cross:
        markers += [{"date": m["t"], "kind": GT.EMA_CROSS_MARK[m["dir"]], "label": m["text"], "price": _f(m["ema"])}
                    for m in cross.pop("_marks")]
    markers = GT._on_bars(markers, fr["bars"])
    stats = [s for s in ({"k": "Change", "v": GT._pct(scan_row.get("change_pct"))},
                         {"k": "Volume", "v": GT._compact(scan_row.get("volume"))}) if s["v"]]
    stats.append({"k": "Gap", "v": "%s ATRs" % _num(r.get("gap_atr"), ".2f")})
    stats.append({"k": "Bar vol", "v": "%s×" % _num(r.get("bar_vol_mult"), ".1f")})
    chips = GT._chips(read_doc, GC.DIVERGING_SUB, {}, scan_row, sess, halt_doc, None, pass_at=pass_at)
    g = {"setup": GC.DIVERGING_SUB, "state": STATE, "state_label": state_label(r), "criteria": criteria(r),
         "missed": [], "unjudged": [], "plan_text": None, "chips": chips, "listed": GT._listed_block(listed_info),
         "diverging": record_words(r)}
    vol_avg = fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None
    out = {"symbol": sym, "name": read_doc.get("name"), "href": GT.chart_href(sym, fr["tf"], vv), "tf": fr["tf"],
           "bars": fr["bars"], "vol_avg": vol_avg, "bands": [], "lines": [], "markers": markers, "stats": stats,
           "why": "", "badges": [], "curves": fr["curves"], "ema_blink": GT.ema_blink_of(fr), "gajjala": g}
    ax = GT.card_axis(fr, vv, sym=sym)
    if ax is not None:
        out["axis"] = ax
    return out


def _cards(rows: list, *, scan_row: Callable, sess: dict, halts_by: dict, listed: dict, pass_at, v) -> tuple:
    """(tiles, chartless, faults) — EACH listed name in its own try; a name is never dropped from the words."""
    from chart_maps.gajjala import tab as GT
    tiles, chartless, faults = [], [], []
    for row in rows:
        sym, r = row["symbol"], row["read"]
        hm = _hhmm(r.get("bar_t")) or DASH
        line = {"symbol": sym, "at_text": "%s ET" % hm, "state_label": None, "href": None,
                "text": CHARTLESS_TEXT.format(sym=sym or DASH, hhmm=hm)}
        try:
            line["state_label"] = state_label(r)
            line["href"] = GT.chart_href(sym, V.of(v).primary, v) if sym else None
            t = card(row["read_doc"], row, scan_row=scan_row(sym), sess=sess, halt_doc=(halts_by or {}).get(sym),
                     listed_info=(listed or {}).get(sym), pass_at=pass_at, v=v)
            if not t["bars"]:
                chartless.append(line)
                continue
            tiles.append(t)
        except Exception as exc:                                    # noqa: BLE001 — one name never takes the sub down
            log.warning("gajjala diverging tab: card %s failed: %s", sym, type(exc).__name__)
            chartless.append(line)
            faults.append(sym)
    return tiles, chartless, faults


# ── the served block ────────────────────────────────────────────────────────────────────────────────────────────
def block(ev: Optional[dict], *, session: date, now: datetime, is_today: bool, in_window: bool, reads_by: dict,
          scan_row: Callable, sess: dict, halts_by: dict, listed: dict, pass_at, flags, v) -> Optional[dict]:
    """The 🌱 sub's served block (+ `_tiles`, popped by tab.build). None ONLY when the evaluation faulted (`ev` None →
    tab serves FAULT_TEXT). `flags` is the order list tab.build applies with broker_bottom after the cut."""
    if ev is None:
        return None
    rows = list(ev.get("rows") or [])
    behind = list(ev.get("behind") or [])
    latest = ev.get("latest_bar_t")
    out = {"title": TITLE, "ask_text": ASK_TEXT, "pick_texts": list(PICK_TEXTS), "rule_label": RULE_LABEL,
           "rule_text": rule_text(), "honesty": honesty(), "cohort_text": COHORT_TEXT,
           "window_text": DVT.window_text(sess),
           "bars_text": (BARS_TEXT.format(hhmm=_hhmm(latest) or DASH, n=len(behind), n_read=int(ev.get("n_read") or 0))
                         if behind else None),
           "order_note": ORDER_NOTE, "n": len(rows), "n_read": int(ev.get("n_read") or 0),
           "empty_text": (None if rows else EMPTY_TODAY if is_today else
                          EMPTY_SESSION.format(label=(sess or {}).get("label") or session.isoformat()))}
    tiles, chartless, card_faults = _cards(rows, scan_row=scan_row, sess=sess, halts_by=halts_by, listed=listed,
                                           pass_at=pass_at, v=v)
    faults = list(dict.fromkeys(list(ev.get("faults") or []) + card_faults))
    out["chartless"] = chartless
    out["faults"] = faults
    out["faults_text"] = FAULTS_TEXT.format(n=len(faults)) if faults else None
    out["_tiles"] = tiles
    return out


__all__ = ["FAULT_TEXT", "TITLE", "ASK_TEXT", "PICK_TEXTS", "RULE_LABEL", "COHORT_TEXT", "BARS_TEXT", "EMPTY_TODAY",
           "EMPTY_SESSION", "FAULTS_TEXT", "ORDER_NOTE", "clock_of", "widen_run", "pre_bars", "read_bars", "read_doc",
           "evaluate", "rule_text", "honesty", "state_label", "criteria", "record_words", "card", "block"]
