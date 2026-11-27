/* 📅 GgwRunRoster on the phone (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster). Ajay: "Ok then add them to our watch
 * list and track them please..". The served roster is `folded_default`: on the phone it is ONE header line until he taps
 * it (remembered beside `ggw.opened`), and a board refresh never unfolds it. 430 px: no fixed width, every row wraps,
 * the record tables scroll inside their own box. NEGATIVES throughout. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import gold from '../lib/__fixtures__/ggwRunRoster.golden.json';
import GgwRunRoster from './GgwRunRoster';
import { GGW_OPENED_KEY } from '../lib/gajjalaWatch';
import { GGW_RUNROSTER_OPEN_KEY, GGW_RUNTRACK_PATH, parseRunRoster, type GgwRunRoster as Block } from '../lib/ggwRunRoster';

const G = gold as any;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const block = (o: Record<string, unknown> = {}): Block => parseRunRoster({ ...clone(G.runners), ...o }) as Block;
let store: Map<string, string>;
function memStorage(): Storage {
  store = new Map<string, string>();
  const m = store;
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
let urls: string[] = [];
beforeEach(() => {
  urls = [];
  vi.stubGlobal('localStorage', memStorage());
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    urls.push(String(u));
    return { ok: true, json: async () => (String(u).includes(GGW_RUNTRACK_PATH) ? G.track_all : {}) } as unknown as Response;
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const rows = () => document.querySelectorAll('[data-testid^="ggw-rr-row-"]').length;
const view = (b: Block) => <GgwRunRoster block={b} phone onChanged={() => {}} />;

describe('📱 the roster folds on the phone', () => {
  it('folded until tapped: one header button with the served text, no rows, no hint visible', () => {
    render(view(block()));
    const head = screen.getByTestId('ggw-rr-head');
    expect(head.tagName).toBe('BUTTON');
    expect(head.getAttribute('aria-expanded')).toBe('false');
    expect(head.textContent).toContain(G.runners.text);
    expect(rows()).toBe(0);
    expect(screen.getByTestId('ggw-rr').getAttribute('data-folded')).toBe('true');
    expect((screen.getByTestId('ggw-rr-info') as HTMLDetailsElement).open).toBe(false);
  });
  it('opens on tap — every row (no fold_at cut on the phone) — and remembers it beside ggw.opened', () => {
    render(view(block()));
    fireEvent.click(screen.getByTestId('ggw-rr-head'));
    expect(rows()).toBe(G.runners.rows.length);
    expect(screen.queryByTestId('ggw-rr-more')).toBeNull();
    expect(store.get(GGW_RUNROSTER_OPEN_KEY)).toBe('1');
    expect(store.has(GGW_OPENED_KEY)).toBe(false);
    fireEvent.click(screen.getByTestId('ggw-rr-head'));
    expect(rows()).toBe(0);
    expect(store.has(GGW_RUNROSTER_OPEN_KEY)).toBe(false);
  });
  it('NEGATIVE: stays folded on refresh (a newer served roster does not unfold it)', () => {
    const { rerender } = render(view(block()));
    rerender(view(block({ text: '📅 Runners · 10' })));
    expect(rows()).toBe(0);
    expect(screen.getByTestId('ggw-rr-head').textContent).toContain('📅 Runners · 10');
  });
  it('a remembered open opens on the next visit; junk in the key → folded', () => {
    localStorage.setItem(GGW_RUNROSTER_OPEN_KEY, '1');
    const a = render(view(block()));
    expect(rows()).toBe(G.runners.rows.length);
    a.unmount();
    localStorage.setItem(GGW_RUNROSTER_OPEN_KEY, 'yes');
    render(view(block()));
    expect(rows()).toBe(0);
  });
  it('NEGATIVE: a roster served WITHOUT folded_default is open on the phone', () => {
    render(view(block({ folded_default: false })));
    expect(rows()).toBe(G.runners.rows.length);
  });
  it('NEGATIVE: folded → no track fetch at all', async () => {
    render(view(block()));
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
    expect(urls.filter((u) => u.includes(GGW_RUNTRACK_PATH))).toEqual([]);
  });
});

describe('📱 430 px', () => {
  it('rows wrap with min-width 0, the tables scroll in their own box, no fixed width anywhere in the roster CSS', async () => {
    const css = await readSource('src/styles/ggwRunRoster.css');
    const rule = (sel: string) => new RegExp(`\\n${sel.replace(/[.>]/g, (m) => `\\${m}`)} \\{([^}]*)\\}`).exec(css)?.[1] || '';
    for (const sel of ['.ggw-rr', '.ggw-rr-headline', '.ggw-rr-row']) {
      expect(rule(sel), sel).toMatch(/min-width: 0/);
    }
    expect(rule('.ggw-rr-row')).toMatch(/flex-wrap: wrap/);
    expect(rule('.ggw-rr-headline')).toMatch(/flex-wrap: wrap/);
    expect(rule('.ggw-rr-scroll')).toMatch(/overflow-x: auto/);
    expect(rule('.ggw-rr-scroll')).toMatch(/max-width: 100%/);
    expect(rule('.ggw-rr')).toMatch(/max-width: 100%/);
    const body = css.replace(/\/\*[\s\S]*?\*\//g, '');
    expect(body).not.toMatch(/(^|[;{\s])(min-)?width:\s*[1-9][\d.]*(px|rem|em|ch)/);
    expect(body).not.toMatch(/nowrap/);
  });
  it('the opened record table sits inside .ggw-rr-scroll (never the page)', async () => {
    render(view(block({ folded_default: false })));
    const det = screen.getByTestId('ggw-rr-info') as HTMLDetailsElement;
    await act(async () => { det.open = true; fireEvent(det, new Event('toggle')); });
    for (let i = 0; i < 4; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
    const t = screen.getByTestId('ggw-rr-track-table');
    expect(t.parentElement!.className).toBe('ggw-rr-scroll');
  });
});
