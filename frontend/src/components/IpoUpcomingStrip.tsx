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
 */
import {
  IPO_NO_UPCOMING, ipoCorroborationLine, ipoText, upcomingRows,
} from '../lib/ipoTab';
import type {
  IpoCorroboration, IpoCounts, IpoPayloadLike, IpoUpcoming,
} from '../lib/ipoTab';

function Row({ r }: { r: IpoUpcoming }) {
  const sym = String(r.symbol || '').toUpperCase();
  return (
    <li className="ipo-up-row" data-testid={`ipo-upcoming-${sym}`}>
      <span className="ipo-up-sym">{sym}</span>
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
  return (
    <section className="ipo-up" role="complementary" aria-label="Upcoming IPOs"
             data-testid="ipo-upcoming-strip">
      <div className="ipo-up-head">
        <span className="ipo-up-title">🗓️ Coming up</span>
        <em className="ipo-up-sub">
          expected listings from Finnhub&apos;s IPO calendar · pinned here, never filtered
          by the board controls below
        </em>
      </div>
      <p className="ipo-up-basis" data-testid="ipo-upcoming-basis">
        {ipoCorroborationLine(corroboration ?? null, counts ?? null)}
      </p>
      {rows.length ? (
        <>
          <ol className="ipo-up-list" data-testid="ipo-upcoming-list">
            {rows.map((r, i) => (
              <Row key={`${String(r.symbol)}-${String(r.date ?? i)}`} r={r} />
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
  );
}

export { IpoUpcomingStrip };
