/* alertKinds — ONE registry of push kinds + the ET clock helpers every
 * alert surface shares.
 *
 * Ajay 2026-09-05: "Do we have the same logic in back end demand for the ones
 * that I get alerts. Would it be the same list of stocks.. Also can I go to a
 * dedicated page to see the list of alerts? May be add it to recent alerts or
 * something?"
 *
 * Before this file PushHistoryPanel carried its own KIND_LABEL map and the
 * three zone kinds that page his phone (demand_alert, zone_bounce_alert,
 * supply_break_alert) were not in it — a 🧲 push rendered as the raw id
 * `demand_alert`. The new /alerts page, the panel, the bell and the
 * "alerted today" chips on the boards all read from here, so a kind added in
 * one place is labelled everywhere.
 *
 * Times: push_history.ts is a UTC epoch (seconds). Ajay reads the tape in ET,
 * so everything shown to him is formatted in America/New_York and says "ET".
 * Never the browser's local zone — a phone on a trip would relabel every row.
 */

export type AlertKindGroup =
  | 'zones' | 'trading' | 'breakout' | 'setup' | 'learning' | 'household' | 'admin' | 'system';

export type AlertKindDef = {
  emoji: string;
  /** Plain label, no emoji — `kindLabel()` joins the two. */
  label: string;
  group: AlertKindGroup;
};

/* Keys mirror the backend `kind` field set by send_to_all / send_to_user
 * callers (backend/push/*.py, supply_demand/*_alerts.py, zone_edge.py). */
export const ALERT_KINDS: Record<string, AlertKindDef> = {
  // ── Supply & Demand zone pushes (the phone-gated ones) ────────────────────
  demand_alert:        { emoji: '🧲', label: 'Demand-zone approach',    group: 'zones' },
  zone_bounce_alert:   { emoji: '🪃', label: 'Demand-level bounce',     group: 'zones' },
  supply_break_alert:  { emoji: '🚀', label: 'Breaking resistance',     group: 'zones' },
  trade_flash:         { emoji: '⚡', label: 'Trade flash at a zone',   group: 'zones' },

  // ── trading ───────────────────────────────────────────────────────────────
  pivot_alert:         { emoji: '🎯', label: 'Pivot / buy zone',        group: 'trading' },
  position_alert:      { emoji: '💼', label: 'Position alert',          group: 'trading' },
  promo_alert:         { emoji: '🎪', label: 'Promo mover',             group: 'trading' },
  price_alert:         { emoji: '🔔', label: 'Price alert',             group: 'trading' },
  pankaj_alert:        { emoji: '📊', label: "Pankaj's level",          group: 'trading' },
  stage_out_alert:     { emoji: '📉', label: 'Stage-out',               group: 'trading' },
  accumulation_change: { emoji: '🏦', label: 'Accumulation change',     group: 'trading' },
  scalp_tape:          { emoji: '🎛️', label: 'Scalp tape',              group: 'trading' },
  sepa_new_candidate:  { emoji: '🆕', label: 'New SEPA candidate',      group: 'trading' },
  morning_brief:       { emoji: '🌅', label: 'Morning brief',           group: 'trading' },
  market_hours_reminder: { emoji: '🔔', label: 'Market reminder',       group: 'trading' },

  // ── breakouts (also arrive as source='breakout' rows) ─────────────────────
  volume_breakout:     { emoji: '🚀', label: 'Volume breakout',         group: 'breakout' },
  rising_momentum:     { emoji: '📈', label: 'Rising momentum',         group: 'breakout' },
  watchlist_breakout:  { emoji: '⭐', label: 'Watchlist breakout',      group: 'breakout' },
  leaderboard_breakout:{ emoji: '🏆', label: 'Leaderboard breakout',    group: 'breakout' },
  juggernaut_watchlist:{ emoji: '💪', label: 'Juggernaut',              group: 'breakout' },
  stage_breakdown:     { emoji: '⚠️', label: 'Stage breakdown',         group: 'breakout' },
  stage_breakdown_2_3: { emoji: '⚠️', label: 'Stage 2→3 topping',       group: 'breakout' },
  stage_breakdown_2_4: { emoji: '🔻', label: 'Stage 2→4 cliff',         group: 'breakout' },
  stage_breakdown_3_4: { emoji: '🔻', label: 'Stage 3→4 decline',       group: 'breakout' },
  watchlist_stage_breakdown: { emoji: '🛑', label: 'Watchlist breakdown', group: 'breakout' },

  // ── setups (setups/ cron) ─────────────────────────────────────────────────
  setup_inside_day:    { emoji: '📦', label: 'Inside-day setup',        group: 'setup' },
  setup_peg:           { emoji: '⚡', label: 'PEG setup',               group: 'setup' },
  setup_orb_capture:   { emoji: '🎯', label: 'ORB range set',           group: 'setup' },
  setup_orb_triggered: { emoji: '🎯', label: 'ORB triggered',           group: 'setup' },
  setup_base_n_break:  { emoji: '🧱', label: 'Base-n-break setup',      group: 'setup' },
  setup_bull_flag:     { emoji: '🚩', label: 'Bull flag setup',         group: 'setup' },
  setup_cheat:         { emoji: '🎭', label: 'Cheat setup',             group: 'setup' },
  setup_ema_crossback: { emoji: '〰️', label: 'EMA crossback setup',     group: 'setup' },
  setup_episodic_pivot:{ emoji: '💥', label: 'Episodic pivot setup',    group: 'setup' },
  setup_exhaustion_extension: { emoji: '🥵', label: 'Exhaustion extension', group: 'setup' },
  setup_high_tight_flag: { emoji: '🏳️', label: 'High tight flag',       group: 'setup' },
  setup_post_earnings_drift: { emoji: '🌊', label: 'Post-earnings drift', group: 'setup' },
  setup_reversal_extension: { emoji: '↩️', label: 'Reversal extension',  group: 'setup' },
  setup_wedge_drop:    { emoji: '📐', label: 'Wedge drop setup',        group: 'setup' },
  setup_wedge_pop:     { emoji: '📐', label: 'Wedge pop setup',         group: 'setup' },

  // ── learning ──────────────────────────────────────────────────────────────
  minervini_flashcards:{ emoji: '🃏', label: 'Flash card',              group: 'learning' },
  vb_education:        { emoji: '📖', label: 'Volleyball card',         group: 'learning' },

  // ── household ─────────────────────────────────────────────────────────────
  todo_reminder:       { emoji: '📌', label: 'Todo reminder',           group: 'household' },
  todo_daily_digest:   { emoji: '📋', label: 'Todo digest',             group: 'household' },
  vb_workout:          { emoji: '🏐', label: 'Volleyball workout',      group: 'household' },
  vb_supplement:       { emoji: '💊', label: 'Volleyball supplements',  group: 'household' },
  house_daily:         { emoji: '🏡', label: 'House daily',             group: 'household' },
  house_scrape_failed: { emoji: '⚠️', label: 'House scrape failed',     group: 'household' },
  house_stagnant:      { emoji: '📉', label: 'House stagnant',          group: 'household' },

  // ── admin / system ────────────────────────────────────────────────────────
  user_signin:         { emoji: '👋', label: 'New user',                group: 'admin' },
  product_launch:      { emoji: '🚀', label: 'Product launch',          group: 'system' },
  generic:             { emoji: '📣', label: 'Notification',            group: 'system' },
};

