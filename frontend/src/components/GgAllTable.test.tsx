import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgAllTable, ggAllPriceText } from './GgAllTable';
import { GgEntryMiniTape, _resetGgLiteCache } from './GgEntryTape';
import { withSource } from '../lib/navSource';

/* 📋 All strategies table (2026-11-13, spec §3.5 WP-B, F1–F7 + F9 + F10).
 *
 * Ajay 2026-11-13: "Hey can you build be a table like track record on Gajjals landing page.. Call all strategies. I want
 * this table to rank based how gajjals sees them.. He watches 18 stocks simultaneously ..."
 *
 * The block below is HAND-MADE test data shaped like backend chart_maps/gajjala/all_table.block (never a golden, never a
 * ✨ id). Every assertion compares the DOM to the served value: the FE prints served strings in SERVED order and types
 * none. NEGATIVES: out-of-order rows render as served; no divider when every row is in the watch; zero entry-tape
 * fetches and zero observers with a preset spark; an empty / null live label falls back to the served text; null / ""
 * chips print nothing; a non-in-app href is text; the source types no head / tier / tape word, no percent, no toFixed,
 * imports nothing from GajjalaBoard; the stylesheet sets no px width on a .gg-all rule. */

const HEADS = [
  { key: 'rank', label: 'served #' }, { key: 'symbol', label: 'served Ticker' }, { key: 'spark', label: 'served Tape' },
  { key: 'category', label: 'served Category' }, { key: 'price', label: 'served Price' },
  { key: 'plan', label: 'served Trigger / stop' }, { key: 'dist', label: 'served To trigger' },
  { key: 'volume', label: 'served Volume' }, { key: 'float', label: 'served Float' },
];
const T0 = Date.UTC(2026, 10, 13, 14, 35);
const spark = (sym: string, setup: string, bars = 3) => ({
  id: `${sym}|${setup}`, ticker: sym, tf: 'served tf', lite: true,
  bars: Array.from({ length: bars }, (_, i) => ({ t: T0 + i * 300_000, c: 1 + i / 10, s: i ? 'rth' : 'premarket' })),
  n_bars: bars, rules: [], title: `served spark title ${sym} ${setup}`, tone: 'up' as const, note: null,
  aria: `served aria ${sym}`, as_of: '2026-11-13T10:00:00-05:00',
});
const row = (rank: number, tier: number, sym: string, setup: string, over: Record<string, unknown> = {}) => ({
  rank, tier, tier_key: `t${tier}`, tier_label: `served tier ${tier}`, symbol: sym, setup,
  category_text: `served category ${sym} ${setup}`, state: 'forming', state_word: 'served word',
  href: `/chart-maps?tab=gajjala&sub=${setup}&focus=${sym}`, card_href: `/chart-maps?tab=gajjala&sub=${setup}&focus=${sym}&card=1`,
  price: 1.23, price_text: `served px ${sym}`, change_text: `served chg ${sym}`, volume_text: `served vol ${sym}`,
  rvol_text: `served rvol ${sym}`, float_text: `served float ${sym}`, plan_text: `served plan ${sym}`,
  dist_text: `served dist ${sym}`, entry_plan: false, in_watch: true, vol_dried: null,
  broker_text: null, trader_text: null, promo_text: null, new_mark: null,
  spark: spark(sym, setup), ...over,
});
const block = (rows: any[], over: Record<string, unknown> = {}) => ({
  title: 'served title', heads: HEADS, order_text: 'served order line',
  watch: { n: 18, rows: 19, text: "served GG's 18 — 18 names (19 rows)" },
  rows, n: rows.length, more_n: null, more_text: null, faults_n: 0, fault_text: null,
  empty_text: null, honesty: 'served honesty line', tape_head: 'served tape head', ...over,
});

const SEARCH = '?tab=gajjala&sub=all_strategies';
const BACK = '/chart-maps?tab=gajjala&sub=all_strategies';
const mount = (b: any, extra: Record<string, unknown> = {}) => render(
  <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=all_strategies']}>
    <GgAllTable block={b} search={SEARCH} back={BACK} {...extra} />
  </MemoryRouter>);
