/* 🩳 Short interest column on the 📋 All strategies table (2026-11-16, spec §3.4 WP-B, V1–V8).
 *
 * Ajay 2026-11-16 (screenshot of this table): "Add a short interest colume fo this table when available".
 *
 * The block below is HAND-MADE test data shaped like backend chart_maps/gajjala/all_table.block §3.3 (never a golden).
 * The FE prints the served si_text verbatim in the `si` cell with the served si_title on hover, the served head hover, a
 * class hook when si_stale === true, and the served si_fault_text under the fault line. NEGATIVES: a missing record is an
 * EMPTY cell (never 0 / a dash / 0%) with no hover; a non-boolean stale adds no class; no fault served → no note; the FE
 * never sorts by the column; the source types no head word, no percent, no "stale", no dash; the CSS keeps the cell on one
 * line with no px width; an older API (no si keys / no si head) renders as before. */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GG_ALL_SORT_KEY, GgAllTable } from './GgAllTable';
import { resetGgwList } from '../lib/ggWatchList';

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

const HEADS = [
  { key: 'rank', label: 'served #' }, { key: 'symbol', label: 'served Ticker' }, { key: 'dist', label: 'served To trigger' },
  { key: 'volume', label: 'served Volume' }, { key: 'float', label: 'served Float' }, { key: 'si', label: 'served SI head' },
];
const HEADS_OLD = HEADS.filter((h) => h.key !== 'si');
const SI_HEAD_TITLE = 'served si head title';
const row = (rank: number, sym: string, over: Record<string, unknown> = {}) => ({
  rank, near_rank: rank, tier: 1, symbol: sym, setup: 'bull_flag', dist_text: `served dist ${sym}`,
  volume_text: `served vol ${sym}`, float_text: `served float ${sym}`, in_watch: true,
  si_text: `served si ${sym}`, si_title: `served si title ${sym}`, si_stale: false, si_asof: '2026-09-30', ...over,
});
const block = (rows: any[], over: Record<string, unknown> = {}) => ({
  title: 'served title', heads: HEADS, order_text: 'served order', rows, fault_text: null,
  si_head_title: SI_HEAD_TITLE, si_fault_text: null, ...over,
});
const mount = (b: any) => render(<MemoryRouter><GgAllTable block={b} search="" back="/" /></MemoryRouter>);
const cellsOf = (sym: string) => [...screen.getByTestId(`gg-all-row-${sym}-bull_flag`).querySelectorAll(':scope > td')];
const siCell = (sym: string) => screen.getByTestId(`gg-all-si-${sym}-bull_flag`);
const order = (c: HTMLElement) => [...c.querySelectorAll('tbody tr')].map((tr) => tr.getAttribute('data-testid'))
  .filter((x) => x && x.startsWith('gg-all-row-')).map((x) => x!.replace('gg-all-row-', '').replace('-bull_flag', ''));

beforeEach(() => {
  vi.stubGlobal('localStorage', memStorage());
  resetGgwList();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ state: 'owner_only', reason: 'r', title: 't' }) })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('V1 — the served si_text in the si cell, after Float; served hovers on cell and head', () => {
  it('prints the served chip verbatim with the served title; the head label + hover are served', () => {
    const r = row(1, 'AAA', { si_text: '🩳 SI 30.0% float · 2.3d · 9/30', si_title: '🩳 Short interest — FINRA settlement 2026-09-30 …' });
    const { container } = mount(block([r]));
    const cells = cellsOf('AAA');
    expect(cells).toHaveLength(HEADS.length);
    const fi = HEADS.findIndex((h) => h.key === 'float');
    expect(cells[fi].textContent).toBe(r.float_text);
    expect(cells[fi + 1]).toBe(siCell('AAA'));
    expect(siCell('AAA').textContent).toBe(r.si_text);
    expect(siCell('AAA').getAttribute('title')).toBe(r.si_title);
    expect(siCell('AAA').className).toBe('gg-all-si');
    const ths = [...container.querySelectorAll('thead th')];
    expect(ths.map((th) => th.textContent)).toEqual(HEADS.map((h) => h.label));
    const siTh = ths[HEADS.findIndex((h) => h.key === 'si')];
    expect(siTh.getAttribute('title')).toBe(SI_HEAD_TITLE);
    // NEGATIVE: only the si head carries a hover
    for (const th of ths) if (th !== siTh) expect(th.getAttribute('title')).toBeNull();
  });
});

