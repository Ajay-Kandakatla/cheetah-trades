/* 🔥 Hottest — sectors ranked, opening into industries and then names.
 *
 * Ajay 2026-09-11: "From the sectors. Can you find the hottest of the sectors
 * like the most growth and put them in to a new tab" · "hottest from last 5
 * days and current. Like ANDE was never on my list but its growing" · "List
 * needs to be hottest of the sectors and then hottest from a sector in to a
 * table. Like the catalyst and keep sales and other crucial metrics for me."
 *
 * Asked which window and which grouping, he chose all three legs (today / 5d /
 * 21d) and sectors that expand into industries.
 *
 * WHY ALL ELEVEN SECTORS SHOW, not just the hot end: his own example is a
 * strong name in a COLD sector. ANDE is 2nd of Consumer Defensive's 76 over 21
 * days while the sector sits 8th of 11. A hot-sectors-only list cannot reach
 * it, so every sector is listed and the cold ones simply sort last.
 *
 * The backend owns every number (rotation/hottest.py). Nothing here recomputes
 * heat or traction — two definitions on two surfaces is how the strip and this
 * board would start disagreeing.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { GrowthChip } from './GrowthChip';
import { SignalWatchButton } from './SignalWatchButton';
import { InfoButton } from './InfoButton';

export type HsName = {
  symbol: string; name?: string | null; industry?: string | null;
  last_close?: number | null;
  rel_1d?: number | null; rel_5d?: number | null; rel_21d?: number | null;
  ret_1d?: number | null; ret_5d?: number | null; ret_21d?: number | null;
  traction?: number | null; vs_group_21?: number | null; at_demand?: boolean;
  sales_yoy?: number | null; sales_tier?: string | null;
  sales_accelerating?: boolean | null; sales_prior_yoy?: number | null;
  q_eps_yoy?: number | null; y_eps_growth?: number | null;
  net_margin?: number | null; margin_expanding?: boolean | null;
  eq_score?: number | null; eq_tier?: string | null; code_33?: boolean | null;
  sales_backed?: boolean | null; inventory_flag?: boolean | null;
  next_earnings?: string | null; earnings_when?: string | null;
};
/** The fundamental columns a GROUP row carries: the median of its full
 *  membership, computed in rotation/hottest.py::_fund_medians. Before
 *  2026-09-12 these columns were blank on sector and industry rows, so
 *  sorting on one of them reordered the tree for no visible reason. */
export type HsFundMedians = {
  sales_yoy?: number | null; sales_tier?: string | null;
  q_eps_yoy?: number | null; net_margin?: number | null;
  eq_score?: number | null; fund_basis?: string | null;
};
export type HsIndustry = HsFundMedians & {
  group: string; n_full: number; ranked: boolean; thin: boolean; basis: string;
  rel_1d?: number | null; rel_5d?: number | null; rel_21d?: number | null;
  names: HsName[]; names_total: number;
};
export type HsSector = HsFundMedians & {
  group: string; n_full: number; sampled_of?: number | null; sampled_used?: number | null;
  basis: string; n_measured?: number | null;
  rel_1d?: number | null; rel_5d?: number | null; rel_21d?: number | null;
  industries: HsIndustry[]; names: HsName[]; names_total: number;
};
export type HsTheme = HsFundMedians & {
  group: string; n_full: number; ranked: boolean; thin: boolean; basis: string;
  rel_1d?: number | null; rel_5d?: number | null; rel_21d?: number | null;
  names: HsName[]; names_total: number;
};
export type HsPayload = {
  as_of?: string; benchmark?: string; sorted_by?: string; sorted_dir?: string;
  sortable?: string[]; legs?: string[];
  sectors: HsSector[];
  /** Our own curated rosters — robotics, nuclear, quantum, the AI complex,
   *  crypto. They cut ACROSS the provider's sectors (robotics spans Technology,
   *  Industrials and Consumer Cyclical), so they are a FLAT list with no
   *  industry layer, and they ride alongside the sectors rather than replacing
   *  them: the two disagree and the objective label wins. */
  themes?: HsTheme[];
  coverage?: { priced?: number; with_fundamentals?: number; pct?: number | null };
  note?: string; reason?: string; built_at_iso?: string; stale?: boolean;
};

const SORTS = ['rel_1d', 'rel_5d', 'rel_21d'] as const;

