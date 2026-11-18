/* 🏷️ the tags row on the REAL 👀 Watch board (2026-11-18, spec wtags §3.4 / §3.5 / §3.6, §4 WP-B).
 * Ajay 2026-11-18: "Also add Short Interest tag and other tags on top of stock ticker information for me to read, like
 * here". The 2026-11-17 auto fixture (30 rows) with a served `tags` block on ONE row (OMH); fetch routed by PATHNAME.
 * The row sits ABOVE the head; ONE SI GET, ONE /growth/tags GET and ONE room POST carrying the carded names only.
 * NEGATIVES: no `tags` anywhere → ZERO room POSTs and a tag-less tile's DOM is byte-equal to today's; the 🚩 / 🧪 card
 * grid tile and GgCardView never mount the row; source + CSS guards with a PRE_FIX sheet. Display only; UNMEASURED. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
vi.mock('./GgWatchButton', () => ({ GgWatchButton: ({ symbol }: any) => <span data-testid={`ggwatch-${symbol}`} /> }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GgCardView } from './GgCardView';
import { GgCardTile } from './GgCardGrid';
import { Tile } from './GajjalaWatchTile';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { explosiveChipText } from '../lib/bounceRoom';
import { GGW_LAYOUTS, GGW_LIVE_PATH, parseGgw, parseRowTags, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';
import { GGC_PATH, GGC_STRETCH_ORDER, ggcRow, parseGgc, type GgcPayload } from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';
import type { GgCardWatch } from '../hooks/useGgCardWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const ALL: string[] = RAW.rows.map((r: any) => r.symbol);
const SI_PATH = '/short-interest/map';
const GROWTH_PATH = '/growth/tags';
const ROOM_PATH = '/supply-demand/bounce-room';
const TITLE = '🩳 served SI hover — FINRA settlement 2026-10-30.';
const blk = (sym: string, chip: string) => ({ symbol: sym, status: 'ok', chip, title: TITLE, rows: [], extreme: null });
const SI_ITEMS: Record<string, unknown> = {
  OMH: blk('OMH', '🩳 SI 359.4K sh · 19.5d · 10/30'),
  NVDA: blk('NVDA', '🩳 SI 1.1% float · 1.0d · 10/30'),
  PFAI: blk('PFAI', '🩳 SI 2.5M sh · 9.0d · 10/30'),
};
const GROWTH = { tags: { OMH: { sales: 120, eps: 80 } } };
const TAGS = {
  on_board: true,
  setups: [{ setup: 'reversal_squeeze', label: '🎾 served label', state: 'forming', state_label: 'served state words' }],
  stages: { title: '🧭 served title', sep: '→', text: '🎾 served chain',
            groups: [{ date: '2026-11-18', label: 'served today', tags: [{ setup: 'reversal_squeeze', text: '🎾 served tag' }] }] },
  float: { text: 'Float 3.2M served', shares: 3200000, src: 'served', as_of: '2026-11-17', suspect: false },
  broker_text: null, trader_text: '📌 served trader', promo_text: null,
};
const ROOM_ROW = {
  symbol: 'OMH', coverage: 'covered',
  explosive: { score: null, intact: false, room: { state: 'ROOM', room_pct: 1.1, atr_days: null, band: null }, measured: { status: 'no_signal' } },
  enterable: { kind: 'demand', verdict: 'BLOCKED', reasons: ['band'], reason_text: ['served band sentence'], reason_short: ['not at band'] },
};
const STUDY = { headline: 'served study headline', status: 'no_signal' };

function board(tagged: boolean): any {
  const b = clone(RAW);
  if (tagged) b.rows.find((r: any) => r.symbol === 'OMH').tags = clone(TAGS);
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

type Call = { url: string; method: string; body?: string };
let calls: Call[] = [];
const pathOf = (u: string) => new URL(u, 'http://x').pathname;
const symsOf = (u: string) => decodeURIComponent(new URL(u, 'http://x').searchParams.get('symbols') || '').split(',').filter(Boolean);
function routedFetch(tagged: boolean, si: Record<string, unknown> = SI_ITEMS, growth: unknown = GROWTH) {
  calls = [];
  const fn = vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ url, method, body: typeof init?.body === 'string' ? init.body : undefined });
    const ok = (j: unknown) => ({ ok: true, status: 200, json: async () => j } as unknown as Response);
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return ok({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] });
    if (method === 'POST' && pathOf(url).endsWith(ROOM_PATH)) {
      return ok({ rows: { OMH: ROOM_ROW }, pending: 0, explosive_study: STUDY, as_of: null, in_session: true, store_date: null,
                  params: {}, requested: 1, covered: 1, unavailable: 0, disclaimer: '' });
    }
    if (pathOf(url).endsWith(SI_PATH)) {
      const out: Record<string, unknown> = {};
      for (const s of symsOf(url)) if (si[s]) out[s] = si[s];
      return ok({ items: out, n: Object.keys(out).length, max_symbols: 200 });
    }
    if (pathOf(url).endsWith(GROWTH_PATH)) return ok(growth);
    if (url.includes(GGC_PATH + '/')) return ok(cardPayload('PFAI'));
    if (url.includes('?symbols=')) {
      const syms = symsOf(url);
      const b = board(tagged);
      return ok({ ...b, rows: b.rows.filter((r: any) => syms.includes(r.symbol)) });
    }
    return ok(board(tagged));
  });
  vi.stubGlobal('fetch', fn);
}
const siGets = () => calls.filter((c) => c.method === 'GET' && pathOf(c.url).endsWith(SI_PATH));
const growthGets = () => calls.filter((c) => c.method === 'GET' && pathOf(c.url).endsWith(GROWTH_PATH));
const roomPosts = () => calls.filter((c) => pathOf(c.url).endsWith(ROOM_PATH));

async function mountBoard(tagged: boolean, si: Record<string, unknown> = SI_ITEMS, growth: unknown = GROWTH) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  routedFetch(tagged, si, growth);
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const tile = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;

describe('🏷️ the tags row on the 👀 Watch board', { timeout: 30000 }, () => {
  beforeEach(() => {
    vi.useFakeTimers();
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => {
    cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks();
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
    document.body.style.overflow = '';
  });

  it('the row is the FIRST child of the OMH tile, before .ggw-tile-head; the card tags print from the served block', async () => {
    const c = await mountBoard(true);
    const t = tile(c, 'OMH');
    const row = t.firstElementChild as HTMLElement;
    expect(row.getAttribute('data-testid')).toBe('ggw-tags-OMH');
    expect(row.className).toBe('ggw-tags');
    expect(row.nextElementSibling!.className).toBe('ggw-tile-head');
    expect(within(row).getByTestId('si-chip').textContent).toBe((SI_ITEMS.OMH as any).chip);
    expect(row.querySelector('.cm-badge-growth')).not.toBeNull();
    expect(within(row).getByTestId('ggw-trader-OMH').textContent).toBe(TAGS.trader_text);
    expect(within(row).getByTestId('ggw-float-OMH').textContent).toBe(TAGS.float.text);
    expect(within(row).getByTestId('gg-stages-OMH').getAttribute('aria-label')).toBe(TAGS.stages.text);
    expect(row.querySelector('.cm-badge-explosive')!.textContent).toBe(explosiveChipText(ROOM_ROW.explosive as any, STUDY as any)!.text);
    expect(row.querySelector('.cm-badge-enterable-blocked')!.textContent).toBe('⛔ not at band');
    /* an off-board name with an SI read: the 🩳 chip only — no card tags */
    const nv = tile(c, 'NVDA').firstElementChild as HTMLElement;
    expect(nv.getAttribute('data-testid')).toBe('ggw-tags-NVDA');
    expect(Array.from(nv.children).map((e) => e.getAttribute('data-testid'))).toEqual(['si-chip']);
    /* a name with nothing to print keeps today's first child */
    expect(tile(c, 'AAPL').firstElementChild!.className).toBe('ggw-tile-head');
  });

  it('the ⤢ view of OMH shows the row too (first child of the stretch tile)', async () => {
    const c = await mountBoard(true);
    fireEvent.click(within(tile(c, 'OMH')).getByTestId('ggw-stretch-btn-OMH'));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const st = screen.getByTestId('ggw-stretch-tile-OMH');
    expect(st.firstElementChild!.getAttribute('data-testid')).toBe('ggw-tags-OMH');
    expect(st.firstElementChild!.nextElementSibling!.className).toBe('ggw-tile-head');
    expect(within(st.firstElementChild as HTMLElement).getByTestId('gg-stages-OMH')).not.toBeNull();
  });

  it('ONE SI GET (every row), ONE /growth/tags GET, ONE room POST whose symbols == the carded names only', async () => {
    await mountBoard(true);
    expect(siGets()).toHaveLength(1);
    expect(new Set(symsOf(siGets()[0].url))).toEqual(new Set(ALL));
    expect(growthGets()).toHaveLength(1);
    expect(roomPosts()).toHaveLength(1);
    expect(roomPosts()[0].method).toBe('POST');
    expect(JSON.parse(roomPosts()[0].body!).symbols).toEqual(['OMH']);
    /* the pending poll does not add a second room POST, SI GET or growth GET */
    await act(async () => { await vi.advanceTimersByTimeAsync(RAW.pending_poll_sec * 1000 + 100); });
    expect(roomPosts()).toHaveLength(1);
    expect(siGets()).toHaveLength(1);
    expect(growthGets()).toHaveLength(1);
  });

  it('NEGATIVE: no `tags` on any row → ZERO room POSTs; empty SI / growth → no .ggw-tags, every tile starts with its head', async () => {
    const c = await mountBoard(false, {}, { tags: {} });
    await act(async () => { await vi.advanceTimersByTimeAsync(61_000); });
    expect(roomPosts()).toHaveLength(0);
    expect(c.querySelectorAll('.ggw-tile')).toHaveLength(ALL.length);
    expect(c.querySelector('.ggw-tags')).toBeNull();
    for (const s of ALL) expect(tile(c, s).firstElementChild!.className, s).toBe('ggw-tile-head');
  });

  it('NEGATIVE: a tag-less Tile with `tags` is byte-equal to the pre-change Tile (no `tags`) — every 11-15 row', async () => {
    vi.useRealTimers();
    routedFetch(false, {}, { tags: {} });
    const rows = (parseGgw(clone(watchFixture)) as GgwBoard).rows;
    const props = { phone: false, fit: false, removeLabel: 'Remove', focused: false, busy: false, siNote: true };
    const a = render(<MemoryRouter>{rows.map((r) => <Tile key={r.symbol} row={r} {...props} tags={{ room: null, study: null }} />)}</MemoryRouter>);
    const b = render(<MemoryRouter>{rows.map((r) => <Tile key={r.symbol} row={r} {...props} />)}</MemoryRouter>);
    await waitFor(() => { expect(siGets().length).toBeGreaterThan(0); expect(growthGets().length).toBeGreaterThan(0); });
    await new Promise((r) => setTimeout(r, 30));
    for (const r of rows) {
      const ta = a.container.querySelector(`[data-testid="ggw-tile-${r.symbol}"]`)!;
      const tb = b.container.querySelector(`[data-testid="ggw-tile-${r.symbol}"]`)!;
      expect(ta.outerHTML, r.symbol).toBe(tb.outerHTML);
    }
    expect(a.container.querySelector('.ggw-tags')).toBeNull();
  });
});

