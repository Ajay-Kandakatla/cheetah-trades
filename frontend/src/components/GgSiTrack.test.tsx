import '../test/ggCardWatchOff';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import { GG_DIVERGENCE_SUB, GG_DIVERGING_SUB, GG_HIGH_SI_SUB, GG_TABLE_SUB, type GgHighSiBlock, type GgSiTrackBlock } from '../lib/gajjala';
import { resetGgFold } from '../lib/ggFold';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { _resetBorrowCache } from '../hooks/useBorrow';

/* 🏁 GgSiTrackSection — the 🩳 SI track record inside the 🩳 High SI panel (2026-11-26, spec sitrack §3.7 B, WP fe-track,
 * [fixed: OC1]). Ajay 2026-11-26: "I want us to track these patters for future from SI like a track recprd with in SI stocks
 * itself".
 * Every string below is a SENTINEL shaped like the served block of §3.7 — the component types no word and formats no
 * number, so every assertion compares the DOM to the served value.
 * Pinned: ONE closed 🏁 <details> inside the panel, its summary the served `summary_text`; open → the base line, the
 * first-listed-that-day line, the pattern table in the served order (⛔ SSR first, 🩳 EXTREME second) with the served
 * "Shuffled" column, the day tables in ONE scroll box with the counted rows above the served `new_label`.
 * NEGATIVES: nothing of the 🏁 outside gg-sub-body on the board (fold closed → no 🏁 text on the page); GgHighSiState prints
 * exactly as without the block; block absent / null / junk → the panel DOM is identical; a fault → one error line, no
 * table; a non-string cell prints nothing; every text node is a fixture string; drawn once; an uncounted row is never above
 * the label (even served interleaved); junk heads → no table, no crash; phone: the tables scroll in their own box; no
 * digit / b-word / number formatting / admin address in the file. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> };
});
vi.mock('./GgWatchButton', () => ({ GgWatchButton: ({ symbol }: { symbol: string }) => <span data-testid={`ggw-${symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import { GgSiTrackSection } from './GgSiTrack';
import { GgHighSiPanel, GgHighSiState } from './GgHighSi';
import { GgSubFoldContext } from './GgFold';
import GajjalaBoard from './GajjalaBoard';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const clone = (x: any) => JSON.parse(JSON.stringify(x));

/** The §3.7 shape, every string a sentinel. Patterns in the SERVED order: ⛔ SSR first, 🩳 EXTREME second. */
const ST: GgSiTrackBlock = {
  title: '🏁 🩳 served st title', summary_text: '🏁 served st summary', asof_text: 'served st as of',
  base_text: 'served st base line', new_today_text: 'served st first listed that day line',
  pattern_heads: [['label', 'served Pattern'], ['with', 'served With it'], ['without', 'served Without'],
    ['diff', 'served Difference'], ['shuffle', 'served Shuffled'], ['word', 'served Read']],
  patterns: [
    { key: 'ssr_open', label: '⛔ served ssr label', known_text: 'served ssr known', with_text: 'served ssr with',
      without_text: 'served ssr without', diff_text: 'served ssr diff', shuffle_text: 'served ssr shuffle',
      word: 'served ssr word', unknown_text: 'served ssr unknown', title: 'served ssr hover' },
    { key: 'tier_extreme', label: '🩳 served extreme label', known_text: 'served extreme known', with_text: 'served extreme with',
      without_text: 'served extreme without', diff_text: 'served extreme diff', shuffle_text: 'served extreme shuffle',
      word: 'served extreme word', unknown_text: null, title: null },
    { key: 'prev_winner', label: '📅 served prev label', known_text: null, with_text: 'served prev with',
      without_text: 'served prev without', diff_text: 'served prev diff', shuffle_text: 'served prev shuffle',
      word: 'served prev word', unknown_text: null, title: null },
  ],
  where_text: 'served st where', shape_rows: [
    { label: 'served shape gap', win_text: 'served shape gap win', rest_text: 'served shape gap rest' },
    { label: 'served shape fade', win_text: 'served shape fade win', rest_text: 'served shape fade rest' },
  ],
  heads: [['ticker', 'served Ticker'], ['listed', 'served Listed'], ['si', 'served SI'], ['high', 'served High']],
  days: [
    { date: '2026-11-25', label: 'served day label newest', new_label: 'served first listed that day — not counted', rows: [
      { symbol: 'AAA', href: '/chart-maps?tab=gajjala&focus=AAA', win: '✅', counted: true, chips: ['served chip a'],
        cells: { ticker: 'AAA', listed: 'served before a', si: 'served si a', high: 'served high a' }, title: 'served hover a' },
      { symbol: 'BBB', href: null, win: '', counted: true, chips: [],
        cells: { ticker: 'BBB', listed: 'served before b', si: 'served si b', high: 'served high b' }, title: null },
      { symbol: 'NEW', href: null, win: '✅', counted: false, chips: [],
        cells: { ticker: 'NEW', listed: 'served listed at new', si: 'served si new', high: 'served high new' }, title: null },
    ] },
    { date: '2026-11-24', label: 'served day label older', new_label: 'served first listed older', rows: [
      { symbol: 'CCC', href: null, win: '', counted: true, chips: [],
        cells: { ticker: 'CCC', listed: 'served before c', si: 'served si c', high: 'served high c' }, title: null },
    ] },
  ],
  shown_text: 'served st shown', pending_text: 'served st pending',
  rule_label: 'served st rule label', rule_text: 'served st rule text', honesty: 'served st honesty',
  fault_text: null, empty_text: null, n: 4, n_days: 2,
};

