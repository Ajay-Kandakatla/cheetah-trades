/* UndervalueViewNote — the served 💎 / 🏷️ toggle (2026-09-29). */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import UndervalueViewNote from './UndervalueViewNote';
import type { CmUndervalueView } from '../lib/undervalueView';

const OPTIONS = [{ key: 'psg', label: '💎 P/S ÷ growth' }, { key: 'peers', label: '🏷️ vs peers' }];
const peersBlock = (over: Partial<CmUndervalueView> = {}): CmUndervalueView => ({
  param: 'uv', view: 'peers', default: 'psg', options: OPTIONS, measured: false,
  header: '🏷️ 3 at ≤ 50% of their peers’ P/S — served header',
  note: '🏷️ UNMEASURED — served note', counts: { passed: 3 }, constants: { min_peers: 5 }, ...over,
});
const psgBlock = (): CmUndervalueView => ({
  param: 'uv', view: 'psg', default: 'psg', options: OPTIONS, measured: false,
  header: null, note: null, counts: null, constants: null,
});

describe('UndervalueViewNote', () => {
  afterEach(cleanup);

  it('labels are served; pressed = served view; header + note verbatim', () => {
    render(<UndervalueViewNote block={peersBlock()} onView={() => {}} />);
    expect(screen.getByTestId('cm-uv-view-psg').textContent).toBe('💎 P/S ÷ growth');
    expect(screen.getByTestId('cm-uv-view-peers').textContent).toBe('🏷️ vs peers');
    expect(screen.getByTestId('cm-uv-view-peers').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-uv-view-psg').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('cm-uv-view-peers').className).toContain('cm-phase-on');
    expect(screen.getByTestId('cm-uv-header').textContent).toBe(peersBlock().header);
    expect(screen.getByTestId('cm-uv-note').textContent).toBe(peersBlock().note);
    expect(screen.getByTestId('cm-uv-board').getAttribute('data-view')).toBe('peers');
  });

  it('a click hands the key to the setter', () => {
    const onView = vi.fn();
    render(<UndervalueViewNote block={peersBlock()} onView={onView} />);
    fireEvent.click(screen.getByTestId('cm-uv-view-psg'));
    fireEvent.click(screen.getByTestId('cm-uv-view-peers'));
    expect(onView.mock.calls).toEqual([['psg'], ['peers']]);
  });

  it('the 💎 block renders the toggle only, 💎 pressed', () => {
    render(<UndervalueViewNote block={psgBlock()} onView={() => {}} />);
    expect(screen.getByTestId('cm-uv-view-psg').getAttribute('aria-pressed')).toBe('true');
    expect(screen.queryByTestId('cm-uv-header')).toBeNull();
    expect(screen.queryByTestId('cm-uv-note')).toBeNull();
  });

  it('NEGATIVE: a note equal to the header prints once', () => {
    const b = peersBlock({ note: peersBlock().header });
    render(<UndervalueViewNote block={b} onView={() => {}} />);
    expect(screen.getByTestId('cm-uv-header')).toBeTruthy();
    expect(screen.queryByTestId('cm-uv-note')).toBeNull();
  });

  it('NEGATIVE: absent / array / missing option / empty label render nothing', () => {
    const bad: unknown[] = [
      null, undefined, [], 'x',
      peersBlock({ options: [OPTIONS[0]] }),
      peersBlock({ options: [OPTIONS[0], { key: 'peers', label: '  ' }] }),
      peersBlock({ options: null as never }),
    ];
    for (const b of bad) {
      const { container } = render(<UndervalueViewNote block={b as never} onView={() => {}} />);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: junk fields never print junk text', () => {
    const b = peersBlock({ header: { x: 1 } as never, note: NaN as never, view: undefined as never });
    const { container } = render(<UndervalueViewNote block={b} onView={() => {}} />);
    const t = container.textContent || '';
    expect(t).not.toMatch(/\[object Object\]|NaN|undefined/);
    expect(screen.getByTestId('cm-uv-view-psg').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('cm-uv-view-peers').getAttribute('aria-pressed')).toBe('false');
  });
});
