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
import { Fragment, memo, useCallback, useEffect, useId, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  bandAt, barDomain, barIndexAt, barWidth, clipBands, curveLabels, dropCollidingTicks,
  gutterWidth, hoverLines, lineLabels, markerIndex, offDomainBands, priceAt,
  timeTicks,
  priceTicks, pxText, themeLabel, toneColor, tooltipPos, xFor, yFor,
  type CmBadge, type CmStat, type CmTile,
} from '../lib/chartMaps';
import {
  cardLadder, FOLD_GROUPS, FOLD_LABEL, planLineKey, type FoldItem, type OuterChip,
} from '../lib/cardLadder';
import { sanitizeSourceQuery, withSource } from '../lib/navSource';
import { openTvChart } from '../lib/tvChart';
import { SignalWatchButton } from './SignalWatchButton';
import { GrowthChip } from './GrowthChip';
import { PromoOriginChip } from './PromoOriginChip';
import { ExplosiveChip } from './ExplosiveChip';
import { BandStructureChip } from './BandStructureChip';
import type { BandStructureStudy } from '../lib/bandStructure';
import { EnterableChip } from './EnterableChip';
import { MomentumBurstChip } from './MomentumBurstChip';
import { isBurst, type BurstRead } from '../lib/momentumBurst';
import type { ExplosiveStudy } from '../lib/bounceRoom';
import { AmdRaidsChip } from './AmdRaidsChip';
import {
  amdRaidMarks, occupiedFromMarkers, RAID_R, sanitizeAmdRaids,
} from '../lib/amdRaids';

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
  // The AMD accumulation base (2026-09-12). Without it the band fell to
  // the muted grey default and read as a 0DTE range.
  amd_accumulation: 'var(--cm-violet, #8b5cf6)',
  // The demand BOARD's own band on the per-ticker views (2026-09-14): the
  // same green/red as the swing bands because it IS support/overhead — but
  // drawn as a dashed OUTLINE (see isOutline) so it reads as "the band the
  // alert would name" laid over the finer levels, not as one more fill.
  board_demand: 'var(--positive, #22c55e)',
  board_supply: 'var(--negative, #ef4444)',
};

/** A plan line's dash. `buy` and 🔑 `key` are the only SOLID lines, so a key
 *  level stays easy to tell apart; 🔑 `key_broken` (through it now, or closed
 *  through it today) is a short 3,3 dash; everything else keeps 5,4. */
const lineDash = (tone: string): string | undefined =>
  tone === 'buy' || tone === 'key' ? undefined
    : tone === 'key_broken' ? '3,3'
      : tone === 'ownstop' ? '2,3' : '5,4';

/** Board bands are outlines, never fills — one look, one meaning. */
const isOutline = (kind: string) => kind === 'board_demand' || kind === 'board_supply';

const BAND_NAME: Record<string, string> = {
  base: 'Base', demand: 'Support', supply: 'Overhead', neutral: 'Range',
  fvg_demand: 'Fair value gap', fvg_supply: 'Fair value gap',
  order_block: 'Order block',
  board_demand: 'Board demand', board_supply: 'Board overhead',
};

