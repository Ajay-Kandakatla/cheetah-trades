/* MacroContextModal — per-ticker macro brief.
 *
 * Opens when the user taps the 🌍 chip on a SEPA candidate card.
 * Fetches /macro/{symbol} which returns:
 *   1. A Claude-generated markdown brief covering geopolitics,
 *      futures/commodities tied to the stock, bear case, sector.
 *   2. A handful of recent news headlines from Finnhub (best-effort).
 *
 * Cached 6h server-side, so spam-clicking the chip is free after the
 * first hit. A "↻ refresh" button force-bypasses the cache for users
 * who want a fresh read after a major news event.
 *
 * Markdown rendering is intentionally minimal — no third-party
 * library. We just convert headings, paragraphs, and bullet lists
 * inline. Keeps the bundle slim and we control the look.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';

type Headline = {
  title:        string;
  url?:         string | null;
  source?:      string | null;
  published_at?: number | string | null;
};

type Payload = {
  ok?:           boolean;
  symbol?:       string;
  analysis?:     string;        // markdown
  headlines?:    Headline[];
  provider?:     string;
  model?:        string | null;
  generated_at?: number;
  ttl_at?:       number;
  from_cache?:   boolean;
  error?:        string;
};

/** Minimal markdown → JSX. Handles:
 *    ## heading      → <h3>
 *    - bullet        → <li>
 *    blank line      → paragraph break
 *    **bold**        → <strong>
 *
 *  Anything more elaborate (code blocks, tables) we don't expect from
 *  the Claude prompt. If we ever do, swap to react-markdown. */