/** Readable names for the curated rosters. The payload ships the snake_case id
 *  (it is the key everything else in the app joins on); only the display
 *  changes here. An id with no entry prints as-is rather than being prettified
 *  by a rule that would one day mangle a new one. */
export const THEME_LABELS: Record<string, string> = {
  ai_semis: 'AI semis',
  semi_materials: 'Semi materials',
  ai_power: 'AI power',
  ai_infra: 'AI infra',
  datacenter_build: 'Datacenter build',
  optical: 'Optical',
  robotics: 'Robotics',
  nuclear: 'Nuclear',
  energy: 'Energy (curated)',
  quantum: 'Quantum',
  space: 'Space',
  defense: 'Defense',
  rare_earth: 'Rare earth',
  crypto: 'Crypto equities',
};

export type HsDir = 'desc' | 'asc';
/** Every column, in print order, with the payload key it ranks on.
 *
 *  Ajay 2026-09-12: "Add sort in this". The sort is a BACKEND round-trip, not
 *  a client-side reorder, because the payload holds only `names_per_group`
 *  rows per group — sorting in the browser would rank the visible 25 and never
 *  reach the 46th name. `asc` is the useful direction for Next ER (who reports
 *  soonest) and for hunting the weak end of a column. */
export const HS_COLS: { key: string; label: string; num: boolean; title?: string }[] = [
  { key: 'rel_1d', label: 'Today', num: true },
  { key: 'rel_5d', label: '5 days', num: true },
  { key: 'rel_21d', label: '21 days', num: true },
  { key: 'sales_yoy', label: 'Sales YoY', num: true },
  { key: 'sales_tier', label: 'Sales trend', num: false,
    title: 'ranks explosive › strong › steady › weak › declining' },
  { key: 'q_eps_yoy', label: 'Q EPS', num: true },
  { key: 'net_margin', label: 'Margin', num: true },
  { key: 'eq_score', label: 'Quality', num: true,
    title: 'Minervini Ch.8 earnings quality · 🎯 Code 33 · ⚠️ inventory vs sales' },
  { key: 'next_earnings', label: 'Next ER', num: false,
    title: 'ascending = who reports soonest' },
];

/** The arrow a header shows. Inactive columns show nothing — an idle ⇅ on
 *  nine headers is nine pieces of furniture. */
export function arrow(active: boolean, dir: HsDir): string {
  return active ? (dir === 'desc' ? ' ▼' : ' ▲') : '';
}

