import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import KeyLevelsBoardNote from './KeyLevelsBoardNote';
import type { CmKeyLevelsBoard } from '../lib/chartMaps';

/* 🔑 Key Levels tab header (Ajay 2026-09-28: "Also create me tab for keylevel
 * main. Sort them by stocks that are near lower keylevels"). The component
 * prints the SERVED sentences verbatim and composes nothing — every negative
 * below is a payload shape that must draw nothing rather than junk. */

const HEADER = '🔑 12 names sit above, or within the 0.15% break buffer of, a PWL / PML / 52wL not yet broken — closest first. Not listed: 0 through every low below them.';
const NOTE = '🔑 UNMEASURED — no study in this app says a stock near its prior-week low holds there or turns there.';
const board = (over: Partial<CmKeyLevelsBoard> = {}): CmKeyLevelsBoard => ({
  state: 'ready', session: '2026-09-29', phase: 'rth', periods: ['PWL', 'PML', '52wL'],
  counts: { scanned: 12, ranked: 12, broken: 0, no_level: 0, stale: 0, no_print: 0,
            set_last_session: 0, no_turnover: 0, dropped_thin: 0, shown: 12 },
  header: HEADER, note: NOTE, built_at: '2026-09-29T10:02:11-04:00', measured: false, ...over,
});

describe('KeyLevelsBoardNote', () => {
  it('ready: prints the served header then the note, verbatim', () => {
    const { getByTestId } = render(<KeyLevelsBoardNote board={board()} />);
    const el = getByTestId('cm-keylevels-board');
    expect(el.getAttribute('data-state')).toBe('ready');
    const ps = el.querySelectorAll('p');
    expect(ps).toHaveLength(2);
    expect(ps[0].textContent).toBe(HEADER);
    expect(ps[1].textContent).toBe(NOTE);
    expect(ps[0].getAttribute('role')).toBeNull();
  });

  it('zero counts render as the server wrote them ("0"), never blank', () => {
    const { container } = render(<KeyLevelsBoardNote board={board()} />);
    expect(container.textContent).toContain('Not listed: 0 through');
  });

  it('warming: role="status" and data-state="warming", counts null is fine', () => {
    const warm = '🔑 Reading every name’s prior-week low, prior-month low or 52-week low from the cached daily bars.';
    const { getByTestId } = render(
      <KeyLevelsBoardNote board={board({ state: 'warming', counts: null, header: warm, built_at: null })} />);
    const el = getByTestId('cm-keylevels-board');
    expect(el.getAttribute('data-state')).toBe('warming');
    expect(el.querySelector('p')!.getAttribute('role')).toBe('status');
    expect(el.querySelector('p')!.textContent).toBe(warm);
  });

  it('NEGATIVE: null / undefined / {} / empty header / non-string header → renders nothing, no crash', () => {
    const junk: unknown[] = [null, undefined, {}, 'x', 7, [],
      board({ header: '' }), board({ header: '   ' }),
      { ...board(), header: 42 }, { ...board(), header: null }, { ...board(), header: { t: 'x' } }];
    for (const b of junk) {
      let html = 'unset';
      expect(() => {
        html = render(<KeyLevelsBoardNote board={b as CmKeyLevelsBoard} />).container.innerHTML;
      }).not.toThrow();
      expect(html).toBe('');
    }
  });

  it('NEGATIVE: a missing / empty / non-string note prints only the header', () => {
    for (const note of ['', '  ', null, 5, undefined]) {
      const { getByTestId, unmount } = render(
        <KeyLevelsBoardNote board={{ ...board(), note } as unknown as CmKeyLevelsBoard} />);
      expect(getByTestId('cm-keylevels-board').querySelectorAll('p')).toHaveLength(1);
      unmount();
    }
  });

  it('NEGATIVE: no NaN / undefined / bounce in what it prints', () => {
    const { container } = render(<KeyLevelsBoardNote board={board()} />);
    const t = container.textContent || '';
    for (const bad of ['NaN', 'undefined', '[object Object]']) expect(t.includes(bad), bad).toBe(false);
    expect(/bounce/i.test(t)).toBe(false);
  });
});
