/* GajjalaWatchTile — the 👀 Watch's tile, frame and ⤢ full-screen view, shared (2026-11-16, ggcard3 spec §3.3, WP-A).
 *
 * A PURE MOVE out of GajjalaWatchBoard.tsx (phoneNow / usePhone / useFitBox / Frame / Tile / Stretch → GgwStretch) so
 * the 🚩 Gajjala cards open the SAME three-chart view, never a second implementation. Ajay 2026-11-16: "Also when I
 * click on a card from any of the Gajjala I would like us to open the 3 chart extension like in the Watch list..." and
 * "Actually instead of 3 mins make it 15 mins timeframe".
 *
 * Additions, every one opt-in (the Watch passes none of them, so its DOM is byte-identical):
 *   - `order` on GgwStretch / Tile → ggwStretchFrames(row.frames, order) (default GGW_STRETCH_ORDER, the Watch's 5/3/1);
 *   - `kind` on GgwStretch → `ggw-stretch--${kind}` + data-kind on the root (absent → today's root exactly);
 *   - a frame with no bars and a SERVED `empty_text` prints those words in place of the chart (caption still printed);
 *   - a frame with a SERVED `as_of_et` prints its own stamp chip in the caption (`⚠️ ` on a served `stale`, the head
 *     chip's exact look). Watch frames carry neither key → no chip.
 * The FE composes no word about a stock here: every string is served, except the structural glyphs.
 *
 * 🤖 2026-11-17 (watch-auto spec §3.6, WP-C) — Ajay: "Can you add more stocks in to watch list basically I need
 * portentials from Gajjals's 1 min and regular and also Audited potentials with good volume to Watchlist on an
 * interval.. Remove as they are not progressing". A row the server added carries `auto`: the tile head prints its served
 * chip after SYM (hover = the served added / volume / leaving words) and the ✕ title is its served `remove_title`.
 * Rows without `auto` (his, the 🚩 cards) render exactly as before.
 *
 * 🎯 2026-11-17 (spec ggwaplus) — Ajay: "Also add an A+ tag on watch list as they become A+". A row with a served
 * `aplus` block prints its chip right after SYM (text verbatim, hover = the served title). No block → nothing.
 *
 * 🩳 2026-11-18 (spec sinote §3.5, WP fe-watch) — Ajay: "When there are extreme cases of short interest make a not for
 * them on reversal squeeze like percentage of short interest on the tickers card and also on watch list". `siNote` on
 * Tile / GgwStretch (the Watch passes it; GgCardView does not, so the 🚩 card's ⤢ view is unchanged) mounts
 * GgSiExtremeNote after the 🤖 chip: the SERVED short form verbatim, hover = the served sentence, nothing when the read
 * is not extreme. Display only; UNMEASURED (eod-audits/research/2026-11-17_si_cradle_squeeze/report.md).
 *
 * 👀 2026-11-18 (cardview spec §3.4, WP-A) — Ajay: "I need the watch list kinda chart formant view video view as default
 * here too from the tabs pages". The 🚩 / 🧪 card grid draws THIS tile; three opt-in props on Tile, none passed by the
 * Watch (its DOM is byte-identical):
 *   - `stack` → the frames stacked in `order` (the ⤢ block) on a board tile, `ggw-charts--stack` + testid
 *     `ggw-stack-charts`; a fitted empty frame (served words, no bars) gets flexGrow 0 there, so the words take their own
 *     height and the charts the rest (the ⤢ view keeps flexGrow 1 on every frame);
 *   - `extra` → caller content right after SYM (absent → nothing);
 *   - `onRemove` is optional → no ✕ without it (a 🚩 card cannot be removed from a board).
 * And `data-empty="1"` on a Frame that prints its served empty words (a Watch frame never carries `empty_text`).
 *
 * 🏷️ 2026-11-18 (spec wtags §3.4, WP-B) — Ajay: "Also add Short Interest tag and other tags on top of stock ticker
 * information for me to read, like here". `tags` on Tile / GgwStretch (the Watch passes it; the 🚩 / 🧪 card grid and
 * GgCardView never do → their DOM is byte-identical) mounts GgwTagsRow (its own module, GajjalaWatchTags.tsx) as the
 * FIRST child of the tile, above the head. This file mounts no house chip itself. */
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import {
  GGW_FIT_GROW, GGW_LIVE_EMA_TIP, GGW_PAGER, GGW_PHONE_MQ, GGW_STRETCH, ggwChartHeight, ggwFitViewBoxH,
  ggwFitViewW, ggwSplitFrames, ggwStretchFrames, ggwStretchTitle, type GgwFrame, type GgwRow,
} from '../lib/gajjalaWatch';
import { ggwLiveFrame, type GgwLiveBar, type GgwLiveSym } from '../lib/ggwLive';
import { GgSiExtremeNote } from './GgSiExtremeNote';
import { GgwTagsRow, type GgwTagsCtx } from './GajjalaWatchTags';
import { openYahoo, yahooTitle, YAHOO_LABEL } from '../lib/yahooLink';
import { PATTERN_CHART_VIEW_W, PatternChart } from './PatternChart';
import { EmaBlinkDot } from './EmaBlink';
import { emaBlinkLine } from '../lib/emaBlink';
import '../styles/gajjalaWatch.css';

