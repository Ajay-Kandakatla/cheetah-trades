"""Locks owner auto-grant of new pages (access/store.effective_features).

Ajay 2026-06-03: "by default when I build pages, turn them on for me." Owners
with a customized (saved) nav auto-receive pages added to the catalog AFTER they
last saved — without re-granting pages they deliberately hid.
"""
from access import store


def test_owner_gets_new_page_added_after_baseline():
    saved = {"sepa", "portfolio"}                                   # no leaderboard
    eff = store.effective_features(saved, is_owner=True, seen_version=1)
    assert "leaderboard" in eff                                     # added_in 2 > seen 1
    assert {"sepa", "portfolio"} <= eff


def test_non_owner_does_not_auto_get_new_page():
    eff = store.effective_features({"sepa"}, is_owner=False, seen_version=1)
    assert "leaderboard" not in eff


def test_owner_who_has_seen_current_version_keeps_only_saved():
    eff = store.effective_features({"sepa"}, is_owner=True, seen_version=store.CATALOG_VERSION)
    assert "leaderboard" not in eff                                 # nothing newer than seen


def test_declutter_preserved_old_hidden_page_not_regranted():
    # An existing (added_in 1) page the owner hid must NOT come back — only
    # post-baseline additions auto-add.
    eff = store.effective_features({"sepa"}, is_owner=True, seen_version=1)
    assert "overnight" not in eff


def test_orphan_ids_dropped():
    eff = store.effective_features({"sepa", "not_a_real_feature"}, is_owner=False, seen_version=1)
    assert "not_a_real_feature" not in eff and "sepa" in eff


def test_leaderboard_is_tagged_and_version_bumped():
    entry = next(e for e in store.FEATURE_CATALOG if e["id"] == "leaderboard")
    assert entry.get("added_in") == 2
    assert store.CATALOG_VERSION >= 2
