/* GlobalSearch — the ⌘K command palette over every navigation entry, and (since
 * 2026-09-18) over tickers in the SAME field.
 *
 * Ajay 2026-09-06: "give me a global search navigation like if I wanna search
 * or related like notification I want them to show up from all the
 * navigational menu."
 * Ajay 2026-09-18: "can you make global search help find ickers also directly
 * in the same field."
 *
 * Trigger: a compact pill in the NavBar's meta cluster (desktop) or an icon
 * button in the phone action bar (`compact`). Shortcuts: ⌘K / Ctrl+K anywhere,
 * "/" when focus is not inside an input / textarea / contenteditable. The
 * palette is a fixed overlay (portaled to <body> so the sticky phone nav's
 * stacking context cannot trap it); ↑/↓ move the highlight, Enter navigates
 * (router for in-app paths, a normal browser open for absolute URLs), Esc or
 * a backdrop click closes, and any route change closes it.
 *
 * TWO KINDS OF ROW, one field:
 *  - PAGES come from lib/navSearch.buildIndex over hooks/useMyMenu — the
 *    backend menu is the safe-by-construction surface, so a page result can
 *    never point at something this user cannot reach. Synchronous, unchanged.
 *  - TICKERS come from hooks/useTickerSearch (/symbol-search) ranked by
 *    lib/tickerSearch. Asynchronous and FAIL-OPEN: pages render instantly, are
 *    never blanked by a slow, failed or junk lookup, and typing never waits.
 *    Rendered only when `sepa` is in this user's own menu, because
 *    /sepa/:symbol is FeatureRoute-gated.
 *
 * Ranking of the ticker half is a UX choice. Nothing about it is measured and
 * nothing about it gates an alert, a lane, an order or a threshold.
 */
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import { useMyMenu } from '../hooks/useMyMenu';
import { useNewFeatures } from '../hooks/useNewFeatures';
import { useTickerSearch, tickerQuery } from '../hooks/useTickerSearch';
import { buildIndex, isExternal, searchNav } from '../lib/navSearch';
import { mergeRows, pinnedSymbol, rankTickers, rowKey, sectionHeaderAt, type Row } from '../lib/tickerSearch';
import { trackFeature } from '../lib/usageTracker';

export const GLOBAL_SEARCH_FEATURE_ID = 'global-search';
export const GLOBAL_SEARCH_TICKERS_FEATURE_ID = 'global-search-tickers';
/** Pages only. The ticker half has its own TICKER_RESULT_LIMIT. */
const RESULT_LIMIT = 8;

type Props = {
  /** Icon-only trigger for the phone action bar. */
  compact?: boolean;
  /** Tools sub-group for a feature id (NavBar's TOOLS_SUBGROUP) — names the
   *  group chip "Tools ▸ Signals" instead of a bare "Tools". */
  subgroupOf?: (feature?: string) => string | undefined;
};

function isEditable(el: EventTarget | null): boolean {
  const n = el as HTMLElement | null;
  if (!n || typeof n.closest !== 'function') return false;
  return !!n.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]');
}

function isMac(): boolean {
  if (typeof navigator === 'undefined') return false;
  const p = `${navigator.platform || ''} ${navigator.userAgent || ''}`;
  return /mac|iphone|ipad/i.test(p);
}

