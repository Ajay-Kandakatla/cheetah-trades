"""🧨 The explosive read on the Chart Maps tile boards — 2026-09-15.

Ajay 2026-09-14 asked for a per-stock read of how likely a name in / arriving
at a demand band is to travel >= 5% toward the first supply band, *evaluated
before it ranks*, and offered as an ordering on every tab.

WHAT THESE TESTS PIN, and why each one exists:

* the read is attached on EVERY tile-board request, not only when the 🧨 sort
  is chosen — the chip renders on every tab, and a second request for it would
  be a second fan-out over the same store;
* the ordering runs over ALL tiles, not the `limit x TAPE_POOL_MULT` pool the
  tape and velocity sorts use. That pool exists because those two pay a network
  lookup per name; this read is already attached for free, so a cap would make
  "🧨 first" silently mean "🧨 first among the two dozen the default order
  happened to choose";
* a board where NOT ONE name has a read says so (`sort_unavailable`) instead of
  returning the default order dressed as a ranking — the lesson the
  retail-imbalance sort taught;
* a tile with no read sorts LAST. Missing data must never masquerade as a top
  result: a name with no demand-band read is not a quiet name, it is an
  unknown one;
* every OTHER sort is untouched. This change adds an ordering; it must not
  reorder a single board he already reads.

The ordering key itself (`supply_demand.explosive.explosive_key`) and its
shared fixture are pinned in `test_explosive.py` / `bounceRoom.test.ts`; here
the board is the subject.
"""
import pytest

from chart_maps import board as B


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _read(score=None, intact=True, state="ROOM", room_pct=10.0):
    """A minimal `explosive.read()` return, in the shape §6.1 specifies.

    Only the keys the ORDERING keys on are filled — `explosive_key` reads
    `score`, `intact` and `room`, and nothing on this board may depend on more
    than that.
    """
    band = (None if state == "CLEAR"
            else {"kind": "supply", "lo": 108.0, "hi": 110.0, "touches": 2})
    return {"score": score, "grade": None, "components": [],
            "intact": intact, "session_low": False,
            "room": {"state": state,
                     "room_pct": None if state == "CLEAR" else room_pct,
                     "band": band},
            "band": {"lo": 90.0, "hi": 92.0},
            "convention": None, "measured": {"status": "pending"}}


def _tile(sym, score=0.0, explosive=..., **metrics):
    """A board tile as `_finish` receives it.

    `explosive=...` (the sentinel) leaves the KEY ABSENT, which is what a real
    pre-`attach_explosive` tile looks like; passing None stamps a real "no
    read" answer that `attach_explosive` must then leave alone.
    """
    t = {"symbol": sym, "theme": None, "_score": score, "bars": [],
         "last_price": 100.0,
         "_m": dict(B.tile_metrics({}), **metrics)}
    if explosive is not ...:
        t["explosive"] = explosive
    # `_m["explosive"]` is left None ON PURPOSE — that is what the null branch
    # actually serves, and it means the generic `_sort_key` path can do NONE of
    # the ordering work below. Every 🧨 order these tests assert is therefore
    # the doing of `_explosive_sort`, not of a metric column.
    return t


@pytest.fixture
def no_io(monkeypatch):
    """Everything `_finish` reaches for that is not the subject here."""
    def _bars(tiles, days):
        for t in tiles:
            t["bars"] = [{"t": "2026-09-15", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]
    monkeypatch.setattr(B, "_attach_bars", _bars)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)


# --------------------------------------------------------------------------
# the metric column and the dropdown entry
# --------------------------------------------------------------------------
def test_the_sort_is_offered_under_its_own_key():
    """The internal key is `explosive`; the LABEL is the owner's to rename
    (🚀 Explosive Growth already owns the word on this page). tabUsageKey and
    the ✨ entry key off the key, so a rename is a one-string change."""
    assert "explosive" in B.SORTS
    assert B.SORTS["explosive"].startswith("🧨 ")


