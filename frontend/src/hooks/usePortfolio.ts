/* Hooks for the /portfolio page.
 *
 * Three small hooks that each correspond to one Plaid-backed endpoint:
 *   - useStatus()        → /portfolio/status
 *   - useHoldings()      → /portfolio/holdings (+ refresh)
 *   - usePositionMeta()  → /portfolio/position-meta (GET + PUT)
 *
 * Why separate hooks instead of one mega-hook: each call returns at
 * different cadences (status is cheap and frequent; holdings is heavy
 * and cached for an hour; meta only changes when the user types). The
 * page composes them so partial loads still render the relevant
 * sections.
 *
 * All fetches use `credentials: 'include'` so the session cookie
 * carries the auth identity (per the backend's local_auth + oauth2
 * dual-path setup).
 */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

// ────────────────────────────────────────────────────────────────────────
// Types — mirror the backend response shapes so tsc catches drift early.
// ────────────────────────────────────────────────────────────────────────
export type PortfolioStatus = {
  plaid_configured: boolean;
  has_linked_account: boolean;
  institution_name: string;
  last_sync: number | null;
  linked_at: number | null;
};

export type HoldingRow = {
  symbol: string;
  name: string;
  account_id: string | null;
  quantity: number;
  cost_basis: number | null;
  avg_cost: number | null;
  current_price: number | null;
  plaid_price: number | null;
  current_value: number | null;
  pl_dollars: number | null;
  pl_pct: number | null;
  day_change_pct: number | null;
  entry: number | null;
  stop: number | null;
  target: number | null;
  r_multiple: number | null;
  notes: string;
  // Where this row came from. Backend tags each row as it merges them
  // into the response: Plaid-returned positions, CSV-imported ones (via
  // Fidelity's Download Positions button), or rows typed into the
  // legacy /portfolio form. Used for the source badge on each row.
  source?: 'plaid' | 'csv' | 'manual';
};

export type AccountBalance = {
  available:               number | null;
  current:                 number | null;
  iso_currency_code:       string | null;
  limit:                   number | null;
  margin_loan_amount?:     number | null;
  unofficial_currency_code: string | null;
};

export type AccountRow = {
  account_id:     string;
  name:           string;
  official_name?: string | null;
  type?:          string | null;       // "investment", "depository", ...
  subtype?:       string | null;       // "401k", "hsa", "brokerage", "ira", ...
  mask?:          string | null;       // last 4 digits, e.g. "7733"
  balances?:      AccountBalance;
};

export type HoldingsResponse = {
  rows: HoldingRow[];
  accounts: AccountRow[];
  cached_at: number | null;
  fresh: boolean;
  linked: boolean;
};

export type PositionMeta = {
  symbol: string;
  entry?: number | null;
  stop?: number | null;
  target?: number | null;
  notes?: string;
  updated_at?: number;
};

// ────────────────────────────────────────────────────────────────────────
// useStatus — cheap call, polls on mount + after exchange. Page uses
// the result to switch between the three render states (not configured /
// not linked / connected).
// ────────────────────────────────────────────────────────────────────────
export function useStatus() {
  const [status, setStatus] = useState<PortfolioStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/portfolio/status`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setStatus((await r.json()) as PortfolioStatus);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { status, loading, error, refresh };
}

// ────────────────────────────────────────────────────────────────────────
// useHoldings — the heavy call. Hits Plaid only when cache is stale or
// the user clicks "refresh". Returns the rolled-up rows that feed both
// the table and the heatmap.
// ────────────────────────────────────────────────────────────────────────
export function useHoldings(enabled: boolean = true) {
  const [data, setData] = useState<HoldingsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (forceRefresh: boolean = false) => {
    setLoading(true);
    try {
      const url = `${API}/portfolio/holdings${forceRefresh ? '?refresh=true' : ''}`;
      const r = await fetch(url, { credentials: 'include' });
      if (!r.ok) {
        // 503 (Plaid offline) and 404 (not linked) are surfaced as a
        // friendly error rather than thrown — page renders an empty
        // state with a retry button.
        const body = await r.text().catch(() => '');
        throw new Error(`HTTP ${r.status} ${body}`);
      }
      setData((await r.json()) as HoldingsResponse);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    load(false);
  }, [enabled, load]);

  const refresh = useCallback(async () => {
    // POST refresh endpoint pushes Plaid → cache, then we re-load.
    try {
      await fetch(`${API}/portfolio/holdings/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch (e) {
      /* swallow — falls through to the load() below which surfaces it */
    }
    await load(true);
  }, [load]);

  return { data, loading, error, refresh };
}

