"""Every number 🥇 Luk's tab uses — other modules IMPORT these, never retype one (BUILD SPEC luk-tab §3.1, 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources." Martin Luk — 2025 US Investing Championship winner — sells
nothing; every rule below is his own words in free sources.

Provenance tag that STARTS the comment of every assignment line (tests/test_luk_constants.py enforces it):
  LUK <file>:<line>[-<line>] [h:mm:ss] "<key phrase>"
                     = his words: a YouTube auto-caption line of the byte-copied transcript under
                       backend/tests/fixtures/luk/ (VKNEJA5r8zw, lS9zbnLi1Gg = TraderLion podcasts; iMBI3ZcQ6sU,
                       297D7gVsLY4, tx321OQ8iD0, yvaMXQfOEWI = his own streams); the key phrase sits on that line ±2
  LUK substack "<key phrase>"
                     = his guest post https://tradingresourcehub.substack.com/p/martin-luk-283-usic-2024-key-lessons
                       (2025-02-01; the sentences in tests/fixtures/luk/substack_2025_02_01_quotes.md)
  LUK frame U4/U5/U6 martin-luk.md:<line> "<key phrase>"
                     = his TradingView screener frames on his stream iMBI3ZcQ6sU ~1:17:44, as transcribed in the
                       research sweep (sweeps/martin-luk.md:53-55 + SYNTHESIS §D)
  Ajay design #n     = the main session's binding design point n (Ajay's ask)
  MINE (HIS CALL #n) = a Cheetah transport / default he never gave — listed in the spec's §7, never his
  MINE               = the same without a HIS CALL number (a storage key, a schema version, an emoji)
  derived            = computed from another constant here, from GC (chart_maps.gajjala.constants) or the house clock
                       (LUK_SOURCE_SHA256: computed from the fixture bytes themselves)
  EXTERNAL           = a third party's number, quoted, never applied
  Ajay <yyyy-mm-dd>: "<his words>"
                     = his dated word verbatim — the constant exists because he said so on that day (LUK_PUSH_MODE,
                       LUK_LIVE_SINCE, LUK_LIVE_WORDS)
Nothing here is measured, trades, sizes or gates a push beyond his own screens: since LUK_LIVE_SINCE every 🥇 A+ rings
his phone by his word (LUK_LIVE_WORDS); any other LUK_PUSH_MODE value records in shadow, never sent.
"""
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala.audited_rules import MEASURE_FLOOR_WEEKS   # the strategy lab's 30-entry-week floor (🏁 count)
from daytrading.data import ET_RTH_CLOSE, ET_RTH_OPEN

# ── the tab ───────────────────────────────────────────────────────────────────────────────────────────────────────
LUK_TAB_LABEL = "🥇 Luk's"                 # MINE (HIS CALL #1) — the tab label and its slot right after gajjala_1m
LUK_TAB = "luk"                             # MINE (HIS CALL #1) — the Chart Maps tab key
LUK_PUSH_MODE = "live"                      # Ajay 2026-11-01: "Lets make it live. also alerts too." — HIS CALL #19 answered (was Ajay design #9 SHADOW); anything but "live" = shadow (recorded, never sent)
LUK_LIVE_SINCE = "2026-11-01"               # Ajay 2026-11-01: "Lets make it live. also alerts too." — the day his words flipped LUK_PUSH_MODE (a Sunday: no session ran in shadow)
LUK_LIVE_WORDS = "Lets make it live. also alerts too."   # Ajay 2026-11-01: "Lets make it live. also alerts too." — his words verbatim, spelling kept; every served "by your call" quotes THIS name, never a retyped copy
LUK_RECORD_FROM = "2026-11-01"              # Ajay design #7 — the deploy date; no 🏁 session before it is read
LUK_ENABLED = True                          # MINE (HIS CALL #23) kill switch; env LUK_ENABLED=0 also stops it
LUK_KIND = "luk_setup"                      # MINE (HIS CALL #19, answered 2026-11-01) — the push kind (push/subs.py: OWNER_KEEP_SET + default_prefs False) AND the /alerts pass-health row

