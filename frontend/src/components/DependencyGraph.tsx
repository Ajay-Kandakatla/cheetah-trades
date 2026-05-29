import { useEffect, useMemo, useRef, useState } from 'react';
import type { GraphNode, GraphEdge, FlowTicker } from '../hooks/useSupplyDemand';

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  height?: number;
  centerTicker?: string;
  /** Callback when a node is clicked. If provided, replaces the default
   *  navigation behaviour (used to open the NodeThesisPanel). */
  onNodeClick?: (ticker: string) => void;
  /** Highlight a specific ticker (e.g. the one whose panel is open). */
  selectedTicker?: string | null;
  /** Real-time flow data keyed by ticker. When provided, nodes get tinted
   *  by today's change %, and animated particles travel along edges. */
  flowMap?: Record<string, FlowTicker>;
  /** Whether to animate flow particles. Set to false outside market hours. */
  flowLive?: boolean;
  /** Tickers currently on the SEPA candidate list (any positive tier).
   *  These nodes render larger with a gold ring for visual emphasis —
   *  the dependency graph stays whole, but SEPA names jump out. */
  sepaTickers?: Set<string>;
  /** Per-ticker SEPA tier (STRONG_BUY/BUY/WATCH). Higher tier = bigger bump. */
  sepaTiers?: Record<string, 'STRONG_BUY' | 'BUY' | 'WATCH'>;
};

type LaidOutNode = GraphNode & { x: number; y: number; vx: number; vy: number; pinned?: boolean };

const RELATION_COLORS: Record<string, string> = {
  foundry_for:      '#a855f7',  // purple
  supplier_of:      '#10b981',  // green
  customer_of:      '#3b82f6',  // blue
  competitor_of:    '#ef4444',  // red
  partner_with:     '#f59e0b',  // amber
  depends_on_chip:  '#06b6d4',  // cyan
};

/** Render a relation as a directional sentence using the actual ticker
 *  pair. Solves the "depends on chip" ambiguity from 2026-05-28: with
 *  three "depends on chip" edges fanning out from ARM, the user couldn't
 *  tell which direction each one went. Now: `QCOM depends on ARM's chip`.
 *
 *  The convention in this codebase is: edge.source is the actor / the
 *  one performing the relation; edge.target is the receiver. So
 *  `{source: 'QCOM', target: 'ARM', relation: 'depends_on_chip'}`
 *  reads "QCOM depends on ARM's chip". */
function humanizeRelation(relation: string, source: string, target: string): string {
  switch (relation) {
    case 'depends_on_chip':  return `${source} depends on ${target}'s chip`;
    case 'foundry_for':      return `${source} is a foundry for ${target}`;
    case 'supplier_of':      return `${source} is a supplier of ${target}`;
    case 'customer_of':      return `${source} is a customer of ${target}`;
    case 'competitor_of':    return `${source} ⇄ ${target} (competitors)`;
    case 'partner_with':     return `${source} partners with ${target}`;
    default:                 return `${source} → ${target} (${relation.replace(/_/g, ' ')})`;
  }
}

const SECTOR_COLORS: Record<string, string> = {
  Semiconductors: '#a855f7',
  Tech:           '#3b82f6',
  Auto:           '#10b981',
  Materials:      '#f59e0b',
  Energy:         '#ef4444',
  Utilities:      '#ec4899',
  Healthcare:     '#06b6d4',
  Defense:        '#84cc16',
  Aerospace:      '#fb923c',
  Financial:      '#fbbf24',
};

/**
 * DependencyGraph — SVG force-directed network of S&P companies.
 *
 * Phase 2 polish:
 *  - Sector-based clustering: same-sector nodes share a centroid and pull
 *    toward it, forming visible cluster regions.
 *  - Drag-to-reposition: grab any node and move it; physics relaxes
 *    around your placement (pinned position).
 *  - Glow halo on hover; gradient node fills via radialGradient.
 *  - Edge relation labels on hover.
 *  - onNodeClick callback: lets parent pop a thesis drawer instead of
 *    navigating directly.
 */
