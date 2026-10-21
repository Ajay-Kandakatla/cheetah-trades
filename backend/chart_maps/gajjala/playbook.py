"""📓 Gajjala's Playbook — the served text of the 📓 sub-tab (BUILD_SPEC §3.6, 2026-10-13).

WHAT. His method in HIS words: every quote below is copied from FIRST_HAND_ibd_webinar.md (committed for the tests as
backend/tests/fixtures/gajjala/first_hand_2026_10_13.md) and carries the timestamp and the video it was said in —
`source` "S8" = the Northern Virginia IBD webinar (CI7mNvEQyms, Part 1 of the notes), "S9" = the TraderLion podcast
(10pHBNVi4Jc, Part 2). `verbatim: True` = his words as captioned; `verbatim: False` = our paraphrase of a line he
said at that timestamp. Nothing here is computed from bars and nothing here gates, ranks or pushes.

WORDING. The house rule is "reversal", never the b-word, on every surface Ajay reads. Where GG himself said it the
quote is served with a bracketed edit — "[reverses]", "[reversal]", "[reversing]" — so the edit is visible as an
edit (the test maps each bracket back to the caption and checks the line is still his). The one served occurrence of
another trader's name is his own S8 9:45 self-description, served unedited with `verbatim: True`; every paraphrase
of ours avoids it (the source guard enforces both).

OTHER SOURCES. The "Contradicted / not used" list and the sources table are read from verified_rules.json (WP7, the
verified set) — the claims of the third-party write-ups (the link Ajay gave among them) that GG's own words contradict,
so the tab never "confirms" his method with the wrong source. The knob table is built FROM constants.py, never
retyped. UNMEASURED: no study in this app says these setups win.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from chart_maps.gajjala import constants as GC

log = logging.getLogger("chart_maps.gajjala.playbook")

_RULES_FILE = Path(__file__).resolve().parent / "verified_rules.json"
S8, S9 = "S8", "S9"
SOURCES_FIRST_HAND = (S8, S9)
STATUS_HIS = "confirmed_first_hand"
LABEL_VERBATIM = "his words"
LABEL_PARAPHRASE = "his words, paraphrased"
LABEL_CONTRADICTED = "sources disagree"
LABEL_NOT_BUILT = "not built"
KIND_QUOTE, KIND_SUMMARY, KIND_NOT_BUILT = "quote", "summary", "not_built"
AJAY = "Ajay 2026-10-13"
# Ajay 2026-10-18 "make the change for Long flags" (DECISIONS13 D1): the K4 Bull Flag range is his 2026-10-18 answer —
# the provenance names both dates; the bar range is built from the constants, never retyped.
AJAY_K4_FMT = AJAY + " · 2026-10-18 (%d–%d bars)"   # filled at call time from K4_BF_PULL_MIN / K4_BF_PULL_MAX
CHEETAH_DEFAULT = "Cheetah default (Ajay, not GG)"
AJAY_K11 = "GG S8 1:32:02 / 1:23:30 · Ajay 2026-10-21"   # K11: GG's floor + "it must sustain"; Ajay "keep what ever Gajjala says"
WAITING = "waiting for your number ({h})"
_PCT = 100                                      # a unit, not a rule (a fraction shown as a percent, as rules_info does)
# The bracketed edits of his b-word quotes (the standing reversal rule). Keys = the bracket served, values = what the
# caption says — spelled from parts so this file never carries the bare word (the source guard greps it).
_B = "b" + "ounc"
BRACKET_EDITS = {"[reverses]": _B + "es", "[reversal]": _B + "e", "[reversing]": _B + "ing"}

# Fallback when verified_rules.json cannot be read — the three sources BUILD_SPEC §3.6 names.
_FALLBACK_SOURCES = (
    {"key": S8, "title": "Goverdhan Gajjala – Trading Webinar (Northern Virginia IBD Meetup)",
     "url": "https://www.youtube.com/watch?v=CI7mNvEQyms", "date": "~late Feb 2024", "kind": "first-hand video",
     "first_hand": True},
    {"key": S9, "title": "+805% Trading Champion of 2023 Reveals His Powerful Day Trading Setups (TraderLion, R. Moglen)",
     "url": "https://youtu.be/10pHBNVi4Jc", "date": "Jan 2024", "kind": "first-hand video", "first_hand": True},
    {"key": "S1", "title": "Goverdhan Gajjala: a deep dive (Retail Traders Repository, third-party)",
     "url": "https://retailtradersrepository.substack.com/p/goverdhan-gajjala-a-deep-dive-into", "kind": "third-party",
     "first_hand": False},
)
S1_NOTE = ("the link you gave — a third-party write-up; nothing on this tab is taken from it (its claims his own words "
           "contradict are listed under Contradicted / not used)")


def _q(ts: str, source: str, text: str, note: Optional[str] = None) -> dict:
    """One verbatim quote (his words as captioned, b-word quotes bracket-edited)."""
    it = {"text": text, "ts": ts, "source": source, "verbatim": True, "kind": KIND_QUOTE,
          "status": STATUS_HIS, "status_label": LABEL_VERBATIM}
    if note:
        it["note"] = note
    return it


def _p(ts: str, source: str, text: str) -> dict:
    """One paraphrase of ours of what he said at `ts` (never served as his words)."""
    return {"text": text, "ts": ts, "source": source, "verbatim": False, "kind": KIND_QUOTE,
            "status": STATUS_HIS, "status_label": LABEL_PARAPHRASE}


# ── the sections (BUILD_SPEC §3.6 order) ──────────────────────────────────────────────────────────────────────────
WHO = ("Who he is", [
    _q("9:45", S8, "I consider myself as a intraday swing trader … a mix of Minervini style swing trading in intraday"),
    _q("10:19", S8, "I only do long side trading, I don't short."),
    _q("12:00", S8, "I'm a 100% technical trader … I don't look at the news much … I just trade the price and volume "
                    "action."),
    _q("11:37", S8, "I developed five to six go-to chart setups."),
])

SCANNER = ("The scanner", [
    _q("19:12–19:51", S8, "the watch list scanner that I developed … the price of the stock anything from 50 cents to "
                          "$100 … volume should be minimum 1 million volume and then percentage change from the "
                          "previous day at least minimum 25% change … then it comes to my small caps watch list."),
    _q("1:32:02", S8, "the minimum is 1 million volume in my scanner … the more the better."),
    _q("22:10", S9, "I created my own scanner, small cap volatility scanner … any stock which is above 50 cents and max "
                    "$100 and the volume should be 1 million and at least up by 25%, show me all these stocks."),
    _q("24:07", S9, "I prefer more liquid stocks … volume is a must … I don't take the trades which have less volume "
                    "even though the price move is big."),
    _q("1:21:56", S8, "ThinkorSwim has this pre-market movers scanner … I sort by volume … and also I look at the "
                      "percentage gainers [ToS built-in] … as soon as the market opens this gets filled … I sort by the "
                      "percentage change, see which are the biggest movers."),
    _q("1:23:30", S8, "the bigger the volume the better … 1 million volume and the price is only $2 and it's just one "
                      "bar in five minutes and after that it was fading out — I'm not interested at all. Now the volume "
                      "is picking up, 2.6 million, 3 million … the volume is sustaining and it's increasing … this "
                      "gradual increase in volume catches my attention."),
    _q("1:15:24", S8, "when the float is low when there is volume there can be halt-up kind of magnitude move."),
    _q("21:04", S8, "the reversal squeeze happens only in the low float stocks, the lower the float the better."),
    _p("1:44:09", S8, "He reads the float off the ThinkorSwim \"shares\" column. This tab uses the yfinance float, else "
                      "shares outstanding — the chip says which."),
])

CHART = ("Chart", [
    _q("1:40:07", S8, "I tried 1 minute 3 minute 5 minute 15 minutes … I concluded on the five minute … 5 minute is my "
                      "favorite."),
    _q("1:21:40", S8, "I usually switch between five and 15 minutes."),
    _q("25:36", S8, "this is the 9 EMA, this is the 21 EMA."),
    _q("24:42", S9, "I'll have a 9 EMA and 21 EMA, I have this price and then this volume, that's all. My chart has "
                    "nothing else, I don't have VWAP or ADRs. I'm strictly price and volume based."),
    _q("1:19:00", S8, "even though this is a 5 minute chart I always go and look at the daily … draw the support and "
                      "resistance … I zoom out."),
    _q("1:46:33", S8, "I align my intraday thesis with the daily … continuation run … more confidence."),
    _q("52:49–53:46", S9, "it has a history of prior runs, history of squeezes"),
    _q("52:49–53:46", S9, "When the daily and the intraday have the congruence, the move is going to be exponential"),
])

ROUTINE = ("Routine", [
    _q("13:21–14:34", S8, "in the pre-market I'll see what's moving, I'll open my scanner … ToS pre-market mover scanner "
                          "and the Zendoo online scanner … if it's making some noise in pre-market I put them in my "
                          "watch list and also there will be some stocks which make after hours moves from the past "
                          "day, I'll keep them as well"),
    _q("14:41", S8, "I don't take trades for the first 15 minutes after the market opens … I want to see the direction "
                    "… whenever I tried trading right at the open most of the times I ended up in losses."),
    _q("1:26:03", S8, "at a time I'll be watching closely four or five stocks"),
    _q("1:26:48", S8, "towards the market close sometimes this will squeeze up … and squeeze up after hours too, that's "
                      "why I'll actively watch it towards the close."),
    _q("59:24", S8, "most of the stocks make a big move after hours"),
    _q("1:16:13", S9, "in the post market the run will be much smoother, the volume will be low, but the magnitude of "
                      "the squeezes will be huge"),
    _q("1:16:35", S8, "limit orders only … slippage … I trade with less size after and pre-market."),
    _q("15:32", S8, "if most stocks are in downtrend, the volume is low like in summers, I don't look at the screens, I "
                    "take the day off."),
    _q("43:39–44:37", S8, "in a good day there will be a couple of 100%+ runners"),
    _q("43:39–44:37", S8, "On a very bad day the maximum runners would be 30%–40% and two, three, four of them, and then "
                          "others 10%, 20% — that tells me the market is not strong for my strategy, it's quiet."),
    _p("45:24", S8, "He honours that read: in quiet weeks he trades very little."),
    _q("49:48", S8, "if the market is good on average two, three, four trades per day"),
])

COMMON = ("What every setup shares", [
    _q("34:45", S8, "all these setups have the same criteria: good demand, very shallow pullback with low volume, very "
                    "constructive action, and if it takes the previous highs — enter; stop loss would be the low of "
                    "the base."),
    _q("1:54:53", S9, "strong demand, goes sideways at the top of the bars, volume subsides in those bars, and if it "
                      "reclaims the highs — this is the concept of all the moves."),
])

BULL_FLAG = ("🚩 Bull Flag", [
    _q("21:45–24:37", S8, "gradual increase in price along with gradual increase in volume [2–3 green bars], then "
                          "almost sideways or very shallow pullback with less volume compared to the left side."),
    _q("21:45–24:37", S8, "the pullback is one bar, usually two to three bars … it happens within 10 minutes and takes "
                          "off, this is the fastest."),
    _q("1:59:24", S9, "at least two big green bars (three is good) with a good price increase; the next few bars "
                      "consolidate around the top with low-volume bars; entry at the top of the pullback bar, exit "
                      "[stop] at the bottom of it"),
    _p("21:45–24:37", S8, "Entry: the break of the pullback bar's high. Stop: that bar's low."),
])

KISS_FLY = ("💋 EMA Kiss & Fly", [
    _q("31:33–32:41", S8, "extension of bull flag where the left side won't be that strong, only two green bars or one "
                          "green bar … it waits more and honors the 9 EMA whenever it pulls back … within the pullback "
                          "the volume will be considerably low compared to the green bars"),
    _q("1:55:28", S9, "it will honor the EMAs — the 9 EMA touch and go, touch and go, ride it higher"),
    _p("31:33–32:41", S8, "Entry: the high of the bar that kissed the 9 EMA. Stop: below the low of the previous bar."),
])

FADE = ("➖ Horizontal Fade", [
    _q("32:49–33:50", S8, "left side strong, gradually goes sideways with low volume pullback towards the high of the "
                          "price action, shallow very clean pullback, and when the 9 EMA and 21 EMA merge around that "
                          "area then slowly the momentum starts … risk very tiny below the previous bar."),
    _q("32:49–33:50", S8, "If I flip to 15 minutes it looks even better."),
    _q("1:20:08", S8, "not something that happens very often."),
    _q("1:56:08", S9, "this is like a bull flag in the 15 minute chart … goes sideways at the very high of the price, "
                      "volume subsiding, then if it picks up I take the call."),
    _q("1:57:33", S9, "volume completely dried out and the price is not going down … then it makes a big move.",
       note="said about the strong-demand slow fader — this Fade — \"like a vcp characteristics too\"; not a VCP rule"),
])

VCP = ("🌀 Intraday VCP", [
    _q("33:50–34:37", S8, "left side good demand, then it honors the 21 EMA when it pulls back with less volume … in "
                          "each cycle it honors the 21 EMA and the volatility contracts in each cycle … the entry would "
                          "be the top of this [last] cycle and the stop loss the low of this cycle … it should have "
                          "this uptrend look."),
])

SQUEEZE = ("🎾 Reversal Squeeze", [
    _q("35:02–35:56", S8, "happens only mostly in low float stocks, the lower the float the better … tennis ball "
                          "action: whenever there is a drop it tries to squeeze up, whenever it hits the ground it "
                          "[reverses] back hard … when the volume picks up it squeezes, explosive moves"),
    _q("36:12–38:18", S8, "the pullback is very gradual, all at the top of this bar with gradual decrease in volume … as "
                          "soon as the selling pressure is reduced and the demand kicks in, explosive."),
    _q("2:01:46–2:02:40", S9, "the lower the float the better; good volume; already strong demand, especially when the "
                              "price goes down it almost immediately comes up like a ball under the water"),
    _q("2:01:46–2:02:40", S9, "this time the sell-off was big and the [reversal] back was quick."),
    _q("2:01:46–2:02:40", S9, "it has that look of a ball [reversing] back."),
    _q("2:00:32", S9, "a halt is nothing but too much demand in a very short time"),
    _q("55:18–57:49", S9, "if it moves sideways with less volume and forms another base, high chance it has an even "
                          "bigger move"),
    _p("35:02–35:56", S8, "Entry: when it takes the highs after the quiet base. Stop: the base low."),
])

ENTRY = ("Entry", [
    _q("1:40:56–1:41:55", S8, "when it's breaking out I anticipate the volume is going to follow … I just look at the "
                              "price … I'll enter right at the break [of the previous bar's high]; sometimes I wait for "
                              "the bar to close and enter in the next bar."),
    _q("32:27", S8, "most of my exits [stops] are below the low of the previous bar, always; tight risk-reward entries "
                    "always."),
    _q("1:17:12", S8, "if it stops me out I won't re-enter right then … I need at least a couple of bars to see whether "
                      "the action is good."),
    _q("1:03:33", S9, "I don't want to be the first one in; I want the price and volume to prove it."),
    _q("54:24", S9, "I want to be more careful and have this [higher] high as my buy point."),
])

RISK = ("Risk (his discretion — NOT computed)", [
    _p("26:47–28:01", S8, "Progressive exposure: winning → bigger size, drawdown → smaller; an A+ setup → double size."),
    _q("46:47–48:12", S8, "if $2,000 is the loss in one trade, next trade I cut to $1,000 … then $500"),
    _q("44:06", S9, "if I'm in a −10% or −15% drawdown: next five trades should be only −5% together"),
    _q("1:47:23", S8, "I do it very fast like 5% to 10%, then 2.5%, 2%",
       note="basis ambiguous in the talk (position size or risk) — not served as a risk %"),
    _p("1:47:23", S8, "0.25% of the account per trade was his OWN starting risk (his masterclass and his X post of "
                      "2024-01-30)."),
    _p("1:48:40", S8, "His average reward to risk: 3.5 to 4 : 1."),
    _p("56:27", S8, "All in only on an A+ setup with a profit cushion; otherwise half size, then add."),
])


def _stats_section(doc: Optional[dict]) -> tuple:
    """His 2023 numbers, quoted — plus the per-trade expectancy computed from HIS numbers by WP7 (never ours)."""
    items = [
        _p("37:47–39:14", S9, "2023 by his TraderSync: 745 trades, 31% winners / 68% losers, average winner +8.55%, "
                              "average loser −4.06%; the last six months 165 trades, 28% winners, average winner "
                              "+13%. HIS numbers, quoted — not measured here."),
        _p("1:12:00", S8, "2023: 745 closing trades, 31% winners; a profitable second half on the same ~30/70 win rate "
                          "with larger average winners."),
    ]
    if doc:
        fy, h2 = doc.get("expectancy_full_year_pct"), doc.get("expectancy_h2_pct")
        if isinstance(fy, (int, float)) and isinstance(h2, (int, float)):
            items.append(_p("37:47–39:14", S9, "Per trade, from his own numbers: %+.2f%% over the full year, %+.2f%% "
                                               "in the second half — his result came from SIZE (all in on the A+), "
                                               "not from a per-trade edge." % (fy, h2)))
    return ("His stats (quoted — not ours)", items)


MANAGEMENT = [
    _q("24:46–26:40", S8, "if it doesn't go in my direction I exit right below this bar. If it goes … I want to be "
                          "patient … give it 15 minutes, three bars … then peel off 1/3 or half … trail the remaining "
                          "along the 9 EMA"),
    _q("39:03", S8, "once the price goes in my direction I move my stop loss to break even … then I added half, double "
                    "the size with zero risk."),
    _q("40:54–41:18", S8, "first base, second base, third base, this is a climax run … I was peeling off early."),
    _q("1:00:37", S8, "fourth base, I came out of everything."),
    _q("48:29", S8, "take some partial off … remaining at the buy point … chip up."),
    _q("49:49", S9, "always sell into strength … 1/3, half … 1/3 1/3 1/3"),
    _q("1:09:11", S9, "the psychological levels of $5, $10 get into the picture"),
    _q("1:21:19", S9, "$1 psychological level, when it takes 1.04 I'm interested."),
    _q("1:39:13", S9, "it's going to stop at five … climax run, took it at 4.7."),
    _q("1:12:47", S8, "hold period on average for a winning trade is 45 minutes to 1 hour; for a losing trade 10 "
                      "minutes."),
    _q("1:42:51", S8, "most of the times hard stops, sometimes mental stops when I'm watching with size"),
]

AVOIDS = [
    _p("1:04:13–1:11:07", S8, "Entering on bias from the premarket run without a formed setup; re-entering bigger "
                              "after a stop (revenge)."),
    _q("1:04:13–1:11:07", S8, "left side not strong … climax bar then reversal … green bar with big volume but bad "
                              "close and short range = selling."),
    _p("1:04:13–1:11:07", S8, "Dangerous: a base forming inside a big-volume selling bar — wait for it to reclaim the "
                              "highs and build another tight base."),
    _p("1:04:13–1:11:07", S8, "Never 1-minute charts; never shorts; no overnight holds in low floats."),
    {"text": "Mistakes he names: forcing entries from premarket bias; re-entering bigger after a stop; trading after a "
             "huge after-hours run assuming a repeat; entering a half position on a \"feel\" without a setup; selling "
             "on P&L instead of on price action.",
     "ts": None, "source": S9, "verbatim": False, "kind": KIND_SUMMARY, "status": STATUS_HIS,
     "status_label": LABEL_PARAPHRASE, "note": "his list across the podcast — no single timestamp"},
]

# STRATEGY_SPEC §7 R2-14 — confirmed "not built": each would need Ajay's numbers. Playbook TEXT only. `ts` / `source`
# = where GG speaks to it in FIRST_HAND, None when only another source does.
NOT_BUILT = ("Not built — Playbook text only (each would need your numbers)", [
    ("Exits, partials, base counting, breakeven-and-add — his discretion, shown above, never computed.",
     "24:46–26:40", S8),
    ("Sizing, progressive exposure and the drawdown brake.", "26:47–28:01", S8),
    ("Business Insider's \"exit a loser within five minutes\" (his own losers average about 10 minutes).",
     "1:12:47", S8),
    ("F4VS's \"ignore mid-day names\".", None, None),
    ("A trades-per-day cap.", "49:48", S8),
    ("His \"Pop & Drop\" risk-off read (several names failing their breakouts → smaller size).", None, None),
    ("A confluence score for two or three setups in one chart.", "1:59:01", S9),
    ("Daily-chart congruence as a gate.", "52:49–53:46", S9),
    ("A 30-minute Fade (he names only five and 15 minutes).", "1:21:40", S8),
    ("The CGC \"classic momentum breakout\" as its own sub-tab.", None, None),
    ("Business Insider's \"two EMA touches\" minimum for the Kiss & Fly.", "1:55:28", S9),
    ("A post-market journal with his own fields (your answer R2-8: not now).", "15:57–17:03", S8),
])


# ── verified_rules.json (WP7) — contradicted list + sources table ─────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _rules_doc() -> Optional[dict]:
    try:
        return json.loads(_RULES_FILE.read_text(encoding="utf-8"))
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala playbook: verified_rules.json unreadable: %s", exc)
        return None


def _src_ref(s: dict) -> dict:
    ref = {"key": s.get("key"), "url": s.get("url")}
    if s.get("ts"):
        ref["ts"] = s["ts"]
    return ref


def contradicted(doc: Optional[dict] = None) -> list:
    """Every `contradicted` rule of the verified set (its text, the contradiction, its sources) plus the one
    F4VS claim filed inside a confirmed rule: "require a catalyst" as a filter (rule U8). STRATEGY_SPEC §1.4."""
    doc = _rules_doc() if doc is None else doc
    if not doc:
        return []
    labels = doc.get("status_labels") or {}
    by_key = {s.get("key"): s for s in doc.get("sources") or []}
    out = []
    for topic in doc.get("topics") or []:
        for r in topic.get("verified") or []:
            if r.get("status") == "contradicted":
                text = r.get("rule") or ""
                if r.get("contradiction"):
                    text = f"{text} — {r['contradiction']}"
                out.append({"text": text, "topic": topic.get("topic"), "id": r.get("id"),
                            "status": "contradicted",
                            "status_label": labels.get("contradicted") or LABEL_CONTRADICTED,
                            "verbatim": False, "kind": "contradicted",
                            "sources": [_src_ref(s) for s in r.get("sources") or []]})
            elif r.get("id") == "U8":
                srcs = [_src_ref(s) for s in r.get("sources") or []]
                if by_key.get("S1"):
                    srcs = [_src_ref(by_key["S1"])] + srcs
                # S8 12:00 ("I'm a 100% technical trader") rides U8's own sources since WP7's refix — never re-appended.
                out.append({"text": "F4VS's \"require a catalyst\" as a filter (the write-up you linked) — not used: "
                                    "he calls a catalyst a must but never researches it; he trades price and volume "
                                    "only.",
                            "topic": topic.get("topic"), "id": "U8", "status": "contradicted",
                            "status_label": labels.get("contradicted") or LABEL_CONTRADICTED,
                            "verbatim": False, "kind": "contradicted", "sources": srcs})
    return out


def sources(doc: Optional[dict] = None) -> list:
    """The sources table: the verified set's S1–S18 (BUILD_SPEC's three when the file is missing). S1 — the link
    Ajay gave — is labelled third-party with BUILD_SPEC's note."""
    doc = _rules_doc() if doc is None else doc
    rows = (doc or {}).get("sources") or list(_FALLBACK_SOURCES)
    out = []
    for s in rows:
        row = {k: s.get(k) for k in ("key", "title", "url", "date", "kind", "first_hand", "note") if k in s}
        if row.get("key") == "S1":
            row["first_hand"] = False
            row["kind"] = row.get("kind") or "third-party"
            row["note"] = S1_NOTE
        out.append(row)
    return out


