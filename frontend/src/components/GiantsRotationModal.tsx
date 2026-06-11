/* GiantsRotationModal — "the fund sold $X of this stock: where did the money
 * GO?" For one symbol, every curated Tier S/A giant that moved it last
 * quarter, and — from the SAME 13F filing — that fund's biggest adds (for
 * sellers) or biggest trims (for buyers). The question the per-symbol whales
 * modal can't answer, because yfinance only sees one ticker at a time.
 *
 * Data: GET /giants/rotation/{symbol} — reads the cached full-portfolio
 * filings (SEC EDGAR 13F-HR), no network on the backend hot path. */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';
import { TIER_EMOJI, fmtDeltaUSD, fmtPositionValue } from '../lib/fundTiers';
import { TickerLink } from './TickerLink';

type Move = {
  ticker: string | null;
  name: string;
  delta_usd: number;
  action: string;
  pct_change_shares: number | null;
};

type FundEntry = {
  fund: string;
  name: string;
  tier: 'S' | 'A';
  style: string;
  manager: string;
  quarter: string;
  delta_usd: number;
  action: string;
  pct_change_shares: number | null;
  position_now_usd: number;
  their_top_adds?: Move[];
  their_top_trims?: Move[];
};

type Payload = {
  symbol: string;
  quarter: string | null;
  sellers: FundEntry[];
  buyers: FundEntry[];
  n_funds_checked: number;
  note?: string;
};

const C = { green: '#10b981', red: '#ef4444', muted: '#94a3b8', sub: '#8a93a6' };

function MoveChips({ moves }: { moves: Move[] }) {
  if (!moves?.length) {
    return <span style={{ color: C.sub, fontSize: '0.76rem' }}>no other moves ≥ $1M that quarter</span>;
  }
  return (
    <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
      {moves.map((m, i) => (
        <span key={i}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4,
                       padding: '1px 7px', borderRadius: 6, fontSize: '0.76rem',
                       border: `1px solid ${m.delta_usd > 0 ? C.green : C.red}44`,
                       background: `${m.delta_usd > 0 ? C.green : C.red}10` }}>
          {m.ticker
            ? <TickerLink ticker={m.ticker} showWatchlist={false} title={m.name}
                          style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }}>
                {m.ticker}
              </TickerLink>
            : <span title="not mapped to a US ticker (foreign / non-equity)">{m.name.slice(0, 20)}</span>}
          <b style={{ color: m.delta_usd > 0 ? C.green : C.red }}>{fmtDeltaUSD(m.delta_usd)}</b>
          {m.action === 'new' && <span style={{ color: C.green }}>NEW</span>}
          {m.action === 'exit' && <span style={{ color: C.red }}>EXIT</span>}
        </span>
      ))}
    </span>
  );
}

