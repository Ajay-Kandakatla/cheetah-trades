"""MEASURED 2026-09-21 — the 🚀 100/100 screen itself (cell G100). 2026-10-12.

Ajay's his-call #1 ("Reword those outdated 'never measured' lines?" -> yes).
The 2026-09-21 replay DID measure the screen; every backend surface that said
it "has never been measured forward" now serves `growth.screen_measured`.

What this file defends (the `test_growth_arrivals.py` shape):

1. **Field-for-field pins** of `SCREEN_MEASURED` against the replay's artifact
   cell `G100` — a re-run that moves a number fails here first.
2. **Computed, never typed.** Which intervals clear zero, the verb agreement
   and the negative-control count all come from the constant; the h126
   date-clustered interval CLEARS zero, so "every interval spans zero" is
   banned for this cell.
3. **Where it is served.** The push (`board_arrival.SCREEN_MEASURED_CLAUSE`,
   recommendation sentence BEFORE it), the board disclaimer + the
   `screen_measured` fold, the S&D rules panel — and the old wording is gone.
4. **Loop hygiene [C9].** `/growth/board` and `/growth/tags` run their sync
   bodies under `asyncio.to_thread`.

Rule #10: nothing here sorts, filters, gates or pushes.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from growth import screen_measured as SM

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ARTIFACT = BACKEND / "scripts" / "board_growth_measured.json"
HORIZONS = ("h21", "h63", "h126")


# ─────────────────────────────────────────────────────────── fixtures
@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text())


@pytest.fixture(scope="module")
def cell(art) -> dict:
    return art["cells"]["G100"]


@pytest.fixture(scope="module")
def clause() -> str:
    return SM.screen_clause()


@pytest.fixture(scope="module")
def line() -> str:
    return SM.screen_line()


def r2(pair) -> tuple:
    return tuple(round(float(x), 2) for x in pair)


def _days(h: str) -> int:
    return int(h[1:])


# ─────────────────────────────────────── 1. field-for-field pins (lift)
@pytest.mark.parametrize("h", HORIZONS)
def test_the_lift_constants_equal_the_artifact_at_every_horizon(h, cell):
    got = SM.SCREEN_MEASURED["lift"][h]
    c = cell[h]
    assert got["n"] == c["n"]
    assert got["n_symbols"] == c["n_symbols"]
    assert got["n_dates"] == c["n_dates"]
    assert got["median_lift_pp"] == c["median_lift_vs_all_scored_pp"]
    assert tuple(got["ci_symbol"]) == r2(c["lift_ci_symbol"])
    assert tuple(got["ci_date"]) == r2(c["lift_ci_date"])


@pytest.mark.parametrize("h", HORIZONS)
def test_the_momentum_control_constants_equal_the_artifact(h, cell):
    got = SM.SCREEN_MEASURED["momentum_control"][h]
    c = cell[h]["momentum_control"]
    assert got["n"] == c["n"]
    assert got["mean_excess_pp"] == round(c["mean_excess_pp"], 2)
    assert got["median_excess_pp"] == round(c["median_excess_pp"], 2)
    assert tuple(got["ci_symbol"]) == r2(c["ci_symbol"])
    assert "ci_date" not in c, "an unread date CI would silence the caveat"
    assert "ci_date" not in got


def test_the_provenance_points_at_real_files_and_the_right_cell(art):
    m = SM.SCREEN_MEASURED
    assert m["panel_dates"] == art["repro"]["n_dates_panel"]
    assert m["cell"] == "G100"
    assert m["run_date"] == "2026-09-21"
    assert (ROOT / m["doc"]).is_file()
    assert (ROOT / m["script"]).is_file()


def test_the_horizons_and_clusterings_are_the_artifacts():
    assert SM.HORIZONS == HORIZONS
    assert [k for k, _ in SM.CLUSTERINGS] == ["ci_symbol", "ci_date"]


# ─────────────────────────────────────── 2. computed truth from the artifact
@pytest.mark.parametrize("h", HORIZONS)
@pytest.mark.parametrize("key, art_key", [("ci_symbol", "lift_ci_symbol"),
                                          ("ci_date", "lift_ci_date")])
def test_clears_zero_agrees_with_the_artifact_interval(h, key, art_key, cell):
    """Asserted FROM THE ARTIFACT: a re-run that flips any interval fails here."""
    lo, hi = cell[h][art_key]
    assert hi > 0, "an interval wholly below zero needs new wording"
    assert SM.clears_zero(SM.SCREEN_MEASURED["lift"][h][key]) is (lo > 0)


def test_today_only_the_126_day_date_clustered_interval_clears(cell):
    want = [(_days(h), lab) for h in HORIZONS
            for k, lab in (("lift_ci_symbol", "symbol-clustered"),
                           ("lift_ci_date", "date-clustered"))
            if cell[h][k][0] > 0]
    assert SM.clearing_intervals() == want == [(126, "date-clustered")]


@pytest.mark.parametrize("pair, want", [((1.41, 15.37), True), ((-0.81, 2.89), False),
                                        ((0.0, 3.0), False), ((-2.0, -0.5), False)])
def test_clears_zero_truth_table(pair, want):
    assert SM.clears_zero(pair) is want


def test_the_negative_control_count_is_computed_from_the_artifact(cell):
    want = sum(1 for h in HORIZONS if cell[h]["momentum_control"]["median_excess_pp"] < 0)
    assert SM.negative_control_count() == want == 3


def test_NEGATIVE_the_control_count_is_computed_not_typed(monkeypatch):
    m = json.loads(json.dumps(SM.SCREEN_MEASURED))
    m["momentum_control"]["h63"]["median_excess_pp"] = 0.5
    monkeypatch.setattr(SM, "SCREEN_MEASURED", m)
    assert SM.negative_control_count() == 2
    assert "negative 2 of 3" in SM.screen_clause()
    assert "negative at 2 of 3 horizons" in SM.screen_line()


# ─────────────────────────────────────────────────────── 3. the clause
@pytest.mark.parametrize("needle", [
    "MEASURED 2026-09-21", "+1.11pp/21d", "+3.44pp/63d", "+6.96pp/126d",
    "1 of 6 CIs clears zero", "negative 3 of 3", "a lean, not a finding",
    "momentum-matched",
])
def test_the_clause_carries_each_number_and_caveat(needle, clause):
    assert needle in clause


def test_verb_agreement_is_computed_zero_clear(monkeypatch):
    monkeypatch.setattr(SM, "clearing_intervals", lambda: [])
    assert "0 of 6 CIs clear zero" in SM.screen_clause()
    assert "0 of 6 lift intervals clear zero." in SM.screen_line()


def test_verb_agreement_is_computed_two_clear(monkeypatch):
    monkeypatch.setattr(SM, "clearing_intervals",
                        lambda: [(63, "date-clustered"), (126, "date-clustered")])
    assert "2 of 6 CIs clear zero" in SM.screen_clause()
    assert "2 of 6 lift intervals clear zero: the 63-day date-clustered one, " \
           "the 126-day date-clustered one" in SM.screen_line()


def test_the_clause_is_shorter_than_the_line_and_one_line_each(clause, line):
    """Relational only — NO typed character budget [C4]."""
    assert len(clause) < len(line)
    assert "\n" not in clause and "\n" not in line


# ─────────────────────────────────────────────────────── 4. the line
@pytest.mark.parametrize("needle", [
    "MEASURED 2026-09-21", "EVERY MEMBER, NOT ONLY ARRIVALS",
    "24 monthly cross-sections", "+1.11pp", "+3.44pp at 63 days", "+6.96pp at 126 days",
    "265 symbol-bars, 72 symbols, 20 dates",
    "−0.81 to +2.89", "−1.23 to +3.10", "−3.68 to +8.30", "−2.64 to +8.36",
    "−1.08 to +14.35", "+1.41 to +15.37",
    "+1.41 to +15.37 date-clustered, CLEARS zero",
    "1 of 6 lift intervals clears zero: the 126-day date-clustered one",
    "−0.42pp at 21 days", "−1.55pp at 63", "−2.06pp at 126",
    "negative at 3 of 3 horizons",
    "−0.42 to +4.20", "+0.31 to +13.85", "−2.77 to +20.38",
    "interval is on the MEAN and symbol-clustered only", "A lean, not a finding.",
])
def test_the_line_carries_each_number_and_caveat(needle, line):
    assert needle in line


def test_the_line_says_CLEARS_once_and_spans_five_times(line):
    assert line.count("CLEARS zero") == 1
    assert line.count("spans zero") == 5


def test_the_headline_names_the_date_and_no_measured_number():
    h = SM.screen_headline()
    assert h.startswith("MEASURED 2026-09-21")
    assert "A LEAN, NOT A FINDING" in h
    rest = h.replace(SM.SCREEN_MEASURED["run_date"], "").replace("100/100", "")
    assert re.search(r"\d", rest) is None


# ─────────────────────────────────────────────────────── 5. negatives
BANNED = ["never been measured", "nothing here is backtested",
          "no lift interval clears zero", "every interval", "both span zero",
          "significant", "edge", "bounce"]


@pytest.mark.parametrize("banned", BANNED)
@pytest.mark.parametrize("fn", ["screen_clause", "screen_line", "screen_headline"])
def test_NEGATIVE_no_string_claims_more_or_less_than_the_replay(fn, banned):
    assert banned not in getattr(SM, fn)().lower()


@pytest.mark.parametrize("fn", ["screen_clause", "screen_line", "screen_headline"])
def test_NEGATIVE_no_string_says_buy_except_in_its_negation(fn):
    """'buy' only ever appears inside "not a buy signal" (the line's own
    disclaimer); never as an instruction or a claim."""
    s = getattr(SM, fn)().lower().replace("not a buy signal", "")
    assert "buy" not in s


@pytest.mark.parametrize("fn", ["screen_clause", "screen_line"])
def test_NEGATIVE_no_ascii_minus_in_front_of_a_number(fn):
    """Real minus per number; the only ASCII hyphen beside a digit is inside
    the date (a digit precedes it there)."""
    assert re.search(r"(?<![0-9A-Za-z])-[0-9]", getattr(SM, fn)()) is None


@pytest.mark.parametrize("fn", ["screen_clause", "screen_line"])
def test_NEGATIVE_no_real_minus_ever_touches_a_letter(fn):
    assert re.search(r"[A-Za-z]−|−[A-Za-z]", getattr(SM, fn)()) is None


@pytest.mark.parametrize("lit", ["2026-09-21", "point-in-time", "symbol-clustered",
                                 "date-clustered", "momentum-matched", "symbol-bars"])
def test_ascii_hyphens_in_words_survive(lit, line):
    assert lit in line


def test_NEGATIVE_the_source_never_replaces_hyphens_sentence_wide():
    src = (BACKEND / "growth" / "screen_measured.py").read_text()
    assert '.replace("-"' not in src and ".replace('-'" not in src


def test_NEGATIVE_the_module_is_a_leaf():
    src = (BACKEND / "growth" / "screen_measured.py").read_text()
    for form in ("from growth", "import growth", "from sepa", "import sepa",
                 "from supply_demand", "import supply_demand", "from .", "from chart_maps",
                 "from push", "from portfolio", "from trading"):
        assert form not in src, form


def test_NEGATIVE_the_module_never_names_the_research_artifact():
    assert "board_growth_measured" not in (BACKEND / "growth" / "screen_measured.py").read_text()


def test_NEGATIVE_the_module_sorts_filters_gates_and_sends_nothing():
    src = (BACKEND / "growth" / "screen_measured.py").read_text()
    for banned in ("sort(", "sorted(", "send_push", "alert_gates", "room_gate", "push."):
        assert banned not in src, banned


def test_sgn_is_the_one_helper_arrivals_uses():
    from growth import arrivals as AR
    assert AR._sgn is SM.sgn
    assert SM.sgn(-0.42) == "−0.42" and SM.sgn(0) == "+0.00"


def test_NEGATIVE_the_two_cells_are_never_concatenated():
    from growth import arrivals as AR
    assert SM.screen_clause() not in AR.honesty_line()
    assert SM.screen_line() not in AR.honesty_line()
    assert AR.honesty_line() not in SM.screen_line()


# ─────────────────────────────────────── 6. served: push, board, rules panel
def test_the_push_clause_is_the_served_clause():
    from sepa import board_arrival as BA
    assert BA.SCREEN_MEASURED_CLAUSE == SM.screen_clause()
    assert not hasattr(BA, "NOT_BACKTESTED")


def test_the_board_disclaimer_carries_the_clause_and_the_fold_the_line():
    from growth import api as GA
    out = GA._payload({"rows": [{"symbol": "AAA"}], "built_at": None})
    assert SM.screen_clause() in out["disclaimer"]
    assert out["disclaimer"].startswith("Discovery list, NOT a signal. ")
    assert "No market-cap floor here" in out["disclaimer"]
    sm = out["screen_measured"]
    assert sm["body"] == SM.screen_line()
    assert sm["headline"] == SM.screen_headline()
    assert (sm["run_date"], sm["cell"], sm["doc"]) == ("2026-09-21", "G100",
                                                       SM.SCREEN_MEASURED["doc"])


def test_NEGATIVE_the_board_payload_never_says_the_screen_is_unmeasured():
    from growth import api as GA
    s = json.dumps(GA._payload({"rows": [], "built_at": None}), ensure_ascii=False).lower()
    assert "never been measured" not in s
    assert "nothing here is backtested" not in s


def test_the_rules_panel_growth_stops_line_carries_the_clause():
    from supply_demand import rules_info as RI
    stops = RI.sections()["growth"]["stops"]
    assert any(SM.screen_clause() in s for s in stops)
    assert not any("never been measured" in s.lower() for s in stops)


def test_the_rules_panel_growth_note_says_measured_from_the_constants():
    from supply_demand import rules_info as RI
    note = RI.sections()["growth"]["note"]
    assert note.startswith("Owner screen, no book. ")
    assert ("Measured %s" % SM.SCREEN_MEASURED["run_date"]) in note
    assert SM.SCREEN_MEASURED["doc"] in note
    assert "a lean, not a finding" in note
    assert "\n" not in note


def test_NEGATIVE_the_rules_panel_growth_note_never_says_unmeasured():
    from supply_demand import rules_info as RI
    note = RI.sections()["growth"]["note"].lower()
    for bad in ("not backtested", "never been measured", "nothing here is backtested",
                "significant", "edge", "bounce", "buy"):
        assert bad not in note, bad
    assert not re.search(r"\d", note.replace(SM.SCREEN_MEASURED["run_date"], "")
                                     .replace(SM.SCREEN_MEASURED["doc"].lower(), "")), \
        "no typed number in the note beyond the date and the doc path"
    src = (ROOT / "backend/supply_demand/rules_info.py").read_text()
    assert "Not backtested" not in src


@pytest.mark.parametrize("rel", [
    "backend/growth/alerts.py", "backend/growth/tracker.py", "backend/growth/api.py",
    "backend/growth/arrivals.py", "backend/growth/screen_measured.py",
    "backend/sepa/board_arrival.py", "backend/supply_demand/rules_info.py",
    "backend/push/subs.py",
])
def test_NEGATIVE_the_old_wording_is_gone_from_every_backend_site(rel):
    src = (ROOT / rel).read_text()
    assert "never been measured forward" not in src
    assert "NOTHING HERE IS BACKTESTED" not in src
    assert "NOT_BACKTESTED" not in src


def test_NEGATIVE_no_growth_module_says_never_measured_forward():
    for p in (BACKEND / "growth").glob("*.py"):
        assert "never been measured forward" not in p.read_text(), p


# ─────────────────────────────────────── 7. loop hygiene [C9]
def _top_level_block(head: str) -> str:
    """The source of one top-level def, up to the next top-level statement."""
    src = (BACKEND / "growth" / "api.py").read_text()
    start = src.index(head)
    m = re.compile(r"^\S", re.M).search(src, src.index("\n", start) + 1)
    return src[start:m.start() if m else len(src)]


def _handler_src(name: str) -> str:
    return _top_level_block("async def %s(" % name)


@pytest.mark.parametrize("name, body", [("growth_board", "_board_payload"),
                                        ("growth_tags", "_tags_payload")])
def test_the_growth_handlers_run_their_sync_body_off_the_loop(name, body):
    h = _handler_src(name)
    assert "await asyncio.to_thread(%s)" % body in h
    assert "T.board()" not in h
    assert "_arr.attach(" not in h


def test_NEGATIVE_refresh_and_at_demand_are_untouched_by_the_move():
    assert "to_thread" not in _handler_src("growth_refresh")
    assert "to_thread" not in _handler_src("growth_at_demand")


def test_both_sync_bodies_attach_membership_under_a_guard():
    for fn in ("def _payload(", "def _tags_payload("):
        body = _top_level_block(fn)
        assert "from chart_maps import membership as _mem" in body
        assert "_mem.attach_also_on(arr)" in body
        i_att, i_mem = body.index("_arr.attach(rows)"), body.index("_mem.attach_also_on(arr)")
        assert i_att < i_mem < body.index("_arr.summary(arr)")


def test_NEGATIVE_a_raising_membership_attach_never_takes_either_body_down(monkeypatch):
    import types
    from growth import api as GA
    from growth import arrivals as AR
    from growth import tracker as T
    boom = types.ModuleType("chart_maps.membership")

    def _raise(arr):
        raise RuntimeError("membership down")

    boom.attach_also_on = _raise
    import chart_maps
    monkeypatch.setitem(sys.modules, "chart_maps.membership", boom)
    monkeypatch.setattr(chart_maps, "membership", boom, raising=False)
    monkeypatch.setattr(AR, "attach", lambda rows: [{"symbol": "AAA", "first_seen": "x",
                                                     "liquid": True, "refused": False,
                                                     "warnings": []}])
    monkeypatch.setattr(T, "board", lambda: {"rows": [{"symbol": "AAA"}]})
    out = GA._board_payload()
    assert out["arrivals_n"] == 1 and out["n"] == 1
    tags = GA._tags_payload()
    assert tags["arrivals_n"] == 1 and set(tags["tags"]) == {"AAA"}


def test_a_working_membership_attach_reaches_the_served_arrivals(monkeypatch):
    import types
    from growth import api as GA
    from growth import arrivals as AR
    from growth import tracker as T
    fake = types.ModuleType("chart_maps.membership")

    def _attach(arr):
        for a in arr:
            a["also_on"] = [{"tab": "zones", "built_at": "t", "limit": 80}]

    fake.attach_also_on = _attach
    import chart_maps
    monkeypatch.setitem(sys.modules, "chart_maps.membership", fake)
    monkeypatch.setattr(chart_maps, "membership", fake, raising=False)
    monkeypatch.setattr(AR, "attach", lambda rows: [{"symbol": "AAA", "first_seen": "x",
                                                     "liquid": True, "refused": False,
                                                     "warnings": []}])
    monkeypatch.setattr(T, "board", lambda: {"rows": [{"symbol": "AAA"}]})
    assert GA._board_payload()["arrivals"][0]["also_on"][0]["tab"] == "zones"
    assert GA._tags_payload()["arrivals"][0]["also_on"][0]["limit"] == 80


# ─────────────────────────────────────── 8. import graph
@pytest.mark.parametrize("first", ["import growth.screen_measured; ",
                                   "import sepa.board_arrival; import growth.screen_measured; ",
                                   "import supply_demand.rules_info; "])
def test_every_import_order_is_a_DAG_in_a_fresh_interpreter(first):
    code = ("import sys; sys.path.insert(0, '.'); " + first
            + "import growth.api; import growth.arrivals; import sepa.board_arrival")
    res = subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=BACKEND,
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr[-2000:]


def test_NEGATIVE_importing_the_leaf_loads_no_repo_module():
    code = ("import sys; sys.path.insert(0, '.'); before = set(sys.modules); "
            "import growth.screen_measured; "
            "new = sorted(m for m in set(sys.modules) - before "
            "if m.split('.')[0] in ('growth', 'sepa', 'supply_demand', 'chart_maps', "
            "'push', 'portfolio', 'trading')); "
            "assert new == ['growth', 'growth.screen_measured'], new; print('ok')")
    res = subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=BACKEND,
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0 and "ok" in res.stdout, res.stderr[-2000:]
