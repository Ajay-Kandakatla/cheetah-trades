"""🎯 The A+ push leads with 🎯 A+ and opens the 👀 Watch (2026-11-17, SPEC ggwaplus2 WP-2).

Ajay 2026-11-17 ~17:20 ET, verbatim: "Push new Apluses immediately in to watch list and an alert for me please Missed
AKAN and GP". Both A+ pushes rang and were shown on his iPhone, buried among ~58 pushes. ONE compose
(chart_maps/gajjala/alerts.compose) now titles every A+ "🎯 A+ · {SYM} · {emoji} {label}" and its url is the 👀 Watch
tab on that name; push/recent.ITEM_URL_BY_KIND sends the /alerts ticker link of the two A+ kinds to the same tab.
Body / items / tag / kind are byte-identical; nothing new sends (🧪 still NEVER_SENDS; shadow still calls no sender).
NEGATIVES are the point: the 🧠 potential, 🔀 fade cross and 🥇 Luk pushes keep their titles and urls; a refused A+
sends nothing; an OLD shadow doc keeps its card url on /alerts.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC
from push import recent as R
from tests.test_gajjala_alerts import LABOR_DAY, Spy, at, fake_store, ledger, one, read, stamp
from tests.test_gajjala_alerts import S as SESSION

# frozen strings of tests/test_gajjala_alerts.py::test_the_body_is_the_entry_story_in_order (never retyped there)
OLD_BODY = ("broke 11.00 on the 5m bar closing 10:35 ET · stop 10.81 (−1.7%) · Kissed and honored the 9 EMA; entry = "
            "the kiss bar's high · 🧠 potential rang 10:05 ET · Float 3.2M · UNMEASURED — his setup, not a buy signal")
OLD_ITEM = ("GGA · 💋 EMA Kiss & Fly A+ entry · broke 11.00 · stop 10.81 (−1.7%) · Kissed and honored the 9 EMA; "
            "entry = the kiss bar's high")
WATCH_URL = "/chart-maps?tab=gajjala_watch&focus={sym}"


def _kiss(**kw):
    return AL.compose(read("kiss_fly", entry=stamp(10, 35)), "gga", {"float_text": "Float 3.2M"}, session=SESSION,
                      potential_at_et="10:05", **kw)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")


# ── the title ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_akan_squeeze_title_is_his_lock_screen_line():
    p = AL.compose(read("reversal_squeeze", trigger=2.0, stop=1.9), "akan", {}, session=SESSION)
    assert p["title"] == "🎯 A+ · AKAN · 🎾 Reversal Squeeze"


@pytest.mark.parametrize("setup", GC.SETUPS)
def test_every_setup_title_leads_with_the_aplus_lead(setup):
    emoji, label = AL.SETUP_META[setup]
    p = AL.compose(read(setup), "GGA", {}, session=SESSION)
    assert p["title"].startswith(AL.APLUS_TITLE_LEAD + " · ")
    assert p["title"].endswith(f"{emoji} {label}")
    assert "A+ entry" not in p["title"]                                   # the tail is dropped (HIS CALL #8)


def test_the_lead_is_the_watch_tag_word():
    from chart_maps.gajjala_watch import payload as PL
    assert AL.APLUS_TITLE_LEAD == PL.APLUS_TEXT == "🎯 A+"


def test_the_broker_flag_still_suffixes_the_title():
    from chart_maps.gajjala import tab as GT
    p = _kiss(broker_text=GT.BROKER_FLAG_TEXT)
    assert p["title"] == "🎯 A+ · GGA · 💋 EMA Kiss & Fly · 🚫"


# ── the url ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_url_is_the_watch_tab_on_the_name():
    p = AL.compose(read("reversal_squeeze"), "AKAN", {}, session=SESSION)
    assert p["url"] == f"/chart-maps?tab={WC.TAB}&focus=AKAN" == WATCH_URL.format(sym="AKAN")
    assert p["url"] == AL.ENTRY_URL.format(tab=WC.TAB, sym="AKAN")
    assert "sub=" not in p["url"] and WC.API_PATH not in p["url"] and "/chart-maps/gajjala" not in p["url"]


def test_gg1_same_title_and_url_its_own_kind_and_tag():
    r = read("bull_flag", frame="1m")
    g5 = AL.compose(r, "AKAN", {}, session=SESSION, variant=V.GG5)
    g1 = AL.compose(r, "AKAN", {}, session=SESSION, variant=V.GG1)
    assert g1["title"] == g5["title"] == "🎯 A+ · AKAN · 🚩 Bull Flag"
    assert g1["url"] == g5["url"]                                         # the Watch is one tab
    assert g1["kind"] == "gajjala_1m_setup" == V.GG1.push_kind_setup and g5["kind"] == "gajjala_setup"
    assert g1["tag"] == "gg1-bull_flag-AKAN" and g5["tag"] == "gg-bull_flag-AKAN"


def test_gga_shadow_record_carries_it_and_still_never_sends():
    from chart_maps.gajjala import audited_rules as AUD
    p = AL.compose(read("bull_flag"), "AKAN", {}, session=SESSION, variant=V.GGA)
    assert p["title"] == "🎯 A+ · AKAN · 🚩 Bull Flag" and p["url"] == WATCH_URL.format(sym="AKAN")
    with pytest.raises(RuntimeError) as e:                                # NEGATIVE: nothing new sends
        AL._default_send("owner@example.com", p, variant=V.GGA)
    assert str(e.value) == AUD.NEVER_SENDS


def test_alerts_item_url_of_both_aplus_kinds_is_the_push_url():
    for kind in ("gajjala_setup", "gajjala_1m_setup"):
        assert R.ITEM_URL_BY_KIND[kind] == AL.ENTRY_URL.format(tab=WC.TAB, sym="{sym}")
        assert R.item_url(kind, "NVDA") == AL.ENTRY_URL.format(tab=WC.TAB, sym="NVDA")


# ── NEGATIVES: byte-identical bits ──────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_body_items_tag_kind_are_byte_identical():
    p = _kiss()
    assert p["body"] == OLD_BODY
    assert p["items"] == [{"symbol": "GGA", "text": OLD_ITEM}]
    assert p["tag"] == "gg-kiss_fly-GGA" and p["kind"] == "gajjala_setup" and p["ticker"] == "GGA"


def test_NEGATIVE_potential_push_url_keeps_the_card():
    assert PT.deep_link("akan", "reversal_squeeze") == "/chart-maps?tab=gajjala&sub=reversal_squeeze&focus=AKAN"
    assert PT.deep_link("akan", "bull_flag", V.GG1) == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=AKAN"


def test_NEGATIVE_other_alerts_item_urls_unchanged():
    assert R.ITEM_URL_BY_KIND["gajjala_potential"] == "/chart-maps?tab=gajjala&focus={sym}"
    assert R.ITEM_URL_BY_KIND["gajjala_1m_potential"] == "/chart-maps?tab=gajjala_1m&focus={sym}"
    assert R.ITEM_URL_BY_KIND["luk_setup"] == "/chart-maps?tab=luk&focus={sym}"
    assert len(R.ITEM_KINDS) == 18


def test_NEGATIVE_fade_cross_keeps_its_title_and_card_url():
    p = AL.fade_cross_compose("gga", "horizontal_fade", {"ts": stamp(10, 35), "close": 11.0}, "15m")
    assert p["url"] == "/chart-maps?tab=gajjala&sub=horizontal_fade&focus=GGA"
    assert p["title"].startswith("🔀 GGA · ") and AL.APLUS_TITLE_LEAD not in p["title"]


def test_NEGATIVE_luk_title_unchanged():
    from chart_maps.luk import alerts as LA
    from chart_maps.luk import constants as LC
    setup = LC.SETUPS[0]
    p = LA.compose({"setup": setup, "trigger": 11.0, "stop": 10.5, "entry_bar_t": stamp(10, 35)}, "gga", {})
    assert p["title"].startswith("🥇 GGA · ") and p["title"].endswith(" A+ entry")
    assert p["url"] == f"/chart-maps?tab=luk&sub={setup}&focus=GGA"


# ── NEGATIVES: refusals send nothing ────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("entry,now,session,key", [
    (stamp(8, 0), at(8, 1), SESSION, "suppressed_premarket"),
    (stamp(9, 35), at(9, 36), SESSION, "suppressed_first15"),
    (stamp(10, 5, LABOR_DAY), at(10, 6, LABOR_DAY), LABOR_DAY, "suppressed_closed"),
])
def test_NEGATIVE_refused_aplus_sends_nothing(live, entry, now, session, key):
    counts, send = one(fake_store(), read(entry=entry), now=now, session=session)
    assert counts[key] == 1 and counts["pushed"] == 0 and send.calls == []


def test_NEGATIVE_claimed_before_sends_nothing_the_second_time(live):
    st = fake_store()
    send = Spy()
    one(st, read(entry=stamp(10, 5)), send=send)
    assert len(send.calls) == 1 and send.calls[0][1]["title"] == "🎯 A+ · GGA · 🚩 Bull Flag"
    counts, _ = one(st, read(entry=stamp(11, 30)), now=at(11, 31), send=send)
    assert counts["claimed_before"] == 1 and len(send.calls) == 1


def test_shadow_records_the_new_title_and_calls_no_sender(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")
    st = fake_store()
    counts, send = one(st, read())
    assert send.calls == [] and counts["shadow"] == 1
    wp = ledger(st)["SHADOW:GG:2026-10-13|GGA|bull_flag"]["would_push"]
    assert wp["title"].startswith(AL.APLUS_TITLE_LEAD + " · ") and wp["url"] == WATCH_URL.format(sym="GGA")


def test_NEGATIVE_an_old_shadow_doc_keeps_its_card_url_on_alerts():
    from supply_demand import alert_status as AS
    from tests.test_alert_status import NOW, LedgerColl, _gg
    items = AS.read_gajjala_shadow(LedgerColl([_gg("GGA", "bull_flag")]), NOW)
    assert items[0]["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA"
