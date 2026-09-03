/* useNotificationPrefs — fetches the current user's registered push
   devices (web + mac) and their per-category preferences. Provides
   helpers to toggle a single category, update quiet hours, send a test
   push, and unsubscribe a device entirely.

   All backend calls are user-scoped via the oauth2-proxy email header —
   the API only returns/edits devices owned by the signed-in user. */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type NotificationPrefs = {
  volume_breakout?: boolean;
  rising_momentum?: boolean;
  sepa_new_candidate?: boolean;
  watchlist_breakout?: boolean;
  juggernaut_watchlist?: boolean;
  stage_breakdown?: boolean;
  watchlist_stage_breakdown?: boolean;
  price_alert?: boolean;
  position_alert?: boolean;
  promo_alert?: boolean;
  demand_alert?: boolean;
  morning_brief?: boolean;
  todo_reminder?: boolean;
  todo_daily_digest?: boolean;
  // macbook_deal removed 2026-05-15 — lifeboard Mac deal scraper deleted.
  product_launch?: boolean;
  // Minervini flash cards — 3 push/weekday (9 ET / 12:30 ET / 16:00 ET).
  // Bite-sized education from the SEPA author's books. Backed by
  // backend/flashcards/flashcards.py — 36-card bank, deterministic
  // day-of-year rotation so the user cycles through topics without
  // immediate repetition. Default ON for new subscriptions.
  minervini_flashcards?: boolean;
  // Market open / close reminders — pings 15 min before each bell
  // (9:15 ET + 3:45 ET Mon-Fri, skips US holidays). See
  // backend/market_hours/reminder.py. Default ON.
  market_hours_reminder?: boolean;
  // Volleyball fitness — three independent kinds:
  //   vb_workout    — 7 AM ET daily workout brief
  //   vb_supplement — 9:30 PM ET magnesium reminder
  //   vb_education  — 6 PM ET daily VB/health card
  // See backend/volleyball/reminders.py.
  vb_workout?:    boolean;
  vb_supplement?: boolean;
  vb_education?:  boolean;
  // Pivot / entry alerts (sepa.pivot_alerts cron) — at-pivot / approaching.
  pivot_alert?: boolean;
  // SEPA-cross tape watch (scalping.sepa_watch) — 5-min candle reads at
  // pivot/VWAP/levels on holdings + buyable + at-pivot + leaderboard names.
  scalp_tape?: boolean;
  // Real-estate (house) notifications — see backend/house/daily_scrape.py.
  // Default ON for everyone; only HOUSE_OWNER_EMAIL actually receives
  // pushes since the cron scopes via send_to_user(owner, ...).
  house_daily?:         boolean;
  house_scrape_failed?: boolean;
  house_stagnant?:      boolean;
  user_signin?: boolean;
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
};

export type DeviceRow = {
  kind: 'web' | 'mac' | string;
  endpoint: string;
  endpoint_short: string;
  device_id?: string;
  label?: string;
  prefs?: NotificationPrefs;
  created_at?: number;
  updated_at?: number;
};

export function useNotificationPrefs() {
  const [rows, setRows] = useState<DeviceRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);   // tracks which endpoint is mid-save

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const r = await fetch(`${API}/push/subscriptions`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setRows(j.rows || []);
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  /** Toggle a single boolean pref for one device. Optimistic update — local
   *  state flips immediately; reverts if the server call fails. */
  const togglePref = useCallback(async (endpoint: string, key: keyof NotificationPrefs) => {
    if (!rows) return;
    const target = rows.find(r => r.endpoint === endpoint);
    if (!target) return;
    const next: NotificationPrefs = { ...(target.prefs || {}), [key]: !(target.prefs as any)?.[key] };
    setRows(rs => (rs || []).map(r => r.endpoint === endpoint ? { ...r, prefs: next } : r));
    setBusy(endpoint);
    try {
      await fetch(`${API}/push/prefs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint, prefs: next }),
      });
    } catch (e) {
      // Revert on failure
      setRows(rs => (rs || []).map(r => r.endpoint === endpoint ? { ...r, prefs: target.prefs } : r));
      setError('Failed to save — try again');
    } finally {
      setBusy(null);
    }
  }, [rows]);

  /** Update quiet hours fields together (start/end strings + enabled flag). */
  const setQuietHours = useCallback(async (endpoint: string, fields: Partial<NotificationPrefs>) => {
    if (!rows) return;
    const target = rows.find(r => r.endpoint === endpoint);
    if (!target) return;
    const next: NotificationPrefs = { ...(target.prefs || {}), ...fields };
    setRows(rs => (rs || []).map(r => r.endpoint === endpoint ? { ...r, prefs: next } : r));
    setBusy(endpoint);
    try {
      await fetch(`${API}/push/prefs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint, prefs: next }),
      });
    } catch {
      setError('Failed to save quiet hours');
    } finally {
      setBusy(null);
    }
  }, [rows]);

  /** Unsubscribe (remove) a device entirely. Mac and web have different endpoints. */
  const unsubscribe = useCallback(async (row: DeviceRow) => {
    setBusy(row.endpoint);
    try {
      if (row.kind === 'mac' && row.device_id) {
        await fetch(`${API}/push/mac-unregister`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_id: row.device_id }),
        });
      } else {
        await fetch(`${API}/push/unsubscribe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: row.endpoint }),
        });
      }
      // Drop locally, no need to refetch
      setRows(rs => (rs || []).filter(r => r.endpoint !== row.endpoint));
    } catch {
      setError('Failed to remove device');
    } finally {
      setBusy(null);
    }
  }, []);

  /** Fire a test push to verify the device is alive. */
  const sendTest = useCallback(async (row: DeviceRow) => {
    setBusy(row.endpoint);
    try {
      const url = row.kind === 'mac'
        ? `${API}/push/mac-test`
        : `${API}/push/test`;
      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(row.kind === 'mac'
          ? { device_id: row.device_id }
          : { endpoint: row.endpoint }),
      });
    } catch {
      setError('Test failed');
    } finally {
      setBusy(null);
    }
  }, []);

  /** Set multiple bools at once on one device — used by "select all
   *  trading" / "all off" / preset buttons. Single round-trip rather
   *  than N parallel writes. */
  const setManyPrefs = useCallback(async (endpoint: string, updates: Partial<NotificationPrefs>) => {
    if (!rows) return;
    const target = rows.find(r => r.endpoint === endpoint);
    if (!target) return;
    const next: NotificationPrefs = { ...(target.prefs || {}), ...updates };
    setRows(rs => (rs || []).map(r => r.endpoint === endpoint ? { ...r, prefs: next } : r));
    setBusy(endpoint);
    try {
      await fetch(`${API}/push/prefs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint, prefs: next }),
      });
    } catch {
      setRows(rs => (rs || []).map(r => r.endpoint === endpoint ? { ...r, prefs: target.prefs } : r));
      setError('Failed to save');
    } finally {
      setBusy(null);
    }
  }, [rows]);

  return { rows, error, busy, refresh, togglePref, setManyPrefs, setQuietHours, unsubscribe, sendTest };
}
