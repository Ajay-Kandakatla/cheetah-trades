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
 * 🔎 THE LAST SECTION IS NOT ON HIS SCREEN as this app drew it, deliberately.
 * The character clause (accelerating OR ≥2 consecutive growth quarters) is
 * THIS APP'S (2026-06-16), mis-attributed to Bonde until 2026-09-20; it is the
 * one thing that survived every attack — measuring NEGATIVE. The floor-clearing
 * names it rejects won 56.8% of the next 21 sessions against 51.2% for the ones
 * it accepts. The gate is not edited, because a rule change is Ajay's call
 * (Rule #10); the discarded cohort is shown beside it instead, labelled.
 *
 * 📋 SINCE 2026-09-20 THIS TAB IS A PICK LIST (Ajay: "I need bonde for stock
 * picks rather than deciding to enter … I am looking fro static info"). Every
 * row carries a chip line of his STATIC criteria, each chip one sentence he
 * published with its link. No price-, session- or persistence-derived leg is
 * on that line, by his correction. Nothing on it is measured, nothing on it is
 * a signal, and it gates, sorts and filters nothing.
 *
 * ✨ NEW is his explicit ask — names that ARRIVED on the screen, not names that
 * happen to be there. The backend ledger refuses to badge the first cohort it
 * ever sees, because "we have only just started looking" must never render as
 * "these are fresh finds". It never lights on a 🔎 row: that badge means
 * "arrived on his screen", and those names are precisely the ones that are not.
 *
 * 🎯 DEMAND PROXIMITY (Ajay 2026-09-14, on this tab: "add headers. also sort
 * this by the ones close to demand zone. or give a check box to filter ones
 * closer to demand zones or in the demand zone"). One checkbox does both: it
 * keeps the rows whose live print is INSIDE the board's nearest demand band or
 * within the server's near distance ABOVE its top, and orders them nearest
 * first. The read is the shared bounce-room rule (`demand` on each row) — the
 * same closed-bar BOARD band an alert would name, never a band computed here.
 * The near distance prints from `params.demand_near_pct`; it is not typed in
 * this file. A band price has fallen THROUGH (its floor above the print) is
 * overhead, not demand, and never lights the chip — that is the reclaim class
 * his 2026-09-08 autopsy put at 66% stop-hit.
 *
 * Nothing here gates a scan, fires an alert or buys in any lane.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { InfoButton } from './InfoButton';
import { SignalWatchButton } from './SignalWatchButton';
import { useSignalWatchlist } from '../hooks/useSignalWatchlist';
/* The ↻ button's two reasons are HOTTEST's, imported rather than re-derived:
 * one of them is the market calendar's own sentence and the other is the RTH
 * clock's, and a second copy of either is a second calendar. */
import { rescanBlockedReason, rescanQuietReason } from './HottestSectors';
import {
  BONDE_LIVE_COST_SENTENCE, basisLine, heldOutSentence, periodMark, tierText,
  todayCell, type BondeD1, type BondeHeldOut,
} from '../lib/bondeLive';
import { metricCells } from '../lib/boardMetrics';
import { GrowthChip } from './GrowthChip';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { compareDemandProximity, demandChipText, inOrNearDemand, compareExplosive, type BounceRoomRow } from '../lib/bounceRoom';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { BandStructureChip } from './BandStructureChip';
import { HiddenCount } from './HiddenCount';
import { StudyNote } from './StudyNote';
import { useEnterableFilter } from '../hooks/useEnterableFilter';
import { mergeReasonStats, partitionEnterable, type EnterableRead } from '../lib/enterable';
import { ExplosiveFirstToggle } from './ExplosiveFirstToggle';
import { explosiveStatusOf } from '../hooks/useExplosiveOrder';
/* 📋 the pick line — his STATIC criteria, each one served with its own quote
 * and link. The formatting is pure and lives in one module. */
import { BondePickChips } from './BondePickChips';
import { BondeCriteriaLegend } from './BondeCriteriaLegend';
import { coverageSentence, type BondePick, type BondePickCoverage, type BondePickLegend } from '../lib/bondePicks';

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
  /** The live day leg (`sepa/bonde_live.py`). `today_pct` is null on EVERY row
   *  whenever `d1.basis` is 'close' — the board is never half live. */
  today_pct?: number | null; today_basis?: string | null;
  /** TRI-state, never a bool: false = the year-over-year pair is not four
   *  fiscal quarters apart, null = there are no period keys to check it with,
   *  true = checked and fine. */
  period_ok?: boolean | null; period?: string | null;
  /** 📋 His STATIC criteria for this name, served with their cites. Every leg
   *  is tri-state: `ok: null` is UNKNOWN and never renders as a fail. */
  pick?: BondePick | null;
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
  /** Which session the Today column is on, and why. */
  d1?: BondeD1 | null;
  /** Passers the board refused to tier because their year-over-year pair is
   *  not four fiscal quarters apart — the same rows the 🚀 growth board
   *  refuses. Counted and LISTED: a board that hides must say so. */
  n_tiered?: number; n_period_mismatch?: number;
  period_mismatch_symbols?: BondeHeldOut[];
  /** 📋 The criterion legend, served whole and rendered ONCE. */
  pick_legend?: BondePickLegend | null;
  /** How many rows each pick leg actually knows — a board that shows dashes
   *  without saying why reads as broken. */
  pick_coverage?: BondePickCoverage | null;
};

const SECTIONS: { key: string; label: string; blurb: string }[] = [
  { key: 'pivot', label: '⚡ Episodic Pivots',
    blurb: 'His entry: a stock gapping hard on huge volume, on any catalyst, that also passed his sales gate. This is the board’s original thesis and it is the cell that measured INVERTED — 21-day median −3.22% against −0.11% for date-matched non-Pivot names. Shown because you asked to see his stocks, not because anything measured says to buy them.' },
  { key: 'explosive', label: 'Explosive · sales +100%',
    blurb: 'The 100% boundary of his 2010 "Sales 100% plus but no earnings" Episodic-Pivot CATEGORY — a catalyst category, not a sales gate — used as a tier by this app. Measured median lift over the scored universe: +0.45pp at 21 days, CI −0.31 to +1.36 — it includes zero.' },
  { key: 'strong', label: 'Strong · sales +25%',
    blurb: 'THIS APP’S 25% mid-tier — not a number he published (the first-person quote this board carried until 2026-09-20 was fabricated; it exists in none of his posts). Measured median lift +0.37pp at 21 days, CI −0.16 to +0.78 — it includes zero, and the mean lift that does show up falls to +0.26pp once the top 5% of returns are dropped.' },
  { key: 'steady', label: 'Steady · sales +5%',
    blurb: 'His floor — "Sales/revenue should be up 5% or more." (Stockbee, 2007). Measured flat against the scored universe (−0.01pp at 21 days). Capped here: it is 677 names on the live scan, which is a scroll, not a read.' },
  { key: 'rejected', label: '🔎 Cleared his 5% floor, rejected by THIS APP’S character clause',
    blurb: 'NOT ON HIS SCREEN as this app drew it, and the clause that threw them out is THIS APP’S, not his (mis-attributed until 2026-09-20): accelerating OR ≥2 consecutive growth quarters. It is the one thing in this board that survived every attack, and it measures BACKWARDS: this cohort won 56.8% of the next 21 sessions against 51.2% for the names the gate accepts (+5.64pp, CI +3.91 to +7.52). It does not survive date clustering at 21 days (it does at 63). The gate is not edited because a rule change is Ajay’s call; the cohort it discards is shown here instead.' },
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

/** Column headers, one per grid track of `.bd-row`. The metric heads mirror
 *  `metricCells` — same order, same four cells — so a head sits over its cell. */
const HEADS = {
  sym: { text: 'Ticker', title: 'Ticker · company. ✨ NEW = arrived on his screen recently; 🚀 = also clears the explosive-growth screen; 🎯 = live print in / near the board’s nearest demand band. “+ Signals” puts the name on your watchlist. 📋 chips = his static criteria (legend above) — each one his own sentence, with its link; an em-dash means this app does not know yet, never that the name failed.' },
  today: { text: 'Today', title: 'Each name’s own move so far in THIS session, when the board has a live read — not relative to the benchmark. The whole column shares one basis: when the read is on the last close, every row here is an em-dash rather than yesterday’s number under a “Today” header. The line above the sections says which it is.' },
  sales: { text: 'Sales YoY · base → latest', title: 'Latest quarterly revenue against the same quarter a year ago, with the two dollar figures under it. ⚠ marks a base that is negative or immaterial.' },
  character: { text: 'Character', title: 'His character clause: accelerating (growth rate rising), a streak of consecutive growth quarters, sales-led (top line outpacing the bottom line).' },
  pivot: { text: 'Episodic pivot', title: 'The gap on the pivot day, its volume multiple and how long ago. — = no pivot on this name.' },
  metrics: [
    { text: 'Shares YoY', title: 'Diluted share count, year over year. Down = buybacks; up = dilution.' },
    { text: 'Cash − debt', title: 'Net cash (positive) or net debt (negative).' },
    { text: 'EV / sales', title: 'Enterprise value over trailing revenue. Lower is cheaper for the same sales.' },
    { text: 'FCF yield', title: 'Free cash flow as a share of market cap.' },
  ],
};

export default function BondeBoard() {
  const [d, setD] = useState<BondeBoardData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [newOnly, setNewOnly] = useState(false);
  const [nearDemandOnly, setNearDemandOnly] = useState(false);
  const [explosiveFirst, setExplosiveFirst] = useState(false);
  const [trackedOnly, setTrackedOnly] = useState(false);
  const [heldOutOpen, setHeldOutOpen] = useState(false);
  /* 📡 the ⚡ Signals watchlist — the same store the "+ Signals" button on each
   * row writes, so the box and the buttons can never disagree. "Tracked" is
   * exactly what that button calls ON: on the list, or held in the portfolio
   * (a held name rides Signals by default and leaves with the position). */
  const wl = useSignalWatchlist();
  const tracked = useCallback((sym: string) => wl.has(sym) || wl.isHeld(sym),
                              [wl]);

  // Every row on the tab, once — the shared read is one POST per list.
  const rowSymbols = useMemo(() => {
    const out: string[] = [];
    for (const s of SECTIONS) for (const r of d?.sections?.[s.key] || []) if (r.symbol) out.push(r.symbol);
    return out;
  }, [d]);
  const room = useBounceRoom(rowSymbols);
  const readOf = (sym: string): BounceRoomRow | undefined => room.map.get(String(sym).toUpperCase());
  const nearPct = room.payload?.params?.demand_near_pct;
  // Rows the server actually read bands for (a pending / unavailable row is
  // in the map too, so the map's size would overstate coverage).
  const readCount = useMemo(() => {
    let k = 0;
    for (const r of room.map.values()) if (r.coverage === 'store' || r.coverage === 'ondemand') k += 1;
    return k;
  }, [room.map]);

  /* ↻ Live prices (2026-09-20). The same three rules the 🔥 Hottest loader
   * learned the hard way:
   *  1. LATEST WINS — a late first response must be DISCARDED, or the basis
   *     line reads "live as of 10:14" over rows from the previous answer.
   *  2. A FAILURE KEEPS THE BOARD. A dead provider must not blank his screen.
   *  3. The in-flight guard stops the BUTTON only, never the effect. */
  const seq = useRef(0);
  const inFlight = useRef(false);
  const dataRef = useRef<BondeBoardData | null>(null);

  const load = useCallback(() => {
    const id = ++seq.current;
    inFlight.current = true;
    setLoading(true);
    fetch(`${API}/bonde/board`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: BondeBoardData) => {
        if (id !== seq.current) return;                  // a newer read won
        const rows = Object.values(j?.sections || {}).reduce((k, v) => k + (v?.length || 0), 0);
        if (!rows && dataRef.current) {
          setErr('the live read came back with no rows');
          return;                                        // keep the good board
        }
        dataRef.current = j; setD(j); setErr(null);
      })
      .catch((e) => { if (id === seq.current) setErr(String((e as Error)?.message ?? e)); })
      .finally(() => {
        if (id === seq.current) { inFlight.current = false; setLoading(false); }
      });
  }, []);
  useEffect(() => { void load(); }, [load]);
  const onRescan = () => { if (inFlight.current) return; load(); };

  /* 🎯 The enterable cut (2026-09-15), applied INSIDE each section — his
   * sections are the board, so the filter must never merge them. It COMPOSES
   * with the 🎯 in/near-demand box above and with ✨ new-arrivals: each one
   * removes rows, and the count line below reports only what the ENTERABLE cut
   * took, so "0 hidden" under an empty section correctly points at the other
   * box rather than at this one. */
  const { enterableOnly, kind, setEnterableOnly, ignoreReasons, toggleReason } = useEnterableFilter();
  const enterableOn = enterableOnly && kind !== 'n/a';
  const enterableMap = useMemo(() => {
    const m = new Map<string, EnterableRead | null | undefined>();
    for (const [sym, r] of room.map.entries()) m.set(String(sym).toUpperCase(), r?.enterable ?? null);
    return m;
  }, [room.map]);

  const sections = useMemo(() => {
    if (!d) return [];
    return SECTIONS.map((s) => {
      const all = d.sections?.[s.key] || [];
      let rows = newOnly ? all.filter((r) => r.is_new) : all;
      // 📡 composes with ✨ new arrivals and 🎯 in/near demand — each box
      // removes rows, none of them reorders his sections.
      if (trackedOnly) rows = rows.filter((r) => tracked(r.symbol));
      if (nearDemandOnly) {
        // Filter AND sort: in the band first, then closest above it. The
        // served order (his screen's own) is kept when the box is off.
        rows = rows
          .filter((r) => inOrNearDemand(room.map.get(String(r.symbol).toUpperCase())))
          .slice()
          .sort((a, b) => compareDemandProximity(
            room.map.get(String(a.symbol).toUpperCase()),
            room.map.get(String(b.symbol).toUpperCase())));
      }
      if (explosiveFirst) {
        /* 🧨 opt-in, applied INSIDE each section so his sections survive —
         * the same comparator the backend and every other board use. */
        const status = explosiveStatusOf(room.map);
        rows = rows.slice().sort((a, b) => compareExplosive(
          { symbol: a.symbol, read: room.map.get(String(a.symbol).toUpperCase())?.explosive },
          { symbol: b.symbol, read: room.map.get(String(b.symbol).toUpperCase())?.explosive },
          status));
      }
      const part = partitionEnterable(rows, (r) => r.symbol, enterableMap, enterableOn,
                                      ignoreReasons);
      return { ...s, rows: part.rows, part,
               total: d.counts?.[s.key] ?? all.length, shown: all.length };
    });
    // `ignoreReasons` belongs here: this board calls the partition by hand
    // rather than through the hook, so a missed dep means his chip lights up
    // and the sections do not move.
  }, [d, newOnly, nearDemandOnly, trackedOnly, tracked, explosiveFirst, room.map,
      enterableMap, enterableOn, ignoreReasons]);

  /* One line for the whole tab: the sections are his, the count is the board's. */
  const enterableTotals = useMemo(() => {
    let hidden = 0; let unread = 0; let unhidden = 0;
    const byReason: Record<string, number> = {};
    for (const s of sections) {
      hidden += s.part.hidden;
      unread += s.part.unread;
      unhidden += s.part.unhidden;
      for (const [k2, n2] of Object.entries(s.part.hiddenByReason)) byReason[k2] = (byReason[k2] || 0) + n2;
    }
    // One line for several partitions, so the chips are merged the same way the
    // counts are — summed by CODE, never re-derived from the labels.
    const reasons = mergeReasonStats(sections.map((s) => s.part.reasons));
    return { hidden, unread, unhidden, byReason, reasons };
  }, [sections]);

  // A failed ↻ must never blank a board that is already drawn — the error is
  // reported ABOVE the good rows instead (the Hottest rule, 2026-09-18).
  if (loading && !d) return <div className="bd-note">reading his screen…</div>;
  if (err && !d) return <div className="bd-note bd-err">⛔ {err}</div>;
  if (!d) return null;

  const paused = d.regime?.scanners_paused;
  const m = d.measured;
  const d1 = d.d1 || null;
  /* Only the three fields those two read, so the Bonde block never has to be
     cast to Hottest's payload type. Both sentences stay THEIRS. */
  const d1Pick = d1
    ? { d1: { market_closed: d1.market_closed, in_session: d1.in_session,
              session_window: d1.session_window } }
    : null;
  const rescanBlocked = rescanBlockedReason(d1Pick);
  const rescanQuiet = rescanQuietReason(d1Pick);
  const heldOut = d.period_mismatch_symbols || [];
  const nHeldOut = d.n_period_mismatch ?? heldOut.length;
  const heldOutNote = heldOutSentence(d.note);
  const pickCoverage = coverageSentence(d.pick_coverage);

  return (
    <div className="bd-wrap">
      {/* First thing on the page, above the counts. The tab was built on a
          thesis that measured the wrong way round, and a reader who scrolls
          past the board to find that out has already read it as a buy list. */}
      {m?.headline && (
        /* FOLDED since 2026-09-16 (Ajay: "can you collapse all of these
           please?") — seven paragraphs above a board he is trying to read.
           The ⛔ VERDICT stays above the fold, which is the whole point of
           this banner: the tab was built on a thesis that measured the wrong
           way round, and a reader who has to expand something to find that
           out has already read the board as a buy list. */
        <StudyNote id="bonde-verdict" className="bd-verdict" testId="bd-verdict"
                   glyph="⛔" headingAs="h3" headline={m.headline}
                   body={m.body}>
          {/* keeps .bd-vdim, the class this board's own pins select on */}
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
        </StudyNote>
      )}

      {/* 📋 ONE fold, above the board: every criterion on the pick line, his
          sentence, his link, his date. Rendered once for the whole tab — a
          legend per row would be the wall Rule #5 exists to prevent. */}
      <BondeCriteriaLegend legend={d.pick_legend} />

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
        <div className="bd-toggles">
          <label className="bd-toggle" title="Show only names that ARRIVED on his screen recently">
            <input type="checkbox" checked={newOnly}
                   onChange={(e) => setNewOnly(e.target.checked)} />
            new arrivals only
          </label>
          <label className="bd-toggle"
                 title={`Keep only names whose live print is INSIDE the board’s nearest demand band or within ${nearPct != null ? `${nearPct}%` : 'the near distance'} above its top, nearest first. The band is the same closed-bar board band an alert would name. A band price has fallen through is overhead, not demand, and never counts. Not a buy signal.`}>
            <input type="checkbox" checked={nearDemandOnly}
                   onChange={(e) => setNearDemandOnly(e.target.checked)} />
            🎯 in / near a demand band only{nearPct != null ? ` (≤ ${nearPct}% above)` : ''} · nearest first
          </label>
          <ExplosiveFirstToggle checked={explosiveFirst} onChange={setExplosiveFirst}
                                className="bd-toggle" />
          {/* 📡 Ajay 2026-09-20: "add trackers … the stocks that need to be
              tracked based on his strategy". The tracker list is the ⚡ Signals
              watchlist he already uses everywhere else — one watchlist, not a
              Bonde-only one that would drift from it. */}
          <label className="bd-toggle"
                 title="Keep only the names on your ⚡ Signals watchlist (and the ones you hold, which ride that list by default). Use the “+ Signals” button on a row to start tracking it.">
            <input type="checkbox" checked={trackedOnly}
                   onChange={(e) => setTrackedOnly(e.target.checked)} />
            📡 tracked only
          </label>
          {/* ↻ Live prices — the label says what it does. This board NEVER
              scans on the request path; the click re-reads the Today column
              (one snapshot) and nothing else on the page moves. */}
          <button type="button" className="cm-rescan" data-testid="bonde-rescan"
                  disabled={loading || rescanBlocked !== null}
                  title={rescanBlocked
                    ? `Live prices are off because ${rescanBlocked}. Every column here is`
                      + ' already the last finished session.'
                    : (rescanQuiet ? `${rescanQuiet}. ` : '')
                      + 'Re-reads today’s live price for every name on this board. '
                      + 'His sales tiers, the character clause, the Episodic Pivots and '
                      + 'the CPA metrics do NOT move — they come from the last scan. '
                      + BONDE_LIVE_COST_SENTENCE}
                  onClick={onRescan}>
            {loading ? 'Reading…' : '↻ Live prices'}
          </button>
          <InfoButton inline title="📈 Bonde — what “live” means here">
            <p><b>One column is live, the rest is the scan.</b> “Today” is each name’s
              own move so far in this session. His sales tiers, the year-over-year
              growth, the character chips, the Episodic Pivot and the CPA metrics all
              come from the last scan and do not move when you click ↻.</p>
            <p><b>Never half live.</b> The whole column shares one basis. If the
              benchmark has no live print — before the open, on a holiday, or when the
              provider misses it — every row shows an em-dash instead of yesterday’s
              number under a “Today” header. The line above the sections says which
              session you are looking at, in the market calendar’s own words.</p>
            <p><b>What a click costs.</b> {BONDE_LIVE_COST_SENTENCE} The tiers are not
              re-screened and no scan is triggered.</p>
            <p><b>📡 tracked only</b> filters to your ⚡ Signals watchlist — the same
              list the “+ Signals” button on each row writes to.</p>
            <p>Nothing on this tab is a measured signal. The verdict banner at the top
              is the board’s own measurement, and it came back inverted.</p>
          </InfoButton>
          {nearDemandOnly && (
            <span className="bd-dim bd-sub" title="How many of the tab’s names have a band read yet. Pending rows are being built and will appear on the next poll; a name with no demand band under its print never qualifies.">
              band read on {readCount} of {rowSymbols.length}
              {room.pending > 0 ? ` · ${room.pending} pending` : ''}
              {room.error ? ` · read failed: ${room.error}` : ''}
            </span>
          )}
        </div>
        {/* What this tab IS, in the backend's own words — a pick list, not an
            entry list. Served (`pick_legend.header`), never typed here. */}
        {d.pick_legend?.header && (
          <div className="bd-pick-frame" data-testid="bonde-pick-frame">
            📋 {d.pick_legend.header}
          </div>
        )}
      </div>

      {/* Which session the Today column is on — above the sections, not in a
          tooltip. Served words where the backend has them (the calendar's
          reason), never prose matched here. */}
      <div className="bd-basis" data-testid="bonde-basis" title={d1?.note || undefined}>
        {basisLine(d1)}
        {d1?.live && typeof d1.live_names === 'number' && typeof d1.symbols === 'number' && (
          <span className="bd-dim bd-sub"> · live print on {d1.live_names} of {d1.symbols}</span>
        )}
      </div>

      {/* 📋 What the chip line KNOWS. Six em-dashes with no explanation read as
          a broken board; "short interest 0 of 199 (not warmed)" reads as the
          truth, which is that nobody has looked yet. */}
      {pickCoverage && (
        <div className="bd-pick-coverage bd-dim" data-testid="bonde-pick-coverage"
             title="Coverage of the six chips under each name. An em-dash on a chip means this app has no read for that criterion on that name — never that the name failed it.">
          {pickCoverage}
        </div>
      )}

      {/* A failed ↻ reports itself here and LEAVES the board standing. */}
      {err && <div className="bd-note bd-err" data-testid="bonde-err">⛔ {err}</div>}

      {enterableOn ? (
        <HiddenCount hidden={enterableTotals.hidden} unread={enterableTotals.unread}
                     hiddenByReason={enterableTotals.byReason} enabled kind={kind}
                     reasons={enterableTotals.reasons} unhidden={enterableTotals.unhidden}
                     onToggleReason={toggleReason} unhideCount={ignoreReasons.size}
                     onShowAll={() => setEnterableOnly(false)} />
      ) : null}

      {/* 🪜 No row on this list came back with a band read — say so once,
          the way the 🎯 n/a tabs do, instead of showing no chip anywhere and
          letting it read as a board where the read silently stopped. The
          sentence is SERVED (bounce_room.BAND_STRUCTURE_NO_READ). */}
      {room.payload?.band_structure_coverage?.note ? (
        <div className="cm-hidden-count" data-testid="band-structure-note">
          🪜 {room.payload.band_structure_coverage.note}
        </div>
      ) : null}

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
              {nearDemandOnly && (d.sections?.[s.key] || []).length > 0
                  ? (readCount === 0 && !room.error
                      ? '🎯 band read still loading…'
                      : '🎯 none in or near a demand band right now.')
                : newOnly ? (s.key === 'rejected'
                  ? '✨ NEW never lights here — these names are not on his screen.'
                  : 'no new arrivals in this tier.')
                : s.key === 'pivot' && paused ? 'none — the scanners are paused (above).'
                : 'nothing in this tier right now.'}
            </div>
          ) : (
            <div className="bd-rows">
              <div className="bd-row bd-hdr" aria-hidden="false" role="row">
                <div className="bd-sym" title={HEADS.sym.title}>{HEADS.sym.text}</div>
                <div className="bd-today" title={HEADS.today.title}>{HEADS.today.text}</div>
                <div className="bd-sales" title={HEADS.sales.title}>{HEADS.sales.text}</div>
                <div className="bd-chips" title={HEADS.character.title}>{HEADS.character.text}</div>
                <div className="bd-pivot" title={HEADS.pivot.title}>{HEADS.pivot.text}</div>
                <div className="bd-metrics">
                  {HEADS.metrics.map((h) => <span key={h.text} className="bd-m" title={h.title}>{h.text}</span>)}
                </div>
              </div>
              {s.rows.map((r) => {
                const cells = metricCells(r);
                const baseNote = r.base_state && r.base_state !== 'ok'
                  ? BASE_NOTE[r.base_state] : null;
                const read = readOf(r.symbol);
                const dchip = demandChipText(read);
                const today = todayCell(r, d1);
                const pmark = periodMark(r.period_ok);
                return (
                  <div key={`${s.key}-${r.symbol}`} className="bd-row">
                    <div className="bd-sym">
                      <TickerLink ticker={r.symbol} fromLabel="Bonde" />
                      {/* One click puts the name on his ⚡ Signals watchlist —
                          the "trackers" ask. Non-compact: a bare "+" beside the
                          chips does not read as a control (the same contract
                          the Hottest table carries). */}
                      <SignalWatchButton symbol={r.symbol} />
                      {r.is_new && (
                        /* The DATE on the badge, not only in the title: "✨ NEW"
                           alone cannot be told from a 29-day-old arrival. */
                        <span className="bd-new" data-testid={`bd-new-${r.symbol}`}
                              title={r.first_seen
                                ? `First appeared on his screen ${String(r.first_seen).slice(0, 10)}`
                                : 'Newly arrived on his screen'}>
                          ✨ NEW{r.first_seen ? ` · ${String(r.first_seen).slice(5, 10)}` : ''}
                        </span>
                      )}
                      {/* The year-over-year pair, tri-state. `false` = checked
                          and not four quarters apart; `null` = no period keys
                          to check it with. A tick is never printed for either. */}
                      {pmark && (
                        <span className={pmark.cls} data-testid={`bd-pair-${r.symbol}`}
                              title={pmark.title}>{pmark.text}</span>
                      )}
                      {/* ⚡ rows carry every tier, so the section header does not
                          state it. A row the board WITHHELD the tier from (its
                          pair did not check out) prints an em-dash. */}
                      {s.key === 'pivot' && (
                        <span className="bd-tier bd-dim" data-testid={`bd-tier-${r.symbol}`}
                              title={r.tier
                                ? 'His sales tier for this name.'
                                : 'The growth claim is withheld on this row — its year-over-year pair is not four fiscal quarters apart. The Episodic Pivot is a gap-and-volume event and stands on its own.'}>
                          {tierText(r.tier)}
                        </span>
                      )}
                      {/* Only in / near rows wear the chip — "10% above demand"
                          on every row is noise, not a read (Rule #5). */}
                      {dchip && read?.demand && inOrNearDemand(read) && (
                        <span className={`bd-dchip${read.demand.in_band ? ' bd-dchip-in' : ' bd-dchip-near'}`}
                              title={`Board demand band ${read.demand.lo}–${read.demand.hi} (${read.demand.touches}× tested)${read.print != null ? ` · print ${read.print}` : ''}${read.fresh === false ? ' · stale print' : ''}${room.payload?.store_date ? ` · bands as of ${room.payload.store_date}` : ''}. Same band an alert would name. Not a buy signal.`}>
                          🎯 {dchip}
                        </span>
                      )}
                      {/* 🚀 reaches every Chart Maps tab (Ajay 2026-09-11:
                          "ALL TABS IN CHART MAPS"). Here it is the useful
                          cross-check: a name on Bonde's SALES screen that also
                          clears the 100/100 explosive-growth screen is the two
                          lists agreeing. */}
                      <GrowthChip symbol={r.symbol} className="bd-gchip" />
                      <ExplosiveChip read={read?.explosive} className="bd-gchip"
                                     study={room.payload?.explosive_study} />
                      <EnterableChip read={read?.enterable} className="bd-gchip" />
                      {/* 🪜 Ajay 2026-09-16 "in all chartmaps tabs" — the row's
                          own served ceiling/floor read. `cm-badge` rather than
                          `bd-gchip`: the shared pill is the class that ships
                          with the -band / -band-muted tones. */}
                      <BandStructureChip read={read?.band_structure} className="cm-badge"
                                         study={room.payload?.band_structure_study} />
                      {r.name && <div className="bd-coname">{r.name}</div>}
                      {/* 📋 His static criteria, on EVERY row including 🔎 —
                          the cohort the app's clause rejects is exactly the
                          one a reader most needs the facts for. */}
                      <BondePickChips pick={r.pick} legend={d.pick_legend}
                                      symbol={r.symbol} />
                    </div>

                    <div className={`bd-today ${today.tone}`} title={today.title}
                         data-testid={`bd-today-${r.symbol}`}>
                      {today.text}
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

      {/* 🧾 Held out — the passers the board refused to TIER because their
          newest quarter and its "year-ago" slot are not four fiscal quarters
          apart (Massive omits a missing quarter, usually FY Q4). The 🚀 growth
          board refuses the same rows. A board that hides must say WHICH rows,
          so they are listed rather than silently dropped. Collapsed, because
          it is a data-quality footnote and not part of his screen. */}
      {nHeldOut > 0 && (
        <details className="bd-heldout" data-testid="bonde-heldout"
                 open={heldOutOpen}
                 onToggle={(e) => setHeldOutOpen((e.target as HTMLDetailsElement).open)}>
          <summary>Held out — quarter not four apart ({nHeldOut})</summary>
          {heldOutNote && <p className="bd-note">{heldOutNote}</p>}
          <div className="bd-heldout-rows">
            <div className="bd-heldout-row bd-hdr">
              <span>Ticker</span><span>Tier</span><span>Latest</span><span>Year-ago</span>
            </div>
            {heldOut.map((h) => (
              <div key={h.symbol} className="bd-heldout-row">
                <span><TickerLink ticker={h.symbol} fromLabel="Bonde" /></span>
                <span className="bd-dim">{tierText(h.tier)}</span>
                <span className="bd-dim">{h.latest || '—'}</span>
                <span className="bd-dim">{h.year_ago || '—'}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      <p className="bd-note bd-foot">{d.note}</p>
    </div>
  );
}
