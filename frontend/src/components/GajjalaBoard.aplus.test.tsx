import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CurrentUser } from '../hooks/useUser';
import { GG_CAT_PARAM, GG_KIND_PARAM, GG_VIEW_TIMELINE, ggKindDays, ggKindOn, ggQuery } from '../lib/gajjala';

/* 🎯 A+ filter + the win/loss charts on Gajjala's 🏁 Track record (2026-10-26, BUILD_SPEC25 §3.4 / §3.5 + AMENDMENT A1).
 *
 * Ajay: "Once done can you give me a  A+ filter in the track record I wanna see how many of the A+ were successful draw
 * some charts to show the winning vs losing percentages of A+ trades please" — then "I need these charts on Track Record
 * page" (A1: the A+ block is drawn on the list view ALWAYS whenever `tr.aplus` is served; the 🎯 chip narrows the rows).
 *
 * Fixture: the 🏁 golden's 5d board CLONED with `kinds` / `kind_param` / `kind_empty_text` / `categories_aplus` / `aplus`
 * injected. SYNTHETIC: `aplus` is the BUILD_SPEC25 §3.3 sample (its charts + sentences), its `days` = the clone's own A+
 * rows (kind aplus, line ≠ replayed); the 🎯 chip n / text and `categories_aplus` are built from that count HERE — the
 * test stands in for the server; the component never composes. WP-C's golden test pins the real served payload.
 *
 * Pinned: chips print the served text in the served order, the first selected; filter OFF → the block + its three charts
 * AND the 🧠 counts lines AND every row; tap 🎯 → `?kind=aplus`, ZERO new GETs, rows == `aplus.days` (emptied days
 * gone), the 🧠 counts / ⏪ / more lines gone, the block still there, the honesty line LAST; 🎯 ∧ ❌ → only A+ losers,
 * the cats chips print `categories_aplus`; a span click keeps `kind` and no GET ever carries it; a sub click drops it;
 * the 🕰️ timeline → no chips, no block, `kind` ignored. NEGATIVES: `kind=bogus`; an older payload (no kinds / aplus);
 * kinds served but no aplus → the served kind_empty_text; the served aplus.empty_text → title + empty line only; every
 * digit printed is a whole token of a served string; no NaN / undefined / b-word. */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
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
vi.mock('./GgEntryTape', () => ({
  GgEntryTape: ({ id }: any) => <div data-testid="mock-tape" data-id={id} />,
  GgEntryMiniTape: ({ id }: any) => <span data-testid="mock-mini" data-id={id} />,
}));

import GajjalaBoard from './GajjalaBoard';

async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';
async function readJsonIfPresent(rel: string): Promise<any | null> {
  const fs = await fsMod();
  const p = `${root}/${rel}`;
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
}
const GOLDEN: any = await readJsonIfPresent('src/components/__fixtures__/gajjala_track_record_golden_2026_10_16.json');
const BOARDS: Record<string, any> = GOLDEN?.boards || {};
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const DEFAULT_SPAN = '5d';

/* ---- SYNTHETIC: the BUILD_SPEC25 §3.3 sample (span 10d, served rule: 16 W / 12 L same → 57%) ---- */
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** SYNTHETIC stand-in for ledger._aplus_cell(c, h, detail=False). */
function cell(w: number, l: number, o: number) {
  const decided = w + l;
  const pct = decided ? Math.floor((100 * w) / decided + 0.5) : null;
  return {
    total: w + l + o, decided, pct, loss_pct: pct == null ? null : 100 - pct,
    pct_text: pct == null ? 'no graded entry yet' : `${pct}% won · ${decided} decided`,
    text: `${plural(w, 'win', 'wins')} · ${plural(l, 'loss', 'losses')} · ${pct == null ? 'no graded entry yet' : `${pct}% won`}`
      + (o > 0 ? ` · ${o} other` : ''),
    short_text: `${w}W ${l}L`,
    items: [{ key: 'win', label: 'wins', n: w, text: plural(w, 'win', 'wins') },
            { key: 'loss', label: 'losses', n: l, text: plural(l, 'loss', 'losses') },
            ...(o > 0 ? [{ key: 'other', label: 'other', n: o, text: `${o} other` }] : [])],
  };
}
const grp = (key: string, label: string, s: [number, number, number], n?: [number, number, number]) =>
  ({ key, label, same: cell(...s), next: cell(...(n || s)) });
