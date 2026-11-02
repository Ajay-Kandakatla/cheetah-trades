"""chart_maps/luk/constants.py — every number by name, each with its provenance (BUILD SPEC luk-tab §3.1, WP-A1).

AST scans keep the file honest: every assignment line STARTS its comment with a provenance tag; a Cheetah number (the
spec's MINE / derived list) is never filed as his; every `LUK <file>:<line>` cite resolves — its quoted key phrase sits
on that fixture line (±2, captions wrap); no GG number is retyped (GC names imported); the fixtures are pinned byte for
byte (sha256). NEGATIVE cases feed doctored sources to the same checker.
"""
from __future__ import annotations

import ast
import hashlib
import pathlib
import re

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.luk import constants as LC

SRC_PATH = pathlib.Path(LC.__file__)
SRC = SRC_PATH.read_text(encoding="utf-8")
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "luk"
RESEARCH = pathlib.Path("/Users/ajay/clinet-test/eod-audits/research/champions_2026_11_01")
SUBSTACK_FIXTURE = "substack_2025_02_01_quotes.md"

# the byte-copy pins live in constants.py (spec §3.1) — imported, never retyped here
LUK_SOURCE_SHA256 = LC.LUK_SOURCE_SHA256
RESEARCH_PATH = {
    "SYNTHESIS.md": "SYNTHESIS.md",
    "martin-luk.md": "sweeps/martin-luk.md",
    "luk_bt_readme.md": "sweeps/luk_bt_readme.md",
    "backtests-critiques.md": "sweeps/backtests-critiques.md",
}

# ── the fixture reader (shared by the other Luk tests) ─────────────────────────────────────────────────────────────
_TS = re.compile(r"^\[\d+:\d\d:\d\d\]\s?")


def fold(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def fixture_lines(file: str) -> list:
    return (FIXTURES / file).read_text(encoding="utf-8").splitlines()


def window(file: str, line, pad: int = 2) -> str:
    """The fixture text of lines `line` (an int, "a" or "a-b"; None = the whole file) ± pad, caption timestamps
    stripped, lines joined by one space, whitespace folded."""
    lines = fixture_lines(file)
    if line in (None, ""):
        return fold(" ".join(_TS.sub("", ln) for ln in lines))
    a, _sep, b = str(line).partition("-")
    lo, hi = int(a), int(b or a)
    lo, hi = max(1, lo - pad), min(len(lines), hi + pad)
    return fold(" ".join(_TS.sub("", ln) for ln in lines[lo - 1:hi]))


def phrase_at(phrase: str, file: str, line, pad: int = 2) -> bool:
    """Every "…"-separated fragment of `phrase` sits in that window (whitespace folded, case kept)."""
    win = window(file, line, pad)
    frags = [fold(f) for f in phrase.split("…") if fold(f)]
    return bool(frags) and all(f in win for f in frags)


# ── the tag checker ──────────────────────────────────────────────────────────────────────────────────────────────
# WIDENED 2026-11-01 (Ajay: "Lets make it live. also alerts too."): his dated word is a tag of its own
TAG = re.compile(r'^(LUK |MINE\b|derived\b|EXTERNAL\b|Ajay design #\d+|Ajay \d{4}-\d{2}-\d{2}: ")')
HIS_WORD = re.compile(r'^Ajay \d{4}-\d{2}-\d{2}: "')
LUK_FILE_CITE = re.compile(r"^LUK (?:frame U\d )?(?P<file>[\w.-]+\.(?:txt|md)):(?P<line>\d+(?:-\d+)?)\b.*?\"(?P<q>[^\"]+)\"")
LUK_SUBSTACK = re.compile(r"^LUK substack \"(?P<q>[^\"]+)\"")
# the spec's MINE / derived numbers (§3.1 + §7) — never his
MINE_NAMES = frozenset({
    "LUK_TAB_LABEL", "LUK_TAB", "LUK_ENABLED", "LUK_KIND", "LUK_PASS_OPEN_ET", "LUK_PASS_CLOSE_ET",
    "LUK_PASS_BUDGET_SEC", "LUK_SLOT_MARGIN_SEC", "LUK_LEASE_SEC", "LUK_LEASE_MIN_GAP_SEC", "LUK_SHORTLIST_MAX",
    "LUK_SCREEN_TOP_N", "LUK_DAILY_MAX_NEW_PER_PASS", "LUK_DAILY_WARM_BUDGET_SEC", "LUK_DAILY_TRUST_AFTER_SEC",
    "LUK_STATE_BARS_THROUGH", "LUK_STATE_INDEX", "LUK_GRADE_BUDGET_SEC", "LUK_GRADE_MAX_LOADS", "LUK_GRADE_VERSION", "LUK_LEDGER_SPANS",
    "LUK_LEDGER_SPAN_DEFAULT", "LUK_FILL_FROM_ET", "LUK_FILL_TO_ET", "LUK_HOURLY_SESSIONS", "LUK_HOURLY_SESSION",
    "LUK_LOD_SESSION", "LUK_VOL_1W_SESSIONS", "LUK_PX_VOL_1W_SESSIONS", "LUK_PERF_1M_SESSIONS", "LUK_ADR_SESSIONS",
    "LUK_INSTRUMENT_TYPES", "LUK_TRIGGER_WINDOW_END_MIN", "LUK_PDH_WINDOW", "SETUPS", "SUBS", "DEFAULT_SUB",
    "LUK_SOURCE_SHA256",
})
DESIGN_NAMES = frozenset({"LUK_RECORD_FROM"})     # Ajay's design point #7
HIS_CALL_NAMES = frozenset({"LUK_PUSH_MODE", "LUK_LIVE_SINCE", "LUK_LIVE_WORDS"})   # his dated word (2026-11-01: "Lets make it live. also alerts too.")
# derived from GC by NAME (never retyped): constant → the GC attribute it must be
GC_DERIVED = {
    "LUK_PASS_OPEN_ET": "PASS_OPEN_ET", "LUK_LEASE_SEC": "LEASE_SEC",
    "LUK_DAILY_MAX_NEW_PER_PASS": "DAILY_MAX_NEW_PER_PASS", "LUK_DAILY_TRUST_AFTER_SEC": "BAR_SETTLE_SEC",
    "LUK_LEDGER_SPANS": "LEDGER_SPANS", "LUK_LEDGER_SPAN_DEFAULT": "LEDGER_SPAN_DEFAULT",
    "LUK_INSTRUMENT_TYPES": "SCAN_INSTRUMENT_TYPES",
}


def assigns(src: str) -> list:
    """[(name, value_node, lineno)] for every top-level `NAME = …`."""
    tree = ast.parse(src)
    return [(n.targets[0].id, n.value, n.lineno) for n in tree.body
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)]


