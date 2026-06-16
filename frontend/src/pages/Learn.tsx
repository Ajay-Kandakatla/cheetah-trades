/* Learn — Minervini Learning module.
 *
 *  Two entry paths:
 *
 *    1. User tapped a flashcard PUSH NOTIFICATION on their phone.
 *       URL: /learn?topic=entry&from=alert
 *       → Page opens with the 'entry' tab active and a "← Back to
 *         alerts" link in the header that routes to /notifications.
 *         The notification that triggered the visit is preserved in
 *         push_history so the user can re-read its body alongside the
 *         full topic.
 *
 *    2. User opened /learn from the nav menu directly.
 *       URL: /learn
 *       → Page opens on the "Today's pick" topic (the one currently
 *         mapped to the local-hour slot in HOURLY_TOPIC). Tabs let
 *         the user explore any topic.
 *
 *  Data: GET /flashcards/all returns the full bank (90 cards in 9
 *  topics + the hourly-topic map). Fetched once on mount, cached
 *  for the session in module-level state.
 *
 *  Layout: tab strip at the top (one per topic), card list below.
 *  Each card shows the title, body, source citation, and (for users
 *  arriving from a push) a subtle "← just-pushed" tag on the one
 *  that matches the tag from the notification.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { usePageContext } from '../hooks/usePageContext';

type Card = {
  id:     string;
  topic:  string;
  title:  string;
  body:   string;
  source?: string;
  url?:   string;
};

type AllCardsResponse = {
  by_topic:        Record<string, Card[]>;
  hourly_topic:    Record<string, string>;
  today_per_topic: Record<string, string>;
  total_count:     number;
};

const TOPIC_META: Record<string, { label: string; emoji: string; tone: string; blurb: string }> = {
  entry:            { label: 'Entry',      emoji: '🎯', tone: '#10b981',
                      blurb: 'Pivot rules, base quality, RS gates, follow-through days.' },
  risk:             { label: 'Risk',       emoji: '🛡️', tone: '#f59e0b',
                      blurb: '1% rule, stop placement, asymmetry of losses, sizing formula.' },
  sell_rules:       { label: 'Sell',       emoji: '✂️', tone: '#ef4444',
                      blurb: '-12% rule, partials at 3R, close-of-day rule, climax tops.' },
  psychology:       { label: 'Mindset',    emoji: '🧠', tone: '#8b5cf6',
                      blurb: 'Bounce-back trap, process > outcome, hope-is-not-strategy.' },
  review:           { label: 'Mistakes',   emoji: '⚠️', tone: '#ec4899',
                      blurb: 'No-stop trades, averaging down, regime-mismatch, stage analysis.' },
  fundamentals:     { label: 'Fundamentals', emoji: '📚', tone: '#3b82f6',
                      blurb: 'EPS, P/E vs PEG, FCF, ROIC, equity types, buybacks, EV.' },
  market_structure: { label: 'Market',     emoji: '🏛️', tone: '#06b6d4',
                      blurb: 'T+1 settlement, dark pools, LULD halts, NBBO, options Greeks.' },
  history:          { label: 'History',    emoji: '📖', tone: '#d4af37',
                      blurb: 'Livermore, LTCM, Druckenmiller, GME squeeze, flash crash, '
                              + 'Buffett, PTJ, Soros.' },
  edge_math:        { label: 'Edge math',  emoji: '🧮', tone: '#22c55e',
                      blurb: 'Expectancy, Kelly criterion, drawdown math, Sharpe vs Sortino, '
                              + 'compounding, R-multiples.' },
  chart_patterns:   { label: 'Patterns',   emoji: '🗺️', tone: '#c9a227',
                      blurb: 'Bulkowski bases + the supply/demand WHY — double bottoms, '
                              + 'inverse H&S, cup-handle, flags. Visual drills on /chart-school.' },
  candle_reads:     { label: 'Candles',    emoji: '🕯️', tone: '#fb923c',
                      blurb: 'Wick/body anatomy at levels — the language your SEPA Watch '
                              + 'alerts speak. Honest about the nulls.' },
};

const TOPIC_ORDER: string[] = [
  'entry', 'chart_patterns', 'candle_reads', 'risk', 'sell_rules', 'psychology',
  'review', 'fundamentals', 'market_structure', 'history', 'edge_math',
];

// Session-scoped cache so navigating between /learn and other pages
// doesn't re-fetch the 25KB card bank every time.
let _cache: AllCardsResponse | null = null;


export default function LearnPage() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const { setPageContext } = usePageContext();
  const [data, setData] = useState<AllCardsResponse | null>(_cache);
  const [err, setErr]   = useState<string | null>(null);

  // The active topic is driven by ?topic= (push notifications carry
  // this). If absent, fall back to today's hour's topic so the user
  // lands on "what would have just pushed". If THAT lookup fails for
  // any reason, default to 'entry'.
  const urlTopic = params.get('topic');
  const fromAlert = params.get('from') === 'alert';

  const activeTopic = useMemo(() => {
    if (urlTopic && TOPIC_META[urlTopic]) return urlTopic;
    if (data) {
      const hour = new Date().getHours();
      const t = data.hourly_topic?.[String(hour)];
      if (t && TOPIC_META[t]) return t;
    }
    return 'entry';
  }, [urlTopic, data]);

  // Fetch once. Empty deps because we cache at module scope.
  useEffect(() => {
    if (_cache) { setData(_cache); return; }
    let alive = true;
    fetch(`${API}/flashcards/all`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((j: AllCardsResponse) => {
        _cache = j;
        if (alive) setData(j);
      })
      .catch((e) => { if (alive) setErr(String(e?.message || e)); });
    return () => { alive = false; };
  }, []);

  // Page context for ChatWidget — lets Claude know the user is on the
  // learning module + which topic they're studying. Useful when they
  // ask follow-ups like "explain the pocket pivot more deeply" — the
  // assistant has the topic anchor.
  useEffect(() => {
    setPageContext({
      page:           'learn',
      active_topic:   activeTopic,
      card_count:     data?.by_topic[activeTopic]?.length ?? 0,
      arrived_from:   fromAlert ? 'push_notification' : 'menu',
    });
    return () => setPageContext(null);
  }, [activeTopic, data, fromAlert, setPageContext]);

  const switchTopic = (t: string) => {
    // Use setParams so we don't lose ?from=alert when switching tabs
    // mid-session. The fromAlert UX (back-to-alerts link) stays useful
    // even if the user explores other topics.
    const next = new URLSearchParams(params);
    next.set('topic', t);
    setParams(next, { replace: true });
  };

  const meta = TOPIC_META[activeTopic];
  const cards = data?.by_topic[activeTopic] || [];
  const todayPick = data?.today_per_topic[activeTopic];

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 920, margin: '0 auto' }}>
      {/* Back-to-alerts header — only shown when the user arrived via a
          push notification. Sends them back to the notifications page
          where they can see the original push that brought them here.
          Without ?from=alert, this slot stays empty so menu-arrivals
          aren't confused by a back link to somewhere they didn't come from. */}
      {fromAlert && (
        <div style={{
          marginBottom: '0.6rem',
          fontSize: '0.78rem',
        }}>
          <Link
            to="/notifications"
            state={{ from: location.pathname + location.search, label: 'learning' }}
            style={{
              display: 'inline-block',
              padding: '4px 10px',
              background: 'rgba(212,175,55,0.08)',
              border: '1px solid rgba(212,175,55,0.25)',
              borderRadius: 4,
              color: '#d4af37',
              textDecoration: 'none',
              fontFamily: 'inherit',
            }}
          >
            ← Back to alerts
          </Link>
          <span style={{ marginLeft: 8, color: '#6a6a72', fontSize: '0.72rem' }}>
            You arrived here from a push notification.
            The full message is preserved in your notification history.
          </span>
        </div>
      )}

      <header className="cm-pagehead" style={{ marginBottom: '0.9rem' }}>
        <div className="cm-pagehead__col">
          <div className="eyebrow">Learning · Minervini + general trading</div>
          <h1 className="display cm-pagehead__title" style={{ margin: '0.2rem 0 0' }}>
            Learn
          </h1>
          <p className="lede">
            {data ? `${data.total_count} cards across 9 topics. ` : ''}
            Pushes deliver one per hour. Browse the full bank here, or tap a
            push notification on your phone — it routes you straight to its
            topic.
          </p>
        </div>
      </header>

      {/* Topic tab strip — same emoji + label pair the cards use, plus
          a tone bar so the active tab is visually anchored. */}
      <div role="tablist" style={{
        display: 'flex',
        gap: '0.4rem',
        marginBottom: '0.9rem',
        flexWrap: 'wrap',
      }}>
        {TOPIC_ORDER.map((t) => {
          const tmeta = TOPIC_META[t];
          const active = t === activeTopic;
          return (
            <button
              key={t}
              role="tab"
              aria-selected={active}
              onClick={() => switchTopic(t)}
              style={{
                padding: '0.45rem 0.85rem',
                background: active ? `${tmeta.tone}22` : 'rgba(255,255,255,0.04)',
                border: `1px solid ${active ? tmeta.tone : 'rgba(255,255,255,0.08)'}`,
                borderBottom: active ? `2px solid ${tmeta.tone}` : '1px solid rgba(255,255,255,0.08)',
                borderRadius: 6,
                color: active ? tmeta.tone : '#cfcfd4',
                fontFamily: 'inherit',
                fontWeight: active ? 700 : 500,
                fontSize: '0.82rem',
                cursor: 'pointer',
              }}
            >
              {tmeta.emoji} {tmeta.label}
            </button>
          );
        })}
      </div>

      {/* Topic blurb — quick orientation when the user switches tabs */}
      <section style={{
        padding: '0.65rem 0.85rem',
        background: `${meta.tone}10`,
        border: `1px solid ${meta.tone}30`,
        borderLeft: `3px solid ${meta.tone}`,
        borderRadius: 6,
        marginBottom: '0.9rem',
      }}>
        <div style={{
          fontSize: '0.66rem',
          color: meta.tone,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          fontWeight: 700,
          marginBottom: 3,
        }}>
          {meta.emoji} {meta.label}
        </div>
        <div style={{ fontSize: '0.82rem', color: '#cfcfd4', lineHeight: 1.5 }}>
          {meta.blurb}
        </div>
        {todayPick && (
          <div style={{
            marginTop: 6, fontSize: '0.72rem', color: '#9a9aa3',
          }}>
            Today's card from this topic:
            {' '}<strong style={{ color: meta.tone }}>{todayPick}</strong>
          </div>
        )}
      </section>

      {err && (
        <div style={{
          padding: '0.5rem 0.7rem',
          background: 'rgba(239,68,68,0.06)',
          border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: 4,
          color: '#fca5a5',
          fontSize: '0.78rem',
          marginBottom: '0.6rem',
        }}>
          Couldn't load cards: {err}
        </div>
      )}

      {!data && !err && (
        <div style={{ color: '#9a9aa3', fontSize: '0.85rem' }}>loading cards…</div>
      )}

      {data && cards.length === 0 && (
        <div style={{ color: '#9a9aa3', fontSize: '0.85rem' }}>
          No cards in this topic.
        </div>
      )}

      {/* Card list */}
      {cards.map((c) => {
        const isTodayPick = todayPick === c.title;
        return (
          <article
            key={c.id}
            id={c.id}
            style={{
              padding: '0.7rem 0.9rem',
              background: isTodayPick ? `${meta.tone}10` : 'rgba(20,20,22,0.55)',
              border: `1px solid ${isTodayPick ? `${meta.tone}40` : 'rgba(255,255,255,0.06)'}`,
              borderLeft: `3px solid ${isTodayPick ? meta.tone : 'rgba(255,255,255,0.1)'}`,
              borderRadius: 6,
              marginBottom: '0.55rem',
            }}
          >
            <div style={{
              display: 'flex', alignItems: 'baseline',
              justifyContent: 'space-between', gap: '0.5rem',
              marginBottom: 4,
            }}>
              <div style={{
                fontWeight: 700, fontSize: '0.92rem', lineHeight: 1.3,
              }}>
                {c.title}
              </div>
              {isTodayPick && (
                <span style={{
                  fontSize: '0.62rem', color: meta.tone,
                  letterSpacing: '0.06em', fontWeight: 700,
                  whiteSpace: 'nowrap',
                }}>
                  TODAY
                </span>
              )}
            </div>
            <div style={{
              fontSize: '0.84rem', lineHeight: 1.55,
              color: '#cfcfd4', whiteSpace: 'pre-wrap',
            }}>
              {c.body}
            </div>
            {c.source && (
              <div style={{
                marginTop: 5, fontSize: '0.7rem', color: '#6a6a72',
              }}>
                — {c.source}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
