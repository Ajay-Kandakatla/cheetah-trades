vi.mock('../lib/ggwFrames', async (orig) => (await import('../test/ggwFramesLegacy')).ggwFramesLegacy(orig));
/* 📈📐 👀 Gajjala's Watch — frames 1 / 5 / 15 · VWAP · daily supply & demand zones, the FE (2026-11-23, vwapzones spec §3.9).
 * Ajay 2026-11-23: "can you add vwap and supply demand zone in the daily time frame on the watch list please" · "I think we
 * have 15 mins too" · "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board" · "Add vwap and
 * supply demand too".
 * The real board, fetch stubbed, over a 1m / 5m / 15m payload BUILT IN THIS FILE from the 11-15 fixture (that fixture is
 * never edited — it stays "an older payload"). Every word in these payloads is a stand-in for a served one; the FE prints
 * them verbatim and composes none. NEGATIVES throughout: no 3-min anywhere, a row without `levels` draws no line and no
 * band, an out-of-range zone draws nothing (no edge marker), an older 1m/3m/5m payload still draws, the forming candle is
 * main's while GGW_SEED_FORMING is off, a card payload without the new keys is byte-identical. Display only, UNMEASURED. */
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import type { GgTile } from '../lib/gajjala';
import { EMA_BOLD, toneColor, VWAP_LINE_W, type CmBar } from '../lib/chartMaps';
import { GGC_STRETCH_ORDER, ggcIsCtx, ggcRow, parseGgc, type GgcPayload } from '../lib/gajjalaCardView';
import { GGW_CHART_H, GGW_STRETCH_ORDER, ggwLegendSwatch, parseGgw, type GgwBoard, type GgwFrame, type GgwRow } from '../lib/gajjalaWatch';
import { ggwSeedLive, type GgwLiveBar, type GgwLiveSym } from '../lib/ggwLive';

/* The tile reads GGW_SEED_FORMING through this getter so ONE test can switch it on; every other test runs it off (the
 * shipped value — pinned by source read below and by lib/ggwLive.seed_2026_11_23.test.ts on the real module). */
const seedFlag = vi.hoisted(() => ({ on: false }));
const liveCalls = vi.hoisted(() => [] as Array<{ tf: string; bars: unknown }>);
vi.mock('../lib/gajjalaWatch', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, get GGW_SEED_FORMING() { return seedFlag.on; } };
});
vi.mock('../lib/ggwLive', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, ggwLiveFrame: (f: GgwFrame, bars: unknown, o: unknown) => { liveCalls.push({ tf: f.tf, bars }); return m.ggwLiveFrame(f, bars, o); } };
});

import GajjalaWatchBoard from './GajjalaWatchBoard';
import { Tile } from './GajjalaWatchTile';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

// ── the 1m / 5m / 15m payload (built from the 11-15 fixture; stand-in words) ─────────────────────────────────────────

