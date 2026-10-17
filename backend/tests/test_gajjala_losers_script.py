"""❌ The losers study script (2026-10-16 night, DECISIONS11 D13, BUILD_SPEC11 §3.16 / §4 WP-E, AMENDMENTS11 F1 / F2 /
F4 / F5 / F14) — on the SYNTHETIC 6-row fixture tests/fixtures/gajjala/losers_ledger_2026_10_16.json:
(1) a 🧠 WIN · (2) an A+ shadow loss that rang AH, filled 09:46 next morning, stopped 3 min later, high +0.1R ·
(3) a 🧠 loss filled 15:40 ET, 70 min after the ring, high +0.9R then stopped · (4) + (5) one trade on two setups,
thin R · (6) a ⏪ replayed loss. Expectations are recomputed through LG.loss_facts (F2) — one engine.
Hermetic: no network, no Mongo (the --mongo path runs on an injected fake store)."""
from __future__ import annotations

import copy
import csv
import json
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from scripts import gajjala_losers as GL
from tests.test_gajjala_store import FakeColl, fake_store

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "losers_ledger_2026_10_16.json"
SRC = Path(GL.__file__).read_text(encoding="utf-8")
LOSER_KEYS = {("SYNB", "kiss_fly"), ("SYNC", "horizontal_fade"), ("SYND", "bull_flag"), ("SYND", "intraday_vcp")}
REPLAY_KEY = ("SYNR", "bull_flag")
WIN_KEY = ("SYNA", "bull_flag")


def _docs() -> list:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _write(tmp_path: Path, docs: list, name: str = "in.json") -> str:
    p = tmp_path / name
    p.write_text(json.dumps(docs), encoding="utf-8")
    return str(p)


def _run(tmp_path: Path, docs=None, *extra, out="out") -> tuple:
    src = str(FIXTURE) if docs is None else _write(tmp_path, docs)
    o = tmp_path / out
    rc = GL.main(["--from-json", src, "--out", str(o), *extra])
    return rc, o


