/* 📅 Runners on one continuous chart — the overlay (2026-11-26, spec runcharts rev 2 §3.7, package fe-chart).
 *
 * Ajay 2026-11-26: "I want you to have continous charts for previous day runners we have some examples with traderview
 * charts with couple of indicators can you set that up? I wanna able to horizontal scroll tp check continuity like he does"
 *
 * One lightweight-charts chart of the served sessions over the whole window (portal on <body>, the GgwStretch pattern):
 * candles, volume with its average, the 9 / 21 EMA as served (the cards' engine, never restarted at a session), the
 * served pre-market / after-hours shading and dated session lines (sessionsPrimitive.ts). Drag / wheel / pinch move and
 * zoom; ← → pan; ◀ day / day ▶ jump a session; ‹ › step the strip's names. Every number and every word is the
 * server's; the arithmetic lives in lib/ggRunChart.ts. This file is wiring: the fetch (held back briefly on a ‹ › step, a
 * `busy` answer re-asked), the refresh while visible, the chart's lifecycle (ZoneChart.tsx is the template), focus and
 * keys. Display only — nothing here rings, gates, sorts or adds a name. UNMEASURED. */
import '../styles/ggRunChart.css';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ColorType, CrosshairMode, createChart,
  type CandlestickData, type HistogramData, type IChartApi, type ISeriesApi, type LineData,
  type Logical, type MouseEventParams, type Time,
} from 'lightweight-charts';
import { API } from '../lib/apiBase';
import { EMA_BOLD, EMA_LINE_W } from '../lib/chartMaps';
import { VOLUME_SMA_COLOR } from '../lib/volumePane';
import {
  GGRC_CTRL, GGRC_DEBOUNCE_MS, GGRC_DOWN, GGRC_FETCH_FAILED, GGRC_LOADING, GGRC_MIN_BAR_SPACING,
  GGRC_SHADE, GGRC_TEXT, GGRC_UP, GGRC_VWAP_COLOR,
  ggrcBusyDelayMs, ggrcCandles, ggrcHover, ggrcInitialRange, ggrcKeepRange, ggrcLine, ggrcOpenTitle, ggrcPan, ggrcPath,
  ggrcPrecision, ggrcStepSession, ggrcVolAvg, ggrcVolume, ggrcVwapSegments, parseGgrc,
  type GgrcPayload, type GgrcPoint, type GgrcRange,
} from '../lib/ggRunChart';
import { SessionsPrimitive } from './sessionsPrimitive';
import { usePhone } from './GajjalaWatchTile';

type Load =
  | { key: string; kind: 'ok'; p: GgrcPayload }
  | { key: string; kind: 'text'; text: string; retry: boolean }
  | { key: string; kind: 'busy'; text: string; retry: boolean }
  | { key: string; kind: 'failed' };

type Series = {
  candles: ISeriesApi<'Candlestick', Time>;
  vol: ISeriesApi<'Histogram', Time>;
  avg: ISeriesApi<'Line', Time>;
  ema9: ISeriesApi<'Line', Time>;
  ema21: ISeriesApi<'Line', Time>;
  vwap: ISeriesApi<'Line', Time>[];
  prim: SessionsPrimitive;
};

const BORDER = 'rgba(148,163,184,0.2)';          // = ZoneChart's border
const GRID = 'rgba(148,163,184,0.07)';           // = ZoneChart's grid
const FOCUSABLE = 'button:not([disabled]), summary, a[href], input:not([disabled]), select:not([disabled]), '
  + 'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const LINE_FLAGS = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false } as const;

const lw = <T extends GgrcPoint>(pts: T[]) => pts as unknown as LineData<Time>[];

/** An arrow typed in a field belongs to the field. */
function editable(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  const tag = t.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable;
}

/** The served answer → what the overlay shows for a FIRST read (a re-read that is not `ok` keeps the chart). */
function loadOf(key: string, p: GgrcPayload | null): Load {
  if (!p || p.state === 'owner_only' || p.state === 'off' || p.state === 'busy') return { key, kind: 'failed' };
  if (p.state === 'ok') return { key, kind: 'ok', p };
  if (p.state === 'error') return { key, kind: 'text', text: p.text ?? GGRC_FETCH_FAILED, retry: true };
  return { key, kind: 'text', text: p.text ?? GGRC_FETCH_FAILED, retry: false };
}

