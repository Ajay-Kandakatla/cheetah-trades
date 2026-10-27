/* 🚩 Gajjala's tab — the payload types and a few pure helpers (2026-10-13).
 *
 * Ajay 2026-10-13: "Name the Tab Gajjala's he has multiple strategies..around
 * this. He is volume and price action based traded with short squeeze. He also
 * has premarket and post market analysis." and "Implement his full stategy do
 * not assume anything."
 *
 * The board is scanned, read, counted and ORDERED on the server
 * (backend/chart_maps/gajjala/tab.py, filled by the 5-minute cron pass). Every
 * sentence on the tab is SERVED — the state labels, the strip, the chips, the
 * criteria, the Playbook quotes. This module types the payload contract and
 * the URL plumbing; it types no threshold and no rule number. The one list it
 * carries, GG_SUBS, is the FALLBACK strip before the first response lands and
 * is pinned key / emoji / label against backend constants.SUBS by the
 * contracts, so the two can never drift. Display only: nothing here gates,
 * pushes or trades. UNMEASURED.
 *
 * 🧠 Potential + 📈 Track (2026-10-15). Ajay: "In Gajjalas setup I wanna find
 * potential stocks this shows me what has happened I am trying to setup for
 * this tab to act like Gajjalas brain. So create a potential category in this
 * section." then "In all the sub tab and add a track and alert to show me new
 * potential is added everyday." The server decides what a potential is (the
 * detectors' own forming read, potential.py) and words every row, title, tell
 * and timeline entry; this module only types that payload (BUILD_SPEC4 §3.9)
 * and adds the ninth fallback sub, LAST. No threshold, no rule word.
 *
 * 🔄 Scan on open + 🎯 A+ line (2026-10-15, BUILD_SPEC5 §3.8). Ajay: "When ever
 * I open Gajjala's intiate a new scan of stocks.  In that moment and if there
 * are any enterable stocks on the top which I see in potential i guess". The
 * board POSTs GG_SCAN_PATH once per open (owner only); the server answers at
 * once and sets the poll plan (eta / poll / wait-max seconds) — ggScanPlan only
 * reads those served numbers, no number typed here. The `scan` and `enterable`
 * blocks are SERVED sentences (the as-of line, the scanning line, the A+ rows,
 * the quiet empty line, the note); this module types them and adds nothing. An
 * open rings no device — both push gates run dry on it. UNMEASURED.
 *
 * 🏁 Track record (2026-10-16, BUILD_SPEC9 §3.11). Ajay: "also can you track
 * all Gajjals stocks and keep a new tab to show wins vs losses. To see a
 * percentage and the ticker." and "We are not looking for winners just in time
 * but when they got in to our alerts if they made it or not. Like XLAB today
 * was a winner I made good money on it". The tenth sub, LAST: every alert that
 * rang, graded on the server by GG's trade math (backend chart_maps/gajjala/
 * ledger.py). This module types that payload and adds the `span` param (the
 * day picker); every string SERVED; no number typed. A ledger of the alerts
 * as sent, not a study. UNMEASURED.
 *
 * 🕰️ Entries timeline (2026-10-16, DECISIONS11 D3). Ajay: "We have a Promo Circuit tab in Catalyst tab. Can you use
 * the graph component from  that to show what happened to Entries alert of Gajjala with all the 100% criteria
 * satisfier. One you alert it from the alert system you built please". The 🏁 block gains the SERVED `views` (the
 * toggle labels, the kinds the timeline lists, its empty line, the Tape head and the 📈 title); this module types it,
 * adds the `view` param (FE-only — it never rides the GET: ggQuery is unchanged) and ggTimelineOn. UNMEASURED.
 *
 * ⏪ Replayed line + ✅ / ❌ categories (2026-10-16 night, DECISIONS11 D4–D5 / D11–D12, AMENDMENTS11 F7 / F13). Ajay:
 * "Would you be able to back test for the past week from his alerts any way to do so? build a pre historic timeline or
 * so?" and "I want winners and losers category in his track record and would like us to study the losers". The 🏁
 * block gains the SERVED `replayed_text` / `replayed_note` (the ⏪ line, never in a %), the served chips
 * `categories` / `categories_timeline` (ROW counts inside the served text, never a %), the served
 * `category_empty_text`; each row its served `bucket` / `bucket_text` / `loss_text` / `replay_text`. This module types
 * them, adds the `cat` param (FE-only — it never rides the GET: ggQuery is unchanged) and ggCatOn / ggCatDays (a
 * client-side filter by the SERVED bucket; "all" = the first served chip key — no key typed here). UNMEASURED.
 *
 * 🚫 Broker tag (2026-10-17, DECISIONS12 D1–D9, AMENDMENTS12). Ajay: "ok then avoid showing me names that are not
 * eligible in Fidelity then." and "Or just add a tag that not eligible on Fidelity". A TAG, never a filter: every row /
 * tile type gains the SERVED `broker_text` (tab.BROKER_FLAG_TEXT on a name on his own list, else null) and the board the
 * SERVED owner block `broker_flags` (null for anyone but the primary owner). GG_BROKER_PATH is the owner's add / remove
 * route (POST / DELETE; the board GET carries the list, so the FE never GETs it). Every word is served by tab.py — this
 * module types no word and never the broker's name. ggQuery is unchanged.
 *
 * 📌 Trader tag (2026-10-27, BUILD_SPEC26 §3.4). Ajay: "Add them to Gajjals, they are pretty good". The names a tracked
 * trader flagged for this tab posted join the scan as candidates; every row / tile type gains the SERVED `trader_text`
 * (tab / ledger via trader_names.text_for — served to EVERY viewer, null when untagged) and the strip the SERVED
 * `trader_text` / `trader_skip_text` lines. A TAG: nothing hides, filters or counts a row here. This module types no
 * word and no trader's name. UNMEASURED.
 *
 * 🚩 Gajjala's 1-minute page (2026-10-27, BUILD_SPEC27 §3.8). Ajay: "Can you create a new page, I would like you to do
 * the same logic of Gajjalas but on 1 min candles please." and "do everything and also add the track record for it from
 * today..". The same board, its own endpoint (components/ggVariant.ts GG_VARIANT_BASE): GgTf gains '1m', GgBoard.tab
 * 'gajjala_1m', and the 1-minute board serves a `variant` block (its title, its honesty line, its frames — every word
 * and every frame SERVED by variant.served_block); parseGgTf takes the allowed frames (the served `variant.tfs`, else
 * GG_TFS — a '1m' never reaches the 5-minute board). Every alert there is recorded in shadow. UNMEASURED.
 */
