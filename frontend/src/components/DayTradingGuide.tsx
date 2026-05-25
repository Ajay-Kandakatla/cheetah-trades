import { useState } from 'react';

const GUIDE_SECTIONS = [
  {
    id: 'pre-market',
    title: '1 · Pre-market (8:00–9:30 ET) — set the day',
    summary: 'Before the bell, identify which names are in play.',
    bullets: [
      { hi: 'Watch overnight gappers ≥2%.', body: 'A 2%+ gap on real volume is the cleanest signal that institutions repositioned overnight. Check the news catalyst — earnings, upgrade, sector news.' },
      { hi: 'Map premarket high & low.', body: 'These become intraday levels. The premarket high is your first long target on a continuation; the premarket low is your stop reference on a long.' },
      { hi: 'Check relative volume vs 10-day average.', body: 'RelVol ≥1.5× = elevated interest. <1× = stay away — no liquidity, slippage will kill you.' },
      { hi: 'Note earnings/news in the next 1 hour.', body: 'Don\'t day-trade through scheduled events. Check Earnings Whisper / Finnhub for the calendar.' },
      { hi: 'Verify market regime banner.', body: 'Confirmed Uptrend → bias longs. Correction → bias shorts or sit out. Under Pressure → A+ setups only, half size.' },
    ],
  },
  {
    id: 'opening-bell',
    title: '2 · Opening 15 min (9:30–9:45 ET) — observe, don\'t enter',
    summary: 'The opening range forms now. Resist the urge to trade — institutions are placing block orders, the tape is noisy.',
    bullets: [
      { hi: 'Mark the ORB high and low.', body: 'These are the first 15-minute extremes. Most professional day traders DO NOT enter during this window — they wait for the range to set, then trade the break.' },
      { hi: 'Watch for VWAP behavior.', body: 'Bullish: price quickly rejects below VWAP and reclaims it. Bearish: price fails at VWAP from below.' },
      { hi: 'Watch tape for absorption.', body: 'Heavy buying that doesn\'t move price up = sellers are absorbing. The opposite is also true. The chart shows volume; it\'s a weak proxy but it\'s what we have.' },
      { hi: 'Don\'t chase the open spike.', body: 'The first 5 minutes have the worst risk:reward. Wait for the structure.' },
    ],
  },
  {
    id: 'entry-criteria',
    title: '3 · Entry — what makes a trade worth taking',
    summary: 'A worthwhile setup has three of these aligned. Two = pass. One = certainly pass.',
    bullets: [
      { hi: 'Volume confirms.', body: 'Entry bar must close on volume ≥1.2× recent bar avg. Without volume confirmation the breakout fails 60-70% of the time.' },
      { hi: 'Direction aligns with VWAP.', body: 'Long entries should be ABOVE VWAP. Short entries BELOW. VWAP is where the institutional volume-weighted average sits — fighting it is fighting the size.' },
      { hi: 'Risk is defined and small.', body: 'Stop is a clear price (ORB low, flag low, premarket low). Risk per trade = ≤1% of account. If you can\'t define the stop in one sentence, the setup isn\'t clean.' },
      { hi: 'R:R is at least 1.5:1.', body: 'If target/risk < 1.5, even a 50% win rate is unprofitable. Most setups should target 1.5–2R minimum.' },
      { hi: 'Sector + market context aligns.', body: 'Long NVDA when SPY is red and semis are down? You\'re fighting two layers of context. Drop it.' },
    ],
  },
  {
    id: 'patterns',
    title: '4 · Recognizable setups (the only ones worth trading)',
    summary: 'If your "setup" doesn\'t match one of these, you don\'t have a setup — you have a feeling.',
    bullets: [
      { hi: 'Opening Range Breakout (ORB).', body: 'Break above 15-min RTH high on volume. Stop = ORB low or 1×ATR. Target = 1.5×R. Best on volatile single names; doesn\'t work on indices.' },
      { hi: 'Bull Flag continuation.', body: 'Strong impulse (≥2% in 5–15 bars) → tight 5–15 bar consolidation → breakout. Stop = flag low. Target = pole-height projected. Highest edge of all five strategies in our backtest.' },
      { hi: 'Gap-and-Go.', body: 'Gap ≥1% + first-bar confirmation + break of first 5-min high. Stop = first-5-min low or premarket low. Target = premarket high or 1.5R.' },
      { hi: 'VWAP Reversion.', body: 'Mean-reversion fade when price extends ≥1.5 ATR from VWAP with a reversal candle. Works in chop, fails in trends. Backtest shows negative expectancy on momentum names — use cautiously.' },
      { hi: 'Momentum Failure short.', body: 'Parabolic +3% on rel-vol ≥2× → topping candle (long upper wick or outside bar) → confirmation close below body mid. Stop = topping high. Asymmetric edge — shorts are harder than longs.' },
    ],
  },
  {
    id: 'red-flags',
    title: '5 · Red flags — when to NOT enter',
    summary: 'These conditions kill setups. If you see them, stand aside.',
    bullets: [
      { hi: 'Choppy / range-bound tape.', body: 'If SPY is moving 0.1% per 15-min bar with no direction, breakouts will fail. Wait for a trend day.' },
      { hi: 'Light premarket volume.', body: 'No premarket volume = no institutional interest. Whatever moves intraday will be retail-driven and reverse fast.' },
      { hi: 'Wide spread.', body: 'Spread > 0.1% of price = your cost of entry is already chewing into the R-multiple. Common on illiquid sub-$2B-cap names.' },
      { hi: 'Earnings in <2 hours.', body: 'Implied vol elevated; the market makers will let the stock chop until release. Skip.' },
      { hi: 'Distribution day count ≥5.', body: 'Per IBD methodology — institutions are selling. Long setups have lower follow-through. The Morning Brief surfaces this.' },
      { hi: '"Just one more trade" after 3 losses.', body: 'Discipline rule, not a chart rule. After 3 stops in a row, walk away. The tape isn\'t cooperating with your strategy today.' },
    ],
  },
  {
    id: 'risk-mgmt',
    title: '6 · Risk management — the only thing that keeps you alive',
    summary: 'Strategy edge means nothing without sizing discipline.',
    bullets: [
      { hi: '1% risk per trade, max.', body: 'On a $50k account, max risk per trade = $500. If your stop is 0.5% from entry, position size = $100k notional. The paper-trading panel uses this 1% sizing for the equity curve.' },
      { hi: '3% max drawdown per day → stop.', body: '3 losing 1%-trades = 3% drawdown = day is done. Walk away. Most successful day traders have a hard daily stop.' },
      { hi: 'Move stops to break-even at 1R profit.', body: 'Once price moves 1R in your favor, slide the stop to entry. This converts every winner from "could lose 1R" to "worst case scratch."' },
      { hi: 'Take partials at target.', body: 'Sell half at 1.5R, let the rest run with a trailing stop. Locks in the math; lets winners go further.' },
      { hi: 'Never average down on a loser.', body: 'Adding to a losing position is the textbook way to blow up an account. The setup is wrong — accept it and move on.' },
    ],
  },
  {
    id: 'after-hours',
    title: '7 · After 4:00 ET — review, don\'t trade',
    summary: 'The session is over. The work isn\'t.',
    bullets: [
      { hi: 'Review every trade taken.', body: 'For each: was the setup textbook? Did you follow the stop? What was the actual R-multiple? The paper-trading panel records all of this for you.' },
      { hi: 'Compare to yesterday\'s backtest baseline.', body: 'If today\'s win rate was significantly below the 30d baseline, your setup execution may have drifted — not the strategy itself.' },
      { hi: 'Skip after-hours trades.', body: 'Volume drops 90%, spreads widen, news drives random moves. Day traders take losses overnight, swing traders take overnight risk by design — different game.' },
      { hi: 'Plan tomorrow\'s watchlist.', body: 'Look for stocks that closed strong on volume — they often gap continuation the next morning.' },
    ],
  },
];

export function DayTradingGuide() {
  const [openId, setOpenId] = useState<string | null>('pre-market');

  return (
    <div className="day-guide">
      <div className="day-guide__intro">
        <h2 className="day-guide__h">What to look for</h2>
        <p className="day-guide__lede">
          A daily checklist distilled from the strategies running here
          (Crabel, Raschke, Cameron, Steenbarger, Yoder) plus standard
          institutional desk discipline. Open each section as you work
          through your morning routine.
        </p>
      </div>
      <div className="day-guide__list">
        {GUIDE_SECTIONS.map((s) => (
          <details
            key={s.id}
            className="day-guide__sec"
            open={openId === s.id}
            onToggle={(e) => {
              if ((e.target as HTMLDetailsElement).open) setOpenId(s.id);
              else if (openId === s.id) setOpenId(null);
            }}
          >
            <summary>
              <span className="day-guide__title">{s.title}</span>
              <span className="day-guide__summary">{s.summary}</span>
            </summary>
            <ul className="day-guide__bullets">
              {s.bullets.map((b, i) => (
                <li key={i}>
                  <strong>{b.hi}</strong> {b.body}
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </div>
  );
}
