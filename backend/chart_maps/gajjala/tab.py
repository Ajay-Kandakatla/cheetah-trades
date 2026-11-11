"""🚩 Gajjala's tab — the payload of GET /chart-maps/gajjala (BUILD_SPEC §3.4.1, 2026-10-13).

WHAT. One served board per sub-tab: the five setups (🚩 💋 ➖ 🌀 🎾), ☀️ Premarket, 🌙 Post-market and 📓 Playbook.
Every sentence the card prints is built here — state labels, the situational strip, the chips, the push mode — so
the frontend types only structural words.

READS MONGO ONLY. `build()` never scans, never fetches a bar and never calls a provider: the 5-minute cron pass
(run.py) writes `gajjala_scan` / `_reads` / `_passes` / `_post` / `_ah_carry` / `_alerts` / `_halts` / `_daily`, and
this module reads them through store.py. The route adds ONE live fan-out for the shown tiles' now-line (the Support
precedent) and, on 🏁 Track record only, ONE 1-minute read of today's alerted names (ledger.today_read, memo
LEDGER_TODAY_MEMO_SEC, never written) that it hands to `build(today=…)`; nothing else. A missing collection is the
documented "no data" answer, never an error.

ORDER. Setup sub-tabs list the listed names whose read is aplus / triggered / forming / partial / stopped, ordered by
his setup state (A+ newest first, then closest to its trigger): BUILD_SPEC §3.4.1 ordering keys, exactly. invalid /
none reads are counted, never tiled. ☀️ = volume first (S8 1:21:56 "I sort by volume"), % change as a toggle, the
carried after-hours movers after today's names. 🌙 = after-hours gain first, plus today's A+ recap (states only).

NOT SEPA. Nothing here imports or cites another method's gate; the tile link is the house ticker page. UNMEASURED:
no study here says these setups win; nothing here trades, enters a lane or sizes a position.

🧠 POTENTIAL · 📈 TRACK (2026-10-15, BUILD_SPEC4 §3.9 / WP-B). Ajay, three messages verbatim: "In Gajjalas setup I
wanna find potential stocks this shows me what has happened I am trying to setup for this tab to act like Gajjalas
brain. So create a potential category in this section." / "In all the sub tab and add a track and alert to show me new
potential is added everyday." / "Give me an alert all continous tracker on these specifically when I get alert I will
jump on to ride the wave". Every setup sub serves a `potential` strip (its own forming reads that `potential.py` calls a
potential); the 🧠 Potential sub rolls them up (one tile per symbol), with the 📈 Track (today's first sightings and the
last session's, read from the tracker docs the pass wrote) and the 👀 watch line. Every rule, word and order comes from
`potential.py` (the ONE engine) — this module re-derives none and types no number. UNMEASURED.

🔄 SCAN ON OPEN · 🎯 A+ (2026-10-15, BUILD_SPEC5 §3.6 / WP-B). Ajay, verbatim: "When ever I open Gajjala's intiate a
new scan of stocks.  In that moment and if there are any enterable stocks on the top which I see in potential i guess".
The pass itself runs elsewhere (chart_maps/gajjala/on_demand.py spawns `python -m chart_maps.gajjala.run --on-demand`);
this module still READS MONGO ONLY and serves two more blocks on every sub: `scan` (the "🔄 scanned on open HH:MM ET ·
bars through HH:MM" / "last pass HH:MM ET" line, "scanning…" while the pass lease is held — closed bars only, never a
newer bar) and `enterable` (🎯 the A+ reads of the LATEST pass — the card's own state `aplus`, traded through the trigger
and the bar closed, DECISIONS5 K1 + AMENDMENTS5 A11 — served only while the 5-minute cron pass is current, A10). `pass`
gains `at` (one stamp, `pass_stamp`, shared with the POST) and `on_demand`; `pass.stale` reads the CRON pass, so opens
alone never hide a dead cron (A10). A card whose read is older than the pass shown carries "read at the HH:MM ET pass".
An open rings no device (both push gates run dry on it, K2). UNMEASURED — not a recommendation.

🏁 TRACK RECORD (2026-10-16, BUILD_SPEC9 §3.7 / WP-B). Ajay, verbatim: "also can you track all Gajjals stocks and keep a
new tab to show wins vs losses. To see a percentage and the ticker." / "We are not looking for winners just in time but
when they got in to our alerts if they made it or not. Like XLAB today was a winner I made good money on it". The tenth
sub, LAST: every alert that rang, graded by GG's trade math — ledger.py owns the rows, the grader and every served
string (`served_block`); this module only routes `?sub=track_record&span=…` to it and serves the chip count
(`count_today`). Operational accounting of the alerts as sent, not a study — UNMEASURED.

🚩 THE 1-MINUTE PAGE (2026-10-27, BUILD_SPEC27 §3.7 / WP-C). Ajay, verbatim: "Can you create a new page, I would like you
to do the same logic of Gajjalas but on 1 min candles please." / "do everything and also add the track record for it
from today..". `build(…, variant=V.GG1)` serves the SAME board off the 1-minute page's store (variant.py GG1: its own
`gajjala_1m_*` collections, GG5's scanner list / halts / daily / carry / post): its frames ("1m", the Fade on "5m"
first), its cadence and stale words (variant.cadence_sec / stale_after_sec — never a typed number), its push lines
(variant.WORDS_1M — shadow 2026-10-27…28, live since 2026-10-29 by his call; the words follow the mode), its links
(potential.deep_link(…, v)), `tab` =
"gajjala_1m" and ONE added key, `variant` (variant.served_block — title / honesty / tfs the FE prints). GG5 (variant
None) serves every byte as before and never carries `variant`. A Cheetah variant — UNMEASURED.

🧪 GAJJALA · AUDITED (2026-11-01, BUILD_SPEC gg-audited §3.6 / WP-C). Ajay, verbatim: "I would like you to create a new
tab for Gajjals when you modifiy with audit of End of day.. Gajjals-Audited. So we can keep track of improvements on this
tab". `build(…, variant=V.GGA)` serves the SAME board off 🚩's reads (the GGA store borrows them) with the audit overlay
laid on at serve time (audited_tab.overlay_reads — an A+ whose audit failed serves the state `aplus_held`, listed and
counted, never hidden) and three more keys: `audited` (the 🧪 strip), `held` (the held A+ section, the banner's own
gates) and, on 🏁, `audited_compare`. Every edit here is guarded by `variant.is_audited(v)` — GG5 and GG1 serve every
byte as before. UNMEASURED — shadow only, nothing here trades.
🧪 2026-11-05 (SPEC gg-track-parity §3.3): on 🏁 the audited tab serves 🚩's OWN A+ rows (audited_tab.track_block over
the shared store) with a 🧪 Audit column; the audit is read ONCE (audited_tab.read_span) and handed to both 🏁 blocks —
a failed read lists the rows with a "not read" cell and serves `audited_compare` None (never re-read in a block).
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import entry_zone as EZ               # 🧪 2026-11-08 — the GG1 / GGA entry zone (GG5 serves none)
from chart_maps.gajjala import potential as PT                # 🧠 the ONE potential engine (it imports tab lazily)
from chart_maps.gajjala import trader_names as TN             # 📌 2026-10-27 — the trader tag's served words
from chart_maps.gajjala import promo_names as PN              # 🎪 2026-10-29 — the promo tag's served words
from chart_maps.gajjala import squeeze_marks as SM            # 🎾 2026-11-08 — GG's chart marks on the squeeze card
from chart_maps.gajjala import stages as SG                   # 🧭 2026-11-11 — the setup stages on every card (display only)
from chart_maps.gajjala import variant as V                   # 🚩 2026-10-27 — GG5 (this tab) / GG1 (the 1-minute page)
from supply_demand import timeframes as TF                   # 🚩 2026-11-06 — the Support-tab frame keys, read BY NAME (chart_href)
from daytrading.data import ET_RTH_OPEN as _RTH_OPEN          # the house session clock, never retyped
from trading.broker import DOLLAR_DECIMALS, price_decimals, round_price   # the ONE stock price grid (2026-10-20)

log = logging.getLogger("chart_maps.gajjala.tab")

ET = ZoneInfo("America/New_York")
TILE_STATES = ("aplus", "triggered", "forming", "partial", "stopped")
COUNT_STATES = ("aplus", "forming", "partial", "triggered", "stopped", "invalid", "none")
# 📌 2026-10-27 (BUILD_SPEC26 §3.3): "trader" appended LAST — trader_names.legend_row()
LEGEND_KEYS = tuple(COUNT_STATES) + ("awaiting_answer", "listed", "potential", "track", "trader")   # MINE (DECISIONS15 D1)
# 🎪 2026-10-29 (BUILD_SPEC32 D4): "promo" appended LAST — promo_names.legend_row() — served ONLY when the board's pass
# ran the Promo source or a 🎪 tag is on the list (a board without it keeps every legend byte)
LEGEND_KEYS_PROMO = LEGEND_KEYS + ("promo",)
POTENTIAL_LEGEND_END = "not yet printed."           # MINE (DECISIONS15 D1) — the cut of potential.rules_lines()[0]
POTENTIAL_LEGEND_TAIL = " Counted per symbol, not per setup."   # MINE (DECISIONS15 D1)


def _as_sentence(clause: str) -> str:
    """A served clause as its own sentence: first letter capitalised, a closing "." unless it already ends with one of
    ".!?" (also inside a closing ")"); a trailing ")" gets the "." after it."""
    c = (clause or "").strip()
    if not c:
        return c
    c = c[0].upper() + c[1:]
    if c.endswith((".", "!", "?", ".)", "!)", "?)")):
        return c
    return c + "."


def count_legend(promo: bool = False, audited: bool = False) -> list:
    """DECISIONS15 D1 — the ONE served legend: [{key, word, text}] for every word on the counts line, the 🧠 sub's
    number and the 📈 Track's number. Words = the FE's structural labels (A+, triggered, forming, partial, stopped,
    invalid, none, awaiting your number, listed, 🧠 Potential, 📈 Track). Texts in DECISIONS15's table, reusing served
    phrases: the rules_info A+ phrase ("every rule met and the entry bar closed"), potential.rules_lines()[0]'s first
    sentence (split at ". On top"), detectors.AWAITING_TEXT's spirit for awaiting. Pure, no clock, no Mongo.
    2026-10-18 critic fix: the potential text also carries potential.defaults_clauses()[0]'s base clause (worded for the
    CURRENT POTENTIAL_NEEDS_BASE), so the legend follows the setting — DECISIONS15 D1 wins over BUILD_SPEC15's bare cut.
    🎪 2026-10-29: `promo` True → LEGEND_KEYS_PROMO (promo_names.legend_row() last); False → LEGEND_KEYS, byte for byte.
    🧪 2026-11-01: `audited` True (the audited tab only) → one more row, `aplus_held`, right after A+; False → no byte moves."""
    first = PT.rules_lines()[0]                     # at request time — the ONE 🧠 sentence, never retyped
    head, cut, _rest = first.partition(POTENTIAL_LEGEND_END)
    base = _as_sentence(PT.defaults_clauses()[0][2])   # the POTENTIAL_NEEDS_BASE clause, worded for its current value
    potential = head + cut + " " + base + POTENTIAL_LEGEND_TAIL
    rows = (
        ("aplus", "A+", "every rule of the setup met and the bar that traded through the trigger closed on the "
                        "name's latest closed bar at the pass; it rings only when that bar is fresh and inside the A+ "
                        "window, once per name and setup a day"),
        ("forming", "forming", "no rule has failed yet and the break has not printed — “ready” means the next bar "
                               "over the trigger would be the entry"),
        ("partial", "partial", "a rule failed — the card says which (“missed: …”); a break that was not A+ reads "
                               "here too"),
        ("triggered", "triggered", "every rule met and the break printed earlier — the entry has passed; the stop "
                                   "has not printed"),
        ("stopped", "stopped", "the break printed and then the stop printed"),
        ("invalid", "invalid", "the structure died — the entry bar traded under the stop first, too many pullback "
                               "bars, the base broke, or the trigger would equal the stop (a reference bar with no "
                               "range — no risk)"),
        ("none", "none", "no structure of this setup on the bars, or a judged read blanked by the 🎾 float rule or "
                         "an unknown float, or a detector error"),
        ("awaiting_answer", "awaiting your number", "held by a rule whose number you have not given"),
        ("listed", "listed", "the names his scanner listed for the session — every count above is read on these"),
        ("potential", "🧠 Potential", potential),
        ("track", "📈 Track", "every symbol-and-setup that was a potential at any point that session, with what "
                             "became of it since — a record, not a list to act on"),
    )
    by = {k: (w, t) for k, w, t in rows}
    tr = TN.legend_row()                            # 📌 2026-10-27 — built by trader_names, never retyped here
    by[tr["key"]] = (tr["word"], tr["text"])
    keys = LEGEND_KEYS
    if promo is True:
        pr = PN.legend_row()                        # 🎪 2026-10-29 — built by promo_names, never retyped here
        by[pr["key"]] = (pr["word"], pr["text"])
        keys = LEGEND_KEYS_PROMO
    if audited is True:                             # 🧪 2026-11-01 — the audited tab's held A+ (never on GG5 / GG1)
        held = _held_state()
        by[held] = (HELD_LEGEND_WORD, HELD_LEGEND_TEXT)
        keys = keys[:1] + (held,) + keys[1:]
    return [{"key": k, "word": by[k][0], "text": by[k][1]} for k in keys]


HELD_LEGEND_WORD = "A+ held"                                                    # 🧪 2026-11-01 (§3.6 edit 5) — MINE
HELD_LEGEND_TEXT = "A+ on the original, held here by the audit"                 # 🧪 2026-11-01 (§3.6 edit 5)
HELD_MARKER_LABEL = "A+ (original)"                                             # 🧪 2026-11-01 (§3.6 edit 3)
HELD_RECAP_WORD = "A+ on the original — held here by the audit"                 # 🧪 2026-11-01 (§3.6 edit 4)
ADMIT_MARKER_LABEL = "A+ (🧪 K3S)"                                              # 🧪 2026-11-09 K3S (SPEC §3.4) — MINE
ADMIT_RECAP_WORD = "🧪 A+ by the audit's admit rule — held here by the audit"    # 🧪 2026-11-09 K3S (SPEC §3.4) — MINE


def _admit_of(read) -> Optional[str]:
    """🧪 2026-11-09 K3S — the admit rule id the served audit block carries (only a GGA read has an `audit` key), else
    None. A 🚩 A+ audit carries `admit: None`; a K3S admit carries the rule id."""
    aud = read.get("audit") if isinstance(read, dict) else None
    a = aud.get("admit") if isinstance(aud, dict) else None
    return a if isinstance(a, str) and a else None


def _held_state() -> str:
    """🧪 2026-11-01 — audited_rules.HELD_STATE, imported lazily (the served-only state of the audited tab)."""
    from chart_maps.gajjala import audited_rules as AUD
    return AUD.HELD_STATE
MARKED_STATES = ("aplus", "triggered", "stopped")
SUB_KEYS = tuple(k for k, _e, _l in GC.SUBS)
SUB_META = {k: (e, label) for k, e, label in GC.SUBS}
LIST_SUBS = ("premarket", "postmarket")
TFS = ("5m", "15m")
SORTS_PM = (("volume", "Volume"), ("change", "% change"))
SORT_PM_DEFAULT = "volume"
SESSION_BADGE = {"premarket": "☀️ pre-market", "rth": "RTH", "afterhours": "🌙 after-hours",
                 "closed": "closed · last session"}
BADGE_CLOSED_TODAY = "closed"                   # after the last pass on a session day: today's board, no pass left
OUTSIDE_RTH = {"premarket": "pre-market — he uses limit orders only and less size outside regular hours (S8 1:16:35)",
               "afterhours": "after-hours — he uses limit orders only and less size outside regular hours (S8 1:16:35)"}
UNMEASURED = "UNMEASURED"
# 2026-11-11 formulas audit D10 (K11 words) — Ajay, verbatim: "Can you fix the defects please". A `triggered` read whose
# live A+ alert never rang (K11 refused the entry pass on that pass's volume, the next pass re-judged it A+ with the later
# volume) no longer claims "A+ on the HH:MM bar": the served fact is "no alert rang" (store.alert_rows via _entry_times,
# the 🏁's own read). Live-push pages only (🚩 GG5, 1-minute GG1); 🧪 shadow keeps today's bytes. The SAME words for every
# reader (the 🏁 already serves the rang alerts to non-owners — the nothing-hidden rule). Served, never composed in the FE.
NO_RING_TEXT = "no alert rang"
NO_RING_RECAP = {"triggered": "broke (no alert rang)", "stopped": "broke, then stopped (no alert rang)"}
# 2026-11-09 ~10:25 ET — Ajay, verbatim: "Ok sort any stocks by volume on all Gajjala's charts" → the volume key sits FIRST
# inside every state on every card sub (today's scanner volume = the card's own Volume number; GC.VOLUME_SORT_SETUPS); his
# 2026-10-18 float call is the next key. ~10:30 ET, verbatim: "The ones I am reporting they are not on Fidelity put them at
# the bottom" → broker_bottom (his 🚫 list last on every card board, never hidden). The ordering words, served, FE types none:
VOL_ORDER_TEXT = "📊 highest volume on top · then lowest float"   # served as order_note on 🚩 💋 🌀 (2026-11-09)
RS_ORDER_TEXT = "🎾 highest volume on top · then lowest float"    # DECISIONS13 D3 (float) → volume first 2026-11-09 by his word; the squeeze sub
HF_ORDER_TEXT = "➖ 9 and 21 EMA closest to merged on top · then highest volume"   # 🧪 2026-11-08 — the fade sub; [C3] a snapshot, "closest", never a direction word
POT_ORDER_TEXT = "🧠 trigger armed first · then highest volume"   # served as order_note on the 🧠 sub (potential.order_key, 2026-11-09)
# 2026-11-11 entry spec (WP-TAB) — Ajay, verbatim: "Also apply your proposal too. / Here is how he enters please tell me
# to enter based on this". The card's plan line, served (§3.2, DECISION B — the FE stops composing it); proposal #4 the 💧
# marker (§3.6); #8 the 🌅 day-2 list (§3.7, list only, no push); #9 🔝 Focus 5 (§3.8, display only). Every number is a
# constant read by name (GC.FOCUS_N); nothing here is a gate, an order or a push.
PLAN_ENTRY_HEAD = "Entry above"                   # an entry read (_is_entry_read: A+ or forming-ready)
PLAN_LEVEL_HEAD = "trigger"                       # every other read with a trigger (the FE's words until 2026-11-11)
VOL_DRIED_TEXT = "💧 volume dried up"              # chips.vol_dried — the read's own k3_vol criterion met, an indicator
FOCUS_TEXT = ("🔝 Focus 5 — the first five cards in this board's own order (GG keeps 4–5 names active). Display only: "
              "nothing measured says these five win more.")   # "5" / "five" pinned to GC.FOCUS_N by the WP-TAB test
DAY2_TITLE = "🌅 Day 2 — last session's A+ and after-hours movers"
DAY2_NOTE = ("List only, no push. GG keeps the prior day's movers on his morning list (R2). Our 21-session read: they "
             "print +1R again on day 2 about as often as any listed name — a list, not a signal.")
DAY2_EMPTY = "No A+ rang and no after-hours mover passed his checks last session."
DAY2_APLUS_TEXT = "{sym} · {setup_label} A+ rang {at} ET last session"   # 2026-11-11: "last session", not "yesterday" — on a Monday it is Friday
DAY2_CARRY_TEXT = "{sym} · 🌙 after-hours mover last session"
DAY2_LISTED_TEXT = " · on today's list"
BROKER_BOTTOM_TEXT = "your 🚫 names sit at the bottom of every card board"   # served in broker_block.order_text — the owner strip (2026-11-09); the 🏁 only tags


def _vcp_listed(setup: str, r: dict) -> bool:
    """BUILD_SPEC18 D3 (Ajay 2026-10-20 "show me stocks only that have 2 contractions"): a 🌀 read is carded only with
    at least vcp_list_min_cycles() contractions. Every other setup, the switch off, or a read stored without an int
    `cycles` (the previous code, at most one pass old) lists as before — fail-open. A bool is never a count."""
    if setup != "intraday_vcp":
        return True
    m = GC.vcp_list_min_cycles()
    n = (r or {}).get("cycles")
    if m is None or not isinstance(n, int) or isinstance(n, bool):
        return True
    return n >= m


def vcp_list_note(k: int) -> Optional[str]:
    """The 🌀 sub's served line for the k reads counted but not carded (D3) — the words MINE, the numbers the count and
    the constant; None when nothing was held back or the switch is off."""
    m = GC.vcp_list_min_cycles()
    if m is None or not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        return None
    return (f"🌀 {k} with fewer than {m} contractions counted, not listed — his K4: a VCP needs at least {m} "
            f"contractions, each tighter than the one before (S8 33:50)")


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _clock() -> datetime:
    """The wall clock (tests pin it)."""
    return datetime.now(timezone.utc)


def _cad(v=None) -> int:
    """The pass cadence in minutes of the variant (GG5: PASS_CADENCE_SEC // 60; the 1-minute page: GG1M_CADENCE_SEC
    // 60) — read at call time, never typed."""
    return V.cadence_sec(v) // 60


def _mins(n: int) -> str:
    """"{n} minutes" — "1 minute" for the 1-minute page's cadence (2026-10-27); GG5's "5 minutes" byte for byte."""
    return f"{n} minute" if n == 1 else f"{n} minutes"


def _et(now: Optional[datetime]) -> datetime:
    now = now or _clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ET)


