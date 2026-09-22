"""🔥 Hottest — the sort he picked is REMEMBERED (Ajay 2026-09-21).

    "Can you add a server side sort to this so its persistent"

The sort was already a server round trip (it has to be: the payload truncates
to `names_per_group` rows per group, so a browser-side sort would only ever
reorder the visible 25). What the board did not have was MEMORY — the
component opened on `useState('rel_5d')` every time, so the column he picked
lasted until the next reload and never followed him from the desktop to the
phone.

What these tests pin, in order of how expensive the bug would be:

  1. A BOARD READ NEVER BREAKS. Anonymous, no Mongo, garbage in the stored
     document, a Query object leaking out of a direct call — every one of them
     lands on `H.DEFAULT_SORT` with a 200, byte-identical to how this endpoint
     behaved before any preference existed. `auth.current_user_email` RAISES
     401 in an HTTP context with no session; a preference lookup must never
     drag that onto a board that has always answered without one.
  2. THE READ NEVER WRITES. `GET /rotation/hottest` demotes `sort=pre_1d` to
     the default leg when the pre-market column has nothing in it. Writing
     back what it SERVED would silently overwrite his chosen column with
     `rel_5d` the first time he opened the board after 9:30.
  3. ONE OWNER PER FACT. The column vocabulary lives in `rotation.hottest`
     and is validated in `rotation.api`; `users.store` keeps already-validated
     strings and must never import the board.

No Mongo. `users.store._get_db` is monkeypatched with an in-memory stand-in
that implements the two operations the store actually uses — including dotted
`$set` — so these exercise the real store code rather than a mock of it.

    cd backend && .venv/bin/python -m pytest \
        tests/test_hottest_sort_persist_2026_09_21.py -q
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import api as A            # noqa: E402
from rotation import hottest as H        # noqa: E402
from users import store as user_store    # noqa: E402

EMAIL = "ajaykandakatla@gmail.com"


# ── in-memory `users` collection ─────────────────────────────────────────────
class _Users:
    """Only `find_one` (inclusion projection) and `update_one` with upsert,
    `$set` (DOTTED paths included) and `$setOnInsert` — the exact surface
    `users.store` uses. The dotted `$set` is modelled faithfully because the
    whole point of writing `board_sorts.hottest` rather than `board_sorts` is
    that it leaves sibling keys standing."""

    def __init__(self):
        self.docs: dict = {}
        self.writes = 0

    def find_one(self, q, proj=None):
        d = self.docs.get((q or {}).get("email"))
        if d is None:
            return None
        if not proj:
            return json.loads(json.dumps(d))
        return {k: json.loads(json.dumps(v)) for k, v in d.items() if k in proj}

    def update_one(self, q, upd, upsert=False):
        self.writes += 1
        email = (q or {}).get("email")
        doc = self.docs.get(email)
        if doc is None:
            if not upsert:
                return
            doc = dict((upd.get("$setOnInsert") or {}))
            self.docs[email] = doc
        for path, value in (upd.get("$set") or {}).items():
            cur, parts = doc, path.split(".")
            for p in parts[:-1]:
                nxt = cur.get(p)
                if not isinstance(nxt, dict):
                    nxt = {}
                    cur[p] = nxt
                cur = nxt
            cur[parts[-1]] = value


class _DB:
    def __init__(self):
        self.users = _Users()


@pytest.fixture
def db(monkeypatch):
    d = _DB()
    monkeypatch.setattr(user_store, "_get_db", lambda: d)
    return d


@pytest.fixture
def no_db(monkeypatch):
    """Mongo down — the store's other documented path."""
    monkeypatch.setattr(user_store, "_get_db", lambda: None)


# ── a request that carries an identity, or does not ──────────────────────────
class _Req:
    """What `auth.maybe_current_user` reads off a Request: the header first,
    the local-auth cookie second. A bare `_Req()` is an ANONYMOUS HTTP
    request — the case that 401s through `current_user_email`."""

    def __init__(self, email=None, cookies=None):
        self.headers = {"X-User-Email": email} if email else {}
        self.cookies = cookies or {}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(resp):
    return json.loads(resp.body)