function FundCard({ e, symbol }: { e: FundEntry; symbol: string }) {
  const sold = e.delta_usd < 0;
  return (
    <div style={{ border: `1px solid ${sold ? C.red : C.green}33`, borderRadius: 10,
                  background: `${sold ? C.red : C.green}08`, padding: '0.6rem 0.75rem',
                  marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <b>{TIER_EMOJI[e.tier]} {e.fund}</b>
        {e.manager && <span style={{ color: C.sub, fontSize: '0.74rem' }}>{e.manager}</span>}
        {e.style === 'quant' && (
          <span style={{ color: C.sub, fontSize: '0.7rem', border: `1px solid ${C.sub}55`,
                         borderRadius: 5, padding: '0 5px' }}
                title="Multi-strat / systematic — huge churn, weak per-name signal">
            quant
          </span>
        )}
        <span style={{ marginLeft: 'auto', fontWeight: 700, color: sold ? C.red : C.green }}>
          {fmtDeltaUSD(e.delta_usd)}
        </span>
      </div>
      <div className="mono" style={{ fontSize: '0.74rem', color: C.muted, margin: '2px 0 6px' }}>
        {e.action === 'exit' ? `fully exited ${symbol}`
          : e.action === 'new' ? `NEW ${symbol} position`
          : `${e.action} ${e.pct_change_shares != null ? `${e.pct_change_shares > 0 ? '+' : ''}${e.pct_change_shares}% shares` : ''}`}
        {e.action !== 'exit' && <> · position now {fmtPositionValue(e.position_now_usd)}</>}
      </div>
      <div style={{ fontSize: '0.76rem' }}>
        <span style={{ color: C.sub, marginRight: 6 }}>
          {sold ? 'where their money went →' : 'funded by trimming →'}
        </span>
        <MoveChips moves={(sold ? e.their_top_adds : e.their_top_trims) || []} />
      </div>
    </div>
  );
}

export function GiantsRotationModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/giants/rotation/${encodeURIComponent(symbol)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => alive && setData(d))
      .catch(() => alive && setErr(true));
    return () => { alive = false; };
  }, [symbol]);

  return createPortal(
    <div onClick={onClose}
         style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  zIndex: 1100, padding: '1rem', overflowY: 'auto' }}>
      <div onClick={(e) => e.stopPropagation()}
           style={{ background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
                    border: '1px solid var(--rule, #333)', borderRadius: 8, width: '100%',
                    maxWidth: 'min(760px, calc(100vw - 2rem))', maxHeight: '90vh',
                    overflow: 'auto', padding: '1.1rem clamp(0.8rem, 3vw, 1.3rem)' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                         marginBottom: '0.6rem', gap: '0.4rem', flexWrap: 'wrap' }}>
          <div>
            <div className="eyebrow">🧭 Giant money rotation · full 13F portfolios</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>
              {symbol}
              {data?.quarter && (
                <span style={{ fontSize: '0.78rem', marginLeft: '0.5rem', color: 'var(--cm-slate)' }}>
                  {data.quarter} filings
                </span>
              )}
            </h2>
          </div>
          <button onClick={onClose} className="mono"
                  style={{ background: 'transparent', border: '1px solid var(--rule,#333)',
                           borderRadius: 6, cursor: 'pointer', padding: '8px 14px', color: 'inherit' }}>
            ✕
          </button>
        </header>

        {err && <p className="mono" style={{ color: C.red }}>Rotation read failed — try again shortly.</p>}
        {!err && !data && <p className="mono" style={{ opacity: 0.7 }}>…reading cached 13F filings</p>}

        {data && (
          <>
            {!data.sellers.length && !data.buyers.length && (
              <p style={{ color: C.muted, fontSize: '0.86rem' }}>
                None of the {data.n_funds_checked} curated Tier S/A giants moved {symbol} by ≥ $1M
                last quarter (or their filings aren't cached yet — the nightly refresh fills them in).
                Index-giant flow (Vanguard / BlackRock) is deliberately excluded: mandate-driven, not conviction.
              </p>
            )}

            {data.sellers.length > 0 && (
              <section style={{ marginBottom: 12 }}>
                <div className="eyebrow" style={{ color: C.red, marginBottom: 6 }}>
                  ▼ sold {symbol} — and where that money went
                </div>
                {data.sellers.map((e, i) => <FundCard key={i} e={e} symbol={symbol} />)}
              </section>
            )}

            {data.buyers.length > 0 && (
              <section style={{ marginBottom: 12 }}>
                <div className="eyebrow" style={{ color: C.green, marginBottom: 6 }}>
                  ▲ bought {symbol} — and what they trimmed to fund it
                </div>
                {data.buyers.map((e, i) => <FundCard key={i} e={e} symbol={symbol} />)}
              </section>
            )}

            <p className="mono" style={{ fontSize: '0.7rem', color: C.sub, marginTop: 8 }}>
              {data.note || 'Quarterly 13F-HR data, up to 45-day lag, longs only.'} Moves valued at
              period-end prices (Δshares × price) — separates the fund's decision from market drift.
              Not investment advice.
            </p>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
