/* HotSectors — where money is flowing THIS WEEK, and what it did TODAY, as one
 * compact strip.
 *
 * Ajay 2026-08-31: "make sure this scan you did today to be on top of the
 * chart maps or some section where it says Hot sectors" + "Feel free to
 * categorize more sectors in a similar faction.. Like Health care small caps"
 * + "I need this component market guage tab too".
 *
 * Data: GET /rotation/hot — sector × cap-tier cohorts (tier = S&P 500/400/600
 * membership), median MEMBER return relative to RSP, ranked by the last 5
 * trading days. Same methodology as the /rotation page; this strip is just its
 * two hot ends. Mounted on Chart Maps AND Market Gauge — one component, so the
 * two pages can never disagree.
 *
 * THE INVERSION HE CAUGHT (2026-09-10)
 * ------------------------------------
 * The strip used to rank AND colour every chip by `rel_21d`. Aerospace &
 * Defense therefore read a deep COLD -11.9% on a day its members were running:
 * AIR +3.0, MOG-A +2.9, ATRO +2.5, TXT +2.4, LMT +2.2, AVAV +4.1, RDW +7.5
 * over five sessions. The month was describing a rotation that had already
 * finished. Ajay: *"Actually this is red but it picked up today so its the
 * inverse.. Basically what ever today is what I wanna see in green but keep
 * the other days too, In general Aero was red but if you see 5 days to today
 * its green. May be just keep 5days and today. That is what it should show..
 * Lately sector rotation is with in a week since its bear market... Ignore the
 * 21 day even if its read now recently market rotated that is the actual truth
 * to us."*
 *
 * So TODAY leads every chip and carries its own colour, the week sits beside
 * it, the ORDER is the backend's (ranked by `rel_5d`, never re-sorted here),
 * and the month is demoted to the hover — kept, because he said "keep the
 * other days too", but it no longer tones a chip or decides what counts as
 * hot. The popover behind each chip still carries 21d and 63d per member.
 *
 * And when nothing qualifies as hot, the strip says so in plain words and
 * prints the market-wide read instead of vanishing — same message: *"when
 * there are none hot that day it helps to know overall market it red."* Every
 * number in that line is computed by the backend and printed verbatim.
 *
 * Every chip is a BUTTON (Ajay 2026-09-09: "I would like to click on the
 * sector category and see the related stocks list in a pop over to see which
 * ones are gaining traction") — it opens SectorMembersModal on that group's
 * FULL membership, which is a different set from the 25-name sample behind the
 * median printed on the chip. The panel says that out loud; the chip's number
 * is untouched by any of it.
 *
 * Nothing on this strip gates anything — it is a read, not a condition.
 * Measurement of what moved — not a forecast and not advice.
 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { pct, tone } from '../lib/rotation';
import { SectorMembersModal } from './SectorMembersModal';
import type { GroupKind } from '../lib/rotationMembers';

export type HotRow = {
  group: string; sector?: string; tier?: string; index?: string;
  n?: number; rel_21d: number | null; rel_window?: number | null;
  rel_63d?: number | null; industry?: string; thin?: boolean;
  pct_positive?: number | null;
  /* The two short legs (2026-09-10). `rel_1d` is TODAY — it leads the chip and
   * it is the only leg that colours it; `rel_5d` is the week the backend ranks
   * by. Both optional, because a build persisted before today carries neither:
   * a missing leg prints '—' in the muted tone, never a green one. */
  rel_1d?: number | null;
  rel_5d?: number | null;
  /** How many of the group's members are green TODAY. Hover only, never a
   *  gate — a breadth read is context for a median, not a condition. */
  pct_positive_1d?: number | null;
};

/** The market-wide read, for the days nothing is hot. Backend-computed over
 *  the same benchmark and the same session as the rows; the strip prints it
 *  and derives nothing from it. */
export type MarketRead = {
  benchmark?: string | null;
  /** The benchmark's own return today and over the ranking window. */
  ret_1d?: number | null;
  ret_5d?: number | null;
  /** Share of the measured universe green today — the breadth half of the
   *  sentence, and the half that says whether one index print is the story. */
  pct_positive_1d?: number | null;
  /** "9 of 11 sectors red" — the most literal rendering of what he asked to
   *  see, and the clearest: a count of SECTORS beats a percentage of names
   *  when the question is "is the whole market down". */
  sectors_red?: number | null;
  sectors_measured?: number | null;
};

