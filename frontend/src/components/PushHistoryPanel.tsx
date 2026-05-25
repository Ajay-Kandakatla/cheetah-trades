/* PushHistoryPanel — recent push notifications with FULL bodies.
 *
 *  Why this exists: iOS/Android lock-screen banners truncate the body
 *  field to ~180 chars. For flashcards or breakout alerts whose lesson
 *  ran to ~250 chars, the punchline got clipped and the user had no
 *  way to re-read it. This panel pulls /push/history (backed by
 *  push_history Mongo collection, 90-day TTL) and renders each row
 *  with the UNTRUNCATED body.
 *
 *  Mounted at the top of /notifications. Optional `limit` prop lets
 *  callers reuse this elsewhere (e.g. a dashboard widget) with a
 *  smaller cap. The default 25 matches the user's stated requirement
 *  ("see the last 25 atleast").
 *
 *  Tap a row to open the push's URL (the same destination tapping the
 *  notification on your phone would've taken you to). Internal app
 *  routes navigate via react-router; external URLs open in a new tab.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

type HistoryRow = {
  _id:        string;
  ts:         number;
  ts_iso:     string;
  title:      string;
  body:       string;
  kind:       string | null;
  ticker:     string | null;
  url:        string | null;
  user_email: string | null;
  sent:       number;
  failed:     number;
  total:      number;
  /** Discriminator from the merged /notifications/recent endpoint:
   *  'push' = row originated from push_history (flashcards, morning brief,
   *  todo reminders, etc.); 'breakout' = row originated from
   *  sepa_breakouts (volume breakouts, stage breakdowns). Breakouts
   *  carry a `dismissed` flag instead of delivery counts. */
  source?:    'push' | 'breakout';
  dismissed?: boolean;
};

/* Human-friendly label for each push kind. Keys mirror the backend
 * `kind` field set by send_to_all / send_to_user callers. */
const KIND_LABEL: Record<string, string> = {
  volume_breakout:          '🚀 Volume breakout',
  rising_momentum:          '📈 Rising momentum',
  watchlist_breakout:       '⭐ Watchlist breakout',
  juggernaut_watchlist:     '💪 Juggernaut',
  stage_breakdown:          '⚠️ Stage breakdown',
  watchlist_stage_breakdown:'🛑 Watchlist breakdown',
  price_alert:              '🔔 Price alert',
  position_alert:           '💼 Position alert',
  morning_brief:            '🌅 Morning brief',
  product_launch:           '🚀 Product launch',
  todo_reminder:            '📌 Todo reminder',
  todo_daily_digest:        '📋 Todo digest',
  house_daily:              '🏡 House daily',
  house_scrape_failed:      '⚠️ House scrape failed',
  house_stagnant:           '📉 House stagnant',
  user_signin:              '👋 New user',
  minervini_flashcards:     '🃏 Flash card',
  market_hours_reminder:    '🔔 Market reminder',
  setup_inside_day:         '📦 Inside-day setup',
  setup_peg:                '⚡ PEG setup',
  setup_orb_capture:        '🎯 ORB range set',
  setup_orb_triggered:      '🎯 ORB triggered',
  generic:                  '📣 Notification',
};

function kindLabel(k: string | null): string {
  if (!k) return KIND_LABEL.generic;
  return KIND_LABEL[k] || k;
}

function fmtAgo(ts: number): string {
  const sec = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (sec < 60)    return `${sec}s ago`;
  if (sec < 3600)  return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}

