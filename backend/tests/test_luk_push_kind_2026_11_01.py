"""🥇 luk_setup joins the push stack (luk-live spec WP-A, 2026-11-01).

Ajay 2026-11-01, verbatim: "Lets make it live. also alerts too."

The owner keep-set is SEVEN kinds from this day (six 2026-10-29 … 2026-11-01): `luk_setup` is registered on the ONE
push stack — push/subs.OWNER_KEEP_SET (the dated comment INSIDE the braces) + default_prefs False, push/hooks.
notify_luk_setup -> sender.send_to_user(kind="luk_setup"), market_hours/gate.MARKET_ALERT_KINDS, push/recent.
ITEM_URL_BY_KIND (ITEM_KINDS 17 -> 18). scripts/owner_prefs_apply derives ON/OFF — its code is unchanged.
UNMEASURED: his setup, not a buy signal. NEGATIVE cases are marked NEGATIVE.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from market_hours import gate
from push import hooks, recent, subs
from scripts import owner_prefs_apply as S

QUOTE = "Lets make it live. also alerts too."
# WIDENED 2026-11-12: seven → EIGHT — 📅 long_term (Ajay 2026-11-12: "add an alert list when stocks reach Pankaj's zones …" / "Weekly and if something gets dropped let me know …")
EIGHT = frozenset({"gajjala_setup", "gajjala_potential", "gajjala_1m_setup", "gajjala_1m_potential",
                   "luk_setup", "long_term", "position_alert", "ops_alert"})
OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"
# the contracts.mjs keepSet() regex — the BODY of the frozenset literal
BODY_RE = re.compile(r"^OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)", re.M)


def _subs_src() -> str:
    return Path(subs.__file__).read_text(encoding="utf-8")


def _src(mod) -> str:
    return Path(mod.__file__).read_text(encoding="utf-8")


# ── the keep-set ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_keep_set_is_the_eight_exactly():
    assert subs.OWNER_KEEP_SET == EIGHT
    assert set(subs.OWNER_KEEP_SET) <= set(subs.default_prefs()), "a kept kind missing from default_prefs targets 0"


def test_the_quote_sits_inside_the_braces_beside_the_kind():
    src = _subs_src()
    m = BODY_RE.search(src)
    assert m, "the contracts regex finds the set"
    body = m.group(1)
    assert QUOTE.split(" also")[0] in body                      # the comment wraps the quote over two lines
    assert re.search(r'"Lets make it live\. also alerts\s*#?\s*too\."', body), "his words inside the braces"
    assert '"luk_setup"' in body
    # the quote is a comment — stripping `#…` (contracts keepSet()) leaves exactly the eight names
    names = set(re.findall(r'"([a-z0-9_]+)"', re.sub(r"#[^\n]*", "", body)))
    assert names == set(EIGHT)


def test_the_head_carries_the_seven_sentence_and_still_the_10_29_words():
    src = _subs_src()
    head = src[:BODY_RE.search(src).start()]
    assert "SEVEN since 2026-11-01" in head and QUOTE in head
    assert "Only give me Gajjalas chart notifications from" in head      # the 🔕 test's head read is untouched
    # NEGATIVE: the head amendment added no `#   {kind} ` removed-kind line
    assert not [ln for ln in head.splitlines() if ln.startswith("#   luk_setup")]


def test_owner_prefs_true_default_false_and_another_user_false(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER)
    assert subs.owner_prefs()["luk_setup"] is True
    assert subs.default_prefs()["luk_setup"] is False                   # NEGATIVE: never ON for another user
    assert subs.prefs_for(OTHER)["luk_setup"] is False                  # NEGATIVE
    assert subs.prefs_for(OWNER)["luk_setup"] is True


def test_a_market_kind_not_personal_not_disabled():
    assert "luk_setup" in gate.MARKET_ALERT_KINDS
    assert "luk_setup" not in gate.PERSONAL_KINDS                       # NEGATIVE: the closed-day drop applies
    assert "luk_setup" not in subs.DISABLED_ALERT_KINDS                 # NEGATIVE: a toggle that can fire


def test_the_push_url_and_item_kinds_eighteen():
    assert recent.ITEM_URL_BY_KIND["luk_setup"] == "/chart-maps?tab=luk&focus={sym}"
    assert recent.item_url("luk_setup", "ABC") == "/chart-maps?tab=luk&focus=ABC"
    assert len(recent.ITEM_KINDS) == 18


def test_the_hook_calls_send_to_user_once_with_the_kind(monkeypatch):
    seen = []
    monkeypatch.setattr(hooks.sender, "send_to_user",
                        lambda owner, payload, kind=None: seen.append((owner, payload, kind)) or {"sent": 1})
    payload = {"title": "🥇 ABC · Opening range A+ entry", "kind": "luk_setup"}
    out = hooks.notify_luk_setup(owner=OWNER, payload=payload)
    assert out == {"sent": 1}
    assert seen == [(OWNER, payload, "luk_setup")]


def test_NEGATIVE_send_to_all_is_never_the_hook_path(monkeypatch):
    calls = []
    monkeypatch.setattr(hooks.sender, "send_to_all", lambda *a, **k: calls.append(1) or {"sent": 9})
    monkeypatch.setattr(hooks.sender, "send_to_user", lambda owner, payload, kind=None: {"sent": 1})
    hooks.notify_luk_setup(owner=OWNER, payload={})
    assert calls == [], "owner-scoped only — never a broadcast"


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_luk_potential_kind_anywhere():
    k = "luk_potential"
    assert k not in subs.default_prefs() and k not in subs.OWNER_KEEP_SET
    assert k not in gate.MARKET_ALERT_KINDS and k not in gate.PERSONAL_KINDS
    assert k not in recent.ITEM_URL_BY_KIND
    assert not hasattr(hooks, "notify_luk_potential")
    for mod in (subs, hooks, gate, recent):
        assert k not in _src(mod), mod.__name__
    assert [n for n in dir(hooks) if "luk" in n.lower()] == ["notify_luk_setup"]


def test_NEGATIVE_the_audited_kind_is_still_absent():
    k = "gajjala_audited_setup"
    assert k not in subs.OWNER_KEEP_SET and k not in subs.default_prefs()
    assert not [n for n in dir(hooks) if "audited" in n]
    assert k not in _src(subs) and k not in _src(hooks)


def test_NEGATIVE_a_ninth_kind_breaks_the_eight_pin(monkeypatch):
    monkeypatch.setattr(subs, "OWNER_KEEP_SET", subs.OWNER_KEEP_SET | {"tape_burst_highbeta"})
    try:
        test_the_keep_set_is_the_eight_exactly()
    except AssertionError:
        return
    raise AssertionError("a ninth kind must fail the eight pin")


# ── scripts/owner_prefs_apply derives it ─────────────────────────────────────────────────────────────────────────
def test_on_kinds_carries_luk_setup_and_off_kinds_does_not():
    assert "luk_setup" in S.on_kinds()
    assert "luk_setup" not in S.off_kinds()                             # NEGATIVE


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
    """His devices already at the 2026-10-29 keep-set; one never touched since (no luk_setup key), one stamped by
    push.subs._backfill (luk_setup False); plus another user's device at the defaults."""
    tenth = {**subs.owner_prefs(), **{k: False for k in subs.RETIRED_2026_09_20}}   # his applied shape
    stale = dict(tenth)
    stale.pop("luk_setup")
    backfilled = {**tenth, "luk_setup": False}
    return [
        {"_id": 1, "user_email": OWNER, "label": "iPhone", "kind": "web", "endpoint": "https://p/a",
         "prefs": stale},
        {"_id": 2, "user_email": OWNER, "label": "Mac", "kind": "mac", "endpoint": "mac:2",
         "prefs": backfilled},
        {"_id": 3, "user_email": OTHER, "label": "friend", "kind": "web", "endpoint": "https://p/c",
         "prefs": dict(subs.default_prefs())},
    ]


