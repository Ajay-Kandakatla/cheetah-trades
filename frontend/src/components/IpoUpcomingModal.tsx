/* IpoUpcomingModal — the fact sheet behind a 🗓️ "Coming up" symbol.
 *
 * Ajay 2026-09-20, verbatim: "Can you gather similar info about these please
 * like the ticket and make them clicable the onesin IPO tab that are future".
 *
 * A ticker page shows a company's story and its numbers. An expected listing
 * has no price history, so this shows what a ticker page would if it could:
 * who the company is and what it does, the deal terms, who is underwriting,
 * the last reported revenue and net loss AS PRINTED in the registration
 * filing, the prospectus link, the industry, and the week's headlines.
 *
 * It is a FACT SHEET. Nothing on it is computed, nothing is ranked, nothing
 * is a read: no chip, no state, no colour-coded judgement. Every cell is a
 * string the backend read off the document or off Finnhub's calendar row,
 * printed through the one printer (`ipoText`). No figure is ever parsed out
 * of a filing — a thousands-for-millions slip on a sheet he reads before a
 * listing is exactly the invented number the ask forbids, so revenue and net
 * loss stay SENTENCES, each carrying the units and the period header of its
 * own table (the two quotes routinely come from two different tables).
 *
 * The closing sentence is SERVED (backend `chart_maps/ipo_upcoming.NOTE`) and
 * never typed here: one place says what this is, so the two can never drift.
 *
 * Fetched on mount, i.e. on his click — never on the board build.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  IPO_DRILL_NO_HEADLINES, ipoDrillUrl, ipoHeadlineDate, ipoText, ipoUnderwriters,
} from '../lib/ipoTab';
import type { IpoDrillFiling, IpoDrillPayload, IpoUpcoming } from '../lib/ipoTab';

/** A header line that the filing did not carry. Says WHERE to look rather
 *  than pretending the table had no units. */
const NOT_FOUND = 'not found in the filing — read the linked document';

function asHeader(v: string | null | undefined): string {
  return typeof v === 'string' && v.trim() ? v.trim() : NOT_FOUND;
}

function Line({ k, v }: { k: string; v: string }) {
  return (
    <div className="ipo-drill-line">
      <span className="ipo-drill-k">{k}</span>
      <span className="ipo-drill-v">{v}</span>
    </div>
  );
}

/** One as-printed quote with the units and periods of ITS OWN table under it.
 *  Two of these render side by side, because one units line for two tables is
 *  precisely the misreading this section exists to prevent. */
function QuoteGroup(
  { testid, label, line, units, periods }: {
    testid: string; label: string;
    line?: string | null; units?: string | null; periods?: string | null;
  },
) {
  return (
    <div className="ipo-drill-quote-group" data-testid={testid}>
      <div className="ipo-drill-eyebrow">{label}</div>
      <blockquote className="ipo-drill-quote">{ipoText(line)}</blockquote>
      <Line k="Units" v={asHeader(units)} />
      <Line k="Periods" v={asHeader(periods)} />
    </div>
  );
}

