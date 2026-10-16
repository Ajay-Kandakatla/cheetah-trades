/* DojiSweepBoardNote — prints the SERVED 🕯️ board lines, composes none (2026-10-16).
 *
 * Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a
 * sweep. For any stocks after a down trend. May be from all chart maps
 * especially on the 60% 70% down stocks".
 *
 * Two payloads:
 *   HAND   — typed from the doji spec §3.4 envelope (doji_sweep_tab.ready_block /
 *            warming_block shapes, the W-table strings), so the suite runs before
 *            the backend golden exists;
 *   GOLDEN — components/__fixtures__/doji_sweep_board_golden_2026_10_16.json,
 *            WRITTEN by backend tests/test_doji_sweep_board.py (WP-B). Its cases
 *            SKIP while the file is absent (the main session re-runs them).
 * Every assertion compares the rendered text with the SERVED string, byte for
 * byte; nothing here re-derives a number. */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import DojiSweepBoardNote from './DojiSweepBoardNote';
import type { CmDojiSweepBoard } from '../lib/dojiSweep';
import type { CmSort } from '../lib/chartMaps';

type Payload = { doji_sweep_board: CmDojiSweepBoard; sorts: CmSort[]; sort: string };
type Item = { key: string; label: string; on: boolean; pass: number; fail: number; no_read: number; hidden: number; note: string };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

/* tsc-safe fixture read (the GajjalaBoard.potential.test precedent): the app's
 * tsconfig carries no node types, so `node:fs` is imported dynamically; the
 * path is relative to frontend/ (vitest's cwd). */
async function readJsonIfPresent(rel: string): Promise<any | null> {
  try {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const p = `${root}/${rel}`;
    return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
  } catch {
    return null;
  }
}
const GOLDEN: Record<string, Payload> | null =
  await readJsonIfPresent('src/components/__fixtures__/doji_sweep_board_golden_2026_10_16.json');

const C = '\u{1F56F}\u{FE0F}';
const SORTS: CmSort[] = [
  { key: 'default', label: `${C} Newest candle, deepest first` },
  { key: 'doji_test', label: '\u{1F4CF} Closest to the prior low first' },
  { key: 'doji_ath', label: '\u{1F3D4}\u{FE0F} Deepest under the all-time high first' },
] as CmSort[];
const KEYS = ['w52_40', 'w52_60', 'w52_70', 'ath_60', 'mas', 'reclaimed'];
const LABELS: Record<string, string> = {
  w52_40: '\u{1F4C9} ≥40% off the 52-week high', w52_60: '\u{1F4C9} ≥60% off the 52-week high',
  w52_70: '\u{1F4C9} ≥70% off the 52-week high', ath_60: '\u{1F3D4}\u{FE0F} ≥60% off the all-time high',
  mas: 'Below the 50- and 200-day', reclaimed: 'Undercut and reclaimed',
};
const STUDY = `${C} UNMEASURED — no study in this app has measured what a doji testing its prior 20-session low in a downtrend does next; the pre-registered backtest (docs/research/doji_sweep_study_2026_10_16.md, backend/scripts/doji_sweep_study.py) is the one that may.`;
const WARM_HEADER = `${C} Reading every name's last closed daily candle from the cached bars — the charts appear here as soon as it lands; you don't need to refresh.`;
const NOTE = `${C} Display only — the list describes the last closed candle, not what comes next. Nothing here gates a scan, pushes a phone, sizes a position or enters a lane. Not advice.`;

