/* AlertItems — every entry of a consolidated push, each ticker its own link.
 *
 * Ajay 2026-09-29, on the /alerts card "⚡ Tape burst at a zone — CRWV +7
 * more": "I am unable to see the other that are hiddedn her … Can you show
 * them all and make all the tickers clicable individually?"
 *
 * The server (push/recent.served_items) sends one entry per line: the body
 * lines the phone showed first (`pushed: true`), then the entries the phone
 * never printed (`pushed: false`, logged by the composer as `items`). Only the
 * SYMBOL inside each line is a link — never the whole line — so ⌘-click opens
 * that name in a new tab and the prose around it stays readable.
 *
 * Up to ITEMS_FOLD_AT entries are fully open (measured 2026-09-29: trade_flash
 * p90 16, max 44 per push); above that the first ITEMS_FOLD_AT show plus a
 * "show all N" toggle. Nothing is ever dropped.
 *
 * docs/alerts/every_item_2026_09_29.md
 */
import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import { TickerLink } from './TickerLink';

export type AlertItem = { symbol: string | null; text: string; url?: string | null; pushed?: boolean };

export const ITEMS_FOLD_AT = 20;

const LINE = { fontSize: '0.82rem', lineHeight: 1.5, color: '#cfcfd4', whiteSpace: 'pre-wrap', wordBreak: 'break-word' } as const;
const NOTE = { fontSize: '0.7rem', color: '#8b8b94', marginTop: 4 } as const;
const TOGGLE = {
  marginTop: 4, padding: 0, background: 'none', border: 'none', color: '#9aa8c8',
  fontSize: '0.72rem', cursor: 'pointer', textDecoration: 'underline',
} as const;

/** The `?tab=` of a `/sepa/…` url, else null (a /chart-maps url keeps its own tab). */
export function tabFromUrl(url?: string | null): string | null {
  if (!url || !url.startsWith('/sepa/')) return null;
  const q = url.indexOf('?');
  if (q < 0) return null;
  return new URLSearchParams(url.slice(q + 1)).get('tab') || null;
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** [before, symbol, after] at the first CASE-SENSITIVE whole-token occurrence
 *  of `symbol` in `text` (not preceded by [A-Za-z0-9.-], not followed by
 *  [A-Za-z0-9]); null when absent — "ON" inside "ONTO" is not ON. */
export function splitAtSymbol(text: string, symbol: string): [string, string, string] | null {
  if (!text || !symbol) return null;
  const m = new RegExp(`(?<![A-Za-z0-9.-])${escapeRe(symbol)}(?![A-Za-z0-9])`).exec(text);
  if (!m) return null;
  return [text.slice(0, m.index), symbol, text.slice(m.index + symbol.length)];
}

function ItemLink({ symbol, url }: { symbol: string; url?: string | null }) {
  if (url && url.startsWith('/sepa/')) {
    return (
      <TickerLink ticker={symbol} tab={tabFromUrl(url) ?? undefined} fromLabel="Alerts"
                  fromKey="alerts" showWatchlist={false} className="alert-tk" />
    );
  }
  if (url && url.startsWith('/') && !url.startsWith('//')) {
    return <Link to={url} className="tk-link alert-tk">{symbol}</Link>;
  }
  return (
    <TickerLink ticker={symbol} tab="supply" fromLabel="Alerts" fromKey="alerts"
                showWatchlist={false} className="alert-tk" />
  );
}

function ItemLine({ item }: { item: AlertItem }) {
  const sym = item.symbol;
  if (!sym) return <div data-testid="alert-item" style={LINE}>{item.text}</div>;
  const link = (
    <span data-testid={`alert-item-tk-${sym}`}>
      <ItemLink symbol={sym} url={item.url} />
    </span>
  );
  const parts = splitAtSymbol(item.text, sym);
  return (
    <div data-testid="alert-item" style={LINE}>
      {parts ? <>{parts[0]}{link}{parts[2]}</> : <>{link}{' '}{item.text}</>}
    </div>
  );
}

export function AlertItems({ items, notStored }: { items: AlertItem[]; notStored?: number | null }): JSX.Element {
  const [open, setOpen] = useState(false);
  const folds = items.length > ITEMS_FOLD_AT;
  const visible = folds && !open ? items.slice(0, ITEMS_FOLD_AT) : items;
  const offCount = items.filter((it) => it.pushed === false).length;
  const firstOff = visible.findIndex((it) => it.pushed === false);
  const missing = typeof notStored === 'number' && notStored > 0 ? notStored : 0;
  return (
    <div data-testid="alert-items" style={{ marginTop: 3 }}>
      {visible.map((it, i) => (
        <Fragment key={i}>
          {i === firstOff ? (
            <div data-testid="alert-items-offpush" style={NOTE}>+{offCount} more not in the notification:</div>
          ) : null}
          <ItemLine item={it} />
        </Fragment>
      ))}
      {folds ? (
        <button type="button" data-testid="alert-items-toggle" style={TOGGLE} onClick={() => setOpen((o) => !o)}>
          {open ? 'show fewer' : `show all ${items.length}`}
        </button>
      ) : null}
      {missing > 0 ? (
        <div data-testid="alert-items-not-stored" style={NOTE}>+{missing} more not stored in this push</div>
      ) : null}
    </div>
  );
}
