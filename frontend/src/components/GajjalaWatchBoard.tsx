/* GajjalaWatchBoard — 👀 Gajjala's Watch tab on Chart Maps (2026-11-15, gajjala-watch spec §3.8, WP-C).
 *
 * Ajay 2026-11-15: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove
 * tickers from the dashboard. When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear
 * distinction or may be a brighter and thicker 21 EMA and 9 EMA, from the videos I notice that when ever 9 EMA crosses
 * over 21 EMA on uptrend is where the bullish momentum started I need alerts on these from 1 min to I can be ready... I
 * think the cross over is slow but once it picks up its very rapid.." · "I have a 27 inch monitor I wanna fit 3x3 tikers
 * on watch at any given time on this tashboard" · "Any chart I view make sure you are showing me from 4 AM for
 * historical behaviour and also the right side with gaps to see where it might go".
 *
 * ONE owner-only GET (GET /chart-maps/gajjala-watch, backend chart_maps/gajjala_watch/api.py). `owner_only` → the
 * served reason only. Otherwise: the head (served title · the add box · the served pass line · the 9 / 21 legend · one
 * collapsed ℹ️ with the served honesty, K5 rule and push sentence — printed ONCE) and a 3-column grid of tiles in HIS
 * order (the server never reorders). Each tile: SYM, the served row text / session stamp / as-of, the 🔔 rang chips,
 * one Yahoo ↗, ✕ (DELETE, no confirm); the replay's dark panel with the 1-min chart full width on top and the 3-min +
 * 5-min side by side below — PatternChart chartOnly (no SEPA link), emaStyle bold, the served 04:00 axis.
 *
 * Cadence (spec C4.5 / C2.4 / C2.7): one setTimeout chain re-GETs the board at the served refresh_sec while the page is
 * visible; out of window, ONE re-GET at the served next_window_sec; while a row is pending, the pending names only
 * (?symbols=) every pending_poll_sec up to pending_wait_max_sec; one full re-GET after an add or a remove. No
 * useCardLive, no live-card poll: the minute GET moves the bars.
 *
 * The FE composes NO word about a stock: every visible string is served, except GGW_FETCH_FAILED (no payload to serve
 * one) and structural glyphs (⚠️ on a served stale flag, ✕, ℹ️, "·"). UNMEASURED — a cross is information, not an
 * entry.
 *
 * No house chips on this tab (🚀 growth, 🧨 explosive, 🩳 short interest, 🎯 enterable): each tile is the chart alone, his
 * words "Not the SEPA" (spec §3.8) — the chips live on every other Chart Maps board. No 🧨 ordering toggle either: his
 * list order orders this board (the order he added the names in, as served). */
import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent, type RefObject } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { EMA_BOLD } from '../lib/chartMaps';
import {
  GGW_FETCH_FAILED, GGW_FIT_GROW, GGW_FOCUS_PARAM, GGW_PATH, GGW_PHONE_MQ, ggwChartHeight, ggwFitRowHeight,
  ggwFitViewBoxH, ggwMergeRows, ggwPendingSymbols, ggwRowsPath, ggwSplitFrames, ggwSymbolPath, parseGgw,
  type GgwBoard, type GgwFrame, type GgwPayload, type GgwRow, type GgwWriteAnswer,
} from '../lib/gajjalaWatch';
import { openYahoo, yahooTitle, YAHOO_LABEL } from '../lib/yahooLink';
import { PATTERN_CHART_VIEW_W, PatternChart } from './PatternChart';
import '../styles/gajjalaWatch.css';

type Load = { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: GgwPayload };

function phoneNow(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia(GGW_PHONE_MQ).matches;
}

function usePhone(): boolean {
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

const getJson = (path: string) =>
  fetch(`${API}${path}`, { credentials: 'include', cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))));