@pytest.fixture
def board(monkeypatch):
    """The endpoint with its two Mongo reads and the build stubbed out.

    `build_live` is replaced by a fake that RECORDS the sort it was handed and
    mimics the one behaviour these tests care about: the live demotion of
    `pre_1d` when the pre-market leg has nothing in it.
    `test_the_fake_build_mirrors_the_real_demotion` holds that fake honest
    against the real builder.
    """
    seen: dict = {}
    monkeypatch.setattr(A, "_members_table",
                        lambda: ({"by_symbol": {}, "benchmark": {}}, {}))
    monkeypatch.setattr(A, "_members_payload", lambda: {"as_of": "2026-09-21"})

    def _fake(payload, **kw):
        seen.clear()
        seen.update(kw)
        served = kw.get("sort")
        if served == H.PRE_SORT:              # the live demotion, mirrored
            served = H.DEFAULT_SORT
        return {"sectors": [], "sorted_by": served, "sorted_dir": kw.get("direction")}

    monkeypatch.setattr(A.H, "build_live", _fake)
    return seen


def _seed(db, sort, dir_):
    """A stored preference, written the way the store writes one."""
    user_store.set_board_sort(EMAIL, A.HOTTEST_BOARD, sort, dir_)
    assert db.users.docs[EMAIL]["board_sorts"]["hottest"] == {"sort": sort, "dir": dir_}


# ===========================================================================
# 1 — the three sources, in precedence order
# ===========================================================================
def test_a_saved_preference_opens_the_board(db, board):
    """The whole ask. He picked rel_21d/asc yesterday; today's first load —
    which sends neither param — opens on rel_21d/asc, not on rel_5d/desc."""
    _seed(db, "rel_21d", "asc")
    resp = _run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                   names=25, basis="close"))
    assert resp.status_code == 200
    body = _body(resp)
    assert (body["sort_source"], body["dir_source"]) == ("saved", "saved")
    assert (body["sorted_by"], body["sorted_dir"]) == ("rel_21d", "asc")
    # and it reached the BUILDER — `sorted_by` echoing is not the same as the
    # board actually being ranked on his column
    assert (board["sort"], board["direction"]) == ("rel_21d", "asc")


def test_an_explicit_param_beats_the_saved_preference(db, board):
    """Clicking a column has to win over what is on file, or the board would
    be unusable for anyone whose preference is already set."""
    _seed(db, "rel_21d", "asc")
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="sales_yoy",
                                         dir="desc", names=25, basis="close")))
    assert (body["sort_source"], body["dir_source"]) == ("request", "request")
    assert (body["sorted_by"], body["sorted_dir"]) == ("sales_yoy", "desc")
    assert board["sort"] == "sales_yoy"


def test_no_preference_and_no_param_is_the_board_default(db, board):
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    assert (body["sort_source"], body["dir_source"]) == ("default", "default")
    assert (body["sorted_by"], body["sorted_dir"]) == (H.DEFAULT_SORT, H.DEFAULT_DIR)
    assert db.users.writes == 0, "a board READ must never write"


def test_each_leg_resolves_on_its_own(db, board):
    """He sends a column with no direction (or the reverse). The leg that was
    supplied is honoured and the other still falls back through the same
    ladder, which is why the sources are reported per leg."""
    _seed(db, "rel_21d", "asc")
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="net_margin",
                                         dir="", names=25, basis="close")))
    assert (body["sorted_by"], body["sorted_dir"]) == ("net_margin", "asc")
    assert (body["sort_source"], body["dir_source"]) == ("request", "saved")


def test_an_explicit_pair_skips_the_preference_read_entirely(db, board):
    """Every sorted click would otherwise pay a Mongo round trip for an answer
    it is about to discard."""
    _seed(db, "rel_21d", "asc")
    before = db.users.writes
    calls = {"n": 0}
    real = user_store.get_board_sort
    try:
        user_store.get_board_sort = lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1)
                                                     or real(*a, **k))
        _run(A.rotation_hottest(request=_Req(EMAIL), sort="rel_1d", dir="desc",
                                names=25, basis="close"))
    finally:
        user_store.get_board_sort = real
    assert calls["n"] == 0
    assert db.users.writes == before