def _hhmm(t) -> Optional[str]:
    """"HH:MM" of an ET bar stamp ("YYYY-MM-DD HH:MM") or a datetime (shown in ET)."""
    if isinstance(t, datetime):
        return _et(t).strftime("%H:%M")
    if isinstance(t, str) and len(t) >= 16:
        return t[11:16]
    return None


def _px(x) -> str:
    """The ONE price formatter of the tab, the push, the 🏁 Track record and the 🚩 lane: a price on the broker's own
    grid (trading.broker.round_price / price_decimals — Alpaca takes four decimals under the sub-dollar line, two at or
    over it; 2026-10-20, the MMA finding). Sub-dollar prices drop their trailing zeros ("0.31", "0.3101"); a dollar
    price always carries its two ("4.46", "1.00"). The rule is the broker module's — nothing here types a decimal count."""
    v = _f(x)
    if v is None:
        return "—"
    v = round_price(v)
    n = price_decimals(v)
    s = f"{v:.{n}f}"
    return s if n == DOLLAR_DECIMALS else (s.rstrip("0").rstrip(".") or "0")


def _compact(n) -> Optional[str]:
    v = _f(n)
    if v is None or v < 0:
        return None
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= div:
            return f"{v / div:.1f}{suf}"
    return f"{v:.0f}"


def _pct(x, signed: bool = True) -> Optional[str]:
    v = _f(x)
    if v is None:
        return None
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def _plain(o):
    """JSON-safe copy: datetimes → ISO strings, dates → ISO, tuples → lists (NaN is _scrub's job)."""
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items() if k != "_id"}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    return o


def _text(v) -> Optional[str]:
    if isinstance(v, str):
        return v if v.strip() else None
    if isinstance(v, dict) and isinstance(v.get("text"), str) and v["text"].strip():
        return v["text"]
    return None


def _store(store):
    if store is not None:
        return store
    from chart_maps.gajjala import store as ST
    return ST.default()


def _alerts_find(store, ids: list) -> list:
    try:
        c = store.alerts_coll()
    except Exception:                                               # noqa: BLE001
        c = None
    if c is None or not ids:
        return []
    try:
        return list(c.find({"_id": {"$in": ids}}))
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: alerts read failed: %s", exc)
        return []


# ── the session the board shows ───────────────────────────────────────────────────────────────────────────────────
def _is_market_day(d: date) -> bool:
    from catalysts.medical.reaction import is_market_day
    return is_market_day(d)


def _prev_market_day(d: date) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(d)


def _open_et() -> dtime:
    return dtime.fromisoformat(GC.PASS_OPEN_ET)


def _close_et() -> dtime:
    return dtime.fromisoformat(GC.PASS_CLOSE_ET)


def session_for(now: Optional[datetime] = None) -> tuple:
    """(session date, is_today, in_window). Today ET from the first pass time on a market day; before it, or on a
    closed day, the last market day (its reads stay on the board, labelled)."""
    et = _et(now)
    today = et.date()
    if _is_market_day(today) and et.time() >= _open_et():
        return today, True, et.time() <= _close_et()
    return _prev_market_day(today), False, False


def tape_for(now: Optional[datetime], in_window: bool) -> str:
    """The tape the board is on — the pass's own clock (scanner.pass_tape_session), "closed" out of the window."""
    if not in_window:
        return "closed"
    from chart_maps.gajjala.scanner import pass_tape_session
    return pass_tape_session(_et(now))


def first15(now: Optional[datetime], in_window: bool) -> bool:
    """09:30 ≤ now < 09:30 + NO_TRADE_AFTER_OPEN_MIN on a session day (GG S8 14:41)."""
    if not in_window:
        return False
    et = _et(now)
    start = datetime.combine(et.date(), _RTH_OPEN, tzinfo=ET)
    return start <= et < start + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)


def first15_text() -> str:
    return f"⏳ first {GC.NO_TRADE_AFTER_OPEN_MIN} min — he doesn't trade it (S8 14:41)"


def _session_block(now, session: date, is_today: bool, in_window: bool, v=None) -> dict:
    tape = tape_for(now, in_window)
    badge = (BADGE_CLOSED_TODAY if is_today and tape == "closed"     # 20:05→midnight: "today", not "last session"
             else SESSION_BADGE.get(tape, SESSION_BADGE["closed"]))
    return {"date": session.isoformat(),
            "label": "today" if is_today else f"last session {session.isoformat()}",
            "tape": tape, "badge": badge,
            "first15": first15(now, in_window), "first15_text": first15_text(),
            "refresh_sec": V.cadence_sec(v) if in_window else 0}


def _pass_block(latest: Optional[dict], now, session: date, in_window: bool, cron: Optional[dict] = None,
                v=None) -> dict:
    """The `pass` block. `latest` = the pass shown (any source); `cron` = the newest CRON pass (`_cron_ref`). 2026-10-15
    (AMENDMENTS5 A10): `stale` reads the CRON pass — an on-open pass alone never clears it — and the block gains `at`
    (`pass_stamp`, the stamp the POST answers with) and `on_demand`. `cron` None with a non-on-open `latest` = the
    pre-split shape (every pass was a cron pass): judged on `latest`, exactly as before."""
    at = _at_utc(latest)
    this_session = isinstance(latest, dict) and latest.get("date") == session.isoformat()
    as_of = f"{_et(at).strftime('%H:%M')} ET" if isinstance(at, datetime) else None
    if isinstance(at, datetime) and not this_session:
        as_of = f"{_et(at).strftime('%Y-%m-%d %H:%M')} ET"
    if cron is None and isinstance(latest, dict) and not latest.get("on_demand"):
        cron = latest
    c_at = _at_utc(cron)
    c_this = isinstance(cron, dict) and cron.get("date") == session.isoformat() and c_at is not None
    age = (_et(now) - _et(c_at)).total_seconds() if c_this else None
    warming = bool(in_window and not this_session)
    stale_sec = V.stale_after_sec(v)                                # GG5: STALE_AFTER_SEC (2026-10-27: per variant)
    stale = bool(in_window and this_session and (not c_this or (age is not None and age > stale_sec)))
    out = {"as_of_et": as_of, "stale": stale, "stale_after_sec": stale_sec, "warming": warming,
           "status": (latest or {}).get("status") if isinstance(latest, dict) else None,
           "at": pass_stamp(latest), "on_demand": bool((latest or {}).get("on_demand")) if isinstance(latest, dict)
           else False}
    cad = _cad(v)
    if stale and not c_this:
        out["stale_text"] = f"stale — the {cad}-minute pass has not run this session; it runs every {_mins(cad)}"
    elif stale and cron is latest:
        out["stale_text"] = (f"stale — the last pass was {as_of}, {int(age // 60)} min ago; the pass runs every "
                             f"{_mins(cad)}")
    elif stale:
        out["stale_text"] = (f"stale — the last {cad}-minute pass was {_et(c_at).strftime('%H:%M')} ET, "
                             f"{int(age // 60)} min ago; the pass runs every {_mins(cad)}")
    if warming:
        out["warming_text"] = (f"warming — no pass this session yet (the first runs just after {GC.PASS_OPEN_ET} "
                               "ET); the reads shown are older")
    return out


def strip_text(strip: dict) -> Optional[str]:
    """His situational read (S8 43:39–44:37) in words, from the pass's own counts."""
    if not isinstance(strip, dict) or not strip:
        return None
    n100, n80 = strip.get("runners_100") or 0, strip.get("runners_80") or 0
    best, sym, quiet = _f(strip.get("best_change_pct")), strip.get("best_symbol"), strip.get("quiet")
    if best is None or quiet is None:
        return ("no runner in his band yet — nothing has traded his $%.2f–$%g, %s-share line today"
                % (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE, "{:,}".format(int(GC.SCAN_MIN_VOLUME))))
    head = f"{n100} runner{'s' if n100 != 1 else ''} ≥{GC.SA_BIG_RUNNER_PCT:g}% · {n80} ≥{GC.SA_RUNNER_PCT:g}% · best {sym} {_pct(best)}"
    if quiet:
        return (f"{head} — QUIET: best runner under {GC.SA_QUIET_BEST_PCT:g}% (his bad day: “the maximum runners "
                f"would be 30%–40%”, S8 44:37); on days like this he trades very little")
    return f"{head} — not quiet (his quiet line: best runner under {GC.SA_QUIET_BEST_PCT:g}%, S8 44:37)"


def _strip_block(latest: Optional[dict]) -> dict:
    s = dict((latest or {}).get("strip") or {}) if isinstance(latest, dict) else {}
    tb = (latest or {}).get("trader") if isinstance(latest, dict) else None   # 📌 the pass's trader block
    out = {"runners_100": s.get("runners_100"), "runners_80": s.get("runners_80"),
           "best_change_pct": _f(s.get("best_change_pct")), "best_symbol": s.get("best_symbol"),
           "quiet": s.get("quiet"), "text": strip_text(s),
           "trader_text": TN.strip_text(tb), "trader_skip_text": TN.skip_text(tb)}
    pb = latest.get("promo") if isinstance(latest, dict) else None
    if PN.ran(pb):                                  # 🎪 2026-10-29 — keys ONLY on a pass that ran the source
        out.update(promo_text=PN.strip_text(pb), promo_skip_text=PN.skip_text(pb))
    return out


# ── 🔄 scan on open · 🎯 A+ (2026-10-15, BUILD_SPEC5 §3.6 / §3.7, AMENDMENTS5 A10 / A11 / A13) ─────────────────────
# Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any
# enterable stocks on the top which I see in potential i guess". Every served sentence below is composed here (the FE
# prints what it is given); every number is a constants.py name. His word stays in his quote: the served copy says
# "A+", the card's own state.
RESCAN_LABEL = "🔄 scan now"                                                                             # W8
ENTRY_QUOTE_TS = "1:40:56–1:41:55"                                       # the 📓 Playbook ENTRY item the note slices
ENTRY_QUOTE_FROM = "I'll enter right at the break"


def _at_utc(doc) -> Optional[datetime]:
    """A pass doc's `at` as an aware UTC datetime (the live Mongo client hands back NAIVE UTC — AMENDMENTS5 A5; a naive
    stamp read as ET would shift every clock four hours, alerts.bar_close_et's trap), else None."""
    at = doc.get("at") if isinstance(doc, dict) else None
    if not isinstance(at, datetime):
        return None
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at.astimezone(timezone.utc)


def pass_stamp(doc: Optional[dict]) -> Optional[str]:
    """ONE stamp for a pass doc — the GET's `pass.at` and the POST's `latest_at` (on_demand.request) are this function,
    so the board can tell "the pass the POST waited for has landed" by string inequality. None when no pass."""
    at = _at_utc(doc)
    return at.isoformat() if at is not None else None


def _stamp_utc(v) -> Optional[datetime]:
    if not isinstance(v, datetime):
        return None
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


def _cron_ref(st, latest: Optional[dict]) -> Optional[dict]:
    """The newest CRON pass (AMENDMENTS5 A10): the "latest_cron" pointer; when none is on file (a store from before the
    split), the shown pass when it is not an on-open pass — before the split every pass was a cron pass. None when no
    cron pass is known (an on-open pass alone never stands in for it)."""
    fn = getattr(st, "latest_cron_pass", None)
    lc = None
    if callable(fn):
        try:
            lc = fn()
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala tab: cron pass read failed: %s", exc)
            lc = None
    if isinstance(lc, dict):
        return lc
    if isinstance(latest, dict) and not latest.get("on_demand"):
        return latest
    return None


def _entry_quote() -> Optional[str]:
    """GG's entry sentence, SLICED from the served 📓 Playbook ENTRY item (S8 1:40:56–1:41:55) — never retyped: from
    "I'll enter right at the break" to the end, the trailing "." dropped. None when the item is not found."""
    try:
        from chart_maps.gajjala import playbook as PB
        for it in PB.ENTRY[1]:
            text = it.get("text") if isinstance(it, dict) else None
            if it.get("ts") == ENTRY_QUOTE_TS and isinstance(text, str) and ENTRY_QUOTE_FROM in text:
                return text[text.index(ENTRY_QUOTE_FROM):].rstrip().rstrip(".")
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: entry quote failed: %s", exc)
    return None


def _when(at: Optional[datetime], session: date, *, sec: bool = False) -> Optional[str]:
    """"HH:MM" (or "HH:MM:SS") ET of a stamp; "{date} HH:MM" when it is from another session."""
    if not isinstance(at, datetime):
        return None
    e = _et(at)
    t = e.strftime("%H:%M:%S" if sec else "%H:%M")
    return t if e.date() == session else f"{e.date().isoformat()} {t}"


def scan_block(latest: Optional[dict], lease: dict, now, *, in_window: bool, session: date, v=None) -> dict:
    """§3.6 (b) — the 🔄 line, every sub. state "closed" out of the pass window (C6), "scanning" while the pass lease is
    held (a lease claimed LEASE_SEC ago is not held — a crashed holder never shows "scanning" forever), else "idle".
    Closed bars only (C3): the copy says "bars through HH:MM", never a newer bar. Reads its two arguments only."""
    lease = lease if isinstance(lease, dict) else {}
    latest = latest if isinstance(latest, dict) else None
    at = _at_utc(latest)
    this_session = bool(latest) and latest.get("date") == session.isoformat() and at is not None
    on_demand = bool((latest or {}).get("on_demand"))
    bt = (latest or {}).get("bars_through_et")
    bt = bt if isinstance(bt, str) and bt else None
    cad = _cad(v)
    hhmm = _et(at).strftime("%H:%M") if at is not None else None
    bars = f" · bars through {bt}" if bt else ""
    if not in_window:
        state = "closed"
        as_of = (f"market closed — last pass {hhmm} ET {_et(at).date().isoformat()}" if at is not None
                 else "market closed — no pass on file")                                                  # W3
    else:
        state = "scanning" if lease.get("held") else "idle"
        if this_session and on_demand:
            as_of = f"🔄 scanned on open {hhmm} ET{bars}"                                                   # W1
        elif this_session:
            as_of = f"last pass {hhmm} ET{bars}"                                                            # W2
        elif at is not None:
            as_of = f"last pass {_et(at).date().isoformat()} {hhmm} ET — none yet this session"            # W2b
        else:
            as_of = "no pass on file yet"                                                                   # W2b
    scanning_text = None
    started = None
    if state == "scanning":
        hstart = _stamp_utc(lease.get("holder_started_at")) or _stamp_utc(lease.get("claimed_at"))
        started = _when(hstart, session, sec=True)
        shown = _when(at, session)
        tail = (f"the board below is the {shown} ET read until it lands" if shown
                else "the board fills when it lands")
        when = f" at {started} ET" if started else ""
        if lease.get("held_by") == "on_demand":
            scanning_text = f"scanning… a pass started on open{when} — {tail}"                             # W4
        else:
            scanning_text = f"scanning… the {cad}-minute pass started{when} — {tail}"                      # W5
    elif at is not None:
        started = _when(at, session)
    note = None
    n_l, n_r = (latest or {}).get("n_listed"), (latest or {}).get("n_read")
    if (isinstance(n_l, int) and isinstance(n_r, int) and not isinstance(n_l, bool) and not isinstance(n_r, bool)
            and 0 <= n_r < n_l):
        note = f"{n_l - n_r} of {n_l} names kept their last pass read"                                    # W6 (A13)
    return {"state": state, "on_demand": on_demand, "started_at_et": started, "bars_through_et": bt,
            "as_of_text": as_of, "scanning_text": scanning_text,
            "text": scanning_text if scanning_text else as_of, "note": note,
            "rescan_label": RESCAN_LABEL,
            "rescan_title": (f"Run one pass now — both push gates run dry, so this pass rings no device; the last "
                             f"pass is reused when it finished under {GC.ON_DEMAND_REUSE_SEC} s ago")}    # W9 (A13)