export type HotPayload = {
  /* 2026-09-06 (Ajay: "make ... Hot sectors part of the scans"): "scan" = the
   * last scan's persisted build with its ET stamp; "live" = built on request. */
  source?: 'scan' | 'live' | null;
  built_at_iso?: string | null;
  as_of?: string; start?: string; benchmark?: string;
  in: HotRow[]; out: HotRow[]; ranked_by?: string;
  /* One grain finer (Ajay 2026-09-09: "increase our sectors ... money got
   * moved in to technology too from Semis"). Industry cohorts off the scan's
   * own `industry` label — Semiconductors and Software-Infrastructure are
   * separate rows here and both sit inside the one Technology row above, which
   * on 2026-09-09 hid a 33-point 63-day spread between them. */
  industries_in?: HotRow[]; industries_out?: HotRow[];
  /* His own build-out rosters (Ajay 2026-09-09: "robotics, energy and optic
   * fiber, constructipn like for data centers add these"). Three of those four
   * were ALREADY tracked — they had just never been rendered anywhere, which
   * is why he asked for things the app already had. */
  themes_in?: HotRow[]; themes_out?: HotRow[];
  stance?: { defensive?: number | null; cyclical?: number | null;
             commodity?: number | null };
  /** The tape itself (2026-09-10). Present so an empty hot list can still say
   *  something true; absent on a build made before today. */
  market?: MarketRead | null;
  error?: string;
};

/** A number, or null for anything that is not one. A missing leg must read
 *  UNKNOWN — it must never fall through to a zero that prints as flat. */
function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** The month, demoted to the hover. Ajay 2026-09-10: "keep the other days too"
 *  AND "Ignore the 21 day even if its read now recently market rotated". Both
 *  are satisfied by keeping the number and taking away its vote. */
export function monthLeg(r: HotRow): string {
  return ` · 21d ${r.rel_21d ?? '—'}% rel`;
}

/** Today's breadth inside the group, when the build measured it. */
export function breadthLeg(r: HotRow): string {
  const p = num(r.pct_positive_1d);
  return p == null ? '' : ` · ${Math.round(p)}% of members up today`;
}

/** A theme chip's hover. `thin` cohorts (rare_earth n=4, quantum 5, defense 6)
 *  are SHOWN — he asked for them by name — but a median over four names is
 *  noise wearing a number, so the count and the warning ride the tooltip. */
export function themeTitle(r: HotRow): string {
  const n = `${r.group} — ${r.n} names · 63d ${r.rel_63d ?? '—'}% rel${monthLeg(r)}`;
  const pos = r.pct_positive == null ? '' : ` · ${r.pct_positive}% of members positive`;
  return r.thin
    ? `${n}${pos}${breadthLeg(r)} · THIN: too few names for the median to mean much`
    : `${n}${pos}${breadthLeg(r)}`;
}

/** The chip face, as separately-toned pieces. TODAY leads and is the ONLY leg
 *  that decides the colour — "what ever today is what I wanna see in green".
 *  The week sits beside it because the week is what the order is made of. An
 *  unmeasurable leg prints '—' and tones flat: unknown is never hot. */
export function chipFace(r: HotRow): {
  name: string; day: string; week: string; tone: 'up' | 'down' | 'flat';
} {
  return {
    name: r.group,
    day: pct(num(r.rel_1d)),
    week: pct(num(r.rel_5d)),
    tone: tone(num(r.rel_1d)),
  };
}

/** The ranking window in words, read off the backend's own `ranked_by` rather
 *  than hardcoded. Ajay's whole complaint was a strip that claimed one window
 *  while ranking on another (2026-09-10), so the label cannot be a constant:
 *  if a stale build still ranks by the month, the header says the month. */
/** The same window as a chip-sized tag ("5d"). Derived, never a constant, for
 *  the reason above: a stale build that still ranks by the month must not
 *  print "5d" over 21-day numbers. */
export function shortWindow(rankedBy?: string | null): string {
  const m = /^rel_(\d+)d$/.exec(String(rankedBy || ''));
  return m ? `${m[1]}d` : '';
}

export function windowLabel(rankedBy?: string | null): string {
  if (rankedBy === 'rel_1d') return 'today';
  if (rankedBy === 'rel_5d') return 'the last 5 sessions';
  if (rankedBy === 'rel_21d') return 'the last 21 sessions';
  if (rankedBy === 'rel_63d') return 'the last 63 sessions';
  if (rankedBy === 'rel_window') return 'the full window';
  return 'the ranking window';
}

