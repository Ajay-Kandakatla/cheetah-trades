/* /notifications — the 🚩 gajjala_setup kind (2026-10-13).
 *
 * DECISIONS: "Pushes: YES — owner-only kind gajjala_setup, A+ triggers only …
 * 09:45–16:00 and 16:00–20:00 ET, never 09:30–09:45 … silent on closed days,
 * once per (symbol, setup, session); pref toggle in push/subs.py". Round A: SHADOW
 * first — recorded on /alerts, nothing sent until the switch is flipped.
 * WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that
 * happens", DECISIONS10 D1; default_prefs stays False — AMENDMENTS10 F1). The page
 * must say ON FOR YOUR PHONE (the kind is in the backend owner keep-set), say it
 * is LIVE since 2026-10-16 (his call), say when it fires and when it never does,
 * and say NOT MEASURED. The
 * keep-set ↔ page coherence against backend/push/subs.py and the mode against
 * constants.GAJJALA_PUSH_MODE are the contracts.mjs 🚩 block. */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../hooks/useNotificationPrefs', async () => {
  const actual: any = await vi.importActual('../hooks/useNotificationPrefs');
  return {
    ...actual,
    useNotificationPrefs: () => ({
      rows: [{
        kind: 'web', endpoint: 'https://push.example/aaa', endpoint_short: 'aaa', label: 'iPhone',
        created_at: 1758300000, prefs: { gajjala_setup: true },
      }],
      error: null, busy: false,
      refresh: vi.fn(), togglePref: vi.fn(), setManyPrefs: vi.fn(),
      setQuietHours: vi.fn(), unsubscribe: vi.fn(), sendTest: vi.fn(),
    }),
  };
});
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: { is_admin: false } }) }));
vi.mock('../hooks/useAlertSettings', () => ({
  useAlertSettings: () => ({
    settings: { intraday_emergency_pct: 12, intraday_warning_pct: 8, stop_close_buffer_pct: 1 },
    save: vi.fn(), busy: false,
  }),
}));
vi.mock('../components/PushHistoryPanel', () => ({ PushHistoryPanel: () => null }));
vi.mock('../lib/pushSubscribe', () => ({
  subscribePush: vi.fn(), pushSupported: () => true, isStandalone: () => true,
}));

import NotificationsPage, { CATEGORIES, PRESETS } from './Notifications';
import { ALERT_KINDS } from '../lib/alertKinds';

const gg = () => CATEGORIES.filter((c) => (c.key as string) === 'gajjala_setup');

