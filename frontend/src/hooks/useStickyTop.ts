/* useStickyTop — publishes the height of a sticky top bar as the CSS variable
 * `--sticky-top` on <html>, so anything else that sticks to the top of the
 * page (the promo board's column headers, 2026-09-02) can sit just under it
 * instead of sliding behind it. The phone nav is `position: sticky; top: 0;
 * z-index: 100` and its height depends on what it shows (gauge badge, tab
 * name), so it is measured, not hard-coded. Unmount → the variable is
 * removed and consumers fall back to 0. */
import { useLayoutEffect, type RefObject } from 'react';

export const STICKY_TOP_VAR = '--sticky-top';

export function setStickyTop(px: number | null, root: HTMLElement = document.documentElement): void {
  if (px == null || !(px > 0)) root.style.removeProperty(STICKY_TOP_VAR);
  else root.style.setProperty(STICKY_TOP_VAR, `${Math.round(px)}px`);
}

export function useStickyTop(ref: RefObject<HTMLElement | null>, active = true): void {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!active || !el) { setStickyTop(null); return; }
    const measure = () => setStickyTop(el.getBoundingClientRect().height);
    measure();
    const RO = typeof ResizeObserver === 'undefined' ? null : ResizeObserver;
    const ro = RO ? new RO(() => measure()) : null;
    ro?.observe(el);
    return () => { ro?.disconnect(); setStickyTop(null); };
  }, [ref, active]);
}
