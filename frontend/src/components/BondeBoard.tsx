/* Bonde — Pradeep Bonde's (Stockbee) own screen, as its own Chart Maps tab.
 *
 * Ajay 2026-09-13: "create me a Bonde tab. we already have his rules in the
 * analysis tab on individual ticker but I wanna see explicitly new ones getting
 * added in this tab … but I wanna see his stocks."
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * WHY THE BOARD IS SHAPED THIS WAY
 * ═══════════════════════════════════════════════════════════════════════════
 * Measured on the live scan the day it was built:
 *
 *   his SALES gate alone   1,051 of 2,076 names (50.6%)  ← half the market
 *   the EPISODIC PIVOT alone   50 setups, ELEVEN of them with DECLINING sales
 *   both together              12 names                  ← a board
 *
 * So the sales screen is the UNIVERSE and the Pivot is the ENTRY, which is how
 * he describes his own process. ⚡ Pivots lead because that intersection is the
 * only part of this that is a selection; the tiers below are a watchlist.
 *
 * ✨ NEW is his explicit ask — names that ARRIVED on the screen, not names that
 * happen to be there. The backend ledger refuses to badge the first cohort it
 * ever sees, because "we have only just started looking" must never render as
 * "these are fresh finds".
 *
 * Nothing here gates a scan, fires an alert or buys in any lane.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { metricCells } from '../lib/boardMetrics';
import { GrowthChip } from './GrowthChip';

export type BondePivot = {
  gap_pct?: number | null; vol_mult?: number | null;
  catalyst_type?: string | null; trigger?: number | null;
  stop?: number | null; target?: number | null; rr?: number | null;
  date_et?: string | null; hours_ago?: number | null;
};

export type BondeRow = {
  symbol: string; name?: string | null; last_close?: number | null;
  tier?: string | null; sales_score?: number | null;
  growth_yoy_pct?: number | null; prior_yoy_pct?: number | null;
  accelerating?: boolean | null; consecutive_growth_q?: number | null;
  sales_led?: boolean | null; bonde_reason?: string | null;
  pivot?: BondePivot | null;
  latest_rev?: number | null; base_rev?: number | null;
  base_state?: string | null; rev_added?: number | null;
  is_new?: boolean; first_seen?: string | null;
  shares_yoy_pct?: number | null; cash_minus_debt?: number | null;
  ev_sales?: number | null; fcf_yield?: number | null;
  balance_meaningful?: boolean | null; sector?: string | null;
  shares_yoy_reason?: string | null;
};

export type BondeRegime = {
  is_bull?: boolean | null; label?: string | null;
  score?: number | null; scanners_paused?: boolean;
};

export type BondeBoardData = {
  sections: Record<string, BondeRow[]>;
  counts: Record<string, number>;
  caps: Record<string, number>;
  n_pass: number; n_scanned: number; n_new: number; new_days: number;
  regime?: BondeRegime; note?: string; scan_ts?: number | string | null;
};

const SECTIONS: { key: string; label: string; blurb: string }[] = [
  { key: 'pivot', label: '⚡ Episodic Pivots',
    blurb: 'His entry: a stock gapping hard on huge volume, on any catalyst. These are the sales-qualified names with a live Pivot — the only part of this board that is a selection rather than a watchlist.' },
  { key: 'explosive', label: 'Explosive · sales +100%',
    blurb: 'His own "Sales 100% plus" Episodic-Pivot category (2010).' },
  { key: 'strong', label: 'Strong · sales +25%',
    blurb: 'His stated preferred level — "you can use 25% plus".' },
  { key: 'steady', label: 'Steady · sales +5%',
    blurb: 'His floor — "I take 5%". Capped here: it is 677 names on the live scan, which is a scroll, not a read.' },
];

const n = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

const pct = (v: number | null | undefined, d = 0): string => {
  const x = n(v);
  if (x == null) return '—';
  return `${x > 0 ? '+' : ''}${x.toFixed(d).replace('-', '−')}%`;
};

const usd = (v: number | null | undefined): string => {
  const x = n(v);
  if (x == null) return '—';
  const a = Math.abs(x);
  const [u, d] = a >= 1e9 ? ['B', 1e9] as const
    : a >= 1e6 ? ['M', 1e6] as const
    : a >= 1e3 ? ['K', 1e3] as const : ['', 1] as const;
  const body = `$${(a / d).toFixed(a / d >= 100 ? 0 : 1)}${u}`;
  return x < 0 ? `−${body}` : body;
};

/** Why a growth percentage may not mean what it looks like. Shown ON the row,
 *  never used to hide it — his screen includes these names and the board must
 *  not quietly disagree with his screen. */
const BASE_NOTE: Record<string, string> = {
  non_positive:
    'Year-ago quarterly revenue was NEGATIVE, so this percentage is a sign flip rather than growth. The screen still lists the name; it just cannot be ranked on that number.',
  too_small:
    'Year-ago quarterly revenue was under $1M — effectively pre-revenue, so the percentage is a ratio off a tiny base rather than a growth rate. Sorted below names with a real base. ($1M is this app’s own materiality setting, not a Bonde number.)',
  unknown:
    'Not enough quarterly revenue history to state the base.',
};

