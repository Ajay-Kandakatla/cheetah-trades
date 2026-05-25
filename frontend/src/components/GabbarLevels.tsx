/* GabbarLevels — overlay of Gabbar's curated buy-zone bands.
 *
 * Sourced from veerenj's TradingView Pine Script via backend/catalysts/
 * gabbar_levels.py. The original draws boxes on a chart; we render a
 * vertical band stack instead — easier to scan on phone, no chart-
 * library dependency, and the current price gets a horizontal marker
 * positioned within the bands.
 *
 * Hides itself on uncovered tickers (backend returns 404; we just
 * render null). Attribution + license link in the footer.
 */
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';

type Band = { lo: number; hi: number; label: string };
type Payload = {
  symbol:      string;
  bands:       Band[];
  attribution: {
    source: string; author: string; url: string;
    license: string; snapshot_date: string;
  };
};

export function GabbarLevels({
  symbol,
  currentPrice,
}: {
  symbol: string;
  /** Used to position the "you are here" marker. Optional — without
   *  it we still render the bands as a static reference. */
  currentPrice?: number | null;
}) {
  const [data, setData] = useState<Payload | null>(null);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    fetch(`${API}/catalysts/gabbar-levels/${encodeURIComponent(symbol)}`)
      .then((r) => {
        // 404 = ticker not in the source table. Common case — there
        // are only ~66 covered. We silently bail.
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => { if (!cancelled) { setData(j); setTried(true); } })
      .catch(() => { if (!cancelled) setTried(true); });
    return () => { cancelled = true; };
  }, [symbol]);

  // Compute the price range that fits all bands + current price with a
  // small visual margin so the topmost/bottommost bands aren't flush
  // against the section edges.
  const range = useMemo(() => {
    if (!data?.bands?.length) return null;
    const lows  = data.bands.map((b) => b.lo);
    const highs = data.bands.map((b) => b.hi);
    let lo = Math.min(...lows);
    let hi = Math.max(...highs);
    if (currentPrice != null) {
      lo = Math.min(lo, currentPrice);
      hi = Math.max(hi, currentPrice);
    }
    const pad = (hi - lo) * 0.08 || hi * 0.02;
    return { lo: lo - pad, hi: hi + pad };
  }, [data, currentPrice]);

  // Map a price to a top-percent within the visualization. 0% = top
  // (highest price), 100% = bottom (lowest price). Inverted because
  // CSS top is from the top, but stocks plot high → low downward.
  const priceToPct = (p: number) => {
    if (!range) return 0;
    const span = range.hi - range.lo;
    if (span <= 0) return 50;
    return ((range.hi - p) / span) * 100;
  };

  if (!tried) {
    return null;            // first render before fetch resolves
  }
  if (!data) {
    return null;            // ticker not covered — render nothing
  }

  // Which band (if any) is the current price sitting in? Useful for
  // the inline status line ("📍 in the conservative 1 zone").
  const currentBand = currentPrice != null
    ? data.bands.find((b) => currentPrice >= b.lo && currentPrice <= b.hi)
    : undefined;

  return (
    <section
      style={{
        marginTop: '1rem',
        padding: '0.85rem 1rem',
        border: '1px solid var(--rule, #333)',
        borderRadius: 6,
        background: 'var(--bg-raised, #181818)',
      }}
    >
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.55rem' }}>
        <div>
          <div className="eyebrow">📊 Gabbar's price levels</div>
          <h3 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1rem' }}>
            Buy zones for {symbol}
          </h3>
        </div>
        {currentPrice != null && (
          <div style={{ fontSize: '0.78rem', color: 'var(--cm-slate)' }}>
            Current: <strong style={{ color: 'var(--ink, inherit)' }}>${currentPrice.toFixed(2)}</strong>
            {currentBand && (
              <span style={{ marginLeft: 6, color: 'var(--positive)' }}>
                · 📍 in {currentBand.label} zone
              </span>
            )}
          </div>
        )}
      </header>

      {/* Vertical visualization — green bands stacked at their
          relative price positions. Fixed height keeps the section
          predictable on the page regardless of how many bands a
          ticker has. */}
      <div
        style={{
          position: 'relative',
          height: 180,
          margin: '0.4rem 0 0.6rem',
          background: 'rgba(255,255,255,0.02)',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        {/* Top / bottom price labels — give scale context without an
            axis library. */}
        {range && (
          <>
            <div style={{
              position: 'absolute', top: 2, right: 6,
              fontSize: '0.66rem', color: 'var(--cm-slate)',
              fontFamily: 'monospace',
            }}>
              ${range.hi.toFixed(0)}
            </div>
            <div style={{
              position: 'absolute', bottom: 2, right: 6,
              fontSize: '0.66rem', color: 'var(--cm-slate)',
              fontFamily: 'monospace',
            }}>
              ${range.lo.toFixed(0)}
            </div>
          </>
        )}

        {/* Bands — Gabbar's lime-green tone matching the Pine source. */}
        {data.bands.map((b, i) => {
          const top    = priceToPct(b.hi);
          const bottom = priceToPct(b.lo);
          const heightPct = Math.max(0.5, bottom - top);
          // First band (aggressive) gets a slightly stronger fill so
          // the user can eyeball band ordering without reading labels.
          const isAggressive = i === 0;
          return (
            <div
              key={i}
              title={`${b.label}: $${b.lo} – $${b.hi}`}
              style={{
                position: 'absolute',
                left: '4%',
                right: '20%',
                top: `${top}%`,
                height: `${heightPct}%`,
                background: isAggressive ? 'rgba(194,239,80,0.30)' : 'rgba(194,239,80,0.18)',
                border: '1px solid rgba(194,239,80,0.6)',
                borderRadius: 3,
                display: 'flex',
                alignItems: 'center',
                paddingLeft: 8,
                fontSize: '0.7rem',
                color: '#c2ef50',
                fontWeight: 600,
              }}
            >
              {b.label} · ${b.lo}–${b.hi}
            </div>
          );
        })}

        {/* Current-price line — dashed white-ish so it reads across
            the green bands. Only rendered when currentPrice is known. */}
        {currentPrice != null && range && (
          <div
            title={`Current: $${currentPrice.toFixed(2)}`}
            style={{
              position: 'absolute',
              left: 0,
              right: '20%',
              top: `${priceToPct(currentPrice)}%`,
              borderTop: '2px dashed rgba(255,255,255,0.7)',
              transform: 'translateY(-1px)',
            }}
          >
            <span style={{
              position: 'absolute',
              right: -56,
              top: -10,
              fontSize: '0.7rem',
              fontFamily: 'monospace',
              color: '#fff',
              background: 'rgba(0,0,0,0.6)',
              padding: '1px 4px',
              borderRadius: 2,
              whiteSpace: 'nowrap',
            }}>
              ${currentPrice.toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {/* Compact table for accessibility / copy-paste. The visualization
          above carries the visual signal; this is the "give me numbers"
          fallback for screen readers and anyone planning to type these
          into a broker's order ticket. */}
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.2rem', fontSize: '0.78rem' }}>
        {data.bands.map((b, i) => {
          const inZone = currentPrice != null && currentPrice >= b.lo && currentPrice <= b.hi;
          return (
            <li
              key={i}
              style={{
                display: 'grid',
                gridTemplateColumns: '8rem 1fr auto',
                gap: '0.5rem',
                alignItems: 'baseline',
                padding: '2px 4px',
                background: inZone ? 'rgba(194,239,80,0.08)' : undefined,
                borderRadius: 3,
              }}
            >
              <span style={{ color: '#c2ef50', textTransform: 'uppercase', letterSpacing: '0.04em', fontSize: '0.7rem' }}>
                {b.label}
              </span>
              <span className="mono">${b.lo} — ${b.hi}</span>
              {inZone && (
                <span style={{ color: 'var(--positive)', fontSize: '0.7rem' }}>📍 you are here</span>
              )}
            </li>
          );
        })}
      </ul>

      <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.7rem', lineHeight: 1.5 }}>
        Levels sourced from{' '}
        <a href={data.attribution.url} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>
          {data.attribution.source}
        </a>{' '}
        by {data.attribution.author} ({data.attribution.license}). Snapshot {data.attribution.snapshot_date}.
        First band is the "aggressive" (closest-to-action) entry; deeper bands are progressively more conservative.
      </p>
    </section>
  );
}
