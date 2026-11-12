"""Shadow day tags (rec157 WP-2, 2026-11-11) — READ-ONLY container probe. Prints ONE JSON `inputs` blob of RAW
inputs; the tag formulas live in shadow_day_tags_lib.py on the host. No write anywhere, no provider fetch, no broker.

Imports: pymongo (plain finds), chart_maps.gajjala store / variant / ledger / constants / audited_rules (the served
🏁 row pipeline, exactly as the study's dump_rows.py:95-110 builds it), orderflow.signals.ema (the house EMA, as the
study), sepa.prices `_cut_foreign_head` / `_drop_phantom_tail` (cached_frame_meta's own reshaping, applied to the
probe's OWN find of price_cache), market_hours.reminder.is_market_day (the market-day engine). NO trading.*, NO
daytrading.* (data.py imports massive_keys and its Mongo helper runs create_index), NO provider client.
GG_LOSS_RISK_CUT and ET_RTH_OPEN are read BY NAME with `ast`.

No create_index either (refix 2026-11-12, as track_record_snapshot_probe.py does): main() pre-sets
`portfolio.store._db` and `sepa.prices._mongo_coll` to the probe's own handle, so the house connection helpers
(`_get_db` → portfolio_holdings.create_index, `_get_mongo` → price_cache.create_index) return early and never run.

Run (the CLI does this — ONE exec per run; never docker cp into /app):
  docker exec -i -w /app cheetah-market-app-api-1 python - [--sessions D1,D2] < shadow_day_tags_probe.py
`--sessions` limits the QQQ / IWM minute bars to those sessions (passes, rows and frames are always whole)."""
import ast
import json
import math
import os
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from pymongo import MongoClient

from chart_maps.gajjala import audited_rules as AR
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as L
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from market_hours.reminder import is_market_day
from orderflow.signals import ema
from sepa import prices as P

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
FIRST_SESSION = date(2026, 10, 13)          # the study's first session (day_probe.py:20)
PRE_CUT = dtime(9, 29)                      # the study's :32 — GD6b_pre's pass read
READ_CUTS = (PRE_CUT, AR.T2_FIRST_HOUR_END_ET)
CLOSE_ET = dtime(16, 0)                     # the regular close; + ledger.SETTLE = a closed session
INDEX_SYMS = ("QQQ", "IWM")
PILLARS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA")   # day_probe.py:71 — MINE
IWM_FRAME_BARS = 320                        # day_probe.py:44 `df.iloc[-320:]`
IWM_ROWS_OUT = 60
PILLAR_MIN_BARS = 60                        # day_probe.py:80
PILLAR_ROWS_OUT = 40                        # day_probe.py:112
ROW_KEYS = ("id", "date", "symbol", "setup", "kind", "line", "at_utc", "trigger", "stop", "thin", "plan")
CELL_KEYS = ("fill_t", "exit_t", "end_t", "outcome", "fill_px", "close_pct")
APP = os.getenv("CHEETAH_APP_DIR", "/app")