/* ── the 🚩 / 🧪 card grid tile and GgCardView never pass `tags` ── */
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
function frame(sym: string, tf: string) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf; f.label = tf; f.tile.symbol = sym; f.as_of_et = '10:30'; f.stale = false; f.empty_text = null;
  return f;
}
function cardPayload(sym: string) {
  return { state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
           text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)) };
}
const card = (sym: string): GgTile =>
  ({ symbol: sym, name: null, href: `/sepa/${sym}?tab=supply&tf=5m_today`, bars: [], lines: [], bands: [], markers: [],
     stats: [], why: '', tf: '5m', gajjala: { plan_text: 'served plan' } } as unknown as GgTile);
function cwOf(): GgCardWatch {
  const rowOf = (cd: GgTile): GgwRow => ({
    ...ggcRow(cd, parseGgc(cardPayload(cd.symbol)) as GgcPayload, undefined, { plan: false }),
    tags: parseRowTags(clone(TAGS)),
  });
  return {
    on: true, allowed: true, toggle: () => {}, active: true, phone: false, layout: 2, setLayout: vi.fn(),
    page: 0, pages: 1, paged: false, goPage: vi.fn(), pick: null, usePick: false, togglePick: vi.fn(),
    shown: () => true, rowOf, liveOf: () => undefined, grid: GGW_LAYOUTS[2], fit: false, rowH: null,
    boardRef: { current: null }, headRef: { current: null }, gridRef: { current: null },
  } as unknown as GgCardWatch;
}

