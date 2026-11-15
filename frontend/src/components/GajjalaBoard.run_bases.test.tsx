import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import gg1 from './__fixtures__/gajjala_1m_board_2026_10_27.json';
import onOpen from './__fixtures__/gajjala_on_open_golden_2026_10_15.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import { ggRunBasesLine } from '../lib/gajjala';

/* 📶 GG's base count on Gajjala's cards and the 🏁 Track record, through the REAL GajjalaBoard (2026-11-15, WP-C fe-card).
 *
 * Ajay 2026-11-15: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need that
 * tracked in to Gajjala's".
 *
 * The server serves `gajjala.run_bases` (run_bases.card_block — GG verified rule E6; the definition is Cheetah's;
 * UNMEASURED, information only) and, on a 🏁 row, `base_text` (ledger BASE_TEXT / BASE_FORMING_TEXT). The FE prints both
 * VERBATIM — the strings below are test data shaped like the served words, never typed by the FE. Boards = DEEP COPIES of
 * the existing goldens (the 5-min on-open bull_flag board, the 1-minute 🧠 board, the 🏁 5d board) with the block added.
 * NEGATIVES: absent / null / blank text → no line; a stale `counter_text` is never printed; no `base_text` → no chip;
 * the rendered text === the served text (the FE adds no word); the line is never in a red tone class. */

vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const POT1M: any = (gg1 as any).boards.potential;
const BF5: any = (onOpen as any).boards.bull_flag;
const TR5D: any = (trGolden as any).boards['5d'];

/* Served-shaped test data (the backend pins the real words). */
const CLIMAX = {
  n: 3, state: 'broke', frame: '5m',
  text: '📶 3rd base — climax run, GG peels early · broke out 11:05 ET · 5-min bars',
  title: 'GG S8 40:54: “first base, second base, third base, this is a climax run” — served title test data',
};
const FORMING = {
  n: 1, state: 'forming', frame: '5m',
  text: '📶 2nd base · forming since 10:40 ET · 5-min bars',
  title: 'served forming title',
};

function withBases(src: any, blocks: Record<string, any>): any {
  const b = clone(src);
  b.session = { ...(b.session || {}), refresh_sec: 0 };
  b.tiles = (b.tiles || []).map((t: any) => {
    if (!t.gajjala || !(t.symbol in blocks)) return t;
    const g = { ...t.gajjala };
    if (blocks[t.symbol] === undefined) delete g.run_bases; else g.run_bases = clone(blocks[t.symbol]);
    return { ...t, gajjala: g };
  });
  return b;
}

let board: () => any = () => ({});
function stub() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/entry-tape')) return ok({ id: 'x', bars: [], rules: [], lite: true });
    if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(board());
    if (u.pathname.endsWith('/supply-demand/rules')) return ok({ sections: {} });
    return ok({});
  }));
}
const mount1m = () => render(
  <MemoryRouter initialEntries={['/chart-maps?tab=gajjala_1m&sub=potential']}>
    <GajjalaBoard variant="gajjala_1m" />
  </MemoryRouter>);
