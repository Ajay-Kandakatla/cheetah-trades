import { describe, it, expect } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { filterTile } from '../lib/chartOverlays';
import type { CmKeyLevels, CmLine, CmTile } from '../lib/chartMaps';

/* 🔑 Key levels on the chart tile (Ajay 2026-09-25: "With check box give it a
 * brigh color in the chart. I wanna know when key levels are broken for a
 * stock."). The block is SERVED (supply_demand/key_levels.tile_block): the
 * lines, the PRICE chip and the ▸ more line are printed, never composed here.
 * Solid fuchsia = a frozen level; 3,3 dash = through it now / closed through. */

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`, o: 100, h: 102, l: 98, c: 100 + (i % 2 ? 0.5 : -0.5), v: 1000,
}));

const KEY: CmLine = { price: 103, label: '🔑 PWH 103.00', tone: 'key' };
const BROKEN: CmLine = { price: 98.5, label: '🔑 PWL 98.50', tone: 'key_broken' };

const block = (over: Partial<CmKeyLevels> = {}): CmKeyLevels => ({
  session: '2026-09-25', frame: 'daily', phase: 'rth', measured: false, verified: true,
  levels: [],
  drawn: [{ price: 98.5, label: 'PWL', ids: ['week_low_9850'], tone: 'key_broken' }],
  chip: { text: '🔑 broke PWL 98.50 ↓ 10:42', tone: 'warn' },
  fold: '🔑 RTH levels · PWH 103.00 +3.0% · PWL 98.50 −1.5% broke 10:42',
  rule: 'rule', stale_note: null,
  ...over,
});

const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'KEYT', href: '/sepa/KEYT', bars, bands: [], markers: [], stats: [], why: '',
  lines: [KEY, BROKEN, { price: 100.2, label: 'now', tone: 'now' }],
  badges: [{ text: '↓ Came down from 101.00 (-1.0% today)', tone: 'muted' }],
  key_levels: block(),
  ...over,
});

const draw = (t: CmTile, height?: number) =>
  render(<MemoryRouter><PatternChart tile={t} height={height} /></MemoryRouter>);

const lineOf = (c: HTMLElement, tone: string) =>
  Array.from(c.querySelectorAll(`svg.cm-svg line[data-tone="${tone}"]`));
const gutter = (c: HTMLElement) =>
  Array.from(c.querySelectorAll('svg.cm-svg text')).map((t) => t.textContent || '');

describe('PatternChart — 🔑 key-level lines', () => {
  it('a `key` line is solid, width 1.1, fuchsia', () => {
    const { container } = draw(tile());
    const [ln] = lineOf(container, 'key');
    expect(ln).toBeTruthy();
    expect(ln.getAttribute('stroke-width')).toBe('1.1');
    expect(ln.hasAttribute('stroke-dasharray')).toBe(false);
    expect(ln.getAttribute('stroke')).toBe('var(--cm-key, #d946ef)');
  });

  it('a `key_broken` line is the 3,3 dash at width 1.1, same colour', () => {
    const { container } = draw(tile());
    const [ln] = lineOf(container, 'key_broken');
    expect(ln.getAttribute('stroke-width')).toBe('1.1');
    expect(ln.getAttribute('stroke-dasharray')).toBe('3,3');
    expect(ln.getAttribute('stroke')).toBe('var(--cm-key, #d946ef)');
  });

  it('NEGATIVE: the other tones keep their dashes (buy solid, ownstop 2,3, stop 5,4)', () => {
    const { container } = draw(tile({ lines: [
      { price: 100, label: 'BUY', tone: 'buy' }, { price: 99, label: 'STOP', tone: 'stop' },
      { price: 101, label: 'your stop 101', tone: 'ownstop' },
    ] }));
    expect(lineOf(container, 'buy')[0].hasAttribute('stroke-dasharray')).toBe(false);
    expect(lineOf(container, 'stop')[0].getAttribute('stroke-dasharray')).toBe('5,4');
    expect(lineOf(container, 'ownstop')[0].getAttribute('stroke-dasharray')).toBe('2,3');
  });

  it('the 🔑 label renders in the gutter', () => {
    const { container } = draw(tile());
    expect(gutter(container)).toContain('🔑 PWH 103.00');
    expect(gutter(container)).toContain('🔑 PWL 98.50');
  });

  it('NEGATIVE: a key level far outside the price domain is not drawn', () => {
    const far: CmLine = { price: 500, label: '🔑 52wH 500.00', tone: 'key' };
    const { container } = draw(tile({ lines: [KEY, far] }));
    expect(lineOf(container, 'key')).toHaveLength(1);
    expect(gutter(container)).not.toContain('🔑 52wH 500.00');
  });

  it('priority 1: in a crowded gutter the key LABEL yields to BUY / STOP / TARGET, the key LINE still draws', () => {
    const crowd: CmLine[] = [
      { price: 100.0, label: 'BUY', tone: 'buy' }, { price: 99.9, label: 'STOP', tone: 'stop' },
      { price: 100.1, label: 'TARGET', tone: 'target' }, { price: 100.05, label: 'your cost 100.05', tone: 'cost' },
      { price: 100.02, label: '🔑 PDH 100.02', tone: 'key' },
    ];
    const { container } = draw(tile({ lines: crowd, key_levels: null }), 40);
    const txt = gutter(container);
    for (const plan of ['BUY', 'STOP', 'TARGET', 'your cost 100.05']) expect(txt).toContain(plan);
    expect(txt).not.toContain('🔑 PDH 100.02');
    expect(lineOf(container, 'key')).toHaveLength(1);
  });
});

describe('PatternChart — 🔑 PRICE chip and ▸ more line', () => {
  it('the served chip renders ONCE, in PRICE, before the approach line', () => {
    const { container } = draw(tile());
    const pills = container.querySelectorAll('.cm-keylevel');
    expect(pills).toHaveLength(1);
    expect(pills[0].textContent).toBe('🔑 broke PWL 98.50 ↓ 10:42');
    expect(pills[0].classList.contains('cm-badge-warn')).toBe(true);
    const price = container.querySelector('.cm-rung-price')!;
    expect(price.contains(pills[0])).toBe(true);
    const approach = container.querySelector('.cm-approach')!;
    expect(pills[0].compareDocumentPosition(approach) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    for (const rung of ['.cm-rung-entry', '.cm-rung-setup', '.cm-rung-plan', '.cm-rung-timing']) {
      expect(container.querySelector(rung)?.textContent || '').not.toContain('broke PWL');
    }
  });

  it('the chip alone opens the PRICE rung', () => {
    const { container } = draw(tile({ badges: [] }));
    expect(container.querySelector('.cm-rung-price .cm-keylevel')).not.toBeNull();
  });

  it('the fold line sits in ▸ more (hidden until opened) and counts', () => {
    const { container } = draw(tile({ badges: [] }));
    const fold = container.querySelectorAll('.cm-keylevels-fold');
    expect(fold).toHaveLength(1);
    expect(fold[0].textContent).toBe('🔑 RTH levels · PWH 103.00 +3.0% · PWL 98.50 −1.5% broke 10:42');
    expect(container.querySelector('.cm-more')!.contains(fold[0])).toBe(true);
    const btn = container.querySelector('.cm-badge-more')! as HTMLElement;
    expect(btn.textContent).toBe('▸ more · 1');
    expect((container.querySelector('.cm-more') as HTMLElement).hidden).toBe(true);
    fireEvent.click(btn);
    expect((container.querySelector('.cm-more') as HTMLElement).hidden).toBe(false);
  });

  it('NEGATIVE: chip null → no pill; no bare PRICE rung is drawn for it', () => {
    const { container } = draw(tile({ badges: [], key_levels: block({ chip: null }) }));
    expect(container.querySelector('.cm-keylevel')).toBeNull();
    expect(container.querySelector('.cm-rung-price')).toBeNull();
  });

  it('NEGATIVE: malformed blocks never crash and print nothing', () => {
    const junk: unknown[] = [
      null, undefined, 'x', 7, [],
      { ...block(), levels: 'nope' },
      { ...block(), chip: { text: '', tone: 'warn' } },
      { ...block(), chip: { text: 42, tone: 'warn' } },
      { ...block(), chip: 'broke', fold: 17 },
    ];
    for (const kl of junk) {
      const { container, unmount } = draw(tile({ badges: [], key_levels: kl as any }));
      expect(container.querySelector('.cm-keylevel')).toBeNull();
      expect(container.textContent).not.toContain('undefined');
      expect(container.textContent).not.toContain('NaN');
      unmount();
    }
  });

  it('with the 🔑 box unticked: no pill, no key line, no fold item — and the rest stays', () => {
    const { container } = draw(filterTile(tile(), new Set(['key_levels'])));
    expect(container.querySelector('.cm-keylevel')).toBeNull();
    expect(container.querySelector('.cm-keylevels-fold')).toBeNull();
    expect(lineOf(container, 'key')).toHaveLength(0);
    expect(lineOf(container, 'key_broken')).toHaveLength(0);
    expect(lineOf(container, 'now')).toHaveLength(1);
    expect(container.querySelector('.cm-approach')).not.toBeNull();
  });

  it('nothing on the card says "bounce"', () => {
    const { container } = draw(tile());
    expect(container.textContent || '').not.toMatch(/bounce/i);
  });
});
