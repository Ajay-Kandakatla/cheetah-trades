/* ChartMapsStrategiesTab — the Trading page's 🗺️ Chart Maps view (2026-09-27).
 *
 * Ajay: "stop minerviews use all strategies from Most used from Chart maps.
 * All of them and journal the," / "analayze losses everyday … and
 * restategize and confirm with me". The tab carries four writes on a paper
 * account he trades from, so every write is pinned with its negatives:
 * turning a strategy or the program ON asks first and OFF does not, Confirm on
 * a proposal ALWAYS goes through a dialog (a code-level card says nothing in
 * the engine changes), Dismiss sends no config, and nothing here ever POSTs an
 * order. Rows render in the SERVED (usage) order off a payload shaped like the
 * live 2026-09-27 read; an unknown sid renders instead of crashing; a stale
 * snapshot says why; an existing lane that is capped says why; and no string
 * he reads says "bounce". */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LIVE from './__fixtures__/cm_strategies_live_2026_09_27.json';
import { ChartMapsStrategiesTab } from './ChartMapsStrategiesTab';
import { CODE_CONFIRM_TEXT, NO_REVIEW_TEXT, UNMEASURED_TEXT, type CmReview, type CmStrategiesPayload, type CmStrategyRow } from '../lib/chartMapsLanes';

type Call = { url: string; init?: RequestInit };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const base = (): CmStrategiesPayload => clone(LIVE) as unknown as CmStrategiesPayload;
const row = (p: CmStrategiesPayload, sid: string): CmStrategyRow => p.strategies!.find((r) => r.sid === sid)!;

const REVIEW: CmReview = {
  day: '2026-09-28', built_at: '2026-09-28T17:00:12-04:00', version: 'lane-review-v1',
  program: { enabled: true, started: '2026-09-28', order: ['zones', 'deep_demand'] },
  strategies: [
    { sid: 'deep_demand', label: 'Deep Demand', losers_today: ['CTOS −0.92R −$187 · in: 🎯 READY, band 9.23–9.45, room +5.6% → 10.21 (Deep Demand, cm-lanes-v1) · what happened: shakeout · out: stop'] },
    { sid: 'quick_bounce', label: 'quick_bounce', losers_today: ['ABC −1.00R −$40 · in: 🎯 READY reversal (quick_bounce) · out: stop'] },
    { sid: 'amd', losers_today: [] },
  ],
  proposals: [
    { id: 'p_kill_amd01', sid: 'amd', kind: 'pause', level: 'config', title: 'Pause AMD Raided (n 21, exp R CI below 0)', status: 'proposed',
      change: { key: 'cm_lanes', value: { amd: false } }, evidence: { n_closed: 21, exp_r_ci: [-0.61, -0.04] } },
    { id: 'p_code_dd02', sid: 'deep_demand', kind: 'class', level: 'code', title: 'Stop buffer (3 shakeouts)', status: 'proposed',
      change: { key: 'code', value: 'stop buffer' }, evidence: { class: 'shakeout', n: 3 } },
    { id: 'p_old03', sid: 'zones', kind: 'class', level: 'config', title: 'min touches 2', status: 'dismissed',
      change: { key: 'zone_edge_rules', value: { min_touches: 2 } } },
  ],
  summary_lines: ['2 strategies entered today; 2 losers.'],
};

