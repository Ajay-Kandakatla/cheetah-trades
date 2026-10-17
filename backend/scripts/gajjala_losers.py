"""❌ The Gajjala losers study — every losing alert on the 🏁 Track record, one line each, in classes declared
before the count (2026-10-16 night, DECISIONS11 D13, BUILD_SPEC11 §3.16, AMENDMENTS11 F1 / F2 / F4 / F5 / F14).

THE ASK (Ajay 2026-10-16 ~22:45 ET, verbatim):
  "I want winners and losers category in his track record and would like us to study the losers"

DESCRIPTIVE — a class is a question for Gajjala's rules, not a finding. UNMEASURED: counts of rows and trades only —
no rate, no ratio, no score of a setup. The 2026-10-14 study of the five setups read NULL
(docs/gajjala/study_2026_10_13.md) and nothing here changes that. Rule #9 (Ajay 2026-09-03): one line per loser; a
class with GC.LEDGER_LOSS_CLASS_FLAG_N or more loser TRADES is printed as a candidate rule — HIS CALL, never a gate.

ONE ENGINE (BUILD_SPEC11 C9). Every state, bucket and fact comes from chart_maps.gajjala.ledger: `_state_of`,
`bucket_of`, `loss_facts`, `loss_text`, `fill_facts` (winner trades, F14), `alert_of` (a ⏪ replay doc). No fact,
threshold or word is computed here a second time; the thresholds are the GC.LEDGER_LOSS_* constants, read by name.
Imports: ledger + constants (+ store for --mongo only). Reads only; writes only the --out directory.

INPUT. --mongo: the app's own Mongo settings (store.default()): gajjala_ledger docs of every ledger date, plus the
gajjala_replay docs only with --include-replayed. --from-json FILE: a JSON list of gajjala_ledger docs and / or
replay docs ("REPLAY:" ids). Default lines: live + shadow, both kinds (🧠 potential and 🚩 A+); a REPLAY: doc is kept
ONLY with --include-replayed. A missing column reads "pending" (F4). A read fault prints one line and exits 2 with
nothing written (F5) — an unreadable ledger is never "no loser on file".

THE PRE-DECLARED CLASSES (one tag per dimension, no others): C1 rang AH → filled next morning · C2 fill in the last
LEDGER_LOSS_LATE_RTH_MIN min of RTH · C3 fill ≥ LEDGER_LOSS_STALE_FILL_MIN min after the ring (next-morning fills
excluded, F2) · C4 stopped ≤ LEDGER_LOSS_FAST_MIN min after the fill · C5 high under +LEDGER_LOSS_NO_PROGRESS_R R ·
C6 high ≥ +LEDGER_LOSS_GAVE_BACK_R R, then stopped · C7 thin R · C8 one trade on two or more setups · C9 per setup ·
C10 per rang. A TRADE = one (date, symbol, trigger, stop) (F1): C1–C8 are counted and flagged on trades, the row
count printed beside; C9 / C10 are splits, never flagged (F14). Beside C1–C4 and C7 the same fact among WINNER
trades is counted (fill_facts / the row's thin flag) — counts only; C4's winner side is labelled "at +1R ≤N min".
⏪ REPLAYED rows (--include-replayed) never rang: each md line carries LG.REPLAY_CHIP, and every count / flag above is
over live + shadow trades only — replayed trades are keyed and counted APART, printed "+N ⏪" beside (the
LG._category_text convention, AMENDMENTS11 F13); a replayed trade never makes a class reach the flag.

OUTPUT. losers.csv (one row per loser: the row, the facts, the C1–C8 flags, loss_text) and losers.md (a header, one
line per loser "{date} {SYM} {setup_label} · {loss_text}", the class table). An empty list still writes both files.

RUN (a throwaway api container, after the D6 replay run, outside RTH; reads only):
  docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_losers --mongo --out /replay_out/losers
  docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_losers --mongo --out /replay_out/losers_with_replay --include-replayed
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG

UNREADABLE_TEXT = "ledger unreadable — nothing written"                                    # AMENDMENTS11 F5
EMPTY_TEXT = "no loser on file"
TITLE = "# ❌ Gajjala losers — every losing alert on the 🏁 Track record, in classes declared before the count"
DESCRIPTIVE_TEXT = "descriptive — a class is a question for Gajjala's rules, not a finding"
STUDY_TEXT = ("UNMEASURED. The 2026-10-14 study of the five setups read NULL (docs/gajjala/study_2026_10_13.md); "
              "nothing here changes that. Counts of rows and trades only.")
TRADE_TEXT = ("A trade = one date, symbol, trigger and stop: a name that rang on two setups (or as a 🧠 and its 🎯) is "
              "ONE trade and two rows; classes C1–C8 count trades, the rows beside.")
FLAG_TEXT = "≥{n} → candidate rule — HIS CALL"
CLASS_KEYS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
FACT_OF = {"C1": "next_morning", "C2": "late_rth", "C3": "stale", "C4": "fast", "C5": "no_progress",
           "C6": "gave_back", "C7": "thin"}
WINNER_FACT_OF = {"C1": "next_morning", "C2": "late_rth", "C3": "stale", "C4": "fast", "C7": "thin"}   # F14
FACT_KEYS = ("stopped_min", "fill_after_min", "best_r", "fill_minute", "late_rth", "next_morning", "stale", "fast",
             "no_progress", "gave_back", "thin")
CSV_HEAD = (("date", "symbol", "setup", "setup_label", "kind", "line", "rang", "trigger", "stop", "loss_column",
             "trade") + FACT_KEYS + tuple(k.lower() for k in CLASS_KEYS) + ("loss_text",))


def class_label(k: str) -> str:
    """The class names — every number read from constants.py by name at CALL time."""
    return {"C1": "rang AH → filled next morning",
            "C2": f"fill in the last {GC.LEDGER_LOSS_LATE_RTH_MIN} min of RTH",
            "C3": f"fill ≥{GC.LEDGER_LOSS_STALE_FILL_MIN} min after the ring (next-morning fills not counted)",
            "C4": f"stopped ≤{GC.LEDGER_LOSS_FAST_MIN} min after the fill",
            "C5": f"high under +{GC.LEDGER_LOSS_NO_PROGRESS_R:g}R through the stop minute (no progress)",
            "C6": f"high ≥ +{GC.LEDGER_LOSS_GAVE_BACK_R:g}R through the stop minute, then stopped (gave back)",
            "C7": LG.THIN_TEXT,
            "C8": "one trade on two or more setups (same date, symbol, trigger and stop)",
            "C9": "setup",
            "C10": "rang"}[k]


def setup_label(setup: str) -> str:
    """The 🏁 row's setup label (served_block: the SUBS emoji + label; an unknown setup = its key)."""
    meta = {k: (e, lab) for k, e, lab in GC.SUBS}
    e, lab = meta.get(setup, ("", setup))
    return f"{e} {lab}".strip()


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# ── rows ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _is_replay(doc: dict) -> bool:
    return str(doc.get("_id") or "").startswith(LG.REPLAY_ID_PREFIX)


