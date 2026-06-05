/* Heatmap — a native squarified treemap (Finviz-style market map).

   Ajay 2026-06-05: "can we get the Finviz map view into a small panel on the
   portfolio + leaderboard pages?" Finviz blocks embedding, so this renders our
   own: tiles sized by `value` (position $ / score), colored by `pct` (day %
   change, green↑ / red↓), grouped visually by size. No dependencies — the
   squarify layout (Bruls/Huizing/van Wijk) is ~40 lines.

   Reused on both pages; the caller supplies the tiles + a click handler. */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';

export type HeatTile = {
  symbol: string;
  value: number;            // tile AREA weight (position $, score, …) — must be > 0
  pct: number | null;       // day % change → colour
  label?: string;           // optional second line (e.g. "+1.2%")
};

type Rect = { x: number; y: number; w: number; h: number; tile: HeatTile };

// ── squarified treemap layout ────────────────────────────────────────────────
function worstRatio(areas: number[], side: number): number {
  const sum = areas.reduce((a, b) => a + b, 0);
  if (sum <= 0) return Infinity;
  const max = Math.max(...areas), min = Math.min(...areas);
  return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
}

function squarify(tiles: HeatTile[], width: number, height: number): Rect[] {
  const out: Rect[] = [];
  const items = tiles.filter((t) => t.value > 0).sort((a, b) => b.value - a.value);
  const total = items.reduce((s, t) => s + t.value, 0);
  if (total <= 0 || width <= 0 || height <= 0) return out;
  const scale = (width * height) / total;
  const work = items.map((t) => ({ tile: t, area: t.value * scale }));

  let rect = { x: 0, y: 0, w: width, h: height };
  let idx = 0;
  while (idx < work.length) {
    const side = Math.min(rect.w, rect.h);
    let count = 1;
    let best = worstRatio([work[idx].area], side);
    while (idx + count < work.length) {
      const next = worstRatio(work.slice(idx, idx + count + 1).map((w) => w.area), side);
      if (next > best) break;
      best = next;
      count++;
    }
    const row = work.slice(idx, idx + count);
    const rowArea = row.reduce((s, w) => s + w.area, 0);
    if (rect.w >= rect.h) {
      const stripW = rowArea / rect.h;
      let yy = rect.y;
      for (const w of row) {
        const hh = w.area / stripW;
        out.push({ x: rect.x, y: yy, w: stripW, h: hh, tile: w.tile });
        yy += hh;
      }
      rect = { x: rect.x + stripW, y: rect.y, w: rect.w - stripW, h: rect.h };
    } else {
      const stripH = rowArea / rect.w;
      let xx = rect.x;
      for (const w of row) {
        const ww = w.area / stripH;
        out.push({ x: xx, y: rect.y, w: ww, h: stripH, tile: w.tile });
        xx += ww;
      }
      rect = { x: rect.x, y: rect.y + stripH, w: rect.w, h: rect.h - stripH };
    }
    idx += count;
  }
  return out;
}

// ── colour: red (−3%) → neutral (0) → green (+3%), Finviz-style ──────────────
function lerp(a: number, b: number, t: number): number { return Math.round(a + (b - a) * t); }
function hex(r: number, g: number, b: number): string { return `rgb(${r},${g},${b})`; }
const RED = [246, 53, 56], NEUTRAL = [61, 67, 80], GREEN = [48, 204, 90];
function heatColor(pct: number | null): string {
  if (pct == null || Number.isNaN(pct)) return hex(NEUTRAL[0], NEUTRAL[1], NEUTRAL[2]);
  const t = Math.max(-1, Math.min(1, pct / 3));
  const [from, to] = t >= 0 ? [NEUTRAL, GREEN] : [NEUTRAL, RED];
  const k = Math.abs(t);
  return hex(lerp(from[0], to[0], k), lerp(from[1], to[1], k), lerp(from[2], to[2], k));
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const measure = () => setW(el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function Heatmap({
  tiles,
  height = 200,
  onTileClick,
}: {
  tiles: HeatTile[];
  height?: number;
  onTileClick?: (symbol: string) => void;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [rects, setRects] = useState<Rect[]>([]);

  useEffect(() => {
    if (width > 0 && tiles.length) setRects(squarify(tiles, width, height));
    else setRects([]);
  }, [width, height, tiles]);

  return (
    <div ref={ref} className="heatmap" style={{ position: 'relative', width: '100%', height }}>
      {rects.map((r) => {
        const pct = r.tile.pct;
        const showPct = r.w > 38 && r.h > 26;
        const showSym = r.w > 24 && r.h > 14;
        return (
          <button
            key={r.tile.symbol}
            type="button"
            className="heatmap__tile"
            onClick={() => onTileClick?.(r.tile.symbol)}
            title={`${r.tile.symbol}${pct != null ? `  ${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : ''}`}
            style={{
              position: 'absolute',
              left: r.x, top: r.y, width: Math.max(0, r.w - 1), height: Math.max(0, r.h - 1),
              background: heatColor(pct),
            }}
          >
            {showSym && (
              <span className="heatmap__sym" style={{ fontSize: Math.min(16, Math.max(9, r.w / 5)) }}>
                {r.tile.symbol}
              </span>
            )}
            {showPct && pct != null && (
              <span className="heatmap__pct">{pct >= 0 ? '+' : ''}{pct.toFixed(1)}%</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
