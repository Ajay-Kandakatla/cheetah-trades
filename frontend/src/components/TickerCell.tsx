/* TickerCell — the app-wide ticker renderer (Ajay 2026-06-10: "wherever you
 * show the ticker I want it to be clickable and also add the name of the
 * company in tiny fonts").
 *
 * Symbol on top (clickable → /sepa/{symbol} via the existing TickerLink anchor
 * — Cmd/middle-click friendly — or a custom onPick like chart-select), company
 * name underneath in a tiny muted line resolved from the session-cached
 * /sepa/company-names map. Clicks stop propagation so it composes inside
 * clickable cards/rows without double-firing.
 *
 * For tickers that are ALREADY inside an <a>/<Link> row (no nested
 * interactives), use <TickerName/> alone to add just the tiny label. */
import { useCompanyNames } from '../hooks/useCompanyNames';
import { TickerLink } from './TickerLink';

export function TickerName({ symbol, name, width = 28 }: {
  symbol: string; name?: string | null; width?: number;
}) {
  const names = useCompanyNames();
  const nm = name || names.get((symbol || '').toUpperCase());
  if (!nm) return null;
  return (
    <span style={{ display: 'block', fontSize: '0.56rem', fontWeight: 400,
                   color: 'var(--cm-slate,#8a93a6)', whiteSpace: 'nowrap', overflow: 'hidden',
                   textOverflow: 'ellipsis', lineHeight: 1.15, maxWidth: `${width}ch` }}
          title={nm}>
      {nm.length > width ? nm.slice(0, width - 1) + '…' : nm}
    </span>
  );
}

export function TickerCell({ symbol, name, onPick, size = '0.9rem', nameWidth = 22 }: {
  symbol: string;
  /** Known name (e.g. row.name) — skips the map lookup when provided. */
  name?: string | null;
  /** Override the default navigate-to-detail (e.g. select the live chart). */
  onPick?: (symbol: string) => void;
  size?: string;
  nameWidth?: number;
}) {
  const names = useCompanyNames();
  const sym = (symbol || '').toUpperCase();
  const nm = name || names.get(sym);
  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', lineHeight: 1.1,
                   verticalAlign: 'middle', minWidth: 0 }}
          onClick={(e) => e.stopPropagation()}>
      {onPick ? (
        <button type="button"
                onClick={(e) => { e.stopPropagation(); e.preventDefault(); onPick(sym); }}
                title={`${sym}${nm ? ` — ${nm}` : ''}`}
                style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer',
                         padding: 0, fontWeight: 800, fontSize: size, textAlign: 'left' }}>
          {sym}
        </button>
      ) : (
        <TickerLink ticker={sym} showWatchlist={false} title={nm || sym}
                    style={{ fontWeight: 800, fontSize: size, color: 'inherit', textDecoration: 'none' }}>
          {sym}
        </TickerLink>
      )}
      <TickerName symbol={sym} name={nm} width={nameWidth} />
    </span>
  );
}