def test_the_metric_column_starts_None_and_the_ordering_does_not_read_it():
    """In the null branch there IS no score. The column stays None — and the
    ordering keys on `explosive_key`, never on `_m`, so an honest empty column
    cannot turn the 🧨 sort into a no-op."""
    assert B.tile_metrics({})["explosive"] is None
    import inspect
    src = inspect.getsource(B._explosive_sort)
    assert "explosive_key" in src
    assert '_m' not in src, "the ordering must not fall back to the metric column"


# --------------------------------------------------------------------------
# attach_explosive — one store read, every request
# --------------------------------------------------------------------------
@pytest.fixture
def fake_store(monkeypatch):
    """One `zone_store.load_latest` for the whole board, counted."""
    from supply_demand import zone_store, explosive
    calls = {"n": 0, "symbols": None}

    def _latest(symbols=None, coll=None, today=None):
        calls["n"] += 1
        calls["symbols"] = list(symbols or [])
        return "2026-09-15", {s: {"symbol": s, "feat": {}} for s in (symbols or [])}

    monkeypatch.setattr(zone_store, "load_latest", _latest)
    monkeypatch.setattr(explosive, "read",
                        lambda **kw: _read(intact=True, state="ROOM", room_pct=10.0))
    return calls


def test_the_read_is_attached_on_EVERY_request_not_only_the_explosive_sort(
        no_io, fake_store):
    """The chip renders on every tab. Attaching only under `sort=explosive`
    would mean a second request per board just to draw it."""
    tiles = [_tile("AAA"), _tile("BBB")]
    out, meta = B._finish(tiles, 24, False, 30, sort=B.DEFAULT_SORT,
                          min_tier="any")
    assert all(t["explosive"] is not None for t in out)
    assert fake_store["n"] == 1, "one store read for the whole board, not one per tile"
    assert meta["sort_unavailable"] is None


def test_attach_explosive_is_a_no_op_when_the_key_is_already_there(fake_store):
    """`board()` calls it a second time for the three ledger tabs that never
    reach `_finish`. Keyed on PRESENCE, not truthiness — None is a real answer
    — so the second call must not pay for a second Mongo query."""
    tiles = [_tile("AAA", explosive=None), _tile("BBB", explosive=_read(0.5))]
    assert B.attach_explosive(tiles) == 0
    assert fake_store["n"] == 0
    assert tiles[0]["explosive"] is None


