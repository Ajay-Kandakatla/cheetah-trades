# Swing-Trade Entry/Exit Signals on Top of SEPA — Research Synthesis

**Date:** 2026-05-29
**Scope:** For an already-SEPA-qualified stock (Trend Template + Stage 2 + liquid),
which NON-Minervini signals add the highest-probability *swing* (days-to-weeks) entry
and exit edge? Built from a 108-agent deep-research run (5 search angles → ~26 source
fetches → 85 extracted claims → 75 adversarial verification votes).

**How to read confidence tags:**
- ✅ **VERIFIED** — claim survived adversarial review, source is real and quoted accurately.
- ⚠️ **OVERSTATED** — source is real but the practical magnitude was flagged as misleading
  (usually gross-not-net, or decayed post-publication, or wrong asset class).
- 🔶 **PRACTITIONER** — coherent trader framework, NO academic backtest; anecdotal win rates.

---

## THE ONE FINDING THAT REFRAMES EVERYTHING

✅ **VERIFIED — McLean & Pontiff (2016), J. Finance 71(1):5-32, + Chen-Zimmermann (2022):**
Published return predictors decay ~26% in the near post-sample and ~50% over longer
horizons. **The decay is *largest* for characteristics that are cheapest to arbitrage —
high market cap, high liquidity, low idiosyncratic risk.**

> That is *exactly* the SEPA filter (liquid, large/mid-cap). Any academic anomaly we bolt
> onto already-liquid SEPA names will decay **faster** than the headline study suggests,
> because every other quant reading the same paper is trading it on the same liquid names.

**Implication for Cheetah:** treat all of the below as *probability tilts*, not holy grails.
The edge is in **combining** weak-but-real signals (confluence) + **disciplined exits**, not
in any single indicator. This is the quant version of what Raghu said in your WhatsApp thread.

---

## TIER 1 — ENTRY SIGNALS WORTH ADDING (best evidence-to-effort)

### 1. ✅ VWAP / Volume-Profile / Level confluence ("Triple Combo") + volume-confirmed reclaim
- **Definition:** Entry only when price reclaims a reference level (anchored VWAP, prior
  swing high/low, or a high-volume node / Point of Control) **on ≥2× the average
  consolidation volume**. Avoid entries when price is already **3–4% extended above VWAP**
  (chasing tops). Stop ≤ 1× 14-day ATR, set at the low of the reclaim candle.
- **Evidence:** 🔶 PRACTITIONER (Trader Dale / volume-profile literature). Author attributes
  80-90% of best trades to the 3-way confluence — *anecdotal, no formal backtest.* But the
  components (VWAP mean-reversion, volume nodes as S/R) are individually well-documented.
- **Compute from OHLCV:** anchored VWAP since last base low; rolling avg volume; ATR(14).
  No options data needed. **This is the cheapest high-value add — pure price/volume.**
- **Failure modes:** flat/sideways tape → coin-flip (needs a trending regime filter);
  invalid on <800K-share/day micro-caps (not a SEPA concern).

### 2. ✅ Wyckoff Last-Point-of-Support (LPS) — the SHAKEOUT discriminator
- **Definition:** After a Sign-of-Strength impulse (range expansion 150-200% of avg on high
  volume), the pullback to the LPS must show **narrow-range candles (50-70% of avg range) on
  LOW volume (40-60% of avg)**, with a fresh bullish impulse within 1-3 sessions. **High
  volume (≥80-100% of avg) on the pullback INVALIDATES it** — that's an upthrust/shakeout,
  not support.
- **Evidence:** 🔶 PRACTITIONER but internally rigorous; typical 3:1 R:R (stop just under LPS).
- **Why it matters for YOU specifically:** this is the formal version of "is this 5% dip a
  shakeout or a real breakdown?" — **low-volume narrow pullback = hold; high-volume wide
  pullback = cut.** Directly addresses your panic-sell-at-false-7% problem.
