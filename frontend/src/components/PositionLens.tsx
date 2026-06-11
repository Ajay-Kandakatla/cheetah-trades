import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

/* ==========================================================================
   PositionLens — "Hold or sell today?" verdict for an existing position.

   Different from the SEPA composite score (which is for new buyers). Reuses
   the backend's sell_signals.evaluate + stage classifier + trade_plan to
   answer "I bought at X, what should I do today?"

   Verdicts (from urgent → least): FULL_EXIT · REDUCE · TIGHTEN_STOP · HOLD

   Position is saved per-symbol in localStorage so the user doesn't have to
   re-enter entry/shares every time they open the page.
   ========================================================================== */

type LensTrigger = {
  rule:    string;
  verdict: 'FULL_EXIT' | 'REDUCE' | 'TIGHTEN_STOP' | 'HOLD';
  msg:     string;
};

type LensResponse = {
  ok:       boolean;
  reason?:  string;
  symbol?:  string;
  verdict?: 'FULL_EXIT' | 'REDUCE' | 'TIGHTEN_STOP' | 'HOLD';
  summary?: string;
  pnl?: {
    gain_pct: number;
    gain_per_share: number;
    shares?: number;
    basis_dollars?: number;
    current_value?: number;
    gain_dollars?: number;
  };
  r_multiple?: number | null;
  current?: {
    last_close: number;
    score: number;
    rating: string;
    stage: number;
    rs_rank: number;
    day_change_pct: number;
  };
  stop?: {
    used: number;
    source: string;
    distance_pct: number;
    distance_dollars: number;
    minervini_7pct: number;
    trade_plan_stop?: number | null;
  };
  targets?: { r1?: number | null; r2?: number | null; r3?: number | null };
  triggers?: LensTrigger[];
  actions?: string[];
  signals_panel?: {
    sepa_score?: number;
    sepa_rating?: string;
    stage?: number;
    stage_label?: string;
    rs_rank?: number;
    climax_15d_pct?: number;
    whales?:  { signal: string; n_buying: number; n_selling: number; top_sell?: string | null } | null;
    chaikin?: { score: number; label: string } | null;
    soir?:    { signal: string; soir?: number; percentile?: number | null } | null;
  };
};

const LS_KEY = (sym: string) => `pounce.position.${sym.toUpperCase()}`;

