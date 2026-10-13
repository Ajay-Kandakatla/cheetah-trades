"""✨ Growth arrivals on the payload — 2026-10-12.

Ajay: "In the eplosive growth there are 7 new one ... special emphasis wiht a
tag or something in the chart map pages top ..." then "I saw an alert for 7 in
explosive growth". The 7 was the push's MAX_INDIVIDUAL spill; 11 arrived.

What this file defends:

1. **Field-for-field pins.** `arrivals.ARRIVALS_MEASURED` — the lift AND the
   momentum-matched control — equals `backend/scripts/board_growth_measured.json`
   cell `G100_ARRIVE`. A re-run that moves a number fails here instead of
   quietly rewriting the served sentence (the `test_bonde_steady_label.py`
   pattern).
2. **Honesty.** Every lift interval spans zero on both clusterings, so the line
   may never claim a finding; the control's sign count is computed; real minus
   per number, never a sentence-wide replace.
3. **One ledger read.** `tracker.arrivals_map` is the read `newly_found` wraps;
   `attach` marks every row, keeps served order, never re-derives `liquid`.
4. **Never takes a tab down.** A failing attach leaves `/growth/board` and
   `/growth/tags` serving, with `arrivals == []`.

Rule #10: nothing here sorts, filters, gates or pushes.
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from growth import arrivals as AR
from growth import tracker as T
from growth.screen_measured import screen_clause
from sepa.board_arrival import NOT_A_RECOMMENDATION

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ARTIFACT = BACKEND / "scripts" / "board_growth_measured.json"
HORIZONS = ("h21", "h63", "h126")
MINUS = "−"  # U+2212


# ─────────────────────────────────────────────────────────── fixtures
@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text())


@pytest.fixture(scope="module")
def arrive_cell(art) -> dict:
    return art["cells"]["G100_ARRIVE"]


@pytest.fixture(scope="module")
def line() -> str:
    return AR.honesty_line()


def r2(pair) -> tuple:
    return tuple(round(float(x), 2) for x in pair)


class FakeColl:
    """The `tests/test_growth_seen.py` fake, with the `first_seen` projection
    honoured so the test sees exactly what `arrivals_map` asks for."""

    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.find_calls = 0

    def update_one(self, flt, update, upsert=False):
        _id = flt["_id"]
        cur = self.docs.get(_id)
        if cur is None:
            if not upsert:
                return
            cur = {"_id": _id}
            cur.update(update.get("$setOnInsert", {}))
            self.docs[_id] = cur
        cur.update(update.get("$set", {}))

    def find_one(self, flt, *a, **k):
        return self.docs.get(flt.get("_id"))

    def find(self, flt, projection=None, *a, **k):
        self.find_calls += 1
        ne = (flt.get("_id") or {}).get("$ne")
        gt = (flt.get("first_seen") or {}).get("$gt")
        out = [d for d in self.docs.values()
               if d["_id"] != ne and str(d.get("first_seen", "")) > str(gt)]
        if projection:
            keep = {k for k, v in projection.items() if v}
            out = [{k: v for k, v in d.items() if k in keep or k == "_id"} for d in out]
        return out


class FakeDB:
    def __init__(self):
        self.coll = FakeColl()

    def __getitem__(self, name):
        assert name == T.SEEN_COLL
        return self.coll


class BrokenDB:
    def __getitem__(self, name):
        raise RuntimeError("mongo went away")


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def ledger(tracking_days_ago: float = 60, **first_seen_days_ago) -> FakeDB:
    db = FakeDB()
    db.coll.docs["__meta__"] = {"_id": "__meta__", "tracking_since": iso(tracking_days_ago)}
    for sym, d in first_seen_days_ago.items():
        db.coll.docs[sym] = {"_id": sym, "first_seen": iso(d), "last_seen": iso(0)}
    return db


# ──────────────────────────────────────── 1. field-for-field pins (lift)
@pytest.mark.parametrize("h", HORIZONS)
def test_the_lift_constants_equal_the_artifact_at_every_horizon(h, arrive_cell):
    got = AR.ARRIVALS_MEASURED["lift"][h]
    cell = arrive_cell[h]
    assert got["n"] == cell["n"]
    assert got["n_symbols"] == cell["n_symbols"]
    assert got["n_dates"] == cell["n_dates"]
    assert got["median_lift_pp"] == cell["median_lift_vs_all_scored_pp"]
    assert tuple(got["ci_symbol"]) == r2(cell["lift_ci_symbol"])
    assert tuple(got["ci_date"]) == r2(cell["lift_ci_date"])


def test_the_provenance_points_at_real_files_and_the_right_cell(art):
    m = AR.ARRIVALS_MEASURED
    assert m["panel_dates"] == art["repro"]["n_dates_panel"]
    assert m["cell"] == "G100_ARRIVE"
    assert m["run_date"] == "2026-09-21"
    assert (ROOT / m["doc"]).is_file()
    assert (ROOT / m["script"]).is_file()


# ──────────────────────────────── 1b. field-for-field pins (momentum control)
@pytest.mark.parametrize("h", HORIZONS)
def test_the_momentum_control_constants_equal_the_artifact(h, arrive_cell):
    got = AR.ARRIVALS_MEASURED["momentum_control"][h]
    cell = arrive_cell[h]["momentum_control"]
    assert got["n"] == cell["n"]
    assert got["mean_excess_pp"] == round(cell["mean_excess_pp"], 2)
    assert got["median_excess_pp"] == round(cell["median_excess_pp"], 2)
    assert tuple(got["ci_symbol"]) == r2(cell["ci_symbol"])
    assert "ci_date" not in cell, "an unread date CI would silence the caveat"
    assert "ci_date" not in got


def test_the_control_sign_count_is_pinned_and_the_line_says_it(arrive_cell, line):
    """A re-run that flips a control sign fails here — revisit the wording."""
    neg = sum(1 for h in HORIZONS if arrive_cell[h]["momentum_control"]["median_excess_pp"] < 0)
    assert neg == 2
    assert "negative at 2 of 3 horizons" in line


def test_NEGATIVE_the_sign_count_is_computed_not_typed(monkeypatch):
    m = json.loads(json.dumps(AR.ARRIVALS_MEASURED))
    m["momentum_control"]["h63"]["median_excess_pp"] = 0.5
    monkeypatch.setattr(AR, "ARRIVALS_MEASURED", m)
    out = AR.honesty_line()
    assert "negative at 1 of 3 horizons" in out
    assert "negative at 2 of 3" not in out


# ──────────────────────────────────────────────────────── 2. honesty
@pytest.mark.parametrize("h", HORIZONS)
def test_every_artifact_lift_interval_spans_zero_on_both_clusterings(h, arrive_cell):
    """The line says 'No lift interval clears zero'. If a re-run ever clears
    zero this fails, and the wording is revisited — never silently kept."""
    for key in ("lift_ci_symbol", "lift_ci_date"):
        lo, hi = arrive_cell[h][key]
        assert lo < 0 < hi, f"{h} {key} no longer spans zero — revisit honesty_line()"


@pytest.mark.parametrize("needle", [
    "MEASURED 2026-09-21", "+3.69pp", "−0.22 to +10.13", "−0.43 to +11.77",
    "+5.58pp", "+8.93pp", "No lift interval clears zero", "momentum-matched",
    "+1.37pp", "−1.10pp", "−6.38pp", "+1.65 to +11.83", "symbol-clustered only",
    "LIST EVENT, NOT A SIGNAL", "A lean, not a finding.",
])
def test_the_line_carries_each_number_and_caveat(needle, line):
    assert needle in line


def test_the_line_carries_the_not_a_recommendation_constant_verbatim(line):
    assert NOT_A_RECOMMENDATION["growth"] in line


def test_NEGATIVE_the_line_never_says_unmeasured_beside_MEASURED(line):
    """No never-measured claim beside a line that opens "MEASURED 2026-09-21"
    (the old push constant said "never been measured forward"; renamed
    2026-10-12 to `SCREEN_MEASURED_CLAUSE`). And the two cells are never
    concatenated: the screen clause (G100, one interval clears zero) next to
    this line (G100_ARRIVE, "No lift interval clears zero") would contradict."""
    assert "never been measured" not in line.lower()
    assert "nothing here is backtested" not in line.lower()
    assert screen_clause() not in line


def test_the_line_is_one_string():
    assert isinstance(AR.honesty_line(), str)
    assert "\n" not in AR.honesty_line()


@pytest.mark.parametrize("banned", ["clear of zero", "significant", "edge", "bounce", "buy"])
def test_NEGATIVE_the_line_never_claims_more_than_the_replay(banned, line):
    assert banned not in line.lower()


def test_NEGATIVE_the_line_never_quotes_a_mean_without_its_median(line):
    """The control's MEAN interval is printed; its MEDIAN must be beside it."""
    assert "MEDIAN excess" in line and "interval is on the MEAN" in line


