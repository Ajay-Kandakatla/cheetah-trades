import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import intraday from './__fixtures__/amd_raids_live_orcl_2026_09_24_intraday.json';
import closedP from './__fixtures__/amd_raids_live_orcl_2026_09_24_closed.json';
import { PatternChart } from './PatternChart';
import type { CmTile } from '../lib/chartMaps';

/* 🌀 LIVE captures, not hand-built: GET /chart-maps/support?symbol=ORCL&studies=true
 * from the worktree route on 2026-09-24 — `closed` at 17:09 ET (today's bar
 * closed) and `intraday` with the route's clock pinned to 13:00 ET (live print
 * 139.34, session low 133.48). Ajay: "Show all the possible raids, past ones
 * too and todays too." These prove a REAL payload renders — no junk strings,
 * the 09-01 raid with its markup, today's row not closed. */

const draw = (payload: unknown) => {
  const tile = (payload as any).tile as CmTile;
  return render(<MemoryRouter><PatternChart tile={tile} /></MemoryRouter>);
};

const marks = (c: HTMLElement) => Array.from(c.querySelectorAll('g.pc-amd-raid'))
  .map((g) => g.getAttribute('data-raid-mark'));

const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity', 'bounce', 'Bounce'];

for (const [name, payload] of [['intraday', intraday], ['closed', closedP]] as const) {
  describe('live ORCL payload — ' + name, () => {
    it('opens the list and prints no junk', () => {
      const { container } = draw(payload);
      const chip = container.querySelector('.cm-amd-raids-chip') as HTMLElement;
      expect(chip).toBeTruthy();
      fireEvent.click(chip);
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), bad).toBe(false);
      const txt = container.textContent || '';
      expect(txt).toContain('2026-09-01');
      expect(txt).toContain('marked up 2026-09-03');
      expect(container.querySelectorAll('.cm-amd-raids-row').length).toBeGreaterThan(10);
    });

    it('draws only low raids, numbered by chain; 09-01 is #6', () => {
      const { container } = draw(payload);
      const m = marks(container);
      expect(m).toContain('6');
      expect(m.some((x) => (x || '').startsWith('H'))).toBe(false);
      const g = container.querySelector('g.pc-amd-raid[data-raid-mark="6"]');
      expect(g?.querySelector('title')?.textContent || '').toContain('2026-09-01');
    });
  });
}

describe('live ORCL payload — today', () => {
  it('intraday: today is #7, dashed, and says not closed', () => {
    const { container } = draw(intraday);
    const g = container.querySelector('g.pc-amd-raid[data-raid-mark="7"]') as Element;
    expect(g).toBeTruthy();
    expect(g.getAttribute('class')).toContain('pc-amd-raid-live');
    expect(container.querySelector('.cm-amd-raids-chip')!.textContent)
      .toContain('today low reclaimed (not closed)');
    fireEvent.click(container.querySelector('.cm-amd-raids-chip') as HTMLElement);
    expect(container.textContent).toContain('not closed');
  });

  it('NEGATIVE closed: today is a closed raid (#7, live outcome), never a dashed circle', () => {
    const { container } = draw(closedP);
    const g = container.querySelector('g.pc-amd-raid[data-raid-mark="7"]') as Element;
    expect(g).toBeTruthy();
    expect(g.getAttribute('class')).not.toContain('pc-amd-raid-live');
    expect(container.querySelector('.pc-amd-raid-live')).toBeNull();
    expect(container.querySelector('.cm-amd-raids-chip')!.textContent).not.toContain('not closed');
  });
});
