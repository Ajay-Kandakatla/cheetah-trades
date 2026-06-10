/* GiantsFlowBoard — "Where the giants are buying", aggregated + trended
 * (Ajay 2026-06-10: "leaderboard section of where the giants are buying...
 * a trend somehow where the giants investments are moving, maybe with a
 * timeline... for MU it would help to know where the money from MU moved").
 *
 * Source: full SEC EDGAR 13F-HR portfolios of the curated Tier S/A funds
 * (backend giants/), aggregated per ticker per quarter. Each row carries a
 * multi-quarter net-flow sparkline (the trend), and clicking a row opens the
 * rotation modal — which funds moved it and where THEIR money went.
 *
 * Distinct from <MoneyMovement/> (per-fund view of yfinance's top-15-holder
 * snapshots): this is stock-ranked, dollar-exact across ENTIRE portfolios,
 * with history. Index giants are excluded by design — mandate flow and
 * entity restructurings (e.g. the Vanguard LLC shuffle) read as fake buys. */
import { useMemo, useState } from 'react';
import { useGiantsFlows, type GiantsFlowRow } from '../hooks/useGiantsFlows';
import { useSort } from '../lib/useSort';
import { fmtDeltaUSD } from '../lib/fundTiers';
import { InfoButton } from './InfoButton';
import { GiantsRotationModal } from './GiantsRotationModal';
import { TickerCell } from './TickerCell';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280' };

/** Tiny per-quarter net-flow bars — the row's trend at a glance. */
function Sparkline({ timeline }: { timeline: { q: string; net_usd: number }[] }) {
  const max = Math.max(1, ...timeline.map((t) => Math.abs(t.net_usd)));
  const W = 9, GAP = 3, H = 26, MID = H / 2;
  return (
    <svg width={timeline.length * (W + GAP)} height={H} style={{ display: 'block' }}>
      {timeline.map((t, i) => {
        const h = Math.max(1, (Math.abs(t.net_usd) / max) * (MID - 1));
        const up = t.net_usd >= 0;
        return (
          <rect key={i} x={i * (W + GAP)} y={up ? MID - h : MID} width={W} height={h}
                rx={1} fill={up ? C.green : C.red} opacity={0.55 + 0.45 * (i / Math.max(1, timeline.length - 1))}>
            <title>{`${t.q}: ${fmtDeltaUSD(t.net_usd)} net`}</title>
          </rect>
        );
      })}
      <line x1={0} x2={timeline.length * (W + GAP)} y1={MID} y2={MID}
            stroke="var(--rule,#333)" strokeWidth={0.5} />
    </svg>
  );
}

const SORTS: { key: string; label: string; dir: 'asc' | 'desc' }[] = [
  { key: 'net', label: 'Net $', dir: 'desc' },
  { key: 'funds', label: '# Giants', dir: 'desc' },
  { key: 'symbol', label: 'A–Z', dir: 'asc' },
];