# ── the pass (transport) ──────────────────────────────────────────────────────────────────────────────────────────
LUK_PASS_OPEN_ET = GC.PASS_OPEN_ET          # derived (HIS CALL #3) — 04:00, the 🚩 pass's own open
LUK_PASS_CLOSE_ET = "16:05"                 # MINE (HIS CALL #3) — his setups are RTH; no after-hours pass
LUK_PASS_BUDGET_SEC = 120                   # MINE (HIS CALL #4) — GG5 max 34.7 s + spawn + 120 + margin 20 ≤ 300
LUK_SLOT_MARGIN_SEC = 20                    # MINE (HIS CALL #4) — the child must end this long before the next tick
LUK_LEASE_SEC = GC.LEASE_SEC                # derived (280)
LUK_LEASE_MIN_GAP_SEC = LUK_PASS_BUDGET_SEC  # derived — no second pass inside the first one's budget
LUK_SHORTLIST_MAX = 40                      # MINE (HIS CALL #4) — names whose minute bars one pass loads
LUK_SCREEN_TOP_N = 25                       # MINE (HIS CALL #4) — rows kept per screen
LUK_DAILY_MAX_NEW_PER_PASS = GC.DAILY_MAX_NEW_PER_PASS   # derived (8) — the 🎾 history pattern
LUK_DAILY_WARM_BUDGET_SEC = 60              # MINE (HIS CALL #4) — the daily-facts warm loop's wall budget per pass
LUK_DAILY_TRUST_AFTER_SEC = GC.BAR_SETTLE_SEC   # derived (HIS CALL #27) — a daily bar dated d is a CLOSED day only when cached ≥ d 16:00 ET + 30 s (the house settle rule on the daily bar)
LUK_STATE_BARS_THROUGH = "bars_through"     # MINE (HIS CALL #26) — the luk_state key {session, t1, t5, at}: the 1-minute A+ rule's clock
LUK_STATE_INDEX = "index_state"             # MINE — the luk_state key {session, states, at}: the QQQ/IWM words are computed once per session off Luk's own fetch (2 fetches per session), never off the house cache
LUK_GRADE_BUDGET_SEC = 30                   # MINE (HIS CALL #4) — the 🏁 grade step's wall budget per pass
LUK_GRADE_MAX_LOADS = 60                    # MINE (HIS CALL #4) — minute + daily loads per grade step
LUK_GRADE_VERSION = 1                       # MINE — the 🏁 luk_ledger row schema version (not a rule)
LUK_LEDGER_SPANS = GC.LEDGER_SPANS          # derived — the 🏁 day picker spans
LUK_LEDGER_SPAN_DEFAULT = GC.LEDGER_SPAN_DEFAULT   # derived — "5d"
LUK_FILL_FROM_ET = ET_RTH_OPEN              # derived (HIS CALL #16) — the 🏁 fill window opens at the regular open
LUK_FILL_TO_ET = ET_RTH_CLOSE               # derived (HIS CALL #16) — and closes at the regular close
LUK_LEDGER_ROWS_MAX = GC.LEDGER_ROWS_MAX     # derived (2026-11-02) — the 🏁 list cap (= 🚩's GC.LEDGER_ROWS_MAX), the counts still cover every row on the span

# ── frames ───────────────────────────────────────────────────────────────────────────────────────────────────────
LUK_HOURLY_SESSIONS = 10                    # MINE — ≥ 70 hourly bars for the 21 EMA warm-up (~7 RTH bars a session)
LUK_HOURLY_SESSION = "rth"                  # MINE (HIS CALL #7) — hourly bars from regular-session minutes, clock-anchored
LUK_LOD_SESSION = "rth"                     # MINE (HIS CALL #7) — the low of day = the regular-session low

