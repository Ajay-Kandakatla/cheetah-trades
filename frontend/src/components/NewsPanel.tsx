import { useCallback, useEffect, useMemo, useState } from 'react';
import type { NewsItem, NewsResponse } from '../types';

const WATCH = ['Market', 'NVDA', 'CRDO', 'PLTR', 'META', 'LLY', 'ALAB', 'AVGO', 'MRVL'];

function relativeTime(ts: number | null | undefined): string {
  if (!ts) return '';
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

/** Real-time news aggregator powered by backend /news scraper. */
export function NewsPanel() {
  const [selected, setSelected] = useState('Market');
  const [items, setItems] = useState<NewsItem[]>([]);
  const [fetchedAt, setFetchedAt] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const url = useMemo(
    () => (selected === 'Market' ? '/news' : `/news?symbol=${selected}`),
    [selected]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data: NewsResponse = await r.json();
      setItems(data.items || []);
      setFetchedAt(data.fetchedAt);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh every 3 minutes (matches backend cache TTL)
  useEffect(() => {
    const id = setInterval(load, 180_000);
    return () => clearInterval(id);
  }, [load]);

  return (
    <section className="card">
      <div className="news-head">
        <h2>Real-time research &amp; news</h2>
        <div className="news-meta muted small">
          {fetchedAt && `Updated ${relativeTime(fetchedAt)}`}
          <button
            type="button"
            className="refresh-btn-mini"
            onClick={load}
            disabled={loading}
          >
            {loading ? '…' : '↻'}
          </button>
        </div>
      </div>
      <p className="muted">
        Aggregated from Finnhub company news + Yahoo Finance RSS + Google News RSS.
        Results cached 3 minutes on the server to stay polite with the sources.
      </p>

      <div className="news-tabs">
        {WATCH.map((w) => (
          <button
            key={w}
            type="button"
            className={`news-tab ${selected === w ? 'active' : ''}`}
            onClick={() => setSelected(w)}
          >
            {w}
          </button>
        ))}
      </div>

      {error && <div className="error-card">News fetch failed: {error}</div>}
      {!error && items.length === 0 && !loading && (
        <div className="muted small" style={{ padding: '12px 0' }}>
          No items returned. Make sure FINNHUB_API_KEY is set in backend/.env
          (Yahoo + Google RSS run without a key and should still return something).
        </div>
      )}

      <ul className="news-list">
        {items.map((n, i) => (
          <li key={`${n.url}-${i}`} className="news-item">
            <div className="news-line">
              <a className="news-title" href={n.url} target="_blank" rel="noreferrer">
                {n.title}
              </a>
              <span className={`news-src news-src-${n.provider}`}>{n.source}</span>
            </div>
            {n.summary && <div className="news-summary">{n.summary}</div>}
            <div className="news-foot">
              {relativeTime(n.published)} · {n.provider}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
