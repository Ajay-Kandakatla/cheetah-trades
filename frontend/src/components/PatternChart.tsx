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
import { memo } from 'react';
import { Link } from 'react-router-dom';
import {
  barDomain, barWidth, clipBands, dropCollidingTicks, lineLabels, markerIndex,
  monthTicks, priceTicks, themeLabel, toneColor, xFor, yFor,
  type CmTile,
} from '../lib/chartMaps';
import { withSource } from '../lib/navSource';

const W = 620;
const PAD_R = 62;          // right gutter for the price labels
const PAD_Y = 10;

const BAND_FILL: Record<string, string> = {
  base: 'var(--positive, #22c55e)',
  demand: 'var(--positive, #22c55e)',
  supply: 'var(--negative, #ef4444)',
};

export const PatternChart = memo(function PatternChart(
  { tile, height = 190 }: { tile: CmTile; height?: number },
) {
  const bars = tile.bars || [];
  if (!bars.length) return null;

  const H = height;
  const domain = barDomain(bars, tile.bands, tile.lines);
  const bands = clipBands(tile.bands || [], domain);
  const labels = lineLabels(tile.lines || [], domain, H, PAD_Y);
  const bw = barWidth(bars.length, W, PAD_R);
  const ticks = monthTicks(bars);
  // Axis ticks are computed AFTER the plan labels and yield to them: the
  // plan numbers are the decision, the scale is context.
  const axis = priceTicks(domain, H, PAD_Y);
  // Every tick draws its LINE; only the non-colliding ones draw a NUMBER.
  const axisText = dropCollidingTicks(axis, labels);
  const theme = themeLabel(tile.theme);
  const last = bars[bars.length - 1];

  return (
    <Link
      to={withSource(tile.href, 'chart-maps')}
      state={{ from: '/chart-maps', label: 'Chart Maps' }}
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
          </div>
        </div>

        <svg viewBox={`0 0 ${W} ${H}`} className="cm-svg" role="img"
             aria-label={`${tile.symbol} daily chart, ${bars.length} bars`}>
          {/* price scale — drawn FIRST so bands, candles and plan lines all sit
              on top of it. Numbers live in the right gutter, never over the
              price action. */}
          {axis.map((t) => (
            <line key={`ax-${t.price}`} x1={0} y1={t.y} x2={W - PAD_R} y2={t.y}
                  stroke="var(--rule, #2a2f3a)" strokeWidth={0.6} opacity={0.55} />
          ))}
          {axisText.map((t) => (
            <text key={`axt-${t.price}`} x={W - PAD_R + 4} y={t.y + 3} fontSize="9"
                  fill="var(--text-muted, #7c869b)">{t.text}</text>
          ))}

          {/* price bands (base / demand / supply) */}
          {bands.map((b, i) => {
            const yTop = yFor(b.hi, domain, H, PAD_Y);
            const yBot = yFor(b.lo, domain, H, PAD_Y);
            return (
              <g key={`band-${i}`}>
                <rect x={0} y={yTop} width={W - PAD_R} height={Math.max(yBot - yTop, 1)}
                      fill={BAND_FILL[b.kind] || 'var(--text-muted, #94a3b8)'}
                      opacity={0.13} />
                <line x1={0} y1={yTop} x2={W - PAD_R} y2={yTop}
                      stroke={BAND_FILL[b.kind]} strokeWidth={0.8} opacity={0.45} />
                <line x1={0} y1={yBot} x2={W - PAD_R} y2={yBot}
                      stroke={BAND_FILL[b.kind]} strokeWidth={0.8} opacity={0.45} />
              </g>
            );
          })}

          {/* dated confirmation marker — joined by DATE, never by index */}
          {(tile.markers || []).map((m) => {
            const i = markerIndex(bars, m.date);
            if (i < 0) return null;
            const x = xFor(i, bars.length, W, PAD_R);
            return (
              <g key={`mk-${m.date}`}>
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
                      x1={0} y1={y} x2={W - PAD_R} y2={y}
                      stroke={toneColor(l.tone)} strokeWidth={1.1}
                      strokeDasharray={l.tone === 'buy' ? undefined : '5,4'}
                      opacity={0.9} />
              );
            })}

          {/* candles */}
          {bars.map((b, i) => {
            const x = xFor(i, bars.length, W, PAD_R);
            const up = b.c >= b.o;
            const col = up ? 'var(--positive, #22c55e)' : 'var(--negative, #ef4444)';
            const yo = yFor(b.o, domain, H, PAD_Y);
            const yc = yFor(b.c, domain, H, PAD_Y);
            return (
              <g key={b.t}>
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
            <text key={`lb-${l.text}`} x={W - PAD_R + 4} y={l.y + 3}
                  fontSize="9.5" fill={l.color}
                  fontWeight={l.bold ? 700 : 400}>{l.text}</text>
          ))}

          {/* month ticks */}
          {ticks.map((t) => (
            <text key={`tk-${t.i}`} x={xFor(t.i, bars.length, W, PAD_R)} y={H - 2}
                  fontSize="8.5" fill="var(--text-muted, #7c869b)"
                  textAnchor="middle">{t.label}</text>
          ))}
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
