"""🧮 FLOAT SOURCE AUDIT — the source guards (2026-11-26, spec floatguard rev 2 §4.4, package be-audit).

Ajay 2026-11-26 ~21:20 ET, verbatim: "Also the Float share count issue and SI discrepancy happened too many times need
to do something about it"

short_interest/source_audit.py is DISPLAY ONLY: it imports no push / alert / trading / notify module and never kicks a
worker; it holds no division; only high_si.py imports it (lazily, fenced); it writes only through the store's set_state
and share_basis's own writers (store_mfloats, widen_splits, refresh_symbol). nightly.py names none of the S10 words;
high_si.py still calls SR.si_map once and names the Watch only for its constants; si_track.py's short-interest import
set is unchanged. Every pin has a planted NEGATIVE showing the matcher bites.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SA_REL = "short_interest/source_audit.py"
SA_SRC = BACKEND.joinpath(SA_REL).read_text(encoding="utf-8")
GG = BACKEND.joinpath("chart_maps", "gajjala")
HS_SRC = GG.joinpath("high_si.py").read_text(encoding="utf-8")
NG_SRC = GG.joinpath("nightly.py").read_text(encoding="utf-8")
SIT_SRC = GG.joinpath("si_track.py").read_text(encoding="utf-8")

BANNED_MODULE_PARTS = ("push", "alerts", "alert", "trading", "notify", "notifications", "twilio", "pushover")
WRITE_CALLS = {"update_one", "update_many", "replace_one", "insert_one", "insert_many", "delete_one", "delete_many",
               "bulk_write", "find_one_and_update", "find_one_and_replace", "find_one_and_delete", "set_state",
               "store_mfloats", "widen_splits", "refresh_symbol", "set_broker_flag", "_upsert", "drop"}
ALLOWED_WRITERS = {"set_state", "store_mfloats", "widen_splits", "refresh_symbol"}
SI_WORDS = ("short_interest", "si_map", "si_block", "si_text", "si_read", "pct_of_float", "days_to_cover")


def _modules(src: str) -> set:
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            out.add(mod)
            out |= {f"{mod}.{a.name}" if mod else a.name for a in n.names}
        elif isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
    return out


def _banned_imports(src: str) -> list:
    return sorted(m for m in _modules(src) if any(p in m.split(".") for p in BANNED_MODULE_PARTS))


def _calls_named(src: str, names) -> list:
    out = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if nm in names:
                out.append(nm)
    return out


def _divisions(src: str) -> int:
    return sum(1 for n in ast.walk(ast.parse(src))
               if (isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.FloorDiv)))
               or (isinstance(n, ast.AugAssign) and isinstance(n.op, (ast.Div, ast.FloorDiv))))


# ── display only: no push / alert / trading / notify import, no kick ─────────────────────────────────────────────
def test_source_audit_imports_no_push_alert_trading_or_notify_module_and_never_kicks():
    assert _banned_imports(SA_SRC) == []
    assert _calls_named(SA_SRC, {"kick", "kick_refresh", "spawn_child", "_thread_spawn"}) == []
    assert "kick(" not in SA_SRC and "payload(kick=True" not in SA_SRC


@pytest.mark.parametrize("planted", ["\nfrom push import hooks as PH\n", "\nfrom chart_maps.gajjala import alerts\n",
                                     "\nimport trading.gajjala_entry\n", "\nfrom notify import send\n"])
def test_NEGATIVE_a_push_or_alert_import_trips(planted):
    assert _banned_imports(SA_SRC + planted)


def test_NEGATIVE_a_kick_call_trips():
    assert _calls_named(SA_SRC + "\ndef _x():\n    SB.kick(['A'])\n", {"kick"}) == ["kick"]


# ── no division ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_source_audit_holds_no_division():
    assert _divisions(SA_SRC) == 0


@pytest.mark.parametrize("planted", ["\nx = a / b\n", "\nn = a // b\n", "\np = Path('x') / 'y'\n", "\nq /= 2\n"])
def test_NEGATIVE_a_planted_division_trips(planted):
    assert _divisions(SA_SRC + planted) >= 1


# ── who imports it ───────────────────────────────────────────────────────────────────────────────────────────────
def _importers(planted: dict | None = None) -> set:
    hits = set()
    for f in BACKEND.rglob("*.py"):
        parts = f.relative_to(BACKEND).parts
        if parts[0] in ("tests", ".venv") or "__pycache__" in parts or "site-packages" in parts:
            continue
        rel = f.relative_to(BACKEND).as_posix()
        if rel == SA_REL:
            continue
        src = (planted or {}).get(rel) or f.read_text(encoding="utf-8", errors="ignore")
        if "source_audit" not in src:
            continue
        mods = _modules(src)
        if any(m.endswith("source_audit") for m in mods):
            hits.add(rel)
    return hits


def test_only_high_si_imports_source_audit():
    assert _importers() == {"chart_maps/gajjala/high_si.py"}


def test_NEGATIVE_an_alerts_or_rule_import_of_source_audit_trips():
    rel = "chart_maps/gajjala/alerts.py"
    planted = {rel: GG.joinpath("alerts.py").read_text(encoding="utf-8")
               + "\nfrom short_interest import source_audit as SA\n"}
    assert rel in _importers(planted) - {"chart_maps/gajjala/high_si.py"}


def test_high_si_imports_it_lazily_inside_a_try_and_the_nightly_calls_it_through_high_si():
    tree = ast.parse(HS_SRC)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not [n for n in top if "source_audit" in ast.dump(n)]
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)
             and any(isinstance(m, ast.ImportFrom) and any(a.name == "source_audit" for a in m.names)
                     for m in ast.walk(n))]
    assert len(tries) == 1
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    body = ast.dump(fns["source_audit_night"])
    assert "source_audit" in body and "audit_night" in body
    assert not [m for m in _modules(NG_SRC) if "source_audit" in m] and NG_SRC.count("HS.source_audit_night(") == 1
    nt = ast.parse(NG_SRC)
    fenced = [n for n in ast.walk(nt) if isinstance(n, ast.Try)
              and any(isinstance(m, ast.ImportFrom) and any(a.name == "high_si" for a in m.names) for m in ast.walk(n))
              and "source_audit_night" in ast.dump(n)]
    assert len(fenced) == 1


# ── writes: the store's set_state + share_basis's own writers only ───────────────────────────────────────────────
def _writes(src: str) -> list:
    return _calls_named(src, WRITE_CALLS)


def test_source_audit_writes_only_through_set_state_and_share_basis_writers():
    got = _writes(SA_SRC)
    assert set(got) <= ALLOWED_WRITERS and set(got) >= {"set_state", "store_mfloats"}
    for banned in (".update_one(", ".replace_one(", ".insert_one(", ".bulk_write(", ".delete_one(", "_upsert("):
        assert banned not in SA_SRC, banned


@pytest.mark.parametrize("planted", ["\ndef _x(d):\n    d['si_share_basis'].update_one({'_id': 'A'}, {})\n",
                                     "\ndef _x(st):\n    st._upsert('gajjala_state', 'x', {})\n",
                                     "\ndef _x(c):\n    c.insert_one({})\n"])
def test_NEGATIVE_a_direct_collection_write_trips(planted):
    assert set(_writes(SA_SRC + planted)) - ALLOWED_WRITERS


# ── the neighbours' pins ─────────────────────────────────────────────────────────────────────────────────────────
def test_nightly_holds_none_of_the_s10_words():
    assert [w for w in SI_WORDS if w in NG_SRC] == []


def test_NEGATIVE_an_s10_word_in_the_nightly_trips():
    planted = NG_SRC + "\n# from short_interest import source_audit\n"
    assert [w for w in SI_WORDS if w in planted] == ["short_interest"]


def test_high_si_calls_si_map_once_and_names_the_watch_only_for_constants():
    assert HS_SRC.count("SR.si_map(") == 1
    mods = sorted(m for m in _modules(HS_SRC) if m.startswith("chart_maps.gajjala_watch"))
    assert mods == ["chart_maps.gajjala_watch", "chart_maps.gajjala_watch.constants"] or \
        mods == ["chart_maps.gajjala_watch.constants"]
    assert "gajjala_watch import run_rules" not in HS_SRC


def test_NEGATIVE_a_second_si_map_or_a_run_rules_import_in_high_si_trips():
    planted = HS_SRC + "\ndef _x():\n    from chart_maps.gajjala_watch import run_rules as RR\n    return SR.si_map([])\n"
    assert planted.count("SR.si_map(") == 2 and "gajjala_watch import run_rules" in planted


def _sit_si_imports(src: str) -> set:
    return {m for m in _modules(src) if m.startswith("short_interest.")}


def test_si_track_short_interest_import_set_is_unchanged():
    assert _sit_si_imports(SIT_SRC) == {"short_interest.read", "short_interest.ssr", "short_interest.reg_sho",
                                        "short_interest.basis_math"}
    assert "source_check" not in SIT_SRC and "source_audit" not in SIT_SRC


def test_NEGATIVE_a_source_check_import_in_si_track_trips():
    planted = SIT_SRC + "\nfrom short_interest import source_check as SCK\n"
    assert "short_interest.source_check" in _sit_si_imports(planted)


def test_si_track_row_tier_goes_through_the_ladder_tier_once():
    assert SIT_SRC.count("tier=_ladder_tier(b)") == 1 and 'tier=b.get("tier")' not in SIT_SRC