const SAMPLE_APLUS = () => ({
  title: "🎯 A+ only — every A+ alert, sent or shadow, graded by GG's trade math · UNMEASURED",
  total: 42, n_sent: 22, n_shadow: 20,
  counts: {
    same: { win: 16, loss: 12, no_entry: 7, open: 2, no_plan: 0, no_risk: 1, no_time: 0, pending: 2, thin: 2, pct: 57 },
    next: { win: 17, loss: 13, no_entry: 6, flat: 0, no_plan: 0, no_risk: 1, no_time: 0, pending: 3, thin: 2, split: 0, pct: 57 },
  },
  counts_text: {
    same: 'A+ same session: 16 wins · 12 losses · 57% won · 7 no entry · 2 open · 1 no risk · 2 thin R (not in the %) · 2 not graded yet',
    next: 'A+ through next session: 17 wins · 13 losses · 57% won · 6 no entry · 0 flat · 1 no risk · 2 thin R (not in the %) · 3 not graded yet',
  },
  split_text: '22 sent to your phone · 20 from the shadow period (never sent)', replayed_note: null as string | null,
  more_text: null as string | null, empty_text: null as string | null,
  honesty: "Pooled: the A+ alerts sent to your phone and the shadow-period A+ (never sent) in one %, on its own line — the 🧠 headline % is unchanged. An A+ exists only once the trade survived its entry bar. Small n, a ledger graded by GG's own trade math — not a backtest of a strategy. The 2026-10-14 study of the five setups read NULL — no edge over a matched placebo (docs/gajjala/study_2026_10_13.md); this record does not change that.",
  horizons: [{ key: 'same', label: 'Same session' }, { key: 'next', label: 'Through next session' }],
  horizon_default: 'same', days: [] as any[],
  charts: [
    { key: 'outcomes', title: '🎯 A+ wins vs losses', bars: [
      { key: 'same', label: 'Same session', total: 42, decided: 28, pct: 57, loss_pct: 43, pct_text: '57% won · 28 decided',
        text: '16 wins · 12 losses · 57% won · 14 other', short_text: '16W 12L', items: [
          { key: 'win', label: 'wins', n: 16, text: '16 wins (57% of the 28 decided)' },
          { key: 'loss', label: 'losses', n: 12, text: '12 losses (43% of the 28 decided)' },
          { key: 'open', label: 'open', n: 2, text: '2 open' }, { key: 'no_entry', label: 'no entry', n: 7, text: '7 no entry' },
          { key: 'other', label: 'other', n: 5, text: '5 other · 1 no risk · 2 thin R (not in the %) · 2 not graded yet' }] },
      { key: 'next', label: 'Through next session', total: 42, decided: 30, pct: 57, loss_pct: 43, pct_text: '57% won · 30 decided',
        text: '17 wins · 13 losses · 57% won · 12 other', short_text: '17W 13L', items: [
          { key: 'win', label: 'wins', n: 17, text: '17 wins (57% of the 30 decided)' },
          { key: 'loss', label: 'losses', n: 13, text: '13 losses (43% of the 30 decided)' },
          { key: 'no_entry', label: 'no entry', n: 6, text: '6 no entry' },
          { key: 'other', label: 'other', n: 6, text: '6 other · 1 no risk · 2 thin R (not in the %) · 3 not graded yet' }] }] },
    { key: 'by_setup', title: 'By setup', rows: [
      grp('kiss_fly', '💋 EMA Kiss & Fly', [3, 3, 4]), grp('intraday_vcp', '🌀 Intraday VCP', [7, 2, 6]),
      grp('reversal_squeeze', '🎾 Reversal Squeeze', [6, 7, 4], [7, 8, 2])] },
    { key: 'by_day', title: 'By alert day', cols: [
      grp('2026-10-13', 'Tue 10-13', [1, 2, 1], [2, 2, 0]), grp('2026-10-14', 'Wed 10-14', [2, 1, 1]),
      grp('2026-10-15', 'Thu 10-15', [1, 2, 1], [1, 3, 0]), grp('2026-10-16', 'Fri 10-16', [2, 2, 4]),
      grp('2026-10-19', 'Mon 10-19', [4, 1, 1]), grp('2026-10-20', 'Tue 10-20', [2, 2, 1]), grp('2026-10-21', 'Wed 10-21', [2, 0, 0]),
      grp('2026-10-22', 'Thu 10-22', [2, 1, 2]), grp('2026-10-23', 'Fri 10-23', [0, 1, 0]), grp('2026-10-26', 'Mon 10-26', [0, 0, 3])] },
  ],
});

