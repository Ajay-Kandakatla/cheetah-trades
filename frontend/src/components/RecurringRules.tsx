/* RecurringRules — user-managed day-of-week recurring todo templates.
 *
 * Renders below the regular todo list. Each rule fires a todo on the
 * selected days at the selected time; the 6 AM ET cron
 * (backend/todos/daily_recurring.py) materializes them. After adding
 * a rule whose fire-time is later today, "↻ Add today's batch" runs
 * the materializer immediately so the user doesn't have to wait until
 * tomorrow morning to see today's instance show up.
 *
 * Day-of-week numbering: Monday=0, Sunday=6 (matches Python weekday()).
 * JS getDay returns 0=Sunday — translation happens in this component
 * so the rest of the code can stay Python-aligned.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Rule = {
  _id:           string;
  text:          string;
  days_of_week:  number[];     // 0=Mon … 6=Sun
  hour:          number;       // 0..23 (ET)
  minute:        number;       // 0..59
  important:     boolean;
  ticker:        string | null;
  active:        boolean;
};

// Index 0 = Monday. Frontend display only; backend uses these same indices.
const DAYS = [
  { i: 0, short: 'M',  long: 'Monday' },
  { i: 1, short: 'T',  long: 'Tuesday' },
  { i: 2, short: 'W',  long: 'Wednesday' },
  { i: 3, short: 'Th', long: 'Thursday' },
  { i: 4, short: 'F',  long: 'Friday' },
  { i: 5, short: 'Sa', long: 'Saturday' },
  { i: 6, short: 'Su', long: 'Sunday' },
];

const PRESETS: { label: string; days: number[] }[] = [
  { label: 'Every day',       days: [0, 1, 2, 3, 4, 5, 6] },
  { label: 'Weekdays',        days: [0, 1, 2, 3, 4] },
  { label: 'Weekends',        days: [5, 6] },
];

/** "MTWTF" / "SaSu" / "Daily" — compact label for a set of days. */
function daysLabel(days: number[]): string {
  if (days.length === 7) return 'Daily';
  if (days.length === 5 && [0,1,2,3,4].every((d) => days.includes(d))) return 'Weekdays';
  if (days.length === 2 && days.includes(5) && days.includes(6)) return 'Weekends';
  return days.map((d) => DAYS[d].short).join(' ');
}

function fmtTime(hour: number, minute: number): string {
  const h12 = ((hour + 11) % 12) + 1;
  const suffix = hour < 12 ? 'AM' : 'PM';
  return `${h12}:${String(minute).padStart(2, '0')} ${suffix} ET`;
}

/** "09:30" → {hour: 9, minute: 30}. Returns null on parse failure. */
function parseTimeInput(s: string): { hour: number; minute: number } | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (Number.isNaN(h) || Number.isNaN(min)) return null;
  if (h < 0 || h > 23 || min < 0 || min > 59) return null;
  return { hour: h, minute: min };
}

