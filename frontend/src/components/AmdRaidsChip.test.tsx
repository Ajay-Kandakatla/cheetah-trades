import { describe, it, expect, vi, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Link, MemoryRouter, useLocation } from 'react-router-dom';
import fixture from './__fixtures__/amd_raids_orcl_2026_09_24.json';
import { AmdRaidsChip } from './AmdRaidsChip';
import { sanitizeAmdRaids, type AmdRaidsBlock } from '../lib/amdRaids';

/* 🌀 The AMD raids chip + drill-in (Ajay 2026-09-24: "Show all the possible
 * raids, past ones too and todays too."), driven through the REAL component
 * inside a <Link>, because every Support tile is one: a click that bubbles
 * would open the ticker page instead of the list. */

const RAW = (fixture as any).tile.amd_raids;
const BLOCK = sanitizeAmdRaids(JSON.parse(JSON.stringify(RAW)))!;

function Where() {
  const loc = useLocation();
  return <span data-testid="where">{loc.pathname}</span>;
}

const mount = (block: AmdRaidsBlock | null) => render(
  <MemoryRouter initialEntries={['/chart-maps']}>
    <Link to="/sepa/ORCL" aria-label="ORCL — open SEPA detail">
      <AmdRaidsChip block={block} />
    </Link>
    <Where />
  </MemoryRouter>,
);

const chip = () => screen.getByRole('button', { name: BLOCK.chip!.text });
const openPanel = () => {
  fireEvent.click(chip());
  return screen.getByRole('dialog', { name: 'AMD raids' });
};
const rowTexts = () => Array.from(document.querySelectorAll('.cm-amd-raids-row'))
  .map((el) => (el.textContent || '').trim());

