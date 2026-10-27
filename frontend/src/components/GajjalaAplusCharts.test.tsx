import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { GgTrAplus, GgTrApCell, GgTrApGroup } from '../lib/gajjala';
import GajjalaAplusCharts, { AP_BAR_H, AP_COL_H, AP_COL_W, AP_VB_W, apSegments } from './GajjalaAplusCharts';

/* 🎯 GajjalaAplusCharts (2026-10-26, BUILD_SPEC25 §3.6 + AMENDMENT A1) — geometry only, every string served.
 *
 * Ajay: "Once done can you give me a  A+ filter in the track record I wanna see how many of the A+ were successful draw
 * some charts to show the winning vs losing percentages of A+ trades please" / "I need these charts on Track Record page".
 *
 * SYNTHETIC: the BUILD_SPEC25 §3.3 sample (span 10d, 2026-10-26 ~20:25 ET, served rule — 16 W / 12 L same → 57%, never
 * the raw 53%). The `cell()` helper below stands in for ledger._aplus_cell (detail=False) so the by-setup / by-day cells
 * carry the served shape; the component composes nothing. Pinned: rect width == n / total · AP_VB_W, x cumulative; zero
 * n → no rect while the legend still prints every served item; by_setup widths and by_day heights scale to the MAX
 * served total; served order kept; every text node is a served string; a 0-decided horizon draws its bar and prints only
 * its served pct_text; the toggle defaults to horizon_default and switches by_setup / by_day with no fetch. NEGATIVES:
 * empty charts, total 0 / NaN / negative n, an unknown chart key, a null block. */

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** SYNTHETIC stand-in for ledger._aplus_cell(c, h, detail=False) — the test plays the server. */
function cell(w: number, l: number, o: number): GgTrApCell {
  const decided = w + l;
  const pct = decided ? Math.floor((100 * w) / decided + 0.5) : null;
  const wl = `${plural(w, 'win', 'wins')} · ${plural(l, 'loss', 'losses')} · ${pct == null ? 'no graded entry yet' : `${pct}% won`}`;
  const items = [
    { key: 'win', label: 'wins', n: w, text: plural(w, 'win', 'wins') },
    { key: 'loss', label: 'losses', n: l, text: plural(l, 'loss', 'losses') },
    ...(o > 0 ? [{ key: 'other', label: 'other', n: o, text: `${o} other` }] : []),
  ];
  return { total: w + l + o, decided, pct, loss_pct: pct == null ? null : 100 - pct,
           pct_text: pct == null ? 'no graded entry yet' : `${pct}% won · ${decided} decided`,
           text: wl + (o > 0 ? ` · ${o} other` : ''), short_text: `${w}W ${l}L`, items };
}
const day = (key: string, label: string, s: [number, number, number], n?: [number, number, number]): GgTrApGroup =>
  ({ key, label, same: cell(...s), next: cell(...(n || s)) });

const SAMPLE = (): GgTrAplus => ({
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
  split_text: '22 sent to your phone · 20 from the shadow period (never sent)', replayed_note: null, more_text: null, empty_text: null,
  honesty: 'Pooled: the A+ alerts sent to your phone and the shadow-period A+ (never sent) in one %, on its own line — the 🧠 headline % is unchanged. An A+ exists only once the trade survived its entry bar. Small n, a ledger graded by GG\'s own trade math — not a backtest of a strategy. The 2026-10-14 study of the five setups read NULL — no edge over a matched placebo (docs/gajjala/study_2026_10_13.md); this record does not change that.',
  horizons: [{ key: 'same', label: 'Same session' }, { key: 'next', label: 'Through next session' }],
  horizon_default: 'same', days: [],
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
      { key: 'kiss_fly', label: '💋 EMA Kiss & Fly', same: cell(3, 3, 4), next: cell(3, 3, 4) },
      { key: 'intraday_vcp', label: '🌀 Intraday VCP', same: cell(7, 2, 6), next: cell(7, 2, 6) },
      { key: 'reversal_squeeze', label: '🎾 Reversal Squeeze', same: cell(6, 7, 4), next: cell(7, 8, 2) }] },
    { key: 'by_day', title: 'By alert day', cols: [
      day('2026-10-13', 'Tue 10-13', [1, 2, 1], [2, 2, 0]), day('2026-10-14', 'Wed 10-14', [2, 1, 1]),
      day('2026-10-15', 'Thu 10-15', [1, 2, 1], [1, 3, 0]), day('2026-10-16', 'Fri 10-16', [2, 2, 4]),
      day('2026-10-19', 'Mon 10-19', [4, 1, 1]), day('2026-10-20', 'Tue 10-20', [2, 2, 1]), day('2026-10-21', 'Wed 10-21', [2, 0, 0]),
      day('2026-10-22', 'Thu 10-22', [2, 1, 2]), day('2026-10-23', 'Fri 10-23', [0, 1, 0]), day('2026-10-26', 'Mon 10-26', [0, 0, 3])] },
  ],
});

