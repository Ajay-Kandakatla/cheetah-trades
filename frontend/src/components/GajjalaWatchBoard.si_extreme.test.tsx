/* 🩳 EXTREME short-interest note on the 👀 Watch tiles (2026-11-18, spec sinote §3.5 / §3.6, WP fe-watch).
 * Ajay 2026-11-18: "When there are extreme cases of short interest make a not for them on reversal squeeze like
 * percentage of short interest on the tickers card and also on watch list".
 *
 * The REAL board over the 2026-11-17 auto fixture (12 of his names + 18 🤖 rows) with fetch routed by PATHNAME:
 * `/short-interest/map` answers the served SI blocks (the real useShortInterest hook + the real lib + the real
 * GgSiExtremeNote run); every other `?symbols=` keeps the Watch rows branch. Every word is a stand-in for a served one.
 * The tile prints the served `short` verbatim; the hover is the served `title`. NEGATIVES: extreme null / absent name /
 * stale / no_record / an older API without the key → nothing; never a 0%; the head's existing chips unchanged; ONE map
 * GET for the whole board; the 🚩 card view (GgCardView) never mounts the note; source guards with the PRE_FIX sheet.
 * Display only; UNMEASURED (eod-audits/research/2026-11-17_si_cradle_squeeze/report.md). */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
/* the house bus is not under test here — a no-op subscription */
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GgCardView } from './GgCardView';
import { GgwStretch } from './GajjalaWatchTile';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { GGW_LIVE_PATH, GGW_PATH, parseGgw, type GgwBoard } from '../lib/gajjalaWatch';
import { GGC_PATH, GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const ALL: string[] = RAW.rows.map((r: any) => r.symbol);
const SI_PATH = '/short-interest/map';

/* the served `extreme` object — stand-ins for read.extreme_block's words */
const xOf = (sym: string, pct: string) => ({
  text: `🩳 EXTREME SI ${pct}% float · 1.0d · 10/30`,
  short: `🩳 EXTREME SI ${pct}% float`,
  title: `🩳 EXTREME short interest — ${sym} served hover sentence (SI_HIGH_PCT heuristic). Not advice.`,
  basis: 'si_doc_float',
});
const TITLE = '🩳 Short interest — FINRA settlement 2026-10-30 (published ~2026-11-10). A count of open short positions — not a forecast.';
const blk = (sym: string, status: string, chip: string | null, extra: Record<string, unknown> = {}) =>
  ({ symbol: sym, status, chip, title: TITLE, rows: [], ...extra });
const ITEMS: Record<string, unknown> = {
  OMH: blk('OMH', 'ok', '🩳 SI 36.4% float · 1.0d · 10/30', { extreme: xOf('OMH', '36.4') }),
  XXII: blk('XXII', 'ok', '🩳 SI 41.2% float · 2.0d · 10/30', { extreme: xOf('XXII', '41.2') }),   // 🤖 auto row, ok
  VTSI: blk('VTSI', 'ok', '🩳 SI 25.0% float · 1.0d · 10/30', { extreme: xOf('VTSI', '25.0') }),   // 🤖 auto row, no_prints
  NVDA: blk('NVDA', 'ok', '🩳 SI 1.1% float · 1.0d · 10/30', { extreme: null }),
  TSLA: blk('TSLA', 'stale', '🩳 SI 30.6% float · 5.0d · 8/31 · stale', { extreme: xOf('TSLA', '30.6') }),
  META: blk('META', 'no_record', null, { extreme: xOf('META', '50.0') }),
  GOOG: blk('GOOG', 'ok', '🩳 SI 33.0% float · 1.0d · 10/30'),                                  // an older API: no key
  // AAPL: absent from the map
};
const NOTED = ['OMH', 'XXII', 'VTSI'];
/** a printed zero percent ("0%", "0.0%") — never "25.0%" */
const ZERO_PCT = /(^|[^\d.])0(\.0+)?%/;

/* OMH + NVDA carry every head chip so the order / text check sees all of them */
function board(): any {
  const b = clone(RAW);
  for (const sym of ['OMH', 'NVDA']) {
    const r = b.rows.find((x: any) => x.symbol === sym);
    r.aplus = { tag: '🎯', text: `🎯 A+ ${sym}`, title: `SERVED-TITLE ${sym}`, items: [] };
    r.text = `served line ${sym}`;
    r.from_session = `served from ${sym}`;
    r.as_of_et = '10:30';
  }
  return b;
}

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

type Call = { url: string; method: string };
let calls: Call[] = [];
const pathOf = (u: string) => new URL(u, 'http://x').pathname;
const symsOf = (u: string) => decodeURIComponent(new URL(u, 'http://x').searchParams.get('symbols') || '').split(',').filter(Boolean);
function routedFetch(items: Record<string, unknown> = ITEMS) {
  calls = [];
  const fn = vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ url, method });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) {
      return { ok: true, json: async () => ({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] }) } as unknown as Response;
    }
    if (pathOf(url).endsWith(SI_PATH)) {
      const out: Record<string, unknown> = {};
      for (const s of symsOf(url)) if (items[s]) out[s] = items[s];
      return { ok: true, json: async () => ({ items: out, n: Object.keys(out).length, max_symbols: 200 }) } as unknown as Response;
    }
    if (url.includes('?symbols=')) {
      const syms = symsOf(url);
      const b = board();
      return { ok: true, json: async () => ({ ...b, rows: b.rows.filter((r: any) => syms.includes(r.symbol)) }) } as unknown as Response;
    }
    return { ok: true, json: async () => board() } as unknown as Response;
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}
const gets = () => calls.filter((c) => c.method === 'GET');
const siGets = () => gets().filter((c) => pathOf(c.url).endsWith(SI_PATH));
const full = () => gets().filter((c) => c.url.endsWith(GGW_PATH));
const rows = () => gets().filter((c) => c.url.includes(GGW_PATH + '?symbols='));

