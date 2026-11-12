"""READ-ONLY container probe for the Track-record row snapshot (spec rec157 WP-3, 2026-11-11).

Dumps every stored Track-record row of the four pages through the SERVED engines, with the row features that expire:
  gg5  🚩 5-min      gajjala.ledger.rows_for over the GG5 store (+ grade, dedupe verdict, 🧠 tracker, claim, the reads
                     ctx_eod, the 🧪 overlay verdict, avg_vol_50, bar features from the intraday CACHE)
  gg1  🚩 1-minute   the same over the GG1 store (no 🧪 overlay)
  gga  🧪 Audited    one row per 🚩 A+ row the 🧪 🏁 lists: audited_tab.read_span(span="all") → row_audits (the ONE
                     verdict), + the raw overlay verdict of the row's setup
  luk  🥇 Luk        luk.ledger.rows_for / track_row (every served cell key) / mark_dups, the luk_ledger doc's fill /
                     walk / version / graded_at / graded_from, bar features, + the luk_reads doc (ctx_eod) and the
                     luk_daily doc (daily) of the row's date and symbol
Origin: eod-audits/research/2026-11-11_track_record_patterns/dump_rows.py + day_probe.py:23-34, with three named
changes: `ctx` is `ctx_eod` (the reads doc is REPLACED on every pass → it is the day's LAST write, never "known at the
alert"); the previous session walks back with market_hours.reminder.is_market_day (a holiday is skipped, a weekday
walk is not); every row carries `src_present` = whether each expiring source doc exists NOW.

No write anywhere, no provider fetch (bars come from intraday_cache with a plain find; a symbol-day not cached = None).
The engines' Mongo handle is pre-set (portfolio.store._db) so portfolio.store._get_db never runs its create_index.
Run (the host CLI does this):  docker exec -i -w /app cheetah-market-app-api-1 python - < track_record_snapshot_probe.py
Prints one JSON object: {generated_utc, today_et, constants, pages: {gg5, gg1, gga, luk}, sessions, faults}; a page
whose read raised is null + a fault (never [])."""
import json
import os
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone

PAGES = ("gg5", "gg1", "gga", "luk")
_MAX_WALK = 10


def prev_session(d) -> str:
    """The market day before `d` (ISO str or date): walks back with market_hours.reminder.is_market_day at noon ET —
    the house engine (supply_demand.key_levels.prev_market_day reads the same)."""
    from market_hours.reminder import is_market_day
    x = (date.fromisoformat(d) if isinstance(d, str) else d) - timedelta(days=1)
    for _ in range(_MAX_WALK):
        if is_market_day(datetime.combine(x, dtime(12, 0))):
            return x.isoformat()
        x -= timedelta(days=1)
    return x.isoformat()


def iso(x):
    return x.isoformat() if isinstance(x, datetime) else x


