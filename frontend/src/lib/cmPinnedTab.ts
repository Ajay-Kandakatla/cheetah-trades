/* cmPinnedTab — the Chart Maps tab strip stays pinned, keeps the active tab in
 * view, and a return from a ticker lands where he was.
 *
 * Ajay 2026-09-28: "Pin the tab I am in, as I navigate back and fort lost
 * where I am" (docs/chart_maps/pinned_tab_strip_2026_09_28.md).
 *
 * Pure helpers first (tested without a DOM), then storage (every access in
 * try/catch — Safari private mode throws), then plain-DOM adapters. Nothing
 * here calls scrollIntoView: it scrolls every scroll ancestor, including the
 * window, so an off-screen strip would drag the page vertically. Only the
 * strip's own scrollLeft moves when the active tab is revealed. */

export const CM_TABS_H_VAR = '--cm-tabs-h';
export const CM_TABS_SB_VAR = '--cm-tabs-sb';        // the strip's own horizontal scrollbar height (0 with overlay scrollbars)
export const CM_TABS_FADE_PX = 26;                  // == .cm-tabs-fade width in styles.css
export const CM_SCROLL_KEY = 'cm_scroll_pos_v1';
export const CM_SCROLL_MAX_AGE_MS = 30 * 60 * 1000;  // HIS CALL #3 default
export const CM_RESTORE_DEADLINE_MS = 15_000;        // give up quietly; never jump late
export const CM_PAGE_PATH = '/chart-maps';          // == navSource.ts NAV_SOURCES['chart-maps'].path
export const CM_TICKER_PATH_RE = /^\/sepa\/[^/?#]+/; // the ticker route, App.tsx '/sepa/:symbol'

export type StripBox = { scrollLeft: number; clientWidth: number; scrollWidth: number };
export type CmScrollRec = { v: 1; tab: string; y: number; t: number; src: 'leave' | 'hide'; sym?: string; dy?: number };
export type LeaveAction = 'keep' | 'snapshot' | 'drop';
type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

const SYM_RE = /^[A-Za-z0-9.\-^=]{1,15}$/;

/** sessionStorage, read lazily (so a test's vi.stubGlobal is honoured) and
 *  never throwing — a blocked store is simply "no store". */
export function sessionStore(): Store | null {
  try { return (globalThis as { sessionStorage?: Store }).sessionStorage ?? null; } catch { return null; }
}

// ── pure ────────────────────────────────────────────────────────────────────

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

/** The strip scrollLeft that brings the tab into view (centred), or null when
 *  it is already fully visible — an already-visible tab never moves. A tab
 *  under an edge fade (while more tabs exist past that edge) counts as hidden. */
export function revealLeft(s: StripBox, tab: { left: number; width: number }, pad = CM_TABS_FADE_PX): number | null {
  if (!(s.clientWidth > 0) || !(tab.width > 0)) return null;
  const max = Math.max(0, s.scrollWidth - s.clientWidth);
  const visL = s.scrollLeft + (s.scrollLeft > 0 ? pad : 0);
  const visR = s.scrollLeft + s.clientWidth - (s.scrollLeft < max ? pad : 0);
  if (tab.left >= visL && tab.left + tab.width <= visR) return null;
  const x = Math.round(clamp(tab.left - (s.clientWidth - tab.width) / 2, 0, max));
  return x === Math.round(s.scrollLeft) ? null : x;
}

/** Which edges hide more tabs (drives the ‹ › fades). */
export function stripEdges(s: StripBox): { l: boolean; r: boolean } {
  return { l: s.scrollLeft > 1, r: s.scrollLeft + s.clientWidth < s.scrollWidth - 1 };
}

/** A classic horizontal scrollbar's height; 0 with overlay scrollbars. */
export function scrollbarPx(offsetHeight: number, clientHeight: number, borderPx: number): number {
  const v = offsetHeight - clientHeight - borderPx;
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.round(v));
}

/** Where to scroll so a freshly switched tab opens at its top, right under the
 *  pinned strip — or null when he is not below that point (nothing moves). */
export function boardTopScrollY(sentinelTop: number, scrollY: number, navTop: number): number | null {
  const natural = sentinelTop + scrollY - navTop;
  return scrollY > natural + 1 ? Math.max(0, Math.round(natural)) : null;
}

