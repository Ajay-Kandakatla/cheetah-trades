"""🥇 Luk's three screens (spec §3.6) — his TradingView screener settings (frames U4 / U5 / U6, iMBI3ZcQ6sU 1:17:37 "You
still use your screening settings … I think so"), built over the house whole-market snapshot + the trusted daily facts.

Comparisons are STRICT as his frames read (">"), except the potent screen's 21 EMA, built "≥" (HIS CALL #9). A row the
data cannot judge is never silently dropped and never silently passed:
  · cap unknown (the house cap cache has no entry)  → ok None, "cap unknown — not filtered", the row KEPT (HIS CALL #12)
  · daily facts DEFERRED by the trust rule           → every daily criterion ok None, daily.PENDING_TEXT, the row KEPT
  · a daily fact that is None (no closed frame)      → ok False, "no daily bars cached"
  · no regular-session open yet (pre-open `open` 0)  → ok False, "no regular-session open yet" (spec C12)
A row with any criterion ok False is off that screen; ok None keeps it. Each screen sorts by its served key only
(pre-market % change / 1-month % / % change), cuts LC.LUK_SCREEN_TOP_N, and numbers its rows (`rank`).
"""
from __future__ import annotations

from typing import Iterable, Optional

from . import constants as LC
from . import daily as DA
from . import tiers as TI

CAP_UNKNOWN_TEXT = "cap unknown — not filtered"
NO_DAILY_TEXT = "no daily bars cached"
NO_OPEN_TEXT = "no regular-session open yet"
PENDING_TEXT = DA.PENDING_TEXT
ADR_TEXT = "ADR {adr:.1f}% (20 days) — he mainly trades > {pref:g}% ADR, \"but this isn't a hard rule\""
PREMARKET, LEADER, POTENT = "premarket", "leader", "potent"
SCREENS = (PREMARKET, LEADER, POTENT)
SORT_KEY = {PREMARKET: "pm_chg_pct", LEADER: "perf_1m_pct", POTENT: "chg_pct"}
# his screen names (substack U2: "potent scan", "pre-market scan", "leader scan"); numbers formatted at call time
SCREEN_TITLES = {
    PREMARKET: ("☀️ Pre-market scan — his settings: cap > {cap} · 10-day avg vol > {avg_vol} · price×vol > {px_vol} · "
                "1-week volatility > {vol_1w}% · sorted by pre-market % change"),
    LEADER: ("🏆 Leader scan — his settings: cap > {cap} · 10-day avg vol > {avg_vol} · 1-week price×vol > {px_vol_1w} · "
             "sorted by 1-month % change"),
    POTENT: ("⚡ Potent scan — his settings: price > {e_slow} EMA · price ≥ {e_fast} EMA · cap > {cap} · 1-week "
             "volatility > {vol_1w}% · price×vol > {px_vol} · change from open outside ±{band}% · sorted by % change"),
}
_B, _M, _K = 1_000_000_000, 1_000_000, 1_000                   # units, not rules


# ── formatting ─────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _cmp(v: float) -> float:
    """Float hygiene for a boundary comparison (not a rule): 20.10 vs an open of 20.00 computes 0.5000000000000115 %,
    which must read as exactly 0.5 % — so a value is rounded to 9 decimals before it meets its threshold."""
    return round(float(v), 9)


def money(v) -> Optional[str]:
    v = _num(v)
    if v is None:
        return None
    if abs(v) >= _B:
        return f"${round(v / _B, 1):g}B"
    if abs(v) >= _M:
        return f"${round(v / _M, 1):g}M"
    return f"${round(v):,.0f}"


def count(v) -> Optional[str]:
    v = _num(v)
    if v is None:
        return None
    if abs(v) >= _M:
        return f"{round(v / _M, 2):g}M"
    if abs(v) >= _K:
        return f"{round(v / _K, 1):g}K"
    return f"{round(v):,.0f}"


def pct(v) -> Optional[str]:
    v = _num(v)
    return None if v is None else f"{v:.2f}%"


def title(key: str) -> str:
    """The served title of a screen, its numbers read from the constants NOW."""
    e_fast, e_slow = LC.LUK_POTENT_EMAS
    return SCREEN_TITLES[key].format(
        cap=money(LC.LUK_SCREEN_MIN_CAP_USD), avg_vol=count(LC.LUK_SCREEN_MIN_AVG_VOL_10D),
        px_vol=money(LC.LUK_SCREEN_MIN_PX_VOL_USD), vol_1w=f"{LC.LUK_SCREEN_MIN_VOL_1W_PCT:g}",
        px_vol_1w=money(LC.LUK_LEADER_MIN_PX_VOL_1W_USD), e_fast=e_fast, e_slow=e_slow,
        band=f"{LC.LUK_POTENT_CHG_FROM_OPEN_BAND_PCT:g}")