class Probe:
    def __init__(self, db, now):
        self.db = db
        self.now = now
        self._bar_memo = {}
        try:
            from sepa.symbols import for_massive
        except Exception:                                       # noqa: BLE001
            def for_massive(s):
                return s
        self.for_massive = for_massive

    # ── bars from the intraday CACHE only ─────────────────────────────────────────────────────────────────────────
    def bars_of(self, sym, d):
        k = (sym, d)
        if k not in self._bar_memo:
            doc = self.db.intraday_cache.find_one({"symbol": self.for_massive(sym).upper(), "date": d}, {"bars": 1})
            out = []
            for b in (doc or {}).get("bars") or []:
                try:
                    t = datetime.fromisoformat(str(b["ts_utc"])).replace(tzinfo=timezone.utc)
                except Exception:                               # noqa: BLE001
                    continue
                out.append((t, b.get("open"), b.get("high"), b.get("low"), b.get("close"), b.get("volume") or 0.0,
                            b.get("session")))
            out.sort(key=lambda x: x[0])
            self._bar_memo[k] = out if out else None
        return self._bar_memo[k]

    def bar_feats(self, sym, d, at):
        """Facts known at the ring: bars that CLOSED at or before the ring (start + 1 min <= at)."""
        bs = self.bars_of(sym, d)
        if not bs or at is None:
            return None
        before = [b for b in bs if b[0] + timedelta(minutes=1) <= at]
        rth = [b for b in bs if b[6] == "rth"]
        pre_all = [b for b in bs if b[6] == "premarket"]
        f = {"cached": True, "n_before": len(before)}
        if before:
            f["lod_before"] = min(b[3] for b in before if b[3] is not None)
            f["hod_before"] = max(b[2] for b in before if b[2] is not None)
            f["cumvol_before"] = float(sum(b[5] for b in before))
            f["last_close_before"] = before[-1][4]
            f["vol_last5_before"] = float(sum(b[5] for b in before[-5:]))
            f["vol_last30_before"] = float(sum(b[5] for b in before[-30:]))
            f["dollar_vol_before"] = float(sum((b[5] or 0) * (b[4] or 0) for b in before))
        rb = [b for b in before if b[6] == "rth"]
        if rth:
            f["rth_open"] = rth[0][1]
            f["rth_close"] = rth[-1][4]
            f["rth_high"] = max(b[2] for b in rth)
            f["rth_low"] = min(b[3] for b in rth)
            f["rth_vol"] = float(sum(b[5] for b in rth))
        if rb:
            f["lod_rth_before"] = min(b[3] for b in rb)
            f["hod_rth_before"] = max(b[2] for b in rb)
        if pre_all:
            f["pm_high"] = max(b[2] for b in pre_all)
            f["pm_vol"] = float(sum(b[5] for b in pre_all))
        pb = self.bars_of(sym, prev_session(d))
        if pb:
            prth = [b for b in pb if b[6] == "rth"]
            if prth:
                f["prev_close"] = prth[-1][4]
        return f

    def avg_vol_50(self, sym, d):
        doc = self.db.gajjala_daily.find_one({"symbol": sym, "date": {"$lte": d}, "avg_vol_50": {"$gt": 0}},
                                             {"avg_vol_50": 1, "date": 1}, sort=[("date", -1)])
        return (doc or {}).get("avg_vol_50"), (doc or {}).get("date")

    # ── gg5 / gg1 ────────────────────────────────────────────────────────────────────────────────────────────────
    def gg(self, v):
        from chart_maps.gajjala import ledger as L
        from chart_maps.gajjala import store as ST
        from chart_maps.gajjala import variant as V
        now = self.now
        today = now.astimezone(L.ET).date()
        s = ST.for_variant(v)
        pfx = v.store_prefix
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
            sym, d, setup = row["symbol"], row["date"], row["setup"]
            pot = self.db[f"{pfx}_potentials"].find_one({"_id": f"{d}|{sym}|{setup}"}) or {}
            al = None
            if row["kind"] == "aplus":
                al = self.db[f"{pfx}_alerts"].find_one({"date": d, "symbol": sym, "setup": setup,
                                                        "state": {"$in": ["pushed", "shadow"]},
                                                        "_id": {"$not": {"$regex": "#"}}}) or {}
            rd = self.db[f"{pfx}_reads"].find_one({"_id": f"{d}|{sym}"}, {"ctx": 1})
            ctx = (rd or {}).get("ctx") or {}
            ov = (self.db.gajjala_audited_overlay.find_one({"_id": f"{d}|{sym}"}, {"setups": 1})
                  if v is V.GG5 else None)
            ovs = ((ov or {}).get("setups") or {}).get(setup) if ov else None
            av, av_d = self.avg_vol_50(sym, d)
            at = row.get("at_utc")
            tells = pot.get("first_tells") or {}
            bars_src = self.bars_of(sym, d)
            out.append({
                "variant": v.key, "id": row["id"], "date": d, "symbol": sym, "setup": setup, "kind": row["kind"],
                "line": row["line"], "count_line": L._count_line(row), "at_utc": iso(at), "at_et": row.get("at_et"),
                "rang": row.get("rang"), "trigger": row.get("trigger"), "stop": row.get("stop"), "r": row.get("r"),
                "r_pct": row.get("r_pct"), "thin": row.get("thin"), "plan": row.get("plan"),
                "price_at_alert": row.get("price_at_alert"), "plan_source": row.get("plan_source"),
                "first_seen_et": row.get("first_seen_et"), "trader": row.get("trader"), "promo": row.get("promo"),
                "push_state": row.get("push_state"),
                "same": same, "next": nxt, "state_same": cs, "state_next": cn,
                "bucket": L.bucket_of(cs, cn, True), "dup_of": dups.get(row["id"]),
                "pot": {"first_kind": pot.get("first_kind"), "first_risk_pct": pot.get("first_risk_pct"),
                        "first_seen_et": pot.get("first_seen_et"), "first_px": pot.get("first_px"),
                        "kind_at_push": (pot.get("push") or {}).get("kind_at_push"),
                        "float_shares": tells.get("float_shares"), "rotation_x": tells.get("rotation_x"),
                        "halts_n": tells.get("halts_n"), "volume_first": tells.get("volume"),
                        "prior_max_change_pct": tells.get("prior_max_change_pct"),
                        "ah_move_pct": tells.get("ah_move_pct"), "promo": pot.get("promo")} if pot else None,
                "alert": {"price": al.get("price"), "risk_pct": al.get("risk_pct"),
                          "entry_bar_t": al.get("entry_bar_t"), "mode": al.get("mode"),
                          "session_volume": al.get("session_volume"),
                          "body": ((al.get("would_push") or {}).get("body"))} if al else None,
                "ctx_eod": {"float_shares": ((ctx.get("float") or {}).get("shares")),
                            "float_suspect": bool(ctx.get("float_suspect")),
                            "rotation_x": ((ctx.get("rotation") or {}).get("x")),
                            "halts_n": ((ctx.get("halts") or {}).get("n")), "reg_gain_pct": ctx.get("reg_gain_pct"),
                            "squeeze_hist_n": ((ctx.get("squeeze_history") or {}).get("n"))} if ctx else None,
                "audit": {"aplus": ovs.get("aplus"), "original_aplus": ovs.get("original_aplus"),
                          "failed": [x.get("id") for x in ovs.get("failed") or []]} if isinstance(ovs, dict) else None,
                "avg_vol_50": av, "avg_vol_50_date": av_d,
                "bars": self.bar_feats(sym, d, at if isinstance(at, datetime) else None),
                "src_present": {"ctx_eod": rd is not None, "audit": ov is not None, "avg_vol_50": av is not None,
                                "bars": bars_src is not None},
            })
        return out, ds

    # ── gga ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def gga(self):
        from chart_maps.gajjala import audited_tab as AT
        from chart_maps.gajjala import ledger as L
        from chart_maps.gajjala import store as ST
        from chart_maps.gajjala import variant as V
        now = self.now
        today = now.astimezone(L.ET).date()
        st = ST.for_variant(V.GGA)
        read = AT.read_span(st, today, now, span="all")
        audits = AT.row_audits(read["sides"], read["exits_by_id"])
        out = []
        for o in read["sides"]["original"]:
            sym, d, setup = o["symbol"], o["date"], o["setup"]
            ov = self.db.gajjala_audited_overlay.find_one({"_id": f"{d}|{sym}"}, {"setups": 1})
            ovs = ((ov or {}).get("setups") or {}).get(setup) if ov else None
            cell = audits.get(o["id"])
            out.append({
                "id": o["id"], "date": d, "symbol": sym, "setup": setup, "kind": o.get("kind"),
                "at_utc": iso(o.get("at_utc")),
                "audit_raw": {"aplus": ovs.get("aplus"), "original_aplus": ovs.get("original_aplus"),
                              "failed": [x.get("id") for x in ovs.get("failed") or []],
                              "rules": ovs.get("rules")} if isinstance(ovs, dict) else None,
                "audit_cell": {"state": cell.get("state"), "text": cell.get("text"),
                               "sub_text": cell.get("sub_text")} if isinstance(cell, dict) else None,
                "src_present": {"audit": ov is not None},
            })
        return out, [iso(x) if not isinstance(x, date) else x.isoformat() for x in read["sessions"]]

    # ── luk ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def luk(self):
        from chart_maps.luk import ledger as LL
        from chart_maps.luk import store as LS
        now = self.now
        today = now.astimezone(LL.ET).date()
        store = LS.default()
        record = LL.record_sessions(today)
        rows = LL.rows_for(record, store)
        docs = {d.get("_id"): d for d in (store.ledger_docs(record) or []) if isinstance(d, dict)}
        served = [LL.track_row(r, docs.get(r["id"])) for r in rows]
        LL.mark_dups(served, docs, {r["id"]: r for r in rows})
        out = []
        for r, c in zip(rows, served):
            doc = docs.get(r["id"]) or {}
            sym, d, setup = r["symbol"], r["date"], r["setup"]
            at = r.get("at_utc")
            f = doc.get("fill") if isinstance(doc.get("fill"), dict) else None
            w = doc.get("walk") if isinstance(doc.get("walk"), dict) else None
            rd = self.db.luk_reads.find_one({"_id": f"{d}|{sym}"})
            dl = self.db.luk_daily.find_one({"_id": f"{d}|{sym}"})
            bars_src = self.bars_of(sym, d)
            setups = (rd or {}).get("setups") if isinstance((rd or {}).get("setups"), dict) else {}
            row = {k: iso(val) for k, val in r.items()}
            row.update({
                "cell": dict(c),
                "fill": f, "walk": w, "version": doc.get("version"), "graded_at": doc.get("graded_at"),
                "graded_from": doc.get("graded_from"),
                "fill_px": (f or {}).get("fill_px"), "exit_px": (w or {}).get("exit_px"),
                "bars": self.bar_feats(sym, d, at if isinstance(at, datetime) else None),
                "ctx_eod": {"facts": rd.get("facts"), "tier": rd.get("tier"), "tile": rd.get("tile"),
                            "screens_rank": rd.get("screens_rank"), "cap_text": rd.get("cap_text"),
                            "as_of_bar_t1": rd.get("as_of_bar_t1"), "as_of_bar_t5": rd.get("as_of_bar_t5"),
                            "as_of_bar_t60": rd.get("as_of_bar_t60"),
                            "setup_read": setups.get(setup)} if rd else None,
                "daily": {"facts": dl.get("facts"), "source": dl.get("source"),
                          "daily_cached_at": dl.get("daily_cached_at")} if dl else None,
                "src_present": {"bars": bars_src is not None, "ctx_eod": rd is not None, "daily": dl is not None},
            })
            out.append(row)
        return out, [x.isoformat() for x in record]


