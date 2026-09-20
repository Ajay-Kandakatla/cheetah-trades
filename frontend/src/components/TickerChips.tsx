/* TickerChips — every name in a push, as its own real link.
 *
 *  Ajay 2026-09-20: a digest push ("AAA, BBB, CCC · pushed 08:15 ET") arrived
 *  on /alerts, in the 🔔 bell and on /notifications as ONE row with at most
 *  ONE ticker link — the other names were plain text in the body. Reading a
 *  digest meant typing the symbol into the ticker box by hand.
 *
 *  So: the row's names become chips, and each chip is a real
 *  `<a href="/sepa/SYM?tab=…&from=…">` (TickerLink), which is the whole point
 *  — ⌘-click / Ctrl-click / middle-click / right-click → "Open in new tab"
 *  are handled by the BROWSER, not by a handler this component would have to
 *  get right. A plain click stays in-app through react-router.
 *
 *  TRAP (memory-worthy, cost the whole first attempt): the three surfaces that
 *  render these chips all used to wrap the WHOLE card in a `<Link>` /
 *  `<a href>`. An anchor inside an anchor is invalid HTML — the browser
 *  silently un-nests it, so the inner ticker chip either loses its href or
 *  eats the outer card's click, and ⌘-click lands on the wrong URL. Whenever
 *  chips go on a card, the card must stop being a link: the TITLE carries the
 *  link instead. The tests pin `container.querySelectorAll('a a').length === 0`
 *  on all three surfaces; keep that pin whenever a new surface adopts chips.
 *
 *  The list is deduped and order-preserving (the backend hands them in the
 *  order the push body lists them — push/recent.derive_tickers), so the chips
 *  read in the same order as the body underneath them.
 */
import type { CSSProperties } from 'react';
import { TickerLink } from './TickerLink';

type Props = {
  /** The digest's names, in body order. Wins over `ticker` when non-empty. */
  tickers?: string[] | null;
  /** A single-name push's ticker — the fallback, and what every pre-2026-09-20
   *  row carries. */
  ticker?: string | null;
  /** Which SEPA tab to land on. Supply / Demand everywhere these rows live. */
  tab?: string;
  /** Back-button label on the destination page. */
  fromLabel?: string;
  /** A NAV_SOURCES key for the durable `?from=` signal. Omit it on a surface
   *  that renders on many pages (the bell) — TickerLink then derives the key
   *  from the page it is rendered ON, which is the honest answer there. */
  fromKey?: string;
  /** `data-testid` stem; each chip is `${testIdPrefix}-${SYMBOL}`. */
  testIdPrefix?: string;
};

const WRAP: CSSProperties = {
  display: 'inline-flex', gap: '0.3rem', flexWrap: 'wrap', alignItems: 'baseline',
};

/** Upper-cased, trimmed, deduped, order preserved. */
export function chipList(tickers?: string[] | null, ticker?: string | null): string[] {
  const raw = tickers && tickers.length ? tickers : ticker ? [ticker] : [];
  const out: string[] = [];
  for (const t of raw) {
    const s = String(t ?? '').trim().toUpperCase();
    if (!s || out.includes(s)) continue;
    out.push(s);
  }
  return out;
}

export function TickerChips({
  tickers, ticker, tab = 'supply', fromLabel, fromKey, testIdPrefix = 'tk',
}: Props) {
  const list = chipList(tickers, ticker);
  // Nothing to link — an old row with neither field, or a kind that carries no
  // symbol at all (morning brief, todo reminder). Render NOTHING rather than
  // an empty chip strip that would push the body down for no reason.
  if (!list.length) return null;
  return (
    <span style={WRAP} data-testid={`${testIdPrefix}s`}>
      {list.map((t) => (
        // The testid rides on a wrapper span: TickerLink takes no arbitrary
        // DOM props, and it is not this package's file to widen. The anchor is
        // the span's only child, so `within(getByTestId(...)).getByRole('link')`
        // reaches it.
        <span key={t} data-testid={`${testIdPrefix}-${t}`}>
          <TickerLink
            ticker={t}
            tab={tab}
            fromLabel={fromLabel}
            fromKey={fromKey}
            showWatchlist={false}
            className="alert-tk"
          />
        </span>
      ))}
    </span>
  );
}
