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
 * Every chip is a BUTTON (Ajay 2026-09-09: "I would like to click on the
 * sector category and see the related stocks list in a pop over to see which
 * ones are gaining traction") — it opens SectorMembersModal on that group's
 * FULL membership, which is a different set from the 25-name sample behind the
 * median printed on the chip. The panel says that out loud; the chip's number
 * is untouched by any of it.
 *
 * Measurement of what moved — not a forecast and not advice.
 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { SectorMembersModal } from './SectorMembersModal';
import type { GroupKind } from '../lib/rotationMembers';

export type HotRow = {
  group: string; sector?: string; tier?: string; index?: string;
  n?: number; rel_21d: number | null; rel_window?: number | null;
  rel_63d?: number | null; industry?: string; thin?: boolean;
  pct_positive?: number | null;
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
  error?: string;
};

/** A theme chip's hover. `thin` cohorts (rare_earth n=4, quantum 5, defense 6)
 *  are SHOWN — he asked for them by name — but a median over four names is
 *  noise wearing a number, so the count and the warning ride the tooltip. */
export function themeTitle(r: HotRow): string {
  const n = `${r.group} — ${r.n} names · 63d ${r.rel_63d ?? '—'}% rel`;
  const pos = r.pct_positive == null ? '' : ` · ${r.pct_positive}% of members positive`;
  return r.thin
    ? `${n}${pos} · THIN: too few names for the median to mean much`
    : `${n}${pos}`;
}

export function chipLabel(r: HotRow): string {
  const v = r.rel_21d;
  const num = v == null ? '' : ` ${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
  return `${r.group}${num}`;
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
 *  member panel, Escape closes it. The label and the hover text are byte-for-byte
 *  what the span printed. */
function HotChip({ row, kind, tone, title, open, onOpen, children }: {
  row: HotRow; kind: GroupKind; tone: 'in' | 'out'; title: string;
  open: OpenGroup | null; onOpen: (g: OpenGroup) => void; children: ReactNode;
}) {
  const isOpen = !!open && open.kind === kind && open.row.group === row.group;
  return (
    <button type="button" className={`hs-chip hs-chip-${tone}`} title={title}
            aria-haspopup="dialog" aria-expanded={isOpen}
            onClick={(e) => onOpen({ kind, row, trigger: e.currentTarget })}>
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
  const indIn = data.industries_in || [];
  const indOut = data.industries_out || [];
  const thmIn = data.themes_in || [];
  const thmOut = data.themes_out || [];
  const hasRows = (data.in?.length || 0) + (data.out?.length || 0)
                  + indIn.length + indOut.length + thmIn.length + thmOut.length > 0;
  if (!hasRows) return null;

  const cohortTitle = (r: HotRow) =>
    `${r.group} — ${r.n} names · window ${r.rel_window ?? '—'}% rel`;
  const industryTitle = (r: HotRow) =>
    `${r.group}${r.sector ? ` · inside ${r.sector}` : ''} — ${r.n} names · 63d ${r.rel_63d ?? '—'}% rel`;

  return (
    <div className="hs" role="complementary" aria-label="Hot sectors">
      <span className="hs-head">
        🔥 Hot sectors
        <em className="hs-sub">
          last 21 sessions vs {data.benchmark || 'RSP'} · median member
          {scanStamp(data) ? ` · scan ${scanStamp(data)} ET` : ''}
          {' · click a chip for its member stocks'}
        </em>
      </span>
      <span className="hs-group">
        <em className="hs-tag hs-tag-in">money in</em>
        {(data.in || []).map((r) => (
          <HotChip key={r.group} row={r} kind="cohort" tone="in" title={cohortTitle(r)}
                   open={open} onOpen={setOpen}>
            {chipLabel(r)}
          </HotChip>
        ))}
      </span>
      <span className="hs-group">
        <em className="hs-tag hs-tag-out">money out</em>
        {(data.out || []).map((r) => (
          <HotChip key={r.group} row={r} kind="cohort" tone="out" title={cohortTitle(r)}
                   open={open} onOpen={setOpen}>
            {chipLabel(r)}
          </HotChip>
        ))}
      </span>
      {(indIn.length > 0 || indOut.length > 0) && (
        <>
          <span className="hs-group">
            <em className="hs-tag hs-tag-in">industry in</em>
            {indIn.map((r) => (
              <HotChip key={`ii-${r.group}`} row={r} kind="industry" tone="in"
                       title={industryTitle(r)} open={open} onOpen={setOpen}>
                {chipLabel(r)}
              </HotChip>
            ))}
          </span>
          <span className="hs-group">
            <em className="hs-tag hs-tag-out">industry out</em>
            {indOut.map((r) => (
              <HotChip key={`io-${r.group}`} row={r} kind="industry" tone="out"
                       title={industryTitle(r)} open={open} onOpen={setOpen}>
                {chipLabel(r)}
              </HotChip>
            ))}
          </span>
        </>
      )}
      {(thmIn.length > 0 || thmOut.length > 0) && (
        <>
          <span className="hs-group">
            <em className="hs-tag hs-tag-in">theme in</em>
            {thmIn.map((r) => (
              <HotChip key={`ti-${r.group}`} row={r} kind="theme" tone="in"
                       title={themeTitle(r)} open={open} onOpen={setOpen}>
                {chipLabel(r)}{r.thin ? ' ·thin' : ''}
              </HotChip>
            ))}
          </span>
          <span className="hs-group">
            <em className="hs-tag hs-tag-out">theme out</em>
            {thmOut.map((r) => (
              <HotChip key={`to-${r.group}`} row={r} kind="theme" tone="out"
                       title={themeTitle(r)} open={open} onOpen={setOpen}>
                {chipLabel(r)}{r.thin ? ' ·thin' : ''}
              </HotChip>
            ))}
          </span>
        </>
      )}
      <Link to="/rotation" className="hs-more">full rotation →</Link>
      {open && (
        <SectorMembersModal key={`${open.kind}|${open.row.group}`}
                            kind={open.kind} row={open.row} headline={open.row.rel_21d}
                            returnFocus={open.trigger} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