describe('V2 — NEGATIVE: no record → an EMPTY cell (never 0, never a dash), no hover; the row still renders', () => {
  for (const [label, over] of [
    ['null', { si_text: null, si_title: null, si_stale: null, si_asof: null }],
    ['empty string', { si_text: '', si_title: '', si_stale: null, si_asof: null }],
    ['absent', { si_text: undefined, si_title: undefined, si_stale: undefined, si_asof: undefined }],
  ] as const) {
    it(`si_text ${label}`, () => {
      const r = row(1, 'BBB', over as Record<string, unknown>);
      mount(block([r]));
      const td = siCell('BBB');
      expect(td.textContent).toBe('');
      for (const bad of ['0', '—', '-', '0%']) expect(td.textContent).not.toBe(bad);
      expect(td.hasAttribute('title')).toBe(false);
      const cells = cellsOf('BBB');
      expect(cells).toHaveLength(HEADS.length);
      expect(cells[HEADS.findIndex((h) => h.key === 'float')].textContent).toBe(r.float_text);
      expect(cells[HEADS.findIndex((h) => h.key === 'dist')].textContent).toBe(r.dist_text);
    });
  }
});

describe('V3 — stale: the class hook only when si_stale === true; the served text carries the word', () => {
  it('si_stale true → gg-all-si-stale + the served text', () => {
    mount(block([row(1, 'CCC', { si_text: '🩳 SI 30.0% float · 2.3d · 8/14 · stale', si_stale: true })]));
    expect(siCell('CCC').classList.contains('gg-all-si')).toBe(true);
    expect(siCell('CCC').classList.contains('gg-all-si-stale')).toBe(true);
    expect(siCell('CCC').textContent).toBe('🩳 SI 30.0% float · 2.3d · 8/14 · stale');
  });
  for (const v of [false, null, 'true', 1, undefined] as const) {
    it(`NEGATIVE: si_stale ${JSON.stringify(v)} → no stale class`, () => {
      mount(block([row(1, 'DDD', { si_stale: v })]));
      expect(siCell('DDD').classList.contains('gg-all-si')).toBe(true);
      expect(siCell('DDD').classList.contains('gg-all-si-stale')).toBe(false);
    });
  }
});

