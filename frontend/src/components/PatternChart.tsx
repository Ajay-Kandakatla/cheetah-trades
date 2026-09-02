/* PatternChart — one study tile: daily candles with the geometry that made
 * this chart qualify drawn on top of it.
 *
 * Ajay 2026-08-15: "I need just maps that you are pulling show."
 *
 * Hand-rolled SVG rather than lightweight-charts, for three reasons: a 24-tile
 * grid would mean 24 chart engines and 24 ResizeObservers; v4 has no filled
 * box primitive, so supply/demand bands would need a custom ISeriesPrimitive
 * the app has never written; and every number drawn here comes from pure,
 * tested functions in lib/chartMaps.ts, which a canvas engine hides.
 *
 * All geometry lives in lib/chartMaps.ts. This file only draws.
 */
import { memo, useCallback, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  bandAt, barDomain, barIndexAt, barWidth, clipBands, dropCollidingTicks,
  gutterWidth, hoverLines, lineLabels, markerIndex, priceAt, timeTicks,
  priceTicks, themeLabel, toneColor, tooltipPos, xFor, yFor,
  type CmTile,
} from '../lib/chartMaps';
import { sanitizeSourceQuery, withSource } from '../lib/navSource';
import { openTvChart } from '../lib/tvChart';

const W = 620;
const PAD_Y = 10;
const LABEL_FS = 9.5;

const BAND_FILL: Record<string, string> = {
  base: 'var(--positive, #22c55e)',
  demand: 'var(--positive, #22c55e)',
  supply: 'var(--negative, #ef4444)',
  // Neither a floor nor a lid — the 0DTE gamma walls bracket a RANGE, and
  // painting it green or red would give it a direction it does not have.
  neutral: 'var(--text-muted, #94a3b8)',
  // Smart-Money overlays (2026-08-29). Deliberately NOT the same green/red
  // as the swing bands: a fair value gap is an imbalance and an order block
  // is a footprint, and painting them in the support/overhead colours would
  // claim they are the same kind of evidence.
  fvg_demand: 'var(--info, #38bdf8)',
  fvg_supply: 'var(--warn, #e8a33d)',
  order_block: 'var(--accent, #a78bfa)',
};

const BAND_NAME: Record<string, string> = {
  base: 'Base', demand: 'Support', supply: 'Overhead', neutral: 'Range',
  fvg_demand: 'Fair value gap', fvg_supply: 'Fair value gap',
  order_block: 'Order block',
};

