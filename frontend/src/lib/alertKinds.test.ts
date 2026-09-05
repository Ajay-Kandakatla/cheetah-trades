/* alertKinds — the shared kind registry + ET clock.
 *
 * Ajay reads every stamp in ET and trades real money off "when did that push
 * fire", so the clock math is pinned across the DST switch, not just on one
 * summer afternoon. Negatives: an unknown kind falls back to its raw id (a
 * push he received is never hidden), and a missing stamp renders empty rather
 * than "NaN:NaN ET".
 */
import { describe, it, expect } from 'vitest';
import {
  ALERT_KINDS, BREAKOUT_KINDS, ZONE_KINDS, etDayHeading, etDayKey, etFromIso, etFromTs, kindEmoji,
  kindLabel, kindText, startOfEtDay, todayEtKey,
} from './alertKinds';

const T = (iso: string) => Date.parse(iso) / 1000;

describe('kind registry', () => {
  it('labels the three zone kinds that page the phone', () => {
    expect(kindLabel('demand_alert')).toBe('🧲 Demand-zone approach');
    expect(kindLabel('zone_bounce_alert')).toBe('🪃 Demand-level bounce');
    expect(kindLabel('supply_break_alert')).toBe('🚀 Breaking resistance');
    expect(ZONE_KINDS).toEqual(['demand_alert', 'zone_bounce_alert', 'supply_break_alert']);
    for (const k of ZONE_KINDS) expect(ALERT_KINDS[k].group).toBe('zones');
  });

  it('carries every kind PushHistoryPanel used to label on its own, plus the phone kinds', () => {
    for (const k of [
      'volume_breakout', 'rising_momentum', 'watchlist_breakout', 'juggernaut_watchlist', 'stage_breakdown',
      'watchlist_stage_breakdown', 'price_alert', 'position_alert', 'morning_brief', 'product_launch',
      'todo_reminder', 'todo_daily_digest', 'house_daily', 'house_scrape_failed', 'house_stagnant',
      'user_signin', 'minervini_flashcards', 'market_hours_reminder', 'setup_inside_day', 'setup_peg',
      'setup_orb_capture', 'setup_orb_triggered', 'generic',
      'pivot_alert', 'promo_alert', 'trade_flash', 'vb_workout', 'vb_supplement', 'vb_education',
    ]) {
      expect(ALERT_KINDS[k], k).toBeDefined();
      expect(kindLabel(k)).toMatch(/^\S+ /);
    }
    for (const k of BREAKOUT_KINDS) expect(ALERT_KINDS[k].group).toBe('breakout');
  });

  it('NEGATIVE: an unknown kind falls back to its raw id, never to a made-up label', () => {
    expect(kindLabel('some_future_kind')).toBe('some_future_kind');
    expect(kindText('some_future_kind')).toBe('some_future_kind');
    expect(kindEmoji('some_future_kind')).toBe('📣');
  });

  it('null / empty kind reads as the generic notification', () => {
    expect(kindLabel(null)).toBe('📣 Notification');
    expect(kindLabel('')).toBe('📣 Notification');
    expect(kindText(undefined)).toBe('Notification');
  });
});

