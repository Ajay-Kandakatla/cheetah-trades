/* 🚀 Explosive Growth — the 100%/100% screen.
 *
 * Ajay 2026-09-11: "tell me which new ones are blowing up? in Sales by 100% or
 * more and 100 growth Quarter over Quarter ... I wanna know when ever these are
 * in demand, separately just trackers ... this is outside of regular supply and
 * demand" · "remove the 700M rule for this page" · "I want real growing stocks
 * like AXTI and SABR with genuine sales".
 *
 * THIS BOARD HAS NO CAP FLOOR — his explicit call. The trading engine still
 * has one ($2 a share, $700M known cap, trading/safety_floor.py), so a row can
 * legitimately appear here and be unbuyable there. That is never silent: the
 * backend hands every row a `warnings` list and this table prints it, with ⛔
 * for "the engine will refuse this" and ⚠️ for "look before you size it".
 *
 * The backend owns every number (growth/tracker.py). Nothing here re-screens.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { SignalWatchButton } from './SignalWatchButton';

export type GrowthZone = {
  missing?: boolean; in_band?: boolean; intact?: boolean | null;
  order_block?: boolean; zone_date?: string | null;
  band?: { lo: number; hi: number; touches?: number | null } | null;
};
export type GrowthRow = {
  symbol: string; name?: string | null;
  sector?: string | null; industry?: string | null;
  price?: number | null; market_cap?: number | null;
  avg_dollar_vol?: number | null; liquid?: boolean;
  promo_tagged?: boolean;
  sales_growth_pct?: number | null; sales_prior_pct?: number | null;
  sales_tier?: string | null; sales_accelerating?: boolean | null;
  consecutive_growth_q?: number | null;
  q_eps_growth_pct?: number | null; eps_prior_pct?: number | null;
  npm_latest_pct?: number | null; npm_expanding?: boolean | null;
  inst_ownership_pct?: number | null;
  zone?: GrowthZone; warnings?: string[];
  as_of?: string | null;
};
export type GrowthIndustry = {
  group: string; n: number;
  median_sales_growth_pct?: number | null;
  median_eps_growth_pct?: number | null;
  symbols: string[];
};
export type GrowthGroup = {
  group: string; n: number;
  /** how many SCANNED names sit in this sector — the denominator that turns
   *  "9 names" into "9 of 493", which is the point of the grouping */
  n_scanned?: number | null;
  hit_rate_pct?: number | null;
  median_sales_growth_pct?: number | null;
  median_eps_growth_pct?: number | null;
  industries: GrowthIndustry[];
  symbols: string[];
};
export type GrowthPayload = {
  rows: GrowthRow[]; n: number; built_at?: string | null;
  groups?: GrowthGroup[];
  screen?: {
    min_sales_growth_pct?: number; min_eps_growth_pct?: number;
    min_prior_sales_pct?: number; cap_floor?: number | null;
    universe_mode?: string;
  };
  disclaimer?: string;
};

/** A missing number prints an em-dash. NEVER a zero — a blank fundamental and
 *  a flat quarter are different facts and must not look alike. */