import type { CmTile } from './chartMaps';
import type { ServedVolAvg } from './volumePane';

export type GgSetup = 'bull_flag' | 'kiss_fly' | 'horizontal_fade' | 'intraday_vcp' | 'reversal_squeeze';
export type GgSub = GgSetup | 'premarket' | 'postmarket' | 'playbook' | 'potential' | 'track_record';
export type GgTf = '1m' | '5m' | '15m';
export type GgState = 'aplus' | 'triggered' | 'stopped' | 'forming' | 'partial' | 'invalid' | 'none';

/** URL params. `focus` is the house FOCUS_PARAM (lib/growthArrivals). */
export const GG_SUB_PARAM = 'sub';
export const GG_TF_PARAM = 'tf';
export const GG_SORT_PARAM = 'sort';
/** 🏁 the Track record day picker (the served `spans` keys) — rides only when set. */
export const GG_SPAN_PARAM = 'span';
/** 🕰️ the 🏁 view toggle (the served `views.items` keys) — FE-only, never sent on the GET (DECISIONS11 D3). */
export const GG_VIEW_PARAM = 'view';
/** The served `views.items` key of the 🕰️ entries timeline (tape.VIEWS[1][0]) — the default view rides no param. */
export const GG_VIEW_TIMELINE = 'timeline';
/** ✅ / ❌ the 🏁 category chips (the served `categories[].key`, == ledger.CATEGORY_PARAM) — FE-only, never sent on the GET
 *  (DECISIONS11 D11); the first served key (ledger.CATEGORY_KEYS[0], "all") rides no param. */
export const GG_CAT_PARAM = 'cat';
/** 🎯 the 🏁 A+ filter chip (the served `kinds[].key`, == ledger.KIND_PARAM) — FE-only, never sent on the GET (ggQuery has
 *  no kind; BUILD_SPEC25 §3.4); the first served key (ledger.KIND_KEYS[0], "all") rides no param. */
export const GG_KIND_PARAM = 'kind';
export const GG_DEFAULT_SUB: GgSub = 'bull_flag';
export const GG_TFS: ReadonlyArray<GgTf> = ['5m', '15m'];
/** Every frame a GgTf can name (the type's members) — a served `variant.tfs` entry outside it is dropped.
 *  2026-10-27 (critic finding 5): exported as GG_TF_ALL so a variant page parses its `tf` deep link before its
 *  first board lands (the server ignores a tf outside its own v.tfs). */
export const GG_TF_ALL: ReadonlyArray<GgTf> = ['1m', '5m', '15m'];
const GG_TF_KEYS: ReadonlySet<string> = new Set<string>(GG_TF_ALL);

/** The fallback sub strip — == backend chart_maps/gajjala/constants.SUBS
 *  (DECISIONS order), contract-pinned. The SERVED `subs` (with counts) wins. */
export const GG_SUBS: ReadonlyArray<{ key: GgSub; emoji: string; label: string }> = [
  { key: 'bull_flag', emoji: '\u{1F6A9}', label: 'Bull Flag' },
  { key: 'kiss_fly', emoji: '\u{1F48B}', label: 'EMA Kiss & Fly' },
  { key: 'horizontal_fade', emoji: '➖', label: 'Horizontal Fade' },
  { key: 'intraday_vcp', emoji: '\u{1F300}', label: 'Intraday VCP' },
  { key: 'reversal_squeeze', emoji: '\u{1F3BE}', label: 'Reversal Squeeze' },
  { key: 'premarket', emoji: '☀️', label: 'Premarket' },
  { key: 'postmarket', emoji: '\u{1F319}', label: 'Post-market' },
  { key: 'playbook', emoji: '\u{1F4D3}', label: 'Playbook' },
  { key: 'potential', emoji: '\u{1F9E0}', label: 'Potential' },
  { key: 'track_record', emoji: '\u{1F3C1}', label: 'Track record' },
];
const SUB_KEYS = new Set<string>(GG_SUBS.map((s) => s.key));

/** The five setup subs (== backend constants.SETUPS, test-pinned) — the only
 *  subs that carry a 🧠 strip (☀️ / 🌙 / 📓 / 🧠 never do, BUILD_SPEC4 §3.9 (c)). */
export const GG_SETUPS: ReadonlyArray<GgSetup> = ['bull_flag', 'kiss_fly', 'horizontal_fade', 'intraday_vcp', 'reversal_squeeze'];
const SETUP_KEYS = new Set<string>(GG_SETUPS);
export const isGgSetup = (s: unknown): s is GgSetup => typeof s === 'string' && SETUP_KEYS.has(s);

/** 📋 The chips the card's head row prints, so PatternChart skips its own
 *  copies (the EmaFramesBoard precedent — no chip printed twice). */
export const GG_OUTER_CHIPS = ['growth', 'short', 'explosive', 'enterable'] as const;

/** Ajay's own words for the three "listed, never A+, never pushed" reads
 *  (DECISIONS 2026-10-13: K4a "long flag", K5a "near-kiss", VCP "B — imperfect").
 *  FALLBACK ONLY — the served `variant_label` / `grade_label` wins. */
export const GG_VARIANT_LABEL: Readonly<Record<string, string>> = {
  // long_flag: band empty since 2026-10-18 (DECISIONS13 D1/D4, K4_BF_LONG_FLAG_MAX = None) — a fallback word for older payloads; HIS CALL Q3 to drop.
  long_flag: 'long flag', near_kiss: 'near-kiss',
};
export const GG_GRADE_LABEL: Readonly<Record<string, string>> = { B: 'B — imperfect' };

export type GgCriterion = { key: string; label: string; ok: boolean | null; value?: string | null; need?: string | null };

/** A chip as the server sends it: its text, or an object carrying `text`
 *  (the context FloatRead does), or null when there is nothing to say. */
export type GgChipValue = string | { text?: string | null } | null | undefined;