async function mountBoard(items: Record<string, unknown> = ITEMS) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q,
    addEventListener: () => {}, removeEventListener: () => {} }));
  routedFetch(items);
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  /* past SI_FLUSH_MS so the ONE batched map GET is sent and lands */
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const tile = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;
const note = (root: ParentNode, s: string) => root.querySelector(`[data-testid="ggw-si-extreme-${s}"]`) as HTMLElement | null;
/** the head's children by their own class (ggw-chip / ggw-line are the shared look, not the identity) */
const headKinds = (t: HTMLElement) => Array.from(t.querySelector('.ggw-tile-head')!.children)
  .map((el) => el.className.split(/\s+/).filter((k) => k !== 'ggw-chip' && k !== 'ggw-line' && k !== 'ggw-warn').join(' '));

describe('🩳 EXTREME note on the 👀 Watch board', { timeout: 20000 }, () => {
  beforeEach(() => {
    vi.useFakeTimers();
    _resetShortInterestCache();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); _resetShortInterestCache(); });

  it('his name OMH extreme → the served short form in the tile head, served title, class, basis', async () => {
    const c = await mountBoard();
    const n = note(tile(c, 'OMH'), 'OMH')!;
    expect(n).not.toBeNull();
    expect(n.closest('.ggw-tile-head')).toBe(tile(c, 'OMH').querySelector('.ggw-tile-head'));
    expect(n.textContent).toBe((ITEMS.OMH as any).extreme.short);
    expect(n.getAttribute('title')).toBe((ITEMS.OMH as any).extreme.title);
    expect(n.className).toBe('ggw-chip ggw-si-extreme');
    expect(n.tagName).toBe('SPAN');
    expect(n.getAttribute('data-si-basis')).toBe('si_doc_float');
    /* NEGATIVE: the short form, never the longer card sentence */
    expect(n.textContent).not.toBe((ITEMS.OMH as any).extreme.text);
  });

  it('🤖 auto rows in any state (ok and no_prints) print it too', async () => {
    const c = await mountBoard();
    const parsed = parseGgw(board()) as GgwBoard;
    for (const sym of ['XXII', 'VTSI']) {
      const r = parsed.rows.find((x) => x.symbol === sym)!;
      expect(r.auto, sym).not.toBeNull();
      const n = note(tile(c, sym), sym)!;
      expect(n, sym).not.toBeNull();
      expect(n.textContent).toBe((ITEMS[sym] as any).extreme.short);
      expect(n.getAttribute('title')).toBe((ITEMS[sym] as any).extreme.title);
    }
    expect(tile(c, 'XXII').getAttribute('data-state')).toBe('ok');
    expect(tile(c, 'VTSI').getAttribute('data-state')).toBe('no_prints');
    /* the 🤖 chip comes first, then the note */
    expect(headKinds(tile(c, 'XXII')).slice(0, 3)).toEqual(['ggw-sym', 'ggw-auto', 'ggw-si-extreme']);
  });

  it('the ⤢ full-screen view of OMH shows the note too', async () => {
    const c = await mountBoard();
    fireEvent.click(within(tile(c, 'OMH')).getByTestId('ggw-stretch-btn-OMH'));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const st = screen.getByTestId('ggw-stretch-tile-OMH');
    const n = note(st, 'OMH')!;
    expect(n).not.toBeNull();
    expect(n.textContent).toBe((ITEMS.OMH as any).extreme.short);
    expect(n.closest('.ggw-tile-head')).not.toBeNull();
  });

  it('NEGATIVE: extreme null / absent name / stale / no_record / older API → nothing; only the extreme names carry it', async () => {
    const c = await mountBoard();
    for (const sym of ['NVDA', 'AAPL', 'TSLA', 'META', 'GOOG']) {
      expect(tile(c, sym), sym).not.toBeNull();
      expect(note(c, sym), sym).toBeNull();
    }
    const all = Array.from(c.querySelectorAll('[data-testid^="ggw-si-extreme-"]')).map((e) => e.getAttribute('data-testid'));
    expect(all).toEqual(NOTED.map((s) => `ggw-si-extreme-${s}`));
    expect(c.querySelectorAll('.ggw-si-extreme')).toHaveLength(NOTED.length);
  });

  it('NEGATIVE: never a 0% — no note text, and an empty map draws no note anywhere', async () => {
    expect(ZERO_PCT.test('🩳 EXTREME SI 0.0% float')).toBe(true);
    expect(ZERO_PCT.test('🩳 EXTREME SI 25.0% float')).toBe(false);
    const c = await mountBoard();
    for (const e of Array.from(c.querySelectorAll('.ggw-si-extreme'))) expect(e.textContent).not.toMatch(ZERO_PCT);
    cleanup();
    _resetShortInterestCache();
    const c2 = await mountBoard({});
    expect(c2.querySelectorAll('.ggw-tile').length).toBe(ALL.length);
    expect(c2.querySelector('.ggw-si-extreme')).toBeNull();
    expect(c2.textContent).not.toMatch(ZERO_PCT);
  });

  it('NEGATIVE: the head\'s existing chips keep their order and text; the note sits after 🤖 and before the line', async () => {
    const c = await mountBoard();
    /* NVDA (extreme null) = today's head exactly: its served 🔔 rang chip(s) included */
    const rang = (n: number) => Array.from({ length: n }, () => 'ggw-rang');
    const nRang = RAW.rows.find((r: any) => r.symbol === 'NVDA').rang.length;
    expect(nRang).toBeGreaterThan(0);
    expect(headKinds(tile(c, 'NVDA'))).toEqual(['ggw-sym', 'ggw-aplus', 'ggw-row-text', 'ggw-from', 'ggw-asof', ...rang(nRang), 'ggw-actions']);
    expect(Array.from(tile(c, 'NVDA').querySelectorAll('[data-testid="ggw-rang"]')).map((e) => e.textContent))
      .toEqual(RAW.rows.find((r: any) => r.symbol === 'NVDA').rang.map((r: any) => r.text));
    expect(headKinds(tile(c, 'OMH'))).toEqual(['ggw-sym', 'ggw-aplus', 'ggw-si-extreme', 'ggw-row-text', 'ggw-from', 'ggw-asof', 'ggw-actions']);
    const omh = tile(c, 'OMH');
    expect(within(omh).getByTestId('ggw-aplus').textContent).toBe('🎯 A+ OMH');
    expect(within(omh).getByTestId('ggw-row-text').textContent).toBe('served line OMH');
    expect(within(omh).getByTestId('ggw-from').textContent).toBe('served from OMH');
    expect(within(omh).getByTestId('ggw-asof').textContent).toBe('10:30');
    expect(omh.querySelector('.ggw-sym')!.textContent).toBe('OMH');
  });

  it('ONE /short-interest/map GET for the whole board (every row in it); the Watch\'s own GETs keep their counts', async () => {
    await mountBoard();
    expect(siGets()).toHaveLength(1);
    expect(new Set(symsOf(siGets()[0].url))).toEqual(new Set(ALL));
    expect(full()).toHaveLength(1);
    expect(rows()).toHaveLength(0);
    /* the pending poll (AMD) still asks ?symbols=AMD only, and no second map GET follows it */
    await act(async () => { await vi.advanceTimersByTimeAsync(RAW.pending_poll_sec * 1000 + 100); });
    expect(rows()).toHaveLength(1);
    expect(symsOf(rows()[0].url)).toEqual(['AMD']);
    expect(full()).toHaveLength(1);
    expect(siGets()).toHaveLength(1);
    /* NEGATIVE: the map GET is never mistaken for a Watch row poll, and the row poll never hits the SI route */
    for (const r of rows()) expect(pathOf(r.url).endsWith(SI_PATH)).toBe(false);
    for (const s of siGets()) expect(s.url).not.toContain(GGW_PATH);
  });
});

