"""📅 long_term joins the push stack (pkzone spec WP-BE-KIND, 2026-11-12).

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long
term tabs in general" and (for the Long Term tab) "Weekly and if something gets dropped let me know when to like is Sales
drop or Stage 2 to Stage 3 or stage 4 changes."

ONE kind `long_term` covers both phone pushes (the 🧭 zone reach and the weekly 📅 digest). The owner keep-set is EIGHT
kinds from this day: push/subs.OWNER_KEEP_SET (dated comment INSIDE the braces) + default_prefs False, push/hooks.
notify_long_term -> sender.send_to_user(kind="long_term"), market_hours/gate.MARKET_ALERT_KINDS. push/recent.py is NOT
touched (no `items` on the zone push, [C5]). scripts/owner_prefs_apply derives ON/OFF — its code is unchanged.
UNMEASURED. NEGATIVE cases are marked NEGATIVE.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market_hours import gate
from push import hooks, recent, subs
from scripts import owner_prefs_apply as S

KIND = "long_term"
Q_ZONES = "add an alert list when stocks reach Pankaj's zones"
Q_WEEKLY = "Weekly and if something gets dropped let me know"
EIGHT = frozenset({"gajjala_setup", "gajjala_potential", "gajjala_1m_setup", "gajjala_1m_potential",
                   "luk_setup", "long_term", "position_alert", "ops_alert"})
OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"
ET = timezone(timedelta(hours=-5))
SATURDAY = datetime(2026, 11, 14, 11, 0, tzinfo=ET)
THURSDAY = datetime(2026, 11, 12, 11, 0, tzinfo=ET)
# the contracts.mjs keepSet() regex — the BODY of the frozenset literal
BODY_RE = re.compile(r"^OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)", re.M)
OTHER_LT_KIND = re.compile(r"""["']long_term_[a-z0-9_]*["']""")


def _src(mod) -> str:
    return Path(mod.__file__).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Comment text with the `#` wrap markers removed, whitespace collapsed (a quote may wrap over two lines)."""
    return re.sub(r"\s+", " ", re.sub(r"\n\s*#\s?", " ", text))


# ── the keep-set ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_long_term_is_in_the_keep_set_and_the_keep_set_is_eight():
    assert KIND in subs.OWNER_KEEP_SET
    assert subs.OWNER_KEEP_SET == EIGHT
    assert set(subs.OWNER_KEEP_SET) <= set(subs.default_prefs()), "a kept kind missing from default_prefs targets 0"


def test_owner_true_default_false_another_user_false(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER)
    assert subs.default_prefs()[KIND] is False                          # NEGATIVE: never ON for another user
    assert subs.owner_prefs()[KIND] is True
    assert subs.prefs_for(OWNER)[KIND] is True
    assert subs.prefs_for(OTHER)[KIND] is False                         # NEGATIVE


def test_the_dated_comment_with_both_quotes_sits_inside_the_braces():
    src = _src(subs)
    m = BODY_RE.search(src)
    assert m, "the contracts regex finds the set"
    body = m.group(1)
    flat = _flat(body)
    assert '"long_term"' in body
    assert Q_ZONES in flat and Q_WEEKLY in flat and "2026-11-12" in body
    assert "The keep-set is EIGHT from this day" in flat
    # the comment sits right above the kind, after luk_setup
    assert body.index('"luk_setup"') < body.index(Q_WEEKLY.split(" and")[0]) < body.index('"long_term"')
    # stripping `#…` (contracts keepSet()) leaves exactly the eight names
    names = set(re.findall(r'"([a-z0-9_]+)"', re.sub(r"#[^\n]*", "", body)))
    assert names == set(EIGHT)


def test_the_head_carries_eight_and_still_seven_and_the_10_29_words():
    src = _src(subs)
    head = src[:BODY_RE.search(src).start()]
    flat = _flat(head)
    assert "EIGHT since 2026-11-12" in flat
    assert "SEVEN since 2026-11-01" in head                              # the 11-01 sentence kept verbatim
    assert "Lets make it live. also alerts too." in head                # the luk test's head read is untouched
    assert "Only give me Gajjalas chart notifications from" in head      # the 🔕 test's head read is untouched
    assert Q_ZONES in flat and Q_WEEKLY in flat
    # NEGATIVE: the head amendment added no `#   {kind} ` removed-kind line
    assert not [ln for ln in head.splitlines() if ln.startswith("#   long_term")]


def test_default_prefs_comment_sits_above_the_false():
    src = _src(subs)
    at = src.index('"long_term": False,')
    above = _flat(src[src.rindex('"luk_setup": False,', 0, at):at])
    assert "MARKET kind" in above and "UNMEASURED" in above and "ZERO devices" in above
    assert Q_ZONES in above and Q_WEEKLY in above


# ── the closed-day gate ──────────────────────────────────────────────────────────────────────────────────────────
def test_a_market_kind_not_personal_not_disabled():
    assert KIND in gate.MARKET_ALERT_KINDS
    assert KIND not in gate.PERSONAL_KINDS                               # NEGATIVE: the closed-day drop applies
    assert KIND not in subs.DISABLED_ALERT_KINDS                         # NEGATIVE: a toggle that can fire


def test_saturday_drops_and_a_trading_day_passes(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    assert gate.should_drop_kind(KIND, SATURDAY) == "weekend"
    assert gate.should_drop_kind(KIND, THURSDAY) is None                 # NEGATIVE: a trading day is not dropped


def test_a_holiday_drops(monkeypatch):
    from market_hours.reminder import ALL_HOLIDAYS
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    day = next(d for d in sorted(ALL_HOLIDAYS) if datetime.strptime(d, "%Y-%m-%d").weekday() < 5)
    when = datetime.strptime(day, "%Y-%m-%d").replace(hour=11, tzinfo=ET)
    assert gate.should_drop_kind(KIND, when) == f"holiday {day}"


# ── the hook ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_hook_calls_send_to_user_once_with_the_kind(monkeypatch):
    seen = []
    monkeypatch.setattr(hooks.sender, "send_to_user",
                        lambda owner, payload, kind=None: seen.append((owner, payload, kind)) or {"sent": 1})
    payload = {"title": "📅 TSM · Pankaj's Agg zone", "kind": KIND}
    out = hooks.notify_long_term(owner=OWNER, payload=payload)
    assert out == {"sent": 1}
    assert seen == [(OWNER, payload, KIND)]


def test_NEGATIVE_send_to_all_is_never_the_hook_path(monkeypatch):
    calls = []
    monkeypatch.setattr(hooks.sender, "send_to_all", lambda *a, **k: calls.append(1) or {"sent": 9})
    monkeypatch.setattr(hooks.sender, "send_to_user", lambda owner, payload, kind=None: {"sent": 1})
    hooks.notify_long_term(owner=OWNER, payload={})
    assert calls == [], "owner-scoped only — never a broadcast"
    fn = next(n for n in ast.walk(ast.parse(_src(hooks)))
              if isinstance(n, ast.FunctionDef) and n.name == "notify_long_term")
    names = {a.attr for a in ast.walk(fn) if isinstance(a, ast.Attribute)}
    assert "send_to_user" in names and "send_to_all" not in names


def test_NEGATIVE_the_hook_is_keyword_only():
    try:
        hooks.notify_long_term(OWNER, {})                                # type: ignore[misc]
    except TypeError:
        return
    raise AssertionError("notify_long_term must be keyword-only (owner=, payload=)")


# ── NEGATIVES: one kind, nowhere else ────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_other_long_term_kind_anywhere():
    places = {
        "OWNER_KEEP_SET": set(subs.OWNER_KEEP_SET), "default_prefs": set(subs.default_prefs()),
        "MARKET_ALERT_KINDS": set(gate.MARKET_ALERT_KINDS), "PERSONAL_KINDS": set(gate.PERSONAL_KINDS),
        "ITEM_KINDS": set(recent.ITEM_KINDS), "DIGEST_KINDS": set(recent.DIGEST_KINDS),
        "ITEM_URL_BY_KIND": set(recent.ITEM_URL_BY_KIND),
    }
    for where, kinds in places.items():
        assert not [k for k in kinds if k.startswith("long_term_")], where
    for k in ("long_term_digest", "long_term_zone"):
        assert not hasattr(hooks, f"notify_{k}")
    for mod in (subs, hooks, gate, recent):
        assert not OTHER_LT_KIND.findall(_src(mod)), mod.__name__
    assert [n for n in dir(hooks) if "long_term" in n] == ["notify_long_term"]


def test_NEGATIVE_recent_is_untouched_no_items_url_for_long_term():
    # [C5] the zone push carries no `items`; adding the kind here would move the 18-kind pins
    assert KIND not in recent.ITEM_URL_BY_KIND
    assert KIND not in recent.ITEM_KINDS and KIND not in recent.DIGEST_KINDS
    assert len(recent.ITEM_KINDS) == 18
    assert "long_term" not in _src(recent)


def test_NEGATIVE_a_ninth_kind_breaks_the_eight_pin(monkeypatch):
    monkeypatch.setattr(subs, "OWNER_KEEP_SET", subs.OWNER_KEEP_SET | {"tape_burst_highbeta"})
    try:
        test_long_term_is_in_the_keep_set_and_the_keep_set_is_eight()
    except AssertionError:
        return
    raise AssertionError("a ninth kind must fail the eight pin")


# ── scripts/owner_prefs_apply derives it ─────────────────────────────────────────────────────────────────────────
def test_on_kinds_carries_long_term_and_off_kinds_does_not():
    assert KIND in S.on_kinds()
    assert KIND not in S.off_kinds()                                     # NEGATIVE


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
    """His devices at the 2026-11-01 keep-set: one never touched since (no long_term key), one stamped by
    push.subs._backfill (long_term False); plus another user's device at the defaults."""
    seventh = {**subs.owner_prefs(), **{k: False for k in subs.RETIRED_2026_09_20}}
    stale = dict(seventh)
    stale.pop(KIND)
    backfilled = {**seventh, KIND: False}
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
    assert rows["iPhone"] == {KIND: [None, True]}
    assert rows["Mac"] == {KIND: [False, True]}
    assert coll.docs[2]["prefs"] == other_before                         # NEGATIVE: another user untouched
    assert coll.docs[2]["prefs"][KIND] is False
    coll.updates.clear()
    again = S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    assert again["changed"] == 0 and coll.updates == []                  # idempotent


def test_NEGATIVE_a_dry_run_writes_nothing():
    coll = FakeColl(_docs())
    out = S.apply(coll.find(), owner=OWNER, apply=False, coll=coll)
    assert out["changed"] == 2 and out["applied"] is False and coll.updates == []
    assert KIND not in coll.docs[0]["prefs"]


def test_the_docstring_names_long_term_with_his_quote_and_the_code_types_no_kind():
    src = _src(S)
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    flat = re.sub(r"\s+", " ", doc)
    assert "`long_term` joined OWNER_KEEP_SET" in flat and "2026-11-12" in doc
    assert Q_ZONES in flat and Q_WEEKLY in flat
    assert "Lets make it live. also alerts too." in doc                  # the 11-01 paragraph kept
    kinds = set(subs.default_prefs()) | set(subs.OWNER_KEEP_SET) | set(subs.RETIRED_2026_09_20)
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value != doc}
    assert not (literals & kinds), sorted(literals & kinds)              # NEGATIVE
    code = "\n".join(src.splitlines()[tree.body[0].end_lineno:])
    assert "long_term" not in code, "the code derives; only the docstring names the kind"