def test_NEGATIVE_a_cold_store_leaves_every_tile_unread_and_never_raises(
        monkeypatch):
    """Decoration plus an ordering. A board that 500s because the zone store is
    cold would be a far worse trade than a board with no chips."""
    from supply_demand import zone_store, explosive
    monkeypatch.setattr(zone_store, "load_latest",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cold")))
    monkeypatch.setattr(explosive, "read", lambda **kw: None)
    tiles = [_tile("AAA"), _tile("BBB")]
    assert B.attach_explosive(tiles) == 0
    assert all(t["explosive"] is None for t in tiles)
    assert all("explosive" in t for t in tiles), "the key is stamped even when unread"


def test_NEGATIVE_a_read_that_raises_costs_one_tile_not_the_board(monkeypatch):
    from supply_demand import zone_store, explosive
    monkeypatch.setattr(zone_store, "load_latest",
                        lambda symbols=None, **k: ("2026-09-15",
                                                   {s: {"feat": {}} for s in symbols}))

    def _read_one(**kw):
        if kw.get("symbol") == "BAD":
            raise ValueError("boom")
        return _read(intact=True)

    monkeypatch.setattr(explosive, "read", _read_one)
    tiles = [_tile("BAD"), _tile("GOOD")]
    assert B.attach_explosive(tiles) == 1
    assert tiles[0]["explosive"] is None and tiles[1]["explosive"] is not None


# --------------------------------------------------------------------------
# the ordering — over ALL tiles, before the bar fetch
# --------------------------------------------------------------------------
def test_explosive_sort_runs_over_all_tiles_not_the_pool(no_io):
    """A tile ranked 100th by the default order reaches the TOP.

    `TAPE_POOL_MULT * limit` is 72 here, so a pooled implementation would never
    have seen this tile — and the board would have shown the default order
    under a 🧨 label.
    """
    limit = 24
    n = limit * B.TAPE_POOL_MULT + 40           # 112 tiles, pool would be 72
    tiles = [_tile("S%03d" % i, score=float(n - i),
                   explosive=_read(score=0.10, intact=False,
                                   state="NEAR", room_pct=1.0))
             for i in range(n)]
    # The winner by BOTH branches of the key: top score if the study ever says
    # `separates`, and intact + CLEAR (room_rank's group 0) in the fallback.
    tiles[100]["explosive"] = _read(score=0.99, intact=True, state="CLEAR")

    assert tiles[100]["symbol"] == "S100"
    # by the DEFAULT order it is 101st: `_score` counts down from the front
    assert sorted(tiles, key=lambda t: -t["_score"])[100]["symbol"] == "S100"
    out, meta = B._finish(tiles, limit, False, 30, sort="explosive",
                          min_tier="any")
    assert out[0]["symbol"] == "S100"
    assert meta["sort_unavailable"] is None


def test_explosive_sort_unavailable_when_no_doc(no_io):
    """Not one name on the board has a demand-band read. A sort over an
    all-null column returns the default order, which LOOKS like a working sort
    and is not one — say so instead."""
    tiles = [_tile("AAA", score=1.0, explosive=None),
             _tile("BBB", score=9.0, explosive=None)]
    out, meta = B._finish(tiles, 24, False, 30, sort="explosive", min_tier="any")
    assert meta["sort_unavailable"] == B.EXPLOSIVE_SORT_UNAVAILABLE
    # and the board still renders — the note replaces the claim, not the tiles
    assert {t["symbol"] for t in out} == {"AAA", "BBB"}


def test_NEGATIVE_a_tile_with_no_read_sorts_LAST(no_io):
    """Unknown is not "worst". It is unknown, and it goes to the bottom —
    the same rule every other column on this board follows."""
    tiles = [_tile("UNKNOWN", score=99.0, explosive=None),
             _tile("READ", score=1.0,
                   explosive=_read(score=0.01, intact=False,
                                   state="IN_BAND", room_pct=0.0))]
    out, meta = B._finish(tiles, 24, False, 30, sort="explosive", min_tier="any")
    assert [t["symbol"] for t in out] == ["READ", "UNKNOWN"]
    assert meta["sort_unavailable"] is None, "one read is enough to rank"


def test_NEGATIVE_a_non_explosive_sort_is_untouched_by_the_read(no_io, fake_store):
    """The read is attached on every request; it must not reorder a single
    board he already reads. Volume order stays volume order."""
    tiles = [_tile("QUIET", score=0.0, volume=1.0),
             _tile("LOUD", score=0.0, volume=999.0)]
    out, _meta = B._finish(tiles, 24, False, 30, sort="volume", min_tier="any")
    assert [t["symbol"] for t in out] == ["LOUD", "QUIET"]
    assert all(t["explosive"] is not None for t in out)


def test_NEGATIVE_the_default_order_is_untouched_by_the_read(no_io, fake_store):
    tiles = [_tile("LOW", score=1.0), _tile("HIGH", score=9.0)]
    out, _meta = B._finish(tiles, 24, False, 30, sort=B.DEFAULT_SORT,
                           min_tier="any")
    assert [t["symbol"] for t in out] == ["HIGH", "LOW"]


def test_the_ordering_happens_before_the_bars_are_fetched(no_io):
    """`_finish` exists to rank on metadata and only THEN load `limit +
    BAR_BUFFER` frames. An ordering applied after the fetch would be ranking
    the survivors of a different ranking."""
    import inspect
    src = inspect.getsource(B._finish)
    assert src.index('sort == "explosive"') < src.index("_attach_bars(short, days)")


def test_the_read_never_gates_the_board(monkeypatch):
    """SOURCE GUARD (§6.7 test 9c). The score is an ordering and a chip. If it
    ever starts dropping tiles, that must be a deliberate edit, not a drift."""
    import inspect
    src = inspect.getsource(B.attach_explosive)
    for forbidden in ("min_room", "passes_liquidity", "_spread"):
        assert forbidden not in src


# --------------------------------------------------------------------------
# the two tabs that advertised a sort and ignored it
# --------------------------------------------------------------------------
@pytest.fixture
def turning_rows(monkeypatch):
    """Two stored turning-bullish rows, LO first, with scan volumes that
    disagree with that order."""
    from supply_demand import turning_bullish as TBm
    from sepa import scanner
    rows = [{"symbol": "LO", "last_close": 10.0, "amd": {}, "amd_grade": "raided"},
            {"symbol": "HI", "last_close": 20.0, "amd": {}, "amd_grade": "raided"}]
    monkeypatch.setattr(TBm, "board", lambda kind, limit=120, db=None: {
        "kind": "amd", "rows": rows, "n": 2, "n_all": 2, "capped": False,
        "n_scanned": 2, "n_rows": 2, "counts": {}, "built_at": None, "params": {}})
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": [
        {"symbol": "LO", "volume": {"last_vol": 1}},
        {"symbol": "HI", "volume": {"last_vol": 999}},
    ]})
    monkeypatch.setattr(B, "bars_for",
                        lambda sym, days=130, **k: [{"t": "2026-09-15", "o": 1,
                                                     "h": 1, "l": 1, "c": 1, "v": 1}])
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    return rows


