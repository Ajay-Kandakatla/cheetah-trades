# Scalping page — methodology & sources

Built 2026-06-09 from a vetted, adversarially-verified research pass. The user's
standing rule is *no assumptions*: every detector is tied to a named source, and
where the evidence is thin or a popular claim is folklore, we say so rather than
dress it up. **Educational, not advice.**

> **Bottom line, up front.** Exactly ONE of these has a defensible, reproduced,
> costs-modeled edge for retail — and even it nets only commissions, lives in a
> single 2016–23 bull regime, and runs a ~17% win rate carried by rare tails. The
> account-level evidence is blunt: **~80–99% of retail day-traders net LOSE after
> costs** (Taiwan: ~1–1.6% reliably profitable; Brazil: 97% of persistent day
> traders lost money). No backtest changes that base rate. The page therefore
> shows **gross signal beside net-of-cost reality** on every signal.

## Phase-1 detectors (what we built)

### 1. Stocks-in-Play 5-min Opening-Range Breakout — `detectors.stocks_in_play_orb`
- **Source:** Zarattini, Barbon & Aziz (2024), *A Profitable Day Trading Strategy
  For The U.S. Equity Market*, SSRN abstract_id=4729284 / Swiss Finance Institute
  Research Paper N°24-98. Independently re-coded by QuantConnect (research/18444).
- **Evidence:** strong on source rigor, **medium** on real-world net tradeability.
  Headline (verbatim from the paper): Sharpe **2.81**, >1,600% net, 36% alpha vs
  SPY's ~198%, 2016–2023; QuantConnect reproduced ~2.40 on a top-1000 subset.
- **Rules (as implemented):** universe = today's liquid movers; require
  **RelVol > 1.0** (the "stock in play" filter — the edge lives here); direction =
  sign of the 9:30–9:35 bar (skip dojis); buy-stop at the 5-min OR boundary; stop
  = `ORB_ATR_MULT` × **daily** ATR(14); primary exit = EOD flat or stop. We add a
  `MAX_EXT_PAST_TRIGGER_PCT = 3%` no-chase cap and a regime-alignment flag.
- **Honest demerits (why not "strong"):** author-published, not peer-reviewed; a
  single 2016–23 bull regime (QuantConnect shows it collapses pre-2016); ~17% win
  rate carried by rare 10R tails (operationally hard to hold); the paper nets
  $0.0035/share commission **but not slippage or short-borrow**. Treat 2.81 as an
  optimistic upper bound.

### 2. Volatility-normalized shock fade — `detectors.shock_fade`
- **Source:** Zawadowski, Andor & Kertész (2004), *Short-term market reaction
  after extreme price changes of liquid stocks*, arXiv cond-mat/0406696 (also
  Quantitative Finance 6:283–95, 2006).
- **Evidence:** **strong** for the effect's existence and microstructure honesty;
  net live edge **unproven** in modern markets. The paper is cost-honest in the
  exact way that matters: on NYSE the spread widened at the shock and *eliminated
  most of the profits*; the edge survived only where the spread stayed tight —
  which is why the **live spread gate is the kill-switch**, not a nicety.
- **Rules (as implemented):** a **pure-intraday** move (exclude opening gaps, the
  first 5 min, and the last 60 min) clearing **both** |move| ≥ 4% **and** ≥ 8× the
  name's own intraday σ; fade it; stop = 30% of the shock beyond entry; target =
  ~40% of the shock back; hard **60-min time-stop** (edge decays fast).
- **Documented limitation:** the paper's σ is a same-clock-window stdev over 60
  prior days; we approximate it from today's own 1-min returns. And it's a
  2000–2002 (pre-decimalization-tail, pre-HFT) event study — **gross opportunity,
  not a proven modern net return.**

### 3. Intraday-momentum regime gate — `regime.intraday_regime`
- **Source:** Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, Journal of
  Financial Economics 129(2):394–414, SSRN abstract_id=2440866.
