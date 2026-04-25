import { useEffect, useMemo, useState } from 'react';
import { fetchSepaCandidate, addToWatchlist, planPosition } from '../hooks/useSepa';
import { SepaScoreBar } from './SepaScoreBar';
import { SepaTrendDots } from './SepaTrendDots';
import { InfoButton } from './InfoButton';

const TREND_LABEL: Record<string, { label: string; help: string }> = {
  price_above_ma150_and_ma200: {
    label: 'Price above 150-day & 200-day MA',
    help: 'Closing price is above both the 150-day and 200-day moving averages — confirms an intermediate and long-term uptrend.',
  },
  ma150_above_ma200: {
    label: '150-day MA above 200-day MA',
    help: 'Long-term moving averages are stacking up the right way — bullish ordering.',
  },
  ma200_trending_up: {
    label: '200-day MA trending up',
    help: 'The 200-day moving average is rising over the last month — the long-term trend itself is up, not just the price.',
  },
  ma50_above_ma150_above_ma200: {
    label: '50-day > 150-day > 200-day MA',
    help: 'All three key moving averages are stacked in proper Stage 2 order. Short above intermediate above long.',
  },
  price_above_ma50: {
    label: 'Price above 50-day MA',
    help: 'Closing price is above the 50-day moving average — short-term trend is also intact.',
  },
  at_least_30pct_above_52w_low: {
    label: 'At least 30% above 52-week low',
    help: 'Stock has already lifted at least 30% off its yearly low — meaning it has begun its advance, not just basing.',
  },
  within_25pct_of_52w_high: {
    label: 'Within 25% of 52-week high',
    help: 'Stock is close enough to its yearly high to be a real breakout candidate, not a deep recovery play.',
  },
  rs_rank_at_least_70: {
    label: 'Relative Strength rank ≥ 70',
    help: 'Outperforming at least 70% of the market over the last 12 months. Minervini\'s minimum bar.',
  },
};

const STAT_HELP: Record<string, string> = {
  Stage: '1 Basing → 2 Advancing → 3 Topping → 4 Declining. Only Stage 2 is a buy candidate per Stan Weinstein\'s framework.',
  RS: 'Relative Strength rank — percentile vs the entire market over 12 months. 99 = top 1%. Need ≥ 70.',
  ADR: 'Average Daily Range — the typical daily move as a percentage of price. Higher means more volatility (more profit potential, more risk).',
  '$ vol': 'Average daily dollar volume traded. A liquidity check — too low and you can\'t enter or exit cleanly.',
};

const ModalInfo = (
  <>
    <p>
      <strong>Stock detail view</strong> — everything the scanner found about this
      ticker, plus a position-sizing calculator. The big number is the
      <strong> composite score</strong> (0-100): a blend of trend strength, Relative
      Strength rank, base quality, fundamentals, and any catalyst.
    </p>
    <p>The five tabs:</p>
    <ul>
      <li>
        <strong>Setup</strong> — buy point (<strong>pivot</strong>), exit
        (<strong>stop</strong>), R-multiple targets, and a calculator that turns your
        account size and risk percentage into a share count.
      </li>
      <li>
        <strong>Trend</strong> — Minervini's eight Trend Template rules, which ones
        passed, current stage (1-4), Volatility Contraction Pattern (VCP) details.
      </li>
      <li>
        <strong>Fundamentals</strong> — CANSLIM grades: Current quarterly earnings,
        Annual earnings, Institutional ownership. Empty unless the scan ran with
        catalyst on.
      </li>
      <li>
        <strong>Catalyst</strong> — news sentiment, analyst up/down revisions in the
        last 30 days, top headlines. Empty unless the scan ran with catalyst on.
      </li>
      <li>
        <strong>Insider</strong> — Securities and Exchange Commission (SEC) filings:
        Form 4 insider trades, 13D activist stakes, 13G passive stakes, and how long
        since the company's Initial Public Offering (IPO).
      </li>
    </ul>
    <p>
      Click <strong>+ Add to watchlist</strong> on the Setup tab to track this entry
      plan. Press <strong>Esc</strong> to close.
    </p>
  </>
);

type Props = { symbol: string | null; onClose: () => void };
type Tab = 'chart' | 'setup' | 'trend' | 'fundamentals' | 'catalyst' | 'insider';

function tvSymbolFor(symbol: string, exchange?: string): string {
  const ex = (exchange || '').toUpperCase();
  if (ex.includes('NYSE')) return `NYSE:${symbol}`;
  if (ex.includes('AMEX')) return `AMEX:${symbol}`;
  return `NASDAQ:${symbol}`;
}

