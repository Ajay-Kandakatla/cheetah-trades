import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import BondeCriteriaLegend from './BondeCriteriaLegend';
import type { BondeCite, BondeCriterion, BondePickLegend } from '../lib/bondePicks';

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

  it('the second header line is his sentence off the tape, linked at the second', () => {
    render(<BondeCriteriaLegend legend={legend({
      tape_header: {
        quote: 'a good chart itself is not a setup',
        url: 'https://www.youtube.com/watch?v=fjox2hapu98&t=857s',
        ts: '0:14:17', source: 'tape', date: '2026-02-18', recorded: '~June 2025',
      },
    })} />);
    const heads = screen.getAllByTestId('bonde-tape-header');
    expect(heads.length).toBe(1);
    expect(heads[0].textContent).toContain('a good chart itself is not a setup');
    const a = heads[0].querySelector('a')!;
    expect(a.getAttribute('href')).toMatch(/&t=857s$/);
    expect(a.textContent).toContain('on tape [0:14:17]');
  });

  it('NEGATIVE — no tape header, no tape line, and nothing crashes', () => {
    render(<BondeCriteriaLegend legend={legend()} />);
    expect(screen.queryByTestId('bonde-tape-header')).toBeNull();
    expect(screen.queryByTestId('bonde-tape-source')).toBeNull();
    expect(screen.getAllByTestId('bonde-criteria').length).toBe(1);
  });

  it('a criterion carries its EXTRA cites, one indented line each', () => {
    const cites: BondeCite[] = [
      { quote: 'Technology, biotechnology or healthcare related stock',
        url: 'https://www.youtube.com/watch?v=fjox2hapu98&t=4024s',
        ts: '1:07:04', source: 'tape', date: '2026-02-18', recorded: '~June 2025' },
      { quote: 'You can get rid of everything else if you really want to',
        url: 'https://www.youtube.com/watch?v=fjox2hapu98&t=4037s',
        ts: '1:07:17', source: 'tape', date: '2026-02-18', recorded: '~June 2025',
        note: 'his exclusion; no filter ships off it' },
    ];
    render(<BondeCriteriaLegend legend={legend({
      criteria: [criterion({ key: 'sector_3', label: 'Three sectors', cites })],
    })} />);
    const p = screen.getByTestId('bonde-criterion-sector_3');
    const lines = [...p.querySelectorAll('.bd-pick-cite')];
    expect(lines.length).toBe(2);
    expect(lines[0].textContent)
      .toContain('— also, on tape [1:07:04]: “Technology, biotechnology');
    expect(lines[0].querySelector('a')!.getAttribute('href')).toMatch(/&t=4024s$/);
    expect(lines[1].textContent).toContain('his exclusion; no filter ships off it');
    // the primary sentence is still there — a cite is ADDED, never a swap
    expect(p.textContent).toContain('earnings acceleration of 100% plus');
  });

  it('NEGATIVE — an empty or absent cite list draws no cite line', () => {
    render(<BondeCriteriaLegend legend={legend({
      criteria: [criterion({ cites: [] }), criterion({ key: 'sales_5', cites: null })],
    })} />);
    expect(document.querySelectorAll('.bd-pick-cite').length).toBe(0);
  });

  it('a tape-primary criterion links at its timestamp, not at a date', () => {
    render(<BondeCriteriaLegend legend={legend({
      criteria: [criterion({
        key: 'ep_origin_300', label: 'How EP began', computed: false,
        quote: 'phenomenally good 300 400 500%',
        url: 'https://www.youtube.com/watch?v=fjox2hapu98&t=2939s',
        ts: '0:48:59', source: 'tape', date: '2026-02-18', recorded: '~June 2025',
        not_computed_why: 'the paragraph he quoted, not his own screen',
      })],
    })} />);
    const p = screen.getByTestId('bonde-criterion-ep_origin_300');
    expect(p.querySelector('a')!.textContent).toBe('on tape [0:48:59]');
    expect(p.textContent).toContain('not read here:');
    expect(p.textContent).not.toContain('tape 2026-02-18');
  });

  it('the tape-source line names the show, both dates and when it arrived', () => {
    render(<BondeCriteriaLegend legend={legend({
      tape: {
        url: 'https://www.youtube.com/watch?v=fjox2hapu98',
        title: 'Trading Legend', show: 'Words of Rizdom',
        published: '2026-02-18', recorded: '~June 2025', received: '2026-09-20',
        recorded_cite: {
          quote: 'the last month is over May',
          url: 'https://www.youtube.com/watch?v=fjox2hapu98&t=3911s',
          ts: '1:05:11', source: 'tape',
        },
      },
    })} />);
    const t = screen.getByTestId('bonde-tape-source');
    expect(t.textContent).toContain('Words of Rizdom');
    expect(t.textContent).toContain('published 2026-02-18');
    expect(t.textContent).toContain('recorded ~June 2025');
    expect(t.textContent).toContain('received 2026-09-20');
    expect(t.querySelector('a')!.getAttribute('href')).toMatch(/&t=3911s$/);
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

  it('NEGATIVE — a cite quote is rendered verbatim too, never typed here', () => {
    render(<BondeCriteriaLegend legend={legend({
      criteria: [criterion({
        cites: [{ quote: 'ZZZ-CITE-ONLY', url: 'https://u', ts: '9:99:99',
                  source: 'tape' }],
      })],
    })} />);
    expect(screen.getByTestId('bonde-cite-eps_yoy_100-0').textContent)
      .toContain('— also, on tape [9:99:99]: “ZZZ-CITE-ONLY”');
  });
});
