import { useEffect, useRef, useState } from 'react';
import type { Quote, ConnectionStatus } from '../types';

export function useMarketStream(symbols: string[]) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (symbols.length === 0) return;
    const url = `/stream?symbols=${encodeURIComponent(symbols.join(','))}`;
    const es = new EventSource(url);
    esRef.current = es;
    setStatus('connecting');

    es.onopen = () => setStatus('open');
    es.onerror = () => setStatus('error');
    es.addEventListener('quote', (evt: MessageEvent) => {
      try {
        const q: Quote = JSON.parse(evt.data);
        setQuotes((prev) => ({ ...prev, [q.symbol]: q }));
      } catch (e) {
        console.warn('Bad quote payload', e);
      }
    });

    return () => {
      es.close();
      setStatus('closed');
    };
  }, [symbols.join(',')]);

  return { quotes, status };
}
