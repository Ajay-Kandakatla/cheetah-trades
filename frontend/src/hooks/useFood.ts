/**
 * Family meal planner hooks.
 *
 * Endpoints:
 *   GET  /food/today         — two suggested menus for today + kid options
 *   GET  /food/history       — last N days of cooked entries (calendar)
 *   POST /food/log           — log what you actually cooked
 *   GET  /food/grocery       — projected weekly grocery list
 *   GET  /food/preferences   — telangana bias, iron focus, weekend rules
 *   GET  /food/pantry        — bulk staples on hand
 */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { readCache, writeCache } from '../lib/swrCache';

export type Recipe = {
  id: string;
  name: string;
  type: 'main_curry' | 'side_curry' | 'rasam' | 'breakfast_adult' | 'breakfast_kid' | 'protein_side';
  protein: 'goat' | 'chicken' | 'fish' | 'egg' | 'paneer' | 'dal' | 'veg';
  tags: string[];
  iron_mg?: number;
  prep_min?: number;
  cuisine?: string;
  url?: string;
  video_url?: string;
  /** Long-form recipe video (e.g. Amma Chethi Vanta) — UI warns the cook. */
  video_long?: boolean;
  kid_friendly?: boolean;
  lunch_next_day?: boolean;
  iron_rich?: boolean;
  probiotic?: boolean;
  citrus?: boolean;
  weekend?: boolean;
  quick?: boolean;
  ingredients?: { item: string; qty: number; unit: string; category: string }[];
  /** Validated YouTube video — populated by the food/video_resolver pipeline
   *  (Gemma + YouTube scrape + oEmbed validation). Only present when the
   *  resolver has confirmed the video is currently live. */
  validated_video?: {
    video_id: string;
    video_url: string;
    title: string;
    author_name: string;
    author_url?: string;
    thumbnail?: string;
    validated_at?: number;
  };
  _score?: number;
  _reasons?: string[];
};

export type DailyOption = {
  label: string;
  adult_breakfast: Recipe[];
  kid_breakfast: Recipe[];
  dinner: { main: Recipe[]; side: Recipe[]; charu: Recipe[]; protein_side: Recipe[] };
  iron_total_mg: number;
};

export type EatOutPick = {
  id: string;
  name: string;
  cuisine: string;
  area: string;
  tags: string[];
  vibe: string;
  kid_friendly: boolean;
  buffet: boolean;
  google_maps: string;
  yelp: string;
  emoji: string;
};

export type TodaySuggestion = {
  date_et: string;
  is_weekend: boolean;
  options: DailyOption[];
  kid_breakfast_options: Recipe[];
  eat_out?: EatOutPick[];
  history_summary: {
    recent_iron_count: number;
    recent_proteins: Record<string, number>;
    iron_focus_target: number;
  };
};

export function useFoodToday(quickOnly: boolean = false) {
  const cacheKey = `food.today.${quickOnly ? 'quick' : 'full'}`;
  // SWR — hydrate from localStorage on first mount so the menu renders
  // INSTANTLY on phone, then revalidate in the background. Same pattern
  // as SEPA, which is why those pages feel snappy after first visit.
  const [data, setData] = useState<TodaySuggestion | null>(() => {
    const env = readCache<TodaySuggestion>(cacheKey);
    return env?.data ?? null;
  });
  const [loading, setLoading] = useState(() => readCache<TodaySuggestion>(cacheKey) === null);
  const [allowed, setAllowed] = useState(true);
  const reload = useCallback(async () => {
    try {
      const url = `${API}/food/today${quickOnly ? '?quick_only=true' : ''}`;
      const r = await fetch(url);
      if (r.status === 403 || r.status === 404) { setAllowed(false); setData(null); return; }
      if (r.ok) {
        const fresh = await r.json();
        setData(fresh);
        writeCache(cacheKey, fresh);
      }
      setAllowed(true);
    } finally { setLoading(false); }
  }, [quickOnly, cacheKey]);
  useEffect(() => { reload(); }, [reload]);
  return { data, loading, allowed, reload };
}

export type FoodHistoryRow = {
  date_et: string;
  slot: 'adult_breakfast' | 'kid_breakfast' | 'dinner';
  recipe_ids: string[];
  logged_at?: number;
};

export function useFoodHistory(days: number = 14) {
  const cacheKey = `food.history.${days}`;
  const [rows, setRows] = useState<FoodHistoryRow[]>(() => {
    const env = readCache<{rows: FoodHistoryRow[]}>(cacheKey);
    return env?.data?.rows ?? [];
  });
  const [loading, setLoading] = useState(() => readCache<any>(cacheKey) === null);
  const reload = useCallback(async () => {
    try {
      const r = await fetch(`${API}/food/history?days=${days}`);
      const j = r.ok ? await r.json() : { rows: [] };
      setRows(j.rows || []);
      writeCache(cacheKey, j);
    } finally { setLoading(false); }
  }, [days, cacheKey]);
  useEffect(() => { reload(); }, [reload]);
  return { rows, loading, reload };
}

export type GroceryItem = {
  item: string; category: string; unit: string;
  qty: number; from: string[];
};
export type GroceryResponse = {
  week_start: string;
  n_recipes: number;
  categories: Record<string, GroceryItem[]>;
  in_pantry: string[];
  weekly_recurring: string[];
  bulk_reminders: { item: string; msg: string }[];
};

export function useGrocery() {
  const cacheKey = 'food.grocery';
  const [data, setData] = useState<GroceryResponse | null>(() => {
    const env = readCache<GroceryResponse>(cacheKey);
    return env?.data ?? null;
  });
  const [loading, setLoading] = useState(() => readCache<GroceryResponse>(cacheKey) === null);
  const reload = useCallback(async () => {
    try {
      const r = await fetch(`${API}/food/grocery`);
      if (r.ok) {
        const fresh = await r.json();
        setData(fresh);
        writeCache(cacheKey, fresh);
      }
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { reload(); }, [reload]);
  return { data, loading, reload };
}

export async function logCooked(slot: string, recipeIds: string[], dateEt?: string): Promise<void> {
  await fetch(`${API}/food/log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot, recipe_ids: recipeIds, date_et: dateEt }),
  });
}

const _recipeCache: { ts: number; map: Map<string, Recipe> | null } = { ts: 0, map: null };

export async function getRecipeMap(): Promise<Map<string, Recipe>> {
  if (_recipeCache.map && Date.now() - _recipeCache.ts < 10 * 60_000) {
    return _recipeCache.map;
  }
  const r = await fetch(`${API}/food/recipes`);
  const j = r.ok ? await r.json() : { recipes: [] };
  const m = new Map<string, Recipe>();
  for (const rec of j.recipes || []) m.set(rec.id, rec);
  _recipeCache.ts = Date.now();
  _recipeCache.map = m;
  return m;
}