export function DependencyGraph({ nodes, edges, height: heightProp = 600, centerTicker, onNodeClick, selectedTicker, flowMap, flowLive = true, sepaTickers, sepaTiers }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(900);
  // Effective height: in fullscreen we override with measured container
  // height; otherwise use the prop.
  const [measuredHeight, setMeasuredHeight] = useState<number | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<{ edge: GraphEdge; x: number; y: number } | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Pinned (user-dragged) positions persist across re-layouts
  const [pinned, setPinned] = useState<Record<string, { x: number; y: number }>>({});
  const [drag, setDrag] = useState<{ ticker: string; x: number; y: number } | null>(null);

  // --- Fullscreen ---
  // Uses the standard Fullscreen API where available. iOS Safari doesn't
  // support it on non-video elements, so we fall back to a CSS class
  // that fixes the container to viewport edges (visually identical to
  // fullscreen for our purposes).
  const [isFullscreen, setIsFullscreen] = useState(false);
  // Track real fullscreen state so we sync with browser-controlled exits
  // (Esc, swipe-down on iOS, etc.)
  useEffect(() => {
    const sync = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', sync);
    return () => document.removeEventListener('fullscreenchange', sync);
  }, []);
  const toggleFullscreen = async () => {
    const el = containerRef.current;
    if (!el) return;
    const docEl = document as any;

    if (isFullscreen || docEl.fullscreenElement) {
      // Exit fullscreen
      try {
        if (document.exitFullscreen) await document.exitFullscreen();
        else if ((docEl as any).webkitExitFullscreen) (docEl as any).webkitExitFullscreen();
      } catch { /* ignore */ }
      setIsFullscreen(false);
      return;
    }

    // Enter fullscreen — try real API first, fall back to CSS-only
    try {
      if (el.requestFullscreen) {
        await el.requestFullscreen();
        setIsFullscreen(true);
        return;
      }
      if ((el as any).webkitRequestFullscreen) {
        (el as any).webkitRequestFullscreen();
        setIsFullscreen(true);
        return;
      }
    } catch { /* fall through to CSS fallback */ }

    // CSS fallback — used on iOS Safari (no element-level fullscreen API)
    setIsFullscreen(true);
  };

  // --- Zoom + pan ---
  // `zoom` is a multiplier (1 = native), `pan` is screen-space offset
  // applied AFTER scaling. World→screen: screen = world*zoom + pan.
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [panDrag, setPanDrag] = useState<{ startScreen: { x: number; y: number }; startPan: { x: number; y: number } } | null>(null);
  // Refs for the wheel handler (which is attached non-passive via addEventListener)
  const zoomRef = useRef(zoom);
  const panRef = useRef(pan);
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);
  useEffect(() => { panRef.current = pan; }, [pan]);

  const ZOOM_MIN = 0.4;
  const ZOOM_MAX = 3.5;

  const screenToWorld = (sx: number, sy: number) => ({
    x: (sx - panRef.current.x) / zoomRef.current,
    y: (sy - panRef.current.y) / zoomRef.current,
  });

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const zoomBy = (factor: number, anchor?: { x: number; y: number }) => {
    const z = zoomRef.current;
    const p = panRef.current;
    const newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z * factor));
    if (newZoom === z) return;
    // Anchor zoom to graph center if not provided
    const ax = anchor?.x ?? width / 2;
    const ay = anchor?.y ?? height / 2;
    const wx = (ax - p.x) / z;
    const wy = (ay - p.y) / z;
    setZoom(newZoom);
    setPan({ x: ax - wx * newZoom, y: ay - wy * newZoom });
  };

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      const w = cr?.width ?? 900;
      const h = cr?.height ?? null;
      setWidth(Math.max(500, Math.floor(w)));
      if (h && h > 100) setMeasuredHeight(Math.floor(h));
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // ADA / WCAG SC 2.3.3: respect the OS-level "reduce motion" preference.
  // When set, the radiating ripples + animated flow particles + node pulse
  // are suppressed (steady ring still shown so flow info isn't lost).
  const [reduceMotion, setReduceMotion] = useState<boolean>(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduceMotion(e.matches);
    mql.addEventListener?.('change', handler);
    return () => mql.removeEventListener?.('change', handler);
  }, []);

  // Use measured height when fullscreen (container fills viewport), prop otherwise
  const height = isFullscreen && measuredHeight ? measuredHeight : heightProp;

  // Wheel handler for zoom. Important UX rule:
  //   - Trackpad PINCH gesture (or Ctrl/Cmd+scroll) → zoom the graph
  //   - Plain two-finger scroll → bubble up so the PAGE scrolls (don't trap the user inside the graph)
  //
  // Browsers signal pinch by setting `ctrlKey: true` on the synthetic
  // wheel event even though no key was actually pressed — this is the
  // standard cross-browser convention (Chrome/Safari/Firefox).
  // So pinch and Cmd/Ctrl-scroll both look identical to us, which is exactly
  // what we want: both trigger zoom.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      // If neither ctrlKey nor metaKey is set, this is a plain scroll —
      // let it bubble up so the page scrolls normally.
      if (!e.ctrlKey && !e.metaKey) return;

      e.preventDefault();  // we ARE going to zoom — don't let page scroll too
      const rect = svg.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const z = zoomRef.current;
      const p = panRef.current;
      const wx = (cx - p.x) / z;
      const wy = (cy - p.y) / z;
      // exp() gives smooth multiplicative zoom; deltaY is positive when "scrolling down"
      // (which on a pinch = pinching together = zoom out, matching native intuition)
      const newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z * Math.exp(-e.deltaY * 0.0015)));
      setZoom(newZoom);
      setPan({ x: cx - wx * newZoom, y: cy - wy * newZoom });
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, []);

  // --- Layout
  const layout = useMemo(
    () => computeLayout(nodes, edges, width, height, centerTicker, pinned),
    [nodes, edges, width, height, centerTicker, pinned],
  );

  // While dragging, override that node's position with the live cursor
  const positions = drag
    ? { ...layout.byId, [drag.ticker]: { ...layout.byId[drag.ticker], x: drag.x, y: drag.y } }
    : layout.byId;

  // --- Drag/pan handlers -------------------------------------------------
  // Mousedown on the SVG (background) starts a pan; node-mousedown calls
  // stopPropagation so this never fires for nodes.
  const onSvgMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    setPanDrag({
      startScreen: { x: e.clientX - rect.left, y: e.clientY - rect.top },
      startPan: { ...panRef.current },
    });
  };

  const onSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    if (panDrag) {
      setPan({
        x: panDrag.startPan.x + (sx - panDrag.startScreen.x),
        y: panDrag.startPan.y + (sy - panDrag.startScreen.y),
      });
      return;
    }
    if (drag) {
      const w = screenToWorld(sx, sy);
      setDrag({ ticker: drag.ticker, x: w.x, y: w.y });
    }
  };

  const onSvgMouseUp = () => {
    if (drag) {
      setPinned((prev) => ({ ...prev, [drag.ticker]: { x: drag.x, y: drag.y } }));
      setDrag(null);
    }
    if (panDrag) setPanDrag(null);
  };

  // --- Touch handlers (mobile pinch + pan + node drag) -------------------
  // We use refs (not state) for transient pinch info so changes don't
  // trigger re-renders during the gesture (60fps would render-thrash).
  const touchPinchRef = useRef<{
    startDist: number;
    startZoom: number;
    startPanX: number;
    startPanY: number;
    midX: number;
    midY: number;
  } | null>(null);

  const onSvgTouchStart = (e: React.TouchEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();

    if (e.touches.length === 2) {
      // Two-finger pinch starts — capture initial finger spread
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const x1 = t1.clientX - rect.left;
      const y1 = t1.clientY - rect.top;
      const x2 = t2.clientX - rect.left;
      const y2 = t2.clientY - rect.top;
      const dist = Math.hypot(x2 - x1, y2 - y1);
      touchPinchRef.current = {
        startDist: dist,
        startZoom: zoomRef.current,
        startPanX: panRef.current.x,
        startPanY: panRef.current.y,
        midX: (x1 + x2) / 2,
        midY: (y1 + y2) / 2,
      };
      // If a single-finger pan was in progress, cancel it cleanly
      if (panDrag) setPanDrag(null);
      e.preventDefault();
      return;
    }

    if (e.touches.length === 1 && !touchPinchRef.current) {
      // One finger on background → start panning
      const t = e.touches[0];
      setPanDrag({
        startScreen: { x: t.clientX - rect.left, y: t.clientY - rect.top },
        startPan: { ...panRef.current },
      });
    }
  };

  const onSvgTouchMove = (e: React.TouchEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();

    // Two-finger pinch: scale anchored at the midpoint between fingers
    if (e.touches.length === 2 && touchPinchRef.current) {
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const x1 = t1.clientX - rect.left;
      const y1 = t1.clientY - rect.top;
      const x2 = t2.clientX - rect.left;
      const y2 = t2.clientY - rect.top;
      const dist = Math.hypot(x2 - x1, y2 - y1);
      const p = touchPinchRef.current;
      const ratio = dist / Math.max(1, p.startDist);
      const newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, p.startZoom * ratio));
      // World coord under the midpoint at gesture start
      const wx = (p.midX - p.startPanX) / p.startZoom;
      const wy = (p.midY - p.startPanY) / p.startZoom;
      // After zoom, pan so that midpoint stays fixed over the same world coord
      const newMidX = (x1 + x2) / 2;
      const newMidY = (y1 + y2) / 2;
      setZoom(newZoom);
      setPan({ x: newMidX - wx * newZoom, y: newMidY - wy * newZoom });
      e.preventDefault();
      return;
    }

    // One finger: panning, OR dragging a node (drag state set on node touchstart)
    if (e.touches.length === 1) {
      const t = e.touches[0];
      const sx = t.clientX - rect.left;
      const sy = t.clientY - rect.top;

      if (drag) {
        const w = screenToWorld(sx, sy);
        setDrag({ ticker: drag.ticker, x: w.x, y: w.y });
        e.preventDefault();
        return;
      }
      if (panDrag) {
        setPan({
          x: panDrag.startPan.x + (sx - panDrag.startScreen.x),
          y: panDrag.startPan.y + (sy - panDrag.startScreen.y),
        });
        e.preventDefault();
      }
    }
  };

  const onSvgTouchEnd = (e: React.TouchEvent<SVGSVGElement>) => {
    if (e.touches.length === 0) {
      // All fingers up — commit any in-progress drag
      if (drag) {
        setPinned((prev) => ({ ...prev, [drag.ticker]: { x: drag.x, y: drag.y } }));
        setDrag(null);
      }
      if (panDrag) setPanDrag(null);
      touchPinchRef.current = null;
    } else if (e.touches.length === 1 && touchPinchRef.current) {
      // Released ONE finger of a pinch — switch to single-finger pan
      touchPinchRef.current = null;
      if (svgRef.current) {
        const rect = svgRef.current.getBoundingClientRect();
        const t = e.touches[0];
        setPanDrag({
          startScreen: { x: t.clientX - rect.left, y: t.clientY - rect.top },
          startPan: { ...panRef.current },
        });
      }
    }
  };

  if (!nodes.length) {
    return <div className="dep-graph dep-graph--empty" ref={containerRef}>No graph data.</div>;
  }

  // Compute sector cluster hulls (background tint regions)
  const sectorClusters = computeSectorHulls(nodes, positions);

  // Flow stats — used to scale particle speed against the busiest tickers
  const flowStats = useMemo(() => {
    if (!flowMap) return { medianDV: 0, maxAbsChange: 0 };
    const dvs = Object.values(flowMap).map((f) => f.dollar_volume).filter((v) => v > 0).sort((a, b) => a - b);
    const medianDV = dvs.length ? dvs[Math.floor(dvs.length / 2)] : 0;
    const maxAbsChange = Object.values(flowMap).reduce(
      (m, f) => Math.max(m, Math.abs(f.change_pct ?? 0)),
      0,
    );
    return { medianDV, maxAbsChange };
  }, [flowMap]);

  return (
    <div className={`dep-graph${isFullscreen ? ' dep-graph--fullscreen' : ''}`} ref={containerRef}>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="dep-graph__svg"
        role="img"
        aria-label="Company dependency graph"
        onMouseDown={onSvgMouseDown}
        onMouseMove={onSvgMouseMove}
        onMouseUp={onSvgMouseUp}
        onMouseLeave={onSvgMouseUp}
        onTouchStart={onSvgTouchStart}
        onTouchMove={onSvgTouchMove}
        onTouchEnd={onSvgTouchEnd}
        onTouchCancel={onSvgTouchEnd}
        style={{
          cursor: panDrag ? 'grabbing' : 'default',
          touchAction: 'none',          // disable browser pan/zoom — we handle it
          userSelect: 'none',           // no selection-highlight on long-press
          WebkitUserSelect: 'none',
          WebkitTouchCallout: 'none',   // no iOS callout menu on long-press
        }}
      >
        {/* ---- Defs: gradients + arrowheads + glow ---- */}
        <defs>
          {/* Per-sector radial gradient for nodes.
              ADA: edge stop was darkenColor(..., 30) which dropped contrast
              against the black ticker text below 4.5:1 on purple/blue/pink
              sectors. Eased to 12% so the 3D bubble look survives but the
              edge band stays readable. */}
          {Object.entries(SECTOR_COLORS).map(([sector, color]) => (
            <radialGradient key={`grad-${sector}`} id={`node-grad-${sector.replace(/\s+/g, '-')}`} cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor={lightenColor(color, 50)} />
              <stop offset="55%" stopColor={color} />
              <stop offset="100%" stopColor={darkenColor(color, 12)} />
            </radialGradient>
          ))}
          <radialGradient id="node-grad-default" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stopColor="#cbd5e1" />
            <stop offset="55%" stopColor="#94a3b8" />
            <stop offset="100%" stopColor="#475569" />
          </radialGradient>

          {/* Arrowhead defs — one per relation color.
              Bumped from 6×6 to 14×14 with markerUnits="userSpaceOnUse"
              so size stays absolute regardless of stroke width. The old
              size was barely visible against the node halos — user
              feedback 2026-05-28: "Don't know who is dependent on who".
              We also pull the marker BACK from the path end (refX=2)
              and let the edge path itself stop short of the target node
              (see endpoint trimming below) so the arrow sits cleanly in
              the gap, not hidden behind the node circle. */}
          {Object.entries(RELATION_COLORS).map(([rel, color]) => (
            <marker
              key={rel}
              id={`arrow-${rel}`}
              viewBox="0 0 10 10"
              refX={2}
              refY={5}
              markerWidth={14}
              markerHeight={14}
              markerUnits="userSpaceOnUse"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill={color} />
            </marker>
          ))}

          {/* Glow filter for hovered/selected nodes */}
          <filter id="node-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* ---- Zoom/pan transform group: wraps all interactive content ---- */}
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>

        {/* ---- Sector cluster hulls (background) ---- */}
        {sectorClusters.map((c) => (
          <g key={`hull-${c.sector}`} className="dep-graph__hull">
            <path
              d={c.path}
              fill={c.color}
              fillOpacity={0.06}
              stroke={c.color}
              strokeOpacity={0.25}
              strokeWidth={1}
              strokeDasharray="4 4"
            />
            {/* ADA: 11px @ opacity 0.7 + colored hue on dark bg fell short
                of AA on the borderline sector colors (purple/blue). Bumped
                to 13px and full opacity. */}
            <text
              x={c.centroid.x}
              y={c.centroid.y - c.radius - 8}
              textAnchor="middle"
              fontSize={13}
              fontWeight={800}
              fill={c.color}
              opacity={0.9}
              letterSpacing={1}
              style={{ pointerEvents: 'none' }}
            >
              {c.sector.toUpperCase()}
            </text>
          </g>
        ))}

        {/* ---- Edges ---- */}
        {edges.map((e, i) => {
          const a = positions[e.source];
          const b = positions[e.target];
          if (!a || !b) return null;
          const color = RELATION_COLORS[e.relation] ?? '#94a3b8';
          const strokeW = 1 + (e.strength ?? 0.3) * 2.5;
          const isHovered = hoveredEdge?.edge === e;
          const isAdjacent = hoveredNode === e.source || hoveredNode === e.target;
          const isSelectedAdj = selectedTicker === e.source || selectedTicker === e.target;
          const opacity = hoveredNode
            ? (isAdjacent ? 0.95 : 0.1)
            : (isSelectedAdj ? 0.95 : (isHovered ? 1 : 0.6));
          const dx = b.x - a.x, dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const dr = dist * 1.6;
          // Trim both endpoints so the path starts just outside the
          // source node and ends just outside the target node. Otherwise
          // the arrowhead sits at the path end which is the center of
          // the target node — hidden by the node circle.
          //   sourceTrim = node radius + small gap
          //   targetTrim = node radius + arrow length (so arrow tip
          //                kisses the node edge instead of overlapping)
          // Node radii (see node render): 14 base / 18 hover / 24 center.
          // Use 22 for source trim and 28 for target trim so the arrow
          // is always visible regardless of which node is the bigger
          // centered one.
          const ux = dist > 0 ? dx / dist : 0;
          const uy = dist > 0 ? dy / dist : 0;
          const sourceTrim = 22;
          const targetTrim = 28;
          const ax = a.x + ux * sourceTrim;
          const ay = a.y + uy * sourceTrim;
          const bx = b.x - ux * targetTrim;
          const by = b.y - uy * targetTrim;
          const path = `M${ax.toFixed(1)},${ay.toFixed(1)}A${dr.toFixed(1)},${dr.toFixed(1)} 0 0,1 ${bx.toFixed(1)},${by.toFixed(1)}`;
          const midX = (a.x + b.x) / 2;
          const midY = (a.y + b.y) / 2;
          const pathId = `edge-path-${i}`;

          // --- Flow particle config (only when flowMap is provided) ----
          const sourceFlow = flowMap?.[e.source];
          const targetFlow = flowMap?.[e.target];
          const showFlow = flowLive && flowMap && sourceFlow && targetFlow;
          // Speed: faster for higher dollar volume on the source name (proxy
          // for "real money moving"). Range ~2s (busy) – 10s (quiet).
          let particleDur = 5;
          let particleColor = '#94a3b8';
          let nParticles = 0;
          if (showFlow) {
            const dv = sourceFlow!.dollar_volume || 0;
            const median = flowStats.medianDV || 1;
            const intensity = Math.min(2.5, dv / median);  // 1.0 = median, 2.5 = top
            particleDur = Math.max(1.8, 9 - intensity * 3);
            // Particles per edge — 1 always, +1 if both endpoints up, +1 if very busy
            nParticles = 1
              + (sourceFlow!.change_pct > 0 && targetFlow!.change_pct > 0 ? 1 : 0)
              + (intensity > 1.5 ? 1 : 0);
            // Color: green if both up, red if both down, amber if divergent
            const sUp = (sourceFlow!.change_pct ?? 0) > 0.1;
            const tUp = (targetFlow!.change_pct ?? 0) > 0.1;
            const sDn = (sourceFlow!.change_pct ?? 0) < -0.1;
            const tDn = (targetFlow!.change_pct ?? 0) < -0.1;
            if (sUp && tUp) particleColor = '#10b981';        // both up — healthy
            else if (sDn && tDn) particleColor = '#ef4444';   // both down — chain weak
            else if (sUp && tDn || sDn && tUp) particleColor = '#f59e0b';  // divergent
            else particleColor = '#cbd5e1';                   // flat
          }

          return (
            <g key={i}>
              <path
                id={pathId}
                d={path}
                stroke={color}
                strokeWidth={strokeW}
                fill="none"
                opacity={opacity}
                markerEnd={`url(#arrow-${e.relation})`}
                style={{ transition: 'opacity 100ms', cursor: 'pointer' }}
                onMouseEnter={() => setHoveredEdge({ edge: e, x: midX, y: midY })}
                onMouseLeave={() => setHoveredEdge(null)}
              >
                {/* Native SVG <title> renders as a system tooltip on any
                    OS, including mobile long-press. Belt and braces with
                    the rendered label — if the user just rests on an
                    edge without hovering an adjacent node, they still
                    get the plain-English direction. */}
                <title>{humanizeRelation(e.relation, e.source, e.target)}</title>
              </path>
              {/* Money flow particles (animated along the edge path).
                  ADA: skipped entirely when prefers-reduced-motion is set —
                  edge color/strength already encodes flow direction. */}
              {showFlow && nParticles > 0 && !reduceMotion && Array.from({ length: nParticles }).map((_, pi) => (
                <circle
                  key={`p-${pi}`}
                  r={2.5}
                  fill={particleColor}
                  opacity={opacity > 0.3 ? 0.95 : 0.2}
                  style={{ pointerEvents: 'none', filter: 'drop-shadow(0 0 3px currentColor)' }}
                >
                  <animateMotion
                    dur={`${particleDur}s`}
                    repeatCount="indefinite"
                    begin={`${(pi * particleDur) / nParticles}s`}
                  >
                    <mpath href={`#${pathId}`} />
                  </animateMotion>
                </circle>
              ))}
              {/* Edge label appears only when adjacent node is hovered.
                  Format: SRC → TGT · relation. This was previously just
                  the relation alone ("depends on chip") which left users
                  asking who depends on whom (user feedback 2026-05-28).
                  Showing the ticker pair with an explicit arrow direction
                  removes the ambiguity even before they read the relation
                  phrase. Width scales with text content. */}
              {isAdjacent && (() => {
                const relText = humanizeRelation(e.relation, e.source, e.target);
                const arrowText = `${e.source} → ${e.target}`;
                // Cheap text-width estimate (~6.5 px per char at 11px font).
                const w = Math.max(arrowText.length, relText.length) * 6.8 + 16;
                return (
                  <g style={{ pointerEvents: 'none' }}>
                    <rect
                      x={midX - w / 2}
                      y={midY - 22}
                      width={w}
                      height={36}
                      rx={5}
                      fill="rgba(10,10,10,0.95)"
                      stroke={color}
                      strokeWidth={0.8}
                    />
                    {/* Line 1: ticker pair with arrow, slightly bolder */}
                    <text
                      x={midX}
                      y={midY - 8}
                      textAnchor="middle"
                      fontSize={12}
                      fontWeight={800}
                      fill="#f3f4f6"
                      style={{ fontFamily: '"SF Mono", Menlo, monospace' }}
                    >
                      {arrowText}
                    </text>
                    {/* Line 2: human-readable relation in the edge color */}
                    <text
                      x={midX}
                      y={midY + 8}
                      textAnchor="middle"
                      fontSize={10}
                      fontWeight={600}
                      fill={color}
                    >
                      {relText}
                    </text>
                  </g>
                );
              })()}
            </g>
          );
        })}

        {/* ---- Nodes ---- */}
        {nodes.map((n) => {
          const p = positions[n.ticker];
          if (!p) return null;
          const isCentered = n.ticker === centerTicker;
          const isSelected = n.ticker === selectedTicker;
          const isHover = n.ticker === hoveredNode;
          const isAdj = hoveredEdge && (hoveredEdge.edge.source === n.ticker || hoveredEdge.edge.target === n.ticker);
          const isDimmed = hoveredNode && !isHover && !layout.adjacency[hoveredNode]?.has(n.ticker);
          // Pulse for high-volume names — bigger pulse = more $ flowing
          const nodeFlow = flowMap?.[n.ticker];
          const flowDV = nodeFlow?.dollar_volume ?? 0;
          const flowIntensity = flowStats.medianDV ? Math.min(2.5, flowDV / flowStats.medianDV) : 0;
          const nodeChangePct = nodeFlow?.change_pct ?? 0;

          // SEPA-list emphasis: bump radius based on tier so positive
          // SEPA candidates visually jump out without losing the graph.
          //   STRONG_BUY → +12, BUY → +8, WATCH → +5, plain on-list → +5
          const sepaTier = sepaTiers?.[n.ticker];
          const onSepaList = sepaTier !== undefined || sepaTickers?.has(n.ticker);
          const sepaBump =
            sepaTier === 'STRONG_BUY' ? 12 :
            sepaTier === 'BUY'        ? 8  :
            sepaTier === 'WATCH'      ? 5  :
            onSepaList                ? 5  : 0;

          // Base radius bumped slightly for big-flow names + SEPA emphasis
          const baseR = isCentered ? 24 : (isSelected || isHover ? 18 : 14);
          const r = baseR
            + (flowLive && flowIntensity > 1 ? Math.min(4, flowIntensity * 1.5) : 0)
            + sepaBump;
          const sectorKey = (n.sector ?? '').replace(/\s+/g, '-');
          const fillId = SECTOR_COLORS[n.sector ?? ''] ? `node-grad-${sectorKey}` : 'node-grad-default';
          const sectorColor = SECTOR_COLORS[n.sector ?? ''] ?? '#94a3b8';

          // Flow visualisation: TWO independent signals layered together.
          //
          //   1. Multi-day accumulation/distribution score (Chaikin Money
          //      Flow over 10 sessions). Drives the COLOR of the ring +
          //      whether ripples emit at all.
          //
          //   2. Today's intraday change_pct. Used as fallback when accum
          //      score is null/neutral, so a fresh mover still shows up
          //      even before we have multi-day history.
          //
          // The ring "radiates" — outward expanding ripples for any name
          // with strong accumulation or distribution, looping forever.
          const accumScore = nodeFlow?.accumulation_score ?? null;
          const hasAccum = accumScore !== null && accumScore !== undefined;
          // Primary signal: accumulation if available, else today's % move
          const primarySignal = hasAccum ? accumScore! : nodeChangePct * 12;  // scale change% to similar range

          const isBuying = primarySignal > 5;
          const isSelling = primarySignal < -5;
          const flowTintColor = isBuying ? '#22c55e' : isSelling ? '#ef4444' : '#94a3b8';

          // Show ring if we have ANY signal worth showing
          const showFlowRing = !!flowMap && !!nodeFlow && (
            (hasAccum && Math.abs(accumScore!) >= 10) ||
            Math.abs(nodeChangePct) > 0.1
          );

          // Magnitude → opacity (high floor so it's always visible)
          const magnitudeNorm = Math.min(1, Math.abs(primarySignal) / 60);
          const flowRingOpacity = showFlowRing ? 0.6 + magnitudeNorm * 0.4 : 0;

          // RADIATING RIPPLES: stronger signal = faster ripples
          // |score| ≥ 60 (strong) → 1.6s/ripple, 2 ripples staggered
          // |score| 30-60       → 2.2s/ripple, 2 ripples
          // |score| 10-30       → 2.8s/ripple, 1 ripple
          // weaker             → no ripples (just steady ring)
          // ADA: when reduceMotion is set, suppress all ripples — the
          // steady glow ring still encodes the same info via color/opacity.
          const absSignal = Math.abs(primarySignal);
          let nRipples = 0;
          let rippleDur = 2.5;
          if (showFlowRing && !reduceMotion) {
            if (absSignal >= 60)      { nRipples = 2; rippleDur = 1.6; }
            else if (absSignal >= 30) { nRipples = 2; rippleDur = 2.2; }
            else if (absSignal >= 15) { nRipples = 1; rippleDur = 2.8; }
          }
          // Pulse the inner ring on live high-volume names (live-market only)
          // ADA: respect reduce-motion — drop the pulse animation; the
          // node still gets the size bump from flowIntensity for the same info.
          const pulseDur = flowLive && flowIntensity > 1.2 && !reduceMotion ? Math.max(1.2, 3.5 - flowIntensity) : 0;

          const onMouseDown = (e: React.MouseEvent<SVGGElement>) => {
            // Start drag — tracked at SVG level so we keep getting events
            // even if the cursor leaves the small node circle. Convert
            // screen coords to world (untransformed) since the layout +
            // pinned positions live in world space.
            if (!svgRef.current) return;
            const rect = svgRef.current.getBoundingClientRect();
            const w = screenToWorld(e.clientX - rect.left, e.clientY - rect.top);
            setDrag({ ticker: n.ticker, x: w.x, y: w.y });
            e.stopPropagation();
          };

          // Touch handler for nodes. Differs from mouse: we DON'T immediately
          // commit to drag mode — we record the start position and let
          // SVG-level touchmove decide. If the finger barely moves before
          // touchend, it's a tap (open panel). If it moves past threshold,
          // it becomes a drag.
          const onTouchStart = (e: React.TouchEvent<SVGGElement>) => {
            if (!svgRef.current) return;
            // Only handle single-finger touches on a node (two-finger
            // pinch is an SVG-level gesture and we let it bubble up).
            if (e.touches.length !== 1) return;
            const t = e.touches[0];
            const rect = svgRef.current.getBoundingClientRect();
            const w = screenToWorld(t.clientX - rect.left, t.clientY - rect.top);
            setDrag({ ticker: n.ticker, x: w.x, y: w.y });
            e.stopPropagation();
          };

          // On touchend, if the node never moved measurably, treat as tap.
          // (We can't easily check movement here so we let onClick fire
          // naturally — iOS dispatches a synthetic click after touchend
          // when finger barely moved.)

          return (
            <g
              key={n.ticker}
              transform={`translate(${p.x}, ${p.y})`}
              opacity={isDimmed ? 0.22 : 1}
              onMouseEnter={() => setHoveredNode(n.ticker)}
              onMouseLeave={() => setHoveredNode(null)}
              onMouseDown={onMouseDown}
              onTouchStart={onTouchStart}
              onClick={(e) => {
                // Only trigger click if not dragging
                if (drag) return;
                if (onNodeClick) onNodeClick(n.ticker);
                e.stopPropagation();
              }}
              style={{ cursor: drag?.ticker === n.ticker ? 'grabbing' : 'grab', transition: 'opacity 120ms' }}
            >
              {/* Money-flow ring + RADIATING RIPPLES — bright glowing GREEN
                  for accumulation, RED for distribution.
                  Layers, painted in this order:
                    1. Outermost soft halo (no animation, sets the ambient glow)
                    2. Radiating ripples — concentric rings expanding outward
                       and fading to 0 (the "radiating" effect)
                    3. Mid blurred ring (steady, gives body to the glow)
                    4. Inner sharp ring (the crisp "stroke" edge)  */}
              {showFlowRing && (
                <>
                  {/* Outer halo — ambient glow */}
                  <circle
                    r={r + 14}
                    fill="none"
                    stroke={flowTintColor}
                    strokeWidth={2}
                    opacity={flowRingOpacity * 0.32}
                    style={{ filter: `blur(7px)` }}
                  />

                  {/* RADIATING RIPPLES — animated outward, fading to nothing.
                      This is the part that makes it feel like the bubble is
                      actively emitting energy. Multiple ripples staggered in
                      phase so it's a continuous wave, not a single ping. */}
                  {Array.from({ length: nRipples }).map((_, i) => (
                    <circle
                      key={`ripple-${i}`}
                      r={r + 4}
                      cx={0}
                      cy={0}
                      fill="none"
                      stroke={flowTintColor}
                      strokeWidth={2.2}
                      opacity={0}
                      style={{ filter: `blur(0.5px)` }}
                    >
                      <animate
                        attributeName="r"
                        values={`${r + 4};${r + 28}`}
                        dur={`${rippleDur}s`}
                        begin={`${(i * rippleDur) / nRipples}s`}
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="opacity"
                        values={`${flowRingOpacity * 0.85};0`}
                        dur={`${rippleDur}s`}
                        begin={`${(i * rippleDur) / nRipples}s`}
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="stroke-width"
                        values="2.5;0.5"
                        dur={`${rippleDur}s`}
                        begin={`${(i * rippleDur) / nRipples}s`}
                        repeatCount="indefinite"
                      />
                    </circle>
                  ))}

                  {/* Mid blurred glow — steady body */}
                  <circle
                    r={r + 9}
                    fill="none"
                    stroke={flowTintColor}
                    strokeWidth={3}
                    opacity={flowRingOpacity * 0.55}
                    style={{ filter: `blur(2.5px)` }}
                  />

                  {/* Sharp inner ring — the visible stroke + drop shadow */}
                  <circle
                    r={r + 5}
                    fill="none"
                    stroke={flowTintColor}
                    strokeWidth={3}
                    opacity={flowRingOpacity}
                    style={{ filter: `drop-shadow(0 0 6px ${flowTintColor})` }}
                  >
                    {pulseDur > 0 && (
                      <animate
                        attributeName="r"
                        values={`${r + 3};${r + 8};${r + 3}`}
                        dur={`${pulseDur}s`}
                        repeatCount="indefinite"
                      />
                    )}
                    {pulseDur > 0 && (
                      <animate
                        attributeName="opacity"
                        values={`${flowRingOpacity};${flowRingOpacity * 0.5};${flowRingOpacity}`}
                        dur={`${pulseDur}s`}
                        repeatCount="indefinite"
                      />
                    )}
                  </circle>
                </>
              )}
              {/* SEPA emphasis ring — gold halo around any ticker on the
                  current SEPA candidate list. Sized by tier so STRONG_BUY
                  pops more than WATCH. Pulses subtly to signal "fresh signal". */}
              {onSepaList && (
                <>
                  <circle
                    r={r + 6}
                    fill="none"
                    stroke="var(--gold)"
                    strokeWidth={sepaTier === 'STRONG_BUY' ? 3 : 2}
                    opacity={sepaTier === 'STRONG_BUY' ? 0.85 : 0.6}
                    style={{ filter: `drop-shadow(0 0 5px var(--gold))` }}
                  >
                    <animate attributeName="opacity"
                              values="0.4;0.9;0.4"
                              dur="3s" repeatCount="indefinite" />
                  </circle>
                  {/* Wide soft glow for the highest-tier names only */}
                  {sepaTier === 'STRONG_BUY' && (
                    <circle
                      r={r + 14}
                      fill="var(--gold)"
                      opacity={0.18}
                      style={{ filter: `blur(8px)` }}
                    />
                  )}
                </>
              )}
              {/* Halo (visible when hovered/selected) */}
              {(isHover || isSelected || isCentered) && (
                <circle
                  r={r + 8}
                  fill={sectorColor}
                  opacity={0.18}
                  filter="url(#node-glow)"
                />
              )}
              <circle
                r={r}
                fill={`url(#${fillId})`}
                stroke={
                  isSelected ? 'var(--gold)' :
                  isCentered ? 'var(--gold)' :
                  showFlowRing && Math.abs(nodeChangePct) > 1 ? flowTintColor :
                  (isHover || isAdj) ? '#fff' : 'rgba(255,255,255,0.5)'
                }
                strokeWidth={isSelected || isCentered ? 3 : 1.5}
                style={{ transition: 'r 120ms' }}
              />
              {/* Tiny change-% pill below the ticker. Shows whenever flow
                  data is available (regardless of live/cached). */}
              {!!flowMap && nodeFlow && Math.abs(nodeChangePct) > 0.1 && (
                <g style={{ pointerEvents: 'none', userSelect: 'none' }}>
                  <rect
                    x={-26} y={r + 3}
                    width={52} height={16}
                    rx={7}
                    fill="rgba(10,10,10,0.88)"
                    stroke={flowTintColor}
                    strokeWidth={0.6}
                    opacity={0.95}
                  />
                  <text
                    textAnchor="middle"
                    y={r + 14}
                    fontSize={11}
                    fontWeight={700}
                    fill={flowTintColor}
                  >
                    {nodeChangePct > 0 ? '+' : ''}{nodeChangePct.toFixed(1)}%
                  </text>
                </g>
              )}
              {/* ADA: SVG <title> gives screen readers a real label per node.
                  AT will read it as the accessible name when the <g> is focused. */}
              <title>
                {n.ticker}{n.name ? ` — ${n.name}` : ''}{n.sector ? ` — ${n.sector}` : ''}
                {nodeFlow && Math.abs(nodeChangePct) > 0.05 ? ` — ${nodeChangePct > 0 ? 'up' : 'down'} ${Math.abs(nodeChangePct).toFixed(1)} percent today` : ''}
                {sepaTier ? ` — SEPA ${sepaTier.replace('_', ' ').toLowerCase()}` : ''}
              </title>
              {/* ADA: bumped from 9px → 12px (was below practical readability
                  for low-vision users). Added paint-order stroke halo so the
                  text reads cleanly on both the bright center and the darker
                  edge of the radial gradient — mitigates the contrast drop
                  on multi-letter tickers (GOOGL/AAPL/AVGO) that extend toward
                  the gradient edge. */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={isCentered ? 14 : (isSelected || isHover ? 13 : 12)}
                fontWeight={800}
                fill="#0a0a0a"
                stroke="#ffffff"
                strokeWidth={2.5}
                strokeOpacity={0.55}
                style={{ pointerEvents: 'none', userSelect: 'none', paintOrder: 'stroke fill' }}
              >
                {n.ticker}
              </text>
              {/* Pin indicator if user has dragged this node */}
              {pinned[n.ticker] && (
                <circle
                  r={3}
                  cx={r * 0.7}
                  cy={-r * 0.7}
                  fill="var(--gold)"
                  stroke="#0a0a0a"
                  strokeWidth={0.5}
                />
              )}
            </g>
          );
        })}

        </g>
        {/* ---- end zoom/pan transform group ---- */}
      </svg>

      {/* Edge tooltip on hover */}
      {hoveredEdge && (
        <div
          className="dep-graph__tooltip"
          style={{
            left: Math.min(width - 320, hoveredEdge.x + 16),
            top:  Math.min(height - 220, hoveredEdge.y + 16),
          }}
        >
          <div className="dep-graph__tt-head">
            <strong>{hoveredEdge.edge.source}</strong>
            <span className="dep-graph__tt-rel" style={{ color: RELATION_COLORS[hoveredEdge.edge.relation] ?? '#94a3b8' }}>
              {hoveredEdge.edge.relation.replace(/_/g, ' ')}
            </span>
            <strong>{hoveredEdge.edge.target}</strong>
            <span className="dep-graph__tt-strength mono">str {hoveredEdge.edge.strength}</span>
          </div>
          <div className="dep-graph__tt-evidence">{hoveredEdge.edge.evidence}</div>
          {hoveredEdge.edge.news_links && hoveredEdge.edge.news_links.length > 0 && (
            <ul className="dep-graph__tt-news">
              <li className="dep-graph__tt-news-label">Recent news mentioning both:</li>
              {hoveredEdge.edge.news_links.slice(0, 3).map((n, i) => (
                <li key={i}>
                  {n.url ? (
                    <a href={n.url} target="_blank" rel="noreferrer">{n.title} ↗</a>
                  ) : <span>{n.title}</span>}
                  {n.publisher && <span className="dep-graph__tt-pub"> — {n.publisher}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Zoom controls (top-right of graph) */}
      <div className="dep-graph__zoom">
        <button
          type="button"
          className="dep-graph__zoom-btn"
          onClick={() => zoomBy(1.25)}
          title="Zoom in"
          aria-label="Zoom in"
        >+</button>
        <span className="dep-graph__zoom-level mono" title="Current zoom — pinch (or ⌘/Ctrl + scroll) on the graph to change">
          {Math.round(zoom * 100)}%
        </span>
        <button
          type="button"
          className="dep-graph__zoom-btn"
          onClick={() => zoomBy(0.8)}
          title="Zoom out"
          aria-label="Zoom out"
        >−</button>
        <button
          type="button"
          className="dep-graph__zoom-btn dep-graph__zoom-btn--reset"
          onClick={resetView}
          title="Reset zoom + pan"
          aria-label="Reset view"
          disabled={zoom === 1 && pan.x === 0 && pan.y === 0}
        >⌂</button>
        <button
          type="button"
          className="dep-graph__zoom-btn dep-graph__zoom-btn--fullscreen"
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
          aria-label={isFullscreen ? 'Exit full screen' : 'Full screen'}
        >{isFullscreen ? '✕' : '⛶'}</button>
      </div>

      {/* Legend */}
      <div className="dep-graph__legend">
        <span className="dep-graph__legend-label">Relation:</span>
        {Object.entries(RELATION_COLORS).map(([rel, color]) => (
          <span key={rel} className="dep-graph__legend-key">
            <span className="dep-graph__legend-swatch" style={{ background: color }} /> {rel.replace(/_/g, ' ')}
          </span>
        ))}
        {Object.keys(pinned).length > 0 && (
          <button
            type="button"
            className="dep-graph__reset"
            onClick={() => setPinned({})}
            title="Clear all pinned positions"
          >
            ↻ reset positions
          </button>
        )}
      </div>

      {/* Hint shown if user hasn't interacted yet */}
      {Object.keys(pinned).length === 0 && zoom === 1 && pan.x === 0 && pan.y === 0 && (
        <div className="dep-graph__hint">
          tip: <strong>pinch</strong> to zoom · <strong>drag bg</strong> to pan · <strong>tap</strong> bubble for thesis · <strong>drag</strong> bubble to move
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------
// Layout: sector-clustered force-directed
// -------------------------------------------------------------------------

function computeLayout(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number,
  centerTicker?: string,
  pinned: Record<string, { x: number; y: number }> = {},
) {
  const cx = width / 2, cy = height / 2;

  // Group nodes by sector — distribute each sector's anchor across a 2D
  // GRID covering the full canvas (not a ring around center). With ~10
  // sectors and 56 nodes this lets every sector get its own panel-sized
  // region instead of cramming everything in the middle 30%.
  // Sector cells are weighted by node count so big sectors like
  // Semiconductors get more room than small ones like Aerospace.
  const sectorList = Array.from(new Set(nodes.map((n) => n.sector ?? 'Other'))).sort();
  const nodesPerSector: Record<string, number> = {};
  for (const n of nodes) {
    const s = n.sector ?? 'Other';
    nodesPerSector[s] = (nodesPerSector[s] || 0) + 1;
  }

  const sectorAnchors: Record<string, { x: number; y: number }> = {};
  // Grid layout: cols × rows chosen to match the canvas aspect ratio so cells
  // are roughly square. With width 1500×680 and 10 sectors, that's 4 cols × 3
  // rows = 12 cells (2 spare which go unused).
  const margin = 70;
  const innerW = Math.max(200, width - margin * 2);
  const innerH = Math.max(200, height - margin * 2);
  const N = sectorList.length || 1;
  const aspect = innerW / innerH;
  const cols = Math.max(1, Math.min(N, Math.round(Math.sqrt(N * aspect))));
  const rows = Math.ceil(N / cols);
  const cellW = innerW / cols;
  const cellH = innerH / rows;
  sectorList.forEach((s, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    sectorAnchors[s] = {
      x: margin + cellW * (col + 0.5),
      y: margin + cellH * (row + 0.5),
    };
  });

  // Seed each node near its sector anchor + small jitter
  const positions: Record<string, LaidOutNode> = {};
  nodes.forEach((n, i) => {
    const a = sectorAnchors[n.sector ?? 'Other'] ?? { x: cx, y: cy };
    if (pinned[n.ticker]) {
      positions[n.ticker] = {
        ...n, x: pinned[n.ticker].x, y: pinned[n.ticker].y, vx: 0, vy: 0, pinned: true,
      };
      return;
    }
    if (n.ticker === centerTicker) {
      positions[n.ticker] = { ...n, x: cx, y: cy, vx: 0, vy: 0 };
      return;
    }
    // Deterministic jitter from index so layout is stable across renders
    const jx = ((i * 31) % 80) - 40;
    const jy = ((i * 17) % 80) - 40;
    positions[n.ticker] = {
      ...n,
      x: a.x + jx,
      y: a.y + jy,
      vx: 0,
      vy: 0,
    };
  });

  // Force parameters — tuned to spread nodes across the FULL canvas grid
  // with enough room for the glow RINGS (which extend to r+14 outer halo)
  // plus the change-% label pill below each bubble.
  // - Strong sectorPull keeps each sector locked to its grid cell
  // - centerPull near 0 so clusters DON'T migrate to middle
  // - Big repulsion + long springs to push nodes outward inside their cell
  const repulsion = 5500;          // node-node push (3000 → 5500: rings need room)
  const springRest = 175;          // ideal edge length (130 → 175)
  const springK = 0.035;           // slightly looser springs so repulsion wins
  const damping = 0.84;
  const centerPull = 0.0008;       // tiny — cells stay where they're anchored
  const sectorPull = 0.060;        // strong — keeps each sector compact around its grid centroid
  const ITER = 420;                // more relaxation passes for the new spacing
  // Hard collision: minimum center-to-center distance.
  // Bubble visual footprint = (r=14-24) + outer-halo (+14) + change-% pill
  // below (+16). For two adjacent default bubbles, edges meet at ~28+28 = 56px
  // before any gap. We want a 30-40px visible gap, so center-to-center ~96px.
  const minDist = 96;

  // Build adjacency for hover-highlight
  const adjacency: Record<string, Set<string>> = {};
  for (const e of edges) {
    if (!adjacency[e.source]) adjacency[e.source] = new Set();
    if (!adjacency[e.target]) adjacency[e.target] = new Set();
    adjacency[e.source].add(e.target);
    adjacency[e.target].add(e.source);
  }

  // Inter-sector repulsion multiplier. Pairs from DIFFERENT sectors push
  // each other much harder than same-sector pairs, so cluster hulls stop
  // bleeding into each other (Tech vs Semis was overlapping badly).
  const INTER_SECTOR_MULT = 3.0;

  for (let step = 0; step < ITER; step++) {
    // Repulsion between all node pairs
    const ids = Object.keys(positions);
    for (let i = 0; i < ids.length; i++) {
      const A = positions[ids[i]];
      if (A.pinned) continue;
      for (let j = i + 1; j < ids.length; j++) {
        const B = positions[ids[j]];
        const dx = B.x - A.x;
        const dy = B.y - A.y;
        const dist2 = dx * dx + dy * dy + 0.01;
        // Inter-sector pairs push each other much harder
        const sameSector = A.sector === B.sector;
        const mult = sameSector ? 1.0 : INTER_SECTOR_MULT;
        const f = (repulsion * mult) / dist2;
        const dist = Math.sqrt(dist2);
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        if (!A.pinned) { A.vx -= fx; A.vy -= fy; }
        if (!B.pinned) { B.vx += fx; B.vy += fy; }
      }
    }
    // Springs along edges
    for (const e of edges) {
      const A = positions[e.source];
      const B = positions[e.target];
      if (!A || !B) continue;
      const dx = B.x - A.x;
      const dy = B.y - A.y;
      const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = springK * (dist - springRest) * (0.7 + (e.strength ?? 0.5) * 0.6);
      const fx = (dx / dist) * f;
      const fy = (dy / dist) * f;
      if (!A.pinned) { A.vx += fx; A.vy += fy; }
      if (!B.pinned) { B.vx -= fx; B.vy -= fy; }
    }
    // Sector cluster pull + center pull
    for (const id of ids) {
      const p = positions[id];
      if (p.pinned) continue;
      const a = sectorAnchors[p.sector ?? 'Other'] ?? { x: cx, y: cy };
      p.vx += (a.x - p.x) * sectorPull;
      p.vy += (a.y - p.y) * sectorPull;
      const isCenter = id === centerTicker;
      const pull = isCenter ? centerPull * 6 : centerPull;
      p.vx += (cx - p.x) * pull;
      p.vy += (cy - p.y) * pull;
    }
    // Apply velocities + damping + bounds
    for (const id of ids) {
      const p = positions[id];
      if (p.pinned) continue;
      p.vx *= damping;
      p.vy *= damping;
      const v = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
      const maxV = 14;
      if (v > maxV) { p.vx *= maxV / v; p.vy *= maxV / v; }
      p.x += p.vx;
      p.y += p.vy;
      const margin = 40;
      p.x = Math.max(margin, Math.min(width - margin, p.x));
      p.y = Math.max(margin, Math.min(height - margin, p.y));
    }

    // Hard collision pass — guarantees no two nodes are closer than minDist.
    // Cheap O(n^2) but n is ~56 so it's negligible.
    const ids2 = Object.keys(positions);
    for (let i = 0; i < ids2.length; i++) {
      const A = positions[ids2[i]];
      for (let j = i + 1; j < ids2.length; j++) {
        const B = positions[ids2[j]];
        const dx = B.x - A.x;
        const dy = B.y - A.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.001;
        if (dist < minDist) {
          const overlap = (minDist - dist) / 2;
          const nx = dx / dist;
          const ny = dy / dist;
          if (!A.pinned) { A.x -= nx * overlap; A.y -= ny * overlap; }
          if (!B.pinned) { B.x += nx * overlap; B.y += ny * overlap; }
          // Re-clamp to bounds
          if (!A.pinned) {
            A.x = Math.max(40, Math.min(width - 40, A.x));
            A.y = Math.max(40, Math.min(height - 40, A.y));
          }
          if (!B.pinned) {
            B.x = Math.max(40, Math.min(width - 40, B.x));
            B.y = Math.max(40, Math.min(height - 40, B.y));
          }
        }
      }
    }
  }

  return { byId: positions, adjacency, sectorAnchors };
}

// -------------------------------------------------------------------------
// Sector hull computation (light convex-hull for cluster background tints)
// -------------------------------------------------------------------------

function computeSectorHulls(
  nodes: GraphNode[],
  positions: Record<string, { x: number; y: number }>,
) {
  const bySector: Record<string, { x: number; y: number }[]> = {};
  for (const n of nodes) {
    const s = n.sector ?? 'Other';
    if (!bySector[s]) bySector[s] = [];
    const p = positions[n.ticker];
    if (p) bySector[s].push({ x: p.x, y: p.y });
  }

  const hulls: { sector: string; path: string; color: string; centroid: { x: number; y: number }; radius: number }[] = [];
  for (const [sector, pts] of Object.entries(bySector)) {
    if (pts.length < 2) continue;
    const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
    // Use bounding-circle approximation — simple, fast, looks good
    let maxR = 0;
    for (const p of pts) {
      const d = Math.hypot(p.x - cx, p.y - cy);
      if (d > maxR) maxR = d;
    }
    // Hull padding: enough to enclose bubble + glow ring (~r+14) without
    // visually bleeding into adjacent sector cells.
    const radius = maxR + 14;
    // SVG circle as path: M(cx-r,cy) a(r,r 0 1,0 2r,0) a(r,r 0 1,0 -2r,0)
    const path = `M ${cx - radius} ${cy} a ${radius} ${radius} 0 1 0 ${radius * 2} 0 a ${radius} ${radius} 0 1 0 ${-radius * 2} 0 Z`;
    hulls.push({
      sector,
      path,
      color: SECTOR_COLORS[sector] ?? '#94a3b8',
      centroid: { x: cx, y: cy },
      radius,
    });
  }
  return hulls;
}

// -------------------------------------------------------------------------
// Color helpers
// -------------------------------------------------------------------------

function lightenColor(hex: string, pct: number): string {
  const { r, g, b } = hexToRgb(hex);
  const lr = Math.min(255, r + (255 - r) * (pct / 100));
  const lg = Math.min(255, g + (255 - g) * (pct / 100));
  const lb = Math.min(255, b + (255 - b) * (pct / 100));
  return `rgb(${Math.round(lr)},${Math.round(lg)},${Math.round(lb)})`;
}

function darkenColor(hex: string, pct: number): string {
  const { r, g, b } = hexToRgb(hex);
  return `rgb(${Math.round(r * (1 - pct / 100))},${Math.round(g * (1 - pct / 100))},${Math.round(b * (1 - pct / 100))})`;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '');
  const bigint = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return { r: (bigint >> 16) & 255, g: (bigint >> 8) & 255, b: bigint & 255 };
}
