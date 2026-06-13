/* Notifications settings — manage every registered push device + every
   notification category. One row per device (iPhone PWA, Mac native app,
   Android PWA, etc.) with toggles per category, quiet hours, test push,
   and unsubscribe.

   Replaced the old single-device manager. The hook does optimistic
   updates so toggles feel instant — they revert only if the server fails.
*/
import { useState } from 'react';
import { useNotificationPrefs, type DeviceRow, type NotificationPrefs } from '../hooks/useNotificationPrefs';
import { subscribePush, pushSupported, isStandalone } from '../lib/pushSubscribe';
import { useCurrentUser } from '../hooks/useUser';
import { useAlertSettings } from '../hooks/useAlertSettings';
import { InstallToHomeScreen, clearInstallDismissal, isIPhone } from '../components/InstallToHomeScreen';
import { PushHistoryPanel } from '../components/PushHistoryPanel';

/* ── Category catalogue — keys match backend default_prefs() ─────────── */
type CategoryDef = {
  key:    keyof NotificationPrefs;
  label:  string;
  detail: string;
  group:  'trading' | 'household' | 'admin';
  emoji:  string;
};

const CATEGORIES: CategoryDef[] = [
  // Trading alerts pared to the essentials (Ajay 2026-06-13). The breakout /
  // momentum / new-candidate / stage-breakdown / product-launch / tape-watch /
  // morning-brief pushes were retired here AND hard-stopped server-side
  // (backend/push/subs.py DISABLED_ALERT_KINDS — they can't fire even for a
  // device that still has an old toggle on). price_alert is PAUSED — it returns
  // when custom price alerts come back.
  { key: 'pivot_alert', label: 'Buyable / Enter-zone alerts', emoji: '🎯', group: 'trading',
    detail: 'At-the-pivot (buyable names only) and approaching-pivot buy-stop alerts from the 5-min market-hours cron. Once per name per kind per day.' },
  { key: 'position_alert', label: 'Portfolio alerts', emoji: '💼', group: 'trading',
    detail: 'Stop / target hit on the positions you hold — the up/down moves on your portfolio that need action.' },
  { key: 'minervini_flashcards', label: 'Minervini learning', emoji: '🃏', group: 'trading',
    detail: 'Hourly bite-sized lessons (24h schedule): entry rules, risk, sell rules, psychology, review, fundamentals, market structure, trader history, edge math. ~80 cards, ~2-3 week rotation. Quiet-hours pref below mutes overnight delivery.' },
  { key: 'market_hours_reminder', label: 'Market open / close reminders', emoji: '🔔', group: 'trading',
    detail: '15 min before the bell each weekday — 9:15 AM ET (open) and 3:45 PM ET (close). Skips US market holidays. Open ping routes to /morning brief; close ping routes to /sepa for position management.' },
  { key: 'vb_workout', label: 'Volleyball · daily workout', emoji: '🏐', group: 'household',
    detail: '7 AM ET daily brief — today\'s workout focus, duration, AM supplement reminder (D3/K2 + Moringa). Routes to /volleyball.' },
  { key: 'vb_supplement', label: 'Volleyball · supplements', emoji: '💊', group: 'household',
    detail: '9:30 PM ET Magnesium Glycinate before-bed reminder. The other supplements (D3/K2 + Moringa) are folded into the morning workout ping so this single toggle covers evening only.' },
  { key: 'vb_education', label: 'Volleyball · daily card', emoji: '📖', group: 'household',
    detail: '6 PM ET one card per day from the volleyball/health bank — shoulder durability, finger plantar plate, jump training, recovery, supplements, technique, longevity. ~30-card library, day-of-year rotation.' },
  { key: 'todo_reminder',          label: 'Todo reminders',         emoji: '📌', group: 'household',
    detail: 'Personal todo list reminders fired at the time you set per task.' },
  { key: 'todo_daily_digest',      label: 'Todo daily digest',      emoji: '📋', group: 'household',
    detail: '7 AM ET daily summary of all open todos for the day.' },
  // 'macbook_deal' category removed 2026-05-15 along with the lifeboard
  // Mac deal scraper module.

  // Real-estate (house) notifications — only delivered to HOUSE_OWNER_EMAIL
  // because the daily_scrape cron pushes via send_to_user(owner, ...).
  // Toggles still render for non-owners (no harm) but they'd never fire.
  { key: 'house_daily',            label: 'House · daily summary',  emoji: '🏡', group: 'household',
    detail: '8 AM ET listing summary — views, saves, tours, offers, day-over-day delta. Pulled from Redfin/Zillow/Realtor.' },
  { key: 'house_scrape_failed',    label: 'House · scrape failed',  emoji: '⚠️', group: 'household',
    detail: 'Fires only when all three scrapers (Redfin, Zillow, Realtor) come back empty so you know to enter numbers manually.' },
  { key: 'house_stagnant',         label: 'House · engagement stalled', emoji: '📉', group: 'household',
    detail: '3+ consecutive days without any new views. Nudge to consider a price drop, fresh photos, or an open-house push.' },

  // Admin-only category — only visible to ADMIN_EMAILS.
  { key: 'user_signin',            label: 'New user signed in',     emoji: '👋', group: 'admin',
    detail: 'One-time push when a new email signs in for the first time. Fires exactly once per user. Visible only to admins.' },
];

