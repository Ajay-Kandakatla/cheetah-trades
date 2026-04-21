type Props = {
  onClick: () => void;
  loading?: boolean;
  computedAt?: number | null;
};

function relTime(ts: number | null | undefined): string {
  if (!ts) return 'never';
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (secs < 10) return 'just now';
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

/** Rerun-formulas button for the Dashboard. */
export function RefreshButton({ onClick, loading, computedAt }: Props) {
  return (
    <div className="refresh-wrap">
      <button
        type="button"
        className="refresh-btn"
        onClick={onClick}
        disabled={loading}
      >
        {loading ? '↻ Running…' : '↻ Rerun formulas'}
      </button>
      <span className="refresh-ts muted small">
        Scored {relTime(computedAt)}
      </span>
    </div>
  );
}
