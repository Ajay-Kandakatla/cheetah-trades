/* TapeChart — the ONE tape drawing shared by the Promo Circuit tape (PromoTagTape / MiniTape) and the
 * 🕰️ Gajjala A+ entry tape (GgEntryTape). 2026-10-16 (DECISIONS11 D1, BUILD_SPEC11 §3.6) — Ajay: "Can you use the
 * graph component from  that to show what happened to Entries alert of Gajjala with all the 100% criteria
 * satisfier."
 *
 * Moved VERBATIM out of PromoTagTape.tsx (etStamp, layout, miniLayout and the two SVG bodies), with two widenings
 * that are no-ops for the Promo: `layout(..., extraPx)` folds extra prices into lo / hi, and a mark carrying a finite
 * `px` sits at y(px). Horizontal lines (`hlines`) are new and drawn only when given. Every label is passed in — this
 * file composes no tape word. Attribute ORDER matches PromoTagTape's (React serialises props as written) so the
 * Promo markup stays byte-identical (PromoTagTape.snapshot.test.tsx). Plain SVG — no chart lib. */

export const TAPE_W = 720, TAPE_H = 110, SPARK_H = 30, TAPE_DASH = '3 3', TAPE_DOT_R = 3.5;

export type TapeBar = { t: number; o?: number | null; h?: number | null; l?: number | null; c: number; v?: number | null; s?: string | null };
export type TapeMark = { at: string; px?: number | null; group: string;
  rule?: { stroke?: string; dash?: string } | null; dot?: { r: number; fill?: string } | null; title?: string | null };
export type TapeHLine = { px: number; className: string; label?: string | null };
export type TapeCorners = { bl: string; br: string; tl: string; tr: string };

export const etStamp = (ms: number) =>
  new Date(ms).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' })
    .replace(' AM', 'a').replace(' PM', 'p').replace(',', ' ·') + ' ET';

const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

type LayoutTag = { at: string; px?: number | null };
type SparkTag = { at: string; which?: string };
export type TapeGeomOf<T> = {
  x: (t: number) => number; y: (p: number) => number; lo: number; hi: number; path: string; ext: { x0: number; x1: number }[];
  markers: (T & { ms: number; x: number; y: number; price: number })[]; t0: number; t1: number;
};
export type TapeGeom = TapeGeomOf<TapeMark>;
export type SparkGeom = {
  path: string; ext: { x0: number; x1: number }[]; marker: { x: number; y: number; price: number; ms: number } | null;
  last: { x: number; y: number; price: number }; lo: number; hi: number;
};

/* Pure geometry so the test can pin marker placement. (The overload keeps each caller's own tag fields on its markers.) */
export function layout<T extends LayoutTag>(bars: TapeBar[], tags: T[], w: number, h: number, extraPx?: number[]): TapeGeomOf<T> | null;
export function layout(bars: TapeBar[], tags: LayoutTag[], w: number, h: number, extraPx: number[] = []) {
  if (!bars.length) return null;
  const t0 = bars[0].t, t1 = bars[bars.length - 1].t;
  const extra = extraPx.filter(finite);
  const lo = Math.min(...bars.map((b) => b.l ?? b.c), ...extra), hi = Math.max(...bars.map((b) => b.h ?? b.c), ...extra);   // lite bars carry closes only
  const span = Math.max(1, t1 - t0), range = Math.max(1e-9, hi - lo);
  const x = (t: number) => ((Math.min(Math.max(t, t0), t1) - t0) / span) * (w - 8) + 4;
  const y = (p: number) => h - 14 - ((p - lo) / range) * (h - 26);
  const path = bars.map((b, i) => `${i ? 'L' : 'M'}${x(b.t).toFixed(1)},${y(b.c).toFixed(1)}`).join(' ');
  const ext: { x0: number; x1: number }[] = [];
  let run: { x0: number; x1: number } | null = null;
  bars.forEach((b, i) => {
    const isExt = b.s === 'premarket' || b.s === 'afterhours';
    const xb = x(b.t), xn = i + 1 < bars.length ? x(bars[i + 1].t) : w - 4;
    if (isExt) { if (run) run.x1 = xn; else run = { x0: xb, x1: xn }; }
    else if (run) { ext.push(run); run = null; }
  });
  if (run) ext.push(run);
  const markers = tags.map((tg) => {
    const ms = Date.parse(tg.at);
    const at = [...bars].reverse().find((b) => b.t <= ms) ?? bars[0];
    const price = finite(tg.px) ? tg.px : at.c;
    return { ...tg, ms, x: x(ms), y: y(price), price };
  });
  return { x, y, lo, hi, path, ext, markers, t0, t1 };
}

