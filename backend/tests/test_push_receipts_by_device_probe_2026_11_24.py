"""📬 Phone alerts diagnosis probe (2026-11-24, spec ggrun rev 2 §4 `phone-diag`) — the pure summarize / render.

Ajay, verbatim (2026-11-24): "also i am not getting the alerts on phone".

Hermetic: hand-written push_history / push_subscriptions rows, no Mongo, no network, no send.
"""
import ast
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import push_receipts_by_device_probe as P   # noqa: E402
from push import receipts as RC                             # noqa: E402
from push import subs as SUBS                               # noqa: E402

ET = ZoneInfo("America/New_York")
SRC = Path(P.__file__).read_text()
OWNER = "owner@example.com"
IPHONE_UA = ("Pounce · Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.7 Mobile/15E148 Safari/604.1")
MAC_UA = ("Pounce · Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
EP_I1 = "https://web.push.apple.com/QAbcdef0123456789-old"
EP_I2 = "https://web.push.apple.com/QAbcdef0123456789-new"
EP_M1 = "https://fcm.googleapis.com/fcm/send/aaa111"
EP_GONE = "https://web.push.apple.com/removed-since"


def sha1(s):
    return hashlib.sha1(s.encode()).hexdigest()


def ts(m, d, h, mi=0):
    return int(datetime(2026, m, d, h, mi, tzinfo=ET).timestamp())


NOW = ts(11, 24, 3, 45)
KEEP = {k: True for k in SUBS.OWNER_KEEP_SET}


def sub(ep, ua, created, prefs=None):
    return {"endpoint": ep, "keys": {"p256dh": "K" * 40, "auth": "A" * 16}, "label": ua, "kind": None,
            "user_email": OWNER, "created_at": created, "updated_at": ts(11, 13, 1, 29),
            "prefs": dict(KEEP if prefs is None else prefs)}


def SUBS_ROWS():
    # listed out of created_at order on purpose
    return [sub(EP_M1, MAC_UA, ts(11, 6, 9)),
            sub(EP_I2, IPHONE_UA, ts(10, 26, 9)),
            sub(EP_I1, IPHONE_UA, ts(10, 8, 9), prefs={**KEEP, "gajjala_si_cross": False}),
            {"kind": "mac", "label": "Pounce.app", "user_email": OWNER, "created_at": ts(9, 1, 9), "prefs": KEEP}]


def target(ep, ua, ok=True):
    return {"sub": sha1(ep), "device": RC.device_word(ua), "ok": ok}


def rec(ep, ua, at):
    return {"sub": sha1(ep), "device": RC.device_word(ua), "shown_at": at * 1000, "at": at + 1}


def row(t, kind, targets, receipts=(), push_id="a" * 32, user=OWNER):
    d = {"ts": t, "kind": kind, "user_email": user, "total": len(targets),
         "sent": sum(1 for x in targets if x["ok"]), "failed": sum(1 for x in targets if not x["ok"]),
         "targets": list(targets), "receipts": list(receipts), "ticker": "AKAN"}
    if push_id:
        d["push_id"] = push_id
    return d


def ALL3(ok_i1=True):
    return [target(EP_I1, IPHONE_UA, ok_i1), target(EP_I2, IPHONE_UA), target(EP_M1, MAC_UA)]


def HIST():
    t1, t2, t3 = ts(11, 23, 10, 5), ts(11, 23, 15, 40), ts(11, 22, 9, 31)
    return [
        row(t1, "gajjala_setup", ALL3(), [rec(EP_M1, MAC_UA, t1 + 2), rec(EP_I2, IPHONE_UA, t1 + 30)]),
        row(t2, "gajjala_setup", ALL3(), [rec(EP_M1, MAC_UA, t2 + 3)]),
        row(t3, "gajjala_potential", ALL3(), [rec(EP_I1, IPHONE_UA, t3 + 5), rec(EP_I2, IPHONE_UA, t3 + 6),
                                              rec(EP_M1, MAC_UA, t3 + 1)]),
    ]


def summ(hist=None, subs=None, **kw):
    return P.summarize(HIST() if hist is None else hist, SUBS_ROWS() if subs is None else subs, NOW,
                       owner=OWNER, **kw)


def reg(s, letter):
    return next(g for g in s["regs"] if g["letter"] == letter)


# ── positives ────────────────────────────────────────────────────────────────
def test_ordinal_letters_follow_created_at_and_skip_mac_rows():
    s = summ()
    assert [(g["letter"], g["word"]) for g in s["regs"]] == [("A", "iPhone Safari"), ("B", "iPhone Safari"),
                                                             ("C", "Mac Chrome")]
    assert reg(s, "A")["hash"] == sha1(EP_I1) and reg(s, "B")["hash"] == sha1(EP_I2)
    assert reg(s, "A")["name"] == "A · iPhone Safari · reg 10-08"


def test_letter_ordinal_past_z():
    assert [P.letter(i) for i in (0, 25, 26, 27)] == ["A", "Z", "AA", "AB"]


def test_receipts_counted_per_registration_and_per_kind():
    s = summ()
    kt = s["kind_tot"]
    assert (kt[("A", "gajjala_setup")]["accepted"], kt[("A", "gajjala_setup")]["receipts"]) == (2, 0)
    assert (kt[("B", "gajjala_setup")]["accepted"], kt[("B", "gajjala_setup")]["receipts"]) == (2, 1)
    assert (kt[("C", "gajjala_setup")]["accepted"], kt[("C", "gajjala_setup")]["receipts"]) == (2, 2)
    assert kt[("A", "gajjala_potential")]["receipts"] == 1
    assert s["cells"][("B", "11-23", "gajjala_setup")] == {"targeted": 2, "accepted": 2, "rejected": 0, "receipts": 1}
    rt = s["reg_tot"]["A"]
    assert rt["last"] == ts(11, 22, 9, 31) + 5 and rt["accepted_after_last_receipt"] == 2
    assert s["reg_tot"]["B"]["delay_median_s"] in (6, 18, 30)


def test_hour_of_day_table_only_for_iphones():
    s = summ()
    assert s["hours"][("A", 15)] == {"targeted": 1, "accepted": 1, "rejected": 0, "receipts": 0}
    assert s["hours"][("B", 10)]["receipts"] == 1
    text = P.render(s)
    assert "HOUR OF DAY (ET) — A · iPhone Safari" in text and "HOUR OF DAY (ET) — B · iPhone Safari" in text
    assert "HOUR OF DAY (ET) — C" not in text


def test_targetable_reads_the_pref_and_keep_off_is_listed():
    s = summ()
    assert s["targetable"]["gajjala_si_cross"] == 2 and s["targetable"]["gajjala_setup"] == 3
    assert reg(s, "A")["keep_off"] == ["gajjala_si_cross"]


def test_today_rows_and_last_row():
    t = ts(11, 24, 3, 40)
    s = summ(hist=HIST() + [row(t, "luk_setup", ALL3())])
    assert s["today"] == "11-24" and s["today_kinds"] == {"luk_setup": 1}
    assert s["last_row"]["luk_setup"] == t


def test_watch_summary_counts_claims_and_held_on_that_session_only():
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala_watch import constants as WC
    claims = [{"date": "2026-11-23", "state": AL.FADE_CROSS_STATES[1]},
              {"date": "2026-11-23", "state": AL.FADE_CROSS_STATES[2]},
              {"date": "2026-11-22", "state": AL.FADE_CROSS_STATES[1]}]
    tiles = [{"held": {"1m": {"bar_t": "2026-11-23T10:31:00", "reason": "no_target"}}},
             {"held": {"1m": {"bar_t": "2026-11-20T10:31:00", "reason": "failed"}}}]
    w = P.summarize_watch(claims, tiles, "2026-11-23", held_reasons=WC.HELD_REASONS, states=AL.FADE_CROSS_STATES)
    assert w["claims"][AL.FADE_CROSS_STATES[1]] == 1 and w["claims"][AL.FADE_CROSS_STATES[2]] == 1
    assert w["held"] == {"no_target": 1} and w["held_older_sessions"] == 1


# ── NEGATIVES ────────────────────────────────────────────────────────────────
def test_render_has_no_endpoint_no_hash_no_email():
    s = summ(hist=HIST() + [row(ts(11, 23, 11), "gajjala_setup", [target(EP_GONE, IPHONE_UA)])])
    text = P.render(s, {"session": "2026-11-23", "claims": {"cross_pushed": 1}, "held": {}, "held_older_sessions": 0},
                    {"at": ts(11, 23, 20), "session": "2026-11-23", "n_names": 9, "reason": None})
    assert "https://" not in text
    assert not re.search(r"[0-9a-f]{40}", text)
    assert not re.search(r"[0-9a-f]{32}", text)          # no push id either
    assert "@" not in text
    for ep in (EP_I1, EP_I2, EP_M1, EP_GONE):
        assert ep not in text and sha1(ep) not in text


def test_row_without_push_id_is_before_receipts_never_nobody_showed():
    old = row(ts(11, 23, 12), "gajjala_setup", ALL3(), push_id=None)
    s = summ(hist=[old])
    r = s["rows"][("11-23", "gajjala_setup")]
    assert r[P.BEFORE] == 1 and r["nobody_showed"] == 0
    assert all(c["accepted"] == 0 for c in s["reg_tot"].values())


def test_zero_target_row_is_its_own_count():
    s = summ(hist=[row(ts(11, 23, 12), "gajjala_si_cross", [])])
    r = s["rows"][("11-23", "gajjala_si_cross")]
    assert r["zero_target"] == 1 and r["nobody_showed"] == 0
    assert all(c["targeted"] == 0 for c in s["reg_tot"].values())


def test_rejected_target_is_never_no_receipt():
    t = ts(11, 23, 13)
    s = summ(hist=[row(t, "gajjala_setup", ALL3(ok_i1=False), [rec(EP_M1, MAC_UA, t + 1)])])
    a = s["reg_tot"]["A"]
    assert a["rejected"] == 1 and a["accepted"] == 0 and a["receipts"] == 0
    assert s["kind_tot"][("A", "gajjala_setup")]["accepted"] == 0     # the denominator excludes the refusal
    assert s["hours"].get(("A", 13)) is None
    assert a["accepted_after_last_receipt"] == 0


def test_other_users_rows_never_counted_and_filter_carries_owner_or_broadcast():
    other = row(ts(11, 23, 12), "gajjala_setup", ALL3(), user="someone@else.test")
    bcast = row(ts(11, 23, 14), "gajjala_setup", ALL3(), user=None)
    s = summ(hist=[other, bcast])
    assert s["skipped_other_user"] == 1 and s["reg_tot"]["A"]["accepted"] == 1
    f = P.history_filter("Owner@Example.com", 100)
    assert f["$or"] == [{"user_email": "owner@example.com"}, {"user_email": None}] and f["ts"] == {"$gte": 100}
    assert P.subs_filter("Owner@Example.com") == {"user_email": "owner@example.com"}


def test_target_not_on_a_current_registration_is_not_his():
    s = summ(hist=[row(ts(11, 23, 11), "gajjala_setup", [target(EP_GONE, IPHONE_UA)])])
    assert s["gone"]["iPhone Safari"]["accepted"] == 1
    assert all(c["targeted"] == 0 for c in s["reg_tot"].values())


def test_non_keepset_kinds_and_out_of_window_rows_are_not_read():
    s = summ(hist=[row(ts(11, 23, 11), "tape_burst_highbeta", ALL3()),
                   row(ts(11, 10, 11), "gajjala_setup", ALL3())])
    assert s["rows"] == {}


def test_script_names_no_writer_and_no_sender():
    for bad in ("update_", "insert_", "delete_", "replace_", "_send_one", "send_to_", "test_send",
                "list_subscriptions", "bulk_write", "find_one_and"):
        assert bad not in SRC, bad
    names = {n.attr for n in ast.walk(ast.parse(SRC)) if isinstance(n, ast.Attribute)}
    assert not names & {"update_one", "update_many", "insert_one", "insert_many", "delete_one", "delete_many",
                        "replace_one", "drop", "webpush", "remove_subscription"}
