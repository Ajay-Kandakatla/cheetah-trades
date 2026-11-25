/* 🚫 2026-11-25 — the 🧠 Potential sub's served bottom section (spec fidsec §3.2, WP fe-section).
 *
 * Ajay 2026-11-25 ~10:25 ET, verbatim: "On the potential page move the no fidelity to the bottom segmented category.,"
 *
 * What is built: a header above his 🚫 cards. NOTHING MOVES — those cards have sat last since 2026-11-09 (tab.broker_bottom);
 * nothing is hidden by the server, no order key changes. The server serves ONE owner-only block `broker_flags.section` in
 * the 👀 Watch section shape ({key, title, text, hint, n, symbols} + `folded_default` only when true) and only on the subs
 * of its ONE gate (tab.BROKER_SECTION_SUBS); this file parses it with the Watch's own parser and holds NO sub list, NO
 * key list and NO word about a stock. The phone fold reuses the Watch's fold helpers (ggwFoldedKeys / ggwToggleFold) on
 * this board's own storage keys. Display only, UNMEASURED. */
import { ggwFoldedKeys, ggwToggleFold, parseGgwCollapsed, parseSections, type GgwSection } from './gajjalaWatch';

/** JSON list of served keys he folded on the phone (the `ggw.collapsed` format). */
export const GG_SECTION_COLLAPSED_LS = 'gg.section.collapsed';
/** JSON list of default-folded served keys he opened on the phone (the `ggw.opened` format). */
export const GG_SECTION_OPENED_LS = 'gg.section.opened';
export type GgSectionFold = { collapsed: string[]; opened: string[] };

/** The served section through the 👀 Watch parser (ONE engine); junk / no words / no symbol → null. Takes NO sub. */
export function parseGgBrokerSection(v: unknown): GgwSection | null {
  const s = parseSections([v])?.[0] ?? null;
  return s && s.symbols.length > 0 ? s : null;
}

/** Index of the first DRAWN card of the section; -1 when none is drawn OR when a drawn card after it is not in the
 *  section (the listed cards must be the tail — never label an unlisted card). */
export function ggBrokerSectionStart(drawn: ReadonlyArray<string>, sec: GgwSection | null): number {
  if (!sec || !sec.symbols.length) return -1;
  const at = drawn.findIndex((s) => sec.symbols.includes(s));
  if (at < 0) return -1;
  for (let i = at; i < drawn.length; i += 1) if (!sec.symbols.includes(drawn[i])) return -1;
  return at;
}

/** `head` inserted BEFORE index `at` as a sibling. `head` null / undefined, `at` < 0 or `at` > nodes.length → the SAME
 *  array object (today's children, untouched). Generic — no React import here. */
export function ggSectionSplice<T>(nodes: T[], at: number, head: T | null | undefined): T[] {
  if (head == null || !Number.isInteger(at) || at < 0 || at > nodes.length) return nodes;
  return [...nodes.slice(0, at), head, ...nodes.slice(at)];
}

/** window.localStorage in try/catch; junk / blocked → empty lists. */
export function readGgSectionFold(): GgSectionFold {
  const get = (k: string): string[] => {
    try { return parseGgwCollapsed(window.localStorage.getItem(k)); } catch { return []; }
  };
  return { collapsed: get(GG_SECTION_COLLAPSED_LS), opened: get(GG_SECTION_OPENED_LS) };
}

/** Empty list → removeItem; try/catch (a private window: the fold lasts this visit). */
export function saveGgSectionFold(st: GgSectionFold): void {
  const put = (k: string, keys: ReadonlyArray<string>) => {
    try {
      if (keys.length) window.localStorage.setItem(k, JSON.stringify(keys));
      else window.localStorage.removeItem(k);
    } catch { /* blocked storage: the fold lasts this visit */ }
  };
  put(GG_SECTION_COLLAPSED_LS, st.collapsed);
  put(GG_SECTION_OPENED_LS, st.opened);
}

/** phone && sec && the Watch's folded keys include it; desktop → always false. */
export function ggSectionFolded(sec: GgwSection | null, st: GgSectionFold, phone: boolean): boolean {
  return !!(phone && sec && ggwFoldedKeys([sec], st.collapsed, st.opened).includes(sec.key));
}

/** One header tap: the Watch's ggwToggleFold over this one section. */
export function ggSectionToggle(sec: GgwSection, st: GgSectionFold): GgSectionFold {
  return ggwToggleFold([sec], st, sec.key);
}