def _aplus_text(sym: str, setup: str, r: dict, since: Optional[str], extra: list, v=None) -> str:
    """W16 — "{SYM} · {e} {label} · trigger {T} · stop {S} (−r%) · A+ since HH:MM ET" (+ the card's own variant / grade
    words, + " (15-min bar)" — 2026-10-27: " ({m}-min bar)" when the read is on the variant's SLOW frame)."""
    bits = [sym, _setup_label(setup)] + [x for x in extra if x]
    trig, stop, risk = _f(r.get("trigger")), _f(r.get("stop")), _f(r.get("risk_pct"))
    if trig is not None:
        bits.append(f"trigger {_px(trig)}")
    if stop is not None:
        bits.append(f"stop {_px(stop)}" + (f" (−{abs(risk):.1f}%)" if risk is not None else ""))
    text = " · ".join(bits)
    if since:
        text += f" · A+ since {since} ET"
    vv = V.of(v)
    if (r.get("frame") or vv.primary) == vv.slow:
        text += f" ({V.frame_minutes(vv.slow, vv)}-min bar)"
    return text


def _aplus_note(cad: int) -> str:
    """W19 (AMENDMENTS5 A11 wording: the banner lists what the cards call A+, while the latest pass reads it A+)."""
    q = _entry_quote()
    gg = f" — GG: “{q}” (S8 {ENTRY_QUOTE_TS})" if q else ""
    return (f"A+ = every rule of the setup met, price traded through the trigger and the bar closed{gg}. Listed while "
            f"the latest pass reads the card A+ and the {cad}-minute pass is current; an entry that printed earlier and "
            "a potential still forming are not listed (your K1 answer). Opening the tab rings no device: both alerts "
            f"stay on the {cad}-minute pass. Closed bars only — an open between passes adds new scanner names, not a "
            "newer bar. UNMEASURED — the study of his A+ setups read no edge (2026-10-14); not a recommendation.")


def aplus_block(reads_by: dict, latest: Optional[dict], now, *, in_window: bool, scan: dict,
                cron: Optional[dict] = None, session: Optional[date] = None, v=None) -> dict:
    """§3.6 (c) — the 🎯 banner, every sub (DECISIONS5 K1 / K3, AMENDMENTS5 A10 / A11). Rows = every listed read OF THE
    LATEST PASS (its `updated_at` is that pass's clock — a name the pass did not re-read keeps an older read and is not
    listed) whose card state is `aplus`, a variant / grade read included with the card's own words; ordered newest
    entry bar first, then SETUPS order, then the symbol. NOT listed: triggered (the entry printed earlier, K1), forming
    / armed potentials, partial, stopped, any read of an older pass. Served only while the newest CRON pass (`cron`) is
    within STALE_AFTER_SEC (A10: opens alone never stand in for a dead cron) and only inside the pass window (C6)."""
    from chart_maps.gajjala import alerts as AL                      # bar_close_et: the A+ gate's own clock
    scan = scan if isinstance(scan, dict) else {}
    latest = latest if isinstance(latest, dict) else None
    at = _at_utc(latest)
    session = session or _et(now).date()
    vv = V.of(v)
    cad = _cad(vv)
    if cron is None and latest is not None and not latest.get("on_demand"):
        cron = latest                                                # pre-split: every pass was a cron pass
    c_at = _at_utc(cron)
    c_age = (_et(now) - _et(c_at)).total_seconds() if c_at is not None else None
    cron_ok = c_age is not None and c_age <= V.stale_after_sec(vv)
    this_session = latest is not None and at is not None and latest.get("date") == session.isoformat()
    rows: list = []
    if in_window and this_session and cron_ok:
        keyed = []
        for sym, doc in (reads_by or {}).items():
            if not isinstance(doc, dict):
                continue
            upd = _stamp_utc(doc.get("updated_at"))
            if upd is None or (at - upd).total_seconds() >= 1:       # a read of an older pass (A11 NEGATIVE)
                continue
            setups = doc.get("setups") if isinstance(doc.get("setups"), dict) else {}
            for setup in GC.SETUPS:
                r = setups.get(setup)
                if not isinstance(r, dict) or r.get("state") != "aplus":
                    continue
                sym_u = str(sym or doc.get("symbol") or "").upper()
                close = AL.bar_close_et(r.get("entry_bar_t"))
                since = close.strftime("%H:%M") if close is not None else None
                frame = r.get("frame") if r.get("frame") in vv.tfs else vv.primary
                extra = [variant_label(r), grade_label(r)]
                keyed.append(((order_key({"symbol": sym_u, "gajjala": {"state": "aplus",
                                                                       "entry_bar_t": r.get("entry_bar_t")}})[:2],
                               GC.SETUPS.index(setup), sym_u),
                              {"symbol": sym_u, "setup": setup, "setup_label": _setup_label(setup), "frame": frame,
                               "trigger": _f(r.get("trigger")), "stop": _f(r.get("stop")),
                               "risk_pct": _f(r.get("risk_pct")), "since_et": since,
                               "variant_label": extra[0], "grade_label": extra[1],
                               "href": PT.deep_link(sym_u, setup, vv),
                               "text": _aplus_text(sym_u, setup, r, since, extra, vv)}))
        keyed.sort(key=lambda kv: kv[0])
        rows = [row for _k, row in keyed]
    empty = None
    if not rows:
        hhmm = _et(at).strftime("%H:%M") if at is not None else None
        if not in_window:
            empty = (f"🎯 No A+ · market closed — last pass {hhmm} ET {_et(at).date().isoformat()} · {UNMEASURED}"
                     if at is not None else f"🎯 No A+ · market closed — no pass on file · {UNMEASURED}")        # W18
        elif not this_session:
            empty = f"🎯 No A+ right now · no pass this session yet · {UNMEASURED}"                              # W17b
        elif not cron_ok:
            since = _when(c_at, session)
            empty = ((f"🎯 No A+ shown · the {cad}-minute pass has not run since {since} ET" if since else
                      f"🎯 No A+ shown · the {cad}-minute pass has not run this session")
                     + f" — no alert can ring without it; the banner waits for it · {UNMEASURED}")              # W17c
        elif scan.get("on_demand") or latest.get("on_demand"):
            empty = f"🎯 No A+ right now · scanned on open {hhmm} ET · {UNMEASURED}"                            # W17
        else:
            empty = f"🎯 No A+ right now · last pass {hhmm} ET · {UNMEASURED}"                                  # W17
    title = (f"🎯 A+ — traded through the trigger and the bar closed (GG's entry) · {len(rows)} · {UNMEASURED}"
             if rows else None)                                                                                 # W15
    return {"title": title, "rows": rows, "empty_text": empty, "note": _aplus_note(cad)}


def push_block(v=None) -> dict:
    """The A+ push line. GG5: GAJJALA_PUSH_MODE's sentence, as always. 2026-10-27 — another variant: its own mode
    (variant.push_mode) and its frozen sentence (variant.WORDS_1M "push")."""
    if not V.is_gg5(v):
        return {"mode": V.push_mode(v), "text": V.word("push", v)}
    mode = GC.GAJJALA_PUSH_MODE
    if mode == "live":
        text = ("📲 Every A+ rings your phone — every rule met and the entry bar closed; never the first "
                f"{GC.NO_TRADE_AFTER_OPEN_MIN} minutes, never pre-market, once per name, setup and day. {UNMEASURED}.")
    else:
        # NARROWED to A+ 2026-10-15 (BUILD_SPEC4 W20): 🧠 potentials ring live right under this line
        # (`push_potential`), so the shadow sentence names A+ instead of saying nothing reaches a phone.
        text = ("A+ pushes are in SHADOW — every A+ is recorded on /alerts as “shadow — not sent”; no A+ reaches "
                f"your phone until the {GC.STUDY_SESSIONS}-session study reads and you flip it to live. {UNMEASURED}.")
    return {"mode": mode, "text": text}


def push_potential_block(session: date, v=None) -> dict:
    """🧠 the LIVE potential push line (BUILD_SPEC4 W15, 2026-10-15 msg 3 "Give me an alert … I will jump on to ride
    the wave"): served beside `push` on every sub; the words are potential.push_note's. 2026-10-27 — another variant:
    its own mode (variant.push_mode — the 1-minute page records in shadow) and potential.push_note(session, v)."""
    if not V.is_gg5(v):
        return {"mode": V.push_mode(v), "text": PT.push_note(session, v)}
    return {"mode": "live", "text": PT.push_note(session)}


def push_break_block() -> dict:
    """⚡ 2026-11-11 entry spec §3.1 — the break-push status line, served as `push_break` on GG5 boards beside
    `push_potential`: break_watch.status()'s `mode` and `text` (its `text` names the mode). LAZY import: build calls it
    inside _soft, so an absent / raising break_watch serves None and the board still builds. 2026-11-11 critic fix:
    ONLY {mode, text} (= GgPushBreak) — status()'s process counters (watching / plans / rang / shadow / refused)
    reset on a restart, the FE reads none of them, and they would leak into the goldens."""
    from chart_maps.gajjala import break_watch as BW
    s = BW.status()
    return {"mode": s.get("mode"), "text": s.get("text")}


def _brk_track_text(doc: dict) -> Optional[str]:
    """⚡ 2026-11-11 — the 🧠 Track row word of a doc's ⚡ claim (break_watch.track_text: pushed → "⚡ break rang …",
    shadow → "⚡ break seen … (shadow)", else None). LAZY import; the caller fences it (_soft → None)."""
    from chart_maps.gajjala import break_watch as BW
    return BW.track_text(doc)


def board_note() -> str:
    from chart_maps.gajjala import playbook as PB
    note = "UNMEASURED — his rules as he described them, not a forecast."
    d = PB.decay()
    if d:
        note += " He wrote on %s: “%s”" % (d.get("date"), d.get("quote"))
    return note + " Nothing here trades or enters a lane. Not advice."


# ── reads → state words ───────────────────────────────────────────────────────────────────────────────────────────
def _criteria_labels(read: dict, keys: list) -> str:
    by = {c.get("key"): c.get("label") or c.get("key") for c in read.get("criteria") or [] if isinstance(c, dict)}
    return ", ".join(by.get(k, k) for k in keys)


def state_label(read: dict, rang: Optional[bool] = None) -> str:
    """The served pill. Every label says UNMEASURED; a break that missed a rule says so (HIS CALL 21).
    `rang` (formulas audit D10, 2026-11-11) = _rang's answer for a live-push page: False → a `triggered` read says
    "broke on the HH:MM bar, no alert rang" (no A+ claim); None (unknown / shadow page) or True → today's words."""
    st = read.get("state")
    trig, stop = read.get("trigger"), read.get("stop")
    if (_admit_of(read) and isinstance(read["audit"].get("text"), str)
            and st in ("aplus", _held_state())):            # 🧪 2026-11-09 K3S — the admit's own words, FIRST
        return read["audit"]["text"]
    if st == "aplus":
        return f"A+ — every rule met, entry bar closed · {UNMEASURED}"
    if st == "triggered":
        n = read.get("bars_since_entry")
        ago = f"{n} bar{'s' if n != 1 else ''} ago" if isinstance(n, int) else "earlier"
        if rang is False:                                       # D10 2026-11-11 — proven no-ring: no A+ claim
            return (f"triggered {ago} — broke on the {_hhmm(read.get('entry_bar_t')) or '—'} bar, {NO_RING_TEXT} · "
                    f"{UNMEASURED}")
        return f"triggered {ago} — A+ on the {_hhmm(read.get('entry_bar_t')) or '—'} bar · {UNMEASURED}"
    if st == "stopped":
        return f"stopped — broke {_px(trig)}, then traded under {_px(stop)} · {UNMEASURED}"
    if st == "forming":
        if read.get("ready"):
            return f"forming — ready: the next bar over {_px(trig)} · {UNMEASURED}"
        why = read.get("reason") or "not long enough yet"
        return f"forming — {why} · {UNMEASURED}"
    if st == "partial":
        missed, unjudged = read.get("missed") or [], read.get("unjudged") or []
        head = "broke — not A+" if read.get("broke") else "partial"
        bits = []
        if missed:
            bits.append("missed: " + _criteria_labels(read, missed))
        if unjudged:
            bits.append("not judgeable: 9 EMA warming up")
        return " · ".join([head] + bits + [UNMEASURED])
    if st == "invalid":
        return f"invalid — {read.get('reason') or 'the structure died'} · {UNMEASURED}"
    if (isinstance(read.get("audit"), dict) and isinstance(read["audit"].get("text"), str)
            and st == _held_state()):                       # 🧪 2026-11-01 — the audit's own served words
        return read["audit"]["text"]
    return f"none — {read.get('reason') or 'no setup today'} · {UNMEASURED}"


def variant_label(read: dict) -> Optional[str]:
    v = read.get("variant")
    if v == "long_flag":
        return "long flag — listed, never A+, never pushed"
    if v == GC.KF_NO_TOUCH_VARIANT:
        return "near-kiss — listed, never A+, never pushed"
    return None


def grade_label(read: dict) -> Optional[str]:
    if read.get("grade") == GC.VCP_B_GRADE:
        miss = _criteria_labels(read, read.get("missed") or [])
        return f"B — imperfect{(' · missed: ' + miss) if miss else ''} — listed, never pushed"
    return None


# ── chips ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _psych_text(chip) -> Optional[str]:
    """context.psych_chips row → "🧱 $5 · 4.2% above — his profit-taking / climax level, not an entry"."""
    t = _text(chip)
    if not t:
        return None
    why = chip.get("why") if isinstance(chip, dict) else None
    return f"{t} — {why}" if why and why not in t else t


def psych_chips(price) -> list:
    """🧱 his profit-taking / climax levels within PSY_NEAR_PCT above the price — WP2's engine
    (`context.psych_chips`), worded for the card."""
    from chart_maps.gajjala import context as CX
    return [t for t in (_psych_text(c) for c in CX.psych_chips(price)) if t]


def _psych_from_ctx(v, price) -> list:
    if isinstance(v, list):
        return [t for t in (_psych_text(x) for x in v) if t]
    return psych_chips(price)


def _rotation_text(v, volume, float_read) -> Optional[str]:
    t = _text(v)
    if t:
        return t
    from chart_maps.gajjala import context as CX
    return _text(CX.rotation(volume, float_read if isinstance(float_read, dict) else None))


def _halts_text(v, halt_doc: Optional[dict]) -> Optional[str]:
    """The pass's own ⏸ chip (context.halts_chip, stored in ctx) — else the same words off today's halt ledger row."""
    t = _text(v)
    if t:
        return t
    src = v if isinstance(v, dict) else halt_doc
    if not isinstance(src, dict):
        return None
    n = src.get("n_halts", src.get("n"))
    if not isinstance(n, int) or n <= 0:
        return None
    reasons = src.get("reasons") or []
    rs = ", ".join(str(r) for r in reasons if r) if isinstance(reasons, (list, tuple)) else str(reasons)
    return f"⏸ halted ×{n}{f' ({rs})' if rs else ''}"


def _squeeze_text(v) -> Optional[str]:
    t = _text(v)
    if t:
        return t
    if not isinstance(v, dict) or not isinstance(v.get("n"), int):
        return None
    of = v.get("of") or GC.K8_HISTORY_SESSIONS
    out = (f"🎾 squeeze history: {v['n']} of last {of} sessions (≥{GC.K8_HISTORY_RANGE_PCT:g}% range or a halt)")
    if v.get("ledger_complete") is False and v.get("ledger_from"):
        out += f" · halt list from {v['ledger_from']}"
    return out


def _float_chip(fr) -> Optional[dict]:
    if not isinstance(fr, dict):
        return None
    text = _text(fr)
    shares = _f(fr.get("shares"))
    if not text:
        if shares is None:
            text = "float unknown"
        else:
            word = {"float": "Float", "shares_out_yf": "shares out",
                    "shares_out_massive": "shares out"}.get(fr.get("src"), "Float")
            text = f"{word} {_compact(shares)}" + (" (Massive)" if fr.get("src") == "shares_out_massive" else "")
    return {"shares": shares, "src": fr.get("src"), "text": text,
            "as_of": _plain(fr.get("as_of")), "suspect": bool(fr.get("suspect"))}


def _float_suspect_text(ctx: dict, fr) -> Optional[str]:
    t = _text(ctx.get("float_suspect")) or (_text(fr.get("suspect_text")) if isinstance(fr, dict) else None)
    if t:
        return t
    if isinstance(fr, dict) and fr.get("suspect"):
        tail = ("treated as unknown" if GC.FLOAT_SUSPECT_POLICY == "ineligible" else "using shares out")
        return f"float on file exceeds shares out — {tail}"
    return None


def _red_text(read: dict) -> Optional[str]:
    """WP2's chip (`context.red_closes_chip`, DECISIONS R2-5: a chip, never a rule)."""
    from chart_maps.gajjala import context as CX
    return _text(CX.red_closes_chip(read.get("red_closes")))


def _stopped_text(doc: dict, setup: str, read: dict) -> Optional[str]:
    if read.get("state") == "stopped":
        return None
    hit = (doc.get("stopped_today") or {}).get(setup) if isinstance(doc.get("stopped_today"), dict) else None
    if not hit:
        return None
    at = _hhmm(hit) if isinstance(hit, (str, datetime)) else None     # run.py stores the ENTRY bar, not the stop
    return (f"stopped earlier today on this setup{f' (entered {at}, stopped)' if at else ''} — “Mostly pass and wait "
            "more” (his X post, 2024-01-25)")


def _flag_text(setup: str, read: dict) -> Optional[str]:
    k = read.get("flag_k")
    if setup != "bull_flag" or not isinstance(k, int) or k <= 0:
        return None
    return (f"flag #{k} today · Business Insider: he plays the first and second, usually skips the third (one "
            "third-party source)")


def _read_at_text(doc: dict, pass_at: Optional[datetime]) -> Optional[str]:
    """W7 (2026-10-15): "read at the HH:MM ET pass" when the card's read doc is older than the pass shown by ≥ 1 s —
    a name an on-open pass did not re-read (its budget ran out) or whose bars failed on a pass keeps an earlier read,
    and says so. None when the read is the shown pass's own (or either stamp is missing)."""
    upd = _stamp_utc(doc.get("updated_at")) if isinstance(doc, dict) else None
    pa = _stamp_utc(pass_at)
    if upd is None or pa is None or (pa - upd).total_seconds() < 1:
        return None
    return f"read at the {_et(upd).strftime('%H:%M')} ET pass"


def _float_read(doc: dict, daily: Optional[dict]):
    """The name's float read: the pass's own (ctx) first, else the 🎾 daily doc's."""
    ctx = doc.get("ctx") if isinstance(doc.get("ctx"), dict) else {}
    return ctx.get("float") if isinstance(ctx.get("float"), dict) else (daily or {}).get("float")


def _float_shares_of(fr) -> Optional[int]:
    """🎾 order key (DECISIONS13 D3): the float read's positive share count; None = unknown (sorts last) — no read,
    shares ≤ 0, or a suspect float under FLOAT_SUSPECT_POLICY "ineligible" (the policy context.rotation applies)."""
    if not isinstance(fr, dict):
        return None
    if fr.get("suspect") and GC.FLOAT_SUSPECT_POLICY == "ineligible":
        return None
    shares = _f(fr.get("shares"))
    if shares is None or shares <= 0:
        return None
    return int(shares)