const rowsShown = (c: HTMLElement) => [...c.querySelectorAll('tbody tr')]
  .map((tr) => tr.getAttribute('data-testid')).filter((x) => x && x.startsWith('gg-all-row-'));

/* IntersectionObserver + fetch spies: a preset spark must construct neither. */
let ioCount = 0;
class FakeIO {
  constructor() { ioCount += 1; }
  observe() { /* never visible */ }
  unobserve() { /* unused */ }
  disconnect() { /* unused */ }
  takeRecords() { return []; }
}
let fetchSpy: ReturnType<typeof vi.fn>;
beforeEach(() => {
  ioCount = 0; _resetGgLiteCache();
  vi.stubGlobal('IntersectionObserver', FakeIO);
  fetchSpy = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }));
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('F1 — served heads and rows, in SERVED order, served words verbatim', () => {
  it('heads in served order (the Tape head = served tape_head); one row per served row; every cell the served text', () => {
    const r = row(1, 1, 'AAA', 'kiss_fly');
    const { container } = mount(block([r]));
    const ths = [...container.querySelectorAll('thead th')].map((th) => th.textContent);
    expect(ths).toEqual(HEADS.map((h) => (h.key === 'spark' ? 'served tape head' : h.label)));
    const tr = screen.getByTestId('gg-all-row-AAA-kiss_fly');
    const cells = [...tr.querySelectorAll(':scope > td')];
    expect(cells).toHaveLength(HEADS.length);
    expect(cells[0].textContent).toBe('1');
    expect(cells[3].textContent).toBe(`${r.category_text}${r.tier_label}`);
    expect(cells[4].textContent).toBe(`${r.price_text}${r.change_text}`);
    expect(cells[5].textContent).toBe(r.plan_text);
    expect(cells[6].textContent).toBe(r.dist_text);
    expect(cells[7].textContent).toBe(`${r.volume_text}${r.rvol_text}`);
    expect(cells[8].textContent).toBe(r.float_text);
    expect(screen.getByTestId('gg-all-title').textContent).toBe('served title');
    expect(screen.getByTestId('gg-all-order').textContent).toBe('served order line');
    // the mini's hover = the served spark title
    expect(within(tr).getByTestId('gg-tape-mini')).toHaveAttribute('title', r.spark.title);
    // the table sits inside the 🏁 scroll box
    expect(container.querySelector('table.gg-all-table')!.parentElement!.className).toBe('gg-tr-scroll');
    expect(tr.className).toContain('gg-all-tier-1');
  });

  it('NEGATIVE: rows handed OUT of rank order render in that order — the FE never sorts', () => {
    const rows = [row(3, 3, 'CCC', 'intraday_vcp'), row(1, 1, 'AAA', 'bull_flag'), row(2, 2, 'BBB', 'kiss_fly')];
    const { container } = mount(block(rows));
    expect(rowsShown(container)).toEqual(['gg-all-row-CCC-intraday_vcp', 'gg-all-row-AAA-bull_flag', 'gg-all-row-BBB-kiss_fly']);
    expect([...container.querySelectorAll('td.gg-all-rank')].map((td) => td.textContent)).toEqual(['3', '1', '2']);
  });

  it('a name on two setups is two rows; vol_dried rides under the category; an unknown head key → an empty cell', () => {
    const rows = [row(1, 3, 'AUUD', 'kiss_fly', { vol_dried: 'served dried' }), row(2, 3, 'AUUD', 'intraday_vcp')];
    const b = block(rows, { heads: [...HEADS, { key: 'served_future_key', label: 'served future' }] });
    const { container } = mount(b);
    expect(rowsShown(container)).toEqual(['gg-all-row-AUUD-kiss_fly', 'gg-all-row-AUUD-intraday_vcp']);
    expect(screen.getByTestId('gg-all-dried-AUUD-kiss_fly').textContent).toBe('served dried');
    expect(screen.queryByTestId('gg-all-dried-AUUD-intraday_vcp')).toBeNull();
    const last = screen.getByTestId('gg-all-row-AUUD-kiss_fly').lastElementChild!;
    expect(last.tagName).toBe('TD');
    expect(last.textContent).toBe('');
  });
});

