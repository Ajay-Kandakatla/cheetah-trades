"""Shadow day tags (rec157 WP-2, 2026-11-11) — the pure library. RECORD ONLY: nothing served imports this file, nothing
here gates, mutes or pushes; no page shows a word of it.

Stdlib only, Python 3.9-safe (the host venv). The formulas are the study's, function for function:
/Users/ajay/clinet-test/eod-audits/research/2026-11-11_track_record_patterns/day_indicators.py (STUDY below, line
numbers of that file; sha256 9bef2f1b…0dcbc) and STUDY/analyze.py:48-74 (`trade_of`). The inputs are the raw blob
printed by shadow_day_tags_probe.py (a read-only container probe); every repo constant arrives in `inputs["constants"]`
BY NAME (T2_FIRST_HOUR_END_ET, GG_LOSS_RISK_CUT, LEDGER_MIN_R_PCT, ET_RTH_OPEN) — never retyped here.

A tag = {"status": "ok" | "missing", "on": bool | None, "value": …, "detail": {…}, "why": str | None, "asof": {…}}.
MISSING is never `on: False`.

The store (`day_tags.jsonl`, append-only) and its inputs files (`inputs/<run date>[.rN].json.gz`) — see
docs/gajjala/shadow_day_tags_2026_11_11.md.
"""
import gzip
import hashlib
import json
import math
import os
import tempfile
from collections import defaultdict
from datetime import date, datetime, time as dtime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
SCHEMA = 1

TAG_FORMS = ("GD3w_pre", "GD4_pre", "GD4_by1030", "GD6b_pre", "GD6b_by1030", "GD7_by1030", "LD3i_pre", "LD9_pre")
FORWARD_FROM = "2026-11-12"          # the first session after the study's last measured one (days.csv ends 11-11)
STALE_MIN, WEEK, TWO_WEEKS, PILLAR_WEAK_MIN = 30, 5, 10, 4        # STUDY :30, :34, :35, :47 — each tagged MINE there
GD6_MIN_HIST = 5                     # STUDY :338 `len(hist) >= 5` (an unnamed literal there) — MINE
GD3W_SHARE = 0.5                     # STUDY :276 `f / (f + h) > 0.5` — "5 sessions + 50 % MINE"
LD9_MIN_PILLARS = 6                  # STUDY :481 `None if n < 6` (an unnamed literal there) — MINE
PRE_CUT = (9, 29)                    # STUDY :32 — GD6b_pre's pass read: the last pass AT OR BEFORE 09:29 ET
GD4_PRE_CUT = (9, 30)                # STUDY IND :623 `gd4(d, dtime(9, 30))` — == daytrading.data.ET_RTH_OPEN (test pin)
PILLARS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA")   # STUDY day_probe.py:71 — MINE
INDEX_SYMS = ("QQQ", "IWM")          # STUDY :361 — GD7 reads both

# per tag-form: the THEIRS / MINE note of the study's IND row (STUDY :620-663), verbatim
SOURCE_TAGS = {
    "GD3w_pre": "5 sessions + 50 % MINE",
    "GD4_pre": "halving THEIRS; win reset MINE (lane HIS CALL #18)",
    "GD4_by1030": "halving THEIRS; win reset MINE",
    "GD6b_pre": "median + window MINE",
    "GD6b_by1030": "median + window MINE",
    "GD7_by1030": "both red MINE",
    "LD3i_pre": "9/21 THEIRS",
    "LD9_pre": "9/21 THEIRS; list + 4 MINE",
}
# per tag-form: the pages the study read it on (IND rows: primary + secondary; luk adds lukx, STUDY :874)
PAGES_BY_FORM = {
    "GD3w_pre": ("gg5", "gg1"), "GD4_pre": ("gg5", "gg1"), "GD4_by1030": ("gg5", "gg1"),
    "GD6b_pre": ("gg5", "gg1"), "GD6b_by1030": ("gg5", "gg1"), "GD7_by1030": ("gg5", "gg1"),
    "LD3i_pre": ("luk", "lukx", "gg5", "gg1"), "LD9_pre": ("luk", "lukx", "gg5", "gg1"),
}
READS = tuple((f, p) for f in TAG_FORMS for p in PAGES_BY_FORM[f])   # every (tag-form, page) read, in order