/** The ticker a tile links to (`/sepa/SYM?…`), or null. */
export function tileSymbolFromHref(href: string | null | undefined): string | null {
  if (!href) return null;
  const m = /^\/sepa\/([^/?#]+)/.exec(href);
  if (!m) return null;
  try { return decodeURIComponent(m[1]); } catch { return null; }
}

/** The first tile (DOM order) with a symbol whose bottom is below the edge. */
export function firstVisibleTile(
  tiles: { sym: string | null; top: number; bottom: number }[], edge: number,
): { sym: string; dy: number } | null {
  for (const t of tiles) {
    if (t.sym && t.bottom > edge + 1) return { sym: t.sym, dy: Math.round(t.top) };
  }
  return null;
}

/** What an in-app unmount does with the record, by the route being left for:
 *  - a ticker page → keep a pending restore, else snapshot (← Back / ◀ returns);
 *  - Chart Maps itself (StrictMode's dev double mount) → write back a pending
 *    restore, NEVER snapshot (the dev mount's transient scrollY is no place he chose);
 *  - anything else (menu to /sepa, /portfolio, …) → drop. */
export function leaveAction(destPath: string, hasPending: boolean): LeaveAction {
  if (CM_TICKER_PATH_RE.test(destPath)) return hasPending ? 'keep' : 'snapshot';
  if (destPath === CM_PAGE_PATH) return hasPending ? 'keep' : 'drop';
  return 'drop';
}

// ── storage ─────────────────────────────────────────────────────────────────

export function saveCmScroll(rec: CmScrollRec | null, store: Store | null = sessionStore()): void {
  if (!store) return;
  try {
    if (!rec || !(rec.y > 0)) store.removeItem(CM_SCROLL_KEY);
    else store.setItem(CM_SCROLL_KEY, JSON.stringify(rec));
  } catch { /* blocked store — no memory, no error */ }
}

/** One-shot: the record is removed whether or not it matches. */
export function takeCmScroll(tab: string, now = Date.now(), store: Store | null = sessionStore()): CmScrollRec | null {
  if (!store) return null;
  let raw: string | null = null;
  try { raw = store.getItem(CM_SCROLL_KEY); } catch { raw = null; }
  try { store.removeItem(CM_SCROLL_KEY); } catch { /* blocked */ }
  if (!raw) return null;
  let r: Record<string, unknown>;
  try { r = JSON.parse(raw); } catch { return null; }
  if (!r || typeof r !== 'object') return null;
  if (r.v !== 1 || typeof r.tab !== 'string') return null;
  const y = r.y, t = r.t;
  if (typeof y !== 'number' || !Number.isFinite(y) || !(y > 0)) return null;
  if (typeof t !== 'number' || !Number.isFinite(t)) return null;
  if (r.tab !== tab) return null;
  const age = now - t;
  if (age < 0 || age > CM_SCROLL_MAX_AGE_MS) return null;
  const out: CmScrollRec = { v: 1, tab: r.tab, y, t, src: r.src === 'hide' ? 'hide' : 'leave' };
  if (typeof r.sym === 'string' && SYM_RE.test(r.sym)) out.sym = r.sym;
  if (typeof r.dy === 'number' && Number.isFinite(r.dy)) out.dy = r.dy;
  return out;
}

/** Visible again → a hide record is spent. A leave record is kept. */
export function clearHideRec(store: Store | null = sessionStore()): void {
  if (!store) return;
  try {
    const raw = store.getItem(CM_SCROLL_KEY);
    if (!raw) return;
    let src: unknown = null;
    try { src = (JSON.parse(raw) as { src?: unknown })?.src; } catch { return; }
    if (src === 'hide') store.removeItem(CM_SCROLL_KEY);
  } catch { /* blocked */ }
}

// ── DOM adapters ────────────────────────────────────────────────────────────

export function stripOf(bar: HTMLElement | null): HTMLElement | null {
  return bar?.querySelector<HTMLElement>('.cm-tabs') ?? null;
}

export function readStripBox(strip: HTMLElement): StripBox {
  return { scrollLeft: strip.scrollLeft, clientWidth: strip.clientWidth, scrollWidth: strip.scrollWidth };
}

export function stripScrollbarPx(strip: HTMLElement): number {
  let border = 0;
  try {
    const cs = getComputedStyle(strip);
    border = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
  } catch { border = 0; }
  return scrollbarPx(strip.offsetHeight, strip.clientHeight, border);
}

/** Moves ONLY strip.scrollLeft. Never scrollIntoView, focus or window.scrollTo. */
export function revealActiveTab(strip: HTMLElement | null): boolean {
  if (!strip) return false;
  const el = strip.querySelector<HTMLElement>('.cm-tab-on');
  if (!el) return false;
  const sr = strip.getBoundingClientRect();
  const er = el.getBoundingClientRect();
  const x = revealLeft(readStripBox(strip), { left: er.left - sr.left + strip.scrollLeft, width: er.width });
  if (x == null) return false;
  strip.scrollLeft = x;
  return true;
}

const gridTiles = (page: HTMLElement | null): HTMLAnchorElement[] => {
  const grid = page?.querySelector('.cm-grid');
  if (!grid) return [];
  return Array.from(grid.children).filter((c): c is HTMLAnchorElement => c.tagName === 'A');
};

export function snapshotCmScroll(
  page: HTMLElement | null, bar: HTMLElement | null, tab: string, src: 'leave' | 'hide', now = Date.now(),
): CmScrollRec | null {
  const y = Math.round(window.scrollY);
  if (!(y > 0)) return null;
  const edge = bar ? bar.getBoundingClientRect().bottom : 0;
  const tiles = gridTiles(page).map((a) => {
    const r = a.getBoundingClientRect();
    return { sym: tileSymbolFromHref(a.getAttribute('href')), top: r.top, bottom: r.bottom };
  });
  const anchor = firstVisibleTile(tiles, edge);
  return { v: 1, tab, y, t: now, src, ...(anchor ? { sym: anchor.sym, dy: anchor.dy } : {}) };
}

/** Anchor tile first (the board re-orders), raw y as the fallback; false when
 *  the page is not tall enough yet. */
export function restoreCmScroll(page: HTMLElement | null, rec: CmScrollRec): boolean {
  if (rec.sym) {
    const a = gridTiles(page).find((el) => tileSymbolFromHref(el.getAttribute('href')) === rec.sym);
    if (a) {
      const top = Math.max(0, Math.round(a.getBoundingClientRect().top + window.scrollY - (rec.dy ?? 0)));
      window.scrollTo({ top, left: 0, behavior: 'auto' });
      return true;
    }
  }
  if (document.documentElement.scrollHeight - window.innerHeight >= rec.y) {
    window.scrollTo({ top: rec.y, left: 0, behavior: 'auto' });
    return true;
  }
  return false;
}