def ast_constant(path: str, name: str):
    """The module-level literal `name = …` of `path`, read with ast (no import). A `time(h, m)` / `dtime(h, m)` call
    reads as "HH:MM". Raises KeyError when absent."""
    tree = ast.parse(open(path).read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    v = node.value
                    if isinstance(v, ast.Constant):
                        return v.value
                    if isinstance(v, ast.Call) and len(v.args) == 2 and all(isinstance(a, ast.Constant) for a in v.args):
                        return "%02d:%02d" % (v.args[0].value, v.args[1].value)
    raise KeyError(name)


def market_days(first: date, last: date) -> list:
    """Every market day first … last (is_market_day at noon ET of the day)."""
    out, d = [], first
    while d <= last:
        if is_market_day(datetime.combine(d, dtime(12, 0), tzinfo=ET)):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def last_closed(sessions: list, now: datetime):
    """The latest session whose 16:00 ET close is past by at least ledger.SETTLE."""
    done = [d for d in sessions if datetime.combine(date.fromisoformat(d), CLOSE_ET, tzinfo=ET) + L.SETTLE <= now]
    return done[-1] if done else None


def iso(x):
    return x.isoformat() if isinstance(x, datetime) else x


def scrub(x):
    """NaN / inf → None, datetimes → iso strings."""
    if isinstance(x, float):
        return None if (x != x or math.isinf(x)) else x
    if isinstance(x, datetime):
        return x.isoformat()
    if isinstance(x, dict):
        return {str(k): scrub(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [scrub(v) for v in x]
    return x


def cell(c):
    return {k: iso(c.get(k)) for k in CELL_KEYS} if isinstance(c, dict) else None


def gg5_rows(now: datetime, today: date):
    """dump_rows.py:95-110, 127-136 for GG5, reduced to the keys the formulas read. (rows, last graded_at)."""
    v = V.GG5
    s = ST.for_variant(v)
    ds = sorted(set(s.alert_dates() or []) | set(s.ledger_dates() or []))
    rows = L.rows_for(ds, s, variant=v)
    docs = {d.get("_id"): d for d in (s.ledger_docs(ds) or []) if isinstance(d, dict)}
    facts, built = [], []
    for row in rows:
        doc = docs.get(row["id"]) or {}
        same = doc.get("same") if isinstance(doc.get("same"), dict) else None
        nxt = doc.get("next") if isinstance(doc.get("next"), dict) else None
        facts.append(L.trade_facts(row, same, nxt, group=L.dup_group(row), rank=L._setup_rank(row["setup"])))
        cs = L._cell(row, "same", same, False, now, today, False)["state"]
        cn = L._cell(row, "next", nxt, False, now, today, False)["state"]
        built.append((row, same, nxt, cs, cn))
    dups = L.dedupe_trades([f for f in facts if f])
    out = []
    for row, same, nxt, cs, cn in built:
        r = {k: iso(row.get(k)) for k in ROW_KEYS}
        r.update({"same": cell(same), "next": cell(nxt), "state_same": cs, "state_next": cn,
                  "bucket": L.bucket_of(cs, cn, True), "dup_of": dups.get(row["id"])})
        out.append(r)
    graded = [str(d.get("graded_at")) for d in docs.values() if d.get("graded_at")]
    return out, (max(graded) if graded else None)


def hm_of_id(pid: str):
    parts = str(pid).split("|")
    if len(parts) < 2 or len(parts[1]) < 5 or parts[1][2] != ":":
        return None
    try:
        return dtime(int(parts[1][:2]), int(parts[1][3:5]))
    except ValueError:
        return None


def passes_of(db, sessions: list) -> tuple:
    """{session: {"09:29": pass | None, "10:30": pass | None}}: the LAST gajjala_passes doc whose _id hh:mm ≤ the read
    time (ties by `at`, then _id — none in the study's 22 sessions), as {id, date, at, strip: {n_population}}. The
    pointers ("latest", "latest_cron", any doc with `pointer`) are never a pass."""
    out, last_id, last_at = {}, None, None
    for d in sessions:
        docs = []
        for p in db[ST.PASSES].find({"date": d}, {"_id": 1, "date": 1, "at": 1, "strip.n_population": 1,
                                                    "pointer": 1}):
            pid = p.get("_id")
            if pid in ST.POINTERS or "pointer" in p:
                continue
            hm = hm_of_id(pid)
            if hm is None:
                continue
            strip = p.get("strip")
            docs.append((hm, str(iso(p.get("at"))), str(pid), {
                "id": str(pid), "date": p.get("date"), "at": iso(p.get("at")),
                "strip": {"n_population": strip.get("n_population")} if isinstance(strip, dict) else None}))
            if last_at is None or str(iso(p.get("at"))) > last_at:
                last_at, last_id = str(iso(p.get("at"))), str(pid)
        docs.sort(key=lambda x: (x[0], x[1], x[2]))
        out[d] = {}
        for cut in READ_CUTS:
            ps = [x[3] for x in docs if x[0] <= cut]
            out[d][cut.strftime("%H:%M")] = ps[-1] if ps else None
    return out, last_id


def bar_t(ts):
    if isinstance(ts, datetime):
        t = ts
    else:
        try:
            t = datetime.fromisoformat(str(ts).replace(" ", "T").replace("Z", "+00:00"))
        except ValueError:
            return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t


def index_intraday(db, sessions: list) -> dict:
    """{"SYM|date": [[ts_utc, o, h, l, c, v, session], …] | None}: rth bars that CLOSED by 10:30 ET (start + 1 min ≤
    10:30), read from intraday_cache with a plain find (no fetch). An absent doc → None."""
    out = {}
    for s in INDEX_SYMS:
        for d in sessions:
            doc = db.intraday_cache.find_one({"symbol": s, "date": d}, {"bars": 1})
            bs = (doc or {}).get("bars") or []
            cut = datetime.combine(date.fromisoformat(d), AR.T2_FIRST_HOUR_END_ET, tzinfo=ET)
            keep = []
            for b in bs:
                t = bar_t(b.get("ts_utc"))
                if b.get("session") != "rth" or t is None or t + timedelta(minutes=1) > cut:
                    continue
                keep.append([iso(b.get("ts_utc")), b.get("open"), b.get("high"), b.get("low"), b.get("close"),
                             b.get("volume"), b.get("session")])
            out["%s|%s" % (s, d)] = keep if doc and bs else None
    return out


def last_cache_date(db, sym: str):
    for doc in db.intraday_cache.find({"symbol": sym}, {"date": 1}).sort("date", -1).limit(1):
        return doc.get("date")
    return None


def frame_meta(db, symbol: str):
    """sepa.prices.cached_frame_meta read through the probe's OWN price_cache find_one (never `_get_mongo`, so never its
    create_index): {"frame": df, "cached_at": float} | None on the same rules (no doc / no bars / a non-numeric or
    bool cached_at / an empty frame), the same reshaping by import (`_cut_foreign_head`, `_drop_phantom_tail`). Pinned
    equal to cached_frame_meta by a repo test."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None
    try:
        doc = db.price_cache.find_one({"symbol": sym})
        if not doc:
            return None
        bars = doc.get("bars") or []
        cached_at = doc.get("cached_at")
        if not bars or isinstance(cached_at, bool) or not isinstance(cached_at, (int, float)):
            return None
        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
        df = P._drop_phantom_tail(P._cut_foreign_head(df, sym))
        if df is None or df.empty:
            return None
        return {"frame": df, "cached_at": float(cached_at)}
    except Exception:                                           # noqa: BLE001 — as cached_frame_meta: None
        return None


def iwm_daily(db) -> dict:
    """day_probe.py:37-44 + day_indicators.py:368-374: the house cache frame (a read), the last 320 bars, EMAs 9 / 21
    over those bars; rows [date, close, ema9, ema21] (the last IWM_ROWS_OUT)."""
    m = frame_meta(db, "IWM")
    if not m:
        return {"rows": None, "cached_at": None}
    df = m["frame"].sort_index().iloc[-IWM_FRAME_BARS:]
    c = df["close"].astype(float)
    e9, e21 = ema(c, 9), ema(c, 21)
    rows = [[i.date().isoformat(), float(c.iloc[k]), float(e9.iloc[k]), float(e21.iloc[k])]
            for k, i in enumerate(df.index)]
    return {"rows": rows[-IWM_ROWS_OUT:], "cached_at": m.get("cached_at")}


def pillars(db) -> tuple:
    """day_probe.py:76-112 for the eight pillars only: EMAs over the whole price_cache frame; rows [date, close, e9,
    e21, e50] (the last PILLAR_ROWS_OUT)."""
    out, cached = {}, {}
    for doc in db.price_cache.find({"symbol": {"$in": list(PILLARS)}}, {"symbol": 1, "bars": 1, "cached_at": 1}):
        sym = str(doc.get("symbol") or "").upper()
        bars = doc.get("bars") or []
        if sym not in PILLARS or len(bars) < PILLAR_MIN_BARS:
            continue
        try:
            df = pd.DataFrame(bars)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")[["open", "high", "low", "close", "volume"]].sort_index()
            df = df[~df.index.duplicated(keep="last")]
            close = df["close"].astype(float)
            e9, e21, e50 = ema(close, 9), ema(close, 21), ema(close, 50)
            ds = [i.date().isoformat() for i in df.index]
        except Exception:                                      # noqa: BLE001 — the study skips a bad doc too
            continue
        out[sym] = [[ds[i], float(close.iloc[i]), float(e9.iloc[i]), float(e21.iloc[i]), float(e50.iloc[i])]
                    for i in range(max(0, len(ds) - PILLAR_ROWS_OUT), len(ds))]
        cached[sym] = doc.get("cached_at")
    return out, cached


def main(argv: list) -> None:
    only = None
    if "--sessions" in argv:
        only = set(argv[argv.index("--sessions") + 1].split(","))
    now = datetime.now(UTC)
    today = now.astimezone(ET).date()
    db = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"))[os.getenv("MONGO_DB", "cheetah")]
    import portfolio.store as PS
    PS._db = db                          # ST reads through this handle; _get_db's create_index never runs
    P._mongo_coll = db.price_cache       # any sepa.prices read hits this handle; _get_mongo's create_index never runs
    sessions = market_days(FIRST_SESSION, today)
    try:
        rows, graded = gg5_rows(now, today)
        rows_err = None
    except Exception as exc:                                    # noqa: BLE001 — recorded, the tags read MISSING
        rows, graded, rows_err = None, None, repr(exc)[:300]
    passes, passes_last = passes_of(db, sessions)
    intra = index_intraday(db, [d for d in sessions if only is None or d in only])
    iwm = iwm_daily(db)
    pil, pil_cached = pillars(db)
    out = {
        "generated_utc": now.isoformat(), "today_et": today.isoformat(), "sessions": sessions,
        "last_closed_session": last_closed(sessions, now),
        "constants": {
            "T2_FIRST_HOUR_END_ET": AR.T2_FIRST_HOUR_END_ET.strftime("%H:%M"),
            "LEDGER_MIN_R_PCT": GC.LEDGER_MIN_R_PCT,
            "GG_LOSS_RISK_CUT": ast_constant(os.path.join(APP, "trading", "gajjala_entry.py"), "GG_LOSS_RISK_CUT"),
            "ET_RTH_OPEN": ast_constant(os.path.join(APP, "daytrading", "data.py"), "ET_RTH_OPEN"),
            "MEASURE_FLOOR_WEEKS": AR.MEASURE_FLOOR_WEEKS,
        },
        "gg5_rows": rows, "gg5_rows_error": rows_err,
        "passes": passes, "index_intraday": intra,
        "iwm_daily": iwm, "pillars": pil,
        "asof": {"gg5_last_graded_at": graded, "passes_last_id": passes_last,
                 "qqq_last_date": last_cache_date(db, "QQQ"), "iwm_last_date": last_cache_date(db, "IWM"),
                 "iwm_daily_last_date": (iwm["rows"] or [[None]])[-1][0], "iwm_daily_cached_at": iwm["cached_at"],
                 "pillars_last_date": {s: (r[-1][0] if r else None) for s, r in sorted(pil.items())},
                 "pillars_cached_at": pil_cached},
    }
    sys.stdout.write(json.dumps(scrub(out), sort_keys=True, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main(sys.argv[1:])
