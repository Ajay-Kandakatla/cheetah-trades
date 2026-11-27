vi.mock('../lib/ggwFrames', async (orig) => (await import('../test/ggwFramesLegacy')).ggwFramesLegacy(orig));
/* 🤖 Gajjala's Watch — the auto section on the board (2026-11-17, watch-auto spec §3.6 / §4 WP-C).
 * Ajay: "Can you add more stocks in to watch list basically I need portentials from Gajjals's 1 min and regular and also
 * Audited potentials with good volume to Watchlist on an interval.. Remove as they are not progressing".
 *
 * The REAL board over the 2026-11-17 fixture (the 11-15 fixture + 8 more of his names = 12, then the served `auto`
 * block and [C9] 18 auto rows = cap; 18 removals of removed_total 25). fetch is a routed stub. Every word is a stand-in
 * for a served one. NEGATIVES: junk auto blocks → null; an older payload → no 🤖 anywhere; no chip title when every
 * hover word is null; × on an auto name never toggles and never DELETEs another name; the live POST is never his
 * `symbols` alone; a second GET with the same rows never re-keys a tile. 2026-11-25 (ggwcols): no pages on the board —
 * every row shown in the pick's columns, every chip lit. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import oldFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
/* the house bus is not under test here (the live test drives it) — a no-op subscription */
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import {
  GGW_LIVE_PATH, GGW_PHONE_MQ, ggwLiveSymbols, ggwPageCount, parseGgw, type GgwBoard,
} from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const MANUAL: string[] = RAW.symbols;
const AUTO: string[] = RAW.auto.symbols;
const ALL: string[] = RAW.rows.map((r: any) => r.symbol);
const autoRow = (sym: string) => RAW.rows.find((r: any) => r.symbol === sym);

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

describe('🤖 the fixture itself', () => {
  it('[C9] 12 of his names, then 18 auto rows (= cap); 18 removals of 25', () => {
    expect(MANUAL).toHaveLength(12);
    expect(AUTO).toHaveLength(18);
    expect(RAW.auto.cap).toBe(18);
    expect(RAW.auto.n).toBe(18);
    expect(ALL).toEqual([...MANUAL, ...AUTO]);
    expect(RAW.auto.removed).toHaveLength(18);
    expect(RAW.auto.removed_total).toBe(25);
    /* NEGATIVE: the stored auto order is neither alphabetical nor by volume (the server never re-sorts) */
    expect(AUTO).not.toEqual([...AUTO].sort());
  });
});

