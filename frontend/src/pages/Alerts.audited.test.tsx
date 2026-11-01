/* /alerts — the 🧪 Gajjala · Audited pass row (2026-11-01, gg-audited spec §3.8 [C4] / §4 WP-E).
 *
 * Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day.."
 * "Gajjals-Audited" "So we can keep track of improvements on this tab".
 *
 * The audit overlay rides the 🚩 5-minute pass and records every audited A+ in SHADOW — it never rings. Pinned: its
 * row renders its label and the SERVED cadence inside [data-testid="gga-passes"], under its OWN eyebrow that says
 * "never sent". NEGATIVES: the row is not a descendant of the 1-minute block, and "they ring your phone" is not an
 * eyebrow over it; the header count ("all N passes") is unchanged by the row; it is no /notifications toggle and no
 * alert kind (not a pref kind).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AlertsPage, GG1M_PASSES, GGA_PASSES, PASSES, TAPE_PASSES, sessionLine } from './Alerts';
import { CATEGORIES, PRESETS } from './Notifications';
import { ALERT_KINDS } from '../lib/alertKinds';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

const NOW = Date.parse('2026-09-05T15:00:00Z');           // Sat Sep 5, 11:00 ET
const KEY = 'gajjala_audited_setup';

const fresh = (cadence: number) => ({ as_of: '2026-09-05T10:59:30-04:00', date: '2026-09-05', cadence_sec: cadence, counts: { pushed: 0 } });
/** Every PASSES row fresh at 11:00 ET, plus (optionally) the audited row. */
function status(withGga: boolean, ggaCadence = 600, ggaCounts: Record<string, number> = { candidates: 3, aplus: 1, pushed: 0, shadow: 1, shadow_mode: 1 }) {
  const passes: Record<string, unknown> = {};
  for (const m of PASSES) passes[m.key] = fresh(m.fallbackCadenceSec);
  for (const m of GG1M_PASSES) passes[m.key] = fresh(60);
  if (withGga) passes[KEY] = { ...fresh(ggaCadence), counts: ggaCounts };
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

beforeEach(() => {
  vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] });
  _resetAlertHistoryCache();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('/alerts — the 🧪 Gajjala · Audited pass row (2026-11-01)', () => {
  it('GGA_PASSES is the one shadow row — label says never sent; NOT in PASSES / TAPE_PASSES / GG1M_PASSES', () => {
    expect(GGA_PASSES.map((m) => m.key)).toEqual([KEY]);
    expect(GGA_PASSES[0].label).toBe('🧪 Gajjala · Audited A+ (shadow — recorded, never sent)');
    expect(GGA_PASSES[0].fallbackCadenceSec).toBe(300);
    for (const list of [PASSES, TAPE_PASSES, GG1M_PASSES]) expect(list.map((m) => m.key)).not.toContain(KEY);
  });

  it('renders its label and the SERVED cadence inside [data-testid="gga-passes"], under its own "never sent" eyebrow', async () => {
    stubFetch(status(true, 600));
    draw();
    const block = await screen.findByTestId('gga-passes');
    const row = within(block).getByTestId(`pass-${KEY}`);
    expect(within(row).getByText(GGA_PASSES[0].label)).toBeInTheDocument();
    // the served cadence_sec (600) wins over the fallback (300)
    expect(row.textContent).toContain('every 10 min');
    expect(row.textContent).not.toContain('every 5 min');
    expect(row.textContent).toContain('last pass');
    // its counters print with the 🚩 A+ chip words (shadow — not sent)
    expect(row.textContent).toContain('shadow — not sent');
    const head = screen.getByTestId('gga-passes-head');
    expect(head.textContent).toContain('never sent');
    expect(head.textContent).toContain('not counted in the header');
    // NEGATIVE: its eyebrow never says it rings
    expect(head.textContent).not.toMatch(/ring/i);
  });

  it('no served cadence → the fallback (every 5 min)', async () => {
    const st = status(true);
    delete (st.passes[KEY] as any).cadence_sec;
    stubFetch(st);
    draw();
    const row = await screen.findByTestId(`pass-${KEY}`);
    expect(row.textContent).toContain('every 5 min');
  });

  it('NEGATIVE: the row is not inside the 1-minute block, and "they ring your phone" is not an eyebrow over it', async () => {
    stubFetch(status(true));
    draw();
    const row = await screen.findByTestId(`pass-${KEY}`);
    const gg1m = screen.getByTestId('gg1m-passes');
    expect(gg1m.contains(row)).toBe(false);
    for (let el: HTMLElement | null = row; el; el = el.parentElement) {
      expect(el.getAttribute('data-testid')).not.toBe('gg1m-passes');
    }
    // the nearest eyebrow ABOVE the row's block is its own head, never the 1-minute one
    const block = screen.getByTestId('gga-passes');
    expect(block.previousElementSibling?.getAttribute('data-testid')).toBe('gga-passes-head');
    expect(block.previousElementSibling?.textContent).not.toContain('they ring your phone');
    // and the 🧪 block sits AFTER the 1-minute block
    expect(gg1m.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
});
