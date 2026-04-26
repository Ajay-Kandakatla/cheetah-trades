import { useCallback, useEffect, useState } from 'react';

const API = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

type RedditThread = {
  subreddit: string;
  title: string;
  url: string;
  score: number;
  n_comments: number;
  created: number;
  snippet: string;
  comments?: { score: number; body: string }[];
};

type ValuePickrTopic = {
  id: number;
  title: string;
  slug: string;
  url: string;
  posts_count: number;
  reply_count: number;
  like_count: number;
  views: number;
  bumped_at: number;
};

type MoneyControlArticle = {
  title: string;
  url: string;
  snippet: string;
  date: string;
};

type IndiaPayload = {
  symbol: string;
  company_name: string | null;
  fetched_at: number;
  cached: boolean;
  reddit: {
    available: boolean;
    reason?: string;
    threads: RedditThread[];
    mentions_7d: number;
    mentions_prior_7d: number;
  };
  valuepickr: {
    available: boolean;
    reason?: string;
    topics: ValuePickrTopic[];
    n: number;
  };
  moneycontrol: {
    available: boolean;
    reason?: string;
    articles: MoneyControlArticle[];
    n: number;
  };
  summary: {
    mentions_7d: number;
    mentions_prior_7d: number;
    mention_velocity: number;
    engagement: number;
    vp_topics: number;
    mc_articles: number;
    momentum_label: 'ramping' | 'steady' | 'fading' | 'quiet';
  };
};