function filters(active: string[], passes: Record<string, number>) {
  const items: Item[] = KEYS.map((k) => ({ key: k, label: LABELS[k], on: active.includes(k), pass: passes[k] ?? 0,
    fail: 3 - (passes[k] ?? 0), no_read: 0, hidden: active.includes(k) ? 3 - (passes[k] ?? 0) : 0,
    note: `${LABELS[k]} — served note. UNMEASURED.` }));
  return { keys: KEYS, active, pool: 3, mode: 'all', passed_all: active.length ? 1 : null, shown: active.length ? 1 : null,
    hidden: active.length ? 2 : 0, items, line: active.length ? 'Chips on (every ticked chip must pass) — served line.' : null,
    note: 'Ticked chips narrow the list — every ticked chip must pass. They gate nothing, push nothing and enter no lane.',
    measured: false };
}
function body(on: '5' | '10') {
  return { param: 'dj_body', pct: Number(on), steps: [
    { key: '5', label: `${C} Body under 5%`, title: "The app's own doji (scalping/candles.py) — the body under 5% of the day's range", on: on === '5', default: true },
    { key: '10', label: `${C} Body under 10%`, title: 'A looser doji — the body under 10% of the range (PivotBoss, Liberated Stock Trader); the study reads both', on: on === '10', default: false },
  ] };
}
const LEGEND = [
  '\u{1F4C9} 52-week: 60% or more under the highest intraday high of the last 252 closed sessions.',
  '\u{1F3D4}\u{FE0F} All-time: 60% or more under the all-time high (monthly history to the listing plus the cached daily bars; “high since” when the history is short — the distance is then at least this).',
  'Averages: the close under both the 50- and 200-day simple averages.',
];
const CONSTS = { test_pct: 5.0, ref_sessions: 20, ref_min_age: 4, down_pct: 60.0, sma_fast: 50, sma_slow: 200, year_bars: 252, filter_param: 'dj' };

const HAND_READY: Payload = {
  sort: 'default', sorts: SORTS,
  doji_sweep_board: {
    state: 'ready', session: '2026-10-16', as_of: '2026-10-15', built_at: '2026-10-15T20:05:00-04:00', measured: false,
    study: { status: 'unmeasured', text: STUDY, verdict: null, prereg: 'docs/research/doji_sweep_study_2026_10_16.md', script: 'backend/scripts/doji_sweep_study.py' },
    sort: 'default',
    header: `${C} 3 of 9 names printed a doji on 2026-10-15 — a body under 5% of the day's range — with the low within 5% either side of the lowest low of the 20 sessions before it, in a downtrend: 60%+ under the 52-week high, 60%+ under the all-time high, or below the 50- and 200-day. Sweep: 3 tests · 1 undercut the low.`,
    order_line: 'Order: the newest candle first, then the deepest under the 52-week high — an order, not a ranking of setups.',
    count_line: 'Showing 3 — 1 under the liquidity floor (Ok · ≥$10M/day). Not listed: 1 whose candle was not a doji (a body of 10% of the range or more), 0 whose low sat more than 5% from the prior 20-session low.',
    note: NOTE, body: body('5'), filters: filters([], { w52_40: 3, w52_60: 2, w52_70: 1, ath_60: 1, mas: 2, reclaimed: 1 }),
    counts: { scanned: 9, at_body: 3, shown: 3, undercut: 1 },
    suspects: { n: 1, head: '1 names held out — a one-session close move of 5× or more, the price layer\'s own split / decimal-shift guard. A real collapse can trip it too; check the chart.', lines: ['GLCH — 2.00 → 12.00 on 2026-09-01 (6.00× in one session)'] },
    reads_legend: LEGEND, ...CONSTS,
  } as CmDojiSweepBoard,
};
const HAND_WARM: Payload = {
  sort: 'default', sorts: SORTS,
  doji_sweep_board: {
    state: 'warming', session: '2026-10-16', as_of: null, built_at: null, measured: false,
    study: HAND_READY.doji_sweep_board.study, sort: 'default', header: WARM_HEADER,
    order_line: HAND_READY.doji_sweep_board.order_line, count_line: null, note: NOTE, body: body('5'),
    filters: { ...filters([], {}), pool: 0 }, counts: null, suspects: null, reads_legend: LEGEND, ...CONSTS,
  } as CmDojiSweepBoard,
};

