/* 🧲 Bullish GEX first on the real Chart Maps page (Ajay 2026-09-27):
 *
 *   "Can you add gex exposure bullish or bearish signal to the stocks in our
 *    chartmaps and make it sorted by bullish gex please.."
 *   → "Checkbox, ON by default" · "Also just in time GEX read too." · "One tab
 *     open both"
 *
 * The real page, fetch mocked with the hand-written §3.3 contract example
 * (components/__fixtures__/gex_contract_example_2026_09_27.json) — the tiles
 * carry only symbol + gex there, so this file adds the chart scaffolding. The
 * live-capture fixture lands in the verification step. Pinned:
 *   - the default is ON: bullish first (strongest first), then mixed, bearish,
 *     no read; untick → the served order, `?gex=off`, NO extra board fetch;
 *   - ONE just-in-time POST lands → the disagreeing tile shows close + now and
 *     moves group; a 500 keeps the nightly chips and says "live read failed";
 *   - ⚡ still pins on top of the 🧲 order; 🎯 hides the same tiles either way;
 *   - 0DTE keeps the served order even ticked, the box is disabled, chips muted.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import RAW from '../components/__fixtures__/gex_contract_example_2026_09_27.json?raw';
import { _resetGexLiveCache } from '../hooks/useGexLive';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FX = JSON.parse(RAW) as any;

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`,
  o: 100 + i * 0.1, h: 100.5 + i * 0.1, l: 99.8 + i * 0.1, c: 100.2 + i * 0.1, v: 3e6,
}));
type Tile = Record<string, unknown>;
const scaffold = (t: Tile, extra: Tile = {}): Tile => ({
  name: `${t.symbol} Inc`, href: `/sepa/${t.symbol}?tab=supply`, price: 101, chg_pct: 1.0,
  bars, bands: [{ kind: 'demand', lo: 99.5, hi: 100.4 }], lines: [], markers: [], badges: [],
  stats: [], why: 'back inside a tested band', ...t, ...extra,
});
const BOARD = (extra: Record<string, Tile> = {}) => ({
  ...FX.board,
  tiles: (FX.board.tiles as Tile[]).map((t) => scaffold(t, extra[String(t.symbol)] ?? {})),
});
const ZERO = () => ({ ...FX.zero_dte, tiles: (FX.zero_dte.tiles as Tile[]).map((t) => scaffold(t)) });

type Live = 'none' | 'ok' | 'fail';
function stub(board: Record<string, unknown>, live: Live) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => board } as unknown as Response;
    if (url.includes('/chart-maps/gex-live')) {
      if (live === 'fail') return { ok: false, status: 500, json: async () => ({}) } as unknown as Response;
      if (live === 'ok') return { ok: true, json: async () => FX.live } as unknown as Response;
      return { ok: true, json: async () => ({}) } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const calls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
const boardCalls = () => calls().filter((u) => u.includes('/chart-maps?'));
const liveCalls = () => calls().filter((u) => u.includes('/chart-maps/gex-live'));

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);

const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const box = () => document.querySelector('label.gex-toggle input[type="checkbox"]') as HTMLInputElement;
const search = () => screen.getByTestId('loc').textContent || '';
const tileOf = (sym: string) => Array.from(document.querySelectorAll('.cm-grid .cm-tile'))
  .find((el) => el.querySelector('.cm-tile-id b')?.textContent === sym) as HTMLElement | undefined;
const chipsOf = (sym: string) => Array.from(tileOf(sym)?.querySelectorAll('.cm-gex') ?? []);
const ready = async (first: string) => {
  await waitFor(() => expect(order()[0]).toBe(first));
  await waitFor(() => expect(box()).not.toBeNull());
};

const SERVED = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF', 'GGG', 'HHH', 'III'];
const NIGHTLY_ON = ['HHH', 'DDD', 'FFF', 'AAA', 'BBB', 'GGG', 'CCC', 'EEE', 'III'];
const LIVE_ON = ['HHH', 'EEE', 'FFF', 'AAA', 'BBB', 'DDD', 'GGG', 'CCC', 'III'];

describe('🧲 Bullish GEX first on Chart Maps', () => {
  beforeEach(() => { vi.restoreAllMocks(); _resetGexLiveCache(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('default ON → bullish first; untick → served order + ?gex=off, NO extra board fetch', async () => {
    vi.stubGlobal('fetch', stub(BOARD(), 'none'));
    page('/chart-maps?tab=zones');
    await ready('HHH');
    expect(box().checked).toBe(true);
    expect(order()).toEqual(NIGHTLY_ON);
    expect(search()).not.toContain('gex');
    // Every tile wears its served chip.
    for (const s of SERVED) expect(chipsOf(s).length).toBeGreaterThan(0);
    expect(chipsOf('HHH').map((c) => c.textContent)).toEqual(['🧲 GEX bullish · 3.0%']);
    expect(chipsOf('EEE').map((c) => c.textContent)).toEqual(['🧲 no GEX read']);
    expect(document.querySelector('.gex-count')!.textContent).toBe(' · 3 bullish · 1 mixed · 2 bearish · 3 no read');

    fireEvent.click(box());
    await waitFor(() => expect(search()).toContain('gex=off'));
    expect(box().checked).toBe(false);
    expect(order()).toEqual(SERVED);
    // Chips still show unticked — the box only orders.
    expect(chipsOf('HHH').map((c) => c.textContent)).toEqual(['🧲 GEX bullish · 3.0%']);

    fireEvent.click(box());
    await waitFor(() => expect(search()).not.toContain('gex'));
    expect(order()).toEqual(NIGHTLY_ON);
    expect(boardCalls()).toHaveLength(1);
    expect(boardCalls()[0]).not.toContain('gex');
  });

  it('NEGATIVE: the ?gex=off deep link lands on the served order; a junk value lands ON', async () => {
    vi.stubGlobal('fetch', stub(BOARD(), 'none'));
    page('/chart-maps?tab=zones&gex=off');
    await ready('AAA');
    expect(box().checked).toBe(false);
    expect(order()).toEqual(SERVED);
    cleanup();
    page('/chart-maps?tab=zones&gex=0');
    await ready('HHH');
    expect(box().checked).toBe(true);
  });

  it('ONE live POST for the shown names; the disagreeing tile shows close + now and moves group', async () => {
    vi.stubGlobal('fetch', stub(BOARD(), 'ok'));
    page('/chart-maps?tab=zones');
    await waitFor(() => expect(order()).toEqual(LIVE_ON));
    expect(chipsOf('DDD').map((c) => c.textContent)).toEqual(['🧲 close: bullish · 0.45%', '🧲 now: bearish · 0.62%']);
    expect(chipsOf('III').map((c) => c.textContent)).toEqual(['🧲 no options read']);
    // The pending name keeps its nightly chip; the failed name keeps its nightly chip.
    expect(chipsOf('GGG').map((c) => c.textContent)).toEqual(['🧲 GEX bearish · 1.9%']);
    expect(chipsOf('BBB').map((c) => c.textContent)).toEqual(['🧲 GEX bearish · 0.21%']);
    expect(document.querySelector('.gex-live')!.textContent).toBe(' · live: 1 still reading');
    expect(liveCalls()).toHaveLength(1);
    const init = vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
      .find((c) => String(c[0]).includes('/chart-maps/gex-live'))![1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(body.symbols).toEqual([...SERVED].sort());
    expect(body.tab).toBe('zones');
    expect(body.repoll).toBe(false);
    expect(document.querySelector('.cm-grid')!.innerHTML).not.toMatch(/NaN|undefined|\[object Object\]/);
  });

  it('NEGATIVE: live read 500 → nightly chips intact, "live read failed", nightly order', async () => {
    vi.stubGlobal('fetch', stub(BOARD(), 'fail'));
    page('/chart-maps?tab=zones');
    await ready('HHH');
    await waitFor(() => expect(document.querySelector('.gex-live-failed')).not.toBeNull());
    expect(document.querySelector('.gex-live-failed')!.textContent).toBe(' · live read failed — last close shown');
    expect(order()).toEqual(NIGHTLY_ON);
    expect(chipsOf('DDD').map((c) => c.textContent)).toEqual(['🧲 GEX bullish · 0.45%']);
  });

  it('⚡ ON → the ⚡ names first (in 🧲 order), the rest in 🧲 order', async () => {
    const burst = { state: 'burst', on: true, badge: '⚡ Momentum burst · served', title: 'served' };
    vi.stubGlobal('fetch', stub(BOARD({ CCC: { burst }, AAA: { burst } }), 'none'));
    page('/chart-maps?tab=zones&burst=1');
    await ready('AAA');
    expect(order()).toEqual(['AAA', 'CCC', 'HHH', 'DDD', 'FFF', 'BBB', 'GGG', 'EEE', 'III']);
  });

  it('🎯 hides the same tiles with and without 🧲', async () => {
    const blocked = { enterable: { verdict: 'BLOCKED', reasons: ['room'], reason_short: ['room < 5%'] } };
    vi.stubGlobal('fetch', stub(BOARD({ HHH: blocked, BBB: blocked }), 'none'));
    page('/chart-maps?tab=zones');
    await ready('DDD');
    const on = [...order()];
    expect(on).not.toContain('HHH');
    expect(on).not.toContain('BBB');
    fireEvent.click(box());
    await waitFor(() => expect(search()).toContain('gex=off'));
    const off = [...order()];
    expect([...off].sort()).toEqual([...on].sort());
    expect(off).toEqual(SERVED.filter((s) => s !== 'HHH' && s !== 'BBB'));
  });

  it('0DTE: served order even ticked, box disabled with the served reason, chips muted as served', async () => {
    vi.stubGlobal('fetch', stub(ZERO(), 'none'));
    page('/chart-maps?tab=zero_dte');
    await ready('XXX');
    expect(order()).toEqual(['XXX', 'ZZZ', 'YYY']);
    expect(box().checked).toBe(true);
    expect(box().disabled).toBe(true);
    expect(document.querySelector('.gex-sort-off')!.textContent).toBe(` · ${FX.zero_dte.gex_sort_off.label}`);
    for (const s of ['XXX', 'ZZZ', 'YYY']) {
      for (const c of chipsOf(s)) expect(c.className).toContain('cm-badge-muted');
    }
  });

  it('NEGATIVE: switching tabs never POSTs the previous tab\'s names while the new board loads', async () => {
    let release: (() => void) | null = null;
    const held = new Promise<void>((r) => { release = r; });
    const base = stub(BOARD(), 'ok');
    vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
      const url = String(u);
      if (url.includes('/chart-maps?') && url.includes('tab=zero_dte')) {
        await held;
        return { ok: true, json: async () => ZERO() } as unknown as Response;
      }
      return base(u);
    }));
    page('/chart-maps?tab=zones');
    await waitFor(() => expect(order()).toEqual(LIVE_ON));
    expect(liveCalls()).toHaveLength(1);
    const bodies = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
      .filter((c) => String(c[0]).includes('/chart-maps/gex-live'))
      .map((c) => JSON.parse(String((c[1] as RequestInit).body)));

    fireEvent.click(screen.getByRole('tab', { name: /0DTE Options/ }));
    await waitFor(() => expect(boardCalls().some((u) => u.includes('tab=zero_dte'))).toBe(true));
    // The zones payload is still on screen; give the hooks a few ticks to misfire.
    await new Promise((r) => setTimeout(r, 50));
    expect(liveCalls()).toHaveLength(1);
    for (const b of bodies()) expect(b.tab).toBe('zones');

    release!();
    await waitFor(() => expect(liveCalls()).toHaveLength(2));
    const last = bodies()[1];
    expect(last.tab).toBe('zero_dte');
    expect(last.symbols).toEqual(['XXX', 'YYY', 'ZZZ']);
    for (const s of SERVED) expect(last.symbols).not.toContain(s);
  });

  it('NEGATIVE: an older board with no gex keys renders in the served order with no chips', async () => {
    const legacy: Record<string, unknown> = {
      ...BOARD(),
      tiles: (FX.board.tiles as Tile[]).map((t) => scaffold({ symbol: t.symbol })),
    };
    for (const k of ['gex_rule', 'gex_legend', 'gex_scope', 'gex_sort_off', 'gex_counts', 'gex_as_of', 'gex_note']) delete legacy[k];
    vi.stubGlobal('fetch', stub(legacy, 'none'));
    page('/chart-maps?tab=zones');
    await ready('AAA');
    expect(order()).toEqual(SERVED);
    expect(document.querySelectorAll('.cm-grid .cm-gex')).toHaveLength(0);
    expect(document.querySelector('.gex-count')!.textContent).toBe('');
    expect(document.querySelector('label.gex-toggle')!.outerHTML).not.toMatch(/undefined|NaN/);
  });
});
