"""🥇 Luk's pass-health row on /alerts (luk-tab spec §3.12 / WP-D, 2026-11-01).

Ajay 2026-11-01: "pic the next best one like Gajjala … Implement their strategy".

`LUK_KIND = "luk_setup"` is Luk's pass-health row: Luk's pass records its own pass doc so /alerts can say it ran.
Its cadence is DERIVED from the 🚩 pass it rides (never typed).

INVERTED 2026-11-01 (Ajay 2026-11-01: "Lets make it live. also alerts too." — HIS CALL #19 answered): the same
string is now ALSO a LIVE push kind — push/hooks.notify_luk_setup, default_prefs False, the owner keep-set's
SEVENTH kind. Was: "never a push kind — no sender, no notify_* hook, no pref, the keep-set stays exactly six".

NEGATIVES: push/subs.py and push/hooks.py name only "luk_setup" (never a "luk_potential"); OWNER_KEEP_SET has
seven; "luk_setup" sits in the test_alert_status literal exactly once; the kind is not a daily pass; the conftest
kill switch is ASSIGNED "0".
"""
from __future__ import annotations

import ast
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import alert_status as AS   # noqa: E402

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 2, 9, 41, tzinfo=ET)


class FakeColl:
    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


# ── the kind ─────────────────────────────────────────────────────────────────
def test_the_kind_is_typed_exported_and_in_pass_kinds_right_after_the_audited_kind():
    assert AS.LUK_KIND == "luk_setup"
    assert "LUK_KIND" in AS.__all__
    assert AS.PASS_KINDS.count(AS.LUK_KIND) == 1
    i = AS.PASS_KINDS.index(AS.GAJJALA_AUDITED_KIND)
    assert AS.PASS_KINDS[i + 1] == AS.LUK_KIND


def test_the_kind_equals_the_luk_constant_when_that_module_exists():
    try:
        from chart_maps.luk import constants as LC
    except ImportError:
        return                                     # WP-A1 not merged in this tree yet — the string pin above holds
    assert LC.LUK_KIND == AS.LUK_KIND


def test_cadence_is_derived_from_the_gajjala_pass_never_typed():
    assert AS.CADENCE_SEC[AS.LUK_KIND] == AS.CADENCE_SEC[AS.GAJJALA_KIND]
    src = (BACKEND / "supply_demand" / "alert_status.py").read_text(encoding="utf-8")
    assert "CADENCE_SEC[LUK_KIND] = CADENCE_SEC[GAJJALA_KIND]" in src
    assert not re.search(r"CADENCE_SEC\[LUK_KIND\]\s*=\s*\d", src), "NEGATIVE: the Luk cadence is never a typed number"


def test_the_status_payload_carries_the_row_with_its_counts_and_cadence():
    pc, lc = FakeColl(), FakeColl()
    assert AS.record_pass(AS.LUK_KIND, {"n_read": 12, "aplus": 1, "shadow": 1, "pushed": 0}, NOW, coll=pc)
    p = AS.status_payload(pass_coll=pc, latest_coll=lc, now=NOW)
    row = p["passes"][AS.LUK_KIND]
    assert row["as_of"] == NOW.isoformat() and row["date"] == "2026-11-02"
    assert row["counts"] == {"n_read": 12, "aplus": 1, "shadow": 1, "pushed": 0}
    assert row["cadence_sec"] == AS.CADENCE_SEC[AS.GAJJALA_KIND]
    assert set(p["passes"]) == set(AS.PASS_KINDS)


def test_no_doc_yet_is_the_empty_shape_with_cadence():
    p = AS.status_payload(pass_coll=FakeColl(), latest_coll=FakeColl(), now=NOW)
    assert p["passes"][AS.LUK_KIND] == {"as_of": None, "date": None, "counts": {},
                                        "cadence_sec": AS.CADENCE_SEC[AS.LUK_KIND]}


# ── NEGATIVES ────────────────────────────────────────────────────────────────
def test_NEGATIVE_not_a_daily_pass_and_no_schedule_slot():
    assert AS.LUK_KIND not in AS.DAILY_PASS_KINDS
    assert AS.LUK_KIND not in AS.schedule_map()


def test_push_subs_and_hooks_name_luk_setup_and_no_other_luk_kind():
    # INVERTED 2026-11-01 (Ajay: "Lets make it live. also alerts too."): subs/hooks now DO name luk — the one kind.
    for rel in ("push/subs.py", "push/hooks.py"):
        src = (BACKEND / rel).read_text(encoding="utf-8")
        assert src, rel
        assert '"luk_setup"' in src, rel
        assert not re.search("luk_potential", src, re.I), rel                # NEGATIVE: no Luk potential kind
    from push import hooks
    assert [n for n in dir(hooks) if "luk" in n.lower()] == ["notify_luk_setup"]
    assert callable(hooks.notify_luk_setup)


def test_the_owner_keep_set_is_seven_with_luk_setup_and_default_prefs_off():
    # INVERTED 2026-11-01 (Ajay: "Lets make it live. also alerts too."): was "still exactly six and has no luk kind".
    from push import subs
    assert len(subs.OWNER_KEEP_SET) == 7
    assert AS.LUK_KIND in subs.OWNER_KEEP_SET
    assert subs.default_prefs()[AS.LUK_KIND] is False                        # NEGATIVE: never ON for anyone else
    assert [k for k in subs.OWNER_KEEP_SET if "luk" in k.lower()] == [AS.LUK_KIND]


def test_NEGATIVE_luk_setup_sits_in_the_pass_kind_literal_exactly_once():
    """The hard-coded set in test_alert_status (WIDENED 2026-11-01) names the kind once; the PASS_KINDS pin holds."""
    tree = ast.parse((BACKEND / "tests" / "test_alert_status.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "test_status_payload_contract_shape_gate_numbers_and_in_session_at_request_time")
    sets = [n for n in ast.walk(fn) if isinstance(n, ast.Set)
            and any(isinstance(e, ast.Constant) and e.value == "zone_edge" for e in n.elts)]
    assert len(sets) == 1
    names = [e.value for e in sets[0].elts if isinstance(e, ast.Constant)]
    assert names.count("luk_setup") == 1
    assert set(names) == set(AS.PASS_KINDS)


def test_NEGATIVE_conftest_assigns_the_kill_switch_off_never_setdefault():
    assert os.environ.get("LUK_ENABLED") == "0"
    src = (BACKEND / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert 'os.environ["LUK_ENABLED"] = "0"' in src
    assert not re.search(r"setdefault\(\s*[\"']LUK_ENABLED", src)
    assert '"LUK_ENABLED"' in src.split("prior = ", 1)[1].split("\n", 1)[0], "restored on teardown with the others"
