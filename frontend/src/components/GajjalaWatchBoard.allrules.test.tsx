/* ✅ 👀 Watch — All rules met, the board (2026-11-24, spec watch_all_rules §3.6 / §4 WP fe-watch).
 * Ajay 2026-11-24: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep tracking
 * them later". The real board, fetch stubbed. The server serves a LAST section `rules` (`folded_default: true`) and ✅
 * rows under `row.auto` (`why: "rules"`). Phone: ✅ is ONE folded header line until he taps it (remembered in
 * `ggw.opened`); a push link / pager tap into ✅ opens it; ✅ names post to the live hub only while open, always last.
 * Desktop: no headers, ✅ tiles after 🤖. A served `rules.state "unreadable"` → one warn line OUTSIDE ℹ️. Every word is a
 * stand-in for a served one. NEGATIVES: a section without folded_default stays open; junk folded_default → open; junk
 * ggw.opened → folded; nothing else new above the cards; × on a ✅ row → DELETE with the served remove_title; 430 px
 * source guards; his names always live. */
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import gold from '../lib/__fixtures__/ggwAllRules.golden.json';
import gold90 from '../lib/__fixtures__/ggwAllRules90.golden.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_COLLAPSED_KEY, GGW_LIVE_PATH, GGW_OPENED_KEY, GGW_PATH, GGW_PICK_KEY } from '../lib/gajjalaWatch';

/* the live bus is not under test here — a no-op subscription (the GajjalaWatchBoard.live pattern) */
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const AUTO = (why: string, sym: string) => ({
  tag: why === 'rules' ? '✅' : '🤖', text: `served-auto-${why}-${sym}`, why, added_text: 'served-added-words',
  remove_title: `served-remove-title-${why}-${sym}`,
});
const ORG = (group: string, sym: string) => ({
  group, when: { bucket: 'intraday', text: `served-when-${sym}`, title: null }, setup: null, ran: null, past_winner: null,
});
function rowOf(sym: string, group: string, o: Record<string, unknown> = {}): any {
  const base = clone(RAW.rows[2]);
  base.symbol = sym;
  if (typeof base.text === 'string') base.text = base.text.split('XYZQ').join(sym);
  return { ...base, auto: null, aplus: null, added_at: null, org: ORG(group, sym), ...o };
}
const SEC = (key: string, n: number, syms: string[], o: Record<string, unknown> = {}) => ({
  key, title: `served-title-${key}`, text: `served-head-${key} · ${n}`, hint: `served-hint-${key}`, n, symbols: syms, ...o,
});
function rows(): any[] {
  return [
    rowOf('H1', 'yours'), rowOf('H2', 'yours'),
    rowOf('AP1', 'aplus', { auto: AUTO('aplus', 'AP1'), aplus: { tag: '🎯', text: 'served-aplus', title: null, items: [] } }),
    rowOf('AU1', 'auto', { auto: AUTO('potential', 'AU1') }),
    rowOf('R1', 'rules', { auto: AUTO('rules', 'R1') }),
    rowOf('R2', 'rules', { auto: AUTO('rules', 'R2') }),
  ];
}
const RULES_FOLD = { folded_default: true };
function board(o: { rules?: unknown; rulesSec?: Record<string, unknown>; refresh?: number } = {}): any {
  const b = clone(RAW);
  b.rows = rows();
  b.symbols = ['H1', 'H2'];
  b.refresh_sec = o.refresh ?? 0;
  b.next_window_sec = null;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  b.auto = { state: 'ok', n: 2, symbols: ['AP1', 'AU1'], title: 'served-auto-head', hint: 'served-auto-hint', removed: [] };
  b.sections = [SEC('yours', 2, ['H1', 'H2']), SEC('aplus', 1, ['AP1']), SEC('auto', 1, ['AU1']),
    SEC('rules', 2, ['R1', 'R2'], o.rulesSec ?? RULES_FOLD)];
  if (o.rules !== undefined) b.rules = o.rules;
  return b;
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;

type Call = { url: string; method: string; body?: string };
let serve: () => any = () => board();
let calls: Call[] = [];
let scrolled: string[] = [];
let phoneNow = true;
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });

async function mount(search = '') {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: phoneNow, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method, body: init?.body as string | undefined });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return res({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] });
    if (method === 'DELETE') return res({ state: 'dismissed', symbols: ['H1', 'H2'], symbol: null, text: 'served-dismissed' });
    if (url.includes(GGW_PATH)) return res(serve());
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch${search}`]}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 5; i += 1) await flush();
  return r.container;
}
const q = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
const tile = (c: HTMLElement, s: string) => q(c, `ggw-tile-${s}`);
const isShown = (c: HTMLElement, s: string) => !!tile(c, s) && !tile(c, s)!.hidden;
const store = () => window.localStorage;
const gridKids = (c: HTMLElement) => Array.from(c.querySelector('.ggw-grid')!.children).map((e) => e.getAttribute('data-testid'));
const posts = () => calls.filter((x) => x.method === 'POST' && x.url.endsWith(GGW_LIVE_PATH));
const lastPosted = (): string[] => JSON.parse(posts()[posts().length - 1].body as string).symbols;

const origScroll = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse('2026-11-24T15:00:00.000Z'));
  vi.stubGlobal('localStorage', memStorage());
  vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  serve = () => board();
  scrolled = [];
  phoneNow = true;
  (Element.prototype as any).scrollIntoView = function (this: HTMLElement) { if (this.id) scrolled.push(this.id); };
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  (Element.prototype as any).scrollIntoView = origScroll;
});

describe('📱 phone: ✅ is one folded header line until he opens it', { timeout: 20000 }, () => {
  it('✅ header LAST, folded ("▸"), its tiles hidden; every other section open', async () => {
    const c = await mount();
    expect(gridKids(c)).toEqual([
      'ggw-section-yours', 'ggw-tile-H1', 'ggw-tile-H2', 'ggw-section-aplus', 'ggw-tile-AP1',
      'ggw-section-auto', 'ggw-tile-AU1', 'ggw-section-rules', 'ggw-tile-R1', 'ggw-tile-R2',
    ]);
    const btn = q(c, 'ggw-section-btn-rules')!;
    expect(btn.textContent).toBe('▸ served-head-rules · 2');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(q(c, 'ggw-section-rules')!.classList.contains('ggw-section--folded')).toBe(true);
    for (const s of ['R1', 'R2']) expect(isShown(c, s)).toBe(false);
    for (const s of ['H1', 'H2', 'AP1', 'AU1']) expect(isShown(c, s)).toBe(true);
    for (const k of ['yours', 'aplus', 'auto']) expect(q(c, `ggw-section-btn-${k}`)!.getAttribute('aria-expanded')).toBe('true');
  });
  it('a tap opens ✅ and persists ggw.opened (ggw.collapsed untouched); still open after a remount; a 2nd tap folds it', async () => {
    let c = await mount();
    fireEvent.click(q(c, 'ggw-section-btn-rules')!);
    await flush();
    expect(q(c, 'ggw-section-btn-rules')!.textContent).toBe('▾ served-head-rules · 2');
    expect(isShown(c, 'R1')).toBe(true);
    expect(JSON.parse(store().getItem(GGW_OPENED_KEY)!)).toEqual(['rules']);
    expect(store().getItem(GGW_COLLAPSED_KEY)).toBeNull();
    cleanup();
    c = await mount();
    expect(isShown(c, 'R2')).toBe(true);
    fireEvent.click(q(c, 'ggw-section-btn-rules')!);
    await flush();
    expect(isShown(c, 'R2')).toBe(false);
    expect(store().getItem(GGW_OPENED_KEY)).toBeNull();
  });
  it('folding 🤖 still writes ggw.collapsed exactly as before (and never ggw.opened)', async () => {
    const c = await mount();
    fireEvent.click(q(c, 'ggw-section-btn-auto')!);
    await flush();
    expect(isShown(c, 'AU1')).toBe(false);
    expect(JSON.parse(store().getItem(GGW_COLLAPSED_KEY)!)).toEqual(['auto']);
    expect(store().getItem(GGW_OPENED_KEY)).toBeNull();
  });
  it('?focus= (a push link) on a ✅ name opens ✅ and scrolls once', async () => {
    const c = await mount('&focus=R2');
    for (let i = 0; i < 3; i += 1) await flush();
    expect(isShown(c, 'R2')).toBe(true);
    expect(q(c, 'ggw-section-btn-rules')!.getAttribute('aria-expanded')).toBe('true');
    expect(scrolled.filter((x) => x === 'ggw-R2')).toHaveLength(1);
    expect(JSON.parse(store().getItem(GGW_OPENED_KEY)!)).toEqual(['rules']);
  });
  it('a pager tap on a ✅ name opens ✅ (never turns the name off)', async () => {
    const c = await mount();
    fireEvent.click(q(c, 'ggw-pager-R1')!);
    for (let i = 0; i < 3; i += 1) await flush();
    expect(isShown(c, 'R1')).toBe(true);
    expect(isShown(c, 'R2')).toBe(true);
    expect(isShown(c, 'H1')).toBe(true);
    expect(scrolled.filter((x) => x === 'ggw-R1')).toHaveLength(1);
  });
  it('NEGATIVE: a section without folded_default → open as before', async () => {
    serve = () => board({ rulesSec: {} });
    const c = await mount();
    expect(q(c, 'ggw-section-btn-rules')!.getAttribute('aria-expanded')).toBe('true');
    expect(isShown(c, 'R1')).toBe(true);
  });
  it('NEGATIVE: junk folded_default ("yes", 1) → open', async () => {
    for (const junk of ['yes', 1]) {
      serve = () => board({ rulesSec: { folded_default: junk } });
      const c = await mount();
      expect(isShown(c, 'R1')).toBe(true);
      cleanup();
    }
  });
  it('NEGATIVE: junk ggw.opened → ✅ folded', async () => {
    for (const junk of ['not json', '{"rules":1}', '[1]', 'rules']) {
      store().setItem(GGW_OPENED_KEY, junk);
      const c = await mount();
      expect(isShown(c, 'R1')).toBe(false);
      expect(isShown(c, 'H1')).toBe(true);
      cleanup();
    }
  });
});

describe('🖥 desktop unchanged', { timeout: 20000 }, () => {
  it('no headers; ✅ tiles come after 🤖 in served order; the default fold never hides a desktop tile', async () => {
    phoneNow = false;
    const c = await mount('&per=9');
    expect(c.querySelector('.ggw-section')).toBeNull();
    expect(gridKids(c)).toEqual(['ggw-tile-H1', 'ggw-tile-H2', 'ggw-tile-AP1', 'ggw-tile-AU1', 'ggw-tile-R1', 'ggw-tile-R2']);
    for (const s of ['H1', 'AU1', 'R1', 'R2']) expect(isShown(c, s)).toBe(true);
  });
  it('NEGATIVE: a ✅ name never joins his pick (a pick of H1 stays H1 — the ✅ tiles stay off)', async () => {
    phoneNow = false;
    serve = () => {
      const b = board();
      for (const r of b.rows) r.added_at = '2026-11-24T14:59:00Z';
      return b;
    };
    store().setItem(GGW_PICK_KEY, 'H1');
    const c = await mount();
    expect(isShown(c, 'H1')).toBe(true);
    expect(isShown(c, 'R1')).toBe(false);
    expect(isShown(c, 'R2')).toBe(false);
    expect(store().getItem(GGW_PICK_KEY)!.split(',')).not.toContain('R1');
  });
});

describe('✅ [C4] the live interest', { timeout: 20000 }, () => {
  it('phone, ✅ folded → no ✅ symbol posted; opened → posted, last', async () => {
    serve = () => board({ refresh: 60 });
    const c = await mount();
    expect(posts().length).toBeGreaterThan(0);
    expect(lastPosted()).toEqual(['H1', 'H2', 'AP1', 'AU1']);
    fireEvent.click(q(c, 'ggw-section-btn-rules')!);
    for (let i = 0; i < 3; i += 1) await flush();
    expect(lastPosted()).toEqual(['H1', 'H2', 'AP1', 'AU1', 'R1', 'R2']);
  });
  it('NEGATIVE: his names always live — folding 👤 and 🤖 never drops them', async () => {
    serve = () => board({ refresh: 60 });
    store().setItem(GGW_COLLAPSED_KEY, '["yours","auto"]');
    await mount();
    expect(lastPosted()).toEqual(['H1', 'H2', 'AP1', 'AU1']);
  });
  it('desktop: every row posted, ✅ last', async () => {
    phoneNow = false;
    serve = () => {
      const b = board({ refresh: 60 });
      b.rows = [b.rows[4], ...b.rows.slice(0, 4), b.rows[5]];          // a server that interleaves ✅ first
      return b;
    };
    await mount('&per=9');
    expect(lastPosted()).toEqual(['H1', 'H2', 'AP1', 'AU1', 'R1', 'R2']);
  });
});

describe('✅ ×, the fault line and the head', { timeout: 20000 }, () => {
  it('× on a ✅ row → DELETE that name; the button title is the served remove_title', async () => {
    phoneNow = false;
    const c = await mount('&per=9');
    const rm = tile(c, 'R1')!.querySelector('.ggw-remove') as HTMLButtonElement;
    expect(rm.getAttribute('title')).toBe('served-remove-title-rules-R1');
    fireEvent.click(rm);
    for (let i = 0; i < 3; i += 1) await flush();
    const del = calls.filter((x) => x.method === 'DELETE');
    expect(del).toHaveLength(1);
    expect(decodeURIComponent(del[0].url.split('/').pop() as string)).toBe('R1');
  });
  it('rules.state "unreadable" → ONE warn line outside ℹ️; the other rows intact', async () => {
    serve = () => board({ rules: { state: 'unreadable', n: 0, text: 'served-rules-unreadable' } });
    const c = await mount();
    const lines = c.querySelectorAll('[data-testid="ggw-rules-unreadable"]');
    expect(lines).toHaveLength(1);
    expect(lines[0].textContent).toBe('served-rules-unreadable');
    expect(lines[0].classList.contains('ggw-warn')).toBe(true);
    expect(lines[0].classList.contains('ggw-line')).toBe(true);
    expect(lines[0].closest('details')).toBeNull();
    expect(lines[0].closest('.ggw-head')).not.toBeNull();
    for (const s of ['H1', 'H2', 'AP1', 'AU1']) expect(isShown(c, s)).toBe(true);
  });
  it('NEGATIVE: state ok / off / unreadable without text → no line; nothing else new above the cards', async () => {
    serve = () => board();
    const base = (await mount()).querySelector('.ggw-head')!.innerHTML;
    cleanup();
    for (const rules of [{ state: 'ok', n: 2, keep_sessions: 5, text: 'x', not_seated_n: 3 }, { state: 'off', text: 'x' },
      { state: 'unreadable', text: null }, 'junk']) {
      serve = () => board({ rules });
      const c = await mount();
      expect(q(c, 'ggw-rules-unreadable')).toBeNull();
      expect(c.querySelector('.ggw-head')!.innerHTML).toBe(base);
      cleanup();
    }
  });
});

describe('✅ the BE goldens on the real board (be-payload writes them; pinned both sides)', { timeout: 20000 }, () => {
  const G = (): any => clone(gold as any);
  const G90 = (): any => clone(gold90 as any);
  const rulesSyms = (b: any): string[] => b.rows.filter((r: any) => r.org?.group === 'rules').map((r: any) => r.symbol);
  it('phone: the ✅ header is folded ("▸" + the served words), its tiles hidden; a tap opens it and persists ggw.opened', async () => {
    serve = G;
    const c = await mount();
    const sec = (G().sections as any[]).find((s) => s.key === 'rules');
    const btn = q(c, 'ggw-section-btn-rules')!;
    expect(btn.textContent).toBe(`▸ ${sec.text}`);
    const kids = gridKids(c);
    expect(kids.indexOf('ggw-section-rules')).toBeGreaterThan(kids.indexOf('ggw-section-auto'));
    for (const s of rulesSyms(G())) expect(isShown(c, s)).toBe(false);
    fireEvent.click(btn);
    await flush();
    for (const s of rulesSyms(G())) expect(isShown(c, s)).toBe(true);
    expect(JSON.parse(store().getItem(GGW_OPENED_KEY)!)).toEqual(['rules']);
  });
  it('90-row golden, phone: ✅ folded → only the 👤/🎯/🤖 names posted; opened → every name, ✅ after all of them', async () => {
    serve = G90;
    const c = await mount();
    const rs = new Set(rulesSyms(G90()));
    const others = G90().rows.map((r: any) => r.symbol).filter((s: string) => !rs.has(s));
    expect(lastPosted()).toEqual(others);
    fireEvent.click(q(c, 'ggw-section-btn-rules')!);
    for (let i = 0; i < 3; i += 1) await flush();
    const all = lastPosted();
    expect(all).toHaveLength(G90().rows.length);
    expect(all.slice(0, others.length)).toEqual(others);
    expect(all.slice(others.length).every((s) => rs.has(s))).toBe(true);
    expect(all.slice(80).every((s) => rs.has(s))).toBe(true);           // the hub's refused tail is ✅ only
  });
  it('desktop (golden): no headers, ✅ tiles after 🤖', async () => {
    phoneNow = false;
    serve = G;
    const c = await mount('&per=9');
    expect(c.querySelector('.ggw-section')).toBeNull();
    const kids = gridKids(c);
    const lastAuto = Math.max(...G().rows.filter((r: any) => r.org?.group === 'auto').map((r: any) => kids.indexOf(`ggw-tile-${r.symbol}`)));
    for (const s of rulesSyms(G())) expect(kids.indexOf(`ggw-tile-${s}`)).toBeGreaterThan(lastAuto);
  });
});

describe('📱 430 px guards (jsdom has no layout — source guards on the stylesheet the board imports)', () => {
  async function css(): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/styles/gajjalaWatch.css`, 'utf8');
  }
  const rule = (src: string, sel: string): string | null => {
    const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  it('the ✅ header wraps inside the board (min-width 0, wrap, max-width 100%); tiles never wider than the board', async () => {
    const src = await css();
    expect(rule(src, '.ggw-section')).toMatch(/min-width:\s*0/);
    const btn = rule(src, '.ggw-section-btn')!;
    for (const re of [/white-space:\s*normal/, /overflow-wrap:\s*anywhere/, /min-width:\s*0/, /max-width:\s*100%/]) expect(btn).toMatch(re);
    const t = rule(src, '.ggw-tile, .ggw-frame')!;
    expect(t).toMatch(/min-width:\s*0/);
    expect(t).toMatch(/max-width:\s*100%/);
    /* NEGATIVE: a nowrap header would fail */
    expect(rule('.ggw-section-btn { white-space: nowrap; }', '.ggw-section-btn')).not.toMatch(/white-space:\s*normal/);
  });
  it('on the phone the ✅ header and the fault line are wrapping classes; ✅ tiles are plain .ggw-tile', async () => {
    serve = () => board({ rules: { state: 'unreadable', text: 'served-rules-unreadable-a-very-long-unbreakable-word' } });
    const c = await mount();
    expect(q(c, 'ggw-section-btn-rules')!.classList.contains('ggw-section-btn')).toBe(true);
    expect(q(c, 'ggw-rules-unreadable')!.classList.contains('ggw-line')).toBe(true);
    expect(tile(c, 'R1')!.classList.contains('ggw-tile')).toBe(true);
    expect(tile(c, 'R1')!.getAttribute('style') ?? '').not.toMatch(/width/);
  });
});