/** An em-dash, never a zero — a missing quarter is not flat growth. */
export function pct(v: number | null | undefined, dp = 1): string {
  return typeof v === 'number' && Number.isFinite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(dp)}%` : '—';
}
/** Tone by the value's OWN sign. Ajay 2026-09-10: "what ever today is what I
 *  wanna see in green" — so today's cell is green only when today is up, even
 *  inside a row that is hot over five days. */
export function tone(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return 'hs-flat';
  return v > 0 ? 'hs-up' : v < 0 ? 'hs-dn' : 'hs-flat';
}
export function tierChip(t?: string | null): string {
  const k = (t || '').toLowerCase();
  if (k === 'explosive') return '🚀';
  if (k === 'strong') return '💪';
  if (k === 'steady') return '➖';
  if (k === 'weak') return '🐌';
  if (k === 'declining') return '🔻';
  return '';
}

function LegCells({ r }: { r: { rel_1d?: number | null; rel_5d?: number | null; rel_21d?: number | null } }) {
  return (
    <>
      {SORTS.map((k) => (
        <td key={k} className={`mono hs-num ${tone(r[k])}`}>{pct(r[k])}</td>
      ))}
    </>
  );
}

/** The four fundamental cells + the trend + Next ER, for a GROUP row (sector
 *  or industry). Medians of the full membership — the row's own read on the
 *  column it may be sorted by. */
function GroupFundCells({ r }: { r: HsFundMedians }) {
  const t = r.fund_basis || 'median of full membership';
  return (
    <>
      <td className={`mono hs-num hs-med ${tone(r.sales_yoy)}`} title={t}>{pct(r.sales_yoy)}</td>
      <td className="hs-tier hs-med" title={t}>{tierChip(r.sales_tier)} {r.sales_tier || '—'}</td>
      <td className={`mono hs-num hs-med ${tone(r.q_eps_yoy)}`} title={t}>{pct(r.q_eps_yoy, 0)}</td>
      <td className={`mono hs-num hs-med ${tone(r.net_margin)}`} title={t}>{pct(r.net_margin)}</td>
      <td className="mono hs-num hs-med" title={t}>
        {typeof r.eq_score === 'number' ? r.eq_score.toFixed(0) : '—'}
      </td>
      <td className="hs-spacer" />
    </>
  );
}

function NameRow({ r }: { r: HsName }) {
  return (
    <tr className="hs-name">
      <td className="hs-sym">
        <TickerLink ticker={r.symbol} fromLabel="Hottest sectors" />
        {/* 🚀 also on the Explosive Growth board (Ajay 2026-09-11:
            "ALL TABS IN CHART MAPS"). */}
        <GrowthChip symbol={r.symbol} className="hs-badge" />
        {/* Ajay 2026-09-11: "add to signals button in that table I wanna pick a
            few stocks from this". NOT compact — compact prints a bare "+" which
            sits next to TickerLink's ☆ and reads as decoration rather than a
            control. The word is what makes it a button. */}
        <SignalWatchButton symbol={r.symbol} />
        <div className="hs-coname">{r.name || ''}</div>
      </td>
      <LegCells r={r} />
      <td className={`mono hs-num ${tone(r.sales_yoy)}`} title={
        r.sales_prior_yoy != null ? `prior quarter ${pct(r.sales_prior_yoy)}` : undefined}>
        {pct(r.sales_yoy)}{r.sales_accelerating ? ' ⚡' : ''}
      </td>
      <td className="hs-tier" title={r.sales_tier || 'no filed quarterly series from our provider'}>
        {tierChip(r.sales_tier)} {r.sales_tier || '—'}
      </td>
      <td className={`mono hs-num ${tone(r.q_eps_yoy)}`}>{pct(r.q_eps_yoy, 0)}</td>
      <td className={`mono hs-num ${tone(r.net_margin)}`}>
        {pct(r.net_margin)}{r.margin_expanding ? ' ↑' : ''}
      </td>
      <td className="mono hs-num" title={r.eq_tier || undefined}>
        {typeof r.eq_score === 'number' ? r.eq_score.toFixed(0) : '—'}
        {r.code_33 ? ' 🎯' : ''}{r.inventory_flag ? ' ⚠️' : ''}
      </td>
      <td className="hs-er">
        {r.next_earnings || '—'}{r.earnings_when ? ` ${r.earnings_when}` : ''}
      </td>
    </tr>
  );
}

export function HottestSectors() {
  const [data, setData] = useState<HsPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<string>('rel_5d');
  const [dir, setDir] = useState<HsDir>('desc');
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [byIndustry, setByIndustry] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/rotation/hottest?sort=${encodeURIComponent(sort)}&dir=${dir}`,
          { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: HsPayload) => { setData(j); setErr(null); setLoading(false); })
      .catch((e) => { setErr(String(e?.message ?? e)); setLoading(false); });
  }, [sort, dir]);
  useEffect(() => { load(); }, [load]);

  const sectors = useMemo(() => data?.sectors || [], [data]);
  const themes = useMemo(() => data?.themes || [], [data]);
  const toggle = (k: string) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  /** Click a new column → sort it DESC (the interesting end of every column
   *  except Next ER). Click the active column again → flip direction. */
  const clickSort = (k: string) => {
    if (k === sort) setDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else { setSort(k); setDir(k === 'next_earnings' ? 'asc' : 'desc'); }
  };

  if (err) return <div className="cm-note cm-note-warn">Hottest sectors unavailable: {err}</div>;
  if (!data && loading) return <div className="cm-note">Reading the rotation table…</div>;
  if (data?.reason) return <div className="cm-note cm-note-warn">{data.reason}</div>;

  return (
    <div className="hs">
      <div className="hs-controls">
        {/* The three leg chips used to live here. They set the same backend
            `sort` the column headers now do, and two controls for one piece of
            state is how a board starts lying about its own order. The header
            arrow IS the state. */}
        <div className="hs-sorts">
          <span className="hs-sorted-by">
            ranked on <b>{HS_COLS.find((c) => c.key === sort)?.label || sort}</b>
            {dir === 'desc' ? ' ▼ high → low' : ' ▲ low → high'}
            <span className="hs-dim"> · click any column header</span>
          </span>
        </div>
        <label className="hs-toggle">
          <input type="checkbox" checked={byIndustry}
                 onChange={(e) => setByIndustry(e.target.checked)} />
          Break into industries
        </label>
        <InfoButton inline title="🔥 Hottest — how to read this">
          <p>Every sector ranked on <b>{HS_COLS.find((c) => c.key === sort)?.label || sort}</b>
            against <b>{data?.benchmark || 'RSP'}</b>,
            the equal-weight benchmark — so a name is measured against the average stock, not the
            mega-caps. Open a sector for its industries, then its names.</p>
          <p><b>All eleven sectors are listed, not just the hot ones.</b> A strong name often sits in
            a cold sector: ANDE is 2nd of Consumer Defensive&rsquo;s 76 over 21 days while the sector
            is 8th of 11. Listing only the hot end would hide exactly the names this board is for.</p>
          <p><b>Two populations.</b> Sector and industry heat is the rotation grid&rsquo;s sampled
            median — the same number the Hot-sectors strip prints, reused so the two can never
            disagree. Name rows are the <b>full</b> membership. Industries too small for a ranked row
            still show, flagged <i>thin</i>: a 6-name median is not a 25-name one.</p>
          <p><b>Every column sorts, and it sorts on the server.</b> Click a header to rank on
            it; click it again to flip the direction. The board keeps 25 names per group, so a
            browser-side sort would only reorder those 25 — the round-trip re-ranks the FULL
            membership and then takes the top 25 of the column you picked. A blank always sorts
            LAST, in both directions. Sector and industry rows show the <b>median of their full
            membership</b> in the fundamental columns, so a sort there has something visible behind
            it; the three return legs stay the rotation grid&rsquo;s sampled median.</p>
          <p><b>Our rosters sit above the sectors.</b> Robotics, the AI complex, nuclear,
            quantum, rare earth, crypto — these are lists we curated, and they cut ACROSS the
            provider&rsquo;s sectors (robotics spans Technology, Industrials and Consumer
            Cyclical), so they have no industry layer. They <i>ride alongside</i> and never
            overrule: on 2026-09-09 our <code>ai_semis</code> roster read −0.28 over 21 days while
            the provider&rsquo;s <code>Semiconductors</code> cohort read −1.95 — opposite signs on
            the same question. &ldquo;How are semis doing&rdquo; is a question about all semis, so
            the objective label answers it. A roster too small for a ranked row still shows,
            flagged <i>thin</i>.</p>
          <p><b>Names are ranked by return, not by traction.</b> Traction measures acceleration, and it
            ranks ANDE 23rd of 76 while the 5-day ranks it 3rd.</p>
          <p><b>This is a discovery list, not a signal.</b> It is trailing returns — nothing here is
            backtested and none of it is a buy signal. Sales, EPS and margin come from the weekly
            research cache, so they can be up to a week behind a fresh print. A blank prints as
            &mdash;, never as a zero.</p>
        </InfoButton>
      </div>

      <div className="hs-meta">
        <span>as of {data?.as_of || '—'}</span>
        {data?.coverage?.pct != null ? (
          <span> · sales on {data.coverage.pct}% of {data.coverage.priced} priced names</span>
        ) : null}
        {data?.stale ? <span className="hs-stale"> · build is stale</span> : null}
      </div>

      <div className="hs-scroll">
        <table className="hs-table">
          <thead>
            <tr>
              <th className="hs-sym">Sector / Name</th>
              {HS_COLS.map((c) => {
                const on = sort === c.key;
                return (
                  <th key={c.key} className={`${c.num ? 'hs-num' : ''}${on ? ' is-sorted' : ''}`}
                      aria-sort={on ? (dir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                    <button type="button" className="hs-sort" onClick={() => clickSort(c.key)}
                            title={c.title ? `${c.title} · click to sort` : 'click to sort'}>
                      {c.label}{arrow(on, dir)}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {/* THEMES FIRST (Ajay 2026-09-12: "Where is Robitics and crypto
                here?"). They were tracked all along — the Hot-sectors strip has
                ranked them as chips for days — but this board only ever read
                the sector and industry grains, so a roster he asked for by name
                was invisible on the one surface built to answer "what is hot".
                Above the sectors because they are the rosters he curated; the
                provider's eleven follow underneath, unchanged. */}
            {themes.length ? (
              <tr className="hs-grain"><td colSpan={10}>
                our rosters · cut across the sectors below
              </td></tr>
            ) : null}
            {themes.map((t) => {
              const k = `t:${t.group}`;
              const isOpen = !!open[k];
              return (
                <>
                  <tr key={k} className={`hs-sector hs-theme${isOpen ? ' is-open' : ''}`}>
                    <td className="hs-sym">
                      <button type="button" className="hs-disc" aria-expanded={isOpen}
                              onClick={() => toggle(k)}>
                        {isOpen ? '▾' : '▸'} {THEME_LABELS[t.group] || t.group}
                      </button>
                      <span className="hs-n" title={
                        t.thin
                          ? `${t.n_full} names — too few for a ranked row of its own, so this median is thinner than a sector's. Kept because you asked for these rosters by name.`
                          : `${t.n_full} names · ${t.basis}`}>
                        {t.n_full}{t.thin ? ' · thin' : ''}
                      </span>
                    </td>
                    <LegCells r={t} />
                    <GroupFundCells r={t} />
                  </tr>
                  {isOpen ? t.names.map((r) => <NameRow key={`${k}|${r.symbol}`} r={r} />) : null}
                  {isOpen && t.names_total > t.names.length ? (
                    <tr key={`${k}|more`}><td colSpan={10} className="hs-more">
                      showing {t.names.length} of {t.names_total}
                    </td></tr>
                  ) : null}
                </>
              );
            })}
            {themes.length ? (
              <tr className="hs-grain"><td colSpan={10}>
                the provider&rsquo;s sectors
              </td></tr>
            ) : null}
            {sectors.map((s) => {
              const k = `s:${s.group}`;
              const isOpen = !!open[k];
              return (
                <>
                  <tr key={k} className={`hs-sector${isOpen ? ' is-open' : ''}`}>
                    <td className="hs-sym">
                      <button type="button" className="hs-disc" aria-expanded={isOpen}
                              onClick={() => toggle(k)}>
                        {isOpen ? '▾' : '▸'} {s.group}
                      </button>
                      <span className="hs-n" title={
                        s.sampled_used && s.sampled_of && s.sampled_used < s.sampled_of
                          ? `heat measured on ${s.sampled_used} of ${s.sampled_of} names (the rotation grid's sample); the ${s.n_full} name rows below are the full membership`
                          : `${s.n_full} names`}>
                        {s.n_full}
                        {s.sampled_used && s.sampled_of && s.sampled_used < s.sampled_of
                          ? ` · heat on ${s.sampled_used}` : ''}
                      </span>
                    </td>
                    <LegCells r={s} />
                    <GroupFundCells r={s} />
                  </tr>
                  {isOpen && byIndustry ? s.industries.map((ind) => {
                    const ik = `${k}|i:${ind.group}`;
                    const iOpen = !!open[ik];
                    return (
                      <>
                        <tr key={ik} className="hs-industry">
                          <td className="hs-sym">
                            <button type="button" className="hs-disc hs-disc--ind" aria-expanded={iOpen}
                                    onClick={() => toggle(ik)}>
                              {iOpen ? '▾' : '▸'} {ind.group}
                            </button>
                            <span className="hs-n" title={`${ind.n_full} names · ${ind.basis}`}>
                              {ind.n_full}{ind.thin ? ' · thin' : ''}
                            </span>
                          </td>
                          <LegCells r={ind} />
                          <GroupFundCells r={ind} />
                        </tr>
                        {iOpen ? ind.names.map((r) => <NameRow key={`${ik}|${r.symbol}`} r={r} />) : null}
                        {iOpen && ind.names_total > ind.names.length ? (
                          <tr key={`${ik}|more`}><td colSpan={10} className="hs-more">
                            showing {ind.names.length} of {ind.names_total}
                          </td></tr>
                        ) : null}
                      </>
                    );
                  }) : null}
                  {isOpen && !byIndustry ? s.names.map((r) => <NameRow key={`${k}|${r.symbol}`} r={r} />) : null}
                  {isOpen && !byIndustry && s.names_total > s.names.length ? (
                    <tr key={`${k}|more`}><td colSpan={10} className="hs-more">
                      showing {s.names.length} of {s.names_total}
                    </td></tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
      {data?.note ? <p className="rw__note">{data.note}</p> : null}
    </div>
  );
}