def titles() -> dict:
    return {k: title(k) for k in SCREENS}


# ── one row ────────────────────────────────────────────────────────────────────────────────────────────────────
def row_of(sym: str, snap_row: dict, facts, cap, session_iso: str) -> dict:
    """The screen row of one snapshot name. price = the snapshot's last print (`prices.extended_print`), else the
    day close; pm_chg_pct ONLY when that print is pre-market AND dated `session_iso` (a print of yesterday is not
    today's pre-market); chg_from_open_pct only when the regular-session open is > 0. `facts` = the daily facts, a
    `daily.Pending` slot (deferred), or None."""
    from sepa.prices import extended_print
    row = snap_row if isinstance(snap_row, dict) else {}
    ep = None
    try:
        ep = extended_print(row)
    except Exception:                                           # noqa: BLE001
        ep = None
    price = _num(ep.get("price")) if ep else None
    if price is None:
        price = _num(row.get("close"))
    prev_close = _num(row.get("prev_day_close"))
    pm = None
    if ep and ep.get("session") == "premarket" and ep.get("date") == session_iso and prev_close and prev_close > 0:
        pm = (float(ep["price"]) / prev_close - 1) * 100
    op = _num(row.get("open"))
    cfo = (price / op - 1) * 100 if (price is not None and op is not None and op > 0) else None
    capv = _num(cap)
    pending = DA.is_pending(facts)
    f = facts if (isinstance(facts, dict) and not pending) else {}
    out = {"symbol": str(sym).upper(), "price": price, "pm_chg_pct": pm, "chg_pct": _num(row.get("change_pct")),
           "open": op, "chg_from_open_pct": cfo, "cap": capv,
           "cap_text": money(capv) if capv is not None else CAP_UNKNOWN_TEXT,
           "daily_pending": pending, "pending_text": PENDING_TEXT if pending else None}
    for k in DA.FACT_KEYS:
        out[k] = f.get(k)
    out["tier_text"] = TI.tier_text(out.get("tier"))
    out["small_cap_text"] = TI.small_cap_text(capv)
    adr = _num(out.get("adr20_pct"))
    out["adr_text"] = ADR_TEXT.format(adr=adr, pref=LC.LUK_ADR_PREF_PCT) if adr is not None else None
    out["adr_pref_ok"] = (adr > LC.LUK_ADR_PREF_PCT) if adr is not None else None
    return out


def crit(key: str, label: str, ok, value_text, need_text) -> dict:
    return {"key": key, "label": label, "ok": ok, "value_text": value_text, "need_text": need_text}


# ── criteria (one function each — a None fact / a deferred row is judged the same way everywhere) ─────────────
def _daily(row: dict, key: str, label: str, fact: str, threshold, fmt, need: str, *, strict: bool = True) -> dict:
    if row.get("daily_pending"):
        return crit(key, label, None, None, PENDING_TEXT)
    v = _num(row.get(fact))
    t = _num(threshold)
    if v is None or t is None:
        return crit(key, label, False, None, NO_DAILY_TEXT)
    return crit(key, label, (_cmp(v) > t) if strict else (_cmp(v) >= t), fmt(v), need)


def _cap(row: dict) -> dict:
    v = _num(row.get("cap"))
    need = f"> {money(LC.LUK_SCREEN_MIN_CAP_USD)}"
    if v is None:
        return crit("cap", "Market cap", None, None, CAP_UNKNOWN_TEXT)
    return crit("cap", "Market cap", _cmp(v) > LC.LUK_SCREEN_MIN_CAP_USD, money(v), need)


def _avg_vol(row):
    return _daily(row, "avg_vol_10d", "10-day avg volume", "avg_vol_10d", LC.LUK_SCREEN_MIN_AVG_VOL_10D, count,
                  f"> {count(LC.LUK_SCREEN_MIN_AVG_VOL_10D)}")


def _px_vol(row):
    return _daily(row, "px_vol", "Price × volume", "px_vol", LC.LUK_SCREEN_MIN_PX_VOL_USD, money,
                  f"> {money(LC.LUK_SCREEN_MIN_PX_VOL_USD)}")


def _vol_1w(row):
    return _daily(row, "vol_1w_pct", "1-week volatility", "vol_1w_pct", LC.LUK_SCREEN_MIN_VOL_1W_PCT, pct,
                  f"> {LC.LUK_SCREEN_MIN_VOL_1W_PCT:g}%")


