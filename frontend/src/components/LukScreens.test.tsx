import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { LukScreens } from './LukScreens';
import type { LukScreen } from '../lib/luk';

/* 🥇 Luk's scan tables (2026-11-01, luk spec §3.6 / §3.10). Rows in the SERVED order, the served cells, the criteria
 * ticks, the "cap unknown — not filtered" row KEPT, the served not-screened / considerations / honesty lines. The FE
 * sorts nothing and types no word. NEGATIVES: no re-sort, an empty screen prints no table, no blank cell says "undefined". */

const SCREEN: LukScreen = {
  key: 'leader', title: '🏆 Leader scan — his settings: cap > $100M · price×vol 1W > $300M · sorted by 1-month %',
  sorted_by_text: 'sorted by 1-month % change',
  heads: [{ key: 'rank', label: '#' }, { key: 'symbol', label: 'Ticker' }, { key: 'perf_1m_text', label: '1M %' },
    { key: 'cap_text', label: 'Cap' }, { key: 'px_vol_text', label: 'Price×vol' }, { key: 'tier_text', label: 'Tier' }],
  rows: [
    // served order: rank 1 has the SMALLER 1M % on purpose — the FE must not re-sort.
    { rank: 1, symbol: 'ZZZ', href: '/sepa/ZZZ', perf_1m_text: '+41.0%', cap_text: '$2.4B', px_vol_text: '$520M', tier_text: 'Lead',
      criteria: [{ key: 'cap', label: 'cap > $100M', ok: true, value: '$2.4B', need: null },
        { key: 'px_vol_1w', label: 'price×vol 1W > $300M', ok: true, value: '$520M', need: null }] },
    { rank: 2, symbol: 'AAA', href: '/sepa/AAA', perf_1m_text: '+88.0%', cap_text: 'cap unknown — not filtered', px_vol_text: '$310M', tier_text: 'Mediocre',
      criteria: [{ key: 'cap', label: 'cap > $100M', ok: null, value: null, need: 'cap unknown — not filtered' },
        { key: 'px_vol_1w', label: 'price×vol 1W > $300M', ok: true, value: '$310M', need: null }] },
    { rank: 3, symbol: 'MMM', href: null, perf_1m_text: '+30.2%', cap_text: '$900M', px_vol_text: null, tier_text: 'Lag',
      criteria: [{ key: 'avg_vol', label: '10-day avg vol > 500K', ok: false, value: null, need: 'no daily bars cached' }] },
  ],
  not_screened_text: "12 not screened yet — daily facts pending — Luk's own post-close fetch not made yet",
  considerations_text: 'He is considering a $100M dollar-volume floor and filtering biotechs and buyouts/mergers out (iMBI3ZcQ6sU 1:17:58–1:18:43) — listed, not applied: HIS CALL',
  honesty: 'his settings as he showed them — UNMEASURED',
};

const mount = (s: LukScreen | null) => render(<MemoryRouter><LukScreens screen={s} /></MemoryRouter>);

describe('LukScreens', () => {
  it('rows in the SERVED order with the served heads and cells', () => {
    const { container } = mount(SCREEN);
    const order = Array.from(container.querySelectorAll('tbody tr')).map((tr) => tr.getAttribute('data-testid'));
    expect(order).toEqual(['luk-screen-row-ZZZ', 'luk-screen-row-AAA', 'luk-screen-row-MMM']);
    const heads = Array.from(container.querySelectorAll('thead th')).map((th) => th.textContent);
    expect(heads.slice(0, 6)).toEqual(['#', 'Ticker', '1M %', 'Cap', 'Price×vol', 'Tier']);
    expect(screen.getByTestId('luk-screen-row-ZZZ')).toHaveTextContent('+41.0%');
    expect(screen.getByTestId('luk-screen-link-ZZZ').getAttribute('href')).toBe('/sepa/ZZZ');
    expect(screen.getByTestId('luk-screen-title')).toHaveTextContent(SCREEN.title);
    expect(screen.getByTestId('luk-screen-sorted')).toHaveTextContent(SCREEN.sorted_by_text!);
  });

  it('criteria ticks: ✓ met, ✗ not met with the served need, · unjudged', () => {
    mount(SCREEN);
    expect(screen.getByTestId('luk-screen-crit-ZZZ-cap')).toHaveTextContent('✓ cap > $100M — $2.4B');
    expect(screen.getByTestId('luk-screen-crit-MMM-avg_vol')).toHaveTextContent('✗ 10-day avg vol > 500K (no daily bars cached)');
    expect(screen.getByTestId('luk-screen-crit-AAA-cap')).toHaveTextContent('· cap > $100M (cap unknown — not filtered)');
  });

  it('NEGATIVE: the "cap unknown — not filtered" row is KEPT (never dropped by the cap)', () => {
    mount(SCREEN);
    expect(screen.getByTestId('luk-screen-row-AAA')).toHaveTextContent('cap unknown — not filtered');
  });

  it('the served not-screened, considerations and honesty lines print verbatim', () => {
    mount(SCREEN);
    expect(screen.getByTestId('luk-not-screened')).toHaveTextContent(SCREEN.not_screened_text!);
    expect(screen.getByTestId('luk-considerations')).toHaveTextContent(SCREEN.considerations_text!);
    expect(screen.getByTestId('luk-screen-honesty')).toHaveTextContent(SCREEN.honesty!);
  });

  it('NEGATIVE: a row with no href prints the bare symbol; a null cell prints nothing (never "null"/"undefined")', () => {
    const { container } = mount(SCREEN);
    expect(screen.queryByTestId('luk-screen-link-MMM')).toBeNull();
    expect(screen.getByTestId('luk-screen-row-MMM')).toHaveTextContent('MMM');
    expect(container.textContent).not.toMatch(/undefined|\bnull\b|NaN/);
  });

  it('string heads zip with the served row fields', () => {
    const s: LukScreen = { ...SCREEN, heads: ['#', 'Ticker', 'Price', '1M %'],
      rows: [{ rank: 1, symbol: 'QQQ1', href: null, price_text: '10.00', perf_1m_text: '+5.0%', criteria: [] }] };
    const { container } = mount(s);
    const cells = Array.from(container.querySelectorAll('tbody tr td')).map((td) => td.textContent);
    expect(cells.slice(0, 4)).toEqual(['1', 'QQQ1', '10.00', '+5.0%']);
  });

  it('NEGATIVE: an empty screen prints no table but keeps the served lines; no screen renders nothing', () => {
    const r = mount({ ...SCREEN, rows: [] });
    expect(screen.queryByTestId('luk-screen-table')).toBeNull();
    expect(screen.getByTestId('luk-not-screened')).toBeTruthy();
    r.unmount();
    const { container } = mount(null);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: no b-word, no "edge"', () => {
    const { container } = mount(SCREEN);
    expect(container.textContent).not.toMatch(new RegExp('b' + 'ounce', 'i'));
    expect(container.textContent).not.toMatch(/\bedge\b/i);
  });
});
