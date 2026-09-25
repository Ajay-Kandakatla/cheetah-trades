import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LIVE from './__fixtures__/key_levels_live_orcl_2026_09_25.json';
import { PatternChart } from './PatternChart';
import type { CmTile } from '../lib/chartMaps';

/* 🔑 LIVE captures, not hand-built: GET /chart-maps/support?symbol=ORCL&studies=true
 * at tf daily / 15m / 5m_today from the key-levels branch API on 2026-09-25
 * ~12:20 ET (market open). Ajay: "I wanna know when key levels are broken for a
 * stock." ORCL opened 138.57, under last week's low 139.00, so PWL reads broken
 * (gapped through ↓) on every frame. These prove the REAL payload renders:
 * fuchsia 🔑 lines, the broken one dashed, the chip in PRICE, no junk strings. */

const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity', 'bounce', 'Bounce'];
const draw = (tf: keyof typeof LIVE) =>
  render(<MemoryRouter><PatternChart tile={(LIVE as any)[tf].tile as CmTile} /></MemoryRouter>);

for (const tf of ['daily', '15m', '5m_today'] as const) {
  describe('live ORCL key levels — ' + tf, () => {
    it('renders 🔑 lines in the key colour, the broken PWL dashed, and no junk', () => {
      const { container } = draw(tf);
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), bad).toBe(false);
      const key = Array.from(container.querySelectorAll('line[data-tone="key"], line[data-tone="key_broken"]'));
      expect(key.length).toBeGreaterThan(0);
      for (const l of key) expect(l.getAttribute('stroke') || '').toContain('--cm-key');
      const broken = container.querySelectorAll('line[data-tone="key_broken"]');
      expect(broken.length).toBeGreaterThan(0);
      for (const l of Array.from(broken)) expect(l.getAttribute('stroke-dasharray')).toBe('3,3');
      expect(container.textContent || '').toContain('PWL');
    });

    it('prints the served chip once, in PRICE', () => {
      const { container } = draw(tf);
      const pills = container.querySelectorAll('.cm-keylevel');
      expect(pills.length).toBe(1);
      expect(pills[0].textContent).toBe((LIVE as any)[tf].tile.key_levels.chip.text);
      expect(pills[0].textContent).toContain('PWL 139.00');
    });
  });
}

describe('live ORCL key levels — per frame', () => {
  it('the intraday frames add the prior-day levels; the daily frame does not', () => {
    const labels = (tf: keyof typeof LIVE) => ((LIVE as any)[tf].tile.lines || [])
      .filter((l: any) => String(l.tone || '').startsWith('key')).map((l: any) => String(l.label));
    expect(labels('daily').some((s: string) => /PDH|PDL/.test(s))).toBe(false);
    expect(labels('15m').some((s: string) => /PDH|PDL/.test(s))).toBe(true);
    expect(labels('5m_today').some((s: string) => /pre-mkt/.test(s))).toBe(true);
    expect(labels('daily').some((s: string) => /pre-mkt/.test(s))).toBe(false);
  });
});
