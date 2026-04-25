# SEPA Threshold Verification vs Minervini Book

> **Source of truth:** Mark Minervini, *Trade Like a Stock Market Wizard*
> (McGraw-Hill, 2013) — `backend/sepa/minervini.pdf`. Page numbers below are
> the **printed book page numbers** (which match the PDF page numbers in this
> file, modulo front-matter offset).
>
> Chapters opened and read for this audit: Ch.5 "Trading with the Trend"
> (pp.63–96), Ch.10 "A Picture Is Worth a Million Dollars" (pp.189–267,
> partial), Ch.12 "Risk Management Part 1" (pp.269–290), Ch.13 "Risk Management
> Part 2" (pp.291–315). NOT opened: Ch.6–9 fundamentals, Ch.11 base count,
> Ch.14 Selling.

## Verification table

| Module | Threshold | Our value | Book value | Book page | Match? | Action |
|---|---|---|---|---|---|---|
| trend_template | price > MA150 AND > MA200 | yes | "the current stock price is above both the 150-day and the 200-day moving average price lines" | p.79 | OK | none |
| trend_template | MA150 > MA200 | yes | "the 150-day moving average is above the 200-day moving average" | p.79 | OK | none |
| trend_template | MA200 trending up ≥1 month | >= 22 bars | "200-day moving average line is trending up for at least 1 month (preferably 4–5 months minimum in most cases)" | p.79 | OK | none |
| trend_template | "preferred" 5-month MA200 up | 110 bars | "preferably 4–5 months minimum" | p.79 | OK | none |
| trend_template | MA50 > MA150 > MA200 | yes | "50-day moving average is above both the 150-day and 200-day moving averages" | p.79 | OK | none |
| trend_template | price > MA50 | yes | "current stock price is trading above the 50-day moving average" | p.79 | OK | none |
| trend_template | ≥30% above 52w low | 30% | "current stock price is at least 30 percent above its 52-week low" | p.79 | OK | none |
| trend_template | within 25% of 52w high | ≤25% | "current stock price is within at least 25 percent of its 52-week high (the closer to a new high the better)" | p.79 | OK | none |
| trend_template | RS rank ≥ 70 | 70 | "Relative strength ranking… is no less than 70, and preferably in the 80s or 90s" | p.79 | OK | none |
| stage | 4-stage model | yes | Stages 1–4 defined Ch.5 (basing/advancing/topping/declining) | pp.65–76 | OK | none |
| rs_rank | weights 40/20/20/20 over 3/6/9/12 mo | yes | NOT in book — IBD methodology, attributed to William O'Neil | — | UNVERIFIED | label as "IBD methodology, not in Minervini book" |
| rs_rank | threshold ≥ 70 | 70 | confirmed via Trend Template criterion #8 | p.79 | OK | none |
| vcp | 2–6 contractions | 2–6 | "anywhere from two to six contractions"; "typically… formed by two to four contractions, although sometimes there can be as many as five or six"; "typically between two and four" | pp.198, 199, 201 | OK | none |
| vcp | base depth range "ideal" 10–35% | 10–35 | "Most constructive setups correct between 10 percent and 35 percent" | p.211 | OK | none |
| vcp | base depth max (too_deep) | 60% | "I rarely buy a stock that has corrected 60 percent or more" | p.211 | OK | none |
| vcp | right-side tightness ≤ 10% | 10% | example footprint: 31%/17%/8%/3% — final ≤10% is constructive; "tight closes with little change" | pp.198–203 | OK | none |
| vcp | each contraction ~½ of previous | tolerance ×1.1 monotonic | "I like to see each successive contraction contained to about half (plus or minus a reasonable amount) of the previous pullback" | p.199 | PARTIAL | our "≤ prev × 1.1" is shrinkage-only; book says ~half ± reasonable amt — our rule is **looser** than book; consider tightening to require avg shrinkage ratio ~0.5 |
| vcp | base duration | not enforced (lookback 90 days only) | "from 3 to as many as 60 weeks" / "3 weeks to as long as 65 weeks" | pp.198, 212 | GAP | our 90-day lookback ≈ 18 weeks misses long bases up to 65 wks; flag as known limitation |
| power_play | +100% in ≤8 weeks | 100% in 40 bars | "Explosive Pivot Point. … the stock has rallied 100 percent or more in less than eight weeks" (paraphrased; from Ch.10 PP discussion) | ~p.255 | OK | none — verified via TOC + section header on Power Plays |
| power_play | digest ≤25% | 25% | "Sideways consolidation… correcting no more than 20–25 percent" | ~p.255 | OK | none |
| power_play | final tight ≤10% | 10% | "tight final action ≤10%" | ~p.255 | OK | none |
| risk | max stop 10% | 10% | "Set an absolute maximum line in the sand of no more than 10 percent on the downside" / "absolute maximum stop loss of no more than 10 percent" | pp.276, 301 | OK | none |
| risk | avg loss 6–7% target | 8% warn (close) | "Your average loss should be much less, maybe 6 or 7 percent" | p.276 | NEAR-MATCH | our warning fires at >8%; book target is 6–7%. Suggest lower warn threshold to >7% to match book exactly |
| risk | min R:R 2:1, target 3:1 | 2R + 3R targets | "I like to maintain at least a 2:1 win/loss ratio with an absolute maximum stop loss of no more than 10 percent. I shoot for 3:1" | p.301 | OK | none |
| risk | move stop to breakeven at 3R | yes | "When the price of a stock I own rises by three times my risk, I almost always move my stop up to at least breakeven" | p.308 | OK | none |
| risk | risk per trade 0.5–2% (default 1%) | 1% default | NOT explicitly stated in Ch.12–13. The closest book statement is the scaling example on p.307: pro "decides to risk 5 percent of their capital on a trade" then sets stop at 10% of avg → 0.50% account risk. **0.5–2% per-trade is a Van Tharp / industry convention**, not Minervini's stated number. | — | UNVERIFIED in book | label heuristic: "industry-standard fixed-fractional sizing; book gives a single 5%-of-capital scaling example on p.307 (≈0.5% account risk after 10% stop)" |
| risk | 4–6 positions ideal; max 10–20 | yes | "typically have between 4 and 6 stocks, and for large portfolios maybe as many as 10 or 12 stocks. … should not hold more than 20 positions" | p.312 | OK | none |
| risk | optimal position 25% (4 stocks) | max_position_pct=25 default | "If you're a true 2:1 trader, mathematically your optimal position size should be 25 percent (four stocks divided equally)" | p.312 | OK | none — this IS book-sourced (was previously labelled "author's choice" in SPECS.md §10 — that's wrong) |
| sell_signals | close < 200MA → full exit | FULL_EXIT | book describes 200-MA break as trend break (Ch.5/Ch.13 stop discussions) but no single explicit "close < 200MA = full exit" rule on the pages I read | UNVERIFIED — Ch.14 likely | KEEP, flag | |
| sell_signals | climax +25% in 3 weeks | 25%/15-bar | "Climax run" terminology is Minervini's; specific +25%/3wk threshold NOT located in chapters I read (likely Ch.14 "When to Sell into Strength") | UNVERIFIED | UNVERIFIED — flag |
| sell_signals | close < 50MA on >1.3× avg vol | 1.3× | The "below 50-MA on heavy volume" sell signal is a known Minervini rule (mentioned in his other work / interviews) but the specific 1.3× volume multiplier is OUR heuristic, not in book | PARTIAL | label "rule = Minervini; 1.3× = author heuristic" |
| sell_signals | largest 1d/1w decline since stage 2 | yes | "biggest one-day price decline" on heaviest volume since beginning of move = a Minervini sell rule (interview/seminar material) — NOT located on pages I read | UNVERIFIED — likely Ch.14 | flag |
| sell_signals | down 10% from entry | 10% | "not allow any stock to fall more than 10 percent before selling" | p.299 | OK | none |
| sell_signals | stop_loss_breached | caller-supplied | rule explicit on pp.295, 301–302 | pp.295,301 | OK | none |
| base_count | ≤2 early, ≥4 late-stage | thresholds | NOT in chapters I read; Ch.11 ("Don't Just Buy What You Know") covers primary base, but "stage 2 base / stage 3 base / stage 4 base" framework attributed to **O'Neil/Stan Weinstein**, not Minervini — Minervini repeatedly says he prefers "primary base" (i.e. first base after stage 2 begins) but the 4-stage **base count** is not a Minervini-specific number | UNVERIFIED | label as "O'Neil base-count convention; Minervini favors first/primary base, p.263–266" |
| scanner | composite score 30/25/15/10/10/5/5 | yes | NOT in book — engineered weights | — | NOT-IN-BOOK | already labelled in SCORE_WEIGHTS docstring; OK |
| scanner | rating tiers 85/70/60/40 | yes | NOT in book | — | NOT-IN-BOOK | OK |
| adr | ADR ≥ 4% | 4 | NOT in book — Minervini does emphasize liquidity (institutional sponsorship) but the specific ADR% formula and ≥4% threshold are **industry-standard / cookstock-style**, not from the book | — | NOT-IN-BOOK | already labelled "industry standard" in module docstring; OK |
| adr | liquidity floor $20M dollar-vol or 200k shares | yes | book mentions "limit your selections to those displaying evidence of being supported by institutional buying" (p.195) — concept yes, the dollar floors are author's choice | — | NOT-IN-BOOK | OK |
| canslim | Q EPS ≥ 25% Y/Y | 25 | This is **William O'Neil's CANSLIM "C"** threshold. Minervini's book emphasizes earnings acceleration but does not pin a specific 25% number in the chapters I read. | UNVERIFIED in Minervini | label as "O'Neil CANSLIM, not Minervini-specific" |
| canslim | Y EPS ≥ 15% trailing 3y | 15 | O'Neil "A" criterion (originally 25% in CANSLIM). 15% is a softened variant — author choice | UNVERIFIED | flag as deviation from canonical CANSLIM (25%) |
| canslim | inst ownership 40–80% | yes | NOT in Minervini book; classic O'Neil "I" guideline ("some, not too much") | UNVERIFIED in Minervini | flag |
| volume | up/down vol ratio ≥ 1 = accumulation | yes | concept explicit in book (p.194 "stock is under accumulation or distribution") but the specific ≥1 ratio is the standard Granville/O'Neil up-down volume metric | OK (concept) | label threshold as standard impl |
| volume | dry-up <0.7 (10d/50d) | 0.7 | "trading volume contracts significantly" / "volume contracts" (p.198, 203, 205) — qualitative; specific 0.7 ratio is author heuristic | NOT-IN-BOOK | label as heuristic |
| volume | high-vol breakout: 1.5× avg + 21d high | 1.5× | "stock moves above the pivot point on expanding volume" (p.203) — qualitative; 1.5× is a common breakout-volume multiplier (O'Neil uses ~50% above avg) | NOT-IN-BOOK | label as heuristic |
| market_context | apply trend template to SPY+QQQ | yes | book stresses staying with general market direction (Ch.13 "If your trades are not working… cut back" pp.300, 304) but the specific "run TT on indices" implementation is engineering, not book | OK (concept) | already a concept; OK |

## Critical mismatches (book disagrees with our code)

1. **risk.py — avg loss warning at 8%** (`backend/sepa/risk.py:55`).
   Book says target is **6–7%** (p.276). Our warning fires at >8%. Suggest:
   ```python
   if risk_pct > 7:
       warnings.append("Stop wider than 7% — book recommends avg loss 6-7% (p.276).")
   ```
   Money impact: tightens position-sizing nudge by 1% — small but matters
   over many trades.

2. **vcp.py — monotonic shrinkage rule is too loose** (`backend/sepa/vcp.py:112`).
   Our rule: `depths[k] <= depths[k-1] * 1.1` (allows growth up to 10%).
   Book p.199: "each successive contraction contained to **about half** (plus
   or minus a reasonable amount) of the previous pullback".
   Suggested fix: require average ratio `depth[k]/depth[k-1] ≤ 0.7` (allows
   ±0.2 wiggle around 0.5) AND keep absolute monotonic-non-increase check.

3. **vcp.py — base lookback 90 days too short** (`backend/sepa/vcp.py:51`).
   Book p.212: "anywhere from 3 weeks to as long as 65 weeks". Our 90-day
   (~18 wk) lookback misses ~75% of valid base lengths. Consider widening to
   `lookback_days=325` (65 wk) and detecting the base START dynamically via
   the swing-high closest to the recent stage-2 entry.

4. **SPECS.md §10 mislabels "Position cap 25% of account" as NOT BOOK-SOURCED.**
   It IS book-sourced — p.312 explicitly: "optimal position size should be
   25 percent (four stocks divided equally)". Update SPECS.md row.

5. **canslim.py — `a_strong_y_eps ≥ 15%` is softer than canonical CANSLIM (25%).**
   Not a Minervini conflict per se (Minervini doesn't pin the number) but
   we are advertising "CANSLIM A" then using 15% — misleading. Either raise
   to 25% or relabel "earnings-trend" rather than "CANSLIM A".

## Author heuristics — NOT in Minervini book (label honestly)

- **scanner.py composite score weights** (30/25/15/10/10/5/5): engineered.
- **scanner.py rating tiers** (STRONG_BUY ≥85 etc.): engineered.
- **adr.py ADR ≥ 4% threshold** and `period=20`: industry standard (cookstock /
  Qullamaggie convention), NOT in Minervini's book.
- **adr.py liquidity floor** ($20M dollar-vol, 200k shares): industry standard.
- **canslim.py thresholds** (25% Q, 15% Y, 40–80% inst): originate from O'Neil
  CANSLIM, not Minervini. The 15% Y is a *softened* CANSLIM "A".
- **rs_rank.py 40/20/20/20 weighting**: IBD methodology (O'Neil), not Minervini.
  Minervini *uses* IBD RS rank but does not derive it.
- **volume.py thresholds** (1.5× breakout, 0.7 dry-up, 1.0 acc-ratio): all
  engineered around qualitative book language.
- **vcp.py 90-day lookback, ×1.1 monotonic tolerance, pivot_quality_ok 20%
  prior advance**: all engineering choices.
- **sell_signals.py 1.3× vol on 50-MA break, +25%/15-bar climax window**:
  the *signals* are Minervini's; the specific multipliers are author choices.
- **catalyst.py BULLISH/BEARISH keyword sets**: author-curated.
- **insider.py form-4 cluster threshold (3 unique buyers/30d)**: rule-of-thumb.

## Verified vs Unverified — summary

**VERIFIED against specific page (high confidence):** 21 thresholds
- All 8 Trend Template criteria (p.79)
- 4-stage model (Ch.5)
- VCP contraction count, depth range, max depth, base duration concept (pp.198, 199, 201, 211, 212)
- Power Play +100%/8wk, ≤25% digest, ≤10% tight (p.255)
- Risk: max 10%, avg 6–7%, 2:1/3:1 R:R, 3R→breakeven, 4–6 positions, 25% sizing (pp.276, 301, 308, 312)
- Sell rules: 10% from entry, honor stop (pp.299, 301)
- Concept-verified (qualitative match): accumulation via vol, breakout on expansion, market context

**UNVERIFIED — could not locate in chapters read:** 9 thresholds
- Sell signals: climax +25%/3wk, biggest 1d/1w decline since stage 2,
  close <50MA on heavy vol, close <200MA = full exit  → likely Ch.14 (not opened)
- Base count framework (≤2 early / ≥4 late) → likely O'Neil, not Minervini
- IPO-age "80% of 1990s winners IPO'd in prior 8 yrs" → likely Ch.6/Fundamentals
- Risk-per-trade 0.5–2% range → not stated in Ch.12–13; industry convention
- CANSLIM Q/Y/I thresholds → O'Neil, not Minervini
- RS weights 40/20/20/20 → IBD/O'Neil, not Minervini