def _chips(doc: dict, setup: str, read: dict, scan_row: dict, sess: dict, halt_doc, daily: Optional[dict],
           pass_at: Optional[datetime] = None) -> dict:
    ctx = doc.get("ctx") if isinstance(doc.get("ctx"), dict) else {}
    fr = _float_read(doc, daily)
    daily = daily or {}
    price = scan_row.get("price")
    tape = sess.get("tape")
    out = {
        "float": _float_chip(fr),
        "float_suspect": _float_suspect_text(ctx, fr),
        "rotation": _rotation_text(ctx.get("rotation"), scan_row.get("volume"), fr),
        "halts": _halts_text(ctx.get("halts"), halt_doc),
        "psych": _psych_from_ctx(ctx.get("psych"), price) if "psych" in ctx else psych_chips(price),
        "change_pct": _f(scan_row.get("change_pct")),
        "volume": _f(scan_row.get("volume")),
        "vol_src": scan_row.get("vol_src"),
        "session_badge": sess.get("badge"),
        "first15": bool(sess.get("first15")),
        "red_closes": _red_text(read),
        "stopped_earlier": _stopped_text(doc, setup, read),
        "flag_k": _flag_text(setup, read),
        "instrument": GC.SCAN_UNKNOWN_TYPE_LABEL if scan_row.get("type") == GC.SCAN_UNKNOWN_TYPE else None,
        "outside_rth": OUTSIDE_RTH.get(tape),
        "read_at": _read_at_text(doc, pass_at),
    }
    if setup == "reversal_squeeze":
        out["squeeze_history"] = _squeeze_text(ctx.get("squeeze_history") or daily.get("squeeze_history"))
    vd = vol_dried_text(read)                                        # 💧 2026-11-11 (#4) — the key only when met
    if vd:
        out["vol_dried"] = vd
    return out


def _listed_block(info: Optional[dict]) -> Optional[dict]:
    if not isinstance(info, dict):
        return None
    out = {k: info.get(k) for k in ("since", "last_qualified", "day_n", "of")}
    if isinstance(out.get("day_n"), int):
        of = f"/{out['of']}" if isinstance(out.get("of"), int) else ""
        out["text"] = f"listed day {out['day_n']}{of}" + (f" · since {out['since']}" if out.get("since") else "")
    return out


# ── tiles ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _tile_frame(doc: dict, tf: str, v=None, *, wide: bool = False) -> dict:
    """The stored tile of one frame: `tf` when it is one of the variant's frames, else its primary (GG5: "15m" → the
    bars15 keys, anything else → bars5, as always; the 1-minute page: "5m" → bars5, anything else → bars1). The key
    suffix is variant.frame_minutes (2026-10-27), never typed.
    🎾 `wide` (2026-11-08, the squeeze card): when the doc stored the prior session's tail of this frame
    (`bars{suf}_prior`, the GG5 pass) it is laid AHEAD of today's bars — curves merged by tone, the volume average
    joined, a side that lacks one padded with None — and the LAST GC.RS_TILE_BARS_MAX bars are served. No `_prior`
    keys (GG1, the 15-minute frame, a doc from before the upgrade) → exactly today's frame."""
    vv = V.of(v)
    tile = doc.get("tile") if isinstance(doc.get("tile"), dict) else {}
    t = tf if tf in vv.tfs else vv.primary
    suf = str(V.frame_minutes(t, vv))
    out = {"tf": t, "bars": list(tile.get(f"bars{suf}") or []),
           "curves": list(tile.get(f"curves{suf}") or []), "vol_avg": tile.get(f"vol_avg{suf}")}
    prior = tile.get(f"bars{suf}_prior")
    if not wide or not isinstance(prior, list) or not prior:
        return out
    return _wide_frame(out, prior, tile.get(f"curves{suf}_prior"), tile.get(f"vol_avg{suf}_prior"))


def _fit(vals, n: int) -> list:
    """`vals` as exactly `n` aligned values (a missing / short side padded with None)."""
    vals = list(vals) if isinstance(vals, list) else []
    return vals[:n] + [None] * (n - len(vals[:n]))


def _wide_frame(today: dict, prior: list, prior_curves, prior_vol) -> dict:
    """🎾 prior tail + today on one frame, cut to the last GC.RS_TILE_BARS_MAX bars (every aligned list cut alike)."""
    n_p, n_t = len(prior), len(today["bars"])
    bars = list(prior) + today["bars"]
    by_p = {c.get("tone"): c for c in (prior_curves if isinstance(prior_curves, list) else []) if isinstance(c, dict)}
    by_t = {c.get("tone"): c for c in today["curves"] if isinstance(c, dict)}
    tones = list(dict.fromkeys(list(by_p) + list(by_t)))
    curves = []
    for tone in tones:
        p, q = by_p.get(tone) or {}, by_t.get(tone) or {}
        curves.append({"tone": tone, "label": q.get("label", p.get("label")),
                       "values": _fit(p.get("values"), n_p) + _fit(q.get("values"), n_t)})
    pv = prior_vol if isinstance(prior_vol, dict) else None
    tv = today["vol_avg"] if isinstance(today["vol_avg"], dict) else None
    vol = None
    if pv or tv:
        a, b = pv or {}, tv or {}
        vol = {"period": b.get("period", a.get("period")), "label": b.get("label", a.get("label")),
               "values": _fit(a.get("values"), n_p) + _fit(b.get("values"), n_t)}
    cut = max(0, len(bars) - GC.RS_TILE_BARS_MAX)
    if cut:
        bars = bars[cut:]
        for c in curves:
            c["values"] = c["values"][cut:]
        if vol:
            vol["values"] = vol["values"][cut:]
    return {"tf": today["tf"], "bars": bars, "curves": curves, "vol_avg": vol}


def chart_href(sym: str, tf: Optional[str], v=None) -> str:
    """The card's click target (Ajay 2026-11-06): the house ticker page's Supply / Demand tab (chart_maps.board._href,
    unchanged for every other board) opened on the Support-tab frame of the frame the card is DRAWN on — `tf` when it
    is one of the variant's frames, else its primary (a bar-less ☀️/🌙 tile). The key is read off supply_demand.timeframes
    BY NAME (GC.CHART_FRAME_KEY_CONST) at call time: GG5 "5m" → M5_TODAY, "15m" → M15, the 1-minute page "1m" → M1_TODAY.
    Never the bare "5m" (the Support tab's alias for the 24-hour frame) and never "1m" (its one-month window).
    This helper holds the module's ONE call of the board's _href (the contract counts it); the tile builders call this."""
    from chart_maps import board as board_mod
    vv = V.of(v)
    t = tf if tf in vv.tfs else vv.primary
    key = getattr(TF, GC.CHART_FRAME_KEY_CONST[t])
    return f"{board_mod._href(sym)}&{GC.CHART_TF_PARAM}={key}"


def _last_close(doc: dict, frame: str, v=None) -> Optional[float]:
    bars = _tile_frame(doc, frame, v).get("bars") or []
    for b in reversed(bars):
        c = _f(b.get("c")) if isinstance(b, dict) else None
        if c is not None:
            return c
    return None


def _bars_to_go(read: dict) -> Optional[int]:
    """forming (not ready): bars still missing to the setup's minimum length (None = unknown, sorts last)."""
    if isinstance(read.get("bars_to_go"), int):
        return read["bars_to_go"]
    have = (read.get("base") or {}).get("bars") if isinstance(read.get("base"), dict) else None
    have = have if isinstance(have, int) else 0
    need = {"bull_flag": GC.K4_BF_PULL_MIN, "horizontal_fade": GC.K4_HF_BASE_MIN,
            "reversal_squeeze": GC.RS_BASE_MIN_BARS}.get(read.get("setup"))
    if read.get("setup") == "intraday_vcp":
        cyc = (read.get("meta") or {}).get("cycles") if isinstance(read.get("meta"), dict) else None
        if isinstance(cyc, int):
            return max(0, GC.K4_VCP_MIN_CYCLES - cyc)
        return None
    if not isinstance(need, int):
        return None
    return max(0, need - have)


def order_key(t: dict) -> tuple:
    """BUILD_SPEC §3.4.1 ordering keys: state rank; A+/triggered/stopped newest entry first; ready forming nearest
    its trigger; forming by bars to go; partial by fewest misses, then biggest change; final tie the symbol.
    🎾 (DECISIONS13 D3, Ajay 2026-10-18 "for the float lower the better is what I wanna follow so sort it by
    lowest on top"): a reversal_squeeze card built by setup_tile (it carries `_float_shares`) sorts by float ascending, unknown last —
    GC.RS_FLOAT_SORT "within_state" = right after the state rank; "global" = above it.
    ➖ (Ajay 2026-11-07 "I need a ranking in horizontal fade when the stock 9 EMA and 21 EMA are converging or close to
    converge on all tabs"): a horizontal_fade card built by setup_tile (it carries `_ema_gap_pct`, the k6_merge number)
    sorts by the 9/21 EMA gap ascending, unknown last. GC.HF_EMA_SORT "pre_break" (built): every read that has NOT broken
    out — forming AND partial (a FULL-length base with the EMAs apart is partial, detectors._resolve_forming; only a
    SHORT base stays forming) — ranks together at the forming-ready rank by the gap, today's key breaking ties; A+ /
    held / triggered / stopped keep today's key (+ the float since 2026-11-09). "within_state" = the gap right after each state rank;
    "global" = the gap above every state. The gap is a snapshot at the read's ref bar, never a direction.
    2026-11-09 (Ajay "can you update other tabs in the same way" · "When I say all tabs with in Gajjalas only"): every
    setup in GC.FLOAT_SORT_SETUPS takes the 🎾 float key (state rank, float ascending, unknown last, today's key; placed
    by GC.RS_FLOAT_SORT); ➖ keeps its gap FIRST and takes the float right after it (a rung ➖ card, no gap key, takes
    the float like the rest). Display order only. A setup outside the tuple, and a read without the stash (the
    cross-setup focus pick, the 🧠 rows' potential.order_key), keeps today's key byte-identical.
    2026-11-09 ~10:25 ET (Ajay, verbatim: "Ok sort any stocks by volume on all Gajjala's charts"): every setup in
    GC.VOLUME_SORT_SETUPS whose card carries `_volume` (setup_tile — the card's own Volume number) takes the volume key
    DESCENDING (unknown last) in the SAME slot, BEFORE the float: the slot is `sk` = (volume, float), placed by
    GC.RS_FLOAT_SORT ("within_state" = right after the state rank; "global" = above it); ➖ keeps its gap first and takes
    the slot right after it. Today's key still breaks every tie. His 🚫 list is NOT in this key — `broker_bottom` partitions
    the sorted board afterwards (his 2026-11-09 ~10:30 ET word), so every exact-tuple pin on this function holds."""
    g = t.get("gajjala") or {}
    key = _state_key(g, t.get("symbol") or "")
    has_fl = g.get("setup") in GC.FLOAT_SORT_SETUPS and "_float_shares" in g     # 2026-11-09: every setup sub
    fl = g.get("_float_shares")
    fkey = float(fl) if fl else float("inf")
    has_vol = g.get("setup") in GC.VOLUME_SORT_SETUPS and "_volume" in g        # 2026-11-09 ~10:25 ET: volume FIRST (his word)
    vol = _f(g.get("_volume"))
    vkey = -vol if vol is not None else float("inf")                             # highest on top, unknown last
    sk = ((vkey,) if has_vol else ()) + ((fkey,) if has_fl else ())             # the sort slot: volume, then float
    if g.get("setup") == "horizontal_fade" and "_ema_gap_pct" in g:
        gap = g.get("_ema_gap_pct")
        gkey = float(gap) if gap is not None else float("inf")
        ft = sk                                                 # 2026-11-09: volume + float right AFTER the gap, never before
        if GC.HF_EMA_SORT == "global":
            return (0, gkey) + ft + key
        if GC.HF_EMA_SORT == "within_state":
            return key[:1] + (gkey,) + ft + key[1:]
        if g.get("state") in ("forming", "partial"):            # pre_break: ONE bucket, gap first, today's key breaks ties
            return (_PRE_BREAK_RANK, gkey) + ft + key
        # [C6] rung / stopped cards carry no gap key — they take the float key below like every other setup (2026-11-09)
    if sk:
        if GC.RS_FLOAT_SORT == "global":
            return (0,) + sk + key
        return key[:1] + sk + key[1:]
    return key


# the k6_merge criterion's served value, verbatim (detectors._fade_checks: f"EMAs {gap/close*100:.2f}% apart")
_EMA_GAP_RE = re.compile(r"EMAs (\d+(?:\.\d+)?)% apart")


def _ema_gap_pct(read: dict) -> Optional[float]:
    """The k6_merge number as the detector printed it (2 dp) — |EMA9 − EMA21| / close × 100 at the read's ref bar;
    None when the read has no k6_merge row or the EMAs were warming ("EMAs —% apart") → sorts last. The criteria are
    served on forming AND partial reads (detectors._set_criteria runs first), so a partial fade keeps its number."""
    for c in (read or {}).get("criteria") or []:
        if isinstance(c, dict) and c.get("key") == "k6_merge":
            m = _EMA_GAP_RE.fullmatch(str(c.get("value") or ""))
            return float(m.group(1)) if m else None
    return None


_PRE_BREAK_RANK = 2      # the forming-ready rank of _state_key — the ➖ pre_break bucket sits there (ONE definition)


def _state_key(g: dict, sym: str) -> tuple:
    """Today's §3.4.1 key (state rank first) — order_key's tail for every setup."""
    st = g.get("state")
    big = float("inf")
    if st in MARKED_STATES:
        rank = {"aplus": 0, "triggered": 1, "stopped": 5}[st]
        digits = "".join(ch for ch in str(g.get("entry_bar_t") or "") if ch.isdigit())
        return (rank, -float(digits) if digits else big, 0.0, sym)      # newest entry bar first
    if st == "forming" and g.get("ready"):
        trig, last = _f(g.get("trigger")), _f(g.get("_last"))
        return (_PRE_BREAK_RANK, (trig - last) / last if (trig is not None and last) else big, 0.0, sym)
    if st == "forming":
        n = g.get("_bars_to_go")
        return (3, float(n) if isinstance(n, int) else big, 0.0, sym)
    if st == "partial":
        ch = _f((g.get("chips") or {}).get("change_pct"))
        return (4, float(len(g.get("missed") or [])), -ch if ch is not None else big, sym)
    if "audit" in g and st == _held_state():                # 🧪 2026-11-01 — right after the A+, newest entry first
        digits = "".join(ch for ch in str(g.get("entry_bar_t") or "") if ch.isdigit())
        return (0.5, -float(digits) if digits else big, 0.0, sym)
    return (9, big, 0.0, sym)


def _is_entry_read(read: dict) -> bool:
    """The trigger IS the entry: A+ (every rule met and the entry bar closed through it) or a forming read that is
    ready (the next bar over the trigger would be the entry). Everything else with a trigger — partial (a rule failed),
    a break that was not A+, not ready, triggered earlier, stopped — is a level to watch, not a buy."""
    st = (read or {}).get("state")
    return st == "aplus" or (st == "forming" and read.get("ready") is True)


def _tile_lines(read: dict) -> list:
    """2026-10-21 (Ajay, a NAUT 🚩 card reading "broke — not A+ · missed: K3": "Why does this chart in potential say buy?
    If its in Buy at the rate why is it not in A+?"): the trigger line says BUY only when the read is the entry
    (_is_entry_read); every other read prints TRIGGER — a level, never a word that reads as advice. The tone stays
    "buy" (the line style and the card ladder's Entry row key on it); the STOP line is unchanged."""
    out = []
    # `text` (2026-10-21, Ajay on a NUAI card whose PLAN row said "Entry 3.60" under a chart label "TRIGGER 3.61" and a
    # read line "trigger 3.61": "The entry getting changed.."): the ONE print of the level, _px on the broker grid
    # (3.605 → "3.61"; 0.3101 keeps its four), served next to the raw `price` so the card's PLAN row prints the same
    # text the chart label and the read line carry instead of rounding the float on its own (toFixed gave 3.60). The
    # label still carries the word + the same text for the chart gutter; the FE strips the text off the label to name
    # the row ("Stop", "Entry") and prints the text once.
    if _f(read.get("trigger")) is not None:
        entry = _is_entry_read(read)
        tx = _px(read["trigger"])
        out.append({"price": _f(read["trigger"]),
                    "label": f"BUY > {tx}" if entry else f"TRIGGER {tx}",
                    "tone": "buy",                      # the tone (line style, the ladder's Entry row) is unchanged
                    "text": tx})
    if _f(read.get("stop")) is not None:
        tx = _px(read["stop"])
        out.append({"price": _f(read["stop"]), "label": f"STOP {tx}", "tone": "stop", "text": tx})
    return out


def plan_text(read: dict) -> Optional[str]:
    """2026-11-11 entry spec §3.2 (DECISION B) — Ajay: "Here is how he enters please tell me to enter based on this".
    The card's ONE plan line, served: an entry read (_is_entry_read) → "Entry above {T} · stop {S} · risk {r}%"; any
    other read with a trigger → "trigger {T} · stop {S} · risk {r}%" (the FE's composed words until today, now
    served). {T} / {S} = _px (the broker grid — the same text as the BUY / STOP lines); {r} = the read's own risk_pct
    `.1f` (= the FE's riskText). A missing part is dropped; no trigger → None. The read's own bar high / low — GG's
    ±1 cent is HIS CALL #8, not applied here. 2026-11-11 critic fix: "Entry above" only when the plan is a real one
    (ledger.plan_of == LG.PLANS[0], "ok": trigger above the stop) — a no-risk (trigger == stop), a stop above the
    trigger or a missing stop says "trigger …" (the ledger calls those no_risk / no_plan and the push refuses them; the
    no-risk guard in detectors._resolve_break runs only when the bar breaks). An unloadable ledger → "trigger …"."""
    read = read or {}
    trig = _f(read.get("trigger"))
    if trig is None:
        return None
    stop, risk = _f(read.get("stop")), _f(read.get("risk_pct"))
    LG = _ledger() if stop is not None and _is_entry_read(read) else None
    head = PLAN_ENTRY_HEAD if LG is not None and LG.plan_of(trig, stop)[0] == LG.PLANS[0] else PLAN_LEVEL_HEAD
    parts = [f"{head} {_px(trig)}",
             f"stop {_px(stop)}" if stop is not None else None,
             f"risk {risk:.1f}%" if risk is not None else None]
    return " · ".join(p for p in parts if p)


def vol_dried_text(read: dict) -> Optional[str]:
    """2026-11-11 entry spec §3.6 (proposal #4) — VOL_DRIED_TEXT when the read's own criteria row of key
    detectors.K3_VOL_KEY ("k3_vol", every setup) has ok True AND the read is still being read (state in
    detectors.LIVE_STATES: forming / aplus / triggered); else None (the chip key is then absent). An indicator only —
    no order, no gate, no push."""
    from chart_maps.gajjala import detectors as D
    read = read or {}
    if read.get("state") not in D.LIVE_STATES:
        return None
    ok = any(isinstance(c, dict) and c.get("key") == D.K3_VOL_KEY and c.get("ok") is True
             for c in read.get("criteria") or [])
    return VOL_DRIED_TEXT if ok else None


