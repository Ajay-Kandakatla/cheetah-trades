/**
 * 🌫️ 2026-11-15 — the served day read (backend chart_maps/gajjala/day_read.served_block). Ajay 2026-11-14: "Also lately
 * I am seeing very choppy market but Gajjals examples are very bullish"; 2026-11-15 "yes" to an information-only label.
 * Served on GET /chart-maps/gajjala, /chart-maps/gajjala-1m and /chart-maps/luk to the primary owner only (null for
 * anyone else, null on 🧪 audited, absent on an older API). INFORMATION ONLY: nothing on the board is ordered, filtered
 * or marked by it. Every word is served; the FE types none.
 */
export type DayReadChip = {
  form: string;
  state: 'on' | 'off' | 'missing' | 'pending' | string;
  text: string;
  state_text?: string | null;
  value_text?: string | null;
  why?: string | null;
  asof_text?: string | null;
  source?: string | null;
  reads_at?: string | null;
};

export type DayRead = {
  state: 'read' | 'absent' | string;
  session?: string | null;
  is_today?: boolean | null;
  computed_at_et?: string | null;
  grades_through_et?: string | null;
  head?: string | null;
  counts?: Record<string, number> | null;
  fold_text?: string | null;
  chips?: DayReadChip[] | null;
  note?: string | null;
  caption?: string | null;
  read_date_text?: string | null;
  tags?: Record<string, unknown> | null;
};
