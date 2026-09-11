/* SectorMembersModal — the member stocks behind one Hot sectors chip.
 *
 * Ajay 2026-09-10: *"I would like to click on the sector category and see the
 * related stocks list in a pop over to see which ones are gaining traction"*.
 *
 * The strip prints one median per group. This is the drill: every member of
 * that group, its own 5 / 21 / 63-session return vs RSP, how far it sits from
 * its own group's median, whether it is standing at a demand band, and the
 * backend's traction flag — sorted by the backend's traction score, with the
 * definition of that score printed next to the sort label so the ranking is
 * never a vibe.
 *
 * THE ONE THING THIS PANEL MUST SAY OUT LOUD
 * ------------------------------------------
 * The chip's median is measured over a deterministic 25-name SAMPLE
 * (rotation.tracker COHORT_SAMPLE / INDUSTRY_SAMPLE); this table is the FULL
 * liquidity-filtered membership. Technology is 25 names on the chip and 348
 * here. A member table sitting under a median it did not produce reads as that
 * median's arithmetic, so `sampleVsFullLine` is rendered in the body — the
 * second line of the panel, not a tooltip and not a footnote. Nothing here
 * changes, restates or "reconciles" the number on the chip.
 *
 * Coverage is printed rather than swallowed (tracker decision 4: dead tickers
 * are dropped, not counted as flat) — a group nothing could be priced in says
 * so instead of looking like an empty sector.
 *
 * Conventions: portal + overlay-click + Escape, same as SignalDrillModal /
 * GiantsRotationModal / WhalesFlowModal. Body scroll is deliberately NOT
 * locked — locking it strands mobile readers inside the panel.
 *
 * Measurement of what moved — not a forecast and not advice.
 */
import { useEffect, useRef } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { TickerLink } from './TickerLink';
import {
  coverageLine, fmtPts, fmtRel, sampleVsFullLine, sortLine,
  type GroupKind, type GroupRef, type MemberRow, type MembersPayload,
} from '../lib/rotationMembers';
import { useRotationMembers } from '../hooks/useRotationMembers';

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Green when the name is ahead of its own group, red behind, muted at par. */
function toneOf(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v) || v === 0) return 'hsm-flat';
  return v > 0 ? 'hsm-up' : 'hsm-down';
}

/** Raw (un-rebased) legs on the row's hover. Kept OUT of the columns: the
 *  columns are all vs-benchmark, and a column holding two measures is not a
 *  column. */
function rowTitle(m: MemberRow, benchmark: string): string {
  const raw = [
    m.r5 != null ? `5d ${fmtRel(m.r5)}` : '',
    m.r21 != null ? `21d ${fmtRel(m.r21)}` : '',
    m.r63 != null ? `63d ${fmtRel(m.r63)}` : '',
  ].filter(Boolean).join(' · ');
  const head = `${m.symbol}${m.name ? ` — ${m.name}` : ''}`;
  return [
    head,
    raw ? `raw (not vs ${benchmark}): ${raw}` : '',
    m.traction_score != null ? `traction score ${m.traction_score.toFixed(2)}` : '',
    m.at_demand === true ? demandLabel(m) : '',
  ].filter(Boolean).join(' · ');
}

/* The ONE demand read behind this column. The tracker marks a member with
 * bounce_room.in_demand_read ONLY — "the print is inside an eligible demand
 * band". It does NOT run bounce_read, so there is no reversal read here and
 * this column must not imply one: an earlier draft rendered a 🪃 off a nested
 * `demand.bounce` object the endpoint has never sent, so the marker was dead
 * in production and would have claimed a read we do not compute. ◧ is the
 * whole vocabulary; null coverage stays blank, which is "never looked", not
 * "not at demand". */
function demandLabel(m: MemberRow): string {
  const depth = m.zone_depth_pct != null ? `, ${m.zone_depth_pct.toFixed(1)}% into it` : '';
  return `print is inside an eligible ${m.zone_role === 'broken_supply'
    ? 'broken-supply shelf now acting as support' : 'demand band'}${depth}`;
}

