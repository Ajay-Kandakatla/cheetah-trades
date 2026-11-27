/* 📚 Playbook learning — the playbook videos' FE plumbing (2026-11-27, playbookvid spec §3.5, WP fe-core).
 *
 * Ajay 2026-11-27 ~02:15 ET, verbatim: "I loved the video can you move them under our replay tab with a PLaybook
 * learning and also add it to the playbook tab too with videos".
 *
 * The narrated setups film (his teaching charts) is published by a host script into videos/playbook/<film>/ and listed
 * by ONE owner-only GET (GET /chart-maps/replays/playbook, backend chart_maps/replays/playbook_api.py); its `<video>`
 * reads the owner-only playbook video route with Range requests. This module holds the route, the URL param, the two
 * mounts' settings, the payload TYPES (spec §3.4), the text / src guards and the URL helpers. Every word about a chapter
 * is SERVED; the FE types the two section titles, PBV_FETCH_FAILED, the ▶ glyph and three aria-labels. A study film:
 * hand-picked teaching charts, descriptive, UNMEASURED, not a signal. */
import { API } from './apiBase';

/** The listing route (== backend chart_maps/replays/constants.PLAYBOOK_API_PATH — contract-pinned). */
export const PBV_PATH = '/chart-maps/replays/playbook';
/** The URL param: `playbook=1` open · `playbook=0` closed · absent = the mount's default. */
export const PBV_PARAM = 'playbook';

export type PbvWhere = 'replays' | 'playbook';
/** The two mounts. 🎬 Replays: closed + lazy at the top of the board. 🚩 📓 Playbook: open, quiet (nothing at all until a
 *  film is listed). `replays.title` == backend constants.PLAYBOOK_TITLE (contract-pinned). */
export const PBV_WHERE: Record<PbvWhere, { title: string; defaultOpen: boolean; quiet: boolean }> = {
  replays: { title: '📚 Playbook learning', defaultOpen: false, quiet: false },
  playbook: { title: '🎬 Videos', defaultOpen: true, quiet: true },
};
/** The one FE sentence: the GET itself failed, so nothing was served. */
export const PBV_FETCH_FAILED = 'Could not load the playbook videos.';

// ── payload types (backend playbook.payload, spec §3.4) — every field optional but key / src ─────────────────────────

export type PbvVariant = {
  key: string; src: string; label?: string; file?: string; duration_s?: number; length_text?: string; bytes?: number;
  size_text?: string; height?: number | null; quality_text?: string | null;
};
export type PbvMarker = { start_s: number; text: string };
export type PbvChapter = {
  key: string; nn?: number; nn_text?: string; id?: string; title?: string; subtitle?: string | null;
  variants?: PbvVariant[];
};
export type PbvFull = {
  key: string; title?: string; subtitle?: string | null; variants?: PbvVariant[]; markers?: PbvMarker[];
};
export type PbvFilm = {
  slug: string; title?: string; description?: string | null; summary_text?: string; chapters?: PbvChapter[];
  full?: PbvFull | null;
};
export type PbvOption = { key: string; label: string };
export type PbvCounts = { films?: number; chapters?: number; videos?: number; skipped_bad?: number; no_sidecar?: number };
export type PbvPayload = {
  state: string; title?: string; tab?: string; text?: string | null; note?: string; variant_options?: PbvOption[];
  counts?: PbvCounts; films?: PbvFilm[];
};

// ── guards (pure) ───────────────────────────────────────────────────────────────────────────────────────────────────

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);

/** A served text: a string prints as itself; anything else prints nothing. */
export function pbvText(x: unknown): string {
  return typeof x === 'string' ? x : '';
}

/** The `<video>` src: API + the served `src`, ONLY when it is on the playbook video route. Anything else → ''. */
export function pbvSrc(v: { src?: unknown } | null | undefined): string {
  const src = v ? v.src : undefined;
  if (typeof src !== 'string' || !src.startsWith(`${PBV_PATH}/video/`)) return '';
  return `${API}${src}`;
}

