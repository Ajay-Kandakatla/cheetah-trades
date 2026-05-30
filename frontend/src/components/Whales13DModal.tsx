/* Whales13DModal — recent SEC filings of interest for one ticker.
 *
 * Triggered by the "📋 SEC activity" chip on SepaCandidateCard. Sections:
 *   - 4   / 4-A   — insider trades (2-day lag, fires constantly)
 *   - 144         — insider pre-sale notice (planned restricted sale)
 *   - SC 13D/G    — fund crossed 5% ownership (rare, high-signal)
 *
 * Filer name and trade details live on the cover page of each filing;
 * the modal renders deep links to SEC.gov so the user can verify.
 * Cover-page parse for inline display is a v2 work item.
 *
 * History: started 2026-05-29 as a 13D/G-only chip. Widened later the
 * same day after SEPA's liquid universe yielded ~0 13D hits across
 * 150 candidates — Form 4/144 is the actual real-time-ish signal here.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';

type Bucket = 'form4' | 'form144' | 'form13' | null;

type Filing = {
  form:              string;
  filing_date:       string;
  accession_number:  string;
  primary_doc_url:   string | null;
  primary_doc_desc?: string | null;
  bucket?:           Bucket;
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
  n_form4?:      number;
  n_form144?:    number;
  n_form13?:     number;
  source?:       string;
  disclaimer?:   string;
  error?:        string;
};

function fmtForm(f: string): { emoji: string; tone: 'new' | 'amend' | 'insider' | 'notice'; label: string } {
  const isAmend = f.endsWith('/A');
  if (f === '4' || f === '4/A') {
    return { emoji: '👤', tone: 'insider', label: 'Form 4 (insider trade)' + (isAmend ? ' · amend' : '') };
  }
  if (f === '144') {
    return { emoji: '📤', tone: 'notice', label: 'Form 144 (pre-sale notice)' };
  }
  if (f.startsWith('SC 13D')) {
    return { emoji: '📜', tone: isAmend ? 'amend' : 'new', label: f };
  }
  if (f.startsWith('SC 13G')) {
    return { emoji: '📑', tone: isAmend ? 'amend' : 'new', label: f };
  }
  return { emoji: '📄', tone: 'new', label: f };
}

const BUCKET_HEADERS: Record<Exclude<Bucket, null>, { emoji: string; title: string; subtitle: string }> = {
  form4: {
    emoji: '👤',
    title: 'Insider trades · Form 4',
    subtitle: 'Officers, directors, and 10%+ owners filing within 2 business days of a transaction.',
  },
  form144: {
    emoji: '📤',
    title: 'Insider pre-sale notice · Form 144',
    subtitle: 'Planned sale of restricted stock — supply-side warning, not an executed trade.',
  },
  form13: {
    emoji: '📜',
    title: '5% ownership threshold · SC 13D / 13G',
    subtitle: 'Outside fund crossed 5% ownership. Rare but high-signal (activist plays, anchors).',
  },
};

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
            <div className="eyebrow">📋 SEC activity · insider trades + 5% threshold</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>
              {symbol}
              <span style={{ fontSize: '0.78rem', marginLeft: '0.5rem', color: 'var(--cm-slate)' }}>
                {n} filing{n === 1 ? '' : 's'} · last {data?.window_days ?? windowDays} days
              </span>
            </h2>
            {n > 0 && (
              <p style={{ fontSize: '0.74rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0', opacity: 0.9, fontFamily: '"SF Mono", Menlo, monospace' }}>
                {(data?.n_form4   ?? 0)} Form 4 · {(data?.n_form144 ?? 0)} Form 144 · {(data?.n_form13 ?? 0)} SC 13D/G
              </p>
            )}
            <p style={{ fontSize: '0.74rem', color: 'var(--cm-slate)', margin: '0.25rem 0 0', opacity: 0.75 }}>
              Real-time-ish institutional + insider tape from SEC EDGAR.
              Click any row for the full filing on SEC.gov.
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
            No tracked SEC filings (Form 4 / 144 / 13D / 13G) in the last {data.window_days ?? windowDays} days.
          </div>
        )}

        {n > 0 && (['form13', 'form4', 'form144'] as const).map((bucketKey) => {
          const bucketFilings = filings.filter((f) => f.bucket === bucketKey);
          if (bucketFilings.length === 0) return null;
          const header = BUCKET_HEADERS[bucketKey];
          return (
            <section key={bucketKey} style={{ marginTop: '0.9rem' }}>
              <div style={{ marginBottom: '0.35rem' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, letterSpacing: '0.02em' }}>
                  {header.emoji} {header.title}
                  <span style={{ marginLeft: 6, color: 'var(--cm-slate)', fontWeight: 400 }}>
                    ({bucketFilings.length})
                  </span>
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 1, opacity: 0.85 }}>
                  {header.subtitle}
                </div>
              </div>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.35rem' }}>
                {bucketFilings.map((f, i) => {
                  const meta = fmtForm(f.form);
                  const tone = bucketKey === 'form13' ? 'good' : 'neutral';
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
                        padding: '0.45rem 0.6rem',
                        background: bg,
                        border: `1px solid ${border}`,
                        borderRadius: 5,
                        fontSize: '0.82rem',
                        minWidth: 0,
                      }}
                    >
                      <span style={{ fontFamily: '"SF Mono", Menlo, monospace', fontSize: '0.76rem', color: 'var(--cm-slate)' }}>
                        {f.filing_date}
                      </span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
                        {meta.emoji} <strong>{meta.label}</strong>
                        {f.filer_name && <span style={{ marginLeft: 8 }}>· {f.filer_name}</span>}
                        {f.pct_owned != null && (
                          <span style={{ marginLeft: 8, fontFamily: '"SF Mono", Menlo, monospace' }}>
                            · {(f.pct_owned * 100).toFixed(1)}%
                          </span>
                        )}
                        {f.primary_doc_desc && (
                          <div style={{ color: 'var(--cm-slate)', fontSize: '0.68rem', marginTop: 1 }}>
                            {f.primary_doc_desc}
                          </div>
                        )}
                      </span>
                      {f.primary_doc_url && (
                        <a
                          href={f.primary_doc_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'var(--cm-mint, #6ee7b7)', fontSize: '0.74rem', textDecoration: 'none' }}
                        >
                          SEC.gov ↗
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}

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
