import { useState } from 'react';
import { SepaMovers } from '../components/SepaMovers';
import { Calibration } from '../components/Calibration';
import { InfoButton } from '../components/InfoButton';

/* ==========================================================================
   /track — historical timeline view of how the app's signals are evolving.
   Phase 1 ships SEPA Movers (entered / exited / score deltas).
   Phase 2 will add Catalyst History.  Phase 3 adds Predictions Ledger.
   ========================================================================== */

const TrackInfo = (
  <>
    <p>
      <strong>Track</strong> answers two questions you keep asking the SEPA list:
      <em> who's new today, and who fell off?</em>
    </p>
    <p>
      Every scan run is persisted, so you can compare any two dates and see
      what entered the candidate set, what dropped out, and which scores moved
      most. Use the date selector inside each section to scrub backwards in
      time.
    </p>
    <p className="mono" style={{ opacity: 0.7 }}>
      Phase 1 of 3 — SEPA only. Catalyst history and prediction-accuracy
      tracking land in the next sessions.
    </p>
  </>
);

type Tab = 'sepa' | 'calibration' | 'catalyst' | 'predictions';

export default function TrackPage() {
  const [tab, setTab] = useState<Tab>('calibration');

  return (
    <div className="track-page">
      <div className="track-page__title">
        <InfoButton title="Track">{TrackInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ 11 — Timeline</div>
          <h1 className="display track-page__h1">Track</h1>
          <p className="lede">
            What changed and was it right? — historical diffs across SEPA,
            catalysts, and predictions.
          </p>
        </div>
      </div>

      <div className="track-tabs">
        <button
          className={`track-tab ${tab === 'calibration' ? 'is-active' : ''}`}
          onClick={() => setTab('calibration')}
        >
          Calibration · accuracy
        </button>
        <button
          className={`track-tab ${tab === 'sepa' ? 'is-active' : ''}`}
          onClick={() => setTab('sepa')}
        >
          SEPA Movers
        </button>
        <button
          className={`track-tab ${tab === 'catalyst' ? 'is-active' : ''}`}
          onClick={() => setTab('catalyst')}
          disabled
          title="Coming next session"
        >
          Catalyst History
        </button>
        <button
          className={`track-tab ${tab === 'predictions' ? 'is-active' : ''}`}
          onClick={() => setTab('predictions')}
          disabled
          title="Coming after catalyst history"
        >
          Predictions Ledger
        </button>
      </div>

      {tab === 'calibration' && <Calibration />}
      {tab === 'sepa' && <SepaMovers />}
      {(tab === 'catalyst' || tab === 'predictions') && (
        <div className="movers-empty">
          <p>{tab === 'catalyst' ? 'Catalyst history' : 'Predictions ledger'} ships in the next phase.</p>
        </div>
      )}
    </div>
  );
}