describe('🤖 parseGgw — auto', () => {
  const ok = (mut: (b: any) => void = () => {}) => { const b = clone(RAW); mut(b); return parseGgw(b) as GgwBoard; };
  it('keeps the auto block, the row blocks and info.auto_text', () => {
    const b = ok();
    expect(b.auto?.state).toBe('ok');
    expect(b.auto?.n).toBe(18);
    expect(b.auto?.cap).toBe(18);
    expect(b.auto?.symbols).toEqual(AUTO);
    expect(b.auto?.removed).toHaveLength(18);
    expect(b.auto?.removed[0].text_full).toBe(RAW.auto.removed[0].text_full);
    expect(b.auto?.removed_total).toBe(25);
    expect(b.auto?.push_mode).toBe('off');
    expect(b.info?.auto_text).toBe(RAW.info.auto_text);
    const x = b.rows.find((r) => r.symbol === 'XXII')!;
    expect(x.auto).toEqual(autoRow('XXII').auto);
    expect(b.rows.filter((r) => r.auto).map((r) => r.symbol)).toEqual(AUTO);
    expect(b.rows.slice(0, 12).every((r) => r.auto === null)).toBe(true);
  });
  it('NEGATIVE: junk auto blocks → null; a row block without tag or text → null; a removal without text_full dropped', () => {
    for (const junk of [null, 'x', 3, [], {}, { state: '' }, { state: 3 }]) {
      expect(ok((b) => { b.auto = junk; }).auto).toBeNull();
    }
    for (const junk of [null, 'x', [], {}, { tag: '🤖' }, { text: 't' }, { tag: '', text: 't' }, { tag: '🤖', text: ' ' }]) {
      expect(ok((b) => { b.rows[12].auto = junk; }).rows[12].auto).toBeNull();
    }
    const b = ok((r) => { r.auto.removed[0].text_full = ''; r.auto.removed[1] = 'x'; r.auto.n = -3; r.auto.removed_total = 'x'; });
    expect(b.auto?.removed).toHaveLength(16);
    expect(b.auto?.n).toBe(0);
    expect(b.auto?.removed_total).toBeNull();
  });
  it('NEGATIVE: an older payload (no auto anywhere) → auto null, every row auto null, info.auto_text null', () => {
    const b = parseGgw(clone(oldFixture)) as GgwBoard;
    expect(b.auto).toBeNull();
    expect(b.rows.every((r) => r.auto === null)).toBe(true);
    expect(b.info?.auto_text).toBeNull();
  });
  it('ggwLiveSymbols = every row in served order (his, then auto) — NEGATIVE: never his `symbols` alone', () => {
    const b = ok();
    expect(ggwLiveSymbols(b)).toEqual(ALL);
    expect(ggwLiveSymbols(b)).toHaveLength(30);
    expect(ggwLiveSymbols(b)).not.toEqual(b.symbols);
    const old = parseGgw(clone(oldFixture)) as GgwBoard;
    expect(ggwLiveSymbols(old)).toEqual(old.rows.map((r) => r.symbol));
  });
  it('30 rows page at 2 / 4 / 9 per screen', () => {
    expect(ggwPageCount(30, 2)).toBe(15);
    expect(ggwPageCount(30, 4)).toBe(8);
    expect(ggwPageCount(30, 9)).toBe(4);
  });
});

type Call = { url: string; method: string; body?: string };
let calls: Call[] = [];
let boardNow: () => any = () => clone(RAW);
async function mount(opts: { phone?: boolean; board?: () => any } = {}) {
  boardNow = opts.board ?? (() => clone(RAW));
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: !!opts.phone && q === GGW_PHONE_MQ, media: q,
    addEventListener: () => {}, removeEventListener: () => {} }));
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ url, method, body: init?.body as string | undefined });
    if (method === 'DELETE') return { ok: true, json: async () => ({ state: 'dismissed', symbols: MANUAL, symbol: null, text: 'served dismissed' }) };
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return { ok: true, json: async () => ({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] }) };
    return { ok: true, json: async () => boardNow() };
  }));
  const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const tile = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;
const shown = (c: HTMLElement) => ALL.filter((s) => tile(c, s) && !tile(c, s).hidden);
const posts = () => calls.filter((x) => x.method === 'POST' && x.url.endsWith(GGW_LIVE_PATH));

