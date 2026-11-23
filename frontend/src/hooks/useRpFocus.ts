/* useRpFocus — scroll ONE element into view once per jump (2026-11-22, pwjump spec §3.4).
 *
 * Ajay 2026-11-22: "New feature when I click on this past winner tag take me to that video so change the date and focus
 * me on that video at that. time". Used by 🎬 Replays: the 🏆 reel row a chip jumps to, the "no longer listed" line, and
 * the day card Back returns to. The house precedent is 👀 Watch `?focus=SYM` (scroll once the tile is shown). */
import { useEffect, useRef, type RefObject } from 'react';

/** Scroll the element into view ONCE per non-empty `key`, as soon as `ready` is true AND the element is mounted; a new
 *  key fires again; '' resets (the same key can focus again later). `el.scrollIntoView?.({ block: 'start' })` then
 *  `el.focus?.({ preventScroll: true })`. A null element or `ready === false` never marks the key done. */
export function useRpFocus<T extends HTMLElement>(key: string, ready: boolean): RefObject<T> {
  const ref = useRef<T>(null);
  const done = useRef('');
  /* NO dependency array on purpose: three comparisons per render, so an element that mounts a render after its key
   * (or a `ready` that turns true later) is still caught. */
  useEffect(() => {
    if (!key) { done.current = ''; return; }
    if (!ready || done.current === key) return;
    const el = ref.current;
    if (!el) return;
    done.current = key;
    el.scrollIntoView?.({ block: 'start' });
    el.focus?.({ preventScroll: true });
  });
  return ref;
}
