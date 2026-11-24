/* 🚫 the 👀 Watch's one-way broker mark on the REAL board (2026-11-19, spec watchfid §3.3 / §4 WP-C tests 5, 6, 8, 9, 10).
 * The 2026-11-17 auto fixture (12 of his names, then 18 🤖 rows) + a served `broker` block + a served row word on ONE of
 * his rows (OMH); fetch routed by method + path. Every word is a stand-in for a served one. NEGATIVES: no block → no
 * button and a byte-equal tile; no 🚫 in the ⤢ view; the 🚫 never sits beside ✕; a failed DELETE prints
 * GGW_FETCH_FAILED; never a DELETE on the broker route; the FE files type no broker word; scoped CSS only;
 * GajjalaBoard.tsx untouched. UNMEASURED. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { Tile } from './GajjalaWatchTile';
import { GgwBrokerButton } from './GgwBrokerMark';
import { API } from '../lib/apiBase';
import { GG_BROKER_PATH } from '../lib/gajjala';
import { GGW_FETCH_FAILED, GGW_LIVE_PATH, GGW_PATH, ggwSymbolPath, parseGgw, type GgwBoard } from '../lib/gajjalaWatch';
import type { GgwBroker } from '../lib/ggwBroker';
import markSrc from './GgwBrokerMark.tsx?raw';
import brokerLibSrc from '../lib/ggwBroker.ts?raw';
import boardSrc from './GajjalaWatchBoard.tsx?raw';
import tileSrc from './GajjalaWatchTile.tsx?raw';
import tagsSrc from './GajjalaWatchTags.tsx?raw';
import watchLibSrc from '../lib/gajjalaWatch.ts?raw';
import ggBoardSrc from './GajjalaBoard.tsx?raw';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const BLOCK: GgwBroker = {
  toggle: '🚫', text: '🚫 served broker word', title: 'served mark title — served words', editable: true,
  fault_text: null, auto_text: '🚫 served kept-off line: AZI, CHSN', auto_fault_text: null,
};
const WORD = '🚫 served broker word';
const DEL_TEXT = 'served removed words';
function boardWith(block: unknown = BLOCK): any {
  const b = clone(RAW);
  if (block !== undefined) b.broker = clone(block);
  for (const r of b.rows) r.broker_text = r.symbol === 'OMH' ? WORD : null;
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
let delStatus = 200;
async function mount(board: () => any = () => boardWith()) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ url, method, body: typeof init?.body === 'string' ? init.body : undefined });
    const ok = (j: unknown) => ({ ok: true, status: 200, json: async () => j } as unknown as Response);
    if (method === 'DELETE') {
      if (delStatus !== 200) return { ok: false, status: delStatus, json: async () => ({}) } as unknown as Response;
      return ok({ state: 'removed', symbols: [], symbol: null, text: DEL_TEXT });
    }
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return ok({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] });
    if (method === 'POST' && url.endsWith(GG_BROKER_PATH)) return ok({ state: 'ok', symbols: ['OMH'] });
    if (method === 'POST') return ok({ items: {}, rows: {} });
    if (url.includes('/short-interest/') || url.includes('/growth/')) return ok({ items: {}, tags: {} });
    if (url.includes('?symbols=')) return ok({ ...board(), rows: [] });
    return ok(board());
  }));
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const flush = async () => { for (let i = 0; i < 6; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); }); };
const tile = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;
const markBtn = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-broker-mark-${s}"]`) as HTMLButtonElement | null;
const fullGets = () => calls.filter((x) => x.method === 'GET' && x.url === `${API}${GGW_PATH}`);
const writes = () => calls.filter((x) => x.method === 'DELETE' || (x.method === 'POST' && x.url.endsWith(GG_BROKER_PATH)));

describe('🚫 the mark on the 👀 Watch board', { timeout: 30000 }, () => {
  beforeEach(() => {
    delStatus = 200;
    vi.useFakeTimers();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.style.overflow = ''; });

  it('every tile carries ONE 🚫, FIRST in its action group; lit only on the served row word', async () => {
    const c = await mount();
    for (const s of RAW.rows.map((r: any) => r.symbol)) {
      const acts = tile(c, s).querySelector('.ggw-actions') as HTMLElement;
      expect(acts.firstElementChild, s).toBe(markBtn(c, s));
      expect(acts.querySelectorAll('.ggw-broker-mark')).toHaveLength(1);
      expect(markBtn(c, s)!.getAttribute('aria-pressed'), s).toBe(s === 'OMH' ? 'true' : 'false');
      expect(markBtn(c, s)!.getAttribute('title')).toBe(BLOCK.title);
      expect(markBtn(c, s)!.textContent).toBe(BLOCK.toggle);
    }
    /* the board order on a tile: 🚫 ⤢ TV ↗ Yahoo ↗ ✕
     * WIDENED 2026-11-23 (+ ggw-tv before ggw-yahoo) — Ajay: "Also add traderview charts on charts please.. Yahoo has been
     * hard to configure" (question card: "TV ↗ button only"). */
    const kids = Array.from(tile(c, 'AMD').querySelector('.ggw-actions')!.children).map((e) => e.className);
    expect(kids).toEqual(['ggw-btn ggw-broker-mark', 'ggw-btn ggw-stretch-btn', 'ggw-btn ggw-tv', 'ggw-btn ggw-yahoo', 'ggw-btn ggw-remove']);
  });

  it('click 🚫 on his row → POST his 🚫 list {symbol} → DELETE the Watch name → ONE full re-GET; the served answer prints', async () => {
    const c = await mount();
    const before = fullGets().length;
    calls.length = 0;
    fireEvent.click(markBtn(c, 'AMD')!);
    await flush();
    expect(writes().map((x) => [x.method, x.url])).toEqual([
      ['POST', `${API}${GG_BROKER_PATH}`], ['DELETE', `${API}${ggwSymbolPath('AMD')}`],
    ]);
    expect(JSON.parse(writes()[0].body!)).toEqual({ symbol: 'AMD' });
    expect(fullGets()).toHaveLength(1);
    expect(before).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('ggw-msg').textContent).toBe(DEL_TEXT);
    expect(calls.filter((x) => x.method === 'DELETE' && x.url.includes(GG_BROKER_PATH))).toHaveLength(0);
  });

  it('a 🤖 tile → the same two writes (the same DELETE route as ✕)', async () => {
    const c = await mount();
    calls.length = 0;
    fireEvent.click(markBtn(c, 'XXII')!);
    await flush();
    expect(writes().map((x) => [x.method, x.url])).toEqual([
      ['POST', `${API}${GG_BROKER_PATH}`], ['DELETE', `${API}${ggwSymbolPath('XXII')}`],
    ]);
  });

  it('NEGATIVE [C6]: DELETE 500 → ggw-broker-err prints GGW_FETCH_FAILED; no served message', async () => {
    delStatus = 500;
    const c = await mount();
    fireEvent.click(markBtn(c, 'AMD')!);
    await flush();
    expect(screen.getByTestId('ggw-broker-err').textContent).toBe(GGW_FETCH_FAILED);
    expect(screen.queryByTestId('ggw-msg')).toBeNull();
  });

  it('the head prints the served kept-off / fault lines verbatim', async () => {
    await mount(() => boardWith({ ...BLOCK, auto_fault_text: '🚫 served auto fault line' }));
    expect(screen.getByTestId('ggw-broker-auto').textContent).toBe(BLOCK.auto_text);
    expect(screen.getByTestId('ggw-broker-auto-fault').textContent).toBe('🚫 served auto fault line');
    expect(screen.queryByTestId('ggw-broker-fault')).toBeNull();
  });

  it('NEGATIVE: a fault block (editable false) → the served fault line and NO button anywhere', async () => {
    const c = await mount(() => boardWith({ ...BLOCK, editable: false, fault_text: '🚫 served fault line', auto_text: null }));
    expect(screen.getByTestId('ggw-broker-fault').textContent).toBe('🚫 served fault line');
    expect(c.querySelector('.ggw-broker-mark')).toBeNull();
  });

  it('NEGATIVE: an older server (no block) → no button, no head line; the tile DOM equals the no-`actions` tile', async () => {
    const c = await mount(() => { const b = clone(RAW); delete b.broker; return b; });
    expect(c.querySelector('.ggw-broker-mark')).toBeNull();
    expect(c.querySelector('[data-testid^="ggw-broker-"]')).toBeNull();
    expect(tile(c, 'AMD').querySelector('.ggw-actions')!.firstElementChild!.className).toBe('ggw-btn ggw-stretch-btn');
  });

  it('NEGATIVE: no 🚫 inside the ⤢ stretch view', async () => {
    const c = await mount();
    fireEvent.click(screen.getByTestId('ggw-stretch-btn-OMH'));
    await flush();
    const st = screen.getByTestId('ggw-stretch');
    expect(st.querySelector('.ggw-broker-mark')).toBeNull();
    expect(markBtn(c, 'OMH')).not.toBeNull();
  });
});

