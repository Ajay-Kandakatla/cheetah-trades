/* TapePanel — order-flow analytics for one ticker (the Tape tab).
 *
 * Raw prints → buy/sell tick-rule classification → cumulative delta, big
 * prints, trade-flash bursts, session volume profile (the honest bookmap
 * substitute), intraday EMAs, zones + GEX context — and the deterministic
 * BUY / WAIT / AVOID checklist. Every concept carries an ⓘ explainer
 * (Ajay 2026-07-06: "I do not entirely understand what these are").
 *
 * Honest by design: tick rule ≈75-80% of the quote rule; no Level-2 feed so
 * no bookmap; the accuracy strip shows OUR measured record, not the WhatsApp
 * group's 70%. Reads /orderflow/{sym}; Scan POSTs a fresh compute. */
import { useEffect, useRef } from 'react';
import { useOrderflow } from '../hooks/useOrderflow';
import { InfoButton } from './InfoButton';
import {
  accuracyLine, deltaTone, fmtDollars, fmtShares, sparklinePoints, verdictView,
} from '../lib/orderflow';
import type { TapeData } from '../lib/orderflow';

const CARD: React.CSSProperties = {
  padding: '0.8rem 1rem',
  background: 'rgba(255,255,255,0.02)',
  border: '1px solid rgba(255,255,255,0.10)',
  borderRadius: 8,
  marginTop: '1rem',
};

