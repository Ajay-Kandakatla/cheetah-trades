/* Shared skeleton loaders (Ajay 2026-06-16: "add skeleton loaders to the
 * Portfolio page and Leaderboard"). Reuses the .skel* primitives in
 * styles/skeleton.css (shimmer + reduced-motion fallback) so they match the
 * existing SEPA card skeletons. Layout-preserving so the page doesn't jump when
 * real data streams in.
 */

/** A compact list-board placeholder — for Leaderboard boards (ranked rows). */
export function ListSkeleton({ rows = 6, label }: { rows?: number; label?: string }) {
  return (
    <div aria-busy="true" aria-label={label || 'Loading'} style={{ marginTop: '0.5rem' }}>
      {label && <div className="skel skel-line skel-line--sm" style={{ width: 150, marginBottom: 10 }} />}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 4px' }}>
            <div className="skel skel-line skel-line--sm" style={{ width: 18 }} />
            <div className="skel skel-line" style={{ width: 64 }} />
            <div className="skel skel-pill" style={{ width: 54 }} />
            <div className="skel skel-line skel-line--sm" style={{ width: 100, marginLeft: 'auto' }} />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Holdings placeholder — for the Portfolio page (card-shaped rows). Reuses the
 *  .sepa-card-skel chrome so it lines up with the real holding cards. */
export function HoldingsSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading positions"
         style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: '0.8rem' }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="sepa-card sepa-card-skel" aria-hidden="true">
          <div className="sepa-card-skel__head">
            <div className="sepa-card-skel__sym">
              <div className="skel skel-line skel-line--lg" style={{ width: '38%' }} />
              <div className="skel skel-line skel-line--sm" style={{ width: '60%' }} />
            </div>
            <div className="sepa-card-skel__right">
              <div className="skel skel-bar" style={{ width: 110 }} />
              <div className="skel skel-line skel-line--sm" style={{ width: 64 }} />
            </div>
          </div>
          <div className="skel skel-bar" style={{ width: '100%' }} />
          <div className="sepa-card-skel__chips">
            {Array.from({ length: 4 }).map((_, j) => (
              <div key={j} className="skel skel-pill" style={{ width: 50 + (j % 2) * 26 }} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
