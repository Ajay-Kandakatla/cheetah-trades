"""The learning + volleyball kinds are RETIRED (Ajay 2026-09-20).

"Remove volleyball and learning of stocks I do dont wanna see them they are
spamming too much."

1,712 `minervini_flashcards` rows and ~215 `vb_*` rows sat in push_history —
the hourly flash card fired EVERY hour of EVERY day. Four things had to happen
together, and this file pins all four:

  * the four kinds leave `default_prefs()` (no toggle to leave half-on),
  * they enter `DISABLED_ALERT_KINDS` (the delivery chokepoint — a device whose
    stored pref is still True can't be reached),
  * they leave `PERSONAL_KINDS` (nothing left to classify),
  * the three modules exit 0 in SILENCE when their cron line survives in the
    host-mounted crontab (which a deploy does not ship).

The labels deliberately STAY in `frontend/src/lib/alertKinds.ts` so the old
history rows keep rendering a name for the 90 days their TTL runs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from push import subs

ROOT = Path(__file__).resolve().parents[2]
RETIRED = ("minervini_flashcards", "vb_workout", "vb_supplement", "vb_education")


# ── the registry ───────────────────────────────────────────────────────────
def test_the_retired_set_is_exactly_the_four_he_named():
    assert subs.RETIRED_2026_09_20 == frozenset(RETIRED)


def test_the_four_are_gone_from_default_prefs_and_stopped_at_the_chokepoint():
    d = subs.default_prefs()
    for k in RETIRED:
        assert k not in d, f"{k} still has a default pref — the toggle survives"
        assert k in subs.DISABLED_ALERT_KINDS, k


def test_the_four_are_no_longer_classified_as_personal_kinds():
    from market_hours import gate
    for k in RETIRED:
        assert k not in gate.PERSONAL_KINDS, k
        assert k not in gate.MARKET_ALERT_KINDS, f"{k} must not move sets, it must go"


def test_delivery_short_circuits_before_mongo_for_every_retired_kind(monkeypatch):
    """Same shape as test_alert_kill_switch: an empty target list is returned
    WITHOUT opening a database, so a stored `True` cannot resurrect the kind."""
    def boom():
        raise AssertionError("_get_db must not be reached for a retired kind")
    monkeypatch.setattr(subs, "_get_db", boom)
    for k in RETIRED:
        assert subs.list_subscriptions(filter_kind=k) == [], k
        assert subs.list_mac_device_ids("a@b.com", filter_kind=k) == set(), k


# ── NEGATIVE: the crontab ──────────────────────────────────────────────────
def test_no_live_crontab_line_still_runs_a_retired_module():
    """The crontab is bind-mounted from the MAIN tree — a deploy does not ship
    it. If a line survives, the module guard below makes it silent; this test
    is the belt to that suspenders."""
    lines = (ROOT / "backend/crontab").read_text(encoding="utf-8").splitlines()
    live = [l for l in lines if l.strip() and not l.lstrip().startswith("#")]
    offenders = [l for l in live if "flashcards" in l or "volleyball" in l]
    assert offenders == [], offenders


# ── NEGATIVE: the module guards ────────────────────────────────────────────
@pytest.fixture()
def no_send(monkeypatch):
    """Every send path raises and every history write counts — so a guarded
    run proves itself by NOT tripping either."""
    from push import sender, history
    from sepa import notify
    calls = {"history": 0}

    def boom(*a, **k):
        raise AssertionError("a retired kind must never reach the sender")

    monkeypatch.setattr(sender, "send_to_all", boom)
    monkeypatch.setattr(sender, "send_to_user", boom)
    monkeypatch.setattr(notify, "send_alert", boom)
    monkeypatch.setattr(history, "record",
                        lambda *a, **k: calls.__setitem__("history", calls["history"] + 1))
    return calls


def test_flashcards_main_exits_zero_and_sends_nothing(no_send, capsys):
    from flashcards import flashcards
    rc = flashcards.main(["hourly"])
    assert isinstance(rc, int) and rc == 0, rc
    assert "retired 2026-09-20" in capsys.readouterr().out
    assert no_send["history"] == 0


def test_chart_quiz_main_exits_zero_even_though_an_empty_quiz_would_exit_one(no_send, capsys):
    """`fire_daily()` returns {"ok": False} with no items and the old __main__
    turned that into exit 1. The guard PRECEDES it: nothing ran, so nothing
    failed, and cron logs stay clean."""
    from flashcards import chart_quiz
    rc = chart_quiz.main([])
    assert isinstance(rc, int) and rc == 0, rc
    assert "retired 2026-09-20" in capsys.readouterr().out
    assert no_send["history"] == 0


@pytest.mark.parametrize("cmd", ["morning", "education", "magnesium"])
def test_volleyball_main_exits_zero_for_every_command(no_send, capsys, cmd):
    from volleyball import reminders
    rc = reminders.main([cmd])
    assert isinstance(rc, int) and rc == 0, rc
    assert "retired 2026-09-20" in capsys.readouterr().out
    assert no_send["history"] == 0


def test_the_three_modules_name_their_kind_once_and_read_it_from_there():
    from flashcards import flashcards, chart_quiz
    from volleyball import reminders
    assert flashcards.KIND == "minervini_flashcards"
    assert chart_quiz.KIND == "minervini_flashcards"
    assert reminders.KINDS == ("vb_workout", "vb_supplement", "vb_education")
    for mod in (flashcards, chart_quiz, reminders):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        body = src.split("def main(", 1)[0]
        assert 'kind="minervini_flashcards"' not in body, mod.__name__
        assert 'kind="vb_' not in body, mod.__name__


# ── POSITIVE CONTROL: the guard is what stops them, not a broken module ────
def test_lifting_the_kill_switch_lets_the_send_path_run_again(monkeypatch):
    """If the modules were merely broken, the tests above would pass for the
    wrong reason. Remove the kind from DISABLED_ALERT_KINDS and the dispatch
    IS reached."""
    from flashcards import flashcards
    monkeypatch.setattr(subs, "DISABLED_ALERT_KINDS",
                        frozenset(k for k in subs.DISABLED_ALERT_KINDS
                                  if k != "minervini_flashcards"))
    seen = []
    from push import sender
    monkeypatch.setattr(sender, "send_to_all",
                        lambda payload, kind=None: (seen.append((kind, payload)),
                                                    {"sent": 1, "failed": 0})[1])
    rc = flashcards.main(["morning"])
    assert rc == 0
    assert seen and seen[0][0] == "minervini_flashcards"


def test_lifting_the_kill_switch_lets_volleyball_dispatch_again(monkeypatch):
    from volleyball import reminders
    monkeypatch.setattr(subs, "DISABLED_ALERT_KINDS",
                        frozenset(k for k in subs.DISABLED_ALERT_KINDS
                                  if not k.startswith("vb_")))
    seen = []
    monkeypatch.setattr(reminders, "fire_magnesium",
                        lambda: (seen.append("magnesium"), {"ok": True})[1])
    assert reminders.main(["magnesium"]) == 0
    assert seen == ["magnesium"]
    # an unknown command is still a usage error, not a silent success
    assert reminders.main(["nonsense"]) == 2


def test_lifting_the_kill_switch_lets_chart_quiz_dispatch_again(monkeypatch):
    from flashcards import chart_quiz
    monkeypatch.setattr(subs, "DISABLED_ALERT_KINDS",
                        frozenset(k for k in subs.DISABLED_ALERT_KINDS
                                  if k != "minervini_flashcards"))
    monkeypatch.setattr(chart_quiz, "fire_daily", lambda: {"ok": False, "n": 0})
    assert chart_quiz.main([]) == 1, "an empty quiz is exit 1 when the kind is live"


# ── the nav catalog ────────────────────────────────────────────────────────
def test_the_nav_catalog_dropped_learning_and_volleyball_but_kept_chart_school():
    from access import store
    ids = {f["id"] for f in store.FEATURE_CATALOG}
    for gone in ("learn", "learning", "volleyball"):
        assert gone not in ids, gone
    assert "chart-school" in ids, "the chart-reading quiz is not the flash-card feed"
    assert store.ALL_FEATURE_IDS == ids
    assert not ({"learn", "learning", "volleyball"}
                & (store.DEFAULT_FEATURES | store.RESTRICTED_FEATURES))


def test_the_menu_builder_no_longer_special_cases_learning():
    import inspect
    from access import store
    src = inspect.getsource(store.build_menu)
    assert 'fid == "learning"' not in src


# ── the frontend keeps the labels (history rows must still read) ───────────
def test_the_frontend_still_labels_the_retired_kinds_for_old_history_rows():
    kinds = (ROOT / "frontend/src/lib/alertKinds.ts").read_text(encoding="utf-8")
    for k in RETIRED:
        assert f"{k}:" in kinds, f"{k} lost its label — old rows would show a raw id"
    prefs = (ROOT / "frontend/src/hooks/useNotificationPrefs.ts").read_text(encoding="utf-8")
    page = (ROOT / "frontend/src/pages/Notifications.tsx").read_text(encoding="utf-8")
    for k in RETIRED:
        assert f"{k}?:" not in prefs, f"{k} still has a pref type"
        assert f"key: '{k}'" not in page, f"{k} still has a toggle"