export const PatternChart = memo(function PatternChart(
  { tile, height = 190, tvTf }: { tile: CmTile; height?: number; tvTf?: string },
) {
  const location = useLocation();
  const bars = tile.bars || [];
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);

  // Client px -> viewBox units. Exact because .cm-svg is width:100% with no
  // height set, so the rendered box keeps the viewBox's aspect ratio and the
  // default preserveAspectRatio never letterboxes.
  const onMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const el = svgRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    setHover({
      x: ((e.clientX - r.left) / r.width) * W,
      y: ((e.clientY - r.top) / r.height) * height,
    });
  }, [height]);

  const onLeave = useCallback(() => setHover(null), []);

  if (!bars.length) return null;

  const H = height;
  const domain = barDomain(bars, tile.bands, tile.lines);
  const bands = clipBands(tile.bands || [], domain);
  const labels = lineLabels(tile.lines || [], domain, H, PAD_Y);
  const axis = priceTicks(domain, H, PAD_Y);
  // The gutter is sized from the labels it has to hold. Ajay 2026-08-19 sent a
  // META tile reading "overhead 553" and "support 527." — a fixed 62 units
  // could not fit "overhead 553.67", and the Support tab is exactly the place
  // where that label IS the answer.
  const padR = gutterWidth(
    [...labels.map((l) => l.text), ...axis.map((t) => t.text)], LABEL_FS);
  const plotW = W - padR;
  // Every tick draws its LINE; only the non-colliding ones draw a NUMBER.
  const axisText = dropCollidingTicks(axis, labels);
  const bw = barWidth(bars.length, W, padR);
  const ticks = timeTicks(bars);
  // Extended-hours runs (live frame): consecutive bars flagged pre/ah become
  // one shaded span each, so the overnight stretch reads at a glance.
  const extSpans: { from: number; to: number }[] = [];
  bars.forEach((b, i) => {
    if (!b.s) return;
    const last = extSpans[extSpans.length - 1];
    if (last && last.to === i - 1) last.to = i; else extSpans.push({ from: i, to: i });
  });
  const theme = themeLabel(tile.theme);
  const last = bars[bars.length - 1];

  /* Hover readout. `hover` stays null on touch devices and whenever the
   * pointer is outside, so none of this runs on the 24-tile board unless you
   * are actually pointing at a tile. */
  const hx = hover ? Math.min(hover.x, plotW) : 0;
  const hIdx = hover ? barIndexAt(hx, bars.length, W, padR) : -1;
  const hBar = hIdx >= 0 ? bars[hIdx] : null;
  const hPrice = hover ? priceAt(hover.y, domain, H, PAD_Y) : null;
  const hBand = hPrice != null ? bandAt(hPrice, bands) : null;
  const tipLines = hoverLines(hBar);
  const TIP_W = 104;
  const TIP_H = tipLines.length * 11 + 8;
  const tip = hover
    ? tooltipPos(xFor(Math.max(hIdx, 0), bars.length, W, padR), hover.y,
                 TIP_W, TIP_H, plotW, H)
    : null;

  // State carries the page's search too — resolveBack prefers state, and a
  // bare '/chart-maps' here was why even a PLAIN click lost the tab
  // (Ajay 2026-08-25: "back button do not take me to the same place in these
  // tabs"). The ?from/from_q pair covers the no-state new-tab branch.
  const carryQ = sanitizeSourceQuery(location.search);
  const backTarget = carryQ ? `/chart-maps?${carryQ}` : '/chart-maps';

  return (
    <Link
      to={withSource(tile.href, 'chart-maps', location.search)}
      state={{ from: backTarget, label: 'Chart Maps' }}
      style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
      aria-label={`${tile.symbol} — open SEPA detail`}
    >
      <div className="cm-tile">
        <div className="cm-tile-head">
          <div className="cm-tile-id">
            <b>{tile.symbol}</b>
            {tile.name ? <span className="cm-tile-name">{tile.name}</span> : null}
          </div>
          <div className="cm-tile-badges">
            {theme ? <span className="cm-badge cm-badge-theme">{theme}</span> : null}
            {(tile.badges || []).map((b) => (
              <span key={b.text} className={`cm-badge cm-badge-${b.tone}`}>{b.text}</span>
            ))}
            <button type="button" className="cm-tv"
                    title={`Open ${tile.symbol} in TradingView`}
                    aria-label={`Open ${tile.symbol} in TradingView`}
                    onClick={(e) => openTvChart(e, tile.symbol, tvTf)}>
              TV ↗
            </button>
          </div>
        </div>

        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="cm-svg" role="img"
             onMouseMove={onMove} onMouseLeave={onLeave}
             aria-label={`${tile.symbol} daily chart, ${bars.length} bars`}>
          {/* price scale — drawn FIRST so bands, candles and plan lines all sit
              on top of it. Numbers live in the right gutter, never over the
              price action. */}
          {axis.map((t) => (
            <line key={`ax-${t.price}`} x1={0} y1={t.y} x2={plotW} y2={t.y}
                  stroke="var(--rule, #2a2f3a)" strokeWidth={0.6} opacity={0.55} />
          ))}
          {axisText.map((t) => (
            <text key={`axt-${t.price}`} x={plotW + 4} y={t.y + 3} fontSize="9"
                  fill="var(--text-muted, #7c869b)">{t.text}</text>
          ))}

          {/* price bands (base / demand / supply). The <title> gives the same
              answer the crosshair does, for a pointer that just rests here and
              for a screen reader. */}
          {bands.map((b, i) => {
            const yTop = yFor(b.hi, domain, H, PAD_Y);
            const yBot = yFor(b.lo, domain, H, PAD_Y);
            const on = hBand === b;
            return (
              <g key={`band-${i}`}>
                <rect x={0} y={yTop} width={plotW} height={Math.max(yBot - yTop, 1)}
                      fill={BAND_FILL[b.kind] || 'var(--text-muted, #94a3b8)'}
                      opacity={on ? 0.26 : 0.13}>
                  <title>
                    {`${b.label || BAND_NAME[b.kind] || b.kind} `
                     + `${b.lo.toFixed(2)}–${b.hi.toFixed(2)}`}
                  </title>
                </rect>
                <line x1={0} y1={yTop} x2={plotW} y2={yTop}
                      stroke={BAND_FILL[b.kind]} strokeWidth={on ? 1.2 : 0.8}
                      opacity={on ? 0.9 : 0.45} />
                <line x1={0} y1={yBot} x2={plotW} y2={yBot}
                      stroke={BAND_FILL[b.kind]} strokeWidth={on ? 1.2 : 0.8}
                      opacity={on ? 0.9 : 0.45} />
              </g>
            );
          })}

          {/* dated confirmation marker — joined by DATE, never by index.
              buy/sell markers render as candle-anchored tags (the GainzAlgo
              convention: BUY under the bar, SELL above it); sweep/BOS/ORB
              markers as small glyphs; anything else keeps the gold line. */}
          {(tile.markers || []).map((m, mi) => {
            const i = markerIndex(bars, m.date);
            if (i < 0) return null;
            const x = xFor(i, bars.length, W, padR);
            const bar = bars[i];
            if (m.kind === 'buy' || m.kind === 'sell') {
              const buy = m.kind === 'buy';
              const y = buy
                ? yFor(bar.l, domain, H, PAD_Y) + 12
                : yFor(bar.h, domain, H, PAD_Y) - 5;
              const fill = buy ? 'var(--positive, #22c55e)' : 'var(--negative, #ef4444)';
              const wTag = (m.label || '').length * 5.4 + 8;
              return (
                <g key={`mk-${m.date}-${mi}`}>
                  <line x1={x} y1={buy ? y - 10 : y + 3}
                        x2={x} y2={buy ? y - 4 : y + 8}
                        stroke={fill} strokeWidth={1.2} />
                  <rect x={x - wTag / 2} y={buy ? y - 2 : y - 9}
                        width={wTag} height={11} rx={2.5} fill={fill} opacity={0.92} />
                  <text x={x} y={buy ? y + 6.5 : y - 0.5} fontSize="8" fontWeight="700"
                        textAnchor="middle" fill="#0b0e14">{m.label}</text>
                </g>
              );
            }
            if (m.kind === 'sweep' || m.kind === 'bos' || m.kind === 'choch'
                || m.kind === 'orb_up' || m.kind === 'orb_dn') {
              const yG = yFor(bar.h, domain, H, PAD_Y) - 3;
              return (
                <text key={`mk-${m.date}-${mi}`} x={x} y={yG} fontSize="7.5"
                      textAnchor="middle" fill="var(--text-muted, #94a3b8)">
                  {m.label}
                </text>
              );
            }
            return (
              <g key={`mk-${m.date}-${mi}`}>
                <line x1={x} y1={PAD_Y} x2={x} y2={H - PAD_Y}
                      stroke="var(--gold, #c9a227)" strokeWidth={1} strokeDasharray="3,3"
                      opacity={0.8} />
                <text x={x + 3} y={PAD_Y + 9} fontSize="9" fill="var(--gold, #c9a227)">
                  {m.label || 'confirmed'}
                </text>
              </g>
            );
          })}

          {/* plan levels */}
          {(tile.lines || [])
            .filter((l) => l.price >= domain.lo && l.price <= domain.hi)
            .map((l) => {
              const y = yFor(l.price, domain, H, PAD_Y);
              return (
                <line key={`ln-${l.label}-${l.price}`}
                      x1={0} y1={y} x2={plotW} y2={y}
                      stroke={toneColor(l.tone)} strokeWidth={1.1}
                      strokeDasharray={l.tone === 'buy' ? undefined : '5,4'}
                      opacity={0.9} />
              );
            })}

          {/* extended-hours shading (live frame only) */}
          {extSpans.map((sp) => {
            const x0 = xFor(sp.from, bars.length, W, padR) - bw / 2;
            const x1 = xFor(sp.to, bars.length, W, padR) + bw / 2;
            return (
              <rect key={`ext-${sp.from}`} className="pc-ext"
                    x={x0} y={PAD_Y} width={Math.max(x1 - x0, 1)} height={H - 2 * PAD_Y}
                    fill="var(--ink, #e7e7e7)" opacity={0.06} />
            );
          })}

          {/* candles */}
          {bars.map((b, i) => {
            const x = xFor(i, bars.length, W, padR);
            const up = b.c >= b.o;
            const col = up ? 'var(--positive, #22c55e)' : 'var(--negative, #ef4444)';
            const yo = yFor(b.o, domain, H, PAD_Y);
            const yc = yFor(b.c, domain, H, PAD_Y);
            return (
              <g key={b.t} opacity={(hIdx >= 0 && hIdx !== i ? 0.82 : 1) * (b.s ? 0.7 : 1)}>
                <line x1={x} y1={yFor(b.h, domain, H, PAD_Y)}
                      x2={x} y2={yFor(b.l, domain, H, PAD_Y)}
                      stroke={col} strokeWidth={0.9} />
                <rect x={x - Math.max(bw * 0.32, 0.8)} y={Math.min(yo, yc)}
                      width={Math.max(bw * 0.64, 1.4)}
                      height={Math.max(Math.abs(yo - yc), 0.9)} fill={col} />
              </g>
            );
          })}

          {/* right-edge price labels, de-collided */}
          {labels.map((l) => (
            <text key={`lb-${l.text}`} x={plotW + 4} y={l.y + 3}
                  fontSize={LABEL_FS} fill={l.color}
                  fontWeight={l.bold ? 700 : 400}>{l.text}</text>
          ))}

          {/* month ticks */}
          {ticks.map((t) => (
            // A first-of-window "Aug '25" centered on bar 0 would clip at the
            // left edge — keep every label inside the plot.
            <text key={`tk-${t.i}`}
                  x={Math.max(xFor(t.i, bars.length, W, padR), t.label.length * 2.2)}
                  y={H - 2}
                  fontSize="8.5" fill="var(--text-muted, #7c869b)"
                  textAnchor="middle">{t.label}</text>
          ))}

          {/* ── hover crosshair + readout ──────────────────────────────────
              Ajay 2026-08-19: "hover over prices at the level or something".
              The price chip in the gutter is the point — it answers "what
              price is my cursor on" for EVERY pixel, not just the handful of
              levels that earned a printed label. */}
          {hover && hPrice != null ? (
            <g pointerEvents="none">
              <line x1={0} y1={hover.y} x2={plotW} y2={hover.y}
                    stroke="var(--text-muted, #94a3b8)" strokeWidth={0.7}
                    strokeDasharray="2,3" opacity={0.75} />
              {hIdx >= 0 ? (
                <line x1={xFor(hIdx, bars.length, W, padR)} y1={PAD_Y}
                      x2={xFor(hIdx, bars.length, W, padR)} y2={H - PAD_Y}
                      stroke="var(--text-muted, #94a3b8)" strokeWidth={0.7}
                      strokeDasharray="2,3" opacity={0.6} />
              ) : null}

              {/* price chip, in the gutter, sitting on the crosshair */}
              <rect x={plotW + 1} y={hover.y - 6.5} width={padR - 2} height={13}
                    rx={2.5} fill="var(--ink, #e7e7e7)" />
              <text x={plotW + 4} y={hover.y + 3.2} fontSize="9.5"
                    fontWeight={700} fill="var(--bg-sunken, #0f1115)">
                {hPrice.toFixed(2)}
              </text>

              {/* which level the cursor is standing on, if any */}
              {hBand ? (
                <text x={4} y={PAD_Y + 9} fontSize="9"
                      fill={BAND_FILL[hBand.kind] || 'var(--text-muted, #94a3b8)'}>
                  {`${hBand.label || BAND_NAME[hBand.kind] || hBand.kind} `
                   + `${hBand.lo.toFixed(2)}–${hBand.hi.toFixed(2)}`}
                </text>
              ) : null}

              {/* the bar under the cursor */}
              {tip && tipLines.length ? (
                <g>
                  <rect x={tip.x} y={tip.y} width={TIP_W} height={TIP_H} rx={4}
                        fill="var(--bg-raised, #181c24)"
                        stroke="var(--rule, #2a2f3a)" strokeWidth={0.8}
                        opacity={0.97} />
                  {tipLines.map((ln, i) => (
                    <text key={ln + i} x={tip.x + 6} y={tip.y + 12 + i * 11}
                          fontSize="8.6"
                          fill={i === 0 ? 'var(--ink, #e7e7e7)'
                                        : 'var(--cm-slate, #8595ad)'}>
                      {ln}
                    </text>
                  ))}
                </g>
              ) : null}
            </g>
          ) : null}
        </svg>

        <div className="cm-tile-why">{tile.why}</div>
        <div className="cm-tile-stats">
          {(tile.stats || []).map((s) => (
            <span key={s.k} className="cm-stat">
              <span className="cm-stat-k">{s.k}</span>
              <span className="cm-stat-v">{s.v}</span>
            </span>
          ))}
          <span className="cm-stat cm-stat-last">
            <span className="cm-stat-k">Last</span>
            <span className="cm-stat-v">{last ? last.c : '—'}</span>
          </span>
        </div>
      </div>
    </Link>
  );
});
