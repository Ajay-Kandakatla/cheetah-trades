/* useBreakoutBoard — fetches the dedicated /breakouts page feed
 * (GET /sepa/breakout-board): every name that has broken out, ranked by
 * breakout COUNT (highest first), each carrying the Minervini+Bonde buy_verdict.
 * Display-only; one fetch with a manual reload. */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import type { BuyVerdict } from '../components/BuyVerdictChip';
import type { ConvictionDetail, EntryExitDecision } from './useSepa';

export type BreakoutBoardRow = {
  symbol: string;
  name?: string | null;
  breakout_count: number;
  window_bars?: number;
  last_vol?: number | null;
  avg_vol_50?: number | null;
  days_since_breakout: number | null;
  high_vol_breakout: boolean;
  broke_out_today: boolean;
  last_close?: number | null;
  day_change_pct?: number | null;
  rs_rank?: number | null;
  stage?: number | null;
  stage_label?: string | null;
  beta?: number | null;               // 1y daily beta vs SPY — volatility (<1 = low-vol)
  r1?: number | null;                 // trade-plan R-multiple targets (entry +1R / +2R)
  r2?: number | null;
  industry?: string | null;
  /** AI-ecosystem sector tag + priority (backend supply_demand.sectors) — Ajay
   *  wants breakout lists led by AI-sector winners (chips/energy/water-cooling/…).
   *  ai_sector_rank: 0 = highest priority; null = not an AI-ecosystem name. */
  ai_sector?: string | null;
  ai_sector_id?: string | null;
  ai_sector_etf?: string | null;
  ai_sector_rank?: number | null;
  is_etf?: boolean;
  /** Strict Minervini buy-now gate (scanner._is_buyable) — the SAME gate the
   *  SEPA scan's 🟢 Enter uses, not just the Trend-Template qualifier. */
  is_buyable?: boolean;
  setup_ready?: boolean;
  /** Why a SETUP row isn't buyable. `extended` = the breakout closed >3% past
   *  the pivot it cleared (too far to chase, TLSW p.224) → wait for a pullback. */
  setup_note?: { kind: 'extended'; ext_pct: number; pivot: number | null } | null;
  /** Institutions selling into the breakout (churn/climax distribution) — its
   *  own held-out-of-Enter reason, distinct from `setup_note`. */
  distribution_selling?: boolean;
  /** Entry-setup type (VCP / POWER_PLAY / POCKET_PIVOT / BREAKOUT) — drives the
   *  'Base only' filter that hides bare breakouts with no detected base. */
  setup_type?: string | null;
  /** Momentum-led conviction rank 0-100 (backend sepa/conviction.py) — the new
   *  default sort for the board. Climax names suppressed to the bottom. */
  conviction?: number | null;
  conviction_detail?: ConvictionDetail | null;
  /** Climax-aware ENTER/WATCH/AVOID verdict (entry_exit) — a climax breakout
   *  reads AVOID here, not a buy. */
  decision?: EntryExitDecision | null;
  decision_color?: string | null;
  buy_verdict?: BuyVerdict | null;
  /** EPS + explosive-growth overlay (Ajay 2026-09-12: "update the breakout page
   *  with EPS and explosive growth logic we created"). Sales/EPS come from the
   *  SAME research cache the 🔥 Hottest board reads, so the two boards cannot
   *  print different numbers for one name. `explosive` is MEMBERSHIP of the
   *  🚀 Growth board (100% sales AND 100% quarterly EPS, prior quarter also
   *  growing) — a pointer, never a second copy of that screen. */
  sales_yoy?: number | null;
  q_eps_yoy?: number | null;
  sales_tier?: string | null;
  explosive?: boolean;
  /** The 🚀 name is one the trading engine will REFUSE (sub-$2 or a known cap
   *  under $700M). Good growth must not make an unbuyable row look clean. */
  explosive_refused?: boolean;
  /** It ARRIVED on the growth board recently (growth.tracker.newly_found).
   *  False until first-seen tracking has actually observed an arrival — a name
   *  present at the very first build is not "new", it is just the first thing
   *  we ever saw. */
  explosive_new?: boolean;
};

export type BreakoutBoardSummary = {
  total: number;
  broke_out_today: number;
  buyable: number;
  minervini_pass: number;
  minervini_fail: number;
  bonde_pass: number;
  bonde_fail: number;
  both_pass: number;
};

type Board = {
  rows: BreakoutBoardRow[];
  summary: BreakoutBoardSummary | null;
  scanTs: number | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  stageInfo: StageInfo;
};

const EMPTY_SUMMARY: BreakoutBoardSummary = {
  total: 0, broke_out_today: 0, buyable: 0, minervini_pass: 0, minervini_fail: 0,
  bonde_pass: 0, bonde_fail: 0, both_pass: 0,
};

export type StageInfo = {
  /** the gate was applied by the server */
  on: boolean;
  /** names the gate removed BEFORE the top-N cut */
  dropped: number;
  /** how many names passed the gate in total (the cut is taken from these) */
  qualifying: number;
  /** how many had broken out at all, before the gate */
  scanned: number;
};
const EMPTY_STAGE: StageInfo = { on: false, dropped: 0, qualifying: 0, scanned: 0 };

export function useBreakoutBoard(top = 250, minCount = 1, stages = true): Board {
  const [rows, setRows] = useState<BreakoutBoardRow[]>([]);
  const [summary, setSummary] = useState<BreakoutBoardSummary | null>(null);
  const [scanTs, setScanTs] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  /* What the stage gate removed, so a filtered board can never read as the
     whole market breaking out (Ajay 2026-09-12). */
  const [stageInfo, setStageInfo] = useState<StageInfo>(EMPTY_STAGE);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fetch(`${API}/sepa/breakout-board?top=${top}&min_count=${minCount}&stages=${stages}`,
          { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => {
        if (!alive) return;
        setRows(Array.isArray(j.rows) ? j.rows : []);
        setSummary(j.summary ?? EMPTY_SUMMARY);
        setScanTs(j.scan_ts ?? null);
        setStageInfo({
          on: !!j.stage_filter,
          dropped: typeof j.n_stage_dropped === 'number' ? j.n_stage_dropped : 0,
          qualifying: typeof j.n_all === 'number' ? j.n_all : 0,
          scanned: typeof j.n_prestage === 'number' ? j.n_prestage : 0,
        });
        setLoading(false);
      })
      .catch((e) => {
        if (!alive) return;
        setError(String(e?.message || e));
        setLoading(false);
      });
    return () => { alive = false; };
  }, [top, minCount, stages, nonce]);

  return { rows, summary, scanTs, loading, error, reload, stageInfo };
}
