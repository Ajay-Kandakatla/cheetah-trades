/* MoatPeersModal — opens when the user taps the moat chip on a SEPA card.
   Shows the full component breakdown for the clicked symbol AND a peer
   comparison table from the same industry, so the user can see *why*
   the score came out where it did. Highlights the weakest and
   strongest components vs peers. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Component = {
  score: number;
  roe_pct?: number | null;
  gross_pct?: number | null;
  operating_pct?: number | null;
  fcf_margin_pct?: number | null;
  net_debt_ebitda?: number | null;
  rev_growth_pct?: number | null;
};

type Moat = {
  score: number;
  label: string;
  tier: number;
  narrative: string;
  components: {
    profitability: Component;
    margins:       Component;
    fcf:           Component;
    capital:       Component;
    growth:        Component;
  };
};

type Peer = {
  symbol: string;
  name: string;
  rs_rank?: number;
  score?: number;
  rating?: string;
  moat: Moat;
  deltas: Record<string, number>;
};

type ComponentGap = {
  name: string;
  label: string;
  target: number;
  peer_avg: number;
  gap?: number;
  lead?: number;
  narrative: string;
};

type PeersResponse = {
  target: { symbol: string; name: string; industry: string | null; sector: string | null; moat: Moat | null };
  peers: Peer[];
  peer_count: number;
  industry: string | null;
  weakest_component?: ComponentGap;
  strongest_component?: ComponentGap;
  reason?: string;
};

const COMPONENTS: { key: keyof Moat['components']; label: string; max: number }[] = [
  { key: 'profitability', label: 'Profit', max: 25 },
  { key: 'margins',       label: 'Margin', max: 25 },
  { key: 'fcf',           label: 'FCF',    max: 25 },
  { key: 'capital',       label: 'Capital', max: 15 },
  { key: 'growth',        label: 'Growth', max: 10 },
];

const labelColor = (label: string) => {
  switch (label) {
    case 'WIDE':   return 'var(--positive, #10b981)';
    case 'NARROW': return 'var(--positive, #10b981)';
    case 'SOME':   return 'var(--warn, #d97706)';
    case 'NONE':   return 'var(--negative, #ef4444)';
    default:       return 'var(--cm-slate, #888)';
  }
};

export function MoatPeersModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [data, setData] = useState<PeersResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null); setErr(null);
    fetch(`${API}/sepa/moat/${encodeURIComponent(symbol)}/peers?limit=6`, { cache: 'no-store' })
      .then(r => r.json())
      .then(j => { if (!cancelled) setData(j); })
      .catch(e => { if (!cancelled) setErr(String(e)); });
    return () => { cancelled = true; };
  }, [symbol]);

  // Close on ESC
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const t = data?.target;
  const tm = t?.moat;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '1rem', overflowY: 'auto',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
          border: '1px solid var(--rule, #333)', borderRadius: 8,
          width: '100%', maxWidth: 680, maxHeight: '90vh', overflow: 'auto',
          padding: '1.2rem 1.4rem',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.5rem' }}>
          <div>
            <div className="eyebrow">Moat breakdown · peer comparison</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.4rem' }}>
              {symbol} {tm && <span style={{ color: labelColor(tm.label), fontSize: '0.9rem', marginLeft: '0.4rem' }}>🏰 {tm.label} {tm.score.toFixed(0)}</span>}
            </h2>
            {t?.industry && <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--cm-slate)' }}>{t.industry} · {t.sector}</div>}
          </div>
          <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}>×</button>
        </div>

        {err && <div style={{ color: 'var(--negative)', marginTop: '0.5rem' }}>Couldn't load peers: {err}</div>}
        {!data && !err && <div style={{ color: 'var(--cm-slate)', marginTop: '0.5rem' }}>Loading peers…</div>}

        {data && !tm && (
          <p style={{ color: 'var(--cm-slate)', marginTop: '0.5rem' }}>
            No moat data for {symbol} — yfinance fundamentals missing.
          </p>
        )}

        {data && tm && (
          <>
            <p style={{ fontSize: '0.85rem', marginTop: '0.6rem', color: 'var(--ink, #ddd)' }}>{tm.narrative}</p>

            {/* Per-component scores */}
            <div className="eyebrow" style={{ marginTop: '0.9rem' }}>Where the {tm.score.toFixed(0)} came from</div>
            <table className="mono" style={{ width: '100%', fontSize: '0.78rem', borderCollapse: 'collapse', marginTop: '0.3rem' }}>
              <thead>
                <tr style={{ color: 'var(--cm-slate)' }}>
                  <th style={{ textAlign: 'left',  padding: '0.25rem 0.4rem 0.25rem 0' }}>Component</th>
                  <th style={{ textAlign: 'right', padding: '0.25rem 0.4rem' }}>You</th>
                  <th style={{ textAlign: 'right', padding: '0.25rem 0.4rem' }}>Max</th>
                  <th style={{ textAlign: 'right', padding: '0.25rem 0' }}>Detail</th>
                </tr>
              </thead>
              <tbody>
                {COMPONENTS.map(({ key, label, max }) => {
                  const c = tm.components[key];
                  const pctOfMax = c.score / max;
                  const tone = pctOfMax >= 0.7 ? 'var(--positive, #10b981)'
                              : pctOfMax >= 0.4 ? 'var(--warn, #d97706)'
                              : 'var(--negative, #ef4444)';
                  return (
                    <tr key={key} style={{ borderTop: '1px dashed var(--hairline, #333)' }}>
                      <td style={{ padding: '0.32rem 0.4rem 0.32rem 0' }}>{label}</td>
                      <td style={{ padding: '0.32rem 0.4rem', textAlign: 'right', color: tone, fontWeight: 700 }}>{c.score}</td>
                      <td style={{ padding: '0.32rem 0.4rem', textAlign: 'right', color: 'var(--cm-slate)' }}>/{max}</td>
                      <td style={{ padding: '0.32rem 0', textAlign: 'right', fontSize: '0.72rem', color: 'var(--cm-slate)' }}>
                        {key === 'profitability' && c.roe_pct != null && `ROE ${c.roe_pct}%`}
                        {key === 'margins' && `GM ${c.gross_pct ?? '—'}% · OM ${c.operating_pct ?? '—'}%`}
                        {key === 'fcf' && c.fcf_margin_pct != null && `FCF/rev ${c.fcf_margin_pct}%`}
                        {key === 'capital' && `NetDebt/EBITDA ${c.net_debt_ebitda ?? '—'}`}
                        {key === 'growth' && c.rev_growth_pct != null && `rev +${c.rev_growth_pct}%`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Why it lost points / gained points */}
            {(data.weakest_component || data.strongest_component) && (
              <div style={{ marginTop: '0.9rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.5rem' }}>
                {data.weakest_component && (
                  <div style={{ padding: '0.6rem 0.8rem', borderLeft: '3px solid var(--negative, #ef4444)', background: 'rgba(239,68,68,0.06)', borderRadius: 4 }}>
                    <div className="eyebrow" style={{ color: 'var(--negative)' }}>where you lag peers</div>
                    <div style={{ fontWeight: 700, marginTop: 2 }}>{data.weakest_component.label}</div>
                    <div style={{ fontSize: '0.78rem', marginTop: 2 }}>
                      You {data.weakest_component.target} vs peer avg {data.weakest_component.peer_avg}
                      <span style={{ color: 'var(--negative)' }}> (-{data.weakest_component.gap?.toFixed(1)})</span>
                    </div>
                    {data.weakest_component.narrative && <div style={{ fontSize: '0.72rem', color: 'var(--cm-slate)', marginTop: 4 }}>{data.weakest_component.narrative}</div>}
                  </div>
                )}
                {data.strongest_component && (
                  <div style={{ padding: '0.6rem 0.8rem', borderLeft: '3px solid var(--positive, #10b981)', background: 'rgba(16,185,129,0.06)', borderRadius: 4 }}>
                    <div className="eyebrow" style={{ color: 'var(--positive)' }}>where you beat peers</div>
                    <div style={{ fontWeight: 700, marginTop: 2 }}>{data.strongest_component.label}</div>
                    <div style={{ fontSize: '0.78rem', marginTop: 2 }}>
                      You {data.strongest_component.target} vs peer avg {data.strongest_component.peer_avg}
                      <span style={{ color: 'var(--positive)' }}> (+{data.strongest_component.lead?.toFixed(1)})</span>
                    </div>
                    {data.strongest_component.narrative && <div style={{ fontSize: '0.72rem', color: 'var(--cm-slate)', marginTop: 4 }}>{data.strongest_component.narrative}</div>}
                  </div>
                )}
              </div>
            )}

            {/* Peer table */}
            <div className="eyebrow" style={{ marginTop: '1rem' }}>
              Peers in {data.industry || '—'} {data.peer_count > 0 ? `· ${data.peer_count} found` : ''}
            </div>
            {data.peers.length === 0 ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)', marginTop: '0.4rem' }}>
                {data.reason || 'No same-industry peers in the latest SEPA scan. Peers appear once they pass the scan filters too.'}
              </p>
            ) : (
              <table className="mono" style={{ width: '100%', fontSize: '0.78rem', borderCollapse: 'collapse', marginTop: '0.3rem' }}>
                <thead>
                  <tr style={{ color: 'var(--cm-slate)' }}>
                    <th style={{ textAlign: 'left',  padding: '0.25rem 0.4rem 0.25rem 0' }}>Peer</th>
                    <th style={{ textAlign: 'right', padding: '0.25rem 0.4rem' }}>Moat</th>
                    {COMPONENTS.map(({ key, label }) => (
                      <th key={key} style={{ textAlign: 'right', padding: '0.25rem 0.3rem', fontSize: '0.66rem' }}>{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Target row, anchored at top */}
                  <tr style={{ borderTop: '1px dashed var(--hairline, #333)', background: 'rgba(255,255,255,0.03)' }}>
                    <td style={{ padding: '0.32rem 0.4rem 0.32rem 0' }}>
                      <strong>{symbol}</strong> <span style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>(you)</span>
                    </td>
                    <td style={{ padding: '0.32rem 0.4rem', textAlign: 'right', color: labelColor(tm.label), fontWeight: 700 }}>
                      {tm.label} {tm.score.toFixed(0)}
                    </td>
                    {COMPONENTS.map(({ key }) => (
                      <td key={key} style={{ padding: '0.32rem 0.3rem', textAlign: 'right' }}>
                        {tm.components[key].score}
                      </td>
                    ))}
                  </tr>
                  {data.peers.map((p) => (
                    <tr key={p.symbol} style={{ borderTop: '1px dashed var(--hairline, #333)' }}>
                      <td style={{ padding: '0.32rem 0.4rem 0.32rem 0' }}>
                        <strong>{p.symbol}</strong>
                        {p.rating && <span style={{ marginLeft: 4, fontSize: '0.66rem', color: 'var(--cm-slate)' }}>{p.rating}</span>}
                        <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>{p.name.slice(0, 28)}</div>
                      </td>
                      <td style={{ padding: '0.32rem 0.4rem', textAlign: 'right', color: labelColor(p.moat.label), fontWeight: 700 }}>
                        {p.moat.label} {p.moat.score.toFixed(0)}
                      </td>
                      {COMPONENTS.map(({ key }) => {
                        const peerScore = p.moat.components[key].score;
                        const delta = p.deltas[key] ?? 0;
                        const tone = delta > 0 ? 'var(--positive, #10b981)' : delta < 0 ? 'var(--negative, #ef4444)' : 'var(--cm-slate)';
                        return (
                          <td key={key} style={{ padding: '0.32rem 0.3rem', textAlign: 'right' }}>
                            {peerScore}
                            <div style={{ fontSize: '0.6rem', color: tone }}>
                              {delta > 0 ? `+${delta}` : delta < 0 ? delta : '='}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <p style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: '0.9rem' }}>
              Tiers: ≥80 WIDE · ≥60 NARROW · ≥40 SOME · &lt;40 NONE. Per Buffett's "durable competitive advantage" framework, codified by Pat Dorsey (Morningstar).
            </p>
          </>
        )}
      </div>
    </div>
  );
}