export type GgChips = {
  float?: GgChipValue;
  rotation?: GgChipValue;
  halts?: GgChipValue;
  psych?: GgChipValue[] | null;
  squeeze_history?: GgChipValue;
  change_pct?: number | string | null;
  volume?: number | string | null;
  vol_src?: string | null;
  session_badge?: GgChipValue;
  first15?: boolean | string | null;
  /** DECISIONS R2-5: more than 3 red closes = he waits — a chip, never a gate. */
  red_closes?: GgChipValue;
  /** DECISIONS R2-6: this setup on this name was stopped earlier today. */
  stopped_earlier?: GgChipValue;
  /** 🔄 2026-10-15 (W7): "read at the HH:MM ET pass" — this card's read is older than the latest pass. */
  read_at?: GgChipValue;
  /** DECISIONS: a listing with no reference type yet is labelled "type unknown". */
  instrument?: GgChipValue;
  /** Outside regular hours: his limit-orders / less-size line (S8 1:16:35). */
  outside_rth?: GgChipValue;
  float_suspect?: GgChipValue;
  flag_k?: GgChipValue;
};

export type GgRead = {
  setup: GgSub;
  state: GgState | string;
  state_label: string;
  frame?: GgTf | string;
  ready?: boolean;
  broke?: boolean;
  trigger?: number | null;
  stop?: number | null;
  risk_pct?: number | null;
  entry_bar_t?: string | null;
  criteria?: GgCriterion[];
  missed?: string[];
  unjudged?: string[];
  grade?: string | null;
  grade_label?: string | null;
  variant?: string | null;
  variant_label?: string | null;
  chips?: GgChips;
  listed?: { since?: string | null; last_qualified?: string | null; day_n?: number | null; text?: string | null } | null;
  premarket?: { text?: string | null; carry_text?: string | null; off_pm_high_text?: string | null } | null;
  postmarket?: { text?: string | null; checked_text?: string | null; exhaustion_text?: string | null } | null;
  /** 🧠 sub tiles only: why this card is on the roll-up (§3.9 (b), W12). */
  potential?: GgPotentialTile | null;
};

/* ---- 🧠 Potential + 📈 Track (2026-10-15, BUILD_SPEC4 §3.9) — every string SERVED. ---- */
export type GgPotentialKind = 'armed' | 'building';
/** One of GG's tells — a badge, never a gate; `cite` = his timestamped words. */
export type GgTell = { key: string; text: string; cite?: string | null };
/** One row of a setup sub's 🧠 strip; `text` is the whole served line (W9). */
export type GgPotentialRow = {
  symbol: string;
  setup: GgSetup | string;
  kind: GgPotentialKind | string;
  kind_label: string;
  trigger?: number | null;
  stop?: number | null;
  risk_pct?: number | null;
  reason?: string | null;
  first_seen_et?: string | null;
  again?: boolean;
  tells?: GgTell[];
  href?: string | null;
  text: string;
  /** 🚫 the served tag (tab.BROKER_FLAG_TEXT) when the name is on his list — owner only; null / absent → no chip. */
  broker_text?: string | null;
  /** 📌 the served trader tag (trader_names.text_for) — every viewer; null / absent → no chip. */
  trader_text?: string | null;
};
export type GgPotentialStrip = {
  title: string;
  text?: string | null;
  counts?: { armed?: number; building?: number; today?: number } | null;
  rows: GgPotentialRow[];
  empty_text?: string | null;
};
export type GgPotentialTile = {
  kind: GgPotentialKind | string;
  kind_label: string;
  setup: GgSetup | string;
  setup_label?: string | null;
  first_seen_et?: string | null;
  again?: boolean;
  tells?: GgTell[];
  also?: { setup: string; label: string }[];
  text: string;
};
export type GgTrackRow = {
  symbol: string;
  setup: GgSetup | string;
  setup_label?: string | null;
  first_seen_et?: string | null;
  first_kind?: GgPotentialKind | string | null;
  first_kind_label?: string | null;
  first_px?: number | null;
  first_trigger?: number | null;
  first_stop?: number | null;
  last_state?: string | null;
  last_state_text?: string | null;
  last_px?: number | null;
  move_pct?: number | null;
  move_text?: string | null;
  vs_trigger_pct?: number | null;
  vs_trigger_text?: string | null;
  /** "📲 sent 09:21 ET" / "held: …" — incl. AMENDMENTS4 D9's "held: joined mid-session: tracking, not ringing". */
  push_text?: string | null;
  /** "🎯 entry sent 10:36 ET" — 🎯 served by tab._track_row — the FE composes none (2026-10-16, DECISIONS10 D4);
   *  null when no live A+ entry rang for this (symbol, setup, session). */
  entry_text?: string | null;
  graveyard_on?: string | null;
  timeline?: { at_et?: string | null; text: string }[];
  text: string;
  href?: string | null;
  /** 🚫 the served tag — owner only; null / absent → no chip. */
  broker_text?: string | null;
  /** 📌 the served trader tag (trader_names.text_for) — every viewer; null / absent → no chip. */
  trader_text?: string | null;
};
export type GgTrackBlock = { date?: string; label?: string; title?: string | null; n?: number;
                             armed_n?: number; building_n?: number; pushed_n?: number;
                             rows: GgTrackRow[]; more_n?: number | null };
export type GgTrack = {
  title: string;
  unmeasured?: string | null;
  empty_today?: string | null;
  today?: GgTrackBlock | null;
  yesterday?: GgTrackBlock | null;
};
/** 👀 ☀️ / 🌙 names with no potential in any setup — display only, never pushed. */
export type GgWatch = { text: string; symbols: { symbol: string; href: string; broker_text?: string | null;
  /** 📌 the served trader tag — every viewer; null / absent → no chip. */
  trader_text?: string | null }[] };

/* ---- 🏁 Track record (2026-10-16, BUILD_SPEC9 §3.8 / §3.11) — every string SERVED; `state` is a CSS hook only. ---- */
/** `no_risk` = trigger equal to the stop on the alert (AMENDMENTS9 E4) — listed, never counted. `no_time` = no
 *  alert time on the row (E3) — listed, never graded. */