def _px_vol_1w(row):
    return _daily(row, "px_vol_1w", "1-week price × volume", "px_vol_1w", LC.LUK_LEADER_MIN_PX_VOL_1W_USD, money,
                  f"> {money(LC.LUK_LEADER_MIN_PX_VOL_1W_USD)}")


def _vs_ema(row, span: int, *, strict: bool) -> dict:
    key, label = f"price_vs_ema{span}", f"Price vs {span} EMA"
    need = f"{'>' if strict else '≥'} {span} EMA"
    if row.get("daily_pending"):
        return crit(key, label, None, None, PENDING_TEXT)
    e, p = _num(row.get(f"ema{span}")), _num(row.get("price"))
    if e is None:
        return crit(key, label, False, None, NO_DAILY_TEXT)
    if p is None:
        return crit(key, label, False, None, need)
    return crit(key, label, (_cmp(p) > _cmp(e)) if strict else (_cmp(p) >= _cmp(e)), f"{p:.2f} vs {e:.2f}", need)


def _chg_from_open(row) -> dict:
    band = LC.LUK_POTENT_CHG_FROM_OPEN_BAND_PCT
    key, label, need = "chg_from_open", "Change from open", f"outside ±{band:g}%"
    op = _num(row.get("open"))
    if op is None or op <= 0:
        return crit(key, label, False, None, NO_OPEN_TEXT)
    v = _num(row.get("chg_from_open_pct"))
    if v is None:
        return crit(key, label, False, None, need)
    return crit(key, label, abs(_cmp(v)) > band, f"{v:+.2f}%", need)


def criteria(key: str, row: dict) -> list:
    """The ordered criteria of screen `key` for one row (his frame's order)."""
    if key == PREMARKET:
        return [_cap(row), _avg_vol(row), _px_vol(row), _vol_1w(row)]
    if key == LEADER:
        return [_cap(row), _avg_vol(row), _px_vol_1w(row)]
    if key == POTENT:
        e_fast, e_slow = LC.LUK_POTENT_EMAS
        return [_vs_ema(row, e_slow, strict=True), _vs_ema(row, e_fast, strict=False), _cap(row), _vol_1w(row),
                _px_vol(row), _chg_from_open(row)]
    raise KeyError(key)


def _screen(key: str, rows: Iterable[dict], *, need_sort_key: bool = False) -> list:
    sk = SORT_KEY[key]
    kept = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        if need_sort_key and _num(r.get(sk)) is None:
            continue
        cs = criteria(key, r)
        if any(c["ok"] is False for c in cs):
            continue
        kept.append(dict(r, criteria=cs))
    kept.sort(key=lambda r: (_num(r.get(sk)) is None, -(_num(r.get(sk)) or 0.0)))   # the served key only; stable
    out = kept[:int(LC.LUK_SCREEN_TOP_N)]
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def premarket(rows) -> list:
    """☀️ — rows without a pre-market print dated today are excluded (`no_premarket_n` counts them)."""
    return _screen(PREMARKET, rows, need_sort_key=True)


def no_premarket_n(rows) -> int:
    return sum(1 for r in rows or [] if isinstance(r, dict) and _num(r.get(SORT_KEY[PREMARKET])) is None)


def leader(rows) -> list:
    return _screen(LEADER, rows)


def potent(rows) -> list:
    return _screen(POTENT, rows)


# ── the shortlist ──────────────────────────────────────────────────────────────────────────────────────────────
def shortlist(screens: dict, carried) -> tuple:
    """(names, capped_n): the union of the three screens' symbols + `carried` (reads still forming / triggered),
    ordered by |chg_pct| desc then symbol (a carried name on no screen today has no change served → read as 0), cut
    to LC.LUK_SHORTLIST_MAX; capped_n = the names cut."""
    chg: dict = {}
    for key in SCREENS:
        for r in (screens or {}).get(key) or []:
            if isinstance(r, dict) and r.get("symbol"):
                s = str(r["symbol"]).upper()
                v = _num(r.get("chg_pct"))
                chg[s] = max(chg.get(s, 0.0), abs(v)) if v is not None else chg.get(s, 0.0)
    for s in carried or ():
        if s:
            chg.setdefault(str(s).upper(), 0.0)
    names = sorted(chg, key=lambda s: (-chg[s], s))
    cap = int(LC.LUK_SHORTLIST_MAX)
    return names[:cap], max(0, len(names) - cap)
