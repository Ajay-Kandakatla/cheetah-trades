/* 🔕 Clean Gajjala alerts — the frontend copy (24 Nov 2026, clean-alerts spec §3.4 / WP fe-copy).
 *
 * Ajay 24 Nov 2026 ~22:15 ET: "ok remove EMA entry alerts and divergence alerts. Keep Gajjals clean entries when we find
 * new potentials with all the rules getting satisfied.." then "and then A+ entries..", then "Honestly The potenail alerts
 * are not bad..". The three 🔀 9 / 21 EMA cross pushes (👀 Watch 1-min, ➖ Horizontal Fade, 🩳 High SI) are switched off
 * at the source; 🎯 A+, 🧠 potentials and 💧 volume dried keep ringing.
 *
 * Pinned: ONE switch-off date (lib/alertKinds.GAJJALA_CROSS_PUSH_OFF_SINCE); the 🩳 row leads SWITCHED OFF and carries
 * his full words once; the 🧠 row carries one 🔀-off sentence with his first sentence only; the Essentials clause and
 * the /alerts 🩳 eyebrow say switched off; the real backend off sentence renders through GajjalaWatchBoard.
 * NEGATIVES: no over-mute of 🎯 / 💧 / 🥇; no "shadow"; no typed date in Notifications.tsx / Alerts.tsx; the Luk eyebrow
 * unchanged; the 👀 info never says "rings once per ticker".
 */
