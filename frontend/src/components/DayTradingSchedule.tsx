/* DayTradingSchedule — session-aware banner explaining WHEN buy signals fire.
 *
 * The intraday strategies need regular-hours price action, so nothing is
 * "buyable" pre-open. This tells the user, live, where we are in the session
 * and when entries start — so the empty Live Signals / Paper sections make
 * sense. Computes the ET session client-side (no backend call), ticks each min.
 */
import { useEffect, useState } from 'react';

type Session = 'premarket' | 'regular' | 'afterhours' | 'closed';

const WD: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

/** Current ET weekday (0=Sun) + minutes since ET midnight. */
function etNow(): { wd: number; mins: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date());
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  const wd = WD[get('weekday')] ?? 1;
  let hour = parseInt(get('hour'), 10);
  if (hour === 24) hour = 0;                 // some engines render midnight as 24
  const minute = parseInt(get('minute'), 10);
  return { wd, mins: hour * 60 + minute };
}

function sessionOf(wd: number, mins: number): Session {
  if (wd === 0 || wd === 6) return 'closed';
  if (mins >= 4 * 60 && mins < 9 * 60 + 30) return 'premarket';
  if (mins >= 9 * 60 + 30 && mins < 16 * 60) return 'regular';
  if (mins >= 16 * 60 && mins < 20 * 60) return 'afterhours';
  return 'closed';
}

export function DayTradingSchedule() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 30_000);
    return () => clearInterval(t);
  }, []);

  const { wd, mins } = etNow();
  const session = sessionOf(wd, mins);

  let cls = 'dts--closed';
  let icon = '🌙';
  let msg: React.ReactNode;

  if (session === 'premarket') {
    cls = 'dts--pre';
    icon = '⏱';
    const toOpen = 9 * 60 + 30 - mins;
    const h = Math.floor(toOpen / 60);
    const m = toOpen % 60;
    const cd = h > 0 ? `${h}h ${m}m` : `${m}m`;
    msg = (
      <>
        Market opens in <strong>{cd}</strong>. This is your <strong>watchlist</strong> right now —
        buy signals start firing after the bell: <strong>Gap-and-Go ~9:35</strong>,{' '}
        <strong>ORB ~9:46</strong> ET. The <strong>PM High</strong> is your Gap-and-Go trigger.
      </>
    );
  } else if (session === 'regular') {
    cls = 'dts--open';
    icon = '🟢';
    msg = (
      <>
        Market <strong>open</strong> — signals fire live as setups trigger. New entries land in
        Live Signals and open a paper trade below.
      </>
    );
  } else if (session === 'afterhours') {
    cls = 'dts--ah';
    icon = '🌆';
    msg = (
      <>
        Regular session <strong>closed</strong>. Signals resume tomorrow premarket — movers from
        4:00 ET, entries after 9:30.
      </>
    );
  } else {
    msg = (
      <>
        Market <strong>closed</strong>. Buy signals resume at the next session open (Mon–Fri,
        9:30 ET). The list below is your watchlist to prep from.
      </>
    );
  }

  return (
    <div className={`dts ${cls}`} role="status">
      <span className="dts__icon" aria-hidden>{icon}</span>
      <span className="dts__msg">{msg}</span>
    </div>
  );
}