describe('🚫 Tile `actions` [C11]', () => {
  afterEach(() => cleanup());
  const B = parseGgw(clone(RAW)) as GgwBoard;
  const row = B.rows.find((r) => r.symbol === 'AMD')!;
  const base = { row, phone: false, fit: false, removeLabel: 'Remove', focused: false, busy: false,
                 onRemove: () => {}, onStretch: () => {} };

  it('no `actions` → the same DOM as a null-rendering action (an older server through the board)', () => {
    const a = render(<Tile {...base} />).container.innerHTML;
    cleanup();
    const b = render(<Tile {...base} actions={<GgwBrokerButton row={row} block={null} busy={false} onMark={() => {}} />} />).container.innerHTML;
    expect(b).toBe(a);
    expect(a).not.toContain('ggw-broker-mark');
  });
  it('with `actions`: the 🚫 is the FIRST child of .ggw-actions; the sibling right before ✕ is ↗ — NEGATIVE: never beside ✕', () => {
    const { container } = render(<Tile {...base} actions={<GgwBrokerButton row={row} block={BLOCK} busy={false} onMark={() => {}} />} />);
    const acts = container.querySelector('.ggw-actions')!;
    expect(acts.firstElementChild!.className).toBe('ggw-btn ggw-broker-mark');
    const x = acts.querySelector('.ggw-remove')!;
    expect(x.previousElementSibling!.className).toBe('ggw-btn ggw-yahoo');
    expect(x.previousElementSibling!.classList.contains('ggw-broker-mark')).toBe(false);
    expect(x.nextElementSibling?.classList.contains('ggw-broker-mark') ?? false).toBe(false);
  });
  it('NEGATIVE: the ⤢ view (onUnstretch) never draws `actions`', () => {
    const { container } = render(<Tile {...base} onUnstretch={() => {}}
                                        actions={<GgwBrokerButton row={row} block={BLOCK} busy={false} onMark={() => {}} />} />);
    expect(container.querySelector('.ggw-broker-mark')).toBeNull();
  });
});