# ===========================================================================
# 2 — NEGATIVES: a board read never breaks
# ===========================================================================
def test_NEGATIVE_an_anonymous_http_request_still_gets_a_board(db, board):
    """`current_user_email` 401s on exactly this request. The board must not.

    The 401 is asserted first so this test fails loudly if the tolerant
    resolution is ever swapped back for the strict dependency.
    """
    from fastapi import HTTPException

    from auth import current_user_email

    req = _Req()                                   # no header, no cookie
    with pytest.raises(HTTPException) as caught:
        _run(current_user_email(request=req, x_user_email=None))
    assert caught.value.status_code == 401

    body = _body(_run(A.rotation_hottest(request=req, sort="", dir="",
                                         names=25, basis="close")))
    assert (body["sorted_by"], body["sorted_dir"]) == (H.DEFAULT_SORT, H.DEFAULT_DIR)
    assert body["sort_source"] == "default"


def test_NEGATIVE_no_request_object_at_all_is_anonymous_not_the_default_user(db, board):
    """A cron/smoke caller importing the handler has no VIEWER. Falling back to
    DEFAULT_USER_EMAIL here would rank a script's board on Ajay's column."""
    _seed(db, "rel_21d", "asc")
    body = _body(_run(A.rotation_hottest(sort="", dir="", names=25, basis="close")))
    assert body["sort_source"] == "default"
    assert body["sorted_by"] == H.DEFAULT_SORT


def test_NEGATIVE_garbage_in_mongo_is_ignored_and_nothing_500s(db, board):
    """Hand-edited, or written before this validation existed. The column
    vocabulary is checked on the way OUT of the store too — a stored string is
    not a trusted string."""
    db.users.docs[EMAIL] = {"email": EMAIL, "board_sorts": {
        "hottest": {"sort": "DROP TABLE", "dir": "sideways"}}}
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    assert (body["sorted_by"], body["sorted_dir"]) == (H.DEFAULT_SORT, H.DEFAULT_DIR)
    assert body["sort_source"] == "default"
    assert board["sort"] == H.DEFAULT_SORT


@pytest.mark.parametrize("stored,want", [
    ({"sort": "rel_21d"}, ("rel_21d", H.DEFAULT_DIR)),
    ({"dir": "asc"}, (H.DEFAULT_SORT, "asc")),
    ({"sort": "rel_21d", "dir": "sideways"}, ("rel_21d", H.DEFAULT_DIR)),
])
def test_half_a_stored_preference_applies_the_half_that_is_valid(db, board, stored, want):
    """The store never WRITES half a pair, so this is a hand-edited or
    pre-schema document. The legs resolve independently everywhere else in
    this endpoint; dropping a perfectly good column because its direction
    rotted would be a second rule for the same ladder."""
    db.users.docs[EMAIL] = {"email": EMAIL, "board_sorts": {"hottest": stored}}
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    assert (body["sorted_by"], body["sorted_dir"]) == want


@pytest.mark.parametrize("stored", [
    {},
    {"sort": None, "dir": None},
    {"sort": {"$ne": 1}, "dir": ["asc"]},     # not even strings
    "rel_21d",                                # not a mapping
    [],
    None,
])
def test_NEGATIVE_a_malformed_stored_shape_never_raises(db, board, stored):
    db.users.docs[EMAIL] = {"email": EMAIL, "board_sorts": {"hottest": stored}}
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    assert body["sorted_by"] == H.DEFAULT_SORT
    assert body["sort_source"] == "default"


def test_NEGATIVE_an_unreadable_preference_store_costs_the_column_not_the_board(
        db, board, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("mongo went away mid-read")

    monkeypatch.setattr(user_store, "get_board_sort", _boom)
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    assert body["sorted_by"] == H.DEFAULT_SORT
    assert body["sort_source"] == "default"


def test_NEGATIVE_a_leaked_query_object_is_not_a_sort(db, board):
    """FastAPI resolves `Query(...)` defaults at REQUEST time, so a direct call
    receives the Query OBJECT — truthy, with no string methods. That bug has
    shipped twice on the demand board; here it would rank the whole table on a
    `Query` instance. Omitting the params is exactly that call."""
    _seed(db, "rel_21d", "asc")
    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), names=25, basis="close")))
    assert body["sorted_by"] == "rel_21d"       # the saved column, not a crash
    assert body["sort_source"] == "saved"


