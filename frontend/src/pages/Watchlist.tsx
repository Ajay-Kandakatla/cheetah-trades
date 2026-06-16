import { useState, useMemo } from 'react';
import { useWatchlist, type WatchlistEntry } from '../hooks/useWatchlist';
import { TickerLink } from '../components/TickerLink';
import { TickerPrice } from '../components/TickerPrice';
import { InfoButton } from '../components/InfoButton';
import { PriceAlertModal } from '../components/PriceAlertModal';

/* ==========================================================================
   /watchlist — user-curated ticker shelf with auto-research.
   Adding a ticker spawns a background task that fetches yfinance info, looks
   up SEPA score, and finds 3-5 industry peers (auto-added as competitors).
   ========================================================================== */

const WatchlistInfo = (
  <>
    <p>
      <strong>Watchlist</strong> is your personal ticker shelf. When you add
      something, the app does the legwork in the background:
    </p>
    <ul>
      <li>Fetches sector / industry / market cap / live price</li>
      <li>Looks up the latest SEPA score if the ticker has been analyzed</li>
      <li>Finds <strong>3-5 industry peers</strong> from the analyzed
        universe and auto-adds them as competitors</li>
      <li>Hooks the ticker into the supply/demand graph so it shows up
        on the next refresh</li>
    </ul>
    <p>
      You can add tickers from anywhere in the app via the <strong>★</strong>
      icon next to a symbol. Removing a primary ticker also removes the
      competitors that were added because of it.
    </p>
  </>
);

function statusPill(status: string) {
  const map: Record<string, string> = {
    queued: 'wl-status--queued',
    researching: 'wl-status--researching',
    ready: 'wl-status--ready',
    failed: 'wl-status--failed',
  };
  const label: Record<string, string> = {
    queued: 'Queued',
    researching: 'Researching…',
    ready: 'Ready',
    failed: 'Failed',
  };
  return <span className={`wl-status ${map[status] ?? ''}`}>{label[status] ?? status}</span>;
}

