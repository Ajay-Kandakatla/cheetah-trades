/* Bonde — Pradeep Bonde's (Stockbee) own screen, as its own Chart Maps tab.
 *
 * Ajay 2026-09-13: "create me a Bonde tab. we already have his rules in the
 * analysis tab on individual ticker but I wanna see explicitly new ones getting
 * added in this tab … but I wanna see his stocks."
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * THE BOARD LEADS WITH ITS OWN MEASUREMENT, BECAUSE IT CAME BACK INVERTED
 * ═══════════════════════════════════════════════════════════════════════════
 * It shipped on the reasoning that his SALES screen is the universe and the
 * EPISODIC PIVOT is the entry, so the intersection is the selection. Two
 * measurement passes later — the second an independent audit on ~2x the panel
 * — that intersection is the WORST cell either pass found: 21-day median
 * −3.22% against −0.11% for date-matched non-Pivot names, a lift of −3.11pp
 * (95% CI −5.28 to −1.16). The sales gate alone separated nothing.
 *
 * So the verdict banner is the first thing on the page, above the counts, in
 * the same shape the Keltner and AMD tabs use. Every number in it is SERVED
 * (`d.measured`), never typed here: `sepa/bonde.py::MEASURED` is the one home
 * for these figures, and `backend/scripts/bonde_audit/` is the re-runnable
 * source.
 *
 * 🔎 THE LAST SECTION IS NOT ON HIS SCREEN, deliberately. His character clause
 * (accelerating OR ≥2 consecutive growth quarters) is the one thing that
 * survived every attack — measuring NEGATIVE. The floor-clearing names it
 * rejects won 56.8% of the next 21 sessions against 51.2% for the ones it
 * accepts. The gate is not edited, because it is his and this board exists to
 * show his screen; the discarded cohort is shown beside it instead, labelled.
 *
 * ✨ NEW is his explicit ask — names that ARRIVED on the screen, not names that
 * happen to be there. The backend ledger refuses to badge the first cohort it
 * ever sees, because "we have only just started looking" must never render as
 * "these are fresh finds". It never lights on a 🔎 row: that badge means
 * "arrived on his screen", and those names are precisely the ones that are not.
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

/** The verdict banner, served whole. Nothing in it is composed in the
 *  component — a measured negative result gets exactly one home. */
export type BondeMeasured = {
  headline?: string; body?: string; not_a_short?: string;
  tiers?: string; rejected?: string; struck?: string;
  limits?: string; scripts?: string;
};

export type BondeBoardData = {
  sections: Record<string, BondeRow[]>;
  counts: Record<string, number>;
  caps: Record<string, number>;
  n_pass: number; n_rejected?: number; n_scanned: number;
  n_new: number; new_days: number;
  regime?: BondeRegime; note?: string; scan_ts?: number | string | null;
  measured?: BondeMeasured;
};

const SECTIONS: { key: string; label: string; blurb: string }[] = [
  { key: 'pivot', label: '⚡ Episodic Pivots',
    blurb: 'His entry: a stock gapping hard on huge volume, on any catalyst, that also passed his sales gate. This is the board’s original thesis and it is the cell that measured INVERTED — 21-day median −3.22% against −0.11% for date-matched non-Pivot names. Shown because you asked to see his stocks, not because anything measured says to buy them.' },
  { key: 'explosive', label: 'Explosive · sales +100%',
    blurb: 'His own "Sales 100% plus" Episodic-Pivot category (2010). Measured median lift over the scored universe: +0.45pp at 21 days, CI −0.31 to +1.36 — it includes zero.' },
  { key: 'strong', label: 'Strong · sales +25%',
    blurb: 'His stated preferred level — "you can use 25% plus". Measured median lift +0.37pp at 21 days, CI −0.16 to +0.78 — it includes zero, and the mean lift that does show up falls to +0.26pp once the top 5% of returns are dropped.' },
  { key: 'steady', label: 'Steady · sales +5%',
    blurb: 'His floor — "I take 5%". Measured flat against the scored universe (−0.01pp at 21 days). Capped here: it is 677 names on the live scan, which is a scroll, not a read.' },
  { key: 'rejected', label: '🔎 Cleared his floor, rejected for character',
    blurb: 'NOT ON HIS SCREEN. These names cleared Bonde’s 5% sales floor and were thrown out by the character clause — not accelerating, and under 2 consecutive growth quarters. That clause is the one thing in this whole board that survived every attack, and it measures BACKWARDS: this cohort won 56.8% of the next 21 sessions against 51.2% for the names the gate accepts (+5.64pp, CI +3.91 to +7.52). His gate is not edited — it is his — so the cohort it discards is shown here instead. It does not survive date clustering at 21 days (it does at 63).' },
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
  const m = d.measured;

  return (
    <div className="bd-wrap">
      {/* First thing on the page, above the counts. The tab was built on a
          thesis that measured the wrong way round, and a reader who scrolls
          past the board to find that out has already read it as a buy list. */}
      {m?.headline && (
        <div className="bd-verdict">
          <h3 className="bd-vh">⛔ {m.headline}</h3>
          {m.body && <p>{m.body}</p>}
          {m.not_a_short && <p className="bd-vdim">{m.not_a_short}</p>}
          {m.tiers && <p>{m.tiers}</p>}
          {m.rejected && <p>{m.rejected}</p>}
          {m.struck && <p className="bd-vdim">{m.struck}</p>}
          {m.limits && <p className="bd-vdim">{m.limits}</p>}
          {m.scripts && (
            <p className="bd-vdim">
              Re-runnable verbatim: <code>{m.scripts}</code> — its README carries
              the run recipe, the struck claims and the limits.
            </p>
          )}
        </div>
      )}

      <div className="bd-head">
        <div className="bd-stats">
          <span><strong>{d.n_pass.toLocaleString()}</strong> pass his screen</span>
          <span className="bd-dim">of {d.n_scanned.toLocaleString()} scanned</span>
          {typeof d.n_rejected === 'number' && (
            <span className="bd-dim" title="Cleared his 5% sales floor, rejected by the character clause. Measured as the better-performing cohort — see the verdict above.">
              🔎 <strong>{d.n_rejected.toLocaleString()}</strong> floor-clearers rejected
            </span>
          )}
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
              {newOnly ? (s.key === 'rejected'
                  ? '✨ NEW never lights here — these names are not on his screen.'
                  : 'no new arrivals in this tier.')
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
