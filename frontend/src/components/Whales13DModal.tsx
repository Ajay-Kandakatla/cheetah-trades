/* Whales13DModal — list of recent SC 13D / 13G filings for one ticker.
 *
 * Triggered by the "📜 13D" chip on SepaCandidateCard. Renders a compact
 * table of every filing in the lookback window: date · form · accession
 * number · deep link to the cover page on SEC.gov.
 *
 * Filer name and exact % owned aren't surfaced in v1 — those require
 * cover-page parsing which is in the v2 backlog. The deep link is the
 * fallback: one click and the user sees the full filing.
 *
 * Data lag: 13D/G must be filed within 10 days of crossing 5% ownership.
 * That's the "real-time-ish" signal — way fresher than 13F's 45-day lag.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';

type Filing = {
  form:              string;
  filing_date:       string;
  accession_number:  string;
  primary_doc_url:   string | null;
  primary_doc_desc?: string | null;
  filer_name?:       string | null;
  pct_owned?:        number | null;
};

type Payload = {
  ticker?:       string;
  cik?:          string | null;
  as_of?:        string | null;
  window_days?:  number;
  filings?:      Filing[];
  n_filings?:    number;
  source?:       string;
  disclaimer?:   string;
  error?:        string;
};

function fmtForm(f: string): { emoji: string; tone: 'new' | 'amend'; label: string } {
  const isAmend = f.endsWith('/A');
  const is13D = f.startsWith('SC 13D');
  return {
    emoji: is13D ? '📜' : '📑',
    tone: isAmend ? 'amend' : 'new',
    label: f,
  };
}

type Props = { symbol: string; onClose: () => void; windowDays?: number };

export function Whales13DModal({ symbol, onClose, windowDays = 120 }: Props) {
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null); setErr(null);
    fetch(`${API}/supply-demand/whales/${encodeURIComponent(symbol)}/13d?days=${windowDays}`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((j: Payload) => { if (alive) setData(j); })
      .catch((e) => { if (alive) setErr(String(e?.message || e)); });
    return () => { alive = false; };
  }, [symbol, windowDays]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const filings = data?.filings || [];
  const n = filings.length;

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '1rem', overflowY: 'auto',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
          border: '1px solid var(--rule, #333)', borderRadius: 8,
          width: '100%',
          maxWidth: 'min(720px, calc(100vw - 2rem))',
          maxHeight: '90vh', overflow: 'auto',
          padding: '1.1rem clamp(0.8rem, 3vw, 1.3rem)',
          minWidth: 0,
        }}
      >
        <header style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'baseline', marginBottom: '0.6rem', gap: '0.4rem', flexWrap: 'wrap',
        }}>
          <div>
            <div className="eyebrow">📜 SEC 13D / 13G filings · 5% ownership threshold</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>
              {symbol}
              <span style={{ fontSize: '0.78rem', marginLeft: '0.5rem', color: 'var(--cm-slate)' }}>
                {n} filing{n === 1 ? '' : 's'} · last {data?.window_days ?? windowDays} days
              </span>
            </h2>
            <p style={{ fontSize: '0.74rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0', opacity: 0.85 }}>
              Filed within 10 days of a fund crossing 5% ownership — closest free
              real-time-ish institutional signal. Click a row for the full cover page.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none', border: 0, color: 'var(--cm-slate)',
              cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1,
            }}
          >×</button>
        </header>

        {err && (
          <div style={{ padding: '0.8rem', color: 'var(--cm-rose, #f87171)', fontSize: '0.85rem' }}>
            Failed to load: {err}
          </div>
        )}

        {data?.error && (
          <div style={{ padding: '0.8rem', color: 'var(--cm-slate)', fontSize: '0.85rem' }}>
            {data.error}
          </div>
        )}

        {!err && data && n === 0 && (
          <div style={{ padding: '0.9rem 0', color: 'var(--cm-slate)', fontSize: '0.88rem' }}>
            No 13D/13G filings in the last {data.window_days ?? windowDays} days.
          </div>
        )}

        {n > 0 && (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.45rem' }}>
            {filings.map((f, i) => {
              const meta = fmtForm(f.form);
              const tone = meta.tone === 'new' ? 'good' : 'neutral';
              const bg = tone === 'good' ? 'rgba(16,185,129,0.06)' : 'rgba(148,163,184,0.06)';
              const border = tone === 'good' ? 'rgba(16,185,129,0.22)' : 'rgba(148,163,184,0.22)';
              return (
                <li
                  key={`${f.accession_number}-${i}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'auto 1fr auto',
                    columnGap: '0.6rem',
                    alignItems: 'baseline',
                    padding: '0.5rem 0.6rem',
                    background: bg,
                    border: `1px solid ${border}`,
                    borderRadius: 5,
                    fontSize: '0.84rem',
                    minWidth: 0,
                  }}
                >
                  <span style={{ fontFamily: '"SF Mono", Menlo, monospace', fontSize: '0.78rem', color: 'var(--cm-slate)' }}>
                    {f.filing_date}
                  </span>
                  <span style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    minWidth: 0,
                  }}>
                    {meta.emoji} <strong>{meta.label}</strong>
                    {meta.tone === 'amend' && (
                      <span style={{ marginLeft: 6, color: 'var(--cm-slate)', fontSize: '0.74rem' }}>
                        (amendment)
                      </span>
                    )}
                    {f.filer_name && (
                      <span style={{ marginLeft: 8 }}>· {f.filer_name}</span>
                    )}
                    {f.pct_owned != null && (
                      <span style={{ marginLeft: 8, fontFamily: '"SF Mono", Menlo, monospace' }}>
                        · {(f.pct_owned * 100).toFixed(1)}%
                      </span>
                    )}
                    <div style={{ color: 'var(--cm-slate)', fontSize: '0.7rem', marginTop: 1 }}>
                      Accession: {f.accession_number}
                      {f.primary_doc_desc ? ` · ${f.primary_doc_desc}` : ''}
                    </div>
                  </span>
                  {f.primary_doc_url && (
                    <a
                      href={f.primary_doc_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: 'var(--cm-mint, #6ee7b7)',
                        fontSize: '0.76rem',
                        textDecoration: 'none',
                      }}
                    >
                      SEC.gov ↗
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        <footer style={{
          marginTop: '0.9rem',
          paddingTop: '0.7rem',
          borderTop: '1px dashed var(--rule, #333)',
          fontSize: '0.7rem',
          color: 'var(--cm-slate)',
          lineHeight: 1.45,
        }}>
          <p style={{ margin: 0 }}>
            <strong>What this is:</strong> {data?.disclaimer || 'SC 13D/G — required SEC filings within 10 days of crossing 5% beneficial ownership of a class of shares. Source: SEC EDGAR.'}
          </p>
          <p style={{ margin: '0.4rem 0 0' }}>
            <strong>Filer name + % owned</strong> are on the linked cover page.
            v1 surfaces only filing metadata; cover-page parse is on the roadmap.
          </p>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