def row_of(doc: dict) -> Optional[dict]:
    """A gajjala_ledger doc → the alert_of-shaped dict (§3.16 step 2: date, symbol, setup, kind, line + the stored
    alert block's trigger, stop, r, thin, rang, plan; at_utc = LG._parse_at(alert.at)); a replay doc → LG.alert_of
    (line "replayed" only). None when the doc is not a row (wrong kind / line, no symbol / setup / date)."""
    if not isinstance(doc, dict):
        return None
    if _is_replay(doc):
        r = LG.alert_of(doc, LG.KINDS[1])
        return r if r is not None and r.get("line") == LG.LINES[2] else None
    sym = str(doc.get("symbol") or "").upper()
    setup, kind, line, d = doc.get("setup"), doc.get("kind"), doc.get("line"), doc.get("date")
    if (not sym or not isinstance(setup, str) or not setup or not isinstance(d, str) or kind not in LG.KINDS
            or line not in (LG.LINES[0], LG.LINES[1])):
        return None
    a = doc.get("alert") if isinstance(doc.get("alert"), dict) else {}
    return {"id": str(doc.get("_id") or ""), "date": d[:10], "symbol": sym, "setup": setup, "kind": kind,
            "line": line, "trigger": a.get("trigger"), "stop": a.get("stop"), "r": a.get("r"),
            "thin": bool(a.get("thin")), "rang": a.get("rang"), "plan": a.get("plan"),
            "at_utc": LG._parse_at(a.get("at"))}