const fx = (v: number) => v.toFixed(2);
const range = (bars: CmBar[]) => ({ lo: Math.min(...bars.map((b) => b.l)), hi: Math.max(...bars.map((b) => b.h)) });
/** The served VWAP curve shape (backend payload.vwap_curve): null on premarket bars, a value after. */
const vwapOf = (bars: CmBar[]) => ({
  tone: 'vwap', label: 'VWAP',
  values: bars.map((b) => ((b as any).s === 'pre' ? null : Math.round(((b.h + b.l + b.c) / 3) * 1e6) / 1e6)),
});
/** A 15-min frame from a served 5-min frame (three 5-min slots to a bucket — the test's stand-in for the server's 15m). */
function fifteenFrom(f5: any): any {
  const groups = new Map<number, number[]>();
  f5.axis.x.forEach((s: number, i: number) => {
    const k = Math.floor(s / 3);
    groups.set(k, [...(groups.get(k) ?? []), i]);
  });
  const keys = [...groups.keys()];
  const bars = keys.map((k) => {
    const ix = groups.get(k)!;
    const bs = ix.map((i) => f5.tile.bars[i]);
    const s = bs[0].s;
    return { t: bs[bs.length - 1].t, o: bs[0].o, h: Math.max(...bs.map((b: any) => b.h)), l: Math.min(...bs.map((b: any) => b.l)),
      c: bs[bs.length - 1].c, v: bs.reduce((a: number, b: any) => a + b.v, 0), ...(s ? { s } : {}) };
  });
  const lastOf = (vals: Array<number | null>) => keys.map((k) => { const ix = groups.get(k)!; return vals[ix[ix.length - 1]]; });
  return {
    ...clone(f5), tf: '15m', label: '15-min',
    tile: { ...clone(f5.tile), bars, markers: [], curves: f5.tile.curves.map((c: any) => ({ ...c, values: lastOf(c.values) })) },
    axis: { ...clone(f5.axis), slots: f5.axis.slots / 3, x: keys,
      shade: f5.axis.shade.map((s: any) => ({ ...s, from_slot: Math.floor(s.from_slot / 3), to_slot: Math.floor(s.to_slot / 3) })),
      ticks: f5.axis.ticks.filter((t: any) => t.slot % 3 === 0).map((t: any) => ({ ...t, slot: t.slot / 3 })) },
    ema_cross: null, held: null,
  };
}
/** The three served zone bands of a row, set from its 1-min candle range: two INSIDE the range, one far above it. */
function zonesFor(bars: CmBar[]) {
  const r = range(bars);
  const span = r.hi - r.lo;
  const d = { lo: +fx(r.lo + span * 0.2), hi: +fx(r.lo + span * 0.35) };
  const s = { lo: +fx(r.lo + span * 0.7), hi: +fx(r.lo + span * 0.85) };
  const far = { lo: +fx(r.hi * 1.5), hi: +fx(r.hi * 1.55) };
  const band = (kind: 'board_demand' | 'board_supply', z: { lo: number; hi: number }) => ({
    kind, lo: z.lo, hi: z.hi, label: `Daily ${kind === 'board_demand' ? 'demand' : 'supply'} ${fx(z.lo)}–${fx(z.hi)}`,
    gutter: kind === 'board_demand' ? 'demand' : 'supply', ctx: true,
  });
  return { inside: [band('board_demand', d), band('board_supply', s)], far: band('board_supply', far) };
}
const LEVELS = {
  ok: (sym: string) => ({ state: 'ok', text: `served-zones-line-${sym} (ok)`, title: 'served-zones-sentence', as_of: '2026-11-20' }),
  retry: (sym: string) => ({ state: 'retry', text: `served-zones-line-${sym} (retry)`, title: 'served-zones-sentence', as_of: null }),
  none: (sym: string) => ({ state: 'none', text: `served-zones-line-${sym} (none)`, title: 'served-zones-sentence', as_of: null }),
  pending: (sym: string) => ({ state: 'pending', text: `served-zones-line-${sym} (pending)`, title: 'served-zones-sentence', as_of: null }),
};
const EMPTY_15 = 'served-no-closed-15-min-bar-words';
const VWAP_TEXT = 'served-vwap-sentence';
const ZONES_TEXT = 'served-zones-sentence';

/** OMH: 1m / 5m / 15m with VWAP + zones (ok) · AMD pending (pending) · XYZQ no_prints (none) · NVDA 1m / 5m + a 15m
 *  placeholder (retry, no bands) · PLAIN: OMH's frames with NO levels key, no VWAP, no zone (an older-shape row). */
