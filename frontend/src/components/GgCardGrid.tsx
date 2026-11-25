/* GgCardGrid — the 🚩 / 🧪 card grid in the 👀 Watch layout (2026-11-18, spec cardview §3.5, WP-B).
 *
 * Ajay 2026-11-18: "I need the watch list kinda chart formant view video view as default here too from the tabs pages" →
 * his pick "Tab cards as Watch tiles": big tiles, 2 per screen side by side, each with the live 15 / 5 / 1-min stacked
 * charts. The small cards are no longer the default.
 *
 * Three small pieces, every one drawn by the 👀 Watch's OWN parts (never a second chart engine):
 *  - GgCardWatchToggle — the board's (5) row button beside 📺 (FE control words, the 📺 precedent);
 *  - GgCardGridFrame — `!cw.active` → EXACTLY today's `.cm-grid` div (OFF, an empty sub, 🏁 / 📋, a disallowed board);
 *    `cw.active` → the Watch's board shell: the per-screen pick (desktop), the pager (no ×: a card is never removed from
 *    a board) and the Watch grid [C7];
 *  - GgCardTile — the Watch's `Tile`, frames stacked 15 / 5 / 1 (GGC_STRETCH_ORDER), the card's overlay via cw.rowOf,
 *    the card's SEPA page link + ➕ Watch in the head, ⤢ → the board's existing GgCardView.
 * Every sentence about a stock is served; the FE types only the control words of lib/gajjalaCardView.
 * DISPLAY ONLY, UNMEASURED — nothing here rings, gates, sizes, orders or trades. */
import type { CSSProperties, ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { GGC_FRAME_MIN_PX, GGC_STRETCH_ORDER, GGC_WATCH_LABEL, GGC_WATCH_TITLE } from '../lib/gajjalaCardView';
import { ggHref, type GgTile } from '../lib/gajjala';
import { SEPA_LINK_LABEL, sepaLinkTestId, sepaLinkTitle } from '../lib/cardLinks';
import { sanitizeSourceQuery, withSource } from '../lib/navSource';
import type { GgCardWatch } from '../hooks/useGgCardWatch';
import type { GgwSection } from '../lib/gajjalaWatch';
import { Tile } from './GajjalaWatchTile';
import { GgwLayoutPick, GgwPager } from './GajjalaWatchLayout';
import { GgWatchButton } from './GgWatchButton';

/** The toggle beside 📺 in the board's (5) row — the board mounts it only when cw.allowed. */
export function GgCardWatchToggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button type="button" data-testid="gg-card-watch" aria-pressed={on} title={GGC_WATCH_TITLE}
            className={`cm-phase-btn gg-cardwatch-btn${on ? ' cm-phase-on' : ''}`} onClick={onToggle}>
      {GGC_WATCH_LABEL}
    </button>
  );
}

/** The grid wrapper. `!cw.active` → exactly today's div and nothing else; `cw.active` → the Watch's board shell. */
export function GgCardGridFrame({ cw, loading, symbols, children, groups }: {
  cw: GgCardWatch; loading: boolean; symbols: string[]; children: ReactNode;
  /** 🚫 2026-11-25 (spec fidsec): a served section label for the pager ONLY (GgwPager `groups`); absent → today's pager. */
  groups?: ReadonlyArray<{ at: number; section: GgwSection }>;
}) {
  if (!cw.active) {
    return <div className={`cm-grid${loading ? ' cm-grid-stale' : ''}`} aria-busy={loading || undefined}>{children}</div>;
  }
  const style = {
    ...(cw.fit ? { '--ggw-row-h': `${cw.rowH}px` } : {}),
    '--ggc-frame-min': `${GGC_FRAME_MIN_PX}px`,
  } as CSSProperties;
  return (
    <div className="ggw-board gg-cardwatch" data-testid="gg-cardwatch" ref={cw.boardRef}>
      <div className="ggw-head gg-cardwatch-head" ref={cw.headRef}>
        {symbols.length > 0 && !cw.phone
          ? <GgwLayoutPick layout={cw.layout} onPick={cw.setLayout} testidPrefix="ggc-layout" /> : null}
      </div>
      {symbols.length > 1 ? (
        <GgwPager rows={symbols.map((s) => ({ symbol: s }))} onPage={(i) => cw.shown(symbols[i])} paged={cw.paged}
                  cur={cw.page} pages={cw.pages} usePick={cw.usePick} busy={false} removeLabel={null}
                  onToggle={cw.togglePick} onPrev={() => cw.goPage(Math.max(0, cw.page - 1))}
                  onNext={() => cw.goPage(Math.min(cw.pages - 1, cw.page + 1))} testidPrefix="ggc-pager" groups={groups} />
      ) : null}
      <div className={`ggw-grid ggw-grid--cols${cw.grid.cols} gg-cardgrid${cw.fit ? ' ggw-grid--fit' : ''}${loading ? ' cm-grid-stale' : ''}`}
           ref={cw.gridRef} data-testid="gg-cardgrid" data-layout={cw.layout}
           data-pick={cw.usePick && cw.pick ? cw.pick.length : undefined} aria-busy={loading || undefined} style={style}>
        {children}
      </div>
    </div>
  );
}

/** One card's Watch tile: the Watch's own Tile, stacked 15m / 5m / 1m, the card's overlays via rowOf, ⤢ → GgCardView. */
export function GgCardTile({ card, cw, onStretch }: { card: GgTile; cw: GgCardWatch; onStretch: (sym: string) => void }) {
  const row = cw.rowOf(card);
  const location = useLocation();
  /* the board's back-to-tab glue (GajjalaBoard / PatternChart: sanitizeSourceQuery → /chart-maps?…) */
  const carryQ = sanitizeSourceQuery(location.search);
  const backTarget = carryQ ? `/chart-maps?${carryQ}` : '/chart-maps';
  const href = ggHref(card.href);
  const extra = (
    <>
      {href ? (
        <Link to={withSource(href, 'chart-maps', location.search)} state={{ from: backTarget, label: 'Chart Maps' }}
              data-testid={sepaLinkTestId(card.symbol)} title={sepaLinkTitle(card.symbol)}
              aria-label={sepaLinkTitle(card.symbol)} className="ggw-chip gg-cardwatch-sepa">
          {SEPA_LINK_LABEL}
        </Link>
      ) : null}
      <GgWatchButton symbol={card.symbol} />
    </>
  );
  return (
    <Tile row={row} phone={cw.phone} fit={cw.fit} removeLabel={null} focused={false} busy={false} stack
          order={GGC_STRETCH_ORDER} extra={extra} onStretch={onStretch} live={cw.liveOf(card.symbol)} />
  );
}