def _state(col) -> str:
    return LG._state_of(col) if isinstance(col, dict) else "pending"                       # AMENDMENTS11 F4


def graded(doc: dict, row: dict) -> tuple:
    """-> (bucket, the column that made it) — LG.bucket_of over the two stored columns (a replayed row whose next
    column was never cached is not due, F7); the column = next when its state is the bucket, else same."""
    same = doc.get("same") if isinstance(doc.get("same"), dict) else None
    nxt = doc.get("next") if isinstance(doc.get("next"), dict) else None
    s, n = _state(same), _state(nxt)
    due = not (row.get("line") == LG.LINES[2] and nxt is None)
    b = LG.bucket_of(s, n, due)
    return b, (nxt if n == b else same)


def _trade_key(row: dict) -> tuple:
    return (row["date"], row["symbol"], LG._num(row.get("trigger")), LG._num(row.get("stop")))


def _replayed(x: dict) -> bool:
    return x["row"].get("line") == LG.LINES[2]


def _group(items: list) -> dict:
    out: dict = {}
    for x in items:
        out.setdefault(_trade_key(x["row"]), []).append(x)
    return out


def collect(docs: list, include_replayed: bool) -> dict:
    """-> {"losers": [loser dicts, time order], "winners": [winner dicts], "docs": n read, "skipped": n not rows}."""
    losers, winners, skipped = [], [], 0
    for doc in docs or []:
        if not isinstance(doc, dict) or (_is_replay(doc) and not include_replayed):
            continue
        try:
            row = row_of(doc)
        except Exception:                                       # noqa: BLE001
            row = None
        if row is None:
            skipped += 1
            continue
        bucket, col = graded(doc, row)
        if bucket == LG.BUCKETS[1]:
            losers.append({"row": row, "col": col,
                           "column": GC.LEDGER_HORIZONS[1] if col is doc.get("next") else GC.LEDGER_HORIZONS[0],
                           "facts": LG.loss_facts(row, col), "text": LG.loss_text(row, col)})
        elif bucket == LG.BUCKETS[0]:
            winners.append({"row": row, "facts": LG.fill_facts(row, col)})
    key = (lambda x: (x["row"]["date"], x["row"]["at_utc"].timestamp() if x["row"].get("at_utc") else 0.0,
                      x["row"]["symbol"], x["row"]["setup"], x["row"]["kind"]))
    losers.sort(key=key)
    trades = _group([x for x in losers if not _replayed(x)])
    rtrades = _group([x for x in losers if _replayed(x)])
    for x in losers:
        x["trade_rows"] = len((rtrades if _replayed(x) else trades)[_trade_key(x["row"])])
    return {"losers": losers, "winners": winners, "trades": trades, "replay_trades": rtrades,
            "docs": len(docs or []), "skipped": skipped}


def _has(x: dict, k: str, winner: bool = False) -> bool:
    fact = (WINNER_FACT_OF if winner else FACT_OF).get(k)
    if fact == "thin":
        return bool(x["row"].get("thin"))
    return bool((x.get("facts") or {}).get(fact))


def _class_n(trades: dict, k: str) -> tuple:
    """-> (trades, rows) of class k over one trade map (C8 = trades with two or more loser rows)."""
    if k == "C8":
        dup = [rs for rs in trades.values() if len(rs) > 1]
        return len(dup), sum(len(rs) for rs in dup)
    hit = [[x for x in rs if _has(x, k)] for rs in trades.values()]
    hit = [h for h in hit if h]
    return len(hit), sum(len(h) for h in hit)


def _winner_n(wtrades: dict, k: str) -> int:
    return sum(1 for ws in wtrades.values() if any(_has(w, k, winner=True) for w in ws))


def _split(trades: dict, field: str) -> dict:
    split: dict = {}
    for rs in trades.values():
        for v in sorted({str(x["row"].get(field) or "—") for x in rs}):
            s = split.setdefault(v, {"trades": 0, "rows": 0})
            s["trades"] += 1
            s["rows"] += sum(1 for x in rs if str(x["row"].get(field) or "—") == v)
    return split


