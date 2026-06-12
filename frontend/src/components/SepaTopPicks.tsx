/* SepaTopPicks — the "what do I buy right now" indicator on the portfolio page.
   Reads GET /sepa/top-picks (top actionable buys from the LATEST scan), so it
   refreshes whenever a scan runs. Ranks fresh breakouts first (see backend
   sepa/top_picks.py). Fails quiet — never breaks the portfolio page. */
import { lazy, Suspense, useEffect, useState } from 'react';
import { WatchlistButton } from './WatchlistButton';
import { Link, useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { leveragedEtfInfo } from '../lib/leveragedEtf';
import { usePatternVerdicts } from '../hooks/usePatternVerdicts';
import { PatternChips } from './PatternChips';
import { TickerName } from './TickerCell';
import { EarningsChip } from './EarningsChip';
import { useEarningsMap } from '../hooks/useEarningsMap';
import { AnalystPulseChip } from './AnalystPulseChip';
import { useAnalystMap } from '../hooks/useAnalystMap';

// Lazy — the analyst drill only loads when a 📊 chip is tapped.
const AnalystPulseModal = lazy(() =>
  import('./AnalystPulseModal').then((m) => ({ default: m.AnalystPulseModal })),
);

type Pick = {
  symbol: string;
  name?: string | null;
  score?: number | null;
  rating?: string | null;
  rs_rank?: number | null;
  status: 'buyable' | 'ready';
  tier: number;
  days_since_breakout?: number | null;
  decision?: string | null;
  decision_reason?: string | null;
  buy?: number | null;
  stop?: number | null;
  why?: string;
  // confidence metrics (backend sepa/top_picks._metrics)
  vol_x?: number | null;            // today vol ÷ 50-day avg — volume deviation
  vol_dryup?: number | null;
  ud_ratio?: number | null;
  accumulation?: string | null;
  dist_to_pivot_pct?: number | null;
  risk_pct?: number | null;
  tightness?: number | null;        // VCP final contraction %
};

function volTone(v?: number | null): string {
  if (v == null) return 'dim';
  if (v >= 1.5) return 'hot';        // breakout-level participation
  if (v >= 1.0) return 'warm';
  return 'cool';                     // below average — thin
}
function accTone(a?: string | null): string {
  if (a === 'strong' || a === 'accumulating') return 'good';
  if (a === 'distributing') return 'bad';
  return 'dim';
}
function pivotLabel(d?: number | null): string {
  if (d == null) return '—';
  if (Math.abs(d) < 0.5) return 'at pivot';
  return d > 0 ? `+${d}% past` : `${d}% to piv`;
}
type Resp = {
  picks: Pick[];
  as_of?: number | null;
  scanned?: number | null;
  buyable_count?: number | null;
  qualifier_count?: number | null;
};

function statusOf(p: Pick): { label: string; color: string } {
  if (p.status === 'ready') return { label: 'Ready · awaiting trigger', color: '#eab308' };
  if (p.tier === 0) return { label: 'Breaking out today', color: '#10b981' };
  if (p.tier === 1) return { label: 'Broke out this week', color: '#34d399' };
  return { label: 'In-base buy (pocket pivot)', color: '#38bdf8' };
}

/* AutoPilotButton — 🤖 jump to /trading with the symbol prefilled. Sits INSIDE
   the card's <Link>, so it must stopPropagation AND preventDefault (house
   lesson — preventDefault alone doesn't stop the row's Link navigation, and
   stopPropagation alone doesn't stop the anchor default). */
function AutoPilotButton({ symbol }: { symbol: string }) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className="wl-btn wl-btn--sm"
      title="Enter via Auto-Pilot"
      aria-label={`Enter ${symbol} via Auto-Pilot`}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        navigate(`/trading?symbol=${encodeURIComponent(symbol)}`);
      }}
    >
      🤖
    </button>
  );
}