/** What the tape did, for the days no group qualifies. Ajay 2026-09-10: "when
 *  there are none hot that day it helps to know overall market it red."
 *
 *  Returns null when the build measured neither leg — an empty strip is better
 *  than an invented sentence about a market nobody read. */
/** Is the DAY broadly red? Majority of sectors down, or the benchmark down —
 *  a plain read on the tape, computed from what the backend already sent. */
export function marketIsRed(d: Pick<HotPayload, 'market'>): boolean {
  const m = d.market || {};
  const red = num(m.sectors_red);
  const measured = num(m.sectors_measured);
  if (red != null && measured) return red * 2 > measured;
  const day = num(m.ret_1d);
  return day != null && day < 0;
}

export function marketLine(d: Pick<HotPayload, 'market' | 'benchmark'>,
                           noneHot = true): string | null {
  const m = d.market || {};
  const sym = m.benchmark || d.benchmark || 'RSP';
  const day = num(m.ret_1d);
  const breadth = num(m.pct_positive_1d);
  if (day == null && breadth == null) return null;
  const red = num(m.sectors_red);
  const measured = num(m.sectors_measured);
  const parts: string[] = [];
  if (day != null) parts.push(`${sym} ${pct(day)}`);
  if (red != null && measured) parts.push(`${red} of ${measured} sectors red`);
  if (breadth != null) parts.push(`${Math.round(breadth)}% of names up`);
  const tape = day == null ? 'the tape reads'
    : day < 0 ? 'the whole tape is red'
      : day > 0 ? 'the whole tape is green'
        : 'the tape is flat';
  const lead = noneHot
    ? 'nothing is hot today'
    : 'read the chips against the tape';
  return `${lead}; ${tape}: ${parts.join(', ')}`;
}

/** 'HH:MM' of the scan that built the strip, or '' when it was built on
 *  request. The stamp is already ET with its offset — a substring, never a
 *  timezone conversion. */
export function scanStamp(d: Pick<HotPayload, 'source' | 'built_at_iso'>): string {
  const iso = d.source === 'scan' && d.built_at_iso ? String(d.built_at_iso) : '';
  return iso.length >= 16 && iso[10] === 'T' ? iso.slice(11, 16) : '';
}

/** Which group a chip is standing for. `cohort` is rotation.tracker's own word
 *  for the sector × cap-tier rows. */
type OpenGroup = { kind: GroupKind; row: HotRow; trigger: HTMLElement | null };

/** One chip. A real <button> rather than a styled span so it is reachable and
 *  operable from the keyboard for free — Tab lands on it, Enter/Space opens the
 *  member panel, Escape closes it.
 *
 *  The face is three spans rather than one string so today's number can be
 *  green on a chip sitting in the "money out" bucket — which is the entire
 *  point of the 2026-09-10 change. */
function HotChip({ row, kind, title, rankedBy, open, onOpen, children }: {
  row: HotRow; kind: GroupKind; title: string; rankedBy?: string | null;
  open: OpenGroup | null; onOpen: (g: OpenGroup) => void; children?: ReactNode;
}) {
  const isOpen = !!open && open.kind === kind && open.row.group === row.group;
  const face = chipFace(row);
  return (
    <button type="button" className={`hs-chip hs-chip-${face.tone}`} title={title}
            aria-haspopup="dialog" aria-expanded={isOpen}
            onClick={(e) => onOpen({ kind, row, trigger: e.currentTarget })}>
      <span className="hs-name">{face.name}</span>{' '}
      <span className="hs-today">{face.day}</span>{' · '}
      <span className="hs-week">{shortWindow(rankedBy)} {face.week}</span>
      {children}
    </button>
  );
}

