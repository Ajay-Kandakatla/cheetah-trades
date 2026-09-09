/* HotPullbackBoard — the 🔥 Hot Pullback tab (2026-09-09).
 *
 * Ajay: "a new tab for hot pull back like 21 day moving average drops but have
 * a reversal from demand zones ... like DYN today which bounced back quick."
 *
 * He trades off this board with real money and the setup is rare, so the tests
 * pin the three things that would mislead him: the measured HORIZON must be on
 * screen (the edge dies by day five), an empty board must say the setup is rare
 * rather than look broken, and the near-misses must be reachable so an empty
 * list is still information. Plus the usual: no NaN, errors reported.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import {
  HotPullbackBoard, pct, money, bandText, headline, studyLine, scanLabel, scanNote,
  EMPTY_TEXT, WARMING_TEXT, NEAR_MISS_LABEL, SCAN_LABEL, SCANNING_LABEL,
} from './HotPullbackBoard';
import type { HpPayload, HpRow } from './HotPullbackBoard';

const DYN: HpRow = {
  symbol: 'DYN', date: '2026-09-08', live: false,
  close: 20.31, open: 17.08, high: 20.91, low: 17.0,
  prev_close: 24.28, change_pct: -16.35, ma21: 25.58, high_10d: 26.69,
  above_52w_low_pct: 96.3, flush_pct: -36.3, under_ma21_pct: -20.59,
  dollar_vol_musd: 48.0, vol_x: 11.2,
  reversal: { off_low_pct: 19.46, range_pos: 0.846 },
  band: { kind: 'demand', lo: 16.56, hi: 17.02, touches: 4, strength: 92 },
  plan: {
    entry_note: 'next open (measured better than the close: the signal day gaps down into it 60% of the time)',
    trigger: 20.93, stop: 16.91, risk_from_close_pct: 16.7,
    target: 25.58, target_pct: 26.0, horizon: '1-3 sessions — the edge measured gone by day 5',
  },
  misses: [],
};
const NEAR: HpRow = {
  symbol: 'REAX', close: 12.4, change_pct: -14.2, flush_pct: -21.0, under_ma21_pct: -13.0,
  reversal: { off_low_pct: 9.1, range_pos: 0.8 }, band: null,
  misses: ['the low never reached a tested demand band — the study says this is the one that matters'],
};
const NULLS: HpRow = {
  symbol: 'NULLY', close: null, change_pct: null, flush_pct: null,
  under_ma21_pct: null, reversal: null, band: null, plan: null, misses: [],
};

const STUDY = {
  events: 65, names: 56,
  next_open_fwd1_pct: 2.40, next_open_fwd2_pct: 2.85, next_open_up2_pct: 66,
  placebo_fwd1_pct: 0.05, placebo_fwd3_pct: 0.19, fwd5_p: 0.45, worst_3d_pct: -36.1,
};

const PAYLOAD: HpPayload = {
  warming: false, universe: 'full', as_of: '2026-09-09T08:12:00-04:00',
  zone_store_day: '2026-09-08', scanned: 2594, n: 1,
  rows: [DYN], near_miss: [NEAR], study: STUDY,
  rules: ['Hot first: the prior close sits at least 30% above its own 52-week low, median 50-day dollar volume at least $5M.',
          'THE EDGE DIES BY DAY 5: fwd5 +0.39%, 51% up, p=0.45. This is a 1-3 session trade, not a hold.'],
};

function stub(payload: HpPayload | null, calls: string[]) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => {
    calls.push(String(url));
    if (payload === null) return Promise.resolve({ ok: false, status: 502, json: async () => ({}) });
    return Promise.resolve({ ok: true, json: async () => payload });
  }));
}

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('pure helpers', () => {
  it('never print NaN', () => {
    expect(pct(null)).toBe('—'); expect(pct(Number.NaN)).toBe('—');
    expect(pct(-36.34)).toBe('-36.3'.concat('%')); expect(pct(2.4)).toBe('+2.4%');
    expect(money(null)).toBe('—'); expect(money(20.31)).toBe('$20.31'); expect(money(1738)).toBe('$1738');
    expect(bandText(null)).toBe('—');
    expect(bandText({ lo: 16.56, hi: 17.02, touches: 4 })).toBe('$16.56–17.02 · 4× tested');
    expect(bandText({ lo: 16.56, hi: 17.02 })).toBe('$16.56–17.02');
  });

  it('the headline says how many of how many, and flags the near-misses', () => {
    expect(headline(PAYLOAD)).toBe('1 name of 2,594 scanned · 1 one rule short');
    expect(headline({ ...PAYLOAD, n: 3, near_miss: [] })).toBe('3 names of 2,594 scanned');
    expect(headline({ warming: true })).toBe(WARMING_TEXT);
    expect(headline(null)).toBe('');
  });

  it('the study line carries the horizon and the ugly tail, from the payload', () => {
    const s = studyLine(STUDY);
    expect(s).toContain('65 events');
    expect(s).toContain('+2.85%');   // 2dp: a measured figure must not be rounded on screen
    expect(s).toContain('+2.40%');
    expect(s).toContain('66% up');
    expect(s).toContain('gone by day five');
    expect(s).toContain('-36.1%');
    expect(studyLine(null)).toBe('');
  });
});

describe('HotPullbackBoard', () => {
  it('renders the DYN row with every measured fact and the horizon on the plan', async () => {
    const calls: string[] = [];
    stub(PAYLOAD, calls);
    render(<HotPullbackBoard />);
    await screen.findByText('1 name of 2,594 scanned · 1 one rule short');
    expect(calls[0]).toMatch(/\/supply-demand\/hot-pullback$/);

    const row = screen.getByTestId('hp-row');
    expect(within(row).getByText('DYN')).toBeTruthy();
    expect(within(row).getByText('$20.31')).toBeTruthy();
    expect(within(row).getByText('-16.4%')).toBeTruthy();
    expect(within(row).getByText('11.2× volume')).toBeTruthy();
    expect(row.textContent).toContain('-36.3%');       // off the 10-day high
    expect(row.textContent).toContain('-20.6%');       // under the 21-day line
    expect(row.textContent).toContain('+19.5%');       // off the low
    expect(row.textContent).toContain('85%');          // up the range
    expect(row.textContent).toContain('$16.56–17.02 · 4× tested');

    const plan = screen.getByTestId('hp-plan');
    expect(plan.textContent).toContain('next open');
    expect(plan.textContent).toContain('$16.91');      // the stop
    expect(plan.textContent).toContain('$25.58');      // the 21-day target
    expect(plan.textContent).toContain('the edge measured gone by day 5');

    expect(document.body.textContent).not.toContain('NaN');
  });

  it('the measured study line leads the board', async () => {
    stub(PAYLOAD, []);
    render(<HotPullbackBoard />);
    const s = await screen.findByTestId('hp-study');
    expect(s.textContent).toContain('placebo');
    expect(s.textContent).toContain('gone by day five');
  });

  it('an empty board says the setup is RARE, not that something broke', async () => {
    stub({ ...PAYLOAD, n: 0, rows: [], near_miss: [] }, []);
    render(<HotPullbackBoard />);
    expect(await screen.findByText(EMPTY_TEXT)).toBeTruthy();
    expect(screen.queryAllByTestId('hp-row')).toHaveLength(0);
    expect(EMPTY_TEXT).toContain('65 in two years');
  });

  it('near-misses are behind one click and name the rule that failed', async () => {
    stub(PAYLOAD, []);
    render(<HotPullbackBoard />);
    const btn = await screen.findByRole('button', { name: `${NEAR_MISS_LABEL} (1)` });
    expect(screen.queryByTestId('hp-near')).toBeNull();
    fireEvent.click(btn);
    const near = screen.getByTestId('hp-near');
    expect(near.textContent).toContain('REAX');
    expect(near.textContent).toContain('never reached a tested demand band');
  });

  it('the rules panel is collapsed until asked and prints the horizon rule', async () => {
    stub(PAYLOAD, []);
    render(<HotPullbackBoard />);
    const btn = await screen.findByRole('button', { name: 'ℹ️ What decides a row' });
    expect(screen.queryByText(/THE EDGE DIES BY DAY 5/)).toBeNull();
    fireEvent.click(btn);
    expect(screen.getByText(/THE EDGE DIES BY DAY 5/)).toBeTruthy();
  });

  it('says so while warming, and reports a failed load (negative)', async () => {
    stub({ warming: true, rows: [] }, []);
    const a = render(<HotPullbackBoard />);
    expect(await screen.findAllByText(WARMING_TEXT)).toHaveLength(2);
    a.unmount();
    stub(null, []);
    render(<HotPullbackBoard />);
    expect(await screen.findByText(/Could not load: HTTP 502/)).toBeTruthy();
  });

  it('a row of nulls renders without NaN and without a plan block', async () => {
    stub({ ...PAYLOAD, rows: [NULLS], near_miss: [] }, []);
    render(<HotPullbackBoard />);
    await screen.findByText('NULLY');
    expect(screen.queryByTestId('hp-plan')).toBeNull();
    expect(document.body.textContent).not.toContain('NaN');
  });
});

/* The Scan button (2026-09-09).
 *
 * Ajay: "can you give me a scan button in hot pull back or just do a scan
 * please". The board had a Refresh that only re-read the 3-minute cache — it
 * could not rescan, so pressing it looked like nothing happened. Scan sends
 * force=true, which now blocks on the backend for a real universe walk. */