function FlowTable({ rows, direction, onPick }: {
  rows: GiantsFlowRow[]; direction: 'in' | 'out'; onPick: (sym: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const sort = useSort<GiantsFlowRow>(rows, {
    net: (r) => Math.abs(r.net_usd),
    funds: (r) => (direction === 'in' ? r.n_buying : r.n_selling),
    symbol: (r) => r.ticker,
  }, 'net');
  const visible = showAll ? sort.sorted : sort.sorted.slice(0, 12);
  if (!rows.length) {
    return <p style={{ color: C.sub, fontSize: '0.82rem' }}>no net {direction === 'in' ? 'inflows' : 'outflows'} this quarter</p>;
  }
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 4, marginBottom: 4 }}>
        {SORTS.map((s) => (
          <button key={s.key} onClick={() => sort.toggle(s.key, s.dir)}
                  style={{ fontSize: '0.64rem', padding: '0 6px', borderRadius: 5, cursor: 'pointer',
                           background: sort.key === s.key ? 'var(--gold,#c9a227)' : 'transparent',
                           color: sort.key === s.key ? '#1a1a1a' : 'inherit',
                           border: `1px solid ${sort.key === s.key ? 'var(--gold,#c9a227)' : 'var(--hairline,#2a2a2a)'}` }}>
            {s.label}{sort.arrow(s.key)}
          </button>
        ))}
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ color: C.sub, fontSize: '0.68rem', textTransform: 'uppercase' }}>
              <th style={{ textAlign: 'left', padding: '3px 8px' }}>Ticker</th>
              <th style={{ textAlign: 'right', padding: '3px 8px' }}>Net flow</th>
              <th style={{ textAlign: 'right', padding: '3px 8px' }}>Giants</th>
              <th style={{ textAlign: 'left', padding: '3px 8px' }}>
                {direction === 'in' ? 'Top buyer' : 'Top seller'}
              </th>
              <th style={{ textAlign: 'left', padding: '3px 8px' }} title="net giant flow per quarter, oldest → newest">Trend</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => {
              const lead = direction === 'in' ? r.buyers[0] : r.sellers[0];
              return (
                <tr key={r.ticker} onClick={() => onPick(r.ticker)}
                    style={{ borderTop: '1px solid var(--hairline,#2a2a2a)', cursor: 'pointer' }}
                    title={`open ${r.ticker} rotation — who moved it and where their money went`}>
                  <td style={{ padding: '5px 8px' }}><TickerCell symbol={r.ticker} size="0.84rem" nameWidth={16} /></td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 700,
                               color: r.net_usd >= 0 ? C.green : C.red }}>
                    {fmtDeltaUSD(r.net_usd)}
                  </td>
                  <td style={{ padding: '5px 8px', textAlign: 'right' }}
                      title={`${r.n_buying} buying / ${r.n_selling} selling (moves ≥ $2M)`}>
                    <span style={{ color: C.green }}>{r.n_buying}▲</span>
                    {' '}
                    <span style={{ color: C.red }}>{r.n_selling}▼</span>
                  </td>
                  <td style={{ padding: '5px 8px', color: C.muted, fontSize: '0.76rem' }}>
                    {lead ? <>{lead.fund} <b style={{ color: lead.usd >= 0 ? C.green : C.red }}>{fmtDeltaUSD(lead.usd)}</b></> : '—'}
                  </td>
                  <td style={{ padding: '5px 8px' }}><Sparkline timeline={r.timeline || []} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {sort.sorted.length > 12 && (
        <button onClick={() => setShowAll(!showAll)} className="mono"
                style={{ marginTop: 6, fontSize: '0.7rem', background: 'transparent', cursor: 'pointer',
                         border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 6, padding: '2px 10px', color: 'inherit' }}>
          {showAll ? 'show top 12' : `show all ${sort.sorted.length}`}
        </button>
      )}
    </div>
  );
}