# ──────────────────────────────────────────────── 2b. hyphen integrity
@pytest.mark.parametrize("v, want", [(-0.22, "−0.22"), (3.69, "+3.69"),
                                     (24.0, "+24.00"), (0, "+0.00"), (-11.9, "−11.90")])
def test_sgn_signs_every_number_with_a_real_minus(v, want):
    assert AR._sgn(v) == want


@pytest.mark.parametrize("lit", ["2026-09-21", "point-in-time", "symbol-clustered",
                                 "date-clustered", "momentum-matched", "symbol-bars"])
def test_ascii_hyphens_in_words_survive(lit, line):
    assert lit in line


def test_NEGATIVE_no_real_minus_ever_touches_a_letter(line):
    assert re.search(r"[A-Za-z]−|−[A-Za-z]", line) is None


def test_NEGATIVE_no_ascii_minus_in_front_of_a_number(line):
    assert re.search(r"(?<![0-9A-Za-z])-[0-9]", line) is None


def test_NEGATIVE_the_source_never_replaces_hyphens_sentence_wide():
    src = (BACKEND / "growth" / "arrivals.py").read_text()
    assert '.replace("-"' not in src and ".replace('-'" not in src


# ─────────────────────────────────────────────── 3. tracker.arrivals_map
def test_arrivals_map_returns_symbol_to_stamp_inside_the_window():
    db = ledger(60, NEW1=3, NEW2=10, OLD=45)
    got = T.arrivals_map(days=30, db=db)
    assert set(got) == {"NEW1", "NEW2"}
    assert got["NEW1"] == db.coll.docs["NEW1"]["first_seen"]