export default function BondeBoard() {
  const [d, setD] = useState<BondeBoardData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [newOnly, setNewOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/bonde/board`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setD(await r.json());
      setErr(null);
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const sections = useMemo(() => {
    if (!d) return [];
    return SECTIONS.map((s) => {
      const all = d.sections?.[s.key] || [];
      return { ...s, rows: newOnly ? all.filter((r) => r.is_new) : all,
               total: d.counts?.[s.key] ?? all.length, shown: all.length };
    });
  }, [d, newOnly]);

  if (loading) return <div className="bd-note">reading his screen…</div>;
  if (err) return <div className="bd-note bd-err">⛔ {err}</div>;
  if (!d) return null;

  const paused = d.regime?.scanners_paused;

  return (
    <div className="bd-wrap">
      <div className="bd-head">
        <div className="bd-stats">
          <span><strong>{d.n_pass.toLocaleString()}</strong> pass his screen</span>
          <span className="bd-dim">of {d.n_scanned.toLocaleString()} scanned</span>
          {/* His explicit ask, given its own place rather than a badge you have
              to hunt for. Zero is a real answer and says so. */}
          <span className="bd-new-count">
            ✨ <strong>{d.n_new}</strong> new in {d.new_days}d
          </span>
        </div>
        <label className="bd-toggle" title="Show only names that ARRIVED on his screen recently">
          <input type="checkbox" checked={newOnly}
                 onChange={(e) => setNewOnly(e.target.checked)} />
          new arrivals only
        </label>
      </div>

      {/* An empty ⚡ Pivots section has a structural cause right now, and a board
          that does not say so reads as broken. */}
      {paused && (
        <div className="bd-paused">
          ⚡ <strong>Pivots are paused</strong> — the regime gate reads
          “{String(d.regime?.label || '').replace(/_/g, ' ')}”
          {n(d.regime?.score) != null && <> (score {d.regime?.score})</>}, and you
          chose to sit out bear markets, so every setup scanner short-circuits and
          writes nothing. Not a fault, and not specific to this tab — every setup
          kind in the app is stale for the same reason. The sales tiers below are
          unaffected: they read the scan, not the setup scanners.
        </div>
      )}

      {sections.map((s) => (
        <section key={s.key} className="bd-section">
          <h3 className="bd-h">
            {s.label}
            <span className="bd-count">
              {s.rows.length}{s.total > s.shown ? ` of ${s.total}` : ''}
            </span>
          </h3>
          <p className="bd-blurb">{s.blurb}</p>
          {s.rows.length === 0 ? (
            <div className="bd-empty">
              {newOnly ? 'no new arrivals in this tier.'
                : s.key === 'pivot' && paused ? 'none — the scanners are paused (above).'
                : 'nothing in this tier right now.'}
            </div>
          ) : (
            <div className="bd-rows">
              {s.rows.map((r) => {
                const cells = metricCells(r);
                const baseNote = r.base_state && r.base_state !== 'ok'
                  ? BASE_NOTE[r.base_state] : null;
                return (
                  <div key={`${s.key}-${r.symbol}`} className="bd-row">
                    <div className="bd-sym">
                      <TickerLink ticker={r.symbol} fromLabel="Bonde" />
                      {r.is_new && (
                        <span className="bd-new"
                              title={r.first_seen
                                ? `First appeared on his screen ${String(r.first_seen).slice(0, 10)}`
                                : 'Newly arrived on his screen'}>✨ NEW</span>
                      )}
                      {/* 🚀 reaches every Chart Maps tab (Ajay 2026-09-11:
                          "ALL TABS IN CHART MAPS"). Here it is the useful
                          cross-check: a name on Bonde's SALES screen that also
                          clears the 100/100 explosive-growth screen is the two
                          lists agreeing. */}
                      <GrowthChip symbol={r.symbol} className="bd-gchip" />
                      {r.name && <div className="bd-coname">{r.name}</div>}
                    </div>

                    <div className="bd-sales">
                      <span className={baseNote ? 'bd-warn' : 'bd-good'}
                            title={baseNote || `Revenue ${usd(r.base_rev)} → ${usd(r.latest_rev)} year over year.`}>
                        {pct(r.growth_yoy_pct, 0)}{baseNote ? ' ⚠' : ''}
                      </span>
                      <span className="bd-dim bd-sub">
                        {usd(r.base_rev)} → {usd(r.latest_rev)}
                      </span>
                    </div>

                    <div className="bd-chips">
                      {r.accelerating && <span className="bd-chip" title="Growth rate is rising quarter over quarter — one of Bonde's named catalysts">accelerating</span>}
                      {n(r.consecutive_growth_q) != null && (r.consecutive_growth_q as number) >= 2 && (
                        <span className="bd-chip" title="Consecutive quarters of positive YoY revenue growth">
                          {r.consecutive_growth_q}q streak
                        </span>
                      )}
                      {r.sales_led && <span className="bd-chip" title="Top line outpacing the bottom line — organic growth rather than buybacks">sales-led</span>}
                    </div>

                    {r.pivot ? (
                      <div className="bd-pivot" title={r.bonde_reason || ''}>
                        <strong>gap {pct(r.pivot.gap_pct, 1)}</strong>
                        <span className="bd-dim bd-sub">
                          {n(r.pivot.vol_mult) != null ? `${r.pivot.vol_mult}× vol` : ''}
                          {n(r.pivot.hours_ago) != null ? ` · ${Math.round(r.pivot.hours_ago as number)}h ago` : ''}
                        </span>
                      </div>
                    ) : <div className="bd-pivot bd-dim">—</div>}

                    <div className="bd-metrics">
                      {cells.map((c, i) => (
                        <span key={i} className={`bd-m ${c.tone ? `bd-${c.tone}` : ''}`}
                              title={c.title}>{c.text}</span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ))}

      <p className="bd-note bd-foot">{d.note}</p>
    </div>
  );
}
