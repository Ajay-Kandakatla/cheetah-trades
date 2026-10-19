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
    expect(kindLabel('demand_alert')).toBe('🧲 Reversal at demand');
    expect(kindLabel('zone_bounce_alert')).toBe('🪃 Intraday demand turn');
    expect(kindLabel('supply_break_alert')).toBe('🚀 Breaking resistance');
    expect(ZONE_KINDS).toEqual(['demand_alert', 'zone_bounce_alert', 'supply_break_alert']);
    for (const k of ZONE_KINDS) expect(ALERT_KINDS[k].group).toBe('zones');
  });

  // Ajay 2026-09-10: "I do not see any reversal alerts today" — he HAD 11 of
  // them. The word was on the wrong kind: the MUTED zone_bounce_alert was
  // labelled "Demand-zone reversal" while the LIVE demand_alert, the one that
  // actually sends "\u2191 reversal off demand", read "Demand-zone approach".
  // KIND_CHIPS is a static list, so the reversal chip rendered on /alerts even
  // though that kind never fires, and clicking it returned nothing.
  it('gives the word "reversal" to the LIVE kind and never to the muted one', () => {
    expect(ALERT_KINDS.demand_alert.label).toMatch(/reversal/i);
    expect(ALERT_KINDS.zone_bounce_alert.label).not.toMatch(/reversal/i);
    // and neither may go back to the word he asked us to drop
    for (const k of ZONE_KINDS) expect(ALERT_KINDS[k].label).not.toMatch(/bounce/i);
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

  /* 🚩 2026-10-13 — gajjala_setup (DECISIONS "Pushes: YES — owner-only kind
   * gajjala_setup"). It ships in SHADOW, but the day it goes live its history
   * rows must read as a label, never as the raw id. */
  it('labels the 🚩 gajjala_setup kind, not its raw id', () => {
    expect(ALERT_KINDS.gajjala_setup).toEqual({ emoji: '🚩', label: 'Gajjala A+ setup', group: 'trading' });
    expect(kindLabel('gajjala_setup')).toBe('🚩 Gajjala A+ setup');
    expect(kindText('gajjala_setup')).toBe('Gajjala A+ setup');
    expect(kindEmoji('gajjala_setup')).toBe('🚩');
  });

  it('NEGATIVE: the 🚩 kind is not a zone or breakout kind and its label never says "bounce"', () => {
    expect(ZONE_KINDS).not.toContain('gajjala_setup');
    expect(BREAKOUT_KINDS).not.toContain('gajjala_setup');
    expect(ALERT_KINDS.gajjala_setup.label).not.toMatch(/bounce/i);
  });

  /* 🎚️ 2026-10-16 — tape_control. Ajay: "I wwant you to alert me when the
   * Buyers are winning in tape for IREN today." A LIVE owner-only kind; its
   * history rows must read as a label, never as the raw id. 🎚️ is U+1F39A,
   * not 🎛️ (U+1F39B, scalp_tape). */
  it('labels the 🎚️ tape_control kind in the tape group', () => {
    expect(ALERT_KINDS.tape_control).toEqual({ emoji: '\u{1F39A}\u{FE0F}', label: 'Buyers in control — tape', group: 'tape' });
    expect(kindLabel('tape_control')).toBe('🎚️ Buyers in control — tape');
    expect(kindEmoji('tape_control')).not.toBe(kindEmoji('scalp_tape'));
  });

  it('NEGATIVE: the 🎚️ label never names a reversal word, a sham, or a buy call, and is not a zone kind', () => {
    const label = ALERT_KINDS.tape_control.label;
    expect(label).not.toMatch(/boun/i);
    expect(label).not.toMatch(/fak[e]/i);
    expect(label).not.toMatch(/\bbuy /i);
    expect(ZONE_KINDS).not.toContain('tape_control');
    expect(BREAKOUT_KINDS).not.toContain('tape_control');
  });

  /* 🔑 2026-09-25 — Ajay: "I wanna know when key levels are broken for a
   * stock." The push kind ships OFF, but the day he turns it on its history
   * rows must read as a label, never as the raw id. */
  it('labels the 🔑 key-level kind, not its raw id', () => {
    expect(kindLabel('key_level_alert')).toBe('🔑 Key level closed through');
    expect(kindText('key_level_alert')).toBe('Key level closed through');
    expect(kindEmoji('key_level_alert')).toBe('🔑');
    expect(ALERT_KINDS.key_level_alert.group).toBe('zones');
  });

  it('NEGATIVE: the 🔑 kind is not a ZONE_KINDS member and never says "bounce" or "broke"', () => {
    // ZONE_KINDS is the three kinds behind alert_gates.py; the /alerts default
    // filter and the boards' 🔔 chip read it. A close through a key level
    // passes no room/proximity gate, so it must not join them.
    expect(ZONE_KINDS).not.toContain('key_level_alert');
    expect(ZONE_KINDS).toHaveLength(3);
    expect(kindLabel('key_level_alert')).not.toMatch(/bounce/i);
    // The kind fires on a CLOSE through the level, not a live pierce.
    expect(ALERT_KINDS.key_level_alert.label).toMatch(/closed through/);
    expect(ALERT_KINDS.key_level_alert.label).not.toMatch(/\bbroke\b/i);
  });

  it('null / empty kind reads as the generic notification', () => {
    expect(kindLabel(null)).toBe('📣 Notification');
    expect(kindLabel('')).toBe('📣 Notification');
    expect(kindText(undefined)).toBe('Notification');
  });

  it('🩺 ops_alert is an admin kind with a plain label', () => {
    expect(ALERT_KINDS.ops_alert.group).toBe('admin');
    expect(kindLabel('ops_alert')).toMatch(/^\S+ /);
    expect(kindLabel('ops_alert')).toBe('🩺 Docker / host watch');
    // NEGATIVE: the house words never reach a label he reads
    for (const w of ['boun' + 'ce', 'fa' + 'ke']) {
      expect(kindLabel('ops_alert').toLowerCase()).not.toContain(w);
    }
  });
});