describe('AmdRaidsChip', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('prints the served chip text verbatim, muted, with the served title', () => {
    mount(BLOCK);
    const b = chip();
    expect(b.textContent).toBe('3 low · 1 high raids · today low reclaimed (not closed)');
    expect(b.className).toContain('cm-badge-muted');
    expect(b).toHaveAttribute('aria-expanded', 'false');
    expect(b.getAttribute('title')).toBe(RAW.chip.title);
    // critique #4: the verdict basis note LEADS the hover
    expect(b.getAttribute('title')!.startsWith(RAW.verdict_basis_note)).toBe(true);
  });

  it('NEGATIVE — a null block or a block with no chip renders nothing', () => {
    const { container, unmount } = mount(null);
    expect(container.querySelector('.cm-amd-raids')).toBeNull();
    unmount();
    const r2 = mount({ ...BLOCK, chip: null });
    expect(r2.container.querySelector('.cm-amd-raids')).toBeNull();
    r2.unmount();
    const r3 = mount(sanitizeAmdRaids({ ...RAW, chip: { text: '' } }));
    expect(r3.container.querySelector('.cm-amd-raids')).toBeNull();
  });

  it('opens the list inside the Link WITHOUT navigating; clicks inside do not navigate either', () => {
    mount(BLOCK);
    expect(screen.getByTestId('where').textContent).toBe('/chart-maps');
    const dlg = openPanel();
    expect(chip()).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('where').textContent).toBe('/chart-maps');
    fireEvent.click(dlg);
    fireEvent.click(dlg.querySelector('.cm-amd-raids-row')!);
    expect(screen.getByTestId('where').textContent).toBe('/chart-maps');
    fireEvent.click(screen.getByRole('button', { name: 'Close AMD raids' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('where').textContent).toBe('/chart-maps');
  });

  it('today rows first, then closed rows newest first, with #mark prefixes', () => {
    mount(BLOCK);
    openPanel();
    const rows = rowTexts();
    expect(rows).toHaveLength(9);
    expect(rows[0].startsWith('#4')).toBe(true);
    expect(rows[0]).toContain('reclaimed; a raid only if it closes there');
    // the bearish holding row carries no number
    expect(rows[1].startsWith('today · not closed · high 140.34')).toBe(true);
    const closedDates = rows.slice(2).map((t) => /(\d{4}-\d{2}-\d{2})/.exec(t)![1]);
    expect(closedDates).toEqual([
      '2026-09-01', '2026-08-19', '2026-07-15', '2026-04-10', '2026-04-09',
      '2026-03-27', '2026-01-08',
    ]);
    expect(rows[2].startsWith('#3')).toBe(true);
    expect(rows[4].startsWith('#H1')).toBe(true);
    expect(rows[5].startsWith('#1·3')).toBe(true);
    expect(rows[6].startsWith('#1·2')).toBe(true);
    expect(rows[7].startsWith('#1')).toBe(true);
  });

  it('the off-chart root is #1 and muted; an un-numbered off-chart row reads — and is muted', () => {
    mount(BLOCK);
    openPanel();
    const els = Array.from(document.querySelectorAll('.cm-amd-raids-row'));
    const root = els.find((e) => (e.textContent || '').includes('2026-03-27 · '))!;
    expect(root.className).toContain('cm-amd-raids-row--off');
    expect(root.querySelector('.cm-amd-raids-mark')!.textContent).toBe('#1');
    const old = els.find((e) => (e.textContent || '').includes('2026-01-08 · '))!;
    expect(old.className).toContain('cm-amd-raids-row--off');
    expect(old.querySelector('.cm-amd-raids-mark')!.textContent).toBe('—');
    const rs = els.find((e) => (e.textContent || '').includes('2026-04-10 · '))!;
    expect(rs.className).toContain('cm-amd-raids-row--resweep');
    const today = els[0];
    expect(today.className).toContain('cm-amd-raids-row--today');
  });

  it('renders the summary, the basis, the verdict note and the measured note', () => {
    mount(BLOCK);
    const dlg = openPanel();
    const t = dlg.textContent || '';
    expect(t).toContain(RAW.summary);
    expect(t).toContain(RAW.basis);
    expect(t).toContain(RAW.verdict_basis_note);
    expect(t).toContain(RAW.note);
    expect(t).toContain('INVERTED');
    expect(t).toContain('has not been measured');
  });

  it('Escape closes the panel', () => {
    mount(BLOCK);
    openPanel();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(chip()).toHaveAttribute('aria-expanded', 'false');
  });

  it('a wide screen anchors the panel right; a narrow phone gets --fixed', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(
      { left: 900, right: 980, top: 0, bottom: 20, width: 80, height: 20, x: 900, y: 0, toJSON() {} } as DOMRect);
    const wide = mount(BLOCK);
    openPanel();
    expect(document.querySelector('.cm-amd-raids-panel--right')).not.toBeNull();
    wide.unmount();

    const orig = window.innerWidth;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 320 });
    try {
      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(
        { left: 100, right: 180, top: 0, bottom: 20, width: 80, height: 20, x: 100, y: 0, toJSON() {} } as DOMRect);
      mount(BLOCK);
      openPanel();
      const p = document.querySelector('.cm-amd-raids-panel')!;
      expect(p.className).toMatch(/cm-amd-raids-panel--(fixed|left)/);
      expect(p.className).toContain('cm-amd-raids-panel--fixed');
    } finally {
      Object.defineProperty(window, 'innerWidth', { configurable: true, value: orig });
    }
  });

  it('NEGATIVE — no NaN / undefined / null / bounce anywhere in the rendered text', () => {
    mount(BLOCK);
    const dlg = openPanel();
    const all = (document.body.textContent || '') + (chip().getAttribute('title') || '');
    for (const bad of [/NaN/, /undefined/, /\bnull\b/, /bounce/i]) expect(all).not.toMatch(bad);
    expect(dlg).toBeTruthy();
  });

  it('NEGATIVE — a junk payload with a valid chip renders the chip and an empty list, no crash', () => {
    const junk = sanitizeAmdRaids({
      chip: { text: 'no raids on this chart · 2 earlier', tone: 'good', title: NaN },
      raids: [{ direction: 'bullish', date: 'soon', raid_level: 'x' }, null],
      today: 'reclaimed', summary: 42, note: null, basis: undefined,
    });
    mount(junk);
    const b = screen.getByRole('button', { name: 'no raids on this chart · 2 earlier' });
    expect(b.className).toContain('cm-badge-muted');
    fireEvent.click(b);
    expect(document.querySelectorAll('.cm-amd-raids-row')).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/NaN|undefined|\bnull\b/);
  });
});
