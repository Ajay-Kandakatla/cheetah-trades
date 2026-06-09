/* SepaCardSkeleton — layout-preserving placeholder for a SEPA candidate card.
 *
 * Rendered in the .sepa-grid while a scan cold-loads (or a setup tab is
 * fetching) so the money screen shows its shape immediately instead of a bare
 * "loading…" line, and the grid never reflows / jumps when real cards stream
 * in. Reuses .sepa-card so border/padding/radius match the real card exactly.
 * Styles live in styles/skeleton.css. (2026-06-09)
 */

function SepaCardSkeleton() {
  return (
    <div className="sepa-card sepa-card-skel" aria-hidden="true">
      <div className="sepa-card-skel__head">
        <div className="sepa-card-skel__sym">
          <div className="skel skel-line skel-line--lg" style={{ width: '42%' }} />
          <div className="skel skel-line skel-line--sm" style={{ width: '72%' }} />
        </div>
        <div className="sepa-card-skel__right">
          <div className="skel skel-bar" style={{ width: 116 }} />
          <div className="skel skel-line skel-line--sm" style={{ width: 64 }} />
        </div>
      </div>
      {/* score / RS bar */}
      <div className="skel skel-bar" style={{ width: '100%' }} />
      {/* chip strip */}
      <div className="sepa-card-skel__chips">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skel skel-pill" style={{ width: 46 + (i % 3) * 24 }} />
        ))}
      </div>
      {/* thesis lines */}
      <div className="skel skel-line" style={{ width: '92%' }} />
      <div className="skel skel-line skel-line--sm" style={{ width: '58%' }} />
    </div>
  );
}

/** A full grid of card skeletons matching the .sepa-grid layout. */
export function SepaCardGridSkeleton({ n = 6 }: { n?: number }) {
  return (
    <div className="sepa-grid" aria-busy="true" aria-label="Loading candidates">
      {Array.from({ length: n }).map((_, i) => (
        <SepaCardSkeleton key={i} />
      ))}
    </div>
  );
}
