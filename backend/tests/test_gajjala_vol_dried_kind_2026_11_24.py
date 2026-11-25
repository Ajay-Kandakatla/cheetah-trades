"""💧 gajjala_vol_dried joins the push stack (spec voldry §3.7, WP be-kind, 2026-11-24).

Ajay 2026-11-24, verbatim: "Can you send me notification of volume dried please.." A NEW kind, in his keep-set → the
owner keep-set is TEN from this day. LIVE at build (the brief: it ships live because he asked for the notification).

Registries: push/subs.OWNER_KEEP_SET (dated comment INSIDE the braces) + default_prefs False, push/hooks.
notify_gajjala_vol_dried -> sender.send_to_user(kind=...), market_hours/gate.MARKET_ALERT_KINDS. NOT in
DISABLED_ALERT_KINDS. sender.URGENT_KINDS is OWNER_KEEP_SET, so the urgency follows. push/recent.py is NOT touched.
scripts/owner_prefs_apply derives ON / OFF — only its docstring changes. No alert_status strip (HIS CALL #9).
UNMEASURED. NEGATIVES are marked.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chart_maps.gajjala import constants as GC
from market_hours import gate
from push import hooks, recent, sender, subs
from scripts import owner_prefs_apply as S

KIND = "gajjala_vol_dried"
QUOTE = "Can you send me notification of volume dried please.."
TEN = frozenset({"gajjala_setup", "gajjala_potential", "gajjala_1m_setup", "gajjala_1m_potential",
                 "luk_setup", "long_term", "gajjala_si_cross", KIND, "position_alert", "ops_alert"})
OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"
ET = timezone(timedelta(hours=-5))
SATURDAY = datetime(2026, 11, 28, 11, 0, tzinfo=ET)
TUESDAY = datetime(2026, 11, 24, 11, 0, tzinfo=ET)
THANKSGIVING = datetime(2026, 11, 26, 11, 0, tzinfo=ET)
BODY_RE = re.compile(r"^OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)", re.M)


def _src(mod) -> str:
    return Path(mod.__file__).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\n\s*#\s?", " ", text))


# ── the kind string: one value everywhere ────────────────────────────────────────────────────────────────────────
def test_the_kind_string_is_one_value():
    assert KIND == "gajjala_vol_dried"
    assert GC.VOL_DRIED_PUSH_KIND == KIND                               # green once be-engine's constants land


# ── the keep-set ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_keep_set_is_the_ten_exactly():
    assert subs.OWNER_KEEP_SET == TEN and len(subs.OWNER_KEEP_SET) == 10
    assert set(subs.OWNER_KEEP_SET) <= set(subs.default_prefs()), "a kept kind missing from default_prefs targets 0"


def test_NEGATIVE_an_eleventh_kind_breaks_the_ten_pin(monkeypatch):
    monkeypatch.setattr(subs, "OWNER_KEEP_SET", subs.OWNER_KEEP_SET | {"tape_burst_highbeta"})
    try:
        test_the_keep_set_is_the_ten_exactly()
    except AssertionError:
        return
    raise AssertionError("an eleventh kind must fail the TEN pin")


def test_NEGATIVE_dropping_the_kind_breaks_the_ten_pin(monkeypatch):
    monkeypatch.setattr(subs, "OWNER_KEEP_SET", subs.OWNER_KEEP_SET - {KIND})
    try:
        test_the_keep_set_is_the_ten_exactly()
    except AssertionError:
        return
    raise AssertionError("nine kinds must fail the TEN pin")


def test_owner_true_default_false_another_user_false(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER)
    assert subs.default_prefs()[KIND] is False                          # NEGATIVE: never ON for another user
    assert subs.owner_prefs()[KIND] is True
    assert subs.prefs_for(OWNER)[KIND] is True
    assert subs.prefs_for(OTHER)[KIND] is False                         # NEGATIVE
    assert subs.prefs_for(None)[KIND] is False                          # NEGATIVE: no address → the defaults


def test_NEGATIVE_not_in_the_kill_switch():
    assert KIND not in subs.DISABLED_ALERT_KINDS
    assert KIND not in subs.RETIRED_2026_09_20


class _FakeSubColl:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def find(self, q):
        self.queries.append(q)
        return list(self.rows)


class _FakeDb:
    def __init__(self, rows):
        self.push_subscriptions = _FakeSubColl(rows)


def test_list_subscriptions_is_not_short_circuited(monkeypatch):
    db = _FakeDb([{"_id": 1, "user_email": OWNER, "prefs": {KIND: True}}])
    monkeypatch.setattr(subs, "_get_db", lambda: db)
    monkeypatch.setattr(subs, "_backfilled", True)
    rows = subs.list_subscriptions(filter_kind=KIND, user_email=OWNER, honor_quiet_hours=False)
    assert [r["_id"] for r in rows] == [1]
    q = db.push_subscriptions.queries[-1]
    assert q[f"prefs.{KIND}"] is True and q["user_email"] == OWNER and q["kind"] == {"$ne": "mac"}


def test_NEGATIVE_a_disabled_kind_is_short_circuited_the_contrast(monkeypatch):
    db = _FakeDb([{"_id": 1, "user_email": OWNER, "prefs": {"vb_workout": True}}])
    monkeypatch.setattr(subs, "_get_db", lambda: db)
    monkeypatch.setattr(subs, "_backfilled", True)
    assert subs.list_subscriptions(filter_kind="vb_workout", user_email=OWNER, honor_quiet_hours=False) == []
    assert db.push_subscriptions.queries == []


def test_the_dated_comment_with_his_words_sits_inside_the_braces():
    body = BODY_RE.search(_src(subs)).group(1)
    flat = _flat(body)
    assert f'"{KIND}"' in body and QUOTE in flat and "2026-11-24" in body
    assert "The keep-set is TEN from this day" in flat and "A MARKET kind" in flat and "UNMEASURED" in flat
    assert body.index('"gajjala_si_cross"') < body.index(QUOTE.split(" notification")[0]) < body.index(f'"{KIND}"')
    names = set(re.findall(r'"([a-z0-9_]+)"', re.sub(r"#[^\n]*", "", body)))
    assert names == set(TEN)                                            # stripping `#…` leaves exactly the TEN


def test_the_head_keeps_seven_eight_nine_and_gains_ten():
    src = _src(subs)
    head = src[:BODY_RE.search(src).start()]
    flat = _flat(head)
    assert "SEVEN since 2026-11-01" in head and "EIGHT since 2026-11-12" in flat and "NINE since 2026-11-23" in flat
    assert "TEN since 2026-11-24" in flat and QUOTE in flat
    assert "Only give me Gajjalas chart notifications from" in head
    assert not [ln for ln in head.splitlines() if ln.startswith(f"#   {KIND}")]   # NEGATIVE: not a removed kind


def test_default_prefs_comment_sits_above_the_false():
    src = _src(subs)
    at = src.index(f'"{KIND}": False,')
    above = _flat(src[src.rindex('"gajjala_si_cross": False,', 0, at):at])
    assert QUOTE in above and "ZERO devices" in above and "MARKET kind" in above and "UNMEASURED" in above
    assert src.count(f'"{KIND}": False,') == 1                         # NEGATIVE: never typed twice


# ── the hook ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_hook_calls_send_to_user_once_with_the_kind(monkeypatch):
    seen = []
    monkeypatch.setattr(hooks.sender, "send_to_user",
                        lambda owner, payload, kind=None: seen.append((owner, payload, kind)) or {"sent": 1})
    payload = {"title": "💧 Armed, volume dried · ABC · setup", "kind": KIND}
    assert hooks.notify_gajjala_vol_dried(owner=OWNER, payload=payload) == {"sent": 1}
    assert seen == [(OWNER, payload, KIND)]


def test_NEGATIVE_never_send_to_all_and_keyword_only(monkeypatch):
    calls = []
    monkeypatch.setattr(hooks.sender, "send_to_all", lambda *a, **k: calls.append(1) or {"sent": 9})
    monkeypatch.setattr(hooks.sender, "send_to_user", lambda owner, payload, kind=None: {"sent": 1})
    hooks.notify_gajjala_vol_dried(owner=OWNER, payload={})
    assert calls == []
    fn = next(n for n in ast.walk(ast.parse(_src(hooks)))
              if isinstance(n, ast.FunctionDef) and n.name == "notify_gajjala_vol_dried")
    names = {a.attr for a in ast.walk(fn) if isinstance(a, ast.Attribute)}
    assert "send_to_user" in names and "send_to_all" not in names
    try:
        hooks.notify_gajjala_vol_dried(OWNER, {})                         # type: ignore[misc]
    except TypeError:
        pass
    else:
        raise AssertionError("notify_gajjala_vol_dried must be keyword-only (owner=, payload=)")
    assert [n for n in dir(hooks) if "vol_dried" in n] == ["notify_gajjala_vol_dried"]


# ── the closed-day gate ──────────────────────────────────────────────────────────────────────────────────────────
def test_a_market_kind_not_personal():
    assert KIND in gate.MARKET_ALERT_KINDS
    assert KIND not in gate.PERSONAL_KINDS                               # NEGATIVE


def test_saturday_and_a_holiday_drop_and_a_trading_day_passes(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    assert gate.should_drop_kind(KIND, SATURDAY) == "weekend"
    assert gate.should_drop_kind(KIND, THANKSGIVING) == "holiday 2026-11-26"
    assert gate.should_drop_kind(KIND, TUESDAY) is None                  # NEGATIVE: a trading day is not dropped


def test_the_sender_drops_it_on_saturday_and_thanksgiving(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    for day in (SATURDAY, THANKSGIVING):
        monkeypatch.setattr(gate, "_now_et", lambda d=day: d)
        out = sender.send_to_user(OWNER, {"title": "x", "kind": KIND}, kind=KIND)
        assert out["sent"] == 0 and out["total_targets"] == 0 and out.get("skipped")


# ── the urgency (through the keep-set) ───────────────────────────────────────────────────────────────────────────
def test_the_kind_is_urgent_through_the_keep_set():
    assert sender.URGENT_KINDS is subs.OWNER_KEEP_SET
    assert KIND in sender.URGENT_KINDS and sender.urgency_for(KIND) == "high"
    assert KIND not in _src(sender)                                      # NEGATIVE: never retyped in the sender


# ── recent.py untouched ──────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_recent_is_untouched():
    assert KIND not in recent.ITEM_URL_BY_KIND and KIND not in recent.ITEM_KINDS
    assert len(recent.ITEM_KINDS) == 18 and KIND not in _src(recent)


# ── scripts/owner_prefs_apply derives it ─────────────────────────────────────────────────────────────────────────
def test_on_kinds_carries_it_and_off_kinds_does_not():
    assert S.on_kinds() == sorted(subs.OWNER_KEEP_SET) == sorted(TEN)
    assert KIND in S.on_kinds() and KIND not in S.off_kinds()


class FakeColl:
    def __init__(self, docs):
        self.docs = docs
        self.updates = []

    def find(self, _q=None):
        return list(self.docs)

    def update_one(self, flt, upd):
        self.updates.append((flt, upd))
        for d in self.docs:
            if d["_id"] == flt["_id"]:
                for k, v in upd["$set"].items():
                    if k.startswith("prefs."):
                        d.setdefault("prefs", {})[k.split(".", 1)[1]] = v
                    else:
                        d[k] = v


def _docs():
    """His devices at the NINE keep-set: one never touched since (no key), one stamped by _backfill (False); plus
    another user's device at the defaults."""
    ninth = {**subs.owner_prefs(), **{k: False for k in subs.RETIRED_2026_09_20}}
    stale = dict(ninth)
    stale.pop(KIND)
    backfilled = {**ninth, KIND: False}
    return [
        {"_id": 1, "user_email": OWNER, "label": "iPhone", "kind": "web", "endpoint": "https://p/a", "prefs": stale},
        {"_id": 2, "user_email": OWNER, "label": "Mac", "kind": "mac", "endpoint": "mac:2", "prefs": backfilled},
        {"_id": 3, "user_email": OTHER, "label": "friend", "kind": "web", "endpoint": "https://p/c",
         "prefs": dict(subs.default_prefs())},
    ]


