import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';
import {
  GG_KISS_FILTER_LS, ggKissFilterBlock, ggKissFilterLine, ggKissFilterSplit, loadGgKissFilter, saveGgKissFilter,
  type GgBoard,
} from '../lib/gajjala';

/* 💋 EMA Kiss & Fly — relative volume order + the "lifting off the 9 EMA" toggle (2026-11-11, kiss rvol spec WP-FE +
 * addendum FE). Ajay 2026-11-11: "Sort by relative volume, and closer to the EMA." and "This filter is needed for EMA
 * Kiss atleast". The server orders the 💋 cards (state › rel volume › 9 EMA distance › volume › float), serves the
 * order word (`order_note`), the mixed-board line (`list_note`), the "Rel volume" stat, the per-card `kiss_now` flag and
 * the `kiss_filter` words. The board prints them verbatim, reorders nothing and types no word. Every board here is a
 * CLONE of the frozen hand fixture (its 🚩 bull_flag board re-keyed to the 💋 sub); every served word is a CLONE value. */

const BASE: any = (fixture as any).boards.bull_flag;
const ORDER = '\u{1F48B} served order word clone · then highest relative volume · then closest to the 9 EMA';
const LIST = '\u{1F48B} 1 of 4 served list note clone';
const LABEL = '\u{1F48B} served toggle label clone';
const HINT = 'served toggle hint clone';
const TPL = '{shown} shown · {hidden} hidden (served clone) · {unknown} unknown kept';
const BLOCK = { label: LABEL, hint: HINT, hidden_text_template: TPL };

type T = { sym: string; state?: string; rv?: string | null; kiss?: boolean | null | 'absent'; broker?: string; focus?: boolean };

function tile(spec: T, i: number): any {
  const t = JSON.parse(JSON.stringify(BASE.tiles[i % BASE.tiles.length]));
  t.symbol = spec.sym;
  t.href = `/stock/${spec.sym}`;
  t.gajjala = { ...t.gajjala, setup: 'kiss_fly', state: spec.state ?? t.gajjala.state };
  t.stats = [{ k: 'Change', v: '+48.2%' }, { k: 'Volume', v: '3.1M' }];
  if (spec.rv) t.stats.splice(2, 0, { k: 'Rel volume', v: spec.rv });
  if (spec.kiss !== 'absent') t.kiss_now = spec.kiss ?? null;
  if (spec.broker) t.broker_text = spec.broker;
  if (spec.focus) t.focus = true;
  return t;
}

function kissBoard(tiles: T[], patch: Record<string, unknown> = {}): any {
  return {
    ...JSON.parse(JSON.stringify(BASE)), sub: 'kiss_fly', order_note: ORDER, list_note: null,
    tiles: tiles.map(tile), kiss_filter: BLOCK, ...patch,
  };
}

const FOUR: T[] = [
  { sym: 'AAA', state: 'aplus', rv: '0.40×', kiss: true },
  { sym: 'BBB', state: 'forming', rv: '9.10×', kiss: false },
  { sym: 'CCC', state: 'forming', rv: null, kiss: null },
  { sym: 'DDD', state: 'forming', rv: '1.20×', kiss: false },
];

function stub(payload: any) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (String(url).includes('/chart-maps/gajjala')
    ? { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(payload)) }
    : { ok: true, status: 200, json: async () => ({}) })));
}

