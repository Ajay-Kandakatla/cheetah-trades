/* useGgwFrames — 👀 Gajjala's Watch: the frames choice (board + ⤢), the average-volume opt-in and the dense pick, held
 * as state and remembered in this browser (2026-11-27, spec watch5m rev 2 §3.2, WP lib-frames). Ajay: "Give me a drop down
 * or multi select like button to toggle 1 mins and 15 mins 5 mins by default..".
 *
 * useGgwFrames takes NO argument (spec C2): the dense pick starts at readGgwDense(); the page link is never read or
 * written here. A toggle starts from ggwFramesOn (spec C7) and stores the cleaned list. useGgwGridBox measures what the
 * dense offer needs: the grid width, its two gaps and the free height — the SAME expression useGgwFitRows fits its rows
 * into (GajjalaWatchLayout.tsx), so the offer and the fitted row height never disagree. No timer, no fetch. */
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import {
  ggwToggleFrame, parseGgwDense, readGgwDense, readGgwFrames, readGgwStretchFrames, readGgwVolAvg,
  saveGgwDense, saveGgwFrames, saveGgwStretchFrames, saveGgwVolAvg, type GgwDense,
} from '../lib/ggwFrames';

export type GgwFramesCtl = {
  board: string[]; stretch: string[]; volAvg: boolean; dense: GgwDense;
  /** state + saveGgwFrames(ggwToggleFrame(…)) */
  toggleBoard: (served: ReadonlyArray<string>, tf: string) => void;
  /** state + saveGgwStretchFrames(ggwToggleFrame(…)) */
  toggleStretch: (served: ReadonlyArray<string>, tf: string) => void;
  /** state + saveGgwVolAvg */
  toggleVolAvg: () => void;
  /** state + saveGgwDense */
  setDense: (d: GgwDense) => void;
};

const sameList = (a: ReadonlyArray<string>, b: ReadonlyArray<string>) =>
  a.length === b.length && a.every((x, i) => x === b[i]);

/** No argument [C2]: dense starts at readGgwDense(). */
export function useGgwFrames(): GgwFramesCtl {
  const [board, setBoard] = useState<string[]>(readGgwFrames);
  const [stretch, setStretch] = useState<string[]>(readGgwStretchFrames);
  const [volAvg, setVolAvg] = useState<boolean>(readGgwVolAvg);
  const [dense, setDenseState] = useState<GgwDense>(readGgwDense);

  const toggleBoard = useCallback((served: ReadonlyArray<string>, tf: string) => {
    setBoard((prev) => {
      const next = ggwToggleFrame(served, prev, tf);
      if (!next.length || sameList(next, prev)) return prev;
      saveGgwFrames(next);
      return next;
    });
  }, []);
  const toggleStretch = useCallback((served: ReadonlyArray<string>, tf: string) => {
    setStretch((prev) => {
      const next = ggwToggleFrame(served, prev, tf);
      if (!next.length || sameList(next, prev)) return prev;
      saveGgwStretchFrames(next);
      return next;
    });
  }, []);
  const toggleVolAvg = useCallback(() => {
    setVolAvg((prev) => { saveGgwVolAvg(!prev); return !prev; });
  }, []);
  const setDense = useCallback((d: GgwDense) => {
    const ok = parseGgwDense(d);
    if (ok == null) return;
    saveGgwDense(ok);
    setDenseState(ok);
  }, []);

  return useMemo(() => ({ board, stretch, volAvg, dense, toggleBoard, toggleStretch, toggleVolAvg, setDense }),
    [board, stretch, volAvg, dense, toggleBoard, toggleStretch, toggleVolAvg, setDense]);
}

export type GgwGridBox = { width: number; colGap: number; rowGap: number; free: number };

const sameBox = (a: GgwGridBox | null, b: GgwGridBox | null) =>
  a === b || (!!a && !!b && a.width === b.width && a.colGap === b.colGap && a.rowGap === b.rowGap && a.free === b.free);

/** The grid's width, its two gaps and the free height (window.innerHeight − (grid top − `.ggw-board` top) — the SAME
 *  expression as useGgwFitRows). Re-read on window resize and when the head resizes (ResizeObserver on `head`) or `key`
 *  changes; state is set ONLY when a value changed. null when `on` is false, with no grid, or width 0 (jsdom). */
export function useGgwGridBox(grid: RefObject<HTMLElement>, head: RefObject<HTMLElement>, on: boolean,
                              key: unknown): GgwGridBox | null {
  const [box, setBox] = useState<GgwGridBox | null>(null);
  const last = useRef<GgwGridBox | null>(null);
  useEffect(() => {
    const put = (b: GgwGridBox | null) => {
      if (sameBox(last.current, b)) return;
      last.current = b;
      setBox(b);
    };
    if (!on || typeof window === 'undefined') { put(null); return; }
    const measure = () => {
      const g = grid.current;
      if (!g) { put(null); return; }
      const r = g.getBoundingClientRect();
      if (!(r.width > 0)) { put(null); return; }
      const cs = getComputedStyle(g);
      const colGap = parseFloat(cs.columnGap) || 0;
      const rowGap = parseFloat(cs.rowGap) || 0;
      const b = g.closest('.ggw-board');
      const boardTop = b ? b.getBoundingClientRect().top : r.top;
      /* ggwFitRowHeight clamps the top at 0 the same way — the two readers agree (spec §6.15). */
      put({ width: r.width, colGap, rowGap, free: window.innerHeight - Math.max(0, r.top - boardTop) });
    };
    measure();
    window.addEventListener('resize', measure);
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    if (ro && head.current) ro.observe(head.current);
    return () => { window.removeEventListener('resize', measure); ro?.disconnect(); };
  }, [on, grid, head, key]);
  return box;
}
