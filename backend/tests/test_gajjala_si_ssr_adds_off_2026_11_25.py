"""⛔🔒 off-list ADDS ship paused (2026-11-25, main session). The review found no TOTAL cap on live adds (only
GC.FLOAT_MAX_NEW_PER_PASS per pass, carried STAY_LISTED_SESSIONS); a cap is his number, so SSN.ADD_ON ships False.
GG's own listed names keep every tag (🩳 title, ⛔/🔒) and the Watch stamp. NEGATIVES: no add while off, even when
eligible; the eligible names are counted as queued, never dropped silently; on_open still adds nothing when on."""
from chart_maps.gajjala import si_ssr_names as SSN


def test_ships_off():
    assert SSN.ADD_ON is False


def test_add_on_is_exported_beside_add_on_open():
    src = open(SSN.__file__).read()
    assert "room = 0 if (not ADD_ON or (on_open and not ADD_ON_OPEN)) else ADD_MAX_NEW_PER_PASS" in src


from tests.test_gajjala_si_ssr_names_2026_11_24 import S, TYPES, worked_rows   # noqa: E402 — the same worked inputs


def test_NEGATIVE_off_means_no_add_and_the_eligible_name_is_queued_not_dropped(monkeypatch):
    monkeypatch.setattr(SSN, "ADD_ON", False)
    res = SSN.resolve({"AKAN": {"ssr_recent": {"text": "⛔"}}}, worked_rows(), S, TYPES, [], set(), on_open=False)
    assert res["added"] == []
    assert res["queued"] == ["AKAN"] or [getattr(r, "get", lambda k: r)("symbol") for r in res["queued"]] == ["AKAN"]


def test_NEGATIVE_off_still_tags_gg_s_own_qualifier(monkeypatch):
    monkeypatch.setattr(SSN, "ADD_ON", False)
    res = SSN.resolve({"GGQ": {"ssr_today": {"text": "⛔"}}}, worked_rows(), S, TYPES, [{"symbol": "GGQ"}], set(),
                      on_open=False)
    assert res["added"] == [] and res["tagged"] == ["GGQ"]


def test_on_adds_the_same_name(monkeypatch):
    monkeypatch.setattr(SSN, "ADD_ON", True)
    res = SSN.resolve({"AKAN": {"ssr_recent": {"text": "⛔"}}}, worked_rows(), S, TYPES, [], set(), on_open=False)
    assert [r["symbol"] for r in res["added"]] == ["AKAN"]


def test_NEGATIVE_on_with_on_open_still_adds_nothing(monkeypatch):
    monkeypatch.setattr(SSN, "ADD_ON", True)
    monkeypatch.setattr(SSN, "ADD_ON_OPEN", False)
    src = open(SSN.__file__).read()
    assert "(on_open and not ADD_ON_OPEN)" in src


def test_tags_do_not_depend_on_add_on(monkeypatch):
    monkeypatch.setattr(SSN, "ADD_ON", False)
    blk = SSN.tag_block("AKAN", {"ssr_recent": {"text": "⛔ SSR 11/23 · day 2", "day_n": 2, "triggered_on": "2026-11-23"}},
                        {"text": "🩳 32.4% short interest · High"}, add=False)
    assert blk and "🩳 32.4% short interest · High" in blk["text"] and "⛔ SSR 11/23 · day 2" in blk["text"]