function MemberLine({ m, benchmark }: { m: MemberRow; benchmark: string }) {
  return (
    <tr className={m.traction ? 'hsm-row hsm-row-traction' : 'hsm-row'}
        title={rowTitle(m, benchmark)}>
      <th scope="row" className="hsm-sym">
        {m.traction && (
          <span className="hsm-flag" aria-label="gaining traction" title="gaining traction">▲</span>
        )}
        <TickerLink ticker={m.symbol} showWatchlist={false} fromLabel="Hot sectors" />
        {/* Ajay 2026-09-10: "Cna you add company name too next to these
          * tickers". Under the symbol, not beside it: names run to "Marathon
          * Petroleum Corporation" and this panel is 720px, so a column would
          * squeeze the five numeric ones the table exists for. Absent for the
          * ~1% with no cached name — the row is unchanged, never blank. */}
        {m.name && <span className="hsm-coname" title={m.name}>{m.name}</span>}
      </th>
      <td className={`hsm-num ${toneOf(m.rel_1d)}`}>{fmtRel(m.rel_1d)}</td>
      <td className={`hsm-num ${toneOf(m.rel_5d)}`}>{fmtRel(m.rel_5d)}</td>
      <td className={`hsm-num ${toneOf(m.rel_21d)}`}>{fmtRel(m.rel_21d)}</td>
      <td className={`hsm-num ${toneOf(m.rel_63d)}`}>{fmtRel(m.rel_63d)}</td>
      <td className={`hsm-num ${toneOf(m.vs_group_21d)}`}>{fmtPts(m.vs_group_21d)}</td>
      <td className="hsm-mark">
        {m.at_demand === true && (
          <span className="hsm-demand" title={demandLabel(m)}>◧</span>
        )}
      </td>
    </tr>
  );
}

/** The column note. Deliberately NOT a <caption>: a caption's text
 *  participates in the table's min-content width, which blew this table out to
 *  1400px inside a 680px panel and pushed the vs-group and demand columns off
 *  the right edge. */
/* SAME DAY at the GROUP level (Ajay 2026-09-10: "Can you also check for same
 * day sector too please?"). The median move of this group's full membership
 * today, and how many of them are green — the breadth is the half that says
 * whether one name is carrying the number. Raw, not rebased: "what is this
 * sector doing today" is a plain question and rebasing it against RSP would
 * answer a different one. */
function todayLine(p: MembersPayload): string {
  const m = p.median_1d_full;
  if (m == null || !Number.isFinite(m)) return '';
  const breadth = p.up_today != null && p.n_priced
    ? `, ${p.up_today} of ${p.n_priced} up` : '';
  return ` · today ${m >= 0 ? '+' : ''}${m.toFixed(1)}%${breadth}`;
}

function ColumnNote({ p }: { p: MembersPayload }) {
  return (
    <p className="hsm-caption">
      Trailing returns restated vs {p.benchmark || 'RSP'}. “vs group” is this
      name’s <b>21-day</b> rel minus its group’s published 21-day median, in
      points. Since 2026-09-10 the chip you clicked leads with <b>today</b> and
      is ranked on the <b>week</b>, so this column is a different window from
      the chip and the two are not meant to line up.
      {p.sampled && p.member_median_21d != null
        ? ` This table’s own full-membership 21-day median is ${fmtRel(p.member_median_21d)} — a different population again, and deliberately not the yardstick here.`
        : ''}
    </p>
  );
}

function Table({ p }: { p: MembersPayload }) {
  const bench = p.benchmark || 'RSP';
  return (
    <table className="hsm-table">
      <thead>
        <tr>
          <th scope="col">Ticker</th>
          <th scope="col" className="hsm-num" title="today: this name's last close against the one before it, restated vs the benchmark">today</th>
          <th scope="col" className="hsm-num">5d</th>
          <th scope="col" className="hsm-num">21d</th>
          <th scope="col" className="hsm-num">63d</th>
          <th scope="col" className="hsm-num">vs group</th>
          <th scope="col" className="hsm-mark" title="◧ the print is inside an eligible demand band (blank = the zone store has no doc for this name, i.e. never looked)">
            demand
          </th>
        </tr>
      </thead>
      <tbody>
        {p.members.map((m) => <MemberLine key={m.symbol} m={m} benchmark={bench} />)}
      </tbody>
    </table>
  );
}

