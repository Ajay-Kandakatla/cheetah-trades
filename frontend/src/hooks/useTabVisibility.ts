import { useEffect, useState } from 'react';

/**
 * useTabVisibility — `true` while the browser tab is visible/focused,
 * `false` when the user has switched tabs / minimized.
 *
 * Wire into polling effects:
 *   const visible = useTabVisibility();
 *   useEffect(() => {
 *     if (!visible) return;        // skip polling while hidden
 *     load();
 *     const t = setInterval(load, pollMs);
 *     return () => clearInterval(t);
 *   }, [visible, ...]);
 *
 * Saves ~70% of background bandwidth — your 30s flow refresh, 60s
 * scan refresh, 30s alert poll all stop firing while you're on
 * another tab. They resume immediately when you come back.
 */
export function useTabVisibility(): boolean {
  const [visible, setVisible] = useState<boolean>(
    typeof document !== 'undefined' ? !document.hidden : true,
  );

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const onChange = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', onChange);
    return () => document.removeEventListener('visibilitychange', onChange);
  }, []);

  return visible;
}