def test_turning_bullish_tiles_honour_sort(no_io, turning_rows):
    """Both tabs ADVERTISED the dropdown and ignored it: `board()` handed every
    other tab's ordering to `_finish` and these two ranked by the stored row
    order alone. Picking "Volume today" and getting the stored order back is a
    control that does nothing."""
    default = B.turning_bullish_tiles("amd", limit=5)
    assert [t["symbol"] for t in default["tiles"]] == ["LO", "HI"]

    by_vol = B.turning_bullish_tiles("amd", limit=5, sort="volume")
    assert [t["symbol"] for t in by_vol["tiles"]] == ["HI", "LO"]


def test_NEGATIVE_turning_bullish_still_keeps_the_names_the_scan_never_saw(
        no_io, monkeypatch, turning_rows):
    """This board is about chart structure, not liquidity — its own comment
    says a name the scan has not seen still gets a tile. Routing it through
    `_finish` must not quietly delete every name without a scan row."""
    from sepa import scanner
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": []})
    out = B.turning_bullish_tiles("amd", limit=5, min_tier="deep")
    assert {t["symbol"] for t in out["tiles"]} == {"LO", "HI"}


def test_turning_bullish_reports_an_unavailable_sort(no_io, turning_rows):
    """The honest note reaches the payload on these two tabs too."""
    out = B.turning_bullish_tiles("amd", limit=5, sort="explosive")
    assert "sort_unavailable" in out


# --------------------------------------------------------------------------
# the banner — `board()` must SERVE the verdict, not only the chips
# --------------------------------------------------------------------------
@pytest.fixture
def quiet_board(monkeypatch):
    """`board()` with the tile builder and the live-tape leg stubbed out.

    `earnings` is the cheapest tab to stand up: it never reaches `_finish`, so
    what is left in `board()` after the stub is exactly the payload-level
    decoration this section is about.
    """
    monkeypatch.setattr(B, "earnings_tiles",
                        lambda limit, days: {"tiles": [_tile("AAA")],
                                             "note": "stub"})
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})


def test_board_serves_the_measured_verdict_for_the_banner(quiet_board):
    """§6.4: the tile tabs' `CmBoard.study` slot reads `explosive_study` off
    THIS payload (`ChartMaps.tsx` renders `data?.explosive_study?.headline`
    and hands the same dict to every `PatternChart`).

    Without this key the verdict banner never renders on a single tile tab and
    every chip tooltip loses its MEASURED line — the chips would be showing an
    order with the sentence that qualifies it stripped off. The FE contract
    only checks the TSX side, so nothing else catches the hole.
    """
    from supply_demand import explosive

    out = B.board(tab="earnings", limit=5)
    assert "explosive_study" in out
    assert out["explosive_study"] == explosive.measured_verdict()
    # the same dict the non-tile boards get from `bounce_room.api_payload`
    assert set(out["explosive_study"]) >= {"headline", "body", "fallback_note",
                                           "limits"}
    assert out["explosive_study"]["headline"]