function servedStrings(x: unknown, out: string[] = []): string[] {
  if (typeof x === 'string') out.push(x);
  else if (Array.isArray(x)) x.forEach((v) => servedStrings(v, out));
  else if (x && typeof x === 'object') Object.values(x).forEach((v) => servedStrings(v, out));
  return out;
}
/** Every non-blank text node under `el` is exactly one served string (the component composes nothing). */
function textNodesServed(el: HTMLElement, served: string[]) {
  const set = new Set(served);
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let seen = 0;
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    const s = t.textContent || '';
    if (!s.trim()) continue;
    if (s === 'ⓘ') continue;   // the one glyph AMENDMENT A1.2 folds the honesty under (GgAplusLine's)
    seen += 1;
    expect(set.has(s), `text node "${s}" is not a served string`).toBe(true);
  }
  return seen;
}
/** The HTML lines under a by-day column (its served label + short_text) — the SVG <title> is not a printed line. */
const colLines = (el: Element) => [...el.querySelectorAll(':scope > span')].map((x) => x.textContent);
const rects = (el: Element) => [...el.querySelectorAll('rect')];
const num = (r: Element, a: string) => Number(r.getAttribute(a));
const segKey = (r: Element) => (r.getAttribute('class') || '').split(/\s+/).find((c) => c.startsWith('gg-ap-') && c !== 'gg-ap-seg')!.slice('gg-ap-'.length);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('apSegments', () => {
  it('width = n / scale · length, x cumulative, served order; zero n skipped', () => {
    const items = [{ key: 'win', label: 'wins', n: 3, text: '' }, { key: 'loss', label: 'losses', n: 0, text: '' },
                   { key: 'other', label: 'other', n: 1, text: '' }];
    const s = apSegments(items, 8, AP_VB_W);
    expect(s.map((x) => x.key)).toEqual(['win', 'other']);
    expect(s[0].x).toBe(0);
    expect(Math.abs(s[0].w - (3 / 8) * AP_VB_W)).toBeLessThan(1e-9);
    expect(Math.abs(s[1].x - s[0].w)).toBeLessThan(1e-9);
    expect(Math.abs(s[1].w - (1 / 8) * AP_VB_W)).toBeLessThan(1e-9);
  });
  it('NEGATIVE: scale 0 / NaN / negative / Infinity → no segment; NaN / negative / missing n → skipped; never a throw', () => {
    const items = [{ key: 'win', label: 'wins', n: 2, text: '' }];
    for (const sc of [0, NaN, -4, Infinity]) expect(apSegments(items, sc, AP_VB_W), String(sc)).toEqual([]);
    const bad: any[] = [{ key: 'win', n: NaN }, { key: 'loss', n: -3 }, { key: 'open' }, null, { key: 'other', n: 2 }];
    expect(apSegments(bad, 4, AP_VB_W)).toEqual([{ key: 'other', x: 0, w: AP_VB_W / 2 }]);
    expect(apSegments(null, 4, AP_VB_W)).toEqual([]);
  });
});

