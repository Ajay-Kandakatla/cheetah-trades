/* TodoDashboardWidget — small stats strip at the top of /todos.
 *
 * Renders the counts that matter most when you open the app:
 *   Open · Today · Overdue · ⭐ Important
 *   plus a Personal / Work split
 *   plus an "AI" mini-strip if any rows have ai_task=true
 *
 * Lightweight on purpose — this is a header, not a full reporting
 * page. The full /todos list below answers the "what specifically"
 * follow-up question. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Stats = {
  open?: { total?: number; personal?: number; work?: number };
  today?: number;
  overdue?: number;
  important_open?: number;
  ai?: { pending?: number; running?: number; done?: number; failed?: number };
  completed_7d?: number;
};

export function TodoDashboardWidget({ refreshKey }: { refreshKey?: any }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/todos/dashboard`)
      .then((r) => r.ok ? r.json() : {})
      .then((j) => { if (!cancelled) setStats(j); })
      .catch(() => { /* widget is informational — silent on failure */ });
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (!stats) {
    return (
      <div style={{ height: 68, marginBottom: '0.7rem', color: 'var(--cm-slate)', fontSize: '0.78rem' }}>
        Loading dashboard…
      </div>
    );
  }

  const open = stats.open || {};
  const ai = stats.ai || {};
  const aiTotal = (ai.pending || 0) + (ai.running || 0) + (ai.done || 0) + (ai.failed || 0);

  return (
    <div
      style={{
        marginBottom: '0.9rem',
        padding: '0.7rem 0.85rem',
        border: '1px solid var(--rule, #333)',
        borderRadius: 6,
        background: 'var(--bg-raised, #181818)',
        display: 'grid',
        gap: '0.6rem',
      }}
    >
      {/* Primary numbers row — single source of "what's on my plate". */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.9rem 1.2rem', alignItems: 'baseline' }}>
        <Stat label="Open"     value={open.total ?? 0} tone="default" />
        <Stat label="Today"    value={stats.today ?? 0} tone="positive" />
        <Stat label="Overdue"  value={stats.overdue ?? 0} tone={(stats.overdue || 0) > 0 ? 'negative' : 'muted'} />
        <Stat label="⭐ Important" value={stats.important_open ?? 0} tone="warn" />
        <Stat label="Done · 7d" value={stats.completed_7d ?? 0} tone="muted" />
      </div>

      {/* Workspace + AI split, if anything to show. Personal and Work
          render as a single line so the widget doesn't grow vertically
          when the user only has personal todos. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1rem', fontSize: '0.74rem', color: 'var(--cm-slate)' }}>
        <span>
          🏠 Personal: <strong style={{ color: 'var(--ink, inherit)' }}>{open.personal ?? 0}</strong>
          {' · '}
          💼 Work: <strong style={{ color: 'var(--ink, inherit)' }}>{open.work ?? 0}</strong>
        </span>
        {aiTotal > 0 && (
          <span title="AI research tasks">
            🤖 AI: <strong style={{ color: 'var(--ink, inherit)' }}>{aiTotal}</strong>
            {(ai.pending || 0) > 0 && <span> · ⏳ {ai.pending}</span>}
            {(ai.running || 0) > 0 && <span> · ⚡ {ai.running}</span>}
            {(ai.done    || 0) > 0 && <span> · ✓ {ai.done}</span>}
            {(ai.failed  || 0) > 0 && <span style={{ color: 'var(--negative)' }}> · × {ai.failed}</span>}
          </span>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: {
  label: string;
  value: number;
  tone: 'default' | 'positive' | 'negative' | 'warn' | 'muted';
}) {
  const color =
    tone === 'positive' ? 'var(--positive, #10b981)' :
    tone === 'negative' ? 'var(--negative, #ef4444)' :
    tone === 'warn'     ? 'var(--warn, #d97706)' :
    tone === 'muted'    ? 'var(--cm-slate)' :
    'var(--ink, inherit)';
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.35rem' }}>
      <span style={{ fontSize: '1.35rem', fontWeight: 700, color }}>{value}</span>
      <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </span>
    </div>
  );
}