def comment_of(src: str, lineno: int) -> str:
    line = src.splitlines()[lineno - 1]
    # the comment starts at the first " #" outside a string — none of the values here carries " # "
    idx = line.find("  #")
    return line[idx:].lstrip()[1:].strip() if idx >= 0 else ""


def tag_errors(src: str) -> list:
    """Every violation of the provenance rules in a constants source."""
    errs = []
    for name, _value, lineno in assigns(src):
        c = comment_of(src, lineno)
        if not TAG.match(c):
            errs.append((name, "untagged"))
            continue
        if name in MINE_NAMES and not re.match(r"^(MINE|derived)\b", c):
            errs.append((name, "a Cheetah number filed as his"))
            continue
        if name in DESIGN_NAMES and not c.startswith("Ajay design #"):
            errs.append((name, "Ajay's design point not tagged as such"))
            continue
        if name in HIS_CALL_NAMES and not HIS_WORD.match(c):
            errs.append((name, "his word not tagged as such"))
            continue
        if c.startswith("LUK "):
            m, s = LUK_FILE_CITE.match(c), LUK_SUBSTACK.match(c)
            if m:
                if not (FIXTURES / m.group("file")).exists():
                    errs.append((name, "cite file missing"))
                elif not phrase_at(m.group("q"), m.group("file"), m.group("line")):
                    errs.append((name, "cite does not resolve"))
            elif s:
                if not phrase_at(s.group("q"), SUBSTACK_FIXTURE, None):
                    errs.append((name, "substack cite does not resolve"))
            else:
                errs.append((name, "LUK tag without a file:line + \"phrase\" or substack phrase"))
    return errs


def luk_tagged() -> set:
    return {name for name, _v, ln in assigns(SRC) if comment_of(SRC, ln).startswith("LUK ")}


