/* IpoUpcomingStrip — "potential future IPOs coming up", pinned above the 🆕 IPO grid.
 *
 * Ajay 2026-09-20, verbatim: "Also potential future IPOs coming up if
 * stocktwitz has". The feed is Finnhub's `/calendar/ipo` (this app holds a
 * Finnhub key and no StockTwits IPO feed exists), served on the board payload
 * as `upcoming` by backend/chart_maps/ipo.py.
 *
 * PINNED, like IndexZones. It renders while the board is warming, while the
 * board is erroring, and when the calendar came back with nothing. The board's
 * controls — limit, theme spread, liquidity floor — describe the TRAILING ≤2y
 * population; a deal that has not listed is not in that population, so none of
 * those controls may filter this strip.
 *
 * VERBATIM, ALWAYS. `price` arrives as a string like "18.00-20.00" and
 * `numberOfShares` can be a string too. Nothing on this strip parses either
 * into a number: a range is not a price, and a share count that has been
 * rounded on the way to the screen is a figure Finnhub never gave. Every cell
 * prints the served value or an em dash.
 *
 * It is a LIST. Nothing here is measured, it gates nothing, orders nothing,
 * alerts nothing and enters nothing — and an expected deal is a plan, not an
 * event: dates move and deals are withdrawn.
 *
 * CLICKABLE since 2026-09-20 (Ajay: "Can you gather similar info about these
 * please like the ticket and make them clicable the onesin IPO tab that are
 * future"). The symbol is a button; it opens IpoUpcomingModal, a fact sheet
 * read off the registration filing on EDGAR. Fetched on the click only —
 * never on the board build, which would cost several EDGAR round trips and a
 * multi-megabyte prospectus download per expected row on every page load.
 */
import { Suspense, useState } from 'react';
import {
  IPO_NO_UPCOMING, ipoCorroborationLine, ipoText, upcomingRows,
} from '../lib/ipoTab';
import type {
  IpoCorroboration, IpoCounts, IpoPayloadLike, IpoUpcoming,
} from '../lib/ipoTab';
import { lazyWithReload } from '../lib/lazyWithReload';

// Lazy: the fact sheet is a click away, not in the board's critical bundle.
// HOUSE RULE — lazyWithReload, never raw React.lazy (stale-chunk self-heal).
const IpoUpcomingModal = lazyWithReload(() =>
  import('./IpoUpcomingModal').then((m) => ({ default: m.IpoUpcomingModal })),
);

function Row({ r, onOpen }: { r: IpoUpcoming; onOpen: (r: IpoUpcoming) => void }) {
  const sym = String(r.symbol || '').toUpperCase();
  return (
    <li className="ipo-up-row" data-testid={`ipo-upcoming-${sym}`}>
      <button type="button" className="ipo-up-sym ipo-up-link"
              data-testid={`ipo-upcoming-open-${sym}`}
              aria-label={`Open ${sym} fact sheet`}
              onClick={(e) => { e.stopPropagation(); onOpen(r); }}>
        {sym}
      </button>
      <span className="ipo-up-name">{ipoText(r.name)}</span>
      <span className="ipo-up-date">{ipoText(r.date)}</span>
      <span className="ipo-up-exch">{ipoText(r.exchange)}</span>
      {/* The range as served — "18.00-20.00" is the honest cell. */}
      <span className="ipo-up-price">{ipoText(r.price)}</span>
      <span className="ipo-up-shares">{ipoText(r.numberOfShares)}</span>
      <span className="ipo-up-status">{ipoText(r.status)}</span>
    </li>
  );
}

export default function IpoUpcomingStrip(
  { data, corroboration, counts }: {
    data?: IpoUpcoming[] | IpoPayloadLike | null;
    corroboration?: IpoCorroboration | null;
    /** The board's bucket counts. The strip reads exactly one of them —
     *  `dropped_uncorroborated` — so the drop the board now makes is stated
     *  where he is reading the calendar's own rows (2026-09-20). */
    counts?: IpoCounts | null;
  },
) {
  const rows = upcomingRows(data ?? null);
  const [open, setOpen] = useState<IpoUpcoming | null>(null);
  return (
    <>
    <section className="ipo-up" role="complementary" aria-label="Upcoming IPOs"
             data-testid="ipo-upcoming-strip">
      <div className="ipo-up-head">
        <span className="ipo-up-title">🗓️ Coming up</span>
        <em className="ipo-up-sub">
          expected listings from Finnhub&apos;s IPO calendar · pinned here, never filtered
          by the board controls below · click a symbol for its fact sheet
        </em>
      </div>
      <p className="ipo-up-basis" data-testid="ipo-upcoming-basis">
        {ipoCorroborationLine(corroboration ?? null, counts ?? null)}
      </p>
      {rows.length ? (
        <>
          <ol className="ipo-up-list" data-testid="ipo-upcoming-list">
            {rows.map((r, i) => (
              <Row key={`${String(r.symbol)}-${String(r.date ?? i)}`} r={r} onOpen={setOpen} />
            ))}
          </ol>
          <p className="ipo-up-dim">
            Prices and share counts are printed exactly as the feed serves them — a
            range is a range, not a price. An expected deal is a plan: dates move and
            deals are withdrawn. Nothing here is measured and nothing here is a signal.
          </p>
        </>
      ) : (
        <p className="ipo-up-empty" data-testid="ipo-upcoming-empty">
          {IPO_NO_UPCOMING}
        </p>
      )}
    </section>
    {open && (
      <Suspense fallback={null}>
        <IpoUpcomingModal row={open} onClose={() => setOpen(null)} />
      </Suspense>
    )}
    </>
  );
}

export { IpoUpcomingStrip };
