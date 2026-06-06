/* MoneyMovement — where the giants are putting money, FUND-centric.
 *
 * Three sections (Hedge Funds / Institutional / Whales). Each fund is ONE ROW
 * listing the stocks it's moving money into (from /sepa/money-movement, which
 * inverts our 13F whale cache). Stocks that overlap our SEPA candidate list or
 * the Pullback-to-MA list get a chip. Top 10 funds per section, expandable.
 * Reuses fundTiers.ts for the ⭐ tier stars. NOT advice (13F is quarter-lagged).
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from './InfoButton';
import { getFundTier, TIER_EMOJI, TIER_LABEL } from '../lib/fundTiers';

type Stock = {
  ticker: string; name: string;
  value: number | null; pct_change: number | null; pct_held: number | null;
  added: number | null; is_sepa: boolean; is_pullback: boolean;
};
type FundRow = {
  fund: string; type: string; total_added: number;
  n_stocks: number; n_sepa: number; n_pullback: number; stocks: Stock[];
};
type SecMove = {
  ticker: string; name: string; n_form13: number; n_form4: number;
  insider_cluster: boolean; n_funds_buying: number; signals: string[];
  score: number; is_sepa: boolean; is_pullback: boolean;
};
type PolRow = {
  ticker: string; name: string; categories: string[]; n_funds_buying: number;
  in_scan: boolean; is_sepa: boolean; is_pullback: boolean;
};
type Payload = {
  sections: Record<'hedge_fund' | 'institutional' | 'whales', FundRow[]>;
  section_labels: Record<string, string>;
  sec_moves: SecMove[];
  political: { potus_family: PolRow[]; us_gov: PolRow[] };
  not_wired: string[];
  tickers_covered: number; funds_total: number; generated_at: number; error?: string;
};

const SECTION_ORDER: ('hedge_fund' | 'institutional' | 'whales')[] =
  ['hedge_fund', 'institutional', 'whales'];
const TYPE_LABEL: Record<string, string> = {
  hedge_fund: 'hedge fund', index_giant: 'index giant', other: 'institution',
};
const STOCKS_SHOWN = 18;   // stock chips visible before "+N more"
const FUNDS_SHOWN = 10;    // fund rows before "show all"

function fmtMoney(v: number): string {
  if (!v) return '—';
  const a = Math.abs(v);
  if (a >= 1e12) return `+$${(a / 1e12).toFixed(1)}T`;
  if (a >= 1e9) return `+$${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `+$${(a / 1e6).toFixed(1)}M`;
  return `+$${(a / 1e3).toFixed(0)}K`;
}

const PageInfo = (
  <>
    <p>
      <strong>Money Movement</strong> flips our 13F whale data around: instead of
      "which funds hold this stock," it shows — for each giant — <strong>the
      stocks they're moving money into</strong>, in one row.
    </p>
    <ul>
      <li><strong>Hedge Funds</strong> — Two Sigma, Renaissance, Citadel, Berkshire…</li>
      <li><strong>Institutional</strong> — the index giants (Vanguard, BlackRock, State Street).</li>
      <li><strong>Whales</strong> — other large 13F holders (Fidelity, Morgan Stanley, JPMorgan…).</li>
    </ul>
    <p>
      Funds rank by <strong>$ added last quarter</strong>; a stock that's also on
      our <strong>SEPA</strong> or <strong>Pullback-to-MA</strong> list gets a chip
      (those sort first). 13F filings are quarter-lagged — informational, not advice.
    </p>
  </>
);

export function MoneyMovement() {
  const navigate = useNavigate();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/money-movement`);
      if (r.ok) setData(await r.json());
    } catch {
      /* keep last */
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <section className="money-movement">
      <div className="mm-head">
        <div className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          🏦 Money Movement
          <InfoButton inline title="Money Movement">{PageInfo}</InfoButton>
        </div>
        <h2 className="mm-title">Where the giants are buying</h2>
        <p className="mm-lede">
          Each fund, one row — the stocks it's moving money into. Chips mark the
          names that also hit our <strong>SEPA</strong> / <strong>Pullback-to-MA</strong> lists.
        </p>
        {data && (
          <div className="mm-stats mono">
            {data.funds_total} funds · {data.tickers_covered} tickers with 13F data
          </div>
        )}
      </div>

      {loading && !data && <p className="mono" style={{ opacity: 0.7 }}>…inverting 13F flows</p>}

      {data && SECTION_ORDER.map((sec) => {
        const rows = data.sections[sec] || [];
        if (rows.length === 0) return null;
        const isOpen = !!expanded[sec];
        const shown = isOpen ? rows : rows.slice(0, FUNDS_SHOWN);
        return (
          <div key={sec} className="mm-section">
            <div className="mm-section__label">
              {data.section_labels[sec]} <span className="mono">· {rows.length}</span>
            </div>
            {shown.map((f) => (
              <FundRowView key={f.fund} f={f} onTicker={(t) =>
                navigate(`/sepa/${encodeURIComponent(t)}`, { state: { from: '/leaderboard', label: 'Leaderboard' } })} />
            ))}
            {rows.length > FUNDS_SHOWN && (
              <button type="button" className="mm-more"
                onClick={() => setExpanded((e) => ({ ...e, [sec]: !isOpen }))}>
                {isOpen ? 'Show fewer' : `Show all ${rows.length} funds`}
              </button>
            )}
          </div>
        );
      })}

      {/* SEC big moves & coordinated buying (13D activist / insider cluster / coordinated funds) */}
      {data && data.sec_moves && data.sec_moves.length > 0 && (
        <div className="mm-section">
          <div className="mm-section__label">
            SEC Big Moves &amp; Coordinated <span className="mono">· {data.sec_moves.length}</span>
          </div>
          <div className="mm-stocks">
            {data.sec_moves.map((r) => (
              <button
                key={r.ticker} type="button"
                className={`mm-sec${r.is_sepa ? ' mm-stock--sepa' : ''}${r.is_pullback ? ' mm-stock--pb' : ''}`}
                onClick={() => navigate(`/sepa/${encodeURIComponent(r.ticker)}`, { state: { from: '/leaderboard', label: 'Leaderboard' } })}
                title={`${r.ticker} · ${r.signals.join(', ')}`}
              >
                <span className="mm-sec__t">{r.ticker}</span>
                {r.n_form13 > 0 && <span className="mm-sig mm-sig--activist" title="SC 13D/G activist filings">🏛 {r.n_form13}×13D</span>}
                {r.insider_cluster && <span className="mm-sig mm-sig--insider" title="Insider cluster buy (≥2 insiders)">👥 cluster</span>}
                {r.n_funds_buying >= 10 && <span className="mm-sig mm-sig--coord" title="Coordinated multi-fund accumulation">🌊 {r.n_funds_buying}</span>}
                {r.is_sepa && <span className="mm-tag mm-tag--sepa">SEPA</span>}
                {r.is_pullback && <span className="mm-tag mm-tag--pb">PB</span>}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* POTUS family + US Gov (curated disclosure list) */}
      {data && data.political && (data.political.potus_family.length > 0 || data.political.us_gov.length > 0) && (
        <div className="mm-section">
          <div className="mm-section__label">Government &amp; POTUS-Family Disclosures</div>
          <PoliticalRowView label="POTUS family" rows={data.political.potus_family}
            onTicker={(t) => navigate(`/sepa/${encodeURIComponent(t)}`, { state: { from: '/leaderboard', label: 'Leaderboard' } })} />
          <PoliticalRowView label="US Government" rows={data.political.us_gov}
            onTicker={(t) => navigate(`/sepa/${encodeURIComponent(t)}`, { state: { from: '/leaderboard', label: 'Leaderboard' } })} />
          <p className="mm-note">Curated disclosure list (OGE filings / news) — informational, not a buy/sell signal.</p>
        </div>
      )}

      {data && data.not_wired && data.not_wired.length > 0 && (
        <p className="mm-note">Not tracked: {data.not_wired.join('; ')}.</p>
      )}
    </section>
  );
}

function PoliticalRowView({ label, rows, onTicker }: { label: string; rows: PolRow[]; onTicker: (t: string) => void }) {
  if (!rows.length) return null;
  return (
    <div className="mm-pol">
      <span className="mm-pol__label">{label}</span>
      <div className="mm-stocks">
        {rows.map((r) => (
          <button
            key={r.ticker} type="button"
            className={`mm-stock${r.is_sepa ? ' mm-stock--sepa' : ''}${!r.in_scan ? ' mm-stock--dim' : ''}`}
            onClick={() => onTicker(r.ticker)}
            title={`${r.ticker}${r.n_funds_buying ? ` · ${r.n_funds_buying} funds buying` : ''}${r.is_sepa ? ' · SEPA candidate' : ''}`}
          >
            {r.ticker}
            {r.n_funds_buying > 0 && <span className="mm-pol__n">{r.n_funds_buying}🐋</span>}
            {r.is_sepa && <span className="mm-tag mm-tag--sepa">SEPA</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

function FundRowView({ f, onTicker }: { f: FundRow; onTicker: (t: string) => void }) {
  const tier = getFundTier(f.fund);
  const overlaps = f.n_sepa + f.n_pullback;
  const more = f.n_stocks - Math.min(f.stocks.length, STOCKS_SHOWN);
  return (
    <div className="mm-fund">
      <div className="mm-fund__head">
        {tier && <span className="mm-tier" title={TIER_LABEL[tier.tier!]}>{TIER_EMOJI[tier.tier!]}</span>}
        <span className="mm-fund__name">{tier?.display || f.fund}</span>
        <span className="mm-fund__type">({TYPE_LABEL[f.type] || f.type})</span>
        <span className="mm-fund__added mono">{fmtMoney(f.total_added)}</span>
        <span className="mm-fund__meta mono">{f.n_stocks} stocks{overlaps ? ` · ${overlaps} on our list` : ''}</span>
      </div>
      <div className="mm-stocks">
        {f.stocks.slice(0, STOCKS_SHOWN).map((s) => (
          <button
            key={s.ticker}
            type="button"
            className={`mm-stock${s.is_sepa ? ' mm-stock--sepa' : ''}${s.is_pullback ? ' mm-stock--pb' : ''}`}
            onClick={() => onTicker(s.ticker)}
            title={`${s.ticker}${s.pct_change != null ? ` · ${s.pct_change > 0 ? '+' : ''}${s.pct_change}% QoQ` : ''}${s.added ? ` · ${fmtMoney(s.added)} added` : ''}${s.is_sepa ? ' · SEPA candidate' : ''}${s.is_pullback ? ' · Pullback-to-MA' : ''}`}
          >
            {s.ticker}
            {s.is_sepa && <span className="mm-tag mm-tag--sepa">SEPA</span>}
            {s.is_pullback && <span className="mm-tag mm-tag--pb">PB</span>}
          </button>
        ))}
        {more > 0 && <span className="mm-stock mm-stock--more">+{more}</span>}
      </div>
    </div>
  );
}