function loadPosition(symbol: string): { entry: string; shares: string; stop: string } {
  try {
    const raw = localStorage.getItem(LS_KEY(symbol));
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { entry: '', shares: '', stop: '' };
}
function savePosition(symbol: string, p: { entry: string; shares: string; stop: string }) {
  try { localStorage.setItem(LS_KEY(symbol), JSON.stringify(p)); }
  catch { /* quota — ignore */ }
}

const VERDICT_TONE: Record<string, { color: string; bg: string; label: string }> = {
  FULL_EXIT:    { color: 'var(--negative, #ef4444)', bg: 'rgba(239, 68, 68, 0.10)', label: '🚨 SELL FULL' },
  REDUCE:       { color: 'var(--warn, #d97706)',     bg: 'rgba(217, 119, 6, 0.10)', label: '⚠️ TRIM / REDUCE' },
  TIGHTEN_STOP: { color: 'var(--ink, #8a93a6)',      bg: 'rgba(107, 114, 128, 0.10)', label: '🔒 TIGHTEN STOP' },
  HOLD:         { color: 'var(--positive, #10b981)', bg: 'rgba(16, 185, 129, 0.10)', label: '✓ HOLD' },
};

export function PositionLens({ symbol }: { symbol: string }) {
  const [pos, setPos] = useState(() => loadPosition(symbol));
  const [data, setData] = useState<LensResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => { setPos(loadPosition(symbol)); }, [symbol]);
  useEffect(() => { savePosition(symbol, pos); }, [symbol, pos]);

  const evaluate = async () => {
    if (!pos.entry || Number(pos.entry) <= 0) return;
    setLoading(true);
    const params = new URLSearchParams({ entry: pos.entry });
    if (pos.shares) params.set('shares', pos.shares);
    if (pos.stop)   params.set('stop',   pos.stop);
    try {
      const r = await fetch(`${API}/sepa/position-lens/${encodeURIComponent(symbol)}?${params}`);
      setData(await r.json());
    } catch (e: any) {
      setData({ ok: false, reason: String(e?.message || e) });
    } finally {
      setLoading(false);
    }
  };

  // Auto-evaluate when an entry has been saved (so reopening the page
  // shows the verdict without an extra click).
  useEffect(() => {
    if (pos.entry && Number(pos.entry) > 0) { evaluate(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  const tone = data?.verdict ? VERDICT_TONE[data.verdict] : null;

  return (
    <div className="position-lens">
      <div className="position-lens__form">
        <Field label="Entry $" value={pos.entry}  onChange={(v) => setPos({ ...pos, entry: v })}  placeholder="666.59" />
        <Field label="Shares"  value={pos.shares} onChange={(v) => setPos({ ...pos, shares: v })} placeholder="45" />
        <Field label="Your stop $ (optional)" value={pos.stop} onChange={(v) => setPos({ ...pos, stop: v })} placeholder="auto" />
        <button className="sepa-btn sepa-btn--primary" onClick={evaluate} disabled={loading || !pos.entry}>
          {loading ? '…evaluating' : 'Evaluate'}
        </button>
      </div>

      {!data && !loading && (
        <p className="position-lens__hint mono">
          Enter your average entry price (and optionally share count + stop) →
          system tells you HOLD / TIGHTEN / REDUCE / SELL based on Minervini Ch.12-13 sell signals.
        </p>
      )}

      {data?.ok === false && (
        <div className="position-lens__error">
          {data.reason || 'Could not evaluate.'}
        </div>
      )}

      {data?.ok && tone && (
        <>
          <div className="position-lens__verdict" style={{ borderColor: tone.color, background: tone.bg }}>
            <div className="position-lens__verdict-tag" style={{ color: tone.color }}>{tone.label}</div>
            <div className="position-lens__summary">{data.summary}</div>
          </div>

          <div className="position-lens__grid">
            <Stat label="P&L %"      value={`${(data.pnl!.gain_pct >= 0 ? '+' : '')}${data.pnl!.gain_pct}%`}
                  tone={data.pnl!.gain_pct >= 0 ? 'good' : 'bad'} />
            {data.pnl?.gain_dollars != null && (
              <Stat label="P&L $"  value={`${data.pnl.gain_dollars >= 0 ? '+' : ''}$${data.pnl.gain_dollars.toLocaleString()}`}
                    tone={data.pnl.gain_dollars >= 0 ? 'good' : 'bad'} />
            )}
            {data.pnl?.current_value != null && (
              <Stat label="Position $" value={`$${data.pnl.current_value.toLocaleString()}`} />
            )}
            {data.r_multiple != null && (
              <Stat label="R-multiple" value={`${data.r_multiple >= 0 ? '+' : ''}${data.r_multiple}R`}
                    tone={data.r_multiple >= 1 ? 'good' : data.r_multiple < 0 ? 'bad' : 'neutral'} />
            )}
            <Stat label="Last close" value={`$${data.current!.last_close.toLocaleString()}`} />
            <Stat label="Stop"       value={`$${data.stop!.used.toLocaleString()}`}
                  sub={`-${data.stop!.distance_pct}% away · ${data.stop!.source}`} />
          </div>

          {/* All signals strip — keeps the SEPA card chips + supply/demand
              panel + options pulse + chart in lockstep with this verdict
              so the user doesn't perceive the dashboards as disconnected. */}
          {data.signals_panel && (
            <div className="position-lens__signals">
              <div className="eyebrow">All signals · how this verdict was formed</div>
              <div className="position-lens__signals-grid">
                <SignalCell
                  label="SEPA score"
                  value={data.signals_panel.sepa_score != null
                    ? `${Math.round(data.signals_panel.sepa_score)} ${data.signals_panel.sepa_rating ?? ''}`
                    : '—'}
                  tone={(() => {
                    const s = data.signals_panel.sepa_score ?? 0;
                    return s >= 70 ? 'good' : s >= 40 ? 'neutral' : 'bad';
                  })()}
                  hint="Buy-side conviction (for fresh entries, not holds)"
                />
                <SignalCell
                  label="Stage"
                  value={`S${data.signals_panel.stage ?? '?'} ${data.signals_panel.stage_label ?? ''}`}
                  tone={data.signals_panel.stage === 2 ? 'good'
                       : data.signals_panel.stage === 3 ? 'neutral'
                       : data.signals_panel.stage === 4 ? 'bad'
                       : 'neutral'}
                  hint="Weinstein 4-stage classification"
                />
                {data.signals_panel.climax_15d_pct != null && (
                  <SignalCell
                    label="15d gain"
                    value={`${data.signals_panel.climax_15d_pct >= 0 ? '+' : ''}${data.signals_panel.climax_15d_pct.toFixed(1)}%`}
                    tone={data.signals_panel.climax_15d_pct >= 25 ? 'bad'
                         : data.signals_panel.climax_15d_pct >= 15 ? 'neutral'
                         : 'good'}
                    hint=">25% in 15 days = climax run / parabolic blow-off"
                  />
                )}
                {data.signals_panel.whales && (
                  <SignalCell
                    label="🐋 Hedge funds"
                    value={data.signals_panel.whales.signal === 'distributing'
                      ? `Selling ${data.signals_panel.whales.n_selling}↓ vs ${data.signals_panel.whales.n_buying}↑`
                      : data.signals_panel.whales.signal === 'accumulating'
                      ? `Buying ${data.signals_panel.whales.n_buying}↑ vs ${data.signals_panel.whales.n_selling}↓`
                      : `Balanced ${data.signals_panel.whales.n_buying}↑/${data.signals_panel.whales.n_selling}↓`}
                    tone={data.signals_panel.whales.signal === 'accumulating' ? 'good'
                         : data.signals_panel.whales.signal === 'distributing' ? 'bad'
                         : 'neutral'}
                    hint="13F filings · 45-day lag · quarterly"
                  />
                )}
                {data.signals_panel.chaikin && (
                  <SignalCell
                    label="📈 Chaikin MF"
                    value={`${data.signals_panel.chaikin.score >= 0 ? '+' : ''}${data.signals_panel.chaikin.score.toFixed(0)}`}
                    sub={data.signals_panel.chaikin.label.toLowerCase()}
                    tone={data.signals_panel.chaikin.score >= 30 ? 'good'
                         : data.signals_panel.chaikin.score <= -30 ? 'bad'
                         : 'neutral'}
                    hint="10-day Chaikin Money Flow · technical, last 2 weeks"
                  />
                )}
                {data.signals_panel.soir && (
                  <SignalCell
                    label="📊 Options"
                    value={data.signals_panel.soir.signal}
                    sub={data.signals_panel.soir.soir != null
                      ? `SOIR ${data.signals_panel.soir.soir.toFixed(2)}`
                      : ''}
                    tone={data.signals_panel.soir.signal === 'BULLISH' ? 'good'
                         : data.signals_panel.soir.signal === 'BEARISH' ? 'bad'
                         : 'neutral'}
                    hint="Schaeffer's Open Interest Ratio (put/call)"
                  />
                )}
              </div>
            </div>
          )}

          {data.actions && data.actions.length > 0 && (
            <div className="position-lens__actions">
              <div className="eyebrow">Mechanical actions</div>
              <ol>
                {data.actions.map((a, i) => <li key={i}>{a}</li>)}
              </ol>
            </div>
          )}

          {data.triggers && data.triggers.length > 0 && (
            <div className="position-lens__triggers">
              <div className="eyebrow">Why this verdict</div>
              <ul>
                {data.triggers.map((t, i) => (
                  <li key={i}>
                    <span className="position-lens__trig-tag" style={{ color: VERDICT_TONE[t.verdict].color }}>
                      {t.verdict.replace('_', ' ')}
                    </span>
                    <span>{t.msg}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button className="position-lens__raw-btn mono" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? '▾ hide raw signals' : '▸ show raw sell-signal data'}
          </button>
          {showRaw && (
            <pre className="position-lens__raw mono">
{JSON.stringify((data as any).raw_sell_signals || {}, null, 2)}
            </pre>
          )}
        </>
      )}
    </div>
  );
}

function Field({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <label className="position-lens__field mono">
      <span>{label}</span>
      <input
        type="number"
        step="any"
        inputMode="decimal"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

/* SignalCell — compact tile for the cross-module "All signals" strip.
   Wraps each contributing signal in a uniform tile so the user sees they
   were all evaluated together (not in disconnected panels). */
function SignalCell({ label, value, sub, tone, hint }: {
  label: string; value: string; sub?: string;
  tone?: 'good' | 'bad' | 'neutral'; hint?: string;
}) {
  const color = tone === 'good' ? 'var(--positive, #10b981)'
              : tone === 'bad'  ? 'var(--negative, #ef4444)'
              : 'inherit';
  return (
    <div className="position-lens__signal-cell" title={hint || ''}>
      <div className="position-lens__signal-label">{label}</div>
      <div className="position-lens__signal-value mono" style={{ color }}>{value}</div>
      {sub && <div className="position-lens__signal-sub mono">{sub}</div>}
    </div>
  );
}

function Stat({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: 'good' | 'bad' | 'neutral'
}) {
  const color = tone === 'good' ? 'var(--positive, #10b981)'
              : tone === 'bad'  ? 'var(--negative, #ef4444)'
              : 'inherit';
  return (
    <div className="position-lens__stat">
      <div className="eyebrow">{label}</div>
      <div className="position-lens__stat-val mono" style={{ color }}>{value}</div>
      {sub && <div className="position-lens__stat-sub mono">{sub}</div>}
    </div>
  );
}