export default function HotSectors() {
  const [data, setData] = useState<HotPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<OpenGroup | null>(null);

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
  const cohIn = data.in || [];
  const cohOut = data.out || [];
  const indIn = data.industries_in || [];
  const indOut = data.industries_out || [];
  const thmIn = data.themes_in || [];
  const thmOut = data.themes_out || [];
  const hasRows = cohIn.length + cohOut.length
                  + indIn.length + indOut.length + thmIn.length + thmOut.length > 0;
  // "when there are none hot that day it helps to know overall market it red"
  // — none hot means nothing on the money-IN side at any grain, which is the
  // shape a red tape actually takes: plenty of outflow rows, no inflow ones.
  const noneHot = cohIn.length + indIn.length + thmIn.length === 0;
  // Show the tape read whenever the DAY is broadly red — not only when the
  // inflow list happens to be empty. His ask was about the day ("when there
  // are none hot that day it helps to know overall market it red") while the
  // chips are now ranked on the WEEK, so gating the line on an empty inflow
  // list would hide it on exactly the day he described: 2026-09-10 had 10 of
  // 11 sectors red and still had 5 cohorts green over the week.
  const tape = noneHot || marketIsRed(data) ? marketLine(data, noneHot) : null;
  // Nothing measured and nothing to say: vanish, exactly as before.
  if (!hasRows && !tape) return null;

  const cohortTitle = (r: HotRow) =>
    `${r.group} — ${r.n} names · window ${r.rel_window ?? '—'}% rel${monthLeg(r)}${breadthLeg(r)}`;
  const industryTitle = (r: HotRow) =>
    `${r.group}${r.sector ? ` · inside ${r.sector}` : ''} — ${r.n} names`
    + ` · 63d ${r.rel_63d ?? '—'}% rel${monthLeg(r)}${breadthLeg(r)}`;

  return (
    <div className="hs" role="complementary" aria-label="Hot sectors">
      <span className="hs-head">
        🔥 Hot sectors
        <em className="hs-sub">
          today first · ranked by {windowLabel(data.ranked_by)} vs {data.benchmark || 'RSP'}
          {' · median member'}
          {scanStamp(data) ? ` · scan ${scanStamp(data)} ET` : ''}
          {' · click a chip for its member stocks'}
        </em>
      </span>
      {noneHot && (
        // Plain words first, so an empty inflow side can never be mistaken for
        // a broken scan or a missing payload.
        <p className="hs-market">{tape || 'nothing is hot today'}</p>
      )}
      {cohIn.length > 0 && (
        <span className="hs-group">
          <em className="hs-tag hs-tag-in">money in</em>
          {cohIn.map((r) => (
            <HotChip key={r.group} row={r} kind="cohort" rankedBy={data.ranked_by} title={cohortTitle(r)}
                     open={open} onOpen={setOpen} />
          ))}
        </span>
      )}
      {cohOut.length > 0 && (
        <span className="hs-group">
          <em className="hs-tag hs-tag-out">money out</em>
          {cohOut.map((r) => (
            <HotChip key={r.group} row={r} kind="cohort" rankedBy={data.ranked_by} title={cohortTitle(r)}
                     open={open} onOpen={setOpen} />
          ))}
        </span>
      )}
      {indIn.length > 0 && (
        <span className="hs-group">
          <em className="hs-tag hs-tag-in">industry in</em>
          {indIn.map((r) => (
            <HotChip key={`ii-${r.group}`} row={r} kind="industry"
                     title={industryTitle(r)} rankedBy={data.ranked_by} open={open} onOpen={setOpen} />
          ))}
        </span>
      )}
      {indOut.length > 0 && (
        <span className="hs-group">
          <em className="hs-tag hs-tag-out">industry out</em>
          {indOut.map((r) => (
            <HotChip key={`io-${r.group}`} row={r} kind="industry"
                     title={industryTitle(r)} rankedBy={data.ranked_by} open={open} onOpen={setOpen} />
          ))}
        </span>
      )}
      {thmIn.length > 0 && (
        <span className="hs-group">
          <em className="hs-tag hs-tag-in">theme in</em>
          {thmIn.map((r) => (
            <HotChip key={`ti-${r.group}`} row={r} kind="theme"
                     title={themeTitle(r)} rankedBy={data.ranked_by} open={open} onOpen={setOpen}>
              {r.thin ? ' ·thin' : ''}
            </HotChip>
          ))}
        </span>
      )}
      {thmOut.length > 0 && (
        <span className="hs-group">
          <em className="hs-tag hs-tag-out">theme out</em>
          {thmOut.map((r) => (
            <HotChip key={`to-${r.group}`} row={r} kind="theme"
                     title={themeTitle(r)} rankedBy={data.ranked_by} open={open} onOpen={setOpen}>
              {r.thin ? ' ·thin' : ''}
            </HotChip>
          ))}
        </span>
      )}
      <Link to="/rotation" className="hs-more">full rotation →</Link>
      {open && (
        // `headline` is the number the panel quotes back as "the chip's": the
        // week, because the week is what the chip is ranked and sampled on.
        // Today's leg has its own full-membership line inside the panel.
        <SectorMembersModal key={`${open.kind}|${open.row.group}`}
                            kind={open.kind} row={open.row} headline={open.row.rel_5d}
                            returnFocus={open.trigger} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
