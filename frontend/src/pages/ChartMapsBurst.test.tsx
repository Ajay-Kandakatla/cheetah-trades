/* ⚡ Momentum burst on the real Chart Maps page (Ajay 2026-09-24):
 *
 *   "Can you add this as a check box in our filters please.."
 *   → "Pin + badge, hide nothing"
 *
 * The real page, fetch mocked with a hand-built payload in the backend's
 * READ_KEYS shape (spec §3.1). Five tiles, #3 and #5 served ⚡. What is pinned:
 *   - OFF is the served order with no ⚡ chip, and the checkbox already counts 2;
 *   - ON is `?burst=1`, the ⚡ names first in their own order, then the rest in
 *     theirs — a permutation, nothing hidden — and the count == the names pinned;
 *   - toggling never refetches the board (the read already rides on every tile);
 *   - a ⚡ name the 🎯 filter holds back is counted "behind 🎯", never pinned
 *     out of nowhere, and comes back when "show all" is picked;
 *   - pre-market (every read unknown) pins nothing and says why;
 *   - a payload with no burst keys renders exactly as before;
 *   - a red day that turned up off its low (ORCL) is pinned like any other.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import type { BurstRead } from '../lib/momentumBurst';

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`,
  o: 100 + i * 0.1, h: 100.5 + i * 0.1, l: 99.8 + i * 0.1, c: 100.2 + i * 0.1, v: 3e6,
}));

const BURST = (sym: string, over: Partial<BurstRead> = {}): BurstRead => ({
  state: 'burst', on: true, reasons: [], reason_text: [], rvol: 2.1, rvol_basis: 'projected',
  rvol_actual: 0.9, rvol_projected: 2.1, session_pct: 40, projection_early: false,
  today_vol: 9e6, avg_vol_50: 1e7, session_day: '2026-09-24', off_low_pct: 0.92, low: 100,
  low_kind: 'session_low', print: 100.92, print_session: 'rth', print_source: 'snapshot',
  as_of: '2026-09-24 11:40 ET', ext_print: null, ext_as_of: null, prev_close: 99.5,
  day_chg_pct: 1.43, session: 'rth', half_day: false,
  badge: `⚡ Momentum burst · 2.10× vol · +0.92% off low`, title: `⚡ ${sym} served title`,
  measured: false, ...over,
});
const NO: BurstRead = {
  state: 'no', on: false, reasons: ['runway_used'], reason_text: ['+3.21% above today\'s low — past the limit'],
  rvol: 2.04, off_low_pct: 3.21, badge: null, title: '⚡ Not a momentum burst', measured: false,
};
const UNKNOWN: BurstRead = {
  state: 'unknown', on: false, reasons: ['premarket'], reason_text: ['pre-market'],
  badge: null, title: '⚡ Unknown: pre-market', measured: false,
};

type Tile = Record<string, unknown>;
const tile = (symbol: string, burst?: BurstRead | null, extra: Tile = {}): Tile => ({
  symbol, name: `${symbol} Inc`, href: `/sepa/${symbol}?tab=supply`, price: 101, chg_pct: 1.0,
  bars, bands: [{ kind: 'demand', lo: 99.5, hi: 100.4 }], lines: [], markers: [], badges: [],
  stats: [], why: 'back inside a tested band',
  ...(burst === undefined ? {} : { burst }), ...extra,
});

const RULE = 'Rule: served rule sentence. UNMEASURED.';
const NOTE = 'Live, 40% of the session done — served note.';
const TILES = () => [
  tile('AAA', NO), tile('BBB', null), tile('CCC', BURST('CCC')), tile('DDD', NO), tile('EEE', BURST('EEE')),
];
const BOARD = (over: Record<string, unknown> = {}) => ({
  tab: 'zones', count: 5, matched: 5, scanned: 100, tiles: TILES(),
  burst_rule: RULE, burst_note: NOTE, burst_counts: { burst: 2, no: 2, unknown: 1 },
  disclaimer: 'Study board.', ...over,
});

function stub(board: Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => board } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);

const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const chips = () => Array.from(document.querySelectorAll('.cm-grid .cm-badge-burst'));
const box = () => document.querySelector('label.mb-toggle input[type="checkbox"]') as HTMLInputElement;
const count = () => document.querySelector('label.mb-toggle .mb-count')!.textContent;
const search = () => screen.getByTestId('loc').textContent || '';
const ready = async (first: string) => {
  await waitFor(() => expect(order()[0]).toBe(first));
  await waitFor(() => expect(box()).not.toBeNull());
};

describe('⚡ Momentum burst on Chart Maps', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('OFF → ON → OFF: served order, then ⚡ pinned in their own order, then back — ONE board fetch', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=zones');
    await ready('AAA');

    // OFF — the default. Served order, no chip, the count already says 2.
    expect(box().checked).toBe(false);
    expect(order()).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE']);
    expect(chips()).toHaveLength(0);
    expect(count()).toBe(' · 2');
    expect(search()).not.toContain('burst');
    expect(screen.queryByTestId('cm-burst-note')).toBeNull();

    // ON — URL, order, chips, count == pinned.
    fireEvent.click(box());
    await waitFor(() => expect(search()).toContain('burst=1'));
    expect(order()).toEqual(['CCC', 'EEE', 'AAA', 'BBB', 'DDD']);
    expect(chips()).toHaveLength(2);
    expect(chips().map((c) => c.textContent)).toEqual([BURST('CCC').badge, BURST('EEE').badge]);
    expect(count()).toBe(` · ${chips().length}`);
    expect(screen.getByTestId('cm-burst-note').textContent).toBe(`⚡ ${NOTE}`);
    // NOTHING hidden — the ON grid is a permutation of the OFF grid.
    expect(order()).toHaveLength(5);

    // OFF again — the key is REMOVED, the served order is back.
    fireEvent.click(box());
    await waitFor(() => expect(search()).not.toContain('burst'));
    expect(order()).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE']);
    expect(chips()).toHaveLength(0);

    // The read rides on every tile: toggling never refetches, never asks the server.
    expect(boardCalls()).toHaveLength(1);
    expect(boardCalls()[0]).not.toContain('burst');
  });

  it('the ?burst=1 deep link lands pinned', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=zones&burst=1');
    await ready('CCC');
    expect(box().checked).toBe(true);
    expect(order()).toEqual(['CCC', 'EEE', 'AAA', 'BBB', 'DDD']);
    expect(chips()).toHaveLength(2);
  });

  it('NEGATIVE: a junk ?burst= value lands on the default (OFF) board', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=zones&burst=true');
    await ready('AAA');
    expect(box().checked).toBe(false);
    expect(chips()).toHaveLength(0);
  });

  it('a ⚡ name BLOCKED by 🎯 is not pinned, says "1 behind 🎯", and appears once "show all" is picked', async () => {
    const tiles = TILES();
    tiles[2] = tile('CCC', BURST('CCC'), {
      enterable: { verdict: 'BLOCKED', reasons: ['room'], reason_short: ['room < 5%'] },
    });
    vi.stubGlobal('fetch', stub(BOARD({ tiles })));
    page('/chart-maps?tab=zones&burst=1');
    await ready('EEE');

    // 🎯 holds CCC back; ⚡ pins only what is on screen and says where CCC went.
    expect(order()).toEqual(['EEE', 'AAA', 'BBB', 'DDD']);
    expect(chips()).toHaveLength(1);
    expect(count()).toBe(' · 1');
    const behind = document.querySelector('label.mb-toggle .mb-behind')!;
    expect(behind.textContent).toBe(' · 1 behind 🎯');

    fireEvent.click(document.querySelector('.cm-hidden-count-btn') as HTMLButtonElement);
    await waitFor(() => expect(order()).toEqual(['CCC', 'EEE', 'AAA', 'BBB', 'DDD']));
    expect(chips()).toHaveLength(2);
    expect(count()).toBe(' · 2');
    expect(document.querySelector('label.mb-toggle .mb-behind')).toBeNull();
    expect(boardCalls()).toHaveLength(1);
  });

  it('NEGATIVE: pre-market (every read unknown) pins nothing, counts "5 unknown", prints the served note when ON', async () => {
    const pre = 'Pre-market — served note: every read is unknown.';
    const tiles = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE'].map((s) => tile(s, UNKNOWN));
    vi.stubGlobal('fetch', stub(BOARD({ tiles, burst_note: pre, burst_counts: { burst: 0, no: 0, unknown: 5 } })));
    page('/chart-maps?tab=zones');
    await ready('AAA');
    expect(count()).toBe(' · 0');
    const unk = document.querySelector('label.mb-toggle .mb-unknown')!;
    expect(unk.textContent).toBe(' · 5 unknown');
    expect(unk.getAttribute('title')).toBe(pre);
    expect(screen.queryByTestId('cm-burst-note')).toBeNull();   // OFF: no note

    fireEvent.click(box());
    await waitFor(() => expect(screen.getByTestId('cm-burst-note').textContent).toBe(`⚡ ${pre}`));
    expect(order()).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE']);
    expect(chips()).toHaveLength(0);
  });

  it('NEGATIVE: a payload with NO burst keys renders exactly as today', async () => {
    const tiles = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE'].map((s) => tile(s));
    const legacy: Record<string, unknown> = { ...BOARD({ tiles }) };
    delete legacy.burst_rule; delete legacy.burst_note; delete legacy.burst_counts;
    vi.stubGlobal('fetch', stub(legacy));
    page('/chart-maps?tab=zones&burst=1');
    await ready('AAA');
    expect(order()).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE']);
    expect(chips()).toHaveLength(0);
    expect(count()).toBe(' · 0');
    expect(document.querySelector('label.mb-toggle .mb-unknown')).toBeNull();
    expect(document.querySelector('label.mb-toggle .mb-behind')).toBeNull();
    expect(screen.queryByTestId('cm-burst-note')).toBeNull();
    expect(document.querySelector('label.mb-toggle')!.getAttribute('title')).not.toContain('undefined');
  });

  it('a gap-down ⚡ tile (red on the day, turned up off its low — ORCL) is pinned like any other', async () => {
    const tiles = TILES();
    tiles[3] = tile('ORCL', BURST('ORCL', { prev_close: 144.56, low: 133.48, print: 134.2,
                                            off_low_pct: 0.54, day_chg_pct: -7.17 }));
    vi.stubGlobal('fetch', stub(BOARD({ tiles })));
    page('/chart-maps?tab=zones&burst=1');
    await ready('CCC');
    expect(order()).toEqual(['CCC', 'ORCL', 'EEE', 'AAA', 'BBB']);
    expect(chips()).toHaveLength(3);
    expect(count()).toBe(' · 3');
  });
});
