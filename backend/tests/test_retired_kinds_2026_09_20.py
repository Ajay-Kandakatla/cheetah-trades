"""The learning + volleyball kinds are RETIRED, and flashcards is DELETED
(Ajay 2026-09-20).

"Remove volleyball and learning of stocks I do dont wanna see them they are
spamming too much."

1,712 `minervini_flashcards` rows and ~215 `vb_*` rows sat in push_history —
the hourly flash card fired EVERY hour of EVERY day. Four things had to happen
together, and this file pins all four:

  * the four kinds leave `default_prefs()` (no toggle to leave half-on),
  * they enter `DISABLED_ALERT_KINDS` (the delivery chokepoint — a device whose
    stored pref is still True can't be reached),
  * they leave `PERSONAL_KINDS` (nothing left to classify),
  * the volleyball module exits 0 in SILENCE when its cron line survives in the
    host-mounted crontab (which a deploy does not ship).

Then, later the same day: **"Delete Flashcards please"**. `backend/flashcards/`
(the card bank, its router and the chart quiz) and the `/learn` +
`/chart-school` pages left the tree entirely, so the two module-guard tests
that used to import `flashcards.flashcards` / `flashcards.chart_quiz` are now
ABSENCE tests. Volleyball STAYS — retired and dark, but still importable and
still guarded, and it must not depend on the deleted module.

The labels deliberately STAY in `frontend/src/lib/alertKinds.ts` so the old
history rows keep rendering a name for the 90 days their TTL runs.
"""
from __future__ import annotations

import importlib.util
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


# ── NEGATIVE: the flashcards feature is GONE, not merely guarded ───────────
# Ajay 2026-09-20: "Delete Flashcards please". A guard is a promise; an absent
# module is a fact. These four replace the two module-guard tests that used to
# import `flashcards.flashcards` and `flashcards.chart_quiz`.
def test_the_flashcards_package_is_not_importable_at_all():
    assert importlib.util.find_spec("flashcards") is None, \
        "backend/flashcards/ is back in the tree — he asked for it deleted"
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("flashcards")


@pytest.mark.parametrize("mod", ["flashcards.flashcards", "flashcards.chart_quiz",
                                 "flashcards.api"])
def test_no_submodule_of_the_deleted_package_survives(mod):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_no_flashcards_source_file_is_left_on_disk():
    """A stray `.py` under backend/ that still defines the bank would be dead
    code the next grep resurrects."""
    skip = {".venv", "node_modules", "__pycache__"}
    strays = sorted(str(q.relative_to(ROOT)) for q in (ROOT / "backend").rglob("*.py")
                    if not (skip & set(q.parts))
                    and ("flashcards" in q.parts
                         or q.name in {"chart_quiz.py", "flashcards.py"}))
    assert strays == [], strays


def test_main_registers_no_flashcards_route_and_still_registers_volleyball():
    """`main.py` imports the whole app, which the test venv may not be able to
    do offline — so this reads the SOURCE, which is where the include lives."""
    src = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    assert "from flashcards import" not in src
    assert "flashcards_router" not in src
    assert "from volleyball import router as volleyball_router" in src, \
        "volleyball must keep working without flashcards"
    # and no module anywhere still declares a /flashcards path
    # `tests` is excluded: this file names the route to assert its absence.
    skip = {".venv", "node_modules", "__pycache__", "tests"}
    routes = [str(q.relative_to(ROOT)) for q in (ROOT / "backend").rglob("*.py")
              if not (skip & set(q.parts)) and '"/flashcards' in q.read_text(encoding="utf-8")]
    assert routes == [], routes


def test_the_deleted_pages_and_their_routes_are_gone_from_the_frontend():
    for gone in ("frontend/src/pages/Learn.tsx", "frontend/src/pages/ChartSchool.tsx"):
        assert not (ROOT / gone).exists(), gone
    app = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    for dead in ('path="/learn"', 'path="/chart-school"',
                 "pages/Learn'", "pages/ChartSchool'"):
        # `pages/LearningPath'` starts with `pages/Learn` — the trailing quote
        # is what separates the deleted page from the study plan that stays.
        assert dead not in app, dead
    # control: the study-plan page he did NOT ask to delete is still routed
    assert 'path="/learning"' in app
    assert (ROOT / "frontend/src/pages/LearningPath.tsx").exists()