def tile_tf(read: dict, tf: str, sub_default: str, v=None) -> str:
    """The frame a card draws: the asked tf when the URL carries one, else the frame its own read was taken on (the
    ➖ Fade reads 15-minute first but falls back to a 5-minute read), else the sub's default. 2026-10-27: the
    variant's frames (GG5 = TFS)."""
    tfs = V.of(v).tfs
    if tf in tfs:
        return tf
    f = read.get("frame")
    return f if f in tfs else sub_default


def _on_bars(markers: list, bars: list) -> list:
    """Only the markers whose stamp is a served bar — an A+ stamped on the other frame has no bar to sit on."""
    stamps = {b.get("t") for b in bars if isinstance(b, dict)}
    return [m for m in markers if m.get("date") in stamps]


def setup_tile(doc: dict, setup: str, tf: str, *, scan_row: dict, sess: dict, listed: Optional[dict],
               halt_doc=None, daily=None, pass_at: Optional[datetime] = None, v=None,
               carry: Optional[dict] = None, prev_iso: Optional[str] = None, rang: Optional[bool] = None) -> dict:
    """One card: bars + 9/21 EMA + served volume average of `tf` (tile_tf), BUY/STOP lines, the A+ marker when its bar
    is served, and the read in words (state pill, criteria, chips; `pass_at` = the shown pass's clock → the
    "read at …" chip, 2026-10-15).
    🎾 2026-11-08: a Reversal Squeeze card draws the WIDE frame (the prior session's tail ahead of today's bars) and
    serves `ellipses` (squeeze_marks — GG's chart marks) on the frame its read was taken on only, `[]` on the other
    frame's toggle; `carry` = the prior session's carry doc (build's ONE read), `prev_iso` = that session's date. Every
    other setup's card is byte-identical (no `ellipses` key, today's bars).
    `rang` (D10, 2026-11-11) = _rang's answer, handed to state_label (only a `triggered` read uses it)."""
    read = dict((doc.get("setups") or {}).get(setup) or {})
    sym = (doc.get("symbol") or "").upper()
    vv = V.of(v)
    wide = setup == "reversal_squeeze"
    fr = _tile_frame(doc, tf, vv, wide=wide)
    if not fr["bars"]:                                               # the asked frame is empty → the other one
        other = next((t for t in vv.tfs if t != fr["tf"]), fr["tf"])
        alt = _tile_frame(doc, other, vv, wide=wide)
        if alt["bars"]:
            fr = alt
    mlabel = ("A+" if read.get("state") in MARKED_STATES else
              (ADMIT_MARKER_LABEL if _admit_of(read) else HELD_MARKER_LABEL)          # 🧪 2026-11-09 K3S admit
              if "audit" in read and read.get("state") == _held_state() else None)   # 🧪 2026-11-01
    markers = _on_bars([{"date": read.get("entry_bar_t"), "kind": "buy", "label": mlabel}]
                       if mlabel and read.get("entry_bar_t") else [], fr["bars"])
    chips = _chips(doc, setup, read, scan_row, sess, halt_doc, daily, pass_at=pass_at)
    stats = [s for s in ({"k": "Change", "v": _pct(scan_row.get("change_pct"))},
                         {"k": "Volume", "v": _compact(scan_row.get("volume"))}) if s["v"]]
    g = {k: read.get(k) for k in ("setup", "state", "frame", "ready", "broke", "trigger", "stop", "risk_pct",
                                  "entry_bar_t", "bars_since_entry", "criteria", "missed", "unjudged", "grade",
                                  "variant", "red_closes", "flag_k", "reason",
                                  "cycles")}            # 🌀 the contraction count (BUILD_SPEC18 D2; critic 2026-10-20)
    g.update({"setup": setup, "state_label": state_label(read, rang), "variant_label": variant_label(read),
              "grade_label": grade_label(read), "chips": chips, "listed": _listed_block(listed),
              "plan_text": plan_text(read),                     # 2026-11-11 §3.2 — the served plan line
              "_last": _last_close(doc, read.get("frame") or vv.primary, vv) or _f(scan_row.get("price")),
              "_bars_to_go": _bars_to_go(read)})
    if "audit" in read:                                              # 🧪 2026-11-01 — the audited tab's block, served
        g["audit"] = read["audit"]
    if setup in GC.FLOAT_SORT_SETUPS:                                # 🎾 order key (DECISIONS13 D3; every setup 2026-11-09), popped
        g["_float_shares"] = _float_shares_of(_float_read(doc, daily))   # the float chip's own read (_chips), no new fetch
    if setup in GC.VOLUME_SORT_SETUPS:                               # 📊 order key (2026-11-09 ~10:25 ET, his word), popped
        g["_volume"] = chips.get("volume")                           # the card's own Volume number (_chips ← scan_row), no new read
    if setup == "horizontal_fade":                                   # ➖ order key (2026-11-08), popped before serving
        g["_ema_gap_pct"] = _ema_gap_pct(read)
    vol_avg = fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None
    tile = {"symbol": sym, "name": doc.get("name"), "href": chart_href(sym, fr["tf"], vv), "tf": fr["tf"], "bars": fr["bars"],
            "vol_avg": vol_avg, "bands": EZ.bands(read, vv), "lines": _tile_lines(read), "markers": markers, "stats": stats,
            "why": read.get("reason") or "", "badges": [], "curves": fr["curves"], "gajjala": g}
    if wide:                                                         # 🎾 GG's chart marks (2026-11-08)
        read_tf = read.get("frame") if read.get("frame") in vv.tfs else vv.primary   # the tile_tf / _last_close rule
        names = carry.get("names") if isinstance(carry, dict) else None
        carry_row = names.get(sym) if isinstance(names, dict) else None
        tile["ellipses"] = (SM.ellipses(read, fr["bars"], entry_t=(markers[0]["date"] if markers else None),
                                        carry_row=carry_row, prev_iso=prev_iso)
                            if fr["tf"] == read_tf else [])          # drawn ONLY on the frame the read was taken on
    return tile


def _strip_private(tiles: list) -> None:
    for t in tiles:
        g = t.get("gajjala")
        if isinstance(g, dict):
            g.pop("_last", None)
            g.pop("_bars_to_go", None)
            g.pop("_float_shares", None)
            g.pop("_volume", None)
            g.pop("_ema_gap_pct", None)


def _list_tile(sym: str, sub: str, doc: Optional[dict], tf: str, *, scan_row: dict, sess: dict,
               listed: Optional[dict], halt_doc=None, daily=None, extra: dict, v=None) -> dict:
    """A ☀️ / 🌙 row: the name's bars when it is listed (its read doc), its list facts in words, no setup lines."""
    doc = doc or {}
    fr = _tile_frame(doc, tf, v) if doc else {"bars": [], "curves": [], "vol_avg": None}
    read = {"setup": sub, "state": "forming"}
    chips = _chips(doc, sub, read, scan_row, sess, halt_doc, daily)
    g = {"setup": sub, "state": "forming", "state_label": extra.pop("state_label"), "chips": chips,
         "listed": _listed_block(listed), "criteria": [], "missed": [], "unjudged": []}
    g.update(extra)
    stats = [s for s in ({"k": "Change", "v": _pct(scan_row.get("change_pct"))},
                         {"k": "Volume", "v": _compact(scan_row.get("volume"))}) if s["v"]]
    return {"symbol": sym, "name": doc.get("name"), "href": chart_href(sym, fr.get("tf"), v), "bars": fr["bars"],
            "vol_avg": fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None, "bands": [],
            "lines": [], "markers": [], "stats": stats, "why": "", "badges": [], "curves": fr["curves"],
            "gajjala": g}


# ── ☀️ Premarket (K9) / 🌙 Post-market (K10) — WP2's engines over what the pass stored ─────────────────────────────
def session_pass(store, latest: Optional[dict], session: date) -> Optional[dict]:
    """The newest pass doc of `session`: the "latest" pointer when it is this session's, else the session's last."""
    if isinstance(latest, dict) and latest.get("date") == session.isoformat():
        return latest
    docs = [d for d in store.passes(session) if isinstance(d, dict)]
    if not docs:
        return None

    def _at(d):
        a = d.get("at")
        return _et(a).isoformat() if isinstance(a, datetime) else str(a or "")
    return max(docs, key=_at)


def premarket_rows(store, session: date, scan_docs: list, pass_doc: Optional[dict], sort: str) -> list:
    """☀️ = `context.premarket_list` (DECISIONS K9, WP2): today's premarket qualifiers by volume (his ToS sort) or
    change, then the previous session's after-hours carry (the set the LAST after-hours pass wrote). The premarket
    volume is the 1-minute sum the pass stored (`pass.premarket.pm_levels`), else the scanner's own number."""
    from chart_maps.gajjala import context as CX
    pm = (pass_doc or {}).get("premarket") if isinstance(pass_doc, dict) else None
    levels = pm.get("pm_levels") if isinstance(pm, dict) and isinstance(pm.get("pm_levels"), dict) else None
    carry = store.ah_carry(_prev_market_day(session))
    return CX.premarket_list(scan_docs, carry, pm_levels=levels, sort=sort)


def _pm_extra(row: dict) -> dict:
    if row.get("carry"):
        return {"state_label": f"carried from the last session's after-hours · {UNMEASURED}",
                "premarket": {"carry_text": row.get("text")}}
    bits = [f"pm volume {_compact(row.get('pm_volume'))}" if _f(row.get("pm_volume")) is not None else None,
            _pct(row.get("pm_change_pct"))]
    off = _f(row.get("off_pm_high_pct"))
    carried = row.get("carried") if isinstance(row.get("carried"), dict) else None
    return {"state_label": f"premarket mover · {UNMEASURED}",
            "premarket": {"text": " · ".join(b for b in bits if b) or None,
                          "carry_text": carried.get("text") if carried else None,
                          "off_pm_high_text": (f"{off:+.1f}% off the premarket high" if off is not None else None)}}


def postmarket_rows(pass_doc: Optional[dict]) -> tuple:
    """🌙 = the rows `context.postmarket_confirm` returned to the session's last pass (DECISIONS K10 — the pass judges
    the CURRENT after-hours gain off the snapshot, which only the pass holds) + its unchecked count. ([], 0) when the
    pass stored none."""
    pm = (pass_doc or {}).get("postmarket") if isinstance(pass_doc, dict) else None
    pm = pm if isinstance(pm, dict) else {}
    rows = [r for r in pm.get("rows") or [] if isinstance(r, dict) and r.get("symbol")]
    rows.sort(key=lambda r: (_f(r.get("ah_gain_pct")) is None, -(_f(r.get("ah_gain_pct")) or 0.0),
                             str(r.get("symbol"))))
    un = pm.get("unchecked_n")
    return rows, (un if isinstance(un, int) and not isinstance(un, bool) and un >= 0 else 0)


def _post_extra(d: dict) -> dict:
    pos = _f(d.get("close_pos"))
    bits = [f"close in the top {max(0.0, (1 - pos) * 100):.0f}% of the range" if pos is not None else None,
            f"AH volume {_compact(d.get('ah_volume'))}" if _f(d.get("ah_volume")) is not None else None,
            f"AH {_pct(d.get('ah_gain_pct'))}" if _f(d.get("ah_gain_pct")) is not None else None]
    at = _hhmm(d.get("checked_at")) if isinstance(d.get("checked_at"), datetime) else None
    reg = _f(d.get("reg_gain_pct"))
    return {"state_label": f"after-hours mover · {UNMEASURED}",
            "postmarket": {"text": " · ".join(b for b in bits if b) or None,
                           "checked_text": d.get("checked_text") or (f"checked {at} ET" if at else None),
                           "exhaustion_text": f"regular session {reg:+.1f}%" if reg is not None else None}}


def recap(reads: list, v=None, entries: Optional[dict] = None) -> dict:
    """🌙 today's A+ recap (DECISIONS R2-7): which reads went A+ / triggered / stopped — states only, no win/loss
    maths. Ordered by the entry bar; each row links its setup card (DECISIONS10 D7b — rendered in commit 2):
    `href` = potential.deep_link(sym, setup), the A+ push url.
    `entries` (formulas audit D10, 2026-11-11) = _entry_times' answer on a live-push page, else None: a `triggered` /
    `stopped` row whose (read date, SYM, setup) is absent reads NO_RING_RECAP; None → today's words."""
    rows = []
    aud = V.is_audited(v)
    for doc in reads:
        sym = (doc.get("symbol") or "").upper()
        for setup in GC.SETUPS:
            r = (doc.get("setups") or {}).get(setup) or {}
            admit = _admit_of(r) if aud else None                # 🧪 2026-11-09 K3S — a 🧪-only A+ says so
            if aud and r.get("state") == _held_state():           # 🧪 2026-11-01 — a held A+ is a recap row too
                e, label = SUB_META[setup]
                rows.append((r.get("entry_bar_t") or "", sym, setup,
                             f"{e} {label} {ADMIT_RECAP_WORD if admit else HELD_RECAP_WORD} at "
                             f"{_hhmm(r.get('entry_bar_t')) or '—'} — broke "
                             f"{_px(r.get('trigger'))}, stop {_px(r.get('stop'))}"))
                continue
            if r.get("state") not in MARKED_STATES:
                continue
            e, label = SUB_META[setup]
            word = {"aplus": "A+", "triggered": "A+ (triggered)", "stopped": "A+, then stopped"}[r["state"]]
            if (entries is not None and r["state"] in NO_RING_RECAP
                    and (str(doc.get("date") or ""), sym, setup) not in entries):   # D10 2026-11-11 — never rang
                word = NO_RING_RECAP[r["state"]]
            rows.append((r.get("entry_bar_t") or "", sym, setup,
                         f"{e} {label} {word} at {_hhmm(r.get('entry_bar_t')) or '—'} — broke {_px(r.get('trigger'))}"
                         f", stop {_px(r.get('stop'))}" + (f" · 🧪 only by {admit}" if admit else "")))
    rows.sort()
    return {"title": f"Today's A+ recap — states only, no win/loss maths · {UNMEASURED}",
            "rows": [{"symbol": sym, "setup": setup, "text": text, "href": PT.deep_link(sym, setup, v)}
                     for _t, sym, setup, text in rows]}


# ── sub resolution (C9 deep links) ────────────────────────────────────────────────────────────────────────────────
def _pushed_potential_setup(potentials, sym: str, day: str) -> Optional[str]:
    """🧠 step of resolve_sub (BUILD_SPEC4 §3.9 (d), 2026-10-15): the setup of the session's newest PUSHED tracker
    doc of `sym` (tie → SETUPS order). The push-history link carries no setup (push.recent.item_url), so this opens
    the sub that rang. Held / unpushed docs and other sessions never count. Never raises."""
    try:
        order = {s: i for i, s in enumerate(GC.SETUPS)}
        hits = []
        for d in potentials or []:
            push = d.get("push") if isinstance(d, dict) else None
            if not isinstance(push, dict) or push.get("state") != "pushed":
                continue
            if str(d.get("symbol") or "").upper() != sym or d.get("date") != day or d.get("setup") not in order:
                continue
            at = push.get("at")
            if isinstance(at, str):
                try:
                    at = datetime.fromisoformat(at)
                except ValueError:
                    at = None
            when = _et(at).isoformat() if isinstance(at, datetime) else ""
            hits.append((when, -order[d["setup"]], d["setup"]))
        return max(hits)[2] if hits else None
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: potential focus read failed: %s", exc)
        return None


def resolve_sub(sub: str, focus: str, *, store, session: date, reads_by: dict, listed: dict,
                pm_syms: set, post_syms: set, potentials: Optional[list] = None, v=None) -> tuple:
    """(sub, resolved_from). An explicit known sub wins; an unknown one → DEFAULT_SUB (fail open). Empty sub + a
    focus symbol → the setup of today's newest pushed (or shadow-recorded) claim, else (2026-10-15) the setup of
    today's newest PUSHED 🧠 potential ("focus_potential"; `potentials` = the tracker docs `build` already read, None →
    store.potentials(session), a failure → none), else the best-ranked read's setup, else ☀️ / 🌙 when the name is
    on that list, else the default."""
    s = (sub or "").strip().lower()
    if s:
        return (s, "param") if s in SUB_KEYS else (GC.DEFAULT_SUB, "default")
    sym = (focus or "").strip().upper()
    if not sym:
        return GC.DEFAULT_SUB, "default"
    day = session.isoformat()
    vv = V.of(v)
    # the variant's claim ids (GG5 "GG:…", the 1-minute page "GG1:…" — alerts.claim_key's shape)
    ids = [f"{p}{vv.claim_prefix}:{day}|{sym}|{st}" for st in GC.SETUPS for p in ("", "SHADOW:")]
    claims = [d for d in _alerts_find(store, ids) if d.get("state") in ("pushed", "shadow")]
    if claims:
        def _when(d):
            v = d.get("claimed_at")
            return _et(v).isoformat() if isinstance(v, datetime) else str(v or "")
        newest = max(claims, key=lambda d: (_when(d), str(d.get("_id"))))
        setup = str(newest.get("_id")).rsplit("|", 1)[-1]
        if setup in GC.SETUPS:
            return setup, "focus_alert"
    if potentials is None:
        try:
            potentials = store.potentials(session) or []            # None = a read fault (2026-10-15): soft here
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala tab: potentials read failed: %s", exc)
            potentials = []
    pot_setup = _pushed_potential_setup(potentials, sym, day)
    if pot_setup:
        return pot_setup, "focus_potential"
    doc = reads_by.get(sym)
    if doc:
        best = None
        for i, setup in enumerate(GC.SETUPS):
            r = (doc.get("setups") or {}).get(setup) or {}
            # a read the 🌀 listing rule holds back has no card there — a focus link must not open an empty sub
            # (BUILD_SPEC18 D3; critic 2026-10-20)
            if r.get("state") not in TILE_STATES or not _vcp_listed(setup, r):
                continue
            t = {"symbol": sym, "gajjala": dict(r, _last=_last_close(doc, r.get("frame") or vv.primary, vv),
                                                _bars_to_go=_bars_to_go(r))}
            k = (order_key(t), i)
            if best is None or k < best[0]:
                best = (k, setup)
        if best:
            return best[1], "focus_read"
    if sym in pm_syms:
        return "premarket", "focus_list"
    if sym in post_syms:
        return "postmarket", "focus_list"
    return GC.DEFAULT_SUB, "default"


