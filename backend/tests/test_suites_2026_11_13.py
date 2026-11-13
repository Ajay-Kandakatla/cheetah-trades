"""Suites refix (2026-11-13): the 🔑 key_levels import guard was WIDENED for two files
(`long_term_list/zone_watch.py`, `scripts/long_term_zone_probe.py`). These tests keep that
widening as narrow as its comment in `tests/test_key_levels.py` claims: the zone pass imports
key_levels lazily, inside `prev_session` only, and reads `prev_market_day` and nothing else;
the probe imports it only to time it and never writes Mongo or sends a push.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from tests.test_key_levels import ALLOWED, _IMPORT_RE

BACKEND = Path(__file__).resolve().parents[1]
ZW_PATH = BACKEND / "long_term_list" / "zone_watch.py"
PROBE_PATH = BACKEND / "scripts" / "long_term_zone_probe.py"

_TOP_LEVEL_IMPORT = re.compile(
    r"^(from\s+supply_demand\s+import\s+[^\n]*\bkey_levels\b|from\s+supply_demand\.key_levels\s+import"
    r"|import\s+supply_demand\.key_levels)", re.M)
_KL_ATTR = re.compile(r"\bKL\.([A-Za-z_]\w*)")
_KEY_LEVELS_ATTR = re.compile(r"\bkey_levels\.([A-Za-z_]\w*)")
_WRITE_CALL = re.compile(r"\.(send|send_push|send_to_all|insert_one|insert_many|update_one|update_many"
                         r"|replace_one|delete_one|delete_many|find_one_and_update|bulk_write)\(")


def _kl_uses(src: str) -> set:
    return set(_KL_ATTR.findall(src))


def _functions_importing_kl(src: str) -> list:
    """Names of the def blocks whose body holds a key_levels import."""
    names, current = [], None
    for line in src.splitlines():
        m = re.match(r"^def\s+(\w+)\(", line)
        if m:
            current = m.group(1)
        elif line and not line[0].isspace():
            current = None
        if _IMPORT_RE.search(line + "\n") and current:
            names.append(current)
    return names


def test_both_widened_files_are_in_the_guard_and_nothing_else_from_long_term_list():
    assert "long_term_list/zone_watch.py" in ALLOWED
    assert "scripts/long_term_zone_probe.py" in ALLOWED
    assert not [p for p in ALLOWED if p.startswith("long_term_list/") and p != "long_term_list/zone_watch.py"]


def test_zone_watch_imports_key_levels_lazily_inside_prev_session_only():
    src = ZW_PATH.read_text(encoding="utf-8")
    assert _IMPORT_RE.search(src)
    assert not _TOP_LEVEL_IMPORT.search(src)
    assert _functions_importing_kl(src) == ["prev_session"]


def test_zone_watch_reads_prev_market_day_and_no_other_key_levels_name():
    src = ZW_PATH.read_text(encoding="utf-8")
    assert _kl_uses(src) == {"prev_market_day"}
    assert not _KEY_LEVELS_ATTR.findall(src.replace("key_levels.prev_market_day", ""))


def test_NEGATIVE_the_checks_catch_a_module_level_import_and_a_tile_read():
    bad_top = "from supply_demand import key_levels as KL\n\ndef prev_session(s):\n    return KL.prev_market_day(s)\n"
    assert _TOP_LEVEL_IMPORT.search(bad_top)
    assert _functions_importing_kl(bad_top) == []
    bad_attr = ("def prev_session(s):\n    from supply_demand import key_levels as KL\n"
                "    KL.tile_block('A', None)\n    return KL.prev_market_day(s)\n")
    assert _kl_uses(bad_attr) == {"prev_market_day", "tile_block"}
    bad_where = "def run_pass(now):\n    from supply_demand import key_levels as KL\n    return KL.prev_market_day(now)\n"
    assert _functions_importing_kl(bad_where) == ["run_pass"]


def test_prev_session_is_the_key_levels_calendar_helper():
    from long_term_list import zone_watch as ZW
    from supply_demand import key_levels as KL
    for s in ("2026-11-13", "2026-11-16", "2026-11-27", "2026-11-30"):
        assert ZW.prev_session(s) == KL.prev_market_day(date.fromisoformat(s)).isoformat()
    assert ZW.prev_session("2026-11-13") == "2026-11-12"
    assert ZW.prev_session("2026-11-16") == "2026-11-13"


def test_NEGATIVE_prev_session_never_returns_a_weekend_or_the_thanksgiving_close():
    from long_term_list import zone_watch as ZW
    assert ZW.prev_session("2026-11-16") not in ("2026-11-15", "2026-11-14")
    assert ZW.prev_session("2026-11-27") != "2026-11-26"
    assert ZW.prev_session("2026-11-27") == "2026-11-25"


def test_probe_imports_key_levels_only_to_time_it_and_never_writes_or_sends():
    src = PROBE_PATH.read_text(encoding="utf-8")
    assert not _TOP_LEVEL_IMPORT.search(src)
    assert _functions_importing_kl(src) == ["main"]
    assert not _KEY_LEVELS_ATTR.findall(src.split('"""', 2)[-1])
    assert not _kl_uses(src)
    assert not _WRITE_CALL.findall(src)
    assert "send_to_all" not in src
    assert "dry=True" in src


def test_NEGATIVE_the_probe_check_catches_a_write_and_an_attribute_read():
    bad = "def main():\n    from supply_demand import key_levels\n    key_levels.tile_block('A')\n    db.x.insert_one({})\n"
    assert _KEY_LEVELS_ATTR.findall(bad) == ["tile_block"]
    assert _WRITE_CALL.findall(bad) == ["insert_one"]
    assert _WRITE_CALL.findall("    push.send(sub, body)\n") == ["send"]
    assert not _WRITE_CALL.findall("    x = 'a $set shape in a docstring'\n")
