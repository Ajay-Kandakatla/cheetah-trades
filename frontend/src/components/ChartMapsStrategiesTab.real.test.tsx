/* ChartMapsStrategiesTab — rendered from a REAL /trading/strategies payload (2026-09-27).
 *
 * The earlier fixture (cm_strategies_live_2026_09_27.json) was hand-built to the
 * spec. This one is captured: `chart_maps_lanes.strategies_payload()` from the
 * branch code, run in a throwaway container against a throwaway Mongo seeded
 * with a read-only copy of the live trading config, usage_stats, journal and
 * options / 0DTE positions, with a FAKE broker (no positions, paper). Nothing was
 * written to production. The program is OFF in it (no cm_* keys live yet), so
 * this pins what he sees on the first deploy. */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import REAL from './__fixtures__/cm_strategies_real_2026_09_27.json';
import { ChartMapsStrategiesTab } from './ChartMapsStrategiesTab';
import { NO_REVIEW_TEXT, UNMEASURED_TEXT, type CmStrategiesPayload } from '../lib/chartMapsLanes';

type Call = { url: string; init?: RequestInit };
const payload = (): CmStrategiesPayload => JSON.parse(JSON.stringify(REAL)) as CmStrategiesPayload;
const DEFAULT_ON = ['zones', 'deep_demand', 'catalysts', 'amd', 'bonde', 'hot_pullback', 'growth', 'quick_bounce', 'patterns', 'breaking'];

function stub(calls: Call[]) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    if (String(url).includes('/trading/review/latest')) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    return Promise.resolve({ ok: true, status: 200, json: async () => payload() });
  }));
}
const rowEl = (sid: string) => document.querySelector(`tr[data-sid="${sid}"]`) as HTMLElement;
const switchOf = (sid: string) => rowEl(sid).querySelector('button[aria-pressed]') as HTMLButtonElement;

afterEach(() => { vi.unstubAllGlobals(); });

describe('ChartMapsStrategiesTab — the captured real payload', () => {
  it('the fixture is the real shape: 22 lanes, 7 not-a-lane tabs, program OFF on paper', () => {
    const p = payload();
    expect(p.strategies).toHaveLength(22);
    expect(p.not_lanes).toHaveLength(7);
    expect(p.program?.switch).toBe(false);
    expect(p.program?.enabled).toBe(false);
    expect(p.program?.mode).toBe('paper');
    expect(p.strategies!.filter((r) => r.default_on).map((r) => r.sid).sort()).toEqual([...DEFAULT_ON].sort());
  });

  it('renders every row in served order with the 10 default-ON switches ON and the rest OFF', async () => {
    const calls: Call[] = [];
    stub(calls);
    render(<MemoryRouter><ChartMapsStrategiesTab /></MemoryRouter>);
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    const sids = Array.from(document.querySelectorAll('tbody tr')).map((r) => r.getAttribute('data-sid'));
    expect(sids).toEqual(payload().strategies!.map((r) => r.sid));
    for (const sid of DEFAULT_ON) {
      expect(switchOf(sid).getAttribute('aria-pressed'), sid).toBe('true');
      expect(switchOf(sid).getAttribute('aria-label'), sid).toMatch(/ ON$/);
    }
    // NEGATIVE: every other lane (hot_sectors, signals, keltner, ...) is OFF.
    for (const sid of sids.filter((s) => !DEFAULT_ON.includes(s!))) {
      expect(switchOf(sid!).getAttribute('aria-pressed'), sid!).toBe('false');
    }
    expect(screen.getAllByRole('button', { name: / ON$/ })).toHaveLength(10);
    // NEGATIVE: nothing is POSTed on mount.
    expect(calls.filter((c) => c.init?.method === 'POST')).toHaveLength(0);
  });

  it('shows the program switch OFF on the paper account, the caps and the unmeasured line', async () => {
    stub([]);
    render(<MemoryRouter><ChartMapsStrategiesTab /></MemoryRouter>);
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    const prog = screen.getByRole('button', { name: 'Program OFF — turn on' });
    expect(prog.getAttribute('aria-pressed')).toBe('false');
    expect(prog).not.toBeDisabled();
    expect(screen.getByText('paper account')).toBeInTheDocument();
    expect(screen.getByTestId('cm-caps').textContent).toMatch(/0\.25% risk a trade/);
    expect(screen.getByTestId('cm-open').textContent).toMatch(/^0 \//);
    expect(screen.getByText(UNMEASURED_TEXT)).toBeInTheDocument();
    expect(screen.getByText(NO_REVIEW_TEXT)).toBeInTheDocument();
  });

  it('folds VCP and topping under "Not a lane"', async () => {
    stub([]);
    render(<MemoryRouter><ChartMapsStrategiesTab /></MemoryRouter>);
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    expect(screen.getByText('Not a lane (7)')).toBeInTheDocument();
    expect(document.querySelector('li[data-tab="vcp"]')?.textContent).toMatch(/OFF with Minervini/);
    expect(document.querySelector('li[data-tab="topping"]')?.textContent).toMatch(/long-only/);
    // NEGATIVE: neither is a lane row.
    expect(rowEl('vcp')).toBeNull();
    expect(rowEl('topping')).toBeNull();
  });

  it('NEGATIVE: no NaN, undefined, [object Object] or "bounce" anywhere in the rendered text', async () => {
    stub([]);
    render(<MemoryRouter><ChartMapsStrategiesTab /></MemoryRouter>);
    await waitFor(() => expect(rowEl('earnings')).toBeTruthy());
    const text = document.body.textContent ?? '';
    expect(text).not.toMatch(/NaN|undefined|\[object Object\]/);
    expect(text).not.toMatch(/bounc/i);
    expect(rowEl('quick_bounce').textContent).toMatch(/Quick Reversal/);
  });
});

describe('ChartMapsStrategiesTab — the served broker-error open block', () => {
  it('NEGATIVE: an unreadable broker (open.error, as status_block serves it) never reads "0 open"', async () => {
    const p = payload();
    p.program!.open = { error: 'BrokerError: 503' };
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: unknown) => (String(url).includes('/trading/review/latest')
      ? Promise.resolve({ ok: false, status: 404, json: async () => ({}) })
      : Promise.resolve({ ok: true, status: 200, json: async () => p }))));
    render(<MemoryRouter><ChartMapsStrategiesTab /></MemoryRouter>);
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    const line = screen.getByTestId('cm-open').textContent ?? '';
    expect(line).toMatch(/^open count unavailable \(broker: BrokerError: 503\) \/ 5 max/);
    expect(line).not.toMatch(/^0 \//);
  });
});