const mount5 = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
const loaded = async (c: HTMLElement) =>
  waitFor(() => expect(c.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const lineOf = (c: HTMLElement, sym: string) =>
  c.querySelector(`[data-testid="gg-run-bases-${sym}"]`) as HTMLElement | null;

beforeEach(() => { board = () => ({}); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('ggRunBasesLine', () => {
  it('serves the text and the title, both trimmed', () => {
    expect(ggRunBasesLine({ text: ' 📶 1st base ', title: ' t ' })).toEqual({ text: '📶 1st base', title: 't' });
    expect(ggRunBasesLine(CLIMAX)).toEqual({ text: CLIMAX.text, title: CLIMAX.title });
  });
  it('a missing / blank / non-string title → "" (no hover), the line still prints', () => {
    expect(ggRunBasesLine({ text: 'x' })).toEqual({ text: 'x', title: '' });
    expect(ggRunBasesLine({ text: 'x', title: '  ' })).toEqual({ text: 'x', title: '' });
    expect(ggRunBasesLine({ text: 'x', title: 5 as any })).toEqual({ text: 'x', title: '' });
  });
  it('NEGATIVE: no block, no text, a blank or non-string text → null', () => {
    expect(ggRunBasesLine(null)).toBeNull();
    expect(ggRunBasesLine(undefined)).toBeNull();
    expect(ggRunBasesLine({ n: 2, state: 'broke' })).toBeNull();
    expect(ggRunBasesLine({ text: '   ', title: 'x' })).toBeNull();
    expect(ggRunBasesLine({ text: null })).toBeNull();
    expect(ggRunBasesLine({ text: 3 as any })).toBeNull();
  });
  it('NEGATIVE: a stale served counter_text is ignored (no counter line in v1)', () => {
    const r = ggRunBasesLine({ ...CLIMAX, counter_text: 'GG counter words' } as any);
    expect(r).toEqual({ text: CLIMAX.text, title: CLIMAX.title });
    expect(JSON.stringify(r)).not.toContain('counter');
  });
});

describe('📶 the card line on the real 5-min board (🚩 bull_flag)', () => {
  const sym = (BF5.tiles || []).find((t: any) => t.gajjala)?.symbol as string;

  it('prints the SERVED text verbatim with the served title, inside the card extras, muted (no tone class)', async () => {
    expect(sym).toBeTruthy();
    board = () => withBases(BF5, { [sym]: CLIMAX });
    stub();
    const { container } = mount5('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const el = lineOf(container, sym)!;
    expect(el).not.toBeNull();
    expect(el.textContent).toBe(CLIMAX.text);
    expect(el.getAttribute('title')).toBe(CLIMAX.title);
    expect(el.className).toBe('cm-note gg-line gg-run-bases');
    expect(el.closest('[data-testid="gg-extras"]')).not.toBeNull();
    expect(container.querySelectorAll('.gg-run-bases').length).toBe(1);
  });

  it('NEGATIVE: the line never carries a red / tone class and adds no word of its own', async () => {
    board = () => withBases(BF5, { [sym]: CLIMAX });
    stub();
    const { container } = mount5('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const el = lineOf(container, sym)!;
    expect(el.className).not.toMatch(/down|neg|red|loss|exit|tone/);
    expect(el.childNodes.length).toBe(1);
    expect(el.innerHTML).toBe(CLIMAX.text);
  });

  it('NEGATIVE: a stale counter_text is NOT printed anywhere on the card', async () => {
    board = () => withBases(BF5, { [sym]: { ...CLIMAX, counter_text: 'COUNTER-WORDS-STALE' } });
    stub();
    const { container } = mount5('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(lineOf(container, sym)!.textContent).toBe(CLIMAX.text);
    expect(container.textContent || '').not.toContain('COUNTER-WORDS-STALE');
  });

  it('NEGATIVE: the golden as served (no run_bases) → no line anywhere', async () => {
    board = () => withBases(BF5, {});
    stub();
    const { container } = mount5('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(container.querySelector('.gg-run-bases')).toBeNull();
    expect(container.textContent || '').not.toContain('📶');
  });

  for (const [name, blk] of [['null', null], ['blank text', { ...CLIMAX, text: '   ' }],
    ['no text', { n: 2, state: 'broke', title: 'only a title' }]] as [string, any][]) {
    it(`NEGATIVE: a ${name} block → no line, and the title is never printed as text`, async () => {
      board = () => withBases(BF5, { [sym]: blk });
      stub();
      const { container } = mount5('tab=gajjala&sub=bull_flag');
      await loaded(container);
      expect(lineOf(container, sym)).toBeNull();
      expect(container.textContent || '').not.toContain('only a title');
    });
  }
});

describe('📶 the card line on the real 1-minute board (🧠 sub)', () => {
  const syms = (POT1M.tiles || []).filter((t: any) => t.gajjala).map((t: any) => t.symbol as string);

  it('each card prints ITS served line; a card without a block prints none', async () => {
    expect(syms.length).toBeGreaterThan(1);
    const [a, b] = syms;
    board = () => withBases(POT1M, { [a]: CLIMAX, [b]: FORMING });
    stub();
    const { container } = mount1m();
    await loaded(container);
    expect(lineOf(container, a)!.textContent).toBe(CLIMAX.text);
    expect(lineOf(container, b)!.textContent).toBe(FORMING.text);
    expect(lineOf(container, b)!.getAttribute('title')).toBe(FORMING.title);
    for (const s of syms.slice(2)) expect(lineOf(container, s)).toBeNull();
  });

  it('a missing title → the line prints with no title attribute', async () => {
    const [a] = syms;
    board = () => withBases(POT1M, { [a]: { ...FORMING, title: null } });
    stub();
    const { container } = mount1m();
    await loaded(container);
    const el = lineOf(container, a)!;
    expect(el.textContent).toBe(FORMING.text);
    expect(el.hasAttribute('title')).toBe(false);
  });
});

describe('📶 the 🏁 Track record base chip', () => {
  const rows = (TR5D.track_record.days || []).flatMap((d: any) => d.rows || []);
  const [r1, r2, r3] = rows;

  function withChips(texts: Record<string, any>): any {
    const b = clone(TR5D);
    for (const d of b.track_record.days || []) {
      d.rows = (d.rows || []).map((r: any) => (r.key in texts ? { ...r, base_text: texts[r.key] } : r));
    }
    return b;
  }

  it('prints both served texts verbatim in the kind cell, after the thin chip slot', async () => {
    expect(rows.length).toBeGreaterThan(2);
    board = () => withChips({ [r1.key]: '📶 base 3', [r2.key]: '📶 base 2 forming' });
    stub();
    const { container } = mount5('tab=gajjala&sub=track_record');
    await loaded(container);
    const c1 = container.querySelector(`[data-testid="gg-tr-base-${r1.key}"]`) as HTMLElement;
    const c2 = container.querySelector(`[data-testid="gg-tr-base-${r2.key}"]`) as HTMLElement;
    expect(c1).not.toBeNull();
    expect(c2).not.toBeNull();
    expect(c1.textContent).toBe('📶 base 3');
    expect(c2.textContent).toBe('📶 base 2 forming');
    expect(c1.className).toBe('gg-tr-chip gg-tr-base');
    const cell = c1.closest('td')!;
    expect(cell.querySelector('.gg-tr-kind')).not.toBeNull();
    expect(cell.lastElementChild).toBe(c1);
  });

  it('NEGATIVE: no base_text / null / blank → no chip; the golden as served carries none', async () => {
    board = () => withChips({ [r1.key]: null, [r2.key]: '   ' });
    stub();
    const { container } = mount5('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(container.querySelector(`[data-testid="gg-tr-base-${r1.key}"]`)).toBeNull();
    expect(container.querySelector(`[data-testid="gg-tr-base-${r2.key}"]`)).toBeNull();
    expect(container.querySelector(`[data-testid="gg-tr-base-${r3.key}"]`)).toBeNull();
    expect(container.querySelector('.gg-tr-base')).toBeNull();
    expect(container.textContent || '').not.toContain('📶');
  });
});

describe('📱 430 px — the line wraps (source guard: jsdom has no layout)', () => {
  async function css(): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/styles/gajjala.css`, 'utf8');
  }
  it('.gg-line (which the line carries) wraps anywhere, and .gg-run-bases sets min-width: 0', async () => {
    const src = await css();
    const wrap = src.match(/\n([^{}\n]*\.gg-line\b[^{}\n]*)\{([^}]*overflow-wrap:\s*anywhere[^}]*)\}/);
    expect(wrap).not.toBeNull();
    const rule = src.match(/\n\.gg-run-bases\s*\{([^}]*)\}/);
    expect(rule).not.toBeNull();
    expect(rule![1]).toMatch(/min-width:\s*0\b/);
  });
  it('NEGATIVE: the .gg-run-bases rule names no red / negative colour (one muted tone for every count)', async () => {
    const rule = (await css()).match(/\n\.gg-run-bases\s*\{([^}]*)\}/)![1];
    expect(rule).not.toMatch(/negative|#dc2626|#ef4444|red/i);
    expect((await css())).not.toMatch(/\.gg-run-bases-\w+/);
  });
});