describe('Notifications · 🚩 gajjala_setup', () => {
  it('exactly one gajjala_setup entry, in the trading group, rendered on the page', () => {
    expect(gg()).toHaveLength(1);
    expect(gg()[0].group).toBe('trading');
    expect(gg()[0].emoji).toBe('🚩');
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getByText('Gajjala A+ setup (his five setups)')).toBeTruthy();
  });

  // WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens") — DECISIONS10 D1; the phrase
  // list follows AMENDMENTS10 F1 ("everyone else starts off" stays), F4 (refusals counted on the pass row), F5 (the words
  // of his rules) and F9 (numbers first).
  it('the detail says ON FOR YOUR PHONE, LIVE SINCE 2026-10-16 (his call), and NOT MEASURED', () => {
    const d = gg()[0].detail;
    for (const phrase of ['ON FOR YOUR PHONE', 'everyone else starts off', 'LIVE SINCE 2026-10-16', 'every A+ entry in the window is its own push',
      'mute it here', 'you alert me when that happens', 'shadow — not sent', 'kissed and honored the 9 EMA', 'the time the 🧠 potential rang',
      'The push leads with the trigger and the stop', 'in the words of his rules (🎾: 2+ sources, no first-hand entry rule on file)',
      "counted on that pass's /alerts row, never rung", 'on their own 🎯 line', 'NOT MEASURED', 'the 2026-10-14 study', 'Not a recommendation']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE (2026-10-16): the 🚩 detail no longer says shadow first / nothing sent yet, and never the reverted wording', () => {
    const d = gg()[0].detail;
    for (const gone of ['SHADOW FIRST', 'no A+ is sent yet', 'until the study of his setups reads',
      'only your phone is ever sent one' /* F1: reverted — "everyone else starts off" stays */,
      'listed on /alerts, never rung' /* F4 */, 'entry in his words' /* F5 */, 'no study here says they win']) {
      expect(d).not.toContain(gone);
    }
  });

  it('NEGATIVE (2026-10-15 W20): the 🚩 detail never says nothing is sent — the 🧠 potential kind rings live', () => {
    const d = gg()[0].detail;
    expect(d).not.toContain('nothing is sent');
    expect(d).not.toMatch(/nothing (rings|reaches|is sent)/i);
  });

  it('WHAT FIRES carries the windows and the once-a-day rule in words', () => {
    const d = gg()[0].detail;
    for (const phrase of ['WHAT FIRES', 'every rule of one of', 'entry bar traded above its trigger',
      'that bar has closed', 'a close above it is not required',
      '09:45–16:00 and 16:00–20:00 ET', '13:00 and 17:00 on NYSE half days', 'never 09:30–09:45', 'never pre-market', 'silent on closed days',
      'once per name, setup and session', 'every A+ its own push']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE: never promises a close above the trigger — the detectors count a break on the bar\'s HIGH', () => {
    // backend chart_maps/gajjala/detectors.py: break = F.h[i] > trigger; no close check (2026-10-13 review)
    const d = gg()[0].detail;
    expect(d).not.toContain('closed above its trigger');
    expect(d).not.toMatch(/clos\w* above (its|the) trigger/);
  });

  // WIDENED 2026-10-18 (DECISIONS13 D1/D4): Ajay "make the change for Long flags" — a 4–5 bar flag is A+ now, so "long flag" left the list.
  it('WHAT NEVER FIRES names the listed-but-never-rung reads', () => {
    const d = gg()[0].detail;
    for (const phrase of ['WHAT NEVER FIRES', 'near-kiss', 'B — imperfect', 'found late']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE: no "long flag" anywhere — the band is empty since 2026-10-18 (DECISIONS13 D4)', () => {
    const d = gg()[0].detail;
    expect(d).not.toContain('long flag');
    expect(d).toContain('WHAT NEVER FIRES: a near-kiss, a "B — imperfect" VCP');
  });

  it('NEGATIVE: never OFF BY DEFAULT while the keep-set carries it, never "bounce", never a buy word', () => {
    const d = gg()[0].detail;
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).not.toMatch(/bounce/i);
    expect(d).not.toMatch(/\bbuy (now|signal)\b/i);
  });

  it('the Essentials preset carries gajjala_setup: true and names it', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect((ess.pref as any).gajjala_setup).toBe(true);
    // 2026-10-29 (BUILD_SPEC29 D1/D6 — Ajay: "Only give me Gajjalas chart notifications from both tabs,"): the six-kind keep-set sentence
    expect(ess.detail).toContain('🚩 Gajjala A+ entries and 🧠 Gajjala potentials from 🚩 Gajjala’s and 🚩 Gajjala’s 1-min');
    expect((ess.pref as any).gajjala_1m_setup).toBe(true);
    expect(ess.detail).not.toContain('shadow first');
  });

  it('the 🧠 potential entry no longer says the A+ are never sent (2026-10-16)', () => {
    const d = CATEGORIES.find((c) => (c.key as string) === 'gajjala_potential')!.detail;
    expect(d).not.toMatch(/A\+[^.]*never sent/);
    expect(d).toContain('ring under 🚩 as an A+ entry since 2026-10-16');
  });

  it('NEGATIVE: Trading-only turns it on and Household-only leaves it off (a trading kind)', () => {
    expect((PRESETS.find((p) => p.id === 'trading_only')!.pref as any).gajjala_setup).toBe(true);
    expect((PRESETS.find((p) => p.id === 'household_only')!.pref as any).gajjala_setup).toBe(false);
  });

  it('the bell registry reads it as 🚩 Gajjala A+ setup, not a raw id', () => {
    expect(ALERT_KINDS.gajjala_setup).toEqual({ emoji: '🚩', label: 'Gajjala A+ setup', group: 'trading' });
  });
});
