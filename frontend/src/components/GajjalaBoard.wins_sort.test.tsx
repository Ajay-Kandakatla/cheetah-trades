/**
 * ✅ wins first + the per-row ✅ / ❌ flags on the 🏁 Track record (2026-10-27).
 *
 * Ajay, verbatim (his spelling kept): "Can you sort the winds in Gajjals I can't seem to tell the difference in that tab or
 * show some greed flags on the wins rows". HIS CALL Q11 of docs/gajjala/track_record_2026_10_16.md answered — AMENDMENTS11
 * F13 (the hidden per-row chip, the planner's default) reversed by his word.
 *
 * The FE draws the SERVED flag (`flag_text`) on win / loss rows, tints every row by its SERVED bucket (a CSS hook), draws the
 * SERVED sort chips (their served labels) and reorders each served day's rows client-side over the SERVED `bucket_order`.
 * A chip click fetches nothing and `sort` never rides the 🏁 GET. NEGATIVES: no served chips → no chips and the served
 * order; an unknown URL sort → the served default; a row serving no flag → no chip; a row without a bucket sinks last and
 * keeps the bare row class; the served order is kept inside a bucket; the loss sub-line stays glued under its row.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import GajjalaBoard from './GajjalaBoard';
import { ggSortRows, ggTrRowClass, ggTrSort } from '../lib/gajjala';

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

/* ---- a 🏁 board shaped like the served payload (every word served; the FE composes none). ---- */
const SUBS = [
  ['bull_flag', '\u{1F6A9}', 'Bull Flag'], ['kiss_fly', '\u{1F48B}', 'EMA Kiss & Fly'], ['horizontal_fade', '➖', 'Horizontal Fade'],
  ['intraday_vcp', '\u{1F300}', 'Intraday VCP'], ['reversal_squeeze', '\u{1F3BE}', 'Reversal Squeeze'],
  ['premarket', '☀️', 'Premarket'], ['postmarket', '\u{1F319}', 'Post-market'], ['playbook', '\u{1F4D3}', 'Playbook'],
  ['potential', '\u{1F9E0}', 'Potential'], ['track_record', '\u{1F3C1}', 'Track record'],
].map(([key, emoji, label]) => ({ key, emoji, label, count: key === 'track_record' ? 6 : 0 }));
const SPANS = [{ key: 'today', label: 'Today' }, { key: '5d', label: 'Last 5 sessions' }];
const HEADS = [{ key: 'symbol', label: 'Ticker' }, { key: 'setup', label: 'Setup' }, { key: 'at', label: 'Alert' },
               { key: 'kind', label: 'Kind' }, { key: 'plan', label: 'Trigger → fill · stop' },
               { key: 'same', label: 'Same session' }, { key: 'next', label: 'Through next session' }];
const cell = (state: string, text: string, sub_text: string | null = null) => ({ state, text, sub_text, provisional: false });
/** One served row; `bucket` / `bucket_text` / `flag_text` exactly as ledger.served_block serves them. */
const row = (symbol: string, at_et: string, bucket: string | null, over: Record<string, unknown> = {}) => {
  const WORDS: Record<string, string> = { win: '✅ winner', loss: '❌ loser', open: '⏳ open', flat: '➖ flat', out: '— no fill / not graded' };
  const key = `2026-10-27-${symbol}-bull_flag-potential`;
  return {
    key, id: `2026-10-27|${symbol}|bull_flag|potential`, date: '2026-10-27', symbol, setup: 'bull_flag',
    setup_label: '\u{1F6A9} Bull Flag', kind: 'potential', line: 'live', kind_text: '\u{1F9E0} live', at_et,
    at_text: `${at_et} ET`, trigger: null, stop: null, fill_px: null, plan_text: 'trigger 1.00 · stop 0.90', note: null,
    href: `/chart-maps?tab=gajjala&sub=bull_flag&focus=${symbol}`, same: cell(bucket === 'out' ? 'no_entry' : bucket || 'open', bucket === 'win' ? 'WIN · best +9.0%' : bucket === 'loss' ? 'LOSS · best +1.0%' : 'no entry'),
    next: cell('pending', "after today's close", 'graded tonight 20:15 ET'), rang_text: null, thin_text: null, replay_text: null,
    bucket, bucket_text: bucket ? WORDS[bucket] : null,
    flag_text: bucket === 'win' || bucket === 'loss' ? WORDS[bucket] : null,
    loss_text: bucket === 'loss' ? 'stopped 14 min after the fill · filled 1 min after it rang' : null,
    broker_text: null, trader_text: null, ...over,
  };
};
/* The SERVED order (as rang): out · loss · win · open · win · (no bucket — an older row) */
const ROWS = [row('OUTA', '09:50', 'out'), row('LOSB', '10:05', 'loss'), row('WINC', '10:20', 'win'),
              row('OPND', '10:35', 'open'), row('WINE', '10:50', 'win'), row('NOBF', '11:05', null, { flag_text: null })];
