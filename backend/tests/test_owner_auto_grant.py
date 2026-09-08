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


def test_breakouts_is_default_on_for_all_users():
    """Ajay 2026-06-23: the Breakouts page is the default landing for non-owners,
    so it must be granted to everyone by default (not owner-only). A default
    non-owner user (no saved nav) gets it."""
    entry = next(e for e in store.FEATURE_CATALOG if e["id"] == "breakouts")
    assert entry["default"] is True
    assert "breakouts" in store.DEFAULT_FEATURES
    # A non-owner default user (no customization) gets it.
    eff = store.effective_features(store.DEFAULT_FEATURES, is_owner=False,
                                   seen_version=store.CATALOG_VERSION)
    assert "breakouts" in eff


def test_sepa_global_is_default_on_for_all_users():
    """Ajay 2026-06-23: SEPA Global is the beginner scanner for everyone, so it
    must be granted by default (the full `sepa` page stays owner-only)."""
    entry = next(e for e in store.FEATURE_CATALOG if e["id"] == "sepa-global")
    assert entry["default"] is True
    assert "sepa-global" in store.DEFAULT_FEATURES
    # The full admin SEPA page is NOT broadly granted.
    sepa = next(e for e in store.FEATURE_CATALOG if e["id"] == "sepa")
    assert sepa["default"] is False
    eff = store.effective_features(store.DEFAULT_FEATURES, is_owner=False,
                                   seen_version=store.CATALOG_VERSION)
    assert "sepa-global" in eff and "sepa" not in eff


# ── Chart Maps lands for everyone (Ajay 2026-09-07) ──────────────────────────
def test_chart_maps_is_default_on_and_re_added_at_catalog_24():
    """Ajay 2026-09-07: "Make chart maps default loading page for me on the app
    load. Also for everyone." Default-on for new accounts AND re-added at v24 so
    a friend whose saved menu predates it gets the page without a manual grant."""
    entry = next(e for e in store.FEATURE_CATALOG if e["id"] == "chart-maps")
    assert entry["default"] is True and entry["added_in"] == 24 == store.CATALOG_VERSION
    assert "chart-maps" in store.DEFAULT_FEATURES
    # a friend with NO saved doc: the default set carries it
    assert "chart-maps" in store.effective_features(store.DEFAULT_FEATURES, is_owner=False,
                                                    seen_version=store.CATALOG_VERSION)
    # a friend who SAVED a menu at v23 without it: appears (default-on page added after)
    assert "chart-maps" in store.effective_features({"sepa-global", "food"}, is_owner=False, seen_version=23)
    # a friend who saved at v24 and left it out: stays hidden (their choice)
    assert "chart-maps" not in store.effective_features({"sepa-global"}, is_owner=False, seen_version=24)


def test_non_owners_do_not_inherit_owner_only_pages_added_after_they_saved():
    """NEGATIVE: the v24 rule grants DEFAULT-ON pages only — an owner-only page
    added after a friend's last save must still need an explicit grant."""
    owner_only = [e["id"] for e in store.FEATURE_CATALOG if not e["default"] and store._added_in(e) > 20]
    assert owner_only, "catalog has owner-only pages past v20"
    eff = store.effective_features({"sepa-global"}, is_owner=False, seen_version=20)
    assert not (set(owner_only) & eff)
    assert "chart-maps" in eff                                       # the default-on one does appear