def _csv(o: Path) -> list:
    with (o / "losers.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _md(o: Path) -> str:
    return (o / "losers.md").read_text(encoding="utf-8")


def _class_line(md: str, k: str) -> str:
    hits = [ln for ln in md.splitlines() if ln.startswith(f"- {k} ")]
    assert len(hits) == 1, (k, hits)
    return hits[0]


def _independent_row(doc: dict) -> dict:
    """The test's OWN reading of a fixture doc (not the script's row_of) — the ledger engine then answers the facts."""
    if doc["_id"].startswith(LG.REPLAY_ID_PREFIX):
        return LG.alert_of(doc, "aplus")
    a = doc["alert"]
    return {"date": doc["date"], "symbol": doc["symbol"], "setup": doc["setup"], "kind": doc["kind"],
            "line": doc["line"], "trigger": a["trigger"], "stop": a["stop"], "r": a["r"], "thin": a["thin"],
            "rang": a["rang"], "plan": a["plan"], "at_utc": LG._parse_at(a["at"])}


def _loss_col(doc: dict):
    nxt = doc.get("next") if isinstance(doc.get("next"), dict) else None
    return nxt if nxt is not None and LG._state_of(nxt) == "loss" else doc["same"]


def _expected_classes(docs: list) -> dict:
    """F1 / F2: per class, the distinct TRADES (date, symbol, trigger, stop) whose loser rows carry the engine's fact."""
    facts = {"C1": "next_morning", "C2": "late_rth", "C3": "stale", "C4": "fast", "C5": "no_progress",
             "C6": "gave_back", "C7": "thin"}
    trades: dict = {}
    for d in docs:
        row = _independent_row(d)
        f = LG.loss_facts(row, _loss_col(d))
        if f is None:
            continue
        trades.setdefault((row["date"], row["symbol"], row["trigger"], row["stop"]), []).append(f)
    out = {}
    for k, fact in facts.items():
        hit = [[f for f in fs if f[fact]] for fs in trades.values()]
        hit = [h for h in hit if h]
        out[k] = (len(hit), sum(len(h) for h in hit))
    dup = [fs for fs in trades.values() if len(fs) > 1]
    out["C8"] = (len(dup), sum(len(fs) for fs in dup))
    return out


def _count(n: int, rows: int) -> str:
    return (f"{n} loser trade{'' if n == 1 else 's'} ({rows} row{'' if rows == 1 else 's'})")


def _loser_docs(include_replayed=False) -> list:
    return [d for d in _docs() if (d["symbol"], d["setup"]) in LOSER_KEYS
            or (include_replayed and (d["symbol"], d["setup"]) == REPLAY_KEY)]


# ── smoke + the input filter ──────────────────────────────────────────────────────────────────────────────────────
def test_smoke_from_json_lists_rows_2_to_5_only(tmp_path):
    rc, o = _run(tmp_path)
    assert rc == 0
    rows = _csv(o)
    assert {(r["symbol"], r["setup"]) for r in rows} == LOSER_KEYS
    assert len(rows) == 4
    assert tuple(rows[0].keys()) == GL.CSV_HEAD
    assert (o / "losers.md").exists()


def test_negative_the_win_never_appears(tmp_path):
    rc, o = _run(tmp_path, None, "--include-replayed")
    assert rc == 0
    assert all(r["symbol"] != WIN_KEY[0] for r in _csv(o))
    assert WIN_KEY[0] not in _md(o).split("## Losers", 1)[1].split("## Classes", 1)[0]


def test_negative_replayed_row_absent_by_default_present_with_the_flag(tmp_path):
    _rc, o = _run(tmp_path, None, out="default")
    assert REPLAY_KEY not in {(r["symbol"], r["setup"]) for r in _csv(o)}
    assert REPLAY_KEY[0] not in _md(o)
    rc, o2 = _run(tmp_path, None, "--include-replayed", out="with")
    assert rc == 0
    rows = {(r["symbol"], r["setup"]): r for r in _csv(o2)}
    assert set(rows) == LOSER_KEYS | {REPLAY_KEY}
    assert rows[REPLAY_KEY]["line"] == "replayed"
    assert REPLAY_KEY[0] in _md(o2)


def test_negative_a_replay_doc_never_reads_as_a_ledger_row_without_the_flag(tmp_path):
    """A REPLAY: doc whose shape also passes as a ledger doc (kind + line) is still dropped by default."""
    rep = copy.deepcopy(next(d for d in _docs() if d["_id"].startswith(LG.REPLAY_ID_PREFIX)))
    rep["line"] = "shadow"
    _rc, o = _run(tmp_path, [rep])
    assert _csv(o) == []


# ── the classes (F1 / F2 / F14) ───────────────────────────────────────────────────────────────────────────────────
def test_class_table_equals_the_engine_counts(tmp_path):
    _rc, o = _run(tmp_path)
    md = _md(o)
    exp = _expected_classes(_loser_docs())
    assert exp == {"C1": (1, 1), "C2": (1, 1), "C3": (1, 1), "C4": (1, 1), "C5": (1, 1), "C6": (1, 1),
                   "C7": (1, 2), "C8": (1, 2)}
    for k, (n, rows) in exp.items():
        assert f" · {_count(n, rows)}" in _class_line(md, k), k
    assert md.count("- C9 ") == 4                                   # one split line per setup
    assert md.count("- C10 ") == 2                                  # rang AH + rang RTH
    assert f"{GL.setup_label('bull_flag')} · {_count(1, 1)}" in md
    assert f"{LG.RANG_TEXT['rth']} · {_count(2, 3)}" in md
    assert f"{LG.RANG_TEXT['ah']} · {_count(1, 1)}" in md


def test_f2_row_2_is_c1_and_not_c3(tmp_path):
    d2 = next(d for d in _docs() if d["symbol"] == "SYNB")
    f = LG.loss_facts(_independent_row(d2), _loss_col(d2))
    assert f["next_morning"] is True and f["stale"] is False and f["fill_after_min"] >= GC.LEDGER_LOSS_STALE_FILL_MIN
    _rc, o = _run(tmp_path, [d2])
    md = _md(o)
    assert f" · {_count(1, 1)}" in _class_line(md, "C1")
    assert f" · {_count(0, 0)}" in _class_line(md, "C3")
    row = _csv(o)[0]
    assert (row["c1"], row["c3"], row["c4"], row["c5"], row["loss_column"]) == ("1", "0", "1", "1", "next")


def test_negative_c8_with_two_rows_is_not_flagged(tmp_path):
    _rc, o = _run(tmp_path)
    md = _md(o)
    flag = GL.FLAG_TEXT.format(n=GC.LEDGER_LOSS_CLASS_FLAG_N)
    assert flag not in _class_line(md, "C8")
    assert not any(flag in ln for ln in md.splitlines() if re.match(r"- C\d+ ", ln))


def _three_c4(docs: list) -> list:
    d2 = next(d for d in docs if d["symbol"] == "SYNB")
    out = [d for d in docs]
    for sym in ("SYNE", "SYNF"):
        c = copy.deepcopy(d2)
        c["symbol"], c["_id"] = sym, c["_id"].replace("SYNB", sym)
        out.append(c)
    return out


def test_three_c4_loser_trades_flag_c4_and_the_constant_mutation_unflags(tmp_path, monkeypatch):
    docs = _three_c4(_docs())
    flag = GL.FLAG_TEXT.format(n=GC.LEDGER_LOSS_CLASS_FLAG_N)
    assert flag == "≥3 → candidate rule — HIS CALL"
    _rc, o = _run(tmp_path, docs, out="three")
    md = _md(o)
    assert _class_line(md, "C4").endswith(f" · {flag}")
    assert f" · {_count(3, 3)}" in _class_line(md, "C4")
    assert flag not in _class_line(md, "C2")                       # 1 trade
    ah = [ln for ln in md.splitlines() if ln.startswith("- C10 ") and LG.RANG_TEXT["ah"] in ln]
    assert ah and _count(3, 3) in ah[0] and "candidate rule" not in ah[0]   # NEGATIVE: C10 is a split, never flagged
    assert not any("candidate rule" in ln for ln in md.splitlines() if ln.startswith("- C9 "))
    monkeypatch.setattr(GC, "LEDGER_LOSS_CLASS_FLAG_N", 4)
    _rc, o4 = _run(tmp_path, docs, out="four")
    md4 = _md(o4)
    assert "candidate rule" not in _class_line(md4, "C4")
    assert "≥4 → candidate rule — HIS CALL" in md4                 # the header reads the constant at call time


def test_f1_three_rows_of_one_trade_count_as_one_trade_never_flagged(tmp_path):
    d2 = next(d for d in _docs() if d["symbol"] == "SYNB")
    docs = []
    for setup in ("kiss_fly", "bull_flag", "intraday_vcp"):
        c = copy.deepcopy(d2)
        c["setup"], c["_id"] = setup, c["_id"].replace("kiss_fly", setup)
        docs.append(c)
    _rc, o = _run(tmp_path, docs)
    md = _md(o)
    for k in ("C1", "C4", "C5", "C8"):
        line = _class_line(md, k)
        assert f" · {_count(1, 3)}" in line, (k, line)
        assert "candidate rule" not in line
    assert len(_csv(o)) == 3 and {r["c8"] for r in _csv(o)} == {"1"}
    assert "loser trades: 1" in md and "loser rows: 3" in md


def test_f14_winner_trades_counted_beside_c1_c4_and_c7_only(tmp_path):
    _rc, o = _run(tmp_path)
    md = _md(o)
    d1 = next(d for d in _docs() if d["symbol"] == "SYNA")
    ff = LG.fill_facts(_independent_row(d1), d1["same"])
    assert ff["fast"] is True and not ff["late_rth"] and not ff["next_morning"] and not ff["stale"]
    assert _class_line(md, "C4").endswith(f" · 1 winner trade at +1R ≤{GC.LEDGER_LOSS_FAST_MIN} min")
    assert not _class_line(md, "C4").endswith(" · 1 winner trade")   # NEGATIVE: C4's winner side is never unlabelled
    for k in ("C1", "C2", "C3", "C7"):
        assert _class_line(md, k).endswith(" · 0 winner trades"), k
    for k in ("C5", "C6", "C8"):
        assert "winner" not in _class_line(md, k), k                # stop-side facts / duplicates: no winner count


# ── the lines and the words ───────────────────────────────────────────────────────────────────────────────────────
def test_every_md_loser_line_is_the_ledger_loss_text(tmp_path):
    _rc, o = _run(tmp_path, None, "--include-replayed")
    md = _md(o)
    body = md.split("## Losers — one line each", 1)[1].split("## Classes", 1)[0]
    got = [ln[2:] for ln in body.splitlines() if ln.startswith("- ")]
    exp = []
    for d in _loser_docs(include_replayed=True):
        row = _independent_row(d)
        e, label = AL.SETUP_META[d["setup"]]
        text = LG.loss_text(row, _loss_col(d))
        assert text
        chip = f" · {LG.REPLAY_CHIP}" if d["_id"].startswith(LG.REPLAY_ID_PREFIX) else ""
        exp.append(f"{d['date']} {d['symbol']} {e} {label} · {text}{chip}")
    assert sorted(got) == sorted(exp)
    assert len(got) == 5
    by_sym = {r["symbol"] + r["setup"]: r["loss_text"] for r in _csv(o)}
    assert all(by_sym[d["symbol"] + d["setup"]] == LG.loss_text(_independent_row(d), _loss_col(d))
               for d in _loser_docs(include_replayed=True))


def _three_replayed(docs: list) -> list:
    rep = next(d for d in docs if d["_id"].startswith(LG.REPLAY_ID_PREFIX))
    out = []
    for sym in ("SYNR", "SYNS", "SYNT"):
        c = copy.deepcopy(rep)
        c["symbol"], c["_id"] = sym, c["_id"].replace("SYNR", sym)
        out.append(c)
    return out


def test_negative_three_replayed_c4_losers_never_flag_and_every_line_carries_the_chip(tmp_path):
    """House rule: a ⏪ row never rang — labelled on its line, counted apart, never in a class count or the flag."""
    reps = _three_replayed(_docs())
    for d in reps:
        f = LG.loss_facts(_independent_row(d), _loss_col(d))
        assert f is not None and f["fast"] is True                  # the engine reads each one as C4
    flag = GL.FLAG_TEXT.format(n=GC.LEDGER_LOSS_CLASS_FLAG_N)
    rc, o = _run(tmp_path, reps, "--include-replayed")
    assert rc == 0
    md = _md(o)
    c4 = _class_line(md, "C4")
    assert f" · {_count(0, 0)} +3 ⏪" in c4
    assert "candidate rule" not in c4 and flag not in c4
    assert not any("candidate rule" in ln for ln in md.splitlines() if re.match(r"- C\d+ ", ln))
    for ln in md.splitlines():
        if ln.startswith("- C10 ") or ln.startswith("- C9 "):
            assert _count(0, 0) in ln and "+3 ⏪" in ln, ln         # the splits count them apart too
    body = md.split("## Losers — one line each", 1)[1].split("## Classes", 1)[0]
    lines = [ln[2:] for ln in body.splitlines() if ln.startswith("- ")]
    assert len(lines) == 3 and all(ln.endswith(f" · {LG.REPLAY_CHIP}") for ln in lines)
    assert "loser rows: 0 +3 ⏪" in md and "loser trades: 0 +3 ⏪" in md
    assert {r["line"] for r in _csv(o)} == {LG.LINES[2]}
    mixed = _three_c4(_docs()) + reps                              # 3 live C4 + 3 ⏪ C4: the flag reads the 3 live
    _rc, o2 = _run(tmp_path, mixed, "--include-replayed", out="mixed")
    md2 = _md(o2)
    assert f" · {_count(3, 3)} +3 ⏪" in _class_line(md2, "C4") and _class_line(md2, "C4").endswith(f" · {flag}")
    body2 = md2.split("## Losers — one line each", 1)[1].split("## Classes", 1)[0]
    live = [ln for ln in body2.splitlines() if ln.startswith("- ") and "SYNR" not in ln and "SYNS" not in ln
            and "SYNT" not in ln]
    assert live and not any(LG.REPLAY_CHIP in ln for ln in live)   # NEGATIVE: a live line is never chipped


@pytest.mark.parametrize("extra", [(), ("--include-replayed",)])
def test_negative_the_files_quote_no_percent_no_score_no_causal_word(tmp_path, extra):
    _rc, o = _run(tmp_path, _three_c4(_docs()), *extra)
    for text in (_md(o), (o / "losers.csv").read_text(encoding="utf-8")):
        assert not re.search(r"\d\s*%", text)
        assert not re.search(r"win rate|expectancy|verdict|\bedge\b", text, re.I)
        assert not re.search(r"\bbecause\b|\bwhy\b|due to|\bcaused?\b", text, re.I)
        assert not re.search(r"bounc|\bfake\b|\bwill\b|\blikely\b", text, re.I)
        assert "None" not in text and "nan" not in text.lower().split()
    md = _md(o)
    assert GL.DESCRIPTIVE_TEXT in md and "UNMEASURED" in md and "NULL" in md


def test_negative_the_source_never_imports_the_study_or_another_method():
    imports = [ln.strip() for ln in SRC.splitlines() if re.match(r"\s*(from|import)\s", ln)]
    assert not any("gajjala_study" in ln or "scripts" in ln for ln in imports)
    assert "gajjala_study" not in SRC
    assert not re.search(r"^\s*(from|import)\s+(sepa|bonde)\b", SRC, re.M)
    mods = {m for ln in imports for m in re.findall(r"from (chart_maps\.gajjala) import (\w+)", ln)}
    assert {m[1] for m in mods} <= {"ledger", "constants", "store"}
    assert not re.search(r"win rate|expectancy|verdict|because|due to|caused", SRC, re.I)
    for n in ("5", "30", "60", "0.3", "0.8"):                      # the thresholds are read by name, never retyped
        assert not re.search(rf"(?<![\w.]){re.escape(n)}(?![\w.])", SRC.split('"""', 2)[2]), n
    assert not re.search(r"[<>=]=?\s*(?:3|5|30|60|0\.3|0\.8)(?![\w.])", SRC.split('"""', 2)[2])   # no compare on a literal
    for name in ("LEDGER_LOSS_LATE_RTH_MIN", "LEDGER_LOSS_STALE_FILL_MIN", "LEDGER_LOSS_FAST_MIN",
                 "LEDGER_LOSS_NO_PROGRESS_R", "LEDGER_LOSS_GAVE_BACK_R", "LEDGER_LOSS_CLASS_FLAG_N"):
        assert f"GC.{name}" in SRC
    for fn in ("LG.bucket_of(", "LG.loss_facts(", "LG.loss_text(", "LG.fill_facts(", "LG._state_of("):
        assert fn in SRC


# ── F4: a missing column reads pending ────────────────────────────────────────────────────────────────────────────
def test_f4_same_only_loss_is_a_loser_same_only_win_is_not_neither_raises(tmp_path):
    docs = _docs()
    d1 = next(d for d in docs if d["symbol"] == "SYNA")
    d3 = next(d for d in docs if d["symbol"] == "SYNC")
    assert "next" not in d1 and "next" not in d3
    bare = copy.deepcopy(d3)
    bare["symbol"], bare["_id"] = "SYNZ", bare["_id"].replace("SYNC", "SYNZ")
    del bare["same"]
    junk = [None, "x", {"_id": "j"}, {"_id": "2026-10-13|SYNY|bull_flag|aplus", "date": "2026-10-13",
                                       "symbol": "SYNY", "setup": "bull_flag", "kind": "aplus", "line": "bogus"}]
    rc, o = _run(tmp_path, [d1, d3, bare] + junk)
    assert rc == 0
    assert [(r["symbol"], r["loss_column"]) for r in _csv(o)] == [("SYNC", "same")]
    assert "not a row: 2" in _md(o)


def test_empty_list_still_writes_both_files(tmp_path):
    rc, o = _run(tmp_path, [])
    assert rc == 0
    assert _csv(o) == []
    md = _md(o)
    assert f"- {GL.EMPTY_TEXT}" in md
    assert f" · {_count(0, 0)}" in _class_line(md, "C1")


def test_negative_an_unreadable_json_writes_nothing(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    o = tmp_path / "out"
    assert GL.main(["--from-json", str(bad), "--out", str(o)]) == 2
    assert not o.exists()
    assert GL.UNREADABLE_TEXT in capsys.readouterr().out
    bad.write_text('{"docs": []}', encoding="utf-8")                # not a list
    assert GL.main(["--from-json", str(bad), "--out", str(o)]) == 2
    assert not o.exists()
    with pytest.raises(SystemExit):
        GL.main(["--out", str(o)])                                  # one of --from-json / --mongo is required
    with pytest.raises(SystemExit):
        GL.main(["--from-json", str(FIXTURE), "--mongo", "--out", str(o)])


# ── --mongo (an injected fake store; reads only) ──────────────────────────────────────────────────────────────────
class RecStore:
    """Wraps a fake GajjalaStore: records every method called; `answers` forces a method's return (None = a fault)."""

    def __init__(self, inner, answers=None):
        self.inner, self.calls, self.answers = inner, [], dict(answers or {})

    def __getattr__(self, name):
        attr = getattr(self.inner, name)
        if not callable(attr):
            return attr

        def fn(*a, **k):
            self.calls.append(name)
            if name in self.answers:
                return self.answers[name]
            return attr(*a, **k)
        return fn


def _mongo_store(answers=None) -> tuple:
    docs = _docs()
    led = FakeColl([d for d in docs if not d["_id"].startswith(LG.REPLAY_ID_PREFIX)])
    rep = FakeColl([d for d in docs if d["_id"].startswith(LG.REPLAY_ID_PREFIX)])
    colls = {ST.LEDGER: led, ST.REPLAY: rep}
    inner = fake_store(**colls)
    return RecStore(inner, answers), inner


def _writes(inner) -> int:
    return sum(inner.coll(n).writes for n in ST.ALL)


def test_mongo_reads_ledger_dates_then_docs_and_never_writes(tmp_path):
    st, inner = _mongo_store()
    o = tmp_path / "m"
    assert GL.main(["--mongo", "--out", str(o)], store=st) == 0
    assert st.calls == ["ledger_dates", "ledger_docs"]
    assert _writes(inner) == 0
    assert {(r["symbol"], r["setup"]) for r in _csv(o)} == LOSER_KEYS
    assert "--mongo" in _md(o)
    st2, inner2 = _mongo_store()
    o2 = tmp_path / "m2"
    assert GL.main(["--mongo", "--out", str(o2), "--include-replayed"], store=st2) == 0
    assert st2.calls == ["ledger_dates", "ledger_docs", "replay_dates", "replay_rows"]
    assert _writes(inner2) == 0
    assert {(r["symbol"], r["setup"]) for r in _csv(o2)} == LOSER_KEYS | {REPLAY_KEY}
    _rc, oj = _run(tmp_path, None, "--include-replayed", out="j")
    assert _csv(o2) == _csv(oj)                                     # one engine: the same rows from either source


@pytest.mark.parametrize("answers,extra", [
    ({"ledger_dates": None}, ()),
    ({"ledger_docs": None}, ()),
    ({"replay_rows": None}, ("--include-replayed",)),
    ({"replay_dates": None}, ("--include-replayed",)),
])
def test_negative_f5_a_read_fault_exits_2_and_writes_nothing(tmp_path, capsys, answers, extra):
    st, inner = _mongo_store(answers)
    o = tmp_path / "m"
    assert GL.main(["--mongo", "--out", str(o), *extra], store=st) == 2
    assert not o.exists()
    assert capsys.readouterr().out.strip() == GL.UNREADABLE_TEXT
    assert _writes(inner) == 0


def test_negative_a_replay_fault_without_the_flag_is_never_read(tmp_path):
    st, _inner = _mongo_store({"replay_rows": None, "replay_dates": None})
    o = tmp_path / "m"
    assert GL.main(["--mongo", "--out", str(o)], store=st) == 0
    assert "replay_rows" not in st.calls and "replay_dates" not in st.calls


def test_negative_a_raising_store_is_unreadable_not_empty(tmp_path, capsys):
    inner = fake_store(**{ST.LEDGER: FakeColl(fail=True)})
    o = tmp_path / "m"
    assert GL.main(["--mongo", "--out", str(o)], store=inner) == 2
    assert not o.exists()