describe('the Scan button', () => {
  it('asks the backend to actually rescan, not just re-read the cache', async () => {
    const calls: string[] = [];
    stub(PAYLOAD, calls);
    render(<HotPullbackBoard />);
    const btn = await screen.findByRole('button', { name: SCAN_LABEL });
    expect(calls[0]).not.toContain('force');          // first load rides the cache
    fireEvent.click(btn);
    expect(calls[1]).toContain('force=true');
  });

  it('shows it is working and refuses a second click mid-scan (negative)', async () => {
    const calls: string[] = [];
    let release: (v: any) => void = () => {};
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => {
      calls.push(String(url));
      if (calls.length === 1) return Promise.resolve({ ok: true, json: async () => PAYLOAD });
      return new Promise((res) => { release = () => res({ ok: true, json: async () => PAYLOAD }); });
    }));
    render(<HotPullbackBoard />);
    const btn = await screen.findByRole('button', { name: SCAN_LABEL });
    fireEvent.click(btn);
    const busy = await screen.findByRole('button', { name: SCANNING_LABEL });
    expect(busy.getAttribute('aria-busy')).toBe('true');
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(busy);
    expect(calls).toHaveLength(2);                    // the second click did nothing
    release(null);
    await screen.findByRole('button', { name: SCAN_LABEL });
  });

  it('prints a receipt so a scan that found nothing new is still visibly a scan', async () => {
    stub(PAYLOAD, []);
    render(<HotPullbackBoard />);
    expect(await screen.findByText('scanned 2,594 names at 08:12:00')).toBeTruthy();
  });

  it('the helpers never invent a receipt (negative)', () => {
    expect(scanLabel(false)).toBe(SCAN_LABEL);
    expect(scanLabel(true)).toBe(SCANNING_LABEL);
    expect(scanNote(null)).toBe('');
    expect(scanNote({ warming: true, scanned: 10 })).toBe('');
    expect(scanNote({ scanned: null as any })).toBe('');
    expect(scanNote({ scanned: Number.NaN })).toBe('');
    expect(scanNote({ scanned: 7 })).toBe('scanned 7 names');
  });
});
