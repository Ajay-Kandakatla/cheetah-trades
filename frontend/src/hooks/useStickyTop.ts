/* useStickyTop — publishes the height of a sticky top bar as the CSS variable
 * `--sticky-top` on <html>, so anything else that sticks to the top of the
 * page (the promo board's column headers, 2026-09-02) can sit just under it
 * instead of sliding behind it. The phone nav is `position: sticky; top: 0;
 * z-index: 100` and its height depends on what it shows (gauge badge, tab
 * name), so it is measured, not hard-coded. Unmount → the variable is
 * removed and consumers fall back to 0. */
import { useLayoutEffect, type RefObject } from 'react';

export const STICKY_TOP_VAR = '--sticky-top';

export function setStickyTop(px: number | null, root: HTMLElement = document.documentElement,
                             name: string = STICKY_TOP_VAR): void {
  if (px == null || !(px > 0)) root.style.removeProperty(name);
  else root.style.setProperty(name, `${Math.round(px)}px`);
}

/* `opts` (2026-09-28, the pinned Chart Maps tab strip): publish under another
 * variable name (`--cm-tabs-h`) on another host element (the page root), so a
 * second sticky bar reuses this one engine. Defaults are the NavBar's call,
 * unchanged: `--sticky-top` on <html>. */
export function useStickyTop(ref: RefObject<HTMLElement | null>, active = true,
                             opts?: { varName?: string; host?: RefObject<HTMLElement | null> }): void {
  const name = opts?.varName ?? STICKY_TOP_VAR;
  const hostRef = opts?.host;
  useLayoutEffect(() => {
    const host = hostRef?.current ?? document.documentElement;
    const el = ref.current;
    if (!active || !el) { setStickyTop(null, host, name); return; }
    const measure = () => setStickyTop(el.getBoundingClientRect().height, host, name);
    measure();
    const RO = typeof ResizeObserver === 'undefined' ? null : ResizeObserver;
    const ro = RO ? new RO(() => measure()) : null;
    ro?.observe(el);
    return () => { ro?.disconnect(); setStickyTop(null, host, name); };
  }, [ref, active, name, hostRef]);
}
