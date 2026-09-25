import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { filterTile } from '../lib/chartOverlays';
import type { CmTile } from '../lib/chartMaps';
import type { BurstRead } from '../lib/momentumBurst';
import type { OuterChip } from '../lib/cardLadder';
import { VOYA, HCSG, ORKA_LIKE } from '../lib/__fixtures__/cardLadder.tiles';
import amdFixture from './__fixtures__/amd_raids_orcl_2026_09_24.json';

/* 📋 The Chart Maps card as an ENTRY LADDER (2026-09-25). Ajay 2026-09-24:
 * "I want them to categorized in a good way so I have enough info for entry of
 * a stock." ENTRY → PRICE → chart → SETUP → PLAN → TIMING → ▸ more; nothing
 * removed (the fold is `hidden`, never unmounted); the plan's prices print
 * with the Trade-lines box unticked. */

let path = '';
function Probe() { path = useLocation().pathname; return null; }

const draw = (tile: CmTile, props: {
  burst?: BurstRead | null; outerChips?: OuterChip[]; expandAll?: boolean;
} = {}) => render(
  <MemoryRouter initialEntries={['/chart-maps']}>
    <Probe />
    <PatternChart tile={tile} {...props} />
  </MemoryRouter>,
);

const TRADE_OFF = new Set(['trade']);           // the shipped default: Trade lines unticked
const before = (a: Element, b: Element) =>
  !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

