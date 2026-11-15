"""🌫️ Day read — GD7's QQQ / IWM warm (Ajay 2026-11-15 "Yes" to turning it on): after 10:30 ET on the live session,
chart_maps/gajjala/day_read.warm_index fetches each symbol ONCE (stored in gajjala_state "day_read_index"), cuts it with
the probe's own filter, and feeds the lib. NEGATIVE cases: before 10:30, another session, a cache hit, a failed / short
fetch, no store."""
from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

from chart_maps.gajjala import day_read as DR
from scripts import shadow_day_tags_lib as LIB
from scripts import shadow_day_tags_probe as PR

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
SESS = "2026-11-16"
D = date.fromisoformat(SESS)


def et_at(h, m):
    return datetime.combine(D, dtime(h, m), tzinfo=ET)


def bars(open_, close_, last_hm=(10, 29), premarket=True):
    """intraday_cache-shaped bars, naive UTC ts like _mongo_put_day: an 09:00 pre-market bar, rth 09:30 → last_hm, one
    10:30 bar (outside the cut)."""
    out = []
    def add(h, m, px, sess):
        t = et_at(h, m).astimezone(UTC).replace(tzinfo=None)
        out.append({"ts_utc": t.isoformat(), "open": px, "high": px, "low": px, "close": px, "volume": 1.0,
                    "session": sess})
    if premarket:
        add(9, 0, open_ * 2, "premarket")
    t = et_at(9, 30)
    end = et_at(*last_hm)
    while t <= end:
        add(t.hour, t.minute, open_ if t == et_at(9, 30) else close_, "rth")
        t += timedelta(minutes=1)
    add(10, 30, close_ * 3, "rth")
    return out


class Store:
    def __init__(self):
        self.d = {}
        self.writes = 0

    def get_state(self, k):
        return self.d.get(k)

    def set_state(self, k, v):
        self.writes += 1
        self.d[k] = v


class Fetch:
    def __init__(self, by_sym):
        self.by_sym, self.calls = by_sym, []

    def __call__(self, sym, session):
        self.calls.append((sym, session))
        return self.by_sym.get(sym, [])


CONST = {"T2_FIRST_HOUR_END_ET": "10:30", "GG_LOSS_RISK_CUT": 0.5}


def blank():
    return {"index_intraday": {f"QQQ|{SESS}": None, f"IWM|{SESS}": None},
            "asof": {"qqq_last_date": "2026-11-13", "iwm_last_date": "2026-11-13"}}



def test_after_1030_fetches_each_symbol_once_and_gd7_reads():
    st, f = Store(), Fetch({"QQQ": bars(100, 99), "IWM": bars(200, 198)})
    inp = DR.warm_index(st, blank(), et_at(10, 31), D, fetch=f)
    assert sorted(s for s, _ in f.calls) == ["IWM", "QQQ"]
    q = inp["index_intraday"][f"QQQ|{SESS}"]
    assert q == PR.cut_bars(bars(100, 99), SESS)
    assert all(b[6] == "rth" for b in q) and q[-1][4] == 99            # the 10:30 bar and pre-market are cut
    assert inp["asof"]["qqq_last_date"] == SESS and inp["asof"]["iwm_last_date"] == SESS
    assert st.d[DR.WARM_ID]["session"] == SESS and st.writes == 1
    tags = LIB.compute(dict(inp, sessions=[SESS], constants=CONST), SESS)
    t = tags["GD7_by1030"]
    assert t["status"] == "ok" and t["on"] is True, t
    assert t["value"] == "QQQ -1.00% IWM -1.00%"


def test_second_pass_reads_the_stored_copy_no_fetch():
    st = Store()
    DR.warm_index(st, blank(), et_at(10, 31), D, fetch=Fetch({"QQQ": bars(100, 101), "IWM": bars(200, 202)}))
    f2 = Fetch({"QQQ": bars(1, 1), "IWM": bars(1, 1)})
    inp = DR.warm_index(st, blank(), et_at(11, 0), D, fetch=f2)
    assert f2.calls == [] and st.writes == 1
    assert inp["index_intraday"][f"QQQ|{SESS}"][-1][4] == 101


def test_NEGATIVE_before_1030_nothing_fetched():
    st, f = Store(), Fetch({"QQQ": bars(100, 99), "IWM": bars(200, 198)})
    inp = DR.warm_index(st, blank(), et_at(10, 29), D, fetch=f)
    assert f.calls == [] and st.writes == 0 and inp["index_intraday"][f"QQQ|{SESS}"] is None


