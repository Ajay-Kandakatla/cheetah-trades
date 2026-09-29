/* The "more columns →" cue for a sideways-scrolling table (🔥 Hottest,
 * 2026-09-28).
 *
 * Ajay 2026-09-28: "Can you fix the horizontal columns hiding". The table now
 * scrolls sideways inside its own box instead of being cut by the page; this
 * hook says WHICH columns sit off to the right, so a column out of view is
 * announced rather than silently missing.
 *
 * It re-measures when the box scrolls, when the box resizes, when the TABLE
 * resizes (opening a group widens the table without resizing the box), and
 * whenever `deps` change (the jsdom path, and a belt for engines that batch
 * ResizeObserver). It also writes `--hs-box-w` on the box — the visible width
 * the full-width rows pin their text to. That custom property is set HERE
 * only, never typed in the board's TSX. */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';

export type HsColBox = { label: string; left: number; width: number };
export type HScrollCue = { left: boolean; right: boolean; offRight: string[] };

/** PURE. 1px tolerance: a column is off to the right when its right edge is
 *  past the visible right edge by more than a pixel. `left` = the box is
 *  scrolled, so content sits under the sticky first column. */
export function hScrollCue(m: { scrollLeft: number; clientWidth: number; scrollWidth: number;
                                cols: HsColBox[] }): HScrollCue {
  const edge = m.scrollLeft + m.clientWidth + 1;
  const offRight = m.scrollWidth > m.clientWidth + 1
    ? m.cols.filter((c) => c.left + c.width > edge).map((c) => c.label)
    : [];
  return { left: m.scrollLeft > 1, right: offRight.length > 0, offRight };
}

const sameCue = (a: HScrollCue, b: HScrollCue) =>
  a.left === b.left && a.right === b.right
  && a.offRight.length === b.offRight.length && a.offRight.every((x, i) => x === b.offRight[i]);

/** `labels` = the printed column labels in print order, EXCLUDING the sticky
 *  first column — paired with `thead th` 2..n by index. Never read from the
 *  header's textContent, which carries "ⓘ" and priority marks. */
export function useHScrollCue(ref: RefObject<HTMLElement>, labels: string[], deps: unknown[]):
  HScrollCue & { onScroll: () => void } {
  const [cue, setCue] = useState<HScrollCue>({ left: false, right: false, offRight: [] });
  const labelsRef = useRef(labels);
  labelsRef.current = labels;
  const raf = useRef<number | null>(null);

  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.setProperty('--hs-box-w', `${el.clientWidth}px`);
    const ths = Array.from(el.querySelectorAll('thead th')).slice(1) as HTMLElement[];
    const cols = ths.map((th, i) => ({
      label: labelsRef.current[i] ?? '', left: th.offsetLeft, width: th.offsetWidth,
    }));
    const next = hScrollCue({ scrollLeft: el.scrollLeft, clientWidth: el.clientWidth,
                              scrollWidth: el.scrollWidth, cols });
    setCue((prev) => (sameCue(prev, next) ? prev : next));
  }, [ref]);

  useEffect(() => {
    measure();
    const el = ref.current;
    if (!el) return undefined;
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => measure());
      ro.observe(el);
      const table = el.querySelector('table');
      if (table) ro.observe(table);
      return () => ro.disconnect();
    }
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [measure, ...deps]);

  useEffect(() => () => {
    if (raf.current != null && typeof cancelAnimationFrame === 'function') {
      cancelAnimationFrame(raf.current);
    }
  }, []);

  const onScroll = useCallback(() => {
    if (raf.current != null) return;
    if (typeof requestAnimationFrame !== 'function') { measure(); return; }
    raf.current = requestAnimationFrame(() => { raf.current = null; measure(); });
  }, [measure]);

  return { ...cue, onScroll };
}
