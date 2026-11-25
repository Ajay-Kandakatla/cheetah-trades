/* useGgwScroll — 👀 Gajjala's Watch: the near gate + the scroll hold (2026-11-25, spec ggwcols §3.2, WP scroll-lib).
 * Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll."
 * jsdom has no layout and no IntersectionObserver: a fake observer class is driven by hand and tile rects come from
 * `data-top` (what the DOM of a commit says). Pixel numbers are stand-ins. NEGATIVES (near): `on` false → null, no
 * observer; no IntersectionObserver → null; same membership → the same Set object. NEGATIVES (hold): no dep changed → no
 * rect read, no scroll; the anchor left / hidden → none; skip() → none; a move under GGW_SCROLL_EPS → none; `on` false
 * → no read; head in view → none; a snapshot never applies on a later commit whose deps did not change. */
import { act, render } from '@testing-library/react';
import { useRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GGW_NEAR_MARGIN, GGW_SCROLL_EPS } from '../lib/ggwScroll';
import { useGgwHold, useGgwNear } from './useGgwScroll';

/* ---- a hand-driven IntersectionObserver ------------------------------------------------------------------------ */
class FakeIO {
  static all: FakeIO[] = [];
  cb: IntersectionObserverCallback;
  opts: IntersectionObserverInit | undefined;
  targets: Element[] = [];
  disconnected = false;
  constructor(cb: IntersectionObserverCallback, opts?: IntersectionObserverInit) {
    this.cb = cb; this.opts = opts; FakeIO.all.push(this);
  }
  observe(el: Element) { this.targets.push(el); }
  unobserve(el: Element) { this.targets = this.targets.filter((t) => t !== el); }
  disconnect() { this.disconnected = true; this.targets = []; }
  takeRecords() { return []; }
  fire(list: Array<[string, boolean]>) {
    const entries = list.map(([sym, on]) => ({ target: document.getElementById(`ggw-${sym}`)!, isIntersecting: on }));
    act(() => { this.cb(entries as unknown as IntersectionObserverEntry[], this as unknown as IntersectionObserver); });
  }
}