function fmtClock(ts: number): string {
  // Render in user's local TZ so they can match against memory of
  // "when did I see that?"
  return new Date(ts * 1000).toLocaleString('en-US', {
    month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}


/** A single row in the history list — title, time, full body, tap action. */
function HistoryRowCard({ row }: { row: HistoryRow }) {
  // Decide whether to render as an in-app link (react-router) or an
  // external anchor. Internal routes start with "/" and are not
  // absolute URLs.
  const isInternal = !!row.url && row.url.startsWith('/') && !row.url.startsWith('//');
  const isExternal = !!row.url && /^https?:\/\//.test(row.url);
  const content = (
    <>
      <div style={{
        display: 'flex', alignItems: 'baseline',
        justifyContent: 'space-between', gap: '0.5rem',
        marginBottom: 2,
      }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <span style={{
            fontSize: '0.62rem',
            color: '#9a9aa3',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            fontWeight: 700,
          }}>
            {kindLabel(row.kind)}
          </span>
          {row.ticker && (
            <span className="mono" style={{
              marginLeft: 6,
              fontSize: '0.66rem',
              color: '#d4af37',
              fontWeight: 700,
            }}>
              {row.ticker}
            </span>
          )}
        </div>
        <div style={{ fontSize: '0.66rem', color: '#6a6a72', whiteSpace: 'nowrap' }}>
          {fmtAgo(row.ts)} · <span title={fmtClock(row.ts)}>{fmtClock(row.ts)}</span>
        </div>
      </div>

      <div style={{
        fontSize: '0.88rem',
        fontWeight: 600,
        lineHeight: 1.35,
        marginBottom: 3,
        color: '#e6e6e6',
      }}>
        {row.title}
      </div>

      {/* FULL body — no truncation. This is the whole point of the panel. */}
      {row.body && (
        <div style={{
          fontSize: '0.82rem',
          lineHeight: 1.5,
          color: '#cfcfd4',
          whiteSpace: 'pre-wrap',   // preserve line breaks from cards (e.g. "— source")
          wordBreak: 'break-word',
        }}>
          {row.body}
        </div>
      )}

      <div style={{
        marginTop: 5,
        fontSize: '0.62rem',
        color: '#6a6a72',
        display: 'flex',
        gap: 12,
        flexWrap: 'wrap',
      }}>
        {row.source === 'breakout' ? (
          // Breakouts don't carry delivery counts (they're a banner-only
          // record in sepa_breakouts, plus a push side-effect that
          // shows up as a SEPARATE 'push' row). Show the active vs
          // dismissed state instead.
          <span style={{ color: row.dismissed ? '#6a6a72' : '#d4af37' }}>
            breakout · {row.dismissed ? 'dismissed' : 'active'}
          </span>
        ) : (
          <>
            <span>delivered to {row.sent}/{row.total} device{row.total === 1 ? '' : 's'}</span>
            {row.failed > 0 && (
              <span style={{ color: '#fca5a5' }}>{row.failed} failed</span>
            )}
            {row.user_email && (
              <span>scoped: {row.user_email.split('@')[0]}</span>
            )}
            {!row.user_email && <span>broadcast</span>}
          </>
        )}
      </div>
    </>
  );

  const cardStyle: React.CSSProperties = {
    padding: '0.55rem 0.7rem',
    background: 'rgba(20,20,22,0.55)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 6,
    marginBottom: '0.4rem',
    color: 'inherit',
    textDecoration: 'none',
    display: 'block',
  };

  if (isInternal) {
    return <Link to={row.url!} style={cardStyle}>{content}</Link>;
  }
  if (isExternal) {
    return <a href={row.url!} target="_blank" rel="noreferrer" style={cardStyle}>{content}</a>;
  }
  return <div style={cardStyle}>{content}</div>;
}


export function PushHistoryPanel({ limit = 25 }: { limit?: number }) {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    // Use the unified feed so volume breakouts + stage breakdowns
    // from sepa_breakouts show up alongside push_history rows.
    fetch(`${API}/notifications/recent?limit=${limit}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => { if (!cancelled) setRows(j?.rows || []); })
      .catch((e) => { if (!cancelled) setErr(String(e?.message || e)); });
    return () => { cancelled = true; };
  }, [limit, reloadKey]);

  return (
    <section style={{
      marginBottom: '1rem',
      padding: '0.7rem 0.85rem',
      background: 'rgba(20,20,22,0.5)',
      border: '1px solid rgba(212,175,55,0.18)',
      borderRadius: 8,
    }}>
      <div style={{
        display: 'flex', alignItems: 'baseline',
        justifyContent: 'space-between', marginBottom: '0.5rem',
      }}>
        <div>
          <div className="eyebrow" style={{
            color: '#d4af37', fontSize: '0.62rem',
            letterSpacing: '0.1em', fontWeight: 700,
          }}>
            🗂️ Recent notifications
          </div>
          <div style={{ fontSize: '0.72rem', color: '#9a9aa3', marginTop: 1 }}>
            Last {limit} alerts — pushes + volume breakouts unified, full body
            (lock-screen truncates at ~180 chars). Tap a row to open its target page.
          </div>
        </div>
        <button
          type="button"
          onClick={() => setReloadKey((k) => k + 1)}
          title="Reload history"
          style={{
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.12)',
            color: '#9a9aa3',
            padding: '3px 9px',
            borderRadius: 4,
            fontSize: '0.7rem',
            fontFamily: 'inherit',
            cursor: 'pointer',
          }}
        >
          ↻ refresh
        </button>
      </div>

      {err && (
        <div style={{
          padding: '0.4rem 0.6rem',
          background: 'rgba(239,68,68,0.06)',
          border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 4,
          fontSize: '0.76rem',
          color: '#fca5a5',
          marginBottom: '0.4rem',
        }}>
          {err}
        </div>
      )}

      {rows === null && !err && (
        <div style={{ color: '#9a9aa3', fontSize: '0.8rem', padding: '0.5rem 0' }}>
          loading…
        </div>
      )}

      {rows && rows.length === 0 && (
        <div style={{
          padding: '0.7rem 0.9rem',
          background: 'rgba(20,20,22,0.5)',
          border: '1px dashed rgba(255,255,255,0.1)',
          borderRadius: 6,
          fontSize: '0.78rem',
          color: '#9a9aa3',
          lineHeight: 1.5,
        }}>
          No history yet. Pushes started being recorded on <strong>2026-05-21</strong>.
          The next breakout / flashcard / morning-brief notification will show up here
          with its full untruncated body.
        </div>
      )}

      {rows && rows.length > 0 && (
        <div>
          {rows.map((r) => <HistoryRowCard key={r._id} row={r} />)}
        </div>
      )}
    </section>
  );
}