describe('ET clock', () => {
  it('formats a UTC epoch in ET and says so', () => {
    // 14:42 UTC in September = 10:42 EDT.
    expect(etFromTs(T('2026-09-05T14:42:00Z'))).toBe('10:42 ET');
    // 14:42 UTC in January = 09:42 EST.
    expect(etFromTs(T('2026-01-15T14:42:00Z'))).toBe('09:42 ET');
  });

  it('DST switch day: the same UTC clock reads one hour later once the clocks move', () => {
    // US DST begins 2026-03-08 02:00 local. 12:00 UTC the day before = 07:00 EST;
    // 12:00 UTC on the day = 08:00 EDT.
    expect(etFromTs(T('2026-03-07T12:00:00Z'))).toBe('07:00 ET');
    expect(etFromTs(T('2026-03-08T12:00:00Z'))).toBe('08:00 ET');
    // US DST ends 2026-11-01: 12:00 UTC = 08:00 EDT the day before, 07:00 EST after.
    expect(etFromTs(T('2026-10-31T12:00:00Z'))).toBe('08:00 ET');
    expect(etFromTs(T('2026-11-01T12:00:00Z'))).toBe('07:00 ET');
  });

  it('midnight renders as 00:xx, never 24:xx', () => {
    expect(etFromTs(T('2026-09-05T04:05:00Z'))).toBe('00:05 ET');
  });

  it('day key is the ET calendar day, not the UTC one', () => {
    // 03:30 UTC Sep 6 is still 23:30 ET Sep 5.
    expect(etDayKey(T('2026-09-06T03:30:00Z'))).toBe('2026-09-05');
    expect(etDayKey(T('2026-09-06T04:30:00Z'))).toBe('2026-09-06');
  });

  it('startOfEtDay lands on 00:00 ET exactly, under EDT and under EST', () => {
    const summer = Date.parse('2026-09-05T15:00:00Z');
    expect(startOfEtDay(0, summer)).toBe(T('2026-09-05T04:00:00Z'));
    expect(startOfEtDay(1, summer)).toBe(T('2026-09-04T04:00:00Z'));
    const winter = Date.parse('2026-01-15T15:00:00Z');
    expect(startOfEtDay(0, winter)).toBe(T('2026-01-15T05:00:00Z'));
  });

  it('startOfEtDay crossing the DST switch uses the offset of the TARGET day', () => {
    // Now: Monday Mar 9 (EDT). Two days back is Saturday Mar 7 (EST): midnight = 05:00Z.
    const now = Date.parse('2026-03-09T15:00:00Z');
    expect(startOfEtDay(0, now)).toBe(T('2026-03-09T04:00:00Z'));
    expect(startOfEtDay(2, now)).toBe(T('2026-03-07T05:00:00Z'));
    // The switch day itself: midnight is still EST.
    expect(startOfEtDay(1, now)).toBe(T('2026-03-08T05:00:00Z'));
  });

  it('startOfEtDay rolls a month boundary', () => {
    const now = Date.parse('2026-09-01T15:00:00Z');
    expect(etDayKey(startOfEtDay(1, now))).toBe('2026-08-31');
    expect(etDayKey(startOfEtDay(30, now))).toBe('2026-08-02');
  });

  it('late ET evening: "today" is still the ET date even after UTC has rolled over', () => {
    // 23:30 ET Sep 5 = 03:30Z Sep 6.
    const now = Date.parse('2026-09-06T03:30:00Z');
    expect(todayEtKey(now)).toBe('2026-09-05');
    expect(startOfEtDay(0, now)).toBe(T('2026-09-05T04:00:00Z'));
  });

  it('day headings name today and yesterday in words', () => {
    const now = Date.parse('2026-09-05T15:00:00Z');
    expect(etDayHeading('2026-09-05', now)).toBe('Today · Sat, Sep 5');
    expect(etDayHeading('2026-09-04', now)).toBe('Yesterday · Fri, Sep 4');
    expect(etDayHeading('2026-09-03', now)).toBe('Thu, Sep 3');
    expect(etDayHeading('garbage', now)).toBe('garbage');
  });

  it('etFromIso reads an ET-offset stamp and a UTC stamp to the same clock', () => {
    expect(etFromIso('2026-09-05T13:02:11-04:00')).toBe('13:02 ET');
    expect(etFromIso('2026-09-05T17:02:11Z')).toBe('13:02 ET');
    expect(etFromIso(null)).toBeNull();
    expect(etFromIso('not a date')).toBeNull();
  });

  it('NEGATIVE: a missing or broken stamp renders empty, never NaN', () => {
    expect(etFromTs(null)).toBe('');
    expect(etFromTs(undefined)).toBe('');
    expect(etFromTs(NaN)).toBe('');
    expect(etFromTs(0)).toBe('');
    expect(etDayKey(null)).toBe('');
  });
});