const rowsOf = (tr: any) => (tr.days || []).flatMap((d: any) => d.rows || []);
const isAp = (r: any) => r.kind === 'aplus' && r.line !== 'replayed';
/** The served category label without its count (the test builds `categories_aplus` the way ledger._category_text does). */
const catLabel = (text: string) => text.replace(/ \d+(?: \+\d+ ⏪)?$/, '');
/** The test plays the server: inject the 🎯 keys into a clone of a golden board (after `edit` touches its rows). */
function withAplus(b0: any, edit?: (tr: any) => void) {
  const b = clone(b0);
  const tr = b.track_record;
  if (edit) edit(tr);
  const rows = rowsOf(tr);
  const ap = rows.filter(isAp);
  const rep = rows.filter((r: any) => r.line === 'replayed').length;
  const all = rows.length - rep;
  tr.kinds = [{ key: 'all', n: all, n_replayed: rep, text: `📋 every alert ${all}${rep ? ` +${rep} ⏪` : ''}` },
              { key: 'aplus', n: ap.length, n_replayed: 0, text: `🎯 A+ only ${ap.length}` }];
  tr.kind_param = 'kind';
  tr.kind_empty_text = 'No 🎯 A+ alert on this span.';
  tr.categories_aplus = tr.categories.map((c: any, i: number) => {
    const n = i === 0 ? ap.length : ap.filter((r: any) => r.bucket === c.key).length;
    return { key: c.key, n, n_replayed: 0, text: `${catLabel(c.text)} ${n}` };
  });
  tr.aplus = SAMPLE_APLUS();
  tr.aplus.days = tr.days.map((d: any) => ({ ...d, rows: d.rows.filter(isAp) })).filter((d: any) => d.rows.length);
  return b;
}

type Call = { method: string; path: string; span: string | null; sub: string | null; cat: string | null; kind: string | null };
let calls: Call[] = [];
function stub(get: (u: URL) => any) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, span: u.searchParams.get('span'), sub: u.searchParams.get('sub'),
                 cat: u.searchParams.get(GG_CAT_PARAM), kind: u.searchParams.get(GG_KIND_PARAM) });
    if (u.pathname.endsWith('/chart-maps/gajjala/scan')) {
      return { ok: true, status: 200, json: async () => ({ state: 'closed', latest_at: null, text: 'served closed line' }) };
    }
    return { ok: true, status: 200, json: async () => clone(get(u)) };
  }));
}
/** Every span of the golden, each with the 🎯 keys injected. */
const AP_BOARDS = () => Object.fromEntries(Object.entries(BOARDS).map(([k, v]) => [k, (v as any)?.track_record ? withAplus(v) : v]));
const bySpan = (boards: Record<string, any>) => (u: URL) => boards[u.searchParams.get('span') || DEFAULT_SPAN] || boards[DEFAULT_SPAN];
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.endsWith('/chart-maps/gajjala'));

let loc = { search: '' };
function Probe() {
  const l = useLocation();
  loc = { search: l.search };
  return null;
}
const mount = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const urlKind = () => new URLSearchParams(loc.search).get(GG_KIND_PARAM);
const shownRowIds = (prefix: string) => screen.queryAllByTestId(new RegExp(`^${prefix}`)).map((r) => r.getAttribute('data-testid'));
const idsOf = (rows: any[], prefix = 'gg-tr-row-') => rows.map((r: any) => `${prefix}${r.key}`);
const CHART_IDS = ['gg-ap-chart-outcomes', 'gg-ap-chart-by_setup', 'gg-ap-chart-by_day'];