/* Pure geometry for the sparkline: closes only, full height, no axis band. */
export function miniLayout<T extends SparkTag>(bars: { t: number; c: number; s?: string | null }[], tags: T[], w: number, h: number): SparkGeom | null;
export function miniLayout(bars: { t: number; c: number; s?: string | null }[], tags: SparkTag[], w: number, h: number): SparkGeom | null {
  if (!bars?.length) return null;
  const t0 = bars[0].t, t1 = bars[bars.length - 1].t;
  const lo = Math.min(...bars.map((b) => b.c)), hi = Math.max(...bars.map((b) => b.c));
  const span = Math.max(1, t1 - t0), range = Math.max(1e-9, hi - lo);
  const x = (t: number) => ((Math.min(Math.max(t, t0), t1) - t0) / span) * (w - 6) + 3;
  const y = (p: number) => h - 3 - ((p - lo) / range) * (h - 6);
  const path = bars.map((b, i) => `${i ? 'L' : 'M'}${x(b.t).toFixed(1)},${y(b.c).toFixed(1)}`).join(' ');
  const ext: { x0: number; x1: number }[] = [];
  let run: { x0: number; x1: number } | null = null;
  bars.forEach((b, i) => {
    const isExt = b.s === 'premarket' || b.s === 'afterhours';
    const xb = x(b.t), xn = i + 1 < bars.length ? x(bars[i + 1].t) : w - 3;
    if (isExt) { if (run) run.x1 = xn; else run = { x0: xb, x1: xn }; }
    else if (run) { ext.push(run); run = null; }
  });
  if (run) ext.push(run);
  const first = tags.find((t) => t.which === 'first') ?? tags[0];
  let marker: { x: number; y: number; price: number; ms: number } | null = null;
  if (first) {
    const ms = Date.parse(first.at);
    const at = [...bars].reverse().find((b) => b.t <= ms) ?? bars[0];
    marker = { x: x(ms), y: y(at.c), price: at.c, ms };
  }
  const last = bars[bars.length - 1];
  return { path, ext, marker, last: { x: x(last.t), y: y(last.c), price: last.c }, lo, hi };
}


/* An hline label sits 2 px above its line, unless that would put it on the top-right corner label (baseline y 11,
 * right-anchored at the same x): then it drops 9 px below its line. Fix round 1, 2026-10-16 — a target line at the top
 * of the range (hi) had its label drawn exactly over the served 'tr' corner. Never reached by the Promo (no hlines). */
export const HLINE_LABEL_MIN_Y = 22;   // MINE — the tr corner's baseline (11) plus one label height (11)
export const hlineLabelY = (yLine: number) => (yLine - 2 < HLINE_LABEL_MIN_Y ? yLine + 9 : yLine - 2);

/* The full tape: ext shading → the close path → horizontal levels → one <g> per mark (rule / dot / title) →
 * the four corner labels (bl, br, tr, tl). */
export function TapeChart({ g, width, height, svgClass, lineClass, ariaLabel, hlines, titleOf, corners }: {
  g: TapeGeom; width: number; height: number; svgClass: string; lineClass: string; ariaLabel: string;
  hlines?: TapeHLine[]; titleOf?: (m: any) => string | null; corners: TapeCorners;
}) {
  return (
    <svg className={svgClass} viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img"
         aria-label={ariaLabel}>
      {g.ext.map((e, i) => <rect key={i} x={e.x0} y={0} width={Math.max(1, e.x1 - e.x0)} height={height - 14} className="ptt__ext" />)}
      <path d={g.path} className={lineClass} fill="none" />
      {(hlines ?? []).filter((hl) => finite(hl.px)).map((hl, i) => (
        <g key={`h${i}`} className={hl.className}>
          <line x1={4} x2={width - 4} y1={g.y(hl.px)} y2={g.y(hl.px)} />
          {hl.label ? <text x={width - 4} y={hlineLabelY(g.y(hl.px))} textAnchor="end" className="ptt__axis">{hl.label}</text> : null}
        </g>
      ))}
      {g.markers.map((m, i) => {
        const title = titleOf ? titleOf(m) : m.title;
        return (
          <g key={i} className={m.group}>
            {m.rule ? <line x1={m.x} x2={m.x} y1={4} y2={height - 14} stroke={m.rule.stroke}
                            strokeDasharray={m.rule.dash} /> : null}
            {m.dot ? <circle cx={m.x} cy={m.y} r={m.dot.r} fill={m.dot.fill} /> : null}
            {title != null ? <title>{title}</title> : null}
          </g>
        );
      })}
      <text x={4} y={height - 3} className="ptt__axis">{corners.bl}</text>
      <text x={width - 4} y={height - 3} textAnchor="end" className="ptt__axis">{corners.br}</text>
      <text x={width - 4} y={11} textAnchor="end" className="ptt__axis">{corners.tr}</text>
      <text x={4} y={11} className="ptt__axis">{corners.tl}</text>
    </svg>
  );
}

/* The sparkline: MiniTape's svg verbatim — the first mark as a full-height rule + dot, the last close as a dot. */
export function TapeSpark({ g, width, height, ariaLabel, up, markGroup = 'ptt__mini-tag', markColor }: {
  g: SparkGeom; width: number; height: number; ariaLabel: string; up: boolean; markGroup?: string; markColor?: string;
}) {
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-label={ariaLabel}>
      {g.ext.map((e, i) => <rect key={i} x={e.x0} y={0} width={Math.max(1, e.x1 - e.x0)} height={height} className="ptt__ext" />)}
      <path d={g.path} className={`ptt__mini-line ${up ? 'is-up' : 'is-dn'}`} fill="none" />
      {g.marker ? (
        <g className={markGroup}>
          <line x1={g.marker.x} x2={g.marker.x} y1={1} y2={height - 1} stroke={markColor} />
          <circle cx={g.marker.x} cy={g.marker.y} r={2.6} fill={markColor} />
        </g>
      ) : null}
      <circle cx={g.last.x} cy={g.last.y} r={2} className="ptt__mini-now" />
    </svg>
  );
}
