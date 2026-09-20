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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { GrowthChip } from './GrowthChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { BandStructureChip } from './BandStructureChip';
import { HiddenCount } from './HiddenCount';
import { useEnterableFilter, useEnterablePartition } from '../hooks/useEnterableFilter';
import { isShown } from '../lib/enterable';
import { useBounceRoom } from '../hooks/useBounceRoom';
import type { BandStructureStudy, BounceRoomRow, ExplosiveStudy } from '../lib/bounceRoom';
import { SignalWatchButton } from './SignalWatchButton';
import { InfoButton } from './InfoButton';

/** Which session the day column on THIS row came from. `live` = the name's own
 *  move so far in the current session; `close` = the rotation snapshot's last
 *  finished session. Backend-owned (rotation/hottest.py) — never inferred here
 *  from whether a number happens to look fresh. */
export type HsD1Source = 'live' | 'close';
/** The day leg's basis for the whole board. Group rows are ALWAYS `close`:
 *  a sector median is taken over every member it counts, and a median mixing
 *  live members with last-close members describes no session at all. */
export type HsD1 = {
  basis?: HsD1Source; live?: boolean;
  /** When the live read was taken (ISO), and which close the rest is from. */
  as_of?: string | null; close_as_of?: string | null;
  benchmark?: string | null; benchmark_move?: number | null;
  symbols?: number | null; live_names?: number | null;
  group_basis?: HsD1Source;
  /** Plain-English why, when the board is NOT live. Must reach the screen. */
  reason?: string | null; note?: string | null;
  /** WHY a re-scan cannot help: the market calendar's own reason (weekend /
   *  holiday YYYY-MM-DD), or null on a trading day. Backend-owned, so nothing
   *  here ever string-matches prose to decide the tape is shut. */
  market_closed?: string | null;
  /** Is the REGULAR session open (supply_demand.bounce_room.in_session)?
   *  `null` when the clock could not be asked — the button then behaves as it
   *  did before this existed rather than guessing. */
  in_session?: boolean | null;
  /** "9:30-16:00 ET", rendered from the constants that enforce it — never a
   *  clock retyped on this surface. */
  session_window?: string | null;
};
/** The two day-leg fields every row carries since 2026-09-16: the snapshot
 *  value is kept whatever the live read did, and the row says which it shows. */
export type HsDayLeg = {
  rel_1d?: number | null; rel_1d_close?: number | null;
  ret_1d_close?: number | null; d1_source?: HsD1Source;
};