def classes(res: dict) -> dict:
    """-> {"C1".."C8": {"trades", "rows", "winner_trades" (C1–C4, C7 only, else None), "flagged", "replayed_trades",
    "replayed_winner_trades"}, "C9": {setup: {"trades", "rows", "replayed_trades"}}, "C10": {rang: (same)}} — trades
    per F1 over live + shadow rows ONLY; ⏪ replayed trades counted APART (never in trades / rows / the flag); the flag
    at GC.LEDGER_LOSS_CLASS_FLAG_N (read at CALL time) on C1–C8 only (F14)."""
    trades, rtrades = res["trades"], res.get("replay_trades") or {}
    wins = [w for w in res["winners"] if not _replayed(w)]
    wtrades, rwtrades = _group(wins), _group([w for w in res["winners"] if _replayed(w)])
    out: dict = {}
    for k in CLASS_KEYS:
        n, rows = _class_n(trades, k)
        win = k in WINNER_FACT_OF
        out[k] = {"trades": n, "rows": rows, "flagged": n >= GC.LEDGER_LOSS_CLASS_FLAG_N,
                  "winner_trades": _winner_n(wtrades, k) if win else None,
                  "replayed_trades": _class_n(rtrades, k)[0],
                  "replayed_winner_trades": _winner_n(rwtrades, k) if win else None}
    for k, field in (("C9", "setup"), ("C10", "rang")):
        split = _split(trades, field)
        for v in split.values():
            v["replayed_trades"] = 0
        for v, c in _split(rtrades, field).items():
            split.setdefault(v, {"trades": 0, "rows": 0, "replayed_trades": 0})["replayed_trades"] = c["trades"]
        out[k] = split
    return out


# ── writers ───────────────────────────────────────────────────────────────────────────────────────────────────────
def loser_line(x: dict) -> str:
    r = x["row"]
    s = f"{r['date']} {r['symbol']} {setup_label(r['setup'])} · {x['text'] or '—'}"
    return s + (f" · {LG.REPLAY_CHIP}" if _replayed(x) else "")          # a ⏪ row never rang — labelled


def _apart(n_replayed) -> str:
    """The ⏪ count printed beside, never inside (LG._category_text convention, AMENDMENTS11 F13)."""
    return f" +{int(n_replayed)} ⏪" if n_replayed else ""


def _count_text(trades: int, rows: int, who: str = "loser") -> str:
    return f"{_plural(trades, who + ' trade', who + ' trades')} ({_plural(rows, 'row', 'rows')})"


def _winner_text(k: str, n: int) -> str:
    s = _plural(n, "winner trade", "winner trades")
    return s + (f" at +1R ≤{GC.LEDGER_LOSS_FAST_MIN} min" if k == "C4" else "")   # fill_facts "fast" = time to +1R


def class_lines(cl: dict) -> list:
    flag = FLAG_TEXT.format(n=GC.LEDGER_LOSS_CLASS_FLAG_N)
    out = []
    for k in CLASS_KEYS:
        c = cl[k]
        s = f"{k} {class_label(k)} · {_count_text(c['trades'], c['rows'])}{_apart(c.get('replayed_trades'))}"
        if c["winner_trades"] is not None:
            s += f" · {_winner_text(k, c['winner_trades'])}{_apart(c.get('replayed_winner_trades'))}"
        if c["flagged"]:
            s += f" · {flag}"
        out.append(s)
    for k, lab in (("C9", setup_label), ("C10", lambda v: LG.RANG_TEXT.get(v, v))):
        if not cl[k]:
            out.append(f"{k} {class_label(k)} · {EMPTY_TEXT}")
        for v, c in sorted(cl[k].items()):
            out.append(f"{k} {class_label(k)} · {lab(v)} · {_count_text(c['trades'], c['rows'])}"
                       f"{_apart(c.get('replayed_trades'))}")
    return out