def test_NEGATIVE_an_unavailable_member_table_still_reports_the_real_column(
        db, board, monkeypatch):
    """The empty sentinel must not leak into the payload on the degraded path
    — the board prints `sorted_by` in its header either way."""
    monkeypatch.setattr(A, "_members_table", lambda: (None, {"reason": "no doc"}))
    _seed(db, "rel_21d", "asc")
    resp = _run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                   names=25, basis="close"))
    assert resp.status_code == 200
    body = _body(resp)
    assert (body["sorted_by"], body["sorted_dir"]) == ("rel_21d", "asc")
    assert body["sort_source"] == "saved" and body["sectors"] == []


# ===========================================================================
# 3 — the read NEVER writes (the demotion trap)
# ===========================================================================
def test_the_fake_build_mirrors_the_real_demotion():
    """Holds this file's stub honest: the REAL builder demotes `pre_1d` when
    the pre-market leg made no read. If that ever stops being true, the trap
    the next test guards has changed shape."""
    assert H.build({}, sort=H.PRE_SORT)["sorted_by"] == H.DEFAULT_SORT
    assert H.PRE_SORT in H.SORT_KEYS


def test_a_demoted_sort_is_never_written_back(db, board):
    """His saved column is `pre_1d`; he opens the board at 10:00 when the
    pre-market leg is empty, so the board serves `rel_5d` and says so. The
    STORED preference must be untouched — otherwise one post-bell page load
    silently replaces the column he chose."""
    _seed(db, H.PRE_SORT, "desc")
    before = json.loads(json.dumps(db.users.docs[EMAIL]))
    writes_before = db.users.writes

    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    assert body["sorted_by"] == H.DEFAULT_SORT        # served: demoted
    assert body["sort_source"] == "saved"             # asked: his column
    assert board["sort"] == H.PRE_SORT                # handed to the builder as asked

    assert db.users.docs[EMAIL] == before
    assert db.users.writes == writes_before


def test_an_explicit_demoted_sort_is_not_written_either(db, board):
    """Same trap through the front door: clicking ☀️ pre-market after the bell
    must not store a preference at all. The READ endpoint has no writer."""
    _run(A.rotation_hottest(request=_Req(EMAIL), sort=H.PRE_SORT, dir="desc",
                            names=25, basis="close"))
    assert db.users.docs == {}
    assert db.users.writes == 0


# ===========================================================================
# 4 — POST /rotation/hottest/sort — the only writer
# ===========================================================================
def test_the_post_stores_the_pair_and_the_next_read_opens_on_it(db, board):
    resp = _run(A.rotation_hottest_sort_save({"sort": "q_eps_yoy", "dir": "asc"},
                                             request=_Req(EMAIL)))
    assert resp.status_code == 200
    assert _body(resp) == {"stored": True, "board": "hottest",
                           "sort": "q_eps_yoy", "dir": "asc"}

    body = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    assert (body["sorted_by"], body["sorted_dir"]) == ("q_eps_yoy", "asc")
    assert body["sort_source"] == "saved"


def test_the_preference_is_per_user(db, board):
    _run(A.rotation_hottest_sort_save({"sort": "rel_1d", "dir": "asc"},
                                      request=_Req(EMAIL)))
    _run(A.rotation_hottest_sort_save({"sort": "net_margin", "dir": "desc"},
                                      request=_Req("someone.else@gmail.com")))
    mine = _body(_run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                         names=25, basis="close")))
    theirs = _body(_run(A.rotation_hottest(request=_Req("someone.else@gmail.com"),
                                           sort="", dir="", names=25, basis="close")))
    assert mine["sorted_by"] == "rel_1d"
    assert theirs["sorted_by"] == "net_margin"


@pytest.mark.parametrize("bad", ["traction_", "DROP TABLE", "../etc/passwd", "",
                                 None, 5, ["rel_5d"]])
def test_NEGATIVE_post_with_an_unknown_column_400s_and_stores_nothing(db, bad):
    resp = _run(A.rotation_hottest_sort_save({"sort": bad, "dir": "desc"},
                                             request=_Req(EMAIL)))
    assert resp.status_code == 400
    body = _body(resp)
    assert body["stored"] is False
    # The valid list rides along — the WRITER's list, which is the sortable
    # vocabulary minus the columns this endpoint would refuse to store.
    assert body["sortable"] == [k for k in H.SORT_KEYS
                                if k not in A.UNSAVEABLE_SORTS]
    assert body["dirs"] == list(H.SORT_DIRS)
    assert db.users.docs == {} and db.users.writes == 0


