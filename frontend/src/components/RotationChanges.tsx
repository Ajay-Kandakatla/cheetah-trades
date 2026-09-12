/* 🔄 What changed — the line that replaces a wall of chips.
 *
 * Ajay 2026-09-12, on the six-row ~35-chip Hot-sectors strip: *"this whole
 * thing is super messay ... I am trying to see what changed if there is no
 * change continously same sectors continue to show the top for example energy
 * has been continous."* and, on the screenshot, *"this is what I mean when I
 * said messy"*.
 *
 * THE WHOLE IDEA: **Energy at #1 for eight days is ONE fact, not eight.** The
 * strip reprinted the same chips every session and left him to diff it by eye.
 * This leads with the DELTA, and when there is no delta it SAYS SO in a line —
 * rather than rendering nothing (an empty strip reads as a broken scan) or
 * rendering everything again (which is what he called messy).
 *
 * It reads `GET /rotation/changes` with the default `grain=all`, deliberately:
 * the strip below it renders cohorts, industries AND themes, so a one-grain
 * answer could print a confident "no change" on a session where themes
 * reshuffled underneath. `quiet` from that endpoint is the AND across grains.
 *
 * The backend owns every number (backend/rotation/history.py). Nothing here
 * recomputes a rank — two definitions on two surfaces is exactly how the strip
 * and the board would start disagreeing.
 *
 * Nothing here gates anything. Sector heat measured NO forward edge
 * (2026-09-09: -0.57pp, interval spanning zero; cold beat hot over 5 days by
 * 2.55pp). A shift being visible is not a reason to trade it.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type RcMove = {
  group: string;
  rank?: number | null;
  prev_rank?: number | null;
  delta?: number | null;
};
export type RcGrain = {
  baseline?: string | null;
  entered?: RcMove[]; left?: RcMove[]; moved?: RcMove[];
  streaks?: Record<string, number>; top?: string[];
  quiet?: boolean; reason?: string;
};
export type RcPayload = {
  grain?: string; as_of?: string | null; baseline?: string | null;
  grains?: Record<string, RcGrain>;
  quiet?: boolean; reason?: string; note?: string;
};

/** Which grain's leader is THE headline. His own example is a SECTOR ("energy
 *  has been continous"), and sectors are the coarsest, steadiest grain — a
 *  theme roster of four names changing places is not the market's answer to
 *  "has anything changed". Falls through when a build carries no sector rows. */
export const HEADLINE_GRAIN_ORDER = ['sectors', 'cohorts', 'industries', 'themes'];

/** How many movers earn a chip before the rest collapse into a count. Four is
 *  what fits on one line at his widths; the fifth would re-start the wall. */
export const MAX_MOVERS = 4;

/** Short grain tag for a mover chip, so "robotics 7→3" says WHERE it moved. */
export function grainTag(g: string): string {
  return g === 'cohorts' ? 'cohort'
    : g === 'industries' ? 'industry'
      : g === 'sectors' ? 'sector' : 'theme';
}

/** "Energy #1 · 8d" — the sentence his ask is actually about. A streak of one
 *  session says nothing worth the pixels, so it prints the rank alone. */
export function streakText(group: string, rank: number, days?: number | null): string {
  const d = typeof days === 'number' && days > 1 ? ` · ${days}d` : '';
  return `${group} #${rank}${d}`;
}

/** The leader and how long it has held the top, off the first grain that has
 *  one. Null when the payload carries no ranked rows at all. */
export function headline(p: RcPayload): { group: string; days: number | null } | null {
  const grains = p.grains || {};
  for (const g of HEADLINE_GRAIN_ORDER) {
    const top = (grains[g]?.top || [])[0];
    if (top) return { group: top, days: grains[g]?.streaks?.[top] ?? null };
  }
  return null;
}

export type RcLine = { key: string; text: string; kind: 'in' | 'out' | 'up' | 'dn' };