export const PatternChart = memo(function PatternChart(
  { tile, height = 190, tvTf, study, bandStudy, burst, outerChips, expandAll }: {
    tile: CmTile; height?: number; tvTf?: string;
    /** 🧨 The board's served explosive verdict, for the chip's tooltip —
     *  the number never lives in this file (board.explosive_study). */
    study?: ExplosiveStudy | null;
    /** 🪜 The board's served band-structure verdict, for the chip's tooltip —
     *  the status never lives in this file (board.band_structure_study). */
    bandStudy?: BandStructureStudy | null;
    /** ⚡ The served momentum-burst read, passed ONLY while the Chart Maps
     *  checkbox is ticked (null otherwise), so the badge and the pin can never
     *  disagree. Prop-fed; nothing is computed here. */
    burst?: BurstRead | null;
    /** 📋 The chips the WRAPPER already prints beside this tile (the Support
     *  head, the POTUS head, the 9 EMA strip). The tile skips exactly these,
     *  so one card never shows the same chip twice. */
    outerChips?: ReadonlyArray<OuterChip>;
    /** ⊞ The page's "Expand all" answer for every card's ▸ more. A card he
     *  opens or closes by hand keeps his choice until ⊞ is pressed again. */
    expandAll?: boolean;
  },
) {
  const location = useLocation();
  const bars = tile.bars || [];
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  /* 📋 ▸ more, per card per session (the SepaCandidateCard "#3 declutter"
   * toggle). `null` = follow the page's ⊞; a click here overrides it, and a
   * new ⊞ answer clears the override (⊞ means all). Above the early return. */
  const [moreOv, setMoreOv] = useState<boolean | null>(null);
  const moreId = useId();
  useEffect(() => { setMoreOv(null); }, [expandAll]);
  const more = moreOv ?? !!expandAll;

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
  const domain = barDomain(bars, tile.bands, tile.lines, 6, tile.curves);
  const bands = clipBands(tile.bands || [], domain);
  /* The BOARD bands that fell outside the plot. Only the board ones: they are
   * the ones the served note points at by name, and a reader who cannot find
   * the dashed band is being invited to read the solid intraday ones as the
   * board's (2026-09-23). Every other overlay speaks for itself. */
  const offBoard = offDomainBands(tile.bands || [], domain)
    .filter((o) => isOutline(String(o.band.kind)));
  const labels = lineLabels(
    [...(tile.lines || []), ...curveLabels(tile.curves)], domain, H, PAD_Y, LABEL_FS);
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
  /* 🌀 Every AMD raid (Ajay 2026-09-24: "Show all the possible raids, past
   * ones too and todays too."). The block is served whole by the backend —
   * past raids on CLOSED bars, today's provisional read off the live print —
   * and filterTile drops it with the AMD family. The circles and the chip's
   * list read the SAME sanitized array, so they cannot disagree. Row spacing
   * is 11 viewBox units, so two circles on one row need that many units of
   * bars between them. Display only. */
  const raids = sanitizeAmdRaids((tile as any).amd_raids);
  const raidMarks = amdRaidMarks(raids, bars, {
    minGapBars: Math.max(1, Math.ceil(11 / (plotW / Math.max(bars.length, 1)))),
    lowY: (i) => yFor(bars[i].l, domain, H, PAD_Y),
    highY: (i) => yFor(bars[i].h, domain, H, PAD_Y),
    top: PAD_Y + RAID_R,
    // clear of the squeeze dot row at H - PAD_Y - 2
    bottom: H - PAD_Y - 4 - RAID_R,
    occupied: occupiedFromMarkers(tile.markers || [], bars),
  });

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

  /* 📋 THE ENTRY LADDER (Ajay 2026-09-24: "I want them to categorized in a
   * good way so I have enough info for entry of a stock"; 2026-09-25 "Yes,
   * build the ladder"). ENTRY → PRICE → chart → SETUP → PLAN → TIMING →
   * ▸ more. lib/cardLadder.ts decides every rung from the SERVED strings; this
   * file only draws them. Nothing is removed: the fold is `hidden`, never
   * unmounted, so every folded read stays in the DOM and on the ticker page. */
  const skip = new Set<OuterChip>(outerChips || []);
  const ladder = cardLadder(tile, { skip: outerChips });
  const pill = (b: CmBadge, i: number) => (
    <span key={`${i}-${b.text}`} className={`cm-badge cm-badge-${b.tone}`}>{b.text}</span>
  );
  const kv = (st: CmStat, i: number, wide = false) => (
    <span key={`${i}-${st.k}`} className={`cm-stat${wide || st.v.length > 16 ? ' cm-stat-wide' : ''}`}>
      <span className="cm-stat-k">{st.k}</span>
      <span className="cm-stat-v">{st.v}</span>
    </span>
  );
  const lastPx = last ? pxText(last.c) : null;
  const lastStat = (
    <span className="cm-stat">
      <span className="cm-stat-k">Last</span>
      <span className="cm-stat-v">{lastPx ?? '\u2014'}</span>
    </span>
  );

  /* PLAN rows: the served band as the buy ZONE plus the BUY line as the entry
   * (his answer 2026-09-25: "Zone + entry"), then stop / target, then the
   * served room stats. A price that is not a finite number drops its row. */
  const lineOf = (tone: string) => ladder.plan.lines.find((l) => l.tone === tone);
  const buyPx = pxText(lineOf('buy')?.price);
  const zoneLo = pxText(ladder.plan.buyZone?.lo);
  const zoneHi = pxText(ladder.plan.buyZone?.hi);
  const planRows: { st: CmStat; wide?: boolean }[] = [];
  if (zoneLo && zoneHi) {
    planRows.push({ wide: true, st: { k: 'Buy zone',
      v: `${zoneLo}\u2013${zoneHi}${buyPx ? ` \u00B7 entry ${buyPx}` : ''}` } });
  } else if (buyPx) {
    planRows.push({ st: { k: 'Entry', v: buyPx } });
  }
  /* A row is named by WHAT THE LINE IS, not by its tone: the fixed word only
   * when the served label is the canonical one. Breaking serves its lid as
   * {label:'BREAK', tone:'target'}, Holdings a '200d' MA as tone 'stop' — those
   * print under their own served label, never as "Target" / "Stop". */
  for (const [tone, k] of [['stop', 'Stop'], ['target', 'Target'], ['cost', 'Cost'],
                           ['ownstop', 'Your stop']] as const) {
    const line = lineOf(tone);
    const px = pxText(line?.price);
    if (!px || !line) continue;
    const label = typeof line.label === 'string' ? line.label.trim() : '';
    planRows.push({ st: { k: planLineKey(tone, label, k), v: px } });
  }
  for (const st of ladder.plan.stats) planRows.push({ st });
  const showBand = !skip.has('band');
  const planHas = planRows.length > 0 || ladder.plan.lastOnFace && !!last
    || ladder.plan.pills.length > 0 || (showBand && !!tile.band_structure);

  /* 🎯 One mount, placed on the face or in READS by the ladder. */
  const enterableChip = skip.has('enterable') ? null : <EnterableChip read={tile.enterable} />;
  const explosiveChip = skip.has('explosive') ? null
    : <ExplosiveChip read={tile.explosive} study={study} />;
  const zonePill = ladder.zone ? (
    <span className={`cm-badge cm-badge-${ladder.zone.tone}`}>{ladder.zone.text}</span>
  ) : null;

  // 🌀 The study run: served overlay verdicts (KC first, AMD last), then the raids
  // chip that expands the AMD verdict. Hoisted so contract #13's source order holds.
  const studyChips = (tile.badges || []).map((b, i) => ({ b, i }))
    .filter(({ b }) => !!b && !!b.group)
    .sort((x, y) => Number(x.b.group === 'amd') - Number(y.b.group === 'amd') || x.i - y.i)
    .map(({ b }) => <span key={b.text} className={`cm-badge cm-badge-${b.tone}`}>{b.text}</span>);
  const studyRun = (<>{studyChips}<AmdRaidsChip block={raids} /></>);

  const entryHas = (ladder.enterableOnFace && !!enterableChip) || ladder.entry.length > 0
    || !!(ladder.zone && ladder.zone.onFace);
  const priceHas = !!ladder.approach || ladder.price.length > 0 || ladder.priceAfter.length > 0
    || isBurst(burst) || !!ladder.keyLevel;
  const setupHas = !!ladder.why || ladder.setup.badges.length > 0 || ladder.setup.stats.length > 0;
  const timingHas = ladder.timing.badges.length > 0 || ladder.timing.stats.length > 0
    || !!ladder.timing.mergedBoard || studyChips.length > 0 || !!raids || ladder.moreCount > 0;

  /* ▸ more — the folded-warn cue: a warn-toned served chip behind the fold
   * turns the button amber and says how many (the vetoes never fold). */
  const warnN = ladder.moreWarn.length;
  const moreTitle = 'Risk, tape, floor, sector and study reads \u2014 nothing dropped'
    + (warnN ? ` \u00B7 folded warning${warnN === 1 ? '' : 's'}: ${ladder.moreWarn.map((b) => b.text).join(' \u00B7 ')}` : '');
  const foldItem = (it: FoldItem, i: number) => {
    if (it.badge) return pill(it.badge, i);
    if (it.slot === 'explosive') return <Fragment key={`s-${i}`}>{explosiveChip}</Fragment>;
    if (it.slot === 'enterable') return <Fragment key={`s-${i}`}>{enterableChip}</Fragment>;
    if (it.slot === 'zone') return <Fragment key={`s-${i}`}>{zonePill}</Fragment>;
    // 🔑 The served key-level line: every member, its distance and state,
    // undrawn ones and reversals included (cardLadder puts it here only when
    // `fold` is a non-empty string).
    if (it.slot === 'keylevels') {
      return (
        <span key={`s-${i}`} className="cm-badge cm-badge-muted cm-keylevels-fold">
          {tile.key_levels?.fold}
        </span>
      );
    }
    return null;
  };

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
            {/* What the company IS: theme, growth, promo origin, the served
                company facts. Never an entry read. */}
            <div className="cm-tile-ident">
              {theme ? <span className="cm-badge cm-badge-theme">{theme}</span> : null}
              {/* 🚀 Explosive Growth (Ajay 2026-09-11: "I am hoping this new
                  list will be considerd in all chart maps. Like in Deep demand
                  scan"). Every tile board renders through this component, so one
                  chip here lights up Back in Demand, Deep Demand, Quick Reversal,
                  Breaking, VCP and the rest. ⛔ tone when the trading engine will
                  refuse the name — good sales must not make it look clean. */}
              {skip.has('growth') ? null : <GrowthChip symbol={tile.symbol} />}
              {skip.has('promo') ? null : <PromoOriginChip symbol={tile.symbol} />}
              {ladder.ident.map(pill)}
            </div>
          </div>
          <div className="cm-tile-actions">
            {/* Ajay 2026-09-07: "One click and add to signals tab" — every card,
              * every board; the Signals tab reads the same store. */}
            {skip.has('watch') ? null : <SignalWatchButton symbol={tile.symbol} />}
            <button type="button" className="cm-tv"
                    title={`Open ${tile.symbol} in TradingView`}
                    aria-label={`Open ${tile.symbol} in TradingView`}
                    onClick={(e) => openTvChart(e, tile.symbol, tvTf)}>
              TV ↗
            </button>
          </div>
        </div>

        {entryHas || priceHas ? (
          <div className="cm-rungs">
            {/* ① ENTRY — can I enter? 🎯 first, then the served verdicts and
                vetoes (warn → good → muted), then the zone pill ONLY when it
                disagrees with the board's premise (amber, his call #4). */}
            {entryHas ? (
              <div className="cm-rung cm-rung-entry">
                <span className="cm-rung-tag">ENTRY</span>
                <div className="cm-rung-items">
                  {/* 🎯 The ENTERABLE read (2026-09-15). Ajay: "I only wanna see
                      the stocks that are enterable." Prop-fed off the tile,
                      exactly like the 🧨 chip — nothing here decides the
                      verdict. The n/a kind folds into READS. */}
                  {ladder.enterableOnFace ? enterableChip : null}
                  {ladder.entryNotes.map((n, i) => (
                    <span key={`n-${i}-${n}`} className="cm-rung-note">{`\u00B7 ${n}`}</span>
                  ))}
                  {ladder.entry.map(pill)}
                  {ladder.zone && ladder.zone.onFace ? zonePill : null}
                </div>
              </div>
            ) : null}
            {/* ② PRICE — where is it now? Position pills, the approach LINE in
                its served tone, the ⚡ momentum burst, then tape and money. */}
            {priceHas ? (
              <div className="cm-rung cm-rung-price">
                <span className="cm-rung-tag">PRICE</span>
                <div className="cm-rung-items">
                  {ladder.price.map(pill)}
                  {/* 🔑 Key level (2026-09-25): the served chip, only while
                      the price is through a level now or after it CLOSED
                      through one. Display only — UNMEASURED. */}
                  {ladder.keyLevel ? (
                    <span className={`cm-badge cm-badge-${ladder.keyLevel.tone} cm-keylevel`}>
                      {ladder.keyLevel.text}
                    </span>
                  ) : null}
                  {ladder.approach ? (
                    <span className={`cm-approach cm-approach-${ladder.approach.tone}`}>
                      {ladder.approach.text}
                    </span>
                  ) : null}
                  {/* ⚡ Momentum burst (Ajay 2026-09-24: "Pin + badge, hide
                      nothing"). Served per tile by chart_maps/board.attach_burst
                      and handed down by the page only while its checkbox is
                      ticked. Renders nothing unless the server said ⚡. UNMEASURED. */}
                  <MomentumBurstChip read={burst} />
                  {ladder.priceAfter.map(pill)}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

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
            const outline = isOutline(String(b.kind));
            const colour = BAND_FILL[b.kind] || 'var(--text-muted, #94a3b8)';
            return (
              <g key={`band-${i}`} data-band-kind={b.kind}>
                <rect x={0} y={yTop} width={plotW} height={Math.max(yBot - yTop, 1)}
                      fill={outline ? 'none' : colour}
                      stroke={outline ? colour : 'none'}
                      strokeWidth={outline ? (on ? 1.6 : 1.2) : 0}
                      strokeDasharray={outline ? '5,3' : undefined}
                      opacity={outline ? (on ? 1 : 0.85) : (on ? 0.26 : 0.13)}>
                  <title>
                    {`${b.label || BAND_NAME[b.kind] || b.kind} `
                     + `${b.lo.toFixed(2)}–${b.hi.toFixed(2)}`}
                  </title>
                </rect>
                {!outline && (
                  <line x1={0} y1={yTop} x2={plotW} y2={yTop}
                        stroke={colour} strokeWidth={on ? 1.2 : 0.8}
                        opacity={on ? 0.9 : 0.45} />
                )}
                {!outline && (
                  <line x1={0} y1={yBot} x2={plotW} y2={yBot}
                        stroke={colour} strokeWidth={on ? 1.2 : 0.8}
                        opacity={on ? 0.9 : 0.45} />
                )}
              </g>
            );
          })}

          {/* A BOARD BAND THAT IS NOT ON THIS CHART SAYS SO (2026-09-23).
              `clipBands` drops a band entirely outside the domain, so on an
              intraday frame the board's daily band usually vanished while the
              note below still called it "the dashed band". An edge marker with
              its numbers, on the side it fell off, instead of a claim about a
              rectangle nobody can see. */}
          {offBoard.map((o, i) => {
            const colour = BAND_FILL[o.band.kind] || 'var(--text-muted, #94a3b8)';
            const below = o.side === 'below';
            const yEdge = below ? H - PAD_Y : PAD_Y;
            return (
              <g key={`offband-${i}`} data-band-kind={`${o.band.kind}-off`}>
                <line x1={0} y1={yEdge} x2={plotW} y2={yEdge} stroke={colour}
                      strokeWidth={1} strokeDasharray="5,3" opacity={0.6} />
                <text x={3} y={below ? yEdge - 3 : yEdge + 9} fontSize="8.5"
                      fill={colour} opacity={0.95}>
                  {`${o.band.label || BAND_NAME[o.band.kind] || o.band.kind} `
                   + `${o.band.lo.toFixed(2)}–${o.band.hi.toFixed(2)} — `
                   + `${below ? 'below' : 'above'} this chart`}
                </text>
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
            {/* 2026-09-14 — the studies mark WHERE they happened. */}
            if (m.kind === 'kc_sq') {
              // TTM squeeze dot row: one dot under each bar the Bollinger band
              // sits inside the Keltner channel. Bottom of the plot, never on
              // the candles.
              return (
                <circle key={`mk-${m.date}-${mi}`} className="pc-kc-sq"
                        cx={x} cy={H - PAD_Y - 2} r={1.6}
                        fill="var(--cm-amberlt, #f59e0b)" opacity={0.9} />
              );
            }
            if (m.kind === 'touch_d' || m.kind === 'touch_s') {
              // The swing that made a band: ▲ under a swing low, ▼ over a
              // swing high, in the band's own colour.
              const low = m.kind === 'touch_d';
              const y = low ? yFor(bar.l, domain, H, PAD_Y) + 3
                            : yFor(bar.h, domain, H, PAD_Y) - 3;
              const pts = low
                ? `${x - 2.6},${y + 4.5} ${x + 2.6},${y + 4.5} ${x},${y}`
                : `${x - 2.6},${y - 4.5} ${x + 2.6},${y - 4.5} ${x},${y}`;
              return (
                <polygon key={`mk-${m.date}-${mi}`}
                         className={low ? 'pc-touch-d' : 'pc-touch-s'}
                         points={pts}
                         fill={low ? 'var(--positive, #22c55e)' : 'var(--negative, #ef4444)'}
                         opacity={0.85} />
              );
            }
            if (m.kind === 'amd_a' || m.kind === 'amd_m' || m.kind === 'amd_d'
                || m.kind === 'amd_x') {
              // A on the base's first bar, M on the raid bar, ✗ on the bar
              // that closed through the raided edge — all under the low; D on
              // the markup bar, over the high. Violet, like the family.
              const above = m.kind === 'amd_d';
              const y = above ? yFor(bar.h, domain, H, PAD_Y) - 8
                              : yFor(bar.l, domain, H, PAD_Y) + 8;
              const fill = m.kind === 'amd_x' ? 'var(--negative, #ef4444)'
                                              : 'var(--cm-violet, #8b5cf6)';
              return (
                <g key={`mk-${m.date}-${mi}`} className={`pc-amd pc-${m.kind}`}>
                  <circle cx={x} cy={y} r={4.6} fill={fill} opacity={0.92} />
                  <text x={x} y={y + 2.4} fontSize="6.5" fontWeight="700"
                        textAnchor="middle" fill="#0b0e14">{m.label || ''}</text>
                </g>
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

          {/* 🌀 numbered AMD raid circles (2026-09-24) — one per drawn raid,
              the served mark inside (3·2 = a re-sweep of raid 3's base).
              Dashed = today, not closed; ? = beyond the edge now, not a raid.
              Stacked clear of the tile's own glyphs; a raid with no free row
              stays in the list and off the chart. */}
          {raidMarks.map((m) => (
            <g key={`raid-${m.dir}-${m.i}-${m.mark}`}
               className={'pc-amd-raid pc-amd-raid-' + m.dir
                          + (m.live ? ' pc-amd-raid-live' : '')
                          + (m.unsure ? ' pc-amd-raid-unsure' : '')}
               data-raid-mark={m.mark}>
              <title>{m.text}</title>
              <circle cx={xFor(m.i, bars.length, W, padR)} cy={m.y} r={m.r} />
              <text x={xFor(m.i, bars.length, W, padR)} y={m.y + 2.3} fontSize={6.5}
                    fontWeight={700} textAnchor="middle">{m.mark}</text>
            </g>
          ))}

          {/* plan levels */}
          {(tile.lines || [])
            .filter((l) => l.price >= domain.lo && l.price <= domain.hi)
            .map((l, li) => {
              const y = yFor(l.price, domain, H, PAD_Y);
              return (
                // Keyed by index too: two lines can legitimately share a
                // label and a price (2026-09-14), and duplicate React keys in
                // a subtree that re-renders on every mousemove drop children.
                <line key={`ln-${li}-${l.label}-${l.price}`}
                      data-tone={l.tone}
                      x1={0} y1={y} x2={plotW} y2={y}
                      stroke={toneColor(l.tone)} strokeWidth={l.tone === 'cost' ? 1.4 : 1.1}
                      strokeDasharray={lineDash(l.tone)}
                      opacity={0.9} />
              );
            })}

          {/* Per-bar overlays — the Keltner channel (Ajay 2026-09-13, MU).
            * Drawn UNDER the candles so the price action stays on top, and
            * split on nulls: the EMA/ATR warm-up leaves the left edge empty
            * on a long frame, and joining across that gap would draw a
            * straight segment through a channel that did not exist yet. */}
          {(tile.curves || []).map((c, ci) => {
            const segs: string[] = [];
            let cur: string[] = [];
            (c.values || []).forEach((v, i) => {
              if (v == null || !Number.isFinite(v)) {
                if (cur.length > 1) segs.push(cur.join(' '));
                cur = [];
                return;
              }
              cur.push(`${xFor(i, bars.length, W, padR)},${yFor(v, domain, H, PAD_Y)}`);
            });
            if (cur.length > 1) segs.push(cur.join(' '));
            return segs.map((pts, si) => (
              <polyline key={`cv-${ci}-${c.label}-${si}`} points={pts} fill="none"
                        stroke={toneColor(c.tone)} strokeWidth={1.1}
                        strokeDasharray={(c.label || '').includes('mid') ? '5,4' : undefined}
                        opacity={0.85} />
            ));
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

          {/* pointers: a label pushed off its level points back to it
            * (Ajay 2026-09-08: "These overlap, can you use some pointers") */}
          {labels
            .filter((l) => l.y0 != null && Math.abs(l.y - l.y0) >= 2)
            .map((l, li) => (
              <path key={`ld-${li}-${l.text}`} className="pc-leader"
                    d={`M${plotW},${l.y0} L${plotW + 3},${l.y}`}
                    stroke={l.color} strokeWidth={0.8} opacity={0.6} fill="none" />
            ))}

          {/* right-edge price labels, de-collided */}
          {labels.map((l, li) => (
            <text key={`lb-${li}-${l.text}`} x={plotW + 4} y={l.y + 3}
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

        {setupHas || planHas || timingHas ? (
          <div className="cm-rungs">
            {/* SETUP — pattern tabs only: the why line when it is not a copy of
                the PRICE line, the stats no rung claims, and every served badge
                the ladder does not know (the safety net — on the face, never
                in the fold). */}
            {setupHas ? (
              <div className="cm-rung cm-rung-setup">
                <span className="cm-rung-tag">SETUP</span>
                <div className="cm-rung-items">
                  {ladder.why ? <div className="cm-tile-why">{ladder.why}</div> : null}
                  {ladder.setup.badges.map(pill)}
                  {ladder.setup.stats.length ? (
                    <div className="cm-kv">{ladder.setup.stats.map((st, i) => kv(st, i))}</div>
                  ) : null}
                </div>
              </div>
            ) : null}
            {/* ③ PLAN — buy zone / entry, stop, target, R:R, room, printed as
                text whether or not the Trade-lines box draws them (his call
                #2), then the served room pills and the 🪜 line. */}
            {planHas ? (
              <div className="cm-rung cm-rung-plan">
                <span className="cm-rung-tag">PLAN</span>
                <div className="cm-rung-items">
                  {planRows.length || (ladder.plan.lastOnFace && last) ? (
                    <div className="cm-kv">
                      {planRows.map((r, i) => kv(r.st, i, r.wide))}
                      {ladder.plan.lastOnFace && last ? lastStat : null}
                    </div>
                  ) : null}
                  {ladder.plan.pills.map(pill)}
                  {/* 🪜 The BAND STRUCTURE read (2026-09-16). Ajay: "prioritize
                      stock by the thinnest over head or Supply zone". Prop-fed;
                      it prints the server's own sentence, so this file derives
                      no percentage. The `Bands` stat that repeats it word for
                      word is not printed a second time. */}
                  {showBand ? <BandStructureChip read={tile.band_structure} study={bandStudy} /> : null}
                </div>
              </div>
            ) : null}
            {/* ④ TIMING — fresh or stale: dwell, back in, then the study run
                (KC, then AMD, then the raids chip that expands it), then ▸ more.
                The study verdicts sit HERE, not in ENTRY: both reads are
                MEASURED INVERTED and must not look like an entry trigger. */}
            {timingHas ? (
              <div className="cm-rung cm-rung-timing">
                <span className="cm-rung-tag">TIMING</span>
                <div className="cm-rung-items cm-tile-badges">
                  {ladder.timing.badges.map(pill)}
                  {ladder.timing.mergedBoard ? (
                    <span className="cm-stat"><span className="cm-stat-v">{ladder.timing.mergedBoard}</span></span>
                  ) : null}
                  {ladder.timing.stats.map((st, i) => (
                    <span key={`${i}-${st.k}`} className="cm-stat">
                      <span className="cm-stat-k">{st.k}</span>
                      <span className="cm-stat-v">{st.v}</span>
                    </span>
                  ))}
                  {studyRun}
                  {ladder.moreCount > 0 ? (
                    <button type="button"
                            className={`cm-badge cm-badge-more${warnN ? ' cm-badge-more-warn' : ''}`}
                            aria-expanded={more} aria-controls={moreId} title={moreTitle}
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setMoreOv(!more); }}>
                      {more ? '\u25BE less' : `\u25B8 more \u00B7 ${ladder.moreCount}${warnN ? ` \u00B7 \u26A0${warnN}` : ''}`}
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* ▸ more — labelled groups, each drawn only when it has items. HIDDEN,
            never unmounted: every folded read stays in the DOM. */}
        {ladder.moreCount > 0 ? (
          <div id={moreId} className="cm-more" hidden={!more}>
            {FOLD_GROUPS.filter((g) => ladder.more[g].length > 0).map((g) => {
              const items = ladder.more[g];
              const stats = items.filter((it) => it.stat || it.slot === 'last');
              const chips = items.filter((it) => !(it.stat || it.slot === 'last'));
              return (
                <div key={g} className="cm-more-group">
                  <span className="cm-rung-tag">{FOLD_LABEL[g]}</span>
                  <div className="cm-rung-items">
                    {stats.length ? (
                      <div className="cm-kv">
                        {stats.map((it, i) => (it.stat ? kv(it.stat, i)
                          : <Fragment key={`last-${i}`}>{lastStat}</Fragment>))}
                      </div>
                    ) : null}
                    {chips.map(foldItem)}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </Link>
  );
});
