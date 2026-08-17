/* Supply/demand bands drawn INTO the price scale.
 *
 * Ajay 2026-08-16: *"But may be static makes sense I know it would break the
 * zones"*. It does not have to. A band is a price RANGE, so once it is drawn
 * through the series' own price scale it stays glued to those prices while the
 * chart zooms and pans — the thing the SVG version could not do and the reason
 * he assumed the trade-off existed.
 *
 * This is the first ISeriesPrimitive in the app. PatternChart.tsx:8 notes that
 * lightweight-charts v4 has no filled-box primitive and that a custom one is
 * something "the app has never written"; this is that custom one. It stays
 * deliberately small: it converts prices to y-coordinates and fills rectangles,
 * and holds no state of its own beyond the bands it was handed.
 *
 * Geometry decisions live in lib/zoneChart.ts (bandsFor). Nothing here computes
 * a price.
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
import type { BandSpec } from '../lib/zoneChart';

/* Fills chosen so a band never competes with a candle for attention: the
 * entry band is the only one with an outline, matching the SVG version's rule
 * that the plan outranks context. */
const FILL = {
  supply: 'rgba(239,68,68,0.10)',
  demand: 'rgba(34,197,94,0.10)',
  entry: 'rgba(34,197,94,0.22)',
};
const EDGE = {
  supply: 'rgba(239,68,68,0.45)',
  demand: 'transparent',
  entry: 'rgba(34,197,94,0.95)',
};

class ZoneBandsRenderer implements ISeriesPrimitivePaneRenderer {
  constructor(
    private readonly bands: BandSpec[],
    private readonly series: ISeriesApi<SeriesType, Time> | null,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    const series = this.series;
    if (!series || !this.bands.length) return;

    target.useBitmapCoordinateSpace((scope) => {
      const { context: ctx, bitmapSize, horizontalPixelRatio, verticalPixelRatio } = scope;

      for (const b of this.bands) {
        const yHi = series.priceToCoordinate(b.hi);
        const yLo = series.priceToCoordinate(b.lo);
        // A band entirely outside the visible price range converts to null.
        // Skipping is correct: clamping would pin it to the edge and draw a
        // zone at a price it does not occupy.
        if (yHi == null || yLo == null) continue;

        const top = Math.round(Math.min(yHi, yLo) * verticalPixelRatio);
        const bottom = Math.round(Math.max(yHi, yLo) * verticalPixelRatio);
        // Never collapse to nothing: a sub-pixel band still marks a real level.
        const height = Math.max(1, bottom - top);
        const kind = b.isEntry ? 'entry' : b.kind;

        ctx.fillStyle = FILL[kind];
        ctx.fillRect(0, top, bitmapSize.width, height);

        if (EDGE[kind] !== 'transparent') {
          ctx.fillStyle = EDGE[kind];
          const lw = Math.max(1, Math.round(horizontalPixelRatio));
          ctx.fillRect(0, top, bitmapSize.width, lw);
          if (b.isEntry) ctx.fillRect(0, bottom - lw, bitmapSize.width, lw);
        }
      }
    });
  }
}

class ZoneBandsPaneView implements ISeriesPrimitivePaneView {
  constructor(private readonly owner: ZoneBandsPrimitive) {}

  /** Under the candles. A band is context; the price action is the subject. */
  zOrder(): 'bottom' { return 'bottom'; }

  renderer(): ISeriesPrimitivePaneRenderer {
    return new ZoneBandsRenderer(this.owner.bands, this.owner.series);
  }
}

export class ZoneBandsPrimitive implements ISeriesPrimitive<Time> {
  bands: BandSpec[];
  series: ISeriesApi<SeriesType, Time> | null = null;
  private readonly views: ISeriesPrimitivePaneView[];
  private requestUpdate?: () => void;

  constructor(bands: BandSpec[]) {
    this.bands = bands;
    this.views = [new ZoneBandsPaneView(this)];
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

  /** Swap the bands without tearing the chart down — the payload can refresh
   *  while the user is mid-zoom. */
  setBands(bands: BandSpec[]): void {
    this.bands = bands;
    this.requestUpdate?.();
  }
}