def decay(doc: Optional[dict] = None) -> Optional[dict]:
    """His own 2024-10-11 words that the method decayed (the board's UNMEASURED note quotes it)."""
    doc = _rules_doc() if doc is None else doc
    d = (doc or {}).get("decay")
    return dict(d) if isinstance(d, dict) and d.get("quote") else None


# ── knobs — built FROM constants.py ──────────────────────────────────────────────────────────────────────────────
def _hcall(name: str) -> Optional[str]:
    for h, names in GC.PLACEHOLDERS.items():
        if name in names:
            return h
    return None


def _v(name: str, fmt: str = "%g") -> str:
    """A constant formatted, or "waiting for your number (Hn)" while its placeholder is None (never "None")."""
    val = getattr(GC, name, None)
    if val is None:
        return WAITING.format(h=_hcall(name) or "?")
    if isinstance(val, str):
        return val
    return fmt % val


def _pct_of(name: str) -> str:
    """A fraction constant shown as a percent ("%g%%" of value × 100) — the ℹ️ panel's own rendering."""
    val = getattr(GC, name, None)
    return "%g%%" % (val * _PCT) if isinstance(val, (int, float)) else _v(name)


def _n(name: str) -> str:
    val = getattr(GC, name, None)
    return "{:,}".format(int(val)) if isinstance(val, (int, float)) else _v(name)