function servedStrings(x: unknown, out: string[] = []): string[] {
  if (typeof x === 'string') out.push(x);
  else if (Array.isArray(x)) x.forEach((v) => servedStrings(v, out));
  else if (x && typeof x === 'object') Object.values(x).forEach((v) => servedStrings(v, out));
  return out;
}
const NUM = /\d+(?:[.,:]\d+)*/g;
/** Whole-token check (the 🏁 tests' helper): every number printed is a WHOLE number token of some served string. */
function numbersServed(el: HTMLElement, served: string[]) {
  const toks = new Set(served.join(' \u0000 ').match(NUM) || []);
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let seen = 0;
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    for (const n of (t.textContent || '').match(NUM) || []) {
      seen += 1;
      expect(toks.has(n), `number ${n} (in "${t.textContent}") is not a token of any served string`).toBe(true);
    }
  }
  return seen;
}

beforeEach(() => { userRet = null; calls = []; });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('GajjalaBoard — 🎯 A+ filter + charts (golden clone, SYNTHETIC aplus)', () => {
  it('the golden exists and its 5d board has A+ rows, non-A+ rows and a ⏪ row (the clone filters something)', () => {
    expect(GOLDEN).not.toBeNull();
    const tr = BOARDS[DEFAULT_SPAN]?.track_record;
    expect(tr).toBeTruthy();
    const rows = rowsOf(tr);
    expect(rows.filter(isAp).length).toBeGreaterThan(0);
    expect(rows.filter((r: any) => !isAp(r)).length).toBeGreaterThan(0);
    expect(rows.some((r: any) => r.line === 'replayed')).toBe(true);
    // at least one day has no A+ row (the filter must drop it)
    expect(tr.days.some((d: any) => !d.rows.some(isAp))).toBe(true);
  });

  it('filter OFF (A1): the chips in the served order (first selected) under the view toggle, the block + its three charts, the 🧠 lines and EVERY row', async () => {
    const boards = AP_BOARDS();
    stub(bySpan(boards));
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    const tr = boards[DEFAULT_SPAN].track_record;
    const box = screen.getByTestId('gg-tr-kinds');
    const btns = within(box).getAllByRole('tab');
    expect(btns.map((b) => b.getAttribute('data-testid'))).toEqual(tr.kinds.map((k: any) => `gg-tr-kind-${k.key}`));
    expect(btns.map((b) => b.textContent)).toEqual(tr.kinds.map((k: any) => k.text));
    expect(btns.filter((b) => b.getAttribute('aria-selected') === 'true').map((b) => b.getAttribute('data-testid')))
      .toEqual([`gg-tr-kind-${tr.kinds[0].key}`]);
    expect(btns.every((b) => b.className.includes('cm-phase-btn'))).toBe(true);
    expect(box.previousElementSibling).toBe(screen.getByTestId('gg-tr-views'));
    expect(box.nextElementSibling).toBe(screen.getByTestId('gg-tr-cats'));
    // the block, always (A1.1)
    expect(screen.getByTestId('gg-ap')).not.toBeNull();
    expect(screen.queryAllByTestId(/^gg-ap-chart-/).map((c) => c.getAttribute('data-testid'))).toEqual(CHART_IDS);
    // the 🧠 lines + every row + the main chips
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(tr.counts_text.same);
    expect(screen.getByTestId('gg-tr-counts-next').textContent).toBe(tr.counts_text.next);
    expect(screen.getByTestId('gg-tr-replayed').textContent).toBe(tr.replayed_text);
    expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(rowsOf(tr)));
    expect(within(screen.getByTestId('gg-tr-cats')).getAllByRole('tab').map((b) => b.textContent))
      .toEqual(tr.categories.map((c: any) => c.text));
    // order: today → the block → the first day table; the honesty line LAST (A1.3)
    expect(screen.getByTestId('gg-tr-today').nextElementSibling).toBe(screen.getByTestId('gg-ap'));
    expect(screen.getByTestId('gg-ap').nextElementSibling?.querySelector(`[data-testid="gg-tr-day-${tr.days[0].date}"]`)).not.toBeNull();
    expect(screen.getByTestId('gg-track-record').lastElementChild).toBe(screen.getByTestId('gg-tr-honesty'));
    expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
  });

  it('tap 🎯: ?kind=aplus, ZERO new GETs, rows == aplus.days (emptied days gone), 🧠 / ⏪ / more lines gone, the block stays, honesty LAST; 📋 brings all back', async () => {
    const boards = AP_BOARDS();
    boards[DEFAULT_SPAN].track_record.more_text = '+3 more rows on this span';
    stub(bySpan(boards));
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    const tr = boards[DEFAULT_SPAN].track_record;
    expect(screen.getByTestId('gg-tr-more').textContent).toBe(tr.more_text);
    const before = gets().length;
    fireEvent.click(screen.getByTestId('gg-tr-kind-aplus'));
    await waitFor(() => expect(urlKind()).toBe('aplus'));
    await waitFor(() => expect(screen.getByTestId('gg-tr-kind-aplus').getAttribute('aria-selected')).toBe('true'));
    await new Promise((r) => setTimeout(r, 30));
    expect(gets().length).toBe(before);                                        // NEGATIVE: a chip never fetches
    expect(gets().every((c) => c.kind == null)).toBe(true);                    // NEGATIVE: kind never rides the GET
    const apRows = tr.aplus.days.flatMap((d: any) => d.rows);
    expect(apRows.length).toBeGreaterThan(0);
    expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(apRows));
    for (const d of tr.days) {
      if (tr.aplus.days.some((x: any) => x.date === d.date)) expect(screen.getByTestId(`gg-tr-day-${d.date}`).textContent).toBe(d.label);
      else expect(screen.queryByTestId(`gg-tr-day-${d.date}`), d.date).toBeNull();   // NEGATIVE: an emptied day is gone
    }
    // NEGATIVE: no 🧠 / replayed row under 🎯
    for (const r of rowsOf(tr).filter((x: any) => !isAp(x))) expect(screen.queryByTestId(`gg-tr-row-${r.key}`), r.key).toBeNull();
    // H10: the 🧠 counts lines, the ⏪ lines and the list's more line hide; the 🎯 entries / shadow lines stay as served
    expect(screen.queryByTestId('gg-tr-counts-same')).toBeNull();
    expect(screen.queryByTestId('gg-tr-counts-next')).toBeNull();
    expect(screen.queryByTestId('gg-tr-replayed')).toBeNull();
    expect(screen.queryByTestId('gg-tr-replayed-note')).toBeNull();
    expect(screen.queryByTestId('gg-tr-more')).toBeNull();
    if (tr.entries_text) expect(screen.getByTestId('gg-tr-entries').textContent).toBe(tr.entries_text);
    if (tr.shadow_text) expect(screen.getByTestId('gg-tr-shadow').textContent).toBe(tr.shadow_text);
    // the block + the three charts with their served titles
    const ap = screen.getByTestId('gg-ap');
    expect(screen.getByTestId('gg-ap-title').textContent).toBe(tr.aplus.title);
    expect(screen.getByTestId('gg-ap-counts-same').textContent).toBe(tr.aplus.counts_text.same);
    expect(screen.queryAllByTestId(/^gg-ap-chart-/).map((c) => c.getAttribute('data-testid'))).toEqual(CHART_IDS);
    for (const c of tr.aplus.charts) expect(screen.getByTestId(`gg-ap-chart-${c.key}`).textContent).toContain(c.title);
    expect(ap.contains(screen.getByTestId('gg-ap-honesty'))).toBe(true);
    // the cats chips switch to categories_aplus
    expect(within(screen.getByTestId('gg-tr-cats')).getAllByRole('tab').map((b) => b.textContent))
      .toEqual(tr.categories_aplus.map((c: any) => c.text));
    expect(screen.getByTestId('gg-track-record').lastElementChild).toBe(screen.getByTestId('gg-tr-honesty'));
    expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
    // 📋 every alert → back to every row + the 🧠 lines, no GET
    fireEvent.click(screen.getByTestId(`gg-tr-kind-${tr.kinds[0].key}`));
    await waitFor(() => expect(urlKind()).toBeNull());
    await waitFor(() => expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(rowsOf(tr))));
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(tr.counts_text.same);
    expect(screen.getByTestId('gg-tr-more').textContent).toBe(tr.more_text);
    expect(screen.getByTestId('gg-ap')).not.toBeNull();
    expect(gets().length).toBe(before);
  });

  it('🎯 ∧ ❌ (cat=loss): only the A+ losers; the cats chips print categories_aplus; NEGATIVE a 🧠 loser never shows', async () => {
    const tail = (tr: any) => {
      const apR = rowsOf(tr).find(isAp);
      const brain = rowsOf(tr).find((r: any) => r.kind === 'potential');
      apR.bucket = 'loss';
      brain.bucket = 'loss';
    };
    const b = withAplus(BOARDS[DEFAULT_SPAN], tail);
    const tr = b.track_record;
    stub(() => b);
    const { container } = mount(`tab=gajjala&sub=track_record&${GG_KIND_PARAM}=aplus&${GG_CAT_PARAM}=loss`);
    await loaded(container);
    const losers = tr.aplus.days.flatMap((d: any) => d.rows).filter((r: any) => r.bucket === 'loss');
    expect(losers).toHaveLength(1);
    expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(losers));
    const brainLoser = rowsOf(tr).find((r: any) => r.kind === 'potential' && r.bucket === 'loss');
    expect(screen.queryByTestId(`gg-tr-row-${brainLoser.key}`)).toBeNull();
    const cats = within(screen.getByTestId('gg-tr-cats')).getAllByRole('tab');
    expect(cats.map((x) => x.textContent)).toEqual(tr.categories_aplus.map((c: any) => c.text));
    expect(screen.getByTestId('gg-tr-cat-loss').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('gg-tr-kind-aplus').getAttribute('aria-selected')).toBe('true');
    expect(screen.queryByTestId('gg-tr-cat-empty')).toBeNull();
    // the same cat with 🎯 off → every loser (🧠 included)
    fireEvent.click(screen.getByTestId('gg-tr-kind-all'));
    await waitFor(() => expect(urlKind()).toBeNull());
    expect(new URLSearchParams(loc.search).get(GG_CAT_PARAM)).toBe('loss');
    await waitFor(() => expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(rowsOf(tr).filter((r: any) => r.bucket === 'loss'))));
  });

  it('🎯 ∧ a bucket with no A+ row → the served category_empty_text (the A+ rows exist, none in it)', async () => {
    const b = withAplus(BOARDS[DEFAULT_SPAN]);
    const tr = b.track_record;
    const none = tr.categories_aplus.slice(1).find((c: any) => c.n === 0);
    expect(none).toBeTruthy();
    stub(() => b);
    const { container } = mount(`tab=gajjala&sub=track_record&${GG_KIND_PARAM}=aplus&${GG_CAT_PARAM}=${none.key}`);
    await loaded(container);
    expect(screen.getByTestId('gg-tr-cat-empty').textContent).toBe(tr.category_empty_text);
    expect(shownRowIds('gg-tr-row-')).toEqual([]);
    expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
    expect(screen.getByTestId('gg-track-record').lastElementChild).toBe(screen.getByTestId('gg-tr-honesty'));
  });

  it('a span click keeps kind (the next GET never carries it); NEGATIVE a sub click drops it', async () => {
    const boards = AP_BOARDS();
    stub(bySpan(boards));
    const { container } = mount(`tab=gajjala&sub=track_record&${GG_KIND_PARAM}=aplus`);
    await loaded(container);
    const tr = boards[DEFAULT_SPAN].track_record;
    const pick = tr.spans.find((s: any) => s.key !== tr.span && boards[s.key]?.track_record);
    expect(pick).toBeTruthy();
    fireEvent.click(screen.getByTestId(`gg-tr-span-${pick.key}`));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('span')).toBe(pick.key));
    expect(urlKind()).toBe('aplus');
    await waitFor(() => expect(gets()[gets().length - 1].span).toBe(pick.key));
    expect(gets().every((c) => c.kind == null)).toBe(true);
    const ptr = boards[pick.key].track_record;
    await waitFor(() => expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(ptr.aplus.days.flatMap((d: any) => d.rows))));
    fireEvent.click(screen.getByTestId('gg-sub-bull_flag'));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sub')).toBe('bull_flag'));
    expect(urlKind()).toBeNull();
  });

  it('NEGATIVE: the 🕰️ timeline view → no 🎯 chips, no A+ block, kind ignored (the same rows as without it)', async () => {
    const boards = AP_BOARDS();
    stub(bySpan(boards));
    const tr = boards[DEFAULT_SPAN].track_record;
    const { container, unmount } = mount(`tab=gajjala&sub=track_record&view=${GG_VIEW_TIMELINE}`);
    await loaded(container);
    const plain = shownRowIds('gg-tl-row-');
    expect(plain.length).toBeGreaterThan(0);
    expect(screen.queryByTestId('gg-tr-kinds')).toBeNull();
    expect(screen.queryByTestId('gg-ap')).toBeNull();
    unmount();
    stub(bySpan(boards));
    const r2 = mount(`tab=gajjala&sub=track_record&view=${GG_VIEW_TIMELINE}&${GG_KIND_PARAM}=aplus`);
    await loaded(r2.container);
    expect(shownRowIds('gg-tl-row-')).toEqual(plain);
    expect(screen.queryByTestId('gg-tr-kinds')).toBeNull();
    expect(screen.queryByTestId('gg-ap')).toBeNull();
    expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
    expect(within(screen.getByTestId('gg-tr-cats')).getAllByRole('tab').map((b) => b.textContent))
      .toEqual(tr.categories_timeline.map((c: any) => c.text));
    expect(urlKind()).toBe('aplus');
  });
});

