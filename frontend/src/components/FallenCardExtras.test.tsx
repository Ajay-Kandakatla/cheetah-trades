/* 📉 FallenCardExtras — the served 💥 / Bonde lines under one card (2026-10-02).
 *
 * Ajay, verbatim: "But I also need you to capture informations about sales
 * like Bondes and other indicators based on Bondes formula please." and "also
 * add things like possible catalyst that made is drop like that."
 *
 * Every string asserted is one the test served. Negatives: no block → nothing,
 * an item without a url → no link, empty items → the served empty sentence,
 * never junk. */
import { describe, expect, it, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import FallenCardExtras from './FallenCardExtras';
import type { CmTile } from '../lib/chartMaps';
import type { BondePickLegend } from '../lib/bondePicks';
import FIXTURE from './__fixtures__/fallen_tab_2026_10_02.json';

type P = { tiles: CmTile[]; fallen_board: { pick_legend: BondePickLegend } };
const READY = (FIXTURE as unknown as Record<string, P>).default_40;
const LEGEND = READY.fallen_board.pick_legend;
const real = (sym: string) => JSON.parse(JSON.stringify(READY.tiles.find((t) => t.symbol === sym))) as CmTile;
const drop = (over: Record<string, unknown> = {}) => ({
  date: '2026-02-12', c2c_pct: -19.68, gap_pct: -11.56, intraday_pct: -9.18, larger_leg: 'gap', vol_x50: 3.62,
  share_of_fall_pct: 19.28, prev_close: 456.81, close: 366.91, window: { lo: '2026-02-11', hi: '2026-02-13' },
  line: 'L-served', items: [], empty: 'E-served', group: { line: 'G-served' }, ...over,
});
const tile = (fallenOver: Record<string, unknown> = {}, over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'ZZZ', href: '/sepa/ZZZ', bars: [], bands: [], lines: [], markers: [], stats: [], why: '',
  pick: { legs: { eps_yoy_100: { ok: true, value: 120, why: null } } },
  fallen: {
    hit: { text: 'HIT-served', class: 'nothing', date: '2026-02-12' },
    bonde: { n_pass: 1, n_read: 1, n_not_read: 12, line: 'BONDE-served' },
    drops_head: 'HEAD-served', drops: [drop()],
    ...fallenOver,
  } as never,
  ...over,
});
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];

afterEach(cleanup);

