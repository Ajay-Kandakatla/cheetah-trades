import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

export type Workspace = 'personal' | 'work';
export type AiStatus  = 'pending' | 'running' | 'done' | 'failed' | null;

export type Todo = {
  _id: string;
  text: string;
  created_at: number;
  due_at: number | null;
  notify_at: number | null;
  notified_at: number | null;
  status: 'active' | 'completed';
  completed_at: number | null;
  ticker: string | null;
  important: boolean;
  /** New axis: 'personal' (default) | 'work'. Legacy rows without
   *  the field are treated as personal by the backend filter. */
  workspace?: Workspace;
  /** Free-form provenance tag: 'manual', 'claude', 'cron', 'admin',
   *  'recurring'. Surfaced as a small badge in the UI. */
  source?: string;
  /** When true, the LLM runner cron picks it up and writes ai_result. */
  ai_task?: boolean;
  ai_status?: AiStatus;
  /** Full markdown research note from the LLM. Shown in the expand panel. */
  ai_result?: string | null;
  /** Brief TL;DR extracted from ai_result. Shown inline on the row so
   *  the user knows what the AI found without expanding. */
  ai_summary?: string | null;
  ai_processed_at?: number | null;
};

export function useTodos(
  status: 'all' | 'active' | 'completed' = 'all',
  workspace: 'all' | Workspace = 'all',
) {
  const [rows, setRows] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const r = await fetch(`${API}/todos?status=${status}&workspace=${workspace}`);
      const j = await r.json();
      setRows(j.rows || []);
    } finally {
      setLoading(false);
    }
  }, [status, workspace]);

  useEffect(() => { refetch(); }, [refetch]);

  const add = useCallback(async (payload: {
    text: string; due_at?: number | null;
    notify_at?: number | null; ticker?: string | null;
    important?: boolean;
    workspace?: Workspace;
    ai_task?: boolean;
    source?: string;
  }) => {
    await fetch(`${API}/todos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    refetch();
  }, [refetch]);

  const update = useCallback(async (id: string, patch: Partial<Todo>) => {
    await fetch(`${API}/todos/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    refetch();
  }, [refetch]);

  const remove = useCallback(async (id: string) => {
    await fetch(`${API}/todos/${id}`, { method: 'DELETE' });
    refetch();
  }, [refetch]);

  const toggle = useCallback(async (t: Todo) => {
    await update(t._id, { status: t.status === 'active' ? 'completed' : 'active' });
  }, [update]);

  /** Run / re-run the LLM on one AI task. Returns the runner's
   *  result dict so the caller can show a quick "✓ done" toast.
   *  Blocks for the duration of the LLM round-trip (~2-15s depending
   *  on the model + prompt). */
  const runAi = useCallback(async (id: string) => {
    const r = await fetch(`${API}/todos/${id}/run-ai`, { method: 'POST' });
    const j = await r.json();
    await refetch();
    return j;
  }, [refetch]);

  return { rows, loading, refetch, add, update, remove, toggle, runAi };
}