function timeAgo(unixSec: number): string {
  if (!unixSec) return '—';
  const diff = Math.floor(Date.now() / 1000) - unixSec;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function RedditThreadCard({ t }: { t: RedditThread }) {
  return (
    <a className="cm-thread" href={t.url} target="_blank" rel="noreferrer">
      <div className="cm-thread__head mono">
        <span className="cm-thread__sub">r/{t.subreddit}</span>
        <span className="cm-thread__sep">·</span>
        <span className="cm-thread__score">▲ {t.score}</span>
        <span className="cm-thread__sep">·</span>
        <span>{t.n_comments} comments</span>
        <span className="cm-thread__sep">·</span>
        <span>{timeAgo(t.created)}</span>
      </div>
      <div className="cm-thread__title">{t.title}</div>
      {t.snippet && <div className="cm-thread__snippet">{t.snippet}</div>}
      {t.comments && t.comments.length > 0 && (
        <div className="cm-thread__comments">
          {t.comments.map((c, i) => (
            <div key={i} className="cm-thread__comment">
              <span className="mono cm-thread__comment-score">▲ {c.score}</span>
              <span>{c.body}</span>
            </div>
          ))}
        </div>
      )}
    </a>
  );
}

export function ChatterIndiaPanel({ symbol, onClose }: { symbol: string; onClose?: () => void }) {
  const [data, setData] = useState<IndiaPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const params = refresh ? '?refresh=true' : '';
      const r = await fetch(`${API}/sepa/chatter-in/${encodeURIComponent(symbol)}${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: IndiaPayload = await r.json();
      setData(j);
      setErr(null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => { load(false); }, [load]);

  if (loading && !data) {
    return (
      <div className="sepa-drawer__loading">
        <div className="eyebrow">Loading {symbol} chatter…</div>
        <div className="sepa-loading__dots"><span /><span /><span /></div>
      </div>
    );
  }
  if (err) return <p className="sepa-err">{err}</p>;
  if (!data) return null;

  const s = data.summary;

  return (
    <div className="cm-chatter">
      {/* Header with back button */}
      <div className="cm-chatter__panel-head">
        {onClose && (
          <button type="button" className="cm-chatter__back" onClick={onClose}>
            ← Back to universe
          </button>
        )}
        <div className="cm-chatter__panel-title">
          <strong className="mono">{data.symbol}</strong>
          {data.company_name && <span className="cm-chatter__panel-name">{data.company_name}</span>}
        </div>
      </div>

      {/* Summary strip */}
      <div className="cm-chatter__summary">
        <div className="cm-chatter__metric">
          <div className="eyebrow">Momentum</div>
          <div className={`cm-mom cm-mom--${s.momentum_label}`}>{s.momentum_label}</div>
        </div>
        <div className="cm-chatter__metric">
          <div className="eyebrow">Mentions · 7d</div>
          <div className="cm-chatter__big mono">
            {s.mentions_7d}
            <span className="cm-chatter__sub mono">vs {s.mentions_prior_7d} prior</span>
          </div>
        </div>
        <div className="cm-chatter__metric">
          <div className="eyebrow">Velocity</div>
          <div className={`cm-chatter__big mono cm-velocity cm-velocity--${
            s.mention_velocity >= 1.5 ? 'ramp' :
            s.mention_velocity <= 0.6 ? 'fade' : 'steady'
          }`}>
            {s.mention_velocity}×
          </div>
        </div>
        <div className="cm-chatter__metric">
          <div className="eyebrow">Engagement</div>
          <div className="cm-chatter__big mono">{s.engagement.toLocaleString()}</div>
        </div>
        <div className="cm-chatter__metric cm-chatter__refresh-cell">
          <button
            className="dm-refresh"
            onClick={() => load(true)}
            disabled={loading}
            title={data.cached ? `Cached · ${timeAgo(data.fetched_at)}` : 'Live data'}
          >
            {loading ? '…' : data.cached ? `Refresh (cached ${timeAgo(data.fetched_at)})` : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Reddit · India */}
      <section className="cm-chatter__lane">
        <div className="eyebrow">
          Reddit · India
          <span className="cm-chatter__lane-sub mono">
            {' '}IndianStockMarket / IndiaInvestments / NSEbets / StockMarketIndia / DalalStreetTalks
          </span>
        </div>
        {!data.reddit.available ? (
          <p className="sepa-empty">{data.reddit.reason ?? 'No data'}</p>
        ) : data.reddit.threads.length === 0 ? (
          <p className="sepa-empty">No threads above the score floor in the last 30 days.</p>
        ) : (
          <div className="cm-thread-list">
            {data.reddit.threads.map((t, i) => <RedditThreadCard key={i} t={t} />)}
          </div>
        )}
      </section>

      {/* ValuePickr */}
      <section className="cm-chatter__lane">
        <div className="eyebrow">
          ValuePickr
          <span className="cm-chatter__lane-sub mono">
            {' '}forum.valuepickr.com · {data.valuepickr.n} {data.valuepickr.n === 1 ? 'topic' : 'topics'}
          </span>
        </div>
        {!data.valuepickr.available ? (
          <p className="sepa-empty">{data.valuepickr.reason ?? 'No data'}</p>
        ) : data.valuepickr.topics.length === 0 ? (
          <p className="sepa-empty">No matching topics in the last 6 months.</p>
        ) : (
          <div className="cm-vp-list">
            {data.valuepickr.topics.map((t) => (
              <a key={t.id} className="cm-vp-topic" href={t.url} target="_blank" rel="noreferrer">
                <div className="cm-vp-topic__title">{t.title}</div>
                <div className="cm-vp-topic__meta mono">
                  ❤ {t.like_count} · {t.posts_count} posts · {t.views.toLocaleString()} views
                  {t.bumped_at > 0 && ` · ${timeAgo(t.bumped_at)}`}
                </div>
              </a>
            ))}
          </div>
        )}
      </section>

      {/* MoneyControl */}
      <section className="cm-chatter__lane">
        <div className="eyebrow">
          MoneyControl News
          <span className="cm-chatter__lane-sub mono">
            {' '}{data.moneycontrol.n} recent {data.moneycontrol.n === 1 ? 'article' : 'articles'}
          </span>
        </div>
        {!data.moneycontrol.available ? (
          <p className="sepa-empty">{data.moneycontrol.reason ?? 'No data'}</p>
        ) : data.moneycontrol.articles.length === 0 ? (
          <p className="sepa-empty">No tagged articles found.</p>
        ) : (
          <div className="cm-hn-list">
            {data.moneycontrol.articles.map((a, i) => (
              <div key={i} className="cm-hn-story">
                <a className="cm-hn-story__title" href={a.url} target="_blank" rel="noreferrer">
                  {a.title}
                </a>
                {a.snippet && <div className="cm-hn-story__meta">{a.snippet}</div>}
                {a.date && <div className="cm-hn-story__meta mono">{a.date}</div>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
