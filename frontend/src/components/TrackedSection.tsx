/* TrackedSection — records a one-shot usage event when a page section actually
 * scrolls into view (Ajay 2026-06-16: "add section tracking first" so a real
 * usage-driven reorg of Portfolio/Leaderboard becomes possible once data
 * accrues). Fires `section:<name>` via trackFeature when the section is ≥40%
 * visible AND has real height — so empty/null boards don't pollute the signal.
 * One event per mount; the wrapper div is layout-neutral (no margin/padding).
 */
import { useEffect, useRef } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { trackFeature } from '../lib/usageTracker';

export function TrackedSection({ name, children, style }: {
  name: string;
  children: ReactNode;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const fired = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!fired.current && e.isIntersecting && e.intersectionRatio >= 0.4
            && e.boundingClientRect.height > 24) {
          fired.current = true;
          trackFeature(`section:${name}`);
          io.disconnect();
          break;
        }
      }
    }, { threshold: [0.4] });
    io.observe(el);
    return () => io.disconnect();
  }, [name]);

  return <div ref={ref} data-section={name} style={style}>{children}</div>;
}