async function mount(payload: any, opts: { sub?: string; variant?: 'gajjala' | 'gajjala_1m' | 'gajjala_audited' } = {}) {
  stub(payload);
  const sub = opts.sub ?? 'kiss_fly';
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${sub}`]}>
      {opts.variant ? <GajjalaBoard variant={opts.variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  return r;
}

const order = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="gg-tile-"]')]
  .map((el) => el.getAttribute('data-testid') || '')
  .filter((id) => /^gg-tile-[A-Z]+$/.test(id))
  .map((id) => id.replace('gg-tile-', ''));

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
/** The source with block and line comments removed (a quoted `//` inside a URL string is not in this file's code). */
const stripComments = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');

/** An in-memory store (the emaFrames.test precedent — this jsdom build has no usable localStorage). */
function mem() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear() };
}
beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('💋 served order words + Rel volume stat — printed verbatim, never reordered', () => {
  it('prints the served 💋 order_note and list_note verbatim', async () => {
    const { unmount } = await mount(kissBoard(FOUR, { list_note: LIST }));
    expect(screen.getByTestId('gg-order-note').textContent).toBe(ORDER);
    expect(screen.getByTestId('gg-list-note').textContent).toBe(LIST);
    unmount();
  });

  it('NEGATIVE: no list_note line when the server serves null (an all-known or all-unknown board)', async () => {
    const { unmount } = await mount(kissBoard(FOUR));
    expect(screen.queryByTestId('gg-list-note')).toBeNull();
    unmount();
  });

  it('draws the cards in the SERVED order — a reversed rel volume is not re-sorted by the FE', async () => {
    const rev: T[] = [
      { sym: 'LOW', state: 'forming', rv: '0.20×', kiss: true },
      { sym: 'MID', state: 'forming', rv: '2.00×', kiss: true },
      { sym: 'TOP', state: 'forming', rv: '50.00×', kiss: true },
    ];
    const { container, unmount } = await mount(kissBoard(rev));
    expect(order(container)).toEqual(['LOW', 'MID', 'TOP']);
    unmount();
  });

  it('the Rel volume stat prints the served v on its card', async () => {
    const { unmount } = await mount(kissBoard(FOUR));
    const card = screen.getByTestId('gg-tile-BBB');
    expect(card.textContent).toContain('Rel volume');
    expect(card.textContent).toContain('9.10×');
    unmount();
  });

  it('NEGATIVE: a card without the served stat prints no "Rel volume"', async () => {
    const { unmount } = await mount(kissBoard(FOUR));
    expect(screen.getByTestId('gg-tile-CCC').textContent).not.toContain('Rel volume');
    unmount();
  });

  it('NEGATIVE: GajjalaBoard.tsx types none of the served words in code (comments excluded)', async () => {
    const code = stripComments(await readSource('src/components/GajjalaBoard.tsx')).toLowerCase();
    /* `bounc` is not scanned here: internal identifiers keep it (useBounceRoom); the RENDERED check is below. */
    for (const w of ['relative volume', 'rel volume', 'lifting off', 'not at the 9 ema', 'unknown kept']) {
      expect(code).not.toContain(w);
    }
  });

  it('NEGATIVE: the comment stripper is real — the raw source does carry his words in a comment', async () => {
    const raw = (await readSource('src/components/GajjalaBoard.tsx')).toLowerCase();
    expect(raw).toContain('this filter is needed for ema kiss atleast');
    expect(stripComments(raw)).not.toContain('this filter is needed for ema kiss atleast');
  });
});

