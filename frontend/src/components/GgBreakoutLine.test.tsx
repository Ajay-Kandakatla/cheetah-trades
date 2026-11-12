import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GgBreakoutLine, GgBreakoutWord } from './GgBreakoutLine';

/* ⏸ No-breakout line (2026-11-12, no-breakout spec §3.3 / FE package). Every string below is TEST DATA standing in for
 * the served words (backend breakout_state.py); the component types none. NEGATIVES: null / undefined / empty or
 * non-string head → nothing; a state that is not ^[a-z_]+$ → no state class; no text → hint as the row title. */

const WAITING = {
  state: 'waiting',
  head: '⏸ no breakout since the trigger',
  detail: ' · last close 1.46 (+35.2% vs the trigger 1.08) · needs a close above 1.50 (the high since the trigger) on volume louder than 631.5K (the base\'s busiest bar) · 10 min since the trigger bar (10:30)',
  text: '⏸ no breakout since the trigger · last close 1.46 (+35.2% vs the trigger 1.08) · needs a close above 1.50 (the high since the trigger) on volume louder than 631.5K (the base\'s busiest bar) · 10 min since the trigger bar (10:30)',
  hint: 'served hint — display only, UNMEASURED',
};
const ROW = { state: 'no_break', head: '⏸ no breakout over 0.4451', detail: '', text: '⏸ no breakout over 0.4451', hint: 'served row hint' };

afterEach(() => cleanup());

describe('⏸ GgBreakoutLine — the card line, served words verbatim', () => {
  it('renders <strong>{head}</strong>{detail}; textContent === served text; title === hint; testid + classes', () => {
    const { container } = render(<GgBreakoutLine breakout={WAITING} sym="ABC" />);
    const el = container.querySelector('[data-testid="gg-brk-ABC"]') as HTMLElement;
    expect(el).not.toBeNull();
    expect(el.tagName).toBe('DIV');
    expect(el.querySelector('strong')?.textContent).toBe(WAITING.head);
    expect(el.firstElementChild?.tagName).toBe('STRONG');
    expect(el.textContent).toBe(WAITING.text);
    expect(el.textContent).toBe(WAITING.head + WAITING.detail);
    expect(el.getAttribute('title')).toBe(WAITING.hint);
    expect(el.classList.contains('gg-line')).toBe(true);
    expect(el.classList.contains('cm-note')).toBe(true);
    expect(el.classList.contains('gg-brk')).toBe(true);
    expect(el.classList.contains('gg-brk-waiting')).toBe(true);
  });

  it('every served word replaced by ZZ… renders as-is (the FE types none)', () => {
    const { container } = render(<GgBreakoutLine breakout={{ state: 'broke_vol', head: 'ZZ1', detail: 'ZZ2', text: 'ZZ3', hint: 'ZZ4' }} sym="Q" />);
    const el = container.querySelector('[data-testid="gg-brk-Q"]') as HTMLElement;
    expect(el.textContent).toBe('ZZ1ZZ2');
    expect(el.getAttribute('title')).toBe('ZZ4');
    expect(el.textContent).not.toMatch(/breakout|trigger|volume|⏸/);
  });

  it('head only (no detail) → just the bold head; no hint → no title attribute', () => {
    const { container } = render(<GgBreakoutLine breakout={{ state: 'no_break_yet', head: '⏸ no breakout yet' }} sym="X" />);
    const el = container.querySelector('[data-testid="gg-brk-X"]') as HTMLElement;
    expect(el.textContent).toBe('⏸ no breakout yet');
    expect(el.hasAttribute('title')).toBe(false);
    expect(el.textContent).not.toMatch(/undefined|null|NaN/);
  });

  it('NEGATIVE: null / undefined / non-object / empty, blank or non-string head → nothing', () => {
    const bad: any[] = [null, undefined, 'x', 42, {}, { head: '' }, { head: '   ' }, { head: null }, { head: 7 },
                        { head: { a: 1 } }, { state: 'waiting', detail: ' · d', text: 't', hint: 'h' }];
    for (const b of bad) {
      const { container } = render(<GgBreakoutLine breakout={b} sym="N" />);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: a state that is not ^[a-z_]+$ adds no state class (head still renders)', () => {
    for (const state of ['x y<', 'Waiting', 'broke-vol', '', 42, null, '<script>']) {
      const { container } = render(<GgBreakoutLine breakout={{ state: state as any, head: 'H' }} sym="S" />);
      const el = container.querySelector('[data-testid="gg-brk-S"]') as HTMLElement;
      expect(el.className).toBe('cm-note gg-line gg-brk');
      cleanup();
    }
  });
});

describe('⏸ GgBreakoutWord — the 📈 row word', () => {
  it('renders " · " + bold head; title === served text; testid gg-track-nobrk-ID', () => {
    const { container } = render(<GgBreakoutWord breakout={ROW} id="ABC-bull_flag" />);
    const el = container.querySelector('[data-testid="gg-track-nobrk-ABC-bull_flag"]') as HTMLElement;
    expect(el).not.toBeNull();
    expect(el.tagName).toBe('SPAN');
    expect(el.textContent).toBe(' · ' + ROW.head);
    expect(el.querySelector('strong')?.textContent).toBe(ROW.head);
    expect(el.getAttribute('title')).toBe(ROW.text);
    expect(el.className).toBe('gg-track-push gg-track-nobrk');
  });

  it('the row prints the head only — never the detail; title falls back to the hint when no text', () => {
    const { container } = render(<GgBreakoutWord breakout={{ ...WAITING, text: null }} id="I" />);
    const el = container.querySelector('[data-testid="gg-track-nobrk-I"]') as HTMLElement;
    expect(el.textContent).toBe(' · ' + WAITING.head);
    expect(el.textContent).not.toContain('last close');
    expect(el.getAttribute('title')).toBe(WAITING.hint);
    cleanup();
    const c2 = render(<GgBreakoutWord breakout={{ head: 'H' }} id="J" />).container;
    expect(c2.querySelector('[data-testid="gg-track-nobrk-J"]')?.hasAttribute('title')).toBe(false);
  });

  it('NEGATIVE: absent / null / empty or non-string head → nothing', () => {
    for (const b of [null, undefined, {}, { head: '' }, { head: ' ' }, { head: 0 }, { text: 'only text' }] as any[]) {
      const { container } = render(<GgBreakoutWord breakout={b} id="Z" />);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });
});