/** Every string in a fixture (the leaves of the object), for the "the FE types no word" scans. */
function strings(x: unknown, out: Set<string> = new Set()): Set<string> {
  if (typeof x === 'string') out.add(x);
  else if (Array.isArray(x)) x.forEach((v) => strings(v, out));
  else if (x && typeof x === 'object') Object.values(x).forEach((v) => strings(v, out));
  return out;
}
const textNodes = (el: HTMLElement): string[] => {
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const out: string[] = [];
  for (let n = w.nextNode(); n; n = w.nextNode()) if ((n.textContent || '').trim()) out.push(n.textContent as string);
  return out;
};
const wrap = { wrapper: ({ children }: any) => <MemoryRouter>{children}</MemoryRouter> };
const openFold = (el: HTMLElement) => {
  (el as HTMLDetailsElement).open = true;
  fireEvent(el, new Event('toggle'));
};
const HS: GgHighSiBlock = {
  title: 'served hs title', ask_text: 'served his words', rule_label: 'served rule label', rule_text: 'served rule text',
  honesty: 'served honesty', counts_text: 'served counts', push_text: 'served push', n: 2, faults_text: null,
  empty_text: 'served empty', chartless: [], ssr_new: { title: 'served ssr title', fault_text: null },
};
const ST_TIDS = ['gg-st-title', 'gg-st-asof', 'gg-st-base', 'gg-st-new-today', 'gg-st-patterns-box', 'gg-st-patterns',
  'gg-st-where', 'gg-st-shape-', 'gg-st-days', 'gg-st-shown', 'gg-st-pending', 'gg-st-rule'];

beforeEach(() => { resetGgFold(); });
afterEach(() => { vi.restoreAllMocks(); });