let seen: Array<ReadonlySet<string> | null> = [];
const lastSeen = () => seen[seen.length - 1];
function NearBoard({ syms, on = true }: { syms: string[]; on?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const near = useGgwNear(ref, syms.join(','), on);
  seen.push(near);
  return (
    <div ref={ref}>
      <h3 className="ggw-section" id="ggw-HEAD">head</h3>
      {syms.map((s) => <section key={s} className="ggw-tile" id={`ggw-${s}`} />)}
    </div>
  );
}

describe('useGgwNear', () => {
  beforeEach(() => { FakeIO.all = []; seen = []; vi.stubGlobal('IntersectionObserver', FakeIO); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('ONE observer, every tile observed (never the section header), rootMargin = GGW_NEAR_MARGIN', () => {
    render(<NearBoard syms={['A', 'B', 'C']} />);
    expect(FakeIO.all).toHaveLength(1);
    const io = FakeIO.all[0];
    expect(io.targets.map((t) => t.id)).toEqual(['ggw-A', 'ggw-B', 'ggw-C']);
    expect(io.opts).toEqual({ root: null, rootMargin: GGW_NEAR_MARGIN, threshold: 0 });
  });

  it('a callback sets the names; a later one removes one', () => {
    render(<NearBoard syms={['A', 'B', 'C']} />);
    const io = FakeIO.all[0];
    io.fire([['A', true], ['B', true], ['C', false]]);
    expect([...(lastSeen() ?? [])].sort()).toEqual(['A', 'B']);
    io.fire([['A', false]]);
    expect([...(lastSeen() ?? [])]).toEqual(['B']);
    expect(lastSeen()!.has('A')).toBe(false);
  });

  it('a re-key re-observes and HOLDS the old Set until the new observer\'s first callback', () => {
    const { rerender } = render(<NearBoard syms={['A', 'B']} />);
    FakeIO.all[0].fire([['A', true], ['B', false]]);
    const before = lastSeen();
    rerender(<NearBoard syms={['A', 'B', 'D']} />);
    expect(FakeIO.all).toHaveLength(2);
    expect(FakeIO.all[0].disconnected).toBe(true);
    expect(FakeIO.all[1].targets.map((t) => t.id)).toEqual(['ggw-A', 'ggw-B', 'ggw-D']);
    expect(lastSeen()).toBe(before);                  // never a one-frame "everything near" (null) burst
    expect(lastSeen()).not.toBeNull();
    FakeIO.all[1].fire([['A', false], ['B', false], ['D', true]]);
    expect([...(lastSeen() ?? [])]).toEqual(['D']);
  });

  it('unmount disconnects', () => {
    const { unmount } = render(<NearBoard syms={['A']} />);
    const io = FakeIO.all[0];
    unmount();
    expect(io.disconnected).toBe(true);
  });

  it('NEGATIVE: on false → null and no observer built', () => {
    render(<NearBoard syms={['A', 'B']} on={false} />);
    expect(FakeIO.all).toHaveLength(0);
    expect(seen.every((s) => s === null)).toBe(true);
  });

  it('NEGATIVE: no IntersectionObserver global → null (fail-open: every tile counts as near)', () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    render(<NearBoard syms={['A', 'B']} />);
    expect(FakeIO.all).toHaveLength(0);
    expect(seen.every((s) => s === null)).toBe(true);
  });

  it('NEGATIVE: same membership → the same Set object (no new state)', () => {
    render(<NearBoard syms={['A', 'B']} />);
    const io = FakeIO.all[0];
    io.fire([['A', true]]);
    const first = lastSeen();
    io.fire([['A', true], ['B', false]]);
    expect(lastSeen()).toBe(first);
    io.fire([['B', false]]);
    expect(lastSeen()).toBe(first);
  });

  it('NEGATIVE: before any callback the hook returns null (fail-open), never an empty Set', () => {
    render(<NearBoard syms={['A']} />);
    expect(lastSeen()).toBeNull();
  });
});

/* ---- the hold ------------------------------------------------------------------------------------------------ */
type T = { sym: string; top: number; h?: number; hidden?: boolean };
const col = (syms: string[], top: number, h = 200, gap = 13): T[] =>
  syms.map((sym, i) => ({ sym, top: top + i * (h + gap), h }));
function HoldBoard({ tiles, dep, on = true, skip = () => false }:
                   { tiles: T[]; dep: unknown; on?: boolean; skip?: () => boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useGgwHold(ref, on, [dep], skip);
  return (
    <div ref={ref}>
      {tiles.map((t) => (
        <section key={t.sym} className="ggw-tile" id={`ggw-${t.sym}`} data-top={t.top} data-h={t.h ?? 200}
                 hidden={t.hidden || undefined} />
      ))}
    </div>
  );
}

describe('useGgwHold', () => {
  let rect: ReturnType<typeof vi.spyOn>;
  let scroll: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    rect = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      const el = this as HTMLElement;
      const t = el.getAttribute('data-top');
      if (t == null || el.hidden) return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
      const top = Number(t); const h = Number(el.getAttribute('data-h'));
      return { top, bottom: top + h, left: 0, right: 400, width: 400, height: h, x: 0, y: top, toJSON: () => ({}) } as DOMRect;
    });
    vi.spyOn(window, 'getComputedStyle').mockImplementation(() => ({ scrollMarginTop: '55px' }) as CSSStyleDeclaration);
    scroll = vi.spyOn(window, 'scrollBy').mockImplementation(() => {});
  });
  afterEach(() => { vi.restoreAllMocks(); });

  const SYMS = ['A', 'B', 'C', 'D'];

  it('a row lands above the tile in view → scrollBy(0, that tile\'s shift) once', () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} />);   // B (-87..113) is the anchor
    expect(scroll).not.toHaveBeenCalled();
    rerender(<HoldBoard tiles={col(['Z', ...SYMS], -300)} dep={2} />);            // B → 126
    expect(scroll).toHaveBeenCalledTimes(1);
    expect(scroll).toHaveBeenCalledWith(0, 213);
  });

  it('a dep changes and the anchor moved +120 → scrollBy(0, 120) once; −120 → scrollBy(0, −120)', () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} />);
    rerender(<HoldBoard tiles={col(SYMS, -180)} dep={2} />);
    expect(scroll).toHaveBeenCalledTimes(1);
    expect(scroll).toHaveBeenLastCalledWith(0, 120);
    rerender(<HoldBoard tiles={col(SYMS, -300)} dep={3} />);
    expect(scroll).toHaveBeenCalledTimes(2);
    expect(scroll).toHaveBeenLastCalledWith(0, -120);
  });

  it('NEGATIVE: no dep changed → no rect read, no scroll', () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} />);
    rect.mockClear();
    rerender(<HoldBoard tiles={col(SYMS, -180)} dep={1} />);
    expect(rect).not.toHaveBeenCalled();
    expect(scroll).not.toHaveBeenCalled();
  });

  it("NEGATIVE: the anchor's symbol left the grid → no scroll", () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} />);
    rerender(<HoldBoard tiles={col(['A', 'C', 'D'], -180)} dep={2} />);
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: the anchor is hidden after the commit (a chip filter) → no scroll', () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} />);
    const after = col(SYMS, -180).map((t) => (t.sym === 'B' ? { ...t, hidden: true } : t));
    rerender(<HoldBoard tiles={after} dep={2} />);
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: skip() true (a pending focus) → no scroll', () => {
    const skip = vi.fn(() => true);
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} skip={skip} />);
    rerender(<HoldBoard tiles={col(SYMS, -180)} dep={2} skip={skip} />);
    expect(skip).toHaveBeenCalled();
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: a move under GGW_SCROLL_EPS → no scroll', () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} />);
    rerender(<HoldBoard tiles={col(SYMS, -300 + GGW_SCROLL_EPS / 2)} dep={2} />);
    expect(scroll).not.toHaveBeenCalled();
    rerender(<HoldBoard tiles={col(SYMS, -300)} dep={3} />);
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: on false → no rect read, no scroll', () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} on={false} />);
    rect.mockClear();
    rerender(<HoldBoard tiles={col(SYMS, -180)} dep={2} on={false} />);
    expect(rect).not.toHaveBeenCalled();
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: the grid start at / below the inset (head in view) → no scroll', () => {
    const { rerender } = render(<HoldBoard tiles={col(SYMS, 55)} dep={1} />);
    rerender(<HoldBoard tiles={col(SYMS, 175)} dep={2} />);
    rerender(<HoldBoard tiles={col(SYMS, 330)} dep={3} />);
    rerender(<HoldBoard tiles={col(SYMS, 450)} dep={4} />);
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: a snapshot from one render never applies on a later commit whose deps did not change', () => {
    let skipNow = true;
    const skip = () => skipNow;
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} skip={skip} />);
    rerender(<HoldBoard tiles={col(SYMS, -300)} dep={2} skip={skip} />);         // snapshot taken, skipped
    expect(scroll).not.toHaveBeenCalled();
    skipNow = false;
    rerender(<HoldBoard tiles={col(SYMS, -180)} dep={2} skip={skip} />);         // moved, but no dep changed
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: plain jsdom (every rect 0 × 0) → no scroll', () => {
    rect.mockImplementation(() => ({ top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect);
    const { rerender } = render(<HoldBoard tiles={col(SYMS, -300)} dep={1} />);
    rerender(<HoldBoard tiles={col(SYMS, -180)} dep={2} />);
    expect(scroll).not.toHaveBeenCalled();
  });
});