def test_arrivals_map_is_one_projected_find():
    db = ledger(60, NEW1=3)
    T.arrivals_map(db=db)
    assert db.coll.find_calls == 1


def test_NEGATIVE_the_first_cohort_is_never_new():
    db = FakeDB()
    T._record_seen([{"symbol": "AAA"}, {"symbol": "BBB"}], db=db)
    assert db.coll.docs["AAA"]["first_seen"] == db.coll.docs["__meta__"]["tracking_since"]
    assert T.arrivals_map(db=db) == {}


def test_NEGATIVE_no_meta_row_means_nothing_is_new():
    db = ledger(60, NEW1=3)
    del db.coll.docs["__meta__"]
    assert T.arrivals_map(db=db) == {}


def test_NEGATIVE_no_db_means_nothing_is_new(monkeypatch):
    monkeypatch.setattr(T, "_db", lambda: None)
    assert T.arrivals_map() == {}
    assert T.newly_found() == set()


def test_NEGATIVE_a_broken_db_returns_empty_and_never_raises():
    assert T.arrivals_map(db=BrokenDB()) == {}
    assert T.newly_found(db=BrokenDB()) == set()


def test_NEGATIVE_a_doc_with_an_empty_stamp_is_never_new():
    """Belt and braces: a lenient backend that returns a doc whose first_seen
    is empty must not produce a key."""
    db = ledger(60, NEW1=3)

    class Lenient(FakeColl):
        def find(self, flt, projection=None, *a, **k):
            return [{"_id": "NEW1", "first_seen": db.coll.docs["NEW1"]["first_seen"]},
                    {"_id": "EMPTY", "first_seen": ""}, {"_id": "MISSING"}]

    lc = Lenient()
    lc.docs = db.coll.docs
    db.coll = lc
    assert set(T.arrivals_map(db=db)) == {"NEW1"}


def test_newly_found_is_exactly_the_keys_of_arrivals_map():
    db = ledger(60, NEW1=3, NEW2=10, OLD=45)
    assert T.newly_found(db=db) == set(T.arrivals_map(db=db)) == {"NEW1", "NEW2"}


# ──────────────────────────────────────────────────────── 4. attach
def test_attach_marks_every_row_and_keeps_served_order():
    db = ledger(60, ZZZ=2, AAA=5)
    rows = [{"symbol": "ZZZ", "liquid": True}, {"symbol": "MMM", "liquid": True},
            {"symbol": "AAA", "liquid": False}]
    out = AR.attach(rows, db=db)
    assert [a["symbol"] for a in out] == ["ZZZ", "AAA"], "served order, not alphabetical"
    assert rows[0]["is_new"] is True and rows[0]["first_seen"] == db.coll.docs["ZZZ"]["first_seen"]
    assert rows[2]["is_new"] is True and rows[2]["first_seen"]
    assert rows[1]["is_new"] is False and rows[1]["first_seen"] is None
    assert set(out[0]) == {"symbol", "first_seen", "liquid", "refused", "warnings"}