export default function GgRunChart({ symbol, list, onClose, onStep }: {
  symbol: string; list?: ReadonlyArray<string>; onClose: () => void; onStep: ((d: -1 | 1) => void) | null;
}) {
  const phone = usePhone();
  const [tf, setTf] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [load, setLoad] = useState<Load | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  const key = `${symbol}|${tf ?? ''}`;
  const shown = load && load.key === key && load.kind === 'ok' ? load.p : null;
  const chartKey = shown ? key : null;

  const dlgRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const elRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const sRef = useRef<Series | null>(null);
  const lenRef = useRef<number | null>(null);
  const idxRef = useRef<Map<number, number>>(new Map());
  const loadRef = useRef<Load | null>(null);
  const framesRef = useRef<{ key: string; label: string }[]>([]);
  const seq = useRef(0);
  const prevSym = useRef<string | null>(null);
  const prevKey = useRef<string | null>(null);
  const tries = useRef(0);
  const busyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const phoneRef = useRef(phone);
  phoneRef.current = phone;

  const put = (l: Load) => {
    loadRef.current = l;
    if (l.kind === 'ok' && l.p.frames.length) framesRef.current = l.p.frames;
    setLoad(l);
  };

  /* ── fetch: deps EXACTLY [symbol, tf, tick]; newest wins; a ‹ › step waits GGRC_DEBOUNCE_MS ── */
  useEffect(() => {
    const k = `${symbol}|${tf ?? ''}`;
    if (prevKey.current !== k) tries.current = 0;
    prevKey.current = k;
    const delay = prevSym.current !== null && prevSym.current !== symbol ? GGRC_DEBOUNCE_MS : 0;
    prevSym.current = symbol;
    const my = ++seq.current;
    const ctrl = new AbortController();
    const live = () => my === seq.current && !ctrl.signal.aborted;
    const okOnScreen = () => {
      const l = loadRef.current;
      return !!l && l.key === k && l.kind === 'ok';
    };
    const run = () => {
      fetch(`${API}${ggrcPath(symbol, tf)}`, { credentials: 'include', cache: 'no-store', signal: ctrl.signal })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((j: unknown) => {
          if (!live()) return;
          const p = parseGgrc(j);
          if (p && p.state === 'busy') {
            if (okOnScreen()) return;                     // a re-read: the chart stays; the next refresh tick asks
            tries.current += 1;
            const ms = ggrcBusyDelayMs(p, tries.current);
            put({ key: k, kind: 'busy', text: p.text ?? GGRC_LOADING, retry: ms === null });
            if (ms !== null) {
              busyTimer.current = setTimeout(() => { busyTimer.current = null; setTick((t) => t + 1); }, ms);
            }
            return;
          }
          tries.current = 0;
          if (p && p.state === 'ok') put({ key: k, kind: 'ok', p });
          else if (!okOnScreen()) put(loadOf(k, p));
        })
        .catch(() => {
          if (!live()) return;
          tries.current = 0;
          if (!okOnScreen()) put({ key: k, kind: 'failed' });   // a failed RE-read keeps the chart
        });
    };
    let timer: ReturnType<typeof setTimeout> | null = null;
    if (delay > 0) timer = setTimeout(run, delay);
    else run();
    return () => {
      if (timer) clearTimeout(timer);
      if (busyTimer.current) { clearTimeout(busyTimer.current); busyTimer.current = null; }
      ctrl.abort();
    };
  }, [symbol, tf, tick]);

  /* ── refresh while the market is open, only while the page is visible ── */
  const refresh = shown?.refresh_sec ?? 0;
  useEffect(() => {
    if (!(refresh > 0)) return undefined;
    const id = setInterval(() => {
      if (typeof document === 'undefined' || document.visibilityState === 'visible') setTick((t) => t + 1);
    }, refresh * 1000);
    return () => clearInterval(id);
  }, [refresh]);

  /* ── body scroll lock ── */
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  /* ── focus: ✕ on open, the opener back on close (when it is still in the document) ── */
  useEffect(() => {
    const opener = document.activeElement;
    closeRef.current?.focus();
    return () => {
      if (opener instanceof HTMLElement && opener !== document.body && document.contains(opener)) opener.focus();
    };
  }, []);

  /* ── keys: ONE window listener, capture phase; nothing under the overlay sees what it handles ── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        if (editable(e.target)) return;
        e.stopPropagation();
        e.preventDefault();
        const ts = chartRef.current?.timeScale();
        const r = ts?.getVisibleLogicalRange();
        if (ts && r) {
          const next = ggrcPan({ from: r.from, to: r.to }, e.key === 'ArrowLeft' ? -1 : 1);
          ts.setVisibleLogicalRange({ from: next.from as Logical, to: next.to as Logical });
        }
        return;
      }
      if (e.key === 'Tab') {
        const root = dlgRef.current;
        if (!root) return;
        const f = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        const active = document.activeElement;
        const outside = !active || !root.contains(active);
        const target = e.shiftKey
          ? (active === first || outside ? last : null)
          : (active === last || outside ? first : null);
        if (target) {
          e.stopPropagation();
          e.preventDefault();
          target.focus();
        }
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, []);

  /* ── the chart: created once per symbol:tf, torn down on change / unmount ── */
  useEffect(() => {
    const el = elRef.current;
    if (!chartKey || !el) return undefined;
    const chart = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: GGRC_TEXT, fontSize: 11 },
      grid: { vertLines: { color: GRID }, horzLines: { color: GRID } },
      rightPriceScale: { borderColor: BORDER, scaleMargins: { top: 0.06, bottom: 0.24 } },
      timeScale: { borderColor: BORDER, timeVisible: true, secondsVisible: false, minBarSpacing: GGRC_MIN_BAR_SPACING },
      crosshair: { mode: CrosshairMode.Normal },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });
    const candles = chart.addCandlestickSeries({
      upColor: GGRC_UP, downColor: GGRC_DOWN, borderVisible: false, wickUpColor: GGRC_UP, wickDownColor: GGRC_DOWN,
      priceLineVisible: false,
    });
    const vol = chart.addHistogramSeries({
      priceScaleId: '', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false,
    });
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    const avg = chart.addLineSeries({ priceScaleId: '', color: VOLUME_SMA_COLOR, lineWidth: 1, ...LINE_FLAGS });
    const ema9 = chart.addLineSeries({ color: EMA_BOLD.ema9.color, lineWidth: EMA_LINE_W, ...LINE_FLAGS });
    const ema21 = chart.addLineSeries({ color: EMA_BOLD.ema21.color, lineWidth: EMA_LINE_W, ...LINE_FLAGS });
    const prim = new SessionsPrimitive();
    candles.attachPrimitive(prim);
    chartRef.current = chart;
    sRef.current = { candles, vol, avg, ema9, ema21, vwap: [], prim };
    lenRef.current = null;

    const onMove = (param: MouseEventParams<Time>) => {
      const t = param.time as number | undefined;
      const i = typeof t === 'number' ? idxRef.current.get(t) : undefined;
      setHover(i === undefined ? null : i);
    };
    chart.subscribeCrosshairMove(onMove);
    const ro = typeof ResizeObserver === 'function'
      ? new ResizeObserver(() => { chart.applyOptions({ width: el.clientWidth, height: el.clientHeight }); })
      : null;
    ro?.observe(el);

    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      ro?.disconnect();
      chart.remove();
      chartRef.current = null;
      sRef.current = null;
      lenRef.current = null;
      setHover(null);
    };
  }, [chartKey]);

  /* ── data: first data of a symbol:tf → the initial range; a refresh → setData on the SAME series + his range kept ── */
  useEffect(() => {
    const s = sRef.current, chart = chartRef.current;
    if (!shown || !s || !chart) return;
    const ts = chart.timeScale();
    const before = lenRef.current === null ? null : ts.getVisibleLogicalRange();
    const last = shown.bars.length ? shown.bars[shown.bars.length - 1].c : null;
    s.candles.applyOptions({ priceFormat: { type: 'price', ...ggrcPrecision(last) } });
    s.candles.setData(ggrcCandles(shown) as unknown as CandlestickData<Time>[]);
    s.vol.setData(ggrcVolume(shown) as unknown as HistogramData<Time>[]);
    s.avg.setData(lw(ggrcVolAvg(shown)));
    s.ema9.setData(lw(ggrcLine(shown, 'ema9')));
    s.ema21.setData(lw(ggrcLine(shown, 'ema21')));
    const segs = ggrcVwapSegments(shown);
    while (s.vwap.length > segs.length) chart.removeSeries(s.vwap.pop() as ISeriesApi<'Line', Time>);
    while (s.vwap.length < segs.length) {
      s.vwap.push(chart.addLineSeries({ color: GGRC_VWAP_COLOR, lineWidth: 1, ...LINE_FLAGS }));
    }
    segs.forEach((seg, i) => s.vwap[i].setData(lw(seg)));
    s.prim.setData({ shade: shown.shade, sessions: shown.sessions });
    idxRef.current = new Map(shown.bars.map((b, i) => [b.x, i]));

    if (lenRef.current === null) {
      const r = ggrcInitialRange(shown, phoneRef.current);
      if (r) ts.setVisibleLogicalRange({ from: r.from as Logical, to: r.to as Logical });
      else ts.fitContent();
    } else {
      const k = ggrcKeepRange(before ? { from: before.from, to: before.to } : null, lenRef.current, shown.bars.length);
      if (k) ts.setVisibleLogicalRange({ from: k.from as Logical, to: k.to as Logical });
    }
    lenRef.current = shown.bars.length;
  }, [shown, chartKey]);

  const range = (): GgrcRange | null => {
    const r = chartRef.current?.timeScale().getVisibleLogicalRange();
    return r ? { from: r.from, to: r.to } : null;
  };
  const setRange = (r: GgrcRange) => {
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: r.from as Logical, to: r.to as Logical });
  };
  const stepDay = (d: -1 | 1) => {
    const r = range();
    if (shown && r) setRange(ggrcStepSession(r, shown.sessions, d));
  };
  const latest = () => {
    if (!shown) return;
    const r = ggrcInitialRange(shown, phone);
    if (r) setRange(r);
    else chartRef.current?.timeScale().fitContent();
  };
  const retry = () => { tries.current = 0; setTick((t) => t + 1); };
  const pickTf = (k: string) => {
    if (k === (tf ?? shown?.tf ?? null)) return;
    setTf(k);
  };

  const names = list ?? [];
  const at = names.indexOf(symbol);
  const activeTf = tf ?? shown?.tf ?? null;
  const frames = shown?.frames.length ? shown.frames : framesRef.current;
  const hud = shown ? (ggrcHover(shown, hover ?? -1) ?? ggrcHover(shown, shown.bars.length - 1)) : null;
  const labelOf = (tone: string): string => shown?.curves.find((c) => c.tone === tone)?.label ?? '';
  const drawn = shown ? shown.curves.filter((c) => c.tone !== 'vwap' || ggrcVwapSegments(shown).length > 0) : [];

  let msg: { text: string; retry: boolean } | null = null;
  if (!shown) {
    const cur = load && load.key === key ? load : null;
    if (!cur) msg = { text: GGRC_LOADING, retry: false };
    else if (cur.kind === 'failed') msg = { text: GGRC_FETCH_FAILED, retry: true };
    else if (cur.kind === 'text' || cur.kind === 'busy') msg = { text: cur.text, retry: cur.retry };
  }

  return createPortal(
    <div className="ggrc-backdrop" role="dialog" aria-modal="true" aria-label={shown?.title ?? ggrcOpenTitle(symbol)}
         data-testid="ggrc" ref={dlgRef}>
      <div className="ggrc-head">
        {onStep && (
          <>
            <button type="button" className="ggrc-btn" data-testid="ggrc-prev-sym" disabled={at <= 0}
                    title={at > 0 ? names[at - 1] : undefined} onClick={() => onStep(-1)}>{GGRC_CTRL.prevSym}</button>
            <button type="button" className="ggrc-btn" data-testid="ggrc-next-sym"
                    disabled={at < 0 || at >= names.length - 1}
                    title={at >= 0 && at < names.length - 1 ? names[at + 1] : undefined}
                    onClick={() => onStep(1)}>{GGRC_CTRL.nextSym}</button>
          </>
        )}
        <span className="ggrc-title" data-testid="ggrc-title">{shown?.title ?? symbol}</span>
        {shown?.ran && (
          <span className="ggrc-ran" title={shown.ran.title ?? undefined}>{shown.ran.text}</span>
        )}
        {frames.length > 0 && (
          <span className="ggrc-frames">
            {frames.map((f) => (
              <button key={f.key} type="button" className="ggrc-btn" data-testid={`ggrc-tf-${f.key}`}
                      aria-pressed={activeTf === f.key} onClick={() => pickTf(f.key)}>{f.label}</button>
            ))}
          </span>
        )}
        <button type="button" className="ggrc-btn" data-testid="ggrc-prev-day" disabled={!shown}
                onClick={() => stepDay(-1)}>{GGRC_CTRL.prevDay}</button>
        <button type="button" className="ggrc-btn" data-testid="ggrc-next-day" disabled={!shown}
                onClick={() => stepDay(1)}>{GGRC_CTRL.nextDay}</button>
        <button type="button" className="ggrc-btn" data-testid="ggrc-all" disabled={!shown}
                onClick={() => chartRef.current?.timeScale().fitContent()}>{GGRC_CTRL.all}</button>
        <button type="button" className="ggrc-btn" data-testid="ggrc-latest" disabled={!shown}
                onClick={latest}>{GGRC_CTRL.latest}</button>
        {shown?.hint && (
          <details className="ggrc-hint" data-testid="ggrc-hint">
            <summary className="ggrc-btn">{GGRC_CTRL.hint}</summary>
            <div className="ggrc-hint-body">{shown.hint}</div>
          </details>
        )}
        <button type="button" className="ggrc-btn ggrc-close" data-testid="ggrc-close" ref={closeRef}
                onClick={() => onClose()}>{GGRC_CTRL.close}</button>
      </div>
      {shown && shown.notes.length > 0 && (
        <ul className="ggrc-notes" data-testid="ggrc-notes">
          {shown.notes.map((n, i) => <li key={`${n.kind}-${i}`} data-kind={n.kind}>{n.text}</li>)}
        </ul>
      )}
      {shown?.as_of_text && <div className="ggrc-asof">{shown.as_of_text}</div>}
      {shown && (
        <div className="ggrc-legend" data-testid="ggrc-legend">
          {drawn.map((c) => (
            <span key={c.tone} className="ggrc-key">
              <i className="ggrc-sw" style={{ background: c.tone === 'ema9' ? EMA_BOLD.ema9.color
                : c.tone === 'ema21' ? EMA_BOLD.ema21.color : GGRC_VWAP_COLOR }} />{c.label}
            </span>
          ))}
          {shown.vol_avg && (
            <span className="ggrc-key"><i className="ggrc-sw" style={{ background: VOLUME_SMA_COLOR }} />
              {shown.vol_avg.label}</span>
          )}
          {(shown.words.pre || shown.words.ah) && (
            <span className="ggrc-key"><i className="ggrc-sw" style={{ background: GGRC_SHADE }} />
              {[shown.words.pre, shown.words.ah].filter(Boolean).join(' / ')}</span>
          )}
        </div>
      )}
      {shown && (
        <div className="ggrc-hud" data-testid="ggrc-hud">
          {hud && (
            <>
              <span>{hud.when}</span>
              {hud.session && <span>{hud.session}</span>}
              <span>O {hud.open}</span><span>H {hud.high}</span><span>L {hud.low}</span>
              <span className={hud.up ? 'ggrc-up' : 'ggrc-down'}>C {hud.close}{hud.changePct ? ` ${hud.changePct}` : ''}</span>
              <span>V {hud.volume}</span>
              {hud.ema9 && <span style={{ color: EMA_BOLD.ema9.color }}>{labelOf('ema9')} {hud.ema9}</span>}
              {hud.ema21 && <span style={{ color: EMA_BOLD.ema21.color }}>{labelOf('ema21')} {hud.ema21}</span>}
              {hud.vwap && <span style={{ color: GGRC_VWAP_COLOR }}>{labelOf('vwap')} {hud.vwap}</span>}
            </>
          )}
        </div>
      )}
      {shown ? (
        <div ref={elRef} className="ggrc-canvas" data-testid="ggrc-canvas" />
      ) : (
        <div className="ggrc-msg" role="status" data-testid="ggrc-msg">
          <span>{msg?.text ?? GGRC_LOADING}</span>
          {msg?.retry && (
            <button type="button" className="ggrc-btn" data-testid="ggrc-retry" onClick={retry}>{GGRC_CTRL.retry}</button>
          )}
        </div>
      )}
    </div>,
    document.body,
  );
}
