/* 🔀 <EmaBlinkDot> / <EmaBlinkLine> (2026-11-15, SPEC blinker §3.9, WP-E (a)). The dot's class is the served tier, its
 * label the served sentence, its hover the served short title; the line prints the served sentence verbatim with the
 * served state as its colour class. NEGATIVES: blink false / state none / an unknown tier / null / junk → nothing. */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { EmaBlinkDot, EmaBlinkLine } from './EmaBlink';
import { EMA_BLINK_TIERS } from '../lib/emaBlink';

afterEach(() => cleanup());

const TEXT = '◐ served closing-in sentence';
const TITLE = '🔀 served short title';
const near = { state: 'closing_in', tier: 'near', blink: true, text: TEXT, title: TITLE };

describe('🔀 EmaBlinkDot', () => {
  it('renders the served tier class, the served text as aria-label and the served title on hover', () => {
    const { container } = render(<EmaBlinkDot block={near} testid="d" />);
    const d = container.querySelector('[data-testid="d"]')!;
    expect(d.tagName).toBe('SPAN');
    expect(d.className).toBe('ema-blink-dot ema-blink-near');
    expect(d.getAttribute('role')).toBe('img');
    expect(d.getAttribute('aria-label')).toBe(TEXT);
    expect(d.getAttribute('title')).toBe(TITLE);
    expect(d.textContent).toBe('');
  });
  it('every served tier → its own class', () => {
    for (const tier of EMA_BLINK_TIERS) {
      const { container, unmount } = render(<EmaBlinkDot block={{ ...near, tier }} />);
      expect(container.querySelector('.ema-blink-dot')!.className).toBe(`ema-blink-dot ema-blink-${tier}`);
      unmount();
    }
  });
  it('NEGATIVE: blink false, state none, unknown tier, null, undefined, junk → nothing', () => {
    const cases: unknown[] = [
      { ...near, blink: false }, { state: 'none', tier: null, blink: false, text: null }, { ...near, tier: 'warp' },
      { ...near, blink: 'yes' }, null, undefined, 'near', 42, [],
    ];
    for (const c of cases) {
      const { container, unmount } = render(<EmaBlinkDot block={c as any} testid="d" />);
      expect(container.innerHTML).toBe('');
      unmount();
    }
  });
});

describe('🔀 EmaBlinkLine', () => {
  it('prints the served sentence verbatim with the state class; hover = the served title, or the info when given', () => {
    const { container, unmount } = render(<EmaBlinkLine block={near} sym="OMH" />);
    const l = container.querySelector('[data-testid="ema-blink-OMH"]')!;
    expect(l.textContent).toBe(TEXT);
    expect(l.className).toBe('cm-note ema-blink-line ema-blink-closing_in');
    expect(l.getAttribute('title')).toBe(TITLE);
    unmount();
    const r = render(<EmaBlinkLine block={near} sym="OMH" info="served long info" />);
    expect(r.container.querySelector('[data-testid="ema-blink-OMH"]')!.getAttribute('title')).toBe('served long info');
  });
  it('NEGATIVE: a junk state never becomes a class', () => {
    const { container } = render(<EmaBlinkLine block={{ ...near, state: 'x" onload="y' }} sym="OMH" />);
    expect(container.querySelector('[data-testid="ema-blink-OMH"]')!.className).toBe('cm-note ema-blink-line');
  });
  it('NEGATIVE: no line for a non-blinking block, a blank text, null or junk', () => {
    for (const c of [{ ...near, blink: false }, { ...near, text: '  ' }, { ...near, text: undefined }, null, undefined, 7]) {
      const { container, unmount } = render(<EmaBlinkLine block={c as any} sym="OMH" />);
      expect(container.innerHTML).toBe('');
      unmount();
    }
  });
});
