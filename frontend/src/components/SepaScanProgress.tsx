/**
 * SepaScanProgress — live progress UI for /sepa/scan/stream.
 *
 * Replaces the static "Scanning…" button label with a real-time view:
 *   - phase banner (loading universe / RS / scanning / enriching / writing)
 *   - progress bar with current/total + ETA
 *   - candidate counter that ticks up as hits are discovered
 *   - sliding window of recent tickers (last 12) with candidate highlighting
 *   - cache hits/misses for fast scans
 */
import { useMemo } from 'react';
import type { ScanStreamState } from '../hooks/useSepaScanStream';

function fmtDuration(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return '—';
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec - m * 60);
  return `${m}m ${s}s`;
}

function fmtTimeAgo(unixSec: number): string {
  const diff = Date.now() / 1000 - unixSec;
  if (diff < 1) return 'now';
  if (diff < 60) return `${Math.round(diff)}s ago`;
  return `${Math.round(diff / 60)}m ago`;
}

function PhasePill({ phase, label }: { phase: string; label: string }) {
  const cls = `sepa-progress__phase sepa-progress__phase--${phase}`;
  return <span className={cls}>{label}</span>;
}

export function SepaScanProgress(props: ScanStreamState) {
  const {
    phase, phaseMessage, current, total, analyzed, candidateCount,
    cacheHits, cacheMisses, candidates, activity, failures,
    retryCount, startedAt, finishedAt, error,
  } = props;

  const queuedFailures = failures.filter((f) => f.status === 'queued').length;
  const retryingFailures = failures.filter((f) => f.status === 'retrying').length;
  const permanentFailures = failures.filter((f) => f.status === 'permanent').length;
  const recoveredFailures = failures.filter((f) => f.status === 'recovered').length;

  const elapsed = useMemo(() => {
    if (!startedAt) return 0;
    const end = finishedAt ?? Date.now() / 1000;
    return end - startedAt;
  }, [startedAt, finishedAt]);

  const eta = useMemo(() => {
    if (!startedAt || current === 0 || total === 0 || phase !== 'scanning') return null;
    const rate = current / Math.max(elapsed, 0.1);    // tickers / sec
    const remaining = total - current;
    return remaining / Math.max(rate, 0.01);
  }, [startedAt, current, total, elapsed, phase]);

  const pct = total > 0 ? Math.min(100, (current / total) * 100) : 0;
  const isDone = phase === 'done';
  const isError = phase === 'error';

  return (
    <div className={`sepa-progress sepa-progress--${phase}`}>
      <div className="sepa-progress__head">
        <div className="sepa-progress__head-left">
          <PhasePill phase={phase} label={phaseLabel(phase)} />
          <span className="sepa-progress__msg mono">{phaseMessage || phaseLabel(phase)}</span>
        </div>
        <div className="sepa-progress__head-right mono">
          {isError ? (
            <span className="sepa-progress__error">⚠ {error}</span>
          ) : (
            <>
              <span>{fmtDuration(elapsed)} elapsed</span>
              {eta != null && !isDone && (
                <>
                  <span className="sepa-progress__sep">·</span>
                  <span>~{fmtDuration(eta)} left</span>
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="sepa-progress__bar-wrap">
        <div
          className={`sepa-progress__bar ${isDone ? 'is-done' : ''} ${isError ? 'is-error' : ''}`}
          style={{ width: `${isDone || isError ? 100 : pct}%` }}
        />
      </div>

      {/* Counters row */}
      <div className="sepa-progress__counters">
        <div className="sepa-progress__counter">
          <div className="eyebrow">Progress</div>
          <div className="mono sepa-progress__big">
            {total > 0 ? `${current} / ${total}` : '—'}
          </div>
        </div>
        <div className="sepa-progress__counter">
          <div className="eyebrow">Analyzed</div>
          <div className="mono sepa-progress__big">{analyzed}</div>
        </div>
        <div className="sepa-progress__counter">
          <div className="eyebrow">Candidates</div>
          <div className="mono sepa-progress__big sepa-progress__big--candidate">
            {candidateCount}
          </div>
        </div>
        {cacheHits != null && cacheMisses != null && (
          <div className="sepa-progress__counter">
            <div className="eyebrow">Cache hits</div>
            <div className="mono sepa-progress__big">
              {cacheHits} <span className="sepa-progress__sub">/{cacheMisses} miss</span>
            </div>
          </div>
        )}
        {failures.length > 0 && (
          <div className="sepa-progress__counter">
            <div className="eyebrow">Failures</div>
            <div className="mono sepa-progress__big sepa-progress__big--failure">
              {permanentFailures}
              <span className="sepa-progress__sub">
                {' '}{recoveredFailures} recovered · {retryingFailures + queuedFailures} pending
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Two columns: candidates discovered + activity log */}
      <div className="sepa-progress__cols">
        <div className="sepa-progress__col">
          <div className="eyebrow">Candidates discovered</div>
          {candidates.length === 0 ? (
            <div className="sepa-progress__empty">
              {phase === 'scanning' ? 'Watching for hits…' : 'None yet'}
            </div>
          ) : (
            <div className="sepa-progress__candidates">
              {candidates.slice(0, 8).map((c) => (
                <div key={`${c.symbol}-${c.ts}`} className="sepa-progress__hit">
                  <span className="mono sepa-progress__hit-sym">{c.symbol}</span>
                  <span className="mono sepa-progress__hit-score">{Math.round(c.score)}</span>
                  {c.rating && (
                    <span className={`sepa-progress__hit-rating sepa-progress__hit-rating--${c.rating.toLowerCase()}`}>
                      {c.rating.replace('_', ' ')}
                    </span>
                  )}
                  {c.rs_rank != null && (
                    <span className="mono sepa-progress__hit-rs">RS {c.rs_rank}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="sepa-progress__col">
          <div className="eyebrow">Recent activity</div>
          {activity.length === 0 ? (
            <div className="sepa-progress__empty">{activityWaitingMessage(phase)}</div>
          ) : (
            <div className="sepa-progress__activity">
              {activity.map((a) => (
                <div
                  key={`${a.symbol}-${a.ts}`}
                  className={`sepa-progress__activity-row ${a.is_candidate ? 'is-candidate' : ''}`}
                >
                  <span className="mono sepa-progress__activity-pos">
                    {a.current}/{a.total}
                  </span>
                  <span className="mono sepa-progress__activity-sym">{a.symbol}</span>
                  {a.is_candidate && <span className="sepa-progress__activity-tag">✓ candidate</span>}
                  <span className="sepa-progress__activity-time">{fmtTimeAgo(a.ts)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Failures + retry section — only renders when there are failures */}
      {failures.length > 0 && (
        <div className="sepa-progress__failures">
          <div className="sepa-progress__failures-head">
            <span className="eyebrow">Failures &amp; retries</span>
            <span className="mono sepa-progress__failures-summary">
              {permanentFailures} permanent · {recoveredFailures} recovered ·
              {' '}{retryingFailures} retrying · {queuedFailures} queued
              {retryCount > 0 && <> · {retryCount} retries fired</>}
            </span>
          </div>
          <div className="sepa-progress__failures-grid">
            {failures.slice(0, 24).map((f) => (
              <div
                key={f.symbol}
                className={`sepa-progress__failure sepa-progress__failure--${f.status}`}
                title={`${f.symbol} · attempt ${f.attempt} · ${f.error}`}
              >
                <div className="sepa-progress__failure-head">
                  <span className="mono sepa-progress__failure-sym">
                    {truncate(f.symbol, 18)}
                  </span>
                  <span className="sepa-progress__failure-status">
                    {failureStatusLabel(f.status)}
                  </span>
                </div>
                <div className="sepa-progress__failure-err mono">{truncate(f.error, 90)}</div>
              </div>
            ))}
            {failures.length > 24 && (
              <div className="sepa-progress__failure-more mono">
                +{failures.length - 24} more
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function activityWaitingMessage(phase: string): string {
  switch (phase) {
    case 'loading_universe': return 'Loading universe…';
    case 'rs':               return 'Computing Relative Strength ranks — ticker activity starts after this';
    case 'warming_names':    return 'Warming company-name cache — ticker activity starts after this';
    case 'scanning':         return 'Waiting for first ticker…';
    case 'retrying':         return 'Retrying failed tickers — see Failures section';
    case 'enriching':        return 'Enriching top candidates with catalyst + insider data';
    case 'market_context':   return 'Computing market regime…';
    case 'writing':          return 'Persisting scan results…';
    case 'done':             return 'Scan complete';
    case 'error':            return 'Scan failed — see error above';
    default:                 return 'Waiting…';
  }
}

function failureStatusLabel(s: string): string {
  switch (s) {
    case 'queued':    return 'queued for retry';
    case 'retrying':  return 'retrying…';
    case 'recovered': return '✓ recovered';
    case 'permanent': return '✗ permanent';
    default:          return s;
  }
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

function phaseLabel(phase: string): string {
  switch (phase) {
    case 'idle':             return 'Idle';
    case 'loading_universe': return 'Loading universe';
    case 'rs':               return 'RS ranks';
    case 'warming_names':    return 'Company names';
    case 'scanning':         return 'Scanning';
    case 'market_context':   return 'Market context';
    case 'enriching':        return 'Enriching';
    case 'writing':          return 'Persisting';
    case 'done':             return 'Done';
    case 'error':            return 'Error';
    default:                 return phase;
  }
}