def test_the_banner_prose_is_built_not_typed(quiet_board):
    """SOURCE GUARD. The banner is the one place a number could be typed into
    the payload by hand. It must come from `explosive.measured_verdict()` —
    `board()` may not compose a sentence of its own."""
    import inspect
    src = inspect.getsource(B.board)
    assert "measured_verdict()" in src
    assert "MEASURED" not in src, "no verdict prose is composed in board()"


def test_NEGATIVE_a_verdict_that_raises_costs_the_banner_not_the_board(
        quiet_board, monkeypatch):
    """Decoration, like the chip. A board that 500s because the verdict module
    is unimportable would be a far worse trade than a board with no banner —
    and `None` is the honest answer the FE already renders nothing for."""
    from supply_demand import explosive
    monkeypatch.setattr(explosive, "measured_verdict",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    out = B.board(tab="earnings", limit=5)
    assert out["explosive_study"] is None
    assert out["tiles"], "the tiles still render"


def test_NEGATIVE_the_verdict_is_served_on_a_tab_that_never_reaches_finish(
        quiet_board):
    """`earnings` / `winners` / `zero_dte` read ledgers and skip `_finish`
    entirely — they keep `sorts: []`. The banner is a READ, not a control, so
    withholding it there would be withholding the sentence that qualifies the
    chip on exactly the tabs whose ordering he cannot change."""
    out = B.board(tab="earnings", limit=5)
    assert out["sorts"] == []
    assert out["explosive_study"] is not None


# --------------------------------------------------------------------------
# the two accepted side effects (2026-09-15) — pinned so a change is deliberate
# --------------------------------------------------------------------------
def test_the_tile_read_keys_on_the_SCAN_print_not_the_live_one(no_io, monkeypatch):
    """ACCEPTED SIDE EFFECT, his call to change.

    `attach_explosive` runs inside `_finish`; `attach_live_now` runs later, in
    `board()`, and moves the tile's `now` line to the live (pre/post included)
    print WITHOUT re-running the read. So the tile path reads the closed scan
    print while the bounce-room ROW path reads the live snapshot, and intraday
    the two surfaces can disagree about the band state.

    Ranking on the live tape here would mean a second fan-out before the
    liquidity floor and an ordering that moves under him while he reads the
    board. The chip's tooltip says "closed-bar read" for exactly this reason.
    """
    from supply_demand import zone_store, explosive
    seen = {}
    monkeypatch.setattr(zone_store, "load_latest",
                        lambda symbols=None, **k: ("2026-09-15",
                                                   {s: {"feat": {}} for s in symbols}))

    def _read_px(**kw):
        seen[kw.get("symbol")] = kw.get("px")
        return _read(intact=True)

    monkeypatch.setattr(explosive, "read", _read_px)

    tile = _tile("AAA")                       # last_price 100.0, the scan print
    tile["lines"] = [{"price": 100.0, "label": "now", "tone": "now"}]
    out, _meta = B._finish([tile], 24, False, 30, sort=B.DEFAULT_SORT,
                           min_tier="any")
    assert seen["AAA"] == 100.0, "the read keyed on the closed scan print"

    # ... and now the live print arrives, 12% higher. The tile DISPLAYS it; the
    # read is not recomputed, and nothing here pretends otherwise.
    B.attach_live_now(out, {}, live={"AAA": {"price": 112.0, "t": None}})
    assert out[0]["live_price"] == 112.0
    assert seen["AAA"] == 100.0, "no second read — the disagreement is the known one"
    assert out[0]["explosive"] is not None


def test_the_read_is_attached_before_the_live_print_is_moved():
    """The order above is not incidental — it is what `board()` does. Written
    down so flipping it is a decision, not a diff nobody read."""
    import inspect
    src = inspect.getsource(B.board)
    assert src.index("attach_explosive(") < src.index("attach_live_now(")


def test_turning_bullish_themes_first_SPREADS_but_drops_nothing(no_io, monkeypatch):
    """ACCEPTED SIDE EFFECT, his call to change.

    These two tabs used to sort by `_theme_rank` alone, so `themes_first` only
    pulled theme names to the front. Routing them through `_finish` also applies
    `_spread` (MAX_PER_THEME), so the 7th name of one theme now sits BEHIND the
    other themes instead of ahead of them — the same spread every other tab
    already shows.

    It drops nothing: `_spread` keeps the overflow as a tail, and every name is
    still on the board.
    """
    from supply_demand import turning_bullish as TBm
    from sepa import scanner
    n_theme = B.MAX_PER_THEME + 2                       # 8 names in one theme
    syms = ["AI%d" % i for i in range(n_theme)] + ["SOLO"]
    monkeypatch.setattr(TBm, "board", lambda kind, limit=120, db=None: {
        "kind": "amd", "rows": [{"symbol": s, "last_close": 10.0, "amd": {},
                                 "amd_grade": "raided"} for s in syms],
        "n": len(syms), "n_all": len(syms), "capped": False, "n_scanned": len(syms),
        "n_rows": len(syms), "counts": {}, "built_at": None, "params": {}})
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": []})
    monkeypatch.setattr(B, "bars_for",
                        lambda sym, days=130, **k: [{"t": "2026-09-15", "o": 1,
                                                     "h": 1, "l": 1, "c": 1, "v": 1}])
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "_theme", lambda sym: "nuclear" if sym == "SOLO" else "ai_semis")
    monkeypatch.setattr(B, "_theme_rank", lambda theme: 0 if theme == "ai_semis" else 1)

    out = B.turning_bullish_tiles("amd", limit=24, themes_first=True)
    got = [t["symbol"] for t in out["tiles"]]
    assert set(got) == set(syms), "the spread reorders; it must not drop a name"
    assert got.index("SOLO") == B.MAX_PER_THEME, "the other theme moves up at the cap"
    assert got[-2:] == ["AI6", "AI7"], "the overflow is a tail, in rank order"