// ────────────────────────────────────────────────────────────────────────
// usePositionMeta — user-typed entry/stop/target/notes. PUTting a row
// triggers an optimistic local update + a refetch on success so the
// R-multiple recomputes on the next holdings render.
// ────────────────────────────────────────────────────────────────────────
export function usePositionMeta() {
  const [metas, setMetas] = useState<PositionMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/portfolio/position-meta`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setMetas((body.metas || []) as PositionMeta[]);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const set = useCallback(async (
    symbol: string,
    fields: { entry?: number | null; stop?: number | null; target?: number | null; notes?: string }
  ) => {
    try {
      const r = await fetch(`${API}/portfolio/position-meta`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, ...fields }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
    } catch (e) {
      setError(String(e));
    }
  }, [load]);

  return { metas, loading, error, set, refresh: load };
}

// ────────────────────────────────────────────────────────────────────────
// Plaid Link flow helpers — minted server-side, opened client-side.
// Kept in the hooks file so the page component doesn't import anything
// Plaid-specific until the user actually clicks "Connect".
// ────────────────────────────────────────────────────────────────────────
export async function fetchLinkToken(): Promise<string> {
  const r = await fetch(`${API}/portfolio/plaid/link-token`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = await r.json();
  return body.link_token as string;
}

export async function exchangePublicToken(publicToken: string): Promise<{ ok: boolean; institution_name: string }> {
  const r = await fetch(`${API}/portfolio/plaid/exchange`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ public_token: publicToken }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function disconnectPlaid(): Promise<{ removed: boolean; error?: string }> {
  const r = await fetch(`${API}/portfolio/plaid/disconnect`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ────────────────────────────────────────────────────────────────────────
// CSV import — Fidelity "Download Positions" CSV fallback when Plaid's
// Investments Trial tier returns balances without per-position detail.
// Returns the backend's import summary so the page can show "X imported,
// Y skipped" right after upload.
// ────────────────────────────────────────────────────────────────────────
export type CsvImportResult = {
  ok:              boolean;
  written?:        number;
  failed?:         Array<{ ticker: string; reason: string }>;
  total_value?:    number;
  skipped_csv?:    number;
  parsed_summary?: { imported_rows: number; total_value: number; skipped: number };
  reason?:         string;
  hint?:           string;
};

export async function uploadFidelityCsv(file: File): Promise<CsvImportResult> {
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch(`${API}/portfolio/csv-import`, {
    method:      'POST',
    credentials: 'include',
    body:        fd,
  });
  // Backend returns 400 with a JSON body on parse errors; surface that
  // to the page instead of throwing a bare HTTP error.
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    return { ok: false, reason: body?.reason || `HTTP ${r.status}`, hint: body?.hint };
  }
  return body as CsvImportResult;
}

export type CsvDiskListing = {
  drop_dir: string;
  files: Array<{ name: string; size: number; mtime: number }>;
};

export async function listCsvDisk(): Promise<CsvDiskListing> {
  const r = await fetch(`${API}/portfolio/csv-import/disk`, { credentials: 'include' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function syncCsvFromDisk(archive: boolean = false): Promise<CsvImportResult & { file?: string }> {
  const r = await fetch(`${API}/portfolio/csv-import/sync-disk?archive=${archive}`, {
    method:      'POST',
    credentials: 'include',
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    return { ok: false, reason: body?.reason || `HTTP ${r.status}`, hint: body?.hint };
  }
  return body;
}

// ────────────────────────────────────────────────────────────────────────
// Alerts — Web Push pipeline for portfolio positions. Sends fire from
// the every-15-min cron during market hours and at 3:00/3:30 PM ET for
// the EOD brief. Tapping a notification opens /portfolio?ack=<symbol>
// which calls ackAlert() on mount to stop the 15-min re-ringing.
// ────────────────────────────────────────────────────────────────────────
export type AlertStateRow = {
  user_email:        string;
  symbol:            string;
  date_key:          string;       // YYYY-MM-DD in ET
  verdict:           string;       // FULL_EXIT | REDUCE | TIGHTEN_STOP | HOLD
  fired_count:       number;
  first_fired_at:    number;
  last_fired_at:     number;
  acknowledged_at?:  number | null;
};

export function useAlertState() {
  const [rows, setRows] = useState<AlertStateRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/portfolio/alerts/state`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setRows((body.rows || []) as AlertStateRow[]);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { rows, loading, error, refresh };
}