describe('PatternChart — the entry ladder', () => {
  it('reads top to bottom: ENTRY < PRICE < chart < PLAN < TIMING < ▸ more', () => {
    const { container } = draw(filterTile(VOYA, TRADE_OFF));
    const order = ['.cm-rung-entry', '.cm-rung-price', 'svg.cm-svg', '.cm-rung-plan',
      '.cm-rung-timing', '.cm-more'].map((s) => container.querySelector(s)!);
    order.forEach((el) => expect(el).not.toBeNull());
    for (let i = 1; i < order.length; i += 1) expect(before(order[i - 1], order[i])).toBe(true);
    expect(container.querySelector('.cm-rung-entry')!.textContent).toContain('🎯 READY');
    expect(container.querySelector('.cm-approach')!.textContent)
      .toBe('↓ Came down from 97.37 (-1.3% today), holding 0.3% off the 95.78 low');
    expect(container.querySelector('.cm-approach')!.classList.contains('cm-approach-muted')).toBe(true);
  });

  it('prints Buy zone · entry, Stop and Target with the Trade-lines box UNTICKED', () => {
    const t = filterTile(VOYA, TRADE_OFF);
    expect(t.lines.some((l) => l.tone === 'buy')).toBe(false);          // not drawn …
    const { container } = draw(t);
    const plan = container.querySelector('.cm-rung-plan')!;
    expect(screen.getByText('Buy zone')).toBeInTheDocument();                 // … but printed
    expect(screen.getByText('94.86–97.08 · entry 96.09')).toBeInTheDocument();
    expect(plan.textContent).toContain('Stop93.44');
    expect(plan.textContent).toContain('Target103.05');
    expect(plan.textContent).toContain('R:R2.6R');
    expect(plan.textContent).toContain('room+7.2% -> 103.05');
    expect(plan.textContent).toContain('🪜 ceiling 2.7% wide');
    expect(screen.queryByText('Entry')).not.toBeInTheDocument();
  });

  it('NEGATIVE: no served band → a single Entry price, no Buy zone', () => {
    draw({ ...VOYA, enterable: { ...VOYA.enterable!, band: null } });
    expect(screen.queryByText('Buy zone')).not.toBeInTheDocument();
    expect(screen.getByText('Entry')).toBeInTheDocument();
    expect(screen.getAllByText('96.09').length).toBeGreaterThanOrEqual(1);
  });

  it('NEGATIVE: a NaN / undefined price drops its row — "NaN" and "undefined" never print', () => {
    const { container } = draw({
      ...VOYA,
      lines: [{ price: NaN, label: 'BUY', tone: 'buy' }, { price: undefined as any, label: 'STOP', tone: 'stop' },
              { price: 103.05, label: 'TARGET', tone: 'target' }],
      enterable: { ...VOYA.enterable!, band: { lo: NaN, hi: 97.08 } },
    });
    expect(screen.queryByText('Buy zone')).not.toBeInTheDocument();
    expect(screen.queryByText('Entry')).not.toBeInTheDocument();
    expect(screen.queryByText('Stop')).not.toBeInTheDocument();
    expect(screen.getByText('Target')).toBeInTheDocument();
    expect(container.innerHTML).not.toMatch(/NaN|undefined/);
  });

  it('the fold is hidden by default, its reads are in the DOM, and the toggle does not navigate', () => {
    const { container } = draw(filterTile(VOYA, TRADE_OFF));
    const fold = container.querySelector('.cm-more') as HTMLElement;
    expect(fold.hidden).toBe(true);
    expect(fold.textContent).toContain('Break-even');
    expect(fold.textContent).toContain('At Demand · favorable');
    expect(fold.textContent).toContain('— sector flat Financial Services -0.5% vs RSP (5d)');
    const btn = container.querySelector('.cm-badge-more') as HTMLButtonElement;
    expect(btn.textContent).toBe('▸ more · 6');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(btn.getAttribute('aria-controls')).toBe(fold.id);
    fireEvent.click(btn);
    expect(path).toBe('/chart-maps');
    expect(btn.getAttribute('aria-expanded')).toBe('true');
    expect(btn.textContent).toBe('▾ less');
    expect(fold.hidden).toBe(false);
    fireEvent.click(btn);
    expect(fold.hidden).toBe(true);
    expect(path).toBe('/chart-maps');
  });

  it('prints each fact once: no Bands / On board / Sector flow copy, the why tail gone', () => {
    const { container } = draw(filterTile(VOYA, TRADE_OFF));
    const txt = container.textContent || '';
    expect(txt).not.toContain('Bands');
    expect(txt).not.toContain('On board');
    expect(txt).not.toContain('Sector flow (5d)');
    expect(txt.match(/came down from 97\.37/gi)?.length).toBe(1);
    expect(screen.getAllByText('Last')).toHaveLength(1);                     // folded, still there
  });

  it('HCSG: At Supply · caution on the face in amber, beside 🎯 READY', () => {
    const { container } = draw(filterTile(HCSG, TRADE_OFF));
    const entry = container.querySelector('.cm-rung-entry')!;
    const zone = screen.getByText('At Supply · caution');
    expect(entry.contains(zone)).toBe(true);
    expect(zone.classList.contains('cm-badge-warn')).toBe(true);
  });

  it('a folded warn chip turns ▸ more amber with ⚠1 and names it in the title', () => {
    const { container } = draw(filterTile(ORKA_LIKE, TRADE_OFF));
    const btn = container.querySelector('.cm-badge-more')!;
    expect(btn.classList.contains('cm-badge-more-warn')).toBe(true);
    expect(btn.textContent).toBe('▸ more · 10 · ⚠1');
    expect(btn.getAttribute('title')).toContain('🧊 cold sector Biotechnology -2.1% vs RSP (5d)');
    expect(container.querySelector('.cm-rung-entry')!.textContent).toContain('⛔ floor swept');
    expect(container.querySelector('.cm-rung-entry')!.textContent).toContain('· weak day');
  });

  it('NEGATIVE: no folded warn → no ⚠, no amber class', () => {
    const { container } = draw(filterTile(VOYA, TRADE_OFF));
    const btn = container.querySelector('.cm-badge-more')!;
    expect(btn.classList.contains('cm-badge-more-warn')).toBe(false);
    expect(btn.textContent).not.toContain('⚠');
  });

  it('NEGATIVE: nothing to fold → no ▸ more button and no fold; empty rungs draw nothing', () => {
    const { container } = draw({
      symbol: 'BARE', href: '/sepa/BARE', bars: VOYA.bars, bands: [], lines: [], markers: [],
      stats: [], why: '',
    });
    expect(container.querySelector('.cm-badge-more')).toBeNull();
    expect(container.querySelector('.cm-more')).toBeNull();
    for (const r of ['entry', 'price', 'setup', 'timing']) {
      expect(container.querySelector(`.cm-rung-${r}`)).toBeNull();
    }
    expect(container.querySelector('.cm-rung-plan')!.textContent).toContain('Last');
  });

  it('the AMD verdict is the last badge before the raids chip, in TIMING; unticked → neither', () => {
    const t = (amdFixture as any).tile as CmTile;
    const { container, unmount } = draw(t);
    const items = container.querySelector('.cm-rung-timing .cm-rung-items')!;
    const kids = Array.from(items.children);
    const verdict = kids.findIndex((k) => k.textContent === 'AMD raided · today');
    const chip = kids.findIndex((k) => k.classList.contains('cm-amd-raids'));
    expect(verdict).toBeGreaterThanOrEqual(0);
    expect(chip).toBe(verdict + 1);
    expect(container.querySelector('.cm-more')?.querySelector('.cm-amd-raids')).toBeFalsy();
    unmount();
    const off = draw(filterTile(t, new Set(['amd'])));
    expect(off.container.textContent).not.toContain('AMD raided');
    expect(off.container.querySelector('.cm-amd-raids')).toBeNull();
  });

  it('NEGATIVE: no NaN, undefined or "bounce" anywhere in a rendered live tile', () => {
    for (const t of [VOYA, HCSG, ORKA_LIKE]) {
      const { container, unmount } = draw(filterTile(t, TRADE_OFF));
      expect(container.textContent || '').not.toMatch(/NaN|undefined/);   // case-sensitive: "Financial" is fine
      expect(container.textContent || '').not.toMatch(/bounce/i);
      unmount();
    }
  });

  it("outerChips=['band'] → no 🪜 on the tile; another list keeps it", () => {
    const a = draw(VOYA, { outerChips: ['band'] });
    expect(a.container.textContent).not.toContain('🪜');
    a.unmount();
    const b = draw(VOYA, { outerChips: ['growth', 'promo'] });
    expect(b.container.textContent).toContain('🪜 ceiling 2.7% wide');
  });

  it("outerChips=['enterable','watch'] → no 🎯 and no + Signals on the tile (the wrapper prints them)", () => {
    const { container } = draw(VOYA, { outerChips: ['enterable', 'watch'] });
    expect(container.textContent).not.toContain('🎯 READY');
    expect(screen.queryByRole('button', { name: /VOYA (to|from) Signals/ })).toBeNull();
    expect(screen.getByRole('button', { name: /VOYA in TradingView/ })).toBeInTheDocument();
  });
});

