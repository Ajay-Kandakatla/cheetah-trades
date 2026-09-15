import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EnterableChip } from './EnterableChip';
import type { EnterableRead } from '../lib/enterable';

/* 🎯 EnterableChip — it renders a SERVED verdict or nothing at all.
 *
 * The locks: the class family per surface (a chip with no rule ships
 * unstyled — 2026-09-10), the served reason word printed verbatim, and the
 * negatives: no read and a null verdict must render NOTHING rather than a chip
 * that implies a measurement nobody made.
 */

const mk = (over: Partial<EnterableRead> = {}): EnterableRead => ({
  kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [],
  print: { px: 100, source: 'live' }, measured: { status: 'pending' }, ...over,
});

describe('EnterableChip', () => {
  it('renders READY with the cm-badge family', () => {
    const { container } = render(<EnterableChip read={mk()} />);
    expect(screen.getByText('🎯 READY')).toBeInTheDocument();
    expect(container.querySelector('.cm-badge.cm-badge-enterable-ready')).not.toBeNull();
  });

  it('renders the served WATCH reason and the watch class', () => {
    const { container } = render(<EnterableChip read={mk({
      verdict: 'WATCH', reasons: ['weak_day'], reason_short: ['weak day'],
      reason_text: ['down 4.2% today — that bucket closed up only 22% of the time'],
    })} />);
    expect(screen.getByText('🎯 WATCH · weak day')).toBeInTheDocument();
    expect(container.querySelector('.cm-badge-enterable-watch')).not.toBeNull();
    expect(screen.getByTitle(/down 4.2% today/)).toBeInTheDocument();
  });

  it('renders the served BLOCKED reason and the blocked class', () => {
    const { container } = render(<EnterableChip read={mk({
      verdict: 'BLOCKED', reasons: ['proximity'], reason_short: ['not at band'],
    })} />);
    expect(screen.getByText('⛔ not at band')).toBeInTheDocument();
    expect(container.querySelector('.cm-badge-enterable-blocked')).not.toBeNull();
  });

  it('takes the surface class family it is given', () => {
    const { container } = render(<EnterableChip read={mk()} className="sb-chip" />);
    expect(container.querySelector('.sb-chip.sb-chip-enterable-ready')).not.toBeNull();
  });

  it('NEGATIVE: renders nothing for a missing read', () => {
    const { container } = render(<EnterableChip read={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('NEGATIVE: renders nothing for a read the server did not grade', () => {
    const { container } = render(<EnterableChip read={mk({ verdict: null })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('NEGATIVE: an n/a tab wears a muted n/a chip, never a verdict', () => {
    const { container } = render(<EnterableChip read={mk({
      kind: 'n/a', verdict: null, reasons: ['na'],
      reason_text: ['no demand read for this tab — its rows are not demand reversals'],
    })} />);
    expect(screen.getByText('n/a')).toBeInTheDocument();
    expect(container.querySelector('.cm-badge-enterable-na')).not.toBeNull();
    expect(container.textContent).not.toContain('READY');
  });
});
