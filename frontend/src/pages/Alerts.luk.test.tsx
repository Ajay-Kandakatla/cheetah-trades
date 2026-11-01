/* /alerts — the 🥇 Luk's pass row (2026-11-01, luk-tab spec §3.12 / WP-D).
 *
 * Ajay 2026-11-01: "pic the next best one like Gajjala … Implement their strategy".
 *
 * Luk's pass is a detached child of the 🚩 5-minute pass and records in SHADOW — PASS HEALTH only, never a push kind.
 * Pinned: its row renders inside [data-testid="luk-passes"] under its OWN eyebrow ("recorded in shadow, never sent ·
 * not counted in the header"), right AFTER the 🧪 gga-passes strip and BEFORE 🗓️ Daily passes. NEGATIVES: not in
 * PASSES / GG1M_PASSES / TAPE_PASSES / GGA_PASSES; the header count is unchanged by it; it is no /notifications toggle,
 * no preset key and no alert kind; alertKinds.ts, useNotificationPrefs.ts and Notifications.tsx never name "luk".
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AlertsPage, GG1M_PASSES, GGA_PASSES, LUK_PASSES, PASSES, TAPE_PASSES, sessionLine } from './Alerts';
import { CATEGORIES, PRESETS } from './Notifications';
import { ALERT_KINDS } from '../lib/alertKinds';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

const NOW = Date.parse('2026-09-05T15:00:00Z');           // Sat Sep 5, 11:00 ET
const KEY = 'luk_setup';

const fresh = (cadence: number) => ({ as_of: '2026-09-05T10:59:30-04:00', date: '2026-09-05', cadence_sec: cadence, counts: { pushed: 0 } });
function status(withLuk: boolean, lukCadence = 600) {
  const passes: Record<string, unknown> = {};
  for (const m of PASSES) passes[m.key] = fresh(m.fallbackCadenceSec);
  for (const m of GG1M_PASSES) passes[m.key] = fresh(60);
  for (const m of GGA_PASSES) passes[m.key] = fresh(300);
  if (withLuk) passes[KEY] = fresh(lukCadence);
  return {
    in_session: true, now_et: '2026-09-05T11:00:00-04:00',
    gate: { min_room_pct: 5.0, max_above_demand_pct: 1.0, min_cap_usd: 700_000_000, min_cap_txt: '$700M' },
    passes, disclaimer: 'Configured price-structure alerts. Not advice.',
  };
}
function stubFetch(st: unknown) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/alerts/status')) return { ok: true, status: 200, json: async () => st } as Response;
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  }));
}
const draw = () => render(<MemoryRouter initialEntries={['/alerts']}><AlertsPage /></MemoryRouter>);

async function src(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

beforeEach(() => {
  vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] });
  _resetAlertHistoryCache();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("/alerts — the 🥇 Luk's pass row (2026-11-01)", () => {
  it('LUK_PASSES is the one shadow row; NOT in PASSES / TAPE_PASSES / GG1M_PASSES / GGA_PASSES', () => {
    expect(LUK_PASSES.map((m) => m.key)).toEqual([KEY]);
    expect(LUK_PASSES[0].label).toBe("🥇 Luk's pass");
    expect(LUK_PASSES[0].fallbackCadenceSec).toBe(300);
    for (const list of [PASSES, TAPE_PASSES, GG1M_PASSES, GGA_PASSES]) expect(list.map((m) => m.key)).not.toContain(KEY);
  });

  it('renders its label and the SERVED cadence inside [data-testid="luk-passes"], under its own "never sent" eyebrow', async () => {
    stubFetch(status(true, 600));
    draw();
    const block = await screen.findByTestId('luk-passes');
    const row = within(block).getByTestId(`pass-${KEY}`);
    expect(within(row).getByText(LUK_PASSES[0].label)).toBeInTheDocument();
    expect(row.textContent).toContain('every 10 min');
    expect(row.textContent).toContain('last pass');
    const head = screen.getByTestId('luk-passes-head');
    expect(head.textContent).toBe("🥇 Luk's pass · recorded in shadow, never sent · not counted in the header");
    expect(block.previousElementSibling).toBe(head);
    // NEGATIVE: its eyebrow never says it rings
    expect(head.textContent).not.toMatch(/ring/i);
    // NEGATIVE: exactly one row for the kind on the page
    expect(screen.getAllByTestId(`pass-${KEY}`)).toHaveLength(1);
  });

  it('no served cadence → the fallback (every 5 min); no doc at all → "no pass yet today"', async () => {
    const st = status(true);
    delete (st.passes[KEY] as any).cadence_sec;
    stubFetch(st);
    const { unmount } = draw();
    expect((await screen.findByTestId(`pass-${KEY}`)).textContent).toContain('every 5 min');
    unmount();
    _resetAlertHistoryCache();
    stubFetch(status(false));
    draw();
    expect((await screen.findByTestId(`pass-${KEY}`)).textContent).toContain('no pass yet today');
  });

  it('sits right AFTER the 🧪 gga-passes strip and BEFORE the 🗓️ Daily passes eyebrow', async () => {
    stubFetch(status(true));
    draw();
    const block = await screen.findByTestId('luk-passes');
    const head = screen.getByTestId('luk-passes-head');
    const gga = screen.getByTestId('gga-passes');
    expect(gga.nextElementSibling).toBe(head);
    expect(gga.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const daily = screen.getByText('🗓️ Daily passes');
    expect(block.nextElementSibling).toBe(daily);
    // NEGATIVE: never inside the 1-minute, 🧪 or tape blocks
    for (const id of ['gg1m-passes', 'gga-passes', 'tape-passes']) {
      expect(screen.getByTestId(id).contains(block)).toBe(false);
    }
  });

  it('NEGATIVE: the header count is unchanged by the row (fresh or stale, present or absent)', async () => {
    const without = sessionLine(status(false) as any, '2026-09-05');
    const withFresh = sessionLine(status(true) as any, '2026-09-05');
    const stale = status(true);
    (stale.passes[KEY] as any).as_of = '2026-09-05T08:00:00-04:00';
    const withStale = sessionLine(stale as any, '2026-09-05');
    expect(withFresh).toBe(without);
    expect(withStale).toBe(without);
    expect(without).toContain(`all ${PASSES.length} passes`);
    stubFetch(stale);
    draw();
    expect((await screen.findByTestId('session-line')).textContent).toBe(without);
  });

  it('NEGATIVE: no /notifications toggle, no preset key and no alert kind for it (not a pref kind)', () => {
    expect(CATEGORIES.map((c) => String(c.key))).not.toContain(KEY);
    for (const p of PRESETS) expect(Object.keys(p.pref)).not.toContain(KEY);
    expect(Object.keys(ALERT_KINDS)).not.toContain(KEY);
  });

  it('NEGATIVE: alertKinds.ts, useNotificationPrefs.ts and Notifications.tsx never name "luk"', async () => {
    for (const rel of ['src/lib/alertKinds.ts', 'src/hooks/useNotificationPrefs.ts', 'src/pages/Notifications.tsx']) {
      const text = await src(rel);
      expect(text.length).toBeGreaterThan(0);
      expect(text).not.toMatch(/luk/i);
    }
  });
});