function board155(o: { info?: boolean; org?: boolean } = {}): any {
  const b = clone(RAW);
  const [omh, amd, xyzq, nvda] = b.rows;
  const remake = (row: any, withOverlays: boolean, placeholder15 = false) => {
    const f1 = row.frames.find((f: any) => f.tf === '1m');
    const f5 = row.frames.find((f: any) => f.tf === '5m');
    const f15 = placeholder15
      ? { tf: '15m', label: '15-min', tile: { symbol: row.symbol, href: '', bars: [], curves: [], markers: [], lines: [], bands: [], stats: [], why: '' },
        axis: null, ema_cross: null, uptrend: null, held: null, ema_blink: null, ema_tail: null, empty_text: EMPTY_15 }
      : fifteenFrom(f5);
    const frames = [f1, f5, f15];
    if (withOverlays) {
      const z = zonesFor(f1.tile.bars);
      for (const f of frames) {
        if (!f.tile.bars.length) continue;
        f.tile.curves = [...f.tile.curves, vwapOf(f.tile.bars)];
        f.tile.bands = [...z.inside, z.far];
      }
    }
    return { ...row, frames };
  };
  const plain = { ...remake(clone(omh), false), symbol: 'PLAIN' };
  for (const f of plain.frames) f.tile.symbol = 'PLAIN';
  b.rows = [
    { ...remake(omh, true), levels: LEVELS.ok('OMH') },
    { ...amd, levels: LEVELS.pending('AMD') },
    { ...xyzq, levels: LEVELS.none('XYZQ') },
    { ...remake(nvda, false, true), levels: LEVELS.retry('NVDA') },
    plain,
  ];
  b.symbols = b.rows.map((r: any) => r.symbol);
  delete b.pending_poll_sec; delete b.pending_wait_max_sec;
  b.refresh_sec = 0; b.next_window_sec = null;
  b.legend = [
    ...b.legend,
    { tone: 'vwap', label: 'served-vwap-label', title: VWAP_TEXT },
    { tone: 'zone_demand', label: 'served-zone-demand-label', title: ZONES_TEXT },
    { tone: 'zone_supply', label: 'served-zone-supply-label', title: ZONES_TEXT },
  ];
  if (o.info !== false) b.info = { ...b.info, vwap_text: VWAP_TEXT, zones_text: ZONES_TEXT };
  if (o.org) {
    b.sections = [{ key: 'yours', title: 'served-title', text: 'served-head · 5', hint: 'served-hint', n: 5, symbols: b.symbols }];
    for (const r of b.rows) r.org = { group: 'yours', when: null, setup: null, ran: null, past_winner: null };
  }
  return b;
}

function stubFetch(board: () => any) {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => board() }) as unknown as Response));
}
async function mount(board: () => any, phone = false) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: phone && q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  stubFetch(board);
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch&per=9']}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r;
}
const tile = (c: HTMLElement, sym: string) => c.querySelector(`[data-testid="ggw-tile-${sym}"]`) as HTMLElement;
const frameEl = (c: HTMLElement, sym: string, tf: string) => c.querySelector(`[data-testid="ggw-frame-${sym}-${tf}"]`) as HTMLElement;
const bandTitles = (el: Element) => Array.from(el.querySelectorAll('g[data-band-kind] > rect > title')).map((t) => t.textContent);

beforeEach(() => { vi.useFakeTimers(); seedFlag.on = false; liveCalls.length = 0; });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

// ── constants + source guards ────────────────────────────────────────────────────────────────────────────────────────

