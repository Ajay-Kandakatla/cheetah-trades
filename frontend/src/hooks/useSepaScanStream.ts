import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';


export type CandidateHit = {
  symbol: string;
  score: number;
  rating?: string;
  rs_rank?: number;
  ts: number;
};

export type ActivityRow = {
  ts: number;
  symbol: string;
  current: number;
  total: number;
  is_candidate: boolean;
};

export type FailureStatus = 'queued' | 'retrying' | 'recovered' | 'permanent';

export type FailureRow = {
  symbol: string;
  error: string;
  attempt: number;
  status: FailureStatus;
  ts: number;
};

export type ScanPhase =
  | 'idle'
  | 'loading_universe'
  | 'rs'
  | 'warming_names'
  | 'scanning'
  | 'market_context'
  | 'enriching'
  | 'retrying'
  | 'writing'
  | 'done'
  | 'error';

export type ScanStreamState = {
  scanning: boolean;
  phase: ScanPhase;
  phaseMessage: string;
  current: number;
  total: number;
  analyzed: number;
  candidateCount: number;
  cacheHits: number | null;
  cacheMisses: number | null;
  candidates: CandidateHit[];      // running list of hits
  activity: ActivityRow[];         // sliding window of recent tickers
  failures: FailureRow[];          // every symbol that failed, by status
  retryCount: number;              // total retry attempts fired
  recoveredCount: number;          // succeeded on retry
  startedAt: number | null;
  finishedAt: number | null;
  result: any | null;
  error: string | null;
};

const INITIAL: ScanStreamState = {
  scanning: false,
  phase: 'idle',
  phaseMessage: '',
  current: 0,
  total: 0,
  analyzed: 0,
  candidateCount: 0,
  cacheHits: null,
  cacheMisses: null,
  candidates: [],
  activity: [],
  failures: [],
  retryCount: 0,
  recoveredCount: 0,
  startedAt: null,
  finishedAt: null,
  result: null,
  error: null,
};

const ACTIVITY_WINDOW = 12;  // last N tickers shown in the live log

