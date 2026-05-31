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
import { useEffect, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';
import { patchWhalesFlowRow } from '../hooks/useWhalesFlow';
// Curated fund-credibility tier list — added 2026-05-28 per user
// request to distinguish smart-money active managers (Tiger, Coatue,
// Berkshire) from passive index giants (Vanguard) and unknown LPs.
// Edit src/lib/fundTiers.ts to add/remove funds.
import {
  getFundTier,
  fundScore,
  fundDollarsAdded,
  fmtPositionValue,
  fmtPctHeld,
  fmtDeltaUSD,
  TIER_EMOJI,
  TIER_LABEL,
  type FundTierInfo,
} from '../lib/fundTiers';

type Mover = {
  holder:     string;
  pct_change: number;     // 0.15 = +15%, -0.20 = −20%
  type?:      string | null;
  // Added 2026-05-28 alongside the fund-credibility tier feature.
  // value    = dollar value of this fund's position in this stock
  // pct_held = % of the stock's float this fund holds (0.025 = 2.5%)
  // Both are forwarded by backend supply_demand/whales.py · _summarize_moves.
  // Optional — older cached responses won't have them; chip degrades.
  value?:     number | null;
  pct_held?:  number | null;
};

type WhalesPayload = {
  ticker?:   string;
  cached_at?: number | null;
  generated_at?: number | null;
  // Count of institutional holders returned by this fetch. 0 = empty/failed
  // fetch (used to avoid clobbering the card chip with a false 0/0).
  n_holders?: number | null;
  // Set when the backend served the last GOOD snapshot because the latest
  // yfinance refresh came back empty (foreign-ADR / transient flakiness).
  _stale_empty_refetch?: boolean;
  _stale_note?: string;
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
  // Look up the curated fund tier once per row. Returns null for funds
  // not on the smart-money / index-giant lists in src/lib/fundTiers.ts
  // — those rows render with no badge, just the bare holder name.
  const tier: FundTierInfo | null = useMemo(() => getFundTier(m.holder), [m.holder]);
  const positionStr = fmtPositionValue(m.value);
  const concentrationStr = fmtPctHeld(m.pct_held);
  // $ deployed last quarter — the headline number per user feedback
  // 2026-05-28 ("add total volume of these investments instead of
  // percentage"). Falls back to null when backend value is missing.
  const dollarsAdded = fundDollarsAdded(m.value, m.pct_change);
  const dollarsAddedStr = dollarsAdded != null ? fmtDeltaUSD(dollarsAdded) : null;
  const tierBadge = tier ? TIER_EMOJI[tier.tier as 'S' | 'A' | 'B'] : null;
  const tierLabel = tier ? TIER_LABEL[tier.tier as 'S' | 'A' | 'B'] : null;
  // Build a rich title (tooltip) so hovering the row explains exactly
  // what the badge means + the honesty caveat (Tier S ≠ "will be right
  // on this stock"; Tier B ≠ "bad signal", just mandate-driven).
  const titleParts: string[] = [];
  if (tier) {
    titleParts.push(`${tierBadge} ${tierLabel}`);
    if (tier.manager) titleParts.push(`  ${tier.display} · ${tier.manager}`);
    else              titleParts.push(`  ${tier.display}`);
  }
  if (dollarsAddedStr)          titleParts.push(`${isBuy ? 'Bought' : 'Sold'} last quarter: ${dollarsAddedStr}`);
  if (positionStr !== '—')      titleParts.push(`Current position: ${positionStr}`);
  if (concentrationStr !== '—') titleParts.push(`% of float: ${concentrationStr}`);
  titleParts.push(`Position change: ${fmtPct(m.pct_change)}`);
  if (m.type)                   titleParts.push(`Backend tag: ${m.type}`);
  titleParts.push('');
  titleParts.push('Tier S/A reflects the fund\'s historical reputation for active stock-picking — NOT a forward prediction that they\'re right on this stock. Tier B "index giant" buys due to mandate, not conviction.');
  const tooltip = titleParts.join('\n');
  return (
    <li
      title={tooltip}
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
          display: 'flex',
          gap: 4,
          alignItems: 'baseline',
        }}>
          {tierBadge && (
            <span style={{
              fontSize: '0.72rem',
              flexShrink: 0,
              opacity: 0.95,
            }}>{tierBadge}</span>
          )}
          <span style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>{m.holder}</span>
        </div>
        {/* Second line: type + (when $ headline is shown) the % change
            + current position + concentration. Compact even with all
            four present. */}
        <div style={{
          color: 'var(--cm-slate)',
          fontSize: '0.66rem',
          marginTop: 1,
          display: 'flex',
          gap: 6,
          flexWrap: 'wrap',
        }}>
          {m.type && <span>({m.type})</span>}
          {dollarsAddedStr && (
            // Only show % change as secondary when $ delta is the headline.
            // Otherwise % change IS the headline and would be redundant here.
            <span style={{ fontFamily: '"SF Mono", Menlo, monospace' }}>
              {fmtPct(m.pct_change)} qoq
            </span>
          )}
          {positionStr !== '—' && (
            <span style={{
              color: 'var(--ink-body, #c7c9d1)',
              fontFamily: '"SF Mono", Menlo, monospace',
            }}>· {positionStr} position</span>
          )}
          {concentrationStr !== '—' && (
            <span style={{
              fontFamily: '"SF Mono", Menlo, monospace',
            }}>· {concentrationStr} float</span>
          )}
        </div>
      </div>
      {/* Headline number — $ deployed when we have it, falls back to %
          change when backend hasn't shipped value/pct_held yet. */}
      <strong
        className="mono"
        style={{
          color: isBuy ? 'var(--positive)' : 'var(--negative)',
          whiteSpace: 'nowrap',
          alignSelf: 'start',
          lineHeight: 1.3,
        }}
      >
        {dollarsAddedStr ?? fmtPct(m.pct_change)}
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
        // Only sync the card chip when this per-ticker fetch actually
        // returned institutional data. A transient empty/failed fetch (no
        // holders, no moves) used to clobber a CORRECT bulk value — e.g. a
        // "🐋 Accumulating +9" chip collapsing to "Balanced 0/0" the moment
        // the modal opened ("the 9 goes away after clicking", user
        // 2026-05-30). Heavier 13F load under the broad universe makes those
        // empty fetches more frequent. When the fetch is empty we leave the
        // bulk chip untouched rather than overwrite good data with zeros.
        const fetchHasData =
          (j?.n_holders ?? 0) > 0 ||
          (m.n_buying ?? 0) > 0 || (m.n_selling ?? 0) > 0 ||
          (m.n_unchanged ?? 0) > 0 ||
          notableBuys.length > 0 || notableSells.length > 0;
        if (fetchHasData) {
          patchWhalesFlowRow(symbol, {
            ticker:      symbol.toUpperCase(),
            signal:      m.net_signal || 'balanced',
            n_buying:    m.n_buying ?? 0,
            n_selling:   m.n_selling ?? 0,
            n_unchanged: m.n_unchanged,
            top_buy:     notableBuys[0]?.holder ?? null,
            top_sell:    notableSells[0]?.holder ?? null,
          });
        }
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
  // True only when this fetch returned real institutional data. Distinguishes
  // "genuinely balanced / no movers" from "the fetch came back empty"
  // (yfinance returned nothing). When empty we don't assert a BALANCED verdict
  // — that's what was contradicting the card chip.
  const hasData = !!data && (
    (data.n_holders ?? 0) > 0 ||
    (moves?.n_buying ?? 0) > 0 || (moves?.n_selling ?? 0) > 0 ||
    (moves?.n_unchanged ?? 0) > 0 ||
    (moves?.notable_buys?.length ?? 0) > 0 || (moves?.notable_sells?.length ?? 0) > 0
  );
  const signal = hasData ? moves?.net_signal : undefined;
  const signalLabel =
    signal === 'accumulating' ? '🟢 ACCUMULATING' :
    signal === 'distributing' ? '🔴 DISTRIBUTING' :
    signal === 'balanced'     ? '⚪️ BALANCED' :
    '';
  const cachedAtIso = data?.cached_at ? new Date(data.cached_at * 1000).toLocaleDateString() : null;

  // ── $ totals across buyers / sellers — user request 2026-05-28
  //    "add total volume of these investments instead of percentage".
  //    Aggregates the per-fund dollars-added estimate so the header
  //    shows "Net inflow: +$11.2B from 15 funds" instead of just
  //    counts. When backend hasn't shipped value yet, sums collapse
  //    to 0 and the UI falls back to fund counts only.
  const totals = useMemo(() => {
    if (!moves) return { buyUSD: 0, sellUSD: 0, buyCovered: 0, sellCovered: 0 };
    let buyUSD = 0, sellUSD = 0, buyCovered = 0, sellCovered = 0;
    for (const m of moves.notable_buys || []) {
      const d = fundDollarsAdded(m.value, m.pct_change);
      if (d != null) { buyUSD += d; buyCovered += 1; }
    }
    for (const m of moves.notable_sells || []) {
      const d = fundDollarsAdded(m.value, m.pct_change);
      // sells produce a NEGATIVE delta naturally (pct_change < 0);
      // convert to a positive "magnitude sold" for display.
      if (d != null) { sellUSD += Math.abs(d); sellCovered += 1; }
    }
    return { buyUSD, sellUSD, buyCovered, sellCovered };
  }, [moves]);
  const netUSD = totals.buyUSD - totals.sellUSD;
  const hasUSDData = totals.buyCovered > 0 || totals.sellCovered > 0;

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
            {!loading && !err && !hasData && (
              <p style={{ fontSize: '0.75rem', color: 'var(--cm-amber, #d97706)', margin: '0.3rem 0 0' }}>
                No fresh 13F holder data returned for {symbol} right now — the card
                chip keeps its last cached reading rather than resetting to 0/0.
              </p>
            )}
            {!loading && !err && hasData && data?._stale_empty_refetch && (
              <p style={{ fontSize: '0.72rem', color: 'var(--cm-amber, #d97706)', margin: '0.3rem 0 0' }}>
                ⓘ {data._stale_note || 'Showing the last good 13F snapshot — the latest refresh came back empty.'}
              </p>
            )}
            {hasData && moves && (
              <p style={{ fontSize: '0.78rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0' }}>
                {moves.n_buying} buying · {moves.n_selling} selling
                {moves.n_unchanged ? ` · ${moves.n_unchanged} unchanged` : ''}
                {data?.major?.n_institutions
                  ? `  (out of ${data.major.n_institutions} reporting funds)` : ''}
              </p>
            )}
            {/* $ totals line — shows the actual capital deployed last
                quarter when backend ships value/pct_held. Falls back
                silently when the data isn't there yet (backend not
                rebuilt, or yfinance didn't return value for any holder). */}
            {moves && hasUSDData && (
              <p
                style={{
                  fontSize: '0.82rem',
                  margin: '0.35rem 0 0',
                  fontFamily: '"SF Mono", Menlo, monospace',
                  lineHeight: 1.45,
                }}
                title={
                  `Estimated capital deployed last quarter (sum of per-fund position change in $).\n\n` +
                  `Formula: ΔPosition ≈ current_value × pct_change / (1 + pct_change)\n\n` +
                  `Coverage: ${totals.buyCovered}/${moves.notable_buys.length} buyers, ` +
                  `${totals.sellCovered}/${moves.notable_sells.length} sellers had reportable position values. ` +
                  `Funds with missing value are excluded from the sum.`
                }
              >
                <span style={{ color: 'var(--positive)' }}>
                  +{fmtDeltaUSD(totals.buyUSD).replace('+', '')} bought
                </span>
                {totals.sellUSD > 0 && (
                  <>
                    {' · '}
                    <span style={{ color: 'var(--negative)' }}>
                      −{fmtDeltaUSD(totals.sellUSD).replace('+', '')} sold
                    </span>
                  </>
                )}
                {' · '}
                <strong style={{
                  color: netUSD >= 0 ? 'var(--positive)' : 'var(--negative)',
                }}>
                  Net {netUSD >= 0 ? 'inflow' : 'outflow'}: {fmtDeltaUSD(netUSD)}
                </strong>
              </p>
            )}
            {/* 13F filing timeline — dominant period + span across funds.
                Cherry-picked from feat/whales-modal-timeline 2026-05-30. */}
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

        {/* Banner shown when no row in either list has a usable
            position value — typically means the backend container still
            has the pre-2026-05-28 image that didn't forward value /
            pct_held. Rebuild the api container to populate. */}
        {moves && !hasUSDData &&
         ((moves.notable_buys || []).length + (moves.notable_sells || []).length) > 0 && (
          <div style={{
            marginTop: '0.5rem',
            padding: '0.4rem 0.6rem',
            background: 'rgba(212,168,95,0.08)',
            border: '1px solid rgba(212,168,95,0.25)',
            borderRadius: 4,
            fontSize: '0.72rem',
            color: 'var(--gold, #d4a85f)',
            lineHeight: 1.45,
          }}>
            <strong>$ totals unavailable.</strong> Per-fund position values not in this
            payload — most likely the api container needs a rebuild to ship the
            additive whales-payload change from 2026-05-28. Falling back to
            % change. Run <code style={{ fontSize: '0.92em' }}>docker compose build api &amp;&amp; docker compose up -d --force-recreate api</code> to enable totals.
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
              <div
                className="eyebrow"
                style={{ color: 'var(--positive)', marginBottom: '0.4rem' }}
                title={hasUSDData
                  ? `${totals.buyCovered} of ${moves.notable_buys.length} listed buyers had reportable position values. Total = ${fmtDeltaUSD(totals.buyUSD)}.`
                  : `Position-value data not yet available. Showing buy count only.`}
              >
                ▲ BUYING — {moves.n_buying} funds
                {hasUSDData && totals.buyUSD > 0 && (
                  <span style={{
                    marginLeft: '0.5rem',
                    fontFamily: '"SF Mono", Menlo, monospace',
                    fontSize: '0.85em',
                  }}>
                    · {fmtDeltaUSD(totals.buyUSD)} total
                  </span>
                )}
              </div>
              {moves.notable_buys.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)' }}>
                  No funds increased their position &gt;10% this filing cycle.
                </p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.3rem' }}>
                  {/* Sorted by composite credibility score
                      (tier × log10(position $) × concentration). When
                      backend hasn't shipped value/pct_held yet, score
                      collapses to tier only — Tier S/A funds still
                      float to top of their respective lists. */}
                  {[...moves.notable_buys]
                    .sort((a, b) => {
                      const tA = getFundTier(a.holder)?.tier ?? null;
                      const tB = getFundTier(b.holder)?.tier ?? null;
                      return fundScore(b.value, b.pct_held, tB) -
                             fundScore(a.value, a.pct_held, tA);
                    })
                    .map((m, i) => (
                      <MoverRow key={`buy-${i}-${m.holder}`} mover={m} tone="buy" />
                  ))}
                </ul>
              )}
            </section>

            {/* ── Sellers ─────────────────────────────────────────── */}
            <section style={{ minWidth: 0 }}>
              <div
                className="eyebrow"
                style={{ color: 'var(--negative)', marginBottom: '0.4rem' }}
                title={hasUSDData
                  ? `${totals.sellCovered} of ${moves.notable_sells.length} listed sellers had reportable position values. Total = ${fmtDeltaUSD(totals.sellUSD)}.`
                  : `Position-value data not yet available. Showing sell count only.`}
              >
                ▼ SELLING — {moves.n_selling} funds
                {hasUSDData && totals.sellUSD > 0 && (
                  <span style={{
                    marginLeft: '0.5rem',
                    fontFamily: '"SF Mono", Menlo, monospace',
                    fontSize: '0.85em',
                  }}>
                    · −{fmtDeltaUSD(totals.sellUSD).replace('+', '')} total
                  </span>
                )}
              </div>
              {moves.notable_sells.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)' }}>
                  No funds reduced their position &gt;10% this filing cycle.
                </p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.3rem' }}>
                  {[...moves.notable_sells]
                    .sort((a, b) => {
                      const tA = getFundTier(a.holder)?.tier ?? null;
                      const tB = getFundTier(b.holder)?.tier ?? null;
                      return fundScore(b.value, b.pct_held, tB) -
                             fundScore(a.value, a.pct_held, tA);
                    })
                    .map((m, i) => (
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
          <br />
          {/* Fund-tier legend — added 2026-05-28. Curated list in
              src/lib/fundTiers.ts. The honesty caveat is critical:
              Tier S/A is BACKWARD-LOOKING reputation, not a forward
              prediction. Tier B (Vanguard etc.) is mandate-driven flow,
              not a "bad" signal — just a different KIND of signal. */}
          <strong>Fund tiers:</strong>{' '}
          <span title="Legendary stock-picker with a long track record of active alpha">⭐⭐⭐ legendary stock-picker</span>
          {' · '}
          <span title="Well-known active mutual-fund manager">⭐⭐ active alpha-seeker</span>
          {' · '}
          <span title="Index giant — buys due to index inclusion mandate, not conviction">🏛 index giant (mandate)</span>
          {' · '}
          <em>no badge = not on the curated list.</em>{' '}
          Tier is the fund's <em>historical</em> reputation for active stock-picking, NOT
          a forward prediction that they'll be right on this stock. Lists are sorted by
          composite credibility = tier × log(position $) × concentration. Edit{' '}
          <code style={{ fontSize: '0.85em' }}>src/lib/fundTiers.ts</code> to add/remove funds.
          {cachedAtIso && <> · Cached {cachedAtIso}.</>}
        </p>
      </div>
    </div>,
    document.body,
  );
}