- **Compute from OHLCV:** range vs trailing-avg-range ratio; volume vs trailing-avg-volume;
  distance to prior support. No options needed.

### 3. ⚠️ Earnings IV-crush AVOIDANCE filter (not a long entry — a timing gate)
- **Definition:** S&P names lose 30-55% of IV within hours of earnings; ~72% of the crush
  happens at the next open. Stocks move LESS than the implied move 70-75% of the time.
- **Evidence:** ✅ VERIFIED on the IV-crush magnitude and frequency (multiple consistent
  sources). ⚠️ the *premium-selling* win-rate numbers (54-78%) carry fat-tail risk — Meta
  Q4'22 short straddle = −187% single trade.
- **Use for SEPA (not as an options trade):** **don't initiate a fresh swing long in the
  1-2 days before earnings** — you're buying into a coin-flip + IV crush. Flag "earnings in
  N days" as a *do-not-enter* gate. You already have an earnings calendar wired.

### 4. ⚠️ OPEX-week long tilt
- **Definition:** S&P 100 stocks show higher avg returns in option-expiration weeks (week of
  the 3rd Friday). Long-only OPEX-week timing: 0.528% avg week return; 9.3% annualized,
  Sharpe 0.61 (Stivers & Sun 2010, SSRN 1571786).
- **Evidence:** ✅ VERIFIED source + figures; ⚠️ effect studied 1988-2010, may have decayed.
- **Use:** a mild *calendar tilt* (favor entries / hold through OPEX week), not a standalone
  edge. Cheap to compute (just the date).

---

## TIER 2 — REAL BUT WEAKER / NICHE

### 5. ⚠️ Short-volume as a CONTRARIAN exit signal (NOT an entry)
- **Definition:** Short-sellers are contrarian — they short AFTER up-moves. Daily short-volume
  spikes predict negative returns over the next 1-5 days. Long-low / short-high portfolios
  showed 2.6%/mo (1-day) to 2.9%/mo (5-day) **gross** (Diether-Lee-Werner 2009, RFS 22:2).
- **Verification verdict:** ⚠️ **OVERSTATED.** The authors themselves say the strategy is **NOT
  profitable net of trading costs** at these horizons. Predictive power comes from SMALL
  trades, not institutional blocks. **Use as a soft EXIT warning, never a strategy.**
- **Practical:** rising daily short-volume on an up-day = "smart money fading this" → tighten
  stop / take partial. Signal only.

### 6. ⚠️ Gamma-squeeze setup (GEX / call-wall / NΔOI)
- **Definition:** Net GEX > $10M (mid-cap) / >$50M (mega-cap), price closing above the
  call-wall strike, plus aggressive call sweeps. Academic version: Net Delta Open-Interest
  ≥ 7.5% of shares-out, held ≥22 days → +5% day-1, +5.8% over next month (broad);
  +19.5% / +16.6% in meme names (Baig-Strong-Zaynutdinova "Seeking Gamma" 2025).
- **Verification verdict:** ⚠️ **OVERSTATED / partially inverted.** Verifiers flagged the
  "NΔOI is the dominant predictor" framing as an overreach of the actual paper. The broad-
  universe edge (+5%) is modest; the big numbers are meme-stock-only (15 events).
- **Symmetric exit:** when NΔOI% drops, comparable NEGATIVE abnormal returns — a clean
  deterministic exit if you ever ride one. **Needs options-chain data (OI by strike).** High
  build cost for a signal that mostly fires on meme names, not SEPA leaders.

### 7. ⚠️ Cost-to-borrow / shorting-demand spike
- **Definition:** A rise in loan fee *driven by shorting demand* (not supply contraction)
  → −2.54% avg abnormal return next month (Cohen-Diether-Malloy 2007, J.Finance, Smith
  Breeden winner). Short-interest LEVEL alone is unreliable (jointly set by supply+demand).
- **Verification verdict:** ⚠️ headline "47%/yr gross, 4.5% net" flagged as overstated/dated;
  effect concentrated in low-analyst-coverage names (not SEPA large-caps). **Borrow-fee data
  is paid/hard to source.** Low priority for our universe.

