import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmBar, CmEllipse, CmTile } from '../lib/chartMaps';

/* 📶 GG's base count marks on the card chart (2026-11-15, WP-C fe-card). PatternChart is NOT edited: the server serves
 * the run-base ellipses as `tile.ellipses` items of kind `run_base` (run_bases.ellipses — tone `structure`, GG's magenta
 * pen), and the existing ellipse layer draws every served kind. This pins that a `run_base` item draws with its SERVED
 * label and tone, appended after the 🎾 squeeze marks on a 🎾 card, and alone on any other card.
 * Ajay 2026-11-15: "There is a concept of 3 bases and climax run can you bake that in to the app please".
 * NEGATIVES: an unknown / red-ish tone → `structure` (never a red stroke); stamps off the served bars → no mark; no
 * `ellipses` → no layer; the chart face prints the short label only, GG's quote lives in the <title> hover. */

const MAGENTA = '#e879f9';
const hm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const BARS: CmBar[] = Array.from({ length: 60 }, (_, i) => {
  const p = 2 + 0.05 * Math.sin(i / 5) + 0.01 * i;
  return { t: `2026-11-13 ${hm(9 * 60 + 35 + 5 * i)}`, o: p, h: p + 0.03, l: p - 0.03, c: p + 0.01, v: 1000 + i };
});
const NOTE = 'GG S8 40:54: “served quote test data”';
const rb = (n: number, from: string, to: string, over: Partial<CmEllipse> = {}): CmEllipse => ({
  kind: 'run_base', from_t: `2026-11-13 ${from}`, to_t: `2026-11-13 ${to}`, lo: 2.1, hi: 2.2,
  label: ['1st base', '2nd base', '3rd base', '4th base'][n - 1] ?? `base ${n}`, note: NOTE, tone: 'structure',
  ...({ n } as any), ...over,
});
const BASES = [rb(1, '10:05', '10:20'), rb(2, '10:50', '11:00'), rb(3, '11:30', '11:35')];
const SQUEEZE: CmEllipse[] = [
  { kind: 'tennis', from_t: '2026-11-13 10:00', to_t: '2026-11-13 10:10', lo: 2.0, hi: 2.1, label: 'tennis ball',
    note: 'squeeze note', tone: 'structure' },
  { kind: 'entry', from_t: '2026-11-13 10:15', to_t: '2026-11-13 10:15', lo: 2.05, hi: 2.12, label: 'entry',
    note: 'entry note', tone: 'entry' },
];
const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'ABCD', href: '/sepa/ABCD', bars: BARS, bands: [], lines: [], markers: [], stats: [], why: '', ...over,
});
const draw = (t: CmTile) => render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);
const groups = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg [data-ellipse-kind]'));
const runBases = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg [data-ellipse-kind="run_base"]'));

afterEach(() => cleanup());

describe('PatternChart — 📶 run-base marks', () => {
  it('a non-🎾 card: one run_base group per served base, the served label on the face, tone structure, magenta', () => {
    const { container } = draw(tile({ ellipses: BASES }));
    const gs = runBases(container);
    expect(gs).toHaveLength(3);
    expect(gs.map((g) => g.querySelector('text')!.textContent)).toEqual(['1st base', '2nd base', '3rd base']);
    for (const g of gs) {
      expect(g.getAttribute('data-ellipse-tone')).toBe('structure');
      expect(g.querySelector('ellipse')!.getAttribute('stroke')).toBe(MAGENTA);
    }
  });

  it('the hover <title> carries the served note (GG quote); the chart face never does', () => {
    const { container } = draw(tile({ ellipses: BASES }));
    const g = runBases(container)[2];
    expect(g.querySelector('title')!.textContent).toBe(`3rd base · 11:30–11:35 · ${NOTE}`);
    for (const t of Array.from(container.querySelectorAll('svg.cm-svg text'))) {
      expect(t.textContent || '').not.toContain('served quote test data');
    }
  });

  it('a 🎾 card: the squeeze marks first, THEN the bases (served order kept)', () => {
    const { container } = draw(tile({ ellipses: [...SQUEEZE, ...BASES] }));
    expect(groups(container).map((g) => g.getAttribute('data-ellipse-kind')))
      .toEqual(['tennis', 'entry', 'run_base', 'run_base', 'run_base']);
  });

  it('NEGATIVE: an unknown or red-ish tone draws as structure — never a red stroke', () => {
    const { container } = draw(tile({ ellipses: [rb(4, '12:00', '12:10', { tone: 'exit' }), rb(5, '12:30', '12:40', { tone: 'red' })] }));
    const gs = runBases(container);
    expect(gs).toHaveLength(2);
    for (const g of gs) {
      expect(g.getAttribute('data-ellipse-tone')).toBe('structure');
      expect(g.querySelector('ellipse')!.getAttribute('stroke')).toBe(MAGENTA);
    }
    expect(gs.map((g) => g.querySelector('text')!.textContent)).toEqual(['4th base', 'base 5']);
  });

  it('NEGATIVE: a base whose stamp is off the served bars (e.g. a 15m card) draws nothing', () => {
    const off = rb(1, '10:07', '10:20');
    const { container } = draw(tile({ ellipses: [off, rb(2, '10:50', '19:55')] }));
    expect(runBases(container)).toHaveLength(0);
    expect(container.querySelector('g.pc-gg-ellipses')).toBeNull();
  });

  it('NEGATIVE: no ellipses / an empty list → no run_base mark, no layer', () => {
    for (const t of [tile(), tile({ ellipses: [] })]) {
      const { container } = draw(t);
      expect(runBases(container)).toHaveLength(0);
      expect(container.querySelector('g.pc-gg-ellipses')).toBeNull();
      cleanup();
    }
  });
});