const GROUP_LABELS: Record<CategoryDef['group'], string> = {
  trading:   'Trading signals',
  household: 'Household & deals',
  admin:     'Admin',
};

export default function NotificationsPage() {
  const { rows, error, busy, refresh, togglePref, setManyPrefs, setQuietHours, unsubscribe, sendTest } = useNotificationPrefs();
  const { user } = useCurrentUser();
  const isAdmin = !!user?.is_admin;
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addOk, setAddOk] = useState(false);
  // When a user wants to re-read the iOS / Android install steps —
  // typically after they tapped "Got it" on the first-run prompt and
  // need a refresher. Clearing the dismissal flag too so a phone
  // restart-and-revisit also re-triggers the prompt if they still
  // haven't installed.
  const [showInstall, setShowInstall] = useState(false);
  const openInstallGuide = () => {
    clearInstallDismissal();
    setShowInstall(true);
  };

  const addThisDevice = async () => {
    setAdding(true); setAddError(null); setAddOk(false);
    try {
      if (!pushSupported()) {
        setAddError('This browser does not support web push. Use Chrome / Safari (iOS as PWA).');
        return;
      }
      const r = await subscribePush('Pounce · ' + (navigator.userAgent.slice(0, 100)));
      if (!r.ok) {
        setAddError(r.reason || 'Subscription failed');
        return;
      }
      setAddOk(true);
      await refresh();
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 920, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '1rem' }}>
        <div className="cm-pagehead__col">
          <div className="eyebrow">№ Notifications · subscribe / unsubscribe</div>
          <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>Notifications</h1>
          <p className="lede">
            One card per device. Toggle each category to control what pings what. Changes save instantly.
          </p>
        </div>
      </header>

      {/* Recent pushes — full untruncated bodies. Lives at the TOP so the
          user lands on the most-asked-for info ("what was that notification
          that just got clipped on my lock screen?") before scrolling
          through pref toggles. */}
      <PushHistoryPanel limit={25} />

      {/* Add this device card */}
      <section style={{
        marginBottom: '1rem', padding: '0.9rem 1.1rem',
        border: '1px solid var(--rule, #ddd)', borderLeft: '4px solid var(--positive, #10b981)',
        borderRadius: 5, background: 'var(--bg-raised)',
      }}>
        <div className="eyebrow" style={{ color: 'var(--positive)' }}>Add this device</div>
        <p style={{ fontSize: '0.84rem', margin: '0.4rem 0 0.6rem' }}>
          If this browser / PWA isn't in the list below, subscribe it now. Android works in Chrome directly.
          iOS needs the app installed as a PWA first (Share → Add to Home Screen).
        </p>
        <button
          onClick={addThisDevice}
          disabled={adding}
          className="sepa-btn sepa-btn--primary"
          style={{ minHeight: 40 }}
        >
          {adding ? '…subscribing' : '🔔 Subscribe this device'}
        </button>
        {!isStandalone() && /iPhone|iPad/.test(navigator.userAgent) && (
          <div style={{ fontSize: '0.78rem', color: 'var(--warn, #d97706)', marginTop: '0.5rem' }}>
            ⚠ iOS: install as PWA first (Safari Share → Add to Home Screen), then open the PWA and subscribe from there. Subscribing in Safari directly won't deliver pushes.
          </div>
        )}
        {/* Walkthrough — iPhone only. Android Chrome and desktop browsers
            deliver push to a regular tab; they don't need this guide, and
            showing the button there is confusing. The auto-show prompt
            uses the same gate (see shouldAutoShowInstallPrompt). */}
        {isIPhone() && (
          <button
            onClick={openInstallGuide}
            style={{
              marginTop: '0.6rem',
              background: 'none',
              border: '1px dashed var(--rule, #555)',
              color: 'var(--ink, inherit)',
              padding: '0.5rem 0.75rem',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontFamily: 'inherit',
            }}
          >
            📱 Show install instructions (Add to Home Screen)
          </button>
        )}
        {addError && <div style={{ color: 'var(--negative)', fontSize: '0.8rem', marginTop: '0.4rem' }}>{addError}</div>}
        {addOk && <div style={{ color: 'var(--positive)', fontSize: '0.8rem', marginTop: '0.4rem' }}>✓ Subscribed — see the device card below.</div>}
      </section>

      {/* The modal is force-opened from the button above, so it bypasses
          the auto-show gates (won't refuse to render on desktop or in
          standalone mode). User explicitly asked to see it. */}
      {showInstall && (
        <InstallToHomeScreen forceOpen onClose={() => setShowInstall(false)} />
      )}

      {error && (
        <div style={{ padding: '0.5rem 0.8rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 4, color: 'var(--negative)', marginBottom: '1rem', fontSize: '0.85rem' }}>
          {error} · <button onClick={refresh} style={{ color: 'inherit', background: 'none', border: 0, textDecoration: 'underline', cursor: 'pointer' }}>retry</button>
        </div>
      )}

      {rows === null && <div style={{ color: 'var(--cm-slate)' }}>Loading devices…</div>}

      {rows && rows.length === 0 && (
        <div style={{ padding: '1rem 1.2rem', border: '1px dashed var(--rule, #444)', borderRadius: 6, color: 'var(--cm-slate)', textAlign: 'center' }}>
          No devices subscribed yet. Tap "Subscribe this device" above.
        </div>
      )}

      {/* Alert thresholds — global to the user. Drives the -12% intraday
          chip on every SEPA card; tightening it (e.g. to -10%) flows
          through all cards instantly via the cached settings store. */}
      <AlertThresholdsSection />

      {rows && rows.map((row) => (
        <DeviceCard
          key={row.endpoint}
          row={row}
          busy={busy === row.endpoint}
          isAdmin={isAdmin}
          onToggle={(k) => togglePref(row.endpoint, k)}
          onMany={(updates) => setManyPrefs(row.endpoint, updates)}
          onQuietHours={(fields) => setQuietHours(row.endpoint, fields)}
          onTest={() => sendTest(row)}
          onRemove={() => {
            if (confirm(`Remove ${row.label || row.endpoint_short}? Notifications will stop on this device.`)) {
              unsubscribe(row);
            }
          }}
        />
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────── */
/* ────────────────────────────────────────────────────────────────────── */
function AlertThresholdsSection() {
  const { settings, update, busy } = useAlertSettings();

  // Preset chips for the intraday emergency — most users want a one-tap
  // pick, not a slider. The custom input is below for fine-tuning.
  const EMERGENCY_PRESETS: { value: number; label: string; sub: string }[] = [
    { value: 8,  label: '−8%',  sub: 'tight · low volatility names' },
    { value: 10, label: '−10%', sub: 'moderate · most growth stocks' },
    { value: 12, label: '−12%', sub: 'Minervini default' },
    { value: 15, label: '−15%', sub: 'loose · high-vol / leveraged' },
  ];

  return (
    <section style={{
      marginBottom: '1rem', padding: '0.9rem 1.1rem',
      border: '1px solid var(--rule, #ddd)', borderLeft: '4px solid var(--warn, #d97706)',
      borderRadius: 5, background: 'var(--bg-raised)',
    }}>
      <div className="eyebrow" style={{ color: 'var(--warn, #d97706)' }}>
        ⚙️ Alert thresholds
      </div>
      <p style={{ fontSize: '0.82rem', margin: '0.4rem 0 0.8rem' }}>
        Customize the <strong>⚠ Exit</strong> level shown on every SEPA card.
        Tightening to −8% means earlier alerts at the cost of more shakeouts;
        loosening to −15% gives volatile names breathing room.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.45rem', marginBottom: '0.7rem' }}>
        {EMERGENCY_PRESETS.map(p => {
          const active = Math.abs(settings.intraday_emergency_pct - p.value) < 0.01;
          return (
            <button
              key={p.value}
              onClick={() => update({ intraday_emergency_pct: p.value })}
              disabled={busy}
              style={{
                padding: '0.55rem 0.5rem',
                background: active ? 'rgba(217, 119, 6, 0.12)' : 'transparent',
                border: '2px solid',
                borderColor: active ? 'var(--warn, #d97706)' : 'var(--rule, #555)',
                borderRadius: 5,
                cursor: 'pointer', fontFamily: 'inherit',
                color: 'inherit',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: active ? 'var(--warn)' : 'inherit' }}>
                {p.label}
              </div>
              <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: 2 }}>
                {p.sub}
              </div>
            </button>
          );
        })}
      </div>

      {/* Fine-tune slider */}
      <div style={{ marginTop: '0.5rem' }}>
        <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ flexShrink: 0, color: 'var(--cm-slate)' }}>Fine tune:</span>
          <input
            type="range"
            min="5"
            max="20"
            step="0.5"
            value={settings.intraday_emergency_pct}
            onChange={(e) => update({ intraday_emergency_pct: Number(e.target.value) })}
            style={{ flex: 1 }}
          />
          <span className="mono" style={{ minWidth: 50, textAlign: 'right', color: 'var(--warn)' }}>
            −{settings.intraday_emergency_pct}%
          </span>
        </label>
      </div>

      {/* Secondary thresholds — collapsed under a "More" disclosure to
          avoid overwhelming the casual user. */}
      <details style={{ marginTop: '0.7rem' }}>
        <summary style={{ cursor: 'pointer', fontSize: '0.75rem', color: 'var(--cm-slate)' }}>
          More thresholds
        </summary>
        <div style={{ marginTop: '0.5rem', display: 'grid', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ flexShrink: 0, color: 'var(--cm-slate)', width: 130 }}>Early warning:</span>
            <input
              type="range" min="3" max="15" step="0.5"
              value={settings.intraday_warning_pct}
              onChange={(e) => update({ intraday_warning_pct: Number(e.target.value) })}
              style={{ flex: 1 }}
            />
            <span className="mono" style={{ minWidth: 50, textAlign: 'right' }}>−{settings.intraday_warning_pct}%</span>
          </label>
          <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginLeft: 130 }}>
            Push fires when an intraday move crosses this threshold — earlier signal before the structural emergency.
          </div>

          <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ flexShrink: 0, color: 'var(--cm-slate)', width: 130 }}>Stop buffer:</span>
            <input
              type="range" min="0" max="5" step="0.25"
              value={settings.stop_close_buffer_pct}
              onChange={(e) => update({ stop_close_buffer_pct: Number(e.target.value) })}
              style={{ flex: 1 }}
            />
            <span className="mono" style={{ minWidth: 50, textAlign: 'right' }}>{settings.stop_close_buffer_pct}%</span>
          </label>
          <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginLeft: 130 }}>
            Notify when price closes within this % of your stop level.
          </div>
        </div>
      </details>
    </section>
  );
}

