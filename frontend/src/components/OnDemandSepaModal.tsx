import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API = (import.meta as any).env?.VITE_API_BASE ?? '';

type Phase = 'pending' | 'running' | 'done' | 'error';
type Step = { key: string; label: string; phase: Phase };

type Props = {
  symbol: string;
  name?: string;
  onClose: () => void;
};

/**
 * OnDemandSepaModal — runs the SEPA pipeline on a single ticker that may
 * not be in the curated universe. Shows a phase progress list while the
 * backend works (the actual analysis is one POST, but we surface phases
 * so users see something happening for the 5-15s round-trip).
 */
export function OnDemandSepaModal({ symbol, name, onClose }: Props) {
  const navigate = useNavigate();
  const [steps, setSteps] = useState<Step[]>([
    { key: 'prices',   label: 'Pulling 2-year price history', phase: 'pending' },
    { key: 'rs',       label: 'Computing RS rank vs universe', phase: 'pending' },
    { key: 'analyze',  label: 'Trend Template / Stage / VCP / Power Play / fundamentals', phase: 'pending' },
    { key: 'enrich',   label: 'Enriching with catalyst + insider data', phase: 'pending' },
  ]);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const setStepPhase = (key: string, phase: Phase) =>
    setSteps((prev) => prev.map((s) => s.key === key ? { ...s, phase } : s));

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // The backend runs all phases in one POST, but we update the UI in
        // a staggered way so there's visual progress during the wait.
        setStepPhase('prices', 'running');
        const url = `${API}/sepa/analyze/${encodeURIComponent(symbol)}?with_catalyst=true`;
        const promise = fetch(url, { method: 'POST' });

        // Visual pacing — these don't represent real wall-clock phases,
        // they signal that the request is in flight and which sub-step
        // is "likely" running.
        await new Promise((r) => setTimeout(r, 600));
        if (cancelled) return;
        setStepPhase('prices', 'done');
        setStepPhase('rs', 'running');

        await new Promise((r) => setTimeout(r, 800));
        if (cancelled) return;
        setStepPhase('rs', 'done');
        setStepPhase('analyze', 'running');

        const r = await promise;
        if (cancelled) return;
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          throw new Error(j.error || `HTTP ${r.status}`);
        }
        const data = await r.json();
        setStepPhase('analyze', 'done');
        setStepPhase('enrich', 'done');
        setResult(data);
      } catch (e: any) {
        if (cancelled) return;
        setError(String(e?.message || e));
        setSteps((prev) => prev.map((s) => s.phase === 'running' ? { ...s, phase: 'error' } : s));
      }
    })();
    return () => { cancelled = true; };
  }, [symbol]);

  return (
    <div className="sepa-on-demand" role="dialog" aria-modal="true">
      <div className="sepa-on-demand__card">
        <div className="sepa-on-demand__head">
          <h3>
            On-demand SEPA — <span className="ticker">{symbol}</span>
            {name && <span className="muted small"> · {name}</span>}
          </h3>
          <button className="sepa-on-demand__close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="sepa-on-demand__phases">
          {steps.map((s) => (
            <div key={s.key} className={`sepa-on-demand__phase is-${s.phase}`}>
              <span className="dot" />
              <span>{s.label}</span>
            </div>
          ))}
        </div>

        {error && (
          <div className="sepa-on-demand__verdict" style={{ borderLeftColor: '#ef4444', color: '#fecaca' }}>
            <strong>Failed:</strong> {error}
          </div>
        )}

        {result && (
          <div className="sepa-on-demand__verdict">
            <div className="eyebrow">Verdict</div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'baseline', marginTop: 4 }}>
              <strong style={{ fontSize: '1.4rem' }}>{Math.round(result.score ?? 0)}</strong>
              <span className="muted">composite score</span>
              <span style={{ marginLeft: 'auto' }} className="mono">
                {result.rating ?? '—'}
              </span>
            </div>
            <div style={{ marginTop: 8, fontSize: '0.85rem', display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              <span>RS <strong>{result.rs_rank ?? '—'}</strong></span>
              <span>Trend <strong>{result.trend?.passed ?? '—'}/8</strong></span>
              <span>Stage <strong>{result.stage?.stage ?? '—'}</strong></span>
              {result.entry_setup && (
                <span>Setup <strong>{result.entry_setup.type}</strong> @ {result.entry_setup.pivot}</span>
              )}
              <span>{result.is_candidate ? '✅ candidate' : '— not a candidate'}</span>
            </div>
          </div>
        )}

        <div className="sepa-on-demand__actions">
          <button className="cm-live__add" onClick={onClose}>Close</button>
          {result && (
            <button
              className="cm-live__add"
              onClick={() => navigate(`/sepa/${encodeURIComponent(symbol)}`)}
              style={{ background: '#fbbf24', color: '#0b0d12' }}
            >
              View full detail →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