function MarkdownLite({ text }: { text: string }) {
  if (!text) return null;
  const lines = text.split('\n');
  const nodes: any[] = [];
  let listBuffer: string[] = [];

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return;
    nodes.push(
      <ul key={`ul-${key}`} style={{ margin: '0.3rem 0 0.6rem', paddingLeft: '1.2rem', display: 'grid', gap: '0.25rem' }}>
        {listBuffer.map((b, i) => (
          <li key={i} style={{ lineHeight: 1.55 }}>{inlineFmt(b)}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  let paraBuffer: string[] = [];
  const flushPara = (key: string) => {
    if (paraBuffer.length === 0) return;
    const text = paraBuffer.join(' ').trim();
    if (text) {
      nodes.push(
        <p key={`p-${key}`} style={{ margin: '0.3rem 0 0.6rem', lineHeight: 1.55 }}>{inlineFmt(text)}</p>,
      );
    }
    paraBuffer = [];
  };

  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (line.startsWith('## ')) {
      flushList(`h-${i}`);
      flushPara(`h-${i}`);
      nodes.push(
        <h3 key={`h-${i}`} style={{
          fontSize: '0.92rem',
          fontWeight: 700,
          color: 'var(--gold, #d4af37)',
          margin: '1rem 0 0.3rem',
          letterSpacing: '0.01em',
        }}>
          {line.replace(/^##\s*/, '')}
        </h3>,
      );
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      flushPara(`l-${i}`);
      listBuffer.push(line.replace(/^[-*]\s*/, ''));
    } else if (line === '') {
      flushList(`b-${i}`);
      flushPara(`b-${i}`);
    } else {
      flushList(`p-${i}`);
      paraBuffer.push(line);
    }
  });
  flushList('end');
  flushPara('end');
  return <>{nodes}</>;
}

/** **bold** → <strong>. Nothing fancy — escapes ignored. */
function inlineFmt(s: string): any {
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    /^\*\*(.+)\*\*$/.test(p)
      ? <strong key={i}>{p.replace(/\*\*/g, '')}</strong>
      : <span key={i}>{p}</span>,
  );
}

function fmtAge(epoch: number | undefined | null): string {
  if (!epoch) return '';
  const ageSec = Date.now() / 1000 - epoch;
  if (ageSec < 60) return 'just now';
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m ago`;
  if (ageSec < 86400) return `${Math.floor(ageSec / 3600)}h ago`;
  return `${Math.floor(ageSec / 86400)}d ago`;
}

export function MacroContextModal({
  symbol,
  onClose,
}: {
  symbol: string;
  onClose: () => void;
}) {
  const [data,    setData]    = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [err,     setErr]     = useState<string | null>(null);

  const load = async (force = false) => {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch(`${API}/macro/${encodeURIComponent(symbol)}${force ? '?force=true' : ''}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: Payload = await r.json();
      if (!j.ok) throw new Error(j.error || 'failed');
      setData(j);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(false); /* eslint-disable-next-line */ }, [symbol]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

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
          // Wider than WhalesFlowModal — the markdown analysis reads
          // better at ~840px column width. Caps at viewport width
          // minus 2rem so phones don't overflow.
          width: '100%',
          maxWidth: 'min(840px, calc(100vw - 2rem))',
          maxHeight: '92vh', overflow: 'auto',
          padding: '1.1rem clamp(0.9rem, 3vw, 1.4rem)',
          minWidth: 0,
        }}
      >
        <header style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'baseline', marginBottom: '0.6rem', gap: '0.4rem', flexWrap: 'wrap',
        }}>
          <div>
            <div className="eyebrow">🌍 Macro context</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>
              {symbol}
              <span style={{ color: 'var(--cm-slate)', fontSize: '0.7rem', marginLeft: '0.5rem', fontStyle: 'italic' }}>
                geopolitics · futures · bear case
              </span>
            </h2>
            {data && (
              <p style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0' }}>
                {data.from_cache ? '📦 cached' : '🆕 fresh'}
                {data.generated_at && ` · ${fmtAge(data.generated_at)}`}
                {data.model && ` · ${data.model}`}
                {data.provider && data.provider !== 'anthropic' && data.provider !== 'local' && (
                  <span style={{ color: 'var(--warn, #d97706)' }}> · {data.provider}</span>
                )}
              </p>
            )}
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <button
              onClick={() => load(true)}
              disabled={loading}
              aria-busy={loading}
              style={{
                background: 'none', border: '1px solid var(--rule, #555)',
                color: 'var(--cm-slate)', padding: '4px 10px', borderRadius: 3,
                cursor: 'pointer', fontSize: '0.72rem',
              }}
              title="Bypass the 6h cache and regenerate. Costs a Claude call (~$0.01)."
            >
              {loading ? '…refreshing' : '↻ refresh'}
            </button>
            <button
              onClick={onClose}
              aria-label="Close"
              style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}
            >×</button>
          </div>
        </header>

        {loading && !data && (
          <div style={{ color: 'var(--cm-slate)', padding: '1.5rem 0' }}>
            Generating macro brief… (Claude usually takes 5–10s)
          </div>
        )}

        {err && (
          <div style={{
            padding: '0.5rem 0.7rem', marginTop: '0.4rem',
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 4, color: 'var(--negative)', fontSize: '0.85rem',
          }}>
            Failed to load macro brief: {err}
            <button
              onClick={() => load(false)}
              style={{
                marginLeft: '0.5rem',
                background: 'none', border: '1px solid currentColor',
                color: 'inherit', padding: '1px 6px', borderRadius: 3,
                cursor: 'pointer', fontSize: '0.74rem',
              }}
            >retry</button>
          </div>
        )}

        {data?.analysis && (
          <div style={{ fontSize: '0.88rem' }}>
            <MarkdownLite text={data.analysis} />
          </div>
        )}

        {data && data.analysis === '' && (
          <p style={{
            padding: '0.6rem 0.8rem',
            background: 'rgba(212,175,55,0.06)',
            border: '1px solid rgba(212,175,55,0.3)',
            borderRadius: 4,
            color: 'var(--warn, #d97706)',
            fontSize: '0.84rem',
            margin: '0.4rem 0 0.8rem',
          }}>
            ⚠ Macro brief unavailable — Claude API may not be configured.
            Check <code>ANTHROPIC_LLM_API_KEY</code> in backend/.env. News
            headlines below still work.
          </p>
        )}

        {/* News headlines section — separate from the AI analysis so
            the user can see real-time signal even if Claude is down
            or returns a stale read. Pulled from Finnhub via the
            existing news module. */}
        {data?.headlines && data.headlines.length > 0 && (
          <section style={{ marginTop: '1.4rem' }}>
            <h3 style={{
              fontSize: '0.92rem', fontWeight: 700,
              color: 'var(--gold, #d4af37)',
              margin: '0 0 0.4rem', letterSpacing: '0.01em',
            }}>
              📰 Recent headlines
            </h3>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.35rem' }}>
              {data.headlines.map((h, i) => (
                <li
                  key={i}
                  style={{
                    padding: '0.45rem 0.6rem',
                    background: 'rgba(255,255,255,0.025)',
                    border: '1px solid var(--rule, #333)',
                    borderRadius: 4,
                    fontSize: '0.82rem',
                  }}
                >
                  {h.url ? (
                    <a href={h.url} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
                      <div style={{ lineHeight: 1.4 }}>{h.title}</div>
                      <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: 2 }}>
                        {h.source}
                        {h.published_at && (
                          <> · {typeof h.published_at === 'number'
                            ? new Date(h.published_at * 1000).toLocaleDateString()
                            : new Date(h.published_at).toLocaleDateString()}</>
                        )}
                      </div>
                    </a>
                  ) : (
                    <div>{h.title}</div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        <p style={{
          fontSize: '0.66rem', color: 'var(--cm-slate)',
          marginTop: '1.2rem', lineHeight: 1.55,
        }}>
          <strong>How this is generated:</strong> Claude synthesizes the macro brief from its training
          knowledge of this company (sector, suppliers, customers, competitors, regulatory exposure).
          Headlines are live from Finnhub. Cached 6h so repeat opens are free.
          <br />
          <strong>Caveat:</strong> Claude's training has a knowledge cutoff. For breaking events use
          the headlines section as ground truth, then re-open this card after the cache expires for
          updated synthesis.
        </p>
      </div>
    </div>,
    document.body,
  );
}