describe("F2 — GG's 18 divider", () => {
  it('after the LAST in_watch row, carrying the served watch text verbatim (both numbers)', () => {
    const rows = [row(1, 1, 'A1', 'bull_flag'), row(2, 3, 'A2', 'kiss_fly'),
      row(3, 3, 'A3', 'kiss_fly', { in_watch: false }), row(4, 4, 'A4', 'bull_flag', { in_watch: false })];
    const { container } = mount(block(rows));
    const trs = [...container.querySelectorAll('tbody > tr')];
    const at = trs.findIndex((t) => t.getAttribute('data-testid') === 'gg-all-divider');
    expect(trs[at - 1].getAttribute('data-testid')).toBe('gg-all-row-A2-kiss_fly');
    expect(trs[at + 1].getAttribute('data-testid')).toBe('gg-all-row-A3-kiss_fly');
    expect(screen.getByTestId('gg-all-divider').textContent).toBe("served GG's 18 — 18 names (19 rows)");
    expect(screen.getByTestId('gg-all-divider').querySelector('td')!.getAttribute('colspan')).toBe(String(HEADS.length));
    expect(screen.getAllByTestId('gg-all-divider')).toHaveLength(1);
    expect(trs[0].className).toContain('gg-all-watch');
    expect(trs[at + 1].className).not.toContain('gg-all-watch');
  });

  it('NEGATIVE: every row in_watch → no divider; no in_watch row → no divider', () => {
    const { unmount } = mount(block([row(1, 1, 'A1', 'bull_flag'), row(2, 3, 'A2', 'kiss_fly')]));
    expect(screen.queryByTestId('gg-all-divider')).toBeNull();
    unmount();
    mount(block([row(1, 1, 'A1', 'bull_flag', { in_watch: false }), row(2, 3, 'A2', 'kiss_fly', { in_watch: false })]));
    expect(screen.queryByTestId('gg-all-divider')).toBeNull();
  });

  it('NEGATIVE: no rows → the served empty_text and no table body', () => {
    const { container } = mount(block([], { empty_text: 'served empty line' }));
    expect(screen.getByTestId('gg-all-empty').textContent).toBe('served empty line');
    expect(container.querySelector('table')).toBeNull();
    expect(container.querySelector('tbody')).toBeNull();
  });

  it('NEGATIVE: a null block → the served empty_note only; nothing at all without one', () => {
    const { container, unmount } = mount(null, { emptyNote: 'served empty note' });
    expect(screen.getByTestId('gg-empty').textContent).toBe('served empty note');
    expect(container.querySelector('.gg-all')).toBeNull();
    unmount();
    const r2 = mount(null, { emptyNote: null });
    expect(r2.container.textContent).toBe('');
  });
});