def test_NEGATIVE_not_today_nothing_fetched():
    st, f = Store(), Fetch({"QQQ": bars(100, 99), "IWM": bars(200, 198)})
    nxt = datetime.combine(D + timedelta(days=1), dtime(11, 0), tzinfo=ET)
    DR.warm_index(st, blank(), nxt, D, fetch=f)
    assert f.calls == [] and st.writes == 0


def test_NEGATIVE_cache_hit_no_fetch():
    st, f = Store(), Fetch({"QQQ": bars(100, 99), "IWM": bars(200, 198)})
    inp = blank()
    inp["index_intraday"] = {f"QQQ|{SESS}": [["x"]], f"IWM|{SESS}": [["y"]]}
    DR.warm_index(st, inp, et_at(11, 0), D, fetch=f)
    assert f.calls == [] and st.writes == 0 and inp["asof"]["qqq_last_date"] == "2026-11-13"


def test_NEGATIVE_failed_or_short_fetch_is_not_stored_and_retried():
    st = Store()
    f = Fetch({"QQQ": [], "IWM": bars(200, 198, last_hm=(10, 20))})
    inp = DR.warm_index(st, blank(), et_at(10, 31), D, fetch=f)
    assert st.writes == 0 and inp["index_intraday"][f"QQQ|{SESS}"] is None
    assert inp["index_intraday"][f"IWM|{SESS}"] is None and inp["asof"]["iwm_last_date"] == "2026-11-13"
    tags = LIB.compute(dict(inp, sessions=[SESS], constants=CONST), SESS)
    assert tags["GD7_by1030"]["status"] == "missing"
    f2 = Fetch({"QQQ": bars(100, 99), "IWM": bars(200, 198)})
    DR.warm_index(st, blank(), et_at(10, 36), D, fetch=f2)
    assert len(f2.calls) == 2 and st.writes == 1


def test_NEGATIVE_one_symbol_stored_other_retried_alone():
    st = Store()
    DR.warm_index(st, blank(), et_at(10, 31), D, fetch=Fetch({"QQQ": bars(100, 99)}))
    assert set(st.d[DR.WARM_ID]["bars"]) == {"QQQ"}
    f2 = Fetch({"QQQ": bars(1, 1), "IWM": bars(200, 198)})
    DR.warm_index(st, blank(), et_at(10, 36), D, fetch=f2)
    assert [s for s, _ in f2.calls] == ["IWM"]
    assert set(st.d[DR.WARM_ID]["bars"]) == {"QQQ", "IWM"}


def test_NEGATIVE_no_store_no_fetch():
    f = Fetch({"QQQ": bars(100, 99), "IWM": bars(200, 198)})
    inp = DR.warm_index(None, blank(), et_at(11, 0), D, fetch=f)
    assert f.calls == [] and inp["index_intraday"][f"QQQ|{SESS}"] is None


def test_NEGATIVE_yesterdays_stored_copy_is_ignored():
    st = Store()
    st.d[DR.WARM_ID] = {"session": "2026-11-13", "bars": {"QQQ": [["old"]], "IWM": [["old"]]}}
    f = Fetch({"QQQ": bars(100, 99), "IWM": bars(200, 198)})
    inp = DR.warm_index(st, blank(), et_at(10, 31), D, fetch=f)
    assert len(f.calls) == 2 and inp["index_intraday"][f"QQQ|{SESS}"] != [["old"]]


def test_cut_bars_is_index_intradays_filter():
    class Coll:
        def find_one(self, q, proj):
            return {"bars": bars(100, 99)} if q["symbol"] == "QQQ" else None

    class Db:
        intraday_cache = Coll()
    out = PR.index_intraday(Db(), [SESS])
    assert out[f"QQQ|{SESS}"] == PR.cut_bars(bars(100, 99), SESS) and out[f"IWM|{SESS}"] is None


def test_the_recorder_never_reads_the_warm_doc():
    src = (PR.__file__ and open(PR.__file__).read())
    assert "day_read_index" not in src and "WARM_ID" not in src


def test_NEGATIVE_a_raising_fetch_never_stops_the_other_symbol_or_the_read():
    st = Store()

    def boom(sym, session):
        if sym == "QQQ":
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return bars(200, 198)
    inp = DR.warm_index(st, blank(), et_at(10, 31), D, fetch=boom)
    assert inp["index_intraday"][f"QQQ|{SESS}"] is None
    assert inp["index_intraday"][f"IWM|{SESS}"] == PR.cut_bars(bars(200, 198), SESS)
    assert set(st.d[DR.WARM_ID]["bars"]) == {"IWM"}
    tags = LIB.compute(dict(inp, sessions=[SESS], constants=CONST), SESS)
    assert tags["GD7_by1030"]["status"] == "missing"