describe('📈 constants: 1m / 5m / 15m, ⤢ 15 / 5 / 1, the seed OFF', () => {
  it('GGW_CHART_H keys are 1m / 5m / 15m; GGW_STRETCH_ORDER == GGC_STRETCH_ORDER == 15 / 5 / 1', () => {
    expect(Object.keys(GGW_CHART_H)).toEqual(['1m', '5m', '15m']);
    expect([...GGW_STRETCH_ORDER]).toEqual(['15m', '5m', '1m']);
    expect([...GGW_STRETCH_ORDER]).toEqual([...GGC_STRETCH_ORDER]);
  });
  it('[O2] GGW_SEED_FORMING = false sits beside GGW_LIVE_EMA_TIP (source read of the real module)', async () => {
    const src = await readSource('src/lib/gajjalaWatch.ts');
    expect(src).toMatch(/\nexport const GGW_SEED_FORMING = false;/);
    const tip = src.indexOf('export const GGW_LIVE_EMA_TIP');
    const seed = src.indexOf('export const GGW_SEED_FORMING');
    expect(tip).toBeGreaterThan(0);
    expect(seed - tip).toBeGreaterThan(0);
    expect(seed - tip).toBeLessThan(800);
  });
  it('NEGATIVE: no \'3m\' literal in the Watch lib, tile or board source', async () => {
    for (const rel of ['src/lib/gajjalaWatch.ts', 'src/components/GajjalaWatchTile.tsx', 'src/components/GajjalaWatchBoard.tsx']) {
      expect(await readSource(rel), rel).not.toMatch(/['"`]3m['"`]/);
    }
  });
  it('CSS: .ggw-levels wraps (min-width 0 + overflow-wrap anywhere); the zone swatch is the glass box (solid edge, 2026-11-23)', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    const m = css.match(/\n\.ggw-levels\s*\{([^}]*)\}/);
    expect(m).not.toBeNull();
    expect(m![1]).toMatch(/min-width:\s*0/);
    expect(m![1]).toMatch(/overflow-wrap:\s*anywhere/);
    expect(m![1]).not.toMatch(/white-space:\s*nowrap/);
    const z = css.match(/\.ggw-swatch\.ggw-swatch--zone\s*\{([^}]*)\}/);
    expect(z![1]).toMatch(/border:\s*1px solid/);   // 🟩 CHANGED 2026-11-23: the glass swatch (was dashed)
    expect(z![1]).not.toMatch(/dashed/);
    expect(z![1]).toMatch(/background:\s*transparent/);
  });
});

// ── the board ────────────────────────────────────────────────────────────────────────────────────────────────────────

describe('📈 board: 1-min on top, the 5-/15-min pair, ⤢ 15 / 5 / 1', () => {
  it('1m on top, pair [5m, 15m]; NEGATIVE: no data-tf="3m" anywhere', async () => {
    const { container } = await mount(() => board155());
    const charts = tile(container, 'OMH').querySelector('.ggw-charts')!;
    expect(charts.firstElementChild!.getAttribute('data-tf')).toBe('1m');
    expect(Array.from(charts.querySelectorAll('.ggw-frame-pair > .ggw-frame')).map((f) => f.getAttribute('data-tf'))).toEqual(['5m', '15m']);
    expect(container.querySelector('[data-tf="3m"]')).toBeNull();
    expect(charts.querySelector('.ggw-frame[data-tf="15m"] svg')!.getAttribute('viewBox')).toBe(`0 0 620 ${GGW_CHART_H['15m']}`);
  });
  it('⤢ order 15 / 5 / 1', async () => {
    const { container, getByTestId } = await mount(() => board155());
    fireEvent.click(getByTestId('ggw-stretch-btn-OMH'));
    const tfs = Array.from(document.querySelectorAll('[data-testid="ggw-stretch-charts"] > figure')).map((f) => f.getAttribute('data-tf'));
    expect(tfs).toEqual(['15m', '5m', '1m']);
    expect(container).toBeTruthy();
  });
  it('a placeholder 15-min frame prints its served words; the tile is not blank (1m + 5m still drawn)', async () => {
    const { container } = await mount(() => board155());
    expect(frameEl(container, 'NVDA', '15m').textContent).toContain(EMPTY_15);
    expect(frameEl(container, 'NVDA', '15m').getAttribute('data-empty')).toBe('1');
    expect(frameEl(container, 'NVDA', '15m').querySelector('svg')).toBeNull();
    expect(frameEl(container, 'NVDA', '1m').querySelector('svg')).not.toBeNull();
    expect(frameEl(container, 'NVDA', '5m').querySelector('svg')).not.toBeNull();
  });
  it('NEGATIVE: an older 1m / 3m / 5m payload still draws — three charts, no levels line, no VWAP, no zone band', async () => {
    const { container } = await mount(() => { const b = clone(RAW); b.refresh_sec = 0; b.next_window_sec = null; return b; });
    const t = tile(container, 'OMH');
    expect(t.querySelectorAll('svg')).toHaveLength(3);
    expect(Array.from(t.querySelectorAll('.ggw-frame-pair > .ggw-frame')).map((f) => f.getAttribute('data-tf'))).toEqual(['3m', '5m']);
    expect(container.querySelector('[data-testid^="ggw-levels-"]')).toBeNull();
    expect(container.querySelector('.pc-vwap')).toBeNull();
    expect(container.querySelector('g[data-band-kind^="board_"]')).toBeNull();
  });
});