function fmtTimeInput(hour: number, minute: number): string {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

export function RecurringRules() {
  const [rules, setRules]   = useState<Rule[] | null>(null);
  const [err,   setErr]     = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const refresh = async () => {
    try {
      const r = await fetch(`${API}/todos/recurring`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setRules(j.rules || []);
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  };

  useEffect(() => { void refresh(); }, []);

  const deleteRule = async (id: string) => {
    if (!confirm('Delete this recurring rule?')) return;
    try {
      await fetch(`${API}/todos/recurring/${id}`, { method: 'DELETE' });
      await refresh();
    } catch (e: any) { setErr(String(e?.message || e)); }
  };

  const toggleActive = async (rule: Rule) => {
    try {
      await fetch(`${API}/todos/recurring/${rule._id}`, {
        method:  'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ active: !rule.active }),
      });
      await refresh();
    } catch (e: any) { setErr(String(e?.message || e)); }
  };

  /** Run today's materializer — useful after adding a rule whose
   *  fire-time is later today; the daily cron won't run again until
   *  tomorrow morning. Idempotent on the backend so a double-click
   *  is harmless. */
  const materializeNow = async () => {
    try {
      const r = await fetch(`${API}/todos/recurring/materialize`, { method: 'POST' });
      const j = await r.json();
      if (j.inserted > 0) {
        alert(`Created ${j.inserted} todo${j.inserted === 1 ? '' : 's'} for today.`);
      } else {
        alert(
          `No new todos created. ` +
          `${j.skipped_exists || 0} already existed, ${j.skipped_past || 0} are past their fire time.`,
        );
      }
    } catch (e: any) { setErr(String(e?.message || e)); }
  };

  return (
    <section style={{ marginTop: '1.5rem', padding: '0.85rem 1.05rem', border: '1px solid var(--rule, #333)', borderRadius: 6, background: 'var(--bg-raised, #181818)' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
        <div>
          <div className="eyebrow">№ Recurring rules</div>
          <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.15rem' }}>Weekly schedule</h2>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button
            onClick={() => setAdding((v) => !v)}
            className="sepa-btn"
            style={{ minHeight: 36, fontSize: '0.84rem' }}
          >
            {adding ? 'Cancel' : '+ Add rule'}
          </button>
          <button
            onClick={materializeNow}
            className="sepa-btn"
            style={{ minHeight: 36, fontSize: '0.84rem' }}
            title="Run today's rule check now — picks up any rule fire-time later today without waiting for tomorrow's 6 AM cron."
          >
            ↻ Add today's batch
          </button>
        </div>
      </header>

      {err && (
        <div style={{ color: 'var(--negative)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>{err}</div>
      )}

      {adding && (
        <AddRuleForm
          onAdded={async () => { setAdding(false); await refresh(); }}
          onError={(m) => setErr(m)}
        />
      )}

      {rules == null && <div style={{ color: 'var(--cm-slate)' }}>Loading rules…</div>}
      {rules && rules.length === 0 && !adding && (
        <p style={{ fontSize: '0.84rem', color: 'var(--cm-slate)', margin: '0.4rem 0' }}>
          No recurring rules yet. Tap <strong>+ Add rule</strong> to create one — e.g.,
          "Take out trash" every Tuesday at 9 AM, or "Volleyball court payment" every Saturday at 9 PM.
        </p>
      )}

      {rules && rules.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.45rem' }}>
          {rules.map((r) => (
            <li
              key={r._id}
              style={{
                display: 'grid',
                gridTemplateColumns: 'auto 1fr auto auto',
                gap: '0.6rem',
                alignItems: 'center',
                padding: '0.45rem 0.6rem',
                border: '1px solid var(--rule, #2a2a2a)',
                borderRadius: 4,
                background: r.active ? 'rgba(255,255,255,0.02)' : 'rgba(120,120,120,0.04)',
                opacity: r.active ? 1 : 0.6,
              }}
            >
              <span
                style={{
                  fontSize: '0.66rem',
                  padding: '1px 6px',
                  background: 'rgba(212,175,55,0.1)',
                  color: 'var(--warn, #d97706)',
                  border: '1px solid rgba(212,175,55,0.3)',
                  borderRadius: 3,
                  whiteSpace: 'nowrap',
                }}
              >
                {daysLabel(r.days_of_week)}
              </span>
              <div>
                <div style={{ fontSize: '0.9rem' }}>
                  {r.important && <span style={{ color: 'var(--warn, #d97706)', marginRight: '0.3rem' }}>★</span>}
                  {r.text}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>
                  {fmtTime(r.hour, r.minute)}
                </div>
              </div>
              <button
                onClick={() => toggleActive(r)}
                style={{
                  background: 'none',
                  border: '1px solid var(--rule, #555)',
                  color: 'var(--cm-slate)',
                  padding: '2px 8px',
                  borderRadius: 3,
                  cursor: 'pointer',
                  fontSize: '0.7rem',
                }}
                title={r.active ? 'Pause this rule' : 'Reactivate this rule'}
              >
                {r.active ? '⏸ pause' : '▶ resume'}
              </button>
              <button
                onClick={() => deleteRule(r._id)}
                style={{
                  background: 'none',
                  border: '1px solid var(--rule, #555)',
                  color: 'var(--negative)',
                  padding: '2px 8px',
                  borderRadius: 3,
                  cursor: 'pointer',
                  fontSize: '0.7rem',
                }}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.7rem', lineHeight: 1.5 }}>
        Rules materialize as actual todos at 6 AM ET each day. Push notifications respect the time
        you set; toggle "Todo reminders" in <a href="/notifications" style={{ color: 'inherit' }}>Notifications</a>
        if you want or don't want phone pings.
      </p>
    </section>
  );
}

// ── Add-rule form ──────────────────────────────────────────────────────
function AddRuleForm({
  onAdded,
  onError,
}: {
  onAdded: () => void;
  onError: (msg: string) => void;
}) {
  const [text, setText]       = useState('');
  const [days, setDays]       = useState<number[]>([]);
  const [time, setTime]       = useState('09:00');
  const [important, setImportant] = useState(false);
  const [busy, setBusy]       = useState(false);

  const toggleDay = (i: number) => {
    setDays((prev) => prev.includes(i) ? prev.filter((d) => d !== i) : [...prev, i].sort());
  };
  const applyPreset = (preset: number[]) => setDays(preset);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    onError('');
    if (!text.trim()) { onError('Add some text.'); return; }
    if (days.length === 0) { onError('Pick at least one day.'); return; }
    const parsed = parseTimeInput(time);
    if (!parsed) { onError('Time must be HH:MM.'); return; }

    setBusy(true);
    try {
      const r = await fetch(`${API}/todos/recurring`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          text:         text.trim(),
          days_of_week: days,
          hour:         parsed.hour,
          minute:       parsed.minute,
          important,
        }),
      });
      const j = await r.json();
      if (!r.ok || !j.ok) {
        onError(j.reason || `HTTP ${r.status}`);
        return;
      }
      // Reset + collapse.
      setText(''); setDays([]); setTime('09:00'); setImportant(false);
      onAdded();
    } catch (err: any) {
      onError(String(err?.message || err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: '0.55rem', padding: '0.6rem 0.7rem', border: '1px dashed var(--rule, #444)', borderRadius: 4, marginBottom: '0.7rem' }}>
      <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.8rem' }}>
        <span className="eyebrow">Text</span>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g., Take out trash"
          maxLength={300}
          style={{
            padding: '0.45rem 0.6rem',
            background: 'var(--bg, #0f0f0f)',
            color: 'inherit',
            border: '1px solid var(--rule, #444)',
            borderRadius: 4,
            fontFamily: 'inherit',
            fontSize: '0.92rem',
          }}
        />
      </label>

      <div style={{ display: 'grid', gap: '0.25rem', fontSize: '0.8rem' }}>
        <span className="eyebrow">Days</span>
        {/* Day chips — Monday-first to match Python weekday(). Each is a
            toggleable pill so the user can build any combo (Tue+Thu,
            M-F+Sa, etc.). Presets below set common combinations. */}
        <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
          {DAYS.map((d) => {
            const on = days.includes(d.i);
            return (
              <button
                key={d.i}
                type="button"
                onClick={() => toggleDay(d.i)}
                title={d.long}
                style={{
                  width: 34, height: 34,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  background: on ? 'var(--positive, #10b981)' : 'transparent',
                  border: `1px solid ${on ? 'var(--positive, #10b981)' : 'var(--rule, #555)'}`,
                  color: on ? '#fff' : 'var(--ink, inherit)',
                  borderRadius: 17,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  fontSize: '0.78rem',
                  fontWeight: on ? 700 : 500,
                }}
              >
                {d.short}
              </button>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.2rem', flexWrap: 'wrap' }}>
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => applyPreset(p.days)}
              style={{
                background: 'none',
                border: '1px dashed var(--rule, #555)',
                color: 'var(--cm-slate)',
                padding: '2px 8px',
                borderRadius: 3,
                cursor: 'pointer',
                fontSize: '0.7rem',
                fontFamily: 'inherit',
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.8rem' }}>
        <span className="eyebrow">Time (ET)</span>
        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          style={{
            padding: '0.45rem 0.6rem',
            background: 'var(--bg, #0f0f0f)',
            color: 'inherit',
            border: '1px solid var(--rule, #444)',
            borderRadius: 4,
            fontFamily: 'inherit',
            fontSize: '0.92rem',
            width: 140,
          }}
        />
      </label>

      <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', fontSize: '0.84rem', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={important}
          onChange={(e) => setImportant(e.target.checked)}
          style={{ width: 16, height: 16 }}
        />
        Pin to top of the daily list (important)
      </label>

      <div>
        <button
          type="submit"
          disabled={busy}
          className="sepa-btn sepa-btn--primary"
          style={{ minHeight: 38, padding: '0.45rem 1rem', fontSize: '0.86rem' }}
        >
          {busy ? '…adding' : 'Add rule'}
        </button>
      </div>
    </form>
  );
}

// Helper kept here too so the parsed input survives a future refactor.
// fmtTimeInput / parseTimeInput aren't currently exported.
export { fmtTimeInput, parseTimeInput };
