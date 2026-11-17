/* 🎯 Gajjala's Watch — the A+ tag (2026-11-17, spec ggwaplus).
 * Ajay 2026-11-17 ~12:58 ET, verbatim: "Also add an A+ tag on watch list as they become A+".
 *
 * The REAL board over the 2026-11-17 auto fixture with a served `aplus` block on one of his names (OMH) and on the first
 * auto name. Every word is a stand-in for a served one. NEGATIVES: junk / missing blocks parse to null → no chip and no
 * pager prefix; an older payload tags nothing; an item without source / setup / state is dropped; the chip never
 * nowraps (it wraps at 430 px like every .ggw-chip). */
import { act, cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import oldFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_LIVE_PATH, GGW_PHONE_MQ, parseGgw, parseRowAplus, type GgwBoard } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const BASE = autoFixture as any;
const MANUAL: string[] = BASE.symbols;
const AUTO: string[] = BASE.auto.symbols;
const HIS = 'OMH';
const BOT = AUTO[0];
const block = (at: string, extra: any[] = []) => ({
  tag: '🎯', text: `🎯 A+ ${at}`, title: `SERVED-TITLE ${at}`,
  items: [{ source: 'gajjala', source_word: '🚩 5-min', setup: 'kiss_fly', setup_label: '💋 EMA Kiss & Fly',
            state: 'triggered', word: 'A+ (triggered)', at_et: at }, ...extra],
});
function tagged(): any {
  const b = clone(BASE);
  for (const r of b.rows) r.aplus = null;
  b.rows.find((r: any) => r.symbol === HIS).aplus = block('10:35');
  b.rows.find((r: any) => r.symbol === BOT).aplus = block('09:47');
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

describe('🎯 parse', () => {
  it('keeps the served block verbatim on the tagged rows; every other row is null', () => {
    const b = parseGgw(tagged()) as GgwBoard;
    expect(b.rows.find((r) => r.symbol === HIS)!.aplus).toEqual(block('10:35'));
    expect(b.rows.find((r) => r.symbol === BOT)!.aplus).toEqual(block('09:47'));
    expect(b.rows.filter((r) => r.aplus).map((r) => r.symbol)).toEqual([HIS, BOT]);
  });
  it('NEGATIVE: junk / missing → null; an item without source / setup / state is dropped', () => {
    for (const junk of [undefined, null, 'x', 3, [], {}, { tag: '🎯' }, { text: '🎯 A+' }, { tag: '', text: 't' },
      { tag: '🎯', text: ' ' }]) {
      expect(parseRowAplus(junk)).toBeNull();
    }
    const p = parseRowAplus(block('10:35', [{ source: 'gga' }, 'x', null, { source: 'gga', setup: 'kiss_fly', state: '' }]));
    expect(p!.items).toHaveLength(1);
    expect(parseRowAplus({ tag: '🎯', text: '🎯 A+', title: 3, items: 'x' })).toEqual(
      { tag: '🎯', text: '🎯 A+', title: null, items: [] });
  });
  it('NEGATIVE: an older payload (no aplus anywhere) → every row null', () => {
    const b = parseGgw(clone(oldFixture)) as GgwBoard;
    expect(b.rows.every((r) => r.aplus === null)).toBe(true);
  });
});

let boardNow: () => any = tagged;
async function mount(opts: { phone?: boolean; board?: () => any } = {}) {
  boardNow = opts.board ?? tagged;
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: !!opts.phone && q === GGW_PHONE_MQ, media: q,
    addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return { ok: true, json: async () => ({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] }) };
    return { ok: true, json: async () => boardNow() };
  }));
  const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const tile = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;

describe('🎯 the board', { timeout: 20000 }, () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('tile: the chip prints the served text verbatim right after SYM; hover = the served title', async () => {
    const c = await mount();
    for (const [s, at] of [[HIS, '10:35'], [BOT, '09:47']]) {
      const chip = tile(c, s).querySelector('[data-testid="ggw-aplus"]') as HTMLElement;
      expect(chip.textContent).toBe(`🎯 A+ ${at}`);
      expect(chip.getAttribute('title')).toBe(`SERVED-TITLE ${at}`);
      expect(chip.classList.contains('ggw-chip')).toBe(true);
      expect(chip.classList.contains('ggw-aplus')).toBe(true);
      expect(chip.previousElementSibling!.classList.contains('ggw-sym')).toBe(true);
    }
    expect(c.querySelectorAll('[data-testid="ggw-aplus"]')).toHaveLength(2);
  });
  it('NEGATIVE: an untagged row (null / junk / absent block) draws no chip', async () => {
    const c = await mount({ board: () => {
      const b = tagged();
      b.rows.find((r: any) => r.symbol === HIS).aplus = { tag: '🎯' };          // junk
      delete b.rows.find((r: any) => r.symbol === BOT).aplus;                    // absent
      return b;
    } });
    expect(c.querySelectorAll('[data-testid="ggw-aplus"]')).toHaveLength(0);
    expect(screen.getByTestId(`ggw-pager-${HIS}`).textContent).toBe(HIS);
    expect(screen.getByTestId(`ggw-pager-${BOT}`).textContent).toBe(`🤖 ${BOT}`);
  });
  it('pager: the served 🎯 prefix + the --aplus class only on tagged names (before the 🤖 tag on an auto name)', async () => {
    await mount();
    const his = screen.getByTestId(`ggw-pager-${HIS}`);
    expect(his.textContent).toBe(`🎯 ${HIS}`);
    expect(his.classList.contains('ggw-pager-sym--aplus')).toBe(true);
    expect(his.getAttribute('title')).toBe('SERVED-TITLE 10:35');
    const bot = screen.getByTestId(`ggw-pager-${BOT}`);
    expect(bot.textContent).toBe(`🎯 🤖 ${BOT}`);
    expect(bot.classList.contains('ggw-pager-sym--aplus')).toBe(true);
    for (const s of [...MANUAL, ...AUTO].filter((x) => x !== HIS && x !== BOT)) {
      const b = screen.getByTestId(`ggw-pager-${s}`);
      expect(b.textContent!.startsWith('🎯')).toBe(false);
      expect(b.classList.contains('ggw-pager-sym--aplus')).toBe(false);
      expect(b.hasAttribute('title')).toBe(false);
    }
  });
  it('phone 430 px: the chip still renders as a wrapping .ggw-chip', async () => {
    const c = await mount({ phone: true });
    const chip = tile(c, HIS).querySelector('[data-testid="ggw-aplus"]') as HTMLElement;
    expect(chip.className).toBe('ggw-chip ggw-aplus');
  });
});

describe('🎯 stylesheet (source guards — jsdom has no layout)', () => {
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
  it('the chip and the pager outline read --positive; the chip wraps (min-width 0) — NEGATIVE: never nowrap', async () => {
    const src = await css();
    expect(rule(src, '.ggw-chip.ggw-aplus')).toMatch(/color:\s*var\(--positive/);
    expect(rule(src, '.ggw-pager-sym.ggw-pager-sym--aplus')).toMatch(/border-color:\s*var\(--positive/);
    const chip = rule(src, '.ggw-chip')!;
    expect(chip).toMatch(/white-space:\s*normal/);
    expect(chip).toMatch(/min-width:\s*0/);
    expect(chip).toMatch(/overflow-wrap:\s*anywhere/);
    for (const sel of ['.ggw-chip.ggw-aplus', '.ggw-pager-sym.ggw-pager-sym--aplus']) {
      expect(rule(src, sel)).not.toMatch(/nowrap|min-width:\s*[1-9]/);
    }
  });
});
