/* 👀 2026-11-27 (spec watch5m §3.6, WP tile) — Ajay: "So I can look at 5 mins charts like 6 in one go...". GgwLayoutPick
 * gains opt-in `options`, `disabled` + `disabledTitle`, and `layout: null`.
 * NEGATIVES: without options / disabled → exactly 1 · 2 · 4 · 9 as today (HTML identical to passing them explicitly);
 * a disabled pick's click calls nothing; `layout: null` lights nothing; a disabled pick with no disabledTitle keeps the
 * plain title; the card grid's prefix still renames every testid. */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GgwLayoutPick } from './GajjalaWatchLayout';
import { GGW_LAYOUT_ORDER, type GgwLayout } from '../lib/gajjalaWatch';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const btns = () => Array.from(screen.getByTestId('ggw-layout').querySelectorAll('button'));

describe('GgwLayoutPick options / disabled / layout null', () => {
  it('options={[6, 9, 12]} → three buttons ggw-layout-6/9/12, titles "N per screen", the label kept', () => {
    const onPick = vi.fn();
    render(<GgwLayoutPick<number> layout={9} options={[6, 9, 12]} onPick={onPick} />);
    expect(btns().map((b) => b.getAttribute('data-testid'))).toEqual(['ggw-layout-6', 'ggw-layout-9', 'ggw-layout-12']);
    expect(btns().map((b) => b.getAttribute('title'))).toEqual(['6 per screen', '9 per screen', '12 per screen']);
    expect(btns().map((b) => b.textContent)).toEqual(['6', '9', '12']);
    expect(screen.getByTestId('ggw-layout-9').className).toBe('ggw-btn ggw-layout-btn is-on');
    expect(screen.getByTestId('ggw-layout-9').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('ggw-layout').textContent).toContain('per screen');
    fireEvent.click(screen.getByTestId('ggw-layout-12'));
    expect(onPick).toHaveBeenCalledWith(12);
  });
  it('disabled={[12]} disabledTitle="x" → that button is disabled, its title ends with "x"; NEGATIVE a click calls nothing', () => {
    const onPick = vi.fn();
    render(<GgwLayoutPick<number> layout={6} options={[6, 9, 12]} disabled={[12]} disabledTitle="x" onPick={onPick} />);
    const b = screen.getByTestId('ggw-layout-12') as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.getAttribute('title')).toBe('12 per screen — x');
    expect(b.getAttribute('title')!.endsWith('x')).toBe(true);
    fireEvent.click(b);
    expect(onPick).not.toHaveBeenCalled();
    /* the offered ones stay plain and live */
    expect((screen.getByTestId('ggw-layout-9') as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByTestId('ggw-layout-9').hasAttribute('disabled')).toBe(false);
    expect(screen.getByTestId('ggw-layout-9').getAttribute('title')).toBe('9 per screen');
    fireEvent.click(screen.getByTestId('ggw-layout-9'));
    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onPick).toHaveBeenCalledWith(9);
  });
  it('NEGATIVE: every pick disabled → still all drawn (greyed, never removed), none callable', () => {
    const onPick = vi.fn();
    render(<GgwLayoutPick<number> layout={null} options={[6, 9]} disabled={[6, 9]} disabledTitle="y" onPick={onPick} />);
    expect(btns()).toHaveLength(2);
    for (const b of btns()) { expect((b as HTMLButtonElement).disabled).toBe(true); fireEvent.click(b); }
    expect(onPick).not.toHaveBeenCalled();
  });
  it('NEGATIVE: a disabled pick without disabledTitle keeps the plain "N per screen" title', () => {
    render(<GgwLayoutPick<number> layout={6} options={[6, 9]} disabled={[9]} onPick={() => {}} />);
    expect(screen.getByTestId('ggw-layout-9').getAttribute('title')).toBe('9 per screen');
    expect((screen.getByTestId('ggw-layout-9') as HTMLButtonElement).disabled).toBe(true);
  });
  it('layout={null} → no is-on, no aria-pressed="true"', () => {
    render(<GgwLayoutPick<number> layout={null} options={[6, 9, 12]} onPick={() => {}} />);
    for (const b of btns()) {
      expect(b.className).toBe('ggw-btn ggw-layout-btn');
      expect(b.getAttribute('aria-pressed')).toBe('false');
    }
  });
  it('NEGATIVE: without options / disabled → exactly 1 · 2 · 4 · 9 as today, HTML identical to passing them explicitly', () => {
    const a = render(<GgwLayoutPick layout={2} onPick={() => {}} />);
    expect(btns().map((b) => b.textContent)).toEqual(GGW_LAYOUT_ORDER.map(String));
    expect(btns().map((b) => b.getAttribute('title'))).toEqual(GGW_LAYOUT_ORDER.map((l) => `${l} per screen`));
    for (const b of btns()) expect(b.hasAttribute('disabled')).toBe(false);
    expect(screen.getByTestId('ggw-layout-2').className).toBe('ggw-btn ggw-layout-btn is-on');
    const want = a.container.innerHTML;
    a.unmount();
    const b = render(<GgwLayoutPick<GgwLayout> layout={2} options={GGW_LAYOUT_ORDER} disabled={[]} disabledTitle="z"
                                               onPick={() => {}} />);
    expect(b.container.innerHTML).toBe(want);
  });
  it('NEGATIVE: the card grid\'s prefix still renames every testid with options given', () => {
    render(<GgwLayoutPick<number> layout={6} options={[6, 9]} disabled={[9]} disabledTitle="x" onPick={() => {}}
                                  testidPrefix="ggc-layout" />);
    expect(screen.queryByTestId('ggw-layout')).toBeNull();
    expect(screen.getByTestId('ggc-layout-6')).toBeTruthy();
    expect((screen.getByTestId('ggc-layout-9') as HTMLButtonElement).disabled).toBe(true);
  });
});