const noop = () => {};
const draw = (p: Payload, h: Partial<{ onSort: (k: string) => void; onToggleFilter: (k: string) => void; onBody: (k: string) => void }> = {}) =>
  render(<DojiSweepBoardNote board={p.doji_sweep_board} sorts={p.sorts} sort={p.sort}
                             onSort={h.onSort ?? noop} onToggleFilter={h.onToggleFilter ?? noop} onBody={h.onBody ?? noop} />);
/* the b-word is spelt in two halves so the word itself never sits in this file */
const BAD_WORDS = new RegExp(`${['bou', 'nce'].join('')}|NaN|undefined|None`);

afterEach(() => cleanup());

/* The cases every payload must pass — the getter is read inside each `it`, so
 * a skipped (absent) golden is never touched at collection time. */
function readyCases(get: () => Payload, skip: boolean) {
  it.skipIf(skip)('header / study / order / counts print byte-equal to the served strings; the study sits right under the header', () => {
    const p = get(); const b = p.doji_sweep_board;
    draw(p);
    expect(screen.getByTestId('cm-dj-board').getAttribute('data-state')).toBe('ready');
    expect(screen.getByTestId('cm-dj-header').textContent).toBe(b.header);
    expect(screen.getByTestId('cm-dj-header').getAttribute('role')).toBeNull();
    expect(screen.getByTestId('cm-dj-study').textContent).toBe(b.study.text);
    expect(screen.getByTestId('cm-dj-order').textContent).toBe(b.order_line);
    expect(screen.getByTestId('cm-dj-counts').textContent).toBe(b.count_line);
    expect(screen.getByTestId('cm-dj-header').nextElementSibling).toBe(screen.getByTestId('cm-dj-study'));
    if (b.note !== b.header) expect(screen.getByTestId('cm-dj-note').textContent).toBe(b.note);
  });

  it.skipIf(skip)('sort buttons: one per served sort, served label, pressed = the served sort, click → onSort(key)', () => {
    const p = get(); const onSort = vi.fn();
    draw(p, { onSort });
    for (const s of p.sorts) {
      const btn = screen.getByTestId(`cm-dj-sort-${s.key}`);
      expect(btn.textContent).toBe(s.label);
      expect(btn.getAttribute('aria-pressed')).toBe(s.key === p.sort ? 'true' : 'false');
    }
    const other = p.sorts.find((s) => s.key !== p.sort)!;
    fireEvent.click(screen.getByTestId(`cm-dj-sort-${other.key}`));
    expect(onSort).toHaveBeenCalledWith(other.key);
  });

  it.skipIf(skip)('body switch: one button per served step, served label + title, pressed = served on, click → onBody(key)', () => {
    const p = get(); const onBody = vi.fn();
    draw(p, { onBody });
    expect(screen.getByTestId('cm-dj-body').getAttribute('aria-label')).toBe('Doji body');
    for (const s of p.doji_sweep_board.body.steps) {
      const btn = screen.getByTestId(`cm-dj-body-${s.key}`);
      expect(btn.textContent).toBe(s.label);
      expect(btn.getAttribute('title')).toBe(s.title);
      expect(btn.getAttribute('aria-pressed')).toBe(s.on ? 'true' : 'false');
      fireEvent.click(btn);
      expect(onBody).toHaveBeenLastCalledWith(s.key);
    }
  });

  it.skipIf(skip)('chips: one checkbox per served item, served label and pass count, checked = served on, click → onToggleFilter(key); NEGATIVE no mode switch', () => {
    const p = get(); const onToggleFilter = vi.fn();
    draw(p, { onToggleFilter });
    const items = (p.doji_sweep_board.filters as { items: Item[] }).items;
    expect(items.map((i) => i.key)).toEqual(KEYS);
    for (const i of items) {
      const box = screen.getByTestId(`cm-dj-filter-${i.key}`) as HTMLInputElement;
      expect(box.checked).toBe(i.on);
      const label = box.closest('label')!;
      expect(label.textContent).toContain(i.label);
      expect(label.textContent).toContain(String(i.pass));
      fireEvent.click(box);
      expect(onToggleFilter).toHaveBeenLastCalledWith(i.key);
    }
    expect(screen.queryByTestId('cm-dj-filter-mode')).toBeNull();
  });

  it.skipIf(skip)('the reads fold lists the three served legend lines (summary = the fold label)', () => {
    const p = get();
    draw(p);
    const fold = screen.getByTestId('cm-dj-reads');
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.querySelector('summary')!.textContent).toBe('The three downtrend reads');
    expect(screen.getAllByTestId('cm-dj-read').map((e) => e.textContent)).toEqual(p.doji_sweep_board.reads_legend);
    expect(p.doji_sweep_board.reads_legend).toHaveLength(3);
  });

  it.skipIf(skip)('NEGATIVE: the rendered text never carries the b-word, NaN, undefined or None', () => {
    const p = get();
    const { container } = draw(p);
    expect(container.textContent || '').not.toMatch(BAD_WORDS);
  });
}