@pytest.mark.parametrize("bad", ["sideways", "DESC", "", None, 1])
def test_NEGATIVE_post_with_an_unknown_direction_400s_and_stores_nothing(db, bad):
    resp = _run(A.rotation_hottest_sort_save({"sort": "rel_5d", "dir": bad},
                                             request=_Req(EMAIL)))
    assert resp.status_code == 400
    assert _body(resp)["dirs"] == list(H.SORT_DIRS)
    assert db.users.docs == {} and db.users.writes == 0


@pytest.mark.parametrize("payload", [{}, None, [], "rel_5d", 7])
def test_NEGATIVE_a_body_that_is_not_a_preference_400s_without_raising(db, payload):
    resp = _run(A.rotation_hottest_sort_save(payload, request=_Req(EMAIL)))
    assert resp.status_code == 400
    assert db.users.docs == {}


def test_NEGATIVE_a_400_never_overwrites_a_good_stored_preference(db):
    _seed(db, "rel_21d", "asc")
    before = json.loads(json.dumps(db.users.docs[EMAIL]))
    _run(A.rotation_hottest_sort_save({"sort": "nope", "dir": "asc"},
                                      request=_Req(EMAIL)))
    assert db.users.docs[EMAIL] == before


def test_NEGATIVE_an_anonymous_post_answers_200_not_stored(db):
    """A preference with nobody to attach it to is a disappointment, not an
    error — the board keeps working on the view-local sort."""
    resp = _run(A.rotation_hottest_sort_save({"sort": "rel_1d", "dir": "asc"},
                                             request=_Req()))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["stored"] is False and body["sort"] == "rel_1d"
    assert "no signed-in user" in body["reason"]
    assert db.users.docs == {} and db.users.writes == 0


def test_NEGATIVE_an_unreachable_store_answers_200_not_stored(no_db):
    resp = _run(A.rotation_hottest_sort_save({"sort": "rel_1d", "dir": "asc"},
                                             request=_Req(EMAIL)))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["stored"] is False
    assert "unavailable" in body["reason"]