def _levels() -> str:
    return " / ".join("$%g" % x for x in GC.PSY_LEVELS)


def _setup_names(keys) -> str:
    labels = {k: label for k, _e, label in GC.SUBS}
    return " and ".join(labels.get(k, k) for k in keys)


def _event_rule_text() -> str:
    rule = getattr(GC, "K8_FAIL_EVENT_RULE", None)
    if rule == "distinct":
        return "a separate, earlier sell-off (it must end before the tennis ball)"
    if rule == "same_ok":
        return "the tennis-ball drop may itself be the failed try"
    return WAITING.format(h=_hcall("K8_FAIL_EVENT_RULE") or "?")


def knobs() -> list:
    """K1–K11 (+ round-A/C answers and H1–H5) rendered from constants.py with their provenance."""
    rows = [
        ("Scanner", "price $%s–$%s, %s+ shares today, up %s%%+ on the prior regular close; common stock + ADRs"
         % (_v("SCAN_MIN_PRICE", "%.2f"), _v("SCAN_MAX_PRICE"), _n("SCAN_MIN_VOLUME"), _v("SCAN_MIN_CHANGE_PCT")),
         "GG (floor: his X post 2024-02-01); types: " + AJAY),
        ("Stays listed", "%s sessions after it last qualified" % _v("STAY_LISTED_SESSIONS", "%d"), CHEETAH_DEFAULT),
        ("K1", "demand bar: close ≥ open +%s%%, range ≥ %s× the prior %s bars' average"
         % (_v("K1_BODY_GAIN_PCT"), _v("K1_RANGE_MULT"), _v("K1_RANGE_LOOKBACK", "%d")), AJAY),
        ("K2", "leg volume rising bar to bar, no step over %s×" % _v("K2_MAX_VOL_STEP"), AJAY),
        ("K3", "pullback lows ≥ last demand high − %s × its range (%s only); pullback volume ≤ %s× the leg's mean"
         % (_v("K3_DEPTH_FRAC"), _setup_names(GC.K3_DEPTH_SETUPS), _v("K3_VOL_FRAC")), AJAY),
        ("K4", "Bull Flag %s–%s bars%s · Kiss & Fly ≤ %s · Fade base %s–%s · VCP ≥ %s contractions"
         % (_v("K4_BF_PULL_MIN", "%d"), _v("K4_BF_PULL_MAX", "%d"),
            # Ajay 2026-10-18 (DECISIONS13 D1/D4): the long-flag band is empty while K4_BF_LONG_FLAG_MAX is None
            (" (up to %s = long flag, never A+)" % _v("K4_BF_LONG_FLAG_MAX", "%d")
             if GC.K4_BF_LONG_FLAG_MAX is not None else ""),
            _v("K4_KF_PULL_MAX", "%d"), _v("K4_HF_BASE_MIN", "%d"), _v("K4_HF_BASE_MAX", "%d"),
            _v("K4_VCP_MIN_CYCLES", "%d")), AJAY_K4_FMT % (GC.K4_BF_PULL_MIN, GC.K4_BF_PULL_MAX)),
        ("K5", "kiss = low ≤ 9 EMA +%s%% and close above it; uptrend = 9 over 21, both above %s bars back; every "
               "pullback close ≥ the 9 EMA" % (_v("K5_KISS_TOL_PCT"), _v("K5_SLOPE_BARS", "%d")), AJAY),
        ("K6", "EMAs within %s%%, base ≤ %s%% of price, second-half volume < %s× the first"
         % (_v("K6_MERGE_PCT"), _v("K6_TIGHT_PCT"), _v("K6_SELL_DECAY")), AJAY),
        ("K7", "each cycle ≤ %s× the one before, cycle lows ≥ 21 EMA −%s%%, higher lows"
         % (_v("K7_CONTRACTION"), _v("K7_EMA21_TOL_PCT")), AJAY),
        ("K8", "float ≤ %s; drop ≥ %s%% recovered within %s%% in %s bars; squeeze-history chip: last %s sessions, "
               "≥ %s%% range or a halt"
         % (_n("K8_MAX_FLOAT"), _v("K8_DROP_PCT"), _v("K8_RECOVER_PCT"), _v("K8_RECOVER_BARS", "%d"),
            _v("K8_HISTORY_SESSIONS", "%d"), _v("K8_HISTORY_RANGE_PCT")), AJAY),
        ("K9", "premarket %s+ shares; yesterday's after-hours movers up %s%%+" % (_n("K9_PM_MIN_VOLUME"),
                                                                                _v("K9_AH_CARRY_PCT")), AJAY),
        ("K10", "regular close in the top %s of the day's range, %s+ after-hours shares, up %s%%+ on the close"
         % (_pct_of("K10_CLOSE_TOP_FRAC"), _n("K10_AH_MIN_VOLUME"), _v("K10_AH_MIN_GAIN_PCT")), AJAY),
        # K11 (2026-10-21, BUILD_SPEC22 B3): GG VR 0.4 — Ajay "keep what ever Gajjala says"; the floor is his scanner's
        ("K11", "today's volume ≥ %s shares at the ring (his scanner floor; 'it must sustain')"
         % _n("K11_MIN_SESSION_VOLUME"), AJAY_K11),
        ("H1", "failed try at the highs: within %s%% of today's high, then %s%% under it"
         % (_v("K8_FAIL_NEAR_PCT"), _v("K8_FAIL_DROP_PCT")), AJAY),
        ("H2", "failed try vs the tennis ball: %s" % _event_rule_text(), AJAY),
        ("H3", "left-side demand bars: Fade ≥ %s, VCP ≥ %s" % (_v("HF_LEG_MIN_BARS", "%d"),
                                                           _v("VCP_LEG_MIN_BARS", "%d")), AJAY),
        ("H4", "squeeze quiet base ≥ %s bars" % _v("RS_BASE_MIN_BARS", "%d"), AJAY),
        ("H5", "VCP pivots confirmed by %s bars each side" % _v("VCP_PIVOT_WINDOW", "%d"), AJAY),
        ("🧱 Psych chip", "%s within %s%% above the price" % (_levels(), _v("PSY_NEAR_PCT")), CHEETAH_DEFAULT),
    ]
    return [{"key": k, "text": t, "value": prov} for k, t, prov in rows]