describe('GajjalaAplusCharts — the §3.3 sample (SYNTHETIC)', () => {
  it('draws the served lines, then the three charts in the served order with their served titles, honesty folded last', () => {
    const b = SAMPLE();
    render(<GajjalaAplusCharts block={b} />);
    const root = screen.getByTestId('gg-ap');
    expect(root.className).toContain('gg-ap');
    expect(screen.getByTestId('gg-ap-title').textContent).toBe(b.title);
    expect(screen.getByTestId('gg-ap-counts-same').textContent).toBe(b.counts_text!.same);
    expect(screen.getByTestId('gg-ap-counts-next').textContent).toBe(b.counts_text!.next);
    expect(screen.getByTestId('gg-ap-split').textContent).toBe(b.split_text);
    expect(screen.queryByTestId('gg-ap-replayed-note')).toBeNull();        // NEGATIVE: served null → nothing
    expect(screen.queryByTestId('gg-ap-more')).toBeNull();
    expect(screen.queryByTestId('gg-ap-empty')).toBeNull();
    const charts = screen.queryAllByTestId(/^gg-ap-chart-/);
    expect(charts.map((c) => c.getAttribute('data-testid'))).toEqual(b.charts.map((c) => `gg-ap-chart-${c.key}`));
    for (const c of b.charts) expect(screen.getByTestId(`gg-ap-chart-${c.key}`).textContent).toContain(c.title);
    const hon = screen.getByTestId('gg-ap-honesty');
    expect(hon.tagName).toBe('DETAILS');
    expect(hon.className).toContain('gg-aplus-note');
    expect(hon.querySelector('summary')!.textContent).toBe('ⓘ');
    expect(hon.textContent).toBe(`ⓘ${b.honesty}`);
    expect(root.lastElementChild).toBe(hon);
    expect(textNodesServed(root, servedStrings(b))).toBeGreaterThan(20);
    // NEGATIVE: the SVGs carry no text element — every label is HTML (it wraps on a phone)
    expect(root.querySelectorAll('svg text')).toHaveLength(0);
  });

  it('outcomes: each rect width == n / total · AP_VB_W (1e-9), x cumulative, one <title> = the served item text; the legend prints every served item', () => {
    const b = SAMPLE();
    render(<GajjalaAplusCharts block={b} />);
    const out = b.charts[0] as any;
    for (const bar of out.bars) {
      const svg = screen.getByTestId(`gg-ap-svg-${bar.key}`);
      expect(svg.getAttribute('viewBox')).toBe(`0 0 ${AP_VB_W} ${AP_BAR_H}`);
      expect(svg.getAttribute('preserveAspectRatio')).toBe('none');
      expect(svg.getAttribute('role')).toBe('img');
      expect(svg.getAttribute('aria-label')).toBe(bar.text);
      const rs = rects(svg);
      const drawn = bar.items.filter((i: any) => i.n > 0);
      expect(rs.map(segKey)).toEqual(drawn.map((i: any) => i.key));
      let x = 0;
      rs.forEach((r, k) => {
        const it = drawn[k];
        expect(Math.abs(num(r, 'width') - (it.n / bar.total) * AP_VB_W)).toBeLessThan(1e-9);
        expect(Math.abs(num(r, 'x') - x)).toBeLessThan(1e-9);
        expect(num(r, 'height')).toBe(AP_BAR_H);
        expect(r.querySelector('title')!.textContent).toBe(it.text);
        x += num(r, 'width');
      });
      expect(Math.abs(x - AP_VB_W)).toBeLessThan(1e-9);                     // Σ items.n == total → the bar spans the box
      const head = screen.getByTestId(`gg-ap-bar-${bar.key}`);
      expect(head.textContent).toContain(bar.label);
      expect(screen.getByTestId(`gg-ap-pct-${bar.key}`).textContent).toBe(bar.pct_text);
      for (const it of bar.items) {
        const lg = screen.getByTestId(`gg-ap-legend-${bar.key}-${it.key}`);
        expect(lg.textContent).toBe(it.text);
        expect(lg.querySelector(`.gg-ap-sw.gg-ap-${it.key}`)).not.toBeNull();
      }
    }
  });

  it('NEGATIVE: a zero-n item draws no rect, yet the legend still prints it (served text)', () => {
    const b = SAMPLE();
    const bar = (b.charts[0] as any).bars[1];
    bar.items.splice(2, 0, { key: 'flat', label: 'flat', n: 0, text: '0 flat' });
    render(<GajjalaAplusCharts block={b} />);
    const svg = screen.getByTestId('gg-ap-svg-next');
    expect(rects(svg).map(segKey)).not.toContain('flat');
    expect(screen.getByTestId('gg-ap-legend-next-flat').textContent).toBe('0 flat');
  });

  it('by_setup: one bar per served row in the served order, widths scale to the MAX served total of the picked horizon', () => {
    const b = SAMPLE();
    render(<GajjalaAplusCharts block={b} />);
    const ch = screen.getByTestId('gg-ap-chart-by_setup');
    const rows = (b.charts[1] as any).rows;
    expect(within(ch).queryAllByTestId(/^gg-ap-row-/).map((r) => r.getAttribute('data-testid')))
      .toEqual(rows.map((r: any) => `gg-ap-row-${r.key}`));
    const max = Math.max(...rows.map((r: any) => r.same.total));
    expect(max).toBe(17);
    for (const r of rows) {
      const row = screen.getByTestId(`gg-ap-row-${r.key}`);
      expect(row.textContent).toContain(r.label);
      expect(screen.getByTestId(`gg-ap-text-${r.key}`).textContent).toBe(r.same.text);
      const rs = rects(screen.getByTestId(`gg-ap-svg-${r.key}`));
      const drawn = r.same.items.filter((i: any) => i.n > 0);
      let x = 0;
      rs.forEach((rect, k) => {
        expect(Math.abs(num(rect, 'width') - (drawn[k].n / max) * AP_VB_W)).toBeLessThan(1e-9);
        expect(Math.abs(num(rect, 'x') - x)).toBeLessThan(1e-9);
        x += num(rect, 'width');
      });
      expect(Math.abs(x - (r.same.total / max) * AP_VB_W)).toBeLessThan(1e-9);
    }
  });

  it('by_day: inside the house scroll box, columns in the served (ascending) order, heights scale to the max total, stacked from the bottom', () => {
    const b = SAMPLE();
    render(<GajjalaAplusCharts block={b} />);
    const ch = screen.getByTestId('gg-ap-chart-by_day');
    expect(ch.querySelector('.gg-tr-scroll .gg-ap-cols')).not.toBeNull();
    const cols = (b.charts[2] as any).cols;
    expect(within(ch).queryAllByTestId(/^gg-ap-col-/).map((c) => c.getAttribute('data-testid')))
      .toEqual(cols.map((c: any) => `gg-ap-col-${c.key}`));
    const max = Math.max(...cols.map((c: any) => c.same.total));
    expect(max).toBe(8);
    for (const c of cols) {
      const col = screen.getByTestId(`gg-ap-col-${c.key}`);
      expect(colLines(col)).toEqual([c.label, c.same.short_text]);
      const svg = screen.getByTestId(`gg-ap-svg-${c.key}`);
      expect(svg.getAttribute('viewBox')).toBe(`0 0 ${AP_COL_W} ${AP_COL_H}`);
      expect(svg.querySelector('title')!.textContent).toBe(c.same.text);
      const drawn = c.same.items.filter((i: any) => i.n > 0);
      const rs = rects(svg);
      expect(rs.map(segKey)).toEqual(drawn.map((i: any) => i.key));
      let y = AP_COL_H;
      rs.forEach((r, k) => {
        const hgt = (drawn[k].n / max) * AP_COL_H;
        expect(Math.abs(num(r, 'height') - hgt)).toBeLessThan(1e-9);
        expect(Math.abs(num(r, 'y') - (y - hgt))).toBeLessThan(1e-9);
        expect(num(r, 'width')).toBe(AP_COL_W);
        y -= hgt;
      });
    }
  });

  it('a 0-decided horizon draws its bar (its other items) and prints only its served pct_text', () => {
    const b = SAMPLE();
    (b.charts[0] as any).bars[0] = { ...cell(0, 0, 3), key: 'same', label: 'Same session' };
    render(<GajjalaAplusCharts block={b} />);
    expect(screen.getByTestId('gg-ap-pct-same').textContent).toBe('no graded entry yet');
    const rs = rects(screen.getByTestId('gg-ap-svg-same'));
    expect(rs.map(segKey)).toEqual(['other']);
    expect(Math.abs(num(rs[0], 'width') - AP_VB_W)).toBeLessThan(1e-9);
    // NEGATIVE: no % / NaN / null printed for it
    expect(screen.getByTestId('gg-ap-bar-same').textContent || '').not.toMatch(/%|NaN|null|undefined/);
    // and the Mon 10-26 column (0 decided, 3 other) draws its other segment + its served short_text
    expect(colLines(screen.getByTestId('gg-ap-col-2026-10-26'))).toEqual(['Mon 10-26', '0W 0L']);
  });

  it('the horizon toggle defaults to horizon_default; a tap switches by_setup + by_day to next with no fetch; outcomes keep both bars', () => {
    const f = vi.fn();
    vi.stubGlobal('fetch', f);
    const b = SAMPLE();
    render(<GajjalaAplusCharts block={b} />);
    const hs = screen.getByTestId('gg-ap-hs');
    expect(hs.className).toContain('cm-phase');
    const btns = within(hs).getAllByRole('tab');
    expect(btns.map((x) => x.textContent)).toEqual(b.horizons.map((x) => x.label));
    expect(screen.getByTestId('gg-ap-h-same').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('gg-ap-h-next').getAttribute('aria-selected')).toBe('false');
    const rs = (b.charts[1] as any).rows.find((r: any) => r.key === 'reversal_squeeze');
    expect(screen.getByTestId('gg-ap-text-reversal_squeeze').textContent).toBe(rs.same.text);
    fireEvent.click(screen.getByTestId('gg-ap-h-next'));
    expect(screen.getByTestId('gg-ap-h-next').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('gg-ap-text-reversal_squeeze').textContent).toBe(rs.next.text);
    const d13 = (b.charts[2] as any).cols[0];
    expect(colLines(screen.getByTestId(`gg-ap-col-${d13.key}`))).toEqual([d13.label, d13.next.short_text]);
    expect(screen.getByTestId('gg-ap-svg-2026-10-13').querySelector('title')!.textContent).toBe(d13.next.text);
    // the outcome bars are not on the toggle — both still drawn
    expect(screen.getByTestId('gg-ap-bar-same')).not.toBeNull();
    expect(screen.getByTestId('gg-ap-bar-next')).not.toBeNull();
    expect(f).not.toHaveBeenCalled();                                       // NEGATIVE: the toggle never fetches
  });

  it('horizon_default "next" is honoured on first draw', () => {
    const b = SAMPLE();
    b.horizon_default = 'next';
    render(<GajjalaAplusCharts block={b} />);
    expect(screen.getByTestId('gg-ap-h-next').getAttribute('aria-selected')).toBe('true');
    const rs = (b.charts[1] as any).rows[2];
    expect(screen.getByTestId(`gg-ap-text-${rs.key}`).textContent).toBe(rs.next.text);
  });
});

