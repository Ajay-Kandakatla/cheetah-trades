/* MarketClockStrip — live clock + countdown to the 4 PM ET close,
   displayed in Central Time because that's where the user lives.

   Anchors all SEPA evaluations: the daily scan re-runs after the
   official close (16:00 ET / 15:00 CT), so until then any rating
   on the cards is based on yesterday's close. This strip makes that
   timing explicit so the user doesn't trust a stale BUY into a
   collapsing intraday tape (the MU lesson).

   Display rules:
     - Pre-market (CT 03:00 – 08:30):    "Pre-market · Opens in 2h 14m"
     - Regular session (08:30 – 15:00):  "Market open · Close in 4h 59m"
     - After hours    (15:00 – 19:00):   "After hours · Closed at 15:00"
     - Closed         (19:00 – 03:00):   "Market closed · Opens in 9h 29m"

   Weekends: always "Market closed · Opens Monday 8:30 AM CT".

   Update cadence: every 30 seconds. No need for second precision — the
   user's decision window is in minutes, and ticking that fast burns
   battery on phones for no real signal.
*/
import { useEffect, useState } from 'react';

type SessionState = {
  label:     string;     // "Market open", "Pre-market", etc.
  detail:    string;     // "Close in 4h 59m", "Opens in 2h 14m", ...
  mood:      'live' | 'pre' | 'after' | 'closed';
  nextScan:  string;     // "Next SEPA rescan: tonight 15:30 CT"
};

// ============================================================================
// US market holidays — full closures only (NYSE + NASDAQ).
// Mirrors backend/market_hours/reminder.py HOLIDAYS_2026/2027. Update yearly
// when NYSE publishes the next year's calendar:
// https://www.nyse.com/markets/hours-calendars
// Keys are YYYY-MM-DD; values are human-readable holiday names for display.
// ============================================================================
const US_MARKET_HOLIDAYS: Record<string, string> = {
  // 2026
  '2026-01-01': "New Year's Day",
  '2026-01-19': 'MLK Jr Day',
  '2026-02-16': 'Presidents Day',
  '2026-04-03': 'Good Friday',
  '2026-05-25': 'Memorial Day',
  '2026-06-19': 'Juneteenth',
  '2026-07-03': 'Independence Day (observed)',
  '2026-09-07': 'Labor Day',
  '2026-11-26': 'Thanksgiving',
  '2026-12-25': 'Christmas',
  // 2027
  '2027-01-01': "New Year's Day",
  '2027-01-18': 'MLK Jr Day',
  '2027-02-15': 'Presidents Day',
  '2027-03-26': 'Good Friday',
  '2027-05-31': 'Memorial Day',
  '2027-06-18': 'Juneteenth (observed)',
  '2027-07-05': 'Independence Day (observed)',
  '2027-09-06': 'Labor Day',
  '2027-11-25': 'Thanksgiving',
  '2027-12-24': 'Christmas (observed)',
};

/** Get YYYY-MM-DD for the given Date in US Eastern (the market's TZ). */
function dateKeyET(d: Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(d);
  const y = parts.find(p => p.type === 'year')?.value;
  const m = parts.find(p => p.type === 'month')?.value;
  const da = parts.find(p => p.type === 'day')?.value;
  return `${y}-${m}-${da}`;
}

/** Return the human-readable holiday name if today is a US market holiday,
 *  else null. */
function todaysHoliday(d: Date): string | null {
  return US_MARKET_HOLIDAYS[dateKeyET(d)] || null;
}

/** Find the next trading day (skips weekends + holidays). Returns a Date
 *  at 08:30 CT (regular session open) of that day, useful for "opens in N". */
