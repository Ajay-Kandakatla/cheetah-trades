/* DemandReentryPanel — S&P 500 names entering BACK INTO a demand zone.
 *
 * Ajay 2026-08-13: "update my Supply and demand page with stocks that entering
 * back in to demand zones and give me a scan button … scan only S&P 500."
 *
 * A transition read, not a snapshot: the name ran above the band, came back
 * down into it, and the trend still holds. Each row carries the written plan
 * (buy band / stop / target) and the reason it qualified.
 *
 * Backend: GET /supply-demand/demand-reentry, POST …/scan (force).
 * Configured price-structure method — NOT a book method, NOT advice.
 */
import { useCallback, useEffect, useState } from 'react';
import { TickerLink } from './TickerLink';
import { bandLabel, freshnessLabel, money, planLine, rrBand } from '../lib/zonePlan';
import type { ZoneMapPayload } from '../lib/zonePlan';
import { API } from '../lib/apiBase';


type Payload = {
  rows: ZoneMapPayload[];
  n: number;
  scanned: number;
  universe: number;
  universe_note: string;
  universe_is_sp500: boolean;
  /* Age in days when the constituent list came from an expired cache, else
   * null. `universe_is_sp500` only catches the loud failure (fell through to
   * the curated list); a stale cache holds the REAL constituents and so was
   * indistinguishable from a fresh list — it sat 76 days out of date without
   * a word on the page. See STALE_DAYS_WARN below. */
  universe_stale_days: number | null;
  universe_source: string | null;
  took_sec: number;
  as_of: string;
  cached: boolean;
  disclaimer: string;
};

/* Days of cache staleness past which the notice goes from muted to loud.
 * The cache TTL is 30 days, so any staleness at all already means the live
 * fetch is broken — but the S&P turns over only a few names a quarter, so a
 * month or two adrift is a footnote, not an alarm. Two quarters is an alarm. */
const STALE_DAYS_LOUD = 120;

export function DemandReentryPanel() {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (force: boolean) => {
    force ? setScanning(true) : setLoading(true);
    setErr(null);
    try {
      const r = force
        ? await fetch(`${API}/supply-demand/demand-reentry/scan`, {
            method: 'POST', credentials: 'include',
          })
        : await fetch(`${API}/supply-demand/demand-reentry`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setLoading(false);
      setScanning(false);
    }
  }, []);

  useEffect(() => { load(false); }, [load]);

  const busy = loading || scanning;

  return (
    <section className="sd-section">
      <div className="sepa-tab-help">
        <strong>🟢 Back in demand</strong> — S&P 500 names that ran up, then pulled
        back <em>into</em> a demand band they had already left, while the trend still
        holds. Sitting in a band forever is not a re-entry; leaving and returning is.
        Each row shows where to buy, where the idea is wrong (stop), and the first
        place sellers are waiting (target).
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', margin: '0.6rem 0' }}>
        <button className="sepa-btn" onClick={() => load(true)} disabled={busy}>
          {scanning ? 'Scanning S&P 500…' : '🔄 Scan S&P 500'}
        </button>
        {data && (
          <span className="mono" style={{ fontSize: '0.72rem', opacity: 0.75 }}>
            {data.n} in demand · {data.scanned}/{data.universe} scanned
            {data.took_sec ? ` · ${data.took_sec}s` : ''}
            {data.cached ? ' · cached' : ''}
          </span>
        )}
      </div>

      {data && !data.universe_is_sp500 && (
        <div className="sepa-err" style={{ marginBottom: '0.6rem' }}>
          ⚠️ {data.universe_note} — this is NOT the S&P 500. Results below cover the
          curated list instead.
        </div>
      )}

      {/* Stale-but-real constituents. Different failure from the one above and
        * it needs a different volume: these ARE the S&P 500, just frozen on the
        * day the live fetch broke, so the list is ~99% right and the scan is
        * still worth reading. Muted note by default; escalates past
        * STALE_DAYS_LOUD, where enough quarterly index turnover has stacked up
        * to actually miss names. */}
      {data && data.universe_is_sp500 && data.universe_stale_days != null && (
        <div
          className={data.universe_stale_days > STALE_DAYS_LOUD ? 'sepa-err' : undefined}
          style={{
            marginBottom: '0.6rem',
            fontSize: '0.74rem',
            ...(data.universe_stale_days > STALE_DAYS_LOUD ? {} : {
              color: 'var(--cm-slate)',
              border: '1px solid var(--cm-border, #2a3244)',
              borderRadius: '6px',
              padding: '0.45rem 0.6rem',
            }),
          }}
        >
          🕰️ Constituent list is <strong>{data.universe_stale_days} days old</strong> — the
          live S&P 500 fetch is failing, so this is the last good snapshot. Real
          constituents, but index adds/drops since then are missed.
        </div>
      )}

      {err && <div className="sepa-err">Scan failed: {err}</div>}

      {busy && !data && (
        <div style={{ color: 'var(--cm-slate)', padding: '1rem' }}>
          Scanning the S&P 500 for demand-zone re-entries… the first cold pass takes
          a few minutes (cached 3h after).
        </div>
      )}

      {data && data.rows.length === 0 && !busy && (
        <div style={{ color: 'var(--cm-slate)', padding: '1rem' }}>
          Nothing is pulling back into demand right now across {data.scanned} S&P 500
          names. That is a real answer, not an empty list — press Scan after the close
          to re-check.
        </div>
      )}

      {data && data.rows.length > 0 && (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {data.rows.map((r) => {
            const rr = rrBand(r.plan?.rr);
            return (
              <div key={r.symbol} style={{
                padding: '0.6rem 0.75rem', borderRadius: 10,
                background: 'rgba(148,163,184,0.07)',
                borderLeft: '3px solid #22c55e',
              }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <TickerLink ticker={r.symbol} fromLabel="Back in Demand" />
                  <span style={{ fontSize: '0.78rem', opacity: 0.8 }}>{r.name}</span>
                  <span className="mono" style={{ fontSize: '0.74rem' }}>{money(r.last_price)}</span>
                  <span style={{
                    fontSize: '0.62rem', padding: '1px 7px', borderRadius: 999,
                    background: 'rgba(34,197,94,0.16)', color: '#22c55e', fontWeight: 600,
                  }}>
                    {freshnessLabel(r.bars_since_above)}
                  </span>
                  {r.fell_from_pct != null && (
                    <span className="mono" style={{ fontSize: '0.7rem', opacity: 0.7 }}>
                      fell from +{r.fell_from_pct}%
                    </span>
                  )}
                  <span className="mono" title="Swing-low direction + 50-day slope — the falling-knife guard that replaced the Minervini trend template."
                        style={{ fontSize: '0.7rem', opacity: 0.7, marginLeft: 'auto' }}>
                    lows {r.structure?.trend ?? '—'}
                    {r.structure?.ma50_rising != null && ` · 50d ${r.structure.ma50_rising ? '↑' : '↓'}`}
                  </span>
                </div>
                <div className="mono" style={{ fontSize: '0.74rem', marginTop: '0.3rem' }}>
                  {planLine(r.plan)}
                </div>
                <div style={{ fontSize: '0.7rem', opacity: 0.75, marginTop: '0.15rem' }}>
                  Band {bandLabel(r.entry_zone)} · {r.entry_zone?.touches ?? 0}× tested · {rr.label}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {data && (
        <p style={{ fontSize: '0.68rem', opacity: 0.55, marginTop: '0.7rem' }}>
          {data.disclaimer}
        </p>
      )}
    </section>
  );
}
