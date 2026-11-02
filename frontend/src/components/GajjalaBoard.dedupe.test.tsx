/**
 * 🔁 One count per stock per day on the 🏁 Track record (2026-11-02) + the shared 🏁 pieces Luk's 🏁 draws through.
 *
 * Ajay, verbatim: "Can you make Luk's track record similar to Gajjal's and also can you make sure you are not accounting
 * for duplicates of the same stock as winner unless it did the same pattern again and met all the criteria on the same
 * day".
 *
 * The FE composes nothing: a served duplicate (`dup_of` + the served `dup_text`) draws the served 🔁 chip in the Ticker
 * cell, serves no ✅ / ❌ flag, carries the `gg-tr-row-dup` hook, sinks last under ✅ wins first and is hidden under a
 * bucket chip (it is not counted there) while "📋 all" lists it. The generic TrRowCells branch draws a served cell under
 * any head key the switch does not name (Luk's `fill` / `exit`). The pieces are exported with a trailing `export { … }`.
 * NEGATIVES: no `dup_text` → no chip; a blank `dup_text` → no chip; the chip text is byte-equal to the served string; a
 * head with no served cell → an empty td; the filter off → the SAME days array; the Luk tape route never names /gajjala.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GajjalaBoard, { TrCell, TrRowCells, GgTrCats, GgTrSorts, GgTrViews, GgTrHead, GgTrTapeRow, ggTrTapeAt } from './GajjalaBoard';
import { GgVariantContext } from './ggVariant';
import { _resetGgLiteCache } from './GgEntryTape';
import { ggCatDays, ggSortRows, ggTrIsDup, ggTrRowClass, type GgTrRow } from '../lib/gajjala';

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); _resetGgLiteCache(); });

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const root = (globalThis as any).process?.cwd?.() || '.';
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));     // tsc-safe (the GgEntryTape.test precedent)
  return (mod?.default || mod).readFileSync(`${root}/${rel}`, 'utf8');
}

const SUBS = [
  ['bull_flag', '\u{1F6A9}', 'Bull Flag'], ['kiss_fly', '\u{1F48B}', 'EMA Kiss & Fly'], ['horizontal_fade', '➖', 'Horizontal Fade'],
  ['intraday_vcp', '\u{1F300}', 'Intraday VCP'], ['reversal_squeeze', '\u{1F3BE}', 'Reversal Squeeze'],
  ['premarket', '☀️', 'Premarket'], ['postmarket', '\u{1F319}', 'Post-market'], ['playbook', '\u{1F4D3}', 'Playbook'],
  ['potential', '\u{1F9E0}', 'Potential'], ['track_record', '\u{1F3C1}', 'Track record'],
].map(([key, emoji, label]) => ({ key, emoji, label, count: key === 'track_record' ? 4 : 0 }));
const HEADS = [{ key: 'symbol', label: 'Ticker' }, { key: 'setup', label: 'Setup' }, { key: 'at', label: 'Alert' },
               { key: 'kind', label: 'Kind' }, { key: 'plan', label: 'Trigger → fill · stop' },
               { key: 'same', label: 'Same session' }, { key: 'next', label: 'Through next session' }];
const cell = (state: string, text: string, sub_text: string | null = null) => ({ state, text, sub_text, provisional: false });
const WORDS: Record<string, string> = { win: '✅ winner', loss: '❌ loser', open: '⏳ open', out: '— no fill / not graded' };
/** One served row as ledger.served_block serves it; a duplicate serves `dup_of` + `dup_text` and NO flag. */
const row = (symbol: string, setup: string, at_et: string, bucket: string, over: Record<string, unknown> = {}) => {
  const id = `2026-10-16|${symbol}|${setup}|potential`;
  return {
    key: id.split('|').join('-'), id, date: '2026-10-16', symbol, setup, setup_label: `served ${setup}`, kind: 'potential',
    line: 'live', kind_text: '\u{1F9E0} live', at_et, at_text: `${at_et} ET`, trigger: null, stop: null, fill_px: null,
    plan_text: 'trigger 1.89 · stop 1.80', note: null, href: `/chart-maps?tab=gajjala&sub=${setup}&focus=${symbol}`,
    same: cell(bucket === 'out' ? 'no_entry' : bucket, bucket === 'win' ? 'WIN · best +9.0%' : bucket === 'loss' ? 'LOSS' : 'no entry'),
    next: cell('pending', "after today's close"), rang_text: null, thin_text: null, replay_text: null,
    bucket, bucket_text: WORDS[bucket], flag_text: bucket === 'win' || bucket === 'loss' ? WORDS[bucket] : null,
    loss_text: null, broker_text: null, trader_text: null, dup_of: null, dup_text: null, ...over,
  };
};
const DUP_TEXT = '🔁 same trade as the 08:51 ➖ Horizontal Fade ring — not counted';
/* SERVED order (as rang, desc): the 🌀 duplicate WIN (XLAB 10-16 class), a loss, the counted ➖ WIN, an out. */
const COUNTED = row('XLAB', 'horizontal_fade', '08:51', 'win');
const DUP = row('XLAB', 'intraday_vcp', '09:01', 'win', { flag_text: null, dup_of: COUNTED.id, dup_text: DUP_TEXT });
const LOSS = row('LOSB', 'bull_flag', '10:05', 'loss');
const OUT = row('OUTA', 'kiss_fly', '11:00', 'out');
const ROWS = [OUT, LOSS, DUP, COUNTED];
const SORTS = [{ key: 'wins', label: '✅ wins first', bucket_sort: true }, { key: 'rang', label: '🕰️ as rang', bucket_sort: false }];
const BUCKET_ORDER = ['win', 'loss', 'open', 'flat', 'out'];
const block = (over: Record<string, unknown> = {}) => ({
  title: 'served 🏁 title · UNMEASURED', rule_label: 'ⓘ served', rule_text: 'served rule text', honesty: 'served honesty',
  span: 'today', spans: [{ key: 'today', label: 'Today' }], heads: HEADS,
  counts_text: { same: 'Same session: 1 win · 1 loss · 50% won · 1 no entry · 1 duplicate of the same stock not counted', next: 'served next line' },
  shadow_text: null, entries_text: null, today_text: null, more_text: null, empty_text: null, grade_at_et: '20:15',
  days: [{ date: '2026-10-16', label: 'Fri 10-16', more_n: null, rows: ROWS }],
  categories: [{ key: 'all', text: '📋 all 4', n: 4 }, { key: 'win', text: '✅ winners 1', n: 1 }, { key: 'loss', text: '❌ losers 1', n: 1 }],
  category_param: 'cat', category_empty_text: 'served empty category', dup_counts: { live: 1 },
  sorts: SORTS, sort_param: 'sort', sort_default: 'wins', bucket_order: BUCKET_ORDER, ...over,
});
const board = (tr: any) => ({
  tab: 'gajjala', sub: 'track_record', tf: '5m', subs: SUBS,
  session: { date: '2026-10-16', label: 'Fri 2026-10-16', refresh_sec: 0 },
  pass: { as_of_et: '11:10 ET', stale: false, warming: false },
  tiles: [], note: 'UNMEASURED.', empty_note: null, rules_section: 'gajjala', track_record: tr,
});
function stub(b: any) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    if (u.pathname.endsWith('/scan')) return { ok: true, status: 200, json: async () => ({ state: 'closed', latest_at: null, text: 'served' }) };
    return { ok: true, status: 200, json: async () => clone(b) };
  }));
}
const mount = (q: string) => render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const shownKeys = () => within(screen.getByTestId('gg-track-record')).queryAllByTestId(/^gg-tr-row-/).map((r) => r.getAttribute('data-testid'));
const tid = (r: { key: string }) => `gg-tr-row-${r.key}`;