/* ── the 🚩 card view: GgCardView passes no siNote → the note never mounts there ── */
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
function frame(sym: string, tf: string) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf; f.label = tf; f.tile.symbol = sym; f.as_of_et = '10:30'; f.stale = false; f.empty_text = null;
  return f;
}
const cardPayload = (sym: string) => ({
  state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
  text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)),
});
const card = (sym: string): GgTile =>
  ({ symbol: sym, name: null, href: `/sepa/${sym}?tab=supply&tf=5m_today`, bars: [], lines: [], bands: [], markers: [],
     stats: [], why: '', tf: '5m', gajjala: { plan_text: 'served plan' } } as unknown as GgTile);

describe('🩳 NEGATIVE: the 🚩 card view never mounts the note', () => {
  beforeEach(() => { _resetShortInterestCache(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.body.style.overflow = ''; _resetShortInterestCache(); });
  const extremeMap = { PFAI: blk('PFAI', 'ok', '🩳 SI 36.4% float · 1.0d · 10/30', { extreme: xOf('PFAI', '36.4') }) };
  function cardFetch() {
    calls = [];
    const fn = vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
      const url = String(u);
      calls.push({ url, method: (init?.method ?? 'GET').toUpperCase() });
      if (pathOf(url).endsWith(SI_PATH)) return { ok: true, json: async () => ({ items: extremeMap, n: 1, max_symbols: 200 }) } as unknown as Response;
      if (url.includes(GGC_PATH + '/')) return { ok: true, status: 200, json: async () => cardPayload('PFAI') } as unknown as Response;
      return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
    });
    vi.stubGlobal('fetch', fn);
  }

  it('GgCardView with an extreme map → no ggw-si-extreme-* and no map GET', async () => {
    cardFetch();
    render(<MemoryRouter><GgCardView card={card('PFAI')} at="PFAI" variant="gajjala" boardSeq={1} onClose={() => {}} onStep={null} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('ggw-stretch-tile-PFAI').querySelector('svg')).not.toBeNull());
    await new Promise((r) => setTimeout(r, 120));
    expect(document.querySelector('[data-testid^="ggw-si-extreme-"]')).toBeNull();
    expect(document.querySelector('.ggw-si-extreme')).toBeNull();
    expect(siGets()).toHaveLength(0);
  });

  it('control: the same row through GgwStretch WITH siNote prints it (the negative above is not vacuous)', async () => {
    cardFetch();
    const row = (parseGgw(board()) as GgwBoard).rows[0];
    row.symbol = 'PFAI';
    render(<MemoryRouter><GgwStretch row={row} phone={false} removeLabel={null} onClose={() => {}} onStep={null} siNote /></MemoryRouter>);
    const n = await screen.findByTestId('ggw-si-extreme-PFAI');
    expect(n.textContent).toBe(xOf('PFAI', '36.4').short);
    expect(siGets()).toHaveLength(1);
  });
});