export type GgTrState = 'win' | 'loss' | 'open' | 'flat' | 'no_entry' | 'no_plan' | 'no_risk' | 'no_time' | 'pending' | 'split';
export type GgTrCell = { state: GgTrState | string; text: string; sub_text?: string | null; provisional?: boolean };
export type GgTrRow = { key: string; id?: string; date: string; symbol: string; setup: string; setup_label: string;
  kind: string; line: 'live' | 'shadow' | string; kind_text: string; at_et?: string | null; at_text: string;
  /** E1 served session chip ("rang pre" / "rang RTH" / "rang AH"); E4 served "thin R" chip — null when none. */
  rang_text?: string | null; thin_text?: string | null;
  trigger?: number | null; stop?: number | null; fill_px?: number | null; plan_text: string; note?: string | null;
  href?: string | null; same: GgTrCell; next: GgTrCell;
  /** ✅ / ❌ the row's served category (ledger.bucket_of — one of ledger.BUCKETS) and its served words (DECISIONS11 D11).
   *  `bucket` is also the row's tint hook (ggTrRowClass); `bucket_text` feeds the category chips. */
  bucket?: string | null; bucket_text?: string | null;
  /** ✅ / ❌ 2026-10-27 (HIS CALL Q11 answered by his word — F13 reversed): the served flag DRAWN in the Ticker cell on
   *  win / loss rows (ledger.FLAG_BUCKETS); null / absent on every other row → no chip. */
  flag_text?: string | null;
  /** D12 the served loss facts (ledger.loss_text) — a string on bucket "loss" rows only, else null. */
  loss_text?: string | null;
  /** ⏪ the served replayed chip (ledger.REPLAY_CHIP / REPLAY_CHIP_UNGATED) — null on the live / shadow lines. */
  replay_text?: string | null;
  /** 🚫 the served tag (ledger.served_block via the tab's callable) — owner only; null / absent → no chip. */
  broker_text?: string | null;
  /** 📌 the served trader tag (ledger served row, trader_names.text_for) — null on an untagged or replayed row. */
  trader_text?: string | null };
/** ✅ / ❌ one served chip: `text` carries the ROW count (and " +r ⏪" when replayed rows share the bucket — F13);
 *  `n` / `n_replayed` are the served numbers (the FE prints `text` only, never composes a count). */
export type GgTrCategory = { key: string; text: string; n: number; n_replayed?: number | null };
export type GgTrDay = { date: string; label: string; rows: GgTrRow[]; more_n?: number | null };
export type GgTrackRecord = { title: string; rule_label?: string | null; rule_text?: string | null; honesty?: string | null; span: string;
  spans: { key: string; label: string }[]; heads: { key: string; label: string }[];
  counts_text: { same: string; next: string }; shadow_text?: string | null;
  /** 🎯 the live A+ entries' own line (ledger.served_block, AMENDMENTS10 F3 — never pooled with the 🧠 %); served,
   *  null when no live A+ entry is on the span (2026-10-16). */
  entries_text?: string | null; today_text?: string | null;
  days: GgTrDay[]; more_text?: string | null; empty_text?: string | null; grade_at_et?: string | null;
  /** 🕰️ the served view toggle (tape.views_block(), DECISIONS11 D3); absent on an older API → no toggle. */
  views?: GgTrViews | null;
  /** ✅ / ❌ the served chips over the rows shown (ledger.served_block, DECISIONS11 D11 / AMENDMENTS11 F6) — the list
   *  view's and the 🕰️ timeline's own (its kinds only); absent on an older API → no chip row, every row. */
  categories?: GgTrCategory[] | null; categories_timeline?: GgTrCategory[] | null;
  category_param?: string | null; category_empty_text?: string | null;
  /** ⏪ the served replayed line + its caveat line (DECISIONS11 D5) — null when no replayed row is on the span. */
  replayed_text?: string | null; replayed_note?: string | null;
  /** 🎯 the served A+ filter chips (ledger._kinds — ROW counts inside the served text, never a %), the param name and the
   *  served empty line; absent on an older API → no chip row, every row (BUILD_SPEC25 §3.4). */
  kinds?: GgTrKind[] | null; kind_param?: string | null; kind_empty_text?: string | null;
  /** 🎯 the ✅ / ❌ chips over the A+ rows only (ledger._categories(aplus rows)) — the chips while 🎯 is on. */
  categories_aplus?: GgTrCategory[] | null;
  /** 🎯 the served A+ block (ledger.aplus_block): its own capped rows, pooled counts, sentences and the three charts. */
  aplus?: GgTrAplus | null;
  /** ✅ wins first (2026-10-27): the served sort chips (ledger._sorts), the param name, the served default key and the
   *  served bucket order the FE sorts by (ledger.BUCKETS); absent on an older API → no chips, the served order. */
  sorts?: GgTrSort[] | null; sort_param?: string | null; sort_default?: string | null;
  bucket_order?: string[] | null };
/** ✅ one served sort chip: `bucket_sort` says whether it orders the rows by the served `bucket_order` (a boolean —
 *  the FE types no sort key); false / absent = the served order. */
export type GgTrSort = { key: string; label: string; bucket_sort?: boolean | null };
/** 🎯 one served A+ filter chip (`track_record.kinds[]` — NOT `views.kinds`, which is a list of row kinds). */
export type GgTrKind = { key: string; text: string; n: number; n_replayed?: number | null };
/** 🎯 one served chart item (ledger._aplus_cell items): `key` is a CSS hook, `label` / `text` are served words. */
export type GgTrApItem = { key: string; label: string; n: number; text: string };
/** 🎯 one served chart cell (ledger._aplus_cell): every number and sentence served; the FE draws geometry only. */
export type GgTrApCell = { total: number; decided: number; pct: number | null; loss_pct: number | null; pct_text: string;
  text: string; short_text: string; items: GgTrApItem[] };
/** 🎯 one served by-setup row / by-day column — a cell per horizon. */
export type GgTrApGroup = { key: string; label: string; same: GgTrApCell; next: GgTrApCell };
export type GgTrApChart =
  | { key: 'outcomes'; title: string; bars: (GgTrApCell & { key: string; label: string })[] }
  | { key: 'by_setup'; title: string; rows: GgTrApGroup[] }
  | { key: 'by_day'; title: string; cols: GgTrApGroup[] };
/** 🎯 ledger.aplus_block — always served beside the 🏁 list; `days` = its OWN capped A+ rows (the built row dicts). */
export type GgTrAplus = { title: string; total: number; n_sent: number; n_shadow: number;
  counts: { same: Record<string, number | null>; next: Record<string, number | null> };
  counts_text: { same: string; next: string } | null; split_text?: string | null; replayed_note?: string | null;
  more_text?: string | null; empty_text?: string | null; honesty: string; horizons: { key: string; label: string }[];
  horizon_default: string; charts: GgTrApChart[]; days: GgTrDay[] };
