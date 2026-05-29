/* WhalesFlowModal — full institutional-flow drill-in for one ticker.
 *
 * The SEPA card chip ("🐋 Balanced (5↑/6↓)") used to be hover-only and
 * showed just `top_buy` + `top_sell` — one fund per side. Mobile users
 * couldn't hover and even desktop users wanted the rest of the list.
 * This modal fetches the per-ticker /supply-demand/whales/{ticker}
 * endpoint, which returns the top 10 buyers + top 10 sellers with
 * pct_change, and renders them side by side.
 *
 * Data is 13F-filing-based and runs ~45 days behind quarter-end —
 * disclosed prominently in the footer so the user doesn't read it
 * as today's flow.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';
import { patchWhalesFlowRow } from '../hooks/useWhalesFlow';

type Mover = {
  holder:     string;
  pct_change: number;     // 0.15 = +15%, -0.20 = −20%
  type?:      string | null;
};

type WhalesPayload = {
  ticker?:   string;
  cached_at?: number | null;
  generated_at?: number | null;
  major?: {
    institutional_pct?: string | number | null;
    insider_pct?:       string | number | null;
    n_institutions?:    number | null;
  };
  moves?: {
    net_signal:   'accumulating' | 'distributing' | 'balanced';
    n_buying:     number;
    n_selling:    number;
    n_unchanged?: number;
    notable_buys:  Mover[];
    notable_sells: Mover[];
  };
  // Aggregated 13F filing timeline — dominant period_of_report across
  // funds, plus earliest/latest span so a stale outlier is visible.
  period?: {
    dominant:       string;  // "2026-03-31"
    earliest:       string;
    latest:         string;
    quarter_label?: string | null;  // "Q1 2026"
    human?:         string;  // "As of Q1 2026 (Mar 31, 2026)"
    n_dates?:       number;
  } | null;
};

/** Format a pct_change like 0.234 → "+23.4%" (or "−12.5%"). Capped at
 *  4 chars on the integer side so weird outliers don't break the layout. */
function fmtPct(p: number): string {
  if (!isFinite(p)) return '—';
  const sign = p >= 0 ? '+' : '−';
  const pct = Math.abs(p) * 100;
  return `${sign}${pct.toFixed(pct >= 100 ? 0 : 1)}%`;
}

/** A single buyer-or-seller row.
 *
 *  Layout uses CSS Grid inside the <li> instead of flex because:
 *  - `minmax(0, 1fr)` on the name column explicitly allows shrinkage
 *    BELOW the content's natural width (flex's default min-width: auto
 *    refuses to shrink past min-content, which with `white-space: nowrap`
 *    means the full text width — pushing the percentage off-screen).
 *  - `auto` on the percentage column gives it intrinsic width so it
 *    always renders even when the name is gigantic.
 *
 *  The type label ("(index_giant)" / "(other)") was inline before; moved
 *  to a block-level second line so a long holder name doesn't fight it
 *  for the same row. Cleaner stacking on narrow viewports.
 */
