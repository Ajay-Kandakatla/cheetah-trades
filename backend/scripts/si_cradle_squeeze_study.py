"""SI × "previous day had highs" × cradle → second-half squeeze — a read-only, pre-registered study (2026-11-17).

Ajay 2026-11-17 (the ask, verbatim): "Can you do analysis for me if there are cetrain stocks with short interest  on
average of certain percentage.. Previous day had highs..  Then they look like cradle pattern, they grow immensely EOD.
Due to short squeeze..  I think this is a thing with reversal squeeze but they would usualy grow back second half of
the day if they thesis checks out I want you build a new tab but do evaluate this one some previous stocks please"

Design (frozen, sha256 in <out>/design.sha256): eod-audits/research/2026-11-17_si_cradle_squeeze/design.md.
Stages: `fetch` (network: SI history + splits + ONE adjusted minute range per name → the study's own snapshot),
`analyze` (snapshot + Mongo READS only; `intraday_cache` is never read), `render` (results.json → report.md),
`selftest` (the repo test file, in-container). Paper only; nothing here is a gate, a push or a tab.

Every threshold is an existing constant read BY NAME (CONSTANTS) or a quantile of the observed distribution; the only
numeric literals are the analyst choices in ANALYST (design §3.9) + the two house sensitivity costs of sx.py:16, the
float-age description cut the design names (§3.1/§3.4), unit conversions and dp rounding — the test pins the set.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import sys
import time
from bisect import bisect_left
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import reaction as RX  # noqa: E402
from chart_maps import drop10_tab as D10  # noqa: E402
from chart_maps.gajjala import bars as GB  # noqa: E402
from chart_maps.gajjala import constants as GC  # noqa: E402
from chart_maps.gajjala import detectors as DET  # noqa: E402
from chart_maps.gajjala import store as GS  # noqa: E402
from daytrading import data as DT  # noqa: E402
from scripts import resiliency_study as RS  # noqa: E402
from scripts import spy_levels_study_2026_11_05 as SPY  # noqa: E402
from scripts import strategy_lab_2026_10_29 as LAB  # noqa: E402
from sepa import prices as PR  # noqa: E402
from sepa import symbols as SYMS  # noqa: E402
from short_interest import client as SIC  # noqa: E402
from short_interest import read as SR  # noqa: E402

ET = ZoneInfo("America/New_York")
STUDY = "si_cradle_squeeze_2026_11_17"
SCRIPT = "backend/scripts/si_cradle_squeeze_study.py"

# ── design §3.9: the analyst choices (MINE, frozen) — the only numeric literals ──────────────────────────────────────
SEED = 20261117
AS_OF = "2026-11-17"                       # = THESIS_DAY: sanity rows only, never a cell (design C9)
WINDOW_SESSIONS = 120                      # confirmatory window, ending prev_market_day(AS_OF)
NOON_ET = "12:00"                          # his "second half of the day"
LAST_CONFIRM_ET = "15:55"                  # the entry must print inside RTH
FETCH_GAP_SEC = 1.0                        # ≤ 60 Massive requests / minute
FETCH_STOP_ET = "03:30"                    # the fetch pauses itself before the 04:00 pass
SI_LIMIT = 50                              # settlements per name
TERCILES = (1 / 3, 2 / 3)
QUARTILES = (0.25, 0.5, 0.75)
OOS_SPLIT = 60                             # sessions: first 60 = IS (cutpoints), last 60 = OOS (every gate)
COST_RANK = LAB.COST_TIER1_TOP_N + 1       # tier 2 by construction (every universe name is outside the top 1,000)
FRAME_NOW_ET = GC.PASS_CLOSE_ET            # every bar of D closed
SNAPSHOT_BASIS = "massive adjusted=true"
BASES = ("pct_float", "pct_so", "dtc")
NARRATIVE_PRIOR_N = 402
SX_COST = 0.001                            # sx.py:16 COST_BPS — the 11-15/16 "house costs" (sensitivity line only)
SX_SLIP = 0.01                             # sx.py:16 SLIP $/share
FLOAT_AGE_Q = 0.9                          # design §3.4 meta.float_age.p90_d (description)
FLOAT_AGE_DAYS = 60                        # design §3.1 "count > 60 d" (description, no cut — HIS CALL #11)
SANITY = ("AKAN", "GP")
SANITY_EXTRA = (("AKAN", "2026-11-13"), ("AKAN", "2026-11-16"))
DP = 4
EXIT_PIN = 3
MASSIVE_PAGE_BARS = 50000                  # TRANSPORT — daytrading.data._fetch_massive_minute `limit` (data.py:124); pacing only

HS = ("H1", "H2", "H3")
TIERS = tuple(range(1, len(TERCILES) + 2))   # T1..T3
TOP = TIERS[-1]
CRS = ("CRA", "CRB")
ARMS = ("X16", "X20")
SPLITS3 = ("pooled", "is", "oos")
WORD_POS, WORD_NULL, WORD_INV, WORD_SMALL = "POSITIVE", "NULL", "INVERTED", "UNMEASURED-too-small"
PRIMARY = "C01"

ANALYST = {"SEED": SEED, "AS_OF": AS_OF, "WINDOW_SESSIONS": WINDOW_SESSIONS, "NOON_ET": NOON_ET,
           "LAST_CONFIRM_ET": LAST_CONFIRM_ET, "FETCH_GAP_SEC": FETCH_GAP_SEC, "FETCH_STOP_ET": FETCH_STOP_ET,
           "SI_LIMIT": SI_LIMIT, "TERCILES": list(TERCILES), "QUARTILES": list(QUARTILES), "OOS_SPLIT": OOS_SPLIT,
           "COST_RANK": COST_RANK, "FRAME_NOW_ET": FRAME_NOW_ET, "SNAPSHOT_BASIS": SNAPSHOT_BASIS,
           "BASES": list(BASES), "NARRATIVE_PRIOR_N": NARRATIVE_PRIOR_N, "SX_COST": SX_COST, "SX_SLIP": SX_SLIP,
           "FLOAT_AGE_Q": FLOAT_AGE_Q, "FLOAT_AGE_DAYS": FLOAT_AGE_DAYS, "SANITY": list(SANITY)}

# ── design §1.1: every reused constant BY NAME (read at import; the analyze stage compares it with the manifest) ───
CONSTANTS = {
    "K8_MAX_FLOAT": GC.K8_MAX_FLOAT, "K8_DROP_PCT": GC.K8_DROP_PCT, "K8_HISTORY_SESSIONS": GC.K8_HISTORY_SESSIONS,
    "K8_HISTORY_RANGE_PCT": GC.K8_HISTORY_RANGE_PCT, "SCAN_MIN_CHANGE_PCT": GC.SCAN_MIN_CHANGE_PCT,
    "SCAN_MIN_PRICE": GC.SCAN_MIN_PRICE, "SCAN_MAX_PRICE": GC.SCAN_MAX_PRICE, "SCAN_MIN_VOLUME": GC.SCAN_MIN_VOLUME,
    "K4_HF_BASE_MIN": GC.K4_HF_BASE_MIN, "EMA_FAST": GC.EMA_FAST, "EMA_SLOW": GC.EMA_SLOW,
    "LEDGER_MIN_R_PCT": GC.LEDGER_MIN_R_PCT, "LEDGER_FILL_TO_ET": str(GC.LEDGER_FILL_TO_ET),
    "PASS_OPEN_ET": GC.PASS_OPEN_ET, "PASS_CLOSE_ET": GC.PASS_CLOSE_ET,
    "FLOAT_SUSPECT_POLICY": GC.FLOAT_SUSPECT_POLICY,
    "SI_HIGH_PCT": SIC.SI_HIGH_PCT, "SI_ELEV_PCT": SIC.SI_ELEV_PCT,
    "FINRA_PUBLICATION_BDAYS": SR.FINRA_PUBLICATION_BDAYS,
    "SUSPECT_MAX_SHARES_OUT_FRACTION": SR.SUSPECT_MAX_SHARES_OUT_FRACTION,
    "_SCALE_GLITCH_RATIO": PR._SCALE_GLITCH_RATIO,
    "COST_TIER1_TOP_N": LAB.COST_TIER1_TOP_N, "COST_TIER2_BPS": LAB.COST_TIER2_BPS, "SLIPPAGE_BPS": LAB.SLIPPAGE_BPS,
    "BOOT_DRAWS": LAB.BOOT_DRAWS, "PLACEBO_SETS": LAB.PLACEBO_SETS, "PLACEBO_BEAT_SHARE": LAB.PLACEBO_BEAT_SHARE,
    "DSR_PASS": LAB.DSR_PASS, "MIN_BUCKET_N": RS.MIN_BUCKET_N, "CI_PCT": RS.CI_PCT, "DUP_RHO": SPY.DUP_RHO,
}

NS_PER_S = pd.Timedelta(seconds=1).value
NS_PER_MS = pd.Timedelta(milliseconds=1).value
S_PER_MIN = int(pd.Timedelta(minutes=1).total_seconds())


class SnapshotBasisError(RuntimeError):
    """A snapshot file whose `basis` is not SNAPSHOT_BASIS — analyze exits EXIT_PIN."""


class Universe(dict):
    """{SYM: info} + `.excluded` [(sym, reason)]."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.excluded: list = []


# ═════════════════════════════════════════════════════════════════════════════════════════════════ small helpers ═══
def _r(x, dp=DP):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return round(f, dp) if math.isfinite(f) else None


def _num(x) -> Optional[float]:
    if isinstance(x, bool) or x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _iso_date(x) -> Optional[date]:
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    try:
        return date.fromisoformat(str(x).split("T")[0].split(" ")[0])
    except ValueError:
        return None


def _hm(s) -> dtime:
    if isinstance(s, dtime):
        return s
    return datetime.strptime(str(s), "%H:%M").time()


def et_dt(day: date, t) -> datetime:
    return datetime.combine(day, _hm(t), tzinfo=ET)


def et_epoch(day: date, t) -> int:
    return int(et_dt(day, t).timestamp())


def stamp(day, hhmm) -> str:
    d = day.isoformat() if isinstance(day, date) else str(day)
    return f"{d} {hhmm}"