/** 🕰️ tape.views_block() — every label SERVED; `kinds` = the row kinds the timeline lists (the FE picks none itself). */
export type GgTrViews = { param: string; default: string; items: { key: string; label: string }[]; kinds: string[];
  empty_text: string; tape_head: string; tape_toggle: string; tape_toggle_title: string };

/** 🕰️ The timeline view is on: the served toggle offers it AND the URL asks for it (an older API → never). */
export function ggTimelineOn(tr: GgTrackRecord | null | undefined, view: string | null | undefined): boolean {
  return !!tr?.views?.items?.some((i) => i.key === GG_VIEW_TIMELINE) && view === GG_VIEW_TIMELINE;
}

/** ✅ / ❌ a category filter is on: `cat` is a SERVED chip key other than the first (the first = ledger.CATEGORY_KEYS[0],
 *  "all"). No served chips (an older API), a null / unknown `cat` → off (every row). */
export function ggCatOn(cat: string | null | undefined, cats: GgTrCategory[] | null | undefined): boolean {
  const keys = (cats || []).map((c) => (c && typeof c.key === 'string' ? c.key : null));
  return !!cat && keys.length > 1 && keys.indexOf(cat) > 0;
}

/** ✅ / ❌ the served days filtered client-side by the SERVED row `bucket` (DECISIONS11 D11): only rows with
 *  `bucket === cat`, a day left empty is dropped; filter off (ggCatOn false: null / "all" = the first served key /
 *  unknown / no served chips) → the days unchanged (the same array). */
export function ggCatDays(days: GgTrDay[], cat: string | null | undefined,
                          cats?: GgTrCategory[] | null): GgTrDay[] {
  if (!ggCatOn(cat, cats)) return days;
  return (days || [])
    .map((d) => ({ ...d, rows: (d.rows || []).filter((r) => !!r && r.bucket === cat) }))
    .filter((d) => d.rows.length > 0);
}

/** 🎯 the A+ filter is on: `kind` is a SERVED chip key other than the first (ggCatOn's rule — the first =
 *  ledger.KIND_KEYS[0], "all"). No served chips (an older API), a null / unknown `kind` → off (every row). */
export function ggKindOn(kind: string | null | undefined, kinds: GgTrKind[] | null | undefined): boolean {
  const keys = (kinds || []).map((k) => (k && typeof k.key === 'string' ? k.key : null));
  return !!kind && keys.length > 1 && keys.indexOf(kind) > 0;
}

/** 🎯 the rows the list shows: filter off → `days` unchanged (the same array); on → the served `aplus.days` (its OWN
 *  capped A+ rows — the 400-row cap of `days` never cuts them), or none when the block is not served. */
export function ggKindDays(days: GgTrDay[], kind: string | null | undefined, kinds: GgTrKind[] | null | undefined,
                           aplus: GgTrAplus | null | undefined): GgTrDay[] {
  if (!ggKindOn(kind, kinds)) return days;
  return Array.isArray(aplus?.days) ? aplus!.days : [];
}

/** ✅ wins first (2026-10-27): the served sort chip in force — the URL `sort` when it is a served key, else the chip
 *  whose key is the served default; no served chips (an older API) → null = the served order. No key typed here. */
export function ggTrSort(sort: string | null | undefined,
                         tr: Pick<GgTrackRecord, 'sorts' | 'sort_default'> | null | undefined): GgTrSort | null {
  const items = (tr?.sorts || []).filter((s): s is GgTrSort => !!s && typeof s.key === 'string' && s.key !== '');
  if (!items.length) return null;
  const picked = sort ? items.find((s) => s.key === sort) : undefined;
  return picked || items.find((s) => s.key === tr?.sort_default) || null;
}

/** The rows of one served day in the order the chip asks: a bucket sort = a STABLE sort by the row's served `bucket`
 *  position in the served `bucket_order` (a missing / unknown bucket sinks last, served order kept inside a bucket);
 *  any other chip, no chip, or no served order → the rows exactly as served (the same array). */
export function ggSortRows(rows: GgTrRow[], item: GgTrSort | null | undefined,
                           order: readonly string[] | null | undefined): GgTrRow[] {
  if (!item || !item.bucket_sort || !Array.isArray(order) || !order.length) return rows;
  const rank = (r: GgTrRow): number => {
    const i = typeof r.bucket === 'string' ? order.indexOf(r.bucket) : -1;
    return i < 0 ? order.length : i;
  };
  return rows.map((r, i) => ({ r, i })).sort((a, b) => rank(a.r) - rank(b.r) || a.i - b.i).map((x) => x.r);
}

/** The row's tint hook (2026-10-27): `gg-tr-row` plus `gg-tr-row-<bucket>` when the row serves a bucket string — a CSS
 *  hook only (gajjala.css tints win / loss); no bucket → the bare class. */
export function ggTrRowClass(r: Pick<GgTrRow, 'bucket'> | null | undefined): string {
  const b = r && typeof r.bucket === 'string' ? r.bucket.trim() : '';
  return b ? `gg-tr-row gg-tr-row-${b}` : 'gg-tr-row';
}

/** One type for one concept: the served 📊 volume average (lib/volumePane). */
export type GgVolAvg = ServedVolAvg;
/** `tf` = the frame this card actually drew (tab.tile_tf / the empty-frame fallback) — it can differ from the
 *  board's `tf` (a ➖ Fade read that fell back to 5-minute bars). */
export type GgTile = CmTile & { tf?: GgTf | string | null; vol_avg?: GgVolAvg | null; gajjala?: GgRead | null;
  /** 🚫 the served tag — owner only; null / absent → no chip. */
  broker_text?: string | null;
  /** 📌 the served trader tag — every viewer; null / absent → no chip. */
  trader_text?: string | null };

export type GgPlaybookItem = string | {
  text: string;
  ts?: string | null;
  source?: string | null;
  verbatim?: boolean;
  status?: string | null;
  status_label?: string | null;
  sources?: { key?: string | null; url?: string | null; ts?: string | null }[];
};
export type GgPlaybook = {
  title?: string | null;
  note?: string | null;
  sections?: { title: string; items: GgPlaybookItem[] }[];
  avoids?: GgPlaybookItem[];
  management?: GgPlaybookItem[];
  contradicted?: GgPlaybookItem[];
  knobs?: { key: string; text?: string | null; value?: string | number | null; provenance?: string | null }[];
  sources?: { key?: string | null; title: string; url: string; date?: string | null; kind?: string | null;
              first_hand?: boolean; note?: string | null }[];
};