describe('FallenCardExtras — served lines verbatim', () => {
  it('the 💥 line, the Bonde line, the pick chips, and the drops fold with line / group / empty', () => {
    const { container } = render(<FallenCardExtras tile={tile()} legend={LEGEND} />);
    expect(screen.getByTestId('cm-fallen-hit-ZZZ').textContent).toBe('HIT-served');
    expect(screen.getByTestId('cm-fallen-bonde-ZZZ').textContent).toBe('BONDE-served');
    expect(screen.getByTestId('bd-pick-ZZZ')).toBeTruthy();
    const fold = screen.getByTestId('cm-fallen-drops-ZZZ');
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.hasAttribute('open')).toBe(false);
    expect(fold.querySelector('summary')!.textContent).toBe('HEAD-served');
    expect(screen.getByTestId('cm-fallen-drop-line-ZZZ-0').textContent).toBe('L-served');
    expect(screen.getByTestId('cm-fallen-drop-group-ZZZ-0').textContent).toBe('G-served');
    expect(screen.getByTestId('cm-fallen-drop-empty-ZZZ-0').textContent).toBe('E-served');
    for (const bad of JUNK) expect(container.innerHTML.includes(bad), bad).toBe(false);
  });

  it('items: the served text, a link (new tab, noreferrer) ONLY when the item carries a url; the empty line then hides', () => {
    const items = [
      { kind: 'earnings', date: '2026-02-11', text: 'I-earn', url: null, source: 'earnings_watch' },
      { kind: 'news', date: '2026-02-12', text: 'I-news', url: 'https://example.com/a', source: 'finnhub' },
      { kind: 'filing', date: '2026-02-12', text: 'I-file', url: '', source: 'promo' },
    ];
    const { container } = render(<FallenCardExtras tile={tile({ drops: [drop({ items })] })} legend={LEGEND} />);
    expect(screen.getByTestId('cm-fallen-item-ZZZ-0-0').textContent).toBe('I-earn');
    expect(screen.getByTestId('cm-fallen-item-ZZZ-0-0').querySelector('a')).toBeNull();
    const a = screen.getByTestId('cm-fallen-item-ZZZ-0-1').querySelector('a')!;
    expect(a.textContent).toBe('I-news');
    expect(a.getAttribute('href')).toBe('https://example.com/a');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noreferrer');
    // NEGATIVE: a blank url is no url
    expect(screen.getByTestId('cm-fallen-item-ZZZ-0-2').querySelector('a')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-drop-empty-ZZZ-0')).toBeNull();
    expect(container.querySelectorAll('.cm-fallen-drops a')).toHaveLength(1);
  });

  it('the Bonde legend is NOT repeated per card (it renders once above the grid) and the sales line is not repeated (it is a face stat)', () => {
    render(<FallenCardExtras tile={tile({ sales: { line: 'SALES-served' } })} legend={LEGEND} />);
    expect(screen.queryByTestId('bonde-criteria')).toBeNull();
    expect(screen.queryByText('SALES-served')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-sales-ZZZ')).toBeNull();
  });

  it('NEGATIVE: no fallen block → renders nothing', () => {
    for (const f of [undefined, null, 'x', [1], 7]) {
      const { container } = render(<FallenCardExtras tile={tile({}, { fallen: f as never })} legend={LEGEND} />);
      expect(container.innerHTML, String(f)).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: malformed parts are skipped — no hit, no bonde line, junk drops / items, no drops head → no fold', () => {
    const { container } = render(<FallenCardExtras tile={tile({
      hit: { text: 7 }, bonde: null,
      drops: [null, 'x', drop({ line: 5, group: 'g', items: [null, { text: '' }, { text: 9 }, { text: 'I-ok', url: 3 }], empty: 'E' })],
    })} legend={LEGEND} />);
    expect(screen.queryByTestId('cm-fallen-hit-ZZZ')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-bonde-ZZZ')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-drop-line-ZZZ-0')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-drop-group-ZZZ-0')).toBeNull();
    expect(screen.getByTestId('cm-fallen-item-ZZZ-0-0').textContent).toBe('I-ok');
    expect(screen.getByTestId('cm-fallen-item-ZZZ-0-0').querySelector('a')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-drop-empty-ZZZ-0')).toBeNull();
    for (const bad of JUNK) expect(container.innerHTML.includes(bad), bad).toBe(false);
    cleanup();
    render(<FallenCardExtras tile={tile({ drops_head: null })} legend={LEGEND} />);
    expect(screen.queryByTestId('cm-fallen-drops-ZZZ')).toBeNull();
    cleanup();
    render(<FallenCardExtras tile={tile({ drops: [] })} legend={LEGEND} />);
    expect(screen.queryByTestId('cm-fallen-drops-ZZZ')).toBeNull();
  });

  it('NEGATIVE: no pick block → no chips (an empty chip line would read as a name that failed everything)', () => {
    render(<FallenCardExtras tile={tile({}, { pick: null })} legend={LEGEND} />);
    expect(screen.queryByTestId('bd-pick-ZZZ')).toBeNull();
    expect(screen.getByTestId('cm-fallen-hit-ZZZ').textContent).toBe('HIT-served');
  });
});

describe('FallenCardExtras — on the fixture tiles', () => {
  it.each(READY.tiles.map((t) => [t.symbol]))('%s: the served hit text, Bonde line and chips; never bounce / fake / junk', (sym) => {
    const t = real(sym);
    const { container } = render(<FallenCardExtras tile={t} legend={LEGEND} />);
    expect(screen.getByTestId(`cm-fallen-hit-${sym}`).textContent).toBe(t.fallen!.hit.text);
    expect(screen.getByTestId(`cm-fallen-bonde-${sym}`).textContent).toBe(t.fallen!.bonde.line);
    expect(screen.getByTestId(`bd-pick-${sym}`)).toBeTruthy();
    expect(t.fallen!.hit.text).toContain('possible:');
    for (const bad of JUNK) expect(container.innerHTML.includes(bad), `${sym} ${bad}`).toBe(false);
    expect(/bounce|fake/i.test(container.textContent || '')).toBe(false);
  });
});