/* 🎢 🗺️ 2026-10-14 — Ajay: "I need a tape burst notification specific for High
 * Beta stocks from the reselinet separately and also other tape bursts from the
 * Chart Maps page". Two owner-only LIVE kinds; their /alerts rows and the bell
 * must read as labels, never as the raw ids. */
describe('the two tape-burst kinds (2026-10-14)', () => {
  it('labels 🎢 tape_burst_highbeta and 🗺️ tape_burst_chartmaps in their own tape group', () => {
    expect(ALERT_KINDS.tape_burst_highbeta).toEqual({ emoji: '\u{1F3A2}', label: 'Tape burst — High Beta', group: 'tape' });
    expect(ALERT_KINDS.tape_burst_chartmaps).toEqual({ emoji: '\u{1F5FA}\u{FE0F}', label: 'Tape burst — Chart Maps', group: 'tape' });
    expect(kindLabel('tape_burst_highbeta')).toBe('🎢 Tape burst — High Beta');
    expect(kindLabel('tape_burst_chartmaps')).toBe('🗺️ Tape burst — Chart Maps');
    expect(kindText('tape_burst_highbeta')).toBe('Tape burst — High Beta');
    expect(kindText('tape_burst_chartmaps')).toBe('Tape burst — Chart Maps');
    expect(kindEmoji('tape_burst_highbeta')).toBe('🎢');
    expect(kindEmoji('tape_burst_chartmaps')).toBe('🗺️');
  });

  it('NEGATIVE: neither is a zone or breakout kind, and ⚡ trade_flash keeps its own zone label', () => {
    for (const k of ['tape_burst_highbeta', 'tape_burst_chartmaps']) {
      expect(ZONE_KINDS).not.toContain(k);
      expect(BREAKOUT_KINDS).not.toContain(k);
      expect(ALERT_KINDS[k].group).not.toBe('zones');
    }
    expect(ZONE_KINDS).toHaveLength(3);
    expect(ALERT_KINDS.trade_flash).toEqual({ emoji: '⚡', label: 'Trade flash at a zone', group: 'zones' });
  });

  it('NEGATIVE: the labels never say bounce, fake, shadow or a forecast word', () => {
    for (const k of ['tape_burst_highbeta', 'tape_burst_chartmaps']) {
      const l = kindLabel(k).toLowerCase();
      for (const w of ['boun' + 'ce', 'fa' + 'ke', 'shadow', 'reversal', 'will ', 'signal']) expect(l).not.toContain(w);
    }
  });
});