describe('🏁 GgSiTrackSection — standalone', () => {
  it('ONE closed <details> whose summary is the served summary_text; the body is not mounted while closed', () => {
    const { container } = render(<GgSiTrackSection block={clone(ST)} />, wrap);
    const fold = screen.getByTestId('gg-st');
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.hasAttribute('open')).toBe(false);
    expect(fold.querySelector('summary')!.textContent).toBe(ST.summary_text);
    expect(container.querySelectorAll('[data-testid="gg-st"]')).toHaveLength(1);
    // NEGATIVE: closed → no base line, no table, no day rows in the DOM
    expect(screen.queryByTestId('gg-st-base')).toBeNull();
    expect(container.querySelector('table')).toBeNull();
    expect(container.textContent).toBe(ST.summary_text);
  });

  it('open: the served lines in order, the pattern table in the SERVED order (⛔ SSR first, 🩳 EXTREME second) with the Shuffled column', () => {
    const { container } = render(<GgSiTrackSection block={clone(ST)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    expect(screen.getByTestId('gg-st-base').textContent).toBe(ST.base_text);
    expect(screen.getByTestId('gg-st-new-today').textContent).toBe(ST.new_today_text);
    const order = [...container.querySelectorAll('[data-testid^="gg-st-"]')].map((e) => e.getAttribute('data-testid')!)
      .map((t) => ST_TIDS.find((p) => t === p || (p.endsWith('-') && t.startsWith(p))))
      .filter((t, i, a): t is string => !!t && a.indexOf(t) === i);
    expect(order).toEqual(ST_TIDS);
    const table = screen.getByTestId('gg-st-patterns');
    expect([...table.querySelectorAll('th')].map((th) => th.textContent)).toEqual(ST.pattern_heads!.map(([, l]) => l));
    expect([...table.querySelectorAll('th')].map((th) => th.textContent)).toContain('served Shuffled');
    const rows = [...table.querySelectorAll('tbody tr')];
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual(['gg-st-pat-ssr_open', 'gg-st-pat-tier_extreme', 'gg-st-pat-prev_winner']);
    const ssr = rows[0].querySelectorAll('td');
    expect(ssr[0].textContent).toBe('⛔ served ssr labelserved ssr knownserved ssr unknown');
    expect([...ssr].slice(1).map((td) => td.textContent)).toEqual(
      ['served ssr with', 'served ssr without', 'served ssr diff', 'served ssr shuffle', 'served ssr word']);
    expect(rows[0].getAttribute('title')).toBe('served ssr hover');
    // NEGATIVE: an unserved hover → no title attribute
    expect(rows[1].hasAttribute('title')).toBe(false);
    expect(screen.getByTestId('gg-st-where').textContent).toBe(ST.where_text);
    expect(screen.getByTestId('gg-st-shape-0').textContent).toBe('served shape gapserved shape gap winserved shape gap rest');
    expect(screen.getByTestId('gg-st-shown').textContent).toBe(ST.shown_text);
    expect(screen.getByTestId('gg-st-pending').textContent).toBe(ST.pending_text);
  });

  it('the day tables: ONE scroll box, newest first as served, the counted rows ABOVE the served new_label, the rest under it', () => {
    render(<GgSiTrackSection block={clone(ST)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const box = screen.getByTestId('gg-st-days');
    expect(box.className).toContain('gg-tr-scroll');
    expect(box.querySelectorAll('table')).toHaveLength(ST.days!.length);
    expect([...box.querySelectorAll('[data-testid^="gg-st-day-label-"]')].map((e) => e.textContent))
      .toEqual(['served day label newest', 'served day label older']);
    const day = screen.getByTestId('gg-st-day-2026-11-25');
    expect([...day.querySelectorAll('th')].map((th) => th.textContent)).toEqual(ST.heads!.map(([, l]) => l));
    const trs = [...day.querySelectorAll('tbody tr')].map((t) => t.getAttribute('data-testid'));
    expect(trs).toEqual(['gg-st-row-2026-11-25-AAA', 'gg-st-row-2026-11-25-BBB', 'gg-st-newlabel-2026-11-25', 'gg-st-row-2026-11-25-NEW']);
    expect(screen.getByTestId('gg-st-newlabel-2026-11-25').textContent).toBe('served first listed that day — not counted');
    const a = screen.getByTestId('gg-st-row-2026-11-25-AAA');
    expect(a.className).toBe('gg-tr-row-win');
    expect(within(a).getByRole('link').getAttribute('href')).toBe('/chart-maps?tab=gajjala&focus=AAA');
    expect([...a.querySelectorAll('td')].map((td) => td.textContent))
      .toEqual(['AAA✅served chip a', 'served before a', 'served si a', 'served high a']);
    expect(a.getAttribute('title')).toBe('served hover a');
    expect(screen.getByTestId('gg-st-row-2026-11-25-NEW').className).toBe('gg-tr-row-win gg-st-new');
    // NEGATIVE: no uncounted row on the older day → no label there
    expect(screen.queryByTestId('gg-st-newlabel-2026-11-24')).toBeNull();
    expect(screen.queryByText('served first listed older')).toBeNull();
  });

  it('NEGATIVE: an uncounted row served FIRST (or counted null / "true") still sits under the new_label, never above it', () => {
    const b = clone(ST);
    const rows = b.days[0].rows;
    b.days[0].rows = [rows[2], { ...rows[0], symbol: 'NUL', counted: null }, rows[0], { ...rows[1], symbol: 'STR', counted: 'true' }, rows[1]];
    render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const trs = [...screen.getByTestId('gg-st-day-2026-11-25').querySelectorAll('tbody tr')].map((t) => t.getAttribute('data-testid'));
    const at = trs.indexOf('gg-st-newlabel-2026-11-25');
    expect(trs.slice(0, at)).toEqual(['gg-st-row-2026-11-25-AAA', 'gg-st-row-2026-11-25-BBB']);
    expect(trs.slice(at + 1)).toEqual(['gg-st-row-2026-11-25-NEW', 'gg-st-row-2026-11-25-NUL', 'gg-st-row-2026-11-25-STR']);
  });

  it('2026-11-26 refix: a row served with group "other" sits under the served other_label, AFTER the first-listed rows, never under new_label', () => {
    const b: any = clone(ST);
    b.days[0].other_label = 'served not graded label';
    b.days[0].rows = [...b.days[0].rows, { symbol: 'PND', href: null, win: '', counted: false, group: 'other', chips: [],
      cells: { ticker: 'PND', listed: 'served before pnd', si: 'served si pnd', high: 'served bars pending' }, title: null }];
    b.days[0].rows[2].group = 'new';
    render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const trs = [...screen.getByTestId('gg-st-day-2026-11-25').querySelectorAll('tbody tr')].map((t) => t.getAttribute('data-testid'));
    expect(trs).toEqual(['gg-st-row-2026-11-25-AAA', 'gg-st-row-2026-11-25-BBB', 'gg-st-newlabel-2026-11-25',
      'gg-st-row-2026-11-25-NEW', 'gg-st-otherlabel-2026-11-25', 'gg-st-row-2026-11-25-PND']);
    expect(screen.getByTestId('gg-st-otherlabel-2026-11-25').textContent).toBe('served not graded label');
  });

  it('NEGATIVE: with only "other" rows uncounted, no new_label is drawn; no "other" row → no other_label', () => {
    const b: any = clone(ST);
    b.days[0].other_label = 'served not graded label';
    b.days[0].rows[2] = { ...b.days[0].rows[2], symbol: 'PND', win: '', group: 'other' };
    b.days[1].other_label = 'served not graded older';
    render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const trs = [...screen.getByTestId('gg-st-day-2026-11-25').querySelectorAll('tbody tr')].map((t) => t.getAttribute('data-testid'));
    expect(trs).toEqual(['gg-st-row-2026-11-25-AAA', 'gg-st-row-2026-11-25-BBB', 'gg-st-otherlabel-2026-11-25', 'gg-st-row-2026-11-25-PND']);
    expect(screen.queryByTestId('gg-st-newlabel-2026-11-25')).toBeNull();
    expect(screen.queryByText('served first listed that day — not counted')).toBeNull();
    expect(screen.queryByTestId('gg-st-otherlabel-2026-11-24')).toBeNull();
    expect(screen.queryByText('served not graded older')).toBeNull();
  });

  it('NEGATIVE: a counted row served with group "other" (or an unknown group) is still drawn with the counted rows / under new_label as before', () => {
    const b: any = clone(ST);
    b.days[0].other_label = 'served not graded label';
    b.days[0].rows[0].group = 'other';
    b.days[0].rows[2].group = 'zzz';
    render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const trs = [...screen.getByTestId('gg-st-day-2026-11-25').querySelectorAll('tbody tr')].map((t) => t.getAttribute('data-testid'));
    expect(trs).toEqual(['gg-st-row-2026-11-25-AAA', 'gg-st-row-2026-11-25-BBB', 'gg-st-newlabel-2026-11-25', 'gg-st-row-2026-11-25-NEW']);
  });

  it('2026-11-26 refix NEGATIVE: a served flag prints ONCE on its row — the Flags cell only, when the served chips are empty', () => {
    const b: any = clone(ST);
    b.heads = [...b.heads, ['flags', 'served Flags']];
    b.days[0].rows[1].cells.flags = 'served flag 📄 · served flag ✂️';
    render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const row = screen.getByTestId('gg-st-row-2026-11-25-BBB');
    const text = row.textContent || '';
    expect(text.split('served flag 📄').length - 1).toBe(1);
    expect(text.split('served flag ✂️').length - 1).toBe(1);
    expect(row.querySelectorAll('.gg-tr-chip')).toHaveLength(0);
  });

  it('the rule fold: a nested CLOSED <details> under the served label → the rule text + the honesty; NEGATIVE no label → no fold', () => {
    const r = render(<GgSiTrackSection block={clone(ST)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const rule = screen.getByTestId('gg-st-rule');
    expect(rule.tagName).toBe('DETAILS');
    expect(rule.hasAttribute('open')).toBe(false);
    expect(screen.getByTestId('gg-st').contains(rule)).toBe(true);
    expect(rule.querySelector('summary')!.textContent).toBe(ST.rule_label);
    expect(within(rule).getByTestId('gg-st-rule-text').textContent).toBe(ST.rule_text);
    expect(within(rule).getByTestId('gg-st-honesty').textContent).toBe(ST.honesty);
    r.unmount();
    render(<GgSiTrackSection block={{ ...clone(ST), rule_label: null }} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    expect(screen.queryByTestId('gg-st-rule')).toBeNull();
    expect(screen.queryByText(ST.honesty as string)).toBeNull();
  });

  it('NEGATIVE: the component types no word — every text node of the opened fold is a fixture string', () => {
    const { container } = render(<GgSiTrackSection block={clone(ST)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    openFold(screen.getByTestId('gg-st-rule'));
    const served = strings(ST);
    const nodes = textNodes(container);
    expect(nodes.length).toBeGreaterThan(served.size / 2);
    for (const t of nodes) expect(served.has(t), t).toBe(true);
  });

  it('NEGATIVE: a non-string cell / line (number, NaN, null, undefined, "") prints nothing — never "NaN" / "null" / "undefined"', () => {
    const b: any = clone(ST);
    b.base_text = NaN; b.new_today_text = 7; b.where_text = ''; b.shown_text = undefined; b.pending_text = null;
    b.patterns[0].with_text = NaN; b.patterns[0].diff_text = 12.5; b.patterns[0].known_text = null;
    b.days[0].rows[0].cells = { ticker: 'AAA', listed: NaN, si: null, high: 41.2 };
    b.days[0].rows[0].win = NaN; b.days[0].rows[0].chips = [NaN, 3, null, 'served chip a'];
    b.shape_rows = [{ label: NaN, win_text: null, rest_text: undefined }, ...b.shape_rows];
    const { container } = render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    for (const t of ['gg-st-base', 'gg-st-new-today', 'gg-st-where', 'gg-st-shown', 'gg-st-pending', 'gg-st-shape-0']) {
      expect(screen.queryByTestId(t), t).toBeNull();
    }
    const a = screen.getByTestId('gg-st-row-2026-11-25-AAA');
    expect([...a.querySelectorAll('td')].map((td) => td.textContent)).toEqual(['AAAserved chip a', '', '', '']);
    expect(a.className).toBe('');
    const ssr = screen.getByTestId('gg-st-pat-ssr_open').querySelectorAll('td');
    expect(ssr[1].textContent).toBe('');
    expect(ssr[3].textContent).toBe('');
    expect(container.textContent).not.toMatch(/NaN|null|undefined|41\.2|12\.5/);
  });

  it('a served fault_text → ONE error line, no fold, no table (whatever else is served)', () => {
    const { container } = render(<GgSiTrackSection block={{ ...clone(ST), fault_text: 'served st fault' }} />, wrap);
    const f = screen.getByTestId('gg-st-fault');
    expect(f.textContent).toBe('served st fault');
    expect(f.className).toContain('cm-note-err');
    expect(screen.queryByTestId('gg-st')).toBeNull();
    expect(container.querySelector('table, details')).toBeNull();
    expect(container.textContent).toBe('served st fault');
  });

  it('the empty block (no stored doc): the served summary, open → the served empty line only; NEGATIVE no table, no rule', () => {
    const b = { summary_text: '🏁 served empty summary', empty_text: 'served st empty', title: '🏁 served st title', n: 0, n_days: 0 };
    const { container } = render(<GgSiTrackSection block={b} />, wrap);
    expect(screen.getByTestId('gg-st').querySelector('summary')!.textContent).toBe(b.summary_text);
    openFold(screen.getByTestId('gg-st'));
    expect(screen.getByTestId('gg-st-empty').textContent).toBe(b.empty_text);
    expect(container.querySelector('table')).toBeNull();
    expect(container.textContent).not.toMatch(/\d/);
  });

  it('NEGATIVE: null / undefined / a number / a string / an array / {} / no summary_text → nothing at all', () => {
    for (const v of [null, undefined, 3, 'x', [], {}, { ...clone(ST), summary_text: NaN }, { ...clone(ST), summary_text: '' }]) {
      const { container, unmount } = render(<GgSiTrackSection block={v as any} />, wrap);
      expect(container.innerHTML, String(v)).toBe('');
      unmount();
    }
  });

  it('NEGATIVE: junk heads (not a list, short pairs, numbers) → no table, no crash; the lines still print', () => {
    const b: any = { ...clone(ST), pattern_heads: 'x', heads: [['ticker'], [3, 'served Ticker'], null, { key: 'k' }] };
    const { container } = render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    expect(container.querySelector('table')).toBeNull();
    expect(screen.queryByTestId('gg-st-days')).toBeNull();
    expect(screen.getByTestId('gg-st-base').textContent).toBe(ST.base_text);
    const c: any = { ...clone(ST), days: [{ date: 'd', rows: [{ symbol: null }, { symbol: 7 }, 'x'] }, 'junk', null] };
    const r2 = render(<GgSiTrackSection block={c} />, wrap);
    openFold(within(r2.container).getByTestId('gg-st'));
    expect(within(r2.container).queryByTestId('gg-st-days')).toBeNull();
  });

  it('phone (430 px): every table sits in its own .gg-tr-scroll box; no inline width / nowrap; the CSS wraps the fold', async () => {
    const { container } = render(<GgSiTrackSection block={clone(ST)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    openFold(screen.getByTestId('gg-st-rule'));
    for (const t of container.querySelectorAll('table')) expect(t.closest('.gg-tr-scroll')).not.toBeNull();
    for (const el of container.querySelectorAll('*')) {
      expect((el as HTMLElement).getAttribute('style') || '', el.tagName).not.toMatch(/width|nowrap/i);
    }
    const css = await readSource('src/styles/ggSiTrack.css');
    const rule = (sel: string) => new RegExp(`\\n${sel.replace(/[.>]/g, (m) => `\\${m}`)} \\{([^}]*)\\}`).exec(css)?.[1] || '';
    for (const sel of ['.gg-st', '.gg-st-body', '.gg-st-shape', '.gg-st-rule']) {
      expect(rule(sel), sel).toMatch(/min-width: 0/);
      expect(rule(sel), sel).toMatch(/overflow-wrap: anywhere/);
      expect(rule(sel), sel).not.toMatch(/nowrap|(^|;)\s*width:/);
    }
    expect(rule('.gg-st')).toMatch(/max-width: 100%/);
    const house = await readSource('src/styles/gajjala.css');
    expect(/\n\.gg-tr-scroll \{([^}]*)\}/.exec(house)![1]).toMatch(/overflow-x: auto; max-width: 100%/);
  });

  it('NEGATIVE source guards: no digit typed in the code, no b-word, no number formatting, no admin address, its own servedText guard', async () => {
    const src = await readSource('src/components/GgSiTrack.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    expect(code).not.toMatch(/\d/);
    expect(src).not.toMatch(/bounc/i);
    expect(src).not.toMatch(/toFixed\(|toLocaleString\(|Intl\.|\.sort\(/);
    expect(src).not.toMatch(/@gmail|ajaykandakatla/i);
    expect(src).toMatch(/function servedText\(v: unknown\): v is string \{/);
    expect(src).not.toMatch(/from '\.\/GajjalaBoard'/);
    // no typed word between tags: every node body is a served value
    expect(code).not.toMatch(/<[a-z][^<>]*>\s*[^\s<{][^<{]*<\//);
    expect(code).not.toMatch(/\bfetch\(/);
    const css = await readSource('src/styles/ggSiTrack.css');
    expect(css).not.toMatch(/bounc/i);
  });
});

describe('🏁 inside the 🩳 panel — mounted after the ⛔ list, drawn once, the panel otherwise unchanged', () => {
  const withSt = (st: unknown) => ({ ...clone(HS), si_track: st }) as GgHighSiBlock;

  it('the 🏁 sits INSIDE gg-hs right after the ⛔ section, closed, ONCE', () => {
    const { container } = render(<GgHighSiPanel block={withSt(clone(ST))} />, wrap);
    const panel = screen.getByTestId('gg-hs');
    const fold = screen.getByTestId('gg-st');
    expect(panel.contains(fold)).toBe(true);
    expect(screen.getByTestId('gg-ssrn').nextElementSibling).toBe(fold);
    expect(fold.hasAttribute('open')).toBe(false);
    expect(container.querySelectorAll('[data-testid="gg-st"]')).toHaveLength(1);
    expect(fold.querySelector('summary')!.textContent).toBe(ST.summary_text);
  });

  it('NEGATIVE: si_track absent / null / junk → the panel DOM is byte-identical to a block without the key', () => {
    const base = render(<GgHighSiPanel block={clone(HS)} />, wrap);
    const html = base.container.innerHTML;
    base.unmount();
    expect(html).not.toMatch(/gg-st/);
    for (const v of [null, undefined, 3, 'x', {}, { summary_text: null }]) {
      const r = render(<GgHighSiPanel block={withSt(v)} />, wrap);
      expect(r.container.innerHTML, String(v)).toBe(html);
      r.unmount();
    }
  });

  it('a fault block → one error line inside the panel, no table, no fold', () => {
    render(<GgHighSiPanel block={withSt({ fault_text: 'served st fault' })} />, wrap);
    const panel = screen.getByTestId('gg-hs');
    expect(within(panel).getByTestId('gg-st-fault').textContent).toBe('served st fault');
    expect(within(panel).queryByTestId('gg-st')).toBeNull();
    expect(panel.querySelector('table')).toBeNull();
  });

  it('NEGATIVE: GgHighSiState prints exactly what it printed without the block — no 🏁 there, open or closed fold', () => {
    const state = (b: GgHighSiBlock) => render(
      <MemoryRouter><GgSubFoldContext.Provider value={`sub:${GG_HIGH_SI_SUB}`}><GgHighSiState block={b} /></GgSubFoldContext.Provider></MemoryRouter>);
    const shapes: Partial<GgHighSiBlock>[] = [{ faults_text: 'served faults' }, { n: 0 },
      { ssr_new: { fault_text: 'served ssr fault' } },
      { chartless: [{ symbol: 'ZZZ', text: 'served ZZZ listed', state_label: null, href: null }] }];
    for (const over of shapes) {
      const a = state({ ...clone(HS), ...over });
      const html = a.container.innerHTML;
      a.unmount();
      expect(html).not.toBe('');
      const b = state({ ...clone(HS), ...over, si_track: clone(ST) });
      expect(b.container.innerHTML).toBe(html);
      expect(b.container.textContent).not.toContain('🏁');
      b.unmount();
      const c = state({ ...clone(HS), ...over, si_track: { fault_text: 'served st fault' } });
      expect(c.container.innerHTML).toBe(html);
      c.unmount();
    }
  });

  it('source: GgHighSi mounts the 🏁 once, in the panel, right after the ⛔ section; GgHighSiState never names it', async () => {
    const src = await readSource('src/components/GgHighSi.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    expect(code.split('<GgSiTrackSection').length - 1).toBe(1);
    expect(code).toMatch(/<GgSsrNewSection block=\{block\.ssr_new\} \/><GgSiTrackSection block=\{block\.si_track\} \/>\n/);
    const state = code.slice(code.indexOf('export function GgHighSiState('), code.indexOf('export function GgHighSiPanel('));
    expect(state).not.toMatch(/si_track|GgSiTrack/);
  });
});

/* ---- the board: nothing of the 🏁 outside gg-sub-body (the GajjalaBoard.high_si.test.tsx board, its own copy). ---- */

const HAND: Record<string, any> = (hand as any).boards;
const HS_CHIP = { key: GG_HIGH_SI_SUB, emoji: '\u{1FA73}', label: 'High SI', count: 2, title: null };
const DG_CHIP = { key: GG_DIVERGING_SUB, emoji: '\u{1F331}', label: 'Diverging', count: 1, title: null };
const DV_CHIP = { key: GG_DIVERGENCE_SUB, emoji: '\u{1F9E8}', label: 'Divergence', count: 0, title: null };
function strip(b: any): any[] {
  const subs = b.subs.map((s: any) => ({ ...s, title: null }));
  const at = subs.findIndex((s: any) => s.key === 'reversal_squeeze') + 1;
  subs.splice(at, 0, DV_CHIP, DG_CHIP, HS_CHIP);
  return [{ key: GG_TABLE_SUB, emoji: '\u{1F4CB}', label: 'All strategies', count: 0, title: null }, ...subs,
    { key: 'potential', emoji: '\u{1F9E0}', label: 'Potential', count: 0, title: null },
    { key: 'track_record', emoji: '\u{1F3C1}', label: 'Track record', count: 0, title: null }];
}
function hsBoard(st: unknown): any {
  const b = clone(HAND.bull_flag);
  b.sub = GG_HIGH_SI_SUB;
  b.session = { ...b.session, refresh_sec: 0 };
  b.tiles = b.tiles.slice(0, 1).map((t: any) => ({ ...t, lines: [],
    gajjala: { setup: GG_HIGH_SI_SUB, state: 'high_si', state_label: 'served hs card state', criteria: [], missed: [],
      unjudged: [], plan_text: null, chips: {}, listed: null,
      high_si: { tier: 'high', float_check: 'confirmed', si_chip: 'served si chip', carried: false, add_text: null } } }));
  b.empty_note = null;
  b.sorts = [];
  b.subs = strip(b);
  b.high_si = { ...clone(HS), si_track: st };
  return b;
}
let boardSt: unknown = null;
const fetchMock = vi.fn(async (url: string): Promise<any> => {
  const u = new URL(String(url), 'http://x');
  const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(hsBoard(boardSt));
  return ok({});
});
const mountBoard = async () => {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${GG_HIGH_SI_SUB}`]}><GajjalaBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
/** The page's visible text: every text node with no `hidden` ancestor (the fold body closes with the attribute). */
const visibleText = (root: HTMLElement) => {
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let out = '';
  for (let n = w.nextNode(); n; n = w.nextNode()) if (!(n.parentElement && n.parentElement.closest('[hidden]'))) out += n.textContent;
  return out;
};

describe('🏁 on the 🚩 board — inside the 🩳 sub\'s ⓘ fold only', () => {
  beforeEach(() => {
    _resetShortInterestCache(); _resetRegShoCache(); _resetBorrowCache();
    fetchMock.mockClear();
    boardSt = clone(ST);
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('EventSource', class { close() { /* no stream */ } addEventListener() { /* none */ } });
  });
  afterEach(() => { vi.unstubAllGlobals(); _resetBorrowCache(); _resetRegShoCache(); _resetShortInterestCache(); });

  it('fold closed: the 🏁 is mounted inside gg-sub-body and hidden; the page shows no 🏁 text; ONE 🏁 on the page', async () => {
    const { container } = await mountBoard();
    const fold = screen.getByTestId('gg-st');
    expect(fold.closest('[data-testid="gg-sub-body"]')).not.toBeNull();
    expect(fold).not.toBeVisible();
    expect(container.querySelectorAll('[data-testid="gg-st"]')).toHaveLength(1);
    for (const el of container.querySelectorAll('[data-testid="gg-st"], [data-testid^="gg-st-"]')) {
      expect(el.closest('[data-testid="gg-sub-body"]'), el.getAttribute('data-testid')!).not.toBeNull();
    }
    const seen = visibleText(container);
    for (const s of strings(ST)) if (s.length > 1) expect(seen.includes(s), s).toBe(false);
    expect(seen).not.toContain(ST.summary_text);
  });

  it('ⓘ opened: the closed 🏁 line shows (its body still closed); NEGATIVE a fault block → the error line in the fold only', async () => {
    const r = await mountBoard();
    fireEvent.click(screen.getByTestId('gg-sub-toggle'));
    expect(screen.getByTestId('gg-st-summary')).toBeVisible();
    expect(screen.getByTestId('gg-st').hasAttribute('open')).toBe(false);
    expect(screen.queryByTestId('gg-st-base')).toBeNull();
    r.unmount();
    resetGgFold();
    localStorage.clear();
    localStorage.setItem('gg-card-watch', '0');
    boardSt = { fault_text: 'served st fault' };
    const r2 = await mountBoard();
    const f = within(r2.container).getByTestId('gg-st-fault');
    expect(f.closest('[data-testid="gg-sub-body"]')).not.toBeNull();
    expect(f).not.toBeVisible();
    expect(within(r2.container).queryByTestId('gg-substate')).toBeNull();
  });
});