describe('🔁 one count per stock per day — the served duplicate on the 🏁 list (2026-11-02)', () => {
  it('a served dup row draws the served 🔁 chip in the Ticker cell (byte-equal), no ✅ flag, class gg-tr-row-dup', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    const chip = screen.getByTestId(`gg-tr-dup-${DUP.key}`);
    expect(chip.textContent).toBe(DUP_TEXT);                                                // NEGATIVE: nothing composed
    expect(chip.className).toBe('gg-tr-chip gg-tr-dup');
    expect(chip.closest('td')!.className).toBe('gg-tr-sym');                                 // the Ticker cell
    expect(screen.queryByTestId(`gg-tr-flag-${DUP.key}`)).toBeNull();                         // a dup serves no flag
    const tr = screen.getByTestId(tid(DUP));
    expect(tr.className).toBe('gg-tr-row gg-tr-row-win gg-tr-row-dup');
    // the counted twin keeps its flag and its plain tint
    expect(screen.getByTestId(`gg-tr-flag-${COUNTED.key}`).textContent).toBe(WORDS.win);
    expect(screen.getByTestId(tid(COUNTED)).className).toBe('gg-tr-row gg-tr-row-win');
  });
  it('NEGATIVE: a row with no dup_text (null / absent / blank) draws no chip and no -dup class', async () => {
    const blank = row('BLNK', 'bull_flag', '12:00', 'loss', { dup_text: '   ' });
    const absent = row('ABSN', 'bull_flag', '12:05', 'win');
    delete (absent as any).dup_text; delete (absent as any).dup_of;
    stub(board(block({ days: [{ date: '2026-10-16', label: 'Fri 10-16', more_n: null, rows: [...ROWS, blank, absent] }] })));
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    for (const r of [COUNTED, LOSS, OUT, blank, absent]) {
      expect(screen.queryByTestId(`gg-tr-dup-${r.key}`), r.symbol).toBeNull();
      expect(screen.getByTestId(tid(r)).className.includes('gg-tr-row-dup'), r.symbol).toBe(false);
    }
    expect(container.querySelectorAll('.gg-tr-dup').length).toBe(1);
  });
  it('✅ wins first sinks the duplicate LAST (after the out row), the counted win stays on top', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(shownKeys()).toEqual([COUNTED, LOSS, OUT, DUP].map(tid));
  });
  it('🕰️ as rang keeps the served order (the dup in its served place)', async () => {
    stub(board(block()));
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    expect(shownKeys()).toEqual(ROWS.map(tid));
  });
  it('under ?cat=win the duplicate is hidden (not counted there); under 📋 all every row is listed', async () => {
    stub(board(block()));
    const r1 = mount('tab=gajjala&sub=track_record&cat=win');
    await loaded(r1.container);
    expect(shownKeys()).toEqual([tid(COUNTED)]);
    expect(screen.queryByTestId(`gg-tr-dup-${DUP.key}`)).toBeNull();
    r1.unmount();
    const r2 = mount('tab=gajjala&sub=track_record&cat=all');
    await loaded(r2.container);
    expect(shownKeys()).toEqual([COUNTED, LOSS, OUT, DUP].map(tid));
  });
});

