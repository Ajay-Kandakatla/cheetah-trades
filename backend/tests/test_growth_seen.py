"""First-seen tracking on the growth board (2026-09-12).

Built for Ajay's *"If they are newly found explosive growth"* on the breakout
board. The growth doc is `_id: "latest"` — latest-only — so before this there
was no way to tell a name that arrived today from one that has sat there for
months.

The behaviour worth defending: **a name present at the very first build is NOT
new.** It is merely the first thing we ever saw. Reading "unknown" as the
favourable state would have marked all 29 rows ✨ on day one, and a badge that
fires on everything tells him nothing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from growth import tracker as GT


class FakeColl:
    """Enough Mongo for `_record_seen` / `newly_found`: upsert with $set and
    $setOnInsert, find_one by _id, and the one $ne/$gt query they issue."""

    def __init__(self):
        self.docs: dict[str, dict] = {}

    def update_one(self, flt, update, upsert=False):
        _id = flt["_id"]
        cur = self.docs.get(_id)
        if cur is None:
            if not upsert:
                return
            cur = {"_id": _id}
            cur.update(update.get("$setOnInsert", {}))
            self.docs[_id] = cur
        cur.update(update.get("$set", {}))

    def find_one(self, flt, *a, **k):
        return self.docs.get(flt.get("_id"))

    def find(self, flt, *a, **k):
        ne = (flt.get("_id") or {}).get("$ne")
        gt = (flt.get("first_seen") or {}).get("$gt")
        return [d for d in self.docs.values()
                if d["_id"] != ne and str(d.get("first_seen", "")) > str(gt)]


class FakeDB:
    def __init__(self):
        self.coll = FakeColl()

    def __getitem__(self, name):
        assert name == GT.SEEN_COLL
        return self.coll


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def rows(*syms):
    return [{"symbol": s} for s in syms]


# ── recording ──────────────────────────────────────────────────────────────
def test_the_first_build_stamps_when_TRACKING_began_not_just_the_names():
    db = FakeDB()
    GT._record_seen(rows("NVDA", "IPI"), db=db)
    assert "tracking_since" in db.coll.docs["__meta__"]
    assert set(db.coll.docs) == {"__meta__", "NVDA", "IPI"}


def test_first_seen_is_written_ONCE_and_never_moved_by_a_later_build():
    """The whole value of the record. If a rebuild refreshed `first_seen`,
    every name would be permanently new and ✨ would mean nothing."""
    db = FakeDB()
    db.coll.docs["__meta__"] = {"_id": "__meta__", "tracking_since": iso(90)}
    db.coll.docs["NVDA"] = {"_id": "NVDA", "first_seen": iso(60), "last_seen": iso(7)}
    before = db.coll.docs["NVDA"]["first_seen"]
    GT._record_seen(rows("NVDA"), db=db)
    assert db.coll.docs["NVDA"]["first_seen"] == before
    assert db.coll.docs["NVDA"]["last_seen"] > before      # last_seen DOES move


def test_symbols_are_upper_cased_so_one_name_is_one_row():
    db = FakeDB()
    GT._record_seen([{"symbol": "nvda"}, {"symbol": "NVDA"}], db=db)
    assert set(db.coll.docs) == {"__meta__", "NVDA"}


def test_NEGATIVE_a_row_with_no_symbol_is_skipped_not_stored_as_blank():
    db = FakeDB()
    GT._record_seen([{"symbol": None}, {}, {"symbol": "IPI"}], db=db)
    assert set(db.coll.docs) == {"__meta__", "IPI"}


def test_NEGATIVE_a_write_failure_never_breaks_the_build():
    """`build()` calls this before persisting the board. A first-seen write
    failing must not cost him the whole growth board."""
    class Boom:
        def __getitem__(self, name):
            raise RuntimeError("mongo down")

    GT._record_seen(rows("NVDA"), db=Boom())        # must not raise


# ── reading ────────────────────────────────────────────────────────────────
def test_it_returns_the_names_that_ARRIVED_inside_the_window():
    db = FakeDB()
    db.coll.docs = {
        "__meta__": {"_id": "__meta__", "tracking_since": iso(200)},
        "OLD": {"_id": "OLD", "first_seen": iso(120)},
        "NEW": {"_id": "NEW", "first_seen": iso(3)},
    }
    assert GT.newly_found(days=30, db=db) == {"NEW"}


def test_THE_ONE_THAT_MATTERS_the_first_build_cohort_is_not_new():
    """Tracking started two days ago, so every stored name is two days old —
    but none of them ARRIVED, they were simply the first thing observed. The
    answer must be empty, not the whole board."""
    db = FakeDB()
    t0 = iso(2)
    db.coll.docs = {"__meta__": {"_id": "__meta__", "tracking_since": t0},
                    "A": {"_id": "A", "first_seen": t0},
                    "B": {"_id": "B", "first_seen": t0}}
    assert GT.newly_found(days=30, db=db) == set()


def test_a_genuine_arrival_AFTER_tracking_began_still_counts_on_a_young_record():
    db = FakeDB()
    t0 = iso(2)                 # ONE stamp: `_record_seen` writes a single
    db.coll.docs = {            # `now` for the meta row and every symbol
        "__meta__": {"_id": "__meta__", "tracking_since": t0},
        "A": {"_id": "A", "first_seen": t0},
        "LATE": {"_id": "LATE", "first_seen": iso(1)}}
    assert GT.newly_found(days=30, db=db) == {"LATE"}


def test_NEGATIVE_no_meta_row_means_EMPTY_not_everything():
    """A collection written by an older build has no `tracking_since`. Unknown
    must fail to the conservative answer."""
    db = FakeDB()
    db.coll.docs = {"NVDA": {"_id": "NVDA", "first_seen": iso(1)}}
    assert GT.newly_found(days=30, db=db) == set()


def test_NEGATIVE_the_meta_row_is_never_returned_as_a_symbol():
    db = FakeDB()
    db.coll.docs = {"__meta__": {"_id": "__meta__", "tracking_since": iso(200),
                                 "first_seen": iso(1)},
                    "NEW": {"_id": "NEW", "first_seen": iso(1)}}
    assert GT.newly_found(days=30, db=db) == {"NEW"}


def test_NEGATIVE_a_read_failure_returns_EMPTY_so_nothing_is_falsely_badged():
    class Boom:
        def __getitem__(self, name):
            raise RuntimeError("mongo down")

    assert GT.newly_found(days=30, db=Boom()) == set()


def test_the_window_is_a_named_constant_and_covers_more_than_one_rebuild():
    """The board rebuilds Sundays — a window shorter than a week would make
    ✨ depend on which day he opened the page."""
    assert isinstance(GT.NEW_GROWTH_DAYS, int)
    assert GT.NEW_GROWTH_DAYS >= 7


def test_the_build_records_first_seen():
    import inspect
    assert "_record_seen(rows)" in inspect.getsource(GT.build)