def test_apply_None_to_True_and_False_to_True_and_nothing_else_moves():
    coll = FakeColl(_docs())
    other_before = dict(coll.docs[2]["prefs"])
    out = S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    assert out["devices"] == 2 and out["untouched"] == 1 and out["changed"] == 2
    rows = {r["label"]: r["changes"] for r in out["rows"]}
    assert rows["iPhone"] == {KIND: [None, True]} and rows["Mac"] == {KIND: [False, True]}
    assert coll.docs[2]["prefs"] == other_before and coll.docs[2]["prefs"][KIND] is False      # NEGATIVE
    assert {u[0]["_id"] for u in coll.updates} == {1, 2}                                       # NEGATIVE: never _id 3
    coll.updates.clear()
    assert S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)["changed"] == 0 and coll.updates == []


def test_NEGATIVE_a_dry_run_writes_nothing():
    coll = FakeColl(_docs())
    out = S.apply(coll.find(), owner=OWNER, apply=False, coll=coll)
    assert out["changed"] == 2 and out["applied"] is False and coll.updates == []
    assert KIND not in coll.docs[0]["prefs"] and coll.docs[1]["prefs"][KIND] is False


def test_the_docstring_names_the_kind_with_his_words_and_the_code_types_no_kind():
    src = _src(S)
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    flat = re.sub(r"\s+", " ", doc)
    assert f"`{KIND}`" in flat and "TEN kinds" in flat and "2026-11-24" in doc and QUOTE in flat
    assert "re-run after the api deploy, before cron" in flat
    assert "`gajjala_si_cross` (the 🩳 High SI sub's" in flat           # the 11-23 paragraph kept
    assert not _code_types_the_kind(src), "the code derives; only the docstring names the kind"


def _code_types_the_kind(src: str) -> bool:
    tree = ast.parse(src)
    return KIND in "\n".join(src.splitlines()[tree.body[0].end_lineno:])


def test_NEGATIVE_a_retyped_kind_in_the_script_code_fails_the_pin():
    assert _code_types_the_kind(_src(S) + f'\n_ON = ["{KIND}"]\n')