export function SepaCandidateModal({ symbol, onClose }: Props) {
  const [data, setData] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [accountSize, setAccountSize] = useState(100000);
  const [riskPct, setRiskPct] = useState(1);
  const [tab, setTab] = useState<Tab>('chart');
  const [added, setAdded] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setData(null); setErr(null); setPlan(null); setAdded(false); setTab('chart');
    fetchSepaCandidate(symbol).then(setData).catch((e) => setErr(String(e)));
  }, [symbol]);

  const setup = data?.base?.entry_setup;
  const base = data?.base;

  useEffect(() => {
    if (!setup || !accountSize) { setPlan(null); return; }
    planPosition({
      entry: setup.pivot, stop: setup.stop,
      account_size: accountSize, risk_per_trade_pct: riskPct,
    }).then(setPlan).catch(() => setPlan(null));
  }, [setup, accountSize, riskPct]);

  // ESC to close
  useEffect(() => {
    if (!symbol) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [symbol, onClose]);

  const rMultiples = useMemo(() => {
    if (!setup) return null;
    const risk = setup.pivot - setup.stop;
    return {
      entry: setup.pivot,
      stop: setup.stop,
      twoR: setup.pivot + risk * 2,
      threeR: setup.pivot + risk * 3,
      risk,
    };
  }, [setup]);

  if (!symbol) return null;

  return (
    <div className="sepa-drawer-backdrop" onClick={onClose}>
      <aside className="sepa-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`SEPA detail for ${symbol}`}>
        <header className="sepa-drawer__head">
          <div>
            <div className="eyebrow">SEPA candidate</div>
            <h2 className="sepa-drawer__sym">{symbol}</h2>
            {data?.profile?.name && (
              <div className="sepa-drawer__company">
                {data.profile.name}
                {data.profile.exchange && (
                  <span className="sepa-drawer__exchange mono"> · {data.profile.exchange}</span>
                )}
                {data.profile.industry && (
                  <span className="sepa-drawer__industry"> · {data.profile.industry}</span>
                )}
              </div>
            )}
            {base && (
              <SepaScoreBar score={base.score ?? 0} rating={base.rating} size="md" />
            )}
          </div>
          <div className="sepa-drawer__head-actions">
            <InfoButton title={`${symbol} — How to read this`}>{ModalInfo}</InfoButton>
            <button className="sepa-btn sepa-drawer__close" onClick={onClose} aria-label="Close drawer">✕</button>
          </div>
        </header>

        {err && <p className="sepa-err">{err}</p>}
        {!data && !err && (
          <div className="sepa-drawer__loading">
            <div className="eyebrow">Loading</div>
            <div className="sepa-loading__dots"><span /><span /><span /></div>
          </div>
        )}

        {data && (
          <>
            <nav className="sepa-tabs" role="tablist">
              {(['chart', 'setup', 'trend', 'fundamentals', 'catalyst', 'insider'] as Tab[]).map((t) => (
                <button
                  key={t}
                  role="tab"
                  className={`sepa-tab ${tab === t ? 'is-active' : ''}`}
                  onClick={() => setTab(t)}
                >{t}</button>
              ))}
            </nav>

            <div className="sepa-drawer__body">
              {tab === 'chart' && (
                <section>
                  <div className="sepa-tab-help">
                    <strong>Live chart</strong> — TradingView's interactive daily chart.
                    Use the dropdown at the top-left to change interval (1m, 5m, 1h, 1D, 1W).
                    Click <strong>Indicators</strong> to overlay the 50-day, 150-day, and
                    200-day moving averages — the basis of the Trend Template — or volume
                    bars to confirm an accumulation pattern. The chart shows real-time price
                    during market hours.
                  </div>
                  <div className="sepa-drawer__chart">
                    <iframe
                      title={`${symbol} live chart`}
                      src={`https://s.tradingview.com/widgetembed/?frameElementId=tv-sepa-${symbol}&symbol=${encodeURIComponent(tvSymbolFor(symbol, data?.profile?.exchange))}&interval=D&theme=dark&style=1&timezone=America%2FNew_York&withdateranges=1&hide_side_toolbar=0&allow_symbol_change=1&save_image=0&studies=%5B%5D&locale=en`}
                      style={{ width: '100%', height: '100%', border: 0 }}
                      allow="clipboard-write"
                    />
                  </div>
                  <div className="sepa-drawer__chart-links">
                    <a href={`https://www.tradingview.com/symbols/${symbol}/`} target="_blank" rel="noreferrer">Open in TradingView</a>
                    <a href={`https://finance.yahoo.com/quote/${symbol}`} target="_blank" rel="noreferrer">Yahoo Finance</a>
                    <a href={`https://stockanalysis.com/stocks/${symbol.toLowerCase()}/`} target="_blank" rel="noreferrer">StockAnalysis</a>
                  </div>
                </section>
              )}
              {tab === 'setup' && (
                <section>
                  <div className="sepa-tab-help">
                    <strong>Setup</strong> — the entry plan. <strong>Pivot</strong> is the buy
                    point (a defined breakout level from the base). <strong>Stop</strong> is your
                    exit if it fails — kept within 7-8% below pivot per Minervini's risk rules.
                    The <strong>R-multiple ladder</strong> shows where to scale out (+2R, +3R)
                    relative to your initial risk. Set account size and risk percentage to
                    auto-calculate position size.
                  </div>
                  {setup ? (
                    <>
                      <div className="sepa-setup-bar">
                        <span className={`sepa-pill sepa-pill--${setup.type.toLowerCase()}`}>{setup.type}</span>
                        <span className="mono">pivot ${setup.pivot} · stop ${setup.stop}</span>
                      </div>

                      {/* R-multiple ladder */}
                      {rMultiples && (
                        <div className="sepa-rladder">
                          <div className="sepa-rladder__bar">
                            <div className="sepa-rladder__seg sepa-rladder__seg--risk" />
                            <div className="sepa-rladder__seg sepa-rladder__seg--r1" />
                            <div className="sepa-rladder__seg sepa-rladder__seg--r2" />
                            <div className="sepa-rladder__seg sepa-rladder__seg--r3" />
                          </div>
                          <div className="sepa-rladder__labels mono">
                            <span>stop ${rMultiples.stop.toFixed(2)}</span>
                            <span className="sepa-rladder__entry">entry ${rMultiples.entry.toFixed(2)}</span>
                            <span>+2R ${rMultiples.twoR.toFixed(2)}</span>
                            <span>+3R ${rMultiples.threeR.toFixed(2)}</span>
                          </div>
                        </div>
                      )}

                      <div className="sepa-planner">
                        <label className="sepa-field">
                          Account size
                          <input type="number" value={accountSize}
                                 onChange={(e) => setAccountSize(Number(e.target.value))} />
                        </label>
                        <label className="sepa-field">
                          Risk per trade %
                          <input type="number" step="0.25" min="0.25" max="2" value={riskPct}
                                 onChange={(e) => setRiskPct(Number(e.target.value))} />
                        </label>
                      </div>

                      {plan && (
                        <div className="sepa-plan">
                          <div className="sepa-plan__row">
                            <span>Shares</span><strong className="mono">{plan.shares}</strong>
                          </div>
                          <div className="sepa-plan__row">
                            <span>Position</span>
                            <strong className="mono">${plan.dollar_position?.toLocaleString?.() ?? plan.dollar_position} ({plan.position_pct_of_account}%)</strong>
                          </div>
                          <div className="sepa-plan__row">
                            <span>$ Risk</span>
                            <strong className="mono">${plan.dollar_risk} ({plan.risk_pct}% stop)</strong>
                          </div>
                          <div className="sepa-plan__row sepa-plan__row--target">
                            <span>2R target</span><strong className="mono">${plan.reward_target_2r}</strong>
                          </div>
                          <div className="sepa-plan__row sepa-plan__row--target">
                            <span>3R target</span><strong className="mono">${plan.reward_target_3r}</strong>
                          </div>
                          {plan.warnings?.map((w: string, i: number) => (
                            <div key={i} className="sepa-warn">⚠ {w}</div>
                          ))}
                        </div>
                      )}

                      <button
                        className={`sepa-btn sepa-btn--primary sepa-btn--block ${added ? 'is-added' : ''}`}
                        onClick={() => { addToWatchlist(symbol, setup.pivot, setup.stop); setAdded(true); }}
                        disabled={added}
                      >
                        {added ? '✓ Added to watchlist' : '+ Add to watchlist'}
                      </button>
                    </>
                  ) : (
                    <p className="sepa-empty">No qualifying entry setup detected.</p>
                  )}
                </section>
              )}

              {tab === 'trend' && base && (
                <section>
                  <div className="sepa-tab-help">
                    <strong>Trend Template</strong> — Minervini's 8 rules a stock must pass
                    before it's a buy candidate (price above 50/150/200-day moving averages,
                    averages stacked correctly, 200-day rising, within 25% of 52-week high,
                    30%+ off 52-week low, Relative Strength rank ≥ 70). <strong>Stage</strong>
                    is the four-phase cycle: 1 Basing, 2 Advancing, 3 Topping, 4 Declining —
                    only Stage 2 is buyable. <strong>Volatility Contraction Pattern (VCP)</strong>
                    flags a tightening base with shrinking pullbacks.
                  </div>
                  <div className="eyebrow">Trend Template (8 criteria)</div>
                  <SepaTrendDots checks={base.trend.checks} passed={base.trend.passed} />
                  <ul className="sepa-checks">
                    {Object.entries(base.trend.checks).map(([k, v]) => {
                      const meta = TREND_LABEL[k];
                      return (
                        <li key={k} className={v ? 'pass' : 'fail'}>
                          <div className="sepa-check__row">
                            <span className="sepa-check__icon">{v ? '✓' : '✗'}</span>
                            <span className="sepa-check__label">
                              {meta?.label ?? k.replaceAll('_', ' ')}
                            </span>
                          </div>
                          {meta?.help && <div className="sepa-check__help">{meta.help}</div>}
                        </li>
                      );
                    })}
                  </ul>
                  <div className="sepa-meta-grid">
                    {base.stage && (
                      <div title={STAT_HELP['Stage']}>
                        <span className="sepa-meta-label">Stage</span>
                        <strong>S{base.stage.stage} {base.stage.label}</strong>
                        <span className="sepa-meta-hint">{STAT_HELP['Stage']}</span>
                      </div>
                    )}
                    {base.rs_rank != null && (
                      <div title={STAT_HELP['RS']}>
                        <span className="sepa-meta-label">RS</span>
                        <strong>{base.rs_rank}</strong>
                        <span className="sepa-meta-hint">{STAT_HELP['RS']}</span>
                      </div>
                    )}
                    {base.adr_pct != null && (
                      <div title={STAT_HELP['ADR']}>
                        <span className="sepa-meta-label">ADR</span>
                        <strong>{base.adr_pct}%</strong>
                        <span className="sepa-meta-hint">{STAT_HELP['ADR']}</span>
                      </div>
                    )}
                    {base.liquidity?.avg_dollar_vol != null && (
                      <div title={STAT_HELP['$ vol']}>
                        <span className="sepa-meta-label">$ vol</span>
                        <strong>${(base.liquidity.avg_dollar_vol / 1e6).toFixed(1)}M</strong>
                        <span className="sepa-meta-hint">{STAT_HELP['$ vol']}</span>
                      </div>
                    )}
                  </div>
                  {base.vcp?.has_base && (
                    <div className="sepa-vcp">
                      <div className="eyebrow">VCP</div>
                      <div className="mono">
                        {base.vcp.n_contractions} contractions · depth {base.vcp.base_depth_pct}% · final {base.vcp.final_contraction_pct}%
                        {base.vcp.pivot_quality_ok && ' · ✓ pivot quality'}
                      </div>
                    </div>
                  )}
                </section>
              )}

              {tab === 'fundamentals' && (
                <section>
                  <div className="sepa-tab-help">
                    <strong>CANSLIM</strong> — William O'Neil's seven-letter fundamentals check
                    (Current quarterly earnings, Annual earnings, New product/management,
                    Supply &amp; demand, Leader, Institutional sponsorship, Market direction).
                    The rows below grade the quantifiable ones: <strong>C</strong> = quarterly
                    earnings-per-share growth year over year (need ≥ 25%), <strong>A</strong> =
                    three-year annual earnings-per-share growth (need ≥ 25%),
                    <strong> I</strong> = institutional ownership (need 40-80% — too low means
                    no support, too high means no upside left).
                  </div>
                  <div className="eyebrow">CANSLIM fundamentals</div>
                  {base?.fundamentals ? (
                    <div className="sepa-fund">
                      <div className="sepa-fund__row">
                        <span>C — Q EPS Y/Y</span>
                        <strong className={base.fundamentals.checks.c_strong_q_eps ? 'pass' : 'fail'}>
                          {base.fundamentals.q_eps_growth_pct ?? '—'}%
                          {base.fundamentals.checks.c_strong_q_eps ? ' ✓' : ' (need ≥25%)'}
                        </strong>
                      </div>
                      <div className="sepa-fund__row">
                        <span>A — Annual EPS 3yr</span>
                        <strong className={base.fundamentals.checks.a_strong_y_eps ? 'pass' : 'fail'}>
                          {base.fundamentals.y_eps_growth_pct ?? '—'}%
                          {base.fundamentals.checks.a_strong_y_eps ? ' ✓' : ' (need ≥25%)'}
                        </strong>
                      </div>
                      <div className="sepa-fund__row">
                        <span>I — Institutional own</span>
                        <strong className={base.fundamentals.checks.i_institutional ? 'pass' : 'fail'}>
                          {base.fundamentals.inst_ownership_pct ?? '—'}%
                          {base.fundamentals.checks.i_institutional ? ' ✓' : ' (need 40-80%)'}
                        </strong>
                      </div>
                      <div className="sepa-fund__row">
                        <span>Revenue Q Y/Y</span>
                        <strong>{base.fundamentals.rev_growth_q_pct ?? '—'}%</strong>
                      </div>
                    </div>
                  ) : (
                    <p className="sepa-empty">No fundamentals — re-scan with <code>+catalyst</code> to populate.</p>
                  )}
                </section>
              )}

              {tab === 'catalyst' && (
                <section>
                  <div className="sepa-tab-help">
                    <strong>Catalyst</strong> — what could move the stock in the near term.
                    <strong> News sentiment</strong> is a Finnhub composite of recent
                    headlines (negative → positive, roughly -1 to +1). <strong>Up/down
                    revisions</strong> are how many sell-side analysts raised or cut their
                    price targets in the last 30 days — directional pressure on the stock.
                    The headlines list is the latest news; click through and read before
                    buying. This tab is empty unless you ran a <strong>+ catalyst</strong>
                    scan.
                  </div>
                  {data.catalyst ? (
                    <>
                      {data.catalyst.earnings_upcoming && (
                        <div className="sepa-callout">
                          📅 Earnings <strong>{data.catalyst.earnings_upcoming.date}</strong>{' '}
                          ({data.catalyst.earnings_upcoming.hour ?? '—'})
                        </div>
                      )}
                      <div className="sepa-meta-grid">
                        <div><span className="sepa-meta-label">News sentiment</span><strong>{data.catalyst.news_sentiment_score ?? 0}</strong></div>
                        <div><span className="sepa-meta-label">Up revs (30d)</span><strong>{data.catalyst.analyst_up_revisions_30d ?? 0}</strong></div>
                        <div><span className="sepa-meta-label">Down revs (30d)</span><strong>{data.catalyst.analyst_down_revisions_30d ?? 0}</strong></div>
                      </div>
                      <ul className="sepa-news">
                        {data.catalyst.top_news?.slice(0, 6).map((n: any, i: number) => (
                          <li key={i}>
                            <a href={n.link} target="_blank" rel="noreferrer">{n.title}</a>
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="sepa-empty">No catalyst data — run <code>+catalyst</code> scan.</p>
                  )}
                </section>
              )}

              {tab === 'insider' && (
                <section>
                  <div className="sepa-tab-help">
                    <strong>Insider activity</strong> — pulled from Securities and Exchange
                    Commission (SEC) filings. <strong>Form 4</strong> = officer/director
                    open-market trades; multiple insiders buying ("cluster") is bullish.
                    <strong> 13D</strong> = an outside investor crossing 5% with intent to
                    influence (activist stake — strong signal). <strong>13G</strong> = same
                    threshold but passive (index funds) — weaker signal. <strong>IPO
                    age</strong> matters because Minervini favors stocks within 8 years of
                    going public — most big winners come from young companies.
                  </div>
                  {data.insider ? (
                    <ul className="sepa-kv mono">
                      <li>Form 4 (30d): <strong>{data.insider.form4_count_30d}</strong> · unique insiders: <strong>{data.insider.form4_unique_insiders_30d}</strong></li>
                      {data.insider.form4_cluster_buy && <li className="sepa-flag sepa-flag--good">★ Cluster insider buying</li>}
                      <li>13D (180d): {data.insider.sc13d_180d} {data.insider.has_recent_13d && '★ recent'}</li>
                      <li>13G (180d): {data.insider.sc13g_180d}</li>
                    </ul>
                  ) : <p className="sepa-empty">No insider data.</p>}
                  {data.ipo_age && (
                    <div className="sepa-callout mono">
                      IPO {data.ipo_age.first_trade_date} · {data.ipo_age.years_since_ipo}y old
                      {data.ipo_age.is_young && ' · young ✓'}
                      {data.ipo_age.is_recent_ipo && ' · recent IPO ✓'}
                    </div>
                  )}
                </section>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
