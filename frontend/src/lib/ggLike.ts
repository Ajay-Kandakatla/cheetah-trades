/* 🧘 GG-like calm check — the frontend half (2026-11-27, spec gglike §3.9, WP fe-core).
 *
 * Ajay 2026-11-27: "find calmer and better setups.. I want to make sure we are finding similar setups to Gajjala".
 *
 * The server judges every card against the ranges read off GG's own example charts and serves the WORDS (chip, title,
 * check rows, the board's filter / count / note sentences). This file only parses those blocks strictly, splits a card
 * list for the per-device 🚩 display filter, and fills the served templates with counts. It types no served word.
 * Display only: nothing rings, gates or reorders. UNMEASURED. */

export type GgLikeVerdict = 'gg_like' | 'not' | 'unknown';
export type GgLikeCheck = { key: string; ok: boolean | null; info: boolean; mark: string; label: string; value: string | null; need: string | null };
export type GgLike = {
  verdict: GgLikeVerdict; tone: string; chip: string; title: string | null;
  /** `label` is the card's own short (it carries the card's number, e.g. "23% under high"); `count_label` is the
   *  served per-code label with no card number — the hidden-count key when the server sends it. */
  reason: { code: string; label: string; count_label?: string | null } | null;
  keep: boolean; checks: GgLikeCheck[]; info: string | null; source: string | null; source_text: string | null;
};
export type GgLikeBoard = {
  label: string; label_n_text: string | null; hint: string | null; hidden_text: string; reason_text: string;
  kept_text: string; unknown_text: string; none_text: string; all_hidden_text: string | null; show_all_text: string;
  note: string | null; separation_text: string | null; census_text: string | null; rows: string[];
};
export type GgLikeSplit<T> = {
  visible: T[]; hidden: number; kept: number; like: number;
  reasons: { code: string; label: string; n: number }[]; unknown: number; none: number;
};

export const GG_LIKE_VERDICTS: readonly GgLikeVerdict[] = Object.freeze(['gg_like', 'not', 'unknown'] as GgLikeVerdict[]);
/** The served tones (class-name suffixes only). A tone outside this set draws the muted look. */
export const GG_LIKE_TONES: readonly string[] = Object.freeze(['ok', 'no', 'unknown']);

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const str = (x: unknown): string | null => (typeof x === 'string' ? x : null);
const text = (x: unknown): string | null => (typeof x === 'string' && x.trim() ? x : null);

function parseCheck(x: unknown): GgLikeCheck | null {
  if (!isObj(x)) return null;
  const key = text(x.key);
  const label = text(x.label);
  if (!key || !label) return null;
  if (x.ok !== true && x.ok !== false && x.ok !== null) return null;
  return {
    key, label,
    ok: x.ok as boolean | null,
    info: x.info === true,
    mark: str(x.mark) ?? '',
    value: str(x.value),
    need: str(x.need),
  };
}

/** Strict: a non-object, a verdict outside GG_LIKE_VERDICTS or a missing / blank chip → null (a null card is never
 *  hidden). `keep` is true only for a literal `true`; malformed check rows are dropped, never guessed. */
export function parseGgLike(x: unknown): GgLike | null {
  if (!isObj(x)) return null;
  const verdict = x.verdict;
  if (typeof verdict !== 'string' || !(GG_LIKE_VERDICTS as readonly string[]).includes(verdict)) return null;
  const chip = text(x.chip);
  if (!chip) return null;
  const tone = typeof x.tone === 'string' && GG_LIKE_TONES.includes(x.tone) ? x.tone : 'unknown';
  let reason: GgLike['reason'] = null;
  if (isObj(x.reason)) {
    const code = text(x.reason.code);
    const label = text(x.reason.label);
    if (code && label) reason = { code, label, count_label: text(x.reason.count_label) };
  }
  const checks = Array.isArray(x.checks)
    ? x.checks.map(parseCheck).filter((c): c is GgLikeCheck => c !== null)
    : [];
  return {
    verdict: verdict as GgLikeVerdict, tone, chip,
    title: text(x.title), reason,
    keep: x.keep === true,
    checks,
    info: text(x.info),
    source: text(x.source),
    source_text: text(x.source_text),
  };
}

/** Strict: a non-blank label and every count template a string, else null (the toggle is then not drawn). */
export function parseGgLikeBoard(x: unknown): GgLikeBoard | null {
  if (!isObj(x)) return null;
  const label = text(x.label);
  if (!label) return null;
  const req = ['hidden_text', 'reason_text', 'kept_text', 'unknown_text', 'none_text', 'show_all_text'] as const;
  for (const k of req) if (typeof x[k] !== 'string') return null;
  return {
    label,
    label_n_text: text(x.label_n_text),
    hint: text(x.hint),
    hidden_text: x.hidden_text as string,
    reason_text: x.reason_text as string,
    kept_text: x.kept_text as string,
    unknown_text: x.unknown_text as string,
    none_text: x.none_text as string,
    all_hidden_text: text(x.all_hidden_text),
    show_all_text: x.show_all_text as string,
    note: text(x.note),
    separation_text: text(x.separation_text),
    census_text: text(x.census_text),
    rows: Array.isArray(x.rows) ? x.rows.filter((r): r is string => typeof r === 'string' && !!r.trim()) : [],
  };
}