describe('lib/gajjala — the duplicate in ggCatDays / ggSortRows / ggTrRowClass (2026-11-02)', () => {
  const cats = [{ key: 'all', text: 'a', n: 4 }, { key: 'win', text: 'w', n: 1 }, { key: 'loss', text: 'l', n: 1 }];
  const days = [{ date: '2026-10-16', label: 'x', rows: ROWS as unknown as GgTrRow[] }];
  it('ggCatDays: a bucket chip drops the dup; off (null / all / unknown / no chips) → the SAME array', () => {
    expect(ggCatDays(days, 'win', cats)[0].rows.map((r) => r.key)).toEqual([COUNTED.key]);
    expect(ggCatDays(days, null, cats)).toBe(days);
    expect(ggCatDays(days, 'all', cats)).toBe(days);
    expect(ggCatDays(days, 'bogus', cats)).toBe(days);
    expect(ggCatDays(days, 'win', null)).toBe(days);
    // a day left with only a dup under a chip is dropped
    const onlyDup = [{ date: '2026-10-16', label: 'x', rows: [DUP] as unknown as GgTrRow[] }];
    expect(ggCatDays(onlyDup, 'win', cats)).toEqual([]);
  });
  it('ggSortRows: a dup sinks last under a bucket sort, served order kept among dups; a non-bucket chip → the SAME array', () => {
    const dup2 = { ...LOSS, key: 'dup2', dup_of: LOSS.id };
    const rows = [DUP, OUT, dup2, LOSS, COUNTED] as unknown as GgTrRow[];
    expect(ggSortRows(rows, SORTS[0], BUCKET_ORDER).map((r) => r.key)).toEqual([COUNTED.key, LOSS.key, OUT.key, DUP.key, 'dup2']);
    expect(ggSortRows(rows, SORTS[1], BUCKET_ORDER)).toBe(rows);
    // NEGATIVE: a blank dup_of is not a duplicate
    const blank = [{ key: 'b', bucket: 'win', dup_of: '  ' }, { key: 'l', bucket: 'loss', dup_of: null }] as unknown as GgTrRow[];
    expect(ggSortRows(blank, SORTS[0], BUCKET_ORDER).map((r) => r.key)).toEqual(['b', 'l']);
  });
  it('ggTrRowClass / ggTrIsDup: -dup only on a non-empty dup_of', () => {
    expect(ggTrRowClass({ bucket: 'win', dup_of: 'x|Y|z|potential' })).toBe('gg-tr-row gg-tr-row-win gg-tr-row-dup');
    expect(ggTrRowClass({ bucket: null, dup_of: 'x' })).toBe('gg-tr-row gg-tr-row-dup');
    expect(ggTrRowClass({ bucket: 'win', dup_of: null })).toBe('gg-tr-row gg-tr-row-win');           // NEGATIVE
    expect(ggTrRowClass({ bucket: 'win', dup_of: ' ' })).toBe('gg-tr-row gg-tr-row-win');            // NEGATIVE
    expect(ggTrIsDup({ dup_of: undefined })).toBe(false);
    expect(ggTrIsDup(null)).toBe(false);
  });
});

