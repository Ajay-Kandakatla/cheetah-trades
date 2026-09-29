/* MedicalEventRow — one classified medical event (🧬 board and the ticker
 * page's timeline). Every word on the row is served: the label, the impact,
 * the modality / area, the moves and the push state. The row reports what the
 * stock DID; it never names a price to act at — the setup is pending study. */
import { Link } from 'react-router-dom';
import { TickerLink } from './TickerLink';
import { mdy } from './RussellWatch';
import {
  directionClass, etClock, fmtMovePct, fmtUsd, labelFor, pushChipText, pushChipTone, sessionTag,
  type MedEventRow as Row,
} from '../lib/medicalCatalysts';

export function MedicalEventRow({ ev, modalityLabels, areaLabels, showTimeline = true }: {
  ev: Row;
  modalityLabels?: Record<string, string>;
  areaLabels?: Record<string, string>;
  /** Off on the ticker page itself — the row already sits on its timeline. */
  showTimeline?: boolean;
}) {
  const det = ev.reaction?.at_detection ?? null;
  const cls = ev.reaction?.at_close ?? null;
  const fwd = ev.reaction?.fwd ?? null;
  const liq = ev.liquidity ?? null;
  const pubT = etClock(ev.published_at_et);
  const seenT = etClock(ev.first_seen_at_et);
  const rvol = cls?.rvol ?? det?.rvol_so_far ?? null;
  const modality = (ev.modality ?? []).filter(Boolean);
  const areas = (ev.areas ?? []).filter(Boolean);
  const tone = pushChipTone(ev.push);
  return (
    <div className={`mc-row${ev.impact === 'high' ? ' mc-row--high' : ''}`} data-testid="mc-row" data-event-key={ev.event_key}>
      <div className="mc-row__when mono"
           title={seenT ? `published ${pubT ?? '—'} ET · first seen ${seenT} ET${ev.latency_min != null ? ` (${Math.round(ev.latency_min)} min later)` : ''}` : undefined}>
        <b>{mdy(ev.session_date)}</b>{pubT ? <span className="mc-dim"> {pubT} ET</span> : null}
      </div>
      <div className="mc-row__who">
        {ev.ticker
          ? <TickerLink ticker={ev.ticker} tab="supply" fromLabel="🧬 Medical catalysts" className="mc-row__tk" />
          : <span className="mc-row__tk mc-row__tk--none" data-testid="mc-unresolved">{ev.company ?? 'issuer unresolved'}</span>}
        {ev.ticker && ev.company ? <span className="mc-row__co mc-dim">{ev.company}</span> : null}
      </div>
      <div className="mc-row__what">
        <span className={`mc-row__label ${directionClass(ev.direction)}`}>{ev.label}</span>
        {ev.impact === 'high' ? <span className="mc-hi" title="High-impact type — the kind the 🧬 push considers">HIGH</span> : null}
        {(ev.trials ?? []).map((t) => <span key={t} className="mc-chip mc-chip--trial">{t}</span>)}
        {modality.map((m) => <span key={`m-${m}`} className="mc-chip mc-chip--mod">{labelFor(modalityLabels, m)}</span>)}
        {areas.map((a) => <span key={`a-${a}`} className="mc-chip mc-chip--area">{labelFor(areaLabels, a)}</span>)}
        <div className="mc-row__headline">{ev.headline}</div>
      </div>
      <div className="mc-row__moves mono">
        <span title={det?.base_close != null ? `vs $${det.base_close.toFixed(2)} prior close` : undefined}>
          seen {fmtMovePct(det?.move_pct)}{det?.session ? <span className="mc-dim"> {sessionTag(det.session)}</span> : null}
        </span>
        <span>close {fmtMovePct(cls?.day_pct)}</span>
        <span>RVOL {rvol != null && Number.isFinite(rvol) ? `${rvol.toFixed(1)}×` : '—'}</span>
        <span>$vol {fmtUsd(cls?.dollar_volume)}</span>
        {liq?.adv50_usd != null ? <span className="mc-dim">50d median {fmtUsd(liq.adv50_usd)}/day</span> : null}
        {fwd?.matured_5d ? <span className="mc-dim">5d {fmtMovePct(fwd.ret_5d_pct)}</span> : null}
        {fwd?.matured_21d ? <span className="mc-dim">21d {fmtMovePct(fwd.ret_21d_pct)}</span> : null}
      </div>
      <div className="mc-row__tail">
        <span className={`mc-push mc-push--${tone}`} data-testid="mc-push">{pushChipText(ev.push)}</span>
        <details className="mc-src">
          <summary>sources ({ev.n_sources ?? ev.sources.length})</summary>
          <ul className="mc-src__list">
            {ev.sources.map((s, i) => (
              <li key={`${s.provider}-${i}`}>
                <span className="mc-dim mono">{etClock(s.published_et) ?? '—'} ET · {s.provider}{s.source ? ` · ${s.source}` : ''}</span>{' '}
                {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.title ?? s.url}</a> : <span>{s.title ?? '—'}</span>}
              </li>
            ))}
          </ul>
        </details>
        {showTimeline && ev.links?.timeline
          ? <Link className="mc-row__tl" to={ev.links.timeline}>🧬 timeline</Link>
          : null}
      </div>
    </div>
  );
}
