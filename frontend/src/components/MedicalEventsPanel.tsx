/* 🧬 Medical events — the ticker page's Catalyst tab (/sepa/{SYM}?tab=catalyst),
 * mounted right under the ⚖️ two-sided read. Reads
 * GET /catalysts/medical/{symbol}; the served UNMEASURED note and `setup`
 * render on every state that has a payload, including zero events. A fetch
 * error is one muted line — it never takes the rest of the tab with it. */
import { MedicalEventRow } from './MedicalEventRow';
import { mdy } from './RussellWatch';
import { useMedicalSymbol } from '../hooks/useMedicalCatalysts';

export function MedicalEventsPanel({ symbol }: { symbol: string }) {
  const { data, error, loading } = useMedicalSymbol(symbol);
  if (error && !data) {
    return <div className="mc-panel mc-dim" data-testid="mc-panel-error">🧬 Medical events unavailable ({error}).</div>;
  }
  if (!data) {
    return loading ? <div className="mc-panel mc-dim">Loading 🧬 medical events…</div> : null;
  }
  // Newest first: session date, then publication stamp (ISO strings sort).
  const events = [...(data.events ?? [])].sort((a, b) =>
    (b.session_date ?? '').localeCompare(a.session_date ?? '')
    || (b.published_at_et ?? '').localeCompare(a.published_at_et ?? ''));
  return (
    <section className="mc-panel" data-testid="mc-panel">
      <h4 className="mc-panel__h">🧬 Medical events</h4>
      <div className="mc-note" data-testid="mc-panel-unmeasured">{data.labels.note}</div>
      <div className="mc-setup" data-testid="mc-panel-setup">Setup: {data.labels.setup}</div>
      {events.length === 0 ? (
        <div className="mc-empty" data-testid="mc-panel-empty">
          No medical catalysts recorded for {data.symbol || symbol}
          {data.tracking_since ? ` since ${mdy(data.tracking_since)}` : ' yet — the first full roster pass has not finished'}.
        </div>
      ) : (
        events.map((ev) => <MedicalEventRow key={ev.event_key} ev={ev} showTimeline={false} />)
      )}
    </section>
  );
}