describe('📈📐 VWAP + daily zones on every frame with bars', () => {
  it('the VWAP polyline and every in-range zone outline on 1m / 5m / 15m; the out-of-range zone draws nothing, no edge marker', async () => {
    const b = board155();
    const { container } = await mount(() => b);
    const row = b.rows[0];
    for (const tf of ['1m', '5m', '15m']) {
      const el = frameEl(container, 'OMH', tf);
      const f = row.frames.find((x: any) => x.tf === tf);
      expect(el.querySelectorAll('polyline.pc-vwap').length, tf).toBeGreaterThan(0);
      const titles = bandTitles(el);
      const inside = f.tile.bands.filter((z: any) => z.lo !== row.frames[0].tile.bands[2].lo);
      for (const z of inside) expect(titles, `${tf} ${z.label}`).toContain(z.label);
      expect(titles).not.toContain(f.tile.bands[2].label);
      expect(el.querySelector('g[data-band-kind$="-off"]')).toBeNull();
      // 🟩 CHANGED 2026-11-23 (his "subtle green glassy"): the daily zone draws as GLASS — gradient fill, no dash
      const zr = Array.from(el.querySelectorAll('g[data-band-kind^="board_"] > rect'));
      expect(zr.length, tf).toBeGreaterThan(0);
      for (const r of zr) {
        expect(r.getAttribute('fill')).toMatch(/^url\(#.+-glass-board_(demand|supply)\)$/);
        expect(r.getAttribute('stroke-dasharray')).toBeNull();
      }
    }
  });
  it('NEGATIVE: a row without `levels` → no line, no zone band, no VWAP', async () => {
    const { container } = await mount(() => board155());
    const t = tile(container, 'PLAIN');
    expect(t.querySelectorAll('svg')).toHaveLength(3);
    expect(t.querySelector('[data-testid^="ggw-levels-"]')).toBeNull();
    expect(t.querySelector('g[data-band-kind^="board_"]')).toBeNull();
    expect(t.querySelector('.pc-vwap')).toBeNull();
  });
});

describe('📐 the row\'s levels line — verbatim, once (in the ⋯ drawer when compact)', () => {
  it('ok / retry / none / pending each printed verbatim exactly once in its tile, hover = the served title', async () => {
    const { container } = await mount(() => board155());
    for (const [sym, st] of [['OMH', 'ok'], ['NVDA', 'retry'], ['XYZQ', 'none'], ['AMD', 'pending']] as const) {
      const t = tile(container, sym);
      const lines = t.querySelectorAll(`[data-testid="ggw-levels-${sym}"]`);
      expect(lines, sym).toHaveLength(1);
      expect(lines[0].textContent).toBe(LEVELS[st](sym).text);
      expect(lines[0].getAttribute('title')).toBe('served-zones-sentence');
      expect(lines[0].getAttribute('data-state')).toBe(st);
      expect(lines[0].classList.contains('ggw-line')).toBe(true);
      expect(lines[0].classList.contains('ggw-levels')).toBe(true);
      // plain tile: under the head, not in a drawer
      expect(lines[0].closest('.ggw-drawer')).toBeNull();
      expect(t.textContent!.split(LEVELS[st](sym).text)).toHaveLength(2);
    }
  });
  it('compact (org mode): the line sits INSIDE the ⋯ drawer, once per tile', async () => {
    const { container } = await mount(() => board155({ org: true }));
    const t = tile(container, 'OMH');
    expect(t.classList.contains('ggw-tile--compact')).toBe(true);
    const lines = t.querySelectorAll('[data-testid="ggw-levels-OMH"]');
    expect(lines).toHaveLength(1);
    expect(lines[0].closest('[data-testid="ggw-drawer-OMH"]')).not.toBeNull();
    expect(lines[0].textContent).toBe(LEVELS.ok('OMH').text);
  });
  it('NEGATIVE: a served block with no text, or junk → no line', async () => {
    const b = board155();
    b.rows[0].levels = { state: 'ok', text: '', title: 'x', as_of: null };
    b.rows[3].levels = 'junk';
    const { container } = await mount(() => b);
    expect(container.querySelector('[data-testid="ggw-levels-OMH"]')).toBeNull();
    expect(container.querySelector('[data-testid="ggw-levels-NVDA"]')).toBeNull();
    const p = parseGgw(b) as GgwBoard;
    expect(p.rows[3].levels).toBeNull();
    expect('levels' in p.rows[4]).toBe(false);   // never served → the key is absent (an older row stays byte-equal)
  });
});

describe('📈📐 legend swatches + titles, ℹ️ lines', () => {
  it('EMA swatches unchanged; VWAP = the chart\'s blue at VWAP_LINE_W; zones = the glass swatch in the tone colour; titles served', async () => {
    const { container } = await mount(() => board155());
    const item = (tone: string) => container.querySelector(`.ggw-legend-item[data-tone="${tone}"]`) as HTMLElement;
    const sw = (tone: string) => item(tone).querySelector('i') as HTMLElement;
    expect(sw('ema9').style.height).toBe(`${EMA_BOLD.ema9.width}px`);
    expect(sw('ema9').style.background).toBeTruthy();
    expect(sw('ema9').className).toBe('ggw-swatch');
    expect(ggwLegendSwatch('ema9').style).toEqual({ background: EMA_BOLD.ema9.color, height: EMA_BOLD.ema9.width });
    expect(item('ema9').getAttribute('title')).toBeNull();
    expect(ggwLegendSwatch('vwap').style).toEqual({ background: toneColor('vwap'), height: VWAP_LINE_W });
    expect(sw('vwap').style.height).toBe(`${VWAP_LINE_W}px`);
    expect(item('vwap').getAttribute('title')).toBe(VWAP_TEXT);
    for (const tone of ['zone_demand', 'zone_supply'] as const) {
      expect(sw(tone).className).toBe('ggw-swatch ggw-swatch--zone');
      expect(ggwLegendSwatch(tone).style).toEqual({ borderColor: toneColor(tone), background: `color-mix(in srgb, ${toneColor(tone)} 24%, transparent)` });   // 🟩 2026-11-23 glass
      expect(item(tone).getAttribute('title')).toBe(ZONES_TEXT);
    }
    expect(ggwLegendSwatch('mystery')).toEqual({ cls: 'ggw-swatch', style: undefined });
  });
  it('ℹ️ prints the served vwap_text and zones_text; NEGATIVE: none served → neither line', async () => {
    const { container, unmount } = await mount(() => board155());
    expect(container.querySelector('[data-testid="ggw-info-vwap"]')!.textContent).toBe(VWAP_TEXT);
    expect(container.querySelector('[data-testid="ggw-info-zones"]')!.textContent).toBe(ZONES_TEXT);
    unmount();
    const r = await mount(() => board155({ info: false }));
    expect(r.container.querySelector('[data-testid="ggw-info-vwap"]')).toBeNull();
    expect(r.container.querySelector('[data-testid="ggw-info-zones"]')).toBeNull();
  });
  it('parse: legend `title` kept only when served; info texts through str()', () => {
    const p = parseGgw(board155()) as GgwBoard;
    expect(p.legend[0]).toEqual({ tone: 'ema9', label: '9 EMA' });
    expect(p.legend[2]).toEqual({ tone: 'vwap', label: 'served-vwap-label', title: VWAP_TEXT });
    expect(p.info!.vwap_text).toBe(VWAP_TEXT);
    const j = board155(); j.info.vwap_text = 3; j.info.zones_text = '  ';
    const q = parseGgw(j) as GgwBoard;
    expect(q.info!.vwap_text).toBeNull();
    expect(q.info!.zones_text).toBeNull();
  });
});

// ── live: the forming candle with the seed OFF / ON (the tile) ───────────────────────────────────────────────────────

describe('📈 the tile: forming 5- / 15-min candle — main\'s while GGW_SEED_FORMING is off', () => {
  const START = Date.UTC(2026, 10, 23, 9, 0, 0) / 1000;
  const pad = (n: number) => String(n).padStart(2, '0');
  const stamp = (s: number, fm: number) => { const m = 240 + (s + 1) * fm; return `2026-11-23 ${pad(Math.floor(m / 60))}:${pad(m % 60)}`; };
  const b1 = (s: number): CmBar => ({ t: stamp(s, 1), o: 1 + s / 100, h: 1.01 + s / 100, l: 0.99 + s / 100, c: 1 + s / 100, v: 100 + s });
  const fr = (tf: string, fm: number, n: number): GgwFrame => {
    const xs = Array.from({ length: n }, (_, i) => i);
    return {
      tf, label: tf,
      tile: { symbol: 'LIVE', href: '', bars: xs.map((s) => ({ ...b1(s * fm), t: stamp(s, fm) })), bands: [], lines: [], markers: [],
        stats: [], why: '', curves: [] } as any,
      axis: { slots: 960 / fm, x: xs, shade: [], ticks: [], start_epoch: START, frame_min: fm, from_et: '04:00' },
      ema_tail: null, ema_cross: null, uptrend: null, held: null, run_bases: null, ema_blink: null,
    };
  };
  const row = (): GgwRow => ({
    symbol: 'LIVE', state: 'ok', text: null, from_session: null, as_of_et: null, stale: false, rang: [],
    frames: [fr('1m', 1, 37), fr('5m', 5, 7), fr('15m', 15, 2)],
  });
  const lb = (bucket: number, o: number, v: number): GgwLiveBar => ({ bucket, o, h: o, l: o, c: o, v, as_of: START + bucket * 60 + 9 });
  const live: GgwLiveSym = { last_epoch: START + 38 * 60, by: { '1m': [lb(37, 1.37, 5), lb(38, 1.38, 6)], '5m': [lb(7, 1.37, 11)], '15m': [lb(2, 1.37, 11)] } };
  const draw = (r: GgwRow) => render(
    <MemoryRouter><Tile row={r} phone={false} fit={false} removeLabel={null} focused={false} busy={false} live={live} /></MemoryRouter>);

  it('OFF (shipped): the 5- and 15-min frames get main\'s own live bars — the SAME array (byte-equal to ggwLiveFrame(f, own))', () => {
    const r = row();
    draw(r);
    const of = (tf: string) => liveCalls.filter((c) => c.tf === tf).map((c) => c.bars);
    expect(of('15m').length).toBeGreaterThan(0);
    for (const bars of of('15m')) expect(bars).toBe(live.by['15m']);
    for (const bars of of('5m')) expect(bars).toBe(live.by['5m']);
    for (const bars of of('1m')) expect(bars).toBe(live.by['1m']);
  });
  it('ON (mocked): the 15-min frame folds ggwSeedLive (stored 1-min bars of the bucket + the live ones past them)', () => {
    seedFlag.on = true;
    const r = row();
    draw(r);
    const want = ggwSeedLive(r.frames[2], live.by['15m'], r.frames[0], live.by['1m'])!;
    const got = liveCalls.filter((c) => c.tf === '15m').map((c) => c.bars);
    expect(got.length).toBeGreaterThan(0);
    for (const bars of got) expect(bars).toEqual(want);
    expect(want[0].v).toBeGreaterThan(live.by['15m'][0].v);
    // the 1-min frame itself is never seeded
    for (const bars of liveCalls.filter((c) => c.tf === '1m').map((c) => c.bars)) expect(bars).toBe(live.by['1m']);
  });
  it('NEGATIVE: ON but no live given → nothing folds (no forming candle)', () => {
    seedFlag.on = true;
    render(<MemoryRouter><Tile row={row()} phone={false} fit={false} removeLabel={null} focused={false} busy={false} /></MemoryRouter>);
    for (const c of liveCalls) expect(c.bars).toBeUndefined();
  });
});

// ── the 🚩 card view ─────────────────────────────────────────────────────────────────────────────────────────────────

describe('📐 card view: served ctx bands survive ggcRow under both looks; levels reach the row', () => {
  const ZONE = { kind: 'board_demand', lo: 3.95, hi: 4.0, label: 'Daily demand 3.95–4.00', gutter: 'demand', ctx: true };
  const answer = (o: { zones?: boolean; levels?: unknown } = {}) => {
    const frames = clone(RAW.rows[0].frames).map((f: any) => ({ ...f, tf: f.tf === '3m' ? '15m' : f.tf }));
    if (o.zones) for (const f of frames) f.tile.bands = [ZONE];
    return parseGgc({
      state: 'ok', symbol: 'OMH', session: '2026-11-13', is_today: true, in_window: true, as_of_et: '09:41', stale: false,
      text: null, frames, ...('levels' in o ? { levels: o.levels } : {}),
    }) as GgcPayload;
  };
  const card = (): GgTile => ({
    symbol: 'OMH', href: '', bars: [], stats: [], why: '', tf: '5m',
    lines: [{ label: 'trigger', price: 4.2, tone: 'buy' } as any], bands: [{ kind: 'gg_entry', lo: 3.9, hi: 4.0 } as any],
    markers: [], gajjala: { plan_text: 'served plan' } as any,
  } as GgTile);
  it('both looks: the served ctx band first, the card\'s own band still there', () => {
    const c = card();
    for (const look of [undefined, 'video'] as const) {
      const row = ggcRow(c, answer({ zones: true }), look);
      for (const fr of row.frames) {
        expect(fr.tile.bands[0]).toEqual(ZONE);
        expect(ggcIsCtx(fr.tile.bands[0])).toBe(true);
        if (look === undefined) expect(fr.tile.bands.slice(1)).toEqual(c.bands);
        else expect(fr.tile.bands.filter((x) => !ggcIsCtx(x))).toEqual([]);   // video strips only the CARD's band
      }
    }
  });
  it('levels reach the row (key only when served)', () => {
    const lv = { state: 'pending', text: 'served-card-zones-words', title: 't', as_of: null };
    expect(ggcRow(card(), answer({ levels: lv })).levels).toEqual(lv);
    expect(ggcRow(card(), answer({ levels: 'junk' })).levels).toBeNull();
    expect('levels' in ggcRow(card(), answer())).toBe(false);
  });
  it('NEGATIVE: a payload without ctx bands / levels → the card\'s bands reference exactly, the row byte-equal', () => {
    const c = card();
    const p = answer();
    expect('levels' in p).toBe(false);
    const row = ggcRow(c, p);
    for (const fr of row.frames) expect(fr.tile.bands).toBe(c.bands);
    expect(Object.keys(row)).toEqual(['symbol', 'state', 'text', 'from_session', 'as_of_et', 'stale', 'frames', 'rang']);
  });
  it('NEGATIVE: a non-ctx served band (or ctx: "true") is not kept — only the card\'s overlay', () => {
    const p = answer();
    for (const f of p.frames) f.tile.bands = [{ kind: 'board_demand', lo: 1, hi: 2 } as any, { ...ZONE, ctx: 'true' } as any];
    const c = card();
    for (const fr of ggcRow(c, p).frames) expect(fr.tile.bands).toBe(c.bands);
  });
});
