"""🧪 Gajjala · Audited — the registry, the pure gate rules, the store's overlay + borrowed names, the constants
(BUILD SPEC 2026-11-01 §3.1 / §3.3 / §3.4, WP-A).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited / So we can keep track of improvements on this tab"

Every rule number is READ off the frozen prereg (byte copy in tests/fixtures/gajjala/gates_prereg_2026_10_30.md,
sha256 pinned), the picks off the report copy, the gate math off the study script copy (sha256 pinned — critique C1).
Fail-closed: a rule reading None fails. UNMEASURED everywhere. NEGATIVE cases are marked NEGATIVE.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_store import FakeColl, fake_store

BACKEND = Path(__file__).resolve().parents[1]
FIX = BACKEND / "tests" / "fixtures" / "gajjala"
PREREG_FIX = FIX / "gates_prereg_2026_10_30.md"
REPORT_FIX = FIX / "gates_report_2026_10_30.md"
STUDY_FIX = FIX / "gates_study_2026_10_30.py.txt"
HOST_ROOT = Path("/Users/ajay/clinet-test")
FIXTURE_OF = {AUD.PREREG_PATH: PREREG_FIX, AUD.REPORT_PATH: REPORT_FIX, AUD.STUDY_PATH: STUDY_FIX}
SRC = Path(AUD.__file__).read_text(encoding="utf-8")
EDGE = re.compile(r"\bedge\b", re.I)
B_WORD = re.compile("b" + "ounc", re.I)
NUM = re.compile(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?")
STEP = 0.0625                                         # binary-exact (1/16): no decimal literal on a compare edge
TRIG, STOP = 10.0, 9.5


# ── synthetic frames ──────────────────────────────────────────────────────────────────────────────────────────────
def _bars(pattern: str, p: float = 9.75, v: float = 100_000) -> list:
    """G = a green bar (close above its open AND the prior close), R = a red one (below both) — red under either
    RED_CLOSE_DEF."""
    out = []
    for ch in pattern:
        c = p + STEP if ch == "G" else p - STEP
        out.append((p, max(p, c) + STEP, min(p, c) - STEP, c, v))
        p = c
    return out


def world(pattern="GGG", *, close=10.125, brk_vol=200_000, tf="5m", setup="bull_flag", trigger=TRIG, stop=STOP,
          state="aplus", base_vol=100_000):
    base = _bars(pattern, v=base_vol)
    last_c = base[-1][3]
    brk = (last_c, max(close, last_c) + STEP, min(close, last_c) - STEP, close, brk_vol)
    F = FX.frame(base + [brk], prior=FX.warm(9.75), tf=tf)
    s = F.today.start
    read = {"setup": setup, "state": state, "trigger": trigger, "stop": stop, "frame": tf,
            "entry_bar_t": F.t[s + len(base)], "as_of_bar_t": F.t[s + len(base)],
            "base": {"from_t": F.t[s], "to_t": F.t[s + len(base) - 1], "bars": len(base)},
            "red_closes": D.red_closes(F, range(s, s + len(base)))}
    return F, read


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _walk(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _walk(v)
    else:
        yield o


def _served_strings(block) -> list:
    return [block["text"]] + [f["why"] for f in block["failed"]]


def _failed(block) -> dict:
    return {f["id"]: f["why"] for f in block["failed"]}


# ── G1 break-bar proof ────────────────────────────────────────────────────────────────────────────────────────────
def test_all_pass_reads_audited_aplus():
    F, r = world()
    b = AUD.judge(r, F, [])
    assert b["aplus"] is True and b["original_aplus"] is True and b["failed"] == []
    assert b["rules"] == ["G1", "G2", "G4"] == b["passed"]
    assert b["text"] == "audited A+ — G1 · G2 · G4 pass · UNMEASURED"
    assert b["version"] == AUD.AUDIT_VERSION
    assert set(b) == set(AUD.AUDIT_SERVED_KEYS)


def test_g1_volume_exactly_k_times_the_base_mean_passes_one_share_under_fails():
    F, r = world(brk_vol=2.0 * 100_000)
    assert AUD.judge(r, F, [])["aplus"] is True
    F, r = world(brk_vol=2.0 * 100_000 - 1)
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and list(_failed(b)) == ["G1"]                           # NEGATIVE
    assert "break-bar volume" in _failed(b)["G1"] and "2× the base mean 100.0K" in _failed(b)["G1"]
    assert b["values"]["G1"]["base_mean_vol"] == 100_000.0 and b["values"]["G1"]["k"] == AUD.G1_K == 2.0


def test_NEGATIVE_g1_a_close_equal_to_the_trigger_fails_strict():
    F, r = world(close=TRIG)
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and "G1" in _failed(b)
    assert _failed(b)["G1"] == "the break bar closed 10.00 vs trigger 10.00"


def test_NEGATIVE_g1_no_base_bars_fails_with_no_proof():
    F, r = world()
    r["base"] = {"from_t": "1999-01-01 09:30", "to_t": F.t[-2], "bars": 3}            # not on the frame → no base
    b = AUD.judge(r, F, [])
    assert _failed(b)["G1"] == "no base bars to prove against" and b["values"]["G1"]["base_n"] == 0
    assert AUD.g1_pass(F, len(F.c) - 1, TRIG, []) is None


def test_g1_k_is_read_at_call_time(monkeypatch):
    F, r = world(brk_vol=150_000)
    assert AUD.judge(r, F, [])["aplus"] is False
    monkeypatch.setattr(AUD, "G1_K", 1.5)
    assert AUD.judge(r, F, [])["aplus"] is True


# ── G2 red closes ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_g2_a_last_run_of_exactly_three_passes_four_fails():
    F, r = world("GRRR")
    assert AUD.judge(r, F, [])["aplus"] is True and AUD.judge(r, F, [])["values"]["G2"]["run"] == 3
    F, r = world("GRRRR")
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and list(_failed(b)) == ["G2"]                           # NEGATIVE
    assert _failed(b)["G2"] == "4 red closes in a row at the end of the base (> 3)"


def test_g2_last_vs_longest_run(monkeypatch):
    """An EARLIER run of 4 and a LAST run of 2: the prereg's "last" passes, the replay's "longest" fails."""
    F, r = world("RRRRGRR")
    assert r["red_closes"] == 4
    b = AUD.judge(r, F, [])
    assert b["aplus"] is True and b["values"]["G2"] == {"run": 2, "longest": 4, "max": 3, "mode": "last",
                                                        "frame": "5m"}
    monkeypatch.setattr(AUD, "G2_RUN", "longest")
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and "G2" in _failed(b) and b["values"]["G2"]["mode"] == "longest"   # NEGATIVE


def test_NEGATIVE_a_junk_g2_run_raises(monkeypatch):
    monkeypatch.setattr(AUD, "G2_RUN", "first")
    with pytest.raises(ValueError):
        AUD.validate()
    F, r = world()
    with pytest.raises(ValueError):
        AUD.g2_run(F, [0], r)


def test_g2_pass_tri_state():
    assert AUD.g2_pass(3) is True and AUD.g2_pass(4) is False and AUD.g2_pass(0) is True
    assert AUD.g2_pass(None) is None and AUD.g2_pass(True) is None and AUD.g2_pass("3") is None   # NEGATIVE


def test_g2_max_red_is_ggs_constant_by_name():
    assert AUD.G2_MAX_RED == GC.RED_CLOSES_WAIT
    line = next(ln for ln in SRC.splitlines() if ln.startswith("G2_MAX_RED ="))
    assert "GC.RED_CLOSES_WAIT" in line
    assert not re.search(r"(?<![\d.])3(?![\d.])", line), line                           # NEGATIVE: no second 3


# ── G4 stop-distance cap + the 🎾 frozen stop ────────────────────────────────────────────────────────────────────
def test_g4_exactly_ten_percent_passes_ten_point_oh_one_fails():
    F, r = world(stop=9.0)
    b = AUD.judge(r, F, [])
    assert b["aplus"] is True and b["values"]["G4"]["risk_pct"] == 10.0
    F, r = world(stop=8.999)
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and list(_failed(b)) == ["G4"]                           # NEGATIVE
    assert _failed(b)["G4"] == "stop 9.00 is 10.0% under the trigger (> 10%)"
    assert AUD.g4_pass(10.0, 9.0) is True and AUD.g4_pass(10.0, 8.999) is False
    assert AUD.g4_pass(10.0, 10.0) is None and AUD.g4_pass(None, 9.0) is None           # no plan → None


def test_g4_a_squeeze_reads_the_frozen_stop_with_its_trigger():
    F, r = world(setup="reversal_squeeze", stop=9.5)
    assert AUD.judge(r, F, [])["values"]["G4"]["frozen_reason"] == AUD.FROZEN_REASONS["no_match"]
    frozen = [{"trigger": "10.0", "stop": 8.5, "bar_t": F.t[-3], "at_et": "10:31"}]
    b = AUD.judge(r, F, frozen)
    g4 = b["values"]["G4"]
    assert b["aplus"] is False and "G4" in _failed(b)                                   # the wider frozen stop flips it
    assert g4["frozen"] is True and g4["stop_used"] == "8.5" and g4["frozen_reason"] == AUD.FROZEN_REASONS["frozen"]
    assert _failed(b)["G4"].endswith(" · " + AUD.FROZEN_REASONS["frozen"])
    assert AUD.cap_stop_for(r, frozen) == (8.5, True, "frozen")


def test_NEGATIVE_a_frozen_entry_with_another_trigger_is_ignored():
    F, r = world(setup="reversal_squeeze", stop=9.5)
    frozen = [{"trigger": "10.5", "stop": 8.5}, {"trigger": None, "stop": 1.0}, "junk"]
    b = AUD.judge(r, F, frozen)
    assert b["aplus"] is True and b["values"]["G4"]["frozen"] is False
    assert b["values"]["G4"]["frozen_reason"] == AUD.FROZEN_REASONS["no_match"]
    assert b["values"]["G4"]["stop_used"] == "9.5"


def test_NEGATIVE_a_bull_flag_never_reads_the_frozen_list():
    F, r = world(setup="bull_flag", stop=9.5)
    b = AUD.judge(r, F, [{"trigger": "10.0", "stop": 8.5}])
    assert b["aplus"] is True and b["values"]["G4"]["frozen_reason"] == AUD.FROZEN_REASONS["not_squeeze"]
    assert AUD.cap_stop_for(r, [{"trigger": "10.0", "stop": 8.5}]) == (9.5, False, "not_squeeze")


# ── the contract: A+ only, fail-closed, frame, JSON-native ──────────────────────────────────────────────────────
@pytest.mark.parametrize("state", ["triggered", "forming", "none", "aplus_held", None])
def test_NEGATIVE_judge_on_a_non_aplus_read_is_none(state):
    F, r = world(state=state)
    assert AUD.judge(r, F, []) is None
    assert AUD.judge(None, F, []) is None and AUD.judge("aplus", F, []) is None


def test_NEGATIVE_an_entry_bar_off_the_frame_fails_every_rule_with_its_none_why():
    F, r = world()
    r["entry_bar_t"] = "2026-10-13 23:55"
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and b["passed"] == []
    assert _failed(b) == {"G1": AUD.NONE_WHY["G1"], "G2": AUD.NONE_WHY["G2"], "G4": AUD.NONE_WHY["G4"]}
    for s in _served_strings(b):
        assert "None" not in s, s                                                       # NEGATIVE: never prints None
    assert b["text"].startswith("🚩 A+ on the original, held here by: G1 — not judgeable")
    assert b["text"].endswith(" · UNMEASURED")


def test_NEGATIVE_a_rule_reading_none_fails_closed():
    F, r = world()
    r["stop"] = None
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and _failed(b) == {"G4": AUD.NONE_WHY["G4"]}
    assert all("None" not in s for s in _served_strings(b))
    F, r = world()
    r["trigger"] = None
    b = AUD.judge(r, F, [])
    assert set(_failed(b)) == {"G1", "G4"} and all("None" not in s for s in _served_strings(b))


def test_the_frame_is_served_and_a_15m_read_says_15m():
    F, r = world()
    b = AUD.judge(r, F, [])
    assert b["frame"] == F.frame == "5m" == b["values"]["G1"]["frame"] == b["values"]["G2"]["frame"]
    F, r = world(tf="15m", setup="horizontal_fade")
    b = AUD.judge(r, F, [])
    assert b["frame"] == "15m" == b["values"]["G1"]["frame"] == b["values"]["G2"]["frame"]
    for rid in ("G1", "G2"):
        note = AUD.by_id(rid).note
        assert "Horizontal Fade" in note and "15-minute" in note and "HIS CALL #14" in note


def test_judge_is_json_native_no_decimal_anywhere():
    F, r = world()
    held_F, held_r = world("GRRRR", stop=8.0, brk_vol=1)
    none_F, none_r = world()
    none_r["entry_bar_t"] = "nope"
    for F_, r_ in ((F, r), (held_F, held_r), (none_F, none_r)):
        b = AUD.judge(r_, F_, [{"trigger": "10.0", "stop": 8.5}])
        json.dumps(b)
        assert not any(isinstance(x, Decimal) for x in _walk(b))
    assert isinstance(AUD.risk_pct(10.0, 9.0), Decimal)                                 # internal only


def test_held_text_lists_every_failed_rule():
    F, r = world("GRRRR", stop=8.0, brk_vol=1)
    b = AUD.judge(r, F, [])
    assert [f["id"] for f in b["failed"]] == ["G1", "G2", "G4"]
    assert b["text"].startswith("🚩 A+ on the original, held here by: G1 — break-bar volume")
    assert "; G2 — 4 red closes" in b["text"] and "; G4 — stop 8.00 is 20.0% under" in b["text"]


# ── the ported math is the study's ───────────────────────────────────────────────────────────────────────────────
def test_the_study_fixture_is_the_bytes_ported():
    assert hashlib.sha256(STUDY_FIX.read_bytes()).hexdigest() == AUD.STUDY_SHA256
    host = HOST_ROOT / AUD.STUDY_PATH
    if host.exists():
        assert host.read_bytes() == STUDY_FIX.read_bytes()
    assert AUD.STUDY_SHA256 in SRC and "render-only" in SRC


def _study_func(name: str) -> str:
    tree = ast.parse(STUDY_FIX.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.unparse(ast.Module(body=fn.body[1:] if isinstance(fn.body[0], ast.Expr) else fn.body,
                                  type_ignores=[]))


def _ours(name: str) -> str:
    fn = next(n for n in ast.parse(SRC).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.unparse(ast.Module(body=fn.body[1:] if isinstance(fn.body[0], ast.Expr) else fn.body,
                                  type_ignores=[]))


@pytest.mark.parametrize("name", ["last_red_run", "risk_pct"])
def test_verbatim_bodies(name):
    assert _ours(name) == _study_func(name)


def test_base_idx_is_the_studys_base_idx():
    assert _ours("base_idx") == _study_func("_base_idx")


def test_g1_g4_bodies_are_the_studys_after_the_default_line():
    """g1_pass / g4_pass gained ONE line each (`k`/`c` default to the constant at call time); the rest is verbatim."""
    assert _ours("g1_pass").split("\n", 1)[1] == _study_func("g1_pass").replace("base_idx", "idx")
    assert _ours("g4_pass").split("\n", 1)[1] == _study_func("g4_pass").replace("c_pct", "c")


def _docstrings(tree) -> list:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
            out.append(n.body[0].value.value)
    return out


def _run2_cited_alone(src: str) -> list:
    """Every docstring / source line that cites the run-2 sha e308ab74 WITHOUT the ported 20bb1970 beside it."""
    bad = [d[:60] for d in _docstrings(ast.parse(src)) if "e308ab74" in d and "20bb1970" not in d]
    docs = "\n".join(_docstrings(ast.parse(src)))
    bad += [ln for ln in src.splitlines() if "e308ab74" in ln and "20bb1970" not in ln and ln.strip() not in docs]
    return bad


def test_NEGATIVE_the_run2_sha_is_never_cited_without_the_ported_sha():
    assert "e308ab74" in SRC                                                           # it IS cited (report.md:5)
    assert _run2_cited_alone(SRC) == []
    # the guard bites on a mutated copy: a docstring / comment with the run-2 sha alone
    assert _run2_cited_alone('"""ported from e308ab74…"""\nX = 1\n') != []
    assert _run2_cited_alone('X = 1   # sha e308ab74\n') != []


# ── the registry ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_registry_ids_status_and_fields():
    assert tuple(r.id for r in AUD.REGISTRY) == ("G1", "G2", "G3", "G4")
    for r in AUD.REGISTRY:
        assert r.date_added == "2026-11-01" and r.status in AUD.STATUSES
        assert r.name and r.rule and r.params and r.source and r.verdict_source and r.changes
        assert r.verdict == AUD.VERDICT_UNMEASURED
    assert [r.id for r in AUD.on_rules()] == ["G1", "G2", "G4"]
    for i in ("G1", "G2", "G4"):
        assert AUD.by_id(i).status == AUD.STATUS_ON and AUD.by_id(i).applies is True
    assert AUD.by_id("G3").status == AUD.STATUS_LANE_ONLY and AUD.by_id("G3").applies is False   # NEGATIVE
    assert AUD.by_id("G9") is None
    with pytest.raises(Exception):
        AUD.G1.status = "off"                                                          # NEGATIVE: frozen


def test_every_source_resolves_and_quotes_its_file():
    for r in AUD.REGISTRY:
        for path, quote in r.source:
            fx = FIXTURE_OF[path]
            assert fx.exists(), path
            assert quote in fx.read_text(encoding="utf-8"), (r.id, quote)
            host = HOST_ROOT / path
            if host.exists():
                assert host.read_bytes() == fx.read_bytes(), path
        assert r.source[0][0] == AUD.PREREG_PATH


def test_the_prereg_fixture_is_the_frozen_bytes():
    assert hashlib.sha256(PREREG_FIX.read_bytes()).hexdigest() == AUD.PREREG_SHA256
    assert AUD.PREREG_SHA256 in REPORT_FIX.read_text(encoding="utf-8")                  # report.md:5 cites it


def _set_of(text: str, pattern: str) -> set:
    m = re.search(pattern, text)
    assert m, pattern
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", m.group(1))}


def test_every_number_is_in_the_prereg_row():
    pre = PREREG_FIX.read_text(encoding="utf-8")
    assert AUD.G1_K in _set_of(pre, r"k ∈ \{([^}]*)\}")
    assert AUD.G4_MAX_RISK_PCT in _set_of(pre, r"c ∈ \{([^}]*)\}")
    assert AUD.G3_MAX_AGE_MIN in _set_of(pre, r"m ∈ \{([^}]*)\}")
    assert AUD.G3_MISSED_R in _set_of(pre, r"MISSED_R ∈ \{([^}]*)\}")
    assert int(re.search(r"has > (\d+) consecutive red", pre).group(1)) == AUD.G2_MAX_RED


def test_every_number_is_the_reports_pick():
    rep = REPORT_FIX.read_text(encoding="utf-8")
    combined = next(ln for ln in rep.splitlines() if ln.startswith("| Combined"))
    assert float(re.search(r"G1 k=([\d.]+)", combined).group(1)) == AUD.G1_K
    assert int(re.search(r"G2 max_red=(\d+)", combined).group(1)) == AUD.G2_MAX_RED
    assert int(re.search(r"G3 m=(\d+)", combined).group(1)) == AUD.G3_MAX_AGE_MIN
    assert float(re.search(r"missed_r=([\d.]+)", combined).group(1)) == AUD.G3_MISSED_R
    assert float(re.search(r"G4 c=([\d.]+)", combined).group(1)) == AUD.G4_MAX_RISK_PCT
    assert int(re.search(r"the lab's (\d+)-week floor", rep).group(1)) == AUD.MEASURE_FLOOR_WEEKS
    assert "--render-only" in rep.splitlines()[46]                                     # report.md:47 as quoted


def test_every_gg_cite_resolves():
    vr = json.loads((BACKEND / "chart_maps" / "gajjala" / "verified_rules.json").read_text(encoding="utf-8"))
    n = 0
    for r in AUD.REGISTRY:
        for f, where, quote in r.gg:
            p = BACKEND / f
            assert p.exists(), f
            if f.endswith(".md"):
                assert quote in p.read_text(encoding="utf-8").splitlines()[int(where) - 1], (r.id, where)
            else:
                ti, vi = (int(x) for x in re.fullmatch(r"topics\[(\d+)\]\.verified\[(\d+)\]", where).groups())
                assert quote in json.dumps(vr["topics"][ti]["verified"][vi], ensure_ascii=False), (r.id, where)
            n += 1
    assert n == 4 and AUD.G3.gg == ()


def test_registry_rows_are_words_only_and_say_unmeasured():
    rows = AUD.registry_rows()
    assert [r["id"] for r in rows] == ["G1", "G2", "G3", "G4"]
    keys = {"id", "name", "rule", "params_text", "source_text", "since", "status", "status_text", "verdict",
            "verdict_text", "changes_text", "applies", "note"}
    for row in rows:
        assert set(row) == keys
        assert "UNMEASURED" in row["verdict_text"] and "{" not in row["rule"]
        for k, v in row.items():
            if isinstance(v, str):
                assert not EDGE.search(v) and not B_WORD.search(v), (row["id"], k)       # NEGATIVE
    assert rows[0]["rule"].endswith("volume ≥ 2 × the mean volume of the base bars")
    assert rows[1]["rule"] == "not A+ when the base's last run has more than 3 consecutive red closes"
    assert rows[2]["status_text"] == AUD.STATUS_TEXT[AUD.STATUS_LANE_ONLY] and rows[2]["applies"] is False
    json.dumps(rows)


def test_rules_clause_formats_every_number_from_the_constants():
    txt = AUD.rules_clause()
    allowed = {"%g" % x for x in (AUD.G1_K, AUD.G2_MAX_RED, AUD.G3_MAX_AGE_MIN, AUD.G3_MISSED_R,
                                  AUD.G4_MAX_RISK_PCT, AUD.MEASURE_FLOOR_WEEKS)}
    assert set(NUM.findall(txt)) <= allowed, set(NUM.findall(txt)) - allowed
    assert "UNMEASURED" in txt and "G3" in txt and "held" in txt
    assert not EDGE.search(txt) and not B_WORD.search(txt)                                # NEGATIVE
    assert set(NUM.findall("a 7 bar · G1 · 0.25")) == {"7", "0.25"}                       # the guard bites


def test_NEGATIVE_no_gga_word_says_edge_or_the_b_word():
    for k in V.WORDS_GGA:
        assert not EDGE.search(V.WORDS_GGA[k]) and not B_WORD.search(V.WORDS_GGA[k]), k
    for s in list(AUD.NONE_WHY.values()) + list(AUD.FROZEN_REASONS.values()) + [AUD.NEVER_SENDS]:
        assert not EDGE.search(s) and not B_WORD.search(s) and "None" not in s


# ── the store: OVERLAY + borrowed names + held rows ─────────────────────────────────────────────────────────────
@pytest.fixture
def physical_db(monkeypatch):
    """Every un-injected handle resolves by its PHYSICAL name to one FakeColl (the routing under test)."""
    db: dict = {}
    monkeypatch.setattr(ST, "_coll", lambda name: db.setdefault(name, FakeColl()))
    return db


def test_gga_physical_names(physical_db):
    shared = ST.GajjalaStore()
    gga = ST.GajjalaStore(variant=V.GGA, shared=shared)
    for n in (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY):
        assert gga.physical(n) == "gajjala_audited" + n[len("gajjala"):]
    assert gga.physical(ST.OVERLAY) == "gajjala_audited_overlay"
    for n in (ST.READS, ST.POTENTIALS, ST.PASSES, ST.REPLAY):                            # borrowed → GG5's name
        assert gga.physical(n) == n
        assert gga.coll(n) is shared.coll(n)                                             # the SHARED object
    for n in ST.SHARED:
        assert gga.coll(n) is shared.coll(n)
    assert gga.coll(ST.ALERTS) is physical_db["gajjala_audited_alerts"]
    assert gga.coll(ST.ALERTS) is not shared.coll(ST.ALERTS)                             # NEGATIVE: owns its alerts


def test_NEGATIVE_gg5_and_gg1_overlay_names_and_borrows_untouched():
    assert ST.GajjalaStore().physical(ST.OVERLAY) == "gajjala_overlay"
    g1 = ST.GajjalaStore(variant=V.GG1, shared=fake_store())
    assert g1.physical(ST.OVERLAY) == "gajjala_1m_overlay"
    assert g1.physical(ST.READS) == "gajjala_1m_reads"                                  # GG1 borrows nothing
    assert ST.OVERLAY in ST.ALL and ST.OVERLAY in ST.OWN and ST.ALL[-1] == ST.REPLAY
    assert ST.TTL_DAYS[ST.OVERLAY] == GC.READS_TTL_DAYS


class NoIndex(FakeColl):
    def create_index(self, spec, **kw):
        raise AssertionError("an index on a BORROWED collection")


def test_NEGATIVE_ensure_indexes_never_touches_a_borrowed_name():
    shared = fake_store()
    own = {n: (NoIndex() if n in V.GGA.borrows else FakeColl()) for n in ST.OWN}
    gga = ST.GajjalaStore(colls=own, variant=V.GGA, shared=shared)
    gga.ensure_indexes()
    assert all(shared.coll(n).indexes == [] for n in ST.ALL)                             # GG5's untouched
    assert own[ST.OVERLAY].indexes and own[ST.ALERTS].indexes and own[ST.LEDGER].indexes
    ttl = [kw.get("expireAfterSeconds") for spec, kw in own[ST.OVERLAY].indexes if spec == (("at", 1),)]
    assert ttl == [GC.READS_TTL_DAYS * 86400]



def test_NEGATIVE_gg5_and_gg1_ensure_indexes_never_create_an_overlay():
    """🧪 2026-11-01 refix — `create_index` CREATES the collection on Mongo; only the GGA store ever writes an overlay,
    so the GG5 bare run (walks ALL) and the GG1 run (walks OWN) must never index — i.e. never create — theirs."""
    gg5 = fake_store()
    gg5.ensure_indexes()
    assert gg5.coll(ST.OVERLAY).indexes == []                                             # NEGATIVE: GG5 bare store
    assert gg5.coll(ST.READS).indexes and gg5.coll(ST.LEDGER).indexes                     # the rest still indexed
    shared = fake_store()
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GG1, shared=shared)
    g1.ensure_indexes()
    assert g1.coll(ST.OVERLAY).indexes == []                                              # NEGATIVE: GG1 store
    assert g1.coll(ST.READS).indexes and g1.coll(ST.ALERTS).indexes
    assert all(shared.coll(n).indexes == [] for n in ST.ALL)


def test_NEGATIVE_overlay_skip_counts_zero_calls_off_gga():
    """ensure_indexes swallows index errors, so count the calls instead: GG5 never reaches the overlay coll (0 calls,
    not even a TTL); the GGA store reaches its own overlay (TTL + both read-path keys)."""
    class Counting(FakeColl):
        calls = 0

        def create_index(self, spec, **kw):
            type(self).calls += 1
            super().create_index(spec, **kw)
    c5 = Counting()
    fake_store(**{ST.OVERLAY: c5}).ensure_indexes()
    assert Counting.calls == 0                                                            # NEGATIVE
    shared = fake_store()
    own = {n: FakeColl() for n in ST.OWN if n not in V.GGA.borrows}
    ST.GajjalaStore(colls=own, variant=V.GGA, shared=shared).ensure_indexes()
    assert [sp for sp, _ in own[ST.OVERLAY].indexes] == [(("at", 1),), (("date", 1), ("symbol", 1)),
                                                         (("symbol", 1), ("date", -1))]

def _gga_store():
    shared = fake_store()
    own = {n: FakeColl() for n in ST.OWN if n not in V.GGA.borrows}
    return ST.GajjalaStore(colls=own, variant=V.GGA, shared=shared), shared


def test_overlay_round_trip():
    from datetime import datetime, timezone
    gga, shared = _gga_store()
    now = datetime(2026, 11, 3, 15, 41, tzinfo=timezone.utc)
    gga.upsert_overlay("2026-11-03", "abc", {"setups": {"bull_flag": {"aplus": True}}, "pass_at": now}, now=now)
    gga.upsert_overlay("2026-11-03", "XYZ", {"setups": {}}, now=now)
    gga.upsert_overlay("2026-11-04", "ABC", {"setups": {}}, now=now)
    doc = gga.get_overlay("2026-11-03", "ABC")
    assert doc["_id"] == "2026-11-03|ABC" and doc["symbol"] == "ABC" and doc["date"] == "2026-11-03"
    assert doc["setups"] == {"bull_flag": {"aplus": True}} and doc["at"] == now
    assert sorted(d["_id"] for d in gga.overlays("2026-11-03")) == ["2026-11-03|ABC", "2026-11-03|XYZ"]
    gga.upsert_overlay("2026-11-03", "ABC", {"frozen": [{"trigger": "1.0", "stop": 0.9}]}, now=now)
    doc = gga.get_overlay("2026-11-03", "ABC")
    assert doc["frozen"] == [{"trigger": "1.0", "stop": 0.9}] and doc["setups"] == {"bull_flag": {"aplus": True}}
    assert all(shared.coll(n).writes == 0 for n in ST.ALL)                               # NEGATIVE: GG5 never written
    assert gga.get_overlay("2026-11-05", "ABC") is None


def test_held_rows_reads_held_markers_only():
    gga, _shared = _gga_store()
    c = gga.coll(ST.ALERTS)
    c.docs = {
        "GGA:2026-11-03|ABC|bull_flag#held": {"_id": "GGA:2026-11-03|ABC|bull_flag#held", "date": "2026-11-03",
                                              "state": AUD.HELD_ROW_STATE},
        "SHADOW:GGA:2026-11-03|XYZ|bull_flag": {"_id": "SHADOW:GGA:2026-11-03|XYZ|bull_flag", "date": "2026-11-03",
                                                "state": "shadow"},
        "GGA:2026-11-02|OLD|bull_flag#held": {"_id": "GGA:2026-11-02|OLD|bull_flag#held", "date": "2026-11-02",
                                              "state": AUD.HELD_ROW_STATE},
    }
    rows = gga.held_rows(["2026-11-03"])
    assert [r["_id"] for r in rows] == ["GGA:2026-11-03|ABC|bull_flag#held"]            # NEGATIVE: no shadow row
    assert gga.held_rows([]) == []
    dead = ST.GajjalaStore(colls={ST.ALERTS: FakeColl(fail=True)}, variant=V.GGA, shared=fake_store())
    assert dead.held_rows(["2026-11-03"]) is None                                        # a fault is not "none"


def test_NEGATIVE_ledger_keys_unchanged_and_a_top_level_copied_from_is_refused():
    assert ST.LEDGER_KEYS == frozenset({"date", "symbol", "setup", "kind", "line", "alert", "same", "next",
                                        "graded_at", "version"})
    gga, _shared = _gga_store()
    assert gga.upsert_ledger("2026-11-03|ABC|bull_flag|aplus", {"date": "2026-11-03",
                                                                "copied_from": "gajjala_ledger"}) is False
    assert gga.coll(ST.LEDGER).writes == 0
    assert gga.upsert_ledger("2026-11-03|ABC|bull_flag|aplus",
                             {"date": "2026-11-03", "same": {"copied_from": "gajjala_ledger", "version": 1}}) is True


def test_for_variant_gga_is_one_cached_store_over_the_default(monkeypatch):
    monkeypatch.setattr(ST, "_VARIANT_STORES", {})
    a, b = ST.for_variant(V.GGA), ST.for_variant(V.GGA)
    assert a is b and a.variant is V.GGA and a.shared is ST.default()
    assert ST.for_variant(V.GG1) is not a


# ── constants ────────────────────────────────────────────────────────────────────────────────────────────────────
def _const_line(name: str) -> str:
    src = Path(GC.__file__).read_text(encoding="utf-8").splitlines()
    return next(ln for ln in src if ln.startswith(name + " ="))


def _comment(line: str) -> str:
    return line.split("#", 1)[1].strip() if "#" in line else ""


def _audited_mode_tag_ok(line: str) -> bool:
    c = _comment(line)
    return c.startswith("Ajay 2026-11-01") and "SHADOW" in c and "HIS CALL" in c


def test_the_three_constants_and_their_tags():
    assert GC.GAJJALA_AUDITED_PUSH_MODE == "shadow" and GC.GAJJALA_AUDITED_PUSH_MODE in GC.PUSH_MODES
    assert GC.GGA_TAB_LABEL == "🧪 Gajjala · Audited" and GC.GGA_RECORD_FROM == "2026-11-01"
    real = _const_line("GAJJALA_AUDITED_PUSH_MODE")
    assert _audited_mode_tag_ok(real), real
    assert _comment(_const_line("GGA_TAB_LABEL")).startswith("MINE")
    assert _comment(_const_line("GGA_RECORD_FROM")).startswith("Ajay 2026-11-01")
    assert "So we can keep track of improvements on this tab" in _comment(_const_line("GGA_RECORD_FROM"))
    code = real.partition("#")[0].rstrip()
    for bad in (code, real.replace("# Ajay 2026-11-01", "# MINE"),
                real.replace("# Ajay 2026-11-01", "# Cheetah default")):                 # NEGATIVE mutations
        assert bad != real and not _audited_mode_tag_ok(bad), bad


def test_NEGATIVE_his_numbers_untouched():
    assert GC.RED_CLOSES_WAIT == 3 and GC.RED_CLOSE_DEF == "close_below_open"
    assert GC.GAJJALA_PUSH_MODE == "live" and GC.GAJJALA_1M_PUSH_MODE == "live"
    assert GC.GG1M_RECORD_FROM == "2026-10-27" and GC.PASS_CADENCE_SEC == 300