STORE_NAME = "day_tags.jsonl"
INPUTS_DIR = "inputs"


class StoreCorrupt(Exception):
    """The JSONL store does not read back as written: a line that does not parse, a cut last line, a rev gap."""


# ── time helpers (STUDY :64-79) ─────────────────────────────────────────────────────────────────────────────────────
def et_of(iso) -> Optional[datetime]:
    if not iso:
        return None
    s = str(iso).replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t.astimezone(ET)


def hm_of(text: str) -> tuple:
    """"10:30" → (10, 30)."""
    h, m = str(text).split(":")[:2]
    return int(h), int(m)


def hm_text(hm: tuple) -> str:
    return "%02d:%02d" % (hm[0], hm[1])


def at_cut(d: str, hm: tuple) -> datetime:
    """the aware instant of ET wall time hm on session d (STUDY :77-79)."""
    return datetime.combine(date.fromisoformat(d), dtime(hm[0], hm[1]), tzinfo=ET)


# ── the copied engines ──────────────────────────────────────────────────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (v != v or math.isinf(v)) else v


def risk_after_copy(risk_mult, pnl, cut) -> float:
    """trading.gajjala_entry.risk_after (:455-463), copied (that module imports broker code — STUDY no_trade_words.md
    :370): a loss multiplies by `cut` (GG_LOSS_RISK_CUT, by name in inputs), a win resets to 1, flat / unknown keeps."""
    m = _f(risk_mult)
    m = 1.0 if m is None else m
    p = _f(pnl)
    if p is None or p == 0:
        return m
    return float(Decimal(repr(float(m))) * Decimal(repr(float(cut)))) if p < 0 else 1.0


def trade_of(r: dict) -> Optional[dict]:
    """STUDY/analyze.py:48-74 verbatim logic: the served row → a trade dict, or None when it is never a counted trade
    (dup / no plan / no ring time)."""
    if r.get("dup_of") or r.get("plan") != "ok" or not r.get("at_utc"):
        return None
    sn, ss = r.get("state_next"), r.get("state_same")
    b = r.get("bucket")
    g = None
    if sn in ("win", "loss"):
        g = r.get("next")
    elif ss in ("win", "loss"):
        g = r.get("same")
    elif sn == "flat":
        g = r.get("next")
    elif ss == "open":
        g = r.get("same")
    t = {"row": r, "bucket": b, "thin": bool(r.get("thin")), "filled": b in ("win", "loss", "open", "flat"), "R": None}
    if t["filled"] and g and g.get("fill_px") is not None:
        fill, trig, stop = g["fill_px"], r["trigger"], r["stop"]
        unit = trig - stop
        if unit > 0:
            if b == "win":
                t["R"] = 1.0
            elif b == "loss":
                t["R"] = (stop - fill) / unit
            elif g.get("close_pct") is not None:
                t["R"] = fill * g["close_pct"] / 100 / unit
    return t