export function GlobalSearch({ compact = false, subgroupOf }: Props) {
  const { menu } = useMyMenu();
  const navigate = useNavigate();
  const location = useLocation();
  const { isNew, markSeen } = useNewFeatures();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeKey, setActiveKey] = useState<string | null>(null);
  /* Has he MOVED the highlight himself (↑/↓)? Until he has, the highlight is
   * ours to place; the moment he has, it is his and nothing may take it. */
  const [touched, setTouched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const index = useMemo(() => buildIndex(menu, subgroupOf), [menu, subgroupOf]);
  const results = useMemo(() => searchNav(index, query, RESULT_LIMIT), [index, query]);
  const mac = useMemo(isMac, []);

  /* `sepa` in the menu is exactly "the server granted this user SEPA"
   * (buildIndex only adds a deep link whose parent feature is present), so a
   * ticker row can never send a friend to <Navigate to="/" />. */
  const canTickers = useMemo(() => index.some((e) => e.feature === 'sepa'), [index]);
  const tq = useMemo(() => tickerQuery(query), [query]);
  const ticker = useTickerSearch(query, open && canTickers);
  // No `status === 'done'` gate: the hook keeps `raw` while the effective query
  // is unchanged, and gating on the status is what would blank the rows on an
  // unrelated re-render.
  const tickers = useMemo(
    () => (ticker.query === tq && ticker.raw ? rankTickers(ticker.query, ticker.raw) : []),
    [ticker, tq],
  );
  const rows = useMemo(() => mergeRows(results, tickers, query), [results, tickers, query]);

  const openPalette = useCallback(() => {
    setQuery('');
    setActiveKey(null);
    setTouched(false);
    setOpen(true);
    // Opening it once is "seeing" the feature — clears the ✨ on the trigger.
    if (isNew(GLOBAL_SEARCH_FEATURE_ID)) markSeen(GLOBAL_SEARCH_FEATURE_ID);
    if (isNew(GLOBAL_SEARCH_TICKERS_FEATURE_ID)) markSeen(GLOBAL_SEARCH_TICKERS_FEATURE_ID);
  }, [isNew, markSeen]);

  const close = useCallback(() => setOpen(false), []);

  // Global shortcuts: ⌘K / Ctrl+K toggles; "/" opens when not typing elsewhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        if (open) close(); else openPalette();
        return;
      }
      if (e.key === '/' && !open && !e.metaKey && !e.ctrlKey && !e.altKey && !isEditable(e.target)) {
        e.preventDefault();
        openPalette();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, openPalette, close]);

  // Close on route change (pathname or query — a tab deep link is a change).
  const routeKey = `${location.pathname}${location.search}`;
  const lastRoute = useRef(routeKey);
  useEffect(() => {
    if (lastRoute.current !== routeKey) {
      lastRoute.current = routeKey;
      setOpen(false);
    }
  }, [routeKey]);

  // Focus the input once the overlay mounts.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  /* The highlight is anchored to a row KEY, not an index, and seeded on the
   * first non-empty list. A ticker row landing 300 ms after the pages must
   * never move the row under his finger — with an index, the pin arriving at
   * row 0 silently re-points Enter at a different destination. */
  /* THE PIN IS THE EXCEPTION, and it is the whole feature (2026-09-18).
   * Measured against his real 18-symbol menu: for 9 of 18 — AMD, LLY, ANET, MU,
   * TSM, CRDO, SPY, VRT, ARM — the pages answered first, the highlight seeded
   * on page row 0, and when the exact-symbol row then landed ABOVE it the
   * highlight stayed put. He saw `📈 AMD` on top, pressed Enter, and got
   * Supply/Demand. `LLY` went to /volleyball.
   *
   * So the rule is narrower than "a late row never moves the highlight": a late
   * row never moves a highlight HE placed. The pin is the row he literally
   * typed, so while the highlight is still ours it follows the pin. */
  useEffect(() => {
    if (!rows.length) return;
    const pin = pinnedSymbol(query, tickers, results);
    if (!touched && pin) {
      const key = `ticker:${pin}`;
      if (activeKey !== key && rows.some((r) => rowKey(r) === key)) { setActiveKey(key); return; }
    }
    if (activeKey && rows.some((r) => rowKey(r) === activeKey)) return;
    setActiveKey(rowKey(rows[0]));
  }, [rows, activeKey, touched, query, tickers, results]);

  const active = useMemo(() => {
    const i = activeKey ? rows.findIndex((r) => rowKey(r) === activeKey) : -1;
    return i >= 0 ? i : 0;
  }, [rows, activeKey]);

  // Scroll the highlighted row into view for long lists (jsdom has no
  // scrollIntoView). By id, never by child index — section headers are <li>s.
  useEffect(() => {
    if (!open) return;
    const row = listRef.current?.querySelector(`#cm-search-opt-${active}`) as HTMLElement | null;
    if (row && typeof row.scrollIntoView === 'function') row.scrollIntoView({ block: 'nearest' });
  }, [active, open]);

  const choose = useCallback((row: Row | undefined) => {
    if (!row) return;
    trackFeature(GLOBAL_SEARCH_FEATURE_ID);
    setOpen(false);
    if (row.kind === 'ticker') {
      navigate(row.to);
      return;
    }
    if (isExternal(row.entry.to)) {
      window.open(row.entry.to, '_blank', 'noopener');
      return;
    }
    navigate(row.entry.to);
  }, [navigate]);

  const move = (delta: number) => {
    if (!rows.length) return;
    setTouched(true);
    const next = ((active + delta) % rows.length + rows.length) % rows.length;
    setActiveKey(rowKey(rows[next]));
  };

  const onInputKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      move(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      move(-1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(rows[active]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  };

  const showNew = isNew(GLOBAL_SEARCH_FEATURE_ID) || isNew(GLOBAL_SEARCH_TICKERS_FEATURE_ID);
  const trimmed = query.trim();
  const lookingUp = canTickers && ticker.status === 'loading';
  const lookupFailed = canTickers && ticker.status === 'error';

  /* The palette must not read "No matches" while a lookup that could still
   * produce rows is in flight, and must not read "No matches" when the truth is
   * that the lookup failed. Exactly ONE role="status" node, as before. */
  const emptyCopy = !trimmed
    ? 'Nothing in your menu yet.'
    : lookingUp
      ? 'Looking up tickers…'
      : lookupFailed
        ? <>No page matches for <strong>“{trimmed}”</strong> — ticker lookup unavailable</>
        : <>No matches for <strong>“{trimmed}”</strong></>;

  // One muted line under a list that DID render, so the state of the ticker
  // half is never silent. Gated on rows.length so it can never coexist with the
  // empty state — a second role="status" would break getByRole('status').
  const tickerNote = rows.length > 0 && (lookingUp || lookupFailed)
    ? (lookingUp ? 'Looking up tickers…' : 'Ticker lookup unavailable — pages only')
    : null;

  const trigger = compact ? (
    <button
      type="button"
      className="cm-nav__rail-btn cm-search__trigger--compact"
      onClick={openPalette}
      aria-label="Search"
      title={`Search pages and tickers (${mac ? '⌘K' : 'Ctrl+K'})`}
      aria-haspopup="dialog"
      aria-expanded={open}
    >
      🔍
      {showNew && <span className="nav-new-dot" aria-hidden="true">✨</span>}
    </button>
  ) : (
    <button
      type="button"
      className="cm-search__trigger"
      onClick={openPalette}
      aria-label="Search pages and tickers"
      title="Search every page in your menu — and any ticker"
      aria-haspopup="dialog"
      aria-expanded={open}
    >
      <span aria-hidden="true">🔍</span>
      <span className="cm-search__trigger-label">Search</span>
      <kbd className="cm-search__kbd">{mac ? '⌘K' : 'Ctrl K'}</kbd>
      {showNew && <span className="nav-new-dot" aria-label="new feature here" title="New: pages and tickers in one search">✨</span>}
    </button>
  );

  const palette = open ? (
    <div
      className="cm-search__backdrop"
      onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
      data-testid="global-search-backdrop"
    >
      <div
        className="cm-search__panel"
        role="dialog"
        aria-modal="true"
        aria-label="Search pages and tickers"
      >
        <input
          ref={inputRef}
          className="cm-search__input"
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setActiveKey(null); setTouched(false); }}
          onKeyDown={onInputKey}
          placeholder="Search pages or a ticker… (e.g. notification, DOCN)"
          aria-label="Search pages and tickers"
          aria-autocomplete="list"
          aria-controls="cm-search-results"
          aria-activedescendant={rows.length ? `cm-search-opt-${active}` : undefined}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          autoFocus
        />
        {rows.length > 0 ? (
          <ul className="cm-search__list" role="listbox" id="cm-search-results" ref={listRef}>
            {rows.map((r, i) => {
              const header = sectionHeaderAt(rows, i);
              const key = rowKey(r);
              return (
                <Fragment key={key}>
                  {header && (
                    <li className="cm-search__section" role="presentation" aria-hidden="true">{header}</li>
                  )}
                  {r.kind === 'page' ? (
                    <li
                      id={`cm-search-opt-${i}`}
                      role="option"
                      aria-selected={i === active}
                      className={`cm-search__item${i === active ? ' is-active' : ''}`}
                      onMouseEnter={() => setActiveKey(key)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => choose(r)}
                    >
                      <span className="cm-search__label">{r.entry.label}</span>
                      <span className="cm-search__group">{r.entry.group}</span>
                    </li>
                  ) : (
                    <li
                      id={`cm-search-opt-${i}`}
                      role="option"
                      aria-selected={i === active}
                      className={`cm-search__item cm-search__item--ticker${i === active ? ' is-active' : ''}`}
                      onMouseEnter={() => setActiveKey(key)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => choose(r)}
                    >
                      <span className="cm-search__sym">📈 {r.symbol}</span>
                      <span className="cm-search__label">{r.name || r.symbol}</span>
                      <span className="cm-search__group cm-search__group--ticker">Ticker</span>
                    </li>
                  )}
                </Fragment>
              );
            })}
          </ul>
        ) : (
          <div className="cm-search__empty" role="status">{emptyCopy}</div>
        )}
        {tickerNote && (
          <div className="cm-search__ticker-note" data-testid="ticker-note">{tickerNote}</div>
        )}
        <div className="cm-search__foot" aria-hidden="true">
          <span>↑↓ move</span>
          <span>↵ open</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <>
      {trigger}
      {palette && typeof document !== 'undefined' ? createPortal(palette, document.body) : null}
    </>
  );
}
