/* ChartAnalysisPanel — "🤖 Analyze chart" on the ticker page (Ajay
 * 2026-06-11: "I want on-demand analyze chart… what I am looking for is
 * buyable signals… maybe using sonnet").
 *
 * GET /sepa/analyze-chart/{symbol}: the backend gathers OUR system's facts
 * (pattern verdict, latest scan row, live Massive price, market gauge) and
 * Claude Sonnet synthesizes a verdict — BUY_NOW / BUY_ON_CLOSE_CONFIRM /
 * WAIT / PASS — with thesis, risks, and the exact facts it was given
 * (collapsible) so every number is checkable. Backend caches 10 min. */
import { useState } from 'react';
import { API } from '../lib/apiBase';
import { Collapsible } from './Collapsible';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#8a93a6' };

type Analysis = {
  verdict: 'BUY_NOW' | 'BUY_ON_CLOSE_CONFIRM' | 'WAIT' | 'PASS';
  confidence: 'low' | 'medium' | 'high';
  entry: number | null;
  stop: number | null;
  risk_pct: number | null;
  thesis: string[];
  risks: string[];
  what_would_change_it: string;
  citations?: string[];
};

type Resp = {
  ok: boolean;
  symbol?: string;
  analysis?: Analysis;
  facts?: Record<string, unknown>;
  model?: string;
  latency_sec?: number;
  from_cache?: boolean;
  error?: string;
  disclaimer?: string;
  citations?: string[];
};

const VERDICT_META: Record<Analysis['verdict'], { color: string; label: string }> = {
  BUY_NOW: { color: C.green, label: '🟢 BUYABLE NOW' },
  BUY_ON_CLOSE_CONFIRM: { color: C.amber, label: '🟡 BUY IF TODAY CLOSES ABOVE THE LINE' },
  WAIT: { color: C.muted, label: '⏸ WAIT — not there yet' },
  PASS: { color: C.red, label: '⛔ PASS' },
};

export function ChartAnalysisPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Resp | null>(null);
  const [busy, setBusy] = useState(false);

  const run = () => {
    setBusy(true);
    fetch(`${API}/sepa/analyze-chart/${encodeURIComponent(symbol)}`)
      .then((r) => r.json())
      .then((d: Resp) => setData(d))
      .catch(() => setData({ ok: false, error: 'request failed' }))
      .finally(() => setBusy(false));
  };

  const a = data?.ok ? data.analysis : undefined;
  const meta = a ? VERDICT_META[a.verdict] : null;
  // Book citations from the Minervini brain (when the backend grounds the
  // verdict in retrieved pages). Strings rendered verbatim, e.g.
  // "TLSW p.214", "TTLAC §7 (ebook p.98)". Absent → no row.
  const cites = (data?.citations ?? a?.citations ?? []).filter(
    (c): c is string => typeof c === 'string' && c.length > 0,
  );

  return (
    <section className="top-picks" style={{ marginTop: 12 }}>
      <div className="top-picks__head">
        <span className="eyebrow">🤖 AI chart analysis — buyable signal</span>
        <button
          type="button"
          onClick={run}
          disabled={busy}
          className="mono"
          style={{ fontSize: '0.74rem', padding: '6px 14px', borderRadius: 6, minHeight: 32,
                   cursor: busy ? 'wait' : 'pointer', background: 'transparent', color: 'inherit',
                   border: '1px solid var(--gold,#c9a227)' }}
          title="Claude Sonnet synthesizes the scanner's facts (pattern verdict, SEPA gates, live price, market gauge) into a buy decision. ~5-15s, cached 10 min."
        >
          {busy ? '…analyzing' : data ? '↻ Re-analyze' : `Analyze ${symbol}`}
        </button>
      </div>

      {!data && !busy && (
        <p style={{ color: C.sub, fontSize: '0.8rem' }}>
          One press: the pattern verdict, SEPA gates, live price and market regime go to
          Claude Sonnet for a single answer — is this buyable right now, by the book?
        </p>
      )}
      {busy && <p className="mono" style={{ opacity: 0.7, fontSize: '0.8rem' }}>…gathering facts + asking Sonnet (~5–15s)</p>}

      {data && !data.ok && (
        <p className="mono" style={{ color: C.red, fontSize: '0.8rem' }}>
          Analysis failed — {data.error || 'unknown error'}
        </p>
      )}

      {a && meta && (
        <div style={{ border: `1px solid ${meta.color}44`, background: `${meta.color}0d`,
                      borderRadius: 10, padding: '0.7rem 0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <strong style={{ color: meta.color, fontSize: '0.95rem' }}>{meta.label}</strong>
            <span className="mono" style={{ fontSize: '0.72rem', color: C.sub }}>
              confidence {a.confidence}
            </span>
            {(a.entry != null || a.stop != null) && (
              <span className="mono" style={{ fontSize: '0.78rem' }}>
                {a.entry != null && <>entry <b>${a.entry}</b></>}
                {a.stop != null && <> · stop <b style={{ color: C.red }}>${a.stop}</b></>}
                {a.risk_pct != null && <> · risk {a.risk_pct}%</>}
              </span>
            )}
          </div>

          {cites.length > 0 && (
            <div className="mono" style={{ fontSize: '0.7rem', color: C.sub, marginTop: 4 }}>
              per {cites.join(' · ')}
            </div>
          )}

          {a.thesis.length > 0 && (
            <ul style={{ margin: '8px 0 0', paddingLeft: '1.1rem', fontSize: '0.8rem', lineHeight: 1.5 }}>
              {a.thesis.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
          )}

          {a.risks.length > 0 && (
            <div style={{ marginTop: 8, fontSize: '0.76rem' }}>
              <span style={{ color: C.red, fontWeight: 600 }}>Risks: </span>
              {a.risks.join(' · ')}
            </div>
          )}

          {a.what_would_change_it && (
            <div style={{ marginTop: 6, fontSize: '0.76rem', color: C.muted }}>
              <b>Changes the call:</b> {a.what_would_change_it}
            </div>
          )}

          <div style={{ marginTop: 10 }}>
            <Collapsible label="the exact facts the model was given">
              <pre className="mono" style={{ fontSize: '0.68rem', whiteSpace: 'pre-wrap',
                                             background: 'var(--bg-sunken,#0f1115)', borderRadius: 8,
                                             padding: '0.6rem', maxHeight: 320, overflow: 'auto' }}>
                {JSON.stringify(data?.facts ?? {}, null, 1)}
              </pre>
            </Collapsible>
          </div>

          <p className="mono" style={{ fontSize: '0.7rem', color: C.sub, marginTop: 8, marginBottom: 0 }}>
            {data?.model}{data?.latency_sec != null ? ` · ${data.latency_sec}s` : ''}
            {data?.from_cache ? ' · cached' : ''} — {data?.disclaimer ||
              'AI synthesis of our scanner facts. Confirmation is the CLOSE. Not advice.'}
          </p>
        </div>
      )}
    </section>
  );
}
