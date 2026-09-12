/* 📌 GnT — tracking Tito Adhikary (@GnT_Trades).
 *
 * Ajay 2026-09-12: "Can you create a new tab on chartmaps tracking this
 * person.. https://x.com/GnT_Trades ... He had humongous growth of stocks" and
 * "do this daily twice. and create a tab for me. I wanna track his stocks for
 * investing".
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * WHY THIS BOARD SHOWS SENTENCES AND NOT A TICKER LIST
 * ═══════════════════════════════════════════════════════════════════════════
 * He does not post a portfolio. Two incompatible kinds of mention share his
 * timeline, and a bare ticker list conflates them:
 *
 *   FORWARD IDEA  "$SPCX reclaiming 150 into the close. Definitely on watch
 *                  next week, it held up nice all week"        ← what Ajay wants
 *   CLOSED RECAP  "Great day on $QQQ puts, +$12K"              ← a SHORT, done
 *                 "Best trades were on $NVDA $RKLB $GS $NFLX"  ← past tense
 *                 "Traded $NFLX $NVDA $BBBY today"             ← 2022; BBBY is gone
 *
 * So every row leads with his actual words and its age. The ticker is the
 * label, the sentence is the content.
 *
 * AND NO ROW CLAIMS A DIRECTION. One of his own posts reads "caught the upside
 * on $FSLR and downside on $META $TSLA" — one sentence, two directions, split
 * across three tickers. Any long/short badge would mark META and TSLA as longs.
 * The chips below are WORDS FOUND IN THE POST, not a reading of it.
 *
 * The overlay columns are this app's own read of his names — coverage, demand
 * band, growth screen — which is the entire reason this is a Chart Maps tab and
 * not a link to X.
 *
 * Nothing here gates a scan, an alert or a lane.
 */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { GrowthChip } from './GrowthChip';

export type GntPost = {
  id?: string; text?: string; created_at?: string | null;
  url?: string; flags?: string[];
};
export type GntZone = { missing?: boolean; in_band?: boolean; intact?: boolean | null };
export type GntGrowth = { sales?: number | null; eps?: number | null; refused?: boolean };
export type GntTicker = {
  symbol: string; mentions: number; flags: string[];
  last_post: GntPost; posts?: GntPost[];
  age_days?: number | null; fresh?: boolean;
  /** null = we could not load a universe at all — unknown, not "uncovered". */
  covered?: boolean | null;
  growth?: GntGrowth | null; zone?: GntZone | null;
};
export type GntPayload = {
  handle?: string; display?: string; profile_url?: string;
  usic?: { year?: number; division?: string; return_pct?: number; rank?: number;
           source?: string; note?: string };
  n_posts?: number; n_tickers?: number; n_fresh?: number; fresh_days?: number;
  newest_post_at?: string | null; newest_age_days?: number | null;
  tickers?: GntTicker[]; disclaimer?: string; error?: string;
};

/** The words found in his post. A chip is EVIDENCE, never a verdict — see the
 *  $FSLR/$META/$TSLA case in the header comment. */
const FLAG_TONE: Record<string, string> = {
  puts: 'gnt-bear', short: 'gnt-bear',
  calls: 'gnt-bull', long: 'gnt-bull',
  watch: 'gnt-watch', recap: 'gnt-dim',
};
const FLAG_TITLE: Record<string, string> = {
  puts: 'The post mentions puts — a BEARISH trade. Read the sentence.',
  short: 'The post mentions a downside/short trade.',
  calls: 'The post mentions calls.',
  long: 'The post mentions a breakout, reclaim or upside.',
  watch: 'The post reads as forward-looking — a watch, not a closed trade.',
  recap: 'The post reads as a RECAP of a trade already closed, not an open idea.',
};

/** "2h" · "3d" · "1y" — age is the first thing that decides whether a row is an
 *  idea or history, so it has to be readable at a glance. */
export function ageText(days?: number | null): string {
  if (days == null) return '—';
  if (days === 0) return 'today';
  if (days === 1) return '1d';
  if (days < 30) return `${days}d`;
  if (days < 365) return `${Math.round(days / 30)}mo`;
  return `${(days / 365).toFixed(1)}y`;
}

/** This app's read of his name, in one cell. Deliberately the SAME vocabulary
 *  as the 🚀 Growth board so the two can never read differently. */