function MoverRow({ mover: m, tone }: { mover: Mover; tone: 'buy' | 'sell' }) {
  const isBuy = tone === 'buy';
  return (
    <li
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) auto',
        columnGap: '0.5rem',
        alignItems: 'baseline',
        padding: '0.4rem 0.55rem',
        background: isBuy ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)',
        border: `1px solid ${isBuy ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
        borderRadius: 4,
        fontSize: '0.82rem',
        minWidth: 0,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {m.holder}
        </div>
        {m.type && (
          <div style={{
            color: 'var(--cm-slate)',
            fontSize: '0.66rem',
            marginTop: 1,
          }}>
            ({m.type})
          </div>
        )}
      </div>
      <strong
        className="mono"
        style={{
          color: isBuy ? 'var(--positive)' : 'var(--negative)',
          whiteSpace: 'nowrap',
          // Pin to top of the row so when the type label adds a second
          // line under the name, the percentage doesn't drift down with
          // the baseline.
          alignSelf: 'start',
          lineHeight: 1.3,
        }}
      >
        {fmtPct(m.pct_change)}
      </strong>
    </li>
  );
}

export function WhalesFlowModal({
  symbol,
  onClose,
}: {
  symbol: string;
  onClose: () => void;
}) {
  const [data,    setData]    = useState<WhalesPayload | null>(null);
  const [err,     setErr]     = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/supply-demand/whales/${encodeURIComponent(symbol)}`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((j) => {
        if (cancelled) return;
        setData(j);
        setLoading(false);
        // The per-ticker endpoint silently refreshes the Mongo cache
        // when it's >24h old. Patch the shared map so the SEPA card
        // chip behind this modal reflects the freshly-pulled numbers
        // instead of whatever it showed when the page first loaded.
        // Without this, the user sees the staleness reported by the
        // user on 2026-05-21 (card said "2/2 balanced, top sell
        // JPMORGAN" while modal showed "6 buying / 1 selling, JPMORGAN
        // +16%").
        const m = j?.moves || {};
        const notableBuys  = m.notable_buys  || [];
        const notableSells = m.notable_sells || [];
        patchWhalesFlowRow(symbol, {
          ticker:      symbol.toUpperCase(),
          signal:      m.net_signal || 'balanced',
          n_buying:    m.n_buying ?? 0,
          n_selling:   m.n_selling ?? 0,
          n_unchanged: m.n_unchanged,
          top_buy:     notableBuys[0]?.holder ?? null,
          top_sell:    notableSells[0]?.holder ?? null,
        });
      })
      .catch((e) => { if (!cancelled) { setErr(String(e?.message || e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [symbol]);

  // Close on Escape so keyboard users can dismiss without reaching for the X.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const moves = data?.moves;
  const signal = moves?.net_signal;
  const signalLabel =
    signal === 'accumulating' ? '🟢 ACCUMULATING' :
    signal === 'distributing' ? '🔴 DISTRIBUTING' :
    signal === 'balanced'     ? '⚪️ BALANCED' :
    '';
  const cachedAtIso = data?.cached_at ? new Date(data.cached_at * 1000).toLocaleDateString() : null;

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '1rem', overflowY: 'auto',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
          border: '1px solid var(--rule, #333)', borderRadius: 8,
          // Explicit responsive cap — never overflows the viewport even
          // on the smallest phones. The outer padding (1rem on the
          // overlay) is accounted for via calc.
          width: '100%',
          maxWidth: 'min(720px, calc(100vw - 2rem))',
          maxHeight: '90vh', overflow: 'auto',
          // Tighter horizontal padding so the two columns get more
          // breathing room — was 1.3rem each side; now 1rem on phones.
          padding: '1.1rem clamp(0.8rem, 3vw, 1.3rem)',
          // Keep the grid children from spilling out — Safari needs
          // this explicit minWidth: 0 on the flex/grid container too.
          minWidth: 0,
        }}
      >
        <header style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'baseline', marginBottom: '0.5rem', gap: '0.4rem', flexWrap: 'wrap',
        }}>
          <div>
            <div className="eyebrow">🐋 Institutional flow · 13F filings</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>
              {symbol}{' '}
              {signalLabel && (
                <span style={{ fontSize: '0.78rem', marginLeft: '0.4rem', color: 'var(--cm-slate)' }}>
                  {signalLabel}
                </span>
              )}
            </h2>
            {moves && (
              <p style={{ fontSize: '0.78rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0' }}>
                {moves.n_buying} buying · {moves.n_selling} selling
                {moves.n_unchanged ? ` · ${moves.n_unchanged} unchanged` : ''}
                {data?.major?.n_institutions
                  ? `  (out of ${data.major.n_institutions} reporting funds)` : ''}
              </p>
            )}
            {data?.period?.human && (
              <p
                style={{ fontSize: '0.74rem', color: 'var(--cm-slate)', margin: '0.25rem 0 0', opacity: 0.85 }}
                title={`Earliest filing in this snapshot: ${data.period.earliest}  ·  latest: ${data.period.latest}`}
              >
                📅 {data.period.human}
                {data.period.earliest !== data.period.latest && (
                  <span style={{ marginLeft: '0.4rem' }}>
                    · filings span {data.period.earliest} → {data.period.latest}
                  </span>
                )}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none', border: 0, color: 'var(--cm-slate)',
              cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1,
            }}
          >×</button>
        </header>

        {/* Major-holder summary chips — institutional %, insider %, fund count */}
        {data?.major && (data.major.institutional_pct || data.major.insider_pct) && (
          <div style={{
            display: 'flex', gap: '0.6rem', flexWrap: 'wrap',
            fontSize: '0.78rem', marginBottom: '0.7rem',
            color: 'var(--cm-slate)',
          }}>
            {data.major.institutional_pct && (
              <span>Institutional held: <strong style={{ color: 'var(--ink)' }}>{String(data.major.institutional_pct)}</strong></span>
            )}
            {data.major.insider_pct && (
              <span>· Insider: <strong style={{ color: 'var(--ink)' }}>{String(data.major.insider_pct)}</strong></span>
            )}
          </div>
        )}

        {loading && <div style={{ color: 'var(--cm-slate)', marginTop: '0.5rem' }}>Loading 13F filings…</div>}

        {err && (
          <div style={{
            padding: '0.5rem 0.7rem', marginTop: '0.4rem',
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 4, color: 'var(--negative)', fontSize: '0.85rem',
          }}>
            Failed to load whales data: {err}
          </div>
        )}

        {/* Two columns: buyers + sellers. Grid for desktop, stacks
            naturally on narrow phones via the `repeat(auto-fit, …)`
            wrap-down behavior. */}
        {moves && (
          <div style={{
            marginTop: '0.6rem',
            display: 'grid',
            // 240px min lets the two columns coexist down to ~530px
            // total container width; on phones the grid collapses to
            // one column (sells stacks below buys). Was 280px which
            // forced both columns to stay side-by-side even on narrow
            // viewports, creating overflow.
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '0.9rem',
          }}>
            {/* ── Buyers ─────────────────────────────────────────── */}
            <section style={{ minWidth: 0 }}>
              <div className="eyebrow" style={{ color: 'var(--positive)', marginBottom: '0.4rem' }}>
                ▲ BUYING — {moves.n_buying} funds
              </div>
              {moves.notable_buys.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)' }}>
                  No funds increased their position &gt;10% this filing cycle.
                </p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.3rem' }}>
                  {moves.notable_buys.map((m, i) => (
                    <MoverRow key={`buy-${i}-${m.holder}`} mover={m} tone="buy" />
                  ))}
                </ul>
              )}
            </section>

            {/* ── Sellers ─────────────────────────────────────────── */}
            <section style={{ minWidth: 0 }}>
              <div className="eyebrow" style={{ color: 'var(--negative)', marginBottom: '0.4rem' }}>
                ▼ SELLING — {moves.n_selling} funds
              </div>
              {moves.notable_sells.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)' }}>
                  No funds reduced their position &gt;10% this filing cycle.
                </p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.3rem' }}>
                  {moves.notable_sells.map((m, i) => (
                    <MoverRow key={`sell-${i}-${m.holder}`} mover={m} tone="sell" />
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}

        {/* Disclaimer / freshness — 13F data is QUARTERLY and filed
            up to 45 days after quarter end, so even fresh data is
            describing positions that may be 1-4 months old by the
            time the user reads it. Surface this prominently so the
            "balanced" signal isn't misread as "real-time flow". */}
        <p style={{
          fontSize: '0.66rem', color: 'var(--cm-slate)',
          marginTop: '1rem', lineHeight: 1.55,
        }}>
          <strong>What this is:</strong> 13F filings show what institutions held at the
          <em> end</em> of last quarter, filed within 45 days. A "buying" fund increased its
          position by &gt;10%; "selling" reduced by &gt;10%; "unchanged" is anything between
          those bands. Doesn't capture mid-quarter trades or short positions.
          <br />
          <strong>How to read "balanced":</strong> it means roughly equal numbers of large
          funds opened/grew vs trimmed/exited. It's not "no one's trading"; it's "the smart
          money disagrees right now."
          {cachedAtIso && <> · Cached {cachedAtIso}.</>}
        </p>
      </div>
    </div>,
    document.body,
  );
}
