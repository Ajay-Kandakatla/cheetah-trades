/* Shown on the detail page when the backend has no recent bars for a symbol.
 *
 * Ajay 2026-08-16: "look at this issue with SATS stocks". The page said
 * **"SATS looks delisted or acquired"** while SATS traded at $91.89 — EchoStar
 * had renamed to ECHO and our price series simply stopped on the rename date.
 *
 * The banner now says what we OBSERVED (no bars since a date) rather than
 * asserting a corporate action we never verified. Two different claims:
 *   - "our data stops here"     — true, and all we actually know
 *   - "this company was bought" — a guess, and it was wrong
 * The first is useful. The second told him a live position was dead.
 *
 * When the symbol IS a known rename, we say so and name the new ticker.
 */
export function DelistedBanner({ symbol, reason, renamedTo }: {
  symbol: string;
  reason?: string | null;
  renamedTo?: string | null;
}) {
  const renamed = Boolean(renamedTo);
  const accent = renamed ? 'var(--accent, #38bdf8)' : 'var(--negative, #f87171)';
  return (
    <div
      role="status"
      data-testid="delisted-banner"
      style={{
        border: `1px solid ${accent}`,
        background: renamed ? 'rgba(56,189,248,0.07)' : 'rgba(248,113,113,0.07)',
        borderRadius: 8,
        padding: '0.7rem 0.9rem',
        margin: '0.5rem 0',
        fontSize: '0.88rem',
        lineHeight: 1.45,
      }}
    >
      <strong style={{ color: accent }}>
        {renamed
          ? `↪️ ${symbol} now trades as ${renamedTo}.`
          : `⚠️ No recent price data for ${symbol}.`}
      </strong>{' '}
      <span style={{ color: 'var(--cm-slate, #94a3b8)' }}>
        {reason
          || (renamed
            ? `Same company, new ticker — history before and after the change is `
              + `joined, so the chart and the averages are continuous.`
            : 'Our price provider has stopped returning bars for this symbol. That '
              + 'usually means it was delisted, acquired or renamed — but it can also '
              + 'be a data gap, so check before acting on it.')}
      </span>
    </div>
  );
}