/** OFF → every row in place, zero counts (`like` still counted). ON → a row leaves ONLY when its verdict is 'not' AND it
 *  is not served `keep: true` AND the `keep` callback (the ?focus= name) does not return true. 'gg_like', 'unknown',
 *  kept ✗ rows and rows with no parsed block stay IN PLACE (never reordered). `kept` = the ✗ rows kept; `reasons` counts
 *  the HIDDEN rows by reason code under the served `count_label` (no card number), most first, ties by label. A row
 *  whose reason has no `count_label` is grouped by its exact served label instead — a group only ever holds rows that
 *  were served the label it prints (refix 2026-11-27: "3 23% under high" over cards 23% / 51% / 16% lied). */
export function ggLikeSplit<T>(rows: readonly T[], of: (row: T) => GgLike | null, on: boolean,
                               keep?: (row: T) => boolean): GgLikeSplit<T> {
  const out: GgLikeSplit<T> = { visible: [], hidden: 0, kept: 0, like: 0, reasons: [], unknown: 0, none: 0 };
  const byCode = new Map<string, { code: string; label: string; n: number }>();
  for (const row of rows) {
    const l = of(row);
    if (l?.verdict === 'gg_like') out.like += 1;
    if (!on) { out.visible.push(row); continue; }
    if (!l) { out.none += 1; out.visible.push(row); continue; }
    if (l.verdict === 'unknown') { out.unknown += 1; out.visible.push(row); continue; }
    if (l.verdict !== 'not') { out.visible.push(row); continue; }
    if (l.keep === true || keep?.(row) === true) { out.kept += 1; out.visible.push(row); continue; }
    out.hidden += 1;
    if (l.reason) {
      const label = l.reason.count_label ?? l.reason.label;
      const key = `${l.reason.code}\u0000${label}`;
      const r = byCode.get(key);
      if (r) r.n += 1;
      else byCode.set(key, { code: l.reason.code, label, n: 1 });
    }
  }
  out.reasons = [...byCode.values()].sort((a, b) => (b.n - a.n) || (a.label < b.label ? -1 : a.label > b.label ? 1 : 0));
  return out;
}

/** The toggle's n: the rows whose parsed verdict is 'gg_like'. */
export function ggLikeCount<T>(rows: readonly T[], of: (row: T) => GgLike | null): number {
  let n = 0;
  for (const row of rows) if (of(row)?.verdict === 'gg_like') n += 1;
  return n;
}

function fill(tpl: string, vals: Record<string, string | number>): string {
  let s = tpl;
  for (const [k, v] of Object.entries(vals)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

/** The served label_n_text with {label} and {n} filled; a missing template → the served label. */
export function ggLikeLabel(b: GgLikeBoard, n: number): string {
  return b.label_n_text ? fill(b.label_n_text, { label: b.label, n }) : b.label;
}

/** The count line from the served templates; every zero part is dropped. When every row is hidden (nothing visible,
 *  something hidden) the line STARTS with the served all_hidden_text. Nothing to say → ''. */
export function ggLikeLine(b: GgLikeBoard, s: GgLikeSplit<unknown>): string {
  const parts: string[] = [];
  if (s.visible.length === 0 && s.hidden > 0 && b.all_hidden_text) parts.push(b.all_hidden_text);
  if (s.hidden > 0) {
    const why = s.reasons.filter((r) => r.n > 0).map((r) => fill(b.reason_text, { n: r.n, label: r.label }));
    parts.push(fill(b.hidden_text, { n: s.hidden }) + (why.length ? ` (${why.join(' · ')})` : ''));
  }
  if (s.kept > 0) parts.push(fill(b.kept_text, { n: s.kept }));
  if (s.unknown > 0) parts.push(fill(b.unknown_text, { n: s.unknown }));
  if (s.none > 0) parts.push(fill(b.none_text, { n: s.none }));
  return parts.join(' · ');
}

/** ONE key — the 🚩 board only. There is no 👀 Watch filter (spec C1 / C7). */
export const GG_LIKE_LS = Object.freeze({ board: 'gg-like-only:board' } as const);

/** Per-device convenience: '1' = ON; anything else, or blocked storage, = OFF. */
export function loadGgLikeOnly(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === '1';
  } catch {
    return false;
  }
}
export function saveGgLikeOnly(key: string, on: boolean): void {
  try {
    window.localStorage.setItem(key, on ? '1' : '0');
  } catch {
    /* losing it must cost nothing */
  }
}