function phoneNow(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia(GGW_PHONE_MQ).matches;
}

export function usePhone(): boolean {
  const [phone, setPhone] = useState<boolean>(phoneNow);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const m = window.matchMedia(GGW_PHONE_MQ);
    const h = () => setPhone(m.matches);
    h();
    m.addEventListener?.('change', h);
    return () => m.removeEventListener?.('change', h);
  }, []);
  return phone;
}

/** In a fitted tile: the viewBox height that fills this chart's measured box (null → the GGW_CHART_H height). */
function useFitBox(box: RefObject<HTMLDivElement>, fit: boolean): { w: number; h: number } | null {
  const [h, setH] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!fit || !el) { setH(null); return; }
    const measure = () => {
      const r = el.getBoundingClientRect();
      const w = ggwFitViewW(r.width, PATTERN_CHART_VIEW_W);
      const vh = ggwFitViewBoxH(r.width, r.height, w);
      setH((p) => (vh == null ? null : p && p.w === w && p.h === vh ? p : { w, h: vh }));
    };
    measure();
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    ro?.observe(el);
    return () => ro?.disconnect();
  }, [box, fit]);
  return h;
}

export function Frame({ f, phone, fit, style, live }: {
  f: GgwFrame; phone: boolean; fit: boolean; style?: CSSProperties;
  /** This frame's forming bars (lib/ggwLive), or undefined → the stored frame exactly as served. */
  live?: GgwLiveBar[];
}) {
  const box = useRef<HTMLDivElement>(null);
  const fitH = useFitBox(box, fit);
  const blink = emaBlinkLine(f.ema_blink);
  /* The SAME frame object when nothing is live, so PatternChart's memo skips the redraw. */
  const shown = useMemo(() => ggwLiveFrame(f, live, { emaTip: GGW_LIVE_EMA_TIP }), [f, live]);
  /* 2026-11-16 (ggcard3): no stored bars and SERVED words → the words in place of an empty chart. */
  const empty = f.tile.bars.length === 0 && f.empty_text ? f.empty_text : null;
  return (
    <figure className="ggw-frame" data-tf={f.tf} data-testid={`ggw-frame-${f.tile.symbol}-${f.tf}`} style={style}
            data-empty={empty ? '1' : undefined}>
      <div className="ggw-chartbox" ref={box}>
        {empty ? (
          <p className="ggw-line ggw-frame-empty" data-testid={`ggw-frame-empty-${f.tile.symbol}-${f.tf}`}>{empty}</p>
        ) : (
          <PatternChart tile={shown.tile} chartOnly emaStyle="bold" axis={shown.axis}
                        viewW={fit && fitH ? fitH.w : undefined}
                        height={fit && fitH ? fitH.h : ggwChartHeight(f.tf, phone)} />
        )}
      </div>
      <figcaption className="ggw-cap">
        {/* 🔀 the served 9/21 EMA cross blinker of THIS frame — the dot first, then its served sentence as one chip; the
            chart box itself carries no dot (C9: the svg's top-right holds the price axis). */}
        <EmaBlinkDot block={f.ema_blink} testid={`ggw-ema-blink-dot-${f.tile.symbol}-${f.tf}`} />
        <span className="ggw-cap-label">{f.uptrend ? `${f.label} · ${f.uptrend.short}` : f.label}</span>
        {f.held ? <span className="ggw-chip ggw-held" data-testid="ggw-held">{f.held.text}</span> : null}
        {/* 📶 the served base-count line of the 5-min frame (the ONE engine's card line), verbatim; hover = served title */}
        {f.run_bases ? (
          <span className="ggw-chip ggw-bases" data-testid="ggw-bases" title={f.run_bases.title || undefined}>
            {f.run_bases.text}
          </span>
        ) : null}
        {blink ? (
          <span className="ggw-chip ema-blink-chip" data-testid={`ggw-ema-blink-${f.tile.symbol}-${f.tf}`}
                title={blink.title || undefined}>
            {blink.text}
          </span>
        ) : null}
        {/* 2026-11-16 (ggcard3 C3): THIS frame's own served stamp (its source doc), the head chip's exact look; a Watch
            frame carries no `as_of_et` → no chip. */}
        {f.as_of_et != null ? (
          <span className={`ggw-chip ggw-asof${f.stale ? ' ggw-warn' : ''}`} data-testid={`ggw-frame-asof-${f.tile.symbol}-${f.tf}`}>
            {f.stale ? '⚠️ ' : ''}{f.as_of_et}
          </span>
        ) : null}
      </figcaption>
    </figure>
  );
}