# ── the file itself ──────────────────────────────────────────────────────────────────────────────────────────────
def test_every_assignment_carries_a_resolving_tag():
    assert tag_errors(SRC) == []


def test_every_mine_and_design_name_exists():
    names = {n for n, _v, _l in assigns(SRC)}
    assert MINE_NAMES <= names and DESIGN_NAMES <= names and HIS_CALL_NAMES <= names


def test_negative_an_untagged_line_fails():
    bad = SRC.replace('LUK_SHORTLIST_MAX = 40                      # MINE (HIS CALL #4) — names whose minute bars one '
                      'pass loads', 'LUK_SHORTLIST_MAX = 40')
    assert bad != SRC
    assert ("LUK_SHORTLIST_MAX", "untagged") in tag_errors(bad)


def test_negative_a_comment_that_does_not_start_with_a_tag_fails():
    bad = SRC.replace("LUK_SCREEN_TOP_N = 25                       # MINE (HIS CALL #4)",
                      "LUK_SCREEN_TOP_N = 25                       # rows per screen, MINE (HIS CALL #4)")
    assert bad != SRC
    assert ("LUK_SCREEN_TOP_N", "untagged") in tag_errors(bad)


def test_negative_a_mine_number_filed_as_his_fails():
    bad = SRC.replace("LUK_SHORTLIST_MAX = 40                      # MINE (HIS CALL #4)",
                      'LUK_SHORTLIST_MAX = 40                      # LUK VKNEJA5r8zw.txt:359-360 [0:16:09] "0.5%"')
    assert bad != SRC
    assert ("LUK_SHORTLIST_MAX", "a Cheetah number filed as his") in tag_errors(bad)


def test_negative_a_design_point_filed_as_mine_fails():
    # RETARGETED 2026-11-01: LUK_PUSH_MODE is his dated word now (HIS_CALL_NAMES); LUK_RECORD_FROM stays design #7
    bad = SRC.replace('LUK_RECORD_FROM = "2026-11-01"              # Ajay design #7',
                      'LUK_RECORD_FROM = "2026-11-01"              # MINE')
    assert bad != SRC
    assert ("LUK_RECORD_FROM", "Ajay's design point not tagged as such") in tag_errors(bad)


def _push_mode_line() -> str:
    return next(ln for ln in SRC.splitlines() if ln.startswith("LUK_PUSH_MODE = "))


def _retag(line: str, comment: str) -> str:
    return line[:line.find("  #")] + "  # " + comment


def test_negative_his_word_filed_as_mine_fails():
    line = _push_mode_line()
    bad = SRC.replace(line, _retag(line, "MINE"))
    assert bad != SRC and ("LUK_PUSH_MODE", "his word not tagged as such") in tag_errors(bad)


def test_negative_his_word_filed_as_a_design_point_fails():
    line = _push_mode_line()
    bad = SRC.replace(line, _retag(line, "Ajay design #9"))
    assert bad != SRC and ("LUK_PUSH_MODE", "his word not tagged as such") in tag_errors(bad)


def test_negative_his_word_without_the_quote_fails():
    line = _push_mode_line()
    bad = SRC.replace(line, _retag(line, "Ajay 2026-11-01: his call"))
    # no opening quote → not even a tag (TAG requires `Ajay yyyy-mm-dd: "`), so the checker stops at "untagged"
    assert bad != SRC and ("LUK_PUSH_MODE", "untagged") in tag_errors(bad)
    assert not HIS_WORD.match("Ajay 2026-11-01: his call")


def test_negative_the_live_words_filed_as_mine_fails():
    line = next(ln for ln in SRC.splitlines() if ln.startswith("LUK_LIVE_WORDS = "))
    bad = SRC.replace(line, _retag(line, "MINE"))
    assert bad != SRC and ("LUK_LIVE_WORDS", "his word not tagged as such") in tag_errors(bad)


def test_negative_the_old_tag_regex_reads_his_word_as_untagged():
    """The TAG extension is load-bearing: under the pre-2026-11-01 regex every HIS_CALL_NAMES line is untagged."""
    old = re.compile(r"^(LUK |MINE\b|derived\b|EXTERNAL\b|Ajay design #\d+)")
    lines = {n: comment_of(SRC, ln) for n, _v, ln in assigns(SRC) if n in HIS_CALL_NAMES}
    assert set(lines) == HIS_CALL_NAMES
    assert all(not old.match(c) and TAG.match(c) for c in lines.values())