function warmingCases(get: () => Payload, skip: boolean) {
  it.skipIf(skip)('NEGATIVE: warming → the served header as a status + the study line; NO sorts, body switch, chips, counts or folds', () => {
    const p = get(); const b = p.doji_sweep_board;
    const { container } = draw(p);
    expect(screen.getByTestId('cm-dj-board').getAttribute('data-state')).toBe('warming');
    expect(screen.getByTestId('cm-dj-header').getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-dj-header').textContent).toBe(b.header);
    expect(screen.getByTestId('cm-dj-study').textContent).toBe(b.study.text);
    for (const id of ['cm-dj-sorts', 'cm-dj-body', 'cm-dj-filters', 'cm-dj-counts', 'cm-dj-reads', 'cm-dj-suspects', 'cm-dj-order', 'cm-dj-note']) {
      expect(screen.queryByTestId(id), id).toBeNull();
    }
    expect(container.textContent || '').not.toMatch(BAD_WORDS);
  });
}

describe('DojiSweepBoardNote — HAND payload (doji spec §3.4 envelope)', () => {
  readyCases(() => HAND_READY, false);
  warmingCases(() => HAND_WARM, false);

  it('a ticked chip prints the served filter line; checked follows the served on, never a guess', () => {
    const p = clone(HAND_READY);
    p.doji_sweep_board.filters = filters(['reclaimed'], { reclaimed: 1 });
    draw(p);
    expect((screen.getByTestId('cm-dj-filter-reclaimed') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByTestId('cm-dj-filter-mas') as HTMLInputElement).checked).toBe(false);
    expect(screen.getByTestId('cm-dj-filter-line').textContent).toBe('Chips on (every ticked chip must pass) — served line.');
  });

  it('NEGATIVE: pressed is the SERVED sort / step — a non-default served sort and the 10% step', () => {
    const p = clone(HAND_READY);
    p.sort = 'doji_test'; p.doji_sweep_board.sort = 'doji_test'; p.doji_sweep_board.body = body('10');
    draw(p);
    expect(screen.getByTestId('cm-dj-sort-doji_test').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-dj-sort-default').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('cm-dj-body-10').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-dj-body-5').getAttribute('aria-pressed')).toBe('false');
  });

  it('the held-out fold renders the served names only when the served count is above zero', () => {
    draw(HAND_READY);
    const s = HAND_READY.doji_sweep_board.suspects!;
    expect(screen.getByTestId('cm-dj-suspects').querySelector('summary')!.textContent).toBe(s.head);
    expect(screen.getAllByTestId('cm-dj-suspect').map((e) => e.textContent)).toEqual(s.lines);
    cleanup();
    const z = clone(HAND_READY);
    z.doji_sweep_board.suspects = { n: 0, head: 'H-0', lines: [] };
    draw(z);
    expect(screen.queryByTestId('cm-dj-suspects')).toBeNull();
  });

  it('NEGATIVE: an error block prints the served error header (no status role), no chips or counts', () => {
    const p = clone(HAND_WARM);
    p.doji_sweep_board.state = 'error';
    p.doji_sweep_board.header = `${C} The Doji Sweep list could not be built (boom). It is retried every 5 minutes — this is not a warming state.`;
    draw(p);
    expect(screen.getByTestId('cm-dj-board').getAttribute('data-state')).toBe('error');
    expect(screen.getByTestId('cm-dj-header').textContent).toBe(p.doji_sweep_board.header);
    expect(screen.getByTestId('cm-dj-header').getAttribute('role')).toBeNull();
    expect(screen.queryByTestId('cm-dj-filters')).toBeNull();
    expect(screen.queryByTestId('cm-dj-counts')).toBeNull();
  });

  it('NEGATIVE: an absent, malformed or header-less block renders nothing', () => {
    const headerless = clone(HAND_READY.doji_sweep_board) as unknown as Record<string, unknown>;
    delete headerless.header;
    for (const bad of [null, undefined, 'x', 7, [], { state: 'ready' }, { header: '   ' }, { header: 42 }, headerless]) {
      const { container } = render(<DojiSweepBoardNote board={bad as unknown as CmDojiSweepBoard} sorts={SORTS}
                                                        onSort={noop} onToggleFilter={noop} onBody={noop} />);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: malformed sorts / steps / chips / legend entries are skipped, never drawn as "undefined"', () => {
    const p = clone(HAND_READY) as unknown as { doji_sweep_board: Record<string, any>; sorts: unknown[] };
    p.sorts = [null, 'x', { key: 'default' }, { label: 'L' }, ...SORTS];
    p.doji_sweep_board.body.steps.push(null, { key: '15' }, 'x');
    p.doji_sweep_board.filters.items.push({ key: 'b15', label: 'stray', on: false, pass: 1 });
    p.doji_sweep_board.reads_legend = [...LEGEND, null, '', 3];
    p.doji_sweep_board.study = { text: 7 };
    const { container } = render(<DojiSweepBoardNote board={p.doji_sweep_board as CmDojiSweepBoard} sorts={p.sorts as CmSort[]}
                                                      sort="default" onSort={noop} onToggleFilter={noop} onBody={noop} />);
    expect(screen.getAllByRole('button').filter((b) => b.dataset.testid?.startsWith('cm-dj-sort-'))).toHaveLength(3);
    expect(screen.queryByTestId('cm-dj-body-15')).toBeNull();
    expect(screen.queryByTestId('cm-dj-filter-b15')).toBeNull();
    expect(screen.getAllByTestId('cm-dj-read')).toHaveLength(3);
    expect(screen.queryByTestId('cm-dj-study')).toBeNull();
    expect(container.textContent || '').not.toMatch(BAD_WORDS);
  });
});

describe('DojiSweepBoardNote — the WP-B GOLDEN (skips until the fixture is written)', () => {
  const g = (k: string) => () => GOLDEN![k];
  it.skipIf(!GOLDEN)('the golden carries the six served entries', () => {
    for (const k of ['default', 'w52_70', 'reclaimed', 'body10', 'sort_test', 'warming']) {
      expect(GOLDEN![k]?.doji_sweep_board, k).toBeTruthy();
    }
  });
  for (const k of ['default', 'w52_70', 'reclaimed', 'body10', 'sort_test']) {
    describe(k, () => readyCases(g(k), !GOLDEN));
  }
  describe('warming', () => warmingCases(g('warming'), !GOLDEN));

  it.skipIf(!GOLDEN)('the held-out fold follows the served suspects count', () => {
    const p = GOLDEN!.default;
    draw(p);
    const s = p.doji_sweep_board.suspects;
    if (s && s.n > 0) expect(screen.getByTestId('cm-dj-suspects').querySelector('summary')!.textContent).toBe(s.head);
    else expect(screen.queryByTestId('cm-dj-suspects')).toBeNull();
  });
});
