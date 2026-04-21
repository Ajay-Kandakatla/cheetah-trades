/**
 * Formula + weight breakdown for the Cheetah Score.
 */
export function FormulaCard() {
  const weights = [
    { pct: '30%', label: 'Growth', detail: 'Revenue growth YoY, EPS growth, forward revenue estimates.' },
    { pct: '20%', label: 'Momentum', detail: 'RS vs S&P, price vs 50/200-day MA, 3-month price change.' },
    { pct: '20%', label: 'Quality', detail: 'Gross margin, operating margin, ROIC, FCF margin.' },
    { pct: '15%', label: 'Stability', detail: 'Debt-to-revenue, current ratio, interest coverage.' },
    { pct: '15%', label: 'Value', detail: 'PEG ratio, EV/Sales vs peers, forward P/E vs growth.' },
  ];
  return (
    <section className="card">
      <h2>The Cheetah Score Formula</h2>
      <p className="muted">
        A 0–100 composite blending five factor groups. Tuned for short-term horizons
        (days to ~3 months) with emphasis on Growth and Momentum; quality and
        balance-sheet strength prevent chasing junk.
      </p>
      <div className="formula-eq">
        Cheetah Score = 0.30·Growth + 0.20·Momentum + 0.20·Quality + 0.15·Stability + 0.15·Value
      </div>
      <div className="weights">
        {weights.map((w) => (
          <div className="weight-box" key={w.label}>
            <div className="pct">{w.pct}</div>
            <div className="weight-label">{w.label}</div>
            <div className="weight-detail">{w.detail}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