export function zoneText(t: GntTicker): { text: string; tone: string; title: string } {
  if (t.covered === false) {
    return { text: 'not scanned', tone: 'gnt-warn',
             title: 'This name is not in the `full` universe, so no board, scan '
                  + 'or alert in this app can ever see it — however good his call is.' };
  }
  const z = t.zone;
  if (!z || z.missing) {
    return { text: 'no bands', tone: 'gnt-dim',
             title: 'No zone read for this name — blank, not empty.' };
  }
  if (!z.in_band) {
    return { text: 'out', tone: 'gnt-dim', title: 'Not inside a demand band today.' };
  }
  if (z.intact === true) {
    return { text: '🧲 intact', tone: 'gnt-good',
             title: 'In a demand band whose floor has never been pierced — the only '
                  + 'gate that measured (+8.6pp over 31,861 events).' };
  }
  if (z.intact === false) {
    return { text: 'in band, pierced', tone: 'gnt-warn',
             title: 'In the band, but the floor was pierced. That edge does not apply.' };
  }
  return { text: 'in band, floor ?', tone: 'gnt-dim',
           title: 'In a band, but the floor check did not answer — unknown, not pierced.' };
}

export default function GntBoard() {
  const [d, setD] = useState<GntPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [freshOnly, setFreshOnly] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/traders/gnt`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setD(await r.json());
      setErr(null);
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (loading) return <div className="gnt-note">loading his posts…</div>;
  if (err) return <div className="gnt-note gnt-err">⛔ {err}</div>;

  const all = d?.tickers ?? [];
  const rows = freshOnly ? all.filter((t) => t.fresh) : all;
  const u = d?.usic;

  return (
    <div className="gnt-wrap">
      <div className="gnt-head">
        <div>
          <b>📌 {d?.display ?? 'Tito Adhikary'}</b>{' '}
          <a className="gnt-handle" href={d?.profile_url} target="_blank" rel="noreferrer noopener">
            @{d?.handle ?? 'GnT_Trades'} ↗
          </a>
          {u && (
            <span className="gnt-usic" title={u.note}>
              {' · '}USIC {u.year} #{u.rank} · {u.return_pct}% ({u.division})
            </span>
          )}
        </div>
        <label className="gnt-chk">
          <input type="checkbox" checked={freshOnly}
                 onChange={(e) => setFreshOnly(e.target.checked)} />
          last {d?.fresh_days ?? 14} days only ({d?.n_fresh ?? 0})
        </label>
      </div>

      {/* The caveat rides on the board, not in a doc nobody opens. */}
      <div className="gnt-note">
        <b>Read the sentence, not the ticker.</b> {d?.disclaimer}
        {' '}His {d?.n_posts ?? 0} stored posts give {d?.n_tickers ?? 0} names;
        {' '}the newest is {ageText(d?.newest_age_days)} old. Checked twice a day.
      </div>

      {u?.note && <div className="gnt-note gnt-dim">⚠️ {u.note}</div>}

      <div className="gnt-scroll">
        <table className="gnt-table">
          <thead>
            <tr>
              <th>Symbol</th><th className="gnt-num">Age</th><th>What he said</th>
              <th>Reads as</th><th>Our demand read</th><th className="gnt-num">Growth</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => {
              const z = zoneText(t);
              const p = t.last_post || {};
              return (
                <tr key={t.symbol} className={t.fresh ? 'gnt-fresh' : ''}>
                  <td>
                    <TickerLink ticker={t.symbol} fromLabel="GnT" />
                    {/* Ajay 2026-09-11: "I am hoping this new list will be
                        considerd in all chart maps." One name he likes that is
                        ALSO a 100/100 grower is the row worth reading twice. */}
                    <GrowthChip symbol={t.symbol} />
                    {t.mentions > 1 && (
                      <div className="gnt-dim">×{t.mentions} posts</div>
                    )}
                  </td>
                  <td className={`gnt-num ${t.fresh ? 'gnt-good' : 'gnt-dim'}`}>
                    {ageText(t.age_days)}
                  </td>
                  <td className="gnt-said">
                    {p.url
                      ? <a href={p.url} target="_blank" rel="noreferrer noopener">{p.text}</a>
                      : p.text}
                  </td>
                  <td>
                    {(t.flags || []).length === 0
                      ? <span className="gnt-dim">—</span>
                      : (t.flags || []).map((f) => (
                          <span key={f} className={`gnt-chip ${FLAG_TONE[f] || 'gnt-dim'}`}
                                title={FLAG_TITLE[f] || f}>{f}</span>
                        ))}
                  </td>
                  <td className={z.tone} title={z.title}>{z.text}</td>
                  <td className="gnt-num">
                    {t.growth?.sales == null
                      ? <span className="gnt-dim">—</span>
                      : <span className="gnt-good">+{t.growth.sales.toFixed(0)}%</span>}
                    {t.growth?.refused && <div className="gnt-err">⛔ engine refuses</div>}
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={6} className="gnt-dim">
                {freshOnly
                  ? `nothing in the last ${d?.fresh_days ?? 14} days — untick the box for his history.`
                  : 'no posts stored yet. The tracker runs twice a day.'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