/* ── source + CSS guards ── */
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}

describe('🚫 source guards', () => {
  it('no FE file of the Watch types the broker name or its phrase — not even in a comment', () => {
    const files: Record<string, string> = {
      'GgwBrokerMark.tsx': markSrc, 'ggwBroker.ts': brokerLibSrc, 'GajjalaWatchBoard.tsx': boardSrc,
      'GajjalaWatchTile.tsx': tileSrc, 'GajjalaWatchTags.tsx': tagsSrc, 'gajjalaWatch.ts': watchLibSrc,
    };
    for (const [f, s] of Object.entries(files)) {
      expect(s.length, f).toBeGreaterThan(100);
      expect(s, f).not.toMatch(/fidelity/i);
      expect(s, f).not.toMatch(/not eligible/i);
    }
  });
  it('GgwBrokerMark never reads isOwner, never loads gajjala.css, never DELETEs on the broker route', () => {
    expect(markSrc).not.toMatch(/isOwner/);
    expect(markSrc).not.toMatch(/styles\/gajjala\.css/);
    expect(markSrc).not.toMatch(/\.css['"]/);
    const code = noComments(markSrc);
    expect(code).toMatch(/GG_BROKER_PATH\}`, \{\s*method: 'POST'/);
    expect(code.match(/GG_BROKER_PATH/g)).toHaveLength(2);            // the import + the ONE POST
    expect(code).not.toMatch(/GG_BROKER_PATH[^\n]*DELETE/);
  });
  it('the board mounts the button on its tiles only (never in GgwStretch) and keeps tags={tagsOf(r)} verbatim', () => {
    expect(boardSrc).toContain('tags={tagsOf(r)}');
    expect(boardSrc.match(/<GgwBrokerButton /g)).toHaveLength(1);
    expect(boardSrc.match(/useGgwBrokerMark\(/g)).toHaveLength(1);
    const stretch = boardSrc.slice(boardSrc.indexOf('<GgwStretch '));
    expect(stretch.slice(0, stretch.indexOf('/>'))).not.toContain('actions=');
  });
  it('GajjalaBoard.tsx untouched: no Watch mark in it; its own BrokerToggle stays put', () => {
    expect(ggBoardSrc).not.toMatch(/GgwBroker|ggw-broker-mark|ggwBroker/);
    expect(ggBoardSrc).toContain('\nfunction BrokerToggle(');
  });
});

/* vitest serves a .css ?raw import empty (css off) — the sheet is read from disk, the tags test's way */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
describe('🚫 CSS [C3]', () => {
  let watchCss = '';
  beforeAll(async () => { watchCss = await readSource('src/styles/gajjalaWatch.css'); });
  it('scoped .ggw-broker-mark: 0.35 / pressed 1 / disabled 0.5 / pressed+disabled 0.6', () => {
    expect(rule(watchCss, '.ggw-broker-mark')).toMatch(/opacity:\s*0\.35/);
    expect(rule(watchCss, '.ggw-broker-mark[aria-pressed="true"]')).toMatch(/opacity:\s*1\b/);
    expect(rule(watchCss, '.ggw-broker-mark:disabled')).toMatch(/opacity:\s*0\.5/);
    expect(rule(watchCss, '.ggw-broker-mark[aria-pressed="true"]:disabled')).toMatch(/opacity:\s*0\.6/);
  });
  it('NEGATIVE: no unscoped copy of the 🚩 toggle in the Watch sheet', () => {
    expect(watchCss.length).toBeGreaterThan(1000);
    expect(watchCss).not.toMatch(/\.gg-broker-toggle/);
  });
});
