import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';

/* ============================================================================
 * GlobalStockSearch — top-right typeahead that's NOT limited to the SEPA list.
 * ---------------------------------------------------------------------------
 * Calls the existing `/symbol-search` Finnhub-proxy endpoint (universe-wide,
 * cached 6h server-side). On selection navigates to /sepa/<TICKER>.
 *
 * Differs from <SymbolSearch /> (which targets the watchlist "add" flow with
 * Add-to-watch / Run-SEPA buttons). This one is pure navigation, compact,
 * placeable in any page header. Also adds ⌘K / Ctrl+K to focus.
 * ========================================================================== */

type Match = {
  symbol: string;
  display_symbol: string;
  name: string;
  type: string;
};

type Props = {
  /** Override default `/sepa/<sym>` navigation. */
  onSelect?: (symbol: string, name?: string) => void;
  placeholder?: string;
  /** Extra className for the wrapper (e.g. for layout-specific positioning). */
  className?: string;
  /** Set to false to disable the ⌘K shortcut on this instance. Default true. */
  enableShortcut?: boolean;
};

export function GlobalStockSearch({
  onSelect,
  placeholder = 'Search any ticker — e.g. NOK, NVTS, AVGO',
  className = '',
  enableShortcut = true,
}: Props) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Match[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSelect = useCallback((sym: string, name?: string) => {
    setQuery('');
    setResults([]);
    setOpen(false);
    inputRef.current?.blur();
    if (onSelect) onSelect(sym, name);
    else navigate(`/sepa/${sym.toUpperCase()}`);
  }, [navigate, onSelect]);

  // Debounced search.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 1) {
      setResults([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      fetch(`${API}/symbol-search?q=${encodeURIComponent(q)}`)
        .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
        .then((j) => {
          setResults(j.results ?? []);
          setActiveIdx(0);
        })
        .catch((e) => console.warn('symbol-search failed', e))
        .finally(() => setLoading(false));
    }, 180);
    return () => clearTimeout(t);
  }, [query]);

  // Close on outside click.
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  // ⌘K / Ctrl+K focuses the search; Escape blurs.
  useEffect(() => {
    if (!enableShortcut) return;
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
        setOpen(true);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [enableShortcut]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      if (query) {
        setQuery('');
        setResults([]);
      } else {
        inputRef.current?.blur();
        setOpen(false);
      }
      return;
    }
    if (!open || results.length === 0) {
      // No suggestions yet — Enter still accepts raw input as a ticker.
      if (e.key === 'Enter' && query.trim()) {
        e.preventDefault();
        handleSelect(query.trim().toUpperCase());
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(results.length - 1, i + 1));
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const r = results[activeIdx];
      if (r) handleSelect(r.symbol, r.name);
      else if (query.trim()) handleSelect(query.trim().toUpperCase());
    }
  };

  return (
    <div
      className={`symbol-search symbol-search--global ${className}`}
      ref={wrapperRef}
    >
      <div className="symbol-search__row">
        <span className="symbol-search__icon" aria-hidden>⌕</span>
        <input
          ref={inputRef}
          type="text"
          className="symbol-search__input"
          placeholder={placeholder}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          autoComplete="off"
          spellCheck={false}
          aria-label="Search any stock"
        />
        {query ? (
          <button
            type="button"
            className="symbol-search__clear"
            onClick={() => { setQuery(''); setResults([]); inputRef.current?.focus(); }}
            aria-label="Clear search"
          >×</button>
        ) : enableShortcut ? (
          <kbd className="symbol-search__kbd" title="Focus search">⌘K</kbd>
        ) : null}
      </div>

      {open && query.trim().length > 0 && (
        <div className="symbol-search__menu" role="listbox">
          {loading && results.length === 0 && (
            <div className="symbol-search__loading">Searching…</div>
          )}
          {!loading && results.length === 0 && (
            <div className="symbol-search__hint">
              No matches. Press <strong>Enter</strong> to open{' '}
              <strong>{query.trim().toUpperCase()}</strong> anyway.
            </div>
          )}
          {results.map((r, i) => (
            <div
              key={r.symbol}
              className={`symbol-search__row-sym ${i === activeIdx ? 'is-active' : ''}`}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => handleSelect(r.symbol, r.name)}
              role="option"
              aria-selected={i === activeIdx}
            >
              <span className="ticker">{r.display_symbol}</span>
              <span className="name">{r.name}</span>
              <span className="exch">{r.type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
