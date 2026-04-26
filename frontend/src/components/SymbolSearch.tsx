import { useEffect, useRef, useState } from 'react';

const API = (import.meta as any).env?.VITE_API_BASE ?? '';

export type SearchResult = {
  symbol: string;
  display_symbol: string;
  name: string;
  type: string;
};

type Props = {
  /** Called when the user picks a result and presses "Add" (or hits Enter). */
  onAdd: (sym: string, name?: string) => void;
  /** Called when the user wants to run SEPA on the selected ticker. */
  onAnalyze?: (sym: string, name?: string) => void;
  placeholder?: string;
};

/**
 * SymbolSearch — debounced typeahead against the backend `/symbol-search`
 * proxy (Finnhub free-tier symbol search). Lets users add ANY valid US
 * ticker to the live watch table or trigger an on-demand SEPA analysis.
 */
export function SymbolSearch({ onAdd, onAnalyze, placeholder = 'Search any ticker — e.g. ASML, AVGO, TSLA' }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounced search
  useEffect(() => {
    const q = query.trim();
    if (q.length < 1) {
      setResults([]);
      return;
    }
    setLoading(true);
    const handle = setTimeout(() => {
      fetch(`${API}/symbol-search?q=${encodeURIComponent(q)}`)
        .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
        .then((j) => {
          setResults(j.results ?? []);
          setActiveIdx(0);
        })
        .catch((e) => console.warn('symbol-search failed', e))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(handle);
  }, [query]);

  // Close on outside click
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) {
      if (e.key === 'Enter' && query.trim()) {
        // No suggestions yet — accept raw input
        e.preventDefault();
        onAdd(query.trim().toUpperCase());
        setQuery('');
      }
      return;
    }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(results.length - 1, i + 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setActiveIdx((i) => Math.max(0, i - 1)); }
    if (e.key === 'Enter') {
      e.preventDefault();
      const r = results[activeIdx];
      if (r) {
        onAdd(r.symbol, r.name);
        setQuery('');
        setOpen(false);
      }
    }
    if (e.key === 'Escape') setOpen(false);
  };

  const selected = results[activeIdx];

  return (
    <div className="symbol-search" ref={wrapperRef}>
      <div className="symbol-search__row">
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
        />
      </div>

      {open && query.trim().length > 0 && (
        <div className="symbol-search__menu" role="listbox">
          {loading && results.length === 0 && (
            <div className="symbol-search__loading">Searching…</div>
          )}
          {!loading && results.length === 0 && (
            <div className="symbol-search__hint">
              No matches. Press Enter to add <strong>{query.trim().toUpperCase()}</strong> anyway.
            </div>
          )}
          {results.map((r, i) => (
            <div
              key={r.symbol}
              className={`symbol-search__row-sym ${i === activeIdx ? 'is-active' : ''}`}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => { onAdd(r.symbol, r.name); setQuery(''); setOpen(false); }}
              role="option"
              aria-selected={i === activeIdx}
            >
              <span className="ticker">{r.display_symbol}</span>
              <span className="name">{r.name}</span>
              <span className="exch">{r.type}</span>
            </div>
          ))}
          {selected && onAnalyze && (
            <div className="symbol-search__actions">
              <button
                type="button"
                className="symbol-search__action symbol-search__action--primary"
                onClick={() => { onAdd(selected.symbol, selected.name); setQuery(''); setOpen(false); }}
              >
                Add to watch
              </button>
              <button
                type="button"
                className="symbol-search__action"
                onClick={() => { onAnalyze(selected.symbol, selected.name); setQuery(''); setOpen(false); }}
              >
                Run SEPA
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
