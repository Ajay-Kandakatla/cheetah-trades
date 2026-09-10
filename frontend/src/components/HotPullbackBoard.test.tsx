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
  r, correctionLine, funnelNote,
  EMPTY_TEXT, WARMING_TEXT, NEAR_MISS_LABEL, SCAN_LABEL, SCANNING_LABEL, CORRECTION_TEXT,
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
    entry_note: 'next open — the entry the corrected study measures and the paper lane trades',
    trigger: 20.93, stop: 16.91, risk_from_close_pct: 16.7,
    target: 25.58, target_pct: 26.0, horizon: "1-3 sessions — the lane's clock. No measured edge at any horizon.",
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

/* The CORRECTED study block (2026-09-09). The board previously advertised
 * +0.27R off a backtest that started at bar 300 instead of 252. */
const STUDY = {
  events: 83, names: 71, sim_n: 83, sim_distinct_dates: 50,
  sim_win_pct: 51.8, sim_mean_pct: 0.75, sim_expectancy_r: 0.10,
  sim_median_risk_pct: 8.8, sim_worst_pct: -14.61,
  ci_lo_r: -0.18, ci_hi_r: 0.40, p_r_le_zero: 0.26,
  one_per_date_r: -0.031, survivorship_r: 0.0,
  no_band_p: 0.191, band_separation_r: 0.093,
};

const PAYLOAD: HpPayload = {
  warming: false, universe: 'full', as_of: '2026-09-09T08:12:00-04:00',
  zone_store_day: '2026-09-08', scanned: 2594, n: 1,
  rows: [DYN], near_miss: [NEAR], study: STUDY,
  rules: ['Hot first: the prior close sits at least 30% above its own 52-week low, median 50-day dollar volume at least $5M.',
          'NO MEASURED EDGE. 83 trades on 50 dates: 51.8% win, expectancy +0.1R. The 95% interval INCLUDES ZERO.'],
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

  it('the study line leads with the expectancy AND its interval', () => {
    const s = studyLine(STUDY);
    expect(s).toContain('NO MEASURED EDGE');
    expect(s).toContain('83 trades on 50 dates');
    expect(s).toContain('51.8% win');
    expect(s).toContain('+0.10R');          // 2dp: +0.1R reads bigger than it is
    expect(s).toContain('-0.18R');
    expect(s).toContain('+0.40R');
    expect(s).toContain('includes zero');   // the finding, not a footnote
    expect(s).toContain('-0.03R');          // one trade per date
    expect(s).toContain('watchlist, not an edge');
    expect(studyLine(null)).toBe('');
    expect(studyLine({} as any)).toBe('');
  });

  it('the invalidated numbers can never come back through the study line (negative)', () => {
    // The CORRECTION line quotes the old figures on purpose — the study line
    // is the one that must never assert them again.
    const s = studyLine(STUDY);
    for (const gone of ['+2.40%', '+2.85%', '58% win', '+0.27R', '66% up', '-36.1%']) {
      expect(s).not.toContain(gone);
    }
    expect(correctionLine(STUDY)).toContain('+0.27R');   // stated, as history
  });

  it('R is always two decimals and never NaN', () => {
    expect(r(0.1)).toBe('+0.10R');
    expect(r(-0.031)).toBe('-0.03R');
    expect(r(0)).toBe('+0.00R');
    expect(r(null)).toBe('—');
    expect(r(Number.NaN)).toBe('—');
  });

  it('the correction is stated, not quietly applied', () => {
    expect(correctionLine(STUDY)).toBe(CORRECTION_TEXT);
    expect(CORRECTION_TEXT).toContain('+0.27R');    // says what it USED to claim
    expect(CORRECTION_TEXT).toContain('2.3x');
    expect(CORRECTION_TEXT).toContain('NOT load-bearing');
    expect(correctionLine(null)).toBe('');
    expect(correctionLine({} as any)).toBe('');
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
    expect(plan.textContent).toContain('No measured edge at any horizon');

    expect(document.body.textContent).not.toContain('NaN');
  });

  it('the measured study line leads the board, with the correction under it', async () => {
    stub(PAYLOAD, []);
    render(<HotPullbackBoard />);
    const s = await screen.findByTestId('hp-study');
    expect(s.textContent).toContain('NO MEASURED EDGE');
    expect(s.textContent).toContain('includes zero');
    const c = screen.getByTestId('hp-corrected');
    expect(c.textContent).toContain('Corrected 2026-09-09');
    expect(c.textContent).toContain('overstated about 2.3x');
  });

  it('an empty board says the setup is RARE, not that something broke', async () => {
    stub({ ...PAYLOAD, n: 0, rows: [], near_miss: [] }, []);
    render(<HotPullbackBoard />);
    expect(await screen.findByText(EMPTY_TEXT)).toBeTruthy();
    expect(screen.queryAllByTestId('hp-row')).toHaveLength(0);
    expect(EMPTY_TEXT).toContain('83 in a year');
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
    expect(screen.queryByText(/INCLUDES ZERO/)).toBeNull();
    fireEvent.click(btn);
    expect(screen.getByText(/INCLUDES ZERO/)).toBeTruthy();
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


/* ── the depth funnel (Ajay 2026-09-09) ────────────────────────────────────
 * "IN the hot pull back can you add more than 20% too.. I think we are not
 *  seeing some becuz of that limit."
 * There is no limit: the flush rule is a floor. The board now prints WHY it is
 * empty instead, so the question answers itself on screen. */
describe('HotPullbackBoard — the depth funnel', () => {
  const funnel = {
    note: '77 names fell more than 20% off their 10-day high today and 76 of them closed '
      + 'less than 8% off the low — freefall, not a pullback. There is no upper limit on '
      + 'the flush: the rule asks for AT LEAST 12%.',
    deep_cut_pct: -20, deep_n: 77, deep_qualified: 0, deep_no_snapback: 76,
  };

  it('prints the funnel on an empty board', () => {
    expect(funnelNote({ rows: [], funnel })).toMatch(/77 names fell more than 20%/);
    expect(funnelNote({ rows: [], funnel })).toMatch(/no upper limit/);
  });

  it('says nothing when the server sent no funnel (NEGATIVE, old payload)', () => {
    expect(funnelNote({ rows: [] })).toBe('');
    expect(funnelNote({ rows: [], funnel: null })).toBe('');
    expect(funnelNote({ rows: [], funnel: { deep_n: 77 } })).toBe('');
    expect(funnelNote(null)).toBe('');
    expect(funnelNote(undefined)).toBe('');
  });

  it('renders it under the empty-board line', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true, json: () => Promise.resolve({ rows: [], near_miss: [], funnel }),
    } as Response)));
    render(<HotPullbackBoard />);
    const el = await screen.findByTestId('hp-funnel');
    expect(el.textContent).toMatch(/76 of them closed less than 8% off the low/);
    expect(screen.getByText(EMPTY_TEXT)).toBeInTheDocument();
  });
});
