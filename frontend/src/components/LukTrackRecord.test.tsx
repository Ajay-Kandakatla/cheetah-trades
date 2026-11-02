import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LukTrackRecord } from './LukTrackRecord';
import { _resetGgLiteCache } from './GgEntryTape';
import type { LukTrackRecord as LukTr, LukTrRow } from '../lib/luk';
import type { GgTrAplus, GgTrCell } from '../lib/gajjala';

/* 🥇 Luk's 🏁 Track record — 2026-11-02 rewrite on 🚩's SHARED 🏁 pieces (spec luk-track §3.5, WP-D).
 * Ajay 2026-11-02: "Can you make Luk's track record similar to Gajjal's and also can you make sure you are not
 * accounting for duplicates of the same stock as winner unless it did the same pattern again and met all the criteria
 * on the same day".
 *
 * SYNTHETIC block in the backend luk/ledger.served_block shape (§3.3.4-§3.3.7): served chips, served sorts (✅ wins first
 * by default), served heads with the served Tape head SECOND, served fill / exit cells, the ✅ / ❌ flags, the 🔁 duplicate
 * chip (the VG 11-03 shape: 🔔 09:46 behind ↩️ 09:41, both stopped), the served more line, the charts block, honesty last.
 * The mini tape fetches the LUK lite route on mount (jsdom has no IntersectionObserver), 📈 the LUK full route.
 * NEGATIVES: never a 🚩 route; an older block (no heads / views / charts) never throws; no number the payload lacks;
 * no b-word; `more_text` null → no line; a dup row carries no flag and leaves a bucket chip. */

const ID_A = '2026-11-03|AAA|pullback_reversal|aplus';
const ID_V1 = '2026-11-03|VG|pullback_reversal|aplus';
const ID_V2 = '2026-11-03|VG|opening_range_high|aplus';
const ID_C = '2026-11-04|CCC|inside_day_pdh|aplus';
const key = (id: string) => id.replace(/\|/g, '-');
const cell = (state: string, text: string, sub_text: string | null = null): GgTrCell => ({ state, text, sub_text, provisional: false });
const NO_CELL = null as unknown as GgTrCell;

const row = (id: string, symbol: string, setup: string, setup_label: string, at_et: string, extra: Partial<LukTrRow>): LukTrRow => ({
  id, key: key(id), date: id.slice(0, 10), symbol, setup, setup_label, kind: 'aplus', line: 'live',
  kind_text: '🥇 A+ — sent to your phone', at_et, at_text: `${at_et} ET`, rang: 'rth', rang_text: 'rang RTH', thin_text: null,
  href: `/chart-maps?tab=luk&focus=${symbol}`, note: null, loss_text: null, broker_text: null, trader_text: null,
  dup_of: null, dup_text: null, same: NO_CELL, next: NO_CELL, ...extra,
} as LukTrRow);

const ROW_A = row(ID_A, 'AAA', 'pullback_reversal', '↩️ Pullback reversal', '10:06', {
  plan_text: 'trigger 12.40 · stop 11.98 (−3.4%) · R $0.42',
  fill: cell('filled', 'filled 12.41 at 10:07'), exit: cell('win', 'closed below the 9 EMA on 11-05 · +2.3R · 3 sessions', '+3R reached'),
  bucket: 'win', bucket_text: '✅ winner', flag_text: '✅ winner',
});
const ROW_V2 = row(ID_V2, 'VG', 'opening_range_high', '🔔 Opening range', '09:46', {
  plan_text: 'trigger 14.80 · stop 13.96 (−5.7%) · R $0.84',
  fill: cell('filled', 'filled 14.81 at 09:47'), exit: cell('loss', 'stopped 15:06 · −1.0R'),
  bucket: 'loss', bucket_text: '❌ loser', flag_text: null,
  dup_of: ID_V1, dup_text: '🔁 same trade as the 09:41 ↩️ Pullback reversal ring — not counted',
});
const ROW_V1 = row(ID_V1, 'VG', 'pullback_reversal', '↩️ Pullback reversal', '09:41', {
  plan_text: 'trigger 14.60 · stop 13.96 (−4.4%) · R $0.64',
  fill: cell('filled', 'filled 14.61 at 09:42'), exit: cell('loss', 'stopped 15:06 · −1.0R'),
  bucket: 'loss', bucket_text: '❌ loser', flag_text: '❌ loser',
});
const ROW_C = row(ID_C, 'CCC', 'inside_day_pdh', '📦 Inside day', '13:10', {
  plan_text: 'trigger 30.00 · stop 29.10 (−3.0%) · R $0.90',
  fill: cell('filled', 'filled 30.02 at 13:11'), exit: cell('open', 'open · +0.8R after 2 sessions'),
  bucket: 'open', bucket_text: '⏳ open', flag_text: null,
});