- **Evidence:** **strong** — peer-reviewed, out-of-sample, robust to costs. BUT
  it is an **index/ETF timing effect** (SPY), R² ~1–2%, Sharpe ~1.08 — *not* a
  single-name scalp. We use only the **sign** of SPY's first-30-min return as a
  long-bias / short-bias / stand-aside **direction gate** feeding the detectors.
  Do **not** trade its magnitude on a single stock.

## The non-negotiable honesty layer (every signal wears this)
- **Relative volume (RVOL)** — the single most evidence-backed filter; no volume = noise.
- **ATR-normalized triggers** — never a raw % or fixed-cent move.
- **Live bid-ask spread kill-switch** — `nbbo.spread_gate`; Massive snapshot NBBO
  for the active set. Spread unknown → flagged, never assumed zero.
- **Time-of-day arming** — the first 5 min and **last 60 min** are excluded for
  the fade; the close is auction-dominated and hostile.
- **Regime/direction gate** — trend vs fade fire opposite signals and cancel
  without it.
- **Net-of-cost overlay** — `costs.py`: round-trip spread + slippage + commission
  + SEC/FINRA fees + borrow, and the **breakeven win rate** after costs, shown
  beside the gross R:R on every card.

## NOT built — folklore / inflated claims we deliberately rejected
The adversarial verify pass flagged these; do **not** add them as "validated":
- The VWAP 2-σ band-fade "63% win rate, QuantConnect 2022" stat — **fabricated**;
  it exists only on one vendor page with no methodology, and is absent from
  QuantConnect.