# ── 🧠 potential · 📈 track (BUILD_SPEC4 §3.9, 2026-10-15) ──────────────────────────────────────────────────────────
# Ajay 2026-10-15: "In Gajjalas setup I wanna find potential stocks … So create a potential category in this section."
# / "In all the sub tab and add a track and alert to show me new potential is added everyday." Every rule, word and
# order below is potential.py's (potential_kind / tell_values / tells / order_key / row_text / state_word / HELD_WORDS);
# this section only assembles the served shapes. No number is typed here.
WATCH_HEAD = ("👀 On his watch list, no structure yet — “if it's making some noise in pre-market I put them in my watch "
              "list … after hours moves from the past day, I'll keep them as well” (S8 13:21–14:34): ")    # W14
TRACK_UNMEASURED = ("UNMEASURED — what each potential did after it was first seen, recorded pass by pass; not a "
                    "forecast. No study has read this record yet.")                                        # W13b
TRACK_RECORD_FAULT = "🏁 The alert record could not be read this time — the next re-read tries again."    # W16
ENTRY_SENT_TEXT = "🎯 entry sent {at} ET"                                                     # DECISIONS10 D4 (E6)
PUSH_TEXT = {"no_target": "📲 no device took it (toggle off, quiet hours or none registered)",
             "failed": "📲 send failed",
             "claimed": "📲 sending"}           # W19's /alerts word for a claimed doc (a pass died before the settle)

# 🚫 NOT ELIGIBLE AT THE BROKER (2026-10-17, DECISIONS12 D1–D7, AMENDMENTS12). Ajay, verbatim: "ok then avoid showing me
# names that are not eligible in Fidelity then." / "Or just add a tag that not eligible on Fidelity". A TAG, never a
# filter: every row that names a symbol on his own list (store.broker_flags — the seed ∪ his adds − his removes) carries
# `broker_text`; nothing is hidden or counted-as-hidden (2026-11-09 ~10:30 ET, his word: his names sit at the BOTTOM of every
# card board — `broker_bottom`, a stable partition after each board's own order, never a hide). Served to the PRIMARY admin only (the route decides
# `owner`); anyone else reads null. The broker's name lives in constants.py; these are the only served words.
BROKER_FLAG_TEXT = f"🚫 not eligible at {GC.BROKER_NAME}"                       # DECISIONS12 D1 — the ONE served word
BROKER_FLAG_ICON = "🚫"                                                          # D5 — the card toggle (its title = BROKER_FLAG_TEXT)
BROKER_LIST_TEXT = "{text}: {symbols}"                                          # the 🪦 graveyard line's tag
BROKER_EMPTY_TEXT = "none on your list yet — add a ticker when its order ticket refuses it"
BROKER_FAULT_TEXT = "your list could not be read this time — the tags are off until the next read"   # AMENDMENTS12 F5
BROKER_ADD_LABEL = "add"
BROKER_ADD_PLACEHOLDER = "ticker"
BROKER_REMOVE_TITLE = "take it off the list"
BROKER_BAD_SYMBOL = (f"Not a ticker — letters, digits, “.” or “-”, starting with a letter, at most "
                     f"{GC.BROKER_SYMBOL_MAX_LEN} characters.")
BROKER_WRITE_FAULT = "The list could not be saved this time — nothing changed; try again."


def _broker_fold(sym) -> str:
    from chart_maps.gajjala import store as ST
    return ST.broker_fold(sym)


def broker_text_for(sym, flags) -> Optional[str]:
    """D2 — BROKER_FLAG_TEXT iff `sym` is on `flags` ("." and "-" folded on both sides, AMENDMENTS12 F8); `flags` None
    (a non-owner) → None; a name not on the list → None (no surface guesses eligibility)."""
    if flags is None or not isinstance(sym, str) or not sym.strip():
        return None
    k = _broker_fold(sym)
    return BROKER_FLAG_TEXT if any(_broker_fold(f) == k for f in flags) else None


def broker_bottom(rows: list, flags) -> list:
    """2026-11-09 ~10:30 ET — Ajay, verbatim: "The ones I am reporting they are not on Fidelity put them at the bottom".
    Every card board (the five setup subs, 🧠, ☀️, 🌙) keeps its own order and moves the rows whose symbol is on his list
    (store.broker_flags, "." / "-" folded like the tag) to the END in the same relative order — a stable partition, run
    AFTER the limit cut (critic 2026-11-09): the cards shown are the same set as without the list, only their order moves —
    the list never drops a card (the 🎾 board passed the 24-card limit on 4 of the last 6 sessions). The 🧠 strip rows
    take it too. Never hidden, never counted-as-hidden; the 🏁, the counts, the pushes and the 👀 line are untouched. The ORDER is the same for every viewer (the list is read for all);
    only the WORDS stay owner-only — the nothing-hidden invariant (owner payload minus the tags == non-owner payload)
    holds. `flags` None / empty → the rows byte-identical."""
    if not flags:
        return rows
    hit = [broker_text_for(r.get("symbol") if isinstance(r, dict) else None, flags) is not None for r in rows]
    return [r for r, h in zip(rows, hit) if not h] + [r for r, h in zip(rows, hit) if h]


def broker_block(flags, *, fault: bool = False) -> dict:
    """D3 / D5 — the owner's 🚫 strip block. A read fault (AMENDMENTS12 F5): `editable` False, `fault_text` served,
    never `empty_text` (the list is not "empty", it was not read)."""
    return {"editable": not fault, "symbols": sorted(flags or ()), "text": BROKER_FLAG_TEXT, "broker": GC.BROKER_NAME,
            "toggle": BROKER_FLAG_ICON, "empty_text": None if fault else BROKER_EMPTY_TEXT,
            "order_text": BROKER_BOTTOM_TEXT,                                 # 2026-11-09 — his names last, his word
            "fault_text": BROKER_FAULT_TEXT if fault else None, "add_label": BROKER_ADD_LABEL,
            "add_placeholder": BROKER_ADD_PLACEHOLDER, "remove_title": BROKER_REMOVE_TITLE}


def editor_block(store) -> dict:
    """D5 — GET …/broker-flags (and every write's answer): store.broker_doc {symbols, seed, added, removed} + the served
    word, the broker and `fault_text` (BROKER_FAULT_TEXT when the list could not be read — the seed alone is served and
    SAID so, AMENDMENTS12 F5; null when the read is fine). The store's `fault` flag itself is not served."""
    from chart_maps.gajjala import store as ST
    doc = ST.broker_doc(store)
    fault = bool(doc.pop("fault", False))
    return dict(doc, text=BROKER_FLAG_TEXT, broker=GC.BROKER_NAME, fault_text=BROKER_FAULT_TEXT if fault else None)


def _broker_tag(out: dict, flags) -> None:
    """D2 — in place: every §3.4 row that names a symbol gets `broker_text` (tiles, the 🧠 strip rows, 📈 track rows,
    👀 watch symbols, 🎯 A+ rows, 🌙 recap rows) and `graveyard_broker_text` sits beside `graveyard_text`. `flags` None
    → None everywhere. Nothing is removed or reordered (a TAG, never a filter)."""
    def tag(rows):
        for r in rows if isinstance(rows, list) else ():
            if isinstance(r, dict):
                r["broker_text"] = broker_text_for(r.get("symbol"), flags)

    tag(out.get("tiles"))
    for k in ("potential", "enterable"):
        if isinstance(out.get(k), dict):
            tag(out[k].get("rows"))
    tr = out.get("track")
    if isinstance(tr, dict):
        for k in ("today", "yesterday"):
            if isinstance(tr.get(k), dict):
                tag(tr[k].get("rows"))
    if isinstance(out.get("watch"), dict):
        tag(out["watch"].get("symbols"))
    pm = out.get("postmarket")
    if isinstance(pm, dict) and isinstance(pm.get("recap"), dict):
        tag(pm["recap"].get("rows"))
    if "graveyard_text" in out:
        hit = [s for s in out.get("graveyard_today") or [] if broker_text_for(s, flags)]
        out["graveyard_broker_text"] = (BROKER_LIST_TEXT.format(text=BROKER_FLAG_TEXT, symbols=", ".join(hit))
                                        if hit else None)


def _trader_tag(out: dict, tags) -> None:
    """📌 2026-10-27 — in place, the SAME walk as _broker_tag: every row that names a symbol (tiles, the 🧠 / 🎯 rows,
    📈 track rows, 👀 watch symbols, 🌙 recap rows) gets `trader_text` — "📌 {handle}" when a flagged trader's posted
    name put or tagged it on his list (trader_names.tag_map), None otherwise. Served to EVERY viewer (HIS CALL #10).
    Nothing is removed or reordered."""
    tags = tags if isinstance(tags, dict) else {}

    def tag(rows):
        for r in rows if isinstance(rows, list) else ():
            if isinstance(r, dict):
                sym = r.get("symbol")
                r["trader_text"] = ((tags.get(str(sym).upper()) or {}).get("trader_text")
                                    if isinstance(sym, str) and sym else None)

    tag(out.get("tiles"))
    for k in ("potential", "enterable"):
        if isinstance(out.get(k), dict):
            tag(out[k].get("rows"))
    tr = out.get("track")
    if isinstance(tr, dict):
        for k in ("today", "yesterday"):
            if isinstance(tr.get(k), dict):
                tag(tr[k].get("rows"))
    if isinstance(out.get("watch"), dict):
        tag(out["watch"].get("symbols"))
    pm = out.get("postmarket")
    if isinstance(pm, dict) and isinstance(pm.get("recap"), dict):
        tag(pm["recap"].get("rows"))


def _promo_tag(out: dict, ptags) -> None:
    """🎪 2026-10-29 — in place, the SAME walk as _trader_tag: a row whose symbol the Promo circuit put or tagged on
    his list (promo_names.tag_map) gains `promo_text`; every other row is left byte for byte (no key). Every viewer."""
    ptags = ptags if isinstance(ptags, dict) else {}
    if not ptags:
        return

    def tag(rows):
        for r in rows if isinstance(rows, list) else ():
            if isinstance(r, dict) and isinstance(r.get("symbol"), str) and r["symbol"]:
                hit = ptags.get(r["symbol"].upper())
                if hit:
                    r["promo_text"] = hit.get("promo_text")

    tag(out.get("tiles"))
    for k in ("potential", "enterable"):
        if isinstance(out.get(k), dict):
            tag(out[k].get("rows"))
    tr = out.get("track")
    if isinstance(tr, dict):
        for k in ("today", "yesterday"):
            if isinstance(tr.get(k), dict):
                tag(tr[k].get("rows"))
    if isinstance(out.get("watch"), dict):
        tag(out["watch"].get("symbols"))
    pm = out.get("postmarket")
    if isinstance(pm, dict) and isinstance(pm.get("recap"), dict):
        tag(pm["recap"].get("rows"))


def _stage_tag(out: dict, st, session: date, have: dict, *, is_today: bool, v=None, entries=None) -> None:
    """🧭 2026-11-11 — in place: every card in out["tiles"] whose symbol has a 🧠 tracker doc or a rang A+ in the
    listing window (SC._window(session) = the board's session + GC.STAY_LISTED_SESSIONS before it) gains
    gajjala["stages"]. `have` = {date: docs} already read by build (today, prev); the window's other sessions are read
    here (ONE find each) — never per card. `entries` (review fix 2026-11-11, D10) = build's ONE _entry_times read over
    the window, handed in as a zero-arg callable (read at most once per build, only when a card exists); None → its own
    read (a direct caller). 🧪 keeps its separate st.shared read (🚩's claims). Every block is computed FIRST, then
    all are assigned (a raise → no card has the key). A card with no tag keeps every byte. Never reorders, drops or
    gates."""
    from chart_maps.gajjala import scanner as SC
    tiles = [t for t in out.get("tiles") or [] if isinstance(t, dict) and isinstance(t.get("gajjala"), dict)]
    if not tiles:
        return
    win = SC._window(session)
    days = {d: (have[d] if d in have else _safe_list(st.potentials, d)) for d in win}
    aud = V.is_audited(V.of(v))
    if aud:                                              # 🧪 → 🚩's claims (the tracker is borrowed; GGA's own are shadow)
        src = getattr(st, "shared", None)
        entries = (_entry_times(src, win, None) or {}) if src is not None else {}
    elif callable(entries):
        entries = entries() or {}                        # build's ONE alert_rows read (D10); None (a fault) → {}
    else:
        entries = _entry_times(st, win, v) or {}         # `or {}`: a read fault answers None (D10)
    syms = {str(t.get("symbol") or "").upper() for t in tiles}
    by = SG.by_symbol(days, board_session=session, is_today=is_today, symbols=syms, cadence_min=_cad(v),
                      borrowed=aud, entries=entries)
    adds = [(t, SG.for_tile(by[s], t["gajjala"].get("setup"), session))
            for t in tiles for s in [str(t.get("symbol") or "").upper()] if by.get(s)]             # all first
    for t, b in adds:
        t["gajjala"]["stages"] = b


def _soft(what: str, fn, *a, default=None, **kw):
    """D1 on the read path: a raising 🧠 potential / 📈 track piece logs and serves `default`; it never takes down the
    A+ board of any sub."""
    try:
        return fn(*a, **kw)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: %s failed: %s", what, exc)
        return default


def _safe_list(fn, *a) -> list:
    """A store read that may be missing (an older store) or fail: [] — the documented "no data" answer."""
    try:
        out = fn(*a)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: potential read failed: %s", exc)
        return []
    return [d for d in out or [] if isinstance(d, dict)]


def _setup_label(setup: str) -> str:
    e, label = SUB_META.get(setup, ("🧠", setup))
    return f"{e} {label}"


def _potential_reads(reads_by: dict, scan_by: dict, *, trackers: dict, trackers_prev: set, ah_prev, prev_scan_by: dict,
                     setup: Optional[str] = None, v=None) -> list:
    """Every (symbol, setup) potential of the board's listed reads — `setup` given: that setup only — as
    [(order_key, PotRow, read_doc, read)] in potential.order_key order (one order everywhere). `trackers` =
    {(SYM, setup): today's tracker doc} (first_seen_et); `trackers_prev` = {(SYM, setup)} of the session before (↻)."""
    out = []
    for sym, doc in reads_by.items():
        setups = doc.get("setups") if isinstance(doc.get("setups"), dict) else {}
        kinds = {s: PT.potential_kind(setups.get(s)) for s in GC.SETUPS}
        also = [s for s in GC.SETUPS if kinds[s]]
        for s in GC.SETUPS:
            kind = kinds[s]
            if not kind or (setup is not None and s != setup):
                continue
            read = setups.get(s) or {}
            again = (sym, s) in trackers_prev
            values = PT.tell_values(sym, s, ctx=doc.get("ctx"), scan_row=(scan_by.get(sym) or {}).get("last"),
                                    ah_prev=ah_prev, prev_scan=prev_scan_by.get(sym), also=also, again=again)
            tdoc = trackers.get((sym, s)) or {}
            first = tdoc.get("first_seen_et") if isinstance(tdoc.get("first_seen_et"), str) else None
            reason = read.get("reason") if isinstance(read.get("reason"), str) and read.get("reason") else None
            row = {"symbol": sym, "setup": s, "kind": kind, "kind_label": PT.KIND_LABEL[kind],
                   "trigger": _f(read.get("trigger")), "stop": _f(read.get("stop")), "risk_pct": _f(read.get("risk_pct")),
                   "reason": reason, "first_seen_et": first, "again": again, "tells": PT.tells(values),
                   "href": PT.deep_link(sym, s, v), "text": PT.row_text(sym, s, read, kind, first)}
            out.append((PT.order_key(kind, values, s, sym), row, doc, read))
    out.sort(key=lambda x: x[0])
    return out


def _potential_strip(setup: str, pots: list, today_n: int, *, sess: dict, in_window: bool, v=None,
                     flags=None) -> dict:
    """§3.9 (a) — the 🧠 strip of one setup sub (W6 title, W7 text, W8 empty), ALL of its potentials (a compact list,
    never cut by `limit`). 🚫 2026-11-09: `flags` = his list → its names last (broker_bottom), none dropped."""
    rows = broker_bottom([p[1] for p in pots], flags)                 # 🚫 2026-11-09 — his names last, every row kept
    a = sum(1 for r in rows if r["kind"] == GC.POTENTIAL_KINDS[0])
    b = sum(1 for r in rows if r["kind"] == GC.POTENTIAL_KINDS[1])
    concept, ts = PT.CONCEPT
    defaults = PT.defaults_sentence()
    text = ("Forming, not triggered: the run up is in and the quiet sideways part has started (“building”) or is "
            "complete (“trigger armed”); the reclaim of the highs has not printed. "
            f"His words: “{concept}” ({ts}). " + (f"{defaults} " if defaults else "") + "A potential, not an entry.")
    e, label = SUB_META[setup]
    empty = None
    if not rows:
        empty = (f"No {e} {label} forming right now — the next pass is at most {_mins(_cad(v))} "
                 "away." if in_window else f"No {e} {label} was forming at the last pass ({sess['label']}).")
    return {"title": f"🧠 Potential — {a} trigger armed · {b} building · {today_n} first seen {sess['label']} · "
                     f"{UNMEASURED}",
            "text": text, "counts": {"armed": a, "building": b, "today": today_n}, "rows": rows, "empty_text": empty}


def _potential_tiles(pots: list, *, st, session: date, tf_ask: str, scan_row, sess: dict, listed: dict,
                     halts_by: dict, pass_at: Optional[datetime] = None, v=None,
                     carry: Optional[dict] = None, prev_iso: Optional[str] = None,
                     entries: Optional[dict] = None) -> list:
    """§3.9 (b) — one tile per SYMBOL: the existing `setup_tile` card of its PRIMARY potential (the first by
    potential.order_key), with `gajjala.potential` (W12) and the 🧩 other setups forming on it (GG S9 1:59:01).
    `entries` (D10, 2026-11-11) = build's ONE _entry_times read on a live-push page, else None → each card's `rang`."""
    by_sym: dict = {}
    for p in pots:
        by_sym.setdefault(p[1]["symbol"], []).append(p)
    tiles = []
    for sym, items in sorted(by_sym.items(), key=lambda kv: kv[1][0][0]):
        _k, row, doc, read = items[0]
        setup = row["setup"]
        daily = st.get_daily(session, sym) if setup == "reversal_squeeze" else None
        vv = V.of(v)
        tile = setup_tile(doc, setup, tile_tf(read, tf_ask, vv.primary, vv), scan_row=scan_row(sym), sess=sess,
                          listed=listed.get(sym), halt_doc=halts_by.get(sym), daily=daily, pass_at=pass_at, v=vv,
                          carry=carry, prev_iso=prev_iso,                 # 🎾 2026-11-08 — build's ONE carry read
                          rang=_rang(entries, session, sym, setup))       # D10 2026-11-11 — None → today's words
        first = row["first_seen_et"]
        tile["gajjala"]["potential"] = {
            "kind": row["kind"], "kind_label": row["kind_label"], "setup": setup, "setup_label": _setup_label(setup),
            "first_seen_et": first, "again": row["again"], "tells": row["tells"],
            "also": [{"setup": p[1]["setup"], "label": _setup_label(p[1]["setup"])} for p in items[1:]],
            "text": f"🧠 {row['kind_label']} · {_setup_label(setup)}" + (f" · first seen {first} ET" if first else "")}
        tiles.append(tile)
    return tiles