export type SectorMembersModalProps = {
  kind: GroupKind;
  row: GroupRef;
  /** The number printed on the chip that was clicked, so the sample-vs-full
   *  line can name the exact figure it is disclaiming. */
  headline?: number | null;
  /** The element that opened this panel — focus goes back to it on close.
   *  Passed explicitly rather than read off `document.activeElement`, because
   *  Safari does not focus a <button> on click and would strand focus on
   *  <body>. `document.activeElement` stays the fallback. */
  returnFocus?: HTMLElement | null;
  onClose: () => void;
};

export function SectorMembersModal({
  kind, row, headline, returnFocus, onClose,
}: SectorMembersModalProps) {
  const { data, loading, error } = useRotationMembers(kind, row);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Escape closes — same as every other drill panel in the app.
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [onClose]);

  // Focus goes INTO the panel on open and back to the chip that opened it on
  // close — a keyboard user who tabs to a chip, opens it and closes it lands
  // back where they were, not at the top of the page.
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => {
      const back = returnFocus || prev;
      try { back?.focus?.(); } catch { /* node is gone — leave focus alone */ }
    };
    // Mount/unmount only: `returnFocus` is fixed for one open panel, and the
    // parent keys the modal per group so switching chips remounts it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tab cycles inside the panel while it is open.
  const onKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'Tab') return;
    const nodes = Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) || []);
    if (nodes.length === 0) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || !panelRef.current?.contains(active))) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const tractionCount = data ? data.members.filter((m) => m.traction).length : 0;
  const heading = `${row.group} — members`;

  return createPortal(
    <div className="hsm-overlay" onClick={onClose}>
      <div className="hsm-panel" role="dialog" aria-modal="true" aria-label={heading}
           ref={panelRef} onClick={(e) => e.stopPropagation()} onKeyDown={onKeyDown}>
        <header className="hsm-head">
          <div>
            <div className="eyebrow">🔥 Hot sectors · members</div>
            <h2 className="display hsm-title">
              {row.group}
              {row.sector && row.sector !== row.group && (
                <span className="hsm-sub"> inside {row.sector}</span>
              )}
            </h2>
            <div className="hsm-sub">
              {data
                ? `${data.n_priced} of ${data.n_members} members covered${
                    tractionCount ? ` · ${tractionCount} gaining traction` : ''}${
                    todayLine(data)}`
                : loading ? 'reading the group’s membership…' : 'membership unavailable'}
            </div>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close"
                  className="hsm-close mono">✕</button>
        </header>

        {/* Not a tooltip and not a footnote — the panel's second line. */}
        <p className="hsm-warn">{sampleVsFullLine(data, headline)}</p>

        {loading && <p className="hsm-note mono">…loading members</p>}

        {error && (
          <p className="hsm-err mono">
            Member read failed ({error}) — the group’s median on the strip is
            unaffected. Try again shortly.
          </p>
        )}

        {data && (
          <>
            <p className="hsm-sort">{sortLine(data)}</p>
            {data.members.length === 0 ? (
              <p className="hsm-note">
                {data.n_members > 0
                  ? `None of this group’s ${data.n_members} members could be priced — every series was
                     missing or stale, so nothing is ranked here. That is a data gap, not an empty sector.`
                  : 'No member list is stored for this group yet.'}
              </p>
            ) : (
              <>
                <ColumnNote p={data} />
                <div className="hsm-scroll"><Table p={data} /></div>
              </>
            )}
            <p className="hsm-foot mono">
              {coverageLine(data)}
              {data.dropped_symbols && data.dropped_symbols.length > 0 && (
                <> · dropped: {data.dropped_symbols.join(', ')}</>
              )}
            </p>
            <p className="hsm-foot">
              Liquidity-filtered membership from the latest scan. Measurement of what
              moved — not a forecast and not advice.
            </p>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

export default SectorMembersModal;