/* 🧠 2026-10-15 — Ajay: "Give me an alert all continous tracker on these
 * specifically when I get alert I will jump on to ride the wave". A NEW
 * owner-only kind, LIVE; its /alerts rows, the kind chip and the bell must read
 * as a label, never as the raw id. UNMEASURED — a potential, not an entry. */
describe('the 🧠 gajjala_potential kind (2026-10-15)', () => {
  it('labels 🧠 gajjala_potential in the trading group', () => {
    expect(ALERT_KINDS.gajjala_potential).toEqual({ emoji: '🧠', label: 'Gajjala potential', group: 'trading' });
    expect(kindLabel('gajjala_potential')).toBe('🧠 Gajjala potential');
    expect(kindText('gajjala_potential')).toBe('Gajjala potential');
    expect(kindEmoji('gajjala_potential')).toBe('🧠');
  });

  it('NEGATIVE: not a zone or breakout kind; the 🚩 A+ kind beside it is unchanged', () => {
    expect(ZONE_KINDS).not.toContain('gajjala_potential');
    expect(BREAKOUT_KINDS).not.toContain('gajjala_potential');
    expect(ZONE_KINDS).toHaveLength(3);
    expect(ALERT_KINDS.gajjala_setup).toEqual({ emoji: '🚩', label: 'Gajjala A+ setup', group: 'trading' });
    // sits right after 🚩 in the registry (the one appended line at the anchor)
    const keys = Object.keys(ALERT_KINDS);
    expect(keys.indexOf('gajjala_potential')).toBe(keys.indexOf('gajjala_setup') + 1);
  });

  it('NEGATIVE: the label never says the b-word, fake, shadow, "potential to" or a forecast word', () => {
    const l = kindLabel('gajjala_potential').toLowerCase();
    for (const w of ['boun' + 'ce', 'fa' + 'ke', 'shadow', 'potential to', 'will ', 'signal', 'buy']) expect(l).not.toContain(w);
  });
});

/* 🌙 2026-10-19 — overnight_movers. Ajay: "Can you do an over night scan for all
   the stocks they are all growing over night". Ships OFF (his call). */
describe('the 🌙 overnight_movers kind (2026-10-19)', () => {
  it('labels 🌙 overnight_movers in the trading group', () => {
    expect(ALERT_KINDS.overnight_movers).toEqual({ emoji: '🌙', label: 'Overnight movers', group: 'trading' });
    expect(kindLabel('overnight_movers')).toBe('🌙 Overnight movers');
    expect(kindText('overnight_movers')).toBe('Overnight movers');
    expect(kindEmoji('overnight_movers')).toBe('🌙');
  });

  it('NEGATIVE: not a zone or breakout kind; never the raw id; no b-word, sham or buy word', () => {
    expect(ZONE_KINDS).not.toContain('overnight_movers');
    expect(BREAKOUT_KINDS).not.toContain('overnight_movers');
    expect(kindLabel('overnight_movers')).not.toContain('overnight_movers');
    const l = kindLabel('overnight_movers').toLowerCase();
    for (const bad of ['bounce', 'fake', 'buy', 'signal', 'gainers to']) expect(l).not.toContain(bad);
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
