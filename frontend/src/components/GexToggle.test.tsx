/* 🧲 GexToggle — the "🧲 Bullish GEX first" box: checked from its prop, the
 * served legend labels and counts, the served rule + scope in the hover, each
 * live-read state line, and the 0DTE sort-off (disabled + served reason). */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { GexToggle } from './GexToggle';
import RAW from './__fixtures__/gex_contract_example_2026_09_27.json?raw';
import type { GexLivePayload } from '../lib/gexRead';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FX = JSON.parse(RAW) as any;
const COUNTS = [
  { key: 'bullish', label: 'bullish', n: 3 }, { key: 'mixed', label: 'mixed', n: 1 },
  { key: 'bearish', label: 'bearish', n: 2 }, { key: 'none', label: 'no read', n: 3 },
];
const P = (over: Partial<GexLivePayload> = {}) => ({ ...(FX.live as GexLivePayload), pending: 0, ...over });
const live = (o: { payload?: GexLivePayload | null; loading?: boolean; error?: string | null; pending?: number }) =>
  ({ payload: null, loading: false, error: null, pending: 0, ...o });
const draw = (props: Partial<Parameters<typeof GexToggle>[0]> = {}) => render(
  <GexToggle on onChange={() => {}} counts={COUNTS} rule={FX.board.gex_rule} scope={FX.board.gex_scope}
             sortOff={null} live={live({ payload: P() })} {...props} />);
const q = (c: HTMLElement, s: string) => c.querySelector(s);

describe('GexToggle', () => {
  it('checked from its prop; served counts + labels; hover = rule + scope', () => {
    const { container } = draw();
    const box = q(container, 'label.gex-toggle input[type="checkbox"]') as HTMLInputElement;
    expect(box.checked).toBe(true);
    expect(box.disabled).toBe(false);
    expect(q(container, 'label.gex-toggle')!.textContent).toContain('🧲 Bullish GEX first');
    expect(q(container, '.gex-count')!.textContent).toBe(' · 3 bullish · 1 mixed · 2 bearish · 3 no read');
    expect(q(container, 'label.gex-toggle')!.getAttribute('title')).toBe(`${FX.board.gex_rule}\n${FX.board.gex_scope}`);
    expect(q(container, '.gex-sort-off')).toBeNull();
  });

  it('unchecked prop → unchecked box; a click reports the new state', () => {
    const onChange = vi.fn();
    const { container } = draw({ on: false, onChange });
    const box = q(container, 'label.gex-toggle input') as HTMLInputElement;
    expect(box.checked).toBe(false);
    fireEvent.click(box);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('each live state prints its line', () => {
    const cases: [ReturnType<typeof live>, string, boolean][] = [
      [live({ loading: true }), ' · live read…', false],
      [live({ payload: P({ pending: 2 }), pending: 2 }), ' · live: 2 still reading', false],
      [live({ payload: P(), error: 'HTTP 500' }), ' · live read failed — last close shown', true],
      [live({ payload: P({ market_closed: 'weekend', note: 'Market closed (weekend) — served.' }) }), ' · last close (market closed)', false],
      [live({ payload: P() }), ' · live 10:42 ET', false],
    ];
    for (const [l, text, failed] of cases) {
      const { container, unmount } = draw({ live: l });
      const el = q(container, '.gex-live')!;
      expect(el.textContent).toBe(text);
      expect(el.classList.contains('gex-live-failed')).toBe(failed);
      unmount();
    }
    const { container } = draw({ live: live({ payload: P({ market_closed: 'weekend', note: 'Market closed (weekend) — served.' }) }) });
    expect(q(container, '.gex-live')!.getAttribute('title')).toBe('Market closed (weekend) — served.');
  });

  it('NEGATIVE: no live state at all → no live line, no "undefined"', () => {
    const { container } = draw({ live: null, rule: null, scope: null });
    expect(q(container, '.gex-live')).toBeNull();
    expect(container.innerHTML).not.toMatch(/undefined|NaN|\[object Object\]/);
    expect(q(container, 'label.gex-toggle')!.hasAttribute('title')).toBe(false);
  });

  it('sortOff (0DTE) → box disabled, served label shown, served reason in the hover', () => {
    const so = FX.zero_dte.gex_sort_off;
    const { container } = draw({ sortOff: so });
    const box = q(container, 'label.gex-toggle input') as HTMLInputElement;
    expect(box.disabled).toBe(true);
    expect(q(container, '.gex-sort-off')!.textContent).toBe(` · ${so.label}`);
    expect(q(container, 'label.gex-toggle')!.getAttribute('title')).toContain(so.title);
  });

  it('NEGATIVE: no legend → no counts printed', () => {
    const { container } = draw({ counts: [] });
    expect(q(container, '.gex-count')!.textContent).toBe('');
  });
});