/* ── source guards (jsdom has no layout) ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
/** The declarations of the FIRST top-level rule whose selector list is exactly `sel` (outside any @media). */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
/** The declarations of `sel` inside any `@media (min-width: 641px)` block. */
function fitRule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const blocks = src.match(/@media \(min-width: 641px\) \{(?:[^{}]*\{[^}]*\})*\s*\}/g) || [];
  for (const b of blocks) {
    const m = b.match(new RegExp(`\\n\\s*${esc}\\s*\\{([^}]*)\\}`));
    if (m) return m[1];
  }
  return null;
}
/* the phone test's pre-fix sheet (GajjalaWatchBoard.phone.test.tsx) */
const PRE_FIX = `.ggw-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
.ggw-tile { padding: 9px; }
.ggw-chip { white-space: nowrap; }
.ggw-dark { --surface: #000; }`;
const colourRule = (src: string) => { const d = rule(src, '.ggw-si-extreme'); return !!d && /font-weight:\s*700/.test(d); };
const chipWraps = (src: string) => {
  const d = rule(src, '.ggw-chip');
  return !!d && /white-space:\s*normal/.test(d) && /overflow-wrap:\s*anywhere/.test(d) && /min-width:\s*0/.test(d);
};
const FIT_DECLS = [/white-space:\s*nowrap/, /overflow:\s*hidden/, /text-overflow:\s*ellipsis/, /min-width:\s*0/, /flex:\s*0 1 auto/];