/** 🚩 2026-10-27: the served variant block (backend chart_maps/gajjala/variant.served_block) — the 1-minute page only;
 *  absent on 🚩 Gajjala's. `title` / `honesty` are printed verbatim, `tfs` drives the bar-size toggle. The FE types none. */
export type GgVariantBlock = {
  key: string; tab: string; label?: string | null; title?: string | null; honesty?: string | null;
  tfs?: string[] | null; primary?: string | null; slow?: string | null; api_base?: string | null; record_from?: string | null;
};

export type GgBoard = {
  tab: 'gajjala' | 'gajjala_1m';
  /** 🚩 2026-10-27: the 1-minute page's served block; absent on 🚩 Gajjala's (and on an older API). */
  variant?: GgVariantBlock | null;
  sub: GgSub;
  sub_resolved_from?: string;
  tf: GgTf;
  /** ℹ️ 2026-10-18 (DECISIONS15 D1): `title` = the served legend text for the 🧠 sub (tab.count_legend's potential row);
   *  null on every other sub, absent on an older API. Printed as the button's native title; the FE types none. */
  subs: { key: GgSub; emoji: string; label: string; count?: number | null; title?: string | null }[];
  session?: {
    date?: string; label?: string; tape?: string; badge?: string | null;
    first15?: boolean; first15_text?: string | null; refresh_sec?: number | null;
  };
  pass?: {
    as_of_et?: string | null; stale?: boolean; stale_after_sec?: number; warming?: boolean;
    stale_text?: string | null; warming_text?: string | null;
    /** 🔄 2026-10-15: the latest pass's clock (ISO, UTC) — the stamp the scan POST's `latest_at` is compared to. */
    at?: string | null;
    /** 🔄 2026-10-15: the latest pass was an on-open pass. */
    on_demand?: boolean;
  };
  strip?: { runners_100?: number; runners_80?: number; best_change_pct?: number | null;
            best_symbol?: string | null; quiet?: boolean; text?: string | null;
            /** 📌 2026-10-27: the SERVED trader lines (trader_names.strip_text / skip_text) — null when nothing to say. */
            trader_text?: string | null; trader_skip_text?: string | null };
  counts?: Partial<Record<GgState | 'awaiting_answer' | 'listed', number>>;
  counts_text?: string | null;
  /** ℹ️ 2026-10-18 (DECISIONS15 D1): the ONE served legend (tab.count_legend) — one {key, word, text} per word on the
   *  counts line, the 🧠 sub's number and the 📈 Track's number, in served order; absent on an older API (nothing new renders). */
  counts_legend?: { key: string; word: string; text: string }[] | null;
  tiles: GgTile[];
  graveyard_today?: string[];
  graveyard_text?: string | null;
  note?: string | null;
  empty_note?: string | null;
  rules_section?: string;
  awaiting?: { setup: string; his_call: string; text: string }[];
  sorts?: { key: string; label: string }[];
  sort?: string | null;
  /** 🎾 2026-10-18 (DECISIONS13 D3): the served ordering word (tab.RS_ORDER_TEXT) — the squeeze sub only; null on every other
   *  sub, absent on an older API. Printed verbatim; the FE types none. */
  order_note?: string | null;
  /** 🌀 2026-10-20 (BUILD_SPEC18 D3/D6): the served "counted, not listed" line (tab.build `list_note`) — the 🌀 Intraday VCP
   *  sub only, when reads with fewer than K4_VCP_MIN_CYCLES contractions were counted but not carded; null on every other
   *  sub, absent on an older API. Printed verbatim; the FE types none. */
  list_note?: string | null;
  push?: { mode?: string | null; text?: string | null } | null;
  postmarket?: {
    unchecked_n?: number; unchecked_text?: string | null;
    /** 🌙 A+ recap rows — `href` SERVED by tab.recap (= potential.deep_link, the setup card; 2026-10-16, DECISIONS10 D7);
     *  absent on an older API. The FE guards it with ggHref and composes none. */
    recap?: { title?: string | null; rows?: { symbol: string; setup?: string | null; text: string; href?: string | null;
                                             broker_text?: string | null; trader_text?: string | null }[] } | null;
  } | null;
  playbook?: GgPlaybook | null;
  /** 🧠 strip — setup subs only; absent on ☀️ / 🌙 / 📓 / 🧠 and on an older API. */
  potential?: GgPotentialStrip | null;
  /** 📈 Track + 👀 watch line — the 🧠 sub only. */
  track?: GgTrack | null;
  watch?: GgWatch | null;
  /** The LIVE 🧠 push line, printed under the A+ `push` line (LIVE since 2026-10-16). */
  push_potential?: { mode?: string | null; text?: string | null } | null;
  /** 🔄 the served as-of / scanning line (every sub); absent on an older API. */
  scan?: GgScan | null;
  /** 🎯 the served A+ line (every sub); absent on an older API. */
  enterable?: GgEnterable | null;
  /** 🏁 the Track record — the track_record sub only; absent on another sub and on an older API. */
  track_record?: GgTrackRecord | null;
  /** 🚫 the owner's list block (tab.broker_block) — the primary owner only; null for anyone else, absent on an older API. */
  broker_flags?: GgBrokerFlags | null;
  /** 🚫 the served graveyard tag line (present iff graveyard_text) — owner only; null when no graveyard name is listed. */
  graveyard_broker_text?: string | null;
};

/** `?sub=` → a sub. null when ABSENT (so a `focus` deep link can let the
 *  server resolve it); an unknown value lands on the default sub. */
export function parseGgSub(raw: string | null | undefined): GgSub | null {
  if (raw == null) return null;
  const s = String(raw).trim().toLowerCase();
  if (!s) return null;
  return SUB_KEYS.has(s) ? (s as GgSub) : GG_DEFAULT_SUB;
}

/** `?tf=` → a frame in `allowed` (default GG_TFS — 🚩 Gajjala's 5m | 15m; the 1-minute board passes its served
 *  `variant.tfs`), else null. A value that is not a GgTf is null whatever `allowed` says. */
