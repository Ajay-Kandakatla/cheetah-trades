/* GlobalSearch — the ⌘K command palette over every navigation entry.
 *
 * Ajay 2026-09-06: "give me a global search navigation like if I wanna search
 * or related like notification I want them to show up from all the
 * navigational menu."
 *
 * Trigger: a compact pill in the NavBar's meta cluster (desktop) or an icon
 * button in the phone action bar (`compact`). Shortcuts: ⌘K / Ctrl+K anywhere,
 * "/" when focus is not inside an input / textarea / contenteditable. The
 * palette is a fixed overlay (portaled to <body> so the sticky phone nav's
 * stacking context cannot trap it); ↑/↓ move the highlight, Enter navigates
 * (router for in-app paths, a normal browser open for absolute URLs), Esc or
 * a backdrop click closes, and any route change closes it.
 *
 * The index is lib/navSearch.buildIndex over hooks/useMyMenu — the backend
 * menu is the safe-by-construction surface, so a result can never point at a
 * page this user cannot reach. Ranking lives in lib/navSearch (tested).
 */
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import { useMyMenu } from '../hooks/useMyMenu';
import { useNewFeatures } from '../hooks/useNewFeatures';
import { buildIndex, isExternal, searchNav, type NavEntry } from '../lib/navSearch';
import { trackFeature } from '../lib/usageTracker';

export const GLOBAL_SEARCH_FEATURE_ID = 'global-search';
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
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const index = useMemo(() => buildIndex(menu, subgroupOf), [menu, subgroupOf]);
  const results = useMemo(() => searchNav(index, query, RESULT_LIMIT), [index, query]);
  const mac = useMemo(isMac, []);

  const openPalette = useCallback(() => {
    setQuery('');
    setActive(0);
    setOpen(true);
    // Opening it once is "seeing" the feature — clears the ✨ on the trigger.
    if (isNew(GLOBAL_SEARCH_FEATURE_ID)) markSeen(GLOBAL_SEARCH_FEATURE_ID);
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

  // Keep the highlight inside the result list as the list changes.
  useEffect(() => {
    setActive((a) => (results.length ? Math.min(a, results.length - 1) : 0));
  }, [results]);

  // Scroll the highlighted row into view for long lists (jsdom has no scrollIntoView).
  useEffect(() => {
    if (!open) return;
    const row = listRef.current?.children[active] as HTMLElement | undefined;
    if (row && typeof row.scrollIntoView === 'function') row.scrollIntoView({ block: 'nearest' });
  }, [active, open]);

  const choose = useCallback((entry: NavEntry | undefined) => {
    if (!entry) return;
    trackFeature(GLOBAL_SEARCH_FEATURE_ID);
    setOpen(false);
    if (isExternal(entry.to)) {
      window.open(entry.to, '_blank', 'noopener');
      return;
    }
    navigate(entry.to);
  }, [navigate]);

  const onInputKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => (results.length ? (a + 1) % results.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => (results.length ? (a - 1 + results.length) % results.length : 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(results[active]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  };

  const showNew = isNew(GLOBAL_SEARCH_FEATURE_ID);
  const trimmed = query.trim();

  const trigger = compact ? (
    <button
      type="button"
      className="cm-nav__rail-btn cm-search__trigger--compact"
      onClick={openPalette}
      aria-label="Search"
      title={`Search pages (${mac ? '⌘K' : 'Ctrl+K'})`}
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
      aria-label="Search pages"
      title="Search every page in your menu"
      aria-haspopup="dialog"
      aria-expanded={open}
    >
      <span aria-hidden="true">🔍</span>
      <span className="cm-search__trigger-label">Search</span>
      <kbd className="cm-search__kbd">{mac ? '⌘K' : 'Ctrl K'}</kbd>
      {showNew && <span className="nav-new-dot" aria-label="new feature here" title="New: global search">✨</span>}
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
        aria-label="Search pages"
      >
        <input
          ref={inputRef}
          className="cm-search__input"
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setActive(0); }}
          onKeyDown={onInputKey}
          placeholder="Search pages… (e.g. notification)"
          aria-label="Search pages"
          aria-autocomplete="list"
          aria-controls="cm-search-results"
          aria-activedescendant={results.length ? `cm-search-opt-${active}` : undefined}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          autoFocus
        />
        {results.length > 0 ? (
          <ul className="cm-search__list" role="listbox" id="cm-search-results" ref={listRef}>
            {results.map((r, i) => (
              <li
                key={r.to}
                id={`cm-search-opt-${i}`}
                role="option"
                aria-selected={i === active}
                className={`cm-search__item${i === active ? ' is-active' : ''}`}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(r)}
              >
                <span className="cm-search__label">{r.label}</span>
                <span className="cm-search__group">{r.group}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="cm-search__empty" role="status">
            {trimmed
              ? <>No matches for <strong>“{trimmed}”</strong></>
              : 'Nothing in your menu yet.'}
          </div>
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