export function GiantsFlowBoard() {
  const { doc, error } = useGiantsFlows();
  const [tab, setTab] = useState<'in' | 'out'>('in');
  const [rotSym, setRotSym] = useState<string | null>(null);

  const quarterStrip = useMemo(() => (doc?.by_quarter || []).slice(-4), [doc]);

  if (error && !doc) return null; // fail quiet — leaderboard must render

  return (
    <section className="top-picks">
      <div className="top-picks__head">
        <span className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          🏦 Where the giants are buying
          <InfoButton inline title="Where the giants are buying">
            <p>
              Full <strong>13F-HR portfolios</strong> of {doc?.n_funds ?? 38} curated Tier S/A funds
              (Berkshire, Capital World, Fidelity FMR, Primecap, Coatue…) pulled from SEC EDGAR and
              diffed quarter-over-quarter. A move is <em>Δshares × period-end price</em> — price drift
              with no share change is not a flow.
            </p>
            <ul>
              <li><strong>Net flow</strong> — dollars the giants moved into/out of the name last quarter.</li>
              <li><strong>Trend</strong> — the same net flow per quarter, oldest → newest. That's the timeline.</li>
              <li><strong>Click a row</strong> — rotation view: who moved it, and where THAT fund's money
                went in the same filing (e.g. Capital World sold MU → bought AZN, GOOG, AMZN).</li>
            </ul>
            <p className="mono">
              Quarterly, up to 45-day lag, longs only, options excluded. Index giants
              (Vanguard/BlackRock/State Street) excluded — mandate-driven flow, not conviction.
              Not investment advice.
            </p>
          </InfoButton>
        </span>
        <span className="top-picks__meta mono">
          {doc?.latest_quarter ? `${doc.latest_quarter} filings` : ''}
          {doc?.n_funds_with_data != null ? ` · ${doc.n_funds_with_data}/${doc.n_funds} funds` : ''}
        </span>
      </div>

      {doc?.refreshing && (
        <p className="mono" style={{ fontSize: '0.74rem', color: C.amber }}>
          ⏳ refreshing 13F filings from SEC EDGAR
          {doc.refresh_progress ? ` — ${doc.refresh_progress.done}/${doc.refresh_progress.of} funds` : ''}
          {!doc.quarters?.length ? ' (first build downloads ~6 quarters per fund, 15–40 min — fills in as it goes)' : ''}
        </p>
      )}

      {doc && !!quarterStrip.length && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', margin: '6px 0 10px' }}>
          {quarterStrip.map((bq) => (
            <div key={bq.q} style={{ border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 8,
                                     padding: '5px 9px', fontSize: '0.7rem', minWidth: 150 }}>
              <div style={{ color: C.sub, textTransform: 'uppercase', marginBottom: 2 }}>{bq.q}</div>
              <div>
                <span style={{ color: C.green }}>▲ </span>
                {bq.top_in.slice(0, 3).map((t, i) => (
                  <span key={t.ticker}>{i > 0 && ', '}<b>{t.ticker}</b> {fmtDeltaUSD(t.net_usd)}</span>
                ))}
                {!bq.top_in.length && <span style={{ color: C.sub }}>—</span>}
              </div>
              <div>
                <span style={{ color: C.red }}>▼ </span>
                {bq.top_out.slice(0, 3).map((t, i) => (
                  <span key={t.ticker}>{i > 0 && ', '}<b>{t.ticker}</b> {fmtDeltaUSD(t.net_usd)}</span>
                ))}
                {!bq.top_out.length && <span style={{ color: C.sub }}>—</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {doc && (
        <div style={{ display: 'inline-flex', gap: 4, marginBottom: 8 }}>
          {(['in', 'out'] as const).map((d) => (
            <button key={d} onClick={() => setTab(d)}
                    style={{ fontSize: '0.74rem', padding: '2px 12px', borderRadius: 6, cursor: 'pointer',
                             fontWeight: tab === d ? 700 : 400,
                             background: tab === d ? (d === 'in' ? `${C.green}22` : `${C.red}22`) : 'transparent',
                             color: 'inherit',
                             border: `1px solid ${tab === d ? (d === 'in' ? C.green : C.red) : 'var(--hairline,#2a2a2a)'}` }}>
              {d === 'in' ? '▲ Accumulating' : '▼ Distributing'}
            </button>
          ))}
        </div>
      )}

      {doc && (tab === 'in'
        ? <FlowTable rows={doc.rows_in || []} direction="in" onPick={setRotSym} />
        : <FlowTable rows={doc.rows_out || []} direction="out" onPick={setRotSym} />)}

      {doc && !doc.refreshing && !doc.rows_in?.length && !doc.rows_out?.length && (
        <p style={{ color: C.sub, fontSize: '0.82rem' }}>
          {doc.note || 'No giant flow data yet — the nightly 17:35 refresh (or one page view) builds it.'}
        </p>
      )}

      <p className="top-picks__foot mono">
        SEC EDGAR 13F-HR · quarterly, 45-day lag · click a row for the money-rotation view · not investment advice
      </p>

      {rotSym && <GiantsRotationModal symbol={rotSym} onClose={() => setRotSym(null)} />}
    </section>
  );
}