def upper_median(xs: list):
    """STUDY :341 `sorted(hist)[len(hist) // 2]` — the UPPER middle on an even count, not statistics.median."""
    return sorted(xs)[len(xs) // 2]


# ── tags ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def missing(why: str, asof=None) -> dict:
    return {"status": "missing", "on": None, "value": None, "detail": {}, "why": why, "asof": asof or {}}


def _ok(value, on: bool, detail: dict, asof: dict) -> dict:
    if isinstance(value, float) and (value != value or math.isinf(value)):
        return missing("non-finite value", asof)
    return {"status": "ok", "on": bool(on), "value": value, "detail": detail, "why": None, "asof": asof}


class _Ctx:
    """Everything compute() reads, built once per inputs blob."""

    def __init__(self, inputs: dict):
        self.inputs = inputs
        c = inputs.get("constants") or {}
        self.t1030 = hm_of(c["T2_FIRST_HOUR_END_ET"])
        self.loss_cut = float(c["GG_LOSS_RISK_CUT"])
        self.sess = list(inputs.get("sessions") or [])
        self.sidx = {d: i for i, d in enumerate(self.sess)}
        self.asof = inputs.get("asof") or {}
        rows = inputs.get("gg5_rows")
        self.rows_ok = isinstance(rows, list)
        self.gg5 = []                       # STUDY gg_trades("gajjala") :83-94 + norm :122-127
        for r in rows or []:
            if r.get("line") != "live":
                continue
            t = trade_of(r)
            if t:
                self.gg5.append({"date": r["date"], "kind": r.get("kind"), "R": t["R"], "bucket": t["bucket"],
                                 "filled": t["filled"], "thin": t["thin"], "ring_et": et_of(r.get("at_utc")),
                                 "row": r})
        self.by_date = defaultdict(list)    # STUDY :255-257
        for t in self.gg5:
            self.by_date[t["date"]].append(t)
        ev = []                             # STUDY aplus_events :279-290
        for t in self.gg5:
            if t["kind"] != "aplus" or t["bucket"] not in ("win", "loss") or t["R"] is None:
                continue
            r = t["row"]
            cell = r.get("next") if r.get("state_next") in ("win", "loss") else r.get("same")
            xt = et_of((cell or {}).get("exit_t") or (cell or {}).get("end_t"))
            if xt is not None:
                ev.append((xt, t["R"]))
        ev.sort(key=lambda e: e[0])
        self.ap_events = ev

    def prior(self, d: str, n: int) -> Optional[list]:
        """STUDY :210-212."""
        i = self.sidx[d]
        return self.sess[max(0, i - n):i] if i >= n else None

    def prev(self, d: str) -> Optional[str]:
        i = self.sidx[d]
        return self.sess[i - 1] if i > 0 else None

    def pass_at(self, d: str, hm: tuple):
        """STUDY pass_at :173-184 → (pass, why). The probe hands the LAST pass whose _id hh:mm ≤ the read time; the
        staleness and population rules stay here."""
        p = ((self.inputs.get("passes") or {}).get(d) or {}).get(hm_text(hm))
        if not p:
            return None, "no pass at or before %s" % hm_text(hm)
        ph, pm = hm_of(str(p["id"]).split("|")[1][:5])
        age = (hm[0] * 60 + hm[1]) - (ph * 60 + pm)
        s = p.get("strip")
        if age > STALE_MIN:
            return None, "pass %s is %d min old at %s (> %d)" % (p["id"], age, hm_text(hm), STALE_MIN)
        if not isinstance(s, dict) or not s.get("n_population"):
            return None, "pass %s has no n_population" % p["id"]
        return p, None


def _asof(ctx: _Ctx, *keys) -> dict:
    return {k: ctx.asof.get(k) for k in keys}


def _gd3w(ctx: _Ctx, d: str) -> dict:
    """STUDY gd3_week :266-276 over pd_counts :239-252 (cutoff always true)."""
    a = _asof(ctx, "gg5_last_graded_at")
    if not ctx.rows_ok:
        return missing("the GG5 rows could not be read", a)
    w = ctx.prior(d, WEEK)
    if w is None:
        return missing("fewer than %d prior sessions" % WEEK, a)
    f = h = 0
    for x in w:
        for t in ctx.by_date.get(x, []):
            if t["kind"] not in ("aplus", "potential") or t["thin"]:
                continue
            s = t["row"].get("same") or {}
            ft, xt = et_of(s.get("fill_t")), et_of(s.get("exit_t"))
            if ft is None or xt is None:
                continue
            if s.get("outcome") == "loss":
                f += 1
            elif s.get("outcome") == "win":
                h += 1
    if f + h == 0:
        return missing("held + failed == 0 over the prior %d sessions" % WEEK, a)
    return _ok(round(f / (f + h), 3), f / (f + h) > GD3W_SHARE, {"failed": f, "held": h, "window": w}, a)


def _gd4(ctx: _Ctx, d: str, hm: tuple) -> dict:
    """STUDY gd4 :296-303 — risk_after folded over every decided live A+ whose exit came STRICTLY before ET hm on d."""
    a = _asof(ctx, "gg5_last_graded_at")
    if not ctx.rows_ok:
        return missing("the GG5 rows could not be read", a)
    cut = at_cut(d, hm)
    m, n = 1.0, 0
    for xt, r in ctx.ap_events:
        if xt < cut:
            m = risk_after_copy(m, r, ctx.loss_cut)
            n += 1
    return _ok(m, m < 1.0, {"events": n, "cut": hm_text(hm)}, a)


def _gd6b(ctx: _Ctx, d: str, hm: tuple) -> dict:
    """STUDY gd6(d, tm, "n_population") :329-342."""
    a = _asof(ctx, "passes_last_id")
    p, why = ctx.pass_at(d, hm)
    if p is None:
        return missing(why, a)
    hist = []
    i = ctx.sidx[d]
    for x in ctx.sess[max(0, i - TWO_WEEKS):i]:
        q, _ = ctx.pass_at(x, hm)
        if q is not None:
            hist.append(q["strip"]["n_population"])
    if len(hist) < GD6_MIN_HIST:
        return missing("%d history values at %s (< %d)" % (len(hist), hm_text(hm), GD6_MIN_HIST), a)
    v = p["strip"]["n_population"]
    med = upper_median(hist)
    return _ok(v, v < med, {"median": med, "n_hist": len(hist), "pass": p["id"], "cut": hm_text(hm)}, a)


def _move(ctx: _Ctx, sym: str, d: str) -> Optional[float]:
    """STUDY intraday_move :345-357 (the probe already keeps only rth bars closed by 10:30)."""
    bs = (ctx.inputs.get("index_intraday") or {}).get("%s|%s" % (sym, d))
    if not bs:
        return None
    rth = [(et_of(b[0]), b) for b in bs if b[6] == "rth"]
    rth = [x for x in rth if x[0] is not None]
    rth.sort(key=lambda x: x[0])
    if not rth:
        return None
    o = rth[0][1][1]
    cut = at_cut(d, ctx.t1030)
    upto = [b for t, b in rth if t + timedelta(minutes=1) <= cut]
    if not upto or not o:
        return None
    return (upto[-1][4] / o - 1) * 100


def _gd7(ctx: _Ctx, d: str) -> dict:
    """STUDY gd7 :360-364 — BEST-EFFORT: the minute cache fills lazily."""
    a = _asof(ctx, "qqq_last_date", "iwm_last_date")
    q, i = _move(ctx, "QQQ", d), _move(ctx, "IWM", d)
    if q is None or i is None:
        absent = [s for s, v in (("QQQ", q), ("IWM", i)) if v is None]
        return missing("%s bars absent by %s" % ("/".join(absent), hm_text(ctx.t1030)), a)
    return _ok("QQQ %+.2f%% IWM %+.2f%%" % (q, i), q < 0 and i < 0, {"qqq": q, "iwm": i}, a)


def _ld3i(ctx: _Ctx, d: str) -> dict:
    """STUDY ld3(d, "IWM") :393-395 over idx_prev :380-390 — the IWM frame's bar of the PREVIOUS session."""
    a = _asof(ctx, "iwm_daily_last_date", "iwm_daily_cached_at")
    prev = ctx.prev(d)
    rows = (ctx.inputs.get("iwm_daily") or {}).get("rows") or []
    byd = {r[0]: r for r in rows}
    if prev is None or prev not in byd:
        return missing("the IWM frame has no bar for the previous session %s" % prev, a)
    _, c, e9, e21 = byd[prev][:4]
    if _f(e9) is None or _f(e21) is None:
        return missing("the IWM EMAs are not finite on %s" % prev, a)
    return _ok(round(e9 - e21, 2), e9 < e21, {"prev": prev, "close": c, "ema9": e9, "ema21": e21}, a)


def _ld9(ctx: _Ctx, d: str) -> dict:
    """STUDY ld9 :466-481."""
    a = _asof(ctx, "pillars_last_date")
    prev = ctx.prev(d)
    weak = n = 0
    names = []
    for sym, rows in sorted((ctx.inputs.get("pillars") or {}).items()):
        rows = rows or []
        dd = {r[0]: r for r in rows}
        if prev not in dd:
            continue
        ks = [r[0] for r in rows]
        j = ks.index(prev)
        if j == 0:
            continue
        _, c, e9, e21, _e50 = dd[prev]
        n += 1
        if c < e9 and c < e21 and e9 < rows[j - 1][2]:
            weak += 1
            names.append(sym)
    if n < LD9_MIN_PILLARS:
        return missing("%d pillars with a row on %s (< %d)" % (n, prev, LD9_MIN_PILLARS), a)
    return _ok("%d/%d" % (weak, n), weak >= PILLAR_WEAK_MIN, {"weak": names, "prev": prev}, a)


def compute_all(inputs: dict, sessions: list) -> dict:
    """{session: {tag_form: tag}} — one context for many sessions."""
    ctx = _Ctx(inputs)
    out = {}
    for d in sessions:
        if d not in ctx.sidx:
            raise ValueError("session %s is not a market day of the inputs" % d)
        out[d] = {
            "GD3w_pre": _gd3w(ctx, d),
            "GD4_pre": _gd4(ctx, d, GD4_PRE_CUT),
            "GD4_by1030": _gd4(ctx, d, ctx.t1030),
            "GD6b_pre": _gd6b(ctx, d, PRE_CUT),
            "GD6b_by1030": _gd6b(ctx, d, ctx.t1030),
            "GD7_by1030": _gd7(ctx, d),
            "LD3i_pre": _ld3i(ctx, d),
            "LD9_pre": _ld9(ctx, d),
        }
    return out


def compute(inputs: dict, session: str) -> dict:
    """{tag_form: tag} for one session."""
    return compute_all(inputs, [session])[session]


# ── the store ───────────────────────────────────────────────────────────────────────────────────────────────────────
def load_store(path) -> list:
    """Every line of day_tags.jsonl, in order. [] when the file is absent or empty. Raises StoreCorrupt on a line
    that does not parse, a missing trailing newline, or a non-contiguous rev."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as fh:
        raw = fh.read()
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise StoreCorrupt("the last line has no trailing newline (a cut write)")
    out, revs = [], {}
    for n, line in enumerate(raw.split(b"\n")[:-1], 1):
        try:
            rec = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise StoreCorrupt("line %d does not parse" % n)
        if not isinstance(rec, dict) or not isinstance(rec.get("session"), str) or not isinstance(rec.get("rev"), int):
            raise StoreCorrupt("line %d is not a record" % n)
        want = revs.get(rec["session"], -1) + 1
        if rec["rev"] != want:
            raise StoreCorrupt("line %d: session %s rev %s, expected %d" % (n, rec["session"], rec["rev"], want))
        revs[rec["session"]] = rec["rev"]
        out.append(rec)
    return out


def latest_by_session(records: list) -> dict:
    out = {}
    for r in records:
        out[r["session"]] = r
    return out


def sessions_to_compute(records: list, inputs: dict, target: str) -> dict:
    """[C3] the target plus every GAP (a market day of the inputs, FORWARD_FROM ≤ d < target, with NO record) plus
    every earlier forward session whose latest record still holds a MISSING form (missing_retry)."""
    have = latest_by_session(records)
    gaps = [d for d in inputs.get("sessions") or [] if FORWARD_FROM <= d < target and d not in have]
    retry = [d for d in sorted(have) if FORWARD_FROM <= d < target
             and any((t or {}).get("status") == "missing" for t in (have[d].get("tags") or {}).values())]
    return {"target": target, "gaps": gaps, "missing_retry": retry}


def _key(tag: dict) -> tuple:
    return (tag.get("status"), tag.get("on"), json.dumps(tag.get("value"), sort_keys=True))


def plan_append(records: list, session: str, tags: dict, meta: dict, mode: str = "plain") -> Optional[dict]:
    """The line to append for `session`, or None. First compute → rev 0. Otherwise the new tags are merged with the
    latest record's by `mode` and a line is planned only when a (status, on, value) moved:
      plain     — the run's target: every change is taken EXCEPT ok → missing (the old ok stays);
      retry     — an earlier forward session with a MISSING form: only missing → ok is taken;
      recompute — --recompute: every change is taken, ok → missing included (its why says why).
    As-of stamps are never compared."""
    if mode not in ("plain", "retry", "recompute"):
        raise ValueError(mode)
    prev = latest_by_session([r for r in records if r.get("session") == session]).get(session)
    if prev is None:
        new, changed, rev = dict(tags), None, 0
    else:
        old = prev.get("tags") or {}
        new, changed = {}, []
        for f in TAG_FORMS:
            o, n = old.get(f) or missing("absent"), tags[f]
            if _key(o) == _key(n):
                new[f] = o
                continue
            take = (mode == "recompute"
                    or (mode == "plain" and not (o.get("status") == "ok" and n.get("status") == "missing"))
                    or (mode == "retry" and o.get("status") == "missing" and n.get("status") == "ok"))
            new[f] = n if take else o
            if take:
                changed.append(f)
        if not changed:
            return None
        rev = prev["rev"] + 1
    rec = {"schema": SCHEMA, "session": session, "rev": rev, "in_sample": session < FORWARD_FROM,
           "changed": changed, "tags": {f: new[f] for f in TAG_FORMS}}
    rec.update(meta)
    return rec


def _atomic_write(path: str, data: bytes) -> None:
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=d)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append(path, record) -> None:
    """Append ONE record: temp file holding the old bytes + the new line, then os.replace — the old bytes stay a
    prefix, a killed run leaves the old file."""
    append_many(path, [record])


def append_many(path, records: list) -> None:
    old = b""
    if os.path.exists(path):
        with open(path, "rb") as fh:
            old = fh.read()
    new = b"".join(json.dumps(r, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
                   for r in records)
    _atomic_write(path, old + new)


def inputs_blob(inputs: dict) -> bytes:
    """the probe blob, sorted keys, gzip mtime=0 — the same inputs give the same bytes."""
    raw = json.dumps(inputs, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, mtime=0)


def orphan_inputs(out_dir: str, records: list) -> list:
    """inputs files no line references — the orphans of a killed run: never read, never overwritten."""
    d = os.path.join(out_dir, INPUTS_DIR)
    if not os.path.isdir(d):
        return []
    ref = {r.get("inputs_file") for r in records}
    return sorted(os.path.join(INPUTS_DIR, n) for n in os.listdir(d)
                  if n.endswith(".json.gz") and os.path.join(INPUTS_DIR, n) not in ref)


def next_inputs_name(out_dir: str, run_date: str) -> str:
    """inputs/<run date>.json.gz, else the next free .r2 / .r3 … — an existing file (referenced or orphan) is never
    overwritten."""
    d = os.path.join(out_dir, INPUTS_DIR)
    k = 1
    while True:
        name = "%s.json.gz" % run_date if k == 1 else "%s.r%d.json.gz" % (run_date, k)
        if not os.path.exists(os.path.join(d, name)):
            return os.path.join(INPUTS_DIR, name)
        k += 1


def write_run(out_dir: str, inputs_rel: str, blob: bytes, lines: list) -> None:
    """The write order [C2]: the inputs file first (temp + replace), then the JSONL (temp + replace)."""
    os.makedirs(os.path.join(out_dir, INPUTS_DIR), exist_ok=True)
    target = os.path.join(out_dir, inputs_rel)
    if os.path.exists(target):
        raise FileExistsError(target)
    _atomic_write(target, blob)
    append_many(os.path.join(out_dir, STORE_NAME), lines)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def has_nan(x) -> bool:
    if isinstance(x, float):
        return x != x or math.isinf(x)
    if isinstance(x, dict):
        return any(has_nan(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return any(has_nan(v) for v in x)
    return False