def test_NEGATIVE_a_ledger_name_not_on_the_board_is_absent():
    db = ledger(60, GONE=2, AAA=5)
    rows = [{"symbol": "AAA"}]
    assert [a["symbol"] for a in AR.attach(rows, db=db)] == ["AAA"]


def test_NEGATIVE_a_missing_or_empty_stamp_is_never_new(monkeypatch):
    monkeypatch.setattr(T, "arrivals_map", lambda days=30, db=None: {"AAA": "", "BBB": None})
    rows = [{"symbol": "AAA"}, {"symbol": "BBB"}]
    assert AR.attach(rows) == []
    assert all(r["is_new"] is False and r["first_seen"] is None for r in rows)


def test_NEGATIVE_no_db_marks_nothing(monkeypatch):
    monkeypatch.setattr(T, "_db", lambda: None)
    rows = [{"symbol": "AAA"}, {"symbol": "BBB"}]
    assert AR.attach(rows) == []
    assert all(r["is_new"] is False and r["first_seen"] is None for r in rows)


def test_NEGATIVE_attach_never_raises_when_the_read_raises(monkeypatch):
    def boom(**k):
        raise RuntimeError("x")
    monkeypatch.setattr(T, "arrivals_map", boom)
    rows = [{"symbol": "AAA"}]
    assert AR.attach(rows) == []
    assert rows[0]["is_new"] is False


def test_refused_is_true_only_for_a_no_entry_warning():
    db = ledger(60, BAD=2, WARN=2, CLEAN=2)
    rows = [{"symbol": "BAD", "warnings": ["⛔ cap $284M under the $700M floor"]},
            {"symbol": "WARN", "warnings": ["⚠️ thin tape"]},
            {"symbol": "CLEAN"}]
    out = {a["symbol"]: a for a in AR.attach(rows, db=db)}
    assert out["BAD"]["refused"] is True
    assert out["WARN"]["refused"] is False
    assert out["CLEAN"]["refused"] is False
    assert out["WARN"]["warnings"] == ["⚠️ thin tape"]
    assert out["CLEAN"]["warnings"] == []


def test_NEGATIVE_liquid_passes_through_and_is_never_re_derived():
    db = ledger(60, AAA=2, BBB=2)
    rows = [{"symbol": "AAA", "avg_dollar_vol": 9e12},
            {"symbol": "BBB", "liquid": 1, "avg_dollar_vol": 0}]
    out = {a["symbol"]: a for a in AR.attach(rows, db=db)}
    assert out["AAA"]["liquid"] is False, "no `liquid` key → False, never from avg_dollar_vol"
    assert out["BBB"]["liquid"] is True


def test_the_live_eleven_fixture_matches_the_parity_probe():
    """The 2026-10-12 read-only probe: 11 arrivals, 2 refused (MGNX, BMRC), 6
    liquid. Same fixture the main session's container probe diffs against."""
    liquid = ["PGEN", "BBT", "BW", "FBK", "KLIC", "AAON"]
    thin = ["RYM", "PED", "CHMG"]
    refused = ["MGNX", "BMRC"]
    syms = liquid + thin + refused
    db = ledger(30, **{s: 0.5 for s in syms})
    db.coll.docs["OLDONE"] = {"_id": "OLDONE", "first_seen": db.coll.docs["__meta__"]["tracking_since"]}
    rows = ([{"symbol": s, "liquid": True} for s in liquid]
            + [{"symbol": s, "liquid": False, "warnings": ["⚠️ cap unknown"]} for s in thin]
            + [{"symbol": s, "liquid": False, "warnings": ["⛔ under the cap floor"]} for s in refused]
            + [{"symbol": "OLDONE", "liquid": True}])
    out = AR.attach(rows, db=db)
    assert [a["symbol"] for a in out] == syms
    assert sum(a["refused"] for a in out) == 2
    assert sum(a["liquid"] for a in out) == 6
    s = AR.summary(out)
    assert s["arrivals_n"] == 11 and s["new_days"] == T.NEW_GROWTH_DAYS