def write_md(path: Path, res: dict, cl: dict, source: str, include_replayed: bool) -> None:
    lines_txt = ("live + shadow + ⏪ replayed (replayed rows never rang)" if include_replayed
                 else "live + shadow (⏪ replayed rows excluded)")
    n_l = sum(1 for x in res["losers"] if not _replayed(x))
    n_rl = len(res["losers"]) - n_l
    n_w = sum(1 for w in res["winners"] if not _replayed(w))
    n_rw = len(res["winners"]) - n_w
    out = [TITLE, "", f"**{DESCRIPTIVE_TEXT}.** {STUDY_TEXT}", "",
           f"- Source: {source}",
           f"- Lines: {lines_txt}; both kinds (🧠 potential, 🚩 A+)",
           f"- Docs read: {res['docs']} · not a row: {res['skipped']} · loser rows: {n_l}{_apart(n_rl)} · loser "
           f"trades: {len(res['trades'])}{_apart(len(res.get('replay_trades') or {}))} · winner rows: "
           f"{n_w}{_apart(n_rw)}",
           f"- {TRADE_TEXT}",
           f"- Classes declared before the count (DECISIONS11 D13); a class with {GC.LEDGER_LOSS_CLASS_FLAG_N} or "
           f"more loser trades is marked “{FLAG_TEXT.format(n=GC.LEDGER_LOSS_CLASS_FLAG_N)}” (Rule #9, never a "
           f"gate). C9 / C10 are splits, never flagged. “+N ⏪” = replayed trades counted apart — never in a count or "
           f"the flag.", "", "## Losers — one line each", ""]
    out += [f"- {loser_line(x)}" for x in res["losers"]] or [f"- {EMPTY_TEXT}"]
    out += ["", "## Classes — class · n", ""]
    out += [f"- {s}" for s in class_lines(cl)]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    return v


def write_csv(path: Path, res: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_HEAD)
        for x in res["losers"]:
            r, f = x["row"], x["facts"] or {}
            tk = _trade_key(r)
            flags = [_has(x, k) for k in CLASS_KEYS[:7]] + [x["trade_rows"] > 1]
            w.writerow([_cell(v) for v in (
                r["date"], r["symbol"], r["setup"], setup_label(r["setup"]), r["kind"], r["line"], r.get("rang"),
                r.get("trigger"), r.get("stop"), x["column"], f"{tk[0]}|{tk[1]}|{tk[2]}|{tk[3]}")]
                + [_cell(f.get(k)) for k in FACT_KEYS] + [_cell(b) for b in flags] + [x["text"] or ""])


# ── input ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def read_mongo(store, include_replayed: bool) -> Optional[list]:
    """§3.16 step 1 — None on ANY read fault (F5): ledger_dates / ledger_docs, and with the flag replay_dates /
    replay_rows. Reads only."""
    dates = store.ledger_dates()
    if dates is None:
        return None
    docs = store.ledger_docs(dates)
    if docs is None:
        return None
    docs = [d for d in docs if not (isinstance(d, dict) and _is_replay(d))]
    if include_replayed:
        rd = store.replay_dates()
        rep = store.replay_rows(rd) if rd is not None else None
        if rep is None:
            return None
        docs = list(docs) + [d for d in rep if isinstance(d, dict) and _is_replay(d)]
    return list(docs)


def read_json(path: str) -> Optional[list]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return None
    return data if isinstance(data, list) else None


def main(argv=None, *, store=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.gajjala_losers", description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-json", dest="from_json", metavar="FILE")
    src.add_argument("--mongo", action="store_true")
    ap.add_argument("--out", required=True, metavar="DIR")
    ap.add_argument("--include-replayed", dest="include_replayed", action="store_true")
    args = ap.parse_args(argv)
    if args.mongo:
        if store is None:
            from chart_maps.gajjala import store as ST
            store = ST.default()
        try:
            docs = read_mongo(store, args.include_replayed)
        except Exception:                                       # noqa: BLE001
            docs = None
        source = "--mongo (gajjala_ledger" + (" + gajjala_replay)" if args.include_replayed else ")")
    else:
        docs = read_json(args.from_json)
        source = f"--from-json {args.from_json}"
    if docs is None:
        print(UNREADABLE_TEXT)
        return 2
    res = collect(docs, args.include_replayed)
    cl = classes(res)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "losers.csv", res)
    write_md(out / "losers.md", res, cl, source, args.include_replayed)
    n_r = sum(1 for x in res["losers"] if _replayed(x))
    print(f"losers: {_plural(len(res['losers']) - n_r, 'row', 'rows')}{_apart(n_r)} · "
          f"{_plural(len(res['trades']), 'trade', 'trades')}{_apart(len(res['replay_trades']))} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
