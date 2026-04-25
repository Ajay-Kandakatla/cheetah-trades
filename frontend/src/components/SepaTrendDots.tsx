/**
 * SepaTrendDots — render 8 mini dots, one per Trend Template criterion.
 * Filled green = pass, hollow red = fail. Hover for criterion name.
 */
type Props = { checks: Record<string, boolean>; passed?: number };

const ORDER = [
  'price_above_ma50',
  'price_above_ma150',
  'price_above_ma200',
  'ma50_above_ma150',
  'ma150_above_ma200',
  'ma200_trending_up_1mo',
  'pct_above_low_30',
  'pct_below_high_25',
  'rs_rank_at_least_70',
];

const LABEL: Record<string, string> = {
  price_above_ma50: 'Price > 50MA',
  price_above_ma150: 'Price > 150MA',
  price_above_ma200: 'Price > 200MA',
  ma50_above_ma150: '50MA > 150MA',
  ma150_above_ma200: '150MA > 200MA',
  ma200_trending_up_1mo: '200MA up ≥ 1 month',
  pct_above_low_30: '≥ 30% above 52w low',
  pct_below_high_25: '≤ 25% below 52w high',
  rs_rank_at_least_70: 'RS rank ≥ 70',
};

export function SepaTrendDots({ checks, passed }: Props) {
  const ordered = ORDER.filter((k) => k in checks);
  const total = ordered.length || Object.keys(checks).length;
  const passCount = passed ?? Object.values(checks).filter(Boolean).length;
  return (
    <div className="sepa-dots" title={`${passCount}/${total} trend criteria passed`}>
      {ordered.map((k) => (
        <span
          key={k}
          className={`sepa-dot ${checks[k] ? 'is-pass' : 'is-fail'}`}
          title={`${checks[k] ? '✓' : '✗'} ${LABEL[k] ?? k}`}
        />
      ))}
      <span className="sepa-dots__count mono">{passCount}/{total}</span>
    </div>
  );
}
