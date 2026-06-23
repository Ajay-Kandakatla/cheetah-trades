/* DelistedBanner — shown on the detail page when the backend flags a symbol as
 * having no recent price data (delisted / halted / acquired, e.g. KALV after the
 * Chiesi buyout). Live charts can't load for such a name, so we say so plainly
 * instead of rendering a broken TradingView embed / empty candles. */
export function DelistedBanner({ symbol, reason }: { symbol: string; reason?: string | null }) {
  return (
    <div
      role="status"
      data-testid="delisted-banner"
      style={{
        border: '1px solid var(--negative, #f87171)',
        background: 'rgba(248,113,113,0.07)',
        borderRadius: 8,
        padding: '0.7rem 0.9rem',
        margin: '0.5rem 0',
        fontSize: '0.88rem',
        lineHeight: 1.45,
      }}
    >
      <strong style={{ color: 'var(--negative, #f87171)' }}>⚠️ {symbol} looks delisted or acquired.</strong>{' '}
      <span style={{ color: 'var(--cm-slate, #94a3b8)' }}>
        {reason ||
          'No recent price data — the live chart and TradingView won’t load. This stock may have been bought out or stopped trading.'}
      </span>
    </div>
  );
}