/** The served variants that can play: a string key AND a playable src. Served order kept; junk → []. */
export function pbvVariants(x: unknown): PbvVariant[] {
  if (!Array.isArray(x)) return [];
  return x.filter((v): v is PbvVariant => isObj(v) && typeof v.key === 'string' && v.key.length > 0 && pbvSrc(v) !== '');
}

/** The variant that WILL play: the wanted key, else the first playable, else null. */
export function pbvPick(variants: unknown, want: string): PbvVariant | null {
  const vs = pbvVariants(variants);
  return vs.find((v) => v.key === want) || vs[0] || null;
}

/** The size a mount starts on: the phone copy under the house phone breakpoint (useIsMobile), else the 1080p copy. */
export function pbvDefaultVariant(isMobile: boolean): 'phone' | 'desktop' {
  return isMobile ? 'phone' : 'desktop';
}

/** The served size switch options: a string key + a string label each; junk → []. */
export function pbvOptions(x: unknown): PbvOption[] {
  if (!Array.isArray(x)) return [];
  return x.filter((o): o is PbvOption => isObj(o) && typeof o.key === 'string' && o.key.length > 0
    && typeof o.label === 'string' && o.label.length > 0);
}

/** The served chapter markers of the full film: a finite start_s >= 0 and a non-empty text; junk → []. */
export function pbvMarkers(x: unknown): PbvMarker[] {
  if (!Array.isArray(x)) return [];
  return x.filter((m): m is PbvMarker => isObj(m) && typeof m.start_s === 'number' && Number.isFinite(m.start_s)
    && m.start_s >= 0 && typeof m.text === 'string' && m.text.length > 0);
}

/** A served row (chapter or full) with a string key; junk → null. */
function pbvRow<T extends { key: string }>(x: unknown): T | null {
  return isObj(x) && typeof x.key === 'string' && x.key.length > 0 ? (x as unknown as T) : null;
}

/** The served films that hold at least one PLAYABLE row (a chapter or the full film), in served order. Each film keeps
 *  its served rows (junk rows dropped; a row with no playable variant stays, as text with no ▶). A film with a
 *  non-string slug is dropped. Junk → []. */
export function pbvFilms(x: unknown): PbvFilm[] {
  if (!Array.isArray(x)) return [];
  const out: PbvFilm[] = [];
  for (const f of x) {
    if (!isObj(f) || typeof f.slug !== 'string' || !f.slug) continue;
    const chapters = (Array.isArray(f.chapters) ? f.chapters : []).map((c) => pbvRow<PbvChapter>(c))
      .filter((c): c is PbvChapter => c !== null);
    const full = pbvRow<PbvFull>(f.full);
    const playable = chapters.some((c) => pbvVariants(c.variants).length > 0)
      || (full !== null && pbvVariants(full.variants).length > 0);
    if (playable) out.push({ ...(f as unknown as PbvFilm), chapters, full });
  }
  return out;
}

/** The section-wide key of one row: `${slug}/${key}`. */
export function pbvRowKey(slug: unknown, key: unknown): string {
  return `${pbvText(slug)}/${pbvText(key)}`;
}

/** Open or closed: `playbook=1` open, `playbook=0` closed, anything else → the mount's default. */
export function pbvOpen(params: URLSearchParams, defaultOpen: boolean): boolean {
  const v = params.get(PBV_PARAM);
  if (v === '1') return true;
  if (v === '0') return false;
  return defaultOpen;
}

/** The next URL params when the section opens / closes: a COPY of `prev`; the param is deleted when the new state equals
 *  the mount's default, else `1` / `0`. Every other param (`tab`, `date`, `winners`, `reel`, `sub`) rides along. Pure. */
export function pbvToggleParams(prev: URLSearchParams, open: boolean, defaultOpen: boolean): URLSearchParams {
  const next = new URLSearchParams(prev);
  if (open === defaultOpen) next.delete(PBV_PARAM);
  else next.set(PBV_PARAM, open ? '1' : '0');
  return next;
}