const DAY = { date: '2026-10-27', label: 'Tue 2026-10-27 · today', more_n: null, rows: ROWS };
const SORTS = [{ key: 'wins', label: '✅ wins first', bucket_sort: true }, { key: 'rang', label: '🕰️ as rang', bucket_sort: false }];
const BUCKET_ORDER = ['win', 'loss', 'open', 'flat', 'out'];
const block = (over: Record<string, unknown> = {}) => ({
  title: "\u{1F3C1} Track record — every Gajjala alert that rang, graded by GG's trade math · UNMEASURED",
  rule_label: 'ⓘ how each alert is graded', rule_text: "GG's trade math (your answer, 2026-10-16).",
  honesty: 'A ledger of the alerts as sent, graded by GG\'s own trade math — not a backtest of a strategy, and small n early.',
  span: 'today', spans: SPANS, heads: HEADS,
  counts_text: { same: 'Same session: 2 wins · 1 loss · 67% won · 1 no entry · 1 open', next: 'Through next session: 0 wins · 0 losses · no graded entry yet' },
  shadow_text: null, entries_text: null, today_text: 'Today · through 11:10 ET · not final', days: [DAY], more_text: null,
  empty_text: null, grade_at_et: '20:15',
  categories: [{ key: 'all', text: '📋 all 6', n: 6 }, { key: 'win', text: '✅ winners 2', n: 2 }, { key: 'loss', text: '❌ losers 1', n: 1 }],
  category_param: 'cat', category_empty_text: 'No row in this category on this span.',
  sorts: SORTS, sort_param: 'sort', sort_default: 'wins', bucket_order: BUCKET_ORDER,
  ...over,
});
const board = (tr: any) => ({
  tab: 'gajjala', sub: 'track_record', tf: '5m', subs: SUBS,
  session: { date: '2026-10-27', label: 'Tue 2026-10-27', refresh_sec: 0 },
  pass: { as_of_et: '11:10 ET', stale: false, warming: false },
  tiles: [], note: 'UNMEASURED.', empty_note: null, rules_section: 'gajjala', track_record: tr,
});

type Call = { method: string; path: string; query: URLSearchParams };
let calls: Call[] = [];
function stub(b: any) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    calls.push({ method: String(init?.method || 'GET').toUpperCase(), path: u.pathname, query: u.searchParams });
    if (u.pathname.endsWith('/chart-maps/gajjala/scan')) {
      return { ok: true, status: 200, json: async () => ({ state: 'closed', latest_at: null, text: 'served closed line' }) };
    }
    return { ok: true, status: 200, json: async () => clone(b) };
  }));
}
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.endsWith('/chart-maps/gajjala'));

let loc = { search: '' };
function Probe() { loc = { search: useLocation().search }; return null; }
const mount = (q: string) => render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const shownKeys = () => within(screen.getByTestId('gg-track-record')).queryAllByTestId(/^gg-tr-row-/).map((r) => r.getAttribute('data-testid'));
const ids = (rows: any[]) => rows.map((r) => `gg-tr-row-${r.key}`);
const SERVED = ids(ROWS);
const WINS_FIRST = ids([ROWS[2], ROWS[4], ROWS[1], ROWS[3], ROWS[0], ROWS[5]]);