describe('🩳 source guards', () => {
  it('NEGATIVE: the tile file renders no house chip and no 📡; GgCardView passes no siNote', async () => {
    const tileSrc = await readSource('src/components/GajjalaWatchTile.tsx');
    expect(tileSrc).not.toMatch(/<(GrowthChip|ExplosiveChip|ShortInterestChip)\b/);
    expect(tileSrc).not.toContain('📡');
    expect(tileSrc).toMatch(/\{siNote \? <GgSiExtremeNote symbol=\{row\.symbol\} testid=\{`ggw-si-extreme-\$\{row\.symbol\}`\} \/> : null\}/);
    expect(await readSource('src/components/GgCardView.tsx')).not.toContain('siNote');
    const boardSrc = await readSource('src/components/GajjalaWatchBoard.tsx');
    expect(boardSrc.match(/\bsiNote\b/g)).toHaveLength(2);
  });
  it('.ggw-si-extreme top-level rule is bold; .ggw-chip still wraps — NEGATIVE: the PRE_FIX sheet fails both', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    expect(colourRule(css)).toBe(true);
    expect(chipWraps(css)).toBe(true);
    expect(colourRule(PRE_FIX)).toBe(false);
    expect(chipWraps(PRE_FIX)).toBe(false);
  });
  it('fit mode: inside @media (min-width: 641px) the EXTREME chip is one shrinkable line — NEGATIVE: the PRE_FIX sheet fails each', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    const d = fitRule(css, '.ggw-grid--fit .ggw-si-extreme');
    expect(d).not.toBeNull();
    for (const re of FIT_DECLS) expect(d!, String(re)).toMatch(re);
    /* NEGATIVE: the rule is not a top-level one (it would also bite the phone) */
    expect(rule(css, '.ggw-grid--fit .ggw-si-extreme')).toBeNull();
    const pre = fitRule(PRE_FIX, '.ggw-grid--fit .ggw-si-extreme');
    expect(pre).toBeNull();
    for (const re of FIT_DECLS) expect(re.test(pre ?? '')).toBe(false);
    /* the 11-16 GP caption rule beside it is untouched */
    expect(css).toMatch(/\.ggw-grid--fit \.ggw-cap \{ flex-wrap: nowrap; overflow: hidden; \}/);
  });
});
