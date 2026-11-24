"""🩳 gajjala_si_cross joins the push stack (spec highsi §3.7, WP be-push, 2026-11-23).

Ajay 2026-11-23, verbatim (voice-typed — "talks" = stocks): "And also add alerts for these talks when they are crossing
EMA, 9 EMA over 21 EMA." His answer: a NEW kind, in his keep-set → the owner keep-set is NINE from this day.

Registries: push/subs.OWNER_KEEP_SET (dated comment INSIDE the braces) + default_prefs False, push/hooks.
notify_gajjala_si_cross -> sender.send_to_user(kind=...), market_hours/gate.MARKET_ALERT_KINDS, supply_demand/
alert_status (typed leaf + PASS_KINDS + cadence + status_payload). push/recent.py is NOT touched (no `items` on the
payload). scripts/owner_prefs_apply derives ON / OFF — its code is unchanged. UNMEASURED. NEGATIVES are marked.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chart_maps.gajjala import constants as GC
from market_hours import gate
from push import hooks, recent, subs
from scripts import owner_prefs_apply as S
from supply_demand import alert_status as AS

KIND = "gajjala_si_cross"
QUOTE = "And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA."
NINE = frozenset({"gajjala_setup", "gajjala_potential", "gajjala_1m_setup", "gajjala_1m_potential",
                  "luk_setup", "long_term", KIND, "position_alert", "ops_alert"})
OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"
ET = timezone(timedelta(hours=-5))
SATURDAY = datetime(2026, 11, 28, 11, 0, tzinfo=ET)
TUESDAY = datetime(2026, 11, 24, 11, 0, tzinfo=ET)
THANKSGIVING = datetime(2026, 11, 26, 11, 0, tzinfo=ET)
BODY_RE = re.compile(r"^OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)", re.M)
ROOT = Path(__file__).resolve().parents[1]


def _src(mod) -> str:
    return Path(mod.__file__).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\n\s*#\s?", " ", text))


# ── the kind string: one value everywhere ────────────────────────────────────────────────────────────────────────
def test_the_kind_string_is_one_value():
    assert GC.HIGH_SI_CROSS_PUSH_KIND == KIND == AS.GAJJALA_SI_CROSS_KIND


# ── the keep-set ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_keep_set_is_the_nine_exactly():
    assert subs.OWNER_KEEP_SET == NINE and len(subs.OWNER_KEEP_SET) == 9
    assert set(subs.OWNER_KEEP_SET) <= set(subs.default_prefs()), "a kept kind missing from default_prefs targets 0"


def test_NEGATIVE_a_tenth_kind_breaks_the_nine_pin(monkeypatch):
    monkeypatch.setattr(subs, "OWNER_KEEP_SET", subs.OWNER_KEEP_SET | {"tape_burst_highbeta"})
    try:
        test_the_keep_set_is_the_nine_exactly()
    except AssertionError:
        return
    raise AssertionError("a tenth kind must fail the nine pin")


def test_owner_true_default_false_another_user_false(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER)
    assert subs.default_prefs()[KIND] is False                          # NEGATIVE: never ON for another user
    assert subs.owner_prefs()[KIND] is True
    assert subs.prefs_for(OWNER)[KIND] is True
    assert subs.prefs_for(OTHER)[KIND] is False                         # NEGATIVE


def test_the_dated_comment_with_his_words_sits_inside_the_braces():
    body = BODY_RE.search(_src(subs)).group(1)
    flat = _flat(body)
    assert f'"{KIND}"' in body and QUOTE in flat and "2026-11-23" in body
    assert "The keep-set is NINE from this day" in flat and "A MARKET kind" in flat and "UNMEASURED" in flat
    assert body.index('"long_term"') < body.index(QUOTE.split(" these")[0]) < body.index(f'"{KIND}"')
    names = set(re.findall(r'"([a-z0-9_]+)"', re.sub(r"#[^\n]*", "", body)))
    assert names == set(NINE)                                           # stripping `#…` leaves exactly the nine


def test_the_head_keeps_seven_and_eight_and_gains_nine():
    src = _src(subs)
    head = src[:BODY_RE.search(src).start()]
    flat = _flat(head)
    assert "SEVEN since 2026-11-01" in head and "EIGHT since 2026-11-12" in flat
    assert "NINE since 2026-11-23" in flat and QUOTE in flat
    assert "Only give me Gajjalas chart notifications from" in head
    assert not [ln for ln in head.splitlines() if ln.startswith(f"#   {KIND}")]   # NEGATIVE: not a removed kind


def test_default_prefs_comment_sits_above_the_false():
    src = _src(subs)
    at = src.index(f'"{KIND}": False,')
    above = _flat(src[src.rindex('"long_term": False,', 0, at):at])
    assert QUOTE in above and "ZERO devices" in above and "MARKET kind" in above and "UNMEASURED" in above
    assert "AMENDMENTS10 F1" in above


# ── the hook ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_hook_calls_send_to_user_once_with_the_kind(monkeypatch):
    seen = []
    monkeypatch.setattr(hooks.sender, "send_to_user",
                        lambda owner, payload, kind=None: seen.append((owner, payload, kind)) or {"sent": 1})
    payload = {"title": "🩳🔀 ABC", "kind": KIND}
    assert hooks.notify_gajjala_si_cross(owner=OWNER, payload=payload) == {"sent": 1}
    assert seen == [(OWNER, payload, KIND)]


def test_NEGATIVE_never_send_to_all_and_keyword_only(monkeypatch):
    calls = []
    monkeypatch.setattr(hooks.sender, "send_to_all", lambda *a, **k: calls.append(1) or {"sent": 9})
    monkeypatch.setattr(hooks.sender, "send_to_user", lambda owner, payload, kind=None: {"sent": 1})
    hooks.notify_gajjala_si_cross(owner=OWNER, payload={})
    assert calls == []
    fn = next(n for n in ast.walk(ast.parse(_src(hooks)))
              if isinstance(n, ast.FunctionDef) and n.name == "notify_gajjala_si_cross")
    names = {a.attr for a in ast.walk(fn) if isinstance(a, ast.Attribute)}
    assert "send_to_user" in names and "send_to_all" not in names
    try:
        hooks.notify_gajjala_si_cross(OWNER, {})                         # type: ignore[misc]
    except TypeError:
        pass
    else:
        raise AssertionError("notify_gajjala_si_cross must be keyword-only (owner=, payload=)")
    assert [n for n in dir(hooks) if "si_cross" in n] == ["notify_gajjala_si_cross"]


# ── the closed-day gate ──────────────────────────────────────────────────────────────────────────────────────────
def test_a_market_kind_not_personal_not_disabled():
    assert KIND in gate.MARKET_ALERT_KINDS
    assert KIND not in gate.PERSONAL_KINDS                               # NEGATIVE
    assert KIND not in subs.DISABLED_ALERT_KINDS                         # NEGATIVE


def test_saturday_and_a_holiday_drop_and_a_trading_day_passes(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    assert gate.should_drop_kind(KIND, SATURDAY) == "weekend"
    assert gate.should_drop_kind(KIND, THANKSGIVING) == "holiday 2026-11-26"
    assert gate.should_drop_kind(KIND, TUESDAY) is None                  # NEGATIVE: a trading day is not dropped


def test_the_sender_drops_it_on_a_closed_day(monkeypatch):
    from push import sender
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    monkeypatch.setattr(gate, "_now_et", lambda: SATURDAY)
    out = sender.send_to_user(OWNER, {"title": "x", "kind": KIND}, kind=KIND)
    assert out["sent"] == 0 and out["total_targets"] == 0 and out.get("skipped")


# ── recent.py untouched ──────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_recent_is_untouched():
    assert KIND not in recent.ITEM_URL_BY_KIND and KIND not in recent.ITEM_KINDS
    assert len(recent.ITEM_KINDS) == 18 and KIND not in _src(recent)


# ── alert_status ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_alert_status_leaf_pass_kinds_cadence_and_payload():
    assert AS.PASS_KINDS.count(KIND) == 1
    assert AS.PASS_KINDS[AS.PASS_KINDS.index(AS.LUK_KIND) + 1] == KIND
    assert AS.CADENCE_SEC[KIND] == AS.CADENCE_SEC[AS.GAJJALA_KIND]
    assert KIND not in AS.DAILY_PASS_KINDS
    assert "GAJJALA_SI_CROSS_KIND" in AS.__all__

    class PassColl:
        def find_one(self, q):
            return ({"_id": KIND, "as_of": TUESDAY.isoformat(), "date": "2026-11-24", "counts": {"listed": 3}}
                    if q.get("_id") == KIND else None)

        def find(self, *a, **k):
            return []
    p = AS.status_payload(pass_coll=PassColl(), latest_coll=None, now=TUESDAY, gajjala_coll=None,
                          potential_coll=None, tape_control_coll=None)
    row = p["passes"][KIND]
    assert row["cadence_sec"] == AS.CADENCE_SEC[AS.GAJJALA_KIND]
    assert set(p["passes"]) == set(AS.PASS_KINDS)


def test_NEGATIVE_alert_status_stays_a_leaf_and_never_reads_short_interest():
    src = (ROOT / "supply_demand/alert_status.py").read_text(encoding="utf-8")
    assert "short_interest" not in src
    tree = ast.parse(src)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not [n for n in top if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("chart_maps")]


# ── scripts/owner_prefs_apply derives it ─────────────────────────────────────────────────────────────────────────
def test_on_kinds_carries_it_and_off_kinds_does_not():
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
    """His devices at the EIGHT keep-set: one never touched since (no key), one stamped by _backfill (False); plus
    another user's device at the defaults."""
    eighth = {**subs.owner_prefs(), **{k: False for k in subs.RETIRED_2026_09_20}}
    stale = dict(eighth)
    stale.pop(KIND)
    backfilled = {**eighth, KIND: False}
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
    coll.updates.clear()
    assert S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)["changed"] == 0 and coll.updates == []


def test_NEGATIVE_a_dry_run_writes_nothing():
    coll = FakeColl(_docs())
    out = S.apply(coll.find(), owner=OWNER, apply=False, coll=coll)
    assert out["changed"] == 2 and out["applied"] is False and coll.updates == []
    assert KIND not in coll.docs[0]["prefs"]


def test_the_docstring_names_the_kind_with_his_words_and_the_code_types_no_kind():
    src = _src(S)
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    flat = re.sub(r"\s+", " ", doc)
    assert f"`{KIND}`" in flat and "NINE kinds" in flat and "2026-11-23" in doc and QUOTE in flat
    assert "re-run after the api deploy, before cron" in flat
    assert "`long_term` joined OWNER_KEEP_SET" in flat                 # the 11-12 paragraph kept
    code = "\n".join(src.splitlines()[tree.body[0].end_lineno:])
    assert KIND not in code, "the code derives; only the docstring names the kind"
