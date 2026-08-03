/* GEX Board — pure helpers for the cross-sectional dealer-gamma page
 * (Ajay 2026-07-17: "bullish stocks with key nodes and bearish stocks").
 * Rows come from GET /options/gex-board (backend options/gex_history.board —
 * the nightly options-key snapshot). This module only formats; the bucketing
 * (bullish/bearish/mixed) is backend logic so board and engine can't drift. */
import { fmtGex } from './opex';

export type BoardRow = {
  symbol: string;
  date_et?: string;
  spot?: number | null;
  regime?: 'pinning' | 'amplifying' | string | null;
  net_gex_dollars?: number | null;
  net_vex_dollars?: number | null;
  vex_read?: string | null;
  flip_strike?: number | null;
  call_wall?: number | null;
  put_wall?: number | null;
  magnet?: number | null;
  max_pain?: number | null;
  reliability?: 'index' | 'single_name' | string | null;
  expiration_date?: string | null;
};

export type BoardPayload = {
  as_of_date: string | null;
  bullish: BoardRow[];
  bearish: BoardRow[];
  mixed: BoardRow[];
  counts: { bullish: number; bearish: number; mixed: number };
  note?: string | null;
};

export type NodeChip = { icon: string; label: string; text: string };

function pctFrom(spot: number, level: number): string {
  const p = (level / spot - 1) * 100;
  return `${p >= 0 ? '+' : ''}${p.toFixed(1)}%`;
}

/** The key nodes for one row, null-safe and % -anchored to spot. Order:
 *  flip (the regime switch), call wall (ceiling), put wall (shelf), magnet. */
export function nodeChips(row: BoardRow): NodeChip[] {
  const spot = typeof row.spot === 'number' && row.spot > 0 ? row.spot : null;
  const fmt = (level?: number | null) =>
    typeof level === 'number' && level > 0
      ? `$${level % 1 === 0 ? level.toFixed(0) : level.toFixed(2)}` +
        (spot ? ` (${pctFrom(spot, level)})` : '')
      : null;
  const out: NodeChip[] = [];
  const flip = fmt(row.flip_strike);
  if (flip) out.push({ icon: '🎚️', label: 'flip', text: flip });
  const cw = fmt(row.call_wall);
  if (cw) out.push({ icon: '🧱', label: 'call wall', text: cw });
  const pw = fmt(row.put_wall);
  if (pw) out.push({ icon: '🛡️', label: 'put wall', text: pw });
  const mg = fmt(row.magnet);
  if (mg) out.push({ icon: '🧲', label: 'magnet', text: mg });
  return out;
}

/** One caveman sentence per row for the card footer. */
export function rowLine(row: BoardRow): string {
  const gex = fmtGex(row.net_gex_dollars);
  const base =
    row.regime === 'pinning'
      ? `Dealers hold ${gex} of stabilizing gamma — they buy dips, sell rips.`
      : row.regime === 'amplifying'
      ? `Dealers are ${gex} SHORT gamma — their hedging pushes moves further.`
      : 'No clear dealer-gamma read.';
  const vex =
    typeof row.net_vex_dollars === 'number' && row.vex_read
      ? ` VEX: ${row.vex_read}.`
      : '';
  return base + vex;
}

/** Single-name GEX is an approximation of an unobservable dealer book —
 *  badge it so index rows read stronger than single names. */
export function reliabilityBadge(row: BoardRow): { text: string; strong: boolean } {
  return row.reliability === 'index'
    ? { text: 'index-grade read', strong: true }
    : { text: 'single-name approx.', strong: false };
}
