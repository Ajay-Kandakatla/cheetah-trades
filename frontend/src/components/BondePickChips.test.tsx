import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import BondePickChips from './BondePickChips';
import type { BondeCriterion, BondePick, BondePickLegend } from '../lib/bondePicks';

/* 📋 The chip line. The negatives are the file: a row is six facts and a fold,
 * never a score, and an UNKNOWN leg must never render as a pass or a fail. */

const COMPUTED = [
  'eps_5c', 'eps_yoy_100', 'eps_seq_100', 'eps_accel', 'sales_5', 'surprise',
  'float_25m', 'short_dtc_5', 'neglect_analysts', 'fund_holding', 'ipo_10y',
  'cap_10b', 'rev_39_x2', 'sector_3',
];

const criterion = (key: string, computed = true): BondeCriterion => ({
  key, label: `${key} label`,
  quote: `his sentence for ${key}`,
  url: `https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html#${key}`,
  date: '2010-02-12', source: 'stockbee', data: `where ${key} comes from`,
  computed, not_computed_why: computed ? null : 'price-derived — legend only',
  his_call: null,
});

const legend = (): BondePickLegend => ({
  header: 'A pick list of his STATIC criteria — entries are yours.',
  criteria: [
    ...COMPUTED.map((k) => criterion(k)),
    criterion('run_up_65d', false),
    criterion('story_ep', false),
  ],
});

const pick = (over: Partial<BondePick['legs']> = {}): BondePick => ({
  legs: {
    eps_5c: { ok: true, value: 0.31 },
    eps_yoy_100: { ok: true, value: 140 },
    eps_seq_100: { ok: true, value: 120 },
    eps_accel: { ok: true, value: { now: 140, prior: 80 } },
    sales_5: { ok: true, value: 48 },
    surprise: { ok: true, value: 12, as_of: '2026-08-20', age_days: 31, stale: false },
    float_25m: { ok: true, value: 1.8e7, tier: 'ideal' },
    short_dtc_5: { ok: null, value: null, why: 'not_warmed' },
    neglect_analysts: { ok: false, value: 3, value_note: 'covered by 3' },
    fund_holding: { ok: null, value: 22.4, why: 'no_threshold_in_his_writing' },
    ipo_10y: { ok: true, value: 3.2, as_of: '2023-07-11' },
    cap_10b: { ok: true, value: 4e9 },
    rev_39_x2: { ok: true, value: { now: 45, prior: 52 } },
    sector_3: { ok: true, value: 'Technology' },
    ...over,
  },
});

describe('the six chips and the fold', () => {
  it('draws the six, in order, with the served values', () => {
    render(<BondePickChips pick={pick()} legend={legend()} symbol="PTGX" />);
    const line = screen.getByTestId('bd-pick-PTGX');
    const chips = [...line.querySelectorAll('.bd-pick-chip')];
    expect(chips.length).toBe(6);
    expect(chips.map((c) => c.textContent)).toEqual([
      'EPS +140% y/y ✓', 'Sales 2q +45%/+52% ✓', 'Surprise +12% ✓',
      'Float 18M ✓', 'IPO 3.2y ✓', 'DTC —',
    ]);
  });

  it('the fold is closed, says "all 14", and lists every computed criterion with its link', () => {
    render(<BondePickChips pick={pick()} legend={legend()} symbol="PTGX" />);
    const det = screen.getByTestId('bd-pick-PTGX').querySelector('details')!;
    expect((det as HTMLDetailsElement).open).toBe(false);
    expect(det.querySelector('summary')!.textContent).toBe('all 14');
    const rows = [...det.querySelectorAll('.bd-pick-row')];
    expect(rows.length).toBe(14);
    const links = [...det.querySelectorAll('a[href]')];
    expect(links.length).toBe(14);
    for (const a of links) expect(a.getAttribute('href')).toMatch(/^https:\/\//);
  });

  it('a chip carries the criterion label and his sentence in its tooltip', () => {
    render(<BondePickChips pick={pick()} legend={legend()} symbol="PTGX" />);
    const chip = screen.getByTestId('bd-pick-PTGX-float_25m');
    expect(chip.getAttribute('title')).toContain('float_25m label');
    expect(chip.getAttribute('title')).toContain('his sentence for float_25m');
  });

  it('NEGATIVE — a null pick renders nothing at all', () => {
    const { container } = render(
      <BondePickChips pick={null} legend={legend()} symbol="PTGX" />);
    expect(container.innerHTML).toBe('');
    expect(screen.queryByTestId('bd-pick-PTGX')).toBeNull();
  });

  it('NEGATIVE — an unknown leg never shows a tick', () => {
    render(<BondePickChips
      pick={pick({ float_25m: { ok: null, value: null, why: 'no_metrics_doc' } })}
      legend={legend()} symbol="PTGX" />);
    const chip = screen.getByTestId('bd-pick-PTGX-float_25m');
    expect(chip.textContent).toBe('Float —');
    expect(chip.textContent).not.toContain('✓');
    expect(chip.className).toContain('bd-dim');
    // ...and its row in the fold is dim too, never a cross
    const row = screen.getByTestId('bd-pick-row-PTGX-float_25m');
    expect(within(row).getAllByText('—').length).toBeGreaterThan(0);
    expect(row.querySelector('.bd-pick-glyph')!.className).toContain('bd-dim');
  });

  it('NEGATIVE — a row with many passes prints no tally, ratio or "/14"', () => {
    // Nine ticks is not a better name than three; it is a name this app knows
    // more about. No count derived from these legs is ever rendered.
    const { container } = render(
      <BondePickChips pick={pick()} legend={legend()} symbol="PTGX" />);
    const txt = container.textContent || '';
    expect(txt).not.toMatch(/\b9\s*\/\s*14\b/);
    expect(txt).not.toMatch(/\/14\b/);
    expect(txt).not.toMatch(/\b\d+\s+of\s+14\b/);
  });

  it('NEGATIVE — the line never says signal, buy or bounce', () => {
    const { container } = render(
      <BondePickChips pick={pick()} legend={legend()} symbol="PTGX" />);
    const txt = (container.textContent || '').toLowerCase();
    for (const w of ['signal', 'buy', 'bounce']) expect(txt).not.toContain(w);
  });

  it('NEGATIVE — a legend-only criterion gets no chip and no fold row', () => {
    render(<BondePickChips pick={pick()} legend={legend()} symbol="PTGX" />);
    expect(screen.queryByTestId('bd-pick-row-PTGX-run_up_65d')).toBeNull();
    expect(screen.queryByTestId('bd-pick-PTGX-run_up_65d')).toBeNull();
  });

  it('NEGATIVE — with no legend the chips still draw and the fold does not', () => {
    // The legend is served; a board that lost it must not lose the row's facts,
    // and must not open a fold onto nothing.
    render(<BondePickChips pick={pick()} legend={null} symbol="PTGX" />);
    const line = screen.getByTestId('bd-pick-PTGX');
    expect(line.querySelectorAll('.bd-pick-chip').length).toBe(6);
    expect(line.querySelector('details')).toBeNull();
  });
});
