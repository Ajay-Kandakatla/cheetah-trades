import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import type { GgHighSiBlock } from '../lib/gajjala';

/* 🩳 GgHighSiPanel — the served `basis_text` line (2026-11-24, spec sidilute §3.6 / §3.7 [C7]). Ajay: "Make sure we are
 * looking for Dilution.." · "Also split related events and filing so we flag them in the right way". A name that was High /
 * EXTREME on the float on file but whose float is stale or across a split is not tiered, so not listed — the served line
 * names it, printed verbatim right after the counts line. NEGATIVES: a number / empty / NaN / null / absent → nothing drawn,
 * and the panel's testids are exactly today's. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

import { GgHighSiPanel } from './GgHighSi';

const BASIS_TEXT = '⚠️ High or EXTREME on the float on file, but that float is stale or across a split — not tiered, so not listed: '
  + 'SMTK — 🩳 SI 8.9% shs out · 1.0d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13';
const BLOCK: GgHighSiBlock = {
  title: 'served hs title', counts_text: 'served counts', adds_text: 'served adds', asof_text: 'served as of',
  honesty: 'served honesty', n: 3, n_read: 102, chartless: [],
};
const wrap = { wrapper: ({ children }: { children: ReactNode }) => <MemoryRouter>{children}</MemoryRouter> };
const tids = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="gg-hs"]')].map((e) => e.getAttribute('data-testid'));

afterEach(() => { vi.restoreAllMocks(); });

describe('🩳 GgHighSiPanel — basis_text', () => {
  it('prints the served basis_text verbatim, right after the counts line', () => {
    const { container } = render(<GgHighSiPanel block={{ ...BLOCK, basis_text: BASIS_TEXT }} />, wrap);
    const el = screen.getByTestId('gg-hs-basis');
    expect(el.textContent).toBe(BASIS_TEXT);
    expect(el.tagName).toBe('P');
    const ids = tids(container);
    expect(ids.indexOf('gg-hs-basis')).toBe(ids.indexOf('gg-hs-counts') + 1);
    expect(screen.getByTestId('gg-hs-counts').nextElementSibling).toBe(el);
  });

  it('NEGATIVE: basis_text a number / empty / whitespace / NaN / null / undefined / absent → nothing drawn, testids as today', () => {
    const today = tids(render(<GgHighSiPanel block={{ ...BLOCK }} />, wrap).container);
    expect(today).not.toContain('gg-hs-basis');
    for (const v of [7, '', '   ', NaN, null, undefined, ['x'], { t: 'x' }]) {
      const { container, unmount } = render(<GgHighSiPanel block={{ ...BLOCK, basis_text: v as unknown as string }} />, wrap);
      expect(container.querySelector('[data-testid="gg-hs-basis"]'), String(v)).toBeNull();
      expect(tids(container), String(v)).toEqual(today);
      expect(container.textContent).not.toMatch(/NaN|undefined|\[object/);
      unmount();
    }
  });

  it('NEGATIVE: basis_text alone (no counts line) still prints; a null block prints nothing', () => {
    render(<GgHighSiPanel block={{ basis_text: BASIS_TEXT }} />, wrap);
    expect(screen.getByTestId('gg-hs-basis').textContent).toBe(BASIS_TEXT);
    const { container } = render(<GgHighSiPanel block={null} />, wrap);
    expect(container.innerHTML).toBe('');
  });
});
