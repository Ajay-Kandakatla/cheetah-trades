/* HotSectors — where money flowed in the last month, as one compact strip.
 *
 * Ajay 2026-08-31: "make sure this scan you did today to be on top of the
 * chart maps or some section where it says Hot sectors" + "Feel free to
 * categorize more sectors in a similar faction.. Like Health care small caps"
 * + "I need this component market guage tab too".
 *
 * Data: GET /rotation/hot — sector × cap-tier cohorts (tier = S&P 500/400/600
 * membership), median MEMBER return relative to RSP, ranked by the last 21
 * trading days. Same methodology as the /rotation page; this strip is just
 * its two hot ends. Mounted on Chart Maps AND Market Gauge — one component,
 * so the two pages can never disagree.
 *
 * Measurement of what moved — not a forecast and not advice.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

export type HotRow = {
  group: string; sector?: string; tier?: string; index?: string;
  n?: number; rel_21d: number | null; rel_window?: number | null;
  pct_positive?: number | null;
};

export type HotPayload = {
  as_of?: string; start?: string; benchmark?: string;
  in: HotRow[]; out: HotRow[]; ranked_by?: string;
  stance?: { defensive?: number | null; cyclical?: number | null;
             commodity?: number | null };
  error?: string;
};

export function chipLabel(r: HotRow): string {
  const v = r.rel_21d;
  const num = v == null ? '' : ` ${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
  return `${r.group}${num}`;
}

export default function HotSectors() {
  const [data, setData] = useState<HotPayload | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/rotation/hot`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => { if (alive) setData(d); })
      .catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, []);

  // A decorative strip must never block or break the page it rides on:
  // no data yet renders nothing, an error renders nothing.
  if (failed || !data || data.error) return null;
  const hasRows = (data.in?.length || 0) + (data.out?.length || 0) > 0;
  if (!hasRows) return null;

  return (
    <div className="hs" role="complementary" aria-label="Hot sectors">
      <span className="hs-head">
        🔥 Hot sectors
        <em className="hs-sub">last 21 sessions vs {data.benchmark || 'RSP'} · median member</em>
      </span>
      <span className="hs-group">
        <em className="hs-tag hs-tag-in">money in</em>
        {(data.in || []).map((r) => (
          <span key={r.group} className="hs-chip hs-chip-in"
                title={`${r.group} — ${r.n} names · window ${r.rel_window ?? '—'}% rel`}>
            {chipLabel(r)}
          </span>
        ))}
      </span>
      <span className="hs-group">
        <em className="hs-tag hs-tag-out">money out</em>
        {(data.out || []).map((r) => (
          <span key={r.group} className="hs-chip hs-chip-out"
                title={`${r.group} — ${r.n} names · window ${r.rel_window ?? '—'}% rel`}>
            {chipLabel(r)}
          </span>
        ))}
      </span>
      <Link to="/rotation" className="hs-more">full rotation →</Link>
    </div>
  );
}