/* Presets — one-tap configurations of the per-category toggles. */
const PRESETS: { id: string; label: string; emoji: string; detail: string; pref: Partial<NotificationPrefs> }[] = [
  {
    id: 'all_on', label: 'All on', emoji: '🟢',
    detail: 'Every trading + household notification enabled.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, true])) as any,
  },
  {
    id: 'all_off', label: 'All off', emoji: '🔇',
    detail: 'Mute everything. Subscription stays active but no pushes will fire.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, false])) as any,
  },
  {
    id: 'essentials', label: 'Essentials only', emoji: '🎯',
    detail: 'High-signal only: buyable / Enter-zone + portfolio stops.',
    pref: {
      pivot_alert: true, position_alert: true,
      minervini_flashcards: false, market_hours_reminder: false,
      todo_reminder: false, todo_daily_digest: true,
    },
  },
  {
    id: 'trading_only', label: 'Trading only', emoji: '📈',
    detail: 'All trading alerts on, household off.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, c.group === 'trading'])) as any,
  },
  {
    id: 'household_only', label: 'Household only', emoji: '🏠',
    detail: 'All household + deals on, no market noise.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, c.group === 'household'])) as any,
  },
];

function DeviceCard({ row, busy, isAdmin, onToggle, onMany, onQuietHours, onTest, onRemove }: {
  row: DeviceRow;
  busy: boolean;
  isAdmin: boolean;
  onToggle: (key: keyof NotificationPrefs) => void;
  onMany: (updates: Partial<NotificationPrefs>) => void;
  onQuietHours: (fields: Partial<NotificationPrefs>) => void;
  onTest: () => void;
  onRemove: () => void;
}) {
  const created = row.created_at ? new Date(row.created_at * 1000).toLocaleDateString() : '?';
  const prefs = row.prefs || {};
  const kindLabel = row.kind === 'mac' ? '🖥️ Mac native' : '🌐 Web/PWA';
  // Guess platform from UA label
  const platform =
    row.label?.includes('iPhone') ? '📱 iPhone' :
    row.label?.includes('Android') ? '📱 Android' :
    row.label?.includes('Macintosh') ? '🖥️ Mac' :
    row.label?.includes('Windows') ? '🖥️ Windows' :
    null;

  return (
    <section style={{
      marginBottom: '1rem', padding: '0.9rem 1.1rem',
      border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)',
      opacity: busy ? 0.6 : 1, transition: 'opacity 0.15s',
    }}>
      {/* Device header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.8rem' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: '1rem' }}>{platform || kindLabel}</strong>
            <span className="mono" style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>
              {kindLabel} · added {created}
            </span>
          </div>
          {row.label && (
            <div style={{ fontSize: '0.72rem', color: 'var(--cm-slate)', marginTop: 2, wordBreak: 'break-word' }}>
              {row.label.slice(0, 120)}
            </div>
          )}
          <div className="mono" style={{ fontSize: '0.62rem', color: 'var(--cm-slate)', marginTop: 2 }}>
            …{row.endpoint_short}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
          <button onClick={onTest} className="sepa-btn" style={{ fontSize: '0.78rem' }} title="Send a test notification to this device">
            🔔 Test
          </button>
          <button onClick={onRemove} className="sepa-btn" style={{ fontSize: '0.78rem', color: 'var(--negative)' }} title="Unsubscribe this device entirely">
            ✕ Remove
          </button>
        </div>
      </div>

      {/* Preset bar — one-tap multi-category sets */}
      <div style={{
        marginBottom: '0.8rem', padding: '0.5rem 0.6rem',
        background: 'rgba(255,255,255,0.02)',
        border: '1px dashed var(--rule, #444)', borderRadius: 4,
      }}>
        <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.35rem' }}>
          Presets — one-tap configurations
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
          {PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => onMany(p.pref)}
              title={p.detail}
              style={{
                padding: '4px 10px', fontSize: '0.72rem',
                background: 'transparent',
                border: '1px solid var(--rule, #555)',
                borderRadius: 3, color: 'inherit',
                cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              {p.emoji} {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Category toggles, grouped. Admin group only shown to admins. */}
      {(['trading', 'household', 'admin'] as const).map((group) => {
        if (group === 'admin' && !isAdmin) return null;
        const cats = CATEGORIES.filter(c => c.group === group);
        if (cats.length === 0) return null;
        const onCount = cats.filter(c => prefs[c.key] !== false).length;
        const allOn = onCount === cats.length;
        const allOff = onCount === 0;
        return (
          <div key={group} style={{ marginBottom: '0.7rem' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '0.3rem', flexWrap: 'wrap' }}>
              <h4 style={{ margin: 0, fontSize: '0.78rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {GROUP_LABELS[group]}
              </h4>
              <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>{onCount} of {cats.length} on</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.3rem' }}>
                <button
                  onClick={() => onMany(Object.fromEntries(cats.map(c => [c.key, true])) as any)}
                  disabled={allOn}
                  style={{
                    fontSize: '0.66rem', padding: '2px 8px',
                    background: 'none', border: '1px solid var(--rule, #555)',
                    color: allOn ? 'var(--cm-slate)' : 'inherit',
                    borderRadius: 3, cursor: allOn ? 'default' : 'pointer',
                    opacity: allOn ? 0.5 : 1,
                  }}
                  title={`Turn on all ${cats.length} ${group} notifications`}
                >✓ all</button>
                <button
                  onClick={() => onMany(Object.fromEntries(cats.map(c => [c.key, false])) as any)}
                  disabled={allOff}
                  style={{
                    fontSize: '0.66rem', padding: '2px 8px',
                    background: 'none', border: '1px solid var(--rule, #555)',
                    color: allOff ? 'var(--cm-slate)' : 'inherit',
                    borderRadius: 3, cursor: allOff ? 'default' : 'pointer',
                    opacity: allOff ? 0.5 : 1,
                  }}
                  title={`Turn off all ${cats.length} ${group} notifications`}
                >✕ none</button>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.3rem' }}>
              {cats.map((c) => {
                const on = prefs[c.key] !== false;
                return (
                  <button
                    key={c.key}
                    onClick={() => onToggle(c.key)}
                    title={c.detail}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: '0.5rem',
                      padding: '0.55rem 0.7rem',
                      background: on ? 'rgba(16, 185, 129, 0.06)' : 'transparent',
                      border: '1px solid',
                      borderColor: on ? 'rgba(16, 185, 129, 0.3)' : 'var(--rule, #444)',
                      borderRadius: 4,
                      color: 'inherit',
                      textAlign: 'left',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}
                  >
                    {/* iOS-style toggle */}
                    <div style={{
                      width: 28, height: 18, borderRadius: 9,
                      background: on ? 'var(--positive, #10b981)' : 'var(--rule, #555)',
                      position: 'relative', flexShrink: 0,
                      transition: 'background 0.15s',
                      marginTop: 1,
                    }}>
                      <div style={{
                        position: 'absolute',
                        width: 14, height: 14, borderRadius: 7,
                        background: '#fff', top: 2, left: on ? 12 : 2,
                        transition: 'left 0.15s',
                      }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.86rem', fontWeight: 600 }}>
                        <span style={{ marginRight: '0.3rem' }}>{c.emoji}</span>
                        {c.label}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 1, lineHeight: 1.4 }}>
                        {c.detail}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Quiet hours */}
      <div style={{
        marginTop: '0.5rem', paddingTop: '0.7rem',
        borderTop: '1px dashed var(--hairline, #444)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
          <strong style={{ fontSize: '0.85rem' }}>🌙 Quiet hours</strong>
          <button
            onClick={() => onQuietHours({ quiet_hours_enabled: !prefs.quiet_hours_enabled })}
            style={{
              padding: '2px 10px', fontSize: '0.72rem',
              border: '1px solid', borderColor: prefs.quiet_hours_enabled ? 'var(--positive)' : 'var(--rule, #444)',
              color: prefs.quiet_hours_enabled ? 'var(--positive)' : 'var(--cm-slate)',
              background: 'none', borderRadius: 3, cursor: 'pointer',
            }}
          >
            {prefs.quiet_hours_enabled ? 'ON' : 'OFF'}
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.78rem', flexWrap: 'wrap' }}>
          <label>
            from{' '}
            <input
              type="time"
              value={prefs.quiet_hours_start || '22:00'}
              onChange={(e) => onQuietHours({ quiet_hours_start: e.target.value })}
              disabled={!prefs.quiet_hours_enabled}
              style={{ padding: '3px 6px', fontSize: '0.78rem' }}
            />
          </label>
          <label>
            until{' '}
            <input
              type="time"
              value={prefs.quiet_hours_end || '08:00'}
              onChange={(e) => onQuietHours({ quiet_hours_end: e.target.value })}
              disabled={!prefs.quiet_hours_enabled}
              style={{ padding: '3px 6px', fontSize: '0.78rem' }}
            />
          </label>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 4 }}>
          During quiet hours, non-urgent notifications are silenced. Position stop/target alerts still fire.
        </div>
      </div>
    </section>
  );
}