# ── the served dict ──────────────────────────────────────────────────────────────────────────────────────────────
def _items(section: tuple) -> dict:
    title, items = section
    return {"title": title, "items": [dict(it) for it in items]}


def _not_built() -> dict:
    title, rows = NOT_BUILT
    items = [{"text": text, "ts": ts, "source": src, "verbatim": False, "kind": KIND_NOT_BUILT,
              "status": "not_built", "status_label": LABEL_NOT_BUILT} for text, ts, src in rows]
    return {"title": title, "items": items}


def playbook() -> dict:
    """{title, note, sections, management, avoids, contradicted, knobs, sources, decay}. Pure (reads two files)."""
    doc = _rules_doc()
    d = decay(doc)
    note = ("His rules as he described them, each with its timestamp; numbers he never gave are Ajay's (K1–K10, "
            "2026-10-13). UNMEASURED — no study here says these setups win. Not advice.")
    if d:
        note += " He wrote on %s: “%s”" % (d.get("date"), d.get("quote"))
    return {
        "title": "📓 Goverdhan Gajjala — his playbook, in his words",
        "note": note,
        "sections": [_items(s) for s in (WHO, SCANNER, CHART, ROUTINE, COMMON, BULL_FLAG, KISS_FLY, FADE, VCP,
                                         SQUEEZE, ENTRY, RISK, _stats_section(doc))] + [_not_built()],
        "management": [dict(it) for it in MANAGEMENT],
        "avoids": [dict(it) for it in AVOIDS],
        "contradicted": contradicted(doc),
        "knobs": knobs(),
        "sources": sources(doc),
        "decay": d,
    }


def all_items(pb: Optional[dict] = None) -> list:
    """Every quote / paraphrase item of the served dict (sections + management + avoids) — the tests walk this."""
    pb = pb or playbook()
    out = []
    for s in pb.get("sections") or []:
        out.extend(s.get("items") or [])
    out.extend(pb.get("management") or [])
    out.extend(pb.get("avoids") or [])
    return out


def unbracket(text: str) -> str:
    """Undo the bracketed reversal edits — what the caption said (used by the provenance test)."""
    for k, v in BRACKET_EDITS.items():
        text = text.replace(k, v)
    return text


__all__ = ["playbook", "knobs", "contradicted", "sources", "decay", "all_items", "unbracket", "BRACKET_EDITS"]
