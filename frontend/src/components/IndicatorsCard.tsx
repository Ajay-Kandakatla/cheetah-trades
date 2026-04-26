/**
 * Lists the indicators / formulas used when computing each stock's score,
 * plus the industry-expert frameworks those indicators are drawn from.
 */

const INDICATORS = [
  { name: 'Revenue Year-over-Year (YoY) growth', formula: '(quarterly revenue this year − quarterly revenue same quarter last year) ÷ revenue same quarter last year' },
  { name: 'Gross Margin', formula: '(Revenue − Cost of Goods Sold) ÷ Revenue' },
  { name: 'Free Cash Flow (FCF) Margin', formula: 'Free Cash Flow ÷ Revenue' },
  { name: 'Debt / Revenue', formula: 'Total Debt ÷ Trailing 12-Month (TTM) Revenue (lower = safer)' },
  { name: 'Price/Earnings to Growth (PEG) Ratio', formula: 'Forward Price-to-Earnings (P/E) ÷ Expected Earnings Per Share (EPS) Growth %' },
  { name: 'Relative Strength (RS) Rating, Investor\'s Business Daily (IBD)', formula: 'Percentile rank of 12-month total return vs all US stocks (1–99)' },
  { name: '3-Month Price Change', formula: '(Price today − Price 90 days ago) ÷ Price 90 days ago' },
  { name: '50/200-day Moving Average (MA)', formula: 'Simple moving average of close; price above = uptrend' },
  { name: 'Relative Strength Index (RSI), Wilder, 14-period', formula: '100 − (100 ÷ (1 + avgGain/avgLoss)) — live in Live Stream' },
  { name: 'Volume-Weighted Average Price (VWAP)', formula: 'Σ(Price × Volume) ÷ Σ(Volume) — live in Live Stream' },
  { name: 'Earnings Surprise %', formula: '(Actual EPS − Consensus EPS) ÷ |Consensus EPS|' },
  { name: 'Insider Buying', formula: 'Net insider transactions last 90 days' },
];

const EXPERTS = [
  {
    name: "William O'Neil — CAN SLIM",
    book: 'How to Make Money in Stocks',
    use: "Framework for growth + momentum. Drives our Growth (C,A,N) and Momentum (L,I,M) buckets. EPS growth ≥25% QoQ, RS Rating ≥80, leader in its group.",
  },
  {
    name: 'Joel Greenblatt — Magic Formula',
    book: 'The Little Book That Beats the Market',
    use: 'Rank stocks by Return on Capital + Earnings Yield. Informs our Quality (ROIC) and Value (earnings yield vs price) buckets.',
  },
  {
    name: 'Joseph Piotroski — F-Score',
    book: 'Value Investing: The Use of Historical Financial Statement Information',
    use: '9-point quality score (profitability, leverage, operating efficiency). Feeds our Quality and Stability buckets — especially Debt/Revenue, current ratio, and accrual-free earnings.',
  },
  {
    name: 'Peter Lynch — PEG Ratio',
    book: 'One Up on Wall Street',
    use: 'PEG <1 = potentially undervalued growth. Core of our Value bucket; cheetahs with PEG <1.5 are favored even at premium absolute P/E.',
  },
  {
    name: 'Mark Minervini — SEPA / Trend Template',
    book: 'Trade Like a Stock Market Wizard',
    use: 'Price above 150/200-day MA, both MAs rising, RS ≥70, within 25% of 52-week high. Used in Momentum component for identifying stage-2 uptrends.',
  },
  {
    name: 'Warren Buffett — Moat + ROE + Debt Discipline',
    book: 'Berkshire shareholder letters',
    use: 'Durable competitive advantage + high return on equity + conservative leverage. Anchors Quality (ROIC/ROE) and Stability (D/R, interest coverage).',
  },
  {
    name: 'Benjamin Graham — Defensive Investor Criteria',
    book: 'The Intelligent Investor',
    use: 'Margin of safety, adequate size, stable earnings history. Downweighted for short horizon but informs Stability (earnings consistency) floor.',
  },
  {
    name: 'Stan Weinstein — Stage Analysis',
    book: 'Secrets for Profiting in Bull and Bear Markets',
    use: 'Four stages (basing, advancing, topping, declining). Only buy in Stage 2 advance confirmed by volume. Applied through 50-day MA and relative-volume checks.',
  },
];

export function IndicatorsCard() {
  return (
    <>
      <section className="card">
        <h2>Indicators &amp; formulas used in this search</h2>
        <div className="ind-grid">
          {INDICATORS.map((i) => (
            <div key={i.name} className="ind-item">
              <strong>{i.name}</strong>
              <span>{i.formula}</span>
            </div>
          ))}
        </div>
        <p className="muted small">
          Each stock's <em>Key Signals</em> column shows the top drivers for its
          score, color-coded by factor group.
        </p>
      </section>

      <section className="card">
        <h2>What industry experts suggest goes into the formula</h2>
        <p className="muted">
          These are the frameworks the Cheetah Score borrows from. Each has
          decades of empirical backing from its author and from academic
          replications; combining them reduces single-factor risk.
        </p>
        <div className="experts">
          {EXPERTS.map((e) => (
            <div key={e.name} className="expert">
              <div className="expert-name">{e.name}</div>
              <div className="expert-book">{e.book}</div>
              <div className="expert-use">{e.use}</div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