describe('💋 "lifting off the 9 EMA" toggle — default OFF, hides only kiss_now === false', () => {
  it('shows the served label + hint; default OFF hides nothing and prints no count line', async () => {
    const { container, unmount } = await mount(kissBoard(FOUR));
    const btn = screen.getByTestId('gg-kiss-filter-btn');
    expect(btn.textContent).toBe(LABEL);
    expect(btn.getAttribute('title')).toBe(HINT);
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    expect(screen.queryByTestId('gg-kiss-filter-line')).toBeNull();
    unmount();
  });

  it('ON hides the false cards, keeps true + null in the served order, prints the served line with the counts', async () => {
    const { container, unmount } = await mount(kissBoard(FOUR));
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(screen.getByTestId('gg-kiss-filter-btn').getAttribute('aria-pressed')).toBe('true');
    expect(order(container)).toEqual(['AAA', 'CCC']);
    expect(screen.getByTestId('gg-kiss-filter-line').textContent)
      .toBe('2 shown · 2 hidden (served clone) · 1 unknown kept');
    expect((container.textContent || '').toLowerCase()).not.toContain('bounc');
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    expect(screen.queryByTestId('gg-kiss-filter-line')).toBeNull();
    unmount();
  });

  it('NEGATIVE: null and absent kiss_now are never hidden (unknown is not false)', async () => {
    const t: T[] = [
      { sym: 'NUL', state: 'forming', kiss: null },
      { sym: 'ABS', state: 'forming', kiss: 'absent' },
      { sym: 'OFF', state: 'forming', kiss: false },
    ];
    const { container, unmount } = await mount(kissBoard(t));
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(order(container)).toEqual(['NUL', 'ABS']);
    expect(screen.getByTestId('gg-kiss-filter-line').textContent)
      .toBe('2 shown · 1 hidden (served clone) · 2 unknown kept');
    unmount();
  });

  it('the line still prints when nothing is hidden (M = 0)', async () => {
    const t: T[] = [{ sym: 'AAA', state: 'aplus', kiss: true }, { sym: 'BBB', state: 'forming', kiss: true }];
    const { unmount } = await mount(kissBoard(t));
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(screen.getByTestId('gg-kiss-filter-line').textContent)
      .toBe('2 shown · 0 hidden (served clone) · 0 unknown kept');
    unmount();
  });

  it('🚫 names keep their bottom place while ON (order kept, nothing moved up)', async () => {
    const t: T[] = [
      { sym: 'AAA', state: 'forming', kiss: true },
      { sym: 'BBB', state: 'forming', kiss: false },
      { sym: 'ZZZ', state: 'aplus', kiss: true, broker: 'served broker tag clone' },
    ];
    const { container, unmount } = await mount(kissBoard(t));
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(order(container)).toEqual(['AAA', 'ZZZ']);
    unmount();
  });

  it('the 🔝 divider follows the last focus card still drawn when a focus card is hidden', async () => {
    const t: T[] = [
      { sym: 'AAA', state: 'forming', kiss: true, focus: true },
      { sym: 'BBB', state: 'forming', kiss: false, focus: true },
      { sym: 'CCC', state: 'forming', kiss: true },
    ];
    const { container, unmount } = await mount(kissBoard(t, { focus: { n: 2, text: 'served focus clone' } }));
    const after = () => container.querySelector('[data-testid="gg-focus-divider"]')?.previousElementSibling
      ?.getAttribute('data-testid');
    expect(after()).toBe('gg-tile-BBB');
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(after()).toBe('gg-tile-AAA');
    unmount();
  });

  it('ON is remembered per viewer: the click writes the store; a mount with the store set starts ON', async () => {
    const a = await mount(kissBoard(FOUR));
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(window.localStorage.getItem(GG_KISS_FILTER_LS)).toBe('1');
    a.unmount();
    const b = await mount(kissBoard(FOUR));
    expect(screen.getByTestId('gg-kiss-filter-btn').getAttribute('aria-pressed')).toBe('true');
    expect(order(b.container)).toEqual(['AAA', 'CCC']);
    b.unmount();
  });

  it('NEGATIVE: a store that throws on read and write does not crash — OFF, and the click still works', async () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); },
    });
    const { container, unmount } = await mount(kissBoard(FOUR));
    expect(screen.getByTestId('gg-kiss-filter-btn').getAttribute('aria-pressed')).toBe('false');
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    act(() => { fireEvent.click(screen.getByTestId('gg-kiss-filter-btn')); });
    expect(order(container)).toEqual(['AAA', 'CCC']);
    unmount();
  });
});

describe('💋 toggle — NEGATIVES: absent wherever the block is not served', () => {
  it('NEGATIVE: a 💋 board without kiss_filter renders no toggle and hides nothing, even with the store ON', async () => {
    window.localStorage.setItem(GG_KISS_FILTER_LS, '1');
    const { container, unmount } = await mount(kissBoard(FOUR, { kiss_filter: undefined }));
    expect(screen.queryByTestId('gg-kiss-filter')).toBeNull();
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    unmount();
  });

  it('NEGATIVE: a blank served label → no toggle', async () => {
    const { unmount } = await mount(kissBoard(FOUR, { kiss_filter: { ...BLOCK, label: '  ' } }));
    expect(screen.queryByTestId('gg-kiss-filter')).toBeNull();
    unmount();
  });

  it('NEGATIVE: another sub never shows the toggle or hides a card, even if a block rides its payload', async () => {
    window.localStorage.setItem(GG_KISS_FILTER_LS, '1');
    const flag = { ...kissBoard(FOUR), sub: 'bull_flag' };
    const { container, unmount } = await mount(flag, { sub: 'bull_flag' });
    expect(screen.queryByTestId('gg-kiss-filter')).toBeNull();
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    unmount();
  });

  for (const variant of ['gajjala_1m', 'gajjala_audited'] as const) {
    it(`NEGATIVE: the ${variant} page without the block shows no toggle; with the block served it does`, async () => {
      const tab = variant;
      const a = await mount({ ...kissBoard(FOUR, { kiss_filter: null }), tab }, { variant });
      expect(screen.queryByTestId('gg-kiss-filter')).toBeNull();
      a.unmount();
      const b = await mount({ ...kissBoard(FOUR), tab }, { variant });
      expect(screen.getByTestId('gg-kiss-filter-btn').textContent).toBe(LABEL);
      b.unmount();
    });
  }

  it('NEGATIVE: a missing template → the chip still toggles but the FE prints no line of its own', async () => {
    const { container, unmount } = await mount(kissBoard(FOUR, { kiss_filter: { label: LABEL } }));
    fireEvent.click(screen.getByTestId('gg-kiss-filter-btn'));
    expect(order(container)).toEqual(['AAA', 'CCC']);
    expect(screen.queryByTestId('gg-kiss-filter-line')).toBeNull();
    unmount();
  });
});