describe('PatternChart — PLAN names a line by what it is (repair 2026-09-25)', () => {
  /* Breaking serves its broken lid as {label:'BREAK', tone:'target'}
   * (board.py breaking tab). A stock at 54 over a 52 lid must never read
   * "Target 52.00" — a target below the price on a real-money read. */
  const bars = VOYA.bars.map((b, i, a) => (i === a.length - 1 ? { ...b, c: 54 } : b));
  const breaking = (lines: CmTile['lines']): CmTile => ({
    symbol: 'BRK', href: '/sepa/BRK', bars, bands: [], markers: [], stats: [], why: '',
    lines, enterable: { ...VOYA.enterable!, band: { lo: 50, hi: 52 } },
  });

  it('NEGATIVE: a BREAK line (tone target) prints as "BREAK 52.00", never "Target"', () => {
    const { container } = draw(filterTile(breaking([
      { price: 52, label: 'BREAK', tone: 'target' },
      { price: 54, label: 'now', tone: 'now' },
    ]), TRADE_OFF));
    const plan = container.querySelector('.cm-rung-plan')!.textContent || '';
    expect(plan).toContain('BREAK52.00');
    expect(plan).not.toContain('Target');
  });

  it('NEGATIVE: a 200d MA served as tone stop prints "200d", never "Stop"', () => {
    const { container } = draw(breaking([{ price: 48, label: '200d', tone: 'stop' }]));
    const plan = container.querySelector('.cm-rung-plan')!.textContent || '';
    expect(plan).toContain('200d48.00');
    expect(plan).not.toContain('Stop');
  });

  it('the canonical STOP / TARGET labels keep the fixed words', () => {
    const { container } = draw(filterTile(breaking([
      { price: 49, label: 'STOP', tone: 'stop' },
      { price: 60, label: 'TARGET', tone: 'target' },
    ]), TRADE_OFF));
    const plan = container.querySelector('.cm-rung-plan')!.textContent || '';
    expect(plan).toContain('Stop49.00');
    expect(plan).toContain('Target60.00');
  });
});

