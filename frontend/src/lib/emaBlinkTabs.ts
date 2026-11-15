/* 🔀 The tab-button dot feed (2026-11-15, ema-blink spec §3.8 / §3.9 WP-F). Ajay: "On All of the charts and also the
 * tabs I need a new blinker to show me EMA uptrends 9 crossing over 21 EMA please.." · "Or atleast closing in on other
 * tabs for me."
 *
 * ONE served count, `GET /chart-maps/ema-blink`, read by ONE page-level `setTimeout` chain (the 👀 Watch board's shape):
 * GET on mount, re-GET after the SERVED `refresh_sec` while the page is visible. `refresh_sec <= 0` (outside the pass
 * window / a closed day) → that one GET, no chain. A failed GET → no chain. Either way the next visibility change back
 * to the page re-GETs once — never a tight loop, never more than one request per `refresh_sec`.
 *
 * The server decides WHICH tabs carry a dot (the keys of `tabs`), the count `n`, the tier and the words; the FE lists
 * no tab, types no word and picks no tier (an unknown tier is no dot). Information only — UNMEASURED. */
import { useEffect, useState } from 'react';
import { API } from './apiBase';
import { EMA_BLINK_TIERS } from './emaBlink';

/** The route (== backend `GET /chart-maps/ema-blink`; contract-pinned by the main session). */
export const EMA_BLINK_TABS_PATH = '/chart-maps/ema-blink';

export type EmaBlinkTabTop = { symbol: string | null; tier: string | null; closeness: number | null };
export type EmaBlinkTab = {
  n: number;
  crossed_up: number | null;
  closing_in: number | null;
  tier: string | null;
  frame: string | null;
  top: EmaBlinkTabTop | null;
  text: string | null;
};
export type EmaBlinkTabs = {
  as_of: string | null;
  session: string | null;
  in_window: boolean;
  refresh_sec: number;
  info: string | null;
  n_means: string | null;
  tabs: Record<string, EmaBlinkTab | null>;
};

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
/* A served tier becomes a class name: only one of THE tiers (lib/emaBlink, == backend ema_cross.TIERS) passes. */
const isTier = (t: string) => (EMA_BLINK_TIERS as ReadonlyArray<string>).includes(t);

function parseTab(v: unknown): EmaBlinkTab | null {
  if (!isObj(v)) return null;
  const top = isObj(v.top)
    ? { symbol: str(v.top.symbol), tier: str(v.top.tier), closeness: num(v.top.closeness) }
    : null;
  const tier = str(v.tier);
  return {
    n: Math.max(0, num(v.n) ?? 0),
    crossed_up: num(v.crossed_up),
    closing_in: num(v.closing_in),
    tier: tier && isTier(tier) ? tier : null,
    frame: str(v.frame),
    top,
    text: str(v.text),
  };
}

/** The served payload → a typed feed, or null for junk. Unknown / malformed tab entries become null (no dot). */
export function parseEmaBlinkTabs(raw: unknown): EmaBlinkTabs | null {
  if (!isObj(raw)) return null;
  const tabs: Record<string, EmaBlinkTab | null> = {};
  if (isObj(raw.tabs)) for (const [k, v] of Object.entries(raw.tabs)) tabs[k] = parseTab(v);
  const rs = num(raw.refresh_sec);
  return {
    as_of: str(raw.as_of),
    session: str(raw.session),
    in_window: raw.in_window === true,
    refresh_sec: rs != null && rs > 0 ? rs : 0,
    info: str(raw.info),
    n_means: str(raw.n_means),
    tabs,
  };
}

/** The dot for one tab: only when the server named that tab with `n > 0` and a tier; else null. */
export function emaBlinkTabDot(feed: EmaBlinkTabs | null | undefined, tab: string)
  : { tier: string; text: string | null; n: number } | null {
  const d = feed?.tabs?.[tab];
  if (!d || !(d.n > 0) || !d.tier) return null;
  return { tier: d.tier, text: d.text, n: d.n };
}

const getFeed = () =>
  fetch(`${API}${EMA_BLINK_TABS_PATH}`, { credentials: 'include', cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))));

const visible = () => typeof document === 'undefined' || document.visibilityState !== 'hidden';

/** The page-level feed. `enabled` = the Chart Maps page is mounted (any tab — the dot pulls him to a tab he is NOT on).
 *  Keeps the last good feed through a failed GET. */
export function useEmaBlinkTabs(enabled: boolean): EmaBlinkTabs | null {
  const [feed, setFeed] = useState<EmaBlinkTabs | null>(null);

  useEffect(() => {
    if (!enabled) { setFeed(null); return undefined; }
    let alive = true;
    let inFlight = false;
    const timer: { current: ReturnType<typeof setTimeout> | null } = { current: null };
    const clear = () => { if (timer.current) { clearTimeout(timer.current); timer.current = null; } };
    const load = () => {
      if (!alive || inFlight) return;
      clear();
      inFlight = true;
      getFeed()
        .then((raw) => {
          inFlight = false;
          if (!alive) return;
          const p = parseEmaBlinkTabs(raw);
          if (!p) return;                        // junk → no chain (the next visibility change re-GETs)
          setFeed(p);
          if (p.refresh_sec > 0) {
            timer.current = setTimeout(() => {
              timer.current = null;
              if (visible()) load();             // hidden → the chain rests until the page is visible again
            }, p.refresh_sec * 1000);
          }
        })
        .catch(() => { inFlight = false; });   // failed → no chain, never a tight loop
    };
    /* Back to the page: re-GET once, only when nothing is armed or flying (a live chain keeps its own clock). */
    const onVis = () => { if (visible() && !timer.current && !inFlight) load(); };
    load();
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVis);
    return () => {
      alive = false;
      clear();
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVis);
    };
  }, [enabled]);

  return feed;
}
