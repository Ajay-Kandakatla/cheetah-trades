import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import BondeCriteriaLegend from './BondeCriteriaLegend';
import type { BondeCriterion, BondePickLegend } from '../lib/bondePicks';

/* 📋 The legend. This board spent 2026-09-20 removing nine claims attributed
 * to him that were not his, so the one rule here is that every criterion
 * arrives with the sentence he actually published and a link to it — SERVED,
 * never typed into the component. */

const criterion = (over: Partial<BondeCriterion> = {}): BondeCriterion => ({
  key: 'eps_yoy_100', label: 'Earnings +100% year over year',
  quote: 'earnings acceleration of 100% plus',
  url: 'https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html',
  date: '2010-02-12', source: 'stockbee',
  data: 'quarterly EPS series off the scan row',
  computed: true, not_computed_why: null, his_call: null, ...over,
});

const legend = (over: Partial<BondePickLegend> = {}): BondePickLegend => ({
  header: 'A pick list of his STATIC criteria — entries are yours (S&D).',
  criteria: [
    criterion(),
    criterion({ key: 'short_dtc_5', label: '5 plus days to cover',
                quote: 'high short interest ( 5 plus days to cover)',
                url: 'https://x.com/PradeepBonde/status/1801220695197614404',
                date: '2024-06-13', source: 'x',
                his_call: 'the warm cadence and its crontab line' }),
    criterion({ key: 'run_up_65d', label: '65-day run-up', computed: false,
                quote: 'stocks which have not rallied in anticipation of earnings',
                url: 'https://stockbee.blogspot.com/2007/03/how-to-trade-earnings.html',
                date: '2007-03-30',
                not_computed_why: 'price-derived; his correction asks for static info only' }),
  ],
  not_a_source: 'The YouTube summary is NOT a source: nothing here comes from it.',
  warm_note: 'Short interest reads unknown on every row until the warm has run.',
  ...over,
});

beforeEach(() => { try { localStorage.clear(); } catch { /* private window */ } });

describe('the criterion legend', () => {
  it('renders ONCE, folded, with the served headline above the fold', () => {
    render(<BondeCriteriaLegend legend={legend()} />);
    const all = screen.getAllByTestId('bonde-criteria');
    expect(all.length).toBe(1);
    expect(all[0].textContent).toContain('A pick list of his STATIC criteria');
    expect((all[0] as HTMLDetailsElement).open).toBe(false);
  });

  it('every criterion arrives with his sentence and its link', () => {
    render(<BondeCriteriaLegend legend={legend()} />);
    fireEvent.click(screen.getByText(/A pick list of his STATIC criteria/));
    const eps = screen.getByTestId('bonde-criterion-eps_yoy_100');
    expect(eps.textContent).toContain('earnings acceleration of 100% plus');
    const a = eps.querySelector('a')!;
    expect(a.getAttribute('href')).toBe(
      'https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html');
    expect(a.textContent).toContain('2010-02-12');
    expect(a.getAttribute('rel')).toBe('noreferrer');

    const dtc = screen.getByTestId('bonde-criterion-short_dtc_5');
    expect(dtc.querySelector('a')!.getAttribute('href'))
      .toMatch(/^https:\/\/x\.com\/PradeepBonde\//);
  });

  it('a legend-only criterion says why it is not read here', () => {
    render(<BondeCriteriaLegend legend={legend()} />);
    const only = screen.getByTestId('bonde-criterion-run_up_65d');
    expect(only.textContent).toContain('not read here');
    expect(only.textContent).toContain('price-derived');
  });

  it('a criterion whose reading is pending says so in his words', () => {
    render(<BondeCriteriaLegend legend={legend()} />);
    expect(screen.getByTestId('bonde-criterion-short_dtc_5').textContent)
      .toContain('Ajay’s call:');
  });

  it('prints the two served caveats', () => {
    render(<BondeCriteriaLegend legend={legend()} />);
    expect(screen.getByTestId('bonde-not-a-source').textContent)
      .toContain('YouTube summary is NOT a source');
    expect(screen.getByTestId('bonde-warm-note').textContent)
      .toContain('until the warm has run');
  });

  it('computed criteria come before the legend-only ones', () => {
    const { container } = render(<BondeCriteriaLegend legend={legend()} />);
    const keys = [...container.querySelectorAll('.bd-pick-crit')]
      .map((p) => p.getAttribute('data-testid'));
    expect(keys[keys.length - 1]).toBe('bonde-criterion-run_up_65d');
  });

  it('NEGATIVE — no legend, nothing rendered (never a typed fallback)', () => {
    const { container } = render(<BondeCriteriaLegend legend={null} />);
    expect(container.innerHTML).toBe('');
    const empty = render(<BondeCriteriaLegend legend={{ header: '', criteria: [] }} />);
    expect(empty.container.innerHTML).toBe('');
  });

  it('NEGATIVE — the component types none of his quotes itself', async () => {
    // Hand it criteria whose quotes are nonsense: whatever renders is what was
    // served. A quote hard-coded here would be a quote nobody can re-verify.
    render(<BondeCriteriaLegend legend={legend({
      criteria: [criterion({ quote: 'ZZZ-SERVED-ONLY' })],
    })} />);
    expect(screen.getByTestId('bonde-criterion-eps_yoy_100').textContent)
      .toContain('ZZZ-SERVED-ONLY');
    expect(screen.queryByText(/earnings acceleration of 100% plus/)).toBeNull();
  });
});
