/* /gex-board — 🧲 cross-sectional dealer-gamma board (Ajay 2026-07-17:
 * "Gamma exposure page … bullish stocks with key nodes and bearish stocks").
 *
 * Data: the nightly options-key GEX snapshot (backend options/gex_history,
 * 17:50 ET cron; ↻ re-sweeps on demand). Bucketing lives in the BACKEND
 * (board_bucket) so this page can never disagree with the engine's read:
 *   🟢 bullish — dealers net long gamma (pinning) with spot at/above the flip
 *   🔴 bearish — dealers net short gamma (amplifying) with spot below the flip
 * Every card shows the KEY NODES: 🎚️ flip, 🧱 call wall, 🛡️ put wall, 🧲 magnet.
 * HONESTY: the dealer-book sign rule is a heuristic — strongest on index/ETF,
 * approximate on single names (badged per row). Tendency, not a guarantee. */
import { useState } from 'react';
import { useGexBoard } from '../hooks/useGexBoard';
import { fmtGex } from '../lib/opex';
import { nodeChips, reliabilityBadge, rowLine, type BoardRow } from '../lib/gexBoard';
import { InfoButton } from '../components/InfoButton';
import { TickerLink } from '../components/TickerLink';

const HowItWorks = (
  <>
    <p>
      <strong>GEX (gamma exposure)</strong> estimates how much stock the market
      makers who sold the options must buy or sell as price moves.
    </p>
    <ul>
      <li><strong>🟢 Bullish</strong> — dealers are long gamma: they buy dips and
        sell rips, which <em>dampens</em> moves. Price tends to grind and pin.</li>
      <li><strong>🔴 Bearish</strong> — dealers are short gamma: their hedging
        pushes price the way it's already going. Moves get <em>amplified</em>.</li>
      <li><strong>🎚️ Flip</strong> — the price where the regime switches.</li>
      <li><strong>🧱 Call wall / 🛡️ put wall</strong> — the biggest gamma strikes
        above / below: ceiling and shelf, not price targets.</li>
      <li><strong>🧲 Magnet</strong> — the largest single gamma node; price often
        gravitates there into expiration.</li>
      <li><strong>VEX</strong> — dealer <em>vanna</em>: how their hedge shifts when
        IV moves. "Tailwind" = falling IV forces dealer buying.</li>
    </ul>
    <p>
      Honesty: the dealer-position sign rule is the industry heuristic
      (SqueezeMetrics-style) — reliable on SPY/QQQ, an approximation on single
      names, and any earnings/news shock overwhelms it. A tendency, never a
      guarantee — confirm with the SEPA setup.
    </p>
  </>
);

