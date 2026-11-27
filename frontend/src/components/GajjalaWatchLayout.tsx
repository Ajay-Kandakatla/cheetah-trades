/* GajjalaWatchLayout — the 👀 Watch's per-screen pick, pager and fitted-row hook, shared (2026-11-18, cardview spec §3.3,
 * WP-A).
 *
 * A PURE MOVE out of GajjalaWatchBoard.tsx (useFitRows → useGgwFitRows, the "per screen" pick JSX → GgwLayoutPick, the
 * pager JSX → GgwPager) so the 🚩 / 🧪 card grid draws the SAME controls, never a second implementation. Ajay 2026-11-18:
 * "I need the watch list kinda chart formant view video view as default here too from the tabs pages".
 *
 * Additions, every one opt-in (the Watch passes none of them, so its DOM is byte-identical):
 *   - `testidPrefix` on GgwLayoutPick / GgwPager renames every data-testid (absent → the Watch's `ggw-layout` /
 *     `ggw-pager` testids exactly); classes, titles, labels and order never change;
 *   - `onRemove` on GgwPager is optional: ABSENT → no × button at all (a 🚩 card cannot be removed from a board).
 *   - `groups` on GgwPager (🗂 2026-11-22, spec watch_org §3.5 — Ajay: "Manual ones I add them need to be on top then
 *     auto intraday.."): the served section words inline at the first item of each section, items `[🎯?, SYM]`.
 * The FE composes no word about a stock here: the pager titles are the GGW_PAGER control words, the × title is the
 * served remove_title / remove_label, the rest are structural glyphs. docs/gajjala/watch_layout_shared_2026_11_18.md.
 *
 * 👀 2026-11-27 (spec watch5m §3.6, WP tile) — Ajay: "So I can look at 5 mins charts like 6 in one go...". GgwLayoutPick
 * gains opt-in `options` (the picks drawn; absent → GGW_LAYOUT_ORDER), `disabled` (picks drawn greyed, never removed, so
 * the head's width never follows the offer) + `disabledTitle`, and `layout: null` (no pick lit). Absent → the card grid's
 * and the Watch's 1 · 2 · 4 · 9 byte-identical. docs/gajjala/watch_5m_grid_2026_11_27.md. */
import { useEffect, useState, type RefObject } from 'react';
import {
  GGW_LAYOUT_ORDER, GGW_PAGER, ggwFitRowHeight, type GgwLayout, type GgwRowAplus, type GgwRowAuto, type GgwSection,
} from '../lib/gajjalaWatch';

/** The fitted grid row height (px) above the phone break, or null (phone / no layout yet / jsdom). */
export function useGgwFitRows(grid: RefObject<HTMLDivElement>, head: RefObject<HTMLDivElement>,
                              phone: boolean, deps: unknown, rows: number): number | null {
  const [rowH, setRowH] = useState<number | null>(null);
  useEffect(() => {
    if (phone || typeof window === 'undefined') { setRowH(null); return; }
    const measure = () => {
      const g = grid.current;
      if (!g) { setRowH(null); return; }
      const r = g.getBoundingClientRect();
      if (!(r.width > 0)) { setRowH(null); return; }
      const gap = parseFloat(getComputedStyle(g).rowGap) || 0;
      /* 2026-11-16: measured from the BOARD's top, not the page's — the banners above the tabs grew past one screen,
       * so a page-top measure left every row at the floor. With the board scrolled to the top, its head, the pager
       * and `rows` rows fill exactly one window (his "two stocks with 3 charts each at any given moment"). */
      const b = g.closest('.ggw-board');
      const boardTop = b ? b.getBoundingClientRect().top : r.top;
      setRowH(ggwFitRowHeight({ vh: window.innerHeight, top: r.top - boardTop, below: 0, gap }, rows));
    };
    measure();
    window.addEventListener('resize', measure);
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    if (ro && head.current) ro.observe(head.current);
    return () => { window.removeEventListener('resize', measure); ro?.disconnect(); };
  }, [phone, grid, head, deps, rows]);
  return rowH;
}

/** The "1 · 2 · 4 · 9 per screen" pick (the caller guards rows / phone). */
export function GgwLayoutPick<T extends number = GgwLayout>({
  layout, onPick, options, disabled, disabledTitle, testidPrefix = 'ggw-layout',
}: {
  /** The lit pick; null → none lit (2026-11-27: the dense board when the window fits no pick). */
  layout: T | null; onPick: (l: T) => void;
  /** 2026-11-27: the picks drawn, in order; absent → GGW_LAYOUT_ORDER exactly. */
  options?: ReadonlyArray<T>;
  /** 2026-11-27: picks drawn with the `disabled` attribute (greyed, a click does nothing); absent → none. */
  disabled?: ReadonlyArray<T>;
  /** 2026-11-27: appended to a disabled pick's title (`{l} per screen — {disabledTitle}`). */
  disabledTitle?: string;
  /** Renames the testids (`{prefix}`, `{prefix}-{l}`); absent → the Watch's `ggw-layout` exactly. */
  testidPrefix?: string;
}) {
  const picks = options ?? (GGW_LAYOUT_ORDER as ReadonlyArray<number> as ReadonlyArray<T>);
  return (
    <span className="ggw-layout" role="group" aria-label="Charts per screen" data-testid={testidPrefix}>
      {picks.map((l) => {
        const off = !!disabled && disabled.includes(l);
        const title = off && disabledTitle ? `${l} per screen — ${disabledTitle}` : `${l} per screen`;
        return (
          <button key={l} type="button" className={`ggw-btn ggw-layout-btn${l === layout ? ' is-on' : ''}`}
                  aria-pressed={l === layout} title={title} data-testid={`${testidPrefix}-${l}`}
                  disabled={off || undefined}
                  onClick={() => { if (!off) onPick(l); }}>
            {String(l)}
          </button>
        );
      })}
      <span className="ggw-layout-label">per screen</span>
    </span>
  );
}