function pct(v?: number | null, digits = 0): string {
  return v == null || Number.isNaN(v) ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`;
}
function cap(v?: number | null): string {
  if (v == null || Number.isNaN(v)) return '—';
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  return `$${(v / 1e6).toFixed(0)}M`;
}
function money(v?: number | null): string {
  return v == null || Number.isNaN(v) ? '—' : `$${v.toFixed(2)}`;
}

/** READY only when the band floor has never been pierced — the one gate that
 *  measured (+8.6pp over 31,861 events). In-band with a pierced floor is a
 *  different, worse situation and must not read the same. */
function demandCell(z?: GrowthZone): { text: string; tone: string; title: string } {
  if (!z || z.missing) {
    return { text: 'no bands', tone: 'eg-dim',
             title: 'Outside the scan universe, so there is no zone read at all — blank, not empty.' };
  }
  if (!z.in_band) {
    return { text: 'out', tone: 'eg-dim', title: 'Not inside a demand band today.' };
  }
  if (z.intact) {
    return { text: '🧲 intact', tone: 'eg-good',
             title: 'Inside a demand band whose floor has never been pierced — the only gate that measured (+8.6pp win over 31,861 events).' };
  }
  return { text: 'in band, pierced', tone: 'eg-warn',
           title: 'Inside the band, but the floor has been pierced in the sweep window. The intact-floor edge does not apply here.' };
}

export function ExplosiveGrowth() {
  const [data, setData] = useState<GrowthPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [onlyBuyable, setOnlyBuyable] = useState(false);
  const [onlyDemand, setOnlyDemand] = useState(false);
  const [sector, setSector] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const load = useCallback(async (refresh = false) => {
    refresh ? setBusy(true) : setLoading(true);
    try {
      const res = await fetch(`${API}/growth/${refresh ? 'refresh' : 'board'}`,
                              refresh ? { method: 'POST' } : undefined);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setErr(null);
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setLoading(false); setBusy(false);
    }
  }, []);

  useEffect(() => { void load(false); }, [load]);

  const rows = useMemo(() => {
    let r = data?.rows ?? [];
    if (onlyBuyable) r = r.filter((x) => !(x.warnings ?? []).some((w) => w.startsWith('⛔')));
    if (onlyDemand) r = r.filter((x) => x.zone?.in_band && x.zone?.intact);
    if (sector) r = r.filter((x) => (x.sector || '(unmapped)') === sector);
    return r;
  }, [data, onlyBuyable, onlyDemand, sector]);

  const groups = data?.groups ?? [];
  const blockedN = (data?.rows ?? []).filter(
    (x) => (x.warnings ?? []).some((w) => w.startsWith('⛔'))).length;
  const demandN = (data?.rows ?? []).filter((x) => x.zone?.in_band && x.zone?.intact).length;

  if (loading) return <div className="eg-note">loading the growth board…</div>;
  if (err) return <div className="eg-note eg-err">⛔ {err}</div>;

  const s = data?.screen;

  return (
    <div className="eg-wrap">
      <div className="eg-head">
        <div>
          <b>🚀 {data?.n ?? 0} names</b> clear sales {pct(s?.min_sales_growth_pct)} AND
          {' '}quarterly EPS {pct(s?.min_eps_growth_pct)} year-over-year, with the prior
          {' '}quarter also growing.
        </div>
        <div className="eg-actions">
          <label className="eg-chk">
            <input type="checkbox" checked={onlyDemand}
                   onChange={(e) => setOnlyDemand(e.target.checked)} />
            at demand, floor intact ({demandN})
          </label>
          <label className="eg-chk">
            <input type="checkbox" checked={onlyBuyable}
                   onChange={(e) => setOnlyBuyable(e.target.checked)} />
            hide what the engine refuses ({blockedN})
          </label>
          <button className="eg-btn" disabled={busy} onClick={() => void load(true)}>
            {busy ? 'rebuilding…' : 'Rebuild now'}
          </button>
        </div>
      </div>

      <div className="eg-note">
        <b>No market-cap floor on this board</b> — your call. Every other board and the
        trading engine use $700M, so a row marked ⛔ is real on this list and refused at
        the broker. {data?.disclaimer}
        {data?.built_at && <> Built {String(data.built_at).slice(0, 16).replace('T', ' ')} UTC.</>}
      </div>

      {/* Sectors (Ajay 2026-09-11: "I wanna see the secorts in the growth.. To
          show that only some are growing"). The denominator is the point: 9 of
          493 Technology names is a different statement from "9 names". Same
          GICS axis the 🔥 Hottest tab groups by. Click a sector to filter the
          table; expand it for the industries underneath. */}
      {!!groups.length && (
        <div className="eg-groups">
          <div className="eg-groups-head">
            Sectors — how many of each sector's scanned names clear the screen.
            {sector && (
              <button className="eg-btn eg-clear" onClick={() => setSector(null)}>
                clear filter ({sector})
              </button>
            )}
          </div>
          {groups.map((g) => {
            const isOpen = !!open[g.group];
            return (
              <div key={g.group} className="eg-grp">
                <div className={`eg-grp-row${sector === g.group ? ' is-on' : ''}`}>
                  <button className="eg-twist"
                          aria-label={isOpen ? 'collapse' : 'expand'}
                          onClick={() => setOpen((o) => ({ ...o, [g.group]: !isOpen }))}>
                    {isOpen ? '▾' : '▸'}
                  </button>
                  <button className="eg-grp-name"
                          onClick={() => setSector(sector === g.group ? null : g.group)}>
                    {g.group}
                  </button>
                  <span className="eg-grp-n">
                    <b>{g.n}</b>
                    {g.n_scanned ? <span className="eg-dim"> of {g.n_scanned}</span> : null}
                  </span>
                  <span className="eg-num eg-dim">
                    {g.hit_rate_pct == null ? '—' : `${g.hit_rate_pct.toFixed(1)}%`}
                  </span>
                  <span className="eg-num eg-good">{pct(g.median_sales_growth_pct, 1)}</span>
                </div>
                {isOpen && (
                  <div className="eg-inds">
                    {g.industries.map((i) => (
                      <div key={i.group} className="eg-ind">
                        <span className="eg-ind-name">{i.group}</span>
                        <span className="eg-grp-n"><b>{i.n}</b></span>
                        <span className="eg-num eg-good">{pct(i.median_sales_growth_pct, 1)}</span>
                        <span className="eg-ind-syms">{i.symbols.join(', ')}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="eg-scroll">
        <table className="eg-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="eg-num">Sales YoY</th>
              <th className="eg-num">Prior Q</th>
              <th className="eg-num">Q EPS</th>
              <th className="eg-num">Net margin</th>
              <th className="eg-num">Price</th>
              <th className="eg-num">Cap</th>
              <th className="eg-num">$ vol/day</th>
              <th>Demand</th>
              <th>Flags</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const d = demandCell(r.zone);
              const warns = r.warnings ?? [];
              return (
                <tr key={r.symbol}>
                  <td>
                    <TickerLink ticker={r.symbol} fromLabel="Explosive Growth" />
                    {r.name && <div className="eg-coname">{r.name}</div>}
                  </td>
                  <td className="eg-num eg-good">{pct(r.sales_growth_pct, 1)}</td>
                  <td className={`eg-num ${(r.sales_prior_pct ?? 0) > 0 ? 'eg-good' : 'eg-dim'}`}>
                    {pct(r.sales_prior_pct, 1)}
                  </td>
                  <td className="eg-num eg-good">{pct(r.q_eps_growth_pct, 1)}</td>
                  <td className={`eg-num ${r.npm_expanding ? 'eg-good' : ''}`}>
                    {pct(r.npm_latest_pct, 1)}{r.npm_expanding ? ' ↑' : ''}
                  </td>
                  <td className="eg-num">{money(r.price)}</td>
                  <td className="eg-num">{cap(r.market_cap)}</td>
                  <td className="eg-num">
                    {r.avg_dollar_vol == null ? '—' : `$${(r.avg_dollar_vol / 1e6).toFixed(1)}M`}
                  </td>
                  <td className={d.tone} title={d.title}>{d.text}</td>
                  <td className="eg-flags">
                    {warns.length === 0
                      ? <span className="eg-dim">—</span>
                      : warns.map((w) => (
                          <div key={w} className={w.startsWith('⛔') ? 'eg-err' : 'eg-warn'}>{w}</div>
                        ))}
                  </td>
                  <td><SignalWatchButton symbol={r.symbol} /></td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={11} className="eg-dim">
                nothing matches the current filters.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
