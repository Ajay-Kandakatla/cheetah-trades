/* UniverseConvictionPanel — 🌐 full-universe Top-20 conviction scan on the
 * Scalping page (Ajay 2026-06-10: "full universe scan, doesn't have to follow
 * Minervini's SEPA… top 20 picks with strong conviction of the pattern and
 * other safer trend analysis, some fundamentals, a safety net… avoid
 * whale-manipulated stocks — good magnitude of volume").
 *
 * On-demand button → GET /scalping/conviction-scan. Cards show the score,
 * the drivers that earned it (pattern ✓, trend, $ volume, accumulation, EQ),
 * and the safety rails applied. Conviction = signal agreement, NOT a
 * probability — the disclaimer rides on the panel. */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280', gold: 'var(--gold,#c9a227)', blue: '#4fc3f7' };
const SHORT: Record<string, string> = {
  double_bottom: 'Double bottom', triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inv H&S', cup_with_handle: 'Cup w/ handle',
};

type Pick = {
  symbol: string; conviction: number; price?: number | null; rs_rank?: number | null;
  stage?: number | null; dollar_vol_m?: number; pattern?: string | null;
  pattern_status?: string | null; neckline?: number | null; target?: number | null;
  stop?: number | null; is_candidate?: boolean; is_buyable?: boolean;
  eq_score?: number | null; drivers: string[];
};
type Resp = {
  ok: boolean; reason?: string; generated_at: number; n_universe: number; n_screened: number;
  excluded?: Record<string, number>; picks: Pick[]; criteria?: string; disclaimer?: string;
};

export function UniverseConvictionPanel() {
  const navigate = useNavigate();
  const [data, setData] = useState<Resp | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);

  const scan = () => {
    setBusy(true);
    setErr(false);
    fetch(`${API}/scalping/conviction-scan?n=20`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch(() => setErr(true))
      .finally(() => setBusy(false));
  };

  const ex = data?.excluded || {};
  return (
    <section style={{ margin: '0.9rem 0', padding: '0.7rem 0.85rem', borderRadius: 12,
                      border: `1px solid ${C.blue}44`, background: 'var(--bg-raised,#16181d)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span className="eyebrow">🌐 Full universe · Top 20 by conviction</span>
        <button onClick={scan} disabled={busy}
                title="Score EVERY analyzed name (SEPA gate not required): pattern conviction + trend safety + volume magnitude + earnings quality, with hard safety rails. ~5–10s."
                style={{ fontSize: '0.74rem', fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
                         padding: '0.25rem 0.8rem', borderRadius: 7, border: 'none',
                         background: C.blue, color: '#0a1014', opacity: busy ? 0.6 : 1 }}>
          {busy ? 'Scanning the universe…' : '🌐 Scan full universe'}
        </button>
        {data?.ok && (
          <span style={{ fontSize: '0.68rem', color: C.sub }}>
            {data.n_screened} of {data.n_universe} pass the safety rails
            {ex.liquidity != null && <> · excluded: {ex.liquidity} thin tape, {ex.stage4 || 0} Stage 4, {ex.red_flag || 0} EQ red flag</>}
          </span>
        )}
      </div>
      {data?.criteria && <div style={{ fontSize: '0.66rem', color: C.sub, marginTop: 3 }}>{data.criteria}</div>}
      {err && <p className="mono" style={{ color: C.red, fontSize: '0.74rem' }}>Scan failed — retry.</p>}
      {data && !data.ok && <p className="mono" style={{ color: C.amber, fontSize: '0.74rem' }}>{data.reason}</p>}

      {data?.ok && data.picks.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(225px, 1fr))', gap: 7, marginTop: 8 }}>
          {data.picks.map((p, i) => (
            <div key={p.symbol} role="button" tabIndex={0}
                 onClick={() => navigate(`/sepa/${encodeURIComponent(p.symbol)}`)}
                 onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(`/sepa/${encodeURIComponent(p.symbol)}`); }}
                 title={p.drivers.join(' · ')}
                 style={{ padding: '0.5rem 0.6rem', borderRadius: 9, cursor: 'pointer',
                          background: 'var(--bg-sunken,#0f1115)',
                          border: `1px solid ${p.pattern_status === 'confirmed' ? C.green + '66' : 'var(--hairline,#2a2a2a)'}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: '0.66rem', color: C.sub, fontVariantNumeric: 'tabular-nums' }}>#{i + 1}</span>
                <b style={{ fontSize: '0.9rem' }}>{p.symbol}</b>
                {p.is_buyable ? <span style={{ fontSize: '0.6rem', color: C.green }}>✅</span>
                  : p.is_candidate ? <span style={{ fontSize: '0.6rem', color: C.muted }}>SEPA</span>
                  : <span style={{ fontSize: '0.6rem', color: C.sub }} title="Outside the SEPA gate — that's allowed here">non-SEPA</span>}
                <span style={{ marginLeft: 'auto', fontWeight: 800, color: C.blue, fontSize: '0.84rem' }}
                      title="Conviction = how many independent measured signals agree (0–100). A ranking device, not a probability.">
                  {p.conviction}
                </span>
              </div>
              <div style={{ fontSize: '0.66rem', color: C.muted, marginTop: 2 }}>
                ${p.price} · ${p.dollar_vol_m}M/day{p.rs_rank != null ? ` · RS ${p.rs_rank}` : ''}{p.stage != null ? ` · Stg ${p.stage}` : ''}{p.eq_score != null ? ` · EQ ${p.eq_score}` : ''}
              </div>
              {p.pattern && (
                <div style={{ fontSize: '0.68rem', marginTop: 2,
                              color: p.pattern_status === 'confirmed' ? C.green : C.amber, fontWeight: 600 }}>
                  📐 {SHORT[p.pattern] || p.pattern} {p.pattern_status === 'confirmed' ? '✓' : '(forming)'}
                  {p.target != null && <span style={{ color: C.sub, fontWeight: 400 }}> · line {p.neckline} → tgt {p.target} · stop {p.stop}</span>}
                </div>
              )}
              <div style={{ fontSize: '0.62rem', color: C.sub, marginTop: 3, lineHeight: 1.35 }}>
                {p.drivers.slice(0, 3).join(' · ')}
              </div>
            </div>
          ))}
        </div>
      )}
      {data?.disclaimer && <div style={{ fontSize: '0.62rem', color: C.sub, marginTop: 7 }}>{data.disclaimer}</div>}
    </section>
  );
}