export type HsName = HsDayLeg & {
  symbol: string; name?: string | null; industry?: string | null;
  last_close?: number | null;
  rel_5d?: number | null; rel_21d?: number | null;
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
export type HsIndustry = HsFundMedians & HsDayLeg & {
  group: string; n_full: number; ranked: boolean; thin: boolean; basis: string;
  rel_5d?: number | null; rel_21d?: number | null;
  names: HsName[]; names_total: number;
};
/** 📰 The day's two-sided news tag for a sector (Ajay 2026-09-19: "if you
 *  see any postive news I would like you to see a bullish and bearish case
 *  result for a stocks and add it to the sector as a tag for that day").
 *
 *  Written by the cron in backend/rotation/sector_news_tags.py, served as a
 *  pure read. `measured` is ALWAYS false and `read_by` names who wrote the
 *  prose — the surface must never present this as a measurement, and there
 *  is no sentiment score here because we do not have a measured one. */
export type HsDayTag = {
  date: string;
  sector: string;
  symbol: string;
  company?: string | null;
  positive: boolean;
  why_positive?: string | null;
  bull: string;
  bear: string;
  headline_count?: number | null;
  trigger?: { title?: string | null; url?: string | null;
              source?: string | null; published?: number | null } | null;
  /** EVERY headline the model was shown, not just the trigger — the audit
   *  trail for "grounded in the headlines". The news cache rolls within
   *  hours, so without these a number in the prose cannot be traced back. */
  headlines?: { title?: string | null; source?: string | null;
                url?: string | null; published?: number | null }[] | null;
  facts?: Record<string, unknown> | null;
  read_by?: string | null;
  measured?: boolean;
};

export type HsSector = HsFundMedians & HsDayLeg & {
  group: string; n_full: number; sampled_of?: number | null; sampled_used?: number | null;
  basis: string; n_measured?: number | null;
  rel_5d?: number | null; rel_21d?: number | null;
  industries: HsIndustry[]; names: HsName[]; names_total: number;
  /** null when today produced no tag for this sector — the board then
   *  renders exactly as it did before any of this existed. */
  day_tag?: HsDayTag | null;
};
export type HsTheme = HsFundMedians & HsDayLeg & {
  group: string; n_full: number; ranked: boolean; thin: boolean; basis: string;
  rel_5d?: number | null; rel_21d?: number | null;
  names: HsName[]; names_total: number;
};
export type HsPayload = {
  as_of?: string; sorted_by?: string; sorted_dir?: string;
  /** The endpoint answers with the tracker's benchmark OBJECT on some builds
   *  and a bare symbol on others — `benchSymbol` resolves both, because a
   *  header that prints "[object Object]" names no benchmark at all. */
  benchmark?: string | { symbol?: string | null } | null;
  /** What the day column is showing, and why (2026-09-16). */
  d1?: HsD1 | null;
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
  cloud_infra: 'Cloud infra',
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

/* ── "Today" has to mean today (Ajay 2026-09-16) ─────────────────────────────
 *
 * He read TENB at +8.3% under a column headed "Today" while his own ticker page
 * had it at −3.70%, live, the same minute. Both were right: the rotation
 * snapshot is built after the close, so the column was printing the PREVIOUS
 * session under today's word. The backend now serves the live move on the name
 * rows; these helpers make sure the header, the as-of line and any row that
 * missed the live read can never claim a number they do not have. */

/** The benchmark's symbol, whichever shape the payload used. */
export function benchSymbol(d?: Pick<HsPayload, 'benchmark'> | null): string {
  const b = d?.benchmark;
  if (typeof b === 'string' && b.trim()) return b;
  const s = b && typeof b === 'object' ? b.symbol : null;
  return typeof s === 'string' && s.trim() ? s : 'RSP';
}

/** The day column's header. "Today" ONLY when the number is today's; otherwise
 *  the session it actually came from, so the header cannot lie on its own. */
export function d1Label(d?: Pick<HsPayload, 'd1' | 'as_of'> | null): string {
  if (d?.d1?.live) return 'Today';
  const day = d?.d1?.close_as_of || d?.as_of;
  return day ? `Last close ${day}` : 'Last close';
}

/** Any column's printed header. */
export function colLabel(key: string, d?: Pick<HsPayload, 'd1' | 'as_of'> | null): string {
  if (key === 'rel_1d') return d1Label(d);
  return HS_COLS.find((c) => c.key === key)?.label || key;
}

/** A header's hover. The day column's says which session it is, in the
 *  backend's own words, so the explanation cannot drift from the numbers. */
export function colTitle(c: { key: string; title?: string },
                         d?: Pick<HsPayload, 'd1' | 'as_of'> | null): string {
  const own = c.key === 'rel_1d' ? (d?.d1?.note || '') : (c.title || '');
  return own ? `${own} · click to sort` : 'click to sort';
}

/** One day cell, as text + whether it needs the visible "last close" mark.
 *
 *  A row is MARKED when the board is live but this row is not — its number is
 *  the previous session's and would otherwise sit silently in a live column.
 *  When the whole board is on the close the header already says so and 300
 *  identical marks would be noise, so the rows stay clean. */
export function dayCell(r: HsDayLeg, d?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark'> | null,
                        isGroup = false): { text: string; marked: boolean; title: string } {
  const boardLive = !!d?.d1?.live;
  const rowLive = r.d1_source === 'live';
  const day = d?.d1?.close_as_of || d?.as_of || '';
  const marked = boardLive && !rowLive;
  const why = isGroup
    ? `This row is the median over ALL of its members, taken on the ${day || 'last'} close`
      + ' — a median mixing live names with last-close names would describe no session at all.'
    : `No live price came back for this name, so this is its ${day || 'last'} close move`
      + ' — not today.';
  const live = `Today's move so far, measured against ${benchSymbol(d)} the same way the other columns are.`;
  return { text: pct(r.rel_1d), marked, title: marked ? why : (rowLive ? live : '') };
}

/** The line under the controls. It must say which columns are live and which
 *  are the snapshot's, because four of the nine never move intraday. */
export function asOfLine(d?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark'> | null): string {
  const day = d?.d1?.close_as_of || d?.as_of || '—';
  if (d?.d1?.live) {
    return `Today is live, measured against ${benchSymbol(d)} · 5 days, 21 days,`
      + ` Sales YoY and every sector, industry and roster row are from the ${day} close`;
  }
  const why = d?.d1?.reason ? ` (${d.d1.reason})` : '';
  return `every column is from the ${day} close — the last finished session, not today's${why}`;
}

/** Why a ↻ Re-scan cannot help right now, or null when it can.
 *
 *  The calendar's reason is the BACKEND's own sentence, never composed here —
 *  two surfaces wording the same fact differently is how a board starts
 *  disagreeing with itself. */
export function rescanBlockedReason(d?: Pick<HsPayload, 'd1'> | null): string | null {
  const c = d?.d1?.market_closed;
  return typeof c === 'string' && c.trim() ? `the market is closed (${c.trim()})` : null;
}

/** Open tape, but outside the regular session: a re-scan spends the same
 *  provider reads and comes back with the same numbers, because the day bar is
 *  0 before the open and finished after the close.
 *
 *  WARNED, not blocked. He reads extended-hours prints on the Chart Maps tiles
 *  (04:00-20:00, his call), so removing the read outside 9:30-16:00 would take
 *  away a surface he asked for. Making it a block is HIS CALL. */
export function rescanQuietReason(d?: Pick<HsPayload, 'd1'> | null): string | null {
  const s = d?.d1;
  if (!s || s.in_session !== false) return null;
  const w = (s.session_window || '').trim();
  return w ? `the session is shut (${w}) — the day column will not move`
           : 'the session is shut — the day column will not move';
}

/** Does this payload have anything to DRAW? A 200 carrying only `reason` has
 *  not — and replacing a good board with that line is how a failed re-scan
 *  used to blank the whole page. */
export function hasRows(d?: HsPayload | null): boolean {
  return Boolean(d && (((d.sectors || []).length) || ((d.themes || []).length)));
}

/** What one click costs, in the same sentence everywhere it appears. MEASURED
 *  2026-09-18 on the live payload: 7 board chunks (1,721 names / 250), plus 6
 *  bounce-room chunks (1,468 unique name rows / 250) only when the re-rank
 *  changes which names each group shows — both cache keys are sorted sets, so
 *  a pure re-order is free. Never quoted as a bare 7. */
export const RESCAN_COST_SENTENCE =
  'One click is the same provider read as reloading the page — 7 snapshot calls, '
  + 'or 13 when the re-rank changes which names each group shows.';

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

/** The 📰 chip that sits beside a sector's name when the day produced a tag.
 *
 *  Says only WHO it is about and that there is a read to open — the argument
 *  itself lives in the expanded row, because a sector row is already eleven
 *  columns wide and two paragraphs of prose in it would push the returns off
 *  screen on his laptop. */
export function dayTagChipLabel(t: HsDayTag): string {
  return `📰 ${t.symbol}`;
}

/** The tooltip. Deliberately leads with what this is NOT. */
export function dayTagTitle(t: HsDayTag): string {
  return (
    `${t.symbol}${t.company ? ` — ${t.company}` : ''} · ${t.date}\n` +
    `${t.headline_count || 0} headline${t.headline_count === 1 ? '' : 's'} read` +
    `${t.read_by ? ` by ${t.read_by}` : ''}\n` +
    (t.why_positive ? `Why it reads positive: ${t.why_positive}\n` : '') +
    `\nA bull case AND a bear case, written from those headlines and the ` +
    `numbers already on this board. NOT measured, not a signal, not advice. ` +
    `Click to read both.`
  );
}

function DayTagRow({ tag, span }: { tag: HsDayTag; span: number }) {
  const when = tag.trigger?.published
    ? new Date(tag.trigger.published * 1000).toLocaleString()
    : null;
  return (
    <tr className="hs-daytag">
      <td colSpan={span}>
        <div className="hs-daytag__head">
          <strong>{tag.symbol}</strong>
          {tag.company ? <span className="hs-daytag__co">{tag.company}</span> : null}
          <span className={'hs-daytag__read' + (tag.positive ? ' is-pos' : '')}>
            {tag.positive ? 'reads positive' : 'reads neutral / mixed'}
          </span>
          <span className="hs-daytag__meta">
            {tag.date}
            {tag.headline_count ? ` · ${tag.headline_count} headlines` : ''}
            {tag.read_by ? ` · read by ${tag.read_by}` : ''}
          </span>
        </div>

        {tag.trigger?.title ? (
          <div className="hs-daytag__trigger">
            {tag.trigger.url
              ? <a href={tag.trigger.url} target="_blank" rel="noreferrer">{tag.trigger.title}</a>
              : tag.trigger.title}
            <span className="hs-daytag__src">
              {tag.trigger.source || ''}{when ? ` · ${when}` : ''}
            </span>
          </div>
        ) : null}

        {/* What else it read. Folded into a <details> because six headlines
            above two paragraphs would bury the argument — but present, because
            "grounded in the headlines" is only a claim if you can't see them. */}
        {(tag.headlines || []).length > 1 ? (
          <details className="hs-daytag__reads">
            <summary>{tag.headlines!.length} headlines read</summary>
            <ul>
              {tag.headlines!.map((h, i) => (
                <li key={h.url || h.title || i}>
                  {h.url
                    ? <a href={h.url} target="_blank" rel="noreferrer">{h.title}</a>
                    : h.title}
                  {h.source ? <span className="hs-daytag__src">{h.source}</span> : null}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        <div className="hs-daytag__cases">
          <div className="hs-daytag__case hs-daytag__case--bull">
            <span className="hs-daytag__caselbl">Bull case</span>
            <p>{tag.bull}</p>
          </div>
          <div className="hs-daytag__case hs-daytag__case--bear">
            <span className="hs-daytag__caselbl">Bear case</span>
            <p>{tag.bear}</p>
          </div>
        </div>

        {/* Both sides are always shown, which is the whole reason this is a
            briefing and not a recommendation. The line below is not boilerplate:
            this board has no measured edge, and a paragraph of fluent prose is
            exactly the kind of thing that starts reading like one. */}
        <div className="hs-daytag__foot">
          Written from the headlines above and the numbers already on this row.
          Nothing here is measured, no edge is claimed, and this gates no alert
          and enters no lane.
        </div>
      </td>
    </tr>
  );
}

function LegCells({ r, d1, isGroup }: {
  r: HsDayLeg & { rel_5d?: number | null; rel_21d?: number | null };
  d1?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark'> | null; isGroup?: boolean;
}) {
  const day = dayCell(r, d1, !!isGroup);
  return (
    <>
      <td className={`mono hs-num ${tone(r.rel_1d)}${day.marked ? ' hs-d1-close' : ''}`}
          title={day.title || undefined}>
        {day.text}
        {/* Never silent: a close value standing in a live column says so on
            the row, not only in a tooltip. */}
        {day.marked ? <span className="hs-d1-mark"> last close</span> : null}
      </td>
      {(['rel_5d', 'rel_21d'] as const).map((k) => (
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

function NameRow({ r, read, study, bandStudy, d1 }: {
  r: HsName; read?: BounceRoomRow | null; study?: ExplosiveStudy | null;
  bandStudy?: BandStructureStudy | null;
  d1?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark'> | null;
}) {
  return (
    <tr className="hs-name">
      <td className="hs-sym">
        <TickerLink ticker={r.symbol} fromLabel="Hottest sectors" />
        {/* 🚀 also on the Explosive Growth board (Ajay 2026-09-11:
            "ALL TABS IN CHART MAPS"). */}
        <GrowthChip symbol={r.symbol} className="hs-badge" />
        <ExplosiveChip read={read?.explosive} study={study} className="hs-badge" />
        <EnterableChip read={read?.enterable} className="hs-badge" />
        {/* 🪜 Ajay 2026-09-16 "in all chartmaps tabs" — the row's own served
            ceiling/floor read. */}
        <BandStructureChip read={read?.band_structure} study={bandStudy} className="hs-badge" />
        {/* Ajay 2026-09-11: "add to signals button in that table I wanna pick a
            few stocks from this". NOT compact — compact prints a bare "+" which
            sits next to TickerLink's ☆ and reads as decoration rather than a
            control. The word is what makes it a button. */}
        <SignalWatchButton symbol={r.symbol} />
        <div className="hs-coname">{r.name || ''}</div>
      </td>
      <LegCells r={r} d1={d1} />
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

  /* ↻ Re-scan (2026-09-18). Three things this `load` has to get right that the
   * old one did not:
   *  1. LATEST WINS. A sort change fired while a re-scan is in flight must
   *     still go out, and the late first response must be discarded — or the
   *     header reads "ranked on X" over rows that came back ranked on Y.
   *  2. A FAILURE KEEPS THE BOARD. `.catch` no longer drops `data`, and a 200
   *     that came back with no rows is reported without replacing a good board.
   *  3. The in-flight guard stops the BUTTON only (two clicks in one React
   *     tick would both fire before `disabled` re-rendered), never the effect. */
  const seq = useRef(0);
  const inFlight = useRef(false);
  const dataRef = useRef<HsPayload | null>(null);

  const load = useCallback(() => {
    const id = ++seq.current;
    inFlight.current = true;
    setLoading(true);
    fetch(`${API}/rotation/hottest?sort=${encodeURIComponent(sort)}&dir=${dir}`,
          { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: HsPayload) => {
        if (id !== seq.current) return;                  // a newer sort won
        if (!hasRows(j) && hasRows(dataRef.current)) {
          setErr(j?.reason || 'the re-scan came back with no rows');
          return;                                        // keep the good board
        }
        dataRef.current = j; setData(j); setErr(null);
      })
      .catch((e) => { if (id === seq.current) setErr(String(e?.message ?? e)); })
      .finally(() => {
        if (id === seq.current) { inFlight.current = false; setLoading(false); }
      });
  }, [sort, dir]);
  useEffect(() => { load(); }, [load]);
  const onRescan = () => { if (inFlight.current) return; load(); };

  const sectors = useMemo(() => data?.sectors || [], [data]);
  const themes = useMemo(() => data?.themes || [], [data]);
  const toggle = (k: string) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  /* 🧨 ONE bounce-room POST for every name row this table can show (sector,
   * industry and roster groups alike) — the chip and the opt-in ordering read
   * that single map; a per-row fetch on a table this wide is out of the
   * question. */
  const rowSymbols = useMemo(() => {
    const out: string[] = [];
    const eat = (g: { names?: HsName[] }[]) => {
      for (const grp of g || []) for (const n of grp.names || []) if (n.symbol) out.push(n.symbol);
    };
    eat(sectors as { names?: HsName[] }[]);
    eat(themes as { names?: HsName[] }[]);
    for (const s2 of (sectors || []) as { industries?: { names?: HsName[] }[] }[]) {
      eat((s2.industries || []) as { names?: HsName[] }[]);
    }
    return out;
  }, [sectors, themes]);
  const room = useBounceRoom(rowSymbols);
  const readOf = (sym: string) => room.map.get(String(sym).toUpperCase());
  /* 🎯 The enterable cut (2026-09-15) is CLIENT-SIDE over the names this
   * payload carries, and the count line says exactly that: this payload is a
   * SERVER-CUT list — `names_per_group` rows per group, ranked on the server —
   * so hiding four of a group's 25 does not pull the 26th up. A server-side
   * enterable cut is HIS CALL (spec §7.9).
   *
   * WHAT THE NUMBER COUNTS (m4, 2026-09-15): the UNIQUE names in the payload,
   * across every group — themes, sectors and industries — including the groups
   * he has collapsed. Every group on this board starts collapsed, so a line
   * scoped to "rows on screen" would read "0 hidden" on arrival while the cut
   * was already live inside each group; and a name that sits in both its sector
   * and its industry is one name, counted once. The note below is worded to
   * match, because a count line that describes a different set than the one it
   * counted is the same lie as hiding rows quietly. */
  const { enterableOnly, kind, setEnterableOnly, ignoreReasons, toggleReason } = useEnterableFilter();
  const uniqueSymbols = useMemo(
    () => Array.from(new Set(rowSymbols.map((x) => String(x).toUpperCase()))), [rowSymbols]);
  const part = useEnterablePartition(uniqueSymbols, (x) => x, room.map, enterableOnly);
  const enterableCut = enterableOnly && kind !== 'n/a';
  // A plain closure, re-created every render, so it reads the CURRENT ignore
  // set with no dep array — but the set must be passed explicitly, or a name
  // un-hidden in the count line stays missing from its group.
  const showName = (sym: string) => !enterableCut
    || isShown(readOf(sym)?.enterable, 'enterable', ignoreReasons);
  /* NO 🧨 ordering toggle on this board, deliberately. Every other tab gets
   * one; here the payload keeps only `names_per_group` rows per group and the
   * column sorts are a SERVER round-trip for exactly that reason — a
   * browser-side reorder would rank the visible 25 and never reach the 305th
   * Technology name. Ranking these rows by the explosive read has to happen
   * where the truncation happens — i.e. a new `explosive` key in the backend's
   * `/rotation/hottest?sort=` set, which is HIS CALL (a tenth column-sort on a
   * board he already called wide), not a silent browser reorder. The chip
   * still rides on every name, and the omission is pinned by the explosive
   * contract's NO_TOGGLE list in frontend/scripts/contracts.mjs. */
  /** Click a new column → sort it DESC (the interesting end of every column
   *  except Next ER). Click the active column again → flip direction. */
  const clickSort = (k: string) => {
    if (k === sort) setDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else { setSort(k); setDir(k === 'next_earnings' ? 'asc' : 'desc'); }
  };

  /* A COLD failure still shows the failure. What changed on 2026-09-18 is that
   * a failure arriving on top of a board that already rendered no longer blanks
   * it: the previous read stays on screen and the meta line says what failed. */
  if (err && !hasRows(data)) {
    return <div className="cm-note cm-note-warn">Hottest sectors unavailable: {err}</div>;
  }
  if (!data && loading) return <div className="cm-note">Reading the rotation table…</div>;
  if (data?.reason && !hasRows(data)) {
    return <div className="cm-note cm-note-warn">{data.reason}</div>;
  }

  const rescanBlocked = rescanBlockedReason(data);
  const rescanQuiet = rescanQuietReason(data);

  return (
    <div className="hs">
      <div className="hs-controls">
        {/* The three leg chips used to live here. They set the same backend
            `sort` the column headers now do, and two controls for one piece of
            state is how a board starts lying about its own order. The header
            arrow IS the state. */}
        <div className="hs-sorts">
          <span className="hs-sorted-by">
            ranked on <b>{colLabel(sort, data)}</b>
            {dir === 'desc' ? ' ▼ high → low' : ' ▲ low → high'}
            <span className="hs-dim"> · click any column header</span>
          </span>
        </div>
        <label className="hs-toggle">
          <input type="checkbox" checked={byIndustry}
                 onChange={(e) => setByIndustry(e.target.checked)} />
          Break into industries
        </label>
        {/* ↻ Re-scan (Ajay 2026-09-18: "can you give me rebuild or rescan
            button in hot sectors"). Same class, label and disabled shape as the
            Chart Maps re-scan, so the two read as one control. It re-runs the
            live NAME leg; the sector ranking does NOT move — see the tooltip
            and the InfoButton. */}
        <button type="button" className="cm-rescan" data-testid="hottest-rescan"
                disabled={loading || rescanBlocked !== null}
                title={rescanBlocked
                  ? `Re-scan is off because ${rescanBlocked}. Every column here is already`
                    + ' the last finished session.'
                  : (rescanQuiet ? `${rescanQuiet}. ${RESCAN_COST_SENTENCE} ` : '')
                    + "Re-reads today's live price for every name on this board and re-ranks it. "
                    + 'Sector, industry and roster rows, 5 days, 21 days and Sales YoY stay on'
                    + ' the last close.'}
                onClick={onRescan}>
          {loading ? 'Scanning…' : '↻ Re-scan'}
        </button>
        <InfoButton inline title="🔥 Hottest — how to read this">
          <p>Every sector ranked on <b>{colLabel(sort, data)}</b>
            against <b>{benchSymbol(data)}</b>,
            the equal-weight benchmark — so a name is measured against the average stock, not the
            mega-caps. Open a sector for its industries, then its names.</p>
          <p><b>What &ldquo;Today&rdquo; means here.</b> While the market is open, the day column on a
            NAME row is that name&rsquo;s own move so far in this session, still measured against
            {' '}<b>{benchSymbol(data)}</b> exactly like the other legs. Everything else — 5 days,
            21 days, Sales YoY, and every sector, industry and roster row — comes from the last
            close, because the rotation snapshot is built after the bell. A group row is the median
            over <i>all</i> its members, so it can never be half live and half last-close; it stays
            on the close and says so. When the tape is shut, or no live price comes back, the column
            header itself changes to the session it is showing, and any single row that missed the
            live read is marked <i>last close</i> where you can see it.</p>
          <p><b>The ↻ Re-scan button.</b> It re-reads today&rsquo;s live price for every name on
            this board and re-ranks the table on it. What it can <i>not</i> do is move a sector,
            industry or roster row: those are medians over their full membership taken on the last
            close, and a median mixing live names with last-close names describes no session at all.
            The line above the table always says which basis you are looking at. When the tape is
            shut the button is off and says why, in the market calendar&rsquo;s own words; outside
            {' '}{data?.d1?.session_window || '9:30–16:00 ET'} it still works but warns you the day
            column will not move. {RESCAN_COST_SENTENCE} It is not free, and it is not new — the
            board already re-fetches the chip read about once a minute while it is open.</p>
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
        {/* Which columns are today's and which are the snapshot's, in words
            (2026-09-16). He read a last-close number as the live tape because
            this line only ever said "as of". */}
        <span className={data?.d1?.live ? 'hs-live' : 'hs-stale'}>{asOfLine(data)}</span>
        {err && hasRows(data) ? (
          <span className="hs-stale" data-testid="hottest-rescan-failed">
            {' '}· re-scan failed ({err}) — this is the previous read, not a new one
          </span>
        ) : null}
        {data?.coverage?.pct != null ? (
          <span> · sales on {data.coverage.pct}% of {data.coverage.priced} priced names</span>
        ) : null}
        {data?.stale ? <span className="hs-stale"> · build is stale</span> : null}
      </div>

      {enterableCut ? (
        <HiddenCount hidden={part.hidden} unread={part.unread}
                     hiddenByReason={part.hiddenByReason} enabled kind={kind}
                     reasons={part.reasons} unhidden={part.unhidden}
                     onToggleReason={toggleReason} unhideCount={ignoreReasons.size}
                     note="Counted across every group in this payload — themes, sectors and industries, the collapsed ones included — one count per unique name. This board is a server-cut list: the payload keeps only the top names per group, so this is what the cut removed from the names it carries, never from the full membership."
                     onShowAll={() => setEnterableOnly(false)} />
      ) : null}
      {/* 🪜 No row on this list came back with a band read — say so once, the
          way the 🎯 n/a tabs do, instead of showing no chip anywhere and
          letting it read as a board where the read silently stopped. The
          sentence is SERVED (bounce_room.BAND_STRUCTURE_NO_READ); this board
          is a server-cut list, so it describes the names it carries. */}
      {room.payload?.band_structure_coverage?.note ? (
        <div className="cm-hidden-count" data-testid="band-structure-note">
          🪜 {room.payload.band_structure_coverage.note}
        </div>
      ) : null}

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
                            title={colTitle(c, data)}>
                      {colLabel(c.key, data)}{arrow(on, dir)}
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
                    <LegCells r={t} d1={data} isGroup />
                    <GroupFundCells r={t} />
                  </tr>
                  {isOpen ? t.names.filter((r) => showName(r.symbol)).map((r) => <NameRow key={`${k}|${r.symbol}`} r={r} read={readOf(r.symbol)} study={room.payload?.explosive_study} bandStudy={room.payload?.band_structure_study} d1={data} />) : null}
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
                      {/* 📰 The day's two-sided news tag. Sits beside the name
                          and opens its own row — see DayTagRow. A sector with
                          no tag renders exactly as it always did. */}
                      {s.day_tag ? (
                        <button
                          type="button"
                          className={'hs-daytag__chip' + (s.day_tag.positive ? ' is-pos' : '')}
                          aria-expanded={!!open[`${k}|tag`]}
                          title={dayTagTitle(s.day_tag)}
                          onClick={(ev) => { ev.stopPropagation(); toggle(`${k}|tag`); }}
                        >
                          {dayTagChipLabel(s.day_tag)}
                        </button>
                      ) : null}
                      <span className="hs-n" title={
                        s.sampled_used && s.sampled_of && s.sampled_used < s.sampled_of
                          ? `heat measured on ${s.sampled_used} of ${s.sampled_of} names (the rotation grid's sample); the ${s.n_full} name rows below are the full membership`
                          : `${s.n_full} names`}>
                        {s.n_full}
                        {s.sampled_used && s.sampled_of && s.sampled_used < s.sampled_of
                          ? ` · heat on ${s.sampled_used}` : ''}
                      </span>
                    </td>
                    <LegCells r={s} d1={data} isGroup />
                    <GroupFundCells r={s} />
                  </tr>
                  {s.day_tag && open[`${k}|tag`]
                    ? <DayTagRow key={`${k}|tagrow`} tag={s.day_tag} span={10} />
                    : null}
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
                          <LegCells r={ind} d1={data} isGroup />
                          <GroupFundCells r={ind} />
                        </tr>
                        {iOpen ? ind.names.filter((r) => showName(r.symbol)).map((r) => <NameRow key={`${ik}|${r.symbol}`} r={r} read={readOf(r.symbol)} study={room.payload?.explosive_study} bandStudy={room.payload?.band_structure_study} d1={data} />) : null}
                        {iOpen && ind.names_total > ind.names.length ? (
                          <tr key={`${ik}|more`}><td colSpan={10} className="hs-more">
                            showing {ind.names.length} of {ind.names_total}
                          </td></tr>
                        ) : null}
                      </>
                    );
                  }) : null}
                  {isOpen && !byIndustry ? s.names.filter((r) => showName(r.symbol)).map((r) => <NameRow key={`${k}|${r.symbol}`} r={r} read={readOf(r.symbol)} study={room.payload?.explosive_study} bandStudy={room.payload?.band_structure_study} d1={data} />) : null}
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