/** Every grain's movement, flattened into at most MAX_MOVERS chips.
 *
 *  Crossings (entered / left the top band) outrank re-orderings INSIDE it: a
 *  group arriving is the event, a group sliding from 4th to 2nd is a detail.
 *  Within each class the biggest move leads. A group that both entered and
 *  moved prints once — it is one event, and printing it twice is how the old
 *  strip got wide. */
export function moverLines(p: RcPayload, cap = MAX_MOVERS): { lines: RcLine[]; extra: number } {
  const grains = p.grains || {};
  const seen = new Set<string>();
  const push = (out: RcLine[], g: string, m: RcMove, kind: RcLine['kind'], text: string) => {
    const k = `${g}|${m.group}`;
    if (seen.has(k)) return;
    seen.add(k);
    out.push({ key: k, text, kind });
  };
  const crossings: RcLine[] = [];
  const shifts: RcLine[] = [];
  for (const g of Object.keys(grains)) {
    const c = grains[g] || {};
    for (const m of c.entered || [])
      push(crossings, g, m, 'in',
           `＋ ${m.group} ${m.prev_rank ? `${m.prev_rank}→${m.rank}` : `#${m.rank}`}`);
    for (const m of c.left || [])
      push(crossings, g, m, 'out',
           `－ ${m.group} ${m.rank ? `${m.prev_rank}→${m.rank}` : 'dropped out'}`);
  }
  for (const g of Object.keys(grains)) {
    const c = grains[g] || {};
    const ranked = [...(c.moved || [])].sort(
      (a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0));
    for (const m of ranked)
      push(shifts, g, m, (m.delta ?? 0) > 0 ? 'up' : 'dn',
           `${(m.delta ?? 0) > 0 ? '▲' : '▼'} ${m.group} ${m.prev_rank ?? '—'}→${m.rank ?? '—'}`);
  }
  const all = [...crossings, ...shifts];
  // Never silently truncate: what does not fit is COUNTED, so the line can
  // never read as "that was everything" when it was not.
  return { lines: all.slice(0, cap), extra: Math.max(0, all.length - cap) };
}

export default function RotationChanges() {
  const [d, setD] = useState<RcPayload | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    fetch(`${API}/rotation/changes`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j: RcPayload) => { if (live) { setD(j); setFailed(false); } })
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, []);

  // Silent on failure: this rides above a strip that works without it, and a
  // red error bar over a working strip is worse than no line.
  if (failed || !d) return null;
  // A payload with no grains is not a change answer — it is the endpoint
  // saying it had nothing to snapshot (no as_of on the build). Printing its
  // machine reason at a reader is worse than printing nothing.
  if (!d.grains || Object.keys(d.grains).length === 0) return null;

  const head = headline(d);
  const { lines, extra } = moverLines(d);
  const lead = head ? streakText(head.group, 1, head.days) : null;
  // Not quiet, yet nothing to name: a build that moved in a way this strip
  // cannot describe. Say nothing rather than render an empty label.
  if (!d.quiet && lines.length === 0 && !lead) return null;

  return (
    <p className="rc" role="status" aria-label="Rotation changes">
      <em className="rc-head">🔄 what changed</em>
      {d.quiet ? (
        <span className="rc-quiet">
          {d.baseline
            ? <>no rank change since {d.baseline}</>
            // The honest first-run answer: there is no stored prior session to
            // compare against until a second scan lands.
            : <>{d.reason || 'first session on record — nothing to compare yet'}</>}
          {lead && <span className="rc-steady"> · {lead} still leading</span>}
        </span>
      ) : (
        <span className="rc-moves">
          {lines.map((l) => (
            <span key={l.key} className={`rc-chip rc-${l.kind}`}>{l.text}</span>
          ))}
          {extra > 0 && <span className="rc-dim">+{extra} more</span>}
          {lead && <span className="rc-steady">steady: {lead}</span>}
        </span>
      )}
    </p>
  );
}
