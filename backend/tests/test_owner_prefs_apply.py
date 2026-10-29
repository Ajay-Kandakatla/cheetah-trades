"""`scripts.owner_prefs_apply` — the data write behind the owner keep-set.

The code change only decides what a NEWLY registered device starts with. His
phones are already registered, so this script is what actually flips them.
2026-10-29 (Ajay: "Only give me Gajjalas chart notifications from both tabs, /
I am missing out the ones in noise."): it applies `subs.owner_prefs()` IN FULL —
ON = the six-kind keep-set, OFF = every other bool kind of default_prefs()
(never the quiet-hours settings) + the retired set. Both lists are derived,
never retyped.

It is a write against his live devices, so the tests below are mostly
NEGATIVE: dry by default, owner-scoped, idempotent, and refusing outright when
the environment and `growth.alerts.OWNER` disagree.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from push import subs
from scripts import owner_prefs_apply as S

OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"


class FakeColl:
    def __init__(self, docs):
        self.docs = docs
        self.updates = []

    def find(self, _q=None):
        return list(self.docs)

    def update_one(self, flt, upd):
        self.updates.append((flt, upd))
        for d in self.docs:
            if d["_id"] == flt["_id"]:
                for k, v in upd["$set"].items():
                    if k.startswith("prefs."):
                        d.setdefault("prefs", {})[k.split(".", 1)[1]] = v
                    else:
                        d[k] = v


def _docs():
    """Three owner devices (one is the Mac app) + two other users'. The owner's
    stored prefs are the 2026-10-28 shape: tape bursts + the 5-minute Gajjala
    kinds ON, the 1-minute kinds OFF (shadow), two kinds absent, the retired
    learning + volleyball kinds still True."""
    base = dict(subs.default_prefs())
    stale = {**base, "tape_burst_highbeta": True, "tape_burst_chartmaps": True, "tape_control": True,
             "gajjala_setup": True, "gajjala_potential": True, "gajjala_1m_setup": False,
             "gajjala_1m_potential": False, "quiet_hours_enabled": True,
             "minervini_flashcards": True, "vb_workout": True, "vb_supplement": True, "vb_education": True}
    stale.pop("earnings_reaction", None)
    stale.pop("board_arrival", None)
    return [
        {"_id": 1, "user_email": OWNER, "label": "iPhone", "kind": "web",
         "endpoint": "https://push.example/aaa", "prefs": dict(stale)},
        {"_id": 2, "user_email": OWNER.upper(), "label": "iPad", "kind": "web",
         "endpoint": "https://push.example/bbb", "prefs": dict(stale)},
        {"_id": 3, "user_email": OWNER, "label": "Mac", "kind": "mac",
         "endpoint": "mac:device-3", "prefs": dict(stale)},
        {"_id": 4, "user_email": OTHER, "label": "friend", "kind": "web",
         "endpoint": "https://push.example/ccc", "prefs": dict(base)},
        {"_id": 5, "user_email": OTHER, "label": "friend2", "kind": "web",
         "endpoint": "https://push.example/ddd", "prefs": dict(base)},
    ]


# ── the lists are the constants themselves ─────────────────────────────────
def test_the_on_and_off_lists_are_never_retyped():
    assert S.on_kinds() == sorted(subs.OWNER_KEEP_SET)
    d = subs.default_prefs()
    want_off = {k for k, v in d.items() if isinstance(v, bool) and k not in subs.OWNER_KEEP_SET
                and not k.startswith("quiet_hours")} | set(subs.RETIRED_2026_09_20)
    assert S.off_kinds() == sorted(want_off)
    assert not set(S.on_kinds()) & set(S.off_kinds())


def test_on_plus_off_is_owner_prefs_in_full():
    """Every bool kind of owner_prefs() is covered: True ones are ON, False ones are OFF (2026-10-29)."""
    op = subs.owner_prefs()
    for k, v in op.items():
        if not isinstance(v, bool) or k.startswith("quiet_hours"):
            continue
        assert (k in S.on_kinds()) is v and (k in S.off_kinds()) is (not v), k


def test_NEGATIVE_a_keep_set_kind_never_appears_in_off_kinds():
    for k in subs.OWNER_KEEP_SET:
        assert k not in S.off_kinds(), k


def test_NEGATIVE_no_quiet_hours_setting_is_ever_flipped():
    assert [k for k in S.off_kinds() + S.on_kinds() if k.startswith("quiet_hours")] == []
    assert "quiet_hours_enabled" in subs.default_prefs()          # the setting exists — it is skipped, not absent


def test_the_retired_set_is_still_turned_off():
    assert set(subs.RETIRED_2026_09_20) <= set(S.off_kinds())
    for k in ("tape_burst_highbeta", "tape_burst_chartmaps", "pattern_alert", "hot_pullback_alert", "demand_alert"):
        assert k in S.off_kinds(), k


def test_NEGATIVE_the_script_carries_no_kind_name_outside_its_docstring():
    """The lists are derived — no kind of default_prefs / the keep-set / the retired set is typed in the code."""
    import ast
    src = Path(S.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    kinds = set(subs.default_prefs()) | set(subs.OWNER_KEEP_SET) | set(subs.RETIRED_2026_09_20)
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value != doc}
    assert not (literals & kinds), sorted(literals & kinds)


# ── dry run ────────────────────────────────────────────────────────────────
def test_dry_run_changes_nothing_but_reports_every_device():
    coll = FakeColl(_docs())
    before = [dict(d["prefs"]) for d in coll.docs]
    out = S.apply(coll.find(), owner=OWNER, apply=False, coll=coll)
    assert out["devices"] == 3 and out["untouched"] == 2
    assert out["changed"] == 3 and out["applied"] is False
    assert coll.updates == [], "a dry run must not write"
    assert [dict(d["prefs"]) for d in coll.docs] == before
    # the Mac device is one of the three, not skipped for being a mac row
    assert {r["kind"] for r in out["rows"]} == {"web", "mac"}
    for row in out["rows"]:
        assert row["changes"]["tape_burst_highbeta"] == [True, False]
        assert row["changes"]["tape_burst_chartmaps"] == [True, False]
        assert row["changes"]["gajjala_1m_setup"] == [False, True]
        assert row["changes"]["gajjala_1m_potential"] == [False, True]
        assert row["changes"]["earnings_reaction"] == [None, False]
        assert row["changes"]["minervini_flashcards"] == [True, False]
        # NEGATIVE: an already-right kind and the quiet-hours setting are not in the diff
        assert "gajjala_setup" not in row["changes"] and "position_alert" not in row["changes"]
        assert not [k for k in row["changes"] if k.startswith("quiet_hours")]


# ── apply ──────────────────────────────────────────────────────────────────
def test_apply_flips_exactly_the_two_lists_on_owner_devices_only():
    coll = FakeColl(_docs())
    others_before = [dict(d) for d in coll.docs if d["user_email"] == OTHER]
    out = S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    assert out["applied"] is True and out["changed"] == 3
    assert len(coll.updates) == 3
    for d in coll.docs:
        if d["user_email"].lower() != OWNER:
            continue
        for k in S.on_kinds():
            assert d["prefs"][k] is True, k
        for k in S.off_kinds():
            assert d["prefs"][k] is False, k
        # 2026-10-29: the stored bool kinds now equal owner_prefs() — the tape bursts are OFF on his device
        op = subs.owner_prefs()
        for k, v in op.items():
            if isinstance(v, bool) and not k.startswith("quiet_hours"):
                assert d["prefs"][k] is v, k
        assert d["prefs"]["tape_burst_highbeta"] is False and d["prefs"]["tape_burst_chartmaps"] is False
        assert d["prefs"]["quiet_hours_enabled"] is True, "NEGATIVE: his quiet-hours setting is never touched"
        assert isinstance(d["updated_at"], int)
    # NEGATIVE: the other users' documents are byte-identical
    assert [dict(d) for d in coll.docs if d["user_email"] == OTHER] == others_before


def test_apply_touches_only_the_changed_keys_never_the_whole_prefs_dict():
    coll = FakeColl(_docs())
    S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    for _flt, upd in coll.updates:
        keys = set(upd["$set"]) - {"updated_at"}
        assert keys <= {f"prefs.{k}" for k in S.on_kinds() + S.off_kinds()}
        assert "prefs" not in upd["$set"], "never overwrite the whole dict"
        # the already-True keep-set kinds are not rewritten; the quiet-hours settings never
        assert "prefs.position_alert" not in keys and "prefs.gajjala_setup" not in keys
        assert not [k for k in keys if k.startswith("prefs.quiet_hours")]


def test_a_second_apply_is_a_no_op():
    coll = FakeColl(_docs())
    S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    coll.updates.clear()
    out = S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    assert out["changed"] == 0 and coll.updates == []
    assert all(r["changes"] == {} for r in out["rows"])


# ── NEGATIVES ──────────────────────────────────────────────────────────────
def test_a_tree_with_no_owner_device_writes_nothing():
    coll = FakeColl([d for d in _docs() if d["user_email"] == OTHER])
    out = S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    assert out == {"devices": 0, "changed": 0, "applied": True,
                   "untouched": 2, "rows": []}
    assert coll.updates == []


def test_a_truthy_non_boolean_pref_still_counts_as_a_change():
    """`1 == True` but `1 is not True` — a legacy integer must be rewritten to
    a real boolean, or `list_subscriptions` filtering can drift."""
    docs = _docs()[:1]
    docs[0]["prefs"]["gajjala_setup"] = 1
    docs[0]["prefs"]["pattern_alert"] = 0
    out = S.apply(docs, owner=OWNER, apply=False)
    assert out["rows"][0]["changes"]["gajjala_setup"] == [1, True]
    assert out["rows"][0]["changes"]["pattern_alert"] == [0, False]


def test_main_refuses_before_reading_a_device_when_the_env_disagrees(monkeypatch, capsys):
    monkeypatch.setenv("OWNER_EMAIL", OTHER)
    monkeypatch.delenv("DEFAULT_USER_EMAIL", raising=False)

    def boom():
        raise AssertionError("no device may be read when the owner does not match")
    monkeypatch.setattr(subs, "_get_db", boom)
    assert S.main([]) == 2
    err = capsys.readouterr().err
    assert "REFUSING" in err
    # masked to the local part — no full address in the container log
    assert chr(64) not in err


def test_main_refuses_when_mongo_is_unavailable(monkeypatch, capsys):
    from growth.alerts import OWNER as REAL_OWNER
    monkeypatch.setenv("OWNER_EMAIL", REAL_OWNER)
    monkeypatch.setattr(subs, "_get_db", lambda: None)
    assert S.main([]) == 2
    assert "REFUSING" in capsys.readouterr().err


def test_main_is_dry_by_default_and_writes_only_with_apply(monkeypatch, capsys):
    from growth.alerts import OWNER as REAL_OWNER
    monkeypatch.setenv("OWNER_EMAIL", REAL_OWNER)
    docs = _docs()
    for d in docs:
        if d["user_email"].lower() != OTHER:
            d["user_email"] = REAL_OWNER

    class FakeDb:
        def __init__(self, coll):
            self.push_subscriptions = coll
    coll = FakeColl(docs)
    monkeypatch.setattr(subs, "_get_db", lambda: FakeDb(coll))

    assert S.main([]) == 0
    out = capsys.readouterr().out
    assert coll.updates == [], "default run must be dry"
    assert "applied no" in out and "dry run" in out
    assert "untouched (not the owner): 2" in out
    assert "tape_burst_highbeta True→False" in out and "gajjala_1m_setup False→True" in out

    assert S.main(["--apply"]) == 0
    assert len(coll.updates) == 3
    assert "applied yes" in capsys.readouterr().out


def test_the_script_never_carries_the_address_as_a_literal():
    from growth import alerts
    src = Path(S.__file__).read_text(encoding="utf-8")
    assert alerts.OWNER not in src
    assert chr(64) not in src, "no @ literal — the address is imported, never typed"


@pytest.mark.parametrize("flag", ["--json"])
def test_json_output_is_machine_readable(monkeypatch, capsys, flag):
    import json
    from growth.alerts import OWNER as REAL_OWNER
    monkeypatch.setenv("OWNER_EMAIL", REAL_OWNER)
    docs = [d for d in _docs() if d["user_email"] == OTHER]
    docs.append({"_id": 9, "user_email": REAL_OWNER, "label": "iPhone",
                 "kind": "web", "endpoint": "https://push.example/zzz",
                 "prefs": {}})

    class FakeDb:
        def __init__(self, coll):
            self.push_subscriptions = coll
    coll = FakeColl(docs)
    monkeypatch.setattr(subs, "_get_db", lambda: FakeDb(coll))
    assert S.main([flag]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["devices"] == 1 and payload["untouched"] == 2
    assert payload["applied"] is False