import { act, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../hooks/useNotificationPrefs', async () => {
  const actual: any = await vi.importActual('../hooks/useNotificationPrefs');
  return {
    ...actual,
    useNotificationPrefs: () => ({
      rows: [{
        kind: 'web',
        endpoint: 'https://push.example/clean',
        endpoint_short: 'clean',
        label: 'iPhone',
        created_at: 1758300000,
        prefs: { gajjala_si_cross: true, gajjala_potential: true, gajjala_setup: true, gajjala_vol_dried: true },
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
import { AlertsPage, GG1M_PASSES, GGA_PASSES, LUK_PASSES, PASSES, ggSiCrossChipText } from './Alerts';
import GajjalaWatchBoard from '../components/GajjalaWatchBoard';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import {
  GAJJALA_CROSS_PUSH_OFF_SINCE, GAJJALA_SI_CROSS_LIVE_SINCE, GAJJALA_VOL_DRIED_LIVE_SINCE,
} from '../lib/alertKinds';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

/* His words, verbatim (typed here independently of Notifications.tsx so a drift there is caught). */
const CLEAN_ALERTS_ASK = 'ok remove EMA entry alerts and divergence alerts. Keep Gajjals clean entries when we find new potentials with all the rules getting satisfied..';
const CLEAN_ALERTS_SHORT = 'ok remove EMA entry alerts and divergence alerts';
const SI_CROSS_ASK = 'And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA.';
const VOL_DRIED_ASK = 'Can you send me notification of volume dried please..';

const detail = (k: string) => CATEGORIES.find((c) => (c.key as string) === k)!.detail;
const occurrences = (hay: string, needle: string) => hay.split(needle).length - 1;
async function src(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('1 · the ONE switch-off date', () => {
  it('GAJJALA_CROSS_PUSH_OFF_SINCE is an ISO date after the 🩳 live date', () => {
    expect(GAJJALA_CROSS_PUSH_OFF_SINCE).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(GAJJALA_CROSS_PUSH_OFF_SINCE > GAJJALA_SI_CROSS_LIVE_SINCE).toBe(true);
    // the check bites: the live date itself is not after itself
    expect(GAJJALA_SI_CROSS_LIVE_SINCE > GAJJALA_SI_CROSS_LIVE_SINCE).toBe(false);
    expect(CLEAN_ALERTS_ASK.slice(0, CLEAN_ALERTS_ASK.indexOf('.'))).toBe(CLEAN_ALERTS_SHORT);
  });
});

describe('2 · the 🩳 row leads SWITCHED OFF', () => {
  it('leads SWITCHED OFF with his full words, keeps the live history, rings nothing', () => {
    const d = detail('gajjala_si_cross');
    expect(d.startsWith(`SWITCHED OFF ${GAJJALA_CROSS_PUSH_OFF_SINCE} — your call: "${CLEAN_ALERTS_ASK}"`)).toBe(true);
    expect(d).toContain(`ON FOR YOUR PHONE — LIVE SINCE ${GAJJALA_SI_CROSS_LIVE_SINCE}`);
    expect(d).toContain(`your call: "${SI_CROSS_ASK}"`);
    expect(d).toContain('rings nothing');
    expect(d).toContain('WHAT FIRED:');
    expect(d).toContain('The crosses stay drawn on the 🩳 cards.');
    expect(d).toContain('UNMEASURED — information, not an entry. Not a recommendation.');
    // the full quote is served ONCE in the row
    expect(occurrences(d, CLEAN_ALERTS_ASK)).toBe(1);
  });
  it('NEGATIVE: it no longer leads ON FOR YOUR PHONE, never says "WHAT FIRES:", "Mute it here." or shadow', () => {
    const d = detail('gajjala_si_cross');
    expect(d.startsWith('ON FOR YOUR PHONE')).toBe(false);
    expect(d).not.toContain('WHAT FIRES:');
    expect(d).not.toContain('Mute it here.');
    expect(d).not.toMatch(/shadow/i);
  });
});

describe('3 · the 🧠 row carries one 🔀-off sentence', () => {
  const OFF = `The 🔀 9 / 21 EMA cross pushes from 👀 Gajjala’s Watch and ➖ Horizontal Fade that rode this toggle are off since ${GAJJALA_CROSS_PUSH_OFF_SINCE} ("${CLEAN_ALERTS_SHORT}"); the crosses stay drawn on the charts.`;
  it('still leads ON FOR YOUR PHONE and rings live; the 🔀 sentence sits before WHAT NEVER FIRES', () => {
    const d = detail('gajjala_potential');
    expect(d.startsWith('ON FOR YOUR PHONE')).toBe(true);
    expect(d).toContain('rings live');
    expect(occurrences(d, OFF)).toBe(1);
    expect(d).toContain(CLEAN_ALERTS_SHORT);
    expect(d.indexOf(OFF)).toBeLessThan(d.indexOf('WHAT NEVER FIRES'));
  });
  it('NEGATIVE: no "shadow", and the full quote is NOT repeated here (served once, on the 🩳 row)', () => {
    const d = detail('gajjala_potential');
    expect(d).not.toMatch(/shadow/i);
    expect(d).not.toContain(CLEAN_ALERTS_ASK);
    expect(d).not.toContain('SWITCHED OFF');
  });
});

describe('4 · NEGATIVE over-mute guard — 🎯 A+, 💧 vol dried and 🥇 Luk still lead ON', () => {
  it('🎯 gajjala_setup / 💧 gajjala_vol_dried / 🥇 luk_setup keep their ON lead and carry no switch-off words', () => {
    expect(detail('gajjala_setup').startsWith('ON FOR YOUR PHONE — you said "Pushes: YES"')).toBe(true);
    expect(detail('gajjala_vol_dried').startsWith(
      `ON FOR YOUR PHONE — LIVE SINCE ${GAJJALA_VOL_DRIED_LIVE_SINCE}, your call: "${VOL_DRIED_ASK}"; everyone else starts off. Mute it here. `,
    )).toBe(true);
    expect(detail('luk_setup').startsWith('ON FOR YOUR PHONE — LIVE SINCE 2026-11-01')).toBe(true);
    for (const k of ['gajjala_setup', 'gajjala_vol_dried', 'luk_setup']) {
      const d = detail(k);
      expect(d, k).not.toContain('SWITCHED OFF');
      expect(d, k).not.toContain(CLEAN_ALERTS_SHORT);
      expect(d, k).not.toMatch(/switched off/i);
    }
  });
});

describe('5 · Essentials — pref map unchanged, the 🩳 clause says switched off', () => {
  it('the four Gajjala kinds stay ON; the clause says rang from … switched off since …', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    const pref = ess.pref as Record<string, boolean | undefined>;
    for (const k of ['gajjala_si_cross', 'gajjala_potential', 'gajjala_setup', 'gajjala_vol_dried']) expect(pref[k], k).toBe(true);
    expect(ess.detail).toContain(
      `🩳 High SI EMA crosses rang from ${GAJJALA_SI_CROSS_LIVE_SINCE} and are switched off since ${GAJJALA_CROSS_PUSH_OFF_SINCE} ("${CLEAN_ALERTS_SHORT}")`,
    );
    expect(ess.detail).toContain('switched off since');
    // 🩳 still before 💧
    expect(ess.detail.indexOf('🩳 High SI')).toBeLessThan(ess.detail.indexOf('💧 Volume dried'));
  });
  it('NEGATIVE: never "plus 🩳 High SI EMA crosses since", never the full quote, never shadow', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect(ess.detail).not.toContain('plus 🩳 High SI EMA crosses since');
    expect(ess.detail).not.toContain(CLEAN_ALERTS_ASK);
    expect(ess.detail).not.toMatch(/shadow/i);
  });
});

describe('6 · source guards', () => {
  it('Notifications.tsx / Alerts.tsx type neither 2026-11-24 nor 2026-11-25; they interpolate the constant', async () => {
    for (const rel of ['src/pages/Notifications.tsx', 'src/pages/Alerts.tsx']) {
      const text = await src(rel);
      for (const day of ['2026-11-24', '2026-11-25']) expect(text.includes(day), `${rel}: ${day}`).toBe(false);
      expect(text, rel).toContain('GAJJALA_CROSS_PUSH_OFF_SINCE');
    }
    // the check bites
    expect(`x ${GAJJALA_CROSS_PUSH_OFF_SINCE} y`.includes(GAJJALA_CROSS_PUSH_OFF_SINCE)).toBe(true);
  });
  it('Notifications.tsx types his full words exactly once', async () => {
    expect(occurrences(await src('src/pages/Notifications.tsx'), CLEAN_ALERTS_ASK)).toBe(1);
  });
  it("alertKinds.ts: the '2026-11-24' count stays 1; the 💧 extraction still matches '2026-11-25'", async () => {
    const ak = await src('src/lib/alertKinds.ts');
    expect(occurrences(ak, '2026-11-24')).toBe(1);
    const m = ak.match(/export const GAJJALA_VOL_DRIED_LIVE_SINCE = '(\d{4}-\d{2}-\d{2})';/);
    expect(m && m[1]).toBe('2026-11-25');
    const off = ak.match(/export const GAJJALA_CROSS_PUSH_OFF_SINCE = '(\d{4}-\d{2}-\d{2})';/);
    expect(off && off[1]).toBe(GAJJALA_CROSS_PUSH_OFF_SINCE);
  });
});

/* ── 7 · /alerts ─────────────────────────────────────────────────────────────────────────────────────────────────── */
const NOW = Date.parse('2026-09-05T15:00:00Z');
const fresh = (cadence: number) => ({ as_of: '2026-09-05T10:59:30-04:00', date: '2026-09-05', cadence_sec: cadence, counts: { pushed: 0 } });
function alertsStatus() {
  const passes: Record<string, unknown> = {};
  for (const m of PASSES) passes[m.key] = fresh(m.fallbackCadenceSec);
  for (const m of GG1M_PASSES) passes[m.key] = fresh(60);
  for (const m of LUK_PASSES) passes[m.key] = fresh(300);
  for (const m of GGA_PASSES) passes[m.key] = fresh(300);
  passes.gajjala_si_cross = { ...fresh(300), counts: { pushed: 0, off: 3 } };
  return {
    in_session: true, now_et: '2026-09-05T11:00:00-04:00',
    gate: { min_room_pct: 5.0, max_above_demand_pct: 1.0, min_cap_usd: 700_000_000, min_cap_txt: '$700M' },
    passes, disclaimer: 'Configured price-structure alerts. Not advice.',
  };
}

describe('7 · /alerts — the 🩳 eyebrow says switched off', () => {
  beforeEach(() => {
    vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] });
    _resetAlertHistoryCache();
    const st = alertsStatus();
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (String(url).includes('/alerts/status')) return { ok: true, status: 200, json: async () => st } as Response;
      return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
    }));
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('the eyebrow prints the switch-off date; the off chip words unchanged; NEGATIVE: the Luk eyebrow unchanged', async () => {
    render(<MemoryRouter initialEntries={['/alerts']}><AlertsPage /></MemoryRouter>);
    const block = await screen.findByTestId('ggs-passes');
    const head = screen.getByTestId('ggs-passes-head');
    expect(head.textContent).toBe(
      `🩳 High SI cross pass · switched off since ${GAJJALA_CROSS_PUSH_OFF_SINCE} — counted, never sent · not counted in the header`,
    );
    expect(head.textContent).not.toContain('rings your phone');
    expect(block.previousElementSibling).toBe(head);
    expect(within(block).getByTestId('pass-gajjala_si_cross').textContent).toContain('3 held: the push is switched off');
    expect(ggSiCrossChipText('off', 3)).toBe('3 held: the push is switched off');
    // NEGATIVE: 🥇 Luk still rings — its eyebrow is byte-identical
    expect(screen.getByTestId('luk-passes-head').textContent)
      .toBe("🥇 Luk's pass · rings your phone since 2026-11-01 · not counted in the header");
  });
});

/* ── 8 · the real backend off sentence through the real 👀 board ──────────────────────────────────────────────────── */
/* backend chart_maps/gajjala_watch/cross_alerts.rules_line() under PUSH_MODE "off" (spec §3.3), with today's constants:
   EMA_FAST 9 / EMA_SLOW 21, frames 1- / 5- / 15-min, push frame 1-min, CLEAN_ALERTS_CALL "24 Nov",
   CLEAN_ALERTS_WORDS = his words. Served as info.push_text by payload.info(). */
const WATCH_OFF_TEXT = "👀 Gajjala's Watch marks every 9 / 21 EMA cross on your tickers' 1-, 5- and 15-min charts (closed bars). "
  + 'No cross rings your phone — yours or auto-added — the 1-min cross push is off since your call of 24 Nov: '
  + `“${CLEAN_ALERTS_ASK}” UNMEASURED — information, not an entry.`;

describe('8 · 👀 Gajjala’s Watch renders the served off sentence', () => {
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });
  const mount = async (pushText: string) => {
    vi.useFakeTimers();
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {},
    }));
    const board = () => {
      const b: any = JSON.parse(JSON.stringify(fixture));
      b.info = { ...b.info, push_text: pushText, push_mode: 'off' };
      return b;
    };
    vi.stubGlobal('fetch', vi.fn(async (url: any) => (String(url).includes('/short-interest/')
      ? { ok: true, json: async () => ({}) }
      : { ok: true, json: async () => board() })));
    const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    return r.container;
  };

  it('prints the served sentence verbatim; NEGATIVE: never "rings once per ticker"', async () => {
    const c = await mount(WATCH_OFF_TEXT);
    const lines = Array.from(c.querySelectorAll('.ggw-info .ggw-line')).map((p) => p.textContent);
    expect(lines).toContain(WATCH_OFF_TEXT);
    expect(c.textContent).toContain('No cross rings your phone');
    expect(c.textContent).not.toContain('rings once per ticker');
  });
  it('the negative bites: the old live sentence (the 2026-11-15 fixture) does print "rings once per ticker"', async () => {
    const c = await mount((fixture as any).info.push_text);
    expect(c.textContent).toContain('rings once per ticker');
  });
});

describe('the page renders (smoke)', () => {
  it('/notifications shows the 🩳 SWITCHED OFF lead and the 🧠 🔀-off sentence', () => {
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    const text = document.body.textContent || '';
    expect(text).toContain(`SWITCHED OFF ${GAJJALA_CROSS_PUSH_OFF_SINCE}`);
    expect(text).toContain('that rode this toggle are off since');
  });
});