function nextTradingDayOpenCT(from: Date): Date {
  const next = new Date(from);
  // Walk forward day-by-day until we hit a weekday that's not a holiday.
  for (let i = 0; i < 10; i++) {
    next.setUTCDate(next.getUTCDate() + 1);
    const k = dateKeyET(next);
    const wd = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', weekday: 'short',
    }).format(next);
    if (wd === 'Sat' || wd === 'Sun') continue;
    if (US_MARKET_HOLIDAYS[k]) continue;
    // Set time to 08:30 CT (= 09:30 ET = 13:30 UTC standard / 14:30 daylight).
    // We don't need exact UTC math — the duration formatter only uses the
    // overall offset. Just stamp 14:30 UTC, which is close enough.
    next.setUTCHours(14, 30, 0, 0);
    return next;
  }
  return next;
}

/** Get the current time parts in a target IANA timezone, regardless
 *  of the user's actual locale. Returns minutes since midnight + a
 *  weekday number (0 = Sunday). */
function timeInTZ(d: Date, tz: string): { minutes: number; weekday: number } {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    weekday:  'short',
    hour:     '2-digit', minute: '2-digit', hour12: false,
  });
  const parts = fmt.formatToParts(d);
  const get = (t: string) => parts.find(p => p.type === t)?.value || '';
  const hh = parseInt(get('hour') === '24' ? '00' : get('hour'), 10);
  const mm = parseInt(get('minute'), 10);
  const weekday = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].indexOf(get('weekday'));
  return { minutes: hh * 60 + mm, weekday };
}

/** Format CT clock time as "10:01 AM CT". */
function fmtCT(d: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago',
    hour:     'numeric',
    minute:   '2-digit',
    hour12:   true,
  }).format(d) + ' CT';
}

function fmtET(d: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour:     'numeric',
    minute:   '2-digit',
    hour12:   true,
  }).format(d) + ' ET';
}

function dur(mins: number): string {
  if (mins < 0) return '0m';
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h === 0) return `${m}m`;
  return `${h}h ${m}m`;
}

function computeSession(d: Date): SessionState {
  const { minutes, weekday } = timeInTZ(d, 'America/Chicago');
  // CT-anchored windows. Regular session 8:30 - 15:00 CT.
  const OPEN  = 8 * 60 + 30;
  const CLOSE = 15 * 60;
  const PRE   = 3 * 60;          // ECN/futures pre-market kickoff
  const AFTER = 19 * 60;         // after-hours session ends

  // Holiday check FIRST — overrides weekday logic. Memorial Day / July 4 /
  // Thanksgiving / Christmas / etc. all show "Market closed (holiday name)"
  // with the next trading-day open time. The session windows below assume
  // a normal trading day, so jumping here for holidays is correct.
  const holiday = todaysHoliday(d);
  if (holiday) {
    const nextOpen = nextTradingDayOpenCT(d);
    const minsToNextOpen = Math.max(0, Math.round((nextOpen.getTime() - d.getTime()) / 60000));
    return {
      label:  `Market closed · ${holiday}`,
      detail: `US market holiday. Opens in ${dur(minsToNextOpen)} (next trading day 8:30 AM CT)`,
      mood:   'closed',
      nextScan: 'No SEPA scan today — next runs after the next session close',
    };
  }

  // Weekend
  if (weekday === 0 || weekday === 6) {
    // Minutes until Monday 8:30 CT.
    const daysToMonday = weekday === 6 ? 2 : 1;
    const minsToMondayOpen = daysToMonday * 24 * 60 + (OPEN - minutes);
    return {
      label:  'Weekend · Market closed',
      detail: `Opens Mon 8:30 AM CT (in ~${Math.floor(minsToMondayOpen / 60)}h)`,
      mood:   'closed',
      nextScan: 'Next SEPA scan: Mon 15:30 CT (after close)',
    };
  }

  if (minutes < PRE) {
    return {
      label:  'Market closed',
      detail: `Pre-market opens in ${dur(PRE - minutes)} (3:00 AM CT)`,
      mood:   'closed',
      nextScan: 'Next SEPA scan: today 15:30 CT (after close)',
    };
  }
  if (minutes < OPEN) {
    return {
      label:  'Pre-market',
      detail: `Opens in ${dur(OPEN - minutes)} (8:30 AM CT / 9:30 AM ET)`,
      mood:   'pre',
      nextScan: 'Next SEPA scan: today 15:30 CT (after close)',
    };
  }
  if (minutes < CLOSE) {
    return {
      label:  'Market open',
      detail: `Close in ${dur(CLOSE - minutes)} (3:00 PM CT / 4:00 PM ET)`,
      mood:   'live',
      nextScan: 'Next SEPA scan: today 15:30 CT (after close)',
    };
  }
  if (minutes < AFTER) {
    return {
      label:  'After hours',
      detail: `Closed at 3:00 PM CT · After-hours ends ${dur(AFTER - minutes)}`,
      mood:   'after',
      nextScan: minutes < (15 * 60 + 30)
        ? 'SEPA scan running soon — fresh ratings shortly'
        : 'SEPA scan ran at 15:30 CT — ratings reflect today\'s close',
    };
  }
  // Late evening through midnight.
  // Tomorrow's open in CT.
  const minsToTomorrowOpen = (24 * 60 - minutes) + OPEN;
  return {
    label:  'Market closed',
    detail: `Opens tomorrow 8:30 AM CT (in ${dur(minsToTomorrowOpen)})`,
    mood:   'closed',
    nextScan: 'SEPA scan ran at 15:30 CT — ratings reflect today\'s close',
  };
}