/** The three S/D zone kinds that page the phone through alert_gates.py
 *  (room ≥ 5% to the first band overhead, print ≤ 1% above the demand band).
 *  The /alerts page opens on exactly these, and the boards' 🔔 chip reads
 *  only these — a 💼 position alert on the same name is not "the zone
 *  alerted". */
export const ZONE_KINDS: readonly string[] = ['demand_alert', 'zone_bounce_alert', 'supply_break_alert'];

/** The breakout kinds that live in sepa_breakouts rather than push_history.
 *  GET /notifications/recent includes them only when `kinds` names one. */
export const BREAKOUT_KINDS: readonly string[] = [
  'volume_breakout', 'rising_momentum', 'stage_breakdown_2_3', 'stage_breakdown_2_4', 'stage_breakdown_3_4',
];

/** "🧲 Demand-zone approach". Unknown kind → its raw id (never hidden: a
 *  kind the registry has not met is still a real push he received). Null /
 *  empty → the generic label. */
export function kindLabel(kind: string | null | undefined): string {
  if (!kind) return `${ALERT_KINDS.generic.emoji} ${ALERT_KINDS.generic.label}`;
  const d = ALERT_KINDS[kind];
  return d ? `${d.emoji} ${d.label}` : kind;
}

/** Plain label without the emoji, for running text ("No demand-zone approach
 *  alerts today"). Unknown → raw id. */
export function kindText(kind: string | null | undefined): string {
  if (!kind) return ALERT_KINDS.generic.label;
  return ALERT_KINDS[kind]?.label ?? kind;
}

export function kindEmoji(kind: string | null | undefined): string {
  if (!kind) return ALERT_KINDS.generic.emoji;
  return ALERT_KINDS[kind]?.emoji ?? '📣';
}