export function Tile({ row, phone, fit, removeLabel, focused, onRemove, busy, onStretch, onUnstretch, offPage, onPrev, onNext, live, order, siNote,
  stack, extra, tags }: {
  row: GgwRow; phone: boolean; fit: boolean; removeLabel: string | null; focused: boolean; busy: boolean;
  /** This row's forming bars per frame — the caller passes them only when the tile is shown and ggwRowLive(row). */
  live?: GgwLiveSym;
  /** ✕ removes this name (the Watch). ABSENT → no ✕ at all (a 🚩 / 🧪 card tile). */
  onRemove?: (sym: string) => void;
  /** On the board: ⤢ opens this tile full screen. */
  onStretch?: (sym: string) => void;
  /** In the full-screen view: ⤡ goes back (and ✕ is not offered there — no remove one click from closing). */
  onUnstretch?: () => void;
  /** Not on the current page: kept mounted (its charts keep their bars) but not shown. */
  offPage?: boolean;
  /** In the full-screen view: ◀ ▶ step to the previous / next stock of HIS list. */
  onPrev?: () => void;
  onNext?: () => void;
  /** The full-screen frame order (absent → GGW_STRETCH_ORDER, the Watch's 5 / 3 / 1). */
  order?: ReadonlyArray<string>;
  /** 🩳 2026-11-18: mount the served EXTREME short-interest note in the head (the Watch only; absent → today's DOM). */
  siNote?: boolean;
  /** 2026-11-18: a board tile with its frames stacked in `order` (the 🚩 / 🧪 card grid); absent → the Watch's split. */
  stack?: boolean;
  /** 2026-11-18: caller content drawn right after SYM (the card grid's own head); absent → nothing. */
  extra?: ReactNode;
  /** 🏷️ 2026-11-18: the Watch's tags row above the head (the Watch only; the 🚩 / 🧪 card grid and GgCardView never
   *  pass it → their DOM is byte-identical). */
  tags?: GgwTagsCtx;
}) {
  const { top, pair } = ggwSplitFrames(row.frames);
  const stacked = !onUnstretch && !!stack;
  /* 🤖 2026-11-17: an auto-added row's × carries its served title (removed until tomorrow); his rows keep `rm`. */
  const rm = row.auto?.remove_title ?? (removeLabel ? `${removeLabel} ${row.symbol}` : row.symbol);
  const autoTitle = row.auto
    ? [row.auto.added_text, row.auto.volume_text, row.auto.leaving_text].filter(Boolean).join(' · ') || undefined
    : undefined;
  return (
    <section className={`ggw-tile${focused ? ' ggw-tile-focus' : ''}`} id={onUnstretch ? undefined : `ggw-${row.symbol}`}
             data-testid={onUnstretch ? `ggw-stretch-tile-${row.symbol}` : `ggw-tile-${row.symbol}`} data-state={row.state}
             hidden={offPage || undefined}>
      {tags ? <GgwTagsRow row={row} room={tags.room} study={tags.study} /> : null}
      <div className="ggw-tile-head">
        <b className="ggw-sym">{row.symbol}</b>
        {extra ?? null}
        {/* 🎯 the served A+ chip (spec ggwaplus 2026-11-17) — its text verbatim, hover = the served title. No block → no chip. */}
        {row.aplus ? (
          <span className="ggw-chip ggw-aplus" data-testid="ggw-aplus" title={row.aplus.title ?? undefined}>
            {row.aplus.text}
          </span>
        ) : null}
        {/* 🤖 the served auto chip (watch-auto 2026-11-17) — its text verbatim; hover = the served added / volume /
            leaving words. A row without `auto` (his, a 🚩 card) draws nothing here. */}
        {row.auto ? (
          <span className="ggw-chip ggw-auto" data-testid="ggw-auto" title={autoTitle}>{row.auto.text}</span>
        ) : null}
        {/* 🩳 the served EXTREME short-interest note (sinote 2026-11-18) — the served short form verbatim; nothing when
            the read is not extreme, stale or missing. */}
        {siNote ? <GgSiExtremeNote symbol={row.symbol} testid={`ggw-si-extreme-${row.symbol}`} /> : null}
        {row.text ? (
          <span className={`ggw-line ggw-row-text${row.stale ? ' ggw-warn' : ''}`} data-testid="ggw-row-text">
            {row.text}
          </span>
        ) : null}
        {row.from_session ? <span className="ggw-chip ggw-from" data-testid="ggw-from">{row.from_session}</span> : null}
        {row.as_of_et ? (
          <span className={`ggw-chip ggw-asof${row.stale ? ' ggw-warn' : ''}`} data-testid="ggw-asof">
            {row.stale ? '⚠️ ' : ''}{row.as_of_et}
          </span>
        ) : null}
        {row.rang.map((r, i) => (
          <span key={`${r.frame}-${r.at_et}-${i}`} className="ggw-chip ggw-rang" data-testid="ggw-rang">{r.text}</span>
        ))}
        <span className="ggw-actions">
          {onStretch ? (
            <button type="button" className="ggw-btn ggw-stretch-btn" title={ggwStretchTitle(row.symbol)}
                    aria-label={ggwStretchTitle(row.symbol)} data-testid={`ggw-stretch-btn-${row.symbol}`}
                    onClick={() => onStretch(row.symbol)}>
              {GGW_STRETCH.open}
            </button>
          ) : null}
          <button type="button" className="ggw-btn ggw-yahoo" title={yahooTitle(row.symbol)}
                  aria-label={yahooTitle(row.symbol)} onClick={(e) => openYahoo(e, row.symbol)}>
            {YAHOO_LABEL}
          </button>
          {onPrev ? (
            <button type="button" className="ggw-btn ggw-pager-btn" title={GGW_PAGER.prevTitle}
                    aria-label={GGW_PAGER.prevTitle} data-testid="ggw-stretch-prev" onClick={onPrev}>
              {GGW_PAGER.prev}
            </button>
          ) : null}
          {onNext ? (
            <button type="button" className="ggw-btn ggw-pager-btn" title={GGW_PAGER.nextTitle}
                    aria-label={GGW_PAGER.nextTitle} data-testid="ggw-stretch-next" onClick={onNext}>
              {GGW_PAGER.next}
            </button>
          ) : null}
          {onUnstretch ? (
            <button type="button" className="ggw-btn ggw-unstretch" title={GGW_STRETCH.closeTitle}
                    aria-label={GGW_STRETCH.closeTitle} data-testid="ggw-unstretch" onClick={onUnstretch}>
              {GGW_STRETCH.close}
            </button>
          ) : onRemove ? (
            <button type="button" className="ggw-btn ggw-remove" title={rm} aria-label={rm} disabled={busy}
                    onClick={() => onRemove(row.symbol)}>
              {'✕'}
            </button>
          ) : null}
        </span>
      </div>
      {(onUnstretch || stacked) && row.frames.length ? (
        <div className={`ggw-dark ggw-charts ggw-charts--stretch${stacked ? ' ggw-charts--stack' : ''}`}
             data-testid={stacked ? 'ggw-stack-charts' : 'ggw-stretch-charts'}>
          {ggwStretchFrames(row.frames, order).map((f) => (
            <Frame key={f.tf} f={f} phone={phone} fit={fit}
                   style={fit ? { flexGrow: stacked && f.tile.bars.length === 0 && f.empty_text ? 0 : 1 } : undefined}
                   live={live?.by[f.tf]} />
          ))}
        </div>
      ) : top || pair.length ? (
        <div className="ggw-dark ggw-charts">
          {top ? (
            <Frame f={top} phone={phone} fit={fit} style={fit ? { flexGrow: GGW_FIT_GROW.top } : undefined}
                   live={live?.by[top.tf]} />
          ) : null}
          {pair.length ? (
            <div className="ggw-frame-pair" style={fit ? { flexGrow: GGW_FIT_GROW.pair } : undefined}>
              {pair.map((f) => <Frame key={f.tf} f={f} phone={phone} fit={fit} live={live?.by[f.tf]} />)}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/** ⤢ One tile over the whole window (portal on <body>, so no transformed ancestor clips the fixed layer). Esc, ⤡ or a
 *  click on the dark margin closes it; the page under it does not scroll while it is open. The tile re-renders from
 *  the board's own rows, so the minute GET keeps moving its bars. */
export function GgwStretch({ row, phone, removeLabel, onClose, onStep, live, order, kind, siNote, tags }: {
  row: GgwRow; phone: boolean; removeLabel: string | null; onClose: () => void; onStep: ((d: -1 | 1) => void) | null;
  live?: GgwLiveSym;
  /** The frame order, top to bottom (absent → GGW_STRETCH_ORDER). */
  order?: ReadonlyArray<string>;
  /** Who opened it: 'card' = a 🚩 card; absent → the Watch's root exactly (no modifier class, no data-kind). */
  kind?: 'watch' | 'card';
  /** 🩳 2026-11-18: forwarded to the Tile (the Watch passes it; a 🚩 card does not). */
  siNote?: boolean;
  /** 🏷️ 2026-11-18: forwarded to the Tile (the Watch passes it; a 🚩 card does not). */
  tags?: GgwTagsCtx;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (onStep && e.key === 'ArrowLeft') onStep(-1);
      else if (onStep && e.key === 'ArrowRight') onStep(1);
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev; };
  }, [onClose, onStep]);
  useEffect(() => {
    (document.querySelector('[data-testid="ggw-unstretch"]') as HTMLElement | null)?.focus?.();
  }, []);
  return createPortal(
    <div className={kind ? `ggw-stretch ggw-stretch--${kind}` : 'ggw-stretch'} data-kind={kind}
         role="dialog" aria-modal="true" aria-label={ggwStretchTitle(row.symbol)}
         data-testid="ggw-stretch" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={`ggw-grid ggw-grid--stretch${phone ? '' : ' ggw-grid--fit'}`}>
        <Tile row={row} phone={phone} fit={!phone} removeLabel={removeLabel} focused={false} busy={false}
              onRemove={() => {}} onUnstretch={onClose} live={live} order={order} siNote={siNote} tags={tags}
              onPrev={onStep ? () => onStep(-1) : undefined} onNext={onStep ? () => onStep(1) : undefined} />
      </div>
    </div>,
    document.body,
  );
}