export async function ackAlert(symbol: string): Promise<{ ok: boolean }> {
  const r = await fetch(`${API}/portfolio/alerts/ack`, {
    method:      'POST',
    credentials: 'include',
    headers:     { 'Content-Type': 'application/json' },
    body:        JSON.stringify({ symbol }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function runAlertsNow(kind: 'intraday' | 'eod_brief' | 'eod_escalate' = 'intraday'): Promise<any> {
  const r = await fetch(`${API}/portfolio/alerts/run?kind=${kind}`, {
    method:      'POST',
    credentials: 'include',
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function clearCsvImport(account?: string): Promise<{ ok: boolean; removed: number }> {
  const url = account
    ? `${API}/portfolio/csv-import?account=${encodeURIComponent(account)}`
    : `${API}/portfolio/csv-import`;
  const r = await fetch(url, { method: 'DELETE', credentials: 'include' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ────────────────────────────────────────────────────────────────────────
// useDropAttribution — is each holding's move driven by the MARKET, its
// SECTOR, or the STOCK itself? Backend: /portfolio/attribution (CAPM split).
// ────────────────────────────────────────────────────────────────────────
export type AttrVerdict = 'macro' | 'sector' | 'stock' | 'quiet';

export type AttributionRow = {
  symbol: string;
  window_days: number;
  move_pct: number;
  notable: boolean;
  market_move_pct: number;
  sector_move_pct: number | null;
  sector_etf: string;
  sector_name: string | null;
  beta_market: number | null;
  expected_from_market_pct: number;
  explained_by_market_pct: number;
  explained_by_sector_pct: number;
  idiosyncratic_pct: number;
  verdict: AttrVerdict;
  confidence: number;
  summary: string;
};

export type AttributionResponse = {
  rows: AttributionRow[];
  counts: { macro: number; sector: number; stock: number };
  n: number;
  window_days: number;
};

export function useDropAttribution(window: number = 5, enabled: boolean = true) {
  const [data, setData] = useState<AttributionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/portfolio/attribution?window=${window}`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData((await r.json()) as AttributionResponse);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    if (!enabled) return;
    load();
  }, [enabled, load]);

  return { data, loading, error, reload: load };
}

// ────────────────────────────────────────────────────────────────────────
// usePortfolioBetas — per-holding market sensitivity (beta) + expected
// down-day move + a blended portfolio beta. Backend: /portfolio/betas.
// ────────────────────────────────────────────────────────────────────────
export type BetaRow = {
  symbol: string;
  name: string;
  beta_spy_60: number | null;
  beta_spy_1y: number | null;
  beta_qqx_60: number | null;
  last_price: number;
  shares: number;
  market_value: number;
  expect_down_1pct: number | null;   // expected % move on a SPY -1% day
  expect_down_3pct: number | null;
};

export type BetaResponse = {
  rows: BetaRow[];
  n: number;
  total_value: number;
  blended_beta_60d: number | null;
  blended_beta_1y: number | null;
};

export function usePortfolioBetas(enabled: boolean = true) {
  const [data, setData] = useState<BetaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/portfolio/betas`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData((await r.json()) as BetaResponse);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (enabled) load(); }, [enabled, load]);

  return { data, loading, error, reload: load };
}