function fmtMcap(n: number | null | undefined): string {
  if (!n) return '—';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toFixed(0)}`;
}

function WatchEntry({ entry, onRemove, onRefresh, onAlert }: {
  entry: WatchlistEntry;
  onRemove: (t: string) => void;
  onRefresh: (t: string) => void;
  onAlert: (entry: WatchlistEntry) => void;
}) {
  const r = entry.research ?? {};
  const isCompetitor = entry.primary_ticker !== null;
  return (
    <article className={`wl-card ${isCompetitor ? 'wl-card--peer' : ''}`}>
      <header className="wl-card__head">
        <TickerLink ticker={entry.ticker} fromLabel="watchlist" className="wl-card__sym" />
        <TickerPrice ticker={entry.ticker} />
        {statusPill(entry.status)}
        <div className="wl-card__actions">
          <button type="button" className="wl-action" onClick={() => onAlert(entry)}
                  title="Set price alert (defaults to price-above target)">🔔</button>
          <button type="button" className="wl-action" onClick={() => onRefresh(entry.ticker)}
                  title="Re-run research">↻</button>
          <button type="button" className="wl-action wl-action--danger" onClick={() => onRemove(entry.ticker)}
                  title="Remove from watchlist">✕</button>
        </div>
      </header>

      {r.name && <div className="wl-card__name">{r.name}</div>}

      {isCompetitor && (
        <div className="wl-card__via mono">
          added because of <strong>{entry.primary_ticker}</strong>
        </div>
      )}

      {entry.status === 'ready' && (
        <div className="wl-card__meta">
          {r.sector && <span className="wl-tag mono">{r.sector}</span>}
          {r.industry && <span className="wl-tag mono">{r.industry}</span>}
          {r.market_cap != null && <span className="wl-tag mono">cap {fmtMcap(r.market_cap)}</span>}
          {r.score != null && (
            <span className={`wl-tag wl-tag--score ${r.rating ?? ''}`}>
              SEPA {r.score.toFixed(0)} {r.rating && `· ${r.rating}`}
            </span>
          )}
          {r.rs_rank != null && <span className="wl-tag mono">RS {r.rs_rank}</span>}
          {r.stage_label && <span className="wl-tag mono">{r.stage_label}</span>}
        </div>
      )}

      {entry.status !== 'ready' && entry.status !== 'failed' && (
        <div className="wl-card__loading mono">Working in the background…</div>
      )}
      {entry.status === 'failed' && (
        <div className="wl-card__failed mono">Research failed — try refresh</div>
      )}
    </article>
  );
}

export default function WatchlistPage() {
  const { rows, loading, add, remove, refresh } = useWatchlist();
  const [input, setInput] = useState('');
  // Active price-alert modal — set by clicking the 🔔 button on a row.
  // Defaults to "price above" (target-style) per user preference.
  const [alertingEntry, setAlertingEntry] = useState<WatchlistEntry | null>(null);

  // Group: primaries (user-added) at top, with their competitors nested under each
  const groups = useMemo(() => {
    const primaries = rows.filter((r) => r.primary_ticker === null)
      .sort((a, b) => b.added_at - a.added_at);
    const peersByPrimary: Record<string, WatchlistEntry[]> = {};
    for (const r of rows) {
      if (r.primary_ticker) {
        (peersByPrimary[r.primary_ticker] ??= []).push(r);
      }
    }
    return primaries.map((p) => ({
      primary: p,
      peers: (peersByPrimary[p.ticker] ?? [])
        .sort((a, b) => a.ticker.localeCompare(b.ticker)),
    }));
  }, [rows]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    add(input);
    setInput('');
  };

  return (
    <div className="wl-page">
      <div className="wl-page__title">
        <InfoButton title="Watchlist">{WatchlistInfo}</InfoButton>
        <div>
          <div className="eyebrow">Personal shelf</div>
          <h1 className="display wl-page__h1">Watchlist</h1>
          <p className="lede">
            Add a ticker · auto-fetch its peers + sector + score in the background.
          </p>
        </div>
      </div>

      <form className="wl-add" onSubmit={submit}>
        <input
          type="search"
          className="wl-add__input"
          placeholder="Add ticker (e.g. NVDA, SNDK, MU)…"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          autoComplete="off"
        />
        <button type="submit" className="wl-add__btn">+ Add</button>
      </form>

      {loading && rows.length === 0 ? (
        <div className="wl-empty">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="wl-empty">
          <p><strong>Your watchlist is empty.</strong></p>
          <p>Add a ticker above, or click the ☆ icon next to any ticker
            anywhere else in the app.</p>
        </div>
      ) : (
        <div className="wl-groups">
          {groups.map(({ primary, peers }) => (
            <section key={primary.ticker} className="wl-group">
              <WatchEntry entry={primary} onRemove={remove} onRefresh={refresh} onAlert={setAlertingEntry} />
              {peers.length > 0 && (
                <div className="wl-peers">
                  <div className="wl-peers__label mono">
                    Competitors auto-added · {peers.length}
                  </div>
                  <div className="wl-peers__grid">
                    {peers.map((p) => (
                      <WatchEntry key={p.ticker} entry={p} onRemove={remove} onRefresh={refresh} onAlert={setAlertingEntry} />
                    ))}
                  </div>
                </div>
              )}
            </section>
          ))}
        </div>
      )}

      {/* Price-alert modal — opens with kind='above' default per user preference.
          User types the target dollar amount; alert fires push to phone. */}
      {alertingEntry && (
        <PriceAlertModal
          symbol={alertingEntry.ticker}
          currentPrice={alertingEntry.research?.last_price ?? null}
          defaultKind="above"
          defaultLevel=""
          onClose={() => setAlertingEntry(null)}
          onCreated={() => setAlertingEntry(null)}
        />
      )}
    </div>
  );
}
