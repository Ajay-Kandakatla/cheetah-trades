"""Every item of a consolidated push — END TO END on the real chain (2026-09-29).

Ajay, on "⚡ Tape burst at a zone — CRWV +7 more": "I am unable to see the
other that are hiddedn her … Can you show them all and make all the tickers
clicable individually?"

The real trade_flash.record_and_push -> the real push.sender.send_to_user ->
the real push.history.record / list_recent -> the real push.recent.gather.
Only the edges are faked: the events store, the subscription list, the device
send and the push_history collection. Pinned: the DEVICE payload never carries
`items` (Web Push ~4 KB ceiling; the phone is unchanged), the HISTORY row does,
and /alerts serves every burst.

Hermetic: no Mongo, no network.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import trade_flash as TF   # noqa: E402
from push import history as H             # noqa: E402
from push import recent as R              # noqa: E402
from push import sender as S              # noqa: E402

SYMS = ["CRWV", "KLAC", "NVDA", "AVGO", "CRWV", "BRK.B", "PCT", "KLAC"]
KNOWN = frozenset({"CRWV", "KLAC", "NVDA", "AVGO", "BRK.B", "PCT"})


class _Res:
    def __init__(self, upserted):
        self.upserted_id = upserted


class _EventsColl:
    def __init__(self):
        self.seen = set()

    def update_one(self, flt, update, upsert=False):
        _id = flt["_id"]
        if _id in self.seen:
            return _Res(None)
        self.seen.add(_id)
        return _Res(_id)


class _EventsDB:
    def __init__(self):
        self.coll = _EventsColl()

    def __getitem__(self, name):
        assert name == TF.EVENTS_COLL
        return self.coll


class _Cur:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        self.docs = sorted(self.docs, key=lambda d: d.get(key) or 0, reverse=direction < 0)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(self.docs)


class _HistColl:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        doc = dict(doc)
        doc["_id"] = f"h{len(self.docs)}"
        self.docs.append(doc)

    def find(self, q):
        return _Cur([dict(d) for d in self.docs])


def _events(n):
    out = []
    for i, sym in enumerate(SYMS[:n]):
        out.append({"_id": f"{sym}:2026-09-29:13:{10 + i:02d}:00", "symbol": sym,
                    "et_date": "2026-09-29", "time_et": f"13:{10 + i:02d}:00",
                    "side": "buy" if i % 2 else "sell", "dollars": 2_000_000.0 - i * 150_000,
                    "board": "supply", "recorded_at": 1_790_700_000 + i})
    return out


@pytest.fixture
def chain(monkeypatch):
    from market_hours import gate
    from push import subs
    device, hist = [], _HistColl()
    monkeypatch.setattr(TF, "_db", lambda: _EventsDB())
    monkeypatch.setattr(gate, "should_drop_kind", lambda *a, **k: None)
    monkeypatch.setattr(subs, "list_subscriptions",
                        lambda *a, **k: [{"endpoint": "e1", "keys": {}}])
    monkeypatch.setattr(S, "_send_one", lambda sub, payload: device.append(payload) or True)
    monkeypatch.setattr(H, "_get_coll", lambda: hist)
    monkeypatch.setattr(R, "known_symbols", lambda *a, **k: KNOWN)
    return device, hist


def _serve():
    return R.gather("ajay@x", 50, list_recent=H.list_recent, get_db=lambda: None)


def test_eight_bursts_phone_gets_four_lines_alerts_gets_all_eight(chain):
    device, hist = chain
    evs = _events(8)
    out = TF.record_and_push(evs)
    assert out["new"] == 8 and out["pushed"] is True

    # 3. the DEVICE payload: the pre-change keys only, body <= 4 lines
    assert len(device) == 1
    d = device[0]
    assert set(d) == {"title", "body", "url", "kind"}, "items must never reach the phone"
    assert len(d["body"].split("\n")) <= TF.PUSH_BODY_LINES == 4
    assert d["title"] == "⚡ Tape burst at a zone — CRWV +7 more"

    # 4. the HISTORY row: all 8, in body (dollars-desc) order
    [doc] = hist.docs
    assert len(doc["items"]) == 8 and doc["items_total"] == 8
    assert [it["symbol"] for it in doc["items"]] == SYMS
    assert [it["text"] for it in doc["items"]] == [TF.headline(e) for e in evs]
    assert doc["body"] == d["body"], "the stored body is the phone's body"

    # 5-6. served on /alerts
    [row] = _serve()
    items = row["items"]
    assert len(items) == 8
    assert [e["pushed"] for e in items] == [True] * 4 + [False] * 4
    assert [e["symbol"] for e in items] == SYMS
    assert all(e["url"] == TF.tape_url(e["symbol"]) for e in items)
    assert row["items_not_stored"] == 0
    assert "items_total" not in row


def test_NEGATIVE_one_burst_is_one_item_and_nothing_off_push(chain):
    device, hist = chain
    TF.record_and_push(_events(1))
    d = device[0]
    assert "items" not in d and set(d) == {"title", "body", "url", "kind"}
    assert "more" not in d["title"]
    [doc] = hist.docs
    assert len(doc["items"]) == 1 and doc["items_total"] == 1
    [row] = _serve()
    assert len(row["items"]) == 1
    assert all(e["pushed"] for e in row["items"]), "no off-push entries"
    assert row["items_not_stored"] == 0


def test_NEGATIVE_zero_fresh_bursts_push_and_log_nothing(chain):
    device, hist = chain
    out = TF.record_and_push([])
    assert out["new"] == 0 and out["pushed"] is False
    assert device == [] and hist.docs == []
    assert _serve() == []
