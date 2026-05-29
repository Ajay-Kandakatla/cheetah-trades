/**
 * SepaTrendContext — provides per-symbol score + rank trend deltas to
 * every SEPA card without making the cards fetch their own history.
 *
 * Added 2026-05-28 in response to user feedback:
 *   "when points drop is there way we can track and some how maintaining
 *    a trend separately how the trend change based on our ranking of a
 *    stock by day"
 *
 * Pure FE. Zero changes to ranking logic. Uses the three /sepa/history/*
 * endpoints that already exist (backend/sepa/history.py):
 *
 *   /sepa/history/runs?limit=20         → list of recent run dates
 *   /sepa/history/date/{date_et}        → full leaderboard for one day
 *
 * Strategy: fetch the last-trading-day scan + ~5-trading-days-ago scan
 * ONCE per page (not per card — 200 cards × 2 fetches each would crush
 * the API). Build {symbol → {score, rank}} maps off them. Each card
 * looks up its own symbol in O(1) to compute Δ score (vs 7d) and
 * Δ rank (vs yesterday).
 *
 * Rank is derived client-side by sorting each scan's candidates by score
 * descending. This matches how the V1 list sorts the live results, so
 * the displayed "current rank" of a card lines up with what the user
 * actually sees on screen.
 */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { API } from '../lib/apiBase';
import type { RunSummary, DateScan, DateScanCandidate } from '../hooks/useSepaHistory';

/** One symbol's position on a given scan. */
export type TrendPoint = {
  score: number;
  rank: number;        // 1 = leaderboard top
};

type Maps = {
  yesterday: Map<string, TrendPoint>;
  weekAgo:   Map<string, TrendPoint>;
  current:   Map<string, TrendPoint>;
  yesterdayDate: string | null;
  weekAgoDate:   string | null;
  ready: boolean;
  /** False while history endpoints are still being fetched. The card
   *  uses this to render a "—" placeholder instead of a wrong "🆕". */
  loading: boolean;
};

const Ctx = createContext<Maps>({
  yesterday: new Map(),
  weekAgo:   new Map(),
  current:   new Map(),
  yesterdayDate: null,
  weekAgoDate:   null,
  ready: false,
  loading: false,
});

/** Sort an array of candidates by score descending, return Map of
 *  {symbol → {score, rank}}. Mirrors the V1 card ordering. */
function buildRankMap(candidates: Array<{ symbol?: string | null; score?: number | null }>): Map<string, TrendPoint> {
  const m = new Map<string, TrendPoint>();
  const sorted = [...candidates]
    .filter(c => c.symbol && c.score != null)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  sorted.forEach((c, i) => {
    m.set((c.symbol as string).toUpperCase(), {
      score: c.score as number,
      rank:  i + 1,
    });
  });
  return m;
}

interface ProviderProps {
  /** The currently displayed scan's candidates. We sort these here to
   *  compute "current rank" — must include ALL candidates the list is
   *  ranking against, not just the filtered view. */
  currentCandidates: Array<{ symbol?: string | null; score?: number | null }>;
  /** Date of the current scan in YYYY-MM-DD (ET). When provided, we
   *  search for yesterday/week-ago dates STRICTLY before this date so
   *  we don't pick up the same scan we're already showing. */
  currentDateEt?: string | null;
  children: ReactNode;
}

export function SepaTrendProvider({ currentCandidates, currentDateEt, children }: ProviderProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [yScan, setYScan] = useState<DateScan | null>(null);
  const [wScan, setWScan] = useState<DateScan | null>(null);
  const [scansLoading, setScansLoading] = useState(true);

  // Step 1: fetch the recent runs index so we can pick real trading
  // dates (handles weekends / holidays / no-scan days correctly).
  useEffect(() => {
    let alive = true;
    setRunsLoading(true);
    fetch(`${API}/sepa/history/runs?limit=20`)
      .then(r => (r.ok ? r.json() : { runs: [] }))
      .then(j => { if (alive) setRuns(j.runs || []); })
      .finally(() => { if (alive) setRunsLoading(false); });
    return () => { alive = false; };
  }, []);

  // Step 2: pick yesterday's + ~5-trading-days-ago run dates from the
  // sorted runs list. Skip runs whose date_et matches the current scan's
  // date (we want PAST scans, not today's earlier scan of the same day).
  const { yesterdayDate, weekAgoDate } = useMemo(() => {
    // runs come pre-sorted by generated_at DESC, so the first run
    // whose date_et < currentDateEt is "yesterday"; the run ~5
    // positions further back is "5 trading days ago".
    const past = runs.filter(r => r.date_et && (!currentDateEt || r.date_et < currentDateEt));
    // Dedupe by date_et — if cron ran 4 times on the same day we
    // only want one snapshot per day.
    const dedup: string[] = [];
    for (const r of past) {
      if (r.date_et && !dedup.includes(r.date_et)) dedup.push(r.date_et);
    }
    return {
      yesterdayDate: dedup[0] || null,
      weekAgoDate:   dedup[4] || dedup[dedup.length - 1] || null,
    };
  }, [runs, currentDateEt]);

  // Step 3: fetch both historical full-scan payloads in parallel.
  // Single fetch per page — the rank/score maps built from these are
  // re-used across all 200+ cards via context.
  useEffect(() => {
    if (!yesterdayDate || !weekAgoDate) return;
    let alive = true;
    setScansLoading(true);
    Promise.all([
      fetch(`${API}/sepa/history/date/${yesterdayDate}`).then(r => r.ok ? r.json() : null),
      fetch(`${API}/sepa/history/date/${weekAgoDate}`).then(r => r.ok ? r.json() : null),
    ])
      .then(([y, w]) => {
        if (!alive) return;
        setYScan(y);
        setWScan(w);
      })
      .finally(() => { if (alive) setScansLoading(false); });
    return () => { alive = false; };
  }, [yesterdayDate, weekAgoDate]);

  // Step 4: build the three rank maps. Cheap — pure sort + iterate.
  const value = useMemo<Maps>(() => {
    const yesterday = yScan?.candidates ? buildRankMap(yScan.candidates as DateScanCandidate[]) : new Map();
    const weekAgo   = wScan?.candidates ? buildRankMap(wScan.candidates as DateScanCandidate[]) : new Map();
    const current   = buildRankMap(currentCandidates);
    return {
      yesterday,
      weekAgo,
      current,
      yesterdayDate,
      weekAgoDate,
      ready: yScan != null && wScan != null,
      loading: runsLoading || scansLoading,
    };
  }, [yScan, wScan, currentCandidates, yesterdayDate, weekAgoDate, runsLoading, scansLoading]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Read trend data for one symbol. Returns null if the provider isn't
 *  mounted (e.g. outside the SEPA page) so consumers can no-op safely. */
export function useSepaTrend(symbol: string) {
  const ctx = useContext(Ctx);
  const up = symbol.toUpperCase();
  return {
    current:   ctx.current.get(up)   ?? null,
    yesterday: ctx.yesterday.get(up) ?? null,
    weekAgo:   ctx.weekAgo.get(up)   ?? null,
    yesterdayDate: ctx.yesterdayDate,
    weekAgoDate:   ctx.weekAgoDate,
    ready:   ctx.ready,
    loading: ctx.loading,
  };
}