def test_negative_a_cite_at_the_wrong_line_fails():
    bad = SRC.replace('LUK VKNEJA5r8zw.txt:546-548 [0:24:39] "more than 3% from the low of day"',
                      'LUK VKNEJA5r8zw.txt:1546-1548 [0:24:39] "more than 3% from the low of day"')
    assert bad != SRC
    assert ("LUK_NO_CHASE_PCT", "cite does not resolve") in tag_errors(bad)


def test_negative_a_phrase_he_never_said_fails():
    bad = SRC.replace('"maximum will be 5%"', '"maximum will be 6%"')
    assert bad != SRC
    assert ("LUK_STOP_MAX_PCT", "cite does not resolve") in tag_errors(bad)


def test_negative_a_luk_tag_without_a_cite_fails():
    bad = SRC.replace('LUK substack "<$5B market cap"', "LUK his small-cap list")
    assert bad != SRC
    assert ("LUK_SMALL_CAP_USD", "LUK tag without a file:line + \"phrase\" or substack phrase") in tag_errors(bad)


def test_his_numbers_as_he_said_them():
    assert (LC.LUK_RISK_PER_TRADE_PCT, LC.LUK_POSITION_PCT, LC.LUK_POSITION_CAP_2024_PCT, LC.LUK_GROSS_MAX_PCT) == \
        (0.5, (25, 30), 35, 280)
    assert (LC.LUK_STOP_MAX_PCT, LC.LUK_STOP_ADR_FRAC, LC.LUK_STOP_USUAL_PCT) == (5.0, 0.5, (2.5, 3.0))
    assert (LC.LUK_NO_CHASE_PCT, LC.LUK_PULLBACK_DAILY_EMA, LC.LUK_HOURLY_EMAS) == (3.0, 9, (9, 21))
    assert (LC.LUK_ONE_MIN_UNTIL_MIN, LC.LUK_FIVE_MIN_UNTIL_MIN) == (15, 60)
    assert (LC.LUK_STOP_LOD_SHARE, LC.LUK_LOD_SWITCH_PCT) == ((60, 70), 5.0)
    assert (LC.LUK_PARTIAL_R, LC.LUK_TRIM_PCT, LC.LUK_TRIM_RANGE_PCT, LC.LUK_TRIM_PAST_PCT) == ((3, 5), 15, (10, 15), 35)
    assert LC.LUK_TRAIL_EMAS == (9, 21, 50) and LC.LUK_EXIT_RULE == "first_daily_close_below_ema9"
    assert LC.LUK_SIZING_EXAMPLE == (10_000, 0.5, 50, 2.5, 2_000, 20)
    assert (LC.LUK_ORH_CANDLE_MIN, LC.LUK_ORH_SWITCH_MIN) == (1, 5)
    assert LC.LUK_INDEX_SYMBOLS == ("QQQ", "IWM") and LC.LUK_INDEX_EMAS == (9, 21)
    assert (LC.LUK_SCREEN_MIN_CAP_USD, LC.LUK_SCREEN_MIN_AVG_VOL_10D, LC.LUK_SCREEN_MIN_PX_VOL_USD,
            LC.LUK_SCREEN_MIN_VOL_1W_PCT, LC.LUK_LEADER_MIN_PX_VOL_1W_USD) == (100e6, 500e3, 50e6, 3.5, 300e6)
    assert (LC.LUK_POTENT_CHG_FROM_OPEN_BAND_PCT, LC.LUK_POTENT_EMAS, LC.LUK_AVG_VOL_SESSIONS) == (0.5, (21, 50), 10)
    assert LC.LUK_CONSIDERED_PX_VOL_USD == 100e6
    assert (LC.LUK_ADR_PREF_PCT, LC.LUK_SMALL_CAP_USD, LC.LUK_RISK_2026_PCT) == (5.0, 5e9, 0.3)