def test_summary_carries_the_four_keys_and_touches_no_db(monkeypatch):
    monkeypatch.setattr(T, "_db", lambda: (_ for _ in ()).throw(AssertionError("db read")))
    s = AR.summary([{"symbol": "A"}])
    assert set(s) == {"arrivals", "arrivals_n", "new_days", "arrivals_note"}
    assert s["arrivals_n"] == 1 and s["arrivals_note"] == AR.honesty_line()
    assert AR.summary([])["arrivals_n"] == 0


# ─────────────────────────────────────────────────────── 5. _payload
def _two(rows, db=None, days=30):
    for r in rows:
        r["is_new"] = r["symbol"] in ("AAA", "BBB")
        r["first_seen"] = "2026-10-12T02:29:05+00:00" if r["is_new"] else None
    return [{"symbol": s, "first_seen": "2026-10-12T02:29:05+00:00", "liquid": True,
             "refused": False, "warnings": []} for s in ("AAA", "BBB")]


def _raise(*a, **k):
    raise RuntimeError("ledger down")


def test_payload_carries_the_arrival_keys(monkeypatch):
    from growth import api as GA
    monkeypatch.setattr(AR, "attach", _two)
    out = GA._payload({"rows": [{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}],
                       "built_at": None})
    assert out["arrivals_n"] == 2
    assert [a["symbol"] for a in out["arrivals"]] == ["AAA", "BBB"]
    assert out["new_days"] == T.NEW_GROWTH_DAYS
    assert out["arrivals_note"] == AR.honesty_line()
    assert [r["is_new"] for r in out["rows"]] == [True, True, False]


def test_NEGATIVE_a_raising_attach_never_takes_the_board_down(monkeypatch):
    from growth import api as GA
    monkeypatch.setattr(AR, "attach", _raise)
    out = GA._payload({"rows": [{"symbol": "AAA"}], "built_at": None})
    assert out["n"] == 1
    assert out["arrivals"] == [] and out["arrivals_n"] == 0
    assert out["arrivals_note"] == AR.honesty_line()
    assert "is_new" not in out["rows"][0]


def test_NEGATIVE_nan_in_a_row_is_scrubbed_with_arrivals_present(monkeypatch):
    from growth import api as GA
    monkeypatch.setattr(AR, "attach", _two)
    out = GA._payload({"rows": [{"symbol": "AAA", "price": float("nan")},
                                {"symbol": "BBB", "price": float("inf")}],
                       "built_at": None})
    s = json.dumps(out, allow_nan=False)
    assert "NaN" not in s and "Infinity" not in s
    assert out["rows"][0]["price"] is None and out["rows"][1]["price"] is None
    assert out["arrivals_n"] == 2


def test_NEGATIVE_payload_never_builds_the_board(monkeypatch):
    from growth import api as GA
    calls = []
    monkeypatch.setattr(T, "build", lambda *a, **k: calls.append(1))
    GA._payload({"rows": [{"symbol": "AAA"}], "built_at": None})
    assert calls == []


def test_without_mongo_the_payload_simply_has_no_arrivals():
    from growth import api as GA
    out = GA._payload({"rows": [{"symbol": "AAA"}], "built_at": None})
    assert out["arrivals"] == [] and out["arrivals_n"] == 0
    assert out["rows"][0]["is_new"] is False


# ─────────────────────────────────────────────────── 6. /growth/tags
def _tags_body(GA) -> dict:
    """The handler's sync body (2026-10-12: GET /growth/tags runs it under
    asyncio.to_thread). Round-tripped through JSON like the response."""
    return json.loads(json.dumps(GA._tags_payload(), allow_nan=False))


def _tags_via_handler(GA) -> dict:
    # A private loop, never asyncio.run(): that would leave the thread's loop
    # unset and break later tests that call get_event_loop().
    loop = asyncio.new_event_loop()
    try:
        resp = loop.run_until_complete(GA.growth_tags())
    finally:
        loop.close()
    assert resp.status_code == 200
    return json.loads(resp.body)


TAG_ROWS = [
    {"symbol": "PGEN", "sales_growth_pct": 300.0, "q_eps_growth_pct": 150.0,
     "liquid": True, "warnings": []},
    {"symbol": "MGNX", "sales_growth_pct": 200.0, "q_eps_growth_pct": 120.0,
     "liquid": False, "warnings": ["⛔ cap $284M under the $700M floor"]},
    {"symbol": "RYM", "sales_growth_pct": 150.0, "q_eps_growth_pct": 110.0,
     "liquid": False, "warnings": ["⚠️ cap unknown"]},
]
# The pre-change shape, pinned literally: the map must not have moved.
TAGS_BEFORE = {
    "n": 3,
    "tags": {
        "PGEN": {"sales": 300.0, "eps": 150.0, "refused": False},
        "MGNX": {"sales": 200.0, "eps": 120.0, "refused": True},
        "RYM": {"sales": 150.0, "eps": 110.0, "refused": False},
    },
}