def test_NEGATIVE_a_raising_store_answers_200_not_stored(db, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("mongo went away mid-write")

    monkeypatch.setattr(user_store, "set_board_sort", _boom)
    resp = _run(A.rotation_hottest_sort_save({"sort": "rel_1d", "dir": "asc"},
                                             request=_Req(EMAIL)))
    assert resp.status_code == 200
    assert _body(resp)["stored"] is False


def test_every_saveable_column_can_actually_be_saved(db, board):
    """The FE offers one header per `sortable` key. A column the board ranks on
    but the preference endpoint rejects would be a header that silently forgets
    itself — so the two sets have to line up EXACTLY, in both directions.

    The one deliberate exception is `UNSAVEABLE_SORTS`, and it is deliberate on
    BOTH sides: the frontend's `saveBoardSort` returns early for that column,
    so no header silently forgets itself — nothing is offered and nothing is
    refused. The earlier version of this test looped over all of `SORT_KEYS`
    and so asserted the ☀️ bug was correct behaviour."""
    for key in H.SORT_KEYS:
        for d in H.SORT_DIRS:
            resp = _run(A.rotation_hottest_sort_save({"sort": key, "dir": d},
                                                     request=_Req(EMAIL)))
            if key in A.UNSAVEABLE_SORTS:
                assert resp.status_code == 400, (key, d)
                assert _body(resp)["stored"] is False, (key, d)
                continue
            assert resp.status_code == 200, (key, d)
            assert _body(resp)["stored"] is True, (key, d)


# ===========================================================================
# 5 — the store itself
# ===========================================================================
def test_the_store_round_trips_one_board(db):
    assert user_store.get_board_sort(EMAIL, "hottest") is None
    assert user_store.set_board_sort(EMAIL, "hottest", "rel_1d", "asc") == {
        "sort": "rel_1d", "dir": "asc"}
    assert user_store.get_board_sort(EMAIL, "hottest") == {"sort": "rel_1d", "dir": "asc"}


def test_the_email_is_normalised_the_way_every_other_user_field_is(db):
    user_store.set_board_sort("  AJAYKandakatla@Gmail.com ", "hottest", "rel_1d", "asc")
    assert user_store.get_board_sort(EMAIL, "hottest") == {"sort": "rel_1d", "dir": "asc"}
    assert list(db.users.docs) == [EMAIL]


def test_the_write_is_dotted_so_it_cannot_clobber_a_sibling(db):
    """`$set: {board_sorts: {...}}` would delete every other key under the
    field. Two devices saving two boards in the same minute is all it takes."""
    db.users.docs[EMAIL] = {"email": EMAIL,
                            "alert_settings": {"intraday_warning_pct": 8.0},
                            "board_sorts": {"someday_board": {"sort": "x", "dir": "asc"}}}
    user_store.set_board_sort(EMAIL, "hottest", "rel_21d", "desc")
    doc = db.users.docs[EMAIL]
    assert doc["board_sorts"]["someday_board"] == {"sort": "x", "dir": "asc"}
    assert doc["board_sorts"]["hottest"] == {"sort": "rel_21d", "dir": "desc"}
    assert doc["alert_settings"] == {"intraday_warning_pct": 8.0}


def test_NEGATIVE_an_unknown_board_is_a_no_op_not_a_new_field(db):
    """A typo'd or retired board must never grow a field on his user doc."""
    assert "chart_maps" not in user_store.BOARD_SORT_BOARDS
    assert user_store.set_board_sort(EMAIL, "chart_maps", "rel_1d", "asc") == {}
    assert user_store.get_board_sort(EMAIL, "chart_maps") is None
    assert db.users.docs == {} and db.users.writes == 0


@pytest.mark.parametrize("email", ["", "   ", None])
def test_NEGATIVE_a_blank_email_is_a_no_op_not_a_raise(db, email):
    assert user_store.get_board_sort(email, "hottest") is None
    assert user_store.set_board_sort(email, "hottest", "rel_1d", "asc") == {}
    assert db.users.docs == {} and db.users.writes == 0


def test_NEGATIVE_no_mongo_is_a_no_op_not_a_raise(no_db):
    assert user_store.get_board_sort(EMAIL, "hottest") is None
    assert user_store.set_board_sort(EMAIL, "hottest", "rel_1d", "asc") == {}


@pytest.mark.parametrize("sort,dir_", [(None, "asc"), ("rel_1d", None), (5, "asc"),
                                       ("rel_1d", ["asc"]), ("", "asc"), ("rel_1d", " ")])
def test_NEGATIVE_a_non_string_pair_is_never_stored(db, sort, dir_):
    assert user_store.set_board_sort(EMAIL, "hottest", sort, dir_) == {}
    assert db.users.docs == {} and db.users.writes == 0


def test_NEGATIVE_a_read_failure_answers_None_not_an_exception(db, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("cursor died")

    monkeypatch.setattr(db.users, "find_one", _boom)
    assert user_store.get_board_sort(EMAIL, "hottest") is None


def test_NEGATIVE_a_write_failure_answers_empty_not_an_exception(db, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("write concern failed")

    monkeypatch.setattr(db.users, "update_one", _boom)
    assert user_store.set_board_sort(EMAIL, "hottest", "rel_1d", "asc") == {}


def test_the_store_keeps_a_retired_column_verbatim(db):
    """The store has NO opinion about columns — it hands back what is on the
    document and the endpoint's validation decides. That split is what keeps
    one copy of the vocabulary in the app."""
    db.users.docs[EMAIL] = {"email": EMAIL,
                            "board_sorts": {"hottest": {"sort": "rel_99d", "dir": "asc"}}}
    assert user_store.get_board_sort(EMAIL, "hottest") == {"sort": "rel_99d", "dir": "asc"}
    assert A._valid_sort("rel_99d") is None          # and the board drops it


def test_the_store_does_not_import_the_board():
    """ONE OWNER PER FACT. `users.store` importing `rotation.hottest` would put
    a second copy of the column list under the storage layer, and it would
    drift the first time a column is added."""
    tree = ast.parse(inspect.getsource(user_store))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not [m for m in imported if m.startswith("rotation")], imported


def test_the_allowlist_names_the_board_the_endpoint_writes():
    assert A.HOTTEST_BOARD in user_store.BOARD_SORT_BOARDS


# ─────────────────────────────────────────────────────────────────────────────
# ☀️ pre_1d is SORTABLE but never SAVEABLE (found in review, 2026-09-21)
#
# Both reviewers landed on the same two-click sequence from opposite ends.
# The ☀️ button was guarded from the first draft, but pressing it MAKES the
# Pre-mkt column appear, and that column is an ordinary sortable header wired
# straight to the save path. Click ☀️, then click the Pre-mkt header to flip
# it, and `pre_1d` went to the store. Because a cold read is always
# `basis=close`, the endpoint demotes it on EVERY later load — so his real
# column was gone and the board opened ranked on the default leg in whatever
# direction rode along, i.e. 5 days ASCENDING: coldest sectors first, forever.
#
# The rule now has one owner on each side of the wire: `UNSAVEABLE_SORTS` here
# and the `PRE_COL.key` guard inside `saveBoardSort` there.
# ─────────────────────────────────────────────────────────────────────────────
def test_pre_1d_is_a_real_sort_key_which_is_why_this_guard_has_to_exist():
    """If this ever fails, the guard below is guarding nothing."""
    assert H.PRE_SORT in H.SORT_KEYS
    assert A.UNSAVEABLE_SORTS == (H.PRE_SORT,)


def test_NEGATIVE_post_pre_1d_400s_and_stores_nothing(db):
    resp = _run(A.rotation_hottest_sort_save({"sort": H.PRE_SORT, "dir": "desc"},
                                             request=_Req(EMAIL)))
    assert resp.status_code == 400
    body = _body(resp)
    assert body["stored"] is False
    assert H.PRE_SORT in body["error"]
    assert "demoted" in body["reason"]
    assert db.users.docs == {} and db.users.writes == 0


def test_NEGATIVE_post_pre_1d_never_overwrites_the_column_he_actually_picked(db):
    """The expensive half: the refusal must not cost him the stored column."""
    _seed(db, "sales_yoy", "desc")
    before = json.loads(json.dumps(db.users.docs[EMAIL]))
    resp = _run(A.rotation_hottest_sort_save({"sort": H.PRE_SORT, "dir": "asc"},
                                             request=_Req(EMAIL)))
    assert resp.status_code == 400
    assert db.users.docs[EMAIL] == before


def test_the_writer_never_advertises_a_column_it_would_refuse(db):
    """A 400 body that listed `pre_1d` as `sortable` would send the caller
    straight back into the same refusal."""
    resp = _run(A.rotation_hottest_sort_save({"sort": "nope", "dir": "desc"},
                                             request=_Req(EMAIL)))
    assert H.PRE_SORT not in _body(resp)["sortable"]


def test_a_pre_1d_preference_that_predates_this_guard_still_reads_safely(db, board):
    """Defence in depth: a doc written before the guard existed (or by hand)
    must not break the board. The READ path already demotes it — what it must
    never do is 500, and it must still be reported honestly as `saved`."""
    _seed(db, H.PRE_SORT, "desc")
    resp = _run(A.rotation_hottest(request=_Req(EMAIL), sort="", dir="",
                                   names=H.NAMES_PER_GROUP, basis=H.D1_CLOSE))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["sort_source"] == "saved"
    assert body["sorted_by"] == H.DEFAULT_SORT      # demoted, not honoured
    assert db.users.docs[EMAIL]["board_sorts"]["hottest"]["sort"] == H.PRE_SORT


@pytest.mark.parametrize("bag", ["rel_21d", ["rel_21d"], 7, True])
def test_NEGATIVE_a_board_sorts_field_that_is_not_a_mapping_returns_none(db, bag):
    """`get_board_sort` documents "returns None — never raises". A hand-edited
    doc where `board_sorts` is a string used to reach `.get` on a str and
    raise; the one caller caught it, but the docstring is a promise."""
    db.users.docs[EMAIL] = {"email": EMAIL, "board_sorts": bag}
    assert user_store.get_board_sort(EMAIL, "hottest") is None
