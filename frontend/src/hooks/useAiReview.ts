import { useCallback, useState } from 'react';
import { API } from '../lib/apiBase';


export type AiReview = {
  enabled: boolean;
  symbol?: string;
  as_of?: string;
  review?: {
    setup_quality?: number;
    pattern?: string;
    rationale?: string;
    risks?: string[];
    veto?: boolean;
    veto_reason?: string;
    raw?: string;
  };
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
  latency_sec?: number;
  message?: string;
  error?: string;
  from_cache?: boolean;
};

export function useAiReview() {
  const [data, setData] = useState<AiReview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const review = useCallback(async (symbol: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/day/explain/${symbol}`, { cache: 'no-store' });
      const j = await r.json();
      setData(j);
      if (!r.ok && !j.enabled) setError(j.message || 'LLM not enabled');
      else if (j.error) setError(j.error);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => { setData(null); setError(null); }, []);

  return { data, loading, error, review, reset };
}
