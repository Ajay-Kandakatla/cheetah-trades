"""`scripts.owner_prefs_apply` — the data write behind the 2026-09-20 keep-set.

The code change only decides what a NEWLY registered device starts with. His
three phones are already registered, so this script is what actually turns
🏛️ / 📣 / ✨ on and the retired learning + volleyball kinds off on them.

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
    """Three owner devices (one is the Mac app) + two other users'."""
    base = dict(subs.default_prefs())
    stale = {**base, "potus_investment": False, "minervini_flashcards": True,
             "vb_workout": True, "vb_supplement": True, "vb_education": True}
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
    assert S.off_kinds() == sorted(subs.RETIRED_2026_09_20)
    assert not set(S.on_kinds()) & set(S.off_kinds())


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
        assert row["changes"]["potus_investment"] == [False, True]
        assert row["changes"]["earnings_reaction"] == [None, True]
        assert row["changes"]["board_arrival"] == [None, True]
        assert row["changes"]["minervini_flashcards"] == [True, False]


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
        # the four already-True keep-set kinds are not rewritten
        assert "prefs.demand_alert" not in keys


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
    docs[0]["prefs"]["board_arrival"] = 1
    out = S.apply(docs, owner=OWNER, apply=False)
    assert out["rows"][0]["changes"]["board_arrival"] == [1, True]


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
    assert "potus_investment False→True" in out

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