- The "target = 50% of the opening range" retail ORB framing sold as a validated
  edge (e.g. a vendor's "+108% in 6 months" — a tuned single-instrument backtest).
- Generic Bollinger / VWAP band-touch fades with quoted 60–78% win rates — no
  rigorous, cost-included, methodology-disclosed backtest exists.
- The TQQQ ~1,484% / ~2,300% "ORB returns" — a **3× leverage artifact**, not edge.
- Crabel "Stretch" ORB in-book win rates as validated *equity* edge — the only
  reproducible public backtest is on futures and the naïve version graded poorly.
- Warrior/Ross-Cameron Gap-and-Go — precisely documented, but **no** rigorous
  backtest; anecdotal.
- Any backtest treated as a base rate for *your* profitability — see the bottom
  line.

## Deferred to Phase 2 (offer with warnings, don't lead)
Single-instrument QQQ ORB (A/B baseline), End-of-Day Reversal (close-window
ranking overlay), generic ORB (baseline to beat), VWAP trend-pullback & Anchored
VWAP (clearly labeled practitioner/discretionary).

## Configured constants (NOT a book formula — tunable)
See `scalping/detectors.py`, `scalping/nbbo.py`, `scalping/costs.py`. The cost
defaults (commission $0.0035/share per Zarattini; 5 bps/side slippage; SEC §31 +
FINRA TAF; 2% short-borrow) are conservative retail assumptions, not gospel.

---

# SEPA-cross tape watch (added 2026-06-09) — candle wick/body reads at levels

The autonomous alert layer: holdings + buyable + at-pivot + leaderboard names,
each completed 5-min candle read at its levels (SEPA pivot, VWAP, opening-range
high, day high) → states (BREAKOUT_STRONG / BREAKOUT_WEAK / REJECTION /
BREAKDOWN / RECLAIM / STALL) → one push per (symbol, state, ET-day), each alert
self-graded against the +30-min tape. `scalping/candles.py` + `sepa_watch.py`.

## What the evidence actually says (adversarially verified 2026-06-09)

The candle measures we compute (body % of range, wick ratios, Chaikin
close-location-value, volume ratio) are DESCRIPTIVE arithmetic. The question is
whether candle PATTERNS predict — and the verified record is mostly null:

- **Duvinage, Mazza & Petitjean (2013)**, Quantitative Finance 13(7) — **the
  decisive study for this exact tool**: 5-MIN bars, 30 DJIA stocks, 83 candle
  rules. Some pre-cost predictive content, but **no rule beats buy-and-hold
  after costs plus data-snooping correction**. Our horizon, their null.
- **Marshall, Young & Rose (2006)**, J. Banking & Finance 30(8) — NULL: DJIA
  stocks 1992–2002, bootstrap test; candlestick strategies have no value.
- **Marshall, Young & Cahan (2008)**, RQFA 31(2) — NULL in candlesticks' home
  market (TSE 1975–2004): "not even consistently profitable before costs."
- **Horton (2009)**, QREF 49(2) — NULL on 349 US stocks; grounds our rule that
  a doji is a STATE label, never a reversal signal.
- **Fock, Klein & Zwergel (2005)**, J. Derivatives 13(1) — NULL on intraday
  DAX/Bund futures, alone or with momentum.
- Contested daily-bar positives exist — **Caginalp & Laurent (1998)** (S&P 500
  daily, out-of-sample positive; but their test "removes conditions on
  magnitudes", so NO body/wick size threshold has academic validation) and
  **Lu & Shiu (2012, 2016)** (Taiwan/DJIA daily) — cited to show the daily
  evidence is contested, not settled. None of it transfers to 5-min bars.
- **Engle (1982)**, Econometrica 50 — the ONE strong predictive claim we ship:
  volatility clustering means range compression/expansion forecasts more
  VOLATILITY, never direction. STALL is therefore "expect movement", direction
  unsaid.
- **Bulkowski (ThePatternSite)** — used ONLY for identification conventions
  (wick ≥ 2–3× body etc.). His own daily-bar stats are near-random (shooting
  star 59%, hammer 60%); never quoted as win rates here.

## Therefore: what this layer claims, and what it refuses to claim

- Verdicts are **descriptive** ("constructive" / "deteriorating") — who won the
  bar at the level, on what participation. Never "will go up".
- Thresholds (body ≥60%, doji <5%, wick dominance ≥2×, CLV ≥0.6, vol ≥1.5×,
  level band 0.3%) are **CONFIGURED** conventions, not validated formulas — per
  Caginalp & Laurent, no magnitude threshold has academic backing anywhere.
- **Self-scoring is the contract**: every alert is graded against the next 30
  minutes and the page shows the live per-state hit-rate; the historical
  tape-read backtest (`tape_backtest.py`) reports follow-through per state and
  says plainly that ~50% = the read is noise. If the record says the read adds
  nothing, believe the record over the read.
- Refused as folklore: fixed win-rates for hammer/shooting-star/engulfing,
  doji-as-reversal, any "this pattern means X% odds" claim.
- **Daily↔intraday join (2026-06-09)**: FORMING daily patterns' confirmation
  lines (from the verdict scan, ≤24h old) feed the watch as levels — ranked
  just under the SEPA pivot, names not otherwise watched join with the PATTERN
  tag. A 5-min close through the line fires the usual BREAKOUT read WITH the
  discipline caveat ("daily pattern confirms only if today CLOSES above the
  line"). We deliberately do NOT detect cup/W geometry on intraday bars —
  every verified base-rate is a daily-bar statistic and the intraday candle
  record is null (Duvinage 2013); the daily chart defines the level, the
  intraday engine only watches it.

---

# Patterns page (added 2026-06-09) — bullish-reversal scan, double bottom + inverse H&S
# (extended same day: triple bottom, cup with handle, qualifier verdicts, daily candle reads)

On-demand scan (owner ⚡ button, like the SEPA full scan) over the SEPA
universe's cached daily frames. `patterns/detector.py` + `scan.py`.
Second scope (🎯 Scan Qualifiers): EVERY current SEPA qualifier gets a verdict
row — matched pattern(s), recent candle formations, or an explicit "no
pattern". No-match is an answer, not an omission; that's the decision input
Ajay asked for beside SEPA, VCP and volume.
Confirmation-line discipline: a pattern exists only once price CLOSES above the
peak between the bottoms / the neckline (Bulkowski, verified verbatim) — before
that it renders as "forming — NOT a signal" (unconfirmed double bottoms continue
lower 48% of the time per Bulkowski). Every scan also measures OUR universe's
+21-bar outcomes for historically confirmed patterns (deduped per breakout bar)
and shows that record above any book number.

## Verified evidence (adversarial pass 2026-06-09)

- **Lo, Mamaysky & Wang (2000)**, J. Finance 55(4):1705–1765 — PRECISE CLAIM:
  algorithmically-detected patterns carried statistically significant
  INFORMATIONAL content (conditional return distributions differ); NOT a
  profitability result. Per-pattern detail that matters: the **double bottom was
  a NULL on NYSE/AMEX** (failed both their tests there) and significant on
  Nasdaq only — where all 10 patterns were. Inverse H&S: KS p=0.104 on
  NYSE/AMEX (null), significant on Nasdaq.
- **Chang & Osler (1999)**, Economic Journal 109(458) — H&S on FX 1973–94:
  "profitable, but not efficient — dominated by simpler trading rules."
- **Savin, Weller & Zvingelis (2007)**, J. Financial Econometrics 5(2) — H&S on
  S&P 500/Russell 2000 1990–99: predictive excess returns, minimal stand-alone
  strategy profitability. The H&S family is the only one here with two
  independent peer-reviewed predictive results — its grade ceiling is MEDIUM.
- **Dawson & Steeley (2003)**, JBFA 30(1-2) — UK replication of LMW: information
  present, returns not exploitable.
- **Nekrasov (2010)** — self-published LMW replication on 1995–2010 data: "not
  anymore reproducible" (a null we disclose; not peer-reviewed).
- **Park & Irwin (2007)**, J. Economic Surveys 21(4) — the survey backdrop: of
  95 modern studies 56 positive / 20 negative / 19 mixed, with pervasive
  data-snooping caveats.
- **Bulkowski (ThePatternSite, verified verbatim)** — identification conventions,
  the confirmation rule, measure-rule targets, and the ONLY permitted stat
  framing: break-even failure rates (double bottoms 12–16% by variant; inverse
  H&S 11%, n=3,197, throwback 65%) always with the caveat: daily bars,
  bull-market sample, hindsight-measured, no costs, not peer-reviewed. NEVER
  win rates, average rises, or expected returns.
- **Bulkowski, second verified pass (2026-06-09, adversarial workflow over
  tb.html / cup.html and his candle pages — every quote re-fetched, zero
  refuted)**:
  - **Triple bottom** (n>2,500): break-even failure 13%, throwback 65%, rank
    12/39. ID rules used verbatim: three distinct valleys near the same price
    ("allow variations"), confirmation "once price closes above the highest
    peak between the valleys". His measure rule multiplies the height by his
    74% target-hit rate — we use that factor, not full height. SINGLE-SOURCE
    stats (the reason it was previously deferred); built 2026-06-09 at Ajay's
    explicit request with this caveat disclosed.
  - **Cup with handle** (n=913): break-even failure 5%, throwback 62%, rank
    3/39 — AND his own 1990–2024 lesson, disclosed everywhere the rank is:
    "47% of the cup with handle patterns dropped substantially within two
    months of the breakout." ID rules verbatim: U-shaped not V-shaped, cup
    7–65 weeks, rims near the same level ("be flexible"), handle mandatory,
    "1 week minimum with no maximum, forming in the upper half of the cup".
    Measure rule ×61% per the page.
  - **Candlesticks** (all out of 103 candle types, his hindsight sample):
    hammer reverses 60% (overall rank 65); shooting star 59% — his words:
    "near random" (rank 55); southern doji 52% — a coin flip (rank 78);
    bullish engulfing 63% but overall rank 84 — "the post breakout performance
    can be dreadful"; bearish engulfing 79% (rank 5) yet "does not imply a
    lasting reversal" (overall rank 91); morning star 78% (rank 6) with the
    rare strong post-breakout trend (overall rank 12). These frequencies are
    NOT win rates and ride next to the academic nulls below.

## Geometry provenance (CITED vs CONVENTION — constants in patterns/detector.py)
CITED: bottoms >22 trading days apart (LMW/Edwards & Magee → MIN_SEPARATION 23);
most double bottoms within 2–7 weeks (Bulkowski → MAX_SEPARATION 35); ≥10%
interim rise (Bulkowski); inverse-H&S shoulders AND armpits within 1.5% of their
average (LMW Definition 1); close-above-the-line confirmation (Bulkowski).
CONVENTION (ours, labeled): 3% bottom tolerance (inside the honest 1.5–6% band),
zigzag swing extrema as a substitute for LMW's kernel smoothing, the 3% head-depth
gate (no depth gate is cited anywhere), horizontal-neckline simplification
(confirm above the higher armpit — conservative), 60-bar forming expiry,
under-the-low stop, +21-bar validation horizon. CONFIRM_MAX_AGE=1 (2026-06-09,
was 15): a confirmation is an actionable match only on the day it happens or
the next ("decision in the moment, not historical cup patterns" — Ajay);
candle reads likewise only on the most recent bar (RECENT_BARS=1). Older
confirmations feed self-validation and Chart School only. A same-day
confirmation is labeled provisional intraday — it counts at the CLOSE.

Triple bottom — CITED: confirmation above the highest peak between the valleys;
valleys "near the same price, allow variations"; measure-rule ×0.74
(TB_TARGET_FACTOR). CONVENTION: 3% valley tolerance (reusing the double-bottom
band), ≥10 bars between adjacent valleys (TB_MIN_ADJ_SEP — "distinct" needs
separation; no bar count is cited), 120-bar span cap (TB_MAX_SPAN), the shared
≥10% interim-rise gate. His descriptive volume guideline (downward 61% of the
time) deliberately does NOT gate.

Cup with handle — CITED: cup 7–65 weeks (CUP_MIN_BARS 35 / CUP_MAX_BARS 325),
handle mandatory and ≥1 week (HANDLE_MIN_BARS 5) "in the upper half of the cup"
(the half-level kill), breakout above the right cup lip, measure-rule ×0.61
(CWH_TARGET_FACTOR). CONVENTION: 5% rim tolerance ("be flexible" — no number
cited), 8% minimum depth, U-shape operationalized as low-in-the-middle-70%
plus ≥3 bars within 5% of the low (his "U-shaped, not V-shaped" has no formula),
stop under the HANDLE low (the cup low invalidates far too late).

## Daily candle reads (patterns/candles_daily.py) — context, never signals
Named formations (hammer, shooting star, southern doji, bullish/bearish
engulfing, morning star) are STRUCTURAL definitions from Bulkowski's candle
pages with a trend gate (a reversal needs a trend to reverse; ±3% over 10 bars,
CONFIGURED). Every formation carries his verified frequency AND his own
deflating verdict where he gives one, plus the standing caveat: the academic
record on candlesticks as standalone predictors is NULL (Marshall, Young & Rose
2006; Horton 2009; Fock 2005). The last-bar read is the same descriptive
supply/demand arithmetic as the 5-min tape layer (body %, wicks, CLV, volume
ratio) — "who won the bar", never "what happens next".

## Rejected (and why)
- **Rounding bottom** — Bulkowski himself says find it on WEEKLY charts; any
  daily-bar curvature test is an uncited modeling choice.
- **Falling wedge** — bottom-quartile on the source's own numbers (rank 31/39,
  26% break-even failure, only 68% even break upward).
- **Bull flag / high-and-tight flag** — continuation patterns, definitionally
  not a bounce; HTF's "85% success" folklore is contradicted by Bulkowski's own
  current page.
- **Deferred**: Adam/Eve variant labeling. (Triple bottom was deferred here for
  single-source stats; built 2026-06-09 at Ajay's explicit request with that
  caveat disclosed above.)