const moodColor = (m: SessionState['mood']) =>
    m === 'live'   ? 'var(--positive, #10b981)'
  : m === 'pre'    ? 'var(--warn, #d97706)'
  : m === 'after'  ? 'var(--warn, #d97706)'
  :                  'var(--cm-slate, #888)';

export function MarketClockStrip({ compact = false }: { compact?: boolean }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const tick = () => setNow(new Date());
    // Align next tick to the start of the next minute, then run every 30s.
    // Note: in browsers `setTimeout` returns a *number* (the timer id), so
    // we can't stash the interval handle on it as a property — that throws
    // "Cannot create property '_interval' on number" once the runtime hands
    // out a non-zero id. Track both ids in closure scope instead.
    const msToMinute = 60_000 - (Date.now() % 60_000);
    let intervalId: ReturnType<typeof setInterval> | null = null;
    const timeoutId = setTimeout(() => {
      tick();
      intervalId = setInterval(tick, 30_000);
    }, msToMinute);
    return () => {
      clearTimeout(timeoutId);
      if (intervalId != null) clearInterval(intervalId);
    };
  }, []);

  const s = computeSession(now);
  const color = moodColor(s.mood);

  if (compact) {
    return (
      <div className="mono" style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>
        <span style={{ color }}>● {s.label}</span> · {fmtCT(now)} · {s.detail}
      </div>
    );
  }

  return (
    <section
      className="mono"
      style={{
        display: 'flex', flexWrap: 'wrap', alignItems: 'baseline',
        gap: '0.6rem 1rem',
        padding: '0.55rem 0.9rem',
        margin: '0.4rem 0 0.6rem',
        border: '1px solid var(--rule, #ddd)',
        borderLeft: `4px solid ${color}`,
        borderRadius: 4,
        background: 'var(--bg-raised)',
        fontSize: '0.82rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
        <strong style={{ color, fontSize: '0.95rem' }}>● {s.label}</strong>
        <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{fmtCT(now)}</span>
        <span style={{ color: 'var(--cm-slate)', fontSize: '0.7rem' }}>· {fmtET(now)}</span>
      </div>
      <div style={{ flex: 1, color: 'var(--ink)' }}>{s.detail}</div>
      <div style={{ color: 'var(--cm-slate)', fontSize: '0.72rem' }}>{s.nextScan}</div>
    </section>
  );
}