describe('PatternChart — ⊞ expand all (off by default)', () => {
  it('off / absent → every fold closed', () => {
    const { container } = draw(VOYA);
    expect((container.querySelector('.cm-more') as HTMLElement).hidden).toBe(true);
  });

  it('on → the fold opens; a hand click overrides; a new ⊞ answer clears the override', () => {
    const tree = (expandAll: boolean) => (
      <MemoryRouter initialEntries={['/chart-maps']}>
        <Probe />
        <PatternChart tile={VOYA} expandAll={expandAll} />
      </MemoryRouter>
    );
    const { container, rerender } = render(tree(true));
    const fold = () => container.querySelector('.cm-more') as HTMLElement;
    const btn = () => container.querySelector('.cm-badge-more') as HTMLButtonElement;
    expect(fold().hidden).toBe(false);
    expect(btn().getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(btn());                                 // closed by hand under ⊞
    expect(fold().hidden).toBe(true);
    rerender(tree(false));                                   // ⊟ collapse all
    expect(fold().hidden).toBe(true);
    fireEvent.click(btn());                                  // opened by hand under ⊟
    expect(fold().hidden).toBe(false);
    rerender(tree(true));                                    // ⊞ again: all open
    expect(fold().hidden).toBe(false);
    rerender(tree(false));
    expect(fold().hidden).toBe(true);
  });
});

describe('PatternChart — ⚡ burst sits in PRICE', () => {
  const BURST: BurstRead = {
    state: 'burst', on: true, rvol: 1.83, off_low_pct: 0.62,
    badge: '⚡ Momentum burst · 1.83× vol · +0.62% off low', title: 'served title',
  };

  it('burst ON → the ⚡ chip is in the PRICE rung, right after the approach line', () => {
    const { container } = draw(VOYA, { burst: BURST });
    const price = container.querySelector('.cm-rung-price')!;
    const chip = container.querySelector('.cm-badge-burst')!;
    expect(price.contains(chip)).toBe(true);
    expect(chip.previousElementSibling?.classList.contains('cm-approach')).toBe(true);
  });

  it('NEGATIVE: burst OFF (null) → no ⚡ chip anywhere, even with a read on the tile', () => {
    const { container } = draw({ ...VOYA, burst: BURST }, { burst: null });
    expect(container.querySelector('.cm-badge-burst')).toBeNull();
  });

  it('NEGATIVE: a burst alone still draws the PRICE rung; no burst and no price facts → no PRICE rung', () => {
    const bare: CmTile = { symbol: 'B', href: '/sepa/B', bars: VOYA.bars, bands: [], lines: [], markers: [], stats: [], why: '' };
    const a = draw(bare, { burst: BURST });
    expect(a.container.querySelector('.cm-rung-price .cm-badge-burst')).not.toBeNull();
    a.unmount();
    const b = draw(bare, { burst: null });
    expect(b.container.querySelector('.cm-rung-price')).toBeNull();
  });
});