---

## TIER 3 — DON'T BOTHER (for SEPA swing on liquid names)

- ⚠️ **Pre-FOMC drift (49bps in 24h before announcement, Lucca-Moench 2015):** real for the
  *index* historically, but Kurov-Wolfe-Gilbert (2021) showed it **largely DISAPPEARED
  post-2011.** Don't build on it.
- ⚠️ **ORB (Opening Range Breakout):** the cited academic win rates (71% @ tight thresholds)
  are **crude-oil futures, not stocks**, and **NOT robust across subperiods** — all the edge
  is in the high-volatility 2001-2011 window. It's a long-vol regime bet. You already have an
  ORB cron for intraday; don't over-trust it in low-VIX tape.
- ⚠️ **IV-spread / skew "options predict stock returns":** Muravyev-Pearson-Pollet (2025 JFE)
  show **2/3 of the apparent edge vanishes** once you exclude hard-to-borrow stocks — the
  signal mostly proxies the borrow fee. On liquid easy-to-borrow SEPA names, **options-flow
  predictability is much weaker than the headlines.** Sobering for any UOA chip.
- 🔶 **UOA (unusual options activity):** no backtest in any source — case-study/anecdote only.
- 🔶 **GME/squeeze econometrics (anti-leverage effect, EMH-violation):** single-stock,
  one-month case study. Not generalizable to a screen.

---

## RECOMMENDED: 5 ENTRY GATES + 4 EXIT TRIGGERS FOR THE SCANNER

Ranked by (evidence strength × cheapness to compute from data we already have).

### ENTRY GATES (layer on top of the SEPA qualifier)
1. **Volume-confirmed reclaim** — buy only when price reclaims pivot/VWAP on ≥2× avg volume,
   and is NOT >3-4% extended above it. *[OHLCV only — build first]*
2. **Low-volume pullback (Wyckoff LPS)** — entry pullback range ≤70% of avg AND volume ≤60%
   of avg. The shakeout discriminator. *[OHLCV only]*
3. **Not-pre-earnings** — block new entries with earnings inside N days (default 2-3).
   *[earnings calendar — already wired]*
4. **ADX ≥ 20-25 / trending regime** — the VWAP & ORB edges only exist in trending tape;
   gate out chop. *[you just added ADX]*
5. **OPEX-week tilt (soft)** — mild scoring bonus, not a hard gate. *[date only]*

### EXIT TRIGGERS
1. **Closing-basis stop, volatility-scaled** — exit only on a *close* below stop set at
   ~1.5-2× ATR (or under the LPS low), **never on the intraday wick.** Directly fixes the
   panic-sell-at-false-7% problem.
2. **High-volume break of support** — close below MA50/structure on ≥1.5× avg volume = real
   distribution → cut. (Low-volume undercut that closes back above = hold.)
3. **Short-volume spike on an up-day** — soft warning → tighten stop / take partial. Signal,
   not auto-exit.
4. **Gamma unwind (only if you entered on a squeeze)** — NΔOI% rolling over = symmetric
   downside; exit. *[options data — skip unless we add an OI feed]*

---

## BOTTOM LINE

The honest, verified answer: **there is no single "ideal entry" oracle** — the expert who
claims to predict exact entries/exits via supply-demand + short-squeeze is pattern-matching
on a few memorable wins (survivorship), the same thing Pankaj warned about. What the
*evidence* supports is a **confluence of cheap, individually-weak price/volume signals + a
disciplined volatility-scaled CLOSING stop.** Build gates 1, 2, 4 and exit triggers 1, 2
first — they need only OHLCV you already have, and they're the ones that survived adversarial
review. Treat options-flow / gamma / short-squeeze as low-priority because their edge is
weakest precisely on the liquid large-caps SEPA selects.

*(Full claim list + per-claim verification verdicts cached at:
`.../subagents/workflows/wf_468c1bb4-f06/journal.jsonl`)*
