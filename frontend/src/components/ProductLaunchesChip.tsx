/* ProductLaunchesChip — surfaces new product launches per ticker as a
   tappable chip on each SEPA card. Tap → modal lists each launch with
   product name, category, status, expected impact, and a link to the
   source article.

   Data is computed offline by the nightly cron in
   `catalysts.product_launches` and read here from the cache. No LLM in
   the request path. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { getLaunchCount, invalidateLaunchCount } from '../lib/launchesBatcher';
import { subscribe as busSubscribe } from '../lib/eventBus';

type Launch = {
  symbol: string;
  url: string;
  title: string;
  description?: string;
  publisher?: string;
  published_at?: string;
  product_name?: string;
  category?: string;
  status?: 'announced' | 'preorder' | 'shipping' | 'rumored';
  expected_impact?: string;
  reason?: string;
  confidence?: number;
};

const CATEGORY_EMOJI: Record<string, string> = {
  cpu:           '🧠',
  gpu:           '🎮',
  ai_chip:       '🤖',
  server:        '🖥️',
  storage:       '💾',
  networking:    '📡',
  smartphone:    '📱',
  laptop:        '💻',
  tablet:        '📱',
  wearable:      '⌚',
  software:      '🧩',
  saas:          '☁️',
  ai_model:      '🧬',
  api:           '🔌',
  platform:      '🪟',
  vehicle:       '🚗',
  battery:       '🔋',
  robotics:      '🦾',
  medical_device:'🩺',
  drug:          '💊',
  therapy:       '🩹',
  other:         '🚀',
};

const STATUS_COLOR: Record<string, string> = {
  announced: 'var(--cm-slate, #888)',
  preorder:  'var(--warn, #d97706)',
  shipping:  'var(--positive, #10b981)',
  rumored:   'var(--rule, #666)',
};

export function ProductLaunchesChip({ symbol }: { symbol: string }) {
  const [count, setCount] = useState<number | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // Batched lookup — many chips on the SEPA list share one HTTP call.
    // See lib/launchesBatcher.ts for the debounced fan-in logic.
    getLaunchCount(symbol)
      .then(n => { if (!cancelled) setCount(n); })
      .catch(() => { if (!cancelled) setCount(0); });
    return () => { cancelled = true; };
  }, [symbol]);

  // Live-update via SSE: when any client (or the nightly cron) refreshes
  // launches for this symbol, the backend publishes `launch.refreshed`
  // with the new count. We drop the batched cache entry too so any
  // sibling chip that re-mounts later sees the fresh number.
  useEffect(() => {
    return busSubscribe('launch.refreshed', (evt) => {
      const p = evt.payload || {};
      if (typeof p.symbol !== 'string') return;
      if (p.symbol.toUpperCase() !== symbol.toUpperCase()) return;
      invalidateLaunchCount(symbol);
      if (typeof p.count === 'number') setCount(p.count);
    });
  }, [symbol]);

  // Don't render if there are no cached launches — chip would just be noise.
  if (count == null || count === 0) return null;

  return (
    <>
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.stopPropagation(); e.preventDefault(); setOpen(true);
          }
        }}
        className="sepa-flag sepa-flag--good"
        title={`Tap to see ${count} recent product launch${count === 1 ? '' : 'es'} by ${symbol}`}
        style={{ cursor: 'pointer' }}
      >
        🚀 {count} launch{count === 1 ? '' : 'es'}
        <span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 2 }}>↗</span>
      </span>
      {open && <LaunchesModal symbol={symbol} onClose={() => setOpen(false)} />}
    </>
  );
}

function LaunchesModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [rows, setRows] = useState<Launch[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/catalysts/launches/${encodeURIComponent(symbol)}?days=90&limit=20`, { cache: 'no-store' })
      .then(r => r.json())
      .then(j => { if (!cancelled) setRows(j?.launches || []); })
      .catch(() => { if (!cancelled) setRows([]); });
    return () => { cancelled = true; };
  }, [symbol]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${API}/catalysts/launches/${encodeURIComponent(symbol)}/refresh?days=30`, { method: 'POST' });
      const r = await fetch(`${API}/catalysts/launches/${encodeURIComponent(symbol)}?days=90&limit=20`, { cache: 'no-store' });
      const j = await r.json();
      setRows(j?.launches || []);
      // Drop the batched-count cache for this symbol so the chip outside
      // the modal re-fetches the new total via the batcher on next mount.
      invalidateLaunchCount(symbol);
    } catch { /* swallow */ }
    finally { setRefreshing(false); }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '1rem', overflowY: 'auto',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
          border: '1px solid var(--rule, #333)', borderRadius: 8,
          width: '100%', maxWidth: 620, maxHeight: '90vh', overflow: 'auto',
          padding: '1.1rem 1.3rem',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.5rem' }}>
          <div>
            <div className="eyebrow">Product launches · catalyst signal</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>{symbol} <span style={{ color: 'var(--cm-slate)', fontSize: '0.8rem', marginLeft: '0.4rem' }}>recent announcements</span></h2>
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <button onClick={refresh} disabled={refreshing} aria-busy={refreshing} style={{ background: 'none', border: '1px solid var(--rule, #444)', color: 'var(--cm-slate)', padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontSize: '0.72rem' }}>
              {refreshing ? '…scanning' : '↻ refresh'}
            </button>
            <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}>×</button>
          </div>
        </div>

        {rows == null && <div style={{ color: 'var(--cm-slate)', marginTop: '0.5rem' }}>Loading…</div>}
        {rows != null && rows.length === 0 && (
          <p style={{ fontSize: '0.85rem', color: 'var(--cm-slate)', marginTop: '0.5rem' }}>
            No product launches detected in the cache. Tap <strong>↻ refresh</strong> to scan now (15-30s — fetches news and runs each candidate through Gemma).
          </p>
        )}

        {rows && rows.length > 0 && (
          <div style={{ marginTop: '0.6rem', display: 'grid', gap: '0.6rem' }}>
            {rows.map((r) => {
              const emoji = CATEGORY_EMOJI[r.category || 'other'] || '🚀';
              const statusColor = STATUS_COLOR[r.status || 'announced'];
              const pubDate = r.published_at
                ? new Date(r.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                : '';
              return (
                <a
                  key={r.url}
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'block',
                    padding: '0.6rem 0.8rem',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--rule, #333)',
                    borderRadius: 4,
                    color: 'inherit',
                    textDecoration: 'none',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.92rem', minWidth: 0, flex: 1 }}>
                      <span style={{ marginRight: '0.35rem' }}>{emoji}</span>
                      {r.product_name || r.title}
                    </div>
                    <span className="mono" style={{ fontSize: '0.66rem', color: statusColor, textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>
                      {r.status || 'announced'}
                    </span>
                  </div>
                  {r.expected_impact && (
                    <div style={{ fontSize: '0.78rem', marginTop: '0.3rem', lineHeight: 1.45 }}>{r.expected_impact}</div>
                  )}
                  <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.35rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span>{r.category}</span>
                    {pubDate && <span>· {pubDate}</span>}
                    {r.publisher && <span>· {r.publisher}</span>}
                    {r.confidence != null && <span>· conf {(r.confidence * 100).toFixed(0)}%</span>}
                  </div>
                </a>
              );
            })}
          </div>
        )}

        <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.8rem' }}>
          Sourced from news headlines (Massive API) and classified by Gemma. Cached 7 days; refreshed nightly across watchlist + portfolio + SEPA top-50.
        </p>
      </div>
    </div>
  );
}