function stub(payload: CmStrategiesPayload | null, review: CmReview | null | 404, calls: Call[], postStatus = 200) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    if (init?.method === 'POST') {
      return Promise.resolve({ ok: postStatus < 400, status: postStatus, json: async () => (postStatus < 400 ? { ok: true } : { detail: 'already dismissed' }) });
    }
    if (u.includes('/trading/review/latest')) {
      if (review === 404) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      return Promise.resolve({ ok: true, status: 200, json: async () => review ?? {} });
    }
    if (payload === null) return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
    return Promise.resolve({ ok: true, status: 200, json: async () => payload });
  }));
}
const posts = (calls: Call[]) => calls.filter((c) => c.init?.method === 'POST');
const mount = (onChanged?: () => void) => render(<MemoryRouter><ChartMapsStrategiesTab onChanged={onChanged} /></MemoryRouter>);
const rowEl = (sid: string) => document.querySelector(`tr[data-sid="${sid}"]`) as HTMLElement;

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('ChartMapsStrategiesTab — the live-shaped payload', () => {
  it('renders the 22 lanes in SERVED order with 10 ON, and the 7 "not a lane" tabs folded', async () => {
    const calls: Call[] = [];
    stub(base(), 404, calls);
    mount();
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    const sids = Array.from(document.querySelectorAll('tbody tr')).map((r) => r.getAttribute('data-sid'));
    expect(sids).toEqual(base().strategies!.map((r) => r.sid));
    expect(sids.slice(0, 3)).toEqual(['zones', 'deep_demand', 'hot_sectors']);
    expect(screen.getAllByRole('button', { name: / ON$/ })).toHaveLength(10);
    expect(screen.getByText('Not a lane (7)')).toBeInTheDocument();
    expect(document.querySelector('li[data-tab="vcp"]')?.textContent).toMatch(/OFF with Minervini/);
    expect(screen.getByText(UNMEASURED_TEXT)).toBeInTheDocument();
    expect(screen.getByTestId('cm-open').textContent).toMatch(/^4 \/ 15 open \(0 pending\)/);
    expect(screen.getByTestId('cm-caps').textContent).toMatch(/0\.25% risk a trade · 1 a day and 2 open per strategy · 15 open in all · 1 buy a minute/);
    expect(screen.getByText(NO_REVIEW_TEXT)).toBeInTheDocument();
    // It polls exactly the two reads and never POSTs on mount.
    expect(calls.some((c) => c.url.endsWith('/trading/strategies'))).toBe(true);
    expect(calls.some((c) => c.url.includes('/trading/review/latest?format=full'))).toBe(true);
    expect(posts(calls)).toHaveLength(0);
  });

  it('a LIST row shows its note: a READY demand reversal on the tab list, not the tab setup', async () => {
    stub(base(), 404, []);
    mount();
    await waitFor(() => expect(rowEl('amd')).toBeTruthy());
    expect(rowEl('amd').textContent).toMatch(/READY demand reversal on a name from this tab's list, not the tab's own setup/);
    expect(rowEl('patterns').textContent).toMatch(/never on the breakout; most are cup-with-handle bases/);
    expect(within(rowEl('amd')).getByText('MEASURED INVERTED')).toBeInTheDocument();
    expect(within(rowEl('catalysts')).getByText('UNMEASURED')).toBeInTheDocument();
  });

  it('NEGATIVE: nothing he reads says "bounce" — the quick_bounce sid prints as Quick Reversal', async () => {
    const p = base();
    row(p, 'zones').today = { skips: { 'program-cap: quick_bounce daily cap 1 reached': 2 } };
    stub(p, REVIEW, []);
    mount();
    await waitFor(() => expect(rowEl('quick_bounce')).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/CTOS −0.92R/)).toBeInTheDocument());
    expect(rowEl('quick_bounce').textContent).toMatch(/Quick Reversal/);
    const text = document.body.textContent ?? '';
    expect(text).not.toMatch(/bounc/i);
  });

  it('NEGATIVE: an unknown sid in the payload renders instead of crashing', async () => {
    const p = base();
    p.strategies!.push({ sid: 'mystery_lane' } as CmStrategyRow);
    p.strategies!.push({ sid: 'bare', scoreboard: null, today: null, snapshot: null, prior: null, switch: null } as CmStrategyRow);
    stub(p, 404, []);
    mount();
    await waitFor(() => expect(rowEl('mystery_lane')).toBeTruthy());
    expect(rowEl('mystery_lane').textContent).toMatch(/mystery lane/);
    expect(rowEl('mystery_lane').textContent).toMatch(/UNMEASURED/);
    expect(document.body.textContent).not.toMatch(/NaN|undefined|\[object Object\]/);
  });

  it('a stale snapshot shows "stale" and its served reason', async () => {
    stub(base(), 404, []);
    mount();
    await waitFor(() => expect(rowEl('bonde')).toBeTruthy());
    expect(rowEl('bonde').textContent).toMatch(/stale — stale board \(build time unknown\)/);
    expect(rowEl('deep_demand').textContent).toMatch(/stale — stale snapshot \(built another day\)/);
    // NEGATIVE: an existing lane has no snapshot and is not called stale.
    expect(rowEl('zones').textContent).not.toMatch(/stale/);
  });

  it('critic 12: a capped EXISTING lane (zones) says why it did not buy', async () => {
    const p = base();
    row(p, 'zones').today = { entries: [], skips: { 'program-cap: zones daily cap 1 reached': 3, 'program-wait: one entry per minute (taken by amd ORCL at 09:31:45 ET)': 1 } };
    stub(p, 404, []);
    mount();
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    const skips = within(rowEl('zones')).getByTestId('cm-skips');
    expect(skips.textContent).toMatch(/program-cap: zones daily cap 1 reached ×3/);
    expect(skips.querySelectorAll('li')[0].textContent).toMatch(/daily cap/);   // most first
  });

  it('the scoreboard: CIs, a null CI → "—", small n, ≈ approx, the SEPA sell count', async () => {
    const p = base();
    row(p, 'deep_demand').scoreboard = {
      n_closed: 5, n_open: 1, win_pct: 40, win_ci: [0.118, 0.769], exp_r: -0.21, exp_r_ci: [-0.83, 0.44], total_usd: -142,
      open_risk_usd: 88, n_approx: 2, exits_by_kind: { stop: 2, distribution_exit: 3 }, small_n: true,
    };
    row(p, 'amd').scoreboard = { n_closed: 3, win_pct: 33.3, win_ci: [null, null], exp_r: 0.1, exp_r_ci: null, small_n: true };
    stub(p, 404, []);
    mount();
    await waitFor(() => expect(rowEl('deep_demand')).toBeTruthy());
    const dd = rowEl('deep_demand').textContent ?? '';
    expect(dd).toMatch(/win 40% \[12%, 77%\] · exp −0\.21R \[−0\.83R, \+0\.44R\]/);
    expect(dd).toMatch(/small n/);
    expect(dd).toMatch(/≈ 2 approx/);
    expect(dd).toMatch(/SEPA sell 3/);
    expect(dd).toMatch(/risk at entry \$88/);
    const amd = rowEl('amd').textContent ?? '';
    expect(amd).toMatch(/win 33% — · exp \+0\.10R —/);
    // NEGATIVE: an empty scoreboard prints "—", never 0% and never ≈.
    expect(rowEl('growth').textContent).toMatch(/win — · exp —/);
    expect(rowEl('growth').textContent).not.toMatch(/≈|0%/);
  });

  it('warns when an existing lane\'s own switch is OFF', async () => {
    const p = base();
    row(p, 'hot_pullback').lane_switch = { key: 'hot_pullback_entry', value: false };
    stub(p, 404, []);
    mount();
    await waitFor(() => expect(rowEl('hot_pullback')).toBeTruthy());
    expect(rowEl('hot_pullback').textContent).toMatch(/lane switch OFF \(hot_pullback_entry\)/);
    expect(rowEl('zones').textContent).not.toMatch(/lane switch OFF/);
  });

  it('a failed read says so, never crashes (negative)', async () => {
    stub(null, 404, []);
    mount();
    await waitFor(() => expect(screen.getByText(/could not load: HTTP 500/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Program OFF/ })).toBeDisabled();
  });
});

