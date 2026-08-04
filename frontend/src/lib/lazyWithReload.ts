/* lazyWithReload — React.lazy + stale-chunk self-heal (extracted from
 * App.tsx 2026-08-03 after StockAnalysisPanel 404'd post-deploy).
 *
 * Every deploy rebuilds the hashed chunk map; a tab opened BEFORE the deploy
 * still asks for the old hashes and its dynamic imports 404. lazyWithReload
 * catches that and reloads ONCE to pull the fresh index.html + chunk map
 * (index.html is no-cache in nginx, so the reload gets the new build). A 10s
 * sessionStorage guard prevents a reload loop if the chunk is genuinely
 * missing (a truly broken deploy → surface the error instead of looping).
 *
 * HOUSE RULE: never use raw React.lazy for app code — always this wrapper.
 * (30 raw lazy() sites were converted when this module was extracted.) */
import { lazy, type ComponentType } from 'react';

export function lazyWithReload<T extends ComponentType<any>>(
  factory: () => Promise<{ default: T }>,
) {
  return lazy(async () => {
    try {
      return await factory();
    } catch (err) {
      const KEY = 'chunkReloadTs';
      const last = Number(sessionStorage.getItem(KEY) || '0');
      if (Date.now() - last > 10_000) {
        sessionStorage.setItem(KEY, String(Date.now()));
        window.location.reload();
        return new Promise<{ default: T }>(() => {}); // hang until reload swaps the page
      }
      throw err; // reloaded moments ago and still failing → real error
    }
  });
}