describe('🏷️ NEGATIVE: the card grid tile and GgCardView never mount the row', () => {
  beforeEach(() => { _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache(); });
  afterEach(() => {
    cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.style.overflow = '';
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
  });

  it('GgCardTile — even with a served on-board `tags` block on its row and an SI read → no ggw-tags-*', async () => {
    routedFetch(false);
    const cw = cwOf();
    expect(cw.rowOf(card('PFAI')).tags?.on_board).toBe(true);           // the negative is not vacuous
    const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GgCardTile card={card('PFAI')} cw={cw} onStretch={() => {}} /></MemoryRouter>);
    await new Promise((res) => setTimeout(res, 150));
    expect(r.container.querySelector('[data-testid^="ggw-tags-"]')).toBeNull();
    expect(r.container.querySelector('.ggw-tags')).toBeNull();
    expect(r.container.querySelector('.ggw-tile')!.firstElementChild!.className).toBe('ggw-tile-head');
    expect(roomPosts()).toHaveLength(0);
  });

  it('GgCardView with an SI read → no ggw-tags-*', async () => {
    routedFetch(false);
    render(<MemoryRouter><GgCardView card={card('PFAI')} at="PFAI" variant="gajjala" boardSeq={1} onClose={() => {}} onStep={null} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('ggw-stretch-tile-PFAI').querySelector('svg')).not.toBeNull());
    await new Promise((res) => setTimeout(res, 150));
    expect(document.querySelector('[data-testid^="ggw-tags-"]')).toBeNull();
    expect(screen.getByTestId('ggw-stretch-tile-PFAI').firstElementChild!.className).toBe('ggw-tile-head');
    expect(roomPosts()).toHaveLength(0);
  });
});