function Tile({ label, value, sub, color, info }: {
  label: string; value: string; sub?: string; color?: string; info?: React.ReactNode;
}) {
  return (
    <div style={{ padding: '0.45rem 0.65rem', background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6, minWidth: 118, position: 'relative' }}>
      <div style={{ fontSize: '0.63rem', color: 'var(--cm-slate,#9ca3af)', textTransform: 'uppercase',
        letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: 4 }}>
        {label}{info}
      </div>
      <div className="mono" style={{ fontSize: '1rem', fontWeight: 800, color: color ?? '#e5e7eb', marginTop: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

function DeltaSparkline({ series }: { series: [string, number][] }) {
  const pts = sparklinePoints(series);
  if (pts.length < 2) return null;
  const W = 620, H = 90, P = 6;
  const lo = Math.min(0, ...pts), hi = Math.max(0, ...pts);
  const span = hi - lo || 1;
  const x = (i: number) => P + (i / (pts.length - 1)) * (W - 2 * P);
  const y = (v: number) => P + (1 - (v - lo) / span) * (H - 2 * P);
  const line = pts.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  const color = last > 0 ? '#10b981' : last < 0 ? '#ef4444' : '#9ca3af';
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Cumulative delta through the session" style={{ display: 'block', marginTop: '0.4rem' }}>
      <line x1={P} y1={y(0)} x2={W - P} y2={y(0)} stroke="var(--hairline,#2a2a2a)" strokeDasharray="3 3" />
      <path d={line} fill="none" stroke={color} strokeWidth="1.8" />
      <circle cx={x(pts.length - 1)} cy={y(last)} r={3} fill={color} />
      <text x={W - P} y={y(last) - 6} textAnchor="end" fontSize="10" fontWeight={700} fill={color}>{fmtShares(last)}</text>
    </svg>
  );
}

const SIDE_CHIP: Record<string, { label: string; color: string }> = {
  buy: { label: 'BUY', color: '#10b981' },
  sell: { label: 'SELL', color: '#ef4444' },
  unknown: { label: '—', color: '#9ca3af' },
};

export function TapePanel({ symbol }: { symbol: string }) {
  const { data, loading, scanning, scan, accuracy } = useOrderflow(symbol);

  // First visit for a ticker → scan automatically, nobody hunts for a button
  // (Ajay 2026-07-06: "How do I scan this?"). Once per symbol per mount, so a
  // failed scan (found:false) shows its message instead of looping.
  const autoScanned = useRef<string | null>(null);
  useEffect(() => {
    if (data && !data.found && !scanning && autoScanned.current !== symbol) {
      autoScanned.current = symbol;
      scan();
    }
  }, [data, scanning, scan, symbol]);

  if (loading && !data) {
    return <section style={CARD}><Eyebrow /><p className="sepa-empty">Loading tape snapshot…</p></section>;
  }

  const scanBtn = (
    <button className="btn" onClick={scan} disabled={scanning}
      style={{ padding: '0.35rem 0.9rem', fontSize: '0.8rem' }}>
      {scanning ? 'Reading the tape… (a few seconds; up to ~30s on megacaps)' : `Scan tape for ${symbol}`}
    </button>
  );

  if (!data || !data.found) {
    return (
      <section style={CARD}>
        <Eyebrow />
        <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)', margin: '0.4rem 0 0.6rem' }}>
          {data?.message ?? `No tape snapshot yet for ${symbol}.`} The scan pulls every print of the
          most recent session from Massive and classifies each one buyer- vs seller-aggressive.
        </p>
        {scanBtn}
      </section>
    );
  }

  const d = data as TapeData;
  const vv = verdictView(d.verdict);
  const delta = d.tape?.delta;
  const tone = deltaTone(delta?.delta ?? 0);
  const prints = d.tape?.big_prints;
  const bursts = d.tape?.bursts ?? [];
  const accLine = accuracyLine(accuracy);

  return (
    <section style={CARD}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.6rem', flexWrap: 'wrap' }}>
        <Eyebrow />
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {d.stale && <span style={{ fontSize: '0.68rem', color: '#f59e0b' }}>snapshot from {d.et_date} — rescan for fresh</span>}
          {scanBtn}
        </div>
      </div>

      {/* ── The verdict + checklist ─────────────────────────────────────── */}
      <div style={{ marginTop: '0.7rem', padding: '0.7rem 0.85rem', borderRadius: 8,
        background: vv.bg, border: `1px solid ${vv.color}55` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '1.05rem', fontWeight: 800, color: vv.color }}>{vv.icon} {vv.label}</span>
          <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--cm-slate)' }}>
            {d.checks_passed}/{d.checks_total} checks · {d.et_date}{d.thin_tape ? ' · thin tape' : ''}
          </span>
          <InfoButton title="How this verdict is decided" inline align="left">
            <p>A <strong>fixed checklist</strong> — the same five rules every time, no discretion (that's the "deterministic" part):</p>
            <ol style={{ paddingLeft: '1.1rem' }}>
              <li><strong>Daily uptrend</strong> — the gate. If the daily SEPA trend fails, the verdict can <em>never</em> be BUY. This page never fights your main system.</li>
              <li><strong>Intraday EMAs</strong> — 9 above 21 on 5-min bars, price above the 21.</li>
              <li><strong>Delta</strong> — buyers in control for the session AND the last 30 minutes.</li>
              <li><strong>Big prints</strong> — institutional-size trades lean ≥1.25× to the buy side.</li>
              <li><strong>Zone</strong> — price at demand / clear runway; at overhead supply blocks BUY.</li>
            </ol>
            <p>BUY needs 1+2+3 plus (4 or 5). A fail on the gate → AVOID. Anything else → WAIT.
              Under 500 prints the tape is too thin to trust a BUY. Full spec: docs/sepa/orderflow_methodology.md.</p>
          </InfoButton>
        </div>
        <p style={{ margin: '0.35rem 0 0.5rem', fontSize: '0.8rem', color: 'var(--cm-text,#d1d5db)' }}>{d.reason}</p>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.3rem' }}>
          {(d.checks ?? []).map((c) => (
            <li key={c.key} style={{ fontSize: '0.78rem', display: 'flex', gap: '0.45rem', alignItems: 'baseline' }}>
              <span style={{ color: c.pass ? '#10b981' : '#ef4444', fontWeight: 800 }}>{c.pass ? '✓' : '✕'}</span>
              <span style={{ minWidth: 0 }}>
                <strong>{c.label}</strong>
                <span style={{ color: 'var(--cm-slate)' }}> — {c.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* ── Delta ───────────────────────────────────────────────────────── */}
      <div style={{ marginTop: '0.9rem' }}>
        <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Big delta · who's in control
          <InfoButton title="What is delta?" inline align="left">
            <p><strong>Delta = buy volume − sell volume.</strong> Every print is classified
              buyer-aggressive (lifted the offer) or seller-aggressive (hit the bid). Big positive
              delta = buyers doing the chasing; big negative = sellers.</p>
            <p>We classify with the <strong>tick rule</strong> (uptick = buy, downtick = sell) —
              the full quote-rule feed is 5-10× heavier. It agrees with the quote rule ~75-80% of
              the time, so treat delta as a strong estimate, not an exact count.</p>
            <p><strong>Last 30 min</strong> matters most — it's who's in control <em>right now</em>.</p>
          </InfoButton>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.4rem' }}>
          <Tile label="Session delta" value={fmtShares(delta?.delta)} color={tone.color}
            sub={`${delta?.delta_pct_of_volume ?? 0}% of volume · ${tone.word} in control`} />
          <Tile label={`Last ${delta?.late_window_min ?? 30} min`} value={fmtShares(delta?.late_delta)}
            color={deltaTone(delta?.late_delta ?? 0).color} sub="who's in control now" />
          <Tile label="Buy volume" value={fmtShares(delta?.buy_volume)} color="#10b981" />
          <Tile label="Sell volume" value={fmtShares(delta ? -Math.abs(delta.sell_volume) : null)} color="#ef4444" />
        </div>
        {delta?.series && <DeltaSparkline series={delta.series} />}
        {d.tape?.truncated && (
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.68rem', color: '#f59e0b' }}>
            ⚠️ Very heavy tape — analysis covers the first 1.2M prints of the session.
          </p>
        )}
      </div>

      {/* ── Big prints ──────────────────────────────────────────────────── */}
      <div style={{ marginTop: '0.9rem' }}>
        <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Big prints · institutional footprints
          <InfoButton title="What are prints?" inline align="left">
            <p>A <strong>print</strong> is one executed trade on the tape. Most are small retail
              orders; a <strong>big print</strong> (block) is a single trade large enough that it's
              almost certainly an institution — a fund can't buy 30,000 shares invisibly.</p>
            <p>We flag prints ≥ max($100k, the day's top 0.1% by dollar value) — adaptive, so a $40
              small-cap and NVDA both show sensible tapes. A session where the big prints lean
              heavily to the buy side = institutions accumulating.</p>
          </InfoButton>
        </div>
        {prints && prints.prints.length > 0 ? (
          <>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', margin: '0.4rem 0' }}>
              <Tile label="Big buy $" value={fmtDollars(prints.buy_dollars)} color="#10b981" />
              <Tile label="Big sell $" value={fmtDollars(prints.sell_dollars)} color="#ef4444" />
              <Tile label="Threshold" value={fmtDollars(prints.threshold_dollars)} sub="top 0.1% of today's prints" />
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="mono" style={{ fontSize: '0.74rem', borderCollapse: 'collapse', minWidth: 420 }}>
                <thead>
                  <tr style={{ color: 'var(--cm-slate)', textAlign: 'left' }}>
                    <th style={{ padding: '0.2rem 0.8rem 0.2rem 0' }}>time</th>
                    <th style={{ padding: '0.2rem 0.8rem 0.2rem 0' }}>side</th>
                    <th style={{ padding: '0.2rem 0.8rem 0.2rem 0' }}>size @ price</th>
                    <th style={{ padding: '0.2rem 0' }}>$</th>
                  </tr>
                </thead>
                <tbody>
                  {prints.prints.slice(0, 10).map((p, i) => {
                    const sc = SIDE_CHIP[p.side] ?? SIDE_CHIP.unknown;
                    return (
                      <tr key={i} style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '0.22rem 0.8rem 0.22rem 0', color: 'var(--cm-slate)' }}>{p.time_et}</td>
                        <td style={{ padding: '0.22rem 0.8rem 0.22rem 0', color: sc.color, fontWeight: 800 }}>{sc.label}</td>
                        <td style={{ padding: '0.22rem 0.8rem 0.22rem 0' }}>{p.size.toLocaleString()} @ ${p.price}</td>
                        <td style={{ padding: '0.22rem 0', fontWeight: 700 }}>{fmtDollars(p.dollars)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.76rem', color: 'var(--cm-slate)' }}>
            No institutional-size prints this session.
          </p>
        )}
      </div>

      {/* ── Trade flash ─────────────────────────────────────────────────── */}
      <div style={{ marginTop: '0.9rem' }}>
        <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Trade flash · urgency bursts
          <InfoButton title="What is a trade flash?" inline align="left">
            <p>A <strong>burst of rapid one-sided trades</strong> — ≥$250k and ≥15 prints inside 10
              seconds, ≥75% on one side. Somebody wanted in (or out) <em>immediately</em> and paid
              up for it, instead of working the order quietly. Clusters of buy-side flashes near a
              breakout level are the tell.</p>
          </InfoButton>
        </div>
        {bursts.length ? (
          <ul style={{ listStyle: 'none', margin: '0.35rem 0 0', padding: 0, display: 'grid', gap: '0.25rem' }}>
            {bursts.map((b, i) => {
              const sc = SIDE_CHIP[b.side] ?? SIDE_CHIP.unknown;
              return (
                <li key={i} className="mono" style={{ fontSize: '0.75rem' }}>
                  <span style={{ color: 'var(--cm-slate)' }}>{b.time_et}</span>{' '}
                  <span style={{ color: sc.color, fontWeight: 800 }}>{sc.label} FLASH</span>{' '}
                  {fmtDollars(b.dollars)} · {b.n_trades} prints in 10s @ ${b.price}
                </li>
              );
            })}
          </ul>
        ) : (
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.76rem', color: 'var(--cm-slate)' }}>
            No urgency bursts this session — orderly tape.
          </p>
        )}
      </div>

      {/* ── Levels: profile + zones + EMAs + GEX ────────────────────────── */}
      <div style={{ marginTop: '0.9rem' }}>
        <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Levels · profile, zones, EMAs &amp; GEX
          <InfoButton title="Volume profile (and why no bookmap)" inline align="left">
            <p><strong>Bookmap</strong> shows resting limit orders (the order book) as a heatmap.
              That needs a Level-2 depth feed our data plans don't include — and resting orders can
              be spoofed (placed to scare, cancelled before filling).</p>
            <p>We show the <strong>volume profile</strong> instead: where volume <em>actually
              traded</em>. <strong>POC</strong> = the session's heaviest price (the magnet);
              the <strong>value area</strong> = the band holding 70% of volume. These are real
              walls — nobody can fake a filled trade.</p>
            <p><strong>Supply/demand zones</strong> come from the swing structure of the last year
              (same engine as the Supply/Demand read). <strong>EMAs</strong>: 9/21 exponential
              moving averages on 5-min bars — the intraday trend. <strong>GEX</strong>: dealer
              gamma from the options chain — pinning drags price to the magnet, amplifying feeds
              moves (context only; see the Options Flow tab's OpEx panel).</p>
          </InfoButton>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.4rem' }}>
          {d.profile && (
            <>
              <Tile label="POC (magnet)" value={`$${d.profile.poc}`} sub="heaviest traded price" color="#38bdf8" />
              <Tile label="Value area" value={`$${d.profile.value_area_low} ↔ $${d.profile.value_area_high}`} sub={`${d.profile.value_area_pct}% of volume`} />
            </>
          )}
          {d.zone?.nearest_support != null && <Tile label="Support below" value={`$${d.zone.nearest_support}`} sub="nearest demand band" color="#10b981" />}
          {d.zone?.nearest_resistance != null && <Tile label="Supply above" value={`$${d.zone.nearest_resistance}`} sub="nearest overhead band" color="#ef4444" />}
          {d.emas?.intraday?.ema9 != null && (
            <Tile label="5-min EMAs" value={`9: $${d.emas.intraday.ema9} · 21: $${d.emas.intraday.ema21}`}
              sub={d.emas.intraday.pass ? 'aligned up' : 'not aligned'} color={d.emas.intraday.pass ? '#10b981' : '#ef4444'} />
          )}
          {d.gex?.regime && (
            <Tile label="Dealer gamma" value={d.gex.regime === 'pinning' ? '📌 Pinning' : '🚀 Amplifying'}
              sub={d.gex.max_pain_strike ? `max pain $${d.gex.max_pain_strike} · context only` : 'context only'}
              color={d.gex.regime === 'pinning' ? '#f59e0b' : '#a78bfa'} />
          )}
        </div>
        {d.zone?.detail && (
          <p style={{ margin: '0.4rem 0 0', fontSize: '0.76rem', color: 'var(--cm-text,#d1d5db)' }}>{d.zone.detail}</p>
        )}
      </div>

      {/* ── Our measured record ─────────────────────────────────────────── */}
      <div style={{ marginTop: '0.9rem', padding: '0.5rem 0.7rem', borderRadius: 6,
        background: 'rgba(56,189,248,0.06)', border: '1px solid rgba(56,189,248,0.25)' }}>
        <span style={{ fontSize: '0.74rem', color: '#38bdf8', fontWeight: 700 }}>📊 Track record: </span>
        <span style={{ fontSize: '0.74rem', color: 'var(--cm-text,#d1d5db)' }}>
          {accLine ?? 'every verdict on this page is logged and graded against the next days’ closes — the measured hit rate appears here as signals accumulate (no claimed win rate, only ours).'}
        </span>
      </div>

      <p style={{ margin: '0.55rem 0 0', fontSize: '0.7rem', lineHeight: 1.45, color: 'var(--cm-slate)', fontStyle: 'italic' }}>
        Tick-rule classification (~75-80% agreement with the full quote rule) · configured house
        thresholds, not a book method · decision-support, not advice. Order flow is intraday-noisy —
        the daily SEPA gate keeps this page from ever fighting your main system.
      </p>
    </section>
  );
}

function Eyebrow() {
  return (
    <div>
      <div className="eyebrow">Tape · order flow</div>
      <h3 style={{ margin: '0.1rem 0 0', fontSize: '1rem' }}>Who's actually buying — the raw prints</h3>
    </div>
  );
}
