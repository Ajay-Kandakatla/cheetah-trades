/* AdminUsage — per-user engagement dashboard.

   Backend gates this to ADMIN_EMAILS (defaults to Ajay only) and returns
   404 to anyone else. Frontend nav also hides it for non-admins, but the
   page itself can render a "not available" state if a non-admin manages
   to deep-link in.

   Sections:
     1. Top strip — totals (users, sessions, dwell-time) over the window
     2. By user — sorted by total dwell; per-module breakdown bar chart
     3. By module — which features get the most attention
     4. Daily activity — sparkline of daily totals
*/
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';

type UserRow = {
  email: string;
  total_sec: number;
  sessions: number;
  modules: Record<string, number>;
  last_seen_iso: string | null;
};

type ModuleRow = {
  module: string;
  total_sec: number;
  users: number;
  sessions: number;
};

type DailyRow = {
  day_et: string;
  total_sec: number;
  users: number;
  sessions: number;
};

type Dashboard = {
  users: UserRow[];
  modules: ModuleRow[];
  daily: DailyRow[];
  total_users: number;
  total_sessions: number;
  total_sec: number;
  window_days: number;
};

const MODULE_EMOJI: Record<string, string> = {
  morning:       '🌅',
  sepa:          '🎯',
  overnight:     '🌙',
  food:          '🍽️',
  kids:          '🧒',
  house:         '🏠',
  catalysts:     '⚡',
  watchlist:     '⭐',
  notifications: '🔔',
  todos:         '📋',
  options:       '📊',
  track:         '📈',
  tiny:          '🔬',
  live:          '📡',
  glossary:      '📖',
  pioneers:      '🚀',
  admin:         '🛠️',
  home:          '🏡',
};