/* ── source + CSS guards (jsdom has no layout) ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
function fitRule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const blocks = src.match(/@media \(min-width: 641px\) \{(?:[^{}]*\{[^}]*\})*\s*\}/g) || [];
  for (const b of blocks) {
    const m = b.match(new RegExp(`\\n\\s*${esc}\\s*\\{([^}]*)\\}`));
    if (m) return m[1];
  }
  return null;
}
const PRE_FIX = `.ggw-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
.ggw-tile { padding: 9px; }
.ggw-chip { white-space: nowrap; }
.ggw-tags { display: flex; }
.ggw-dark { --surface: #000; }`;
const rowWraps = (s: string) => { const d = rule(s, '.ggw-tags'); return !!d && /flex-wrap:\s*wrap/.test(d) && /min-width:\s*0/.test(d); };
const badgeWraps = (s: string) => {
  const d = rule(s, '.ggw-tags .cm-badge, .ggw-tags .gg-stage, .ggw-tags .gg-stages');
  return !!d && /white-space:\s*normal/.test(d) && /min-width:\s*0/.test(d);
};
const fitOneLine = (s: string) => { const d = fitRule(s, '.ggw-grid--fit .ggw-tags'); return !!d && /flex-wrap:\s*nowrap/.test(d) && /flex:\s*none/.test(d); };
const fitEllipsis = (s: string) => {
  const d = fitRule(s, '.ggw-grid--fit .ggw-tags > *, .ggw-grid--fit .ggw-tags .gg-stages > *');
  return !!d && /white-space:\s*nowrap/.test(d) && /text-overflow:\s*ellipsis/.test(d) && /min-width:\s*0/.test(d);
};
const stretchWraps = (s: string) => {
  const d = fitRule(s, '.ggw-grid--stretch.ggw-grid--fit .ggw-tags, .ggw-grid--stretch.ggw-grid--fit .ggw-tags .gg-stages');
  const e = fitRule(s, '.ggw-grid--stretch.ggw-grid--fit .ggw-tags > *, .ggw-grid--stretch.ggw-grid--fit .ggw-tags .gg-stages > *');
  return !!d && /flex-wrap:\s*wrap/.test(d) && !!e && /white-space:\s*normal/.test(e);
};

describe('🏷️ source guards', () => {
  it('the tile mounts <GgwTagsRow once, before the head; still no house chip; the grid / card view pass no tags', async () => {
    const tileSrc = await readSource('src/components/GajjalaWatchTile.tsx');
    expect(tileSrc.match(/<GgwTagsRow\b/g)).toHaveLength(1);
    expect(tileSrc.indexOf('<GgwTagsRow')).toBeLessThan(tileSrc.indexOf('className="ggw-tile-head"'));
    expect(tileSrc).not.toMatch(/<(GrowthChip|ExplosiveChip|ShortInterestChip)\b/);
    expect(tileSrc).toMatch(/\{siNote \? <GgSiExtremeNote symbol=\{row\.symbol\} testid=\{`ggw-si-extreme-\$\{row\.symbol\}`\} \/> : null\}/);
    for (const f of ['src/components/GgCardGrid.tsx', 'src/components/GgCardView.tsx']) {
      expect(await readSource(f), f).not.toContain('tags=');
    }
  });
  it('the board: siNote ×2, tags= ×2, ONE useGgwTags( read — NEGATIVE: no b-word (the room hook lives in GajjalaWatchTags)', async () => {
    const boardSrc = await readSource('src/components/GajjalaWatchBoard.tsx');
    expect(boardSrc.match(/\bsiNote\b/g)).toHaveLength(2);
    expect(noComments(boardSrc).match(/\btags=\{tagsOf\(/g)).toHaveLength(2);
    expect(noComments(boardSrc).match(/useGgwTags\(/g)).toHaveLength(1);
    expect(boardSrc).not.toMatch(new RegExp('b' + 'ounce', 'i'));
    const tagsSrc = noComments(await readSource('src/components/GajjalaWatchTags.tsx'));
    expect(tagsSrc.match(/useRoomRead\(/g)).toHaveLength(1);
    expect(tagsSrc).toMatch(/import \{ useBounceRoom as useRoomRead \} from '\.\.\/hooks\/useBounceRoom';/);
  });
  it('CSS: .ggw-tags wraps (min-width 0), badges wrap, fitted = one line + ellipsis, stretch wraps — NEGATIVE: PRE_FIX fails each', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    for (const [name, fn] of [['rowWraps', rowWraps], ['badgeWraps', badgeWraps], ['fitOneLine', fitOneLine],
                              ['fitEllipsis', fitEllipsis], ['stretchWraps', stretchWraps]] as const) {
      expect(fn(css), name).toBe(true);
      expect(fn(PRE_FIX), `${name} PRE_FIX`).toBe(false);
    }
    /* the scoped stages copies are here (the Watch chunk does not load gajjala.css) — and the Watch never imports it */
    expect(rule(css, '.ggw-tags .gg-stages')).toMatch(/flex-wrap:\s*wrap/);
    for (const f of ['src/components/GajjalaWatchTags.tsx', 'src/components/GajjalaWatchTile.tsx', 'src/components/GajjalaWatchBoard.tsx']) {
      expect(await readSource(f), f).not.toMatch(/styles\/gajjala\.css/);
    }
    expect(css).not.toMatch(/\.ggw-tags[^{]*\.ggw-chip/);
  });
});
