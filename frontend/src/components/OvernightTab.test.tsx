import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

/* Chart Maps ▸ Overnight — the two subs (BUILD_SPEC16 D1 / §3.7). Both children
 * are mocked: this file pins which one mounts, the `on_sub` param and that the
 * Gappers sub never reaches /overnight/session. */

vi.mock('./OvernightGappers', () => ({
  OvernightGappers: ({ profile, onPick }: any) => (
    <div data-testid="gappers-mock" data-profile={profile}>
      <button type="button" onClick={() => onPick?.('SNDK')}>pick-gapper</button>
    </div>
  ),
}));
vi.mock('./OvernightSessionBoard', () => ({
  default: ({ onPick }: any) => (
    <div data-testid="session-mock">
      <button type="button" onClick={() => onPick?.('QQQ')}>pick-session</button>
    </div>
  ),
}));

import OvernightTab from './OvernightTab';

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}

const draw = (search = '?tab=overnight', onPick = vi.fn()) => render(
  <MemoryRouter initialEntries={[`/chart-maps${search}`]}>
    <OvernightTab onPick={onPick} />
    <Loc />
  </MemoryRouter>,
);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('OvernightTab', () => {
  it('defaults to the 🌙 Overnight session sub', () => {
    draw();
    expect(screen.getByTestId('session-mock')).toBeTruthy();
    expect(screen.queryByTestId('gappers-mock')).toBeNull();
    const sess = screen.getByTestId('ons-sub-session');
    expect(sess.textContent).toBe('\u{1F319} Overnight session');
    expect(sess.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('ons-sub-gappers').textContent).toBe('Gappers');
  });

  it('NEGATIVE: an unknown on_sub lands on the session sub', () => {
    draw('?tab=overnight&on_sub=bogus');
    expect(screen.getByTestId('session-mock')).toBeTruthy();
    expect(screen.queryByTestId('gappers-mock')).toBeNull();
  });

  it('on_sub=gappers mounts the unchanged OvernightGappers (aggressive profile)', () => {
    draw('?tab=overnight&on_sub=gappers');
    const g = screen.getByTestId('gappers-mock');
    expect(g.getAttribute('data-profile')).toBe('aggressive');
    expect(screen.queryByTestId('session-mock')).toBeNull();
  });

  it('a sub click writes on_sub and keeps the rest of the address', () => {
    draw('?tab=overnight&universe=full');
    fireEvent.click(screen.getByTestId('ons-sub-gappers'));
    const q = new URLSearchParams(screen.getByTestId('loc').textContent || '');
    expect(q.get('on_sub')).toBe('gappers');
    expect(q.get('tab')).toBe('overnight');
    expect(q.get('universe')).toBe('full');
    expect(screen.getByTestId('gappers-mock')).toBeTruthy();
    fireEvent.click(screen.getByTestId('ons-sub-session'));
    expect(new URLSearchParams(screen.getByTestId('loc').textContent || '').get('on_sub')).toBe('session');
    expect(screen.getByTestId('session-mock')).toBeTruthy();
  });

  it('both subs hand a picked row to the same onPick', () => {
    const onPick = vi.fn();
    draw('?tab=overnight', onPick);
    fireEvent.click(screen.getByText('pick-session'));
    fireEvent.click(screen.getByTestId('ons-sub-gappers'));
    fireEvent.click(screen.getByText('pick-gapper'));
    expect(onPick.mock.calls).toEqual([['QQQ'], ['SNDK']]);
  });

  // The real-board NEGATIVE (the Gappers sub never fetches /overnight/session, with a positive control)
  // lives in OvernightSessionBoard.test.tsx, where the board is not mocked.
});
