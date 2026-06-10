/* DayLeaderboardLeaders — the rank-consistent SEPA leaders, ranked by TODAY's
 * intraday move, with a live buyable flag. Session-aware: live intraday when the
 * market is open, an "as of last close" watch list for the open when it's not.
 * (Ajay 2026-06-07: "leaderboard stocks + intraday winners" + "last-close list /
 * wait-for-open indicator".)
 */
import { useDayLeaderboard } from '../hooks/useDayTrading';
import { InfoButton } from './InfoButton';
import { useSort } from '../lib/useSort';

const SESSION: Record<string, { tag: string; note: string }> = {
  open:       { tag: 'LIVE',        note: "live intraday move" },
  premarket:  { tag: 'PRE-MARKET',  note: "pre-market move — live signals fire at 9:30 ET" },
  afterhours: { tag: 'AFTER HOURS', note: "as of the close — your watch list for the next open" },
  closed:     { tag: 'MARKET CLOSED', note: "as of the last close — your watch list for the next open" },
  unknown:    { tag: '',            note: "today's move" },
};

const Info = (
  <>
    <p>
      The names that <strong>persist near the top of the SEPA leaderboard</strong>
      {' '}(proven rank consistency), crossed with <strong>today's intraday move</strong>
      {' '}and a live <strong>buyable</strong> flag from the latest scan.
    </p>
    <ul>
      <li><strong>● BUYABLE</strong> — cleared the full SEPA buy gate as of the last scan.</li>
      <li><strong>setup ready</strong> — Stage-2 setup, waiting on a trigger.</li>
      <li><strong>coiling</strong> — VCP base tightening (pre-breakout).</li>
    </ul>
    <p className="mono">
      When the market is closed this is your last-close watch list for the open.
      Educational, not advice.
    </p>
  </>
);

function pct(n?: number | null): string {
  return n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
}
function moveClass(n?: number | null): string {
  return (n ?? 0) > 0 ? 'pos' : (n ?? 0) < 0 ? 'neg' : '';
}

export function DayLeaderboardLeaders({ onPick }: { onPick?: (s: string) => void }) {
  const { data } = useDayLeaderboard(14, 14);
  const sort = useSort<any>(data?.leaders || [], {
    rank: (L) => L.intraday_rank,
    symbol: (L) => L.symbol,
    today: (L) => L.intraday_change_pct,
    last: (L) => L.last_price,
    persist: (L) => L.persistence_pct,
    signal: (L) => (L.is_buyable ? 2 : L.setup_ready ? 1 : 0),
  }, 'rank', 'asc');
  if (!data) return null;
  const sess = SESSION[data.market_session] ?? SESSION.unknown;
  const H = ({ k, label, dir = 'desc' as const, cls = '' }: { k: string; label: string; dir?: 'asc' | 'desc'; cls?: string }) => (
    <button type="button" onClick={() => sort.toggle(k, dir)} title={`Sort by ${label}`}
            className={cls}
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer',
                     padding: 0, font: 'inherit', fontWeight: sort.key === k ? 700 : 400 }}>
      {label}{sort.arrow(k)}
    </button>
  );

  return (
    <section className="day-section dl-section">
      <div className="day-section__head-row">
        <h2 className="day-section__h">
          Leaderboard leaders · intraday movers
          <InfoButton inline title="Leaderboard leaders">{Info}</InfoButton>
        </h2>
        {sess.tag && <span className={`dl-session dl-session--${data.market_session}`}>● {sess.tag}</span>}
      </div>
      <p className="dl-lede">
        Your rank-consistent SEPA leaders, sorted by today's move — {sess.note}.
        {data.buyable_count > 0 && <> <strong>{data.buyable_count} buyable</strong> as of the last scan.</>}
      </p>

      {!data.available && (
        <div className="day-empty">No leaderboard data yet — run a SEPA scan to populate the leaders.</div>
      )}

      {data.available && (
        <div className="dl-list">
          <div className="dl-row dl-row--head">
            <span className="dl-rank"><H k="rank" label="#" dir="asc" /></span>
            <span><H k="symbol" label="Symbol" dir="asc" /></span>
            <span className="dl-num"><H k="today" label="Today" /></span>
            <span className="dl-num"><H k="last" label="Last" /></span>
            <span className="dl-num"><H k="persist" label="Rank · Persist" /></span>
            <span className="dl-sig"><H k="signal" label="Signal" /></span>
          </div>
          {sort.sorted.map((L) => (
            <div
              key={L.symbol}
              className={`dl-row${L.is_buyable ? ' dl-row--buyable' : ''}`}
              role="button"
              tabIndex={0}
              onClick={() => onPick?.(L.symbol)}
              title={`Chart ${L.symbol}`}
            >
              <span className="dl-rank mono">{L.intraday_rank}</span>
              <span className="dl-sym"><strong>{L.symbol}</strong></span>
              <span className={`dl-num mono dl-move dl-move--${moveClass(L.intraday_change_pct)}`}>
                {pct(L.intraday_change_pct)}
              </span>
              <span className="dl-num mono dl-last">{L.last_price ? `$${L.last_price.toFixed(2)}` : '—'}</span>
              <span className="dl-num mono dl-meta">
                #{L.current_rank ?? '—'} · {L.persistence_pct ?? '—'}%
              </span>
              <span className="dl-sig">
                {L.is_buyable
                  ? <span className="dl-chip dl-chip--buy">● BUYABLE</span>
                  : L.setup_ready
                    ? <span className="dl-chip dl-chip--ready">setup ready</span>
                    : <span className="dl-chip dl-chip--watch">watch</span>}
                {L.coiling && <span className="dl-chip dl-chip--coil">coiling</span>}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
