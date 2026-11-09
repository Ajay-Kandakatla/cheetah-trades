"""🧪 Gajjala · Audited — the registry, the pure gate rules, the store's overlay + borrowed names, the constants
(BUILD SPEC 2026-11-01 §3.1 / §3.3 / §3.4, WP-A).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited / So we can keep track of improvements on this tab"

Every rule number is READ off the frozen prereg (byte copy in tests/fixtures/gajjala/gates_prereg_2026_10_30.md,
sha256 pinned), the picks off the report copy, the gate math off the study script copy (sha256 pinned — critique C1).
Fail-closed: a rule reading None fails. UNMEASURED everywhere. NEGATIVE cases are marked NEGATIVE.

2026-11-01 (SPEC gg-audited-mods §3.1 / WP-A — Ajay: "Yes make the changes in audited please" and "But keep a track
record too to see the winners and loster"): the registry holds TWELVE entries; the eight new ones are read off the
frozen prereg2 (byte copy tests/fixtures/gajjala/audited_modifications_prereg_2026_11_01.md, sha256 pinned). The
synthetic world's break bar now closes at 10:50 ET (start 10:45 — inside T2 / A1 / H1) and `_j` hands `judge` the pass
context (session + a +55% top runner) so the G-rule pins read exactly as before; the new rules' pins are at the end.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from chart_maps.gajjala import alerts as AL
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
PREREG2_FIX = FIX / "audited_modifications_prereg_2026_11_01.md"
PREREG3_FIX = FIX / "audited_k3s_prereg_2026_11_09.md"            # 2026-11-09 K3S (SPEC gg-k3s §3.2)
REPORT_FIX = FIX / "gates_report_2026_10_30.md"
STUDY_FIX = FIX / "gates_study_2026_10_30.py.txt"
HOST_ROOT = Path("/Users/ajay/clinet-test")
FIXTURE_OF = {AUD.PREREG_PATH: PREREG_FIX, AUD.REPORT_PATH: REPORT_FIX, AUD.STUDY_PATH: STUDY_FIX,
              AUD.PREREG2_PATH: PREREG2_FIX, AUD.PREREG3_PATH: PREREG3_FIX}
SRC = Path(AUD.__file__).read_text(encoding="utf-8")
EDGE = re.compile(r"\bedge\b", re.I)
B_WORD = re.compile("b" + "ounc", re.I)
NUM = re.compile(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?")
STEP = 0.0625                                         # binary-exact (1/16): no decimal literal on a compare edge
TRIG, STOP = 10.0, 9.5
CTX = {"session": FX.TODAY, "best_change_pct": 55.0, "best_symbol": "RUNR"}   # a pass with a +55% top runner
JUDGE_IDS = ["G1", "G2", "G4", "T2", "A1", "H1", "T4", "A2"]
NEW_IDS = ("T1", "T2", "A1", "H1", "T4", "A2", "T3", "T5")


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
          state="aplus", base_vol=100_000, start="10:35"):
    base = _bars(pattern, v=base_vol)
    last_c = base[-1][3]
    brk = (last_c, max(close, last_c) + STEP, min(close, last_c) - STEP, close, brk_vol)
    F = FX.frame(base + [brk], prior=FX.warm(9.75), tf=tf, start=start)
    s = F.today.start
    read = {"setup": setup, "state": state, "trigger": trigger, "stop": stop, "frame": tf,
            "entry_bar_t": F.t[s + len(base)], "as_of_bar_t": F.t[s + len(base)],
            "base": {"from_t": F.t[s], "to_t": F.t[s + len(base) - 1], "bars": len(base)},
            "red_closes": D.red_closes(F, range(s, s + len(base)))}
    return F, read


def _j(read, F, frozen=None, ctx=CTX):
    """judge with the pass context (session + top runner) — the G-rule pins read as before."""
    return AUD.judge(read, F, frozen, ctx=ctx)


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
    b = _j(r, F, [])
    assert b["aplus"] is True and b["original_aplus"] is True and b["failed"] == []
    assert b["rules"] == JUDGE_IDS == b["passed"]
    assert b["text"] == "audited A+ — G1 · G2 · G4 · T2 · A1 · H1 · T4 · A2 pass · UNMEASURED"
    assert b["version"] == AUD.AUDIT_VERSION
    assert set(b) == set(AUD.AUDIT_SERVED_KEYS)


def test_g1_volume_exactly_k_times_the_base_mean_passes_one_share_under_fails():
    F, r = world(brk_vol=2.0 * 100_000)
    assert _j(r, F, [])["aplus"] is True
    F, r = world(brk_vol=2.0 * 100_000 - 1)
    b = _j(r, F, [])
    assert b["aplus"] is False and list(_failed(b)) == ["G1"]                           # NEGATIVE
    assert "break-bar volume" in _failed(b)["G1"] and "2× the base mean 100.0K" in _failed(b)["G1"]
    assert b["values"]["G1"]["base_mean_vol"] == 100_000.0 and b["values"]["G1"]["k"] == AUD.G1_K == 2.0


def test_NEGATIVE_g1_a_close_equal_to_the_trigger_fails_strict():
    F, r = world(close=TRIG)
    b = _j(r, F, [])
    assert b["aplus"] is False and "G1" in _failed(b)
    assert _failed(b)["G1"] == "the break bar closed 10.00 vs trigger 10.00"


def test_NEGATIVE_g1_no_base_bars_fails_with_no_proof():
    F, r = world()
    r["base"] = {"from_t": "1999-01-01 09:30", "to_t": F.t[-2], "bars": 3}            # not on the frame → no base
    b = _j(r, F, [])
    assert _failed(b)["G1"] == "no base bars to prove against" and b["values"]["G1"]["base_n"] == 0
    assert AUD.g1_pass(F, len(F.c) - 1, TRIG, []) is None


def test_g1_k_is_read_at_call_time(monkeypatch):
    F, r = world(brk_vol=150_000)
    assert _j(r, F, [])["aplus"] is False
    monkeypatch.setattr(AUD, "G1_K", 1.5)
    assert _j(r, F, [])["aplus"] is True


# ── G2 red closes ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_g2_a_last_run_of_exactly_three_passes_four_fails():
    F, r = world("GRRR")
    assert _j(r, F, [])["aplus"] is True and _j(r, F, [])["values"]["G2"]["run"] == 3
    F, r = world("GRRRR")
    b = _j(r, F, [])
    assert b["aplus"] is False and list(_failed(b)) == ["G2"]                           # NEGATIVE
    assert _failed(b)["G2"] == "4 red closes in a row at the end of the base (> 3)"


def test_g2_last_vs_longest_run(monkeypatch):
    """An EARLIER run of 4 and a LAST run of 2: the prereg's "last" passes, the replay's "longest" fails."""
    F, r = world("RRRRGRR")
    assert r["red_closes"] == 4
    b = _j(r, F, [])
    assert b["aplus"] is True and b["values"]["G2"] == {"run": 2, "longest": 4, "max": 3, "mode": "last",
                                                        "frame": "5m"}
    monkeypatch.setattr(AUD, "G2_RUN", "longest")
    b = _j(r, F, [])
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
    b = _j(r, F, [])
    assert b["aplus"] is True and b["values"]["G4"]["risk_pct"] == 10.0
    F, r = world(stop=8.999)
    b = _j(r, F, [])
    assert b["aplus"] is False and list(_failed(b)) == ["G4"]                           # NEGATIVE
    assert _failed(b)["G4"] == "stop 9.00 is 10.0% under the trigger (> 10%)"
    assert AUD.g4_pass(10.0, 9.0) is True and AUD.g4_pass(10.0, 8.999) is False
    assert AUD.g4_pass(10.0, 10.0) is None and AUD.g4_pass(None, 9.0) is None           # no plan → None


def test_g4_a_squeeze_reads_the_frozen_stop_with_its_trigger():
    F, r = world(setup="reversal_squeeze", stop=9.5)
    assert _j(r, F, [])["values"]["G4"]["frozen_reason"] == AUD.FROZEN_REASONS["no_match"]
    frozen = [{"trigger": "10.0", "stop": 8.5, "bar_t": F.t[-3], "at_et": "10:31"}]
    b = _j(r, F, frozen)
    g4 = b["values"]["G4"]
    assert b["aplus"] is False and "G4" in _failed(b)                                   # the wider frozen stop flips it
    assert g4["frozen"] is True and g4["stop_used"] == "8.5" and g4["frozen_reason"] == AUD.FROZEN_REASONS["frozen"]
    assert _failed(b)["G4"].endswith(" · " + AUD.FROZEN_REASONS["frozen"])
    assert AUD.cap_stop_for(r, frozen) == (8.5, True, "frozen")


def test_NEGATIVE_a_frozen_entry_with_another_trigger_is_ignored():
    F, r = world(setup="reversal_squeeze", stop=9.5)
    frozen = [{"trigger": "10.5", "stop": 8.5}, {"trigger": None, "stop": 1.0}, "junk"]
    b = _j(r, F, frozen)
    assert b["aplus"] is True and b["values"]["G4"]["frozen"] is False
    assert b["values"]["G4"]["frozen_reason"] == AUD.FROZEN_REASONS["no_match"]
    assert b["values"]["G4"]["stop_used"] == "9.5"


def test_NEGATIVE_a_bull_flag_never_reads_the_frozen_list():
    F, r = world(setup="bull_flag", stop=9.5)
    b = _j(r, F, [{"trigger": "10.0", "stop": 8.5}])
    assert b["aplus"] is True and b["values"]["G4"]["frozen_reason"] == AUD.FROZEN_REASONS["not_squeeze"]
    assert AUD.cap_stop_for(r, [{"trigger": "10.0", "stop": 8.5}]) == (9.5, False, "not_squeeze")


# ── the contract: A+ only, fail-closed, frame, JSON-native ──────────────────────────────────────────────────────
@pytest.mark.parametrize("state", ["triggered", "forming", "none", "aplus_held", None])
def test_NEGATIVE_judge_on_a_non_aplus_read_is_none(state):
    F, r = world(state=state)
    assert _j(r, F, []) is None
    assert _j(None, F, []) is None and _j("aplus", F, []) is None


def test_NEGATIVE_an_entry_bar_off_the_frame_fails_every_rule_with_its_none_why():
    F, r = world()
    r["entry_bar_t"] = "2026-10-13 23:55"
    b = _j(r, F, [])
    assert b["aplus"] is False and b["passed"] == ["T2", "T4"]          # the clock rules read the stamp itself
    assert _failed(b) == {"G1": AUD.NONE_WHY["G1"], "G2": AUD.NONE_WHY["G2"], "G4": AUD.NONE_WHY["G4"],
                          "A1": "the break bar started 23:50 ET, after 11:59",
                          "H1": "the break bar started 23:50 ET, outside 09:30–16:00 ET",
                          "A2": AUD.NONE_WHY["A2"]}
    for s in _served_strings(b):
        assert "None" not in s, s                                                       # NEGATIVE: never prints None
    assert b["text"].startswith("🚩 A+ on the original, held here by: G1 — not judgeable")
    assert b["text"].endswith(" · UNMEASURED")


def test_NEGATIVE_a_rule_reading_none_fails_closed():
    F, r = world()
    r["stop"] = None
    b = _j(r, F, [])
    assert b["aplus"] is False and _failed(b) == {"G4": AUD.NONE_WHY["G4"]}
    assert all("None" not in s for s in _served_strings(b))
    F, r = world()
    r["trigger"] = None
    b = _j(r, F, [])
    assert set(_failed(b)) == {"G1", "G4"} and all("None" not in s for s in _served_strings(b))


def test_the_frame_is_served_and_a_15m_read_says_15m():
    F, r = world()
    b = _j(r, F, [])
    assert b["frame"] == F.frame == "5m" == b["values"]["G1"]["frame"] == b["values"]["G2"]["frame"]
    F, r = world(tf="15m", setup="horizontal_fade")
    b = _j(r, F, [])
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
        b = _j(r_, F_, [{"trigger": "10.0", "stop": 8.5}])
        json.dumps(b)
        assert not any(isinstance(x, Decimal) for x in _walk(b))
    assert isinstance(AUD.risk_pct(10.0, 9.0), Decimal)                                 # internal only


def test_held_text_lists_every_failed_rule():
    F, r = world("GRRRR", stop=8.0, brk_vol=1)
    b = _j(r, F, [])
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
    assert tuple(r.id for r in AUD.REGISTRY) == ("G1", "G2", "G3", "G4") + NEW_IDS + ("K3S",)   # 2026-11-09: + K3S LAST
    for r in AUD.REGISTRY:
        assert r.date_added == ("2026-11-09" if r.id == "K3S" else "2026-11-01") and r.status in AUD.STATUSES
        assert r.name and r.rule and r.params and r.source and r.verdict_source and r.changes
        assert r.verdict == AUD.VERDICT_UNMEASURED
    assert [r.id for r in AUD.on_rules()] == ["G1", "G2", "G4", "T1", "T2", "A1", "H1", "T4", "A2", "T3", "T5", "K3S"]
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
        assert r.source[0][0] == r.prereg and r.prereg in AUD.PREREG_SHA_BY_PATH
        assert r.prereg == (AUD.PREREG3_PATH if r.id == "K3S" else
                            AUD.PREREG2_PATH if r.id in NEW_IDS else AUD.PREREG_PATH)


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
                entry = vr["topics"][ti]["verified"][vi]
                # the JSON text (escaped quotes) or the rule's own line verbatim (a quote holding GG's quote marks)
                assert quote in json.dumps(entry, ensure_ascii=False) or quote in entry["rule"], (r.id, where)
            n += 1
    assert n == 9 and AUD.G3.gg == ()                                              # 2026-11-09: + K3S's S8 36:12 line
    for rid in ("T1", "A1", "T4", "T3"):                                                  # NO GG words on file
        assert AUD.by_id(rid).gg == (), rid
    assert [w for _f, w, _q in AUD.H1.gg + AUD.T2.gg + AUD.A2.gg + AUD.T5.gg] == [
        "topics[1].verified[5]", "topics[3].verified[9]", "topics[5].verified[3]", "topics[11].verified[9]"]


def test_registry_rows_are_words_only_and_say_unmeasured():
    rows = AUD.registry_rows()
    assert [r["id"] for r in rows] == ["G1", "G2", "G3", "G4"] + list(NEW_IDS) + ["K3S"]
    keys = {"id", "name", "rule", "params_text", "source_text", "since", "status", "status_text", "verdict",
            "verdict_text", "changes_text", "applies", "note", "kind"}                   # 2026-11-01: + kind only
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
                                  AUD.G4_MAX_RISK_PCT, AUD.MEASURE_FLOOR_WEEKS, AUD.T1_DAILY_CAP,
                                  AUD.T4_QUIET_TOP_PCT, AUD.A2_SPIKE_MULT, AUD.T5_EMA,
                                  AL.FRAME_MINUTES[AUD.T5_FRAME], GC.K3_VOL_FRAC) + AUD.T3_R_MULTS}
    for t in (AUD.T2_FIRST_HOUR_END_ET, AUD.A1_LAST_ENTRY_ET, AUD.H1_OPEN_ET, AUD.H1_CLOSE_ET):   # HH and MM parts
        allowed |= {t.strftime("%H"), t.strftime("%M")}
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


# ══ 2026-11-01 — the eight modifications (SPEC gg-audited-mods §3.0 / §3.1, WP-A) ═══════════════════════════════════
from datetime import datetime as _dtm, timedelta as _td   # noqa: E402

from daytrading.data import ET_RTH_CLOSE, ET_RTH_OPEN     # noqa: E402

HOST_LEDGER = HOST_ROOT / AUD.LEDGER_PATH
HALF_DAY = "2026-11-27"                                    # supply_demand.timeframes.HALF_DAYS — regular close 13:00


def world_at(close_hhmm: str, *, tf="5m", **kw):
    """world() whose BREAK bar closes at `close_hhmm` ET on FX.TODAY (pattern "GGG" → the break is today's bar 3)."""
    step = 15 if tf == "15m" else 5
    start = (_dtm.strptime(close_hhmm, "%H:%M") - _td(minutes=3 * step)).strftime("%H:%M")
    F, r = world(tf=tf, start=start, **kw)
    assert r["entry_bar_t"] == f"{FX.TODAY} {close_hhmm}"
    return F, r


def _prereg_rows() -> dict:
    return {ln.split("|")[1].strip(): ln for ln in PREREG2_FIX.read_text(encoding="utf-8").splitlines()
            if ln.startswith("| ") and ln.split("|")[1].strip() in NEW_IDS}


def _all_served(block) -> list:
    return [block["text"]] + [f["why"] for f in block["failed"]]


# ── the frozen prereg2 + the LEDGER rows ────────────────────────────────────────────────────────────────────────────
def test_prereg2_fixture_is_the_frozen_bytes_and_the_host_file_equals_it():
    raw = PREREG2_FIX.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == AUD.PREREG2_SHA256
    host = HOST_ROOT / AUD.PREREG2_PATH
    if host.exists():
        assert host.read_bytes() == raw
    assert dict(AUD.PREREG_SHA_BY_PATH) == {AUD.PREREG_PATH: AUD.PREREG_SHA256, AUD.PREREG2_PATH: AUD.PREREG2_SHA256,
                                            AUD.PREREG3_PATH: AUD.PREREG3_SHA256}
    assert hashlib.sha256(raw + b" ").hexdigest() != AUD.PREREG2_SHA256                 # NEGATIVE: one byte moves it
    line = next(ln for ln in SRC.splitlines() if ln.startswith("PREREG2_SHA256 ="))
    assert AUD.PREREG2_SHA256 in line


def test_prereg2_carries_his_words_the_scope_and_eight_rows():
    pre = PREREG2_FIX.read_text(encoding="utf-8")
    assert '"Yes make the changes in audited please"' in pre
    assert '"But keep a track record too to see the winners and loster"' in pre
    assert "## Scope" in pre and "## Method" in pre and "## Not in scope" in pre
    assert ("🧪 judges ONLY the A+ bars 🚩 would ring on the same pass (`alerts.refusal(...)` is None: a plan, the latest "
            "bar of its frame, the market open, inside 🚩's window, not already claimed today).") in pre
    assert "Every 🧪 record is matched to 🚩's entry by (date, symbol, setup, entry bar)." in pre
    assert ("| id | rule | parameter(s) (frozen) | source line | GG words (if any) | status | verdict | how it is "
            "judged | boundary convention |") in pre
    rows = _prereg_rows()
    assert tuple(rows) == NEW_IDS
    for rid, ln in rows.items():
        assert len(ln.split("|")) == 11, rid                                              # 9 cells, no stray pipe
        assert "| UNMEASURED |" in ln and "| ON on 🧪 only |" in ln, rid


def test_every_new_rule_quotes_its_prereg2_row():
    rows = _prereg_rows()
    for rid in NEW_IDS:
        r = AUD.by_id(rid)
        assert r.date_added == "2026-11-01" and r.status == AUD.STATUS_ON and r.applies is True
        assert r.verdict == AUD.VERDICT_UNMEASURED and r.prereg == AUD.PREREG2_PATH
        assert len(r.source) == 1 and r.source[0][0] == AUD.PREREG2_PATH
        assert r.source[0][1] in rows[rid].split("|")[3], rid                             # the parameter cell
        assert r.verdict_source.startswith(f"LEDGER.md row '🧪 {rid}' 2026-11-01: UNMEASURED")
    assert AUD.T1.source[0][1].startswith("daily entry cap: at most 2 audited A+ a day.")    # C7 wording


def test_every_new_number_is_in_its_prereg2_row():
    rows = _prereg_rows()
    assert f"at most {AUD.T1_DAILY_CAP} audited A+ a day" in rows["T1"]
    assert f"STARTS before {AUD.T2_FIRST_HOUR_END_ET:%H:%M} ET" in rows["T2"]
    assert f"STARTS after {AUD.A1_LAST_ENTRY_ET:%H:%M} ET" in rows["A1"]
    assert f"{AUD.H1_OPEN_ET:%H:%M}–{AUD.H1_CLOSE_ET:%H:%M} ET" in rows["H1"]
    assert f"≤ +{AUD.T4_QUIET_TOP_PCT:g}%" in rows["T4"] and "GC.SA_QUIET_BEST_PCT" in rows["T4"]
    assert f"≥ {AUD.A2_SPIKE_MULT:g} × the prior bar's volume" in rows["A2"]
    for k in AUD.T3_R_MULTS:
        assert f"+{k:g}R" in rows["T3"]
    assert "Intraday VCP rows only" in rows["T3"] and AUD.T3_SETUPS == ("intraday_vcp",)
    assert f"{AL.FRAME_MINUTES[AUD.T5_FRAME]}-minute CLOSE strictly under the {AUD.T5_EMA} EMA" in rows["T5"]


def test_the_ledger_has_one_unmeasured_row_per_new_entry():
    if not HOST_LEDGER.exists():
        pytest.skip("the host LEDGER.md lives outside the repo")
    txt = HOST_LEDGER.read_text(encoding="utf-8")
    want = ("UNMEASURED — forward-recorded on 🧪 from 2026-11-01; the 10-30 cohort (26 filled A+) is TOO SMALL for any "
            "of them")
    for rid in NEW_IDS:
        rows = [ln for ln in txt.splitlines() if ln.startswith(f"| 2026-11-01 | none | 🧪 {rid} ")]
        assert len(rows) == 1, rid
        cells = [c.strip() for c in rows[0].split("|")[1:-1]]
        assert cells[3] == want and cells[6] == "none (N unchanged)" and cells[7] == "0", rid
        assert AUD.PREREG2_SHA256[:12] in cells[8] and "2026-11-01_gajjala_audited_modifications_prereg.md" in cells[8]
    assert "N stays 1." in txt                                                            # NEGATIVE: N unchanged


# ── the registry ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_twelve_entry_registry_and_its_views():
    assert AUD.AUDIT_VERSION == 3                                                         # 2026-11-09: the K3S admit
    assert [r.id for r in AUD.filter_rules()] == ["G1", "G2", "G4", "T1", "T2", "A1", "H1", "T4", "A2"]
    assert [r.id for r in AUD.judge_rules()] == JUDGE_IDS                                 # NEGATIVE: no T1
    assert [r.id for r in AUD.exit_rules()] == ["T3", "T5"]
    assert len(AUD.on_rules()) == 12 and AUD.G3 not in AUD.on_rules()
    for r in AUD.REGISTRY:
        assert r.kind == (AUD.KIND_EXIT if r.id in ("T3", "T5") else
                          AUD.KIND_ADMIT if r.id == "K3S" else AUD.KIND_FILTER), r.id
    assert AUD.KINDS == ("filter", "exit", "admit")
    for i in ("G1", "G2", "G3", "G4"):                                                   # the 10-30 entries unchanged
        assert AUD.by_id(i).prereg == AUD.PREREG_PATH and AUD.by_id(i).kind == AUD.KIND_FILTER
    with pytest.raises(Exception):
        AUD.T1.status = "off"                                                            # NEGATIVE: frozen
    with pytest.raises(Exception):
        AUD.T4.kind = "exit"


@pytest.mark.parametrize("change", [{"kind": "junk"}, {"applies": False}, {"prereg": "eod-audits/research/x.md"},
                                    {"status": "maybe"}])
def test_NEGATIVE_validate_refuses_a_junk_entry(monkeypatch, change):
    bad = dataclasses.replace(AUD.T2, **change)
    monkeypatch.setattr(AUD, "REGISTRY", AUD.REGISTRY[:-1] + (bad,))
    with pytest.raises(ValueError):
        AUD.validate()


def test_validate_passes_on_the_real_registry():
    AUD.validate()


def test_exit_cols_are_built_never_typed(monkeypatch):
    assert AUD.EXIT_COLS == ("T3_2R", "T3_3R", "T5") == AUD.build_exit_cols()
    assert AUD.exit_col_key("T3", 2.0) == "T3_2R" and AUD.exit_col_key("T5") == "T5"
    assert AUD.exit_col_key("T3", 2.5) == "T3_2.5R"
    line = next(ln for ln in SRC.splitlines() if ln.startswith("EXIT_COLS ="))
    assert "build_exit_cols()" in line.partition("#")[0] and "T3_2R" not in line.partition("#")[0]
    monkeypatch.setattr(AUD, "T3_R_MULTS", (2.5,))                                        # NEGATIVE: it rebuilds
    assert AUD.build_exit_cols() == ("T3_2.5R", "T5")


def test_the_new_constants_are_read_by_name():
    def code(name):
        return next(ln for ln in SRC.splitlines() if ln.startswith(name)).partition("#")[0]
    assert AUD.T4_QUIET_TOP_PCT is GC.SA_QUIET_BEST_PCT and "GC.SA_QUIET_BEST_PCT" in code("T4_QUIET_TOP_PCT =")
    assert not re.search(r"\d", code("T4_QUIET_TOP_PCT =").partition("=")[2])             # NEGATIVE: no second 40
    assert AUD.T5_EMA == GC.EMA_SLOW and "GC.EMA_SLOW" in code("T5_EMA =")
    assert not re.search(r"\d", code("T5_EMA =").partition("=")[2])                       # NEGATIVE: no second 21
    assert AUD.T5_FRAME == V.GG5.primary == "5m" and "V.GG5.primary" in code("T5_FRAME =")
    assert (AUD.H1_OPEN_ET, AUD.H1_CLOSE_ET) == (ET_RTH_OPEN, ET_RTH_CLOSE)
    assert "ET_RTH_OPEN, ET_RTH_CLOSE" in code("H1_OPEN_ET, H1_CLOSE_ET =")
    assert AUD.G2_MAX_RED == GC.RED_CLOSES_WAIT == 3                                      # G2 untouched
    assert AUD.A1.params["k8"] == GC.K8_MAX_FLOAT and f"{GC.K8_MAX_FLOAT:,}" in AUD.A1.note


def test_registry_rows_carry_kind_and_the_right_prereg_sha():
    rows = {r["id"]: r for r in AUD.registry_rows()}
    for rid, row in rows.items():
        sha = (AUD.PREREG3_SHA256 if rid == "K3S" else AUD.PREREG2_SHA256 if rid in NEW_IDS else AUD.PREREG_SHA256)
        assert f"(sha256 {sha[:12]}…)" in row["source_text"], rid
        assert row["kind"] == AUD.by_id(rid).kind and "{" not in row["rule"] and "{" not in row["params_text"]
        for v in row.values():
            if isinstance(v, str):
                assert "None" not in v, (rid, v[:60])
    assert rows["T2"]["rule"] == "not A+ when the break bar starts before 10:30 ET"
    assert rows["A1"]["rule"] == "not A+ when the break bar starts after 11:59 ET"
    assert rows["H1"]["rule"].startswith("not A+ when the break bar starts outside 09:30–16:00 ET")
    assert rows["T4"]["rule"] == "not A+ when the day's top scanner runner is ≤ +40% at the ring"
    assert rows["A2"]["rule"] == "not A+ when the break bar's volume is ≥ 10× the prior bar's volume"
    assert "+2R" in rows["T3"]["rule"] and "+3R" in rows["T3"]["rule"]
    assert rows["T5"]["rule"] == "after the fill, exit at the first 5-minute close under the 21 EMA; the stop still first"
    assert rows["T1"]["rule"].startswith("at most 2 audited A+ a day")
    assert 'GG: "Very little premarket trading' in rows["H1"]["source_text"]
    json.dumps(rows)


def test_the_notes_carry_the_prereg_words():
    t4 = AUD.T4.note
    assert "unverified overflow (REPORT §6 T4: GG webinar CI7mNvEQyms ~43:15–45:30)" in t4
    assert ("Ross audit Q5: a ≥50% mover existed by 10:00 on 501 of 504 days, so this gate may almost never fire. "
            "Count how often it fires before anything else") in t4
    assert "fired alone" in t4 and "HIS CALL #18" in t4
    assert "tie" in AUD.T1.note and "HIS CALL #16" in AUD.T1.note and "alerts._candidates" in AUD.T1.note
    assert "HIS CALL #17" in AUD.T3.note and "HIS CALL #20" in AUD.T5.note and "HIS CALL #22" in AUD.H1.note
    assert "a start of exactly 10:30 passes" in AUD.T2.note and "NO-OP" in AUD.A1.note
    assert "exactly 10× fails" in AUD.A2.note and "HIS CALL #14" in AUD.A2.note


def test_NEGATIVE_no_served_registry_word_says_none_edge_or_the_b_word():
    texts = [AUD.rules_clause(), AUD.T1_TIE_TEXT, AUD.T1_KEPT] + list(AUD.NONE_WHY.values())
    for row in AUD.registry_rows():
        texts += [v for v in row.values() if isinstance(v, str)]
    for s in texts:
        assert "None" not in s and not EDGE.search(s) and not B_WORD.search(s), s[:80]
    assert all(AUD.NONE_WHY[i] for i in JUDGE_IDS + ["T1"])                              # one sentence per rule


# ── the clock rules: T2 / A1 / H1 (the break bar's START, alerts.window_reason convention) ────────────────────────
def test_bar_start_is_the_close_minus_the_frame():
    assert AUD.bar_start_et("2026-10-13 10:35", "5m").strftime("%H:%M") == "10:30"
    assert AUD.bar_start_et("2026-10-13 10:45", "15m").strftime("%H:%M") == "10:30"
    assert AUD.bar_start_et("2026-10-13 10:35", "1m").strftime("%H:%M") == "10:34"
    assert AUD.bar_start_et("2026-10-13 10:35", "junk").strftime("%H:%M") == "10:30"     # the GG5 primary's minutes
    assert AUD.bar_start_et("nope", "5m") is None and AUD.bar_start_et(None, "5m") is None   # NEGATIVE


def test_t2_start_1030_passes_1025_fails():
    t = lambda h, m, s=0: _dtm(2026, 10, 13, h, m, s)
    assert AUD.t2_pass(t(10, 30)) is True and AUD.t2_pass(t(10, 25)) is False
    assert AUD.t2_pass(t(10, 29, 59)) is False and AUD.t2_pass(None) is None             # NEGATIVE
    F, r = world_at("10:35")                                                              # start 10:30 → passes
    assert "T2" in _j(r, F, [])["passed"]
    F, r = world_at("10:30")                                                              # start 10:25 → fails
    b = _j(r, F, [])
    assert _failed(b) == {"T2": "the break bar started 10:25 ET, before 10:30"}
    assert b["values"]["T2"] == {"start_et": "10:25", "cut_et": "10:30", "frame": "5m"}


def test_a1_start_1155_passes_1200_fails():
    t = lambda h, m: _dtm(2026, 10, 13, h, m)
    assert AUD.a1_pass(t(11, 55)) is True and AUD.a1_pass(t(11, 59)) is True and AUD.a1_pass(t(12, 0)) is False
    assert AUD.a1_pass(None) is None
    F, r = world_at("12:00")                                                              # start 11:55 → passes
    assert _j(r, F, [])["aplus"] is True
    F, r = world_at("12:05")                                                              # start 12:00 → fails
    b = _j(r, F, [])
    assert _failed(b) == {"A1": "the break bar started 12:00 ET, after 11:59"}            # NEGATIVE


def test_h1_0925_fails_1555_passes_1600_fails():
    d = FX.TODAY
    assert AUD.h1_pass(f"{d} 09:30", d, "5m") is False                                    # start 09:25
    assert AUD.h1_pass(f"{d} 09:35", d, "5m") is True                                     # start 09:30
    assert AUD.h1_pass(f"{d} 16:00", d, "5m") is True                                     # start 15:55
    assert AUD.h1_pass(f"{d} 16:05", d, "5m") is False                                    # start 16:00
    assert AUD.h1_pass(f"{d} 16:15", d, "15m") is False and AUD.h1_pass(f"{d} 16:00", d, "15m") is True
    F, r = world_at("16:05")
    b = _j(r, F, [])
    assert _failed(b)["H1"] == "the break bar started 16:00 ET, outside 09:30–16:00 ET"
    assert b["values"]["H1"] == {"start_et": "16:00", "open_et": "09:30", "close_et": "16:00", "frame": "5m"}


def test_h1_on_a_half_day_closes_at_1300():
    assert AUD.h1_pass(f"{HALF_DAY} 13:00", HALF_DAY, "5m") is True                       # start 12:55
    assert AUD.h1_pass(f"{HALF_DAY} 13:05", HALF_DAY, "5m") is False                      # start 13:00
    F, r = world_at("10:50")
    r["entry_bar_t"] = f"{HALF_DAY} 13:05"                                                # the clock rules read the stamp
    b = AUD.judge(r, F, [], ctx=dict(CTX, session=HALF_DAY))
    assert _failed(b)["H1"] == "the break bar started 13:00 ET, outside 09:30–13:00 ET"


def test_NEGATIVE_h1_without_a_session_or_a_clock_fails_closed():
    assert AUD.h1_pass(f"{FX.TODAY} 10:50", None, "5m") is None
    assert AUD.h1_pass(f"{FX.TODAY} 10:50", "not-a-date", "5m") is None
    assert AUD.h1_pass("nope", FX.TODAY, "5m") is None
    F, r = world_at("10:50")
    b = AUD.judge(r, F, [], ctx={"best_change_pct": 55.0})
    assert _failed(b) == {"H1": AUD.NONE_WHY["H1"]}
    r["entry_bar_t"] = "junk"
    b = _j(r, F, [])
    for rid in ("T2", "A1", "H1"):
        assert _failed(b)[rid] == AUD.NONE_WHY[rid]
    assert b["values"]["T2"]["start_et"] is None


# ── T4 regime gate ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_t4_40_fails_40_01_passes():
    assert AUD.t4_pass(40.0) is False and AUD.t4_pass(40.01) is True and AUD.t4_pass(-5.0) is False
    assert AUD.t4_pass(None) is None and AUD.t4_pass("junk") is None and AUD.t4_pass(True) is None   # NEGATIVE
    assert AUD.t4_pass(float("nan")) is None
    F, r = world_at("10:50")
    b = AUD.judge(r, F, [], ctx=dict(CTX, best_change_pct=40.0))
    assert _failed(b) == {"T4": "the day's top runner is +40.0% (RUNR) — at or under 40%"}
    assert b["values"]["T4"] == {"best_change_pct": 40.0, "best_symbol": "RUNR", "max_pct": 40.0, "fired": True}
    b = AUD.judge(r, F, [], ctx=dict(CTX, best_change_pct=40.01))
    assert b["aplus"] is True and b["values"]["T4"]["fired"] is False
    b = AUD.judge(r, F, [], ctx=dict(CTX, best_change_pct=12.0, best_symbol=None))
    assert _failed(b)["T4"] == "the day's top runner is +12.0% — at or under 40%"


def test_NEGATIVE_judge_without_ctx_holds_on_t4_and_h1():
    F, r = world_at("10:50")
    b = AUD.judge(r, F, [])
    assert b["aplus"] is False and _failed(b) == {"H1": AUD.NONE_WHY["H1"], "T4": AUD.NONE_WHY["T4"]}
    assert b["values"]["T4"]["fired"] is True and b["values"]["T4"]["best_change_pct"] is None
    assert all("None" not in s for s in _all_served(b))


def test_t4_reads_the_constant_at_call_time(monkeypatch):
    monkeypatch.setattr(AUD, "T4_QUIET_TOP_PCT", 60.0)
    assert AUD.t4_pass(55.0) is False and AUD.t4_pass(60.5) is True


# ── A2 volume-spike skip (the read's own frame) ─────────────────────────────────────────────────────────────────────
def test_a2_exactly_10x_fails_9_9x_passes():
    F, r = world_at("10:50", brk_vol=10 * 100_000)
    b = _j(r, F, [])
    assert _failed(b) == {"A2": "break-bar volume 1.0M is ≥ 10× the prior bar 100.0K"}
    assert b["values"]["A2"] == {"vol": 1_000_000.0, "prior_vol": 100_000.0, "mult": 10.0, "ratio": 10.0,
                                 "frame": "5m"}
    F, r = world_at("10:50", brk_vol=990_000)
    b = _j(r, F, [])
    assert b["aplus"] is True and b["values"]["A2"]["ratio"] == 9.9


def test_NEGATIVE_a2_no_prior_bar_or_a_zero_prior_volume_fails_closed():
    F, r = world_at("10:50")
    assert AUD.a2_pass(F, 0) is None and AUD.a2_pass(F, len(F.v)) is None and AUD.a2_pass(None, 3) is None
    assert AUD.a2_pass(F, True) is None
    F, r = world_at("10:50", base_vol=0)                                                  # the prior bar printed 0
    b = _j(r, F, [])
    assert _failed(b) == {"A2": AUD.NONE_WHY["A2"]} and b["values"]["A2"]["ratio"] is None
    assert all("None" not in s for s in _all_served(b))


def test_a2_is_judged_on_the_reads_own_15m_frame():
    F, r = world_at("11:05", tf="15m", setup="horizontal_fade", brk_vol=10 * 100_000)
    j = F.t.index(r["entry_bar_t"])
    b = _j(r, F, [])
    assert "A2" in _failed(b) and b["values"]["A2"]["frame"] == "15m" == b["frame"]
    assert b["values"]["A2"]["prior_vol"] == F.v[j - 1] and AUD.a2_pass(F, j) is False
    assert b["values"]["T2"]["start_et"] == "10:50"                                       # 15-minute START (close − 15)


def test_judge_is_json_native_on_every_new_path():
    F, r = world_at("16:05", brk_vol=10 * 100_000)
    for ctx in (CTX, None, dict(CTX, best_change_pct=40.0), {"session": "junk"}):
        b = AUD.judge(r, F, [], ctx=ctx)
        json.dumps(b)
        assert not any(isinstance(x, Decimal) for x in _walk(b))
        assert set(b) == set(AUD.AUDIT_SERVED_KEYS) and b["rules"] == JUDGE_IDS
        for s in _all_served(b):
            assert "None" not in s and not EDGE.search(s) and not B_WORD.search(s), s


# ── T1: ring order, the slots, the tie, with_t1 ─────────────────────────────────────────────────────────────────────
def _item(sym, setup, bar, aplus=True):
    read = {"setup": setup, "state": "aplus", "entry_bar_t": f"{FX.TODAY} {bar}", "frame": "5m"}
    return (sym, setup, read, {"aplus": aplus})


def test_ring_order_is_alerts_candidates_order_on_the_same_reads():
    items = [_item("zzz", "bull_flag", "10:45"), _item("AAA", "horizontal_fade", "10:45"),
             _item("AAA", "kiss_fly", "10:45"), _item("MMM", "bull_flag", "10:40"),
             _item("BBB", "intraday_vcp", "11:00"), _item("CCC", "reversal_squeeze", "10:45")]
    reads = {}
    for sym, setup, read, _a in items:
        reads.setdefault(sym, {})[setup] = read
    want = [(c[2], c[3]) for c in AL._candidates(reads)]                                 # the ONE engine
    got = [(str(s).upper(), st) for s, st, _r, _a in AUD.ring_order(items)]
    assert got == want
    assert got == [("MMM", "bull_flag"), ("ZZZ", "bull_flag"), ("AAA", "kiss_fly"), ("AAA", "horizontal_fade"),
                   ("CCC", "reversal_squeeze"), ("BBB", "intraday_vcp")]
    # NEGATIVE: setup order is SETUPS order (kiss_fly before horizontal_fade), never alphabetical
    assert got.index(("AAA", "kiss_fly")) < got.index(("AAA", "horizontal_fade"))
    assert AUD.ring_order([]) == [] and AUD.ring_order(None) == []
    assert AUD.ring_order(list(reversed(items))) == AUD.ring_order(items)               # input order never matters


def test_NEGATIVE_a_later_bar_never_outranks_an_earlier_one():
    order = AUD.ring_order([_item("AAA", "bull_flag", "10:50"), _item("ZZZ", "reversal_squeeze", "10:45")])
    assert [o[0] for o in order] == ["ZZZ", "AAA"]


def test_t1_third_survivor_held_first_two_pass():
    order = AUD.ring_order([_item("CCC", "bull_flag", "10:55"), _item("AAA", "bull_flag", "10:45"),
                            _item("BBB", "bull_flag", "10:50")])
    s = AUD.t1_slots(order, set())
    assert [s[(k, "bull_flag")][0] for k in ("AAA", "BBB", "CCC")] == [True, True, False]
    assert s[("AAA", "bull_flag")][2]["slot"] == 1 and s[("BBB", "bull_flag")][2]["slot"] == 2
    ok, why, vals = s[("CCC", "bull_flag")]
    assert why == "daily cap of 2 reached — the slots went to AAA 10:45, BBB 10:50"
    assert vals["tie"] is False and vals["cap"] == 2 and vals["used_before"] == 0 and vals["slot"] is None   # NEGATIVE
    assert vals["holders"] == [{"symbol": "AAA", "setup": "bull_flag", "entry_bar_t": f"{FX.TODAY} 10:45"},
                               {"symbol": "BBB", "setup": "bull_flag", "entry_bar_t": f"{FX.TODAY} 10:50"}]
    assert vals["order"] == 3
    json.dumps({str(k): v for k, v in s.items()})


def test_t1_a_claimed_pair_keeps_its_slot_without_a_new_one():
    order = AUD.ring_order([_item("AAA", "bull_flag", "11:10"), _item("BBB", "bull_flag", "11:10"),
                            _item("CCC", "bull_flag", "11:10")])
    s = AUD.t1_slots(order, {("aaa", "bull_flag")})                                       # case-blind
    assert s[("AAA", "bull_flag")][0] is True and s[("AAA", "bull_flag")][2]["slot"] == AUD.T1_KEPT
    assert s[("BBB", "bull_flag")][0] is True and s[("BBB", "bull_flag")][2]["slot"] == 2
    ok, why, vals = s[("CCC", "bull_flag")]
    assert ok is False and vals["used_before"] == 1
    assert why.startswith("daily cap of 2 reached — the slots went to AAA earlier today, BBB 11:10")
    s = AUD.t1_slots(order, {("XXX", "bull_flag"), ("YYY", "kiss_fly")})                  # cap already used up
    assert all(v[0] is False for v in s.values())


def test_t1_three_on_one_bar_holds_the_symbol_last_and_flags_the_tie():
    order = AUD.ring_order([_item("CCC", "bull_flag", "10:45"), _item("AAA", "bull_flag", "10:45"),
                            _item("BBB", "bull_flag", "10:45")])
    s = AUD.t1_slots(order, set())
    ok, why, vals = s[("CCC", "bull_flag")]
    assert ok is False and vals["tie"] is True and why.endswith(AUD.T1_TIE_TEXT)
    assert s[("BBB", "bull_flag")][2]["tie"] is True                                      # took the LAST slot
    assert s[("AAA", "bull_flag")][2]["tie"] is False                                     # NEGATIVE: not on the line


def test_NEGATIVE_a_hold_on_a_bar_no_other_survivor_shares_is_not_a_tie():
    order = AUD.ring_order([_item("AAA", "bull_flag", "10:45"), _item("BBB", "bull_flag", "10:45"),
                            _item("AAB", "bull_flag", "10:50")])
    s = AUD.t1_slots(order, set())
    ok, why, vals = s[("AAB", "bull_flag")]
    assert ok is False and vals["tie"] is False and not why.endswith(AUD.T1_TIE_TEXT)
    assert s[("BBB", "bull_flag")][2]["tie"] is False


def test_t1_claims_fault_fails_every_survivor_closed():
    order = AUD.ring_order([_item("AAA", "bull_flag", "10:45"), _item("BBB", "bull_flag", "10:50")])
    s = AUD.t1_slots(order, None, claims_fault=True)
    for ok, why, vals in s.values():
        assert ok is None and why == AUD.NONE_WHY["T1"] and vals["holders"] == [] and vals["tie"] is False
    assert AUD.t1_slots([], set()) == {}
    assert AUD.t1_slots(order, set(), cap=1)[("BBB", "bull_flag")][0] is False           # cap read from the argument


def test_with_t1_appends_t1_last_and_recomputes_aplus_and_text():
    F, r = world_at("10:50")
    base = _j(r, F, [])
    before = json.dumps(base, sort_keys=True)
    a = AUD.with_t1(base, True, "", {"slot": 1})
    assert a["rules"] == JUDGE_IDS + ["T1"] == a["passed"] and a["aplus"] is True
    assert a["text"] == "audited A+ — G1 · G2 · G4 · T2 · A1 · H1 · T4 · A2 · T1 pass · UNMEASURED"
    assert a["values"]["T1"] == {"slot": 1} and set(a) == set(AUD.AUDIT_SERVED_KEYS)
    assert json.dumps(base, sort_keys=True) == before                                     # NEGATIVE: input untouched
    h = AUD.with_t1(base, False, "daily cap of 2 reached — the slots went to AAA 10:45, BBB 10:50", {"slot": None})
    assert h["aplus"] is False and h["failed"] == [{"id": "T1", "why": "daily cap of 2 reached — the slots went to "
                                                                      "AAA 10:45, BBB 10:50"}]
    assert h["text"].startswith("🚩 A+ on the original, held here by: T1 — daily cap of 2 reached")
    n = AUD.with_t1(base, None, "ignored", {})
    assert n["aplus"] is False and _failed(n) == {"T1": AUD.NONE_WHY["T1"]}
    again = AUD.with_t1(a, False, "x", {})
    assert again["rules"].count("T1") == 1 and _failed(again) == {"T1": "x"}             # replaced, never doubled
    assert AUD.with_t1(None, True, "", {}) is None and AUD.with_t1("junk", True, "", {}) is None


def test_with_t1_on_a_read_another_rule_held_keeps_that_why():
    F, r = world_at("10:50", brk_vol=10 * 100_000)
    base = _j(r, F, [])
    a = AUD.with_t1(base, True, "", {"slot": 1})
    assert a["aplus"] is False and _failed(a) == _failed(base) and a["rules"][-1] == "T1"
    assert a["passed"][-1] == "T1" and a["frame"] == base["frame"] and a["version"] == AUD.AUDIT_VERSION


def test_NEGATIVE_no_t1_why_says_none_edge_or_the_b_word():
    order = AUD.ring_order([_item("AAA", "bull_flag", "10:45"), _item("BBB", "bull_flag", "10:45"),
                            _item("CCC", "bull_flag", "10:45")])
    for claimed, fault in ((set(), False), ({("AAA", "bull_flag")}, False), (set(), True)):
        for ok, why, vals in AUD.t1_slots(order, claimed, claims_fault=fault).values():
            assert "None" not in why and not EDGE.search(why) and not B_WORD.search(why)
            json.dumps(vals)