def main() -> int:
    from pymongo import MongoClient
    db = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"))[os.getenv("MONGO_DB", "cheetah")]
    import portfolio.store as PS
    PS._db = db                          # the engines read through this handle; _get_db's create_index never runs
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import ledger as L
    from chart_maps.gajjala import variant as V
    from chart_maps.luk import constants as LC
    now = datetime.now(timezone.utc)
    p = Probe(db, now)
    pages, sessions, faults = {}, {}, []
    for page, fn in (("gg5", lambda: p.gg(V.GG5)), ("gg1", lambda: p.gg(V.GG1)), ("gga", p.gga), ("luk", p.luk)):
        try:
            rows, ds = fn()
            pages[page], sessions[page] = rows, ds
        except Exception as exc:                                # noqa: BLE001 — a page that raised is null, never []
            pages[page], sessions[page] = None, None
            faults.append(f"{page}: {type(exc).__name__}: {exc}")
    res = {"generated_utc": now.isoformat(), "today_et": now.astimezone(L.ET).date().isoformat(),
           "constants": {"ledger_r_mult": GC.LEDGER_R_MULT, "ledger_min_r_pct": GC.LEDGER_MIN_R_PCT,
                         "fill_from_et": str(GC.LEDGER_FILL_FROM_ET), "fill_to_et": str(GC.LEDGER_FILL_TO_ET),
                         "luk_grade_version": LC.LUK_GRADE_VERSION},
           "pages": pages, "sessions": sessions, "faults": faults}
    sys.stdout.write(json.dumps(res, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