def _board(monkeypatch):
    monkeypatch.setattr(T, "board", lambda: {"rows": json.loads(json.dumps(TAG_ROWS))})


def test_tags_map_is_unchanged_and_refused_is_the_one_rule(monkeypatch):
    from growth import api as GA
    _board(monkeypatch)
    body = _tags_body(GA)
    assert body["n"] == TAGS_BEFORE["n"]
    assert body["tags"] == TAGS_BEFORE["tags"]
    for r in TAG_ROWS:
        assert body["tags"][r["symbol"]]["refused"] is AR.refused(r)


def test_tags_carry_the_four_arrival_keys(monkeypatch):
    from growth import api as GA
    _board(monkeypatch)
    db = ledger(60, MGNX=1, PGEN=1)
    real = AR.attach
    monkeypatch.setattr(AR, "attach", lambda rows: real(rows, db=db))
    body = _tags_body(GA)
    assert {"arrivals", "arrivals_n", "new_days", "arrivals_note"} <= set(body)
    assert [a["symbol"] for a in body["arrivals"]] == ["PGEN", "MGNX"], "served order"
    assert body["arrivals_n"] == 2
    assert [a["refused"] for a in body["arrivals"]] == [False, True]
    assert body["tags"] == TAGS_BEFORE["tags"]


def test_NEGATIVE_a_raising_attach_never_takes_the_chip_map_down(monkeypatch):
    from growth import api as GA
    _board(monkeypatch)
    monkeypatch.setattr(AR, "attach", _raise)
    body = _tags_body(GA)
    assert body["tags"] == TAGS_BEFORE["tags"] and body["n"] == 3
    assert body["arrivals"] == [] and body["arrivals_n"] == 0


def test_the_handler_serves_exactly_the_sync_body(monkeypatch):
    """The to_thread move changed WHERE the body runs, not what it returns."""
    from growth import api as GA
    _board(monkeypatch)
    db = ledger(60, MGNX=1, PGEN=1)
    real = AR.attach
    monkeypatch.setattr(AR, "attach", lambda rows: real(rows, db=db))
    assert _tags_via_handler(GA) == _tags_body(GA)


def test_NEGATIVE_api_has_no_inline_copy_of_the_refused_rule():
    src = (BACKEND / "growth" / "api.py").read_text()
    assert 'startswith("⛔")' not in src
    assert "from . import arrivals as _arr" in src


# ───────────────────────────────────────── 7. import graph + Rule #10 guard
@pytest.mark.parametrize("first", ["", "import sepa.board_arrival; ",
                                   "import growth.arrivals; ", "import growth.alerts; ",
                                   "import growth.screen_measured; ",
                                   "import sepa.board_arrival; import growth.screen_measured; "])
def test_growth_api_imports_cleanly_in_a_fresh_interpreter(first):
    """The cycle pin. If board_arrival ever imports growth.api this fails —
    do not 'fix' it by moving the import into a try."""
    code = "import sys; sys.path.insert(0, '.'); " + first + "import growth.api"
    res = subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=BACKEND,
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr[-2000:]


def test_the_api_import_is_top_level_not_inside_a_try():
    src = (BACKEND / "growth" / "api.py").read_text()
    assert re.search(r"^from \. import arrivals as _arr$", src, re.M)


def test_NEGATIVE_no_served_growth_module_names_the_research_artifact():
    """Rule #10: the served constant is pinned BY this test; the module never
    reads `board_growth_measured.json`."""
    for p in (BACKEND / "growth").rglob("*.py"):
        assert "board_growth_measured" not in p.read_text(), p
    hits = subprocess.run(["git", "grep", "-l", "board_growth_measured", "--", "backend/growth"],
                          cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert hits == []


def test_NEGATIVE_the_module_sorts_filters_and_gates_nothing():
    src = (BACKEND / "growth" / "arrivals.py").read_text()
    for banned in ("sort(", "sorted(", "send_push", "alert_gates", "room_gate", "push."):
        assert banned not in src, banned
