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

type RedditLane = {
  available: boolean;
  reason?: string;
  threads: RedditThread[];
  mentions_7d: number;
  mentions_prior_7d: number;
};

type StockTwitsMessage = {
  id: number;
  body: string;
  user: string | null;
  followers: number;
  sentiment: 'Bullish' | 'Bearish' | null;
  created: string;
  url: string;
};

type StockTwitsLane = {
  available: boolean;
  reason?: string;
  messages: StockTwitsMessage[];
  bullish: number;
  bearish: number;
  neutral: number;
  total: number;
};

type HnStory = {
  title: string;
  url: string;
  hn_url: string;
  points: number;
  n_comments: number;
  author: string;
  created: number;
};

type HnLane = {
  available: boolean;
  reason?: string;
  stories: HnStory[];
  n: number;
};

type ChatterPayload = {
  symbol: string;
  company_name?: string | null;
  fetched_at: number;
  fetched_at_iso: string;
  thoughtful: RedditLane;
  momentum: RedditLane;
  stocktwits: StockTwitsLane;
  hn: HnLane;
  summary: {
    mentions_7d: number;
    mentions_prior_7d: number;
    mention_velocity: number;
    sentiment_ratio: number | null;
    stocktwits_bullish: number;
    stocktwits_bearish: number;
    hn_stories: number;
    momentum_label: 'ramping' | 'steady' | 'fading' | 'quiet';
  };
  cached: boolean;
};

function timeAgo(unixSec: number | string): string {
  const s = typeof unixSec === 'string' ? Math.floor(Date.parse(unixSec) / 1000) : unixSec;
  const diff = Math.floor(Date.now() / 1000) - s;
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

export function ChatterPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<ChatterPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const params = refresh ? '?refresh=true' : '';
      const r = await fetch(`${API}/sepa/chatter/${encodeURIComponent(symbol)}${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: ChatterPayload = await r.json();
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
        <div className="eyebrow">Loading chatter…</div>
        <div className="sepa-loading__dots"><span /><span /><span /></div>
      </div>
    );
  }

  if (err) return <p className="sepa-err">{err}</p>;
  if (!data) return null;

  const s = data.summary;
  const sentPct = s.sentiment_ratio == null ? null : Math.round(s.sentiment_ratio * 100);

  return (
    <div className="cm-chatter">
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
            <span className="cm-chatter__sub mono">
              vs {s.mentions_prior_7d} prior
            </span>
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
          <div className="eyebrow">Sentiment</div>
          <div className={`cm-chatter__big mono cm-sent cm-sent--${
            sentPct == null ? 'na' :
            sentPct >= 65 ? 'bull' :
            sentPct <= 35 ? 'bear' : 'mixed'
          }`}>
            {sentPct == null ? '—' : `${sentPct}%`}
          </div>
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

      {/* Reddit · Momentum */}
      <section className="cm-chatter__lane">
        <div className="eyebrow">
          Reddit · Momentum
          <span className="cm-chatter__lane-sub mono">
            {' '}WSB / StockMarket / pennystocks / Daytrading / swingtrading
          </span>
        </div>
        {!data.momentum.available ? (
          <p className="sepa-empty">{data.momentum.reason ?? 'No data'}</p>
        ) : data.momentum.threads.length === 0 ? (
          <p className="sepa-empty">No threads above the score floor in the last 30 days.</p>
        ) : (
          <div className="cm-thread-list">
            {data.momentum.threads.map((t, i) => <RedditThreadCard key={i} t={t} />)}
          </div>
        )}
      </section>

      {/* Reddit · Thoughtful */}
      <section className="cm-chatter__lane">
        <div className="eyebrow">
          Reddit · Thoughtful
          <span className="cm-chatter__lane-sub mono">
            {' '}SecurityAnalysis / ValueInvesting / investing / stocks / options
          </span>
        </div>
        {!data.thoughtful.available ? (
          <p className="sepa-empty">{data.thoughtful.reason ?? 'No data'}</p>
        ) : data.thoughtful.threads.length === 0 ? (
          <p className="sepa-empty">No qualifying threads in the last 30 days.</p>
        ) : (
          <div className="cm-thread-list">
            {data.thoughtful.threads.map((t, i) => <RedditThreadCard key={i} t={t} />)}
          </div>
        )}
      </section>

      {/* StockTwits */}
      <section className="cm-chatter__lane">
        <div className="eyebrow">
          StockTwits
          <span className="cm-chatter__lane-sub mono">
            {' '}{data.stocktwits.bullish} bullish · {data.stocktwits.bearish} bearish · {data.stocktwits.neutral} neutral
          </span>
        </div>
        {!data.stocktwits.available ? (
          <p className="sepa-empty">{data.stocktwits.reason ?? 'No data'}</p>
        ) : data.stocktwits.messages.length === 0 ? (
          <p className="sepa-empty">No recent messages.</p>
        ) : (
          <div className="cm-st-list">
            {data.stocktwits.messages.map((m) => (
              <a key={m.id} className={`cm-st-msg cm-st-msg--${(m.sentiment ?? 'neutral').toLowerCase()}`}
                 href={m.url} target="_blank" rel="noreferrer">
                <div className="cm-st-msg__head mono">
                  {m.sentiment && (
                    <span className={`cm-st-tag cm-st-tag--${m.sentiment.toLowerCase()}`}>
                      {m.sentiment}
                    </span>
                  )}
                  <span className="cm-st-msg__user">@{m.user ?? 'anon'}</span>
                  {m.followers > 0 && (
                    <span className="cm-st-msg__followers">· {m.followers.toLocaleString()} followers</span>
                  )}
                  <span className="cm-st-msg__time">· {timeAgo(m.created)}</span>
                </div>
                <div className="cm-st-msg__body">{m.body}</div>
              </a>
            ))}
          </div>
        )}
      </section>

      {/* Hacker News */}
      <section className="cm-chatter__lane">
        <div className="eyebrow">
          Hacker News
          <span className="cm-chatter__lane-sub mono">
            {' '}last 30 days · {data.hn.n} {data.hn.n === 1 ? 'story' : 'stories'}
          </span>
        </div>
        {!data.hn.available ? (
          <p className="sepa-empty">{data.hn.reason ?? 'No data'}</p>
        ) : data.hn.stories.length === 0 ? (
          <p className="sepa-empty">No matching stories — common for non-tech tickers.</p>
        ) : (
          <div className="cm-hn-list">
            {data.hn.stories.map((s, i) => (
              <div key={i} className="cm-hn-story">
                <a className="cm-hn-story__title" href={s.url} target="_blank" rel="noreferrer">
                  {s.title}
                </a>
                <div className="cm-hn-story__meta mono">
                  ▲ {s.points} · {s.n_comments} comments · {timeAgo(s.created)} ·
                  {' '}<a href={s.hn_url} target="_blank" rel="noreferrer">HN thread</a>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