function RowCard({ row }: { row: BoardRow }) {
  const rel = reliabilityBadge(row);
  const chips = nodeChips(row);
  return (
    <div style={{ border: '1px solid var(--cm-border, #2a2f3a)', borderRadius: 10,
                  padding: '0.55rem 0.7rem', background: 'var(--cm-card, #161a22)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <TickerLink ticker={row.symbol} fromLabel="GEX Board" showWatchlist={false} />
        <span className="mono" style={{ fontSize: '0.78rem' }}>
          {typeof row.spot === 'number' ? `$${row.spot.toFixed(2)}` : ''}
        </span>
        <b className="mono" style={{ fontSize: '0.78rem' }}>{fmtGex(row.net_gex_dollars)} GEX</b>
        {typeof row.net_vex_dollars === 'number' && (
          <span className="mono" style={{ fontSize: '0.72rem', opacity: 0.85 }}>
            {fmtGex(row.net_vex_dollars)} VEX
          </span>
        )}
        <span style={{ marginLeft: 'auto', fontSize: '0.62rem',
                       color: rel.strong ? 'var(--positive, #34d399)' : 'var(--cm-slate, #94a3b8)' }}>
          {rel.text}
        </span>
      </div>
      {chips.length > 0 && (
        <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', marginTop: 5 }}>
          {chips.map((c) => (
            <span key={c.label} className="mono" title={c.label}
                  style={{ fontSize: '0.7rem', border: '1px solid var(--cm-border, #2a2f3a)',
                           borderRadius: 999, padding: '1px 8px' }}>
              {c.icon} {c.label} {c.text}
            </span>
          ))}
        </div>
      )}
      <div style={{ fontSize: '0.72rem', color: 'var(--cm-slate, #94a3b8)', marginTop: 5 }}>
        {rowLine(row)}
      </div>
    </div>
  );
}

function Column({ title, tone, rows }: { title: string; tone: string; rows: BoardRow[] }) {
  return (
    <div style={{ flex: '1 1 340px', minWidth: 300 }}>
      <h2 style={{ fontSize: '0.95rem', color: tone, margin: '0 0 0.5rem' }}>
        {title} <span style={{ opacity: 0.7 }}>({rows.length})</span>
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {rows.length === 0 && (
          <p style={{ fontSize: '0.78rem', color: 'var(--cm-slate, #94a3b8)' }}>
            Nothing in this bucket in the latest snapshot.
          </p>
        )}
        {rows.map((r) => <RowCard key={r.symbol} row={r} />)}
      </div>
    </div>
  );
}

export function GexBoardPage() {
  const { data, loading, refreshing, err, refresh, addSymbol } = useGexBoard();
  const [showMixed, setShowMixed] = useState(false);
  const [addDraft, setAddDraft] = useState('');
  const [addBusy, setAddBusy] = useState(false);
  const [addErr, setAddErr] = useState<string | null>(null);

  const submitAdd = async () => {
    if (!addDraft.trim() || addBusy) return;
    setAddBusy(true);
    const e = await addSymbol(addDraft);
    setAddErr(e);
    if (!e) setAddDraft('');
    setAddBusy(false);
  };

  return (
    <div className="sepa-page" style={{ maxWidth: 1080, margin: '0 auto' }}>
      <div className="sepa-page__title" style={{ marginBottom: '0.4rem' }}>
        <div className="eyebrow">Options · dealer positioning</div>
        <h1 className="display sepa-page__h1"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          🧲 GEX Board
          <InfoButton inline title="How the GEX Board works">{HowItWorks}</InfoButton>
        </h1>
        <p style={{ color: 'var(--cm-slate, #94a3b8)', margin: '0.15rem 0 0', fontSize: '0.88rem' }}>
          Where dealer gamma helps you (🟢 dips get bought) vs hurts you
          (🔴 moves get amplified) — with each stock's key nodes.
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', margin: '0.5rem 0', flexWrap: 'wrap' }}>
        <button className="sepa-chip" onClick={() => void refresh()} disabled={refreshing}
                style={{ cursor: 'pointer' }}>
          {refreshing ? '↻ Sweeping ~200 option chains… (up to a minute)' : '↻ Refresh snapshot'}
        </button>
        {data?.as_of_date && (
          <span style={{ fontSize: '0.72rem', color: 'var(--cm-slate, #94a3b8)' }}>
            as of {data.as_of_date} (nightly 17:50 ET snapshot)
          </span>
        )}
        {/* Add-ticker (Ajay 2026-08-03: PLTR/SNAP earnings movers weren't in
            the tracked universe) — one chain pull, joins today's board. */}
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center', marginLeft: 'auto' }}>
          <input
            value={addDraft}
            onChange={(e) => setAddDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void submitAdd(); }}
            placeholder="add ticker…"
            aria-label="Add ticker to the GEX board"
            style={{ width: 110, padding: '0.25rem 0.55rem', borderRadius: 8,
                     border: '1px solid var(--cm-border, #2a2f3a)',
                     background: 'var(--cm-card, #161a22)', color: 'inherit',
                     fontSize: '0.78rem' }}
          />
          <button className="sepa-chip" onClick={() => void submitAdd()}
                  disabled={addBusy} style={{ cursor: 'pointer' }}>
            {addBusy ? '…' : '+ add'}
          </button>
        </span>
        {addErr && <span style={{ fontSize: '0.72rem', color: 'var(--negative, #f87171)' }}>{addErr}</span>}
        {err && <span style={{ fontSize: '0.72rem', color: 'var(--negative, #f87171)' }}>⛔ {err}</span>}
      </div>

      {data?.note && (
        <p style={{ fontSize: '0.72rem', color: 'var(--warning, #f59e0b)' }}>ⓘ {data.note}</p>
      )}

      {loading && <p style={{ color: 'var(--cm-slate, #94a3b8)' }}>Loading the latest snapshot…</p>}

      {data && (
        <>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <Column title="🟢 Bullish — dealers dampen dips" tone="var(--positive, #34d399)"
                    rows={data.bullish} />
            <Column title="🔴 Bearish — dealers amplify moves" tone="var(--negative, #f87171)"
                    rows={data.bearish} />
          </div>
          {data.mixed.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <button className="sepa-chip" onClick={() => setShowMixed((v) => !v)}
                      style={{ cursor: 'pointer' }}>
                {showMixed ? '▾' : '▸'} Mixed — regime and flip disagree ({data.mixed.length})
              </button>
              {showMixed && (
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '0.6rem' }}>
                  <Column title="🌫️ Mixed" tone="var(--cm-slate, #94a3b8)" rows={data.mixed} />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