# ── universe: his three screens (iMBI3ZcQ6sU frames; U2 labels from the guest post) ─────────────────────────────────
LUK_SCREEN_MIN_CAP_USD = 100_000_000        # LUK frame U4 martin-luk.md:53 "Mkt cap > 100M USD" (all three screens)
LUK_SCREEN_MIN_AVG_VOL_10D = 500_000        # LUK frame U4 martin-luk.md:53 "Avg vol 10D > 500K" (premarket + leader)
LUK_SCREEN_MIN_PX_VOL_USD = 50_000_000      # LUK frame U4 martin-luk.md:53 "Price×vol > 50M USD" (premarket + potent)
LUK_SCREEN_MIN_VOL_1W_PCT = 3.5             # LUK frame U4 martin-luk.md:53 "Volatility 1W > 3.5%" (premarket + potent)
LUK_LEADER_MIN_PX_VOL_1W_USD = 300_000_000  # LUK frame U5 martin-luk.md:54 "Price×vol 1W > 300M USD"
LUK_POTENT_CHG_FROM_OPEN_BAND_PCT = 0.5     # LUK frame U6 martin-luk.md:55 "Chg from open outside -0.5% to 0.5%"
LUK_POTENT_EMAS = (21, 50)                  # LUK frame U6 martin-luk.md:55 "Price > EMA 50; Price > EMA 21" — built ≥ on the 21 (HIS CALL #9)
LUK_AVG_VOL_SESSIONS = 10                   # LUK frame U4 martin-luk.md:53 "Avg vol 10D" — his "10D"
LUK_VOL_1W_SESSIONS = 5                     # MINE (HIS CALL #10) — "Volatility 1W" = mean (high−low)/close over 5 sessions
LUK_PX_VOL_1W_SESSIONS = 5                  # MINE (HIS CALL #10) — "Price×vol 1W" = sum over 5 sessions
LUK_PERF_1M_SESSIONS = 21                   # MINE (HIS CALL #10) — "Perf % 1M" = 21 sessions
LUK_ADR_SESSIONS = 20                       # MINE (HIS CALL #10) — ADR = 20 sessions (sepa.adr); his "ADR" names no period
LUK_INSTRUMENT_TYPES = GC.SCAN_INSTRUMENT_TYPES   # derived (HIS CALL #11) — his frames say "US" → common stock + ADRs
LUK_CONSIDERED_PX_VOL_USD = 100_000_000     # LUK iMBI3ZcQ6sU.txt:547-550 [1:17:58] "the volume to like 100 million" — LISTED, not applied (HIS CALL #13)
LUK_CONSIDERED_EXCLUDES = ("biotechs", "buyouts / mergers")   # LUK iMBI3ZcQ6sU.txt:554-559 [1:18:23] "biotechs out on my potential watch list" — LISTED, not applied (HIS CALL #13)
LUK_ADR_PREF_PCT = 5.0                      # LUK substack ">5% ADR for this reason" — "this isn't a hard rule": a CHIP, never a gate
LUK_SMALL_CAP_USD = 5_000_000_000           # LUK substack "<$5B market cap" — his small-cap list (a chip)

# ── entry ────────────────────────────────────────────────────────────────────────────────────────────────────────
LUK_PULLBACK_DAILY_EMA = 9                  # LUK VKNEJA5r8zw.txt:1080-1082 [0:49:58] "wait at least on the daily 9"
LUK_HOURLY_EMAS = (GC.EMA_FAST, GC.EMA_SLOW)   # LUK VKNEJA5r8zw.txt:2501-2505 [1:56:39] "the hourly uh 9 and the 21 EMA" — GC's 9 / 21 (orderflow.signals)
LUK_TRIGGER = "prev_bar_high"               # LUK VKNEJA5r8zw.txt:2505-2509 [1:57:03] "the first breakout of the previous bar high"
LUK_ONE_MIN_UNTIL_MIN = 15                  # LUK VKNEJA5r8zw.txt:2518-2522 [1:57:29] "for the first 15 minute"
LUK_FIVE_MIN_UNTIL_MIN = 60                 # LUK VKNEJA5r8zw.txt:2522-2525 [1:57:42] "to maybe the 60 minute" — "maybe": the window end is HIS CALL #5
LUK_TRIGGER_WINDOW_END_MIN = LUK_FIVE_MIN_UNTIL_MIN   # derived (HIS CALL #5) — the pullback + ORH candle window (60)
LUK_PDH_WINDOW = "rth"                      # MINE (HIS CALL #5) — the inside-day PDH break: any regular-session time
LUK_NO_CHASE_PCT = 3.0                      # LUK VKNEJA5r8zw.txt:546-548 [0:24:39] "more than 3% from the low of day" — LISTED, not A+
LUK_ORH_CANDLE_MIN = 1                      # LUK lS9zbnLi1Gg.txt:802-812 [0:38:40] "forms the one minute candle"
LUK_ORH_SWITCH_MIN = 5                      # LUK lS9zbnLi1Gg.txt:840-843 [0:40:22] "Before the first five minute candle is formed"