export function parseGgTf(raw: string | null | undefined, allowed: ReadonlyArray<string> = GG_TFS): GgTf | null {
  const s = (raw || '').trim().toLowerCase();
  return GG_TF_KEYS.has(s) && allowed.includes(s) ? (s as GgTf) : null;
}

/** The bar-size toggle's frames: the served `variant.tfs` (GgTf members only, served order) when the board serves a
 *  non-empty list, else GG_TFS. */
export function ggTfs(board: Pick<GgBoard, 'variant'> | null | undefined): ReadonlyArray<GgTf> {
  const served = board?.variant?.tfs;
  if (!Array.isArray(served)) return GG_TFS;
  const tfs = served.filter((t): t is GgTf => typeof t === 'string' && GG_TF_KEYS.has(t));
  return tfs.length ? tfs : GG_TFS;
}

/** The endpoint query. `sub` / `tf` / `focus` / `sort` / `span` ride only when
 *  set: an absent `sub` with a `focus` is how the server picks the sub a push
 *  meant (spec §3.4.1); an absent `span` is the server's default span. */
export function ggQuery(q: { sub?: GgSub | null; tf?: GgTf | null; focus?: string | null;
                             sort?: string | null; span?: string | null; limit?: number | null }): string {
  const p = new URLSearchParams();
  if (q.sub) p.set('sub', q.sub);
  if (q.tf) p.set('tf', q.tf);
  if (q.focus) p.set('focus', q.focus);
  if (q.sort) p.set('sort', q.sort);
  if (q.span) p.set(GG_SPAN_PARAM, q.span);
  if (typeof q.limit === 'number' && Number.isFinite(q.limit) && q.limit > 0) p.set('limit', String(Math.floor(q.limit)));
  return p.toString();
}

/** The re-read cadence the SERVER sets (`session.refresh_sec`, 300 inside the
 *  04:00–20:00 window, 0 when closed). null = no timer. */
export function ggRefreshMs(board: unknown): number | null {
  const s = (board as GgBoard | null | undefined)?.session?.refresh_sec;
  return typeof s === 'number' && Number.isFinite(s) && s > 0 ? s * 1000 : null;
}

/** A served chip's text, or null (nothing printed). Never "undefined". */
export function chipText(v: GgChipValue): string | null {
  if (typeof v === 'string') return v.trim() ? v : null;
  if (v && typeof v === 'object' && typeof v.text === 'string' && v.text.trim()) return v.text;
  return null;
}

/** "✓ label — value (need)"; `·` = not judgeable (an EMA still warming up). */
export function criteriaText(c: GgCriterion): string {
  const mark = c.ok === true ? '✓' : c.ok === false ? '✗' : '·';
  const value = typeof c.value === 'string' && c.value.trim() ? ` — ${c.value}` : '';
  const need = typeof c.need === 'string' && c.need.trim() ? ` (${c.need})` : '';
  return `${mark} ${c.label}${value}${need}`;
}

/** The served variant / grade label, else Ajay's word for the key; null when none. */
export function variantText(r: GgRead | null | undefined): string | null {
  if (!r) return null;
  if (typeof r.variant_label === 'string' && r.variant_label.trim()) return r.variant_label;
  return r.variant ? GG_VARIANT_LABEL[r.variant] ?? null : null;
}
export function gradeText(r: GgRead | null | undefined): string | null {
  if (!r) return null;
  if (typeof r.grade_label === 'string' && r.grade_label.trim()) return r.grade_label;
  return r.grade ? GG_GRADE_LABEL[r.grade] ?? null : null;
}

const fin = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

