/* 👀 Gajjala's Watch — the scrolling grid's two hooks (2026-11-25, spec ggwcols §3.2, WP scroll-lib).
 * Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll."
 * useGgwNear — the live RENDER gate: which tiles are in or near the window (ONE IntersectionObserver per board,
 *   fail-open: no observer → null → every tile counts as near). The data path (bus, live POST) is not touched here.
 * useGgwHold — keeps the tile he is looking at where it is across a commit that changes `deps` (the 11-19 anchor
 *   rule, by scroll): snapshot the first in-view tile in render, `window.scrollBy` by its shift after layout.
 * No timer, no fetch, no scroll listener, no storage, no link write. */
import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react';
import { GGW_NEAR_MARGIN, GGW_SCROLL_EPS, GGW_TILE_ID, ggwAnchorNow, ggwGridTiles, ggwTileSym } from '../lib/ggwScroll';

function sameMembers(a: ReadonlySet<string>, b: ReadonlySet<string>): boolean {
  if (a.size !== b.size) return false;
  for (const s of a) if (!b.has(s)) return false;
  return true;
}

/** The names whose board tiles are in or near the window. null = NO gate (every tile counts as near). */
export function useGgwNear(grid: RefObject<HTMLElement>, key: string, on: boolean): ReadonlySet<string> | null {
  const [near, setNear] = useState<ReadonlySet<string> | null>(null);
  const gated = on && GGW_NEAR_MARGIN != null && typeof IntersectionObserver === 'function';
  useEffect(() => {
    if (!gated || GGW_NEAR_MARGIN == null) return;
    const el = grid.current;
    if (!el) return;
    const cur = new Set<string>();                          // this observer's own view; the old Set holds until cb
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        const sym = ggwTileSym((e.target as HTMLElement).id);
        if (!sym) continue;
        if (e.isIntersecting) cur.add(sym); else cur.delete(sym);
      }
      setNear((prev) => (prev && sameMembers(prev, cur) ? prev : new Set(cur)));
    }, { root: null, rootMargin: GGW_NEAR_MARGIN, threshold: 0 });
    for (const t of ggwGridTiles(el)) io.observe(t);
    return () => io.disconnect();
  }, [grid, key, gated]);
  if (!gated || !grid.current) return null;
  return near;
}

/** Keeps the tile he is looking at where it is across a commit that changes `deps` (the 11-19 anchor rule, by scroll). */
export function useGgwHold(grid: RefObject<HTMLElement>, on: boolean, deps: ReadonlyArray<unknown>,
                           skip: () => boolean): void {
  const last = useRef(deps);
  const snap = useRef<{ sym: string; top: number } | null>(null);
  const changed = deps.length !== last.current.length || deps.some((d, i) => !Object.is(d, last.current[i]));
  snap.current = on && changed ? ggwAnchorNow(grid.current) : null;   // a READ of the DOM of the previous commit
  useLayoutEffect(() => {                                              // no deps array: every commit
    const s = snap.current; snap.current = null; last.current = deps;
    if (!on || !s || skip() || typeof window === 'undefined') return;
    const el = ggwGridTiles(grid.current).find((t) => t.id === GGW_TILE_ID + s.sym);
    if (!el || el.hidden) return;                                      // it left the list / a filter hides it
    const d = el.getBoundingClientRect().top - s.top;                  // measured AFTER layout
    if (Number.isFinite(d) && Math.abs(d) >= GGW_SCROLL_EPS) window.scrollBy(0, d);
  });
}
