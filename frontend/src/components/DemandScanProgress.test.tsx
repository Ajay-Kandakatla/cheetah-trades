/* The panel Ajay sees while a Back in Demand scan runs.
 *
 * 2026-08-17: "I am looking at this and its hard to tell if its scanning or now"
 *
 * The arithmetic is pinned in lib/demandScanProgress.test.ts. These tests pin
 * what actually reaches the screen — a number that is computed correctly and
 * then not rendered helps nobody.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DemandScanProgress } from './DemandScanProgress';
import type { DemandScanProgress as Progress } from '../lib/demandScanProgress';

const p = (o: Partial<Progress> = {}): Progress => ({
  universe_key: 'sp1500', universe_label: 'S&P 1500',
  phase: 'scanning', running: true,
  current: 412, total: 1500, hits: 6, symbol: 'NVDA',
  elapsed_sec: 41.2, eta_sec: 108.6, ...o,
});

const bar = (c: HTMLElement) => c.querySelector('.sepa-progress__bar') as HTMLElement;

describe('what a running scan puts on screen', () => {
  it('shows the count, the live hit total and the ticker being analysed', () => {
    render(<DemandScanProgress progress={p()} />);
    expect(screen.getByText('412 / 1,500')).toBeTruthy();
    expect(screen.getByText('6')).toBeTruthy();
    expect(screen.getByText('NVDA')).toBeTruthy();
  });

  it('fills the bar to the measured percentage', () => {
    const { container } = render(<DemandScanProgress progress={p()} />);
    expect(bar(container).style.width).toBe('27.5%');
  });

  it('announces itself to assistive tech — this is a status, not decoration', () => {
    render(<DemandScanProgress progress={p()} />);
    expect(screen.getByRole('status')).toBeTruthy();
  });

  it('shows an ETA while running', () => {
    render(<DemandScanProgress progress={p()} />);
    expect(screen.getByText('~1m 50s left')).toBeTruthy();
  });
});

describe('the honesty cases', () => {
  it('renders an INDETERMINATE bar, not 0%, before the universe resolves', () => {
    // A bar sitting at 0% is exactly the "is it even running?" impression this
    // panel exists to remove.
    const { container } = render(
      <DemandScanProgress progress={p({ phase: 'universe', current: 0, total: 0 })} />);
    const b = bar(container);
    expect(b.style.width).not.toBe('0%');
    expect(Number(b.style.opacity)).toBeLessThan(1);
  });

  it('falls back to elapsed time when there is no ETA yet', () => {
    render(<DemandScanProgress progress={p({ eta_sec: null, elapsed_sec: 41.2 })} />);
    expect(screen.getByText('41s elapsed')).toBeTruthy();
  });

  it('marks a failed scan and says why', () => {
    const { container } = render(
      <DemandScanProgress progress={p({ phase: 'failed', error: 'universe fetch died' })} />);
    expect(container.querySelector('.sepa-progress--error')).toBeTruthy();
    expect(screen.getByText(/universe fetch died/)).toBeTruthy();
  });

  it('marks a finished scan and reports what it found', () => {
    const { container } = render(
      <DemandScanProgress progress={p({ phase: 'done', current: 1500, hits: 9,
                                        took_sec: 141.2 })} />);
    expect(container.querySelector('.sepa-progress--done')).toBeTruthy();
    expect(screen.getByText(/9 in demand/)).toBeTruthy();
  });

  it('names the universe from the caller before the server knows one', () => {
    render(<DemandScanProgress
      progress={p({ phase: 'universe', universe_label: null, total: 0 })}
      universeLabel="S&P 1500 (500 + 400 mid + 600 small)" />);
    expect(screen.getByText(/S&P 1500 \(500 \+ 400 mid \+ 600 small\)/)).toBeTruthy();
  });
});

describe('negatives', () => {
  it('renders NOTHING when idle — an empty panel is worse than no panel', () => {
    const { container } = render(<DemandScanProgress progress={p({ phase: 'idle' })} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing for a missing payload', () => {
    expect(render(<DemandScanProgress progress={null} />).container.firstChild).toBeNull();
    expect(render(<DemandScanProgress progress={undefined} />).container.firstChild).toBeNull();
  });

  it('does not throw on a payload with nothing but a phase', () => {
    expect(() => render(
      <DemandScanProgress progress={{ phase: 'scanning' } as Progress} />)).not.toThrow();
  });

  it('omits the ticker line rather than printing an empty name', () => {
    render(<DemandScanProgress progress={p({ symbol: null })} />);
    expect(screen.queryByText(/^now:/)).toBeNull();
  });
});