/** A served number printed, never computed: "+31.2%". null when not finite. */
export function changeText(v: unknown): string | null {
  if (typeof v === 'string') return v.trim() ? v : null;
  if (!fin(v)) return null;
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

/** "risk 4.2%" from the served `risk_pct`; null when not finite. */
export function riskText(v: unknown): string | null {
  return fin(v) ? `${v.toFixed(1)}%` : null;
}

/* 🚫 One price grid (2026-10-20, the MMA finding: an A+ push rang with the
 * stop printed at the trigger). The card prints a served trigger / stop the
 * way the push, the 🏁 Track record and the 🚩 lane print it — on the
 * broker's own grid: four decimals under the sub-dollar line, two at or over
 * it (backend/trading/broker_alpaca.py SUB_DOLLAR_LINE / SUB_DOLLAR_DECIMALS /
 * DOLLAR_DECIMALS, mirrored here and pinned by scripts/contracts.mjs "🚫
 * Gajjala no-risk A+ · one price grid (2026-10-20)"), half-up on the number's
 * own decimal text (the backend quantizes Decimal(repr(x)); String(x) is the
 * same shortest round-trip text), trailing zeros dropped under a dollar
 * ("0.31", "0.3101", "0.295"), two decimals always kept at or over ("4.46",
 * "1.00"). `null` for anything not a finite number — the caller drops the
 * item. The house pxText (three decimals under a dollar, the S&D card ladder)
 * is untouched: a different surface, HIS call. */
export const GG_PX_GRID = { line: 1.0, under: 4, atOrOver: 2 } as const;

function quantizeHalfUp(text: string, places: number): string {
  const [ip, fp = ''] = text.split('.');
  if (fp.length <= places) return `${ip}.${fp.padEnd(places, '0')}`;
  const digits = (ip + fp.slice(0, places)).split('').map((d) => d.charCodeAt(0) - 48);
  if (fp.charCodeAt(places) - 48 >= 5) {
    let i = digits.length - 1;
    while (i >= 0 && digits[i] === 9) { digits[i] = 0; i -= 1; }
    if (i < 0) digits.unshift(1); else digits[i] += 1;
  }
  const s = digits.join('');
  const cut = s.length - places;
  return `${s.slice(0, cut) || '0'}.${s.slice(cut)}`;
}

export function ggPx(p: unknown): string | null {
  if (typeof p !== 'number' || !Number.isFinite(p)) return null;
  const abs = Math.abs(p);
  const text = String(abs);
  if (/e/i.test(text)) return null;
  let places: number = abs < GG_PX_GRID.line ? GG_PX_GRID.under : GG_PX_GRID.atOrOver;
  let q = quantizeHalfUp(text, places);
  if (places === GG_PX_GRID.under && Number(q) >= GG_PX_GRID.line) {
    places = GG_PX_GRID.atOrOver;                       // a sub-dollar price that rounds onto the line re-grids at two
    q = quantizeHalfUp(q, places);
  }
  if (places === GG_PX_GRID.under) q = q.replace(/0+$/, '').replace(/\.$/, '') || '0';
  return `${p < 0 ? '-' : ''}${q}`;
}

/** A playbook item's text, timestamp tag ("S8 14:41") and status pill (the
 *  SERVED label, else the raw served code — never a guessed pill). */
export function playbookItem(it: GgPlaybookItem): { text: string; tag: string | null; pill: string | null } {
  if (typeof it === 'string') return { text: it, tag: null, pill: null };
  const tags: string[] = [];
  if (it.source || it.ts) tags.push([it.source, it.ts].filter(Boolean).join(' '));
  for (const s of it.sources || []) {
    const t = [s?.key, s?.ts].filter(Boolean).join(' ');
    if (t && !tags.includes(t)) tags.push(t);
  }
  const pill = (typeof it.status_label === 'string' && it.status_label.trim()) ? it.status_label
    : (typeof it.status === 'string' && it.status.trim()) ? it.status : null;
  return { text: it.text, tag: tags.length ? tags.join(' · ') : null, pill };
}

/** A served in-app link, or null — only a same-origin path ("/…", never "//…"). */
export function ggHref(v: unknown): string | null {
  return typeof v === 'string' && v.startsWith('/') && !v.startsWith('//') ? v : null;
}

/** The 👀 watch line split so its trailing served names become links: when the
 *  served text ends with ": " + the served symbols joined by ", ", `lead` is the
 *  text before them; else `lead` is the whole text (the names are not cut). */
export function watchParts(w: GgWatch | null | undefined): { lead: string; trailing: boolean } | null {
  if (!w || typeof w.text !== 'string' || !w.text.trim()) return null;
  const syms = (w.symbols || []).map((s) => s?.symbol).filter((s): s is string => typeof s === 'string' && !!s);
  const tail = syms.length ? `: ${syms.join(', ')}` : '';
  if (tail && w.text.endsWith(tail)) return { lead: `${w.text.slice(0, w.text.length - tail.length)}: `, trailing: true };
  return { lead: w.text, trailing: false };
}

/* ---- 🔄 scan on open + 🎯 A+ line (2026-10-15, BUILD_SPEC5 §3.6 / §3.8) — every string SERVED. ---- */
export const GG_SCAN_PATH = '/chart-maps/gajjala/scan';
export type GgScanState = 'scanning' | 'idle' | 'closed';
export type GgScan = {
  state: GgScanState | string;
  on_demand?: boolean;
  started_at_et?: string | null;
  bars_through_et?: string | null;
  as_of_text?: string | null;
  scanning_text?: string | null;
  text?: string | null;
  note?: string | null;
  rescan_label?: string | null;
  rescan_title?: string | null;
};
/** One 🎯 row — `text` is the whole served line (W16); the FE prints it as is. */
export type GgAplusRow = {
  symbol: string;
  setup: GgSetup | string;
  setup_label?: string | null;
  frame?: string | null;
  trigger?: number | null;
  stop?: number | null;
  risk_pct?: number | null;
  since_et?: string | null;
  variant_label?: string | null;
  grade_label?: string | null;
  href?: string | null;
  text: string;
  /** 🚫 the served tag — owner only; null / absent → no chip. */
  broker_text?: string | null;
  /** 📌 the served trader tag (trader_names.text_for) — every viewer; null / absent → no chip. */
  trader_text?: string | null;
};
export type GgEnterable = { title?: string | null; rows: GgAplusRow[]; empty_text?: string | null; note?: string | null };
export type GgScanResponse = {
  state: 'started' | 'reused' | 'waiting' | 'closed' | 'refused' | string;
  latest_at?: string | null;
  eta_sec?: number | null;
  poll_sec?: number | null;
  wait_max_sec?: number | null;
  text?: string | null;
};

const posFin = (x: unknown): x is number => fin(x) && x > 0;

/** The poll plan the SERVER sets: started / waiting with finite positive poll_sec + wait_max_sec → { firstMs =
 *  clamp(eta_sec ?? poll_sec, poll_sec, wait_max_sec) * 1000, everyMs = poll_sec * 1000, untilMs = wait_max_sec * 1000 };
 *  anything else (reused / closed / refused / a bad number) → null. Fractions allowed (tests serve small ones). */
export function ggScanPlan(r: GgScanResponse | null | undefined): { firstMs: number; everyMs: number; untilMs: number } | null {
  if (!r || (r.state !== 'started' && r.state !== 'waiting')) return null;
  const poll = r.poll_sec;
  const max = r.wait_max_sec;
  if (!posFin(poll) || !posFin(max) || max < poll) return null;
  const eta = r.eta_sec == null ? poll : r.eta_sec;
  if (!fin(eta)) return null;
  const first = Math.min(Math.max(eta, poll), max);
  return { firstMs: first * 1000, everyMs: poll * 1000, untilMs: max * 1000 };
}

/** The pass the POST waited for has landed: the served pass.at is a string, differs from the POST's latest_at, and no
 *  pass is running (scan.state !== 'scanning'). */
export function ggScanAdvanced(board: GgBoard | null | undefined, latestAt: string | null | undefined): boolean {
  const at = board?.pass?.at;
  if (typeof at !== 'string' || !at) return false;
  if (at === latestAt) return false;
  return board?.scan?.state !== 'scanning';
}

/* ---- 🚫 broker tag (2026-10-17, BUILD_SPEC12 §3.9, AMENDMENTS12 F2 / F5) — every word SERVED by tab.py. ---- */
/** The owner's add (POST {symbol}) / remove (DELETE /{symbol}) route — == the api route string (contracts check 7). */
export const GG_BROKER_PATH = '/chart-maps/gajjala/broker-flags';
/** tab.broker_block — `editable` false + `fault_text` when his list could not be read (F5: the add box hides, the
 *  served fault line shows; `empty_text` is never served then). */
export type GgBrokerFlags = {
  editable: boolean;
  symbols: string[];
  text: string;
  broker: string;
  toggle: string;
  empty_text?: string | null;
  add_label: string;
  add_placeholder: string;
  remove_title: string;
  fault_text?: string | null;
};
