/* NewsReadButton — JIT "does the news make this more/less buyable?" verdict.
 *
 * On-demand ONLY: nothing fetches until the user clicks. Reads
 * /catalysts/news-read/<symbol> — last 72h of headlines classified into
 * more-buyable / mixed / less-buyable / sell-risk (LLM when available, else
 * keyword tone). Educational — a news-sentiment read, not advice.
 */
import { useState } from 'react';
import { API } from '../lib/apiBase';

type Headline = { title: string; url?: string | null; publisher?: string | null; when?: string | null; tone: string };
type NewsRead = {
  available: boolean;
  verdict: string;
  label: string;
  color: string;
  reason?: string;
  n: number;
  tone_counts?: { bullish: number; bearish: number; neutral: number };
  headlines?: Headline[];
  source?: string;
  as_of?: string;
  disclaimer?: string;
};

const COLOR_CLS: Record<string, string> = { green: 'nr--green', amber: 'nr--amber', red: 'nr--red', slate: 'nr--slate' };
const TONE_DOT: Record<string, string> = { bullish: '🟢', bearish: '🔴', neutral: '⚪' };

export function NewsReadButton({ symbol }: { symbol: string }) {
  const [data, setData] = useState<NewsRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(
        `${API}/catalysts/news-read/${encodeURIComponent(symbol)}${force ? '?force=true' : ''}`,
        { credentials: 'include' },
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  if (!data && !loading) {
    return (
      <div className="nr">
        <button className="nr__cta" onClick={() => load()}>
          📰 What’s the news say? <span className="nr__cta-sub">more buyable / less / sell — read it now</span>
        </button>
        {error && <p className="nr__err mono">Couldn’t read the news: {error}</p>}
      </div>
    );
  }

  return (
    <div className="nr">
      {loading && <div className="nr__loading mono">📰 Reading the last 72h of news…</div>}
      {data && !loading && (
        <>
          {data.available ? (
            <>
              <div className={`nr__verdict ${COLOR_CLS[data.color] || 'nr--slate'}`}>
                <span className="nr__verdict-label">{data.label}</span>
                {data.source === 'llm' && <span className="nr__src" title="Summarized by the local model">AI read</span>}
              </div>
              {data.reason && <p className="nr__reason">{data.reason}</p>}
              {data.tone_counts && (
                <div className="nr__tones mono">
                  🟢 {data.tone_counts.bullish} · 🔴 {data.tone_counts.bearish} · ⚪ {data.tone_counts.neutral} · {data.n} headlines
                </div>
              )}
              {data.headlines && data.headlines.length > 0 && (
                <ul className="nr__news">
                  {data.headlines.map((h, i) => (
                    <li key={i}>
                      <span className="nr__tone" aria-hidden>{TONE_DOT[h.tone] || '⚪'}</span>
                      {h.url ? (
                        <a href={h.url} target="_blank" rel="noreferrer">{h.title}</a>
                      ) : (
                        <span>{h.title}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <div className="nr__empty mono">{data.reason || 'No recent news.'}</div>
          )}
          <div className="nr__foot">
            <button className="nr__recheck" onClick={() => load(true)} disabled={loading}>↻ re-check</button>
            {data.disclaimer && <span className="nr__disc mono">{data.disclaimer}</span>}
          </div>
        </>
      )}
    </div>
  );
}