const CHARTS = {
  title: "🥇 A+ wins vs losses — every 🥇 A+ on the span, graded by Luk's exit · UNMEASURED",
  total: 4, n_sent: 4, n_shadow: 0, n_dup: 1,
  counts: { exit: { win: 1, loss: 1, open: 1, flat: 0, no_entry: 0, no_plan: 0, no_risk: 0, no_time: 0, pending: 0, thin: 0, pct: 50 } },
  counts_text: { exit: "A+ through Luk's exit: 1 win · 1 loss · 50% won · 1 open · 1 duplicate of the same stock not counted" },
  split_text: '4 sent to your phone', replayed_note: null, more_text: null, empty_text: null,
  honesty: "Every 🥇 A+ on the span — sent or recorded in shadow — in one %, graded by Luk's exit. UNMEASURED.",
  horizons: [], horizon_default: 'exit', days: [],
  charts: [{ key: 'outcomes', title: '🥇 A+ wins vs losses', bars: [
    { key: 'exit', label: "Through Luk's exit (the stop or the first daily close below the 9 EMA)", total: 3, decided: 2, pct: 50,
      loss_pct: 50, pct_text: '50% won · 2 decided', text: '1 win · 1 loss · 50% won · 1 open', short_text: '1W 1L', items: [
        { key: 'win', label: 'wins', n: 1, text: '1 win (50% of the 2 decided)' },
        { key: 'loss', label: 'losses', n: 1, text: '1 loss (50% of the 2 decided)' },
        { key: 'open', label: 'open', n: 1, text: '1 open' }] }] }],
} as unknown as GgTrAplus;

const TR: LukTr = {
  title: "🏁 Track record — every 🥇 A+ recorded here since 2026-11-01, graded by Luk's trade math · UNMEASURED",
  rule_text: 'Fill = the first 1-minute bar at least 30 s after the alert trading at or above the trigger. Exit = the stop or the first daily close below the 9 EMA.',
  honesty: 'Every row rang your phone since 2026-11-01. UNMEASURED until the strategy lab\'s 30-entry-week floor (1 entry weeks so far).',
  counts_text: '4 A+ recorded · 3 filled · 1 stopped · 1 closed below the 9 EMA · 1 open · 1 duplicate of the same stock not counted',
  counts: { n: 4, dup: 1, filled: 3, stopped: 1, open: 1 },
  spans: [{ key: 'today', label: 'today' }, { key: '5d', label: '5 sessions' }, 'all'], span: '5d',
  heads: [{ key: 'symbol', label: 'Ticker' }, { key: 'setup', label: 'Setup' }, { key: 'at', label: 'Alert' },
          { key: 'kind', label: 'Kind' }, { key: 'plan', label: 'Trigger · stop · R' }, { key: 'fill', label: 'Fill' },
          { key: 'exit', label: 'Exit · R · sessions' }],
  views: { param: 'view', default: 'all', items: [], kinds: ['aplus'], empty_text: '', tape_head: 'Tape', tape_toggle: '📈',
           tape_toggle_title: 'the full tape — the alert, the fill, the trigger / stop, the exit and the +3R / +5R marks' },
  categories: [{ key: 'all', text: '📋 all 4', n: 4 }, { key: 'win', text: '✅ winners 1', n: 1 },
               { key: 'loss', text: '❌ losers 1', n: 1 }, { key: 'open', text: '⏳ open 1', n: 1 },
               { key: 'flat', text: '➖ flat 0', n: 0 }, { key: 'out', text: '— no fill / not graded 0', n: 0 }],
  category_param: 'cat', category_empty_text: 'No row in this category on this span.',
  sorts: [{ key: 'wins', label: '✅ wins first', bucket_sort: true }, { key: 'rang', label: '🕰️ as rang', bucket_sort: false }],
  sort_param: 'sort', sort_default: 'wins', bucket_order: ['win', 'loss', 'open', 'flat', 'out'],
  charts: CHARTS, more_text: null, empty_text: 'No 🥇 A+ in this span — none rang, none was recorded.',
  days: [
    { date: '2026-11-04', label: 'Wed 11-04', rows: [ROW_C] },
    { date: '2026-11-03', label: 'Tue 11-03', rows: [ROW_A, ROW_V2, ROW_V1] },
  ],
};