def test_NEGATIVE_an_explicit_sort_on_those_tabs_skips_the_theme_cap(
        no_io, monkeypatch):
    """An explicit ranking must be the ranking the dropdown names. Capping it
    per theme would quietly bury the 7th-loudest name for being popular."""
    from supply_demand import turning_bullish as TBm
    from sepa import scanner
    syms = ["AI%d" % i for i in range(B.MAX_PER_THEME + 2)] + ["SOLO"]
    monkeypatch.setattr(TBm, "board", lambda kind, limit=120, db=None: {
        "kind": "amd", "rows": [{"symbol": s, "last_close": 10.0, "amd": {},
                                 "amd_grade": "raided"} for s in syms],
        "n": len(syms), "n_all": len(syms), "capped": False, "n_scanned": len(syms),
        "n_rows": len(syms), "counts": {}, "built_at": None, "params": {}})
    # SOLO is the QUIETEST name; by volume it must come last, theme or not.
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": [
        {"symbol": s, "volume": {"last_vol": 1 if s == "SOLO" else 100 + i}}
        for i, s in enumerate(syms)]})
    monkeypatch.setattr(B, "bars_for",
                        lambda sym, days=130, **k: [{"t": "2026-09-15", "o": 1,
                                                     "h": 1, "l": 1, "c": 1, "v": 1}])
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "_theme", lambda sym: "nuclear" if sym == "SOLO" else "ai_semis")
    monkeypatch.setattr(B, "_theme_rank", lambda theme: 0 if theme == "ai_semis" else 1)

    out = B.turning_bullish_tiles("amd", limit=24, themes_first=True, sort="volume")
    got = [t["symbol"] for t in out["tiles"]]
    assert set(got) == set(syms)
    assert got[-1] == "SOLO", "explicit sort replaces the theme ranking, cap included"