def _track_row(doc: dict, entries: Optional[dict] = None, v=None, live: bool = False) -> dict:
    """One 📈 Track row from a tracker doc (W13) — the doc's own prices (the pass wrote them, AMENDMENTS4 D2: the
    5-minute frame's closed close first), never recomputed here; states and prices only, no win/loss maths — and the
    🎯 entry that rang (DECISIONS10 D4): `entries` = _entry_times' {(date_iso, SYM, setup): "HH:MM"}; `entry_text` is
    always served, None when no live A+ entry of the row's key rang.
    `live` (formulas audit D10, 2026-11-11) = a live-push page: with `entries` read (not None) and the row's key absent,
    the "now …" word of a `triggered` last state and every `triggered` timeline step read NO_RING_RECAP["triggered"]
    (no A+ claim for an alert that never rang). live False (every bare call) → today's bytes."""
    sym = str(doc.get("symbol") or "").upper()
    setup = str(doc.get("setup") or "")
    entry_at = (entries or {}).get((str(doc.get("date") or ""), sym, setup))
    no_ring = (live and entries is not None
               and (str(doc.get("date") or ""), sym, setup) not in entries)   # D10 2026-11-11
    entry_text = ENTRY_SENT_TEXT.format(at=entry_at) if entry_at else None
    last = doc.get("last") if isinstance(doc.get("last"), dict) else {}
    path = [e for e in doc.get("state_path") or [] if isinstance(e, dict)]
    grave = doc.get("graveyard_on") if isinstance(doc.get("graveyard_on"), str) else None
    if last:
        last_state, last_kind = last.get("state"), last.get("kind")
    else:
        last_state, last_kind = (path[-1].get("state"), path[-1].get("kind")) if path else (None, None)
    last_text = (NO_RING_RECAP["triggered"] if no_ring and last_state == "triggered"
                 else PT.state_word(last_state, last_kind))
    p0, p1, t0 = _f(doc.get("first_px")), _f(last.get("px")), _f(doc.get("first_trigger"))
    m, v = _f(doc.get("move_pct")), _f(doc.get("vs_trigger_pct"))
    move_text = f"{_px(p0)} → {_px(p1)} ({m:+.1f}%) since first seen" if m is not None and p0 and p1 else None
    vs_text = f"{v:+.1f}% vs the trigger at first sight ({_px(t0)})" if v is not None and t0 else None
    push = doc.get("push") if isinstance(doc.get("push"), dict) else None
    push_text = None
    if push:
        ps = push.get("state")
        if ps == "pushed":
            push_text = "📲 sent" + (f" {push['at_et']} ET" if isinstance(push.get("at_et"), str) else "")
        else:
            push_text = PUSH_TEXT.get(ps)
    else:
        hw = PT.held_words(v)                                       # GG5: HELD_WORDS itself (2026-10-27: per variant)
        held = [h.get("reason") for h in doc.get("held") or [] if isinstance(h, dict)
                and (h.get("reason") in hw or h.get("reason") in PT.ADD_HELD)]
        if not held and doc.get("first_seen_mode") == PT.FIRST_SEEN_MODES[1]:
            held = [PT.JOIN_HELD[0]]                                # D9: a joined doc whose hold write was lost
        if held:
            push_text = (TN.TRADER_HOLD_TEXT if held[-1] in PT.TRADER_HELD          # 📌 A2 2026-10-27, verbatim
                         else PN.PROMO_HOLD_TEXT if held[-1] in PT.PROMO_HELD       # 🎪 2026-10-29, verbatim
                         else f"held: {hw[held[-1]]}")
    timeline = []
    for e in path:
        at_et = e.get("at_et") if isinstance(e.get("at_et"), str) else None
        word = (NO_RING_RECAP["triggered"] if no_ring and e.get("state") == "triggered"
                else PT.state_word(e.get("state"), e.get("kind"), on=grave if e.get("state") == "graveyard" else None))
        timeline.append({"at_et": at_et, "text": f"{at_et} {word}" if at_et else word})
    first = doc.get("first_seen_et") if isinstance(doc.get("first_seen_et"), str) else None
    fk = doc.get("first_kind")
    fkl = PT.KIND_LABEL.get(fk)
    bits = [f"{sym} · {_setup_label(setup)}", (f"first seen {first} ET" + (f" {fkl}" if fkl else "")) if first else fkl,
            f"now {last_text}", move_text]
    url = doc.get("url")
    href = (url if isinstance(url, str) and url.startswith("/") and not url.startswith("//")
            else PT.deep_link(sym, setup, v))
    return {"symbol": sym, "setup": setup, "setup_label": _setup_label(setup), "first_seen_et": first,
            "first_kind": fk, "first_kind_label": fkl, "first_px": p0, "first_trigger": t0,
            "first_stop": _f(doc.get("first_stop")), "last_state": last_state, "last_state_text": last_text,
            "last_px": p1, "move_pct": m, "move_text": move_text, "vs_trigger_pct": v, "vs_trigger_text": vs_text,
            "push_text": push_text, "entry_text": entry_text, "graveyard_on": grave, "timeline": timeline,
            "brk_text": _soft("break track word", _brk_track_text, doc, default=None),   # ⚡ 2026-11-11
            "text": " · ".join(b for b in bits if b), "href": href}


def _first_seen_key(doc: dict) -> str:
    v = doc.get("first_seen")
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            v = None
    return _et(v).isoformat() if isinstance(v, datetime) else str(doc.get("first_seen_et") or "")


def _capped(rows: list) -> dict:
    out = {"rows": rows[:GC.TILE_LIMIT_MAX]}
    if len(rows) > GC.TILE_LIMIT_MAX:
        out["more_n"] = len(rows) - GC.TILE_LIMIT_MAX
    return out


def _track_block(today_docs: list, prev_docs: list, *, session: date, prev: date, sess: dict,
                 entries: Optional[dict] = None, v=None, live: bool = False) -> dict:
    """§3.9 (b) `track` — today's first sightings newest first, the session before chronological (no outcome
    ranking), each row's timeline in potential.state_word's words; rows capped at TILE_LIMIT_MAX (`more_n`).
    `entries` = _entry_times' answer, handed to every row (DECISIONS10 D4); `live` = a live-push page (D10 2026-11-11)."""
    order = {s: i for i, s in enumerate(GC.SETUPS)}

    def tie(d):
        return (str(d.get("symbol") or ""), order.get(d.get("setup"), len(order)))
    today = sorted(today_docs, key=tie)
    today = sorted(today, key=_first_seen_key, reverse=True)
    yday = sorted(sorted(prev_docs, key=tie), key=_first_seen_key)
    n = len(today)
    first, last = PT.pass_times(session) if V.is_gg5(v) else PT.pass_times(session, v)
    return {"title": f"📈 Track — {n} potentials first seen {sess['label']} · {UNMEASURED}",
            "unmeasured": TRACK_UNMEASURED,
            "empty_today": (f"No potential first seen yet this session — the pass runs every "
                            f"{_mins(_cad(v))} from {first} to {last} ET."),
            "today": dict({"date": session.isoformat(), "label": sess["label"], "n": n,
                           "armed_n": sum(1 for d in today if d.get("first_kind") == GC.POTENTIAL_KINDS[0]),
                           "building_n": sum(1 for d in today if d.get("first_kind") == GC.POTENTIAL_KINDS[1]),
                           "pushed_n": sum(1 for d in today if isinstance(d.get("push"), dict)
                                           and d["push"].get("state") == "pushed")},
                          **_capped([_track_row(d, entries=entries, v=v, live=live) for d in today])),
            "yesterday": dict({"date": prev.isoformat(),
                               "title": (f"Last session ({prev.isoformat()}) — {len(yday)} potentials and how each "
                                         "ended: states and prices only, no win/loss maths"),
                               "n": len(yday)}, **_capped([_track_row(d, entries=entries, v=v, live=live) for d in yday]))}


def _watch_block(pm_rows: list, post_list: list, exclude: set, v=None) -> Optional[dict]:
    """W14 — ☀️ / 🌙 list names with NO structure yet (GG S8 13:21–14:34): `exclude` = every name with a potential
    in any setup PLUS every name whose read shows a card in any setup sub (a TILE_STATES read — A+, triggered,
    partial, stopped, forming), so the line's own words "no structure yet" stay true. Display only: never pushed,
    never tracked (HIS CALL P9). None when there is none."""
    syms, seen = [], set(exclude)
    for rows, sub in ((pm_rows, "premarket"), (post_list, "postmarket")):
        for r in rows or []:
            sym = str((r or {}).get("symbol") or "").upper()
            if sym and sym not in seen:
                seen.add(sym)
                syms.append({"symbol": sym, "href": f"/chart-maps?tab={V.of(v).tab}&sub={sub}&focus={sym}"})
    if not syms:
        return None
    return {"text": WATCH_HEAD + ", ".join(s["symbol"] for s in syms), "symbols": syms}


# ── the payload ───────────────────────────────────────────────────────────────────────────────────────────────────
def _awaiting(setup: str) -> Optional[dict]:
    from chart_maps.gajjala import detectors as D
    text = D._awaiting(setup)
    if not text:
        return None
    h = next((h for h in GC.PLACEHOLDER_BY_SETUP.get(setup, ())
              if any(getattr(GC, n, None) is None for n in GC.PLACEHOLDERS.get(h, ()))),
             (GC.PLACEHOLDER_BY_SETUP.get(setup) or ("?",))[0])
    e, label = SUB_META[setup]
    return {"setup": setup, "his_call": h,
            "text": f"{e} {label}: waiting for your number ({h}) — it reads nothing until you answer"}


def _ledger():
    """🏁 ledger.py, imported lazily (it imports this module's neighbours); None when it cannot load — the other subs
    still serve and the 🏁 sub serves TRACK_RECORD_FAULT."""
    try:
        from chart_maps.gajjala import ledger as LG
        return LG
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: ledger import failed: %s", exc)
        return None


def _entry_times(st, sessions, v=None) -> Optional[dict]:
    """DECISIONS10 D4 — {(date_iso, SYM, setup): "HH:MM"} of the live A+ entries that RANG on these sessions: ONE read
    (store.alert_rows — the ledger's own) classified by ledger.alert_of (line "live" = a `GG:` claim in state pushed;
    shadow / refusals / claimed / failed / no_target are never entries). Formulas audit D10 (2026-11-11): tri-state —
    no ledger / a read fault / no handle (alert_rows None) → None (UNKNOWN, never "nothing rang"); {} = read fine,
    nothing rang. Each doc in its own try (AMENDMENTS10 F8): one malformed doc never blanks the others."""
    LG = _ledger()
    if LG is None:
        return None
    docs = st.alert_rows(sessions)
    if docs is None:
        return None
    out = {}
    for d in docs:
        try:
            a = (LG.alert_of(d, LG.KINDS[1]) if V.is_gg5(v)                  # GG5: the call as always
                 else LG.alert_of(d, LG.KINDS[1], variant=v))
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala tab: an A+ entry doc could not be read: %s", type(exc).__name__)
            continue
        if a and a.get("line") == LG.LINES[0] and a.get("at_et"):
            out[(a["date"], a["symbol"], a["setup"])] = a["at_et"]
    return out


def _rang(entries: Optional[dict], session, sym: str, setup: str) -> Optional[bool]:
    """D10 (2026-11-11): did the live A+ alert of (session, sym, setup) ring? None when `entries` is None (unknown, or a
    shadow page) → every word stays today's."""
    if entries is None:
        return None
    return (session.isoformat(), sym, setup) in entries


_UNSET = object()


def day2_block(st, session: date, prev: date, listed, v=None, *, entries=_UNSET, carry=_UNSET) -> Optional[dict]:
    """🌅 2026-11-11 entry spec §3.7 (proposal #8) — GG5's ☀️ pre-market sub only; a LIST, never a push.
    Rows: (a) yesterday's A+ that RANG LIVE (_entry_times — store.alert_rows classified by ledger.alert_of, line "live"
    only: shadow, refusals, claimed, failed, no_target never count), ONE row per symbol = its earliest ring (the
    first-ring-counts rule of ledger.dedupe_trades), ordered by ring time; then (b) yesterday's after-hours carry names
    (store.ah_carry(prev), the doc's own order) not already in (a). " · on today's list" when the name is listed today.
    `entries` = build's ONE window read (a zero-arg callable or its dict; None = a read fault); unset → its own
    `_entry_times(st, [prev], v)`. `carry` = build's ONE carry read; unset → its own. An UNKNOWN entries read (None)
    serves None — never "No A+ rang" on a read that failed (the house tri-state, _ledger_count). 2026-11-11 critic
    fix: an UNKNOWN carry (None — the read faulted, or no after-hours pass wrote yesterday's doc; replace_ah_carry
    writes `names: {}` when a pass ran and nothing passed) serves None the same way — never "no after-hours mover
    passed" on a carry that was never read. The entries read still runs first (ONE read per ☀️ build either way)."""
    if entries is _UNSET:
        entries = _entry_times(st, [prev], v)
    elif callable(entries):
        entries = entries()
    if entries is None:
        return None
    if carry is _UNSET:
        carry = st.ah_carry(prev)
    if not isinstance(carry, dict):
        return None
    listed = listed or {}
    day = prev.isoformat()
    order = {s: i for i, s in enumerate(GC.SETUPS)}
    first: dict = {}                                                # SYM → (at, setup order, setup)
    for (d, sym, setup), at in entries.items():
        if d != day or not isinstance(at, str) or not sym:
            continue
        sym = str(sym).upper()
        k = (at, order.get(setup, len(order)), setup)
        if sym not in first or k < first[sym]:
            first[sym] = k
    rows = []
    for sym, (at, _o, setup) in sorted(first.items(), key=lambda kv: (kv[1][0], kv[0])):
        text = DAY2_APLUS_TEXT.format(sym=sym, setup_label=_setup_label(setup), at=at)
        rows.append({"symbol": sym, "text": text + (DAY2_LISTED_TEXT if sym in listed else ""),
                     "href": PT.deep_link(sym, setup, v) if not V.is_gg5(v) else PT.deep_link(sym, setup)})
    names = carry.get("names") if isinstance(carry, dict) else None
    seen = set(first)
    for sym in (names or {}) if isinstance(names, dict) else ():
        sym = str(sym or "").upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        rows.append({"symbol": sym, "text": DAY2_CARRY_TEXT.format(sym=sym) + (DAY2_LISTED_TEXT if sym in listed else ""),
                     "href": f"/chart-maps?tab={V.of(v).tab}&sub=premarket&focus={sym}"})
    return {"title": DAY2_TITLE, "note": DAY2_NOTE, "rows": rows, "empty_text": DAY2_EMPTY}


def focus_block(tiles: list, order_flags) -> Optional[dict]:
    """🔝 2026-11-11 entry spec §3.8 (proposal #9) — display only. When the board serves MORE than GC.FOCUS_N cards,
    the first GC.FOCUS_N of the served order (run AFTER broker_bottom) whose symbol is NOT on his 🚫 list
    (`order_flags` — read for EVERY viewer, so every reader sees the same focus cards; never the owner-only `flags`)
    get `tile["focus"] = True` and the block {n, text} is returned; else None and no card is marked. Never reorders,
    drops or gates a card. Every mark is computed FIRST, then assigned (a raise marks nothing). 2026-11-11 critic fix:
    the header says "the first five cards", so it is served (and the cards marked) only when exactly GC.FOCUS_N
    non-🚫 cards are picked — fewer (his 🚫 names fill the rest) → None and no card is marked."""
    rows = [t for t in tiles or [] if isinstance(t, dict)]
    if len(rows) <= GC.FOCUS_N:
        return None
    picks = [t for t in rows if broker_text_for(t.get("symbol"), order_flags or None) is None][:GC.FOCUS_N]
    if len(picks) < GC.FOCUS_N:                                     # 🚫 names leave fewer than five → no header, no mark
        return None
    for t in picks:
        t["focus"] = True
    return {"n": GC.FOCUS_N, "text": FOCUS_TEXT}


def _ledger_count(st, session: date, v=None) -> Optional[int]:
    """🏁 chip: ledger.count_today over today's tracker docs and today's ledger docs; None when the ledger cannot load
    or EITHER read faulted (an unknown count is never served as 0). The tracker is read here with `st.potentials`
    directly, never through `_safe_list` (which turns a read fault into [] — a chip of 0; critic LOW 2026-10-16)."""
    LG = _ledger()
    if LG is None:
        return None
    pots = st.potentials(session)
    if pots is None:
        return None
    docs = st.ledger_docs([session])
    if docs is None:
        return None
    rows = [d for d in pots if isinstance(d, dict) and d.get("symbol") and d.get("setup")]
    return LG.count_today(rows, docs) if V.is_gg5(v) else LG.count_today(rows, docs, variant=v)


