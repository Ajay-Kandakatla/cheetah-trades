/* PremarketEntry — the 🎯 Ready to enter section of the ⚡ Signals tab (2026-09-09).
 *
 * Ajay: "ready to enter premarket category ... from In demand and Deep demands
 * ... I need an entry signal with mood considered and demand zone and other
 * criterate we discussed." He trades off this section with real money, so the
 * tests pin: READY leads and WATCH follows, a WATCH row SAYS which measured
 * drag demoted it, BLOCKED rows are hidden behind a click but never dropped,
 * mood prints as context on every row, nulls never render as NaN, and the pass
 * selector actually changes the request.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import {
  PremarketEntry, byGrade, headline, pct, money, bandText,
  EMPTY_TEXT, WARMING_TEXT, BLOCKED_LABEL,
} from './PremarketEntry';
import type { PePayload, PeRow } from './PremarketEntry';

const READY: PeRow = {
  symbol: 'PLTR', name: 'Palantir', grade: 'READY', price: 170.3, change_pct: -2.12,
  above_band_pct: -0.3, session: 'rth', band: { lo: 169.42, hi: 170.82 },
  approach_txt: '↓ falling into the band from 174.33 (-2.1% today)',
  plan: 'buy $169.42-170.82 · stop $168.57 (0.5% under the floor, 1.0% risk) · target $185.75 (8.9R)',
  mood_txt: 'mood +44.1 bullish', drags: [], blockers: [], sources: ['demand'],
};
const WATCH: PeRow = {
  symbol: 'WLFC', grade: 'WATCH', price: 57.43, change_pct: 2.15, above_band_pct: -3.35,
  band: { lo: 57.34, hi: 59.42 },
  approach_txt: '↑ reclaiming the band from below (+2.2% today)',
  plan: 'buy $57.34-59.42 · stop $57.05 (0.5% under the floor, 0.7% risk) · target: clear runway',
  mood_txt: 'mood -20.5 leaning bearish',
  drags: [{ key: 'reclaim', text: 'reclaiming the band from below — these hit the floor stop 66% of the time, against 11% for arrivals from above' }],
  blockers: [],
};
const BLOCKED: PeRow = {
  symbol: 'SSTK', grade: 'BLOCKED', price: 5.17, change_pct: -9.9, above_band_pct: 14.2,
  band: { lo: 4.4, hi: 4.53 }, drags: [],
  blockers: ['not at the band — the print must sit between the floor and 1% above its top'],
  mood_txt: 'mood -31 bearish',
};
const NULLS: PeRow = {
  symbol: 'NULLY', grade: 'READY', price: null, change_pct: null, above_band_pct: null,
  plan: null, approach_txt: null, mood_txt: null, drags: [], blockers: [],
};

const PAYLOAD: PePayload = {
  warming: false, pass: 'session', universe: 'full', as_of: '2026-09-09T10:15:00-04:00',
  counts: { READY: 1, WATCH: 1, BLOCKED: 1 }, n: 3,
  rows: [READY, WATCH, BLOCKED], zone_store_day: '2026-09-08', market_closed: null,
  rules: ['Gate 1 — room: at least 5% to the first PROVEN band overhead (2+ touches). A clear runway passes.',
          'Mood is CONTEXT: it orders rows of the same grade and prints on every row. It can never promote, demote or block one.'],
};

function stub(payload: PePayload | null, calls: string[]) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => {
    calls.push(String(url));
    if (payload === null) return Promise.resolve({ ok: false, status: 503, json: async () => ({}) });
    return Promise.resolve({ ok: true, json: async () => payload });
  }));
}

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('pure helpers', () => {
  it('never print NaN', () => {
    expect(pct(null)).toBe('—');
    expect(pct(undefined)).toBe('—');
    expect(pct(Number.NaN)).toBe('—');
    expect(pct(-2.117)).toBe('-2.1%');
    expect(pct(1.2)).toBe('+1.2%');
    expect(money(null)).toBe('—');
    expect(money(Number.POSITIVE_INFINITY)).toBe('—');
    expect(money(57.4)).toBe('$57.40');
    expect(money(1737.99)).toBe('$1738');
  });

  it('bandText says where the print sits, and copes with a missing number', () => {
    expect(bandText({ symbol: 'X', grade: 'READY', above_band_pct: -0.3 })).toBe('0.30% inside the band');
    expect(bandText({ symbol: 'X', grade: 'READY', above_band_pct: 0.4 })).toBe('0.40% above the band');
    expect(bandText({ symbol: 'X', grade: 'READY', above_band_pct: 0 })).toBe('on the band top');
    expect(bandText({ symbol: 'X', grade: 'READY' })).toBe('at the band');
  });

  it('byGrade always returns all three buckets, even empty', () => {
    const g = byGrade([READY, WATCH, BLOCKED]);
    expect(g.READY.map((r) => r.symbol)).toEqual(['PLTR']);
    expect(g.WATCH.map((r) => r.symbol)).toEqual(['WLFC']);
    expect(g.BLOCKED.map((r) => r.symbol)).toEqual(['SSTK']);
    expect(byGrade(undefined)).toEqual({ READY: [], WATCH: [], BLOCKED: [] });
  });

  it('headline counts the grades and names the pass', () => {
    expect(headline(PAYLOAD)).toBe('1 ready · 1 watching · 1 blocked — this session');
    expect(headline({ ...PAYLOAD, pass: 'premarket', counts: { READY: 2, WATCH: 0, BLOCKED: 0 } }))
      .toBe('2 ready · 0 watching — pre-market');
    expect(headline({ warming: true })).toBe(WARMING_TEXT);
    expect(headline(null)).toBe('');
  });
});

describe('PremarketEntry', () => {
  it('leads with READY, shows the WATCH drag in words, and prints mood as context', async () => {
    const calls: string[] = [];
    stub(PAYLOAD, calls);
    render(<PremarketEntry />);
    await screen.findByText('1 ready · 1 watching · 1 blocked — this session');
    expect(calls[0]).toMatch(/\/supply-demand\/premarket-entry$/);

    const rows = screen.getAllByTestId('pe-row');
    expect(within(rows[0]).getByText('PLTR')).toBeTruthy();     // READY first
    expect(within(rows[1]).getByText('WLFC')).toBeTruthy();     // WATCH second
    expect(rows).toHaveLength(2);                               // BLOCKED not shown yet

    expect(within(rows[0]).getByText('READY')).toBeTruthy();
    expect(within(rows[0]).getByText('$170.30')).toBeTruthy();
    expect(within(rows[0]).getByText('-2.1%')).toBeTruthy();
    expect(within(rows[0]).getByText('0.30% inside the band')).toBeTruthy();
    expect(within(rows[0]).getByText(/stop \$168\.57/)).toBeTruthy();

    // the measured drag is spelled out, with its rate
    const drag = screen.getByTestId('pe-drag');
    expect(drag.textContent).toContain('66%');
    expect(drag.textContent).toContain('11%');

    // mood is present on both rows and labelled as context
    const moods = screen.getAllByTestId('pe-mood');
    expect(moods).toHaveLength(2);
    expect(moods[0].textContent).toContain('mood +44.1 bullish');
    expect(moods[0].textContent).toContain('context only');

    expect(document.body.textContent).not.toContain('NaN');
  });

  it('BLOCKED rows are behind a click but never dropped, and say why', async () => {
    const calls: string[] = [];
    stub(PAYLOAD, calls);
    render(<PremarketEntry />);
    const more = await screen.findByRole('button', { name: `${BLOCKED_LABEL} (1)` });
    expect(screen.queryByText('SSTK')).toBeNull();
    expect(more.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(more);
    expect(screen.getByText('SSTK')).toBeTruthy();
    expect(screen.getByTestId('pe-blocker').textContent).toContain('not at the band');
  });

  it('the pass selector re-requests with that pass (negative: default sends none)', async () => {
    const calls: string[] = [];
    stub(PAYLOAD, calls);
    render(<PremarketEntry />);
    await screen.findByText(/1 ready/);
    expect(calls[0]).not.toContain('pass=');
    fireEvent.change(screen.getByLabelText('Which pass'), { target: { value: 'premarket' } });
    await waitFor(() => expect(calls.some((c) => c.includes('pass=premarket'))).toBe(true));
  });

  it('the rules panel is collapsed until asked, then lists what decides a grade', async () => {
    const calls: string[] = [];
    stub(PAYLOAD, calls);
    render(<PremarketEntry />);
    const btn = await screen.findByRole('button', { name: 'ℹ️ What decides a grade' });
    expect(screen.queryByText(/at least 5% to the first PROVEN band/)).toBeNull();
    fireEvent.click(btn);
    expect(screen.getByText(/at least 5% to the first PROVEN band/)).toBeTruthy();
    expect(screen.getByText(/never promote, demote or block one/)).toBeTruthy();
  });

  it('says so in words when warming, when empty, and when the market is closed', async () => {
    const calls: string[] = [];
    stub({ warming: true, rows: [] }, calls);
    const a = render(<PremarketEntry />);
    // twice on purpose: the summary line and the body both say it while cold
    expect(await screen.findAllByText(WARMING_TEXT)).toHaveLength(2);
    expect(screen.queryByText(EMPTY_TEXT)).toBeNull();   // warming is not "nothing found"
    a.unmount();

    stub({ warming: false, rows: [], counts: { READY: 0, WATCH: 0, BLOCKED: 0 }, pass: 'session' }, calls);
    const b = render(<PremarketEntry />);
    expect(await screen.findByText(EMPTY_TEXT)).toBeTruthy();
    b.unmount();

    stub({ ...PAYLOAD, market_closed: 'holiday 2026-11-26' }, calls);
    render(<PremarketEntry />);
    expect(await screen.findByText(/Market closed \(holiday 2026-11-26\)/)).toBeTruthy();
  });

  it('a failed load reports the error instead of rendering an empty board (negative)', async () => {
    const calls: string[] = [];
    stub(null, calls);
    render(<PremarketEntry />);
    expect(await screen.findByText(/Could not load: HTTP 503/)).toBeTruthy();
    expect(screen.queryAllByTestId('pe-row')).toHaveLength(0);
  });

  it('a row of nulls renders without NaN and without a plan line', async () => {
    const calls: string[] = [];
    stub({ ...PAYLOAD, rows: [NULLS], counts: { READY: 1, WATCH: 0, BLOCKED: 0 } }, calls);
    render(<PremarketEntry />);
    await screen.findByText('NULLY');
    const row = screen.getByTestId('pe-row');
    expect(within(row).getByText('at the band')).toBeTruthy();
    expect(within(row).getAllByText('—').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('pe-mood')).toBeNull();
    expect(document.body.textContent).not.toContain('NaN');
  });

  it('collapses to a single header row when the title is clicked', async () => {
    const calls: string[] = [];
    stub(PAYLOAD, calls);
    render(<PremarketEntry />);
    await screen.findByText('PLTR');
    const toggle = screen.getByRole('button', { expanded: true });
    fireEvent.click(toggle);
    expect(screen.queryByText('PLTR')).toBeNull();
    expect(screen.getByText(/1 ready/)).toBeTruthy();     // the summary stays
  });
});
