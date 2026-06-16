import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';

vi.mock('../lib/usageTracker', () => ({ trackFeature: vi.fn() }));
import { trackFeature } from '../lib/usageTracker';
import { TrackedSection } from './TrackedSection';

/* TrackedSection — fires `section:<name>` when a section scrolls into view, the
   foundation for a later usage-driven reorg (Ajay 2026-06-16). Locks: fires
   once when genuinely visible; NOT on a tiny/barely-visible box. */

let ioCb: ((entries: unknown[]) => void) | null = null;
class MockIO {
  constructor(cb: (entries: unknown[]) => void) { ioCb = cb; }
  observe() {}
  disconnect() {}
}

beforeEach(() => {
  ioCb = null;
  (trackFeature as ReturnType<typeof vi.fn>).mockClear();
  vi.stubGlobal('IntersectionObserver', MockIO as unknown as typeof IntersectionObserver);
});
afterEach(() => { vi.unstubAllGlobals(); });

const visible = [{ isIntersecting: true, intersectionRatio: 0.6, boundingClientRect: { height: 120 } }];

describe('TrackedSection', () => {
  it('fires the section event when scrolled into view', () => {
    render(<TrackedSection name="test:foo"><div>hi</div></TrackedSection>);
    ioCb!(visible);
    expect(trackFeature).toHaveBeenCalledWith('section:test:foo');
  });

  it('does NOT fire below the 40% threshold or for a tiny box (negative)', () => {
    render(<TrackedSection name="test:bar"><div>hi</div></TrackedSection>);
    ioCb!([{ isIntersecting: true, intersectionRatio: 0.1, boundingClientRect: { height: 120 } }]); // too little visible
    ioCb!([{ isIntersecting: true, intersectionRatio: 0.9, boundingClientRect: { height: 4 } }]);   // empty board
    expect(trackFeature).not.toHaveBeenCalled();
  });

  it('fires at most once per mount', () => {
    render(<TrackedSection name="test:baz"><div>hi</div></TrackedSection>);
    ioCb!(visible);
    ioCb!(visible);
    expect(trackFeature).toHaveBeenCalledTimes(1);
  });
});