describe('💋 lib helpers (pure)', () => {
  const b = (patch: Partial<GgBoard>) => ({ ...kissBoard(FOUR), ...patch }) as GgBoard;

  it('ggKissFilterBlock: the 💋 sub + a served label only', () => {
    expect(ggKissFilterBlock(b({}), 'kiss_fly')).toEqual(BLOCK);
    expect(ggKissFilterBlock(b({}), 'bull_flag')).toBeNull();
    expect(ggKissFilterBlock(b({}), 'potential')).toBeNull();
    expect(ggKissFilterBlock(b({ kiss_filter: null }), 'kiss_fly')).toBeNull();
    expect(ggKissFilterBlock(null, 'kiss_fly')).toBeNull();
  });

  it('ggKissFilterSplit: OFF keeps all (a copy); ON drops === false only, order kept', () => {
    const ts = [{ kiss_now: true, s: 1 }, { kiss_now: false, s: 2 }, { kiss_now: null, s: 3 }, { s: 4 }];
    const off = ggKissFilterSplit(ts, false);
    expect(off.visible.map((t) => t.s)).toEqual([1, 2, 3, 4]);
    expect(off.visible).not.toBe(ts);
    expect([off.shown, off.hidden, off.unknown]).toEqual([4, 0, 2]);
    const on = ggKissFilterSplit(ts, true);
    expect(on.visible.map((t) => t.s)).toEqual([1, 3, 4]);
    expect([on.shown, on.hidden, on.unknown]).toEqual([3, 1, 2]);
    expect(ggKissFilterSplit([], true)).toEqual({ visible: [], shown: 0, hidden: 0, unknown: 0 });
  });

  it('ggKissFilterLine: fills every placeholder; NEGATIVE: blank / absent template → null', () => {
    expect(ggKissFilterLine({ hidden_text_template: '{shown}/{shown} {hidden} {unknown}' }, { shown: 3, hidden: 1, unknown: 0 }))
      .toBe('3/3 1 0');
    expect(ggKissFilterLine({ hidden_text_template: '  ' }, { shown: 1, hidden: 0, unknown: 0 })).toBeNull();
    expect(ggKissFilterLine({}, { shown: 1, hidden: 0, unknown: 0 })).toBeNull();
    expect(ggKissFilterLine(null, { shown: 1, hidden: 0, unknown: 0 })).toBeNull();
  });

  it('load / save round-trip; NEGATIVE: a junk stored value reads OFF', () => {
    expect(loadGgKissFilter()).toBe(false);
    saveGgKissFilter(true);
    expect(loadGgKissFilter()).toBe(true);
    saveGgKissFilter(false);
    expect(loadGgKissFilter()).toBe(false);
    window.localStorage.setItem(GG_KISS_FILTER_LS, 'true');
    expect(loadGgKissFilter()).toBe(false);
  });
});

describe('📱 💋 toggle at 430 px — the chip row wraps and never sets the board minimum (stylesheet source guard)', () => {
  const rule = (src: string, sel: string) => {
    const m = src.match(new RegExp(`(^|\\n)\\s*${sel.replace(/\./g, '\\.')}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  const PRE = '.gg-kiss-filter { display: flex; }\n.gg-kiss-filter-btn { white-space: nowrap; }';

  it('.gg-kiss-filter wraps with min-width: 0; the chip is white-space: normal, min-width: 0', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const row = rule(css, '.gg-kiss-filter');
    const btn = rule(css, '.gg-kiss-filter-btn');
    expect(row).toMatch(/flex-wrap:\s*wrap/);
    expect(row).toMatch(/min-width:\s*0\b/);
    expect(btn).toMatch(/min-width:\s*0\b/);
    expect(btn).toMatch(/white-space:\s*normal/);
  });

  it('NEGATIVE: a no-wrap stylesheet fails the same matchers', () => {
    expect(rule(PRE, '.gg-kiss-filter')).not.toMatch(/flex-wrap:\s*wrap/);
    expect(rule(PRE, '.gg-kiss-filter')).not.toMatch(/min-width:\s*0\b/);
    expect(rule(PRE, '.gg-kiss-filter-btn')).not.toMatch(/white-space:\s*normal/);
  });
});