export function IpoUpcomingModal({ row, onClose }: { row: IpoUpcoming; onClose: () => void }) {
  const sym = String(row?.symbol || '').toUpperCase();
  const [payload, setPayload] = useState<IpoDrillPayload | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [fetchErr, setFetchErr] = useState<string | null>(null);

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [onClose]);

  useEffect(() => {
    let alive = true;
    setState('loading');
    setFetchErr(null);
    fetch(ipoDrillUrl(sym), { credentials: 'include' })
      .then(async (r) => {
        const j = await Promise.resolve(r.json()).catch(() => null);
        if (!alive) return;
        if (r.ok && j && typeof j === 'object') {
          setPayload(j as IpoDrillPayload);
          setState('ready');
          return;
        }
        // A refused request explains itself in the server's own words when it
        // sent any — the 404 sentence names the calendar window, and retyping
        // it here would be a second opinion about the same fact.
        const detail = j && typeof j === 'object' && typeof (j as { detail?: unknown }).detail === 'string'
          ? String((j as { detail?: unknown }).detail)
          : null;
        setFetchErr(detail || `Couldn't load the filing facts for ${sym}.`);
        setState('error');
      })
      .catch(() => {
        if (!alive) return;
        setFetchErr(`Couldn't load the filing facts for ${sym}.`);
        setState('error');
      });
    return () => { alive = false; };
  }, [sym]);

  const filing: IpoDrillFiling | null = (state === 'ready' && payload?.filing) || null;
  const company = (state === 'ready' && payload?.company) || null;
  const sources = (state === 'ready' && payload?.sources) || null;
  const headlines = state === 'ready' && Array.isArray(payload?.headlines) ? payload!.headlines! : [];
  const servedErr = state === 'ready' && typeof payload?.error === 'string' && payload.error.trim()
    ? payload.error.trim() : null;
  const shownErr = state === 'error' ? fetchErr : servedErr;

  const inFiling = typeof filing?.symbol_in_filing === 'string' ? filing.symbol_in_filing.trim() : '';
  const symbolMismatch = Boolean(inFiling) && inFiling.toUpperCase() !== sym;

  const sic = company?.sic_description || company?.sic
    ? `${ipoText(company?.sic_description)} (${ipoText(company?.sic)})`
    : '—';

  return createPortal(
    <div role="dialog" aria-modal="true" aria-label={`${sym} expected listing fact sheet`}
         className="ipo-drill-backdrop" data-testid="ipo-drill"
         onClick={(e) => { e.stopPropagation(); onClose(); }}>
      <div className="ipo-drill" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="ipo-drill-close" aria-label="Close"
                data-testid="ipo-drill-close"
                onClick={(e) => { e.stopPropagation(); onClose(); }}>
          ×
        </button>

        {/* The calendar row is in hand before any fetch, so the header reads
            the same while EDGAR is being asked and when it could not be. */}
        <div className="ipo-drill-head" data-testid="ipo-drill-head">
          <h3 className="ipo-drill-title">{sym} · {ipoText(row?.name)}</h3>
          <p className="ipo-drill-facts" data-testid="ipo-drill-facts">
            Expected {ipoText(row?.date)} · {ipoText(row?.exchange)} · price {ipoText(row?.price)}
            {' · '}shares {ipoText(row?.numberOfShares)} · {ipoText(row?.status)}
          </p>
        </div>

        {state === 'loading' && (
          <p className="ipo-drill-loading" data-testid="ipo-drill-loading">
            …reading the registration filing on EDGAR
          </p>
        )}

        {shownErr && (
          <p className="ipo-drill-err" data-testid="ipo-drill-err">{shownErr}</p>
        )}

        {state === 'ready' && (
          <>
            <section className="ipo-drill-section" data-testid="ipo-drill-sec-what">
              <div className="ipo-drill-eyebrow">WHAT THEY DO</div>
              <blockquote className="ipo-drill-quote">
                {filing?.overview
                  ? String(filing.overview)
                  : '— (no Overview paragraph found in the filing)'}
              </blockquote>
            </section>

            <section className="ipo-drill-section" data-testid="ipo-drill-sec-deal">
              <div className="ipo-drill-eyebrow">THE DEAL</div>
              <Line k="Symbol line" v={ipoText(filing?.proposed_symbol_line)} />
              <Line k="Shares" v={ipoText(filing?.shares_offered_line)} />
              <Line k="Price" v={ipoText(filing?.price_line)} />
              <Line k="Underwriters" v={ipoUnderwriters(filing)} />
              {symbolMismatch && (
                <div className="ipo-drill-line" data-testid="ipo-drill-symbol-mismatch">
                  The filing names the symbol {inFiling}; the calendar says {sym}.
                </div>
              )}
            </section>

            <section className="ipo-drill-section" data-testid="ipo-drill-sec-printed">
              <div className="ipo-drill-eyebrow">AS PRINTED IN THE FILING</div>
              <QuoteGroup testid="ipo-drill-quote-revenue" label="Revenue"
                          line={filing?.revenue_line}
                          units={filing?.revenue_units_line}
                          periods={filing?.revenue_period_line} />
              <QuoteGroup testid="ipo-drill-quote-net-loss" label="Net loss"
                          line={filing?.net_loss_line}
                          units={filing?.net_loss_units_line}
                          periods={filing?.net_loss_period_line} />
              <p className="ipo-drill-dim">
                Quoted as printed, whitespace collapsed; each line carries the units and
                column order of its own table. Nothing here is converted.
              </p>
              <div className="ipo-drill-line" data-testid="ipo-drill-source">
                <span className="ipo-drill-k">Source</span>
                <span className="ipo-drill-v">
                  {filing?.url ? (
                    <a href={String(filing.url)} target="_blank" rel="noreferrer">
                      {ipoText(filing.form)} filed {ipoText(filing.filed)}
                    </a>
                  ) : '—'}
                </span>
              </div>
              {filing?.parse_note && (
                <p className="ipo-drill-dim" data-testid="ipo-drill-parse-note">
                  {String(filing.parse_note)}
                </p>
              )}
            </section>

            <section className="ipo-drill-section" data-testid="ipo-drill-sec-industry">
              <div className="ipo-drill-eyebrow">INDUSTRY</div>
              <Line k="SIC" v={sic} />
              <Line k="State" v={ipoText(company?.state)} />
              <Line k="FY end (MMDD as filed)" v={ipoText(company?.fiscal_year_end)} />
            </section>

            <section className="ipo-drill-section" data-testid="ipo-drill-sec-headlines">
              <div className="ipo-drill-eyebrow">HEADLINES</div>
              {headlines.length ? (
                <ul className="ipo-drill-list">
                  {headlines.map((h, i) => (
                    <li key={`${String(h?.url ?? i)}`} className="ipo-drill-line">
                      {/* A headline with no url is a title, not a link — an
                          anchor to "—" would point at /— (verify miss, 2026-09-20). */}
                      {h?.url
                        ? <a href={String(h.url)} target="_blank" rel="noreferrer">{ipoText(h?.title)}</a>
                        : <span>{ipoText(h?.title)}</span>}
                      {' · '}{ipoText(h?.source)}{' · '}{ipoHeadlineDate(h?.published)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="ipo-drill-line">
                  {IPO_DRILL_NO_HEADLINES(payload?.headlines_window_days)}
                </p>
              )}
            </section>

            <section className="ipo-drill-section" data-testid="ipo-drill-sec-sources">
              <div className="ipo-drill-eyebrow">SOURCES</div>
              {sources?.edgar_search_url && (
                <p className="ipo-drill-line">
                  <a href={String(sources.edgar_search_url)} target="_blank" rel="noreferrer">
                    EDGAR full-text search
                  </a>
                </p>
              )}
              {sources?.submissions_url && (
                <p className="ipo-drill-line">
                  <a href={String(sources.submissions_url)} target="_blank" rel="noreferrer">
                    EDGAR submissions
                  </a>
                </p>
              )}
              {sources?.filing_url && (
                <p className="ipo-drill-line">
                  <a href={String(sources.filing_url)} target="_blank" rel="noreferrer">
                    Prospectus
                  </a>
                </p>
              )}
            </section>

            <p className="ipo-drill-note" data-testid="ipo-drill-note">
              {ipoText(payload?.note)}
            </p>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

export default IpoUpcomingModal;
