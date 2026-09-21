"""🔔 `price_alert` is un-paused — the CODE chokepoint, 2026-09-21.

Ajay, asked "Price alerts are retired in the push switch and off in your
Notifications, so even a real crossing will not reach your phone. Turn them
back on?": **"Yes to all.."**.

Two chokepoints kept a real crossing off his phone. This file pins the one that
is code:

1. `push.subs._RETIRED_2026_06_13` no longer holds the kind, so
   `list_subscriptions` / `list_mac_device_ids` reach Mongo for it instead of
   short-circuiting to `[]` / `set()`.
2. It joined `OWNER_KEEP_SET`, so a re-registering owner device cannot quietly
   mute it again — and `scripts/owner_prefs_apply.py` (run by hand, in the
   container, after the deploy) reads that same set for the DATA chokepoint.

Nothing about WHAT a rule needs to fire changed: the latch, `ALERT_COOLDOWN_SEC`
and `_threshold` are untouched, `notify.PRIVATE_KINDS` still scopes the kind,
and `price_alerts._target_email` still resolves the creator first.

The last test is the trap that would have shipped with rev 1 of the spec:
`frontend/scripts/contracts.mjs` `keepSet()` anchors on the FIRST literal
`OWNER_KEEP_SET` in `subs.py`. A comment naming the set above its definition
makes the Essentials contract enforce the RETIRED ten instead.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from push import subs

# The ten that stayed retired on 2026-06-13 ("clean up all the alerts besides
# Minervini learning, buyable/Enter-zone, portfolio, market open/close, and
# household"). Retyped ON PURPOSE — this is the pin.
THE_TEN = frozenset({
    "sepa_new_candidate", "volume_breakout", "rising_momentum",
    "watchlist_breakout", "juggernaut_watchlist", "stage_breakdown",
    "watchlist_stage_breakdown", "morning_brief", "product_launch",
    "scalp_tape",
})
THE_FOUR = frozenset({
    "minervini_flashcards", "vb_workout", "vb_supplement", "vb_education",
})
OWNER = "o" + chr(64) + "x.com"


class _Find:
    def __init__(self, rows, log):
        self.rows, self.log = rows, log

    def find(self, q, *a, **kw):
        self.log.append(q)
        return list(self.rows)


class _Db:
    def __init__(self, rows, log):
        self.push_subscriptions = _Find(rows, log)


# ── the code chokepoint is OPEN ──────────────────────────────────────────────
def test_price_alert_reaches_the_prefs_query_instead_of_short_circuiting(monkeypatch):
    row = {"endpoint": "https://push.example/aaa", "user_email": OWNER,
           "prefs": {"price_alert": True}}
    log: list = []
    monkeypatch.setattr(subs, "_get_db", lambda: _Db([row], log))
    monkeypatch.setattr(subs, "_backfill", lambda db: None)
    out = subs.list_subscriptions(filter_kind="price_alert", user_email=OWNER,
                                  honor_quiet_hours=False)
    assert out == [row], "the kill switch no longer swallows the kind"
    assert len(log) == 1
    q = log[0]
    assert q["prefs.price_alert"] is True, "the DATA chokepoint is the stored pref"
    assert q["user_email"] == OWNER


def test_price_alert_reaches_the_mac_query_too(monkeypatch):
    row = {"device_id": "mac-1"}
    log: list = []
    monkeypatch.setattr(subs, "_get_db", lambda: _Db([row], log))
    assert subs.list_mac_device_ids(OWNER, filter_kind="price_alert") == {"mac-1"}
    assert log and log[0]["prefs.price_alert"] is True and log[0]["kind"] == "mac"


# ── NEGATIVE: everything else still dies before Mongo ────────────────────────
def test_every_other_retired_kind_still_short_circuits_before_the_db(monkeypatch):
    def boom():
        raise AssertionError("_get_db must not be reached for a disabled kind")
    monkeypatch.setattr(subs, "_get_db", boom)
    for k in sorted(THE_TEN | THE_FOUR):
        assert subs.list_subscriptions(filter_kind=k) == [], k
        assert subs.list_mac_device_ids(OWNER, filter_kind=k) == set(), k


def test_the_retired_registries_are_exactly_the_ten_and_the_four():
    assert subs._RETIRED_2026_06_13 == THE_TEN
    assert "price_alert" not in subs._RETIRED_2026_06_13
    assert subs.RETIRED_2026_09_20 == THE_FOUR
    assert "price_alert" not in subs.DISABLED_ALERT_KINDS
    assert subs.DISABLED_ALERT_KINDS == THE_TEN | THE_FOUR


# ── the keep-set / prefs side ────────────────────────────────────────────────
def test_owner_prefs_turn_price_alert_on_and_nothing_else_leaked():
    p = subs.owner_prefs()
    assert p["price_alert"] is True
    on = {k for k, v in p.items() if isinstance(v, bool) and v is True}
    assert on == set(subs.OWNER_KEEP_SET)
    for k, v in p.items():
        if isinstance(v, bool) and k not in subs.OWNER_KEEP_SET:
            assert v is False, k
    assert set(subs.OWNER_KEEP_SET) <= set(subs.default_prefs()), \
        "a kept kind missing from default_prefs targets ZERO devices"


def test_the_apply_script_reads_the_set_and_never_retypes_the_kind():
    from scripts import owner_prefs_apply as S
    assert "price_alert" in S.on_kinds()
    assert "price_alert" not in S.off_kinds()
    assert S.on_kinds() == sorted(subs.OWNER_KEEP_SET)
    src = inspect.getsource(S.apply)
    assert "price_alert" not in src, "the writer stays list-driven, never per-kind"


# ── NEGATIVE: the Alerts page is untouched by item 1 ─────────────────────────
def test_un_retiring_price_alert_does_not_change_what_the_feed_hides():
    """`push.recent._retired_kinds()` reads RETIRED_2026_09_20 ONLY, so the
    2026-09-20 four stay hidden and `price_alert` was never hidden there."""
    from push import recent as R
    rows = [
        {"_id": "1", "ts": 600, "kind": "price_alert", "ticker": "GFS",
         "title": "🔔 GFS -7.0%"},
        {"_id": "2", "ts": 500, "kind": "minervini_flashcards", "title": "card"},
        {"_id": "3", "ts": 400, "kind": "vb_workout", "title": "w"},
        {"_id": "4", "ts": 300, "kind": "vb_supplement", "title": "s"},
        {"_id": "5", "ts": 200, "kind": "vb_education", "title": "e"},
        {"_id": "6", "ts": 100, "kind": "demand_alert", "ticker": "NTAP",
         "title": "🧲 NTAP at demand"},
    ]
    out = R.gather("a" + chr(64) + "x", 25,
                   list_recent=lambda email, limit, **kw: [dict(r) for r in rows],
                   get_db=lambda: None)
    assert [r["_id"] for r in out] == ["1", "6"]
    assert {r["kind"] for r in out} == {"price_alert", "demand_alert"}
    assert "price_alert" not in R._retired_kinds()
    assert set(R._retired_kinds()) == THE_FOUR


# ── scoping is unchanged ─────────────────────────────────────────────────────
def test_delivery_scoping_is_unchanged():
    import auth
    from sepa import notify, price_alerts
    assert price_alerts._target_email({}) == auth.HOUSE_OWNER_EMAIL
    assert price_alerts._target_email({"user_email": "k" + chr(64) + "x"}) == "k" + chr(64) + "x"
    assert "price_alert" in notify.PRIVATE_KINDS, \
        "a private kind with no user_email is still refused (notify._send_push)"


# ── source guards ────────────────────────────────────────────────────────────
def _subs_src() -> str:
    return Path(subs.__file__).read_text(encoding="utf-8")


def test_the_source_carries_his_words_and_the_gate_sentence():
    src = _subs_src()
    quote = src.find("Yes to all..")
    assert quote > 0, "his 2026-09-21 words are the reason this kind is back"
    near = src[max(0, quote - 600):quote + 600]
    assert "price_alert" in near
    assert "not what any kind requires to fire" in src
    assert "price_alert`` is PAUSED" not in src and "price_alert` is PAUSED" not in src


# ── [C1] the parser-anchor pin ───────────────────────────────────────────────
def _keep_set_like_contracts(src: str) -> set[str]:
    """`frontend/scripts/contracts.mjs:44-49` keepSet(), re-implemented line for
    line. It anchors on the FIRST literal `OWNER_KEEP_SET`, eats to the first
    `=`, then wants `frozenset({` and stops at the first `})`."""
    m = re.search(r"OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)", src)
    if not m:
        return set()
    body = re.sub(r"#[^\n]*", "", m.group(1))
    return set(re.findall(r"[\"']([a-z0-9_]+)[\"']", body))


def test_the_first_owner_keep_set_literal_is_its_definition():
    src = _subs_src()
    first = src.find("OWNER_KEEP_SET")
    defn = re.search(r"^OWNER_KEEP_SET\s*:\s*frozenset\s*=\s*frozenset\(\{",
                     src, re.M)
    assert defn is not None, "the definition must stay a column-0 annotated assignment"
    assert first == defn.start(), (
        "contracts.mjs keepSet() anchors on the FIRST literal — never write "
        "OWNER_KEEP_SET in a comment above its definition")


def test_the_contracts_parser_reads_the_real_set():
    src = _subs_src()
    parsed = _keep_set_like_contracts(src)
    assert parsed == set(subs.OWNER_KEEP_SET)
    assert "price_alert" in parsed, \
        "the Essentials preset contract demands price_alert: true from this read"
    assert len(parsed) == 9


def test_NEGATIVE_a_comment_above_the_definition_hijacks_the_parser():
    """WHY the pin above exists. Writing the set's name into a comment that
    sits above line 351 makes the parser return the RETIRED ten — the
    Essentials contract would then demand `volume_breakout: true` and never
    check `price_alert`."""
    src = _subs_src()
    poisoned = src.replace("_RETIRED_2026_06_13: frozenset",
                           "# see OWNER_KEEP_SET\n_RETIRED_2026_06_13: frozenset", 1)
    assert poisoned != src
    parsed = _keep_set_like_contracts(poisoned)
    assert parsed == THE_TEN
    assert "price_alert" not in parsed
    assert parsed != set(subs.OWNER_KEEP_SET)


def test_NEGATIVE_no_close_brace_paren_inside_the_set_body():
    """The parser's body ends at the first `})`; one inside a comment in the
    set body truncates the read."""
    src = _subs_src()
    start = re.search(r"^OWNER_KEEP_SET\s*:\s*frozenset\s*=\s*frozenset\(\{",
                      src, re.M).end()
    end = src.index("})", start)
    for line in src[start:end].splitlines():
        comment = line.split("#", 1)[1] if "#" in line else ""
        assert "})" not in comment, line


# ---------------------------------------------------------------------------
# 2026-09-21 (refix) — the doc's cross-reference must follow the answer.
# §HIS CALL 2 is struck as ANSWERED and the fold is built, so "What is NOT
# changed" may no longer point a reader at an open question.
# ---------------------------------------------------------------------------
_PRICE_ALERTS_DOC = (
    Path(__file__).resolve().parents[2] / "docs" / "alerts" / "price_alerts.md")
_COLLAPSE_DOC_REF = "docs/notifications/alerts_feed_collapse.md"


def _not_changed_section() -> str:
    text = _PRICE_ALERTS_DOC.read_text()
    start = text.index("## What is NOT changed")
    end = text.index("## Traps", start)
    return text[start:end]


def test_the_not_changed_section_points_at_the_collapse_doc():
    section = _not_changed_section()
    assert _COLLAPSE_DOC_REF in section, \
        "the /alerts bullet must hand the reader the built spec, not a question"
    assert "hides nothing" in section
    assert "collapse=false" in section, \
        "the escape hatch back to the flat read belongs beside the claim"


def test_NEGATIVE_the_stale_open_question_pointer_is_gone():
    """The bullet used to read `history is not hidden (§HIS CALL 2)` while
    §HIS CALL 2 was struck ANSWERED further down the same file — two truths in
    one doc. Neither the stale sentence nor a bare pointer may come back."""
    text = _PRICE_ALERTS_DOC.read_text()
    assert "history is not hidden (§HIS CALL 2)" not in text
    assert "(§HIS CALL 2)" not in text
    assert _not_changed_section().count("§HIS CALL 2") == 1, \
        "one mention, and it is the one that says ANSWERED"


def test_his_call_2_is_struck_as_answered_and_hands_off():
    text = _PRICE_ALERTS_DOC.read_text()
    start = text.index("2. ~~**Collapse the 2,022 historic")
    entry = text[start:text.index("\n3. ", start)]
    assert "ANSWERED 2026-09-21" in entry
    assert '"Yes to all.."' in entry
    assert _COLLAPSE_DOC_REF in entry
    # NEGATIVE — an ANSWERED entry never keeps the un-struck heading form.
    assert "2. **Collapse" not in text