def _sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _median(xs):
    xs = [x for x in xs if x is not None]
    return float(np.median(xs)) if xs else None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return _r(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return o


def dumps(obj) -> str:
    return json.dumps(_jsonable(obj), sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False)


# ═══════════════════════════════════════════════════════════════════════════════════════════════ window / halves ═══
def sessions_window(as_of: date, n: int) -> list:
    """The n market days ending prev_market_day(as_of), oldest first; `as_of` itself is NEVER in it (design C9)."""
    out, d = [], RX.prev_market_day(as_of)
    while len(out) < n:
        out.append(d)
        d = RX.prev_market_day(d)
    return sorted(out)


def date_halves(window) -> tuple:
    w = sorted(window)
    k = len(w) // 2
    return set(w[:k]), set(w[k:])


def symbol_halves(symbols) -> tuple:
    s = sorted(set(symbols))
    return set(s[0::2]), set(s[1::2])


def stride_names(names, stride: int = 1, offset: int = 0) -> list:
    return sorted(names)[int(offset or 0)::max(1, int(stride or 1))]


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════ universe ═══
def board_symbols(db) -> set:
    out = set()
    for coll in (GS.SCAN, GS.LEDGER, GS.POTENTIALS, GS.DAILY):
        try:
            out.update(str(s).upper() for s in db[coll].distinct("symbol") if s)
        except Exception:                                                   # noqa: BLE001
            continue
    return out


def universe(db, shares_docs=None, board=None, as_of: Optional[date] = None) -> Universe:
    """shares_cache names with 0 < float ≤ K8_MAX_FLOAT and a float not above shares out (the engine's own rule)."""
    as_of = as_of or date.fromisoformat(AS_OF)
    docs = shares_docs if shares_docs is not None else list(
        db["shares_cache"].find({}, {"float_shares": 1, "shares_outstanding": 1, "as_of": 1}))
    board = set(board) if board is not None else board_symbols(db)
    U = Universe()
    for doc in sorted(docs, key=lambda d: str(d.get("_id") or "")):
        sym = str(doc.get("_id") or "").strip().upper()
        if not sym:
            continue
        fl, so = _num(doc.get("float_shares")), _num(doc.get("shares_outstanding"))
        so = so if (so is not None and so > 0) else None
        if fl is None:
            reason = "float_none"
        elif fl <= 0:
            reason = "float_nonpositive"
        elif fl > GC.K8_MAX_FLOAT:
            reason = "float_over_cap"
        elif so is not None and SR._float_suspect(0, fl, so) == SR.FLOAT_EXCEEDS_SHARES:
            reason = SR.FLOAT_EXCEEDS_SHARES
        else:
            reason = None
        if reason:
            U.excluded.append((sym, reason, sym in board))
            continue
        a = _num(doc.get("as_of"))
        asof = datetime.fromtimestamp(a, tz=timezone.utc).date() if (a is not None and a > 0) else None
        U[sym] = {"float_shares": fl, "shares_outstanding": so, "as_of": asof.isoformat() if asof else None,
                  "float_age_days": (as_of - asof).days if asof else None, "board": sym in board}
    return U


def float_age_summary(U) -> dict:
    ages = [v.get("float_age_days") for v in U.values() if v.get("float_age_days") is not None]
    if not ages:
        return {"median_d": None, "p90_d": None, "max_d": None, "n_over_60d": 0, "n_unknown": len(U)}
    a = np.asarray(ages, dtype=float)
    return {"median_d": float(np.median(a)), "p90_d": float(np.quantile(a, FLOAT_AGE_Q)), "max_d": float(a.max()),
            "n_over_60d": int((a > FLOAT_AGE_DAYS).sum()), "n_unknown": len(U) - len(ages)}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════ fetching ═══
def fetch_si_history(sym: str, limit: int = SI_LIMIT) -> list:
    rows = SIC._fetch_short_interest_rows(SYMS.for_massive(sym), limit=limit) or []
    keep = ("settlement_date", "short_interest", "avg_daily_volume", "days_to_cover")
    return [{k: r.get(k) for k in keep} for r in rows if isinstance(r, dict)]


def fetch_splits(sym: str, since_iso: str):
    """The split list, or None when Massive failed (counted, never read as "no split")."""
    try:
        return D10.fetch_splits_strict(sym, since_iso)
    except Exception:                                                       # noqa: BLE001
        return None


def fetch_minutes(sym: str, from_day: date, to_day: date):
    return DT._fetch_massive_minute(SYMS.for_massive(sym), from_day, to_day)


def split_days(df) -> dict:
    """{ET session date: that day's 1-min bars} (naive-UTC index kept)."""
    if df is None or len(df) == 0:
        return {}
    et_days = df.index.tz_localize("UTC").tz_convert(ET).date
    return {d: sub for d, sub in df.groupby(et_days, sort=True)}


_SNAP_COLS = ("open", "high", "low", "close", "volume", "vwap_bar", "trade_count")


def _col(series) -> list:
    out = []
    for x in series.tolist():
        f = _num(x)
        out.append(f)
    return out


def snapshot_bytes(sym: str, by_day: dict, fetched_at_et: Optional[str] = None) -> bytes:
    days = {}
    for d in sorted(by_day):
        df = by_day[d]
        rec = {"t": [int(x) for x in (df.index.asi8 // NS_PER_MS)]}
        for c in _SNAP_COLS:
            if c in df.columns:
                rec[c] = _col(df[c])
        rec["session"] = [str(s) for s in (df["session"].tolist() if "session" in df.columns
                                           else [DT._classify_session(ts) for ts in df.index])]
        days[d.isoformat() if isinstance(d, date) else str(d)] = rec
    doc = {"symbol": sym, "basis": SNAPSHOT_BASIS, "fetched_at_et": fetched_at_et, "days": days}
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(raw)
    return buf.getvalue()


def snapshot_write(path, sym: str, by_day: dict, fetched_at_et: Optional[str] = None) -> dict:
    b = snapshot_bytes(sym, by_day, fetched_at_et)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_bytes(b)
    tmp.replace(p)
    return {"bytes_gz": len(b), "days": len(by_day), "bars": int(sum(len(v) for v in by_day.values()))}


def snapshot_load(path) -> dict:
    with gzip.open(path, "rb") as f:
        doc = json.loads(f.read().decode("utf-8"))
    if doc.get("basis") != SNAPSHOT_BASIS:
        raise SnapshotBasisError(f"{path}: basis {doc.get('basis')!r} != {SNAPSHOT_BASIS!r}")
    return doc


_BASIS_HEAD = '{"basis":'


def snapshot_basis(path) -> Optional[str]:
    """The `basis` field read from the head of the gzip stream (sort_keys puts it first) — no full parse."""
    with gzip.open(path, "rb") as f:
        head = f.read(len(_BASIS_HEAD) + len(json.dumps(SNAPSHOT_BASIS))).decode("utf-8", "replace")
    if not head.startswith(_BASIS_HEAD):
        return None
    try:
        return json.loads(head[len(_BASIS_HEAD):])
    except ValueError:
        return None


def snapshot_read(path, sym: Optional[str] = None, meta_out: Optional[dict] = None) -> dict:
    """{date: DataFrame} on a naive-UTC index with the loader's columns + `session`; `meta_out` (optional) receives the
    snapshot's `fetched_at_et`."""
    doc = snapshot_load(path)
    if meta_out is not None:
        meta_out["fetched_at_et"] = doc.get("fetched_at_et")
    if sym is not None and str(doc.get("symbol")).upper() != str(sym).upper():
        raise SnapshotBasisError(f"{path}: symbol {doc.get('symbol')!r} != {sym!r}")
    out = {}
    for d, rec in sorted((doc.get("days") or {}).items()):
        idx = pd.to_datetime(np.asarray(rec["t"], dtype="int64") * NS_PER_MS)
        idx.name = "ts_utc"
        cols = {c: np.asarray([np.nan if x is None else x for x in rec[c]], dtype=float)
                for c in _SNAP_COLS if c in rec}
        df = pd.DataFrame(cols, index=idx)
        df["session"] = rec.get("session") or [DT._classify_session(ts) for ts in idx]
        out[date.fromisoformat(d)] = df
    return out


def _cache_doc_bars(df) -> list:
    """The bar records exactly as daytrading.data._mongo_put_day builds them (reset_index, ISO ts_utc)."""
    bars = df.reset_index().to_dict(orient="records")
    for b in bars:
        if "ts_utc" in b:
            b["ts_utc"] = b["ts_utc"].isoformat() if hasattr(b["ts_utc"], "isoformat") else str(b["ts_utc"])
        for k, v in list(b.items()):
            if isinstance(v, float) and not math.isfinite(v):
                b[k] = None
    return bars


def cache_side_write(sym: str, by_day: dict, today_et: date, coll=None) -> tuple:
    """Add COMPLETED days (< today_et) that have NO intraday_cache doc, in the loader's doc shape, keyed by the Massive
    spelling (the loader is asked `for_massive(sym)`). `$setOnInsert` + upsert: an existing doc — the pre-split ones
    included — is never touched, even in a race with the live pass. Returns (written, skipped_existing, skipped_today)."""
    if coll is None:
        coll = DT._get_mongo_coll()
    if coll is None:
        return 0, 0, 0
    key = SYMS.for_massive(sym).upper()
    w = se = st = 0
    for day in sorted(by_day):
        if day >= today_et:
            st += 1
            continue
        if coll.find_one({"symbol": key, "date": str(day)}, {"_id": 1}) is not None:
            se += 1
            continue
        res = coll.update_one({"symbol": key, "date": str(day)},
                              {"$setOnInsert": {"symbol": key, "date": str(day), "bars": _cache_doc_bars(by_day[day]),
                                                "cached_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
                              upsert=True)
        if getattr(res, "upserted_id", None) is not None:
            w += 1
        else:
            se += 1
    return w, se, st


class Pacer:
    """At least `gap_sec` between consecutive requests (≤ 60/min at 1.0 s)."""

    def __init__(self, gap_sec: float = FETCH_GAP_SEC, clock: Callable = time.monotonic, sleep: Callable = time.sleep):
        self.gap, self.clock, self.sleep, self.last = float(gap_sec), clock, sleep, None

    def wait(self):
        now = self.clock()
        if self.last is not None:
            due = self.last + self.gap
            if now < due:
                self.sleep(due - now)
                now = due
        self.last = now


def fetch_stop_due(now_et: datetime, stop_hhmm: str = FETCH_STOP_ET) -> bool:
    """True from FETCH_STOP_ET until the after-hours close (20:00 ET): the fetch runs only 20:00 → FETCH_STOP_ET, so it
    never overlaps RTH or the 04:00 pass."""
    t = now_et.astimezone(ET).time() if now_et.tzinfo else now_et.time()
    return _hm(stop_hhmm) <= t < DT.ET_AFTERHOURS_CLOSE


# ═════════════════════════════════════════════════════════════════════════════════════════════ leg (1): SI, PIT ═══
def pit_settlement(rows, D: date) -> Optional[dict]:
    """The latest settlement whose FINRA publication date is STRICTLY before D (+ the row before it)."""
    dated = []
    for r in rows or []:
        s = _iso_date((r or {}).get("settlement_date"))
        if s is not None:
            dated.append((s, r))
    dated.sort(key=lambda x: x[0])
    usable = [(s, r) for s, r in dated if SR.publication_date(s) < D]
    if not usable:
        return None
    s, r = usable[-1]
    prev = [(ps, pr) for ps, pr in dated if ps < s]
    prev_si = _num(prev[-1][1].get("short_interest")) if prev else None
    si = _num(r.get("short_interest"))
    if si is None:
        return None
    return {"settlement": s.isoformat(), "published_on": SR.publication_date(s).isoformat(), "short_interest": si,
            "days_to_cover": _num(r.get("days_to_cover")), "avg_daily_volume": _num(r.get("avg_daily_volume")),
            "prev_short_interest": prev_si,
            "si_change_pct": ((si - prev_si) / prev_si * 100) if (prev_si is not None and prev_si > 0) else None}


def split_factor(splits, settlement, as_of) -> float:
    """Π split_to/split_from over splits executed AFTER the settlement and on/before as_of (today's share basis)."""
    s, a = _iso_date(settlement), _iso_date(as_of)
    f = 1.0
    for x in splits or []:
        ex = _iso_date(x.get("execution_date"))
        fr, to = _num(x.get("split_from")), _num(x.get("split_to"))
        if ex is None or not fr or not to:
            continue
        if s < ex <= a:
            f *= to / fr
    return f


def age_sessions(published_on, D: date) -> Optional[int]:
    """Market days from the publication day to D (design §3.1): the count of sessions in (published_on, D]."""
    p = _iso_date(published_on)
    if p is None or p >= D:
        return None
    n, d = 0, D
    while d > p:
        d = RX.prev_market_day(d)
        n += 1
    return n


def mdv20_before(daily: list, D: date) -> Optional[float]:
    """The 20-day median $ volume known before D (design §3.2): `LAB.own_bar_rolling` median of close × volume over
    the last `LAB.CAP_MDV_BARS` own daily bars dated before D (None with fewer bars) — the lab's cap engine, reused."""
    k = bisect_left([b["date"] for b in daily], D)
    if k < LAB.CAP_MDV_BARS:
        return None
    win = daily[:k]
    vol = np.asarray([np.nan if b.get("volume") is None else b["volume"] for b in win], dtype=float)
    close = np.asarray([b["close"] for b in win], dtype=float)
    own = np.isfinite(close) & np.isfinite(vol)
    dv = np.where(own, close * np.where(own, vol, 0.0), np.nan)
    v = LAB.own_bar_rolling(dv[None, :], own[None, :], LAB.CAP_MDV_BARS, "median")[0, -1]
    return float(v) if np.isfinite(v) else None


def si_features(pit: Optional[dict], factor: Optional[float], float_now, so_now) -> Optional[dict]:
    if pit is None or factor is None:
        return None
    si = pit["short_interest"] * factor
    fl = _num(float_now)
    so = _num(so_now)
    fl = fl if (fl is not None and fl > 0) else None
    so = so if (so is not None and so > 0) else None
    reason = SR._float_suspect(si, fl, so)
    pct_float = si / fl * 100 if fl else None
    if reason is not None:
        pct_float = None
    pct_so = si / so * 100 if so else None
    dtc = pit.get("days_to_cover")
    dtc = dtc if (dtc is not None and dtc >= 0) else None
    return {"settlement": pit["settlement"], "published_on": pit["published_on"], "si_shares": pit["short_interest"],
            "split_factor": factor, "si_shares_adj": si, "pct_float": pct_float, "pct_so": pct_so, "dtc": dtc,
            "float_suspect": reason, "pct_float_over_100": bool(pct_float is not None and pct_float > 100),
            "si_change_pct": pit.get("si_change_pct")}


# ═══════════════════════════════════════════════════════════════════════════════════ leg (2): D-1 had highs ═══
def daily_frame(db_or_frames, sym: str) -> list:
    """[{date, open, high, low, close, volume}] oldest first from the price_cache frame (today's basis)."""
    df = db_or_frames.get(sym) if isinstance(db_or_frames, dict) else PR.bulk_cached_frames([sym]).get(sym)
    if df is None or len(df) == 0:
        return []
    out = []
    for ts, row in df.iterrows():
        out.append({"date": pd.Timestamp(ts).date(), "open": float(row["open"]), "high": float(row["high"]),
                    "low": float(row["low"]), "close": float(row["close"]), "volume": _num(row.get("volume"))})
    out.sort(key=lambda b: b["date"])
    return out


def _daily_at(daily, day) -> Optional[int]:
    dates = [b["date"] for b in daily]
    i = bisect_left(dates, day)
    return i if (i < len(dates) and dates[i] == day) else None


def d1_highs(daily: list, D: date, splits) -> dict:
    K = GC.K8_HISTORY_SESSIONS
    D1 = RX.prev_market_day(D)
    out = {"H1": None, "H2": None, "H3": None, "split_in_lookback": None, "reason": None, "d1": D1.isoformat(),
           "d1_open": None, "d1_high": None, "d1_low": None, "d1_close": None, "d2_close": None,
           "d1_range_pct": None, "d1_close_pos": None, "prior_max_high": None}
    i = _daily_at(daily, D1)
    if i is None:
        out["reason"] = "no_d1_bar"
        return out
    b = daily[i]
    out.update(d1_open=b["open"], d1_high=b["high"], d1_low=b["low"], d1_close=b["close"])
    if b["low"] > 0:
        out["d1_range_pct"] = (b["high"] - b["low"]) / b["low"] * 100
    if b["high"] > b["low"]:
        out["d1_close_pos"] = (b["close"] - b["low"]) / (b["high"] - b["low"])
    if splits is None:
        out["reason"] = "splits_unknown"
        return out
    first = daily[max(0, i - K)]["date"]
    sil = any(first < ex <= D1 for ex in (_iso_date(x.get("execution_date")) for x in splits) if ex is not None)
    out["split_in_lookback"] = bool(sil)
    if sil:
        out["reason"] = "split_in_lookback"
        return out
    if i >= K:
        pm = max(x["high"] for x in daily[i - K:i])
        out["prior_max_high"] = pm
        out["H1"] = bool(b["high"] > pm)
    else:
        out["reason"] = "no_daily_lookback"
    if i >= 1:
        out["d2_close"] = daily[i - 1]["close"]
        out["H2"] = bool(b["high"] >= daily[i - 1]["close"] * (1 + GC.SCAN_MIN_CHANGE_PCT / 100))
    if b["low"] > 0:
        out["H3"] = bool((b["high"] - b["low"]) / b["low"] >= GC.K8_HISTORY_RANGE_PCT / 100)
    return out


def seam_check(raw_prev, raw_day, daily_close_d1) -> Optional[str]:
    """The ONE basis-mismatch engine (prices._is_scale_glitch) on the two seams of a unit (design C1)."""
    if raw_prev is None or len(raw_prev) == 0:
        return None
    if daily_close_d1 is not None and "session" in raw_prev.columns:
        rth = raw_prev[raw_prev["session"] == "rth"]
        if len(rth) and PR._is_scale_glitch(float(rth["close"].iloc[-1]), float(daily_close_d1)):
            return "basis_mismatch_daily"
    if raw_day is not None and len(raw_day):
        if PR._is_scale_glitch(float(raw_day["open"].iloc[0]), float(raw_prev["close"].iloc[-1])):
            return "basis_mismatch_intraday"
    return None


def split_at_unit(splits, D: date) -> bool:
    D1 = RX.prev_market_day(D)
    return any(_iso_date(x.get("execution_date")) in (D1, D) for x in (splits or []))


# ══════════════════════════════════════════════════════════════════════════════════════════ leg (3): the cradle ═══
def frame_for(sym: str, D: date, raw_prev, raw_day):
    fs = GB.build_frames(sym, D, et_dt(D, FRAME_NOW_ET), raw_prev, raw_day)
    return fs.f5 if fs is not None else None


def vol_so_far(F, j: int) -> float:
    return float(sum(F.v[i] for i in F.today if i <= j))


def _session_iso(F) -> Optional[str]:
    return F.t[F.today.start].split(" ")[0] if len(F.today) else None


def noon_index(F, D=None) -> Optional[int]:
    d = D.isoformat() if isinstance(D, date) else _session_iso(F)
    if d is None:
        return None
    cut = stamp(d, NOON_ET)
    js = [i for i in F.today if F.t[i] <= cut]
    return js[-1] if js else None


def floors_ok(F, j: int) -> bool:
    return bool(GC.SCAN_MIN_PRICE <= F.c[j] <= GC.SCAN_MAX_PRICE and vol_so_far(F, j) >= GC.SCAN_MIN_VOLUME)


def _rth_today(F) -> list:
    return [i for i in F.today if F.session[i] == "rth"]


def _ref(F, d1_close) -> Optional[float]:
    rth = _rth_today(F)
    if not rth or d1_close is None:
        return None
    return max(float(F.o[rth[0]]), float(d1_close))


def _lo_idx(F, j: int) -> Optional[int]:
    lo = None
    for i in F.today:
        if i > j:
            break
        if F.session[i] != "rth":
            continue
        if lo is None or F.l[i] < F.l[lo]:
            lo = i
    return lo


def selloff_at_noon(F, j_noon, d1_close) -> bool:
    """S ∧ floors at the noon bar — knowable at noon (design C5)."""
    if j_noon is None or d1_close is None:
        return False
    lo = _lo_idx(F, j_noon)
    ref = _ref(F, d1_close)
    if lo is None or ref is None:
        return False
    return bool(F.l[lo] <= ref * (1 - GC.K8_DROP_PCT / 100) and floors_ok(F, j_noon))


def _reclaim(F, i: int, variant: str) -> bool:
    e9, e21, c = F.ema9[i], F.ema21[i], F.c[i]
    if variant == "CRA":
        return bool(e9 is not None and e21 is not None and c > e9 and c > e21 and e9 > e21)
    if variant == "CRB":
        return bool(e9 is not None and c > e9)
    raise ValueError(f"unknown cradle variant {variant}")


def cradle(F, variant: str, d1_close) -> Optional[dict]:
    """The FIRST afternoon closed 5-min bar j (12:00 < t ≤ LAST_CONFIRM_ET) with S (RTH low printed ≤ 12:00 and
    ≥ K8_DROP_PCT under max(RTH open, D-1 close)) ∧ B (≥ K4_HF_BASE_MIN bars since that low, no undercut) ∧ R (the
    9/21 reclaim) ∧ the floors (price band, today's volume through j ≥ SCAN_MIN_VOLUME)."""
    if variant not in CRS:
        raise ValueError(f"unknown cradle variant {variant}")
    d = _session_iso(F)
    ref = _ref(F, d1_close)
    if d is None or ref is None:
        return None
    noon, last = stamp(d, NOON_ET), stamp(d, LAST_CONFIRM_ET)
    thr = ref * (1 - GC.K8_DROP_PCT / 100)
    lo, vol = None, 0.0
    for i in F.today:
        vol += float(F.v[i])
        if F.session[i] != "rth":
            continue
        if lo is None or F.l[i] < F.l[lo]:
            lo = i
        if not (noon < F.t[i] <= last):
            continue
        S = F.t[lo] <= noon and F.l[lo] <= thr
        B = i - lo >= GC.K4_HF_BASE_MIN
        if not (S and B):
            continue
        if not _reclaim(F, i, variant):
            continue
        if not (GC.SCAN_MIN_PRICE <= F.c[i] <= GC.SCAN_MAX_PRICE and vol >= GC.SCAN_MIN_VOLUME):
            continue
        t_lo, t_j = datetime.strptime(F.t[lo], "%Y-%m-%d %H:%M"), datetime.strptime(F.t[i], "%Y-%m-%d %H:%M")
        return {"j": i, "t": F.t[i], "clock": F.t[i].split(" ")[1], "cradle_low": float(F.l[lo]), "lo_t": F.t[lo],
                "ref": ref, "drop_pct": (ref - F.l[lo]) / ref * 100, "base_bars": i - lo,
                "base_minutes": int((t_j - t_lo).total_seconds() // S_PER_MIN),
                "ema_gap_pct": ((F.ema9[i] - F.ema21[i]) / F.c[i] * 100) if (F.ema9[i] is not None and
                                                                           F.ema21[i] is not None) else None,
                "vol_so_far": vol, "close": float(F.c[i]), "cradle_high": float(max(F.h[lo:i + 1]))}
    return None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════ outcomes ═══
def minute_series(raw_day, from_u: Optional[int] = None) -> dict:
    df = raw_day.sort_index()
    u1 = df.index.asi8 // NS_PER_S
    keep = slice(None) if from_u is None else slice(int(np.searchsorted(u1, from_u, "left")), None)
    return {"u1": np.asarray(u1[keep], dtype="int64"), "o": df["open"].to_numpy(float)[keep],
            "h": df["high"].to_numpy(float)[keep], "l": df["low"].to_numpy(float)[keep],
            "c": df["close"].to_numpy(float)[keep]}


def _horizons(D: date) -> dict:
    return {"X16": et_epoch(D, RX.rth_close_time(D)), "X20": et_epoch(D, DT.ET_AFTERHOURS_CLOSE)}


def cost_side() -> float:
    return LAB.cost_side(COST_RANK)


def _net(gross_pct, e, cs) -> tuple:
    return gross_pct - 2 * cs * 100, gross_pct - SX_COST * 100 - 2 * SX_SLIP / e * 100


def trade(ser: dict, e_u: int, stop: float, D: date, cs: float) -> dict:
    """Entry = the first 1-min open at/after e_u (inside RTH), stop at `stop` (first touch on 1-min bars; gap-honest
    fill min(stop, open); the fill minute itself books at the stop), X16 = the last RTH 1-min close, X20 = the last
    close before 20:00 (a ceiling: thin tape)."""
    u1, o, h, l, c = ser["u1"], ser["o"], ser["h"], ser["l"], ser["c"]
    hz = _horizons(D)
    k0 = int(np.searchsorted(u1, e_u, "left"))
    if k0 >= len(u1) or u1[k0] >= hz["X16"]:
        return {"no_fill": True}
    e = float(o[k0])
    stop_pct = (e - stop) / e * 100 if e > 0 else None
    out = {"no_fill": False, "e": e, "stop": float(stop), "entry_u": int(u1[k0]),
           "entry_lag_min": (int(u1[k0]) - int(e_u)) / S_PER_MIN, "stop_pct": stop_pct}
    if stop_pct is None or stop_pct <= 0:
        out["no_plan"] = True
        return out
    out["no_plan"] = False
    out["thin"] = bool(stop_pct < GC.LEDGER_MIN_R_PCT)
    for arm in ARMS:
        k1 = int(np.searchsorted(u1, hz[arm], "left"))
        hits = np.nonzero(l[k0:k1] <= stop)[0]
        if hits.size:
            ks = k0 + int(hits[0])
            px = float(stop) if ks == k0 else float(min(stop, o[ks]))
            stopped, ex_u, seg = True, int(u1[ks]), slice(k0, ks)
        else:
            ks = k1 - 1
            px, stopped, ex_u, seg = float(c[ks]), False, int(u1[ks]), slice(k0, k1)
        gross = (px / e - 1) * 100
        net, net_sx = _net(gross, e, cs)
        hh = h[seg]
        ll = l[k0:ks + 1]
        mfe = max(0.0, (float(hh.max()) / e - 1) * 100) if hh.size else 0.0
        heat = max(0.0, (e - float(ll.min())) / e * 100) if ll.size else 0.0
        out[arm] = {"gross_pct": gross, "net_pct": net, "net_pct_sx": net_sx, "R": net / stop_pct,
                    "stopped": stopped, "exit_t": datetime.fromtimestamp(ex_u, ET).strftime("%H:%M"),
                    "mfe_pct": mfe, "mfe_R": mfe / stop_pct, "heat_R": heat / stop_pct,
                    "time_to_stop_min": ((ex_u - int(u1[k0])) / S_PER_MIN) if stopped else None}
    return out


def noon_trade(ser: dict, F, j_noon, D: date, cs: Optional[float] = None) -> Optional[dict]:
    """The simpler question: enter at the first 1-min open at/after 12:00 ET, no stop, X16 / X20. None when the noon
    bar fails the floors (design C10) or nothing prints."""
    cs = cost_side() if cs is None else cs
    if j_noon is None or not floors_ok(F, j_noon):
        return None
    hz = _horizons(D)
    u1 = ser["u1"]
    k0 = int(np.searchsorted(u1, et_epoch(D, NOON_ET), "left"))
    if k0 >= len(u1) or u1[k0] >= hz["X16"]:
        return None
    e = float(ser["o"][k0])
    out = {"e12": e, "entry_t": datetime.fromtimestamp(int(u1[k0]), ET).strftime("%H:%M")}
    for arm in ARMS:
        k1 = int(np.searchsorted(u1, hz[arm], "left"))
        px = float(ser["c"][k1 - 1])
        gross = (px / e - 1) * 100
        net, net_sx = _net(gross, e, cs)
        out[arm] = {"gross_pct": gross, "net_pct": net, "net_pct_sx": net_sx}
    return out


def price_at(ser: dict, D: date, hhmm: str) -> Optional[float]:
    """The last 1-min close of bars starting before hhmm ET."""
    k = int(np.searchsorted(ser["u1"], et_epoch(D, hhmm), "left"))
    return float(ser["c"][k - 1]) if k > 0 else None


# ══════════════════════════════════════════════════════════════════════════════════════════════ the 🎾 overlap ═══
def rs_replay(F, float_read) -> dict:
    """The house 🎾 detector re-run bar by bar on the study's frame + K11 on today's volume through the bar. Labelled
    "replay, not the pass"."""
    out = {"first_armed_t": None, "armed_trigger": None, "armed_stop": None,
           "first_aplus_t": None, "aplus_trigger": None, "aplus_stop": None}
    vol = 0.0
    for j in F.today:
        vol += float(F.v[j])
        r = DET.reversal_squeeze(F, F.minutes, float_read, last=j)
        r = DET.k11_gate(r, vol)
        st = r.get("state")
        if out["first_armed_t"] is None and st == "forming" and r.get("ready"):
            out.update(first_armed_t=F.t[j], armed_trigger=r.get("trigger"), armed_stop=r.get("stop"))
        if out["first_aplus_t"] is None and st == "aplus":
            out.update(first_aplus_t=F.t[j], aplus_trigger=r.get("trigger"), aplus_stop=r.get("stop"))
        if out["first_armed_t"] and out["first_aplus_t"]:
            break
    return out


def float_read_of(info: dict, si: Optional[dict]) -> dict:
    fl = info.get("float_shares")
    sus = SR._float_suspect(si["si_shares_adj"] if si else 0, fl, info.get("shares_outstanding"))
    return {"shares": fl, "text": f"Float {fl:,.0f}" if fl else "Float", "suspect": sus or None}


def load_stores(db) -> dict:
    pots, led, scan = {}, {}, set()
    for d in db[GS.POTENTIALS].find({"setup": "reversal_squeeze"},
                                    {"date": 1, "symbol": 1, "first_seen_et": 1, "first_kind": 1, "first_trigger": 1,
                                     "first_stop": 1, "first_bar_t": 1, "push.state": 1}):
        pots[(str(d.get("date")), str(d.get("symbol")).upper())] = d
    for d in db[GS.LEDGER].find({"setup": "reversal_squeeze"}, {"date": 1, "symbol": 1, "kind": 1, "same": 1}):
        led.setdefault((str(d.get("date")), str(d.get("symbol")).upper()), []).append(d)
    for d in db[GS.SCAN].find({}, {"date": 1, "symbol": 1}):
        scan.add((str(d.get("date")), str(d.get("symbol")).upper()))
    return {"potentials": pots, "ledger": led, "scan": scan,
            "potentials_from": min((k[0] for k in pots), default=None),
            "ledger_from": min((k[0] for k in led), default=None),
            "scan_from": min((k[0] for k in scan), default=None)}


def board_overlap(stores: dict, sym: str, D) -> dict:
    d = D.isoformat() if isinstance(D, date) else str(D)
    pf = stores.get("potentials_from")
    lf = stores.get("ledger_from")
    running = bool(pf and d >= pf) or bool(lf and d >= lf)
    p = (stores.get("potentials") or {}).get((d, sym))
    ls = (stores.get("ledger") or {}).get((d, sym)) or []
    ap = [x for x in ls if x.get("kind") == "aplus"]
    lr = ap[0] if ap else (ls[0] if ls else None)
    same = (lr or {}).get("same") or {}
    return {"board_running": running, "rs_potential": p is not None,
            "first_seen_et": (p or {}).get("first_seen_et"), "first_bar_t": (p or {}).get("first_bar_t"),
            "first_kind": (p or {}).get("first_kind"), "first_trigger": (p or {}).get("first_trigger"),
            "first_stop": (p or {}).get("first_stop"), "push_state": ((p or {}).get("push") or {}).get("state"),
            "ledger_kind": (lr or {}).get("kind"), "aplus_same_day": bool(ap), "same_outcome": same.get("outcome"),
            "same_fill_t": same.get("fill_t"), "in_scan": (d, sym) in (stores.get("scan") or set())}


# ══════════════════════════════════════════════════════════════════════════════════════════ one symbol-day unit ═══
def evaluate_unit(sym, D, raw_prev, raw_day, daily, si_rows, splits, info, cs, stores=None, *, as_of=None,
                  force_replay=False) -> tuple:
    """(unit row, internals {F, ser}) for (sym, D). The row carries every feature, outcome and exclusion reason."""
    as_of = as_of or date.fromisoformat(AS_OF)
    u = {"symbol": sym, "date": D.isoformat(), "out": None}
    if raw_day is None or len(raw_day) == 0:
        u["out"] = "no_bars"
        return u, None
    d1i = _daily_at(daily, RX.prev_market_day(D))
    d1_close = daily[d1i]["close"] if d1i is not None else None
    seam = seam_check(raw_prev, raw_day, d1_close)
    if seam:
        u["out"] = seam
        return u, None
    if split_at_unit(splits, D):
        u["out"] = "split_at_unit"
        return u, None
    if d1_close is None:
        u["out"] = "no_d1_bar"
        return u, None
    F = frame_for(sym, D, raw_prev, raw_day)
    if F is None or not _rth_today(F):
        u["out"] = "no_frame"
        return u, None
    pit = pit_settlement(si_rows, D)
    factor = split_factor(splits, pit["settlement"], as_of) if (pit and splits is not None) else None
    si = si_features(pit, factor, info.get("float_shares"), info.get("shares_outstanding"))
    if si:
        si["age_sessions"] = age_sessions(si["published_on"], D)
    u["si"] = si
    u["si_reason"] = None if si else ("no_pit_row" if pit is None else "splits_unknown")
    h = d1_highs(daily, D, splits)
    u["h"] = h
    j_noon = noon_index(F, D)
    u["selloff_at_noon"] = selloff_at_noon(F, j_noon, d1_close)
    u["noon_floor_ok"] = bool(j_noon is not None and floors_ok(F, j_noon))
    ser = minute_series(raw_day)
    u["cradle"], u["trade"] = {}, {}
    for v in CRS:
        cr = cradle(F, v, d1_close)
        u["cradle"][v] = cr
        if cr is not None:
            e_u = et_epoch(D, cr["clock"])
            u["trade"][v] = trade(ser, e_u, cr["cradle_low"], D, cs)
        else:
            u["trade"][v] = None
    u["noon"] = noon_trade(ser, F, j_noon, D, cs) if si else None
    rth = _rth_today(F)
    u["day"] = {"open": float(F.o[rth[0]]), "low": float(min(F.l[i] for i in rth)),
                "open_to_low_pct": (min(F.l[i] for i in rth) / F.o[rth[0]] - 1) * 100,
                "d1close_to_low_pct": (min(F.l[i] for i in rth) / d1_close - 1) * 100,
                "c16": price_at(ser, D, RX.rth_close_time(D).strftime("%H:%M")),
                "c20": price_at(ser, D, DT.ET_AFTERHOURS_CLOSE.strftime("%H:%M"))}
    if u["day"]["c16"] and u["day"]["c20"]:
        u["day"]["ah_pct"] = (u["day"]["c20"] / u["day"]["c16"] - 1) * 100
    u["day"]["mdv20_usd"] = mdv20_before(daily, D)
    any_h = any(h.get(k) is True for k in HS)
    u["replayed"] = False
    if (si and any_h) or force_replay:
        u["replay"] = rs_replay(F, float_read_of(info, si))
        u["replayed"] = True
        if stores is not None:
            u["board"] = board_overlap(stores, sym, D)
    for v in CRS:
        t = u["trade"][v]
        cr = u["cradle"][v]
        if t and not t.get("no_fill") and not t.get("no_plan") and cr:
            t["above_entry_14"] = (price_at(ser, D, "14:00") or 0) > t["e"] if cr["clock"] < "14:00" else None
            t["above_entry_16"] = (u["day"]["c16"] or 0) > t["e"]
    return u, {"F": F, "ser": ser}


# ═══════════════════════════════════════════════════════════════════════════════════════════════ statistics ═══
def cutpoints(values, qs) -> Optional[list]:
    v = [float(x) for x in values if _num(x) is not None]
    if not v:
        return None
    return [float(q) for q in np.quantile(np.asarray(v, dtype=float), list(qs))]


def bucket(v, cuts) -> Optional[int]:
    if v is None or cuts is None or _num(v) is None:
        return None
    return 1 + sum(1 for c in cuts if v > c)


def _clusters(units):
    keys = sorted({k for k, _ in units})
    pos = {k: i for i, k in enumerate(keys)}
    num, w = np.zeros(len(keys)), np.zeros(len(keys))
    for k, v in units:
        num[pos[k]] += v
        w[pos[k]] += 1
    return keys, pos, num, w


def boot_mean(units, draws: int = None, seed: int = SEED) -> dict:
    """units = [(cluster, value)] → mean + percentile CI resampling WHOLE clusters (RS.boot_draws)."""
    draws = LAB.BOOT_DRAWS if draws is None else draws
    units = [(k, float(v)) for k, v in units if _num(v) is not None]
    if not units:
        return {"mean": None, "lo": None, "hi": None, "n": 0, "n_clusters": 0}
    keys, _, num, w = _clusters(units)
    d = RS.boot_draws([(num, w)], draws, seed)[0]
    ci = RS.ci_of(d, dp=DP) or [None, None]
    return {"mean": float(np.mean([v for _, v in units])), "lo": ci[0], "hi": ci[1], "n": len(units),
            "n_clusters": len(keys)}


def boot_diff(a, b, draws: int = None, seed: int = SEED) -> dict:
    """mean(a) − mean(b) with ONE shared index matrix over the union of clusters (same resampled dates)."""
    draws = LAB.BOOT_DRAWS if draws is None else draws
    a = [(k, float(v)) for k, v in a if _num(v) is not None]
    b = [(k, float(v)) for k, v in b if _num(v) is not None]
    if not a or not b:
        return {"mean": None, "lo": None, "hi": None, "n_a": len(a), "n_b": len(b), "n_clusters": 0}
    keys = sorted({k for k, _ in a} | {k for k, _ in b})
    pos = {k: i for i, k in enumerate(keys)}
    n = len(keys)
    na, wa, nb, wb = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    for k, v in a:
        na[pos[k]] += v
        wa[pos[k]] += 1
    for k, v in b:
        nb[pos[k]] += v
        wb[pos[k]] += 1
    da, db_ = RS.boot_draws([(na, wa), (nb, wb)], draws, seed)
    ci = RS.ci_of(da - db_, dp=DP) or [None, None]
    return {"mean": float(np.mean([v for _, v in a]) - np.mean([v for _, v in b])), "lo": ci[0], "hi": ci[1],
            "n_a": len(a), "n_b": len(b), "n_clusters": len(keys)}


def _envelope(blk) -> tuple:
    los = [x for x in (blk.get("lo"), blk.get("lo_sym")) if x is not None]
    his = [x for x in (blk.get("hi"), blk.get("hi_sym")) if x is not None]
    if len(los) < 2 or len(his) < 2:
        return None, None
    return min(los), max(his)


def arm_block(recs, arm: str, draws=None, seed=SEED) -> dict:
    rs = [r for r in recs if r.get(arm)]
    if not rs:
        return {"n": 0, "n_dates": 0, "n_symbols": 0,
                "net_pct": {"mean": None, "lo": None, "hi": None, "lo_sym": None, "hi_sym": None},
                "R": {"mean": None, "median": None}, "stop_rate": None, "win_rate": None, "mfe_R_median": None,
                "gross_pct_mean": None, "net_pct_sx_mean": None}
    bd = boot_mean([(r["date"], r[arm]["net_pct"]) for r in rs], draws, seed)
    bs = boot_mean([(r["symbol"], r[arm]["net_pct"]) for r in rs], draws, seed)
    Rs = [r[arm].get("R") for r in rs if not r.get("thin")]
    return {"n": len(rs), "n_dates": len({r["date"] for r in rs}), "n_symbols": len({r["symbol"] for r in rs}),
            "net_pct": {"mean": bd["mean"], "lo": bd["lo"], "hi": bd["hi"], "lo_sym": bs["lo"], "hi_sym": bs["hi"]},
            "R": {"mean": _mean(Rs), "median": _median(Rs)},
            "stop_rate": _mean([1.0 if r[arm].get("stopped") else 0.0 for r in rs]),
            "win_rate": _mean([1.0 if r[arm]["net_pct"] > 0 else 0.0 for r in rs]),
            "mfe_R_median": _median([r[arm].get("mfe_R") for r in rs if not r.get("thin")]),
            "gross_pct_mean": _mean([r[arm]["gross_pct"] for r in rs]),
            "net_pct_sx_mean": _mean([r[arm]["net_pct_sx"] for r in rs])}


def diff_block(a, b, arm: str, draws=None, seed=SEED) -> dict:
    da = boot_diff([(r["date"], r[arm]["net_pct"]) for r in a if r.get(arm)],
                   [(r["date"], r[arm]["net_pct"]) for r in b if r.get(arm)], draws, seed)
    ds = boot_diff([(r["symbol"], r[arm]["net_pct"]) for r in a if r.get(arm)],
                   [(r["symbol"], r[arm]["net_pct"]) for r in b if r.get(arm)], draws, seed)
    out = {"mean": da["mean"], "lo": da["lo"], "hi": da["hi"], "lo_sym": ds["lo"], "hi_sym": ds["hi"],
           "n_a": da["n_a"], "n_b": da["n_b"], "n_dates": len({r["date"] for r in a + b if r.get(arm)})}
    lo, hi = _envelope(out)
    out["word"] = RS.verdict(out["n_dates"], [lo, hi] if lo is not None else None)
    return out


def _bucketed(recs, cuts):
    for r in recs:
        r["T"] = bucket(r["value"], cuts)
    return recs


# ── placebo (B1, time-of-day AND sell-off matched; design C5 / C11) ─────────────────────────────────────────────
def pool_days_for(trade_rec: dict, sym_units: list, cr: str, matched: bool = True) -> list:
    """Same-symbol pool days for one real trade: other window days in the cohort; matched = `selloff_at_noon` AND the
    cradle `cr` NOT confirmed BY the trade's clock (a day that confirms LATER stays drawable); unmatched = any day
    whose `cr` never confirmed. The bar-after-clock condition is checked by the sim (pool_sim → None)."""
    out = []
    for u in sym_units:
        if u["date"] == trade_rec["date"] or u.get("out"):
            continue
        jt = ((u.get("cradle") or {}).get(cr) or {}).get("clock")
        if matched:
            if not u.get("selloff_at_noon"):
                continue
            if jt is not None and jt <= trade_rec["clock"]:
                continue
        elif jt is not None:
            continue
        out.append(u)
    return out


def pool_sim(ser: dict, day: date, clock: str, stop_pct: float, cs: float, memo: Optional[dict] = None,
             key=None) -> Optional[tuple]:
    """(X16 net, X20 net) of a placebo entry at the first 1-min open ≥ clock on `day` with the stop at the real
    trade's stop % — memoised by (sym, day, clock, round(stop_pct, DP))."""
    sp = round(float(stop_pct), DP)
    mk = (key, day.isoformat(), clock, sp) if key is not None else None
    if memo is not None and mk is not None and mk in memo:
        return memo[mk]
    e_u = et_epoch(day, clock)
    k0 = int(np.searchsorted(ser["u1"], e_u, "left"))
    res = None
    if k0 < len(ser["u1"]) and ser["u1"][k0] < _horizons(day)["X16"]:
        e = float(ser["o"][k0])
        t = trade(ser, e_u, e * (1 - sp / 100), day, cs)
        if not t.get("no_fill") and not t.get("no_plan"):
            res = (t["X16"]["net_pct"], t["X20"]["net_pct"])
    if memo is not None and mk is not None:
        memo[mk] = res
    return res


def placebo_time_matched(real_trades: list, sets: int = None, seed: int = SEED, arm: int = 0) -> dict:
    """real_trades = [{"net": real net %, "outcomes": [(X16, X20), …] of its pool, "fallback": bool}]; one draw per
    real trade per set (size-matched). beat = share of sets whose mean < the real mean (over the drawable trades)."""
    sets = LAB.PLACEBO_SETS if sets is None else sets
    keep = [r for r in real_trades if r.get("outcomes")]
    if not keep:
        return {"beat": None, "plc_mean": None, "real_mean": None, "n": 0,
                "n_pool_empty": len(real_trades), "pool_fallback_share": None, "_set_means": None}
    rng = np.random.default_rng(seed)
    M = np.empty((sets, len(keep)))
    for i, r in enumerate(keep):
        arr = np.asarray([o[arm] for o in r["outcomes"]], dtype=float)
        M[:, i] = arr[rng.integers(0, len(arr), size=sets)]
    sm = M.mean(axis=1)
    real = float(np.mean([r["net"] for r in keep]))
    return {"beat": float(np.mean(sm < real)), "plc_mean": float(sm.mean()), "real_mean": real, "n": len(keep),
            "n_pool_empty": len(real_trades) - len(keep),
            "pool_fallback_share": float(np.mean([1.0 if r.get("fallback") else 0.0 for r in keep])),
            "_set_means": sm}


def placebo_diff(p3: dict, p1: dict) -> dict:
    if p3.get("_set_means") is None or p1.get("_set_means") is None:
        return {"beat": None, "plc_diff_mean": None, "real_diff": None}
    sd = p3["_set_means"] - p1["_set_means"]
    real = p3["real_mean"] - p1["real_mean"]
    return {"beat": float(np.mean(sd < real)), "plc_diff_mean": float(sd.mean()), "real_diff": real}


def _strip(p: dict) -> dict:
    return {k: v for k, v in p.items() if not k.startswith("_")}


# ── B2 within-day SI shuffle (design C6) ─────────────────────────────────────────────────────────────────────────
def _t3_t1_diff(vals, nets, cuts) -> Optional[float]:
    b = [bucket(v, cuts) for v in vals]
    top = len(cuts) + 1
    a3 = [n for n, k in zip(nets, b) if k == top]
    a1 = [n for n, k in zip(nets, b) if k == 1]
    if not a3 or not a1:
        return None
    return float(np.mean(a3) - np.mean(a1))


def shuffle_once(recs: list, rng) -> list:
    """The basis values permuted WITHIN each date (never across dates); single-unit dates keep their value."""
    by = {}
    for i, r in enumerate(recs):
        by.setdefault(r["date"], []).append(i)
    vals = [r["value"] for r in recs]
    out = list(vals)
    for d in sorted(by):
        idx = by[d]
        if len(idx) < 2:
            continue
        perm = rng.permutation(len(idx))
        for a, b in zip(idx, perm):
            out[a] = vals[idx[b]]
    return out


def si_shuffle(recs: list, cuts, sets: int = None, seed: int = SEED, arm: str = "X16") -> dict:
    sets = LAB.PLACEBO_SETS if sets is None else sets
    recs = [r for r in recs if r.get(arm)]
    by = {}
    for r in recs:
        by[r["date"]] = by.get(r["date"], 0) + 1
    n_multi = sum(1 for v in by.values() if v >= 2)
    n_single = sum(1 for v in by.values() if v < 2)
    gate_active = bool(n_multi >= RS.MIN_BUCKET_N)
    nets = [r[arm]["net_pct"] for r in recs]
    obs = _t3_t1_diff([r["value"] for r in recs], nets, cuts) if (recs and cuts) else None
    if obs is None or n_multi == 0:
        return {"p": None, "observed": obs, "n_dates_shuffled": n_multi, "n_dates_single": n_single,
                "gate_active": gate_active}
    rng = np.random.default_rng(seed)
    ge, ok = 0, 0
    for _ in range(sets):
        d = _t3_t1_diff(shuffle_once(recs, rng), nets, cuts)
        if d is None:
            continue
        ok += 1
        ge += 1 if d >= obs else 0
    return {"p": (ge / ok) if ok else None, "observed": obs, "n_dates_shuffled": n_multi,
            "n_dates_single": n_single, "gate_active": gate_active}


# ── C: Deflated Sharpe (design C8) ───────────────────────────────────────────────────────────────────────────────
def dsr_lists(cell_series: dict, prior: list) -> tuple:
    """cell_series = {trial key: {"series": per-date values, "sr": SR or None}} in family order → (gate list =
    prior + one SR per duplicate cluster, naive list = prior + every SR, clusters)."""
    clusters = SPY.duplicate_clusters({k: v["series"] for k, v in cell_series.items()}, rho=SPY.DUP_RHO)
    eff = [cell_series[c[0]]["sr"] for c in clusters if cell_series[c[0]]["sr"] is not None]
    naive = [v["sr"] for v in cell_series.values() if v["sr"] is not None]
    pr = [float(s) for s in (prior or []) if s is not None]
    return pr + eff, pr + naive, clusters


def prior_srs(ledger_path) -> list:
    if not ledger_path or not Path(ledger_path).exists():
        return []
    out = []
    for r in LAB._read_ledger(ledger_path):
        for k in ("sr_per_entry_day", "sr"):
            v = _num(r.get(k))
            if v is not None:
                out.append(v)
                break
    return out


def _sr(x) -> Optional[float]:
    if len(x) < 3:
        return None
    return LAB.moments(np.asarray(x, dtype=float))["sr"]


# ── the verdict (design §3.3; C4, C6) ────────────────────────────────────────────────────────────────────────────
def verdict(primary: dict, min_bucket_n: int = None) -> tuple:
    m = RS.MIN_BUCKET_N if min_bucket_n is None else min_bucket_n
    t3 = primary["T3"]["X16"]["oos"]
    t1 = primary["T1"]["X16"]["oos"]
    df = primary["diff"]["X16"]["oos"]
    g = {}
    g["too_small"] = bool((t3.get("n_dates") or 0) < m or (t1.get("n_dates") or 0) < m)
    lo3, _ = _envelope(t3["net_pct"])
    g["t3_pos"] = bool(lo3 is not None and lo3 > 0)
    lod, hid = _envelope(df)
    g["diff_pos"] = bool(lod is not None and lod > 0)
    pm = (primary.get("placebo") or {}).get("matched") or {}
    b3 = (pm.get("T3") or {}).get("beat")
    bd = (pm.get("diff") or {}).get("beat")
    g["placebo_t3"] = bool(b3 is not None and b3 >= LAB.PLACEBO_BEAT_SHARE)
    g["placebo_diff"] = bool(bd is not None and bd >= LAB.PLACEBO_BEAT_SHARE)
    sh = primary.get("shuffle") or {}
    if sh.get("gate_active"):
        g["shuffle"] = bool(sh.get("p") is not None and sh["p"] <= 1 - LAB.PLACEBO_BEAT_SHARE)
    else:
        g["shuffle"] = "n/a"
    ds = (primary.get("dsr") or {}).get("dsr")
    g["dsr"] = bool(ds is not None and ds >= LAB.DSR_PASS)
    g["replicates_symbols"] = bool((primary.get("oos_symbols") or {}).get("replicates") is True)
    if g["too_small"]:
        return WORD_SMALL, g
    if all(g[k] is True for k in ("t3_pos", "diff_pos", "placebo_t3", "placebo_diff", "dsr", "replicates_symbols")) \
            and g["shuffle"] in (True, "n/a"):
        return WORD_POS, g
    if hid is not None and hid < 0:
        return WORD_INV, g
    return WORD_NULL, g


# ═══════════════════════════════════════════════════════════════════════════════════════════════════ analysis ═══
def cell_ids() -> list:
    out, k = [], 0
    for h in HS:
        for cr in CRS:
            for b in BASES:
                k += 1
                out.append((f"C{k:02d}", h, cr, b))
    return out


def _trade_rec(u: dict, cr: str, half_of: dict) -> Optional[dict]:
    t = (u.get("trade") or {}).get(cr)
    c = (u.get("cradle") or {}).get(cr)
    if u.get("out") or not t or not c or t.get("no_fill") or t.get("no_plan"):
        return None
    return {"symbol": u["symbol"], "date": u["date"], "half": half_of[u["date"]], "clock": c["clock"],
            "stop_pct": t["stop_pct"], "thin": t["thin"], "e": t["e"], "X16": t["X16"], "X20": t["X20"],
            "drop_pct": c["drop_pct"], "above_entry_14": t.get("above_entry_14"),
            "above_entry_16": t.get("above_entry_16"), "si": u.get("si")}


def analysis_set(units: list, h: str, cr: str, basis: str, half_of: dict) -> list:
    out = []
    for u in units:
        if u.get("out") or not u.get("si") or (u.get("h") or {}).get(h) is not True:
            continue
        v = u["si"].get(basis)
        if v is None:
            continue
        r = _trade_rec(u, cr, half_of)
        if r is None:
            continue
        r["value"] = float(v)
        out.append(r)
    out.sort(key=lambda r: (r["date"], r["symbol"]))
    return out


def cell_symbols(units: list) -> set:
    """Every symbol that sits in ANY of the 18 confirmatory cells' analysis sets — the same `analysis_set` the cells
    read (design §5 "BRK-B ∉ cells"); a unit's `half` is the one analyze_core stamped on it."""
    half_of = {u["date"]: u.get("half") for u in units}
    return {r["symbol"] for _cid, h, cr, b in cell_ids() for r in analysis_set(units, h, cr, b, half_of)}


def _tier_blocks(recs_by_split: dict, cuts, draws, seed) -> dict:
    out = {}
    top = len(cuts) + 1 if cuts else 0
    for T in range(1, top + 1):
        out[f"T{T}"] = {arm: {sp: arm_block([r for r in recs_by_split[sp] if r["T"] == T], arm, draws, seed)
                              for sp in SPLITS3} for arm in ARMS}
    out["diff"] = {arm: {sp: diff_block([r for r in recs_by_split[sp] if r["T"] == top],
                                        [r for r in recs_by_split[sp] if r["T"] == 1], arm, draws, seed)
                         for sp in SPLITS3} for arm in ARMS}
    return out


class PlaceboCtx:
    """Pool data for B1: per real (sym, date, cr) the same-symbol pool outcomes; the global selloff-at-noon day registry
    for the cross-symbol fallback (same SI tercile + same date half)."""

    def __init__(self, cs: float):
        self.cs = cs
        self.memo: dict = {}
        self.same: dict = {}          # (sym, date, cr, "matched"|"unmatched") -> [(day_iso, (x16, x20)), …]
        self.registry: dict = {}      # (sym, date) -> {"ser", "half", "jt": {cr: clock|None}, "si": {basis: v}}

    def fallback_outcomes(self, rec: dict, cr: str, basis: str, cuts) -> list:
        out = []
        top = bucket(rec["value"], cuts)
        for (sym, d) in sorted(self.registry):
            if sym == rec["symbol"]:
                continue
            g = self.registry[(sym, d)]
            if g["half"] != rec["half"]:
                continue
            v = (g.get("si") or {}).get(basis)
            if v is None or bucket(v, cuts) != top:
                continue
            jt = g["jt"].get(cr)
            if jt is not None and jt <= rec["clock"]:
                continue
            res = pool_sim(g["ser"], date.fromisoformat(d), rec["clock"], rec["stop_pct"], self.cs, self.memo, sym)
            if res is not None:
                out.append((d, res))
        return out


def _placebo_for(recs: list, cr: str, basis: str, cuts, ctx: PlaceboCtx, sets, seed, kind: str) -> dict:
    trades = []
    for r in recs:
        same = ctx.same.get((r["symbol"], r["date"], cr, kind)) or []
        fb = False
        if not same and kind == "matched":
            same = ctx.fallback_outcomes(r, cr, basis, cuts)
            fb = bool(same)
        trades.append({"net": r["X16"]["net_pct"], "outcomes": [o for _, o in same], "fallback": fb, "T": r["T"]})
    top = len(cuts) + 1 if cuts else 0
    p3 = placebo_time_matched([t for t in trades if t["T"] == top], sets, seed)
    p1 = placebo_time_matched([t for t in trades if t["T"] == 1], sets, seed + 1)
    return {"T3": _strip(p3), "T1": _strip(p1), "diff": placebo_diff(p3, p1)}


def cell(units, cid, h, cr, basis, halves, ctx: Optional[PlaceboCtx], *, draws=None, sets=None,
         seed=SEED) -> tuple:
    """One confirmatory cell → (block, per-split T3 recs for the DSR family)."""
    is_d, oos_d = halves
    half_of = {d.isoformat(): ("is" if d in is_d else "oos") for d in (is_d | oos_d)}
    recs = analysis_set(units, h, cr, basis, half_of)
    is_recs = [r for r in recs if r["half"] == "is"]
    cuts = cutpoints([r["value"] for r in is_recs], TERCILES)
    qcuts = cutpoints([r["value"] for r in is_recs], QUARTILES)
    _bucketed(recs, cuts)
    by = {"pooled": recs, "is": is_recs, "oos": [r for r in recs if r["half"] == "oos"]}
    blk = {"h": h, "cr": cr, "basis": basis, "n": len(recs), "n_dates": len({r["date"] for r in recs}),
           "n_symbols": len({r["symbol"] for r in recs}), "cuts_is": cuts, "quartile_cuts_is": qcuts}
    if cuts is None:
        blk.update({f"T{t}": {arm: {sp: arm_block([], arm) for sp in SPLITS3} for arm in ARMS} for t in TIERS})
        blk["diff"] = {arm: {sp: diff_block([], [], arm) for sp in SPLITS3} for arm in ARMS}
    else:
        blk.update(_tier_blocks(by, cuts, draws, seed))
    dx = blk["diff"]["X16"]
    blk["word"] = dx["oos"]["word"]
    blk["word_pooled"] = dx["pooled"]["word"]
    if ctx is not None and cuts is not None:
        blk["placebo"] = {k: _placebo_for(by["oos"], cr, basis, cuts, ctx, sets, seed, k)
                          for k in ("matched", "unmatched")}
        blk["placebo_pooled"] = {k: _placebo_for(recs, cr, basis, cuts, ctx, sets, seed, k)
                                 for k in ("matched", "unmatched")}
    else:
        empty = {"T3": {"beat": None}, "T1": {"beat": None}, "diff": {"beat": None}}
        blk["placebo"] = {"matched": dict(empty), "unmatched": dict(empty)}
        blk["placebo_pooled"] = {"matched": dict(empty), "unmatched": dict(empty)}
    blk["shuffle"] = si_shuffle(by["oos"], cuts, sets, seed) if cuts else {
        "p": None, "n_dates_shuffled": 0, "n_dates_single": 0, "gate_active": False, "observed": None}
    top = len(cuts) + 1 if cuts else TOP
    blk["oos_dates"] = {sp: {"T3": blk[f"T{top}"]["X16"][sp]["net_pct"], "diff": _dsum(dx[sp])} for sp in ("is", "oos")}
    blk["oos_dates"]["replicates"] = _same_sign(dx["is"]["mean"], dx["oos"]["mean"])
    blk["oos_symbols"] = _symbol_halves_block(by["oos"], draws, seed)
    blk["quartiles"] = _quartiles(recs, qcuts, draws, seed)
    if basis != "dtc":
        blk["bands"] = _bands(by, draws, seed)
    return blk, recs


def _dsum(d: dict) -> dict:
    return {k: d.get(k) for k in ("mean", "lo", "hi", "lo_sym", "hi_sym", "word")}


def _same_sign(a, b) -> Optional[bool]:
    if a is None or b is None:
        return None
    return bool((a > 0 and b > 0) or (a < 0 and b < 0))


def _symbol_halves_block(oos_recs, draws, seed) -> dict:
    A, B = symbol_halves([r["symbol"] for r in oos_recs])
    ra = [dict(r) for r in oos_recs if r["symbol"] in A]
    rb = [dict(r) for r in oos_recs if r["symbol"] in B]
    cuts = cutpoints([r["value"] for r in ra], TERCILES)
    out = {"cut_source": "symbol half A of the OOS date half", "cuts": cuts}
    for name, rs in (("a", ra), ("b", rb)):
        if cuts is None:
            out[name] = {"T3": None, "diff": None, "n": len(rs)}
            continue
        _bucketed(rs, cuts)
        out[name] = {"n": len(rs), "T3": arm_block([r for r in rs if r["T"] == TOP], "X16", draws, seed)["net_pct"],
                     "diff": _dsum(diff_block([r for r in rs if r["T"] == TOP], [r for r in rs if r["T"] == 1],
                                              "X16", draws, seed))}
    da = ((out.get("a") or {}).get("diff") or {}).get("mean")
    db_ = ((out.get("b") or {}).get("diff") or {}).get("mean")
    out["replicates"] = _same_sign(da, db_)
    return out


def _quartiles(recs, qcuts, draws, seed) -> dict:
    if qcuts is None:
        return {}
    out = {}
    for q in range(1, len(qcuts) + 2):
        rs = [r for r in recs if bucket(r["value"], qcuts) == q]
        out[f"Q{q}"] = {arm: arm_block(rs, arm, draws, seed)["net_pct"] for arm in ARMS}
        out[f"Q{q}"]["n"] = len(rs)
    return out


def _band_of(v) -> str:
    if v >= SIC.SI_HIGH_PCT:
        return "high"
    if v >= SIC.SI_ELEV_PCT:
        return "elevated"
    return "low"


def _bands(by, draws, seed) -> dict:
    out = {}
    for sp in ("pooled", "oos"):
        out[sp] = {}
        for band in ("high", "elevated", "low"):
            rs = [r for r in by[sp] if _band_of(r["value"]) == band]
            out[sp][band] = {"n": len(rs), "X16": arm_block(rs, "X16", draws, seed)["net_pct"],
                             "stop_rate": arm_block(rs, "X16", draws, seed)["stop_rate"]}
    return out


def _date_series(recs, dates, arm="X16") -> list:
    by = {}
    for r in recs:
        if r.get(arm):
            by.setdefault(r["date"], []).append(r[arm]["net_pct"])
    return [float(np.mean(by[d])) if d in by else 0.0 for d in dates]


def spearman(x, y) -> Optional[float]:
    if len(x) < 3:
        return None
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def spearman_ci(pairs, draws=None, seed=SEED) -> dict:
    """ρ of (basis value, net) with a percentile CI resampling WHOLE dates; pairs = [(date, x, y)]."""
    draws = LAB.BOOT_DRAWS if draws is None else draws
    if len(pairs) < 3:
        return {"rho": None, "lo": None, "hi": None, "n": len(pairs)}
    rho = spearman([p[1] for p in pairs], [p[2] for p in pairs])
    by = {}
    for d, x, y in pairs:
        by.setdefault(d, []).append((x, y))
    keys = sorted(by)
    rng = np.random.default_rng(seed)
    reps = []
    for _ in range(draws):
        pick = rng.integers(0, len(keys), size=len(keys))
        pts = [p for k in pick for p in by[keys[k]]]
        r = spearman([p[0] for p in pts], [p[1] for p in pts])
        if r is not None:
            reps.append(r)
    ci = RS.ci_of(reps, dp=DP) if reps else None
    return {"rho": rho, "lo": ci[0] if ci else None, "hi": ci[1] if ci else None, "n": len(pairs),
            "n_dates": len(keys)}


def descriptive(units, halves, cell_recs: dict, draws=None, seed=SEED) -> dict:
    is_d, oos_d = halves
    half_of = {d.isoformat(): ("is" if d in is_d else "oos") for d in (is_d | oos_d)}
    out = {"noon": {"by_h": {}}}
    for h in HS:
        hb = {}
        for basis in BASES:
            rs = []
            for u in units:
                if u.get("out") or not u.get("si") or not u.get("noon") or (u.get("h") or {}).get(h) is not True:
                    continue
                v = u["si"].get(basis)
                if v is None:
                    continue
                rs.append({"symbol": u["symbol"], "date": u["date"], "half": half_of[u["date"]], "value": float(v),
                           "X16": u["noon"]["X16"], "X20": u["noon"]["X20"]})
            cuts = cutpoints([r["value"] for r in rs if r["half"] == "is"], TERCILES)
            _bucketed(rs, cuts)
            hb[basis] = {"cuts_is": cuts, "n": len(rs)}
            for T in TIERS:
                hb[basis][f"T{T}"] = {arm: arm_block([r for r in rs if r["T"] == T], arm, draws, seed)["net_pct"]
                                      for arm in ARMS}
            hb[basis]["diff"] = {arm: _dsum(diff_block([r for r in rs if r["T"] == TOP],
                                                       [r for r in rs if r["T"] == 1], arm, draws, seed))
                                 for arm in ARMS}
        per = {}
        for u in units:
            if u.get("out") or not u.get("si") or not u.get("noon"):
                continue
            hv = (u.get("h") or {}).get(h)
            if hv is None:
                continue
            per.setdefault(u["symbol"], {True: [], False: []})[bool(hv)].append(u["noon"]["X16"]["net_pct"])
        paired = [(s, float(np.mean(v[True])) - float(np.mean(v[False])))
                  for s, v in sorted(per.items()) if v[True] and v[False]]
        hb["vs_no_h_paired"] = boot_mean(paired, draws, seed)
        out["noon"]["by_h"][h] = hb
    c01 = cell_recs.get(PRIMARY) or []
    out["monotone"] = spearman_ci([(r["date"], r["value"], r["X16"]["net_pct"]) for r in c01], draws, seed)
    dcuts = cutpoints([r["drop_pct"] for r in c01], TERCILES)
    out["drop_terciles"] = {"cuts": dcuts}
    for T in TIERS:
        rs = [r for r in c01 if bucket(r["drop_pct"], dcuts) == T]
        out["drop_terciles"][f"T{T}"] = arm_block(rs, "X16", draws, seed)["net_pct"] if dcuts else None
    hist = {}
    for u in units:
        c = ((u.get("cradle") or {}).get("CRA") or {}) if not u.get("out") else {}
        if c and u.get("si") and (u.get("h") or {}).get("H1") is True:
            hr = c["clock"].split(":")[0] + ":00"
            hist[hr] = hist.get(hr, 0) + 1
    out["confirm_time_hist"] = dict(sorted(hist.items()))
    t3 = [r for r in c01 if r.get("T") == TOP]
    out["dollar_side"] = {"ge_1": arm_block([r for r in t3 if r["e"] >= 1], "X16", draws, seed)["net_pct"],
                          "lt_1": arm_block([r for r in t3 if r["e"] < 1], "X16", draws, seed)["net_pct"]}
    out["thin_excluded"] = arm_block([r for r in t3 if not r["thin"]], "X16", draws, seed)["net_pct"]
    a14 = [r["above_entry_14"] for r in c01 if r.get("above_entry_14") is not None]
    a16 = [r["above_entry_16"] for r in c01 if r.get("above_entry_16") is not None]
    out["above_entry_14_16"] = {"share_14": _mean([1.0 if x else 0.0 for x in a14]), "n_14": len(a14),
                                "share_16": _mean([1.0 if x else 0.0 for x in a16]), "n_16": len(a16)}
    both = [(u["date"], u["si"]["dtc"], u["si"]["pct_float"]) for u in units
            if not u.get("out") and u.get("si") and u["si"].get("dtc") is not None
            and u["si"].get("pct_float") is not None]
    out["dtc_vs_pct_float_rho"] = {"rho": spearman([b[1] for b in both], [b[2] for b in both]), "n": len(both)}
    return out


def overlap_block(units) -> dict:
    rp = [u for u in units if u.get("replayed") and not u.get("out")]
    brd = [u for u in rp if (u.get("board") or {}).get("board_running")]
    pot = [u for u in brd if u["board"]["rs_potential"]]
    before = after = 0
    for u in pot:
        c = (u.get("cradle") or {}).get("CRA")
        fs = u["board"].get("first_seen_et")
        if c and fs:
            if fs <= c["clock"]:
                before += 1
            else:
                after += 1
    armed = [u["replay"]["first_armed_t"].split(" ")[1] for u in rp if (u.get("replay") or {}).get("first_armed_t")]
    tv = []
    for u in rp:
        c = (u.get("cradle") or {}).get("CRA")
        tr = (u.get("replay") or {}).get("armed_trigger")
        if c and tr and c.get("cradle_high"):
            tv.append((float(tr) / c["cradle_high"] - 1) * 100)
    fse = sorted(u["board"]["first_seen_et"] for u in pot if u["board"].get("first_seen_et"))
    return {"board": {"units_board_running": len(brd), "units_board_not_running": len(rp) - len(brd),
                      "units_with_rs_potential": len(pot), "armed_before_confirm": before, "armed_after": after,
                      "aplus_same_day": sum(1 for u in brd if u["board"].get("aplus_same_day")),
                      "first_seen_et_median": fse[len(fse) // 2] if fse else None},
            "replay": {"units_replayed": len(rp),
                       "rs_read_any": sum(1 for u in rp if (u.get("replay") or {}).get("first_armed_t")
                                          or (u.get("replay") or {}).get("first_aplus_t")),
                       "first_armed_t_median": sorted(armed)[len(armed) // 2] if armed else None,
                       "trigger_vs_cradle_high": _median(tv), "n_trigger_vs_cradle_high": len(tv)}}


def _counts(units, U, excluded, si_hist, daily_all, names) -> dict:
    live = [u for u in units if not u.get("out")]
    reasons = {}
    for u in units:
        if u.get("out"):
            reasons[u["out"]] = reasons.get(u["out"], 0) + 1
    c = {"universe": len(U), "units_total": len(units),
         "units_with_bars": sum(1 for u in units if u.get("out") != "no_bars"),
         "basis_mismatch_daily": reasons.get("basis_mismatch_daily", 0),
         "basis_mismatch_intraday": reasons.get("basis_mismatch_intraday", 0),
         "split_at_unit": reasons.get("split_at_unit", 0), "out_reasons": reasons,
         "units_si": sum(1 for u in live if u.get("si")),
         "float_suspect": sum(1 for u in live if (u.get("si") or {}).get("float_suspect")),
         "pct_float_over_100": sum(1 for u in live if (u.get("si") or {}).get("pct_float_over_100")),
         "dtc_none": sum(1 for u in live if u.get("si") and u["si"].get("dtc") is None),
         "no_fill": sum(1 for u in live for v in CRS if ((u.get("trade") or {}).get(v) or {}).get("no_fill")),
         "no_plan": sum(1 for u in live for v in CRS if ((u.get("trade") or {}).get(v) or {}).get("no_plan")),
         "thin": sum(1 for u in live for v in CRS if ((u.get("trade") or {}).get(v) or {}).get("thin")),
         "noon_floor_fail": sum(1 for u in live if u.get("si") and not u.get("noon_floor_ok")),
         "split_in_lookback": sum(1 for u in live if (u.get("h") or {}).get("split_in_lookback")),
         "no_si_history": sum(1 for s in names if not si_hist.get(s)),
         "no_daily_lookback": sum(1 for s in names if len(daily_all.get(s) or []) <= GC.K8_HISTORY_SESSIONS)}
    for h in HS:
        c[f"units_{h}"] = sum(1 for u in live if (u.get("h") or {}).get(h) is True)
    for v in CRS:
        c[f"cradle_{v}"] = sum(1 for u in live if (u.get("cradle") or {}).get(v))
    ex = {}
    for sym, reason, brd in excluded:
        ex[reason] = ex.get(reason, 0) + 1
    c["excluded"] = ex
    c["float_exceeds_shares_out"] = ex.get(SR.FLOAT_EXCEEDS_SHARES, 0)
    c["float_exceeds_shares_out_names"] = sorted(s for s, r, b in excluded if r == SR.FLOAT_EXCEEDS_SHARES)
    c["float_exceeds_shares_out_board"] = sorted(s for s, r, b in excluded if b and r == SR.FLOAT_EXCEEDS_SHARES)
    c["float_unknown_board"] = sorted(s for s, r, b in excluded if b and r == "float_none")
    c["board_in_universe"] = sum(1 for v in U.values() if v.get("board"))
    return c


def daily_coverage(units, daily_all, names, window) -> dict:
    """What price_cache actually holds for the streamed names (corrects the design §1.3 '650 of 651 have 251 daily
    bars' sentence from the data, never by hand)."""
    lens = {s: len(daily_all.get(s) or []) for s in names}
    top = max(lens.values()) if lens else None
    lost = {}
    for u in units:
        if u.get("out") == "no_d1_bar":
            lost[u["symbol"]] = lost.get(u["symbol"], 0) + 1
    return {"names": len(names), "max_bars": top, "names_at_max_bars": sum(1 for v in lens.values() if v == top),
            "no_price_cache": sorted(s for s, v in lens.items() if v == 0),
            "ends_before_window": sorted(s for s in names if daily_all.get(s)
                                         and daily_all[s][-1]["date"] < window[0]),
            "le_lookback": sum(1 for v in lens.values() if v <= GC.K8_HISTORY_SESSIONS),
            "names_losing_units_no_d1_bar": len(lost), "units_no_d1_bar": sum(lost.values())}


def mdv20_summary(units) -> dict:
    """The 20-day median $ volume over every confirmed trade (CRA or CRB) — printed, never a cut (design §1.2)."""
    xs = sorted((u.get("day") or {}).get("mdv20_usd") for u in units
                if not u.get("out") and (u.get("day") or {}).get("mdv20_usd") is not None
                and any(_trade_rec(u, v, {u["date"]: u.get("half")}) for v in CRS))
    return {"bars": LAB.CAP_MDV_BARS, "n_trade_units": len(xs), "median": _median(xs),
            "min": xs[0] if xs else None, "max": xs[-1] if xs else None}


def _event_row(u: dict) -> dict:
    return {k: v for k, v in u.items()}


def analyze_core(inp: dict, *, draws=None, sets=None, seed=SEED) -> tuple:
    """Deterministic analysis on injected inputs (Mongo-free): inp = {as_of, window, universe (Universe), names,
    daily {sym: list}, si_hist {sym: rows}, splits {sym: list|None}, snapshot(sym) -> {date: df} | None, stores,
    prior, meta extras}. Returns (results, events)."""
    as_of = inp["as_of"]
    window = inp["window"]
    halves = date_halves(window)
    U = inp["universe"]
    cs = cost_side()
    ctx = PlaceboCtx(cs)
    units = []
    sanity = {}
    win_iso = {d.isoformat() for d in window}
    is_d, oos_d = halves
    half_of = {d.isoformat(): ("is" if d in is_d else "oos") for d in window}
    stream = sorted(set(inp["names"]) | set(s for s in SANITY if s in U))
    for sym in stream:
        days = inp["snapshot"](sym)
        if days is None:
            if sym in inp["names"]:
                units.extend({"symbol": sym, "date": d.isoformat(), "out": "no_snapshot"} for d in window)
            continue
        info = U.get(sym) or {}
        daily = inp["daily"].get(sym) or []
        rows = inp["si_hist"].get(sym) or []
        spl = inp["splits"].get(sym)
        sym_units, internals = [], {}
        if sym in inp["names"]:
            for D in window:
                u, it = evaluate_unit(sym, D, days.get(RX.prev_market_day(D)), days.get(D), daily, rows, spl, info,
                                      cs, inp.get("stores"), as_of=as_of)
                u["half"] = half_of[u["date"]]
                sym_units.append(u)
                if it is not None:
                    internals[u["date"]] = it
            _register_pools(sym, sym_units, internals, ctx)
            units.extend(sym_units)
        if sym in SANITY:
            sanity[sym] = _sanity_row(sym, as_of, days, daily, rows, spl, info, cs, inp.get("stores"), inp)
        for s, d in SANITY_EXTRA:
            if s == sym:
                dd = date.fromisoformat(d)
                u, _ = evaluate_unit(sym, dd, days.get(RX.prev_market_day(dd)), days.get(dd), daily, rows, spl,
                                     info, cs, inp.get("stores"), as_of=as_of, force_replay=True)
                sanity.setdefault(f"{sym}_{d}", _slim_unit(u))
        del internals
    assert all(u["date"] in win_iso for u in units)
    cells, cell_recs, fam = {}, {}, {}
    for cid, h, cr, basis in cell_ids():
        blk, recs = cell(units, cid, h, cr, basis, halves, ctx, draws=draws, sets=sets, seed=seed)
        cells[cid] = blk
        cell_recs[cid] = recs
    assert cell_symbols(units) == {r["symbol"] for recs in cell_recs.values() for r in recs}
    oos_dates = sorted(d.isoformat() for d in oos_d)
    for arm in ARMS:
        for cid, h, cr, basis in cell_ids():
            t3 = [r for r in cell_recs[cid] if r["half"] == "oos" and r.get("T") == TOP]
            fam[f"{cid}|{arm}"] = {"series": _date_series(t3, oos_dates, arm),
                                   "sr": _sr([r[arm]["net_pct"] for r in t3])}
    for cid, h, cr, basis in cell_ids():
        if basis == "dtc":
            continue
        hb = [r for r in cell_recs[cid] if r["half"] == "oos" and _band_of(r["value"]) == "high"]
        fam[f"{cid}|band_high"] = {"series": _date_series(hb, oos_dates), "sr": _sr([r["X16"]["net_pct"] for r in hb])}
    prior = list(inp.get("prior") or [])
    gate_list, naive_list, clusters = dsr_lists(fam, prior)
    for cid, h, cr, basis in cell_ids():
        x = [r["X16"]["net_pct"] for r in cell_recs[cid] if r["half"] == "oos" and r.get("T") == TOP]
        g = LAB.deflated(np.asarray(x, dtype=float), gate_list) if len(x) else {}
        nv = LAB.deflated(np.asarray(x, dtype=float), naive_list) if len(x) else {}
        cells[cid]["dsr"] = {"sr": g.get("sr"), "sr0": g.get("sr0"), "psr0": g.get("psr0"), "dsr": g.get("dsr"),
                             "N": len(gate_list), "sr0_naive": nv.get("sr0"), "dsr_naive": nv.get("dsr"),
                             "N_naive": len(naive_list), "n": len(x)}
    word, gates = verdict(cells[PRIMARY])
    c01 = cells[PRIMARY]
    t3o = c01["T3"]["X16"]["oos"]
    primary = {"cell": PRIMARY, "split": "oos_dates", "gates": gates, "verdict": word,
               "band": {"cut_t3_pct_float": (c01.get("cuts_is") or [None, None])[-1],
                        "t3_net_pct_ci_oos": [t3o["net_pct"]["lo"], t3o["net_pct"]["hi"]]}}
    buckets = {}
    for basis in BASES:
        cid = next(c for c, h, cr, b in cell_ids() if h == "H1" and cr == "CRA" and b == basis)
        bb = {"terciles_is": cells[cid]["cuts_is"], "quartiles_is": cells[cid]["quartile_cuts_is"],
              "source_cell": cid}
        if basis != "dtc":
            bb["bands"] = {"SI_HIGH_PCT": SIC.SI_HIGH_PCT, "SI_ELEV_PCT": SIC.SI_ELEV_PCT}
        buckets[basis] = bb
    res = {
        "meta": dict(inp.get("meta") or {}, as_of=as_of.isoformat(), thesis_day=AS_OF,
                     window={"from": window[0].isoformat(), "to": window[-1].isoformat(), "sessions": len(window),
                             "is_to": max(is_d).isoformat(), "oos_from": min(oos_d).isoformat()},
                     seed=seed, analyst=ANALYST, constants=CONSTANTS,
                     cost={"per_side": cs, "basis": "LAB.cost_side(COST_TIER1_TOP_N + 1) = tier 2 + slippage",
                           "sensitivity": {"sx_cost": SX_COST, "sx_slip_per_share": SX_SLIP},
                           "cap_note": "the 1 % of 20-day median $ volume cap is a SIZE rule; this study sizes nothing",
                           "mdv20": mdv20_summary(units)},
                     float_age=float_age_summary(U),
                     counts=dict(_counts(units, U, U.excluded, inp["si_hist"], inp["daily"], inp["names"]),
                                 daily_coverage=daily_coverage(units, inp["daily"], inp["names"], window)),
                     stride=inp.get("stride"), names_streamed=len(inp["names"])),
        "coverage": inp.get("coverage") or {},
        "buckets": buckets,
        "cells": {k: _clean_cell(v) for k, v in cells.items()},
        "primary": primary,
        "dsr_n": {"prior_sr_available": len(prior), "this_study": len(fam), "effective_clusters": len(clusters),
                  "N_gate": len(gate_list), "N_naive": len(naive_list), "narrative_prior": NARRATIVE_PRIOR_N,
                  "narrative_total": NARRATIVE_PRIOR_N + len(fam), "clusters": clusters},
        "descriptive": descriptive(units, halves, cell_recs, draws, seed),
        "overlap": overlap_block(units),
        "sanity": sanity,
        "survivorship": {"text": "Universe = TODAY's shares_cache float ≤ K8_MAX_FLOAT (a look-ahead and a survivorship "
                                 "filter: delisted and reverse-split-away names are absent; names listed after the "
                                 "window start enter when their bars begin).",
                         "counts": {"universe": len(U), "excluded": len(U.excluded)}},
        "basis_note": {"text": "ONE price basis: every 1-min bar is the study's own Massive adjusted=true snapshot; "
                               "intraday_cache is never read (it is a mixed-basis store).",
                       "cache_mixed_basis_finding": "critique C1 probe: 243 of 2,358 sampled intraday_cache docs (10 %) "
                                                    "on 35 of 120 symbols (29 %) sit on a pre-split basis — HIS CALL #2b"},
        "deviations": list(inp.get("deviations") or []),
        "his_calls": HIS_CALLS,
    }
    events = [_event_row(u) for u in units]
    return res, events


def _clean_cell(blk: dict) -> dict:
    return blk


def _slim_unit(u: dict) -> dict:
    keep = ("symbol", "date", "out", "si", "si_reason", "h", "selloff_at_noon", "cradle", "trade", "noon", "replay",
            "board", "day")
    return {k: u.get(k) for k in keep}


def _register_pools(sym, sym_units, internals, ctx: PlaceboCtx):
    """Same-symbol pool outcomes for every confirmed trade of this symbol (matched + unmatched), and the selloff-at-noon
    days into the global fallback registry (their 1-min arrays from noon on)."""
    for u in sym_units:
        if u.get("out") or u["date"] not in internals:
            continue
        if u.get("selloff_at_noon") and u.get("si"):
            it = internals[u["date"]]
            d = date.fromisoformat(u["date"])
            ser = minute_series_slice(it["ser"], et_epoch(d, NOON_ET))
            ctx.registry[(sym, u["date"])] = {"ser": ser, "half": u["half"],
                                              "jt": {v: ((u.get("cradle") or {}).get(v) or {}).get("clock")
                                                     for v in CRS},
                                              "si": {b: u["si"].get(b) for b in BASES}}
    for u in sym_units:
        if u.get("out"):
            continue
        for v in CRS:
            t = (u.get("trade") or {}).get(v)
            c = (u.get("cradle") or {}).get(v)
            if not t or t.get("no_fill") or t.get("no_plan") or not c:
                continue
            rec = {"date": u["date"], "clock": c["clock"]}
            for kind in ("matched", "unmatched"):
                outs = []
                for pu in pool_days_for(rec, sym_units, v, matched=(kind == "matched")):
                    it = internals.get(pu["date"])
                    if it is None:
                        continue
                    res = pool_sim(it["ser"], date.fromisoformat(pu["date"]), c["clock"], t["stop_pct"], ctx.cs,
                                   ctx.memo, sym)
                    if res is not None:
                        outs.append((pu["date"], res))
                ctx.same[(sym, u["date"], v, kind)] = outs


def minute_series_slice(ser: dict, from_u: int) -> dict:
    k = int(np.searchsorted(ser["u1"], from_u, "left"))
    return {key: arr[k:] for key, arr in ser.items()}


def _sanity_row(sym, as_of, days, daily, rows, spl, info, cs, stores, inp) -> dict:
    u, it = evaluate_unit(sym, as_of, days.get(RX.prev_market_day(as_of)), days.get(as_of), daily, rows, spl, info,
                          cs, stores, as_of=as_of, force_replay=True)
    row = _slim_unit(u)
    row["seen_before_freeze"] = True
    row["float_now"] = info.get("float_shares")
    row["shares_out_now"] = info.get("shares_outstanding")
    sd = (inp.get("si_docs") or {}).get(sym) or {}
    si = u.get("si") or {}
    if sd.get("float_shares") and si.get("si_shares"):
        row["pct_float_si_doc"] = si["si_shares"] / sd["float_shares"] * 100
        row["si_doc_float"] = sd.get("float_shares")
        row["si_doc_float_asof"] = sd.get("float_asof")
    d1 = RX.prev_market_day(as_of)
    i = _daily_at(daily, d1)
    row["seams"] = {"daily_close_d1": daily[i]["close"] if i is not None else None,
                    "check": seam_check(days.get(d1), days.get(as_of), daily[i]["close"] if i is not None else None)}
    return row


# ── pins the analyze stage prints and STOPS on (design §5) ───────────────────────────────────────────────────────
def brk_reason(results: dict, events: list, sym: str = "BRK-B") -> str:
    """Why `sym` is (or is not) in a cell — printed beside the pin (design §5 "its reason printed")."""
    cnt = (results.get("meta") or {}).get("counts") or {}
    if sym in (cnt.get("float_exceeds_shares_out_names") or []):
        return f"excluded from the universe: {SR.FLOAT_EXCEEDS_SHARES}"
    mine = [e for e in events if e["symbol"] == sym]
    if not mine:
        return "not streamed"
    live = [e for e in mine if not e.get("out")]
    sus = sorted({(e.get("si") or {}).get("float_suspect") for e in live} - {None})
    trades = sum(1 for e in live for v in CRS if _trade_rec(e, v, {e["date"]: e.get("half")}))
    return (f"units {len(mine)}, live {len(live)}, float_suspect {sus or None}, confirmed cradle trades {trades}, "
            f"cells {'IN' if sym in cell_symbols(mine) else 'none'}")


def pins(results: dict, events: list, stores: Optional[dict]) -> list:
    out = []
    for s, p in (("2026-10-30", "2026-11-10"), ("2026-10-15", "2026-10-26")):     # read.py:24-25
        out.append((f"publication_date({s}) == {p}", SR.publication_date(date.fromisoformat(s)) == date.fromisoformat(p)))
    as_of = results["meta"]["as_of"]
    in_cells = any(e["date"] == as_of for e in events)
    out.append((f"{as_of} absent from every unit", not in_cells))
    out.append((f"BRK-B absent from every cell ({brk_reason(results, events)})", "BRK-B" not in cell_symbols(events)))
    ak = (results.get("sanity") or {}).get("AKAN")
    if ak is not None:
        out.append(("seam_check AKAN AS_OF vs price_cache D-1 close → None", (ak.get("seams") or {}).get("check") is None))
        pot = ((stores or {}).get("potentials") or {}).get((as_of, "AKAN"))
        want = (pot or {}).get("first_bar_t")
        got = (ak.get("replay") or {}).get("first_armed_t")
        out.append((f"AKAN replay first-armed t {got} == stored potential first_bar_t {want}",
                    want is not None and got == want))
    return out


HIS_CALLS = [
    "1 Build the 🛏 Cradle squeeze tab — only after the verdict; a display-only list on his word otherwise.",
    "2a Cache side-writes into intraday_cache vs none; the snapshot in the study folder: purge or keep.",
    "2b The ~10 % pre-split intraday_cache docs (critique C1) — a live-store rewrite he must call.",
    "3 Window and universe — 120 sessions on today's float (look-ahead); a point-in-time float pull = the lab's HIS CALL #1.",
    "4 Any SI condition on the 🎾 read or a push = a rule change (Rule #10); a cradle-squeeze push = a ninth keep-set kind.",
    "5 Which 'had highs' — H1 primary by my reading; 'closed at the highs' / 52-week high = a NEW variant (one more trial).",
    "6 The 12:00 boundary and K4_HF_BASE_MIN (6 bars) as the cradle base minimum — reused constants; another clock = his number.",
    "7 SI bands on the tab — the measured tercile cut vs the chip's SI_HIGH_PCT / SI_ELEV_PCT heuristics; which basis first.",
    "8 Cost line when the two cost models disagree in sign on sub-$1 names.",
    "9 📌/🎪 ADD names — excluding them from any list = a gate change.",
    "10 Fallback runtime — the api-container /tmp route if the throwaway-container key recipe is not acceptable.",
    "11 Float freshness — a freshness cap = his number; this study prints the age and cuts nothing.",
    "12 If the OOS half is too small — widening the window or pooling IS+OOS for the word = a gate change.",
]


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════ render ═══
def _f(v, dp=2, pct=False) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return f"{v:,}"
    try:
        s = f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return str(v)
    return s + (" %" if pct else "")


def _ci(b) -> str:
    if not b or b.get("mean") is None:
        return "n/a"
    return f"{_f(b['mean'])} [{_f(b.get('lo'))}, {_f(b.get('hi'))}] (sym [{_f(b.get('lo_sym'))}, {_f(b.get('hi_sym'))}])"


def render(results: dict) -> str:
    p = results["primary"]
    c = results["cells"][PRIMARY]
    m = results["meta"]
    L = []
    L.append(f"# SI × D-1 highs × cradle — second-half squeeze study ({m['as_of']})")
    L.append("")
    L.append(f"**Verdict (C01 = H1 | CRA | % of float | 16:00 exit, OOS date half): {p['verdict']}** — PROVISIONAL, "
             "post-hoc (the thesis came from watching AKAN on 2026-11-17; 11-17 is OUT of every cell; the IS/OOS halves "
             "sit inside the window).")
    L.append("")
    L.append("## The ask (verbatim)")
    L.append("")
    L.append("> Can you do analysis for me if there are cetrain stocks with short interest  on average of certain "
             "percentage.. Previous day had highs..  Then they look like cradle pattern, they grow immensely EOD. Due to "
             "short squeeze..  I think this is a thing with reversal squeeze but they would usualy grow back second half "
             "of the day if they thesis checks out I want you build a new tab but do evaluate this one some previous "
             "stocks please")
    L.append("")
    cnt = m.get("counts") or {}
    L.append("## What was measured")
    L.append("")
    w = m["window"]
    L.append(f"- Window: {w['sessions']} sessions {w['from']} → {w['to']} (IS to {w['is_to']}, OOS from {w['oos_from']}).")
    L.append(f"- Universe {cnt.get('universe')} names (board ∩ U {cnt.get('board_in_universe')}); units "
             f"{cnt.get('units_total')}, with bars {cnt.get('units_with_bars')}, with point-in-time SI "
             f"{cnt.get('units_si')}; H1/H2/H3 {cnt.get('units_H1')}/{cnt.get('units_H2')}/{cnt.get('units_H3')}; "
             f"cradle CRA {cnt.get('cradle_CRA')}, CRB {cnt.get('cradle_CRB')}.")
    L.append(f"- Excluded: {json.dumps(cnt.get('out_reasons'), sort_keys=True)}; universe drops "
             f"{json.dumps(cnt.get('excluded'), sort_keys=True)}.")
    L.append(f"- Float above shares out (dropped): {', '.join(cnt.get('float_exceeds_shares_out_names') or []) or 'none'}"
             f"; of them on the board: {', '.join(cnt.get('float_exceeds_shares_out_board') or []) or 'none'}.")
    dc = cnt.get("daily_coverage") or {}
    if dc:
        L.append(f"- Daily bars (price_cache), correcting the design §1.3 sentence ('650 of the 651 universe names have "
                 f"251 daily bars'): over the {dc.get('names')} streamed names the longest frame is {dc.get('max_bars')} "
                 f"bars ({dc.get('names_at_max_bars')} name(s)); no price_cache doc: "
                 f"{', '.join(dc.get('no_price_cache') or []) or 'none'}; frame ends before the window: "
                 f"{', '.join(dc.get('ends_before_window') or []) or 'none'}; ≤ K8_HISTORY_SESSIONS bars: "
                 f"{dc.get('le_lookback')} names; {dc.get('names_losing_units_no_d1_bar')} names lose ≥ 1 unit to "
                 f"no_d1_bar ({dc.get('units_no_d1_bar')} units).")
    mdv = (m.get("cost") or {}).get("mdv20") or {}
    if mdv:
        L.append(f"- {mdv.get('bars')}-day median $ volume over the {mdv.get('n_trade_units')} confirmed-trade units: "
                 f"median {_f(mdv.get('median'), 0)}, min {_f(mdv.get('min'), 0)}, max {_f(mdv.get('max'), 0)} "
                 "(printed; the 1 % cap is a size rule, not applied).")
    L.append(f"- {results['survivorship']['text']}")
    L.append(f"- {results['basis_note']['text']} {results['basis_note']['cache_mixed_basis_finding']}.")
    fa = m.get("float_age") or {}
    L.append(f"- Float age (days): median {_f(fa.get('median_d'), 0)}, p90 {_f(fa.get('p90_d'), 0)}, max "
             f"{_f(fa.get('max_d'), 0)}, older than {FLOAT_AGE_DAYS} d: {fa.get('n_over_60d')}.")
    if (m.get("stride") or 1) > 1:
        L.append(f"- SMOKE: every {m['stride']}th name — numbers never quoted.")
    L.append("")
    L.append("## Primary cell C01 — gate table (OOS; pooled twin beside)")
    L.append("")
    L.append("| gate | OOS | pooled |")
    L.append("|---|---|---|")
    t3o, t3p = c["T3"]["X16"]["oos"], c["T3"]["X16"]["pooled"]
    do, dpool = c["diff"]["X16"]["oos"], c["diff"]["X16"]["pooled"]
    L.append(f"| T3 net % / trade, 16:00 | {_ci(t3o['net_pct'])} | {_ci(t3p['net_pct'])} |")
    L.append(f"| T3 stop-out rate · R median · win rate | {_f(t3o['stop_rate'])} · {_f(t3o['R']['median'])} · "
             f"{_f(t3o['win_rate'])} | {_f(t3p['stop_rate'])} · {_f(t3p['R']['median'])} · {_f(t3p['win_rate'])} |")
    L.append(f"| T3 − T1 | {_ci(do)} | {_ci(dpool)} |")
    L.append(f"| n T3 / dates · n T1 / dates | {t3o['n']} / {t3o['n_dates']} · {c['T1']['X16']['oos']['n']} / "
             f"{c['T1']['X16']['oos']['n_dates']} | {t3p['n']} / {t3p['n_dates']} · {c['T1']['X16']['pooled']['n']} / "
             f"{c['T1']['X16']['pooled']['n_dates']} |")
    pm = c["placebo"]["matched"]
    L.append(f"| placebo beaten (T3 / diff) | {_f(pm['T3'].get('beat'))} / {_f(pm['diff'].get('beat'))} | "
             f"{_f(c['placebo_pooled']['matched']['T3'].get('beat'))} |")
    sh = c["shuffle"]
    gate_txt = "gate active" if sh.get("gate_active") else f"n/a: {sh.get('n_dates_shuffled')} dates < MIN_BUCKET_N"
    L.append(f"| SI shuffle p | {_f(sh.get('p'))} ({gate_txt}) | |")
    ds = c["dsr"]
    L.append(f"| DSR gate (N) · naive (N) | {_f(ds.get('dsr'))} ({ds.get('N')}) · {_f(ds.get('dsr_naive'))} "
             f"({ds.get('N_naive')}) | |")
    L.append(f"| symbol halves replicate | {_f(c['oos_symbols'].get('replicates'))} | |")
    L.append("")
    L.append("Gates: " + ", ".join(f"{k} = {v}" for k, v in p["gates"].items()))
    L.append("")
    L.append("## All 18 cells (16:00 exit, OOS date half)")
    L.append("")
    L.append("| cell | H | cradle | basis | T3 net % [CI] | stop-out | T1 net % | T3 − T1 [CI] | word | placebo T3 "
             "matched / unmatched | shuffle p | DSR gate / naive |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for cid, h, cr, basis in cell_ids():
        cc = results["cells"][cid]
        a, b, d = cc["T3"]["X16"]["oos"], cc["T1"]["X16"]["oos"], cc["diff"]["X16"]["oos"]
        L.append(f"| {cid} | {h} | {cr} | {basis} | {_f(a['net_pct']['mean'])} [{_f(a['net_pct']['lo'])}, "
                 f"{_f(a['net_pct']['hi'])}] n {a['n']} | {_f(a['stop_rate'])} | {_f(b['net_pct']['mean'])} | "
                 f"{_f(d['mean'])} [{_f(d['lo'])}, {_f(d['hi'])}] | {d.get('word')} | "
                 f"{_f(cc['placebo']['matched']['T3'].get('beat'))} / {_f(cc['placebo']['unmatched']['T3'].get('beat'))}"
                 f" | {_f(cc['shuffle'].get('p'))} | {_f(cc['dsr'].get('dsr'))} / {_f(cc['dsr'].get('dsr_naive'))} |")
    L.append("")
    L.append("## What percentage (the T3 cut, IS cutpoints)")
    L.append("")
    for basis in BASES:
        bb = results["buckets"][basis]
        unit = "days to cover" if basis == "dtc" else "%"
        cut = (bb.get("terciles_is") or [None, None])[-1]
        cid = bb["source_cell"]
        t3 = results["cells"][cid]["T3"]["X16"]["oos"]["net_pct"]
        L.append(f"- {basis}: T3 = above {_f(cut)} {unit} → OOS net {_ci(t3)}")
    L.append("")
    L.append("## The simpler noon question (12:00 entry, no stop; (1)+(2) units)")
    L.append("")
    nb = results["descriptive"]["noon"]["by_h"]
    for h in HS:
        pf = nb[h]["pct_float"]
        L.append(f"- {h} % of float: T3 16:00 {_ci(pf['T3']['X16'])} · 20:00 {_ci(pf['T3']['X20'])} · T1 16:00 "
                 f"{_ci(pf['T1']['X16'])} · H-day minus same-name non-H day {_f(nb[h]['vs_no_h_paired'].get('mean'))} "
                 f"[{_f(nb[h]['vs_no_h_paired'].get('lo'))}, {_f(nb[h]['vs_no_h_paired'].get('hi'))}]")
    L.append("")
    L.append("## AKAN + GP sanity rows (2026-11-17, out of every cell)")
    L.append("")
    for sym in SANITY:
        s = (results.get("sanity") or {}).get(sym)
        if not s:
            L.append(f"- {sym}: no snapshot")
            continue
        si = s.get("si") or {}
        h = s.get("h") or {}
        cra = (s.get("cradle") or {}).get("CRA") or {}
        tr = (s.get("trade") or {}).get("CRA") or {}
        rp = s.get("replay") or {}
        L.append(f"- {sym}: SI {si.get('settlement')} (published {si.get('published_on')}) "
                 f"{_f(si.get('pct_float'))} % of today's float, {_f(s.get('pct_float_si_doc'))} % of the SI-doc float, "
                 f"{_f(si.get('pct_so'))} % of shares out, dtc {_f(si.get('dtc'))}, suspect {si.get('float_suspect')}; "
                 f"D-1 o {_f(h.get('d1_open'))} h {_f(h.get('d1_high'))} l {_f(h.get('d1_low'))} c {_f(h.get('d1_close'))};"
                 f" H1/H2/H3 {h.get('H1')}/{h.get('H2')}/{h.get('H3')}; seam {(s.get('seams') or {}).get('check')}; "
                 f"CRA {cra.get('t')} low {_f(cra.get('cradle_low'))}; entry {_f(tr.get('e'))} X16 "
                 f"{_f((tr.get('X16') or {}).get('net_pct'))} % X20 {_f((tr.get('X20') or {}).get('net_pct'))} %; "
                 f"🎾 replay armed {rp.get('first_armed_t')} trigger {rp.get('armed_trigger')} stop {rp.get('armed_stop')};"
                 f" board {json.dumps(s.get('board'), sort_keys=True, default=str)}")
    L.append("")
    L.append("## 🎾 reversal squeeze overlap")
    L.append("")
    L.append(f"- board: {json.dumps(results['overlap']['board'], sort_keys=True)}")
    L.append(f"- replay (not the pass): {json.dumps(results['overlap']['replay'], sort_keys=True)}")
    L.append("")
    L.append("## Costs sensitivity (C01 T3 OOS, 16:00)")
    L.append("")
    L.append(f"- 30 bps / side net {_f(t3o['net_pct']['mean'])} % · sx (10 bps + $0.01/share) "
             f"{_f(t3o['net_pct_sx_mean'])} % · gross {_f(t3o['gross_pct_mean'])} %")
    L.append("")
    L.append("## Not done")
    L.append("")
    L.append("- No tab, no push, no gate, no default changed. No point-in-time float. No sealed forward read.")
    csw = (results.get("coverage") or {}).get("cache_side_writes") or {}
    cov = results.get("coverage") or {}
    if csw:
        fw = csw.get("snapshot_fetched_at_et") or {}
        L.append(f"- intraday_cache side-writes {'ON' if csw.get('enabled') else 'OFF'}: {csw.get('written')} docs "
                 f"inserted ($setOnInsert, only (symbol, date) pairs with no doc; skipped existing "
                 f"{csw.get('skipped_existing')}, today {csw.get('skipped_today')}); intraday_cache "
                 f"{cov.get('intraday_cache_before')} → {cov.get('intraday_cache_after')}; snapshots fetched "
                 f"{fw.get('first')} → {fw.get('last')} ET. Keep or purge = HIS CALL #2a.")
    for d in results.get("deviations") or []:
        L.append(f"- deviation: {d}")
    L.append("")
    L.append("## HIS CALL")
    L.append("")
    for h in results.get("his_calls") or []:
        L.append(f"- {h}")
    L.append("")
    L.append("## TAB SPEC (a spec, not a build)")
    L.append("")
    cut = (results["buckets"]["pct_float"].get("terciles_is") or [None, None])[-1]
    L.append(f"🛏 Cradle squeeze = a display-only sub: today's names with float ≤ {GC.K8_MAX_FLOAT:,} (float not suspect), "
             "the point-in-time 🩳 SI via short_interest.read.si_block (both % + days to cover), the D-1 'had highs' "
             "variant that held, and the cradle state (forming / confirmed / none). Measured line it MUST serve: "
             f"\"SI T3 (≥ {_f(cut)} % of float) cradle days, OOS: net {_f(t3o['net_pct']['mean'])} % "
             f"[{_f(t3o['net_pct']['lo'])}, {_f(t3o['net_pct']['hi'])}] to 16:00, stop-out {_f(t3o['stop_rate'])}, "
             f"n {t3o['n']} on {t3o['n_dates']} dates — {p['verdict']}\". Only a POSITIVE (or his word on a NULL) lists "
             "by default.")
    L.append("")
    L.append("## Run recipe + shas")
    L.append("")
    L.append(f"- design sha256 {m.get('design_sha256')}; script sha256 {m.get('script_sha256')}; head "
             f"{m.get('worktree_head')}")
    L.append(f"- `python {SCRIPT} fetch|analyze|render` (see the design §3.8).")
    for pn in results.get("pins") or []:
        L.append(f"- pin {'OK' if pn.get('ok') else 'FAIL'}: {pn.get('pin')}")
    return "\n".join(L) + "\n"


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════ CLI ═══
def _db():
    from pymongo import MongoClient
    return MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"))[os.getenv("MONGO_DB", "cheetah")]


def _now_et() -> datetime:
    return datetime.now(ET)


def _write_json(p, obj):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(dumps(obj) + "\n", encoding="utf-8")
    tmp.replace(p)


def _universe_doc(U: Universe) -> dict:
    return {"names": {k: U[k] for k in sorted(U)}, "excluded": [list(x) for x in U.excluded]}


def cmd_fetch(a) -> int:
    as_of = date.fromisoformat(a.as_of)
    window = sessions_window(as_of, a.sessions)
    out = Path(a.out)
    (out / "bars").mkdir(parents=True, exist_ok=True)
    db = _db()
    U = universe(db, as_of=as_of)
    names = stride_names(sorted(U), a.stride, a.offset)
    fetch_list = sorted(set(names) | {s for s in SANITY if s in U})
    mpath = out / "fetch_manifest.json"
    prev = json.loads(mpath.read_text()) if (a.resume and mpath.exists()) else {}
    si_path, sp_path = out / "si_history.json", out / "splits.json"
    si_hist = json.loads(si_path.read_text()) if (a.resume and si_path.exists()) else {}
    splits = json.loads(sp_path.read_text()) if (a.resume and sp_path.exists()) else {}
    coll = DT._get_mongo_coll()
    man = {"study": STUDY, "as_of": as_of.isoformat(), "sessions": a.sessions,
           "window": [d.isoformat() for d in window], "universe_count": len(U),
           "universe": _universe_doc(U), "names": names, "fetch_list": fetch_list, "stride": a.stride,
           "offset": a.offset, "constants": CONSTANTS, "analyst": ANALYST, "per_name": prev.get("per_name", {}),
           "resumed": bool(prev), "stopped_early_at": None, "cache_write": not a.no_cache_write,
           "intraday_cache_before": prev.get("intraday_cache_before",
                                             coll.estimated_document_count() if coll is not None else None)}
    from_day, since_iso = RX.prev_market_day(window[0]), window[0].replace(year=window[0].year - 1).isoformat()
    pacer = Pacer(FETCH_GAP_SEC)
    today_et = DT._today_et()
    requeue = []

    def one(sym: str, last_try: bool) -> Optional[str]:
        rec = {"si_calls": 0, "split_calls": 0, "minute_calls": 0, "pages": 0, "failed": None}
        pacer.wait()
        si_hist[sym] = fetch_si_history(sym)
        rec["si_calls"] = 1
        rec["si_rows"] = len(si_hist[sym])
        pacer.wait()
        splits[sym] = fetch_splits(sym, since_iso)
        rec["split_calls"] = 1
        rec["split_ok"] = splits[sym] is not None
        pacer.wait()
        DT.clear_fetch_failed()
        df = fetch_minutes(sym, from_day, as_of)
        rec["minute_calls"] = 1
        if df is None and DT.last_fetch_failed():
            rec["failed"] = "minute_provider_failed"
            man["per_name"][sym] = rec
            return "requeue" if not last_try else "failed"
        n = 0 if df is None else len(df)
        rec["pages"] = max(1, -(-n // MASSIVE_PAGE_BARS)) if n else 1
        for _ in range(rec["pages"] - 1):
            pacer.wait()
        by_day = split_days(df)
        rec.update(snapshot_write(out / "bars" / f"{sym}.json.gz", sym, by_day, _now_et().strftime("%Y-%m-%d %H:%M")))
        if not a.no_cache_write:
            rec["docs_written"], rec["skipped_existing"], rec["skipped_today"] = cache_side_write(
                sym, by_day, today_et, coll)
        man["per_name"][sym] = rec
        return None

    for sym in fetch_list:
        if a.resume and (out / "bars" / f"{sym}.json.gz").exists():
            continue
        if fetch_stop_due(_now_et()):
            man["stopped_early_at"] = _now_et().strftime("%Y-%m-%d %H:%M")
            break
        r = one(sym, False)
        if r == "requeue":
            requeue.append(sym)
        _write_json(si_path, si_hist)
        _write_json(sp_path, splits)
        _write_json(mpath, man)
        print(f"fetch {sym} {man['per_name'].get(sym)}", flush=True)
    if man["stopped_early_at"] is None:
        for sym in requeue:
            if fetch_stop_due(_now_et()):
                man["stopped_early_at"] = _now_et().strftime("%Y-%m-%d %H:%M")
                break
            one(sym, True)
            print(f"requeue {sym} {man['per_name'].get(sym)}", flush=True)
    man["requeued"] = requeue
    man["failed"] = sorted(s for s, r in man["per_name"].items() if r.get("failed"))
    man["intraday_cache_after"] = coll.estimated_document_count() if coll is not None else None
    _write_json(si_path, si_hist)
    _write_json(sp_path, splits)
    _write_json(mpath, man)
    print(f"fetch done: {len(man['per_name'])} names, failed {man['failed']}, stopped {man['stopped_early_at']}",
          flush=True)
    return 0


def _stop(msg: str) -> int:
    print(f"STOP: {msg}", flush=True)
    return EXIT_PIN


def cmd_analyze(a) -> int:
    out = Path(a.out)
    as_of = date.fromisoformat(a.as_of)
    window = sessions_window(as_of, a.sessions)
    shaf = out / "design.sha256"
    if not a.design or not Path(a.design).exists() or not shaf.exists():
        return _stop("design file or design.sha256 missing")
    dsha = _sha256_file(a.design)
    if shaf.read_text().split()[0] != dsha:
        return _stop("design sha256 mismatch")
    man = json.loads((out / "fetch_manifest.json").read_text())
    if json.loads(dumps(CONSTANTS)) != man.get("constants"):
        return _stop("CONSTANTS differ from the fetch manifest")
    if man.get("window") != [d.isoformat() for d in window]:
        return _stop("window differs from the fetch manifest")
    bars_dir = out / "bars"
    for p in sorted(bars_dir.glob("*.json.gz")):
        if snapshot_basis(p) != SNAPSHOT_BASIS:
            return _stop(f"{p.name}: snapshot basis is not {SNAPSHOT_BASIS!r}")
    db = _db()
    Ulive = universe(db, as_of=as_of)
    if len(Ulive) != man["universe_count"]:
        return _stop(f"universe count {len(Ulive)} != manifest {man['universe_count']}")
    U = Universe(man["universe"]["names"])
    U.excluded = [tuple(x) for x in man["universe"]["excluded"]]
    names = man["names"]
    if names != stride_names(sorted(U), man.get("stride") or 1, man.get("offset") or 0):
        return _stop("strided names differ from the manifest")
    si_hist = json.loads((out / "si_history.json").read_text())
    splits = json.loads((out / "splits.json").read_text())
    stream = sorted(set(names) | {s for s in SANITY if s in U})
    frames = PR.bulk_cached_frames(stream)
    daily = {s: daily_frame(frames, s) for s in stream}
    stores = load_stores(db)
    si_docs = {s: db[SIC.SI_COLL].find_one({"_id": s}) or {} for s in SANITY}

    fetched_at = []

    def snap(sym):
        p = bars_dir / f"{sym}.json.gz"
        if not p.exists():
            return None
        mo = {}
        days = snapshot_read(p, sym, mo)
        if mo.get("fetched_at_et"):
            fetched_at.append(mo["fetched_at_et"])
        return days

    ledger = a.ledger or str(out.parent / "strategy_lab_ledger.json")
    prior = prior_srs(ledger)
    deviations = []
    if not prior:
        deviations.append(f"prior DSR list empty (ledger not found at {ledger})")
    if man.get("stride") and man["stride"] > 1:
        deviations.append(f"SMOKE run: every {man['stride']}th name from offset {man.get('offset') or 0}")
    if man.get("cache_write"):
        deviations.append("the fetch ran with intraday_cache side-writes ON although HIS CALL #2a lists that choice as "
                          "his — the written docs are counted under coverage.cache_side_writes (keep or purge = his)")
    pn = man.get("per_name") or {}
    coverage = {"snapshot": {"names": len(list(bars_dir.glob('*.json.gz'))),
                             "days": sum(int(r.get("days") or 0) for r in pn.values()),
                             "bars": sum(int(r.get("bars") or 0) for r in pn.values()),
                             "bytes_gz": sum(int(r.get("bytes_gz") or 0) for r in pn.values())},
                "fetch": {"si_calls": sum(int(r.get("si_calls") or 0) for r in pn.values()),
                          "split_calls": sum(int(r.get("split_calls") or 0) for r in pn.values()),
                          "minute_calls": sum(int(r.get("minute_calls") or 0) for r in pn.values()),
                          "pages": sum(int(r.get("pages") or 0) for r in pn.values()),
                          "http_429": None,
                          "http_429_note": "not counted: daytrading.data keeps its 429 count internal; a 429 cap "
                                           "surfaces as a requeued / failed name",
                          "split_failed": sorted(s for s, r in pn.items() if r.get("split_ok") is False),
                          "requeued": man.get("requeued"), "failed": man.get("failed"),
                          "stopped_early_at": man.get("stopped_early_at"), "resumed": man.get("resumed")},
                "cache_side_writes": {"enabled": man.get("cache_write"),
                                      "written": sum(int(r.get("docs_written") or 0) for r in pn.values()),
                                      "skipped_existing": sum(int(r.get("skipped_existing") or 0) for r in pn.values()),
                                      "skipped_today": sum(int(r.get("skipped_today") or 0) for r in pn.values())},
                "intraday_cache_before": man.get("intraday_cache_before"),
                "intraday_cache_after": man.get("intraday_cache_after")}
    inp = {"as_of": as_of, "window": window, "universe": U, "names": names, "daily": daily, "si_hist": si_hist,
           "splits": splits, "snapshot": snap, "stores": stores, "prior": prior, "si_docs": si_docs,
           "stride": man.get("stride"), "coverage": coverage, "deviations": deviations,
           "meta": {"design_sha256": dsha, "script_sha256": _sha256_file(__file__), "worktree_head": a.head}}
    t0 = time.monotonic()
    res, events = analyze_core(inp)
    csw = res["coverage"].setdefault("cache_side_writes", {})
    csw["snapshot_fetched_at_et"] = {"first": min(fetched_at) if fetched_at else None,
                                     "last": max(fetched_at) if fetched_at else None}
    pl = pins(res, events, stores)
    res["pins"] = [{"pin": k, "ok": bool(v)} for k, v in pl]
    for k, v in pl:
        print(f"pin {'OK ' if v else 'FAIL'} {k}", flush=True)
    _write_json(out / "events.json", events)
    _write_json(out / "results.json", res)
    print(f"analyze done in {time.monotonic() - t0:.0f} s: verdict {res['primary']['verdict']}", flush=True)
    if not all(v for _, v in pl):
        return _stop("a pin failed (results.json written with the pins block)")
    return 0


def cmd_render(a) -> int:
    res = json.loads((Path(a.out) / "results.json").read_text())
    Path(a.report).write_text(render(res), encoding="utf-8")
    print(f"wrote {a.report}", flush=True)
    return 0


def cmd_selftest(a) -> int:
    import subprocess
    t = Path(__file__).resolve().parents[1] / "tests" / "test_si_cradle_squeeze_study.py"
    return subprocess.call([sys.executable, "-m", "pytest", str(t), "-q", "-p", "no:cacheprovider"],
                           cwd=str(t.parents[1]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="si_cradle_squeeze_study")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "analyze"):
        s = sub.add_parser(name)
        s.add_argument("--as-of", default=AS_OF)
        s.add_argument("--sessions", type=int, default=WINDOW_SESSIONS)
        s.add_argument("--out", required=True)
        if name == "fetch":
            s.add_argument("--stride", type=int, default=1)
            s.add_argument("--offset", type=int, default=0)
            s.add_argument("--resume", action="store_true")
            s.add_argument("--no-cache-write", action="store_true")
        else:
            s.add_argument("--design", required=True)
            s.add_argument("--ledger", default=None)
            s.add_argument("--head", default=None)
    r = sub.add_parser("render")
    r.add_argument("--out", required=True)
    r.add_argument("--report", required=True)
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    return {"fetch": cmd_fetch, "analyze": cmd_analyze, "render": cmd_render, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