/* ── ET clock ────────────────────────────────────────────────────────────── */

export const ET_ZONE = 'America/New_York';

/* One formatter per shape, built once. `hourCycle: 'h23'` — some engines hand
 * back "24" for midnight under hour12:false, which would read "24:05 ET". */
const ET_PARTS = new Intl.DateTimeFormat('en-US', {
  timeZone: ET_ZONE, hourCycle: 'h23',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit',
});

type Wall = { y: number; m: number; d: number; hh: number; mm: number; ss: number };

function etWall(ms: number): Wall {
  const out: Record<string, number> = {};
  for (const p of ET_PARTS.formatToParts(new Date(ms))) {
    if (p.type !== 'literal') out[p.type] = Number(p.value);
  }
  return { y: out.year, m: out.month, d: out.day, hh: out.hour, mm: out.minute, ss: out.second };
}

const pad2 = (n: number) => String(n).padStart(2, '0');

/** "10:42 ET" for a unix-seconds stamp. Empty string for a missing / broken
 *  stamp rather than "NaN:NaN ET". */
export function etFromTs(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts) || ts <= 0) return '';
  const w = etWall(ts * 1000);
  return `${pad2(w.hh)}:${pad2(w.mm)} ET`;
}

/** "YYYY-MM-DD" of the ET calendar day the stamp falls on. The grouping key
 *  for the list — a 23:30 ET push and the 00:10 ET one after it are different
 *  days here even though they share a UTC date. */
export function etDayKey(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return '';
  const w = etWall(ts * 1000);
  return `${w.y}-${pad2(w.m)}-${pad2(w.d)}`;
}

/* Minutes to ADD to a UTC instant to read the ET wall clock: -240 under EDT,
 * -300 under EST. Read off the formatter, never hard-coded, so the DST
 * switch days come out right. */
function etOffsetMinutes(ms: number): number {
  const w = etWall(ms);
  const asUtc = Date.UTC(w.y, w.m - 1, w.d, w.hh, w.mm, w.ss);
  return Math.round((asUtc - ms) / 60_000);
}

/** Unix seconds of 00:00 ET on the ET day `offsetDays` ago (0 = today's ET
 *  midnight, 1 = yesterday's). This is the `since` the /alerts page and the
 *  boards' "alerted today" read send to /notifications/recent.
 *
 *  Two passes over the offset: the first guess uses the offset in force
 *  five hours into the target day, the second re-reads it AT the guessed
 *  midnight so a day that changes clocks still lands on 00:00 ET exactly. */
export function startOfEtDay(offsetDays = 0, nowMs: number = Date.now()): number {
  const w = etWall(nowMs);
  // Midnight UTC of the target calendar date — date arithmetic in UTC, so a
  // month or year boundary rolls correctly.
  const targetUtcMidnight = Date.UTC(w.y, w.m - 1, w.d - offsetDays);
  let guess = targetUtcMidnight - etOffsetMinutes(targetUtcMidnight + 5 * 3_600_000) * 60_000;
  guess = targetUtcMidnight - etOffsetMinutes(guess) * 60_000;
  return Math.floor(guess / 1000);
}

/** Today's ET day key — the yardstick for "today" everywhere on the page. */
export function todayEtKey(nowMs: number = Date.now()): string {
  return etDayKey(nowMs / 1000);
}

const DAY_HEAD = new Intl.DateTimeFormat('en-US', {
  timeZone: ET_ZONE, weekday: 'short', month: 'short', day: 'numeric',
});

/** Group heading for a day key: "Today · Fri, Sep 5", "Yesterday · Thu, Sep 4",
 *  else "Wed, Sep 3". Says which day in words so a 30-day list scans. */
export function etDayHeading(dayKey: string, nowMs: number = Date.now()): string {
  const [y, m, d] = dayKey.split('-').map(Number);
  if (!y || !m || !d) return dayKey;
  // Noon UTC of that date is inside the same ET day whatever the offset.
  const pretty = DAY_HEAD.format(new Date(Date.UTC(y, m - 1, d, 12)));
  const today = todayEtKey(nowMs);
  const yesterday = etDayKey(startOfEtDay(1, nowMs) + 3600);
  if (dayKey === today) return `Today · ${pretty}`;
  if (dayKey === yesterday) return `Yesterday · ${pretty}`;
  return pretty;
}

/** "HH:MM ET" from a backend ISO stamp (either an ET-offset stamp like
 *  "2026-09-05T13:02:11-04:00" or a UTC one). Null when unparsable. */
export function etFromIso(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return etFromTs(t / 1000);
}