describe('F3 — the mini draws from the preset spark: zero entry-tape fetches, zero observers', () => {
  it('one gg-tape-mini per row, drawn (an svg), no fetch, no IntersectionObserver', () => {
    const rows = [row(1, 1, 'A1', 'bull_flag'), row(2, 3, 'A2', 'kiss_fly'), row(3, 4, 'A3', 'horizontal_fade')];
    const { container } = mount(block(rows));
    const minis = container.querySelectorAll('td.ptt__mini-cell [data-testid="gg-tape-mini"]');
    expect(minis).toHaveLength(3);
    for (const m of minis) expect(m.querySelector('svg')).not.toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(fetchSpy.mock.calls.filter(([u]) => String(u).includes('entry-tape'))).toHaveLength(0);
    expect(ioCount).toBe(0);
  });

  it('NEGATIVE: a row with spark.bars == [] prints the dim glyph and does not throw; no spark → an empty cell', () => {
    const rows = [row(1, 3, 'A1', 'bull_flag', { spark: { ...spark('A1', 'bull_flag'), bars: [], n_bars: 0 } }),
      row(2, 3, 'A2', 'kiss_fly', { spark: null })];
    mount(block(rows));
    const mini = within(screen.getByTestId('gg-all-row-A1-bull_flag')).getByTestId('gg-tape-mini');
    expect(mini.querySelector('svg')).toBeNull();
    expect(mini.querySelector('.pcw__dim')!.textContent).toBe('—');
    const cell2 = screen.getByTestId('gg-all-row-A2-kiss_fly').querySelector('td.ptt__mini-cell')!;
    expect(cell2.textContent).toBe('');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('NEGATIVE (the lazy path unchanged): GgEntryMiniTape WITHOUT data constructs an observer and fetches nothing before it is visible', () => {
    render(<GgEntryMiniTape id="LEDGER-1" width={100} />);
    expect(ioCount).toBe(1);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.getByTestId('gg-tape-mini').textContent).toBe('…');
  });
});

describe('F4 — chips: 🚫 / 📌 / 🎪 / ✨ / 🟢, each only when served', () => {
  const FUTURE = new Date(Date.now() + 3_600_000).toISOString();
  it('served texts → the chips; the 🚫 span is byte-equal to the board GgBrokerChip span', () => {
    const r = row(1, 1, 'A1', 'bull_flag', {
      broker_text: 'served broker', trader_text: 'served trader', promo_text: 'served promo', entry_plan: true,
      new_mark: { kind: 'aplus', at_et: '10:05', until: FUTURE, text: 'served new', title: 'served new title' },
    });
    mount(block([r]));
    const b = screen.getByTestId('gg-broker-all-A1-bull_flag');
    expect(b.tagName).toBe('SPAN');
    expect(b.className).toBe('cm-badge cm-badge-muted gg-broker');
    expect(b.textContent).toBe('served broker');
    expect(screen.getByTestId('gg-trader-all-A1-bull_flag').textContent).toBe('served trader');
    expect(screen.getByTestId('gg-promo-all-A1-bull_flag').textContent).toBe('served promo');
    expect(screen.getByTestId('gg-new-all-A1-bull_flag').textContent).toBe('served new');
    const dot = screen.getByTestId('gg-all-entry-A1-bull_flag');
    expect(dot).toHaveAttribute('title', r.tier_label);
    expect(screen.getByTestId('gg-all-row-A1-bull_flag').className).toContain('gg-all-broker');
  });

  for (const [what, v] of [['null', null], ['""', ''], ['absent', undefined]] as [string, unknown][]) {
    it(`NEGATIVE: ${what} texts / mark / entry_plan → none of the chips, no broker dim`, () => {
      const over: Record<string, unknown> = { broker_text: v, trader_text: v, promo_text: v, new_mark: v, entry_plan: v };
      const r: any = row(1, 3, 'A1', 'bull_flag', over);
      if (v === undefined) for (const k of Object.keys(over)) delete r[k];
      mount(block([r]));
      for (const t of ['gg-broker-all-A1-bull_flag', 'gg-trader-all-A1-bull_flag', 'gg-promo-all-A1-bull_flag',
        'gg-new-all-A1-bull_flag', 'gg-all-entry-A1-bull_flag']) expect(screen.queryByTestId(t), t).toBeNull();
      expect(screen.getByTestId('gg-all-row-A1-bull_flag').className).not.toContain('gg-all-broker');
    });
  }

  it('NEGATIVE: entry_plan false → no 🟢; an expired new_mark → no ✨', () => {
    const r = row(1, 3, 'A1', 'bull_flag', { entry_plan: false,
      new_mark: { kind: 'aplus', at_et: '09:00', until: '2020-01-01T00:00:00Z', text: 'served new', title: 't' } });
    mount(block([r]));
    expect(screen.queryByTestId('gg-all-entry-A1-bull_flag')).toBeNull();
    expect(screen.queryByTestId('gg-new-all-A1-bull_flag')).toBeNull();
  });
});

describe('F5 — links: Ticker → href through withSource, the mini → card_href', () => {
  it('in-app hrefs are router links; the Ticker carries the source query', () => {
    const r = row(1, 1, 'A1', 'bull_flag');
    mount(block([r]));
    expect(screen.getByTestId('gg-all-link-A1-bull_flag')).toHaveAttribute('href', withSource(r.href, 'chart-maps', SEARCH));
    expect(screen.getByTestId('gg-all-link-A1-bull_flag').getAttribute('href')).toContain('from=chart-maps');
    expect(screen.getByTestId('gg-all-card-A1-bull_flag')).toHaveAttribute('href', r.card_href);
    expect(within(screen.getByTestId('gg-all-card-A1-bull_flag')).getByTestId('gg-tape-mini')).toBeTruthy();
  });

  it('NEGATIVE: a non-in-app href / card_href → text, no link', () => {
    mount(block([row(1, 1, 'A1', 'bull_flag', { href: 'https://evil.example/x', card_href: '//evil.example/y' })]));
    expect(screen.queryByTestId('gg-all-link-A1-bull_flag')).toBeNull();
    expect(screen.getByTestId('gg-all-sym-A1-bull_flag').textContent).toBe('A1');
    expect(screen.queryByTestId('gg-all-card-A1-bull_flag')).toBeNull();
    expect(screen.getByTestId('gg-all-row-A1-bull_flag').querySelector('a')).toBeNull();
  });
});

describe('F6 — the price cell prints a SERVED string only', () => {
  const answer = (quotes: Record<string, any>) => ({
    session: 'rth', as_of_epoch: 1, as_of: 'x', footer: { live: null, stale: null }, now_labels: ['now', 'now · pre', 'now · AH'],
    cap: 250, asked: 1, served: 1, missing: [], fault: null, quotes,
  }) as any;
  it('the served live_price_text, else the served price_text — verbatim per row', () => {
    const rows = [row(1, 1, 'A1', 'bull_flag'), row(2, 3, 'A2', 'kiss_fly', { live_price_text: 'served live A2' }),
      row(3, 3, 'A3', 'kiss_fly')];
    mount(block(rows));
    expect(screen.getByTestId('gg-all-px-A1-bull_flag').textContent).toBe('served px A1');
    expect(screen.getByTestId('gg-all-px-A2-kiss_fly').textContent).toBe('served live A2');
    expect(screen.getByTestId('gg-all-px-A3-kiss_fly').textContent).toBe('served px A3');
  });

  it('NEGATIVE: the live poll\'s now.label ("now" / "now · pre" / "now · AH") NEVER reaches the cell', () => {
    const rows = [row(1, 1, 'A1', 'bull_flag'), row(2, 3, 'A2', 'kiss_fly', { live_price_text: 'served live A2' }),
      row(3, 3, 'A3', 'kiss_fly')];
    const ans = answer({
      A1: { bar: null, prev_t: null, now: { price: 0.0, label: 'now' } },
      A2: { bar: null, prev_t: null, now: { price: 0.0, label: 'now · pre' } },
      A3: { bar: null, prev_t: null, now: { price: 4.46, label: 'now · AH' } },
    });
    mount(block(rows), { answer: ans });
    expect(screen.getByTestId('gg-all-px-A1-bull_flag').textContent).toBe('served px A1');
    expect(screen.getByTestId('gg-all-px-A2-kiss_fly').textContent).toBe('served live A2');
    expect(screen.getByTestId('gg-all-px-A3-kiss_fly').textContent).toBe('served px A3');
    for (const r of rows) {
      const t = screen.getByTestId(`gg-all-price-${r.symbol}-${r.setup}`).textContent ?? '';
      expect(t).not.toMatch(/\bnow\b/);
    }
    expect(ggAllPriceText(rows[0] as any, ans)).toBe('served px A1');
    expect(ggAllPriceText(rows[1] as any, ans)).toBe('served live A2');
  });

  it('NEGATIVE: answer null / now null → the served texts; "" / blank served texts → the next served text, never an empty string', () => {
    const r = row(1, 1, 'A1', 'bull_flag');
    expect(ggAllPriceText(r as any, null)).toBe('served px A1');
    expect(ggAllPriceText(r as any)).toBe('served px A1');
    expect(ggAllPriceText(r as any, answer({ A1: { bar: null, prev_t: null, now: null } }))).toBe('served px A1');
    expect(ggAllPriceText({ ...r, live_price_text: '' } as any, null)).toBe('served px A1');
    expect(ggAllPriceText({ ...r, live_price_text: '   ' } as any, null)).toBe('served px A1');
    expect(ggAllPriceText({ ...r, live_price_text: null, price_text: null } as any,
      answer({ A1: { bar: null, prev_t: null, now: { price: 4.4, label: 'now' } } }))).toBeNull();
  });
});

describe('F7 — more / fault / honesty lines', () => {
  it('printed verbatim when served', () => {
    mount(block([row(1, 1, 'A1', 'bull_flag')], { more_text: 'served more', fault_text: 'served fault' }));
    expect(screen.getByTestId('gg-all-more').textContent).toBe('served more');
    expect(screen.getByTestId('gg-all-fault').textContent).toBe('served fault');
    expect(screen.getByTestId('gg-all-honesty').textContent).toBe('served honesty line');
  });
  it('NEGATIVE: absent / null / "" → nothing', () => {
    mount(block([row(1, 1, 'A1', 'bull_flag')], { more_text: '', fault_text: null, honesty: undefined, title: '', order_text: null }));
    for (const t of ['gg-all-more', 'gg-all-fault', 'gg-all-honesty', 'gg-all-title', 'gg-all-order', 'gg-all-empty']) {
      expect(screen.queryByTestId(t), t).toBeNull();
    }
  });
});

/* ---- F9 / F10 source + stylesheet guards (the track_record_tape.test.tsx house pattern — jsdom has no layout) ---- */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const strip = (src: string) => src.replace(/\{\/\*[\s\S]*?\*\/\}/g, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
/* JSX text between a tag's `>` and the next `<` — an arrow `=>` or a `>=` comparison is not a tag end. */
const jsxText = (body: string) => [...body.matchAll(/(?<![=>])>(?!=)([^<>{}\n]+)</g)].map((m) => m[1].trim()).filter(Boolean);
/** Every typed word: JSX text and string literals (template holes blanked). */
function typed(body: string): string[] {
  const jsx = jsxText(body);
  const lits = [...body.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)].map((m) => (m[1] ?? m[2] ?? m[3]).replace(/\$\{[^}]*\}/g, ' '));
  return [...jsx, ...lits];
}
/* The served words the file must never type — spec §3.2's HEADS labels and TIER_WORDS (test data here: the FE must not
 * depend on the backend file existing), plus tape.py's ENTRY_TAPE_WORDS phrases. */