# ── the stop ─────────────────────────────────────────────────────────────────────────────────────────────────────
LUK_STOP_MAX_PCT = 5.0                      # LUK VKNEJA5r8zw.txt:398-400 [0:18:13] "maximum will be 5%" — GATE: not A+ when wider
LUK_STOP_ADR_FRAC = 0.5                     # LUK VKNEJA5r8zw.txt:398-400 [0:18:13] "less than 50% of these stocks average" — GATE (half the ADR)
LUK_STOP_USUAL_PCT = (2.5, 3.0)             # LUK VKNEJA5r8zw.txt:403-406 [0:18:31] "wider than 3% or even 2.5%" — a chip only
LUK_STOP_LOD_SHARE = (60, 70)               # LUK VKNEJA5r8zw.txt:2534-2541 [1:58:18] "60 to 70% at the low of day" — Playbook fact
LUK_STOP_ALTS = ("breakout_bar_low", "prev_bar_low")   # LUK VKNEJA5r8zw.txt:2539-2542 [1:58:31] "the low of the previous bar" — served, not applied (S4 governs)
LUK_LOD_SWITCH_PCT = 5.0                    # LUK lS9zbnLi1Gg.txt:788-793 [0:38:02] "more than 5% between my entry and the low of day"

# ── exits (stated; computed only for the 🏁 grade) ────────────────────────────────────────────────────────────────
LUK_PARTIAL_R = (3, 5)                      # LUK VKNEJA5r8zw.txt:3155-3158 [2:27:37] "three hour or five hour" (= 3R / 5R) — 🏁 flags, not applied
LUK_TRIM_PCT = 15                           # LUK VKNEJA5r8zw.txt:3186-3188 [2:29:07] "at around 15% uh each" — listed
LUK_EXIT_RULE = "first_daily_close_below_ema9"   # LUK VKNEJA5r8zw.txt:3190-3191 [2:29:17] "first close um below the 9 EMA" — the grader's exit
LUK_TRIM_RANGE_PCT = (10, 15)               # LUK lS9zbnLi1Gg.txt:853-854 [0:40:58] "around 10 to 15%" — listed
LUK_TRIM_PAST_PCT = 35                      # LUK lS9zbnLi1Gg.txt:860-863 [0:41:26] "larger than 35%" — listed
LUK_TRAIL_EMAS = (9, 21, 50)                # LUK lS9zbnLi1Gg.txt:884-891 [0:42:37] "21 or even the 50" — listed

# ── sizing (listed, never applied) ───────────────────────────────────────────────────────────────────────────────
LUK_RISK_PER_TRADE_PCT = 0.5                # LUK VKNEJA5r8zw.txt:359-360 [0:16:09] "risk per trade is around 0.5%"
LUK_RISK_2026_PCT = 0.3                     # LUK yvaMXQfOEWI.txt:575-579 [2:13:26] "3% risk per" — the caption says 3%, his arithmetic says 0.3% (caption-ambiguous, HIS CALL #22)
LUK_POSITION_PCT = (25, 30)                 # LUK VKNEJA5r8zw.txt:386 [0:17:34] "average sizing is around 25 to 30%"
LUK_POSITION_CAP_2024_PCT = 35              # LUK VKNEJA5r8zw.txt:369-370 [0:16:41] "portfolio sizing to 35%" — no cap since 2025
LUK_GROSS_MAX_PCT = 280                     # LUK VKNEJA5r8zw.txt:908-911 [0:41:14] "most it is 280% long"
LUK_SIZING_EXAMPLE = (10_000, 0.5, 50, 2.5, 2_000, 20)   # LUK VKNEJA5r8zw.txt:3899-3912 [3:03:50] "$2,000 position" — account, risk %, risk $, stop %, position $, position % (Playbook only)