/** ◀ the tickers (each a toggle, × = remove when `onRemove` is given) ▶ and the "page / pages" stamp. */
export function GgwPager({
  rows, onPage, paged, cur, pages, usePick, busy, removeLabel, onToggle, onPrev, onNext, onRemove, testidPrefix = 'ggw-pager',
  groups,
}: {
  rows: ReadonlyArray<{ symbol: string; aplus?: GgwRowAplus | null; auto?: GgwRowAuto | null }>;
  /** Is row i on screen now (the page, or his toggled pick). */
  onPage: (i: number) => boolean;
  paged: boolean; cur: number; pages: number; usePick: boolean; busy: boolean; removeLabel: string | null;
  onToggle: (sym: string) => void; onPrev: () => void; onNext: () => void;
  /** The Watch's × (DELETE). ABSENT → no × button at all (a 🚩 card cannot be removed from a board). */
  onRemove?: (sym: string) => void;
  /** Renames the testids (`{prefix}`, `-prev`, `-next`, `-{sym}`, `-x-{sym}`, `-at`); absent → `ggw-pager` exactly. */
  testidPrefix?: string;
  /** 🗂 2026-11-22 (spec watch_org §3.5): the served section labels, drawn INLINE before the row index they start at
   *  (lib ggwGroupStarts); the items then read `[🎯?, SYM]` (the dashed outline already says 🤖). ABSENT → today's
   *  pager exactly (the 🚩 / 🧪 card grid passes it only for a served 🚫 section, 2026-11-25). */
  groups?: ReadonlyArray<{ at: number; section: GgwSection }>;
}) {
  const startAt = groups ? new Map(groups.map((g) => [g.at, g.section] as const)) : null;
  return (
    <nav className="ggw-pager" aria-label="Move the view" data-testid={testidPrefix}>
      <button type="button" className="ggw-btn ggw-pager-btn" title={GGW_PAGER.prevTitle} aria-label={GGW_PAGER.prevTitle}
              data-testid={`${testidPrefix}-prev`} disabled={!paged || (!usePick && cur <= 0)}
              onClick={onPrev}>
        {GGW_PAGER.prev}
      </button>
      {rows.map((r, i) => {
        /* 🤖 an auto name: the dashed item, the served tag before SYM, the served × title. */
        const rm = r.auto?.remove_title ?? (removeLabel ? `${removeLabel} ${r.symbol}` : r.symbol);
        const sec = startAt ? startAt.get(i) ?? null : null;
        const label = startAt ? [r.aplus?.tag, r.symbol] : [r.aplus?.tag, r.auto?.tag, r.symbol];
        const item = (
          <span key={r.symbol} className={`ggw-pager-item${r.auto ? ' ggw-pager-item--auto' : ''}${onPage(i) ? ' is-on' : ''}`}>
            {/* 🎯 a name a Gajjala board reads A+ this session: the served tag first + the --aplus outline. */}
            <button type="button"
                    className={`ggw-btn ggw-pager-sym${r.aplus ? ' ggw-pager-sym--aplus' : ''}${onPage(i) ? ' is-on' : ''}`}
                    aria-pressed={onPage(i)} data-testid={`${testidPrefix}-${r.symbol}`}
                    title={r.aplus?.title ?? undefined}
                    onClick={() => onToggle(r.symbol)}>
              {label.filter(Boolean).join(' ')}
            </button>
            {onRemove ? (
              <button type="button" className="ggw-btn ggw-pager-x" title={rm} aria-label={rm} disabled={busy}
                      data-testid={`${testidPrefix}-x-${r.symbol}`} onClick={() => onRemove(r.symbol)}>
                {'×'}
              </button>
            ) : null}
          </span>
        );
        if (!sec) return item;
        return [
          <span key={`grp-${sec.key}`} className={`ggw-pager-group${i === 0 ? ' ggw-pager-group--first' : ''}`}
                data-testid={`${testidPrefix}-group-${sec.key}`} title={sec.hint ?? undefined}>{sec.text}</span>,
          item,
        ];
      })}
      <button type="button" className="ggw-btn ggw-pager-btn" title={GGW_PAGER.nextTitle} aria-label={GGW_PAGER.nextTitle}
              data-testid={`${testidPrefix}-next`} disabled={!paged || (!usePick && cur >= pages - 1)}
              onClick={onNext}>
        {GGW_PAGER.next}
      </button>
      {paged && !usePick ? <span className="ggw-pager-at" data-testid={`${testidPrefix}-at`}>{`${cur + 1} / ${pages}`}</span> : null}
    </nav>
  );
}