def test_apply_None_to_True_and_False_to_True_and_nothing_else_moves():
    coll = FakeColl(_docs())
    other_before = dict(coll.docs[2]["prefs"])
    out = S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    assert out["devices"] == 2 and out["untouched"] == 1 and out["changed"] == 2
    rows = {r["label"]: r["changes"] for r in out["rows"]}
    assert rows["iPhone"] == {"luk_setup": [None, True]}                # never stamped since the deploy
    assert rows["Mac"] == {"luk_setup": [False, True]}                  # stamped by _backfill — also expected
    for d in coll.docs[:2]:
        assert d["prefs"]["luk_setup"] is True
    assert coll.docs[2]["prefs"] == other_before                        # NEGATIVE: another user untouched
    assert coll.docs[2]["prefs"]["luk_setup"] is False


def test_a_second_apply_is_no_change():
    coll = FakeColl(_docs())
    S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    coll.updates.clear()
    out = S.apply(coll.find(), owner=OWNER, apply=True, coll=coll)
    assert out["changed"] == 0 and coll.updates == []
    assert all(r["changes"] == {} for r in out["rows"])


def test_NEGATIVE_a_dry_run_writes_nothing():
    coll = FakeColl(_docs())
    out = S.apply(coll.find(), owner=OWNER, apply=False, coll=coll)
    assert out["changed"] == 2 and out["applied"] is False and coll.updates == []
    assert "luk_setup" not in coll.docs[0]["prefs"]


def test_NEGATIVE_the_script_types_no_kind_name_outside_its_docstring():
    src = _src(S)
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    assert "luk_setup" in doc and QUOTE in doc                          # the dated paragraph is in the docstring
    kinds = set(subs.default_prefs()) | set(subs.OWNER_KEEP_SET) | set(subs.RETIRED_2026_09_20)
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value != doc}
    assert not (literals & kinds), sorted(literals & kinds)
    code = "\n".join(src.splitlines()[tree.body[0].end_lineno:])         # everything after the module docstring
    assert "luk" not in code, "the code derives; only the docstring names the kind"
