import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { BandStructureChip } from './BandStructureChip';
import type { BandStructureRead, BandStructureStudy } from '../lib/bandStructure';

/* 🪜 BandStructureChip — the rules it must never break:
 *   1. no read → NO chip, and an n/a tab → NO chip (coverage is honest; the
 *      board-level note says "this tab has no bands" once, not per row);
 *   2. the pending / no_signal branch is MUTED and never wears the lit tone —
 *      a descriptive ordering dressed as a signal is the Keltner/AMD mistake;
 *   3. it NEVER fetches: the board already put the read on the tile;
 *   4. it prints the SERVED sentence — both halves, his words — and computes
 *      no percentage of its own;
 *   5. a missing SECOND support band says so and never renders as 0.
 */
const STUDY: BandStructureStudy = {
  headline: 'MEASURED: pending — ordered by ceiling thickness, floor layering as the tiebreak, until the study lands',
  fallback_note: 'That is a DESCRIPTIVE ordering of what the bands look like, not a claim that a thin ceiling makes a name go up.',
  status: 'pending',
};

const PENDING_READ: BandStructureRead = {
  symbol: 'CRDO', kind: 'demand', applicable: true, score: null,
  stat: 'ceiling 3.4% wide, 0.5% up · floor 3.5% wide, 2nd band 6.4% under',
  ceiling: { state: 'ROOM', height_pct: 3.4, distance_pct: 0.52, walls_above: 2 },
  floor: { height_pct: 3.5, gap_pct: 6.37, bands_below: 4, in_band: false, distance_pct: 0 },
  measured: { status: 'pending' },
};

const NA_READ: BandStructureRead = {
  symbol: 'ABC', kind: 'n/a', applicable: false, ceiling: null, floor: null, score: null,
  na_text: 'no band read for this tab — its rows are not price-structure bands (pivot / highs / lid / event / options / value)',
  measured: { status: 'pending' },
};

describe('BandStructureChip', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders NOTHING without a read (negative)', () => {
    expect(render(<BandStructureChip read={null} study={STUDY} />).container.innerHTML).toBe('');
    expect(render(<BandStructureChip study={STUDY} />).container.innerHTML).toBe('');
  });

  it('renders NOTHING on a tab with no band read — the n/a note belongs to the board, not to every row (negative)', () => {
    const { container } = render(<BandStructureChip read={NA_READ} study={STUDY} />);
    expect(container.innerHTML).toBe('');
  });

  it('never fetches — the board already holds the read', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    render(<BandStructureChip read={PENDING_READ} study={STUDY} />);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('shows BOTH halves in his words — the ceiling width and distance, the floor width and the gap to the second band', () => {
    const { container } = render(<BandStructureChip read={PENDING_READ} study={STUDY} />);
    const chip = container.querySelector('span')!;
    expect(chip.textContent).toContain('ceiling 3.4% wide, 0.5% up');
    expect(chip.textContent).toContain('floor 3.5% wide, 2nd band 6.4% under');
  });

  it('is MUTED while the study is pending, and says so in the tooltip (negative: never the lit tone)', () => {
    const { container } = render(<BandStructureChip read={PENDING_READ} study={STUDY} />);
    const chip = container.querySelector('span')!;
    expect(chip.className).toContain('cm-badge-band-muted');
    expect(chip.getAttribute('title')).toContain('MEASURED: pending');
    expect(chip.getAttribute('title')).toContain('DESCRIPTIVE');
  });

  it('NEGATIVE: a name with only ONE support band says "no 2nd band" — never a 0% gap', () => {
    const read: BandStructureRead = {
      ...PENDING_READ,
      stat: 'ceiling 3.4% wide, 0.5% up · floor 3.5% wide, no 2nd band',
      floor: { height_pct: 3.5, gap_pct: null, second: null, bands_below: 1 },
    };
    const { container } = render(<BandStructureChip read={read} study={STUDY} />);
    const text = container.querySelector('span')!.textContent || '';
    expect(text).toContain('no 2nd band');
    expect(text).not.toMatch(/2nd band 0(\.\d+)?%/);
  });

  it('wears the lit tone only when the study separates AND the server sent a score', () => {
    const scored: BandStructureRead = { ...PENDING_READ, score: 0.82, measured: { status: 'separates' } };
    const { container } = render(
      <BandStructureChip read={scored} study={{ ...STUDY, status: 'separates' }} />);
    const chip = container.querySelector('span')!;
    expect(chip.className).toContain('cm-badge-band');
    expect(chip.className).not.toContain('cm-badge-band-muted');
    expect(chip.textContent).toContain('0.82');
    expect(chip.textContent).toContain('2nd band 6.4% under');
  });

  it('NEGATIVE: a score with a pending study is still muted and the number is not shown', () => {
    const scored: BandStructureRead = { ...PENDING_READ, score: 0.82 };
    const chip = render(<BandStructureChip read={scored} study={STUDY} />).container.querySelector('span')!;
    expect(chip.className).toContain('cm-badge-band-muted');
    expect(chip.textContent).not.toContain('0.82');
  });

  it('honours the caller class family so it sits beside the other chips on any surface', () => {
    const { container } = render(
      <BandStructureChip read={PENDING_READ} study={STUDY} className="sb-chip" />);
    expect(container.querySelector('span')!.className).toContain('sb-chip-band-muted');
  });
});