describe('🏁 ✅ wins first + row flags (2026-10-27)', () => {
  it('draws the served sort chips, the served default in force, the wins on top of the day, and the served flags', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    const chips = screen.getByTestId('gg-tr-sorts');
    expect([...chips.querySelectorAll('button')].map((b) => b.textContent)).toEqual(['✅ wins first', '🕰️ as rang']);
    expect(screen.getByTestId('gg-tr-sort-wins').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('gg-tr-sort-rang').getAttribute('aria-selected')).toBe('false');
    expect(shownKeys()).toEqual(WINS_FIRST);
    // the served flag, text exactly, win / loss rows only; the row tinted by the served bucket
    for (const r of ROWS) {
      const tr = screen.getByTestId(`gg-tr-row-${r.key}`);
      const flag = screen.queryByTestId(`gg-tr-flag-${r.key}`);
      if (r.bucket === 'win' || r.bucket === 'loss') {
        expect(flag, r.symbol).not.toBeNull();
        expect(flag!.textContent).toBe(r.flag_text);
        expect(flag!.className).toBe(`gg-tr-flag gg-tr-flag-${r.bucket}`);
        expect(flag!.closest('td')!.className).toContain('gg-tr-sym');
        expect(tr.className).toBe(`gg-tr-row gg-tr-row-${r.bucket}`);
      } else {
        expect(flag, `${r.symbol} must carry no flag`).toBeNull();                 // NEGATIVE
        expect(tr.className).toBe(r.bucket ? `gg-tr-row gg-tr-row-${r.bucket}` : 'gg-tr-row');
      }
    }
    // the ❌ row's served loss facts stay glued right under it after the reorder
    const lossLine = screen.getByTestId(`gg-tr-loss-${ROWS[1].key}`).closest('tr')!;
    expect(lossLine.previousElementSibling).toBe(screen.getByTestId(`gg-tr-row-${ROWS[1].key}`));
    // the counts / chips / title are untouched by the order
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(block().counts_text.same);
    // FE-only: ONE GET, and `sort` never rode it
    expect(gets()).toHaveLength(1);
    expect(gets()[0].query.get('sort')).toBeNull();
    expect(gets()[0].query.get('sub')).toBe('track_record');
    expect(document.body.textContent).not.toMatch(/NaN|undefined|null|\[object Object\]/);
  });

  it('a click on 🕰️ as rang restores the served order, writes ?sort=rang, and fetches nothing; wins first clears it', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(shownKeys()).toEqual(WINS_FIRST);
    fireEvent.click(screen.getByTestId('gg-tr-sort-rang'));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sort')).toBe('rang'));
    expect(shownKeys()).toEqual(SERVED);
    expect(screen.getByTestId('gg-tr-sort-rang').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('gg-tr-sort-wins').getAttribute('aria-selected')).toBe('false');
    expect(gets()).toHaveLength(1);                                                  // no refetch
    fireEvent.click(screen.getByTestId('gg-tr-sort-wins'));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sort')).toBeNull());  // the default = no param
    expect(shownKeys()).toEqual(WINS_FIRST);
    expect(gets()).toHaveLength(1);
    // the flags did not move off their rows
    expect(screen.getByTestId(`gg-tr-flag-${ROWS[2].key}`).textContent).toBe('✅ winner');
    expect(screen.getByTestId(`gg-tr-flag-${ROWS[1].key}`).textContent).toBe('❌ loser');
  });

  it('?sort=rang in the URL puts the served order in force; the span GET still carries no sort', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    expect(shownKeys()).toEqual(SERVED);
    expect(screen.getByTestId('gg-tr-sort-rang').getAttribute('aria-selected')).toBe('true');
    expect(gets()[0].query.get('sort')).toBeNull();
  });

  it('NEGATIVE: an unknown ?sort falls back to the served default (wins first) and never rides the GET', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record&sort=bogus');
    await loaded(container);
    expect(shownKeys()).toEqual(WINS_FIRST);
    expect(screen.getByTestId('gg-tr-sort-wins').getAttribute('aria-selected')).toBe('true');
    expect(gets()).toHaveLength(1);
    expect(gets()[0].query.get('sort')).toBeNull();
  });

  it('NEGATIVE: an older API without `sorts` draws no chips and keeps the served order — the tints and flags still draw', async () => {
    stub(board(block({ sorts: null, sort_param: null, sort_default: null, bucket_order: null })));
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(screen.queryByTestId('gg-tr-sorts')).toBeNull();
    expect(shownKeys()).toEqual(SERVED);
    expect(screen.getByTestId(`gg-tr-row-${ROWS[2].key}`).className).toBe('gg-tr-row gg-tr-row-win');
    expect(screen.getByTestId(`gg-tr-flag-${ROWS[2].key}`).textContent).toBe('✅ winner');
    expect(screen.queryByTestId(`gg-tr-flag-${ROWS[0].key}`)).toBeNull();
  });

  it('NEGATIVE: a served default that names no chip, or chips without labels, draw nothing and keep the served order', async () => {
    stub(board(block({ sort_default: 'nope', sorts: [{ key: 'wins', label: '', bucket_sort: true }] })));
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(screen.queryByTestId('gg-tr-sorts')).toBeNull();
    expect(shownKeys()).toEqual(SERVED);
  });

  it('the ✅ / ❌ category filter composes with the sort (the filtered rows keep the wins-first order)', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record&cat=win');
    await loaded(container);
    expect(shownKeys()).toEqual(ids([ROWS[2], ROWS[4]]));
    expect(screen.getByTestId('gg-tr-sort-wins').getAttribute('aria-selected')).toBe('true');
  });
});