describe('GajjalaBoard — 🎯 NEGATIVES (golden clones)', () => {
  it('NEGATIVE: kind=bogus → every row, the 🧠 lines, the first chip selected; the block still drawn (A1 — it never depends on kind)', async () => {
    const boards = AP_BOARDS();
    stub(bySpan(boards));
    const { container } = mount(`tab=gajjala&sub=track_record&${GG_KIND_PARAM}=bogus`);
    await loaded(container);
    const tr = boards[DEFAULT_SPAN].track_record;
    expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(rowsOf(tr)));
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(tr.counts_text.same);
    expect(screen.getByTestId(`gg-tr-kind-${tr.kinds[0].key}`).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('gg-ap')).not.toBeNull();
    expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
  });

  it('NEGATIVE: an older payload (no kinds / aplus) + ?kind=aplus → no chip row, no block, every row, the 🧠 lines', async () => {
    const old = clone(BOARDS[DEFAULT_SPAN]);
    for (const k of ['kinds', 'kind_param', 'kind_empty_text', 'categories_aplus', 'aplus']) delete old.track_record[k];
    stub(() => old);
    const { container } = mount(`tab=gajjala&sub=track_record&${GG_KIND_PARAM}=aplus`);
    await loaded(container);
    expect(screen.queryByTestId('gg-tr-kinds')).toBeNull();
    expect(screen.queryByTestId('gg-ap')).toBeNull();
    expect(screen.queryAllByTestId(/^gg-ap-chart-/)).toHaveLength(0);
    expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
    expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(rowsOf(old.track_record)));
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(old.track_record.counts_text.same);
  });

  it('NEGATIVE: kinds served but aplus absent → off: no block, every row; on: the served kind_empty_text, no row, honesty LAST', async () => {
    const b = withAplus(BOARDS[DEFAULT_SPAN]);
    delete b.track_record.aplus;
    stub(() => b);
    const { container, unmount } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(screen.getByTestId('gg-tr-kinds')).not.toBeNull();
    expect(screen.queryByTestId('gg-ap')).toBeNull();
    expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(rowsOf(b.track_record)));
    unmount();
    stub(() => b);
    const r2 = mount(`tab=gajjala&sub=track_record&${GG_KIND_PARAM}=aplus`);
    await loaded(r2.container);
    expect(screen.getByTestId('gg-tr-kind-empty').textContent).toBe(b.track_record.kind_empty_text);
    expect(screen.getByTestId('gg-tr-kind-empty').className).toContain('cm-note');
    expect(screen.queryByTestId('gg-ap')).toBeNull();
    expect(shownRowIds('gg-tr-row-')).toEqual([]);
    expect(r2.container.querySelector('table')).toBeNull();
    expect(screen.getByTestId('gg-track-record').lastElementChild).toBe(screen.getByTestId('gg-tr-honesty'));
  });

  it('NEGATIVE: the served aplus.empty_text → title + that line only (no chart), no gg-tr-kind-empty, in both states', async () => {
    const b = withAplus(BOARDS[DEFAULT_SPAN]);
    const ap = b.track_record.aplus;
    Object.assign(ap, { total: 0, n_sent: 0, n_shadow: 0, counts_text: null, split_text: null, more_text: null,
                        empty_text: b.track_record.kind_empty_text, charts: [], days: [] });
    b.track_record.kinds[1].n = 0;
    b.track_record.kinds[1].text = '🎯 A+ only 0';
    for (const on of [false, true]) {
      stub(() => b);
      const { container, unmount } = mount(`tab=gajjala&sub=track_record${on ? `&${GG_KIND_PARAM}=aplus` : ''}`);
      await loaded(container);
      const root = screen.getByTestId('gg-ap');
      expect([...root.children].map((c) => c.getAttribute('data-testid'))).toEqual(['gg-ap-title', 'gg-ap-empty']);
      expect(screen.getByTestId('gg-ap-empty').textContent).toBe(ap.empty_text);
      expect(screen.queryAllByTestId(/^gg-ap-chart-/)).toHaveLength(0);
      expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
      if (on) expect(shownRowIds('gg-tr-row-')).toEqual([]);
      else expect(shownRowIds('gg-tr-row-')).toEqual(idsOf(rowsOf(b.track_record)));
      expect(screen.getByTestId('gg-track-record').lastElementChild).toBe(screen.getByTestId('gg-tr-honesty'));
      unmount();
    }
  });

  it('NEGATIVE: the chips print the TEXT only — a served n that disagrees with the text is never printed', async () => {
    const b = withAplus(BOARDS[DEFAULT_SPAN]);
    for (const k of b.track_record.kinds) k.n = 987654;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(screen.getByTestId('gg-tr-kinds').textContent || '').not.toContain('987654');
    expect(within(screen.getByTestId('gg-tr-kinds')).getAllByRole('tab').map((x) => x.textContent))
      .toEqual(b.track_record.kinds.map((k: any) => k.text));
  });

  it('NEGATIVE: every digit inside gg-track-record is a whole token of a served string; no NaN / undefined / the b-word (both states)', async () => {
    const b = withAplus(BOARDS[DEFAULT_SPAN]);
    for (const on of [false, true]) {
      stub(() => b);
      const { container, unmount } = mount(`tab=gajjala&sub=track_record${on ? `&${GG_KIND_PARAM}=aplus` : ''}`);
      await loaded(container);
      const sec = screen.getByTestId('gg-track-record');
      expect(numbersServed(sec, servedStrings(b))).toBeGreaterThan(20);
      const txt = sec.textContent || '';
      expect(txt).not.toMatch(/NaN|undefined|\bNone\b/);
      expect(txt).not.toMatch(/bounc/i);
      expect(sec.innerHTML).not.toMatch(/NaN|undefined/);
      unmount();
    }
  });

  it('ggKindOn / ggKindDays: on only for a served key other than the first; off → the very same days; kind never rides the GET', () => {
    const b = withAplus(BOARDS[DEFAULT_SPAN]);
    const tr = b.track_record;
    expect(ggKindOn('aplus', tr.kinds)).toBe(true);
    expect(ggKindDays(tr.days, 'aplus', tr.kinds, tr.aplus)).toBe(tr.aplus.days);
    // NEGATIVES: null / the first served key / unknown / no served chips → the very same days
    for (const [k, ks] of [[null, tr.kinds], ['all', tr.kinds], ['bogus', tr.kinds], ['aplus', null], ['aplus', []], ['', tr.kinds],
                           ['aplus', [tr.kinds[1]]]] as const) {
      expect(ggKindOn(k as any, ks as any), String(k)).toBe(false);
      expect(ggKindDays(tr.days, k as any, ks as any, tr.aplus), String(k)).toBe(tr.days);
    }
    // NEGATIVE: on with no served block / a block without days → nothing (never the unfiltered days)
    expect(ggKindDays(tr.days, 'aplus', tr.kinds, null)).toEqual([]);
    expect(ggKindDays(tr.days, 'aplus', tr.kinds, { ...tr.aplus, days: undefined })).toEqual([]);
    const q = ggQuery({ sub: 'track_record' as any, span: '5d', ...({ kind: 'aplus' } as any) });
    expect(new URLSearchParams(q).get(GG_KIND_PARAM)).toBeNull();
    expect(GG_KIND_PARAM).toBe('kind');
    expect(GG_KIND_PARAM).toBe(tr.kind_param);
  });
});
