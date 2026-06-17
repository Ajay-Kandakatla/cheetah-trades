/* useIsMobile — shared phone-viewport hook. Mirrors the matchMedia pattern the
 * rails already use (768px) so "mobile" means the same thing everywhere a
 * component needs to compact itself (e.g. BuyVerdictChip's pill). Re-evaluates
 * on viewport change. SSR/test-safe: defaults to desktop when matchMedia is
 * unavailable. */
import { useEffect, useState } from 'react';

export const MOBILE_MAX_WIDTH = 768;
const MQ = `(max-width: ${MOBILE_MAX_WIDTH}px)`;

function query(): boolean {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(MQ).matches;
}

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(query);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const m = window.matchMedia(MQ);
    const h = () => setIsMobile(m.matches);
    h();
    m.addEventListener('change', h);
    return () => m.removeEventListener('change', h);
  }, []);

  return isMobile;
}