/** What sits BELOW `el` on the page: every ancestor's bottom padding / border / margin and every later sibling that
 *  is laid out under it. Never the slack of a short page (a min-height:100vh shell would otherwise shrink the rows
 *  on every measure), never a side-by-side sibling. */
function belowOf(el: HTMLElement): number {
  let below = 0;
  let node: HTMLElement | null = el;
  while (node && node.parentElement && node !== document.documentElement) {
    const parent: HTMLElement = node.parentElement;
    const nodeBottom = node.getBoundingClientRect().bottom;
    below += parseFloat(getComputedStyle(node).marginBottom) || 0;
    for (let sib = node.nextElementSibling as HTMLElement | null; sib; sib = sib.nextElementSibling as HTMLElement | null) {
      const cs = getComputedStyle(sib);
      if (cs.display === 'none' || cs.position === 'absolute' || cs.position === 'fixed') continue;
      const r = sib.getBoundingClientRect();
      if (r.height <= 0 || r.top < nodeBottom - 1) continue;
      below += r.height + (parseFloat(cs.marginTop) || 0) + (parseFloat(cs.marginBottom) || 0);
    }
    const pcs = getComputedStyle(parent);
    below += (parseFloat(pcs.paddingBottom) || 0) + (parseFloat(pcs.borderBottomWidth) || 0);
    node = parent;
  }
  return below;
}

/** The fitted grid row height (px) above the phone break, or null (phone / no layout yet / jsdom). */
function useFitRows(grid: RefObject<HTMLDivElement>, head: RefObject<HTMLDivElement>,
                    phone: boolean, deps: unknown): number | null {
  const [rowH, setRowH] = useState<number | null>(null);
  useEffect(() => {
    if (phone || typeof window === 'undefined') { setRowH(null); return; }
    const measure = () => {
      const g = grid.current;
      if (!g) { setRowH(null); return; }
      const r = g.getBoundingClientRect();
      if (!(r.width > 0)) { setRowH(null); return; }
      const gap = parseFloat(getComputedStyle(g).rowGap) || 0;
      setRowH(ggwFitRowHeight({ vh: window.innerHeight, top: r.top + window.scrollY, below: belowOf(g), gap }));
    };
    measure();
    window.addEventListener('resize', measure);
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    if (ro && head.current) ro.observe(head.current);
    return () => { window.removeEventListener('resize', measure); ro?.disconnect(); };
  }, [phone, grid, head, deps]);
  return rowH;
}

/** In a fitted tile: the viewBox height that fills this chart's measured box (null → the GGW_CHART_H height). */
function useFitBox(box: RefObject<HTMLDivElement>, fit: boolean): number | null {
  const [h, setH] = useState<number | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!fit || !el) { setH(null); return; }
    const measure = () => {
      const r = el.getBoundingClientRect();
      setH(ggwFitViewBoxH(r.width, r.height, PATTERN_CHART_VIEW_W));
    };
    measure();
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    ro?.observe(el);
    return () => ro?.disconnect();
  }, [box, fit]);
  return h;
}

function Frame({ f, phone, fit, style }: { f: GgwFrame; phone: boolean; fit: boolean; style?: CSSProperties }) {
  const box = useRef<HTMLDivElement>(null);
  const fitH = useFitBox(box, fit);
  return (
    <figure className="ggw-frame" data-tf={f.tf} data-testid={`ggw-frame-${f.tile.symbol}-${f.tf}`} style={style}>
      <div className="ggw-chartbox" ref={box}>
        <PatternChart tile={f.tile} chartOnly emaStyle="bold" axis={f.axis}
                      height={fit && fitH ? fitH : ggwChartHeight(f.tf, phone)} />
      </div>
      <figcaption className="ggw-cap">
        <span className="ggw-cap-label">{f.uptrend ? `${f.label} · ${f.uptrend.short}` : f.label}</span>
        {f.held ? <span className="ggw-chip ggw-held" data-testid="ggw-held">{f.held.text}</span> : null}
      </figcaption>
    </figure>
  );
}

