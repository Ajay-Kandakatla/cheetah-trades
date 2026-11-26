/* 📅 The sessions primitive of the continuous runner chart (2026-11-26, spec runcharts rev 2 §3.7, package fe-chart).
 *
 * Ajay 2026-11-26: "I wanna able to horizontal scroll tp check continuity like he does" — his thinkorswim charts shade
 * pre-market and after-hours grey and mark where each day starts. This primitive draws exactly that, on the candle
 * series, in the zoneBandsPrimitive.ts shape with TWO pane views:
 *   zOrder 'bottom' → the served shade runs, full pane height, one grey (GGRC_SHADE);
 *   zOrder 'top'    → a 1-px dashed line (GGRC_SEP) at the start of every session after the first, and each visible
 *                     session's served date label at the top (the session under the left edge keeps its label at 0;
 *                     a label that would start inside the previous drawn label is skipped, so dates never overprint).
 * Bar indexes are turned into pixels INSIDE draw() through the chart's own time scale (logicalToCoordinate), so a pan
 * or a zoom re-places everything. The geometry rules live in lib/ggRunChart.ts (ggrcShadeRects, ggrcSeparators). Holds
 * no state beyond what it was handed; computes no price and no time. */
import type {
  IChartApiBase,
  ISeriesPrimitive,
  ISeriesPrimitivePaneRenderer,
  ISeriesPrimitivePaneView,
  Logical,
  SeriesAttachedParameter,
  Time,
} from 'lightweight-charts';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import {
  GGRC_SEP, GGRC_SHADE, GGRC_TEXT, ggrcSeparators, ggrcShadeRects,
  type GgrcSession, type GgrcShade, type GgrcToX,
} from '../lib/ggRunChart';

export type SessionsData = { shade: GgrcShade[]; sessions: GgrcSession[] };

const LABEL_PX = 11;       // DRAWING — the label's font size (the chart's own axis font size)
const LABEL_PAD = 4;       // DRAWING — gap between the separator and its label
const DASH = 4;            // DRAWING — dash and gap length of a separator

type Scope = {
  context: CanvasRenderingContext2D;
  bitmapSize: { width: number; height: number };
  horizontalPixelRatio: number;
  verticalPixelRatio: number;
};

class ShadeRenderer implements ISeriesPrimitivePaneRenderer {
  constructor(private readonly owner: SessionsPrimitive) {}

  draw(target: CanvasRenderingTarget2D): void {
    const toX = this.owner.toX();
    const shade = this.owner.data.shade;
    if (!toX || !shade.length) return;
    target.useBitmapCoordinateSpace((scope: Scope) => {
      const { context: ctx, bitmapSize, horizontalPixelRatio: hpr } = scope;
      const width = bitmapSize.width / (hpr || 1);
      ctx.fillStyle = GGRC_SHADE;
      for (const r of ggrcShadeRects(shade, toX, width)) {
        ctx.fillRect(Math.round(r.x * hpr), 0, Math.max(1, Math.round(r.w * hpr)), bitmapSize.height);
      }
    });
  }
}

class SeparatorRenderer implements ISeriesPrimitivePaneRenderer {
  constructor(private readonly owner: SessionsPrimitive) {}

  draw(target: CanvasRenderingTarget2D): void {
    const toX = this.owner.toX();
    const sessions = this.owner.data.sessions;
    if (!toX || !sessions.length) return;
    target.useBitmapCoordinateSpace((scope: Scope) => {
      const { context: ctx, bitmapSize, horizontalPixelRatio: hpr, verticalPixelRatio: vpr } = scope;
      const width = bitmapSize.width / (hpr || 1);
      const marks = ggrcSeparators(sessions, toX, width);
      if (!marks.length) return;
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, bitmapSize.width, bitmapSize.height);
      ctx.clip();
      const lw = Math.max(1, Math.round(hpr));
      ctx.strokeStyle = GGRC_SEP;
      ctx.lineWidth = lw;
      ctx.setLineDash([DASH * hpr, DASH * hpr]);
      for (const m of marks) {
        if (!m.line) continue;
        const x = Math.round(m.x * hpr) + (lw % 2 ? 0.5 : 0);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, bitmapSize.height);
        ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.fillStyle = GGRC_TEXT;
      ctx.font = `${Math.round(LABEL_PX * vpr)}px sans-serif`;
      ctx.textBaseline = 'top';
      // A label that would start inside the previous drawn label's width is skipped (a 5-bar session beside a
      // 900-bar one at `all` would otherwise print two dates on top of each other). Bitmap pixels throughout.
      let prevEnd = -Infinity;
      for (const m of marks) {
        const bx = Math.round((m.x + LABEL_PAD) * hpr);
        if (bx < prevEnd) continue;
        ctx.fillText(m.label, bx, Math.round(LABEL_PAD * vpr));
        prevEnd = bx + ctx.measureText(m.label).width;
      }
      ctx.restore();
    });
  }
}

class ShadeView implements ISeriesPrimitivePaneView {
  constructor(private readonly owner: SessionsPrimitive) {}
  /** Under the candles: the shading is context, the price action is the subject. */
  zOrder(): 'bottom' { return 'bottom'; }
  renderer(): ISeriesPrimitivePaneRenderer { return new ShadeRenderer(this.owner); }
}

class SeparatorView implements ISeriesPrimitivePaneView {
  constructor(private readonly owner: SessionsPrimitive) {}
  /** Over the candles, so a date is never hidden under a bar. */
  zOrder(): 'top' { return 'top'; }
  renderer(): ISeriesPrimitivePaneRenderer { return new SeparatorRenderer(this.owner); }
}

export class SessionsPrimitive implements ISeriesPrimitive<Time> {
  data: SessionsData;
  chart: IChartApiBase<Time> | null = null;
  private readonly views: ISeriesPrimitivePaneView[];
  private requestUpdate?: () => void;

  constructor(data?: SessionsData) {
    this.data = data ?? { shade: [], sessions: [] };
    this.views = [new ShadeView(this), new SeparatorView(this)];
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this.chart = param.chart;
    this.requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this.chart = null;
    this.requestUpdate = undefined;
  }

  paneViews(): readonly ISeriesPrimitivePaneView[] {
    return this.views;
  }

  /** The time scale's bar index → x, asked at draw time; null when not attached. */
  toX(): GgrcToX | null {
    const chart = this.chart;
    if (!chart) return null;
    return (i: number) => chart.timeScale().logicalToCoordinate(i as Logical);
  }

  /** Swap the runs and sessions without tearing the chart down (a refresh while he is mid-pan). */
  setData(data: SessionsData): void {
    this.data = data;
    this.requestUpdate?.();
  }
}