def test_the_cheetah_numbers_and_the_design_points():
    # FLIPPED 2026-11-01 (Ajay: "Lets make it live. also alerts too."): shadow → live
    assert LC.LUK_PUSH_MODE == "live" and LC.LUK_RECORD_FROM == "2026-11-01" and LC.LUK_ENABLED is True
    assert LC.LUK_LIVE_SINCE == "2026-11-01"
    assert LC.LUK_LIVE_WORDS == "Lets make it live. also alerts too."
    assert (LC.LUK_TAB, LC.LUK_TAB_LABEL, LC.LUK_KIND) == ("luk", "🥇 Luk's", "luk_setup")
    assert (LC.LUK_PASS_OPEN_ET, LC.LUK_PASS_CLOSE_ET) == ("04:00", "16:05")
    assert (LC.LUK_PASS_BUDGET_SEC, LC.LUK_SLOT_MARGIN_SEC, LC.LUK_SHORTLIST_MAX, LC.LUK_SCREEN_TOP_N) == (120, 20, 40, 25)
    assert (LC.LUK_DAILY_WARM_BUDGET_SEC, LC.LUK_GRADE_BUDGET_SEC, LC.LUK_GRADE_MAX_LOADS) == (60, 30, 60)
    assert (LC.LUK_HOURLY_SESSIONS, LC.LUK_HOURLY_SESSION, LC.LUK_LOD_SESSION, LC.LUK_PDH_WINDOW) == \
        (10, "rth", "rth", "rth")
    assert (LC.LUK_VOL_1W_SESSIONS, LC.LUK_PX_VOL_1W_SESSIONS, LC.LUK_PERF_1M_SESSIONS, LC.LUK_ADR_SESSIONS) == \
        (5, 5, 21, 20)
    assert LC.LUK_STATE_BARS_THROUGH == "bars_through"
    assert LC.LUK_STATE_INDEX == "index_state" and LC.LUK_STATE_INDEX != LC.LUK_STATE_BARS_THROUGH
    assert LC.LUK_TRIGGER_WINDOW_END_MIN == LC.LUK_FIVE_MIN_UNTIL_MIN
    assert LC.LUK_LEASE_MIN_GAP_SEC == LC.LUK_PASS_BUDGET_SEC


def test_the_push_mode_line_quotes_his_live_words_by_name():
    c = comment_of(SRC, next(ln for n, _v, ln in assigns(SRC) if n == "LUK_PUSH_MODE"))
    assert c.startswith('Ajay 2026-11-01: "') and LC.LUK_LIVE_WORDS in c
    for name in ("LUK_LIVE_SINCE", "LUK_LIVE_WORDS"):
        assert LC.LUK_LIVE_WORDS in comment_of(SRC, next(ln for n, _v, ln in assigns(SRC) if n == name))


def test_the_budget_fits_inside_one_tick():
    assert LC.LUK_PASS_BUDGET_SEC + LC.LUK_SLOT_MARGIN_SEC < GC.PASS_CADENCE_SEC
    assert LC.LUK_LEASE_SEC >= LC.LUK_PASS_BUDGET_SEC


@pytest.mark.parametrize("name,gc_name", sorted(GC_DERIVED.items()))
def test_no_gg_number_is_retyped(name, gc_name):
    node = next(v for n, v, _l in assigns(SRC) if n == name)
    assert isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "GC", name
    assert node.attr == gc_name
    assert getattr(LC, name) == getattr(GC, gc_name)


def test_hourly_emas_are_gcs_by_name():
    node = next(v for n, v, _l in assigns(SRC) if n == "LUK_HOURLY_EMAS")
    assert [ast.unparse(e) for e in node.elts] == ["GC.EMA_FAST", "GC.EMA_SLOW"]


def test_the_house_clock_and_the_lab_floor_are_imported():
    from chart_maps.gajjala.audited_rules import MEASURE_FLOOR_WEEKS
    from daytrading.data import ET_RTH_CLOSE, ET_RTH_OPEN
    assert (LC.LUK_FILL_FROM_ET, LC.LUK_FILL_TO_ET) == (ET_RTH_OPEN, ET_RTH_CLOSE)
    assert LC.MEASURE_FLOOR_WEEKS == MEASURE_FLOOR_WEEKS == 30


def test_the_file_imports_only_gc_the_lab_floor_and_the_house_clock():
    tree = ast.parse(SRC)
    mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module)
    assert mods == {"chart_maps.gajjala", "chart_maps.gajjala.audited_rules", "daytrading.data"}