export function SepaTopPicks({ n = 3 }: { n?: number }) {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState(false);
  const { verdicts } = usePatternVerdicts();
  const earningsMap = useEarningsMap();
  // 📊 Analyst Pulse — one modal instance for the whole list; chips set
  // the symbol. Hooks stay above the early return (rules of hooks).
  const picks = data?.picks || [];
  const analystMap = useAnalystMap(picks.map((p) => p.symbol));
  const [analystSym, setAnalystSym] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/sepa/top-picks?n=${n}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => alive && setData(d))
      .catch(() => alive && setErr(true));
    return () => {
      alive = false;
    };
  }, [n]);

  if (err || !data) return null; // fail quiet — portfolio page must still render

  return (
    <section className="top-picks">
      <div className="top-picks__head">
        <span className="eyebrow">🎯 Top SEPA buys right now</span>
        <span className="top-picks__meta mono">
          {data.buyable_count ?? 0} buyable · {data.scanned ?? 0} scanned
        </span>
      </div>

      {picks.length === 0 ? (
        <p className="top-picks__empty">
          No buyable breakouts in the latest scan — everything is still coiling. By the book,
          nothing to chase right now; wait for a pivot to clear on volume.
        </p>
      ) : (
        <div className="top-picks__list">
          {picks.map((p) => {
            const s = statusOf(p);
            const lev = leveragedEtfInfo(p.symbol, p.name);
            return (
              <Link key={p.symbol} to={`/sepa/${p.symbol}`} className="top-pick" title={p.decision_reason || p.why || ''}>
                <div className="top-pick__row">
                  <span className="top-pick__sym">{p.symbol}<WatchlistButton ticker={p.symbol} /><AutoPilotButton symbol={p.symbol} /><TickerName symbol={p.symbol} name={p.name} width={20} /></span>
                  <span className="top-pick__score mono">{p.score ?? '—'}</span>
                  <span className="top-pick__badge" style={{ color: s.color, borderColor: s.color }}>
                    {s.label}
                  </span>
                  <PatternChips v={verdicts.get(p.symbol.toUpperCase())} />
                  {/* asLink={false} — we're inside the row's <Link>; nested anchors are invalid */}
                  <EarningsChip symbol={p.symbol} info={earningsMap.get(p.symbol.toUpperCase())} asLink={false} />
                  {/* 📊 Analyst Pulse — chip stops propagation + default so the
                      row Link doesn't navigate; opens the shared modal below. */}
                  <AnalystPulseChip
                    symbol={p.symbol}
                    entry={analystMap.get(p.symbol.toUpperCase())}
                    onOpenDrill={() => setAnalystSym(p.symbol)}
                  />
                </div>
                {lev.isLeveraged && (
                  <div className="top-pick__lev" title="Leveraged/inverse ETF — daily-rebalance decay + amplified drawdown; SEPA/Minervini criteria don't apply.">
                    <span className="lev-badge">⚡ {lev.label} · not a SEPA stock</span>
                  </div>
                )}
                <div className="top-pick__why mono">{p.why}</div>
                <div className="top-pick__buy mono">
                  buy {p.buy != null ? `$${p.buy}` : '—'}
                  {p.stop != null ? ` · stop $${p.stop}` : ''}
                  {p.rs_rank != null ? ` · RS ${p.rs_rank}` : ''}
                </div>
                <div className="top-pick__metrics mono">
                  <span className="tpm" data-tone={volTone(p.vol_x)}
                        title="Today's bar volume ÷ its own 50-day average (volume deviation / relative volume). ≥1.5× = breakout-level participation.">
                    Vol {p.vol_x != null ? `${p.vol_x}×` : '—'}
                  </span>
                  {p.accumulation && (
                    <span className="tpm" data-tone={accTone(p.accumulation)}
                          title={`Up/down volume pressure${p.ud_ratio != null ? ` · U/D ${p.ud_ratio}` : ''}`}>
                      {p.accumulation}
                    </span>
                  )}
                  <span className="tpm" data-tone={p.dist_to_pivot_pct != null && p.dist_to_pivot_pct > 3 ? 'cool' : 'dim'}
                        title="Close vs the pivot (entry). Past pivot = already triggered; below = still coiling.">
                    {pivotLabel(p.dist_to_pivot_pct)}
                  </span>
                  {p.risk_pct != null && (
                    <span className="tpm" data-tone="dim" title="Entry (pivot) → stop distance — the per-share risk on a buy.">
                      risk {p.risk_pct}%
                    </span>
                  )}
                  {p.tightness != null && (
                    <span className="tpm" data-tone={p.tightness <= 5 ? 'good' : 'dim'}
                          title="VCP final contraction % — tighter coil = lower-risk pivot.">
                      tight {p.tightness}%
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
      <p className="top-picks__foot mono">
        From the latest SEPA scan · refreshes each scan · not investment advice
      </p>

      {analystSym && (
        <Suspense fallback={null}>
          <AnalystPulseModal symbol={analystSym} onClose={() => setAnalystSym(null)} />
        </Suspense>
      )}
    </section>
  );
}