def test_the_nav_catalog_no_longer_gates_a_page_that_does_not_exist():
    from access import store
    ids = {f["id"] for f in store.FEATURE_CATALOG}
    assert "chart-school" not in ids, \
        "chart-school gated /chart-school, which was the flashcards chart quiz"
    assert store.ALL_FEATURE_IDS == ids
    assert "chart-school" not in (store.DEFAULT_FEATURES | store.RESTRICTED_FEATURES)


def test_volleyball_does_not_import_anything_from_the_deleted_module():
    for q in sorted((ROOT / "backend/volleyball").rglob("*.py")):
        src = q.read_text(encoding="utf-8")
        assert "import flashcards" not in src, q.name
        assert "from flashcards" not in src, q.name


@pytest.mark.parametrize("cmd", ["morning", "education", "magnesium"])
def test_volleyball_main_exits_zero_for_every_command(no_send, capsys, cmd):
    from volleyball import reminders
    rc = reminders.main([cmd])
    assert isinstance(rc, int) and rc == 0, rc
    assert "retired 2026-09-20" in capsys.readouterr().out
    assert no_send["history"] == 0


def test_the_surviving_module_names_its_kinds_once_and_reads_them_from_there():
    """Was three modules; two of them were deleted 2026-09-20."""
    from volleyball import reminders
    assert reminders.KINDS == ("vb_workout", "vb_supplement", "vb_education")
    src = Path(reminders.__file__).read_text(encoding="utf-8")
    body = src.split("def main(", 1)[0]
    assert 'kind="vb_' not in body


def test_the_retired_flashcards_kind_still_has_exactly_one_home():
    """Nothing FIRES it any more, but `push.recent`'s serve-time filter keys on
    it to hide ~1,712 old rows — so the literal must live in the registry and
    nowhere else that could send."""
    assert "minervini_flashcards" in subs.RETIRED_2026_09_20
    recent = (ROOT / "backend/push/recent.py").read_text(encoding="utf-8")
    assert "RETIRED_2026_09_20" in recent


# ── POSITIVE CONTROL: the guard is what stops them, not a broken module ────
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


# ── the nav catalog ────────────────────────────────────────────────────────
def test_the_nav_catalog_dropped_learning_volleyball_and_chart_school():
    """`chart-school` left on 2026-09-20 with the flashcards DELETE — it gated
    /chart-school, whose only data source was GET /flashcards/chart-quiz."""
    from access import store
    ids = {f["id"] for f in store.FEATURE_CATALOG}
    for gone in ("learn", "learning", "volleyball", "chart-school"):
        assert gone not in ids, gone
    assert store.ALL_FEATURE_IDS == ids
    assert not ({"learn", "learning", "volleyball", "chart-school"}
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


def test_the_kept_flashcards_label_still_reads_as_a_name_not_a_raw_id():
    """NEGATIVE-adjacent: the feature is deleted, the LABEL is not. An old
    history row must still render "Flash card"."""
    kinds = (ROOT / "frontend/src/lib/alertKinds.ts").read_text(encoding="utf-8")
    assert "minervini_flashcards:" in kinds
    assert "'Flash card'" in kinds
    assert "feature deleted 2026-09-20" in kinds, \
        "the label needs the comment saying why it outlives the feature"


def test_no_frontend_source_still_routes_to_the_deleted_pages():
    """A dead `/learn` or `/chart-school` link is a 404 he would have to hit to
    find out. The serve-time filter in push/recent.py already hides every old
    flashcard row, so nothing renders their stored url either."""
    root = ROOT / "frontend/src"          # NOT scripts/: contracts.mjs names
                                          # these routes to assert their ABSENCE
    offenders = []
    for q in list(root.rglob("*.ts")) + list(root.rglob("*.tsx")):
        if ".test." in q.name:            # navSearch.test.ts builds a STALE menu
            continue                      # row on purpose, to prove it is inert
        src = q.read_text(encoding="utf-8")
        for dead in ("'/learn'", '"/learn"', "'/chart-school'", '"/chart-school"'):
            if dead in src:
                offenders.append(f"{q.relative_to(ROOT)}: {dead}")
    assert offenders == [], offenders