const formatDur = (sec: number): string => {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}m`;
  const h = Math.floor(sec / 3600);
  const m = Math.round((sec % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
};

const formatLast = (iso: string | null): string => {
  if (!iso) return '—';
  const d = new Date(iso);
  const ago = Date.now() - d.getTime();
  if (ago < 5 * 60_000) return 'now';
  if (ago < 60 * 60_000) return `${Math.round(ago / 60_000)}m ago`;
  if (ago < 24 * 60 * 60_000) return `${Math.round(ago / 3_600_000)}h ago`;
  if (ago < 7 * 24 * 60 * 60_000) return `${Math.round(ago / 86_400_000)}d ago`;
  return d.toLocaleDateString();
};

export default function AdminUsage() {
  const [days, setDays] = useState(14);
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetch(`${API}/analytics/dashboard?days=${days}`, { cache: 'no-store' })
      .then(r => {
        if (r.status === 404) throw new Error('not_admin');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(j => { if (!cancelled) setData(j); })
      .catch(e => { if (!cancelled) setError(String(e?.message || e)); });
    return () => { cancelled = true; };
  }, [days]);

  if (error === 'not_admin') {
    // Mirror the stealth-404 pattern from /house — admin existence stays opaque.
    return (
      <div style={{ padding: '4rem 2rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
        <h1 className="display" style={{ margin: 0 }}>404</h1>
        <p className="lede" style={{ marginTop: '0.5rem' }}>Page not found.</p>
      </div>
    );
  }

  const maxUserSec = useMemo(() =>
    Math.max(1, ...(data?.users.map(u => u.total_sec) || [1])),
  [data]);

  const maxDailySec = useMemo(() =>
    Math.max(1, ...(data?.daily.map(d => d.total_sec) || [1])),
  [data]);

  return (
    <div style={{ padding: '1.2rem 1.4rem', maxWidth: 1100, margin: '0 auto' }}>
      <header style={{ marginBottom: '1.2rem' }}>
        <div className="eyebrow">№ Admin · Usage analytics</div>
        <h1 className="display" style={{ margin: '0.25rem 0 0' }}>Usage Dashboard</h1>
        <p className="lede">
          Per-user dwell time + module breakdown. Sessions ≥1 second count; idle tabs cap at 2h/visit so phantom open windows don't dominate.
        </p>
        <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--cm-slate)' }}>Window:</span>
          {[1, 7, 14, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: '4px 10px', fontSize: '0.74rem',
                border: '1px solid', borderColor: days === d ? 'var(--positive)' : 'var(--rule, #555)',
                background: days === d ? 'rgba(16,185,129,0.1)' : 'transparent',
                color: days === d ? 'var(--positive)' : 'inherit',
                borderRadius: 3, cursor: 'pointer',
              }}
            >
              {d}d
            </button>
          ))}
        </div>
      </header>

      {error && error !== 'not_admin' && (
        <div style={{ color: 'var(--negative)', padding: '0.6rem 0.9rem', background: 'rgba(239,68,68,0.08)', borderRadius: 4, marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {data === null && !error && <div style={{ color: 'var(--cm-slate)' }}>Loading…</div>}

      {data && (
        <>
          {/* KPI strip */}
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.6rem', marginBottom: '1.2rem' }}>
            <Kpi label="Active users"     value={String(data.total_users)}        sub={`window: ${days}d`} />
            <Kpi label="Total sessions"   value={data.total_sessions.toLocaleString()} sub="page visits" />
            <Kpi label="Total dwell time" value={formatDur(data.total_sec)}       sub="all users combined" />
            <Kpi label="Avg per session"  value={data.total_sessions > 0 ? formatDur(Math.round(data.total_sec / data.total_sessions)) : '—'} sub="dwell per visit" />
          </section>

          {/* Daily activity sparkline */}
          {data.daily.length > 0 && (
            <section style={{ marginBottom: '1.4rem', padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
              <div className="eyebrow">Daily activity</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 80, marginTop: '0.5rem' }}>
                {data.daily.map(d => {
                  const h = (d.total_sec / maxDailySec) * 70;
                  return (
                    <div key={d.day_et} title={`${d.day_et}: ${formatDur(d.total_sec)} across ${d.users} user(s)`}
                         style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', gap: 2 }}>
                      <div style={{
                        width: '100%',
                        height: Math.max(2, h),
                        background: 'var(--positive, #10b981)',
                        borderRadius: '2px 2px 0 0',
                        opacity: 0.85,
                      }} />
                      <div className="mono" style={{ fontSize: '0.55rem', color: 'var(--cm-slate)' }}>
                        {d.day_et.slice(5)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Two columns: by user + by module */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.5fr) minmax(0, 1fr)', gap: '1rem' }}>
            {/* Users */}
            <section style={{ padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
              <div className="eyebrow">By user</div>
              {data.users.length === 0 && <p style={{ color: 'var(--cm-slate)' }}>No activity in the selected window.</p>}
              <div style={{ marginTop: '0.5rem', display: 'grid', gap: '0.6rem' }}>
                {data.users.map(u => (
                  <UserRowCard key={u.email} row={u} maxSec={maxUserSec} />
                ))}
              </div>
            </section>

            {/* Modules */}
            <section style={{ padding: '0.9rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
              <div className="eyebrow">By module</div>
              <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', marginTop: '0.4rem', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ color: 'var(--cm-slate)', textAlign: 'left' }}>
                    <th style={{ padding: '0.3rem 0.4rem 0.3rem 0' }}>Module</th>
                    <th style={{ padding: '0.3rem 0.4rem', textAlign: 'right' }}>Dwell</th>
                    <th style={{ padding: '0.3rem 0.4rem', textAlign: 'right' }}>Users</th>
                    <th style={{ padding: '0.3rem 0', textAlign: 'right' }}>Visits</th>
                  </tr>
                </thead>
                <tbody>
                  {data.modules.map(m => (
                    <tr key={m.module} style={{ borderTop: '1px dashed var(--hairline, #444)' }}>
                      <td style={{ padding: '0.32rem 0.4rem 0.32rem 0' }}>
                        <span style={{ marginRight: '0.3rem' }}>{MODULE_EMOJI[m.module] || '📄'}</span>
                        {m.module}
                      </td>
                      <td style={{ padding: '0.32rem 0.4rem', textAlign: 'right' }}>{formatDur(m.total_sec)}</td>
                      <td style={{ padding: '0.32rem 0.4rem', textAlign: 'right' }}>{m.users}</td>
                      <td style={{ padding: '0.32rem 0', textAlign: 'right' }}>{m.sessions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ padding: '0.7rem 0.9rem', border: '1px solid var(--rule, #ddd)', borderRadius: 5, background: 'var(--bg-raised)' }}>
      <div className="eyebrow" style={{ fontSize: '0.66rem' }}>{label}</div>
      <div style={{ font: '700 1.4rem var(--serif, serif)', marginTop: 2 }}>{value}</div>
      {sub && <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function UserRowCard({ row, maxSec }: { row: UserRow; maxSec: number }) {
  const sortedModules = Object.entries(row.modules || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const totalShown = sortedModules.reduce((s, [, v]) => s + v, 0);
  return (
    <div style={{ padding: '0.55rem 0.7rem', background: 'rgba(255,255,255,0.02)', borderRadius: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.4rem' }}>
        <strong style={{ fontSize: '0.85rem' }}>{row.email}</strong>
        <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>
          {formatDur(row.total_sec)} · {row.sessions} visits · last seen {formatLast(row.last_seen_iso)}
        </span>
      </div>
      {/* Per-user "where they spent time" bar */}
      <div style={{
        height: 18, display: 'flex', borderRadius: 3, overflow: 'hidden',
        marginTop: '0.4rem', background: 'var(--rule, #333)',
      }}>
        {sortedModules.map(([m, sec]) => {
          const widthPct = totalShown > 0 ? (sec / totalShown) * 100 : 0;
          return (
            <div
              key={m}
              title={`${m}: ${formatDur(sec)} (${widthPct.toFixed(0)}%)`}
              style={{
                width: `${widthPct}%`,
                background: moduleColor(m),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.6rem', color: '#fff', overflow: 'hidden',
              }}
            >
              {widthPct >= 12 && <span>{MODULE_EMOJI[m] || ''}{m}</span>}
            </div>
          );
        })}
      </div>
      {/* Relative bar vs top user */}
      <div style={{ height: 3, background: 'var(--rule, #333)', marginTop: 4, borderRadius: 2 }}>
        <div style={{
          width: `${(row.total_sec / maxSec) * 100}%`,
          height: '100%',
          background: 'var(--positive, #10b981)',
          borderRadius: 2,
          opacity: 0.5,
        }} />
      </div>
    </div>
  );
}

function moduleColor(module: string): string {
  // Deterministic-ish color per module name (hash → hue).
  let h = 0;
  for (let i = 0; i < module.length; i++) h = (h * 31 + module.charCodeAt(i)) & 0xffff;
  const hue = h % 360;
  return `hsl(${hue}, 55%, 45%)`;
}