export function useSepaScanStream() {
  const [state, setState] = useState<ScanStreamState>(INITIAL);
  const sourceRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  // Always close on unmount
  useEffect(() => () => close(), [close]);

  const start = useCallback((opts: {
    fast?: boolean;
    mode?: string;
    with_catalyst?: boolean;
  } = {}) => {
    close();
    const params = new URLSearchParams();
    if (opts.fast) params.set('fast', 'true');
    if (opts.mode) params.set('mode', opts.mode);
    if (opts.with_catalyst) params.set('with_catalyst', 'true');

    const url = `${API}/sepa/scan/stream?${params.toString()}`;
    const es = new EventSource(url);
    sourceRef.current = es;

    setState({
      ...INITIAL,
      scanning: true,
      phase: 'loading_universe',
      phaseMessage: 'Connecting…',
      startedAt: Date.now() / 1000,
    });

    es.addEventListener('phase', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          phase: p.phase,
          phaseMessage: p.message || phaseLabel(p.phase),
          total: p.total ?? s.total,
        }));
      } catch {}
    });

    es.addEventListener('ticker', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => {
          const row: ActivityRow = {
            ts: p.ts,
            symbol: p.symbol,
            current: p.current,
            total: p.total,
            is_candidate: false,  // candidates fire their own event before the ticker event
          };
          const activity = [row, ...s.activity].slice(0, ACTIVITY_WINDOW);
          return {
            ...s,
            current: p.current,
            total: p.total,
            analyzed: p.analyzed ?? s.analyzed,
            candidateCount: p.candidate_count ?? s.candidateCount,
            cacheHits: p.cache_hits ?? s.cacheHits,
            cacheMisses: p.cache_misses ?? s.cacheMisses,
            activity,
          };
        });
      } catch {}
    });

    es.addEventListener('candidate', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => {
          const hit: CandidateHit = {
            symbol: p.symbol,
            score: p.score,
            rating: p.rating,
            rs_rank: p.rs_rank,
            ts: p.ts,
          };
          // Tag the most recent activity row as a candidate if it matches
          const activity = s.activity.map((r, i) =>
            i === 0 && r.symbol === p.symbol ? { ...r, is_candidate: true } : r,
          );
          return { ...s, candidates: [hit, ...s.candidates], activity };
        });
      } catch {}
    });

    es.addEventListener('rs_progress', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          current: p.current,
          total: p.total,
          phaseMessage: `RS ranks · ${p.current}/${p.total} priced (${p.scored} scored)`,
        }));
      } catch {}
    });

    es.addEventListener('name_progress', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          current: p.current,
          total: p.total,
          phaseMessage: `Company names · ${p.current}/${p.total} fetched`,
        }));
      } catch {}
    });

    es.addEventListener('failure', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => {
          const idx = s.failures.findIndex((f) => f.symbol === p.symbol);
          const status: FailureStatus = p.will_retry ? 'queued' : 'permanent';
          const row: FailureRow = {
            symbol: p.symbol,
            error: p.error || 'unknown',
            attempt: p.attempt || 1,
            status,
            ts: p.ts,
          };
          let failures: FailureRow[];
          if (idx >= 0) {
            failures = s.failures.map((f, i) => i === idx ? row : f);
          } else {
            failures = [row, ...s.failures];
          }
          return { ...s, failures };
        });
      } catch {}
    });

    es.addEventListener('retry', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => {
          const failures = s.failures.map((f) =>
            f.symbol === p.symbol ? { ...f, status: 'retrying' as FailureStatus, attempt: p.attempt } : f,
          );
          return {
            ...s,
            failures,
            retryCount: s.retryCount + 1,
            phaseMessage: `Retrying ${p.symbol} (${p.current}/${p.total})`,
          };
        });
      } catch {}
    });

    es.addEventListener('recovered', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => {
          const failures = s.failures.map((f) =>
            f.symbol === p.symbol ? { ...f, status: 'recovered' as FailureStatus } : f,
          );
          return { ...s, failures, recoveredCount: s.recoveredCount + 1 };
        });
      } catch {}
    });

    es.addEventListener('enrich', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          current: p.current,
          total: p.total,
          phaseMessage: `Enriching ${p.symbol} (${p.current}/${p.total})`,
        }));
      } catch {}
    });

    es.addEventListener('log', (e: MessageEvent) => {
      // Freeform info/warn — could surface in a debug panel later. For now, console only.
      try {
        const p = JSON.parse(e.data);
        // eslint-disable-next-line no-console
        console.log(`[scan/${p.level || 'info'}]`, p.message);
      } catch {}
    });

    es.addEventListener('done', (e: MessageEvent) => {
      try {
        const p = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          scanning: false,
          phase: 'done',
          phaseMessage: `Scan complete · ${p.result?.candidate_count ?? 0} candidates · ${p.result?.duration_sec ?? '?'}s`,
          result: p.result,
          finishedAt: Date.now() / 1000,
        }));
      } catch {}
      close();
    });

    es.addEventListener('error', (e: MessageEvent) => {
      // EventSource fires synthetic 'error' on connection drop too — only treat
      // it as a real error if there's a payload (our backend sends one on
      // exception). Otherwise let the browser auto-reconnect handle it.
      let msg: string | null = null;
      try {
        const p = JSON.parse((e as any).data ?? '{}');
        if (p && p.message) msg = String(p.message);
      } catch {}
      if (msg) {
        setState((s) => ({
          ...s,
          scanning: false,
          phase: 'error',
          phaseMessage: msg!,
          error: msg,
          finishedAt: Date.now() / 1000,
        }));
        close();
      }
    });

    // The browser also emits a generic onerror when the stream itself fails
    // (e.g. server reset). If we never received a 'done' or backend 'error',
    // surface a connection-drop error.
    es.onerror = () => {
      setState((s) => {
        if (!s.scanning) return s;  // already finished cleanly
        return {
          ...s,
          scanning: false,
          phase: 'error',
          phaseMessage: 'Connection dropped',
          error: 'Connection dropped',
          finishedAt: Date.now() / 1000,
        };
      });
      close();
    };
  }, [close]);

  const reset = useCallback(() => setState(INITIAL), []);

  return { ...state, start, close, reset };
}

function phaseLabel(phase: string): string {
  switch (phase) {
    case 'loading_universe': return 'Loading universe';
    case 'rs':               return 'Computing Relative Strength ranks';
    case 'warming_names':    return 'Warming company-name cache';
    case 'scanning':         return 'Scanning tickers';
    case 'market_context':   return 'Computing market regime';
    case 'enriching':        return 'Catalyst + insider + CANSLIM enrichment';
    case 'writing':          return 'Persisting scan';
    default:                 return phase;
  }
}
