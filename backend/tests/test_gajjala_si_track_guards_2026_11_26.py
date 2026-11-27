"""🏁 SI track record (spec sitrack WP5) — the source-guard pins behind the five allowlists widened 2026-11-26 by the
main-session suite gate (S10 short-interest readers, the prior-tail readers, the Watch namers, the two 🔒 display-only
reader lists).

si_track.py joins those lists as a DISPLAY module: it reads short interest, the 🔒 / ⛔ payloads, the Watch's winner
and VWAP engines and the stored prior tail; nothing that ranks, gates, alerts or trades imports it. Each pin below has
a NEGATIVE that plants the forbidden shape and shows the matcher bites.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
GG_DIR = BACKEND / "chart_maps" / "gajjala"
SIT_REL = "chart_maps/gajjala/si_track.py"
SIT_SRC = (BACKEND / SIT_REL).read_text(encoding="utf-8")

# the only modules that may import si_track (display: the nightly's fenced step, the 🩳 block's fenced key, the backfill)
IMPORTERS = {"chart_maps/gajjala/nightly.py", "chart_maps/gajjala/high_si.py", "scripts/gajjala_si_track_backfill.py",
             # PIN MOVED 2026-11-26 (spec sishares §4.3, predicted): the 🏁 follow-up module and its backfill script —
             # display only; pinned below (no push / alert import, no Watch store import).
             "chart_maps/gajjala/si_follow.py", "scripts/gajjala_si_follow_backfill.py"}
SF_REL = "chart_maps/gajjala/si_follow.py"
SF_SRC = (BACKEND / SF_REL).read_text(encoding="utf-8")


def _imports(src: str) -> set:
    tree = ast.parse(src)
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            for a in n.names:
                out.add(f"{mod}.{a.name}" if mod else a.name)
                if n.level and a.name == "si_track":
                    out.add("chart_maps.gajjala.si_track")
        elif isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
    return out


def _names_si_track(src: str) -> bool:
    return any(m.endswith("si_track") and "si_track_" not in m for m in _imports(src))


def _importers(planted: dict | None = None) -> set:
    hits = set()
    for sub in ("chart_maps", "push", "trading", "supply_demand", "scripts", "short_interest", "portfolio"):
        root = BACKEND / sub
        if not root.exists():
            continue
        for f in root.rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            rel = f.relative_to(BACKEND).as_posix()
            if rel == SIT_REL:
                continue
            src = (planted or {}).get(rel) or f.read_text(encoding="utf-8", errors="ignore")
            if _names_si_track(src):
                hits.add(rel)
    return hits


def _calls_on(src: str, alias: str) -> list:
    return [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == alias]


# ── nobody that ranks, gates, alerts or trades imports it ────────────────────────────────────────────────────────
def test_only_the_nightly_the_high_si_block_and_the_backfill_import_si_track():
    assert _importers() == IMPORTERS


def test_NEGATIVE_an_alerts_or_trading_import_of_si_track_trips():
    planted = {"chart_maps/gajjala/alerts.py": (GG_DIR / "alerts.py").read_text(encoding="utf-8")
               + "\nfrom chart_maps.gajjala import si_track as SIT\n",
               "trading/gajjala_entry.py": (BACKEND / "trading" / "gajjala_entry.py").read_text(encoding="utf-8")
               + "\ndef _x():\n    from . import si_track\n"}
    hits = _importers(planted)
    assert "chart_maps/gajjala/alerts.py" in hits - IMPORTERS
    assert "trading/gajjala_entry.py" in hits - IMPORTERS


def test_the_two_app_importers_keep_it_fenced_and_lazy():
    for rel in ("chart_maps/gajjala/nightly.py", "chart_maps/gajjala/high_si.py"):
        tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert not [n for n in top if "si_track" in ast.dump(n)], rel                 # lazy only
        tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)
                 and any(isinstance(m, ast.ImportFrom) and any(a.name == "si_track" for a in m.names)
                         for m in ast.walk(n))]
        assert tries, rel                                                              # inside its own try


# ── short interest: the house read only ──────────────────────────────────────────────────────────────────────────
def test_si_track_reads_short_interest_only_through_read_ssr_reg_sho_and_basis_math():
    mods = {m for m in _imports(SIT_SRC) if m.startswith("short_interest")}
    assert mods == {"short_interest.read", "short_interest.ssr", "short_interest.reg_sho", "short_interest.basis_math"}
    tree = ast.parse(SIT_SRC)
    top = {m for n in tree.body if isinstance(n, ast.ImportFrom) and (n.module or "") == "short_interest"
           for m in (a.name for a in n.names)}
    assert top == {"read"}                                                             # the rest are lazy
    for banned in ("si_map(", "short_interest import client", "short_interest.client", "warm_si", "_fetch"):
        assert banned not in SIT_SRC, banned


def test_NEGATIVE_a_client_import_in_si_track_would_trip():
    planted = SIT_SRC + "\nfrom short_interest import client as CL\n"
    mods = {m for m in _imports(planted) if m.startswith("short_interest")}
    assert "short_interest.client" in mods - {"short_interest.read", "short_interest.ssr", "short_interest.reg_sho",
                                               "short_interest.basis_math"}


# ── 🔒 / ⛔: the stored payloads, never a kick ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("alias", ["RSH", "SSR"])
def test_si_track_reads_the_stored_reg_sho_and_ssr_payloads_only(alias):
    calls = _calls_on(SIT_SRC, alias)
    assert calls and {c.func.attr for c in calls} == {"payload"}
    for c in calls:
        kw = {k.arg: k.value for k in c.keywords}
        assert isinstance(kw.get("kick"), ast.Constant) and kw["kick"].value is False
    for banned in ("reg_sho" + "_runs", "kick_refresh", "backfill_history", "kick=True", "refresh(", "spawn", "_popen"):
        assert banned not in SIT_SRC, banned


def test_NEGATIVE_a_kicking_payload_read_in_si_track_would_trip():
    planted = SIT_SRC + "\ndef _x(now):\n    from short_interest import reg_sho as RSH\n    return RSH.payload(kick=True)\n"
    kicks = [c for c in _calls_on(planted, "RSH") if c.func.attr == "payload"
             and any(k.arg == "kick" and isinstance(k.value, ast.Constant) and k.value.value is True
                     for k in c.keywords)]
    assert kicks and "kick=True" in planted


# ── 👀 the Watch: constants, the winner engine and the VWAP engine only ──────────────────────────────────────────
def test_si_track_names_the_watch_only_for_constants_runners_and_vwap():
    from tests.test_gajjala_watch_hook_2026_11_15 import _watch_imports_and_wc_reads
    mods, reads = _watch_imports_and_wc_reads("si_track.py")
    assert mods == ["chart_maps.gajjala_watch.constants", "chart_maps.gajjala_watch.runners",
                    "chart_maps.gajjala_watch.vwap"]
    assert reads == ["BAR_AH", "BAR_PRE", "RAN_MIN_PCT"]
    for banned in ("gajjala_watch import colls", "gajjala_watch import loop", "gajjala_watch import build",
                   "gajjala_watch import payload", "gajjala_watch import store", "gajjala_watch.cross_alerts",
                   "spawn_child", "spawn_loop", "WCO."):
        assert banned not in SIT_SRC, banned


def test_NEGATIVE_a_watch_store_import_in_si_track_would_trip():
    planted = SIT_SRC + "\nfrom chart_maps.gajjala_watch import store as WST\n"
    mods = {m for m in _imports(planted) if m.startswith("chart_maps.gajjala_watch")}
    assert "chart_maps.gajjala_watch.store" in mods
    assert "gajjala_watch import store" in planted


# ── the prior tail: read for the prior close, never written to a stored tile ─────────────────────────────────────
def test_si_track_never_writes_a_prior_key_into_the_reads_store():
    for banned in ("gajjala_reads", "update_one(", "replace_one(", "insert_one(", "bulk_write("):
        hits = [ln for ln in SIT_SRC.split("\n") if banned in ln and "_prior" in ln]
        assert hits == [], banned


def test_NEGATIVE_a_planted_prior_write_would_trip():
    planted = SIT_SRC + '\ndef _x(c, d):\n    c.update_one({"_id": d}, {"$set": {"tile.bars5_prior": []}})\n'
    assert [ln for ln in planted.split("\n") if "update_one(" in ln and "_prior" in ln]


# ── 2026-11-26 (spec sishares §4.3): the 🏁 follow-up module — display only, like si_track ──────────────────────────
SF_BANNED_MODULES = ("push", "alerts", "high_si_cross", "trading", "notify", "twilio")


def _sf_banned(src: str) -> list:
    return sorted(m for m in _imports(src) if any(m == b or m.startswith(b + ".") or m.endswith("." + b)
                                                   or ("." + b + ".") in m for b in SF_BANNED_MODULES))


def test_si_follow_imports_no_push_alert_or_trading_module():
    assert _sf_banned(SF_SRC) == []
    tree = ast.parse(SF_SRC)
    top = sorted(m for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) for m in _imports(ast.unparse(n)))
    assert top == ["__future__.annotations", "chart_maps.gajjala.constants", "chart_maps.gajjala.si_track",
                   "datetime.date", "logging", "typing.Callable",
                   "typing.Optional"]


def test_NEGATIVE_an_alerts_or_push_import_in_si_follow_trips():
    for planted in ("\nfrom chart_maps.gajjala import alerts as AL\n", "\nfrom push import hooks\n",
                    "\ndef _x():\n    from chart_maps.gajjala import high_si_cross\n"):
        assert _sf_banned(SF_SRC + planted), planted


def test_si_follow_names_no_watch_store_and_writes_through_set_state_only():
    for banned in ("gajjala_watch", "update_one", "insert_one", "replace_one", "upsert_read", "send_", "kick"):
        assert banned not in SF_SRC, banned
    assert "st.set_state(" in SF_SRC and "ST.STATE" not in SF_SRC.replace("SIT.", "")
    assert "SIT.Budget(" in SF_SRC


def test_NEGATIVE_a_watch_store_import_in_si_follow_would_trip():
    planted = SF_SRC + "\nfrom chart_maps.gajjala_watch import store as WST\n"
    assert "gajjala_watch import store" in planted and "gajjala_watch" in planted
    assert "chart_maps.gajjala_watch.store" in _imports(planted)