# ── market (a state word, never a gate) ──────────────────────────────────────────────────────────────────────────
LUK_INDEX_SYMBOLS = ("QQQ", "IWM")          # LUK VKNEJA5r8zw.txt:4809-4818 [3:47:19] "cues and IWM" (Qs = QQQ)
LUK_INDEX_EMAS = (9, 21)                    # LUK lS9zbnLi1Gg.txt:2458-2465 [1:57:45] "the 9 EMA is under the" — a STATE word, never a gate (HIS CALL #8)

# ── subs ─────────────────────────────────────────────────────────────────────────────────────────────────────────
SETUPS = ("pullback_reversal", "opening_range_high", "inside_day_pdh")   # MINE — keys of his three entries (E2, E6, E7)
SUBS = (("pullback_reversal", "↩️", "Pullback reversal"),   # MINE — emoji; the labels are his scan / setup names
        ("opening_range_high", "🔔", "Opening range"),
        ("inside_day_pdh", "📦", "Inside day"),
        ("premarket", "☀️", "Premarket"),
        ("leader", "🏆", "Leader"),
        ("potent", "⚡", "Potent"),
        ("playbook", "📓", "Playbook"),
        ("track_record", "🏁", "Track record"))
DEFAULT_SUB = "pullback_reversal"           # MINE — the first setup sub

# ── the sources (spec §3.1: the six transcripts + martin-luk.md, luk_bt_readme.md, backtests-critiques.md; WP-A1 adds
#    SYNTHESIS.md and the substack sentences) ───────────────────────────────────────────────────────────────
LUK_SOURCE_SHA256 = {                       # derived — sha256 of each byte copy under tests/fixtures/luk/ (the cites resolve against these bytes)
    "VKNEJA5r8zw.txt": "ab0a362d6c2ba31104aec7a0e5ad8b8043745c42204c3dd554942087ff6b9333",
    "lS9zbnLi1Gg.txt": "8989ce13e5fe88715347d2496954d02b20b248bd0bbac479098df68b7f31e94e",
    "iMBI3ZcQ6sU.txt": "8fe9b8cbc30fdb54e81f23ade7dae0820db9e94304b307181b262c4f328c7a5f",
    "297D7gVsLY4.txt": "69ef2fc2131069aabc27054bdb46893c364c43f5bfb2bd63fa79ab85c26af109",
    "tx321OQ8iD0.txt": "89d2f997a48f7a7054bebed9d653327e9f4a8ca1063eda3656b49e34bce6aa98",
    "yvaMXQfOEWI.txt": "33bc91dd814f6b3889a31c5737aff687506d2693ae6b33cf587ebd62f2bb9e83",
    "martin-luk.md": "c0c4eef6c74b16836d9e0098aa477322ee3b2fe8a594ec7ae08083484474c10f",
    "luk_bt_readme.md": "c908218d843dd1c366424f08bbfc3f588584521369f55a2a24d3100983378bb3",
    "backtests-critiques.md": "8d5be17d6c641ea08aa5f44e2f5916f27536c7970ef9701ac6b392cf20a353c2",
    "SYNTHESIS.md": "b810fc99a5c96cfac414c57b7b433228d3415e84ffa9fbfc410c10a6b938cef0",
    "substack_2025_02_01_quotes.md": "3250645b9c41e3c6b2464bdda0f13e6d6c0fc98e670962c9629d42ce3b3db4d5",
}
