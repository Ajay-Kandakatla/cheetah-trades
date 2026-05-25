import { useEffect } from 'react';
import { useAiReview } from '../hooks/useAiReview';

type Props = { symbol: string; onClose: () => void };

/**
 * AiReviewModal — calls /day/explain/{symbol} on mount and renders Gemma's
 * structured review (setup_quality 1-10, pattern, rationale, risks, veto).
 */
export function AiReviewModal({ symbol, onClose }: Props) {
  const { data, loading, error, review } = useAiReview();

  useEffect(() => {
    review(symbol);
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [symbol, review, onClose]);

  const rev = data?.review;
  const veto = rev?.veto;

  // Quality color: 1-3 bad, 4-6 warn, 7-10 good
  const quality = rev?.setup_quality ?? 0;
  const qmood = quality >= 7 ? 'good' : quality >= 4 ? 'warn' : 'bad';

  return (
    <div className="regime-modal-backdrop" onClick={onClose} role="presentation">
      <div className="regime-modal ai-review-modal" role="dialog" aria-modal="true"
           aria-label={`Gemma review of ${symbol}`} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="regime-modal__close" onClick={onClose} aria-label="Close">×</button>

        <header className={`ai-review-modal__head ai-review-modal__head--${veto ? 'bad' : qmood}`}>
          <div className="ai-review-modal__head-line">
            <span className="ai-review-modal__emoji" aria-hidden>🤖</span>
            <h2 className="ai-review-modal__title">Gemma's read · <strong>{symbol}</strong></h2>
            {data?.from_cache && <span className="ai-review-modal__cache mono">cached</span>}
          </div>
          {data?.model && (
            <div className="ai-review-modal__sub mono">
              {data.model} · {data.latency_sec}s · {data.input_tokens}→{data.output_tokens} tok
            </div>
          )}
        </header>

        {loading && (
          <div className="ai-review-modal__loading">
            <div className="ai-review-modal__spinner" />
            Gemma is reading the tape… (~3-8s)
          </div>
        )}

        {error && !loading && (
          <div className="ai-review-modal__error">
            <strong>Couldn't get a review.</strong> {error}
          </div>
        )}

        {data && data.enabled === false && (
          <div className="ai-review-modal__error">
            <strong>LLM not configured.</strong>
            <p>{data.message}</p>
          </div>
        )}

        {data && data.message && data.enabled !== false && !rev && (
          <div className="ai-review-modal__loading">{data.message}</div>
        )}

        {rev && (
          <>
            <section className="ai-review-modal__section">
              <div className="ai-review-modal__quality-row">
                <div className="ai-review-modal__quality">
                  <div className="ai-review-modal__quality-label">Setup quality</div>
                  <div className={`ai-review-modal__quality-num ai-review-modal__quality-num--${qmood}`}>
                    {rev.setup_quality}<span className="ai-review-modal__quality-denom">/10</span>
                  </div>
                </div>
                <div className="ai-review-modal__quality-bar">
                  <div className={`ai-review-modal__quality-fill ai-review-modal__quality-fill--${qmood}`}
                       style={{ width: `${(rev.setup_quality ?? 0) * 10}%` }} />
                </div>
              </div>

              {rev.pattern && (
                <div className="ai-review-modal__pattern">
                  <span className="ai-review-modal__pattern-label">Pattern</span>
                  <span className="ai-review-modal__pattern-name">{rev.pattern}</span>
                </div>
              )}

              {rev.veto && (
                <div className="ai-review-modal__veto">
                  <strong>⛔ Veto:</strong> {rev.veto_reason || 'Setup not actionable.'}
                </div>
              )}
            </section>

            {rev.rationale && (
              <section className="ai-review-modal__section">
                <h3>Why</h3>
                <p className="ai-review-modal__rationale">{rev.rationale}</p>
              </section>
            )}

            {rev.risks && rev.risks.length > 0 && (
              <section className="ai-review-modal__section">
                <h3>Risks</h3>
                <ul className="regime-modal__list regime-modal__list--bad">
                  {rev.risks.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </section>
            )}

            {rev.raw && (
              <section className="ai-review-modal__section">
                <h3>Raw model output</h3>
                <pre className="ai-review-modal__raw">{rev.raw}</pre>
              </section>
            )}

            <footer className="ai-review-modal__footer">
              Gemma is a second opinion, not a verdict. Cross-check with the
              numbers and the chart before clicking buy. Reviews cached 5
              minutes per (symbol, last-bar).
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