describe('V4 — the served si_fault_text under the fault line', () => {
  it('served → the gg-all-si-fault note verbatim; rows still render with blank si cells', () => {
    const blank = { si_text: null, si_title: null, si_stale: null, si_asof: null };
    const { container } = mount(block([row(1, 'EEE', blank), row(2, 'FFF', blank)],
      { si_fault_text: 'served si fault sentence', fault_text: 'served fault' }));
    expect(screen.getByTestId('gg-all-si-fault').textContent).toBe('served si fault sentence');
    expect(screen.getByTestId('gg-all-si-fault').className).toBe('cm-note cm-note-err');
    // under the fault line
    const fault = screen.getByTestId('gg-all-fault');
    expect(fault.compareDocumentPosition(screen.getByTestId('gg-all-si-fault')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(order(container)).toEqual(['EEE', 'FFF']);
    expect(siCell('EEE').textContent).toBe('');
    expect(siCell('FFF').textContent).toBe('');
  });
  for (const v of [null, '', undefined] as const) {
    it(`NEGATIVE: si_fault_text ${JSON.stringify(v)} → no note`, () => {
      mount(block([row(1, 'GGG')], { si_fault_text: v }));
      expect(screen.queryByTestId('gg-all-si-fault')).toBeNull();
    });
  }
});

describe('V5 — the FE never sorts by the column: served rank order, and served near_rank under the toggle', () => {
  const SORTS = { default: 'gg', options: [{ key: 'gg', label: 'served gg' }, { key: 'near', label: 'served near' }],
    near_text: 'served near line' };
  const ROWS = () => [
    row(1, 'AAA', { near_rank: 3, si_text: 'zzz' }), row(2, 'BBB', { near_rank: 1, si_text: '🩳 SI 99.9% float' }),
    row(3, 'CCC', { near_rank: 2, si_text: null }), row(4, 'DDD', { near_rank: 4, si_text: '0' }),
  ];
  it('rows lay out by the served rank, then by the served near_rank — never by si_text', () => {
    const { container } = mount(block(ROWS(), { sorts: SORTS }));
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD']);
    fireEvent.click(screen.getByTestId('gg-all-sort-near'));
    expect(order(container)).toEqual(['BBB', 'CCC', 'AAA', 'DDD']);
    expect(window.localStorage.getItem(GG_ALL_SORT_KEY)).toBe('near');
  });
});

/* ---- V6 / V7 source + stylesheet guards (the F9 / F10 helpers, copied — jsdom has no layout) ---- */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const strip = (src: string) => src.replace(/\{\/\*[\s\S]*?\*\/\}/g, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
const jsxText = (body: string) => [...body.matchAll(/(?<![=>])>(?!=)([^<>{}\n]+)</g)].map((m) => m[1].trim()).filter(Boolean);
function typed(body: string): string[] {
  const jsx = jsxText(body);
  const lits = [...body.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)].map((m) => (m[1] ?? m[2] ?? m[3]).replace(/\$\{[^}]*\}/g, ' '));
  return [...jsx, ...lits];
}
const WORDS = ['Short interest', 'stale', '—', '%'];
const hits = (body: string) => typed(body).flatMap((s) => WORDS
  .filter((w) => (/^\w+$/.test(w) ? new RegExp(`\\b${w}\\b`).test(s) : s.includes(w))).map((w) => `${w} in "${s.trim()}"`));
const PCT = /%/;

describe('V6 — GgAllTable.tsx types no Short interest / stale / dash / percent', () => {
  it('the source (comments stripped) types none of them; the si case + class hook are present', async () => {
    const raw = await readSource('src/components/GgAllTable.tsx');
    const src = strip(raw);
    expect(hits(src)).toEqual([]);
    expect(src).not.toContain('Short interest');
    expect(src).not.toContain('—');
    expect(src).not.toMatch(PCT);
    expect(src).toContain("case 'si':");
    expect(src).toContain('gg-all-si-');
    expect(src).toContain('row.si_stale === true');
  });
  it('NEGATIVE: a body typing the head, a percent format or a stale word fails the same matchers', () => {
    expect(hits("const h = 'Short interest';")).not.toEqual([]);
    expect(hits('\nfunction X() {\n  return <th>Short interest</th>;\n}\n')).not.toEqual([]);
    expect('const t = `${row.pct_of_float}%`;').toMatch(PCT);
    expect(hits("const w = 'stale';")).not.toEqual([]);
    expect(hits("const d = '—';")).not.toEqual([]);
    // the class literal inside the template hole is blanked, so the served-class hook passes
    expect(hits("const c = `gg-all-si${row.si_stale === true ? ' gg-all-si-stale' : ''}`;")).toEqual([]);
  });
});

describe('V7 — CSS: the si cell is ONE line (nowrap), no px width; the stale hook sets no width / white-space', () => {
  const rulesOf = (css: string) => [...css.matchAll(/(?:^|\n)([^{}\n]*\.gg-all[^{}\n]*)\{([^}]*)\}/g)]
    .map((m) => ({ sel: m[1].trim(), decl: m[2] }));
  const PX = /(?:^|[;\s])(?:min-|max-)?width:\s*\d+px/;
  const declOf = (css: string, sel: string) => rulesOf(css).filter((r) => r.sel === sel).map((r) => r.decl).join(';');
  const SI = '.gg-all-table td.gg-all-si';
  const STALE = '.gg-all-table td.gg-all-si-stale';
  it('nowrap on the si cell; no px width; the stale rule sets neither width nor white-space', async () => {
    const css = await readSource('src/styles/gajjala.css');
    expect(declOf(css, SI)).toMatch(/white-space:\s*nowrap/);
    expect(declOf(css, SI)).not.toMatch(PX);
    expect(declOf(css, STALE)).not.toBe('');
    expect(declOf(css, STALE)).not.toMatch(PX);
    expect(declOf(css, STALE)).not.toMatch(/white-space/);
    expect(declOf(css, STALE)).not.toMatch(/width/);
  });
  it('NEGATIVE: a wrapping or px-wide si cell fails the same matchers', () => {
    const BAD = `${SI} { white-space: normal; width: 120px; }\n`;
    expect(declOf(BAD, SI)).not.toMatch(/white-space:\s*nowrap/);
    expect(declOf(BAD, SI)).toMatch(PX);
    expect(declOf('', SI)).not.toMatch(/white-space:\s*nowrap/);
  });
});

describe('V8 — an older API renders as before', () => {
  it('rows without any si key and no si_head_title, si head served → empty si cells, no head hover, no throw', () => {
    const r: Record<string, unknown> = row(1, 'HHH');
    for (const k of ['si_text', 'si_title', 'si_stale', 'si_asof']) delete r[k];
    const b: Record<string, unknown> = block([r]);
    delete b.si_head_title; delete b.si_fault_text;
    const { container } = mount(b);
    expect(siCell('HHH').textContent).toBe('');
    expect(siCell('HHH').hasAttribute('title')).toBe(false);
    const siTh = [...container.querySelectorAll('thead th')][HEADS.findIndex((h) => h.key === 'si')];
    expect(siTh.hasAttribute('title')).toBe(false);
    expect(screen.queryByTestId('gg-all-si-fault')).toBeNull();
  });
  it('NEGATIVE: the si head not served → no si column at all (the cell count = the served heads)', () => {
    mount(block([row(1, 'III')], { heads: HEADS_OLD }));
    expect(screen.queryByTestId('gg-all-si-III-bull_flag')).toBeNull();
    expect(cellsOf('III')).toHaveLength(HEADS_OLD.length);
  });
});