describe('🤖 the board', { timeout: 20000 }, () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('tile: the 🤖 chip prints the served text verbatim; its title joins added · volume · leaving; ✕ title = remove_title', async () => {
    const c = await mount();
    const a = autoRow('LGHL').auto;
    const chip = tile(c, 'LGHL').querySelector('[data-testid="ggw-auto"]') as HTMLElement;
    expect(chip.textContent).toBe(a.text);
    expect(chip.getAttribute('title')).toBe(`${a.added_text} · ${a.volume_text} · ${a.leaving_text}`);
    const x = autoRow('XXII').auto;
    expect((tile(c, 'XXII').querySelector('[data-testid="ggw-auto"]') as HTMLElement).getAttribute('title'))
      .toBe(`${x.added_text} · ${x.volume_text}`);
    expect(x.volume_text).toMatch(/pass number/);                 // [C2] the tracker wording, as served
    const rmBtn = tile(c, 'LGHL').querySelector('.ggw-remove') as HTMLElement;
    expect(rmBtn.getAttribute('title')).toBe(a.remove_title);
    expect(rmBtn.getAttribute('aria-label')).toBe(a.remove_title);
    /* NEGATIVE: his tile has no chip and keeps the served remove label */
    expect(tile(c, 'OMH').querySelector('[data-testid="ggw-auto"]')).toBeNull();
    expect((tile(c, 'OMH').querySelector('.ggw-remove') as HTMLElement).getAttribute('title')).toBe(`${RAW.remove_label} OMH`);
    expect(c.querySelectorAll('[data-testid="ggw-auto"]')).toHaveLength(18);
  });
  it('NEGATIVE: no chip title when added / volume / leaving are all null', async () => {
    const c = await mount({ board: () => {
      const b = clone(RAW);
      Object.assign(b.rows[12].auto, { added_text: null, volume_text: null, leaving_text: null });
      return b;
    } });
    const chip = tile(c, AUTO[0]).querySelector('[data-testid="ggw-auto"]') as HTMLElement;
    expect(chip.textContent).toBe(RAW.rows[12].auto.text);
    expect(chip.hasAttribute('title')).toBe(false);
  });
  it('pager: auto items carry the class and the served tag; his items do not', async () => {
    const c = await mount();
    for (const s of AUTO) {
      const b = screen.getByTestId(`ggw-pager-${s}`);
      expect(b.textContent).toBe(`🤖 ${s}`);
      expect(b.parentElement!.classList.contains('ggw-pager-item--auto')).toBe(true);
      expect(screen.getByTestId(`ggw-pager-x-${s}`).getAttribute('title')).toBe(autoRow(s).auto.remove_title);
    }
    for (const s of MANUAL) {
      const b = screen.getByTestId(`ggw-pager-${s}`);
      expect(b.textContent).toBe(s);
      expect(b.parentElement!.classList.contains('ggw-pager-item--auto')).toBe(false);
    }
    expect(c.querySelectorAll('.ggw-pager-item--auto')).toHaveLength(18);
  });
  it('× on an auto name DELETEs that name only — NEGATIVE: never toggles the view, never another name', async () => {
    const c = await mount();
    const before = shown(c);
    fireEvent.click(screen.getByTestId('ggw-pager-x-SOUN'));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const del = calls.filter((x) => x.method === 'DELETE');
    expect(del).toHaveLength(1);
    expect(del[0].url).toContain('/chart-maps/gajjala-watch/symbols/SOUN');
    expect(shown(c)).toEqual(before);
    for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByTestId('ggw-msg').textContent).toBe('served dismissed');
  });
  it('the tile ✕ on an auto name DELETEs that name only', async () => {
    const c = await mount();
    fireEvent.click(tile(c, 'XXII').querySelector('.ggw-remove') as HTMLElement);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const del = calls.filter((x) => x.method === 'DELETE');
    expect(del.map((d) => d.url.split('/').pop())).toEqual(['XXII']);
  });
  it('head: the served title with the hint as its title; the removed strip collapsed, text_full verbatim, summary served', async () => {
    const c = await mount();
    const t = screen.getByTestId('ggw-auto-title');
    expect(t.textContent).toBe(RAW.auto.title);
    expect(t.getAttribute('title')).toBe(RAW.auto.hint);
    const strip = screen.getByTestId('ggw-auto-removed') as HTMLDetailsElement;
    expect(strip.tagName).toBe('DETAILS');
    expect(strip.open).toBe(false);
    expect(strip.querySelector('summary')!.textContent).toBe(RAW.auto.removed_title);
    const lines = Array.from(strip.querySelectorAll('[data-testid="ggw-auto-removed-line"]')).map((p) => p.textContent);
    expect(lines).toEqual(RAW.auto.removed.map((r: any) => r.text_full));
    /* NEGATIVE: no unreadable word, no empty word on a full ok section */
    expect(c.querySelector('[data-testid="ggw-auto-unreadable"]')).toBeNull();
    expect(c.querySelector('[data-testid="ggw-auto-empty"]')).toBeNull();
    expect(screen.getByTestId('ggw-info-auto').textContent).toBe(RAW.info.auto_text);
  });
  it('unreadable: the served word prints as a warning; his rows stay', async () => {
    const c = await mount({ board: () => {
      const b = clone(RAW);
      b.rows = b.rows.filter((r: any) => !r.auto);
      Object.assign(b.auto, { state: 'unreadable', n: 0, symbols: [], removed: [], text: 'served: the auto list could not be read' });
      return b;
    } });
    expect(screen.getByTestId('ggw-auto-unreadable').textContent).toBe('served: the auto list could not be read');
    expect(screen.getByTestId('ggw-auto-unreadable').classList.contains('ggw-warn')).toBe(true);
    expect(c.querySelector('[data-testid="ggw-auto-removed"]')).toBeNull();
    for (const s of MANUAL) expect(tile(c, s)).not.toBeNull();
  });
  it('empty: n == 0 prints the served empty word; NEGATIVE: never when n > 0', async () => {
    await mount({ board: () => {
      const b = clone(RAW);
      b.rows = b.rows.filter((r: any) => !r.auto);
      Object.assign(b.auto, { n: 0, symbols: [], empty_text: 'served: no potential right now' });
      return b;
    } });
    expect(screen.getByTestId('ggw-auto-empty').textContent).toBe('served: no potential right now');
    cleanup();
    const c = await mount({ board: () => { const b = clone(RAW); b.auto.empty_text = 'served: no potential right now'; return b; } });
    expect(c.querySelector('[data-testid="ggw-auto-empty"]')).toBeNull();
  });
  it('NEGATIVE: an older payload renders as today — no 🤖 anywhere', async () => {
    const c = await mount({ board: () => clone(oldFixture) });
    expect(c.textContent).not.toContain('🤖');
    for (const id of ['ggw-auto', 'ggw-auto-title', 'ggw-auto-removed', 'ggw-auto-unreadable', 'ggw-auto-empty', 'ggw-info-auto']) {
      expect(c.querySelector(`[data-testid="${id}"]`)).toBeNull();
    }
    expect(c.querySelector('.ggw-pager-item--auto')).toBeNull();
    expect(JSON.parse(posts()[0].body!)).toEqual({ symbols: (oldFixture as any).rows.map((r: any) => r.symbol) });
  });
  it('[C9] the live POST carries every row: 12 + 18 = 30 in served order — NEGATIVE: not his symbols alone', async () => {
    await mount();
    expect(posts()).toHaveLength(1);
    const body = JSON.parse(posts()[0].body!);
    expect(body).toEqual({ symbols: ALL });
    expect(body.symbols).toHaveLength(30);
    expect(body.symbols).not.toEqual(MANUAL);
  });
  /* 2026-11-25 (ggwcols) — Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive
   * while I scroll." The pick is the grid's columns; every row is in one scrolling grid, every chip lit, no counter. */
  it('30 rows at 2 / 4 / 9 per screen: all 30 shown in the pick\'s columns, no counter, ◀ ▶ disabled; ← → never hide a tile', async () => {
    const c = await mount();
    const grid = () => c.querySelector('.ggw-grid') as HTMLElement;
    const pressedAll = () => ALL.filter((s) => screen.getByTestId(`ggw-pager-${s}`).getAttribute('aria-pressed') === 'true');
    for (const [l, cols] of [[2, 2], [4, 2], [9, 3]] as const) {
      fireEvent.click(screen.getByTestId(`ggw-layout-${l}`));
      expect(grid().dataset.layout).toBe(String(l));
      expect(grid().classList.contains(`ggw-grid--cols${cols}`)).toBe(true);
      expect(shown(c)).toEqual(ALL);
      expect(shown(c)).toHaveLength(30);
      expect(pressedAll()).toEqual(ALL);
      expect(c.querySelector('[data-testid="ggw-pager-at"]')).toBeNull();
      expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
      expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
    }
    /* NEGATIVE: ← → (jsdom: nothing measured) and the greyed ▶ change nothing */
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    for (let i = 0; i < 6; i += 1) fireEvent.keyDown(document, { key: 'ArrowRight' });
    fireEvent.click(screen.getByTestId('ggw-pager-next'));
    expect(shown(c)).toEqual(ALL);
    expect(c.querySelectorAll('.ggw-grid > .ggw-tile[hidden]')).toHaveLength(0);
    expect(c.querySelector('[data-testid="ggw-pager-at"]')).toBeNull();
  });
  it('a tap on an auto name flips THAT one name (the toggle keys by symbol); NEGATIVE: never an empty board', async () => {
    const c = await mount();
    const pressed = (s: string) => screen.getByTestId(`ggw-pager-${s}`).getAttribute('aria-pressed');
    fireEvent.click(screen.getByTestId('ggw-pager-MARA'));
    expect(shown(c)).toEqual(ALL.filter((s) => s !== 'MARA'));
    expect(pressed('MARA')).toBe('false');
    expect(pressed('OMH')).toBe('true');
    fireEvent.click(screen.getByTestId('ggw-pager-OMH'));
    expect(shown(c)).toEqual(ALL.filter((s) => s !== 'MARA' && s !== 'OMH'));
    fireEvent.click(screen.getByTestId('ggw-pager-MARA'));
    expect(shown(c)).toEqual(ALL.filter((s) => s !== 'OMH'));
    expect(pressed('MARA')).toBe('true');
    fireEvent.click(screen.getByTestId('ggw-pager-OMH'));
    expect(shown(c)).toEqual(ALL);
    /* the filter result is unchanged once it narrows: all but MARA off → MARA alone */
    for (const s of ALL) if (s !== 'MARA') fireEvent.click(screen.getByTestId(`ggw-pager-${s}`));
    expect(shown(c)).toEqual(['MARA']);
    fireEvent.click(screen.getByTestId('ggw-pager-MARA'));
    expect(shown(c)).toEqual(ALL);
    expect(shown(c)).not.toHaveLength(0);
  });
  it('[C4] two GETs with the same rows in the same order → a far tile keeps its DOM node (no re-key), every row still shown', async () => {
    const c = await mount();
    const far = ALL[13];
    const before = shown(c);
    const node = tile(c, far);
    expect(before).toEqual(ALL);
    expect(node.hidden).toBe(false);
    const gets = () => calls.filter((x) => x.method === 'GET').length;
    const g0 = gets();
    await act(async () => { await vi.advanceTimersByTimeAsync(RAW.refresh_sec * 1000 + 10); });
    for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(gets()).toBeGreaterThan(g0);
    expect(shown(c)).toEqual(before);
    expect(tile(c, far)).toBe(node);                              // the same DOM node — keyed by symbol, never re-mounted
    expect(c.querySelector('[data-testid="ggw-pager-at"]')).toBeNull();
  });
  it('📱 phone: one column, every row shown (no pages), chips are .ggw-chip (they wrap at 430 px)', async () => {
    const c = await mount({ phone: true });
    expect(shown(c)).toEqual(ALL);
    expect(c.querySelector('[data-testid="ggw-pager-at"]')).toBeNull();
    for (const chip of Array.from(c.querySelectorAll('[data-testid="ggw-auto"]'))) {
      expect(chip.classList.contains('ggw-chip')).toBe(true);
    }
  });
});

describe('🤖 stylesheet (source guards — jsdom has no layout)', () => {
  async function css(): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/styles/gajjalaWatch.css`, 'utf8');
  }
  const rule = (src: string, sel: string) => {
    const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  it('the auto chip, the dashed pager item and the strip summary — NEGATIVE: no nowrap on the chip or the strip', async () => {
    const src = await css();
    expect(rule(src, '.ggw-auto')).toMatch(/color:\s*var\(--accent/);
    expect(rule(src, '.ggw-pager-item--auto .ggw-pager-sym')).toMatch(/border-style:\s*dashed/);
    expect(rule(src, '.ggw-auto-removed summary')).toMatch(/font-size:\s*0\.74rem/);
    expect(rule(src, '.ggw-auto-removed')).toMatch(/min-width:\s*0/);
    for (const sel of ['.ggw-auto', '.ggw-auto-removed', '.ggw-auto-removed summary']) {
      expect(rule(src, sel)).not.toMatch(/nowrap/);
    }
  });
});