function Tile({ row, phone, fit, removeLabel, focused, onRemove, busy }: {
  row: GgwRow; phone: boolean; fit: boolean; removeLabel: string | null; focused: boolean; busy: boolean;
  onRemove: (sym: string) => void;
}) {
  const { top, pair } = ggwSplitFrames(row.frames);
  const rm = removeLabel ? `${removeLabel} ${row.symbol}` : row.symbol;
  return (
    <section className={`ggw-tile${focused ? ' ggw-tile-focus' : ''}`} id={`ggw-${row.symbol}`}
             data-testid={`ggw-tile-${row.symbol}`} data-state={row.state}>
      <div className="ggw-tile-head">
        <b className="ggw-sym">{row.symbol}</b>
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
          <button type="button" className="ggw-btn ggw-yahoo" title={yahooTitle(row.symbol)}
                  aria-label={yahooTitle(row.symbol)} onClick={(e) => openYahoo(e, row.symbol)}>
            {YAHOO_LABEL}
          </button>
          <button type="button" className="ggw-btn ggw-remove" title={rm} aria-label={rm} disabled={busy}
                  onClick={() => onRemove(row.symbol)}>
            {'✕'}
          </button>
        </span>
      </div>
      {top || pair.length ? (
        <div className="ggw-dark ggw-charts">
          {top ? <Frame f={top} phone={phone} fit={fit} style={fit ? { flexGrow: GGW_FIT_GROW.top } : undefined} /> : null}
          {pair.length ? (
            <div className="ggw-frame-pair" style={fit ? { flexGrow: GGW_FIT_GROW.pair } : undefined}>
              {pair.map((f) => <Frame key={f.tf} f={f} phone={phone} fit={fit} />)}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default function GajjalaWatchBoard() {
  const [params] = useSearchParams();
  const focus = (params.get(GGW_FOCUS_PARAM) || '').trim().toUpperCase() || null;
  const phone = usePhone();
  const [load, setLoad] = useState<Load>({ phase: 'loading' });
  const [refreshFailed, setRefreshFailed] = useState(false);
  /** A served `state: "error"` reason while a board is already up — printed verbatim in the head. */
  const [servedErr, setServedErr] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [outlined, setOutlined] = useState<string | null>(null);

  const alive = useRef(true);
  const board = useRef<GgwBoard | null>(null);
  const mainTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendSince = useRef<Map<string, number>>(new Map());
  const focusDone = useRef(false);
  const loadAllRef = useRef<() => void>(() => {});
  const gridRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const rowH = useFitRows(gridRef, headRef, phone, load);
  const fit = rowH != null;

  const clearMain = () => { if (mainTimer.current) { clearTimeout(mainTimer.current); mainTimer.current = null; } };
  const clearPend = () => { if (pendTimer.current) { clearTimeout(pendTimer.current); pendTimer.current = null; } };

  /* The pending poll: the names still waiting for their first read, each for at most pending_wait_max_sec. */
  const armPending = useCallback((b: GgwBoard) => {
    const now = Date.now();
    const pend = ggwPendingSymbols(b);
    for (const s of Array.from(pendSince.current.keys())) if (!pend.includes(s)) pendSince.current.delete(s);
    for (const s of pend) if (!pendSince.current.has(s)) pendSince.current.set(s, now);
    const poll = b.pending_poll_sec ?? 0;
    const max = b.pending_wait_max_sec ?? 0;
    const due = pend.filter((s) => now - (pendSince.current.get(s) ?? now) < max * 1000);
    clearPend();
    if (!due.length || poll <= 0 || max <= 0) return;
    pendTimer.current = setTimeout(() => {
      pendTimer.current = null;
      getJson(ggwRowsPath(due))
        .then((raw) => {
          if (!alive.current) return;
          const part = parseGgw(raw);
          const cur = board.current;
          if (!cur || !part || part.state !== 'ok') return;
          const next = ggwMergeRows(cur, part);
          board.current = next;
          setLoad({ phase: 'loaded', p: next });
          armPending(next);
        })
        .catch(() => { if (alive.current && board.current) armPending(board.current); });
    }, poll * 1000);
  }, []);

  /* The main chain: the served refresh_sec while visible; out of window ONE re-GET at next_window_sec. */
  const armMain = useCallback((b: GgwBoard) => {
    clearMain();
    if (b.refresh_sec > 0) {
      const tick = () => {
        mainTimer.current = null;
        if (typeof document !== 'undefined' && document.hidden) {
          mainTimer.current = setTimeout(tick, b.refresh_sec * 1000);
          return;
        }
        loadAllRef.current();
      };
      mainTimer.current = setTimeout(tick, b.refresh_sec * 1000);
    } else if (b.next_window_sec != null && b.next_window_sec > 0) {
      mainTimer.current = setTimeout(() => { mainTimer.current = null; loadAllRef.current(); }, b.next_window_sec * 1000);
    }
  }, []);

  const loadAll = useCallback(() => {
    getJson(GGW_PATH)
      .then((raw) => {
        if (!alive.current) return;
        const p = parseGgw(raw);
        if (!p) throw new Error('junk');
        if (p.state === 'error' && board.current) {
          /* The server said why it could not build the board: keep the board up, print ITS words, keep the chain. */
          setServedErr(p.reason);
          setRefreshFailed(!p.reason);
          armMain(board.current);
          return;
        }
        setRefreshFailed(false);
        setServedErr(null);
        if (p.state === 'ok') {
          board.current = p;
          armMain(p);
          armPending(p);
        } else {
          board.current = null;
          clearMain();
          clearPend();
        }
        setLoad({ phase: 'loaded', p });
      })
      .catch(() => {
        if (!alive.current) return;
        if (board.current) {
          setRefreshFailed(true);
          armMain(board.current);
        } else {
          setLoad((l) => (l.phase === 'loaded' ? l : { phase: 'failed' }));
        }
      });
  }, [armMain, armPending]);
  loadAllRef.current = loadAll;

  useEffect(() => {
    alive.current = true;
    loadAll();
    return () => { alive.current = false; clearMain(); clearPend(); };
  }, [loadAll]);

  /* ?focus=SYM (a push deep link): scroll that tile into view and outline it, once. */
  useEffect(() => {
    if (focusDone.current || !focus || load.phase !== 'loaded' || load.p.state !== 'ok') return;
    if (!load.p.rows.some((r) => r.symbol === focus)) return;
    focusDone.current = true;
    setOutlined(focus);
    const el = typeof document !== 'undefined' ? document.getElementById(`ggw-${focus}`) : null;
    el?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
  }, [focus, load]);

  const write = (method: 'POST' | 'DELETE', sym: string) => {
    setBusy(true);
    fetch(`${API}${ggwSymbolPath(sym)}`, { method, credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((a: GgwWriteAnswer | null) => {
        if (!alive.current) return;
        setMsg(a && typeof a.text === 'string' && a.text.trim() ? a.text : null);
        if (method === 'POST' && a && (a.state === 'added' || a.state === 'already')) setDraft('');
      })
      .catch(() => { if (alive.current) setMsg(null); })
      .finally(() => {
        if (!alive.current) return;
        setBusy(false);
        loadAllRef.current();
      });
  };

  const onAdd = (e: FormEvent) => {
    e.preventDefault();
    const sym = draft.trim();
    if (!sym || busy) return;
    write('POST', sym);
  };

  if (load.phase === 'loading') return <div className="ggw-board" aria-busy="true" />;
  if (load.phase === 'failed') {
    return <div className="ggw-board"><p className="ggw-line ggw-warn">{GGW_FETCH_FAILED}</p></div>;
  }
  const p = load.p;
  if (p.state === 'owner_only') {
    return <div className="ggw-board"><p className="ggw-line ggw-owner-only">{p.reason}</p></div>;
  }
  if (p.state === 'error') {
    return (
      <div className="ggw-board">
        <p className="ggw-line ggw-warn ggw-served-error" data-testid="ggw-served-error">{p.reason ?? GGW_FETCH_FAILED}</p>
      </div>
    );
  }

  const addLabel = p.add_label ?? '';
  return (
    <div className="ggw-board" data-testid="ggw-board">
      <div className="ggw-head" ref={headRef}>
        {p.title ? <h2 className="ggw-title">{p.title}</h2> : null}
        <form className="ggw-add" onSubmit={onAdd}>
          <input className="ggw-input" type="text" value={draft} aria-label={addLabel || undefined}
                 placeholder={(p.full ? p.full_text : p.add_placeholder) ?? undefined}
                 title={p.full ? p.full_text ?? undefined : undefined}
                 disabled={p.full || busy} autoCapitalize="characters" autoComplete="off" spellCheck={false}
                 onChange={(e) => setDraft(e.target.value)} />
          <button type="submit" className="ggw-btn ggw-add-btn" disabled={p.full || busy || !draft.trim()}>
            {addLabel}
          </button>
        </form>
        {p.full && p.full_text ? <span className="ggw-line ggw-full" data-testid="ggw-full">{p.full_text}</span> : null}
        {msg ? <span className="ggw-line ggw-msg" data-testid="ggw-msg">{msg}</span> : null}
        {p.pass?.text ? (
          <span className={`ggw-line ggw-pass${p.pass.stale ? ' ggw-warn' : ''}`} data-testid="ggw-pass">
            {p.pass.stale ? '⚠️ ' : ''}{p.pass.text}
          </span>
        ) : null}
        {servedErr ? (
          <span className="ggw-line ggw-warn ggw-served-error" data-testid="ggw-served-error">{`⚠️ ${servedErr}`}</span>
        ) : null}
        {refreshFailed ? <span className="ggw-line ggw-warn">{`⚠️ ${GGW_FETCH_FAILED}`}</span> : null}
        {p.legend.length ? (
          <span className="ggw-legend">
            {p.legend.map((l) => {
              const c = (EMA_BOLD as Record<string, { color: string; width: number }>)[l.tone];
              return (
                <span key={l.tone} className="ggw-legend-item" data-tone={l.tone}>
                  <i className="ggw-swatch" style={c ? { background: c.color, height: c.width } : undefined} />
                  {l.label}
                </span>
              );
            })}
          </span>
        ) : null}
        {p.info && (p.info.honesty || p.info.uptrend_rule || p.info.push_text) ? (
          <details className="ggw-info">
            <summary aria-label="info">{'ℹ️'}</summary>
            {p.info.honesty ? <p className="ggw-line">{p.info.honesty}</p> : null}
            {p.info.uptrend_rule ? <p className="ggw-line">{p.info.uptrend_rule}</p> : null}
            {p.info.push_text ? <p className="ggw-line">{p.info.push_text}</p> : null}
          </details>
        ) : null}
      </div>
      {p.rows.length ? (
        <div className={`ggw-grid${fit ? ' ggw-grid--fit' : ''}`} ref={gridRef}
             style={fit ? ({ '--ggw-row-h': `${rowH}px` } as CSSProperties) : undefined}>
          {p.rows.map((r) => (
            <Tile key={r.symbol} row={r} phone={phone} fit={fit} removeLabel={p.remove_label} busy={busy}
                  focused={outlined === r.symbol} onRemove={(s) => write('DELETE', s)} />
          ))}
        </div>
      ) : (
        p.empty_text ? <p className="ggw-line ggw-empty" data-testid="ggw-empty">{p.empty_text}</p> : null
      )}
    </div>
  );
}