describe('lib/gajjala — ggTrSort / ggSortRows / ggTrRowClass (2026-10-27)', () => {
  const tr = { sorts: SORTS, sort_default: 'wins' } as any;
  it('ggTrSort: the URL key when served, else the served default, else null (no key typed)', () => {
    expect(ggTrSort(null, tr)?.key).toBe('wins');
    expect(ggTrSort('rang', tr)?.key).toBe('rang');
    expect(ggTrSort('bogus', tr)?.key).toBe('wins');                                  // NEGATIVE: unknown → default
    expect(ggTrSort('rang', { sorts: SORTS, sort_default: null })?.key).toBe('rang');
    expect(ggTrSort(null, { sorts: SORTS, sort_default: null })).toBeNull();           // NEGATIVE: no default → served order
    expect(ggTrSort('wins', { sorts: null, sort_default: 'wins' })).toBeNull();        // NEGATIVE: no chips → null
    expect(ggTrSort('wins', null)).toBeNull();
    expect(ggTrSort('wins', { sorts: [{ key: '', label: 'x' } as any], sort_default: '' })).toBeNull();
  });
  it('ggSortRows: a stable sort by the served bucket order; unknown / missing buckets sink last; otherwise the SAME array', () => {
    const rows: any[] = ROWS.map((r) => ({ key: r.key, bucket: r.bucket }));
    const sorted = ggSortRows(rows, SORTS[0], BUCKET_ORDER);
    expect(sorted.map((r) => r.key)).toEqual([ROWS[2], ROWS[4], ROWS[1], ROWS[3], ROWS[0], ROWS[5]].map((r) => r.key));
    expect(ggSortRows(rows, SORTS[1], BUCKET_ORDER)).toBe(rows);                      // NEGATIVE: a non-bucket chip → same array
    expect(ggSortRows(rows, null, BUCKET_ORDER)).toBe(rows);
    expect(ggSortRows(rows, SORTS[0], null)).toBe(rows);                              // NEGATIVE: no served order → same array
    expect(ggSortRows(rows, SORTS[0], [])).toBe(rows);
    // an unknown bucket sinks last, after the known ones; the served order is kept inside a bucket
    const odd: any[] = [{ key: 'a', bucket: 'mystery' }, { key: 'b', bucket: 'out' }, { key: 'c', bucket: 'win' }, { key: 'd', bucket: 'win' }];
    expect(ggSortRows(odd, SORTS[0], BUCKET_ORDER).map((r) => r.key)).toEqual(['c', 'd', 'b', 'a']);
    expect(ggSortRows([], SORTS[0], BUCKET_ORDER)).toEqual([]);
    expect(rows.map((r) => r.key)).toEqual(ROWS.map((r) => r.key));                    // the input was never mutated
  });
  it('ggTrRowClass: the bucket as a CSS hook, the bare class without one', () => {
    expect(ggTrRowClass({ bucket: 'win' })).toBe('gg-tr-row gg-tr-row-win');
    expect(ggTrRowClass({ bucket: 'loss' })).toBe('gg-tr-row gg-tr-row-loss');
    expect(ggTrRowClass({ bucket: null })).toBe('gg-tr-row');
    expect(ggTrRowClass({ bucket: '  ' })).toBe('gg-tr-row');
    expect(ggTrRowClass(null)).toBe('gg-tr-row');
  });
});