const TAPE = { id: ID_A, ticker: 'AAA', tf: '5m', lite: false, n_bars: 2, title: 'AAA tape', tone: 'up', note: null,
  aria: 'AAA entry tape', as_of: '2026-11-05', read: 'filled 12.41 · closed below the 9 EMA · +2.3R',
  bars: [{ t: 1762180200, c: 12.4, s: 'rth' }, { t: 1762180500, c: 12.6, s: 'rth' }], rules: [], dots: [], hlines: [] };

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.search}</output>;
}
const mount = (t: LukTr | null, path = '/chart-maps?tab=luk&sub=track_record&span=5d') =>
  render(<MemoryRouter initialEntries={[path]}><LukTrackRecord track={t} /><Where /></MemoryRouter>);
const q = () => new URLSearchParams(screen.getByTestId('where').textContent || '');
const rowOrder = (day: string) => Array.from(screen.getByTestId(`luk-tr-day-${day}`).parentElement!
  .querySelectorAll('tr[data-testid^="luk-tr-row-"]')).map((r) => r.getAttribute('data-testid'));

let fetchMock: ReturnType<typeof vi.fn>;
const urls = () => fetchMock.mock.calls.map((c) => String((c as unknown[])[0]));

describe('LukTrackRecord — 🚩\'s 🏁 on the 🥇 block', () => {
  beforeEach(() => {
    _resetGgLiteCache();
    // Every test stubs fetch (the mini tape reads on mount); a read that never settles keeps the DOM still.
    fetchMock = vi.fn(() => new Promise(() => {}));
    vi.stubGlobal('fetch', fetchMock);
  });
  const serveTape = () => {
    fetchMock = vi.fn(async (u: string) => ({ ok: true, status: 200,
      json: async () => ({ ...JSON.parse(JSON.stringify(TAPE)), lite: String(u).includes('lite=1') }) }));
    vi.stubGlobal('fetch', fetchMock);
  };
  afterEach(() => { vi.unstubAllGlobals(); _resetGgLiteCache(); });

  it('🚩\'s order: title → spans → chips → sorts → counts → charts → days → rule → honesty LAST', () => {
    const { container } = mount(TR);
    const sec = screen.getByTestId('luk-tr');
    expect(sec.className).toContain('gg-track-record');
    const order = Array.from(sec.querySelectorAll('[data-testid]')).map((e) => e.getAttribute('data-testid'))
      .filter((t) => ['luk-tr-title', 'luk-tr-spans', 'gg-tr-cats', 'gg-tr-sorts', 'luk-tr-counts', 'gg-ap',
        'luk-tr-day-2026-11-04', 'luk-tr-day-2026-11-03', 'luk-tr-rule', 'luk-tr-honesty'].includes(t!));
    expect(order).toEqual(['luk-tr-title', 'luk-tr-spans', 'gg-tr-cats', 'gg-tr-sorts', 'luk-tr-counts', 'gg-ap',
      'luk-tr-day-2026-11-04', 'luk-tr-day-2026-11-03', 'luk-tr-rule', 'luk-tr-honesty']);
    expect(sec.lastElementChild).toBe(screen.getByTestId('luk-tr-honesty'));
    expect(screen.getByTestId('luk-tr-title')).toHaveTextContent(TR.title);
    expect(screen.getByTestId('luk-tr-counts')).toHaveTextContent(TR.counts_text!);
    expect(screen.getByTestId('luk-tr-honesty')).toHaveTextContent(TR.honesty!);
    const rule = screen.getByTestId('luk-tr-rule') as HTMLDetailsElement;
    expect(rule.open).toBe(false);
    expect(rule).toHaveTextContent(TR.rule_text!);
    expect(container.querySelector('.luk-tr .gg-tr-scroll > table.gg-tr-table.luk-tr-table')).not.toBeNull();
  });

  it('the served category and sort chips, their served texts; wins first is the served default', () => {
    mount(TR);
    for (const c of TR.categories!) expect(screen.getByTestId(`gg-tr-cat-${c.key}`)).toHaveTextContent(c.text);
    for (const s of TR.sorts!) expect(screen.getByTestId(`gg-tr-sort-${s.key}`)).toHaveTextContent(s.label);
    expect(screen.getByTestId('gg-tr-cat-all').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('gg-tr-sort-wins').getAttribute('aria-selected')).toBe('true');
  });

  it('table heads = the served heads with the served Tape head SECOND', () => {
    mount(TR);
    const ths = Array.from(screen.getByTestId('luk-tr-day-2026-11-03').parentElement!.querySelectorAll('thead th'))
      .map((t) => t.textContent);
    expect(ths).toEqual(['Ticker', 'Tape', 'Setup', 'Alert', 'Kind', 'Trigger · stop · R', 'Fill', 'Exit · R · sessions']);
  });

  it('rows: wins first by default (the dup sinks last); ?sort=rang = the served order; a sort click writes / clears the param', () => {
    mount(TR);
    expect(rowOrder('2026-11-03')).toEqual([`luk-tr-row-${key(ID_A)}`, `luk-tr-row-${key(ID_V1)}`, `luk-tr-row-${key(ID_V2)}`]);
    fireEvent.click(screen.getByTestId('gg-tr-sort-rang'));
    expect(q().get('sort')).toBe('rang');
    expect(rowOrder('2026-11-03')).toEqual([`luk-tr-row-${key(ID_A)}`, `luk-tr-row-${key(ID_V2)}`, `luk-tr-row-${key(ID_V1)}`]);
    fireEvent.click(screen.getByTestId('gg-tr-sort-wins'));
    expect(q().has('sort')).toBe(false);
    expect(q().get('span')).toBe('5d');
  });

  it('?sort=rang on mount keeps the served order', () => {
    mount(TR, '/chart-maps?tab=luk&sub=track_record&sort=rang');
    expect(rowOrder('2026-11-03')).toEqual([`luk-tr-row-${key(ID_A)}`, `luk-tr-row-${key(ID_V2)}`, `luk-tr-row-${key(ID_V1)}`]);
    expect(screen.getByTestId('gg-tr-sort-rang').getAttribute('aria-selected')).toBe('true');
  });

  it('fill / exit cells print the served texts; a win row carries its flag + tint; a dup row its chip and NO flag', () => {
    mount(TR);
    expect(screen.getByTestId(`gg-tr-fill-${key(ID_A)}`)).toHaveTextContent('filled 12.41 at 10:07');
    expect(screen.getByTestId(`gg-tr-exit-${key(ID_A)}`)).toHaveTextContent('closed below the 9 EMA on 11-05 · +2.3R · 3 sessions');
    expect(screen.getByTestId(`gg-tr-exit-${key(ID_A)}`)).toHaveTextContent('+3R reached');
    expect(screen.getByTestId(`gg-tr-exit-${key(ID_C)}`)).toHaveTextContent('open · +0.8R after 2 sessions');
    expect(screen.getByTestId(`gg-tr-flag-${key(ID_A)}`)).toHaveTextContent('✅ winner');
    expect(screen.getByTestId(`luk-tr-row-${key(ID_A)}`).className).toContain('gg-tr-row-win');
    expect(screen.getByTestId(`gg-tr-flag-${key(ID_V1)}`)).toHaveTextContent('❌ loser');
    expect(screen.getByTestId(`gg-tr-dup-${key(ID_V2)}`).textContent).toBe(ROW_V2.dup_text);
    expect(screen.queryByTestId(`gg-tr-flag-${key(ID_V2)}`)).toBeNull();
    expect(screen.getByTestId(`luk-tr-row-${key(ID_V2)}`).className).toContain('gg-tr-row-dup');
    // NEGATIVE: an open row has no flag and no dup chip
    expect(screen.queryByTestId(`gg-tr-flag-${key(ID_C)}`)).toBeNull();
    expect(screen.queryByTestId(`gg-tr-dup-${key(ID_C)}`)).toBeNull();
    const kindCell = within(screen.getByTestId(`luk-tr-row-${key(ID_A)}`)).getByText(ROW_A.kind_text);
    expect(kindCell).toBeTruthy();
    expect(screen.getByTestId(`gg-tr-rang-${key(ID_A)}`)).toHaveTextContent('rang RTH');
  });

  it('?cat=loss lists the counted loser only (the dup is not under a bucket chip); 📋 all lists every row; a click writes / clears cat', () => {
    mount(TR, '/chart-maps?tab=luk&sub=track_record&cat=loss');
    expect(screen.getByTestId('gg-tr-cat-loss').getAttribute('aria-selected')).toBe('true');
    expect(screen.queryByTestId(`luk-tr-row-${key(ID_V1)}`)).not.toBeNull();
    expect(screen.queryByTestId(`luk-tr-row-${key(ID_V2)}`)).toBeNull();
    expect(screen.queryByTestId(`luk-tr-row-${key(ID_A)}`)).toBeNull();
    expect(screen.queryByTestId('luk-tr-day-2026-11-04')).toBeNull();
    fireEvent.click(screen.getByTestId('gg-tr-cat-all'));
    expect(q().has('cat')).toBe(false);
    expect(screen.queryByTestId(`luk-tr-row-${key(ID_V2)}`)).not.toBeNull();
    fireEvent.click(screen.getByTestId('gg-tr-cat-win'));
    expect(q().get('cat')).toBe('win');
    expect(rowOrder('2026-11-03')).toEqual([`luk-tr-row-${key(ID_A)}`]);
  });

  it('NEGATIVE: a chip with no row prints the served category-empty line; the counts never change', () => {
    mount(TR, '/chart-maps?tab=luk&sub=track_record&cat=flat');
    expect(screen.getByTestId('luk-tr-cat-empty')).toHaveTextContent(TR.category_empty_text!);
    expect(screen.queryByTestId('luk-tr-day-2026-11-03')).toBeNull();
    expect(screen.getByTestId('luk-tr-counts')).toHaveTextContent(TR.counts_text!);
    expect(screen.queryByTestId('luk-tr-empty')).toBeNull();
  });

  it('more_text printed when served; NEGATIVE: null → no line', () => {
    const r = mount({ ...TR, more_text: '+1 more rows — the counts above cover all 401' });
    expect(screen.getByTestId('luk-tr-more')).toHaveTextContent('+1 more rows — the counts above cover all 401');
    r.unmount();
    mount(TR);
    expect(screen.queryByTestId('luk-tr-more')).toBeNull();
  });

  it('the charts block is on the page when served (one served exit line, no horizon toggle)', () => {
    mount(TR);
    expect(screen.getByTestId('gg-ap')).toBeTruthy();
    expect(screen.getByTestId('gg-ap-title')).toHaveTextContent(CHARTS.title);
    expect(screen.getByTestId('gg-ap-counts-exit')).toHaveTextContent(CHARTS.counts_text!.exit!);
    expect(screen.queryByTestId('gg-ap-hs')).toBeNull();
    expect(screen.queryByTestId('gg-ap-counts-same')).toBeNull();
  });

  it('the mini tape fetches the LUK lite route on mount; 📈 opens the full tape on the LUK route; NEGATIVE: never a 🚩 route', async () => {
    serveTape();
    mount(TR);
    await waitFor(() => expect(urls().some((u) => u.includes(`/chart-maps/luk/entry-tape?id=${encodeURIComponent(ID_A)}&lite=1`))).toBe(true));
    for (const u of urls()) expect(u).toContain('/chart-maps/luk/entry-tape?id=');
    for (const u of urls()) expect(u).toContain('&lite=1');
    const n0 = urls().length;
    fireEvent.click(screen.getByTestId(`luk-tr-open-${key(ID_A)}`));
    expect(screen.getByTestId(`luk-tr-tape-${key(ID_A)}`)).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('gg-tape-read')).toHaveTextContent(TAPE.read));
    const full = urls().slice(n0);
    expect(full).toEqual([expect.stringContaining(`/chart-maps/luk/entry-tape?id=${encodeURIComponent(ID_A)}`)]);
    expect(full[0]).not.toContain('lite=1');
    for (const u of urls()) expect(u).not.toMatch(/gajjala/);
    fireEvent.click(screen.getByTestId(`luk-tr-open-${key(ID_A)}`));
    expect(screen.queryByTestId(`luk-tr-tape-${key(ID_A)}`)).toBeNull();
  });

  it('NEGATIVE: the minimal older block (LukBoard.test shape) renders luk-tr with no table cells, no Tape column, no chips — never throws', () => {
    const old = {
      title: '🏁 Track record — every 🥇 A+ recorded here since 2026-11-01 · UNMEASURED', rule_text: 'Exit = the stop or the first daily close below the 9 EMA.',
      honesty: 'Every row is a shadow record — none reached your phone.', counts_text: '1 A+ recorded · 1 filled · 0 stopped · 1 open',
      spans: [{ key: '5d', label: '5 sessions' }, { key: 'all', label: 'all' }], span: '5d',
      days: [{ date: '2026-11-03', label: 'Tue 11-03', rows: [{ id: '2026-11-03|AAA|pullback_reversal|aplus', symbol: 'AAA',
        setup_label: 'Pullback reversal', at_et: '10:06', plan_text: 'trigger 12.40 · stop 11.98 (−3.4%) · R $0.42',
        fill_text: 'filled 12.41 at 10:07', exit_text: 'open · +0.8R after 2 sessions', flags_text: '', rang_text: 'rang RTH' }] }],
    } as unknown as LukTr;
    const { container } = mount(old);
    expect(screen.getByTestId('luk-tr')).toBeTruthy();
    expect(screen.getByTestId('luk-tr-day-2026-11-03')).toHaveTextContent('Tue 11-03');
    expect(screen.getByTestId('luk-tr-counts')).toHaveTextContent(old.counts_text!);
    expect(screen.getByTestId('luk-tr-honesty')).toHaveTextContent(old.honesty!);
    expect(container.querySelectorAll('td')).toHaveLength(0);
    expect(container.querySelectorAll('th')).toHaveLength(0);
    expect(container.textContent).not.toContain('Tape');
    for (const t of ['gg-tr-cats', 'gg-tr-sorts', 'gg-ap', 'luk-tr-more', 'luk-tr-cat-empty']) expect(screen.queryByTestId(t)).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('NEGATIVE: no rows → the served empty line; no block → nothing', () => {
    const r = mount({ ...TR, days: [], categories: [{ key: 'all', text: '📋 all 0', n: 0 }] });
    expect(screen.getByTestId('luk-tr-empty')).toHaveTextContent(TR.empty_text!);
    r.unmount();
    const r2 = render(<MemoryRouter><LukTrackRecord track={null} /></MemoryRouter>);
    expect(r2.container.innerHTML).toBe('');
  });

  it('the span chips: the served span is current; a chip keeps the luk sub and sets span', () => {
    mount(TR);
    expect(screen.getByTestId('luk-tr-span-5d').getAttribute('aria-current')).toBe('true');
    expect(screen.getByTestId('luk-tr-span-all')).toHaveTextContent('all');
    const href = screen.getByTestId('luk-tr-span-today').getAttribute('href')!;
    const p = new URLSearchParams(href.split('?')[1]);
    expect(p.get('tab')).toBe('luk'); expect(p.get('sub')).toBe('track_record'); expect(p.get('span')).toBe('today');
  });

  it('NEGATIVE: no number in the DOM the payload lacks; no b-word, no "edge"', () => {
    mount(TR);
    const sec = screen.getByTestId('luk-tr').cloneNode(true) as HTMLElement;
    sec.querySelectorAll('.ptt__mini-cell').forEach((e) => e.remove());   // the tape's own served payload, not this block
    const text = sec.textContent || '';
    const served = JSON.stringify(TR);
    for (const n of text.match(/\d+(?:[.,]\d+)*/g) || []) expect(served).toContain(n);
    expect(text).not.toMatch(new RegExp('b' + 'ounce', 'i'));
    expect(text).not.toMatch(/\bedge\b/i);
  });
});

/* tsc-safe source read (the GajjalaBoard.legend.test precedent): no node types in the app tsconfig. */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('luk.css — 📱 430 px (the served strings wrap, never widen the page)', () => {
  it('.luk-tr has min-width 0; its table cells wrap; the mini tape cell stays on one line', async () => {
    const css = (await readSource('src/styles/luk.css')).replace(/\s+/g, ' ');
    expect(css).toMatch(/\.luk-tr \{ min-width: 0; \}/);
    expect(css).toMatch(/\.luk-tr \.gg-tr-table td \{ white-space: normal; overflow-wrap: anywhere; \}/);
    expect(css).toMatch(/\.luk-tr \.gg-tr-table \.ptt__mini-cell \{ white-space: nowrap; \}/);
  });
  it('NEGATIVE: the retired <ul> row rules and the LukEntryTape toggle are gone', async () => {
    const css = await readSource('src/styles/luk.css');
    for (const dead of ['.luk-tr-rows', '.luk-tape-toggle', '.luk-tr-tape']) expect(css).not.toContain(dead);
  });
});
