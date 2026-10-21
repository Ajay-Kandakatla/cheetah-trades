"""📬 Push delivery receipts (2026-10-21) — push/receipts.py, the sender stamp,
the history fields, the served `shown_on`, the main.py wiring.

Ajay 2026-10-21, on the 15:36:15 ET 🚩 gajjala_setup NIXX push that push_history
recorded as sent 3 / failed 0: "Oh man I did not get an A+ alert for it then
today"; on the two 🧠 potentials around it: "Yes POLA reached and SAIQ too".
``sent`` is the push service's acceptance; the receipt is the device's screen.

Hermetic: hand-written fakes for push_subscriptions and push_history, the
device send stubbed, one TestClient over the router. No Mongo, no network.
"""
import json
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[2]

from push import history as H     # noqa: E402
from push import receipts as RC   # noqa: E402
from push import recent as R      # noqa: E402
from push import sender as S      # noqa: E402

IPHONE_UA = ("Pounce · Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.7 Mobile/15E148 Safari/604.1")
MAC_UA = ("Pounce · Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
EP_IPHONE = "https://web.push.apple.com/QAbcdef0123456789"
EP_MAC1 = "https://fcm.googleapis.com/fcm/send/aaa111"
EP_MAC2 = "https://fcm.googleapis.com/fcm/send/bbb222"
EP_OTHER = "https://fcm.googleapis.com/fcm/send/other-user"


def sha1(s):
    return hashlib.sha1(s.encode()).hexdigest()


# ── fakes ────────────────────────────────────────────────────────────────────
def _match(row, q):
    return all(row.get(k) == v for k, v in q.items())


class _Res:
    def __init__(self, matched):
        self.matched_count = matched


class FakeSubs:
    def __init__(self, rows):
        self.rows = rows

    def find_one(self, q, proj=None):
        for r in self.rows:
            if _match(r, q):
                return dict(r)
        return None


class FakeDB:
    def __init__(self, rows):
        self.push_subscriptions = FakeSubs(rows)


class FakeHist:
    def __init__(self, rows=None):
        self.rows = rows or []

    def find_one(self, q, proj=None):
        for r in self.rows:
            if _match(r, q):
                return dict(r)
        return None

    def update_one(self, q, u):
        pid, h = q["push_id"], q["receipts.sub"]["$ne"]
        for r in self.rows:
            if r.get("push_id") == pid and all(x.get("sub") != h for x in (r.get("receipts") or [])):
                r.setdefault("receipts", []).append(dict(u["$push"]["receipts"]))
                return _Res(1)
        return _Res(0)

    def insert_one(self, doc):
        doc = dict(doc)
        doc["_id"] = f"h{len(self.rows)}"
        self.rows.append(doc)


def _subs():
    return [
        {"endpoint": EP_MAC1, "label": MAC_UA, "user_email": "a@x", "keys": {"p256dh": "k", "auth": "a"}},
        {"endpoint": EP_MAC2, "label": MAC_UA, "user_email": "a@x", "keys": {"p256dh": "k", "auth": "a"}},
        {"endpoint": EP_IPHONE, "label": IPHONE_UA, "user_email": "a@x", "keys": {"p256dh": "k", "auth": "a"}},
        {"endpoint": EP_OTHER, "label": MAC_UA, "user_email": "b@x", "keys": {"p256dh": "k", "auth": "a"}},
        {"endpoint": "mac:dev-1", "label": "Mac app", "user_email": "a@x", "kind": "mac"},
    ]


def _targets(oks=(True, True, True)):
    return RC.targets_of(_subs()[:3], list(oks))


def _row(pid, user, **kw):
    r = {"push_id": pid, "user_email": user, "kind": "gajjala_setup", "ticker": "NIXX",
         "title": "🚩 NIXX A+", "body": "b", "ts": 1_792_000_000, "ts_iso": None, "url": "/u",
         "sent": 3, "failed": 0, "total": 3, "targets": _targets()}
    r.update(kw)
    return r


# ── the hash and the device word ─────────────────────────────────────────────
def test_endpoint_hash_is_sha1_hex_and_never_the_endpoint():
    h = RC.endpoint_hash(EP_IPHONE)
    assert h == sha1(EP_IPHONE) and len(h) == 40
    assert EP_IPHONE not in h and "apple" not in h


@pytest.mark.parametrize("label, word", [
    (IPHONE_UA, "iPhone Safari"),
    (MAC_UA, "Mac Chrome"),
    ("Pounce · Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Vers", "iPhone"),
    ("Pounce · Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36", "Android Chrome"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Edg/130.0", "Windows Edge"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/130.0 Mobile/15E148 Safari/605.1.15", "iPhone Firefox"),
    ("device", "device"),
    ("", "device"),
    (None, "device"),
    ("Pounce · service worker · rotated", "device"),
    ("Kitchen iPad", "iPad"),
    ("my desk", "my desk"),
    ("a custom label that runs on and on past the cap", "a custom label that runs"),
])
def test_device_word(label, word):
    assert RC.device_word(label) == word


def test_targets_of_keeps_hash_word_and_acceptance_only():
    t = RC.targets_of(_subs()[:3], [True, False, True])
    assert t == [{"sub": sha1(EP_MAC1), "device": "Mac Chrome", "ok": True},
                 {"sub": sha1(EP_MAC2), "device": "Mac Chrome", "ok": False},
                 {"sub": sha1(EP_IPHONE), "device": "iPhone Safari", "ok": True}]
    dumped = json.dumps(t)
    assert "fcm.googleapis.com" not in dumped and "apple.com" not in dumped and "p256dh" not in dumped


# ── the sender stamp ─────────────────────────────────────────────────────────
@pytest.fixture
def push_stack(monkeypatch):
    from market_hours import gate
    from push import subs
    sent, recorded = [], []
    monkeypatch.setattr(gate, "should_drop_kind", lambda *a, **k: None)
    monkeypatch.setattr(subs, "list_subscriptions", lambda *a, **k: [dict(s) for s in _subs()[:3]])
    monkeypatch.setattr(S, "_send_one", lambda sub, payload: sent.append(payload) or True)
    monkeypatch.setattr(H, "record", lambda payload, **k: recorded.append((payload, k)))
    return sent, recorded


@pytest.mark.parametrize("path", ["user", "all"])
def test_sender_stamps_one_push_id_on_every_device_payload_and_the_history_row(push_stack, path):
    sent, recorded = push_stack
    p = {"title": "🚩 NIXX A+", "body": "b", "url": "/u", "kind": "gajjala_setup", "items": [{"symbol": "NIXX", "text": "x"}]}
    out = S.send_to_user("a@x", p, kind="gajjala_setup") if path == "user" else S.send_to_all(p, kind="gajjala_setup")
    assert out == {"sent": 3, "failed": 0, "total_targets": 3}
    ids = {d["push_id"] for d in sent}
    assert len(sent) == 3 and len(ids) == 1
    pid = ids.pop()
    assert isinstance(pid, str) and len(pid) == 32
    assert all("items" not in d for d in sent), "LOG_ONLY_KEYS still stripped"
    [(payload, kw)] = recorded
    assert kw["push_id"] == pid, "the history row carries the SAME id the devices got"
    assert kw["targets"] == _targets()
    # NEGATIVE: the caller's dict (what history records) is never mutated.
    assert payload is p and "push_id" not in p and "items" in p


def test_sender_ids_differ_per_send_and_targets_record_acceptance(push_stack, monkeypatch):
    sent, recorded = push_stack
    p = {"title": "t", "body": "b", "url": "/u", "kind": "gajjala_setup"}
    S.send_to_user("a@x", p, kind="gajjala_setup")
    S.send_to_user("a@x", p, kind="gajjala_setup")
    assert recorded[0][1]["push_id"] != recorded[1][1]["push_id"]
    # the second Mac rejects: ok False on its target, counts unchanged in meaning
    monkeypatch.setattr(S, "_send_one", lambda sub, payload: sub["endpoint"] != EP_MAC2)
    out = S.send_to_user("a@x", p, kind="gajjala_setup")
    assert out == {"sent": 2, "failed": 1, "total_targets": 3}
    assert [t["ok"] for t in recorded[2][1]["targets"]] == [True, False, True]


# ── the history fields ───────────────────────────────────────────────────────
@pytest.fixture
def hist(monkeypatch):
    h = FakeHist()
    monkeypatch.setattr(H, "_coll", h)
    monkeypatch.setattr(H, "_disabled", False)
    return h


def test_history_stores_push_id_and_targets_when_given(hist):
    H.record({"title": "t", "kind": "gajjala_setup"}, user_email="a@x",
             result={"sent": 3, "failed": 0, "total_targets": 3},
             push_id="abc", targets=_targets() + ["not-a-dict"])
    [doc] = hist.rows
    assert doc["push_id"] == "abc" and doc["targets"] == _targets()
    assert "receipts" not in doc, "no receipt until a device reports"
    assert (doc["sent"], doc["failed"], doc["total"]) == (3, 0, 3)


def test_NEGATIVE_legacy_record_call_stores_neither_key(hist):
    H.record({"title": "t", "kind": "demand_alert"}, user_email=None, result={"sent": 1, "failed": 0, "total_targets": 1})
    [doc] = hist.rows
    assert "push_id" not in doc and "targets" not in doc and "receipts" not in doc


def test_history_index_on_push_id_is_sparse():
    src = (ROOT / "backend/push/history.py").read_text()
    assert 'create_index("push_id", sparse=True)' in src


# ── the receipt route ────────────────────────────────────────────────────────
@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    db = FakeDB(_subs())
    hist = FakeHist([_row("pid-broadcast", None), _row("pid-a", "a@x"),
                     {"_id": "legacy", "kind": "demand_alert", "sent": 2, "failed": 0, "total": 2}])
    monkeypatch.setattr(RC, "_subs_db", lambda: db)
    monkeypatch.setattr(RC, "_hist_coll", lambda: hist)
    app = FastAPI()
    app.include_router(RC.router)
    return TestClient(app), hist


def _post(c, **body):
    return c.post("/push/receipt", json=body)


def test_known_device_known_push_appends_one_receipt_idempotently(client):
    c, hist = client
    r = _post(c, push_id="pid-a", endpoint=EP_IPHONE, shown_at=1_792_000_123_456)   # Date.now() ms
    assert r.status_code == 200 and r.json() == {"ok": True, "dup": False}
    row = hist.find_one({"push_id": "pid-a"})
    [rc] = row["receipts"]
    assert rc["sub"] == sha1(EP_IPHONE) and rc["device"] == "iPhone Safari"
    assert rc["shown_at"] == 1_792_000_123 and isinstance(rc["at"], int)
    assert EP_IPHONE not in json.dumps(row), "the endpoint is never stored"
    # the same device again: counted once
    r = _post(c, push_id="pid-a", endpoint=EP_IPHONE, shown_at=1_792_000_200_000)
    assert r.status_code == 200 and r.json() == {"ok": True, "dup": True}
    assert len(hist.find_one({"push_id": "pid-a"})["receipts"]) == 1
    # another device: appended
    r = _post(c, push_id="pid-a", endpoint=EP_MAC1)
    assert r.status_code == 200 and r.json()["dup"] is False
    rcs = hist.find_one({"push_id": "pid-a"})["receipts"]
    assert [x["device"] for x in rcs] == ["iPhone Safari", "Mac Chrome"] and rcs[1]["shown_at"] is None


def test_unknown_endpoint_unknown_push_and_another_users_row_all_answer_404(client):
    c, hist = client
    assert _post(c, push_id="pid-a", endpoint="https://fcm.googleapis.com/fcm/send/nope").status_code == 404
    assert _post(c, push_id="no-such-push", endpoint=EP_IPHONE).status_code == 404
    assert _post(c, push_id="pid-a", endpoint=EP_OTHER).status_code == 404, "b@x never touches a@x's row"
    assert _post(c, push_id="pid-a", endpoint="mac:dev-1").status_code == 400, "a mac row has no https endpoint"
    assert "receipts" not in hist.find_one({"push_id": "pid-a"})
    # one body for all three refusals — nothing says which
    bodies = {_post(c, push_id=p, endpoint=e).json()["reason"]
              for p, e in [("pid-a", "https://x.example/nope"), ("zzz", EP_IPHONE), ("pid-a", EP_OTHER)]}
    assert bodies == {"unknown"}


def test_a_broadcast_row_takes_any_registered_users_receipt(client):
    c, hist = client
    assert _post(c, push_id="pid-broadcast", endpoint=EP_OTHER).status_code == 200
    assert hist.find_one({"push_id": "pid-broadcast"})["receipts"][0]["sub"] == sha1(EP_OTHER)


@pytest.mark.parametrize("body", [
    {"endpoint": EP_IPHONE},                                   # no push_id
    {"push_id": "", "endpoint": EP_IPHONE},
    {"push_id": "x" * 65, "endpoint": EP_IPHONE},
    {"push_id": "pid-a"},                                      # no endpoint
    {"push_id": "pid-a", "endpoint": "http://insecure.example/x"},
    {"push_id": "pid-a", "endpoint": "https://" + "x" * 2050},
    {"push_id": ["pid-a"], "endpoint": EP_IPHONE},
])
def test_malformed_bodies_are_400(client, body):
    c, hist = client
    assert c.post("/push/receipt", json=body).status_code == 400
    assert "receipts" not in hist.find_one({"push_id": "pid-a"})


def test_NEGATIVE_a_receipt_never_changes_sent_failed_total(client):
    c, hist = client
    before = {r.get("push_id") or r["_id"]: (r["sent"], r["failed"], r["total"]) for r in hist.rows}
    for ep in (EP_IPHONE, EP_MAC1, EP_MAC2, EP_OTHER, "https://x.example/nope"):
        for pid in ("pid-a", "pid-broadcast", "nope"):
            _post(c, push_id=pid, endpoint=ep)
    after = {r.get("push_id") or r["_id"]: (r["sent"], r["failed"], r["total"]) for r in hist.rows}
    assert after == before
    assert "receipts" not in hist.rows[2], "a legacy row (no push_id) can never take a receipt"


def test_store_unavailable_is_503_not_a_crash(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setattr(RC, "_subs_db", lambda: None)
    monkeypatch.setattr(RC, "_hist_coll", lambda: FakeHist())
    app = FastAPI()
    app.include_router(RC.router)
    r = TestClient(app).post("/push/receipt", json={"push_id": "pid-a", "endpoint": EP_IPHONE})
    assert r.status_code == 503


def test_route_takes_no_auth_dependency_and_is_on_the_public_allowlist():
    """The SW runs with the page closed and maybe no session cookie — the endpoint is the credential."""
    import inspect
    assert RC.RECEIPT_PATH == "/push/receipt"
    assert "current_user_email" not in inspect.getsource(RC)
    src = (ROOT / "backend/main.py").read_text()
    block = src[src.index("_PUBLIC_API_PATHS = {"):]
    block = block[:block.index("}")]
    assert '"/push/receipt",' in block
    assert "from push.receipts import router as push_receipts_router" in src
    assert "app.include_router(push_receipts_router)" in src


# ── shown_on: the served sentence ────────────────────────────────────────────
def _rc(ep, device):
    return {"sub": sha1(ep), "device": device, "shown_at": 1, "at": 2}


def test_shown_on_two_of_three_names_the_shown_and_the_silent_device():
    row = _row("p", "a@x", receipts=[_rc(EP_MAC1, "Mac Chrome"), _rc(EP_MAC2, "Mac Chrome")])
    out = RC.shown_on(row)
    assert out == {"shown": 2, "total": 3, "devices": ["Mac Chrome", "Mac Chrome"], "missing": ["iPhone Safari"],
                   "text": "shown on 2 of 3 devices (Mac Chrome ×2); no receipt from iPhone Safari"}


def test_shown_on_all_three_has_no_missing_tail_and_none_shown_names_every_target():
    row = _row("p", "a@x", receipts=[_rc(EP_MAC1, "Mac Chrome"), _rc(EP_MAC2, "Mac Chrome"), _rc(EP_IPHONE, "iPhone Safari")])
    assert RC.shown_on(row)["text"] == "shown on 3 of 3 devices (Mac Chrome ×2, iPhone Safari)"
    assert RC.shown_on(_row("p", "a@x"))["text"] == "shown on 0 of 3 devices; no receipt from Mac Chrome ×2, iPhone Safari"


def test_shown_on_singular_device_and_a_rejected_target_is_never_missing():
    row = _row("p", "a@x", sent=1, failed=0, total=1, targets=RC.targets_of(_subs()[2:3], [True]))
    assert RC.shown_on(row)["text"] == "shown on 0 of 1 device; no receipt from iPhone Safari"
    # NEGATIVE: a device the push service REJECTED (ok False) cannot show it — not "no receipt"
    row = _row("p", "a@x", sent=2, failed=1, total=3, targets=RC.targets_of(_subs()[:3], [True, False, True]),
               receipts=[_rc(EP_MAC1, "Mac Chrome"), _rc(EP_IPHONE, "iPhone Safari")])
    assert RC.shown_on(row)["text"] == "shown on 2 of 3 devices (Mac Chrome, iPhone Safari)"


def test_NEGATIVE_shown_on_is_none_before_receipts_and_when_nobody_was_targeted():
    assert RC.shown_on({"_id": "legacy", "sent": 3, "failed": 0, "total": 3}) is None
    assert RC.shown_on(_row("p", "a@x", sent=0, failed=0, total=0, targets=[])) is None
    assert RC.shown_on(None) is None


# ── /notifications/recent serves shown_on and strips the hashes ──────────────
def test_recent_serves_shown_on_and_never_the_hashes(monkeypatch):
    monkeypatch.setattr(R, "known_symbols", lambda *a, **k: frozenset({"NIXX"}))
    rows = [_row("p1", "a@x", _id="n1", receipts=[_rc(EP_MAC1, "Mac Chrome"), _rc(EP_MAC2, "Mac Chrome")]),
            {"_id": "legacy", "ts": 1_791_000_000, "ts_iso": None, "kind": "demand_alert", "ticker": "NIXX",
             "title": "t", "body": "b", "url": "/u", "user_email": None, "sent": 2, "failed": 0, "total": 2}]
    served = R.gather("a@x", 10, list_recent=lambda *a, **k: [dict(r) for r in rows], get_db=lambda: None)
    assert [r["_id"] for r in served] == ["n1", "legacy"]
    assert served[0]["shown_on"]["text"] == "shown on 2 of 3 devices (Mac Chrome ×2); no receipt from iPhone Safari"
    assert served[1]["shown_on"] is None
    dumped = json.dumps(served, default=str)
    for secret in (sha1(EP_MAC1), sha1(EP_MAC2), sha1(EP_IPHONE), "receipts", "targets", "push_id"):
        assert secret not in dumped, secret
    # NEGATIVE: sent / failed / total are served as stored
    assert (served[0]["sent"], served[0]["failed"], served[0]["total"]) == (3, 0, 3)


# ── the service worker echoes the id after the notification is on screen ─────
def test_service_worker_posts_the_receipt_after_show_notification():
    sw = (ROOT / "frontend/public/sw.js").read_text()
    assert "/push/receipt" in sw and "function receiptBody(" in sw and "async function sendReceipt(" in sw
    show = sw.index("self.registration.showNotification(title, options)")
    assert ".then(() => sendReceipt(payload)" in sw[show:show + 200], "the receipt follows the shown notification"
    body = sw[sw.index("function receiptBody("):]
    body = body[:body.index("\n}\n")]
    assert "push_id" in body and "endpoint" in body and "shown_at" in body
    assert "keys" not in body and "title" not in body, "a receipt carries no key and no content"