const SERVED_WORDS = ['Ticker', 'Tape', 'Category', 'Price', 'Trigger / stop', 'To trigger', 'Volume', 'Float',
  '\u{1F3AF} A+', '\u{1F9E0} potential', 'forming — close to a setup', 'a rule failed / stopped', "GG's", 'All strategies'];
function tapeWords(tapePy: string): string[] {
  const out: string[] = [];
  const blk = /^ENTRY_TAPE_WORDS = \{([\s\S]*?)\n\}/m.exec(tapePy);
  for (const m of (blk?.[1] || '').matchAll(/^\s*"\w+":\s*"((?:[^"\\]|\\.)*)"/gm)) {
    const p = m[1].split('{')[0].trim();
    if (p.length >= 4) out.push(p);
  }
  return out;
}
const hits = (body: string, words: string[]) => typed(body).flatMap((s) => words
  .filter((w) => (/^\w+$/.test(w) ? new RegExp(`\\b${w}\\b`).test(s) : s.includes(w))).map((w) => `${w} in "${s.trim()}"`));
const FORMAT = /toFixed|Math\.|%|toLocale|Intl\.|\.price\b|\bprice\s*[-+*/]\s*[\w(]/;
const BOARD_IMPORT = /from\s+['"]\.\/GajjalaBoard['"]/;

describe('F9 — GgAllTable.tsx types no served word, formats no number, imports nothing from GajjalaBoard', () => {
  it('no JSX text, no head / tier / tape word, no percent, no toFixed, no price arithmetic, no GajjalaBoard import', async () => {
    const raw = await readSource('src/components/GgAllTable.tsx');
    const src = strip(raw);
    const words = [...SERVED_WORDS, ...tapeWords(await readSource('../backend/chart_maps/gajjala/tape.py'))];
    expect(words.length).toBeGreaterThan(SERVED_WORDS.length + 5);
    expect(jsxText(src)).toEqual([]);
    expect(hits(src, words)).toEqual([]);
    expect(src).not.toMatch(FORMAT);
    expect(raw).not.toMatch(BOARD_IMPORT);
    expect(src).not.toContain('GgBrokerChip');
    // the 🚫 chip rides the shared servedChip with the per-surface test id (contracts D2 "every surface that lists a name")
    expect(raw).toContain('gg-broker-all-');
    expect(raw).toContain('servedChip(');
  });

  it('NEGATIVE: the same matchers flag a body that types a head, a tier word, a percent, toFixed or a GajjalaBoard import', () => {
    expect(jsxText('\nfunction X() {\n  return <th>Ticker</th>;\n}\n')).toEqual(['Ticker']);
    expect(hits("const h = 'Category';", SERVED_WORDS)).not.toEqual([]);
    expect(hits("const t = '\u{1F9E0} potential';", SERVED_WORDS)).not.toEqual([]);
    expect(hits("const c = 'gg-all-cat'; const k = 'category';", SERVED_WORDS)).toEqual([]);
    expect('const s = `${(x * 100).toFixed(1)}%`;').toMatch(FORMAT);
    expect('const p = q.now.price;').toMatch(FORMAT);
    expect('const d = price - trigger;').toMatch(FORMAT);
    expect('const t = row.price_text ?? row.live_price_text;').not.toMatch(FORMAT);
    expect('data-testid={`gg-all-price-${rid(row)}`}').not.toMatch(FORMAT);
    expect("import { X } from './GajjalaBoard';").toMatch(BOARD_IMPORT);
    expect("import { X } from './GgTraderChip';").not.toMatch(BOARD_IMPORT);
  });

  it('GgTraderChip exports servedChip (an export line only — the 🎪 contract\'s own export line kept) and the board keeps its local GgBrokerChip (contracts 9310)', async () => {
    const chip = await readSource('src/components/GgTraderChip.tsx');
    expect(chip).toMatch(/^export \{ GgTraderChip \};$/m);
    expect(chip).toMatch(/^export \{ servedChip \};$/m);
    const board = await readSource('src/components/GajjalaBoard.tsx');
    expect(board).toContain('\nfunction GgBrokerChip(');
    expect(board.split('ptt__mini-cell').length - 1).toBe(1);
  });
});

describe('F10 — 📱 430 px: the table scrolls inside .gg-tr-scroll, no px width on a .gg-all rule, Ticker + Category wrap', () => {
  const rulesOf = (css: string) => [...css.matchAll(/(?:^|\n)([^{}\n]*\.gg-all[^{}\n]*)\{([^}]*)\}/g)]
    .map((m) => ({ sel: m[1].trim(), decl: m[2] }));
  const PX = /(?:^|[;\s])(?:min-|max-)?width:\s*\d+px/;
  const declOf = (css: string, sel: string) => rulesOf(css).filter((r) => r.sel === sel).map((r) => r.decl).join(';');
  const BAD = '.gg-all { width: 640px; }\n.gg-all-table td.gg-all-sym { white-space: nowrap; }\n';
  const CHIP = '.gg-tr-scroll .gg-all-table td.gg-all-sym .cm-badge';
  const WRAPPING_CHIP = `${CHIP} { white-space: normal; overflow-wrap: anywhere; }\n`;

  it('.gg-all min-width 0; the Ticker and Category cells wrap; no .gg-all* rule sets a px width', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const rules = rulesOf(css);
    expect(rules.length).toBeGreaterThan(5);
    for (const r of rules) expect(r.decl, r.sel).not.toMatch(PX);
    expect(declOf(css, '.gg-all')).toMatch(/min-width:\s*0/);
    expect(declOf(css, '.gg-all-table td.gg-all-sym')).toMatch(/white-space:\s*normal/);
    expect(declOf(css, '.gg-all-table td.gg-all-sym')).toMatch(/overflow-wrap:\s*anywhere/);
    expect(declOf(css, '.gg-all-cat')).toMatch(/white-space:\s*normal/);
    // refix 2026-11-13: the 🚫 / 📌 chip stays on ONE line inside the scroller (no word-per-line Ticker cell at 430 px)
    // 2026-11-13 final: the chip wraps on WORD boundaries inside a 9rem box (a one-line chip widened Ticker to ~230 px and
    // squeezed Category to one word per line at 430 px); overflow-wrap normal keeps words whole.
    expect(declOf(css, CHIP)).toMatch(/white-space:\s*normal/);
    expect(declOf(css, CHIP)).toMatch(/max-width:\s*9rem/);
    expect(declOf(css, CHIP)).toMatch(/overflow-wrap:\s*normal/);
    expect(declOf(css, '.gg-all-table td.gg-all-sym .cm-badge')).toBe('');
    expect(declOf(css, '.gg-all-table tr.gg-all-divider > td')).toMatch(/dashed/);
    // the global `table { min-width: 1400px }` (styles.css) is overridden, so #, Ticker and Tape fit the phone (measured 2026-11-13)
    expect(declOf(css, '.gg-all-table')).toMatch(/min-width:\s*0/);
    // the rank (FIRST cell) never breaks "18" in two under the 430 px 🏁 first-cell wrap rule
    expect(declOf(css, '.gg-all-table td.gg-all-rank')).toMatch(/white-space:\s*nowrap/);
  });

  it('NEGATIVE: a px-wide .gg-all or a nowrap Ticker cell fails the same matchers', () => {
    expect(rulesOf(BAD).some((r) => PX.test(r.decl))).toBe(true);
    expect(declOf(BAD, '.gg-all-table td.gg-all-sym')).not.toMatch(/white-space:\s*normal/);
    expect(declOf(BAD, '.gg-all')).not.toMatch(/min-width:\s*0/);
    expect(declOf(BAD, '.gg-all-table')).not.toMatch(/min-width:\s*0/);
  });

  it('NEGATIVE: the pre-refix word-per-line chip (white-space normal + overflow-wrap anywhere) fails the one-line matchers', () => {
    expect(declOf(WRAPPING_CHIP, CHIP)).not.toMatch(/white-space:\s*nowrap/);
    expect(declOf(WRAPPING_CHIP, CHIP)).not.toMatch(/overflow-wrap:\s*normal/);
    expect(declOf('', CHIP)).not.toMatch(/white-space:\s*nowrap/);
  });

  it('the 🚫 chip renders inside .gg-tr-scroll > table td.gg-all-sym as a .cm-badge (the one-line rule reaches it)', () => {
    const r = { ...row(1, 1, 'B1', 'bull_flag'), broker_text: 'not eligible at Fidelity' };
    const { container } = mount(block([r]));
    const chip = screen.getByTestId('gg-broker-all-B1-bull_flag');
    expect(chip.classList.contains('cm-badge')).toBe(true);
    expect(container.querySelector('.gg-tr-scroll .gg-all-table td.gg-all-sym .cm-badge')).toBe(chip);
  });

  it('the rendered table sits inside .gg-tr-scroll and its Ticker / Category cells carry the wrap hooks', () => {
    const { container } = mount(block([row(1, 1, 'A1', 'bull_flag')]));
    expect(container.querySelector('.gg-all table')!.parentElement!.className).toBe('gg-tr-scroll');
    const tr = screen.getByTestId('gg-all-row-A1-bull_flag');
    expect(tr.querySelector('td.gg-all-sym')).not.toBeNull();
    expect(tr.querySelector('td.gg-all-cat')).not.toBeNull();
    for (const td of tr.querySelectorAll('td')) expect(td.getAttribute('style')).toBeNull();
  });
});