describe('ChartMapsStrategiesTab — switches', () => {
  it('turning a strategy ON asks first; only "Yes, on" POSTs {cm_lanes: {sid: true}}', async () => {
    const calls: Call[] = [];
    const onChanged = vi.fn();
    stub(base(), 404, calls);
    mount(onChanged);
    await waitFor(() => expect(rowEl('keltner')).toBeTruthy());
    fireEvent.click(within(rowEl('keltner')).getByRole('button', { name: /OFF$/ }));
    expect(screen.getByRole('dialog', { name: /Turn .*KC Coiled on\?/ })).toBeInTheDocument();
    expect(posts(calls)).toHaveLength(0);                    // NEGATIVE: the click alone writes nothing
    fireEvent.click(screen.getByRole('button', { name: 'Yes, on' }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].url).toMatch(/\/trading\/config$/);
    expect(JSON.parse(String(posts(calls)[0].init?.body))).toEqual({ cm_lanes: { keltner: true } });
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it('"No" on the ON dialog writes nothing (negative)', async () => {
    const calls: Call[] = [];
    stub(base(), 404, calls);
    mount();
    await waitFor(() => expect(rowEl('ict')).toBeTruthy());
    fireEvent.click(within(rowEl('ict')).getByRole('button', { name: /OFF$/ }));
    fireEvent.click(screen.getByRole('button', { name: 'No' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(posts(calls)).toHaveLength(0);
  });

  it('turning a strategy OFF is one click, no dialog: {cm_lanes: {zones: false}}', async () => {
    const calls: Call[] = [];
    stub(base(), 404, calls);
    mount();
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    fireEvent.click(within(rowEl('zones')).getByRole('button', { name: /ON$/ }));
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(JSON.parse(String(posts(calls)[0].init?.body))).toEqual({ cm_lanes: { zones: false } });
  });

  it('the program switch: ON asks first, OFF does not', async () => {
    const calls: Call[] = [];
    stub(base(), 404, calls);
    const { unmount } = mount();
    await waitFor(() => expect(screen.getByRole('button', { name: /Program OFF/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /Program OFF/ }));
    const dlg = screen.getByRole('dialog', { name: 'Turn the Chart Maps program on?' });
    expect(dlg.textContent).toMatch(/Paper only/);
    expect(dlg.textContent).toMatch(/The 10 strategies marked ON start buying/);
    expect(posts(calls)).toHaveLength(0);
    fireEvent.click(within(dlg).getByRole('button', { name: 'Yes, on' }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(JSON.parse(String(posts(calls)[0].init?.body))).toEqual({ cm_program: true });
    unmount();

    const calls2: Call[] = [];
    const on = base();
    on.program!.enabled = true;
    stub(on, 404, calls2);
    mount();
    await waitFor(() => expect(screen.getByRole('button', { name: /Program ON/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /Program ON/ }));
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(posts(calls2)).toHaveLength(1));
    expect(JSON.parse(String(posts(calls2)[0].init?.body))).toEqual({ cm_program: false });
  });

  it('NEGATIVE: a live account cannot turn the program on', async () => {
    const calls: Call[] = [];
    const live = base();
    live.program!.mode = 'live';
    stub(live, 404, calls);
    mount();
    await waitFor(() => expect(screen.getByText(/^Live broker — the program never runs on a live account/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Program OFF/ })).toBeDisabled();
  });
});

describe('ChartMapsStrategiesTab — the daily review and its cards', () => {
  it('shows loser lines per strategy and one card per proposal; a decided card has no buttons', async () => {
    stub(base(), REVIEW, []);
    mount();
    await waitFor(() => expect(screen.getByText(/CTOS −0.92R/)).toBeInTheDocument());
    expect(screen.getByText('2 strategies entered today; 2 losers.')).toBeInTheDocument();
    expect(document.querySelector('[data-review-sid="deep_demand"]')?.textContent).toMatch(/Deep Demand/);
    expect(document.querySelector('[data-review-sid="amd"]')).toBeNull();      // no losers → no block
    const old = screen.getByRole('group', { name: 'proposal p_old03' });
    expect(old.textContent).toMatch(/dismissed/);
    expect(within(old).queryByRole('button')).toBeNull();
  });

  it('a config card: Confirm opens a dialog with level, key, before → after; only "Yes, confirm" POSTs', async () => {
    const calls: Call[] = [];
    stub(base(), REVIEW, calls);
    mount();
    const card = await screen.findByRole('group', { name: 'proposal p_kill_amd01' });
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm…' }));
    const dlg = within(card).getByRole('dialog');
    expect(dlg.textContent).toMatch(/Level: config/);
    expect(dlg.textContent).toMatch(/cm_lanes: \{"amd":true\} → \{"amd":false\}/);
    expect(posts(calls)).toHaveLength(0);                   // NEGATIVE: opening the dialog writes nothing
    fireEvent.click(within(dlg).getByRole('button', { name: 'Yes, confirm' }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].url).toMatch(/\/trading\/review\/proposals\/p_kill_amd01\/confirm$/);
    expect(posts(calls)[0].init?.body).toBeUndefined();     // the server applies the stored change, not the page
    expect(calls.some((c) => c.url.includes('/trading/config'))).toBe(false);
  });

  it('a code-level card\'s Confirm dialog says nothing in the engine changes', async () => {
    const calls: Call[] = [];
    stub(base(), REVIEW, calls);
    mount();
    const card = await screen.findByRole('group', { name: 'proposal p_code_dd02' });
    expect(card.textContent).toMatch(/code change/);
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm…' }));
    const dlg = within(card).getByRole('dialog');
    expect(dlg.textContent).toContain(CODE_CONFIRM_TEXT);
    expect(CODE_CONFIRM_TEXT).toMatch(/Nothing in the engine changes/);
    fireEvent.click(within(dlg).getByRole('button', { name: 'Cancel' }));
    expect(within(card).queryByRole('dialog')).toBeNull();
    expect(posts(calls)).toHaveLength(0);                   // NEGATIVE: Cancel writes nothing
  });

  it('Dismiss is one click and sends no config (negative)', async () => {
    const calls: Call[] = [];
    stub(base(), REVIEW, calls);
    mount();
    const card = await screen.findByRole('group', { name: 'proposal p_kill_amd01' });
    fireEvent.click(within(card).getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].url).toMatch(/\/trading\/review\/proposals\/p_kill_amd01\/dismiss$/);
    expect(posts(calls)[0].init?.body).toBeUndefined();
    expect(calls.some((c) => c.url.includes('/trading/config'))).toBe(false);
  });

  it('a refused confirm (409 already decided) prints the server reason', async () => {
    const calls: Call[] = [];
    stub(base(), REVIEW, calls, 409);
    mount();
    const card = await screen.findByRole('group', { name: 'proposal p_kill_amd01' });
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm…' }));
    fireEvent.click(within(card).getByRole('button', { name: 'Yes, confirm' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/already dismissed/));
  });

  it('NEGATIVE: no path on this tab ever POSTs an order', async () => {
    const calls: Call[] = [];
    stub(base(), REVIEW, calls);
    mount();
    await screen.findByRole('group', { name: 'proposal p_kill_amd01' });
    fireEvent.click(within(rowEl('zones')).getByRole('button', { name: /ON$/ }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    const dismiss = within(screen.getByRole('group', { name: 'proposal p_code_dd02' })).getByRole('button', { name: 'Dismiss' });
    await waitFor(() => expect(dismiss).toBeEnabled());
    fireEvent.click(dismiss);
    await waitFor(() => expect(posts(calls)).toHaveLength(2));
    for (const c of posts(calls)) expect(c.url).not.toMatch(/\/trading\/(enter|flatten|arm|options\/close|zero-dte\/close)/);
  });
});

describe('ChartMapsStrategiesTab — switch vs buying now (fix round 2026-09-27)', () => {
  it('program OFF: the switch shows the ON set, and each row says what buys NOW', async () => {
    const p = base();
    p.program!.enabled = false;
    for (const r of p.strategies!) r.buying_now = false;
    row(p, 'signals').enabled = false;
    row(p, 'signals').buying_now = true;                  // 0DTE keeps its own switch
    row(p, 'zones').buying_now = true;                    // existing lane, switch ON
    stub(p, 404, []);
    mount();
    await waitFor(() => expect(rowEl('signals')).toBeTruthy());
    expect(screen.getAllByRole('button', { name: / ON$/ })).toHaveLength(10);
    expect(within(rowEl('signals')).getByRole('button', { name: / OFF$/ })).toBeInTheDocument();
    expect(within(rowEl('signals')).getByTestId('cm-buying-now').textContent).toBe('buying now on its own lane switch (program OFF)');
    expect(within(rowEl('deep_demand')).getByRole('button', { name: / ON$/ })).toBeInTheDocument();
    expect(within(rowEl('deep_demand')).getByTestId('cm-buying-now').textContent).toBe('not buying until the program is ON');
    // NEGATIVE: switch and reality agree -> no line.
    expect(within(rowEl('zones')).queryByTestId('cm-buying-now')).toBeNull();
    expect(within(rowEl('keltner')).queryByTestId('cm-buying-now')).toBeNull();
  });

  it('NEGATIVE: program ON (buying_now == enabled everywhere) prints no buying-now line', async () => {
    const p = base();
    p.program!.enabled = true;
    for (const r of p.strategies!) r.buying_now = !!r.enabled;
    stub(p, 404, []);
    mount();
    await waitFor(() => expect(rowEl('zones')).toBeTruthy());
    expect(screen.queryAllByTestId('cm-buying-now')).toHaveLength(0);
  });
});