def test_no_threshold_constant_and_the_2pct_example_is_not_a_constant():
    names = {n for n, _v, _l in assigns(SRC)}
    assert not [n for n in names if "THRESHOLD" in n]
    assert "LUK_QQQ_EXAMPLE_PCT" not in names and not hasattr(LC, "LUK_QQQ_EXAMPLE_PCT")


def test_subs_and_setups():
    assert LC.SETUPS == ("pullback_reversal", "opening_range_high", "inside_day_pdh")
    assert tuple(k for k, _e, _l in LC.SUBS) == LC.SETUPS + ("premarket", "leader", "potent", "playbook",
                                                           "track_record")
    assert LC.SUBS[-1] == ("track_record", "🏁", "Track record") and LC.DEFAULT_SUB in LC.SETUPS
    assert all(isinstance(e, str) and e and isinstance(lab, str) and lab for _k, e, lab in LC.SUBS)


# ── the fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,digest", sorted(LUK_SOURCE_SHA256.items()))
def test_the_fixtures_are_pinned_byte_for_byte(name, digest):
    assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest


def test_the_fixture_set_is_exactly_the_pinned_set():
    assert {p.name for p in FIXTURES.iterdir() if p.is_file()} >= set(LUK_SOURCE_SHA256)


_HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


def test_the_pins_live_in_constants_py_and_nowhere_in_the_tests():
    node = next(v for n, v, _l in assigns(SRC) if n == "LUK_SOURCE_SHA256")
    assert isinstance(node, ast.Dict) and len(node.keys) == 11
    assert all(isinstance(v, ast.Constant) and _HEX64.fullmatch(v.value) for v in node.values)
    me = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert not _HEX64.search(me)
    assert LUK_SOURCE_SHA256 is LC.LUK_SOURCE_SHA256


def test_negative_a_doctored_byte_breaks_the_pin():
    raw = (FIXTURES / "VKNEJA5r8zw.txt").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == LC.LUK_SOURCE_SHA256["VKNEJA5r8zw.txt"]
    assert hashlib.sha256(raw + b" ").hexdigest() != LC.LUK_SOURCE_SHA256["VKNEJA5r8zw.txt"]
    assert hashlib.sha256(raw.replace(b"0.5%", b"0.6%", 1)).hexdigest() != LC.LUK_SOURCE_SHA256["VKNEJA5r8zw.txt"]


def test_negative_the_pin_line_untagged_fails():
    line = next(ln for ln in SRC.splitlines() if ln.startswith("LUK_SOURCE_SHA256 = {"))
    bad = SRC.replace(line, "LUK_SOURCE_SHA256 = {")
    assert bad != SRC
    assert ("LUK_SOURCE_SHA256", "untagged") in tag_errors(bad)
    filed_as_his = SRC.replace(line, 'LUK_SOURCE_SHA256 = {   # LUK VKNEJA5r8zw.txt:359-360 [0:16:09] "0.5%"')
    assert ("LUK_SOURCE_SHA256", "a Cheetah number filed as his") in tag_errors(filed_as_his)


@pytest.mark.skipif(not RESEARCH.exists(), reason="the research folder lives on the dev host only")
@pytest.mark.parametrize("name", sorted(n for n in LUK_SOURCE_SHA256 if n != SUBSTACK_FIXTURE))
def test_the_fixtures_are_byte_copies_of_the_research(name):
    src = RESEARCH / RESEARCH_PATH.get(name, "luk_transcripts/" + name)
    assert src.read_bytes() == (FIXTURES / name).read_bytes()


def test_the_substack_fixture_names_its_url_and_fetch_date():
    head = "\n".join(fixture_lines(SUBSTACK_FIXTURE)[:8])
    assert "https://tradingresourcehub.substack.com/p/martin-luk-283-usic-2024-key-lessons" in head
    assert "Published: 2025-02-01" in head and "Fetched: 2026-11-01" in head


def test_negative_the_window_reader_respects_the_pad():
    assert phrase_at("0.5%", "VKNEJA5r8zw.txt", "360", pad=0)
    assert not phrase_at("0.5%", "VKNEJA5r8zw.txt", "365", pad=2)
    assert phrase_at("risk per trade is around … 0.5%", "VKNEJA5r8zw.txt", "359")
    assert not phrase_at("", "VKNEJA5r8zw.txt", "359")
