/* 💎 /notifications after the capital-quality upgrade kind (2026-09-22).
 *
 * Ajay: "Filter and have alerts and new look out for such companies where whcih
 * have very high quality."
 *
 * The kind ships OFF — the only trading kind that does — so most of this file
 * is negative: it must NOT be in the Essentials preset (which mirrors the
 * backend keep-set), it must NOT read as on, and its detail must not borrow
 * credibility the read does not have. `capital_quality.MEASURED` is False.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const togglePref = vi.fn();
// Mutable so one test can look at the ON rendering without a second mock.
const devicePrefs: Record<string, boolean> = {
  hot_pullback_alert: true, pattern_alert: true, demand_alert: true,
  position_alert: true, potus_investment: true,
  growth_demand_alert: true, earnings_reaction: true, board_arrival: true,
  price_alert: true,
  capital_quality_upgrade: false,      // the shipped state
};

vi.mock('../hooks/useNotificationPrefs', async () => {
  const actual: any = await vi.importActual('../hooks/useNotificationPrefs');
  return {
    ...actual,
    useNotificationPrefs: () => ({
      rows: [{
        kind: 'web',
        endpoint: 'https://push.example/aaa',
        endpoint_short: 'aaa',
        label: 'iPhone',
        created_at: 1758300000,
        prefs: devicePrefs,
      }],
      error: null, busy: false,
      refresh: vi.fn(), togglePref, setManyPrefs: vi.fn(),
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
import { ALERT_KINDS, kindLabel } from '../lib/alertKinds';

const KIND = 'capital_quality_upgrade';
const draw = () => render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
const cat = () => CATEGORIES.find((c) => c.key === KIND)!;
const detail = () => cat().detail;

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('Notifications · 💎 capital quality improved (2026-09-22)', () => {
  beforeEach(() => {
    togglePref.mockClear();
    devicePrefs[KIND] = false;
  });

  it('renders the 💎 toggle in Trading signals', () => {
    draw();
    expect(screen.getByText('Trading signals')).toBeTruthy();
    expect(screen.getByText('Capital quality improved')).toBeTruthy();
    expect(cat().group).toBe('trading');
    expect(cat().emoji).toBe('💎');
  });

  it('clicking it round-trips togglePref(endpoint, capital_quality_upgrade)', () => {
    draw();
    fireEvent.click(screen.getByText('Capital quality improved').closest('button')!);
    expect(togglePref).toHaveBeenCalledWith('https://push.example/aaa', KIND);
  });

  const toggleIn = (container: HTMLElement) => {
    const btn = Array.from(container.querySelectorAll('button'))
      .find((b) => b.getAttribute('title') === detail());
    expect(btn).toBeTruthy();
    return btn as HTMLButtonElement;
  };

  it('NEGATIVE: reads OFF in its shipped state, and on only once he flips it', () => {
    expect(toggleIn(draw().container).style.background).toBe('transparent');
    cleanup();
    devicePrefs[KIND] = true;
    expect(toggleIn(draw().container).style.background).toContain('16, 185, 129');
  });

  it('NEGATIVE: it is NOT in the Essentials preset, which mirrors the keep-set', () => {
    const essentials = PRESETS.find((p) => p.id === 'essentials')!;
    expect(KIND in (essentials.pref as any)).toBe(false);
    // "All on" DOES carry it — that preset means all on, and it is derived
    // from CATEGORIES rather than typed, so this is a derivation check.
    expect((PRESETS.find((p) => p.id === 'all_on')!.pref as any)[KIND]).toBe(true);
    expect((PRESETS.find((p) => p.id === 'all_off')!.pref as any)[KIND]).toBe(false);
  });

  it('the detail says it is off, what fires, and every thing that never fires', () => {
    const d = detail();
    for (const phrase of [
      'OFF BY DEFAULT',
      'Filter and have alerts and new look out for such companies where whcih have very high quality',
      'BALANCE-SHEET line on a NEW FISCAL QUARTER',
      'net cash', 'free-cash-flow positive', 'share count stopped rising',
      'return on capital turned positive',
      'It is a CROSSING, not a state',
      'became KNOWN',                    // unknown -> pass never fires
      'because a PEER filed',            // the relative legs never fire
      'same quarter twice',              // the latch
      'DETERIORATION',                   // the downgrade side is his call
      'records a baseline and sends nothing',
      'NOTHING GATES IT',
      'NOT MEASURED',
      'It is a screen, not an edge',
      '17:52 ET',
    ]) {
      expect(d, `detail is missing: ${phrase}`).toContain(phrase);
    }
  });

  it('NEGATIVE: the detail claims no edge, invents no threshold, and never says "bounce"', () => {
    const d = detail();
    expect(d.toLowerCase()).not.toContain('bounce');   // every surface says "reversal"
    for (const overclaim of ['backtested and', 'proven', 'edge over', 'win rate',
      'expectancy', 'outperform', 'we recommend', 'recommended', 'should buy']) {
      expect(d.toLowerCase(), `detail overclaims: ${overclaim}`).not.toContain(overclaim);
    }
    // …and it disclaims in the house wording.
    expect(d).toContain('Not a recommendation');
    // The four legs are SIGN TESTS. A percentage or a multiple in this copy
    // would be a threshold somebody picked — the Bonde fabrication lesson.
    // (The 5% that survives is his own 2026-09-05 zone gate, quoted to say it
    // does NOT apply here.)
    const numbers = (d.match(/\d+(\.\d+)?%/g) || []).filter((n) => n !== '5%' && n !== '1%');
    expect(numbers, `unexplained numbers in the copy: ${numbers}`).toEqual([]);
  });

  it('NEGATIVE: the detail does not leak the admin email', () => {
    expect(detail()).not.toContain('@');
  });
});

describe('alertKinds · the 💎 registry entry', () => {
  it('is registered so a push renders a label, not a raw id', () => {
    expect(ALERT_KINDS[KIND]).toBeTruthy();
    expect(ALERT_KINDS[KIND].emoji).toBe('💎');
    expect(ALERT_KINDS[KIND].group).toBe('trading');
    expect(kindLabel(KIND)).toContain('Capital quality improved');
  });
});

describe('Alerts page · the 💎 daily pass', () => {
  it('carries the pass so a silent evening can say why', async () => {
    const src = await readSource('src/pages/Alerts.tsx');
    expect(src).toContain(`{ key: '${KIND}', label: '💎 Capital quality improved' }`);
    // It belongs in the DAILY strip, not among the three RTH cadence passes:
    // a once-a-day pass that has not run at 10:00 is not late.
    const daily = src.slice(src.indexOf('const DAILY_PASSES'), src.indexOf('DAILY_SCHEDULE_FALLBACK'));
    expect(daily).toContain(KIND);
    const rth = src.slice(src.indexOf('const PASSES'), src.indexOf('const DAILY_PASSES'));
    expect(rth).not.toContain(KIND);
  });
});
