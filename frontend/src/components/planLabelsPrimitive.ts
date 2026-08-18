/* The plan's labels, drawn by us instead of by the library.
 *
 * Ajay 2026-08-17: *"Can you move these labels to the left or something they
 * are all clumsy and its hard to look at the bars"*.
 *
 * WHY THIS FILE HAD TO EXIST AT ALL
 * ---------------------------------
 * lightweight-charts 4.2.3 draws a price line's `title` itself, and gives no
 * way to place it: `PanePriceAxisView._internal_renderer()` takes its alignment
 * from `pane._internal_priceScalePosition(priceScale)`, and it does not
 * de-overlap two titles that land on the same pixels. So the library's plate
 * is switched off — `title: ''`, which is exactly the flag its own
 * `showPaneLabel = options.title !== ''` reads — and redrawn here. The price
 * line itself and its axis chip stay: he said the chips were fine, and
 * reproducing them would mean reimplementing `priceFormat`/`minMove`.
 *
 * WHAT THIS DRAWS AND WHY IT LOOKS LIKE THIS
 * ------------------------------------------
 *   * One plate per level carrying the word AND its own price — `STOP HIT
 *     $63.44`, not `STOP` on the chart and `63.44` on the axis. A displaced
 *     plate must be readable without matching a colour across two surfaces to
 *     a cent, which is the thing that made splitting them unsafe.
 *   * Right-aligned, into the blank gutter ZoneChart reserves. That is where
 *     they already were, where TradingView and thinkorswim put bracket tags,
 *     and — on a fitted chart whose middle is denser than its right edge — the
 *     side where they cover the fewest bars. Moving them left would be worse.
 *   * A leader elbow whenever `layoutPlanLabels` had to move a plate off its
 *     line, so the plate never silently claims the height it is drawn at.
 *
 * All arithmetic lives in lib/labelLayout.ts and lib/zoneChart.ts, which are
 * pure and tested. This file measures text and fills rectangles.
 */
import type {
  ISeriesPrimitive,
  ISeriesPrimitivePaneRenderer,
  ISeriesPrimitivePaneView,
  ISeriesApi,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from 'lightweight-charts';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import { BOX_H, GAP, layoutPlanLabels, type LabelInput } from '../lib/labelLayout';
import type { PriceLineSpec } from '../lib/zoneChart';

const FONT = '600 11px ui-monospace, SFMono-Regular, Menlo, monospace';
const PAD_X = 6;
const EDGE = 6;          // gap between the plate and the price axis
const ELBOW = 7;         // how far left the leader steps before turning
const RADIUS = 3;

/** Plate text is near-black on a bright plate, or near-white on a dark one —
 *  chosen from the plate colour rather than fixed, because SUPPLY red and
 *  NEUTRAL slate sit on opposite sides of readable. */
function inkFor(bg: string): string {
  const m = /^#([0-9a-f]{6})$/i.exec(bg.trim());
  if (!m) return '#0b1120';
  const n = parseInt(m[1], 16);
  const lum = (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  return lum > 0.6 ? '#0b1120' : '#f8fafc';
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number,
                   w: number, h: number, r: number): void {
  const rr = Math.min(r, h / 2, w / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

class PlanLabelsRenderer implements ISeriesPrimitivePaneRenderer {
  constructor(
    private readonly lines: PriceLineSpec[],
    private readonly series: ISeriesApi<SeriesType, Time> | null,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    const series = this.series;
    if (!series || !this.lines.length) return;

    // MEDIA space, not bitmap: this draws TEXT, and the media scope hands back
    // a context already scaled to CSS pixels. Measuring and laying out in
    // device pixels and then dividing is the classic way to get font sizes
    // that are right on one display and wrong on the next.
    target.useMediaCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { width, height } = scope.mediaSize;
      if (!(width > 0) || !(height > 0)) return;

      ctx.save();
      ctx.font = FONT;
      ctx.textBaseline = 'middle';

      const items: LabelInput[] = this.lines.map((l) => ({
        key: l.kind,
        text: l.title,
        color: l.color,
        // null when the price is off the visible scale. layoutPlanLabels drops
        // those rather than pinning them to an edge.
        y: series.priceToCoordinate(l.price),
        priority: l.priority,
      }));

      const placed = layoutPlanLabels(items, { height });

      for (const p of placed) {
        const w = Math.ceil(ctx.measureText(p.text).width) + PAD_X * 2;
        const right = width - EDGE;
        const left = right - w;
        const top = p.labelY - BOX_H / 2;

        // The elbow first, so the plate paints over its own stub end.
        if (p.displaced) {
          ctx.strokeStyle = p.color;
          ctx.globalAlpha = 0.85;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(left, p.labelY);
          ctx.lineTo(left - ELBOW, p.labelY);
          ctx.lineTo(left - ELBOW, p.y);
          ctx.stroke();
          // A dot ON the line: the elbow says "this plate belongs to that
          // level", and the dot says exactly which pixel row it means.
          ctx.globalAlpha = 1;
          ctx.fillStyle = p.color;
          ctx.beginPath();
          ctx.arc(left - ELBOW, p.y, 2, 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.globalAlpha = 1;
        ctx.fillStyle = p.color;
        roundRect(ctx, left, top, w, BOX_H, RADIUS);
        ctx.fill();
        ctx.fillStyle = inkFor(p.color);
        ctx.fillText(p.text, left + PAD_X, p.labelY + 0.5);
      }

      ctx.restore();
    });
  }
}

class PlanLabelsPaneView implements ISeriesPrimitivePaneView {
  constructor(private readonly owner: PlanLabelsPrimitive) {}

  /** Above the candles — unlike the bands, which are context. A plate the tape
   *  paints over is the bug this file is fixing. */
  zOrder(): 'top' { return 'top'; }

  renderer(): ISeriesPrimitivePaneRenderer {
    return new PlanLabelsRenderer(this.owner.lines, this.owner.series);
  }
}

export class PlanLabelsPrimitive implements ISeriesPrimitive<Time> {
  lines: PriceLineSpec[];
  series: ISeriesApi<SeriesType, Time> | null = null;
  private readonly views: ISeriesPrimitivePaneView[];
  private requestUpdate?: () => void;

  constructor(lines: PriceLineSpec[]) {
    this.lines = lines;
    this.views = [new PlanLabelsPaneView(this)];
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this.series = param.series as ISeriesApi<SeriesType, Time>;
    this.requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this.series = null;
    this.requestUpdate = undefined;
  }

  paneViews(): readonly ISeriesPrimitivePaneView[] {
    return this.views;
  }

  setLines(lines: PriceLineSpec[]): void {
    this.lines = lines;
    this.requestUpdate?.();
  }
}

/** Exported for the tests: the vertical pitch the layout uses. */
export const PLATE = { height: BOX_H, gap: GAP };