def build(sub: str = "", *, tf: str = "", focus: str = "", limit: int = GC.TILE_LIMIT_DEFAULT, sort: str = "",
          span: str = "", now: Optional[datetime] = None, store=None, today: Optional[dict] = None,
          owner: bool = False, variant=None) -> dict:
    """The served board. Reads Mongo only (BUILD_SPEC §3.4.1). `span` = the 🏁 Track record day picker (ignored on
    every other sub); `today` = the route's ledger.today_read answer (🏁 only, None = not read on this open).
    🚫 `owner` (2026-10-17, DECISIONS12 D3): `is True` only — the primary admin is served `broker_flags` and every row's
    `broker_text`; anyone else (and a truthy Query / Depends object) reads null on every one. A TAG, never a filter.
    2026-11-09 ~10:30 ET (his word): the ORDER follows his list for EVERY viewer — `broker_bottom` moves his names to the
    end of each card board after its own order; the words stay owner-only, nothing is hidden.
    🚩 `variant` (2026-10-27, BUILD_SPEC27 §3.7): None → GG5, this tab, every byte as before (the store's own variant
    when a store is handed in); V.GG1 → the 1-minute page off ST.for_variant(GG1) — its frames, cadence, stale and push
    words, links, `tab` and the ONE added key `variant` (variant.served_block). The broker list stays ONE list."""
    from chart_maps.gajjala import store as ST
    if store is not None:
        st = store
    elif variant is not None:
        st = ST.for_variant(V.of(variant))
    else:
        st = _store(store)
    v = V.of(variant) if variant is not None else V.of(st)
    gg5 = V.is_gg5(v)
    aud = V.is_audited(v)                       # 🧪 2026-11-01 — every audited edit below is guarded by this
    live_push = V.push_mode(v) == "live"        # D10 2026-11-11 — GG5 / GG1 live; 🧪 shadow → every word as before
    _bf, bfault = _soft("broker flags", ST.broker_flags, st, default=(tuple(GC.BROKER_FLAG_SEED), True))
    order_flags = frozenset(_bf)                # 2026-11-09 ~10:30 ET: read for EVERY viewer — the ORDER follows his list
    flags = order_flags if owner is True else None   # the WORDS stay owner-only (DECISIONS12 D3)
    if owner is not True:
        bfault = False
    now = now or _clock()
    session, is_today, in_window = session_for(now)
    try:
        lim = max(1, min(int(limit), GC.TILE_LIMIT_MAX))
    except (TypeError, ValueError):
        lim = GC.TILE_LIMIT_DEFAULT
    from chart_maps.gajjala import scanner as SC
    try:
        listed = SC.listed_symbols(st, session)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: listed read failed: %s", exc)
        listed = {}
    reads = [d for d in st.reads(session) if d.get("symbol")]
    if listed:
        reads = [d for d in reads if d["symbol"].upper() in listed]
    reads_by = {d["symbol"].upper(): d for d in reads}
    astats = None
    if aud:                                     # 🧪 the audit overlay laid on 🚩's reads at serve time (never stored)
        from chart_maps.gajjala import audited_tab as AT
        reads_by, astats = _soft("audit overlay", AT.overlay_reads, reads_by, st, session, default=(reads_by, None))
    scan_docs = [d for d in st.scan_docs([session]) if d.get("symbol")]
    scan_by = {d["symbol"].upper(): d for d in scan_docs}
    halts_by = {d["symbol"].upper(): d for d in st.halts(session) if d.get("symbol")}
    latest = st.latest_pass()
    spass = session_pass(st, latest, session)
    # 🔄 / 🎯 (2026-10-15): the shown pass, the newest CRON pass (A10) and the lease — Mongo reads, each soft
    pass_doc = spass or latest
    pass_at = _at_utc(pass_doc)
    cron = _soft("cron pass read", _cron_ref, st, pass_doc, default=None)
    lease = _soft("lease read", st.lease_state, now, default={}) or {}
    sk = (sort or "").strip().lower() if isinstance(sort, str) else ""
    sk = sk if sk in dict(SORTS_PM) else SORT_PM_DEFAULT
    try:
        pm_rows = premarket_rows(st, session, scan_docs, spass, sk)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: premarket list failed: %s", exc)
        pm_rows = []
    post_list, unchecked = postmarket_rows(spass)
    # 🧠 the tracker + the previous session's tells, read ONCE and BEFORE resolve_sub (BUILD_SPEC4 WP-B)
    prev = _prev_market_day(session)
    pot_docs = [d for d in _safe_list(st.potentials, session) if d.get("symbol") and d.get("setup")]
    pot_prev = [d for d in _safe_list(st.potentials, prev) if d.get("symbol") and d.get("setup")]
    pot_ok = True                       # D1 on the read path: a raising potential layer never silences the A+ board
    ah_prev = None                      # 🎾 2026-11-08 — bound before the try: the squeeze cards read it either way
    try:
        trackers_today = {(str(d["symbol"]).upper(), d["setup"]): d for d in pot_docs}
        trackers_prev = {(str(d["symbol"]).upper(), d["setup"]) for d in pot_prev}
        try:
            ah_prev = st.ah_carry(prev)
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala tab: carry read failed: %s", exc)
            ah_prev = None
        prev_scan_by = {str(d["symbol"]).upper(): d for d in _safe_list(st.scan_docs, [prev]) if d.get("symbol")}
        pots = _potential_reads(reads_by, scan_by, trackers=trackers_today, trackers_prev=trackers_prev,
                                ah_prev=ah_prev, prev_scan_by=prev_scan_by, v=v)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: potential assembly failed: %s", exc)
        pot_ok, trackers_today, pots = False, {}, []
    pot_syms = {p[1]["symbol"] for p in pots}
    sub_k, resolved = resolve_sub(sub, focus, store=st, session=session, reads_by=reads_by, listed=listed,
                                  pm_syms={str(r.get("symbol")).upper() for r in pm_rows},
                                  post_syms={str(r.get("symbol")).upper() for r in post_list},
                                  potentials=pot_docs, v=v)
    tf_ask = (tf or "").strip().lower() if isinstance(tf, str) else ""
    tf_ask = tf_ask if tf_ask in v.tfs else ""                      # no / unknown tf → each card its read's frame
    tf_k = tf_ask or (v.slow if sub_k == "horizontal_fade" else v.primary)   # GG5: "15m" / "5m", as always
    sess = _session_block(now, session, is_today, in_window, v)

    def _row(sym):
        return dict(((scan_by.get(sym) or {}).get("last") or {}))

    # D10 2026-11-11 + 🧭 review fix: ONE alert_rows read per build, over the listing window (SC._window(session) ⊇
    # [session, prev]), made at most once and only when a consumer needs it — the setup-sub words, the 🧠 entries, the
    # 🌙 recap and the 🧭 stages all share it. Every consumer looks up (date_iso, SYM, setup), so the older window days
    # are never matched by the [session, prev] words.
    ent_win = list(SC._window(session))
    ent_win += [prev] if prev not in ent_win else []
    ent_memo: dict = {}

    def _entries_once():
        if "v" not in ent_memo:
            ent_memo["v"] = _soft("A+ entry read", _entry_times, st, ent_win, v, default=None)
        return ent_memo["v"]

    words_entries = _entries_once() if live_push and sub_k in GC.SETUPS else None   # before the tile loop
    # every setup's tiles — the counts on the strip, the tiles of the shown sub
    per_setup: dict = {}
    counts_by: dict = {}
    n_tiles: dict = {}
    tile_syms: set = set()                                          # names with a card in any setup sub (W14)
    unlisted: dict = {}                                             # 🌀 reads counted, not carded (BUILD_SPEC18 D3)
    for setup in GC.SETUPS:
        tiles, c = [], {k: 0 for k in COUNT_STATES}
        if aud:                                 # 🧪 a held A+ is counted under its own word, never folded into "none"
            c[_held_state()] = 0
        c["awaiting_answer"] = 0
        held = _awaiting(setup)
        for sym, doc in reads_by.items():
            r = (doc.get("setups") or {}).get(setup) or {}
            state = r.get("state") or "none"
            state = state if state in c else "none"
            awaiting = held is not None or (state == "none" and str(r.get("reason") or "").startswith("awaiting"))
            if not (awaiting and state == "none"):                     # a held read is "awaiting", never also "none"
                c[state] += 1
            if awaiting:
                c["awaiting_answer"] += 1
                continue
            if state in (TILE_STATES + ((_held_state(),) if aud else ())):   # 🧪 a held A+ keeps its card
                tile_syms.add(sym)                                      # it HAS structure — never on the 👀 line
                if not _vcp_listed(setup, r):                           # D3: counted above, not carded
                    unlisted[setup] = unlisted.get(setup, 0) + 1
                    continue
                n_tiles[setup] = n_tiles.get(setup, 0) + 1
                if setup == sub_k:                                      # only the shown sub builds its cards
                    daily = st.get_daily(session, sym) if setup == "reversal_squeeze" else None
                    tiles.append(setup_tile(doc, setup, tile_tf(r, tf_ask, tf_k, v), scan_row=_row(sym), sess=sess,
                                            listed=listed.get(sym), halt_doc=halts_by.get(sym), daily=daily,
                                            pass_at=pass_at, v=v, carry=ah_prev, prev_iso=prev.isoformat(),
                                            rang=_rang(words_entries, session, sym, setup)))
        tiles.sort(key=order_key)                                       # 🚫 the partition runs at the serving site, AFTER the cut
        c["listed"] = len(listed) if listed else len(reads_by)
        per_setup[setup], counts_by[setup] = tiles, c

    ptags = _soft("promo tags", lambda: PN.tag_map(st.scan_docs(SC._window(session))), default={})
    legend = count_legend(promo=PN.ran((spass or {}).get("promo")) or bool(ptags), audited=aud)   # D1 — ONE legend
    pot_title = next(r["text"] for r in legend if r["key"] == "potential")
    subs = []
    for key, e, label in GC.SUBS:
        if key == GC.LEDGER_SUB:                # 🏁 today's rows graded so far (ledger.count_today, AMENDMENTS9 E5)
            n = _soft("track record count", _ledger_count, st, session, v, default=None)
        else:
            n = (n_tiles.get(key, 0) if key in per_setup else len(pm_rows) if key == "premarket"
                 else len(post_list) if key == "postmarket" else len(pot_syms) if key == GC.POTENTIAL_SUB else None)
        subs.append({"key": key, "emoji": e, "label": label, "count": n,
                     "title": pot_title if key == GC.POTENTIAL_SUB else None})     # DECISIONS15 D1

    if sub_k in per_setup:
        counts = counts_by[sub_k]
    else:
        counts = {k: sum(c[k] for c in counts_by.values()) for k in list(COUNT_STATES) + ["awaiting_answer"]}
        if aud:
            counts[_held_state()] = sum(c.get(_held_state(), 0) for c in counts_by.values())
        counts["listed"] = len(listed) if listed else len(reads_by)
    out = {"tab": v.tab, "sub": sub_k, "sub_resolved_from": resolved, "tf": tf_k, "subs": subs,
           "session": sess, "pass": _pass_block(pass_doc, now, session, in_window, cron=cron, v=v),
           "strip": _strip_block(spass),
           "counts": counts, "counts_legend": legend, "tiles": [], "graveyard_today": [], "note": board_note(),
           "empty_note": None, "rules_section": "gajjala", "push": push_block() if gg5 else push_block(v),
           "push_potential": (_soft("potential push line", push_potential_block, session) if gg5 else
                              _soft("potential push line", push_potential_block, session, v)),
           "awaiting": [a for a in (_awaiting(s) for s in GC.SETUPS) if a],
           "broker_flags": broker_block(flags, fault=bfault) if flags is not None else None}
    if gg5:                                     # ⚡ 2026-11-11 entry spec §3.1 — GG5 only; a raising watch → None
        out["push_break"] = _soft("break push line", push_break_block, default=None)
    if not gg5:                                 # 🚩 2026-10-27 — the 1-minute page's ONE added key (never on GG5)
        out["variant"] = V.served_block(v)
    out["scan"] = _soft("scan line", scan_block, pass_doc, lease, now, in_window=in_window, session=session,
                        v=v, default=None)
    out["enterable"] = _soft("A+ banner", aplus_block, reads_by, pass_doc, now, in_window=in_window,
                             scan=out["scan"] or {}, cron=cron, session=session, v=v, default=None)
    if aud:                                     # 🧪 2026-11-01 — the strip and the held A+ section, every sub
        out["audited"] = _soft("audit strip", AT.audited_block, st, session, now, latest, astats, default=None)
        out["held"] = _soft("held A+", AT.held_block, reads_by, pass_doc, now, in_window=in_window,
                            scan=out["scan"] or {}, cron=cron, session=session, v=v, default=None)
    try:
        out["graveyard_today"] = SC.graveyard_today(st, session)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: graveyard read failed: %s", exc)
    if out["graveyard_today"]:
        out["graveyard_text"] = "🪦 moved to the graveyard today: " + ", ".join(out["graveyard_today"])

    if sub_k in per_setup:
        out["tiles"] = broker_bottom(per_setup[sub_k][:lim], order_flags)   # 🚫 2026-11-09 — his names last among the cards shown (cut first: the list only reorders)
        out["order_note"] = (RS_ORDER_TEXT if sub_k == "reversal_squeeze" else          # DECISIONS13 D3 — served word
                             HF_ORDER_TEXT if sub_k == "horizontal_fade" else          # 🧪 2026-11-08 — the ➖ word
                             VOL_ORDER_TEXT)                                           # 2026-11-09 — every other setup sub
        out["list_note"] = (_soft("vcp list note", vcp_list_note, unlisted.get(sub_k, 0))
                            if sub_k == "intraday_vcp" else None)                # BUILD_SPEC18 D3 — served line
        e, label = SUB_META[sub_k]
        out["empty_note"] = (f"No {e} {label} on his list right now — the next pass is at most "
                             f"{_mins(_cad(v))} away." if in_window else
                             f"No {e} {label} on the {sess['label']} list.")
        today_n = sum(1 for (_s, setup) in trackers_today if setup == sub_k)
        out["potential"] = _soft("potential strip", _potential_strip, sub_k,
                                 [p for p in pots if p[1]["setup"] == sub_k], today_n, sess=sess,
                                 in_window=in_window, v=v, flags=order_flags) if pot_ok else None
    elif sub_k == GC.POTENTIAL_SUB:
        entries = _entries_once()                       # D4: ONE read (D10: above the tiles, tri-state; the window read)
        out["tiles"] = broker_bottom((_soft("potential tiles", _potential_tiles, pots, st=st, session=session,
                                            tf_ask=tf_ask, scan_row=_row, sess=sess, listed=listed, halts_by=halts_by,
                                            pass_at=pass_at, v=v, carry=ah_prev, prev_iso=prev.isoformat(),
                                            entries=entries if live_push else None, default=[])
                                      if pot_ok else [])[:lim], order_flags)   # 🚫 2026-11-09 — his names last among the cards shown
        out["order_note"] = POT_ORDER_TEXT                              # 2026-11-09 — the 🧠 ordering word, served
        out["track"] = _soft("potential track", _track_block, pot_docs, pot_prev, session=session, prev=prev,
                             sess=sess, entries=entries, v=v, live=live_push) if pot_ok else None
        out["watch"] = _soft("potential watch line", _watch_block, pm_rows, post_list, pot_syms | tile_syms, v)
        out["empty_note"] = ("Nothing forming on his list right now — the next pass is at most "
                             f"{_mins(_cad(v))} away." if in_window else
                             f"Nothing was forming at the last pass ({sess['label']}).")
    elif sub_k == "premarket":
        tiles = []
        for r in pm_rows:                                           # the engine's order (today's, then the carry)
            sym = str(r["symbol"]).upper()
            tiles.append(_list_tile(sym, "premarket", reads_by.get(sym), tf_k, scan_row=_row(sym), sess=sess,
                                    listed=listed.get(sym), halt_doc=halts_by.get(sym), extra=_pm_extra(r), v=v))
        out.update({"tiles": broker_bottom(tiles[:lim], order_flags),     # 🚫 2026-11-09 — his names last among the cards shown
                    "sorts": [{"key": k, "label": lb} for k, lb in SORTS_PM], "sort": sk,
                    "empty_note": "No pre-market mover on his list and no after-hours carry from the last session."})
        if gg5:                                 # 🌅 2026-11-11 (#8) — GG5 ☀️ only; build's ONE entries + carry reads
            out["day2"] = _soft("day-2 list", day2_block, st, session, prev, listed, v, entries=_entries_once,
                                carry=ah_prev, default=None)
    elif sub_k == "postmarket":
        from chart_maps.gajjala import context as CX
        tiles = [_list_tile(str(d["symbol"]).upper(), "postmarket", reads_by.get(str(d["symbol"]).upper()), tf_k,
                            scan_row=_row(str(d["symbol"]).upper()), sess=sess,
                            listed=listed.get(str(d["symbol"]).upper()),
                            halt_doc=halts_by.get(str(d["symbol"]).upper()), extra=_post_extra(d), v=v)
                 for d in post_list]
        out.update({"tiles": broker_bottom(tiles[:lim], order_flags),     # 🚫 2026-11-09 — his names last among the cards shown
                    "postmarket": {"unchecked_n": unchecked, "unchecked_text": CX.unchecked_text(unchecked),
                                   "recap": recap(list(reads_by.values()) if aud else reads, v,
                                                  entries=_entries_once() if live_push else None)},
                    "empty_note": "No after-hours mover has passed his three after-hours checks yet."})
    elif sub_k == "playbook":
        from chart_maps.gajjala import playbook as PB
        out["playbook"] = PB.playbook()
        out["empty_note"] = None
    elif sub_k == GC.LEDGER_SUB:
        LG = _ledger()
        span_s = span if isinstance(span, str) else ""
        if aud:     # 🧪 2026-11-05 — 🚩's A+ rows with the audit's call per row; the audit read ONCE, handed to both
            read = _soft("audited read", AT.read_span, st, session, now, span=span_s, is_today=is_today, default=None)
            out["track_record"] = (_soft("track record", AT.track_block, st, session, now, span=span_s,
                                         is_today=is_today, today=today if isinstance(today, dict) else None,
                                         broker_text_of=lambda s: broker_text_for(s, flags), read=read,
                                         default=None) if LG else None)
            out["empty_note"] = None if out["track_record"] else TRACK_RECORD_FAULT  # W16
            out["audited_compare"] = (_soft("audited compare", AT.compare_block, st, session, now, span=span_s,
                                            is_today=is_today, read=read, default=None)
                                      if read is not None else None)   # [C1] a failed read never re-runs
        else:       # GG5 / GG1 — byte-identical to before
            out["track_record"] = (_soft("track record", LG.served_block, st, session, now, span=span_s,
                                         is_today=is_today, today=today if isinstance(today, dict) else None,
                                         broker_text_of=lambda s: broker_text_for(s, flags),
                                         **({} if gg5 else {"variant": v}), default=None) if LG else None)
            out["empty_note"] = None if out["track_record"] else TRACK_RECORD_FAULT  # W16
    if gg5 and (sub_k in per_setup or sub_k == GC.POTENTIAL_SUB):   # 🔝 2026-11-11 (#9) — after broker_bottom
        fb = _soft("focus five", focus_block, out["tiles"], order_flags, default=None)
        if fb:
            out["focus"] = fb
    _broker_tag(out, flags)                                         # 🚫 D2 — a TAG on every row, never a filter
    tags = _soft("trader tags", lambda: TN.tag_map(st.scan_docs(SC._window(session))), default={})
    _trader_tag(out, tags)                                          # 📌 2026-10-27 — a TAG on every row, every viewer
    _promo_tag(out, ptags)                                          # 🎪 2026-10-29 — the same walk, keys only when tagged
    _soft("setup stages", _stage_tag, out, st, session, {session: pot_docs, prev: pot_prev}, is_today=is_today,
          v=v, entries=_entries_once)                              # 🧭 2026-11-11 — display only, every card
    _strip_private(out["tiles"])
    return _plain(out)


__all__ = ["build", "resolve_sub", "order_key", "RS_ORDER_TEXT", "HF_ORDER_TEXT", "state_label", "strip_text", "session_for", "first15",
           "psych_chips", "recap", "premarket_rows", "postmarket_rows", "session_pass", "push_block",
           "push_potential_block", "board_note", "scan_block", "aplus_block", "pass_stamp", "TRACK_RECORD_FAULT",
           "ENTRY_SENT_TEXT", "BROKER_FLAG_TEXT", "BROKER_FLAG_ICON", "broker_text_for", "broker_block", "editor_block",
           "plan_text", "vol_dried_text", "VOL_DRIED_TEXT", "push_break_block", "day2_block", "focus_block",
           "FOCUS_TEXT", "DAY2_NOTE"]