describe('GajjalaAplusCharts — NEGATIVES', () => {
  it('NEGATIVE: null / undefined block → nothing', () => {
    const { container } = render(<GajjalaAplusCharts block={null} />);
    expect(container.innerHTML).toBe('');
    const r2 = render(<GajjalaAplusCharts block={undefined} />);
    expect(r2.container.innerHTML).toBe('');
  });

  it('NEGATIVE: the served empty_text → the title + that one line only (no counts, no toggle, no chart, no honesty)', () => {
    const b = SAMPLE();
    b.empty_text = 'No 🎯 A+ alert on this span.';
    render(<GajjalaAplusCharts block={b} />);
    const root = screen.getByTestId('gg-ap');
    expect(screen.getByTestId('gg-ap-empty').textContent).toBe(b.empty_text);
    expect([...root.children].map((c) => c.getAttribute('data-testid'))).toEqual(['gg-ap-title', 'gg-ap-empty']);
    expect(root.querySelector('svg')).toBeNull();
  });

  it('NEGATIVE: empty charts → the served lines, no gg-ap-chart-*, no toggle', () => {
    const b = SAMPLE();
    b.charts = [];
    render(<GajjalaAplusCharts block={b} />);
    expect(screen.getByTestId('gg-ap-counts-same').textContent).toBe(b.counts_text!.same);
    expect(screen.queryAllByTestId(/^gg-ap-chart-/)).toHaveLength(0);
    expect(screen.queryByTestId('gg-ap-hs')).toBeNull();
  });

  it('NEGATIVE: only the outcomes chart → no horizon toggle (it moves nothing)', () => {
    const b = SAMPLE();
    b.charts = [b.charts[0]];
    render(<GajjalaAplusCharts block={b} />);
    expect(screen.getByTestId('gg-ap-chart-outcomes')).not.toBeNull();
    expect(screen.queryByTestId('gg-ap-hs')).toBeNull();
  });

  it('NEGATIVE: an unknown chart key is skipped; the known ones still draw in the served order', () => {
    const b = SAMPLE();
    b.charts.splice(1, 0, { key: 'by_ticker', title: 'served title', rows: [] } as any);
    render(<GajjalaAplusCharts block={b} />);
    expect(screen.queryByTestId('gg-ap-chart-by_ticker')).toBeNull();
    expect(screen.queryByText('served title')).toBeNull();
    expect(screen.queryAllByTestId(/^gg-ap-chart-/).map((c) => c.getAttribute('data-testid')))
      .toEqual(['gg-ap-chart-outcomes', 'gg-ap-chart-by_setup', 'gg-ap-chart-by_day']);
  });

  it('NEGATIVE: total 0 / NaN / negative n → no rect, no throw, no NaN attribute', () => {
    const b = SAMPLE();
    const bars = (b.charts[0] as any).bars;
    bars[0].total = 0;
    bars[1].total = NaN;
    for (const it of bars[1].items) it.n = -1;
    (b.charts[1] as any).rows.forEach((r: any) => { r.same.total = NaN; r.same.items.forEach((i: any) => { i.n = NaN; }); });
    (b.charts[2] as any).cols.forEach((c: any) => { c.same.total = -5; c.same.items.forEach((i: any) => { i.n = -2; }); });
    const { container } = render(<GajjalaAplusCharts block={b} />);
    expect(rects(screen.getByTestId('gg-ap-svg-same'))).toHaveLength(0);
    expect(rects(screen.getByTestId('gg-ap-svg-next'))).toHaveLength(0);
    expect(rects(screen.getByTestId('gg-ap-chart-by_setup'))).toHaveLength(0);
    expect(rects(screen.getByTestId('gg-ap-chart-by_day'))).toHaveLength(0);
    expect(container.innerHTML).not.toMatch(/NaN|Infinity|undefined/);
  });

  it('NEGATIVE: a row / column with no cell for the picked horizon is skipped (never a guessed cell)', () => {
    const b = SAMPLE();
    delete (b.charts[1] as any).rows[0].same;
    delete (b.charts[2] as any).cols[0].same;
    render(<GajjalaAplusCharts block={b} />);
    expect(screen.queryByTestId('gg-ap-row-kiss_fly')).toBeNull();
    expect(screen.queryByTestId('gg-ap-col-2026-10-13')).toBeNull();
    expect(screen.getByTestId('gg-ap-row-intraday_vcp')).not.toBeNull();
  });

  it('NEGATIVE: no NaN / undefined / null / b-word in the drawn block; the replayed note + more line print when served', () => {
    const b = SAMPLE();
    b.replayed_note = '⏪ Replayed rows are not in the 🎯 A+ filter, its counts or its charts — they never rang.';
    b.more_text = '+12 more A+ rows — the counts above cover all 42';
    const { container } = render(<GajjalaAplusCharts block={b} />);
    expect(screen.getByTestId('gg-ap-replayed-note').textContent).toBe(b.replayed_note);
    expect(screen.getByTestId('gg-ap-more').textContent).toBe(b.more_text);
    expect(screen.getByTestId('gg-ap-more').nextElementSibling).toBe(screen.getByTestId('gg-ap-honesty'));
    const txt = container.textContent || '';
    expect(txt).not.toMatch(/NaN|undefined|null|None/);
    expect(txt).not.toMatch(/bounc/i);
  });
});