describe('the shared 🏁 pieces — trailing export + the generic served-cell branch (2026-11-02)', () => {
  it('every piece Luk draws through is exported; the declarations stay `\\nfunction NAME(` (the contract scanners)', async () => {
    for (const f of [TrCell, TrRowCells, GgTrCats, GgTrSorts, GgTrViews, GgTrHead, GgTrTapeRow, ggTrTapeAt]) expect(typeof f).toBe('function');
    const src = await readSource('src/components/GajjalaBoard.tsx');
    for (const n of ['TrCell', 'TrRowCells', 'GgTrCats', 'GgTrSorts', 'GgTrViews', 'GgTrHead', 'GgTrTapeRow', 'ggTrTapeAt']) {
      expect(src.includes(`\nfunction ${n}(`), n).toBe(true);
      expect(src.includes(`export function ${n}(`), n).toBe(false);                           // NEGATIVE
    }
    expect(src).toMatch(/\nexport \{ TrCell, TrRowCells, GgTrCats, GgTrSorts, GgTrViews, GgTrHead, GgTrTapeRow, ggTrTapeAt \};\n$/);
    expect(ggTrTapeAt(HEADS)).toBe(1);
  });
  const cells = (r: any, heads: string[]) => render(
    <MemoryRouter><table><tbody><tr>{heads.map((h) => <TrRowCells key={h} row={r} head={h} />)}</tr></tbody></table></MemoryRouter>);
  it('a head whose row value is a served cell (Luk `fill` / `exit`) draws TrCell with the served text + sub line', () => {
    const r = { ...COUNTED, fill: cell('win', 'filled 1.89 at 09:45', 'served sub'), exit: cell('loss', 'stopped 13.96') };
    cells(r, ['fill', 'exit']);
    const f = screen.getByTestId(`gg-tr-fill-${r.key}`);
    expect(f.tagName).toBe('TD');
    expect(f.textContent).toBe('filled 1.89 at 09:45served sub');
    expect(f.className).toBe('gg-tr-cell gg-tr-win');
    expect(screen.getByTestId(`gg-tr-exit-${r.key}`).textContent).toBe('stopped 13.96');
  });
  it('NEGATIVE: a head with no served cell (absent / a string / null / a cell-less object) draws an empty td', () => {
    const r = { ...COUNTED, fill: null, exit: { state: 'win' }, date: '2026-10-16' };
    const { container } = cells(r, ['fill', 'exit', 'date', 'nothing_here']);
    const tds = [...container.querySelectorAll('td')];
    expect(tds.length).toBe(4);
    for (const td of tds) { expect(td.textContent).toBe(''); expect(td.getAttribute('data-testid')).toBeNull(); }
  });
  it("GgTrTapeRow under GgVariantContext 'luk' fetches the mini tape on Luk's route only; NEGATIVE: never /gajjala", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ id: COUNTED.id, bars: [], rules: [] }) }));
    vi.stubGlobal('fetch', fetchMock);
    const views = { param: 'view', default: 'list', items: [], kinds: ['aplus'], empty_text: '', tape_head: 'Tape',
                    tape_toggle: '📈', tape_toggle_title: 'served toggle title' };
    render(
      <MemoryRouter><GgVariantContext.Provider value="luk"><table>
        <GgTrHead heads={HEADS} views={views} at={ggTrTapeAt(HEADS)} />
        <tbody><GgTrTapeRow row={COUNTED as any} heads={HEADS} views={views} at={ggTrTapeAt(HEADS)} tid="luk-tr" /></tbody>
      </table></GgVariantContext.Provider></MemoryRouter>);
    expect(screen.getByTestId(`luk-tr-row-${COUNTED.key}`)).toBeTruthy();
    expect([...document.querySelectorAll('th')].map((t) => t.textContent)[1]).toBe('Tape');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const urls = fetchMock.mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.every((u) => u.includes(`/chart-maps/luk/entry-tape?id=${encodeURIComponent(COUNTED.id)}&lite=1`))).toBe(true);
    expect(urls.some((u) => u.includes('/gajjala'))).toBe(false);
  });
});

describe('gajjala.css — the duplicate row (2026-11-02)', () => {
  it('drops the tint AFTER the win / loss tint rules; the chip wraps', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const dup = css.indexOf('.gg-tr-table tr.gg-tr-row-dup > td {');
    expect(dup).toBeGreaterThan(css.indexOf('.gg-tr-table tr.gg-tr-row-win > td {'));
    expect(dup).toBeGreaterThan(css.indexOf('.gg-tr-table tr.gg-tr-row-loss > td:first-child {'));
    expect(css.slice(dup, css.indexOf('}', dup))).toMatch(/background: none;[^}]*opacity: 0\.65;[^}]*box-shadow: none;/);
    expect(css).toMatch(/\.gg-tr-table tr\.gg-tr-row-dup > td:first-child \{ box-shadow: none; \}/);
    expect(css).toMatch(/\.gg-tr-dup \{[^}]*white-space: normal;[^}]*overflow-wrap: anywhere;/);
  });
});
