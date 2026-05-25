import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useNodeThesis, useWhales } from '../hooks/useSupplyDemand';
import { TickerLink } from './TickerLink';
import { ChatterDeepLinks } from './ChatterDeepLinks';
import type { WhaleHolder } from '../hooks/useSupplyDemand';

type Props = {
  ticker: string | null;
  onClose: () => void;
};

/**
 * NodeThesisPanel — slide-in drawer showing rich detail when user clicks a
 * node in the DependencyGraph. Three sections:
 *   1. Thesis — what the company does, moat, bull/bear, what to watch
 *   2. Relationships — every edge explained in plain English
 *   3. Whales — top 13F institutional holders + recent buys/sells
 *
 * Closes on:
 *   - X button
 *   - Esc key
 *   - Backdrop click
 */
export function NodeThesisPanel({ ticker, onClose }: Props) {
  const location = useLocation();
  // Label for back button: pretty name based on current pathname
  const backLabel = location.pathname.startsWith('/supply-demand') ? 'Supply / Demand'
    : location.pathname.startsWith('/sepa') ? 'SEPA'
    : location.pathname.startsWith('/catalysts') ? 'Catalysts'
    : 'previous';
  const { data: thesis, loading: thesisLoading } = useNodeThesis(ticker);
  const { data: whales, loading: whalesLoading } = useWhales(ticker);

  // Close on Esc
  useEffect(() => {
    if (!ticker) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [ticker, onClose]);

  if (!ticker) return null;

  return (
    <>
      <div className="ntp-backdrop" onClick={onClose} />
      <aside className="ntp-drawer" role="dialog" aria-label={`${ticker} detail`}>
        <header className="ntp-head">
          <div className="ntp-head__main">
            <h2 className="ntp-ticker">{ticker}</h2>
            {thesis?.name && <p className="ntp-name">{thesis.name}</p>}
            <div className="ntp-tags">
              {thesis?.sector && <span className="ntp-tag">{thesis.sector}</span>}
              {thesis?.sub_sector && <span className="ntp-tag ntp-tag--sub">{thesis.sub_sector}</span>}
            </div>
          </div>
          <button className="ntp-close" onClick={onClose} aria-label="Close">×</button>
        </header>

        <div className="ntp-body">
          {/* SECTION 1: Thesis */}
          {thesisLoading && <div className="ntp-loading">Loading thesis…</div>}
          {thesis && (
            <>
              {thesis.thesis?.role && (
                <section className="ntp-section">
                  <h3 className="ntp-section__h">Role in the supply chain</h3>
                  <p className="ntp-text">{thesis.thesis.role}</p>
                </section>
              )}

              {(thesis.thesis?.moat || thesis.thesis?.watch) && (
                <section className="ntp-section">
                  <div className="ntp-grid2">
                    {thesis.thesis?.moat && (
                      <div className="ntp-mini">
                        <h4 className="ntp-mini__h">Moat</h4>
                        <p className="ntp-mini__t">{thesis.thesis.moat}</p>
                      </div>
                    )}
                    {thesis.thesis?.watch && (
                      <div className="ntp-mini">
                        <h4 className="ntp-mini__h">Watch</h4>
                        <p className="ntp-mini__t">{thesis.thesis.watch}</p>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {(thesis.thesis?.bull_case || thesis.thesis?.bear_case) && (
                <section className="ntp-section">
                  <h3 className="ntp-section__h">Bull / Bear</h3>
                  <div className="ntp-bullbear">
                    {thesis.thesis?.bull_case && (
                      <div className="ntp-bull">
                        <strong>Bull:</strong> {thesis.thesis.bull_case}
                      </div>
                    )}
                    {thesis.thesis?.bear_case && (
                      <div className="ntp-bear">
                        <strong>Bear:</strong> {thesis.thesis.bear_case}
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* SECTION 2: Sector exposures */}
              {thesis.sector_exposures && thesis.sector_exposures.length > 0 && (
                <section className="ntp-section">
                  <h3 className="ntp-section__h">Sector exposure</h3>
                  <div className="ntp-sector-list">
                    {thesis.sector_exposures.map((s) => (
                      <div key={s.sector_id} className={`ntp-sector ntp-sector--${s.state}`}>
                        <div className="ntp-sector__top">
                          <strong>{s.label}</strong>
                          <span className="ntp-sector__state">
                            {s.trend_direction === 'tightening' ? '↑' : s.trend_direction === 'loosening' ? '↓' : '→'}{' '}
                            {s.state.toUpperCase()}
                          </span>
                        </div>
                        <div className="ntp-sector__gap mono">{s.gap_index}/100</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* SECTION 3: Relationships */}
              {thesis.relationships && thesis.relationships.length > 0 && (
                <section className="ntp-section">
                  <h3 className="ntp-section__h">
                    Connections ({thesis.n_relationships})
                  </h3>
                  <ul className="ntp-rel-list">
                    {thesis.relationships.map((r, i) => {
                      const otherSide = r.is_outbound ? r.target : r.source;
                      return (
                        <li key={i} className="ntp-rel">
                          <div className="ntp-rel__head">
                            <TickerLink
                              ticker={otherSide}
                              fromLabel={backLabel}
                              className="ntp-rel__chip"
                              title={`open ${otherSide} (Cmd/Ctrl-click to open in new tab)`}
                            >
                              {otherSide}
                            </TickerLink>
                            <span className={`ntp-rel__type ntp-rel__type--${r.relation}`}>
                              {r.relation.replace(/_/g, ' ')}
                            </span>
                            <span className="ntp-rel__strength mono" title="strength 0-1">
                              {r.strength?.toFixed(1)}
                            </span>
                          </div>
                          <p className="ntp-rel__expl">{r.explanation}</p>
                          {r.evidence && (
                            <p className="ntp-rel__ev">
                              <em>Evidence:</em> {r.evidence}
                            </p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}
            </>
          )}

          {/* SECTION 4: Whales */}
          <section className="ntp-section">
            <h3 className="ntp-section__h">
              Hedge fund / Institutional flow
              {whales?.moves?.net_signal && (
                <span className={`ntp-flow ntp-flow--${whales.moves.net_signal}`}>
                  {whales.moves.net_signal === 'accumulating' && '🟢 ACCUMULATING'}
                  {whales.moves.net_signal === 'distributing' && '🔴 DISTRIBUTING'}
                  {whales.moves.net_signal === 'balanced' && '⚪️ BALANCED'}
                </span>
              )}
            </h3>

            {whalesLoading && <div className="ntp-loading">Loading 13F filings…</div>}

            {whales && (
              <>
                {whales.major && (whales.major.institutional_pct || whales.major.insider_pct) && (
                  <div className="ntp-major mono">
                    {whales.major.institutional_pct && <span>Inst held: <strong>{whales.major.institutional_pct}</strong></span>}
                    {whales.major.insider_pct && <span> · Insider: <strong>{whales.major.insider_pct}</strong></span>}
                    {whales.major.n_institutions && <span> · {whales.major.n_institutions} funds</span>}
                  </div>
                )}

                {whales.moves && (whales.moves.notable_buys.length > 0 || whales.moves.notable_sells.length > 0) && (
                  <div className="ntp-moves">
                    {whales.moves.notable_buys.length > 0 && (
                      <div className="ntp-moves__col">
                        <div className="ntp-moves__h ntp-moves__h--buy">RECENT BUYS</div>
                        {whales.moves.notable_buys.map((b, i) => (
                          <div key={i} className="ntp-move ntp-move--buy">
                            <span className="ntp-move__name">{b.holder}</span>
                            <span className="ntp-move__pct mono">+{(b.pct_change * 100).toFixed(0)}%</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {whales.moves.notable_sells.length > 0 && (
                      <div className="ntp-moves__col">
                        <div className="ntp-moves__h ntp-moves__h--sell">RECENT SELLS</div>
                        {whales.moves.notable_sells.map((s, i) => (
                          <div key={i} className="ntp-move ntp-move--sell">
                            <span className="ntp-move__name">{s.holder}</span>
                            <span className="ntp-move__pct mono">{(s.pct_change * 100).toFixed(0)}%</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {whales.holders && whales.holders.length > 0 && (
                  <details className="ntp-holders">
                    <summary>Top {whales.n_holders} institutional holders</summary>
                    <table className="ntp-htable">
                      <thead>
                        <tr>
                          <th>Holder</th>
                          <th>% Held</th>
                          <th>Δ %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {whales.holders.slice(0, 10).map((h: WhaleHolder, i: number) => (
                          <tr key={i} className={`ntp-hrow ntp-hrow--${h.type}`}>
                            <td className="ntp-hrow__name">
                              {h.holder}
                              {h.type === 'hedge_fund' && <span className="ntp-hf-badge">🐋</span>}
                            </td>
                            <td className="mono">{h.pct_held != null ? `${(h.pct_held * 100).toFixed(2)}%` : '—'}</td>
                            <td className={`mono ${(h.pct_change ?? 0) > 0 ? 'pos' : (h.pct_change ?? 0) < 0 ? 'neg' : ''}`}>
                              {h.pct_change != null ? `${h.pct_change > 0 ? '+' : ''}${(h.pct_change * 100).toFixed(0)}%` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )}

                <p className="ntp-disclaimer">{whales.disclaimer}</p>
              </>
            )}

            {!whalesLoading && !whales && (
              <p className="ntp-empty">No 13F data available.</p>
            )}
          </section>

          {/* External chatter / news deep-links */}
          <section className="ntp-section">
            <h3 className="ntp-section__h">Live chatter / news</h3>
            <ChatterDeepLinks ticker={ticker} />
          </section>

          {/* Footer actions */}
          <footer className="ntp-footer">
            <TickerLink
              ticker={ticker}
              fromLabel={backLabel}
              className="ntp-action ntp-action--primary"
              title="Open full SEPA detail (Cmd/Ctrl-click for new tab)"
            >
              Open full SEPA detail →
            </TickerLink>
          </footer>
        </div>
      </aside>
    </>
  );
}
