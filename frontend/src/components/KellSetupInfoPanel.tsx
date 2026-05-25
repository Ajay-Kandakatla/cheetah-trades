/* KellSetupInfoPanel — context-sensitive sticky sidebar for the /kell
 * page. Mirror of SepaSetupInfoPanel: tier label, one-line pitch,
 * Entry/Stop/Target rules, hold time, risk note, and (where applicable)
 * a real-world example from market history.
 *
 * Content sourced from Oliver Kell's "Victory in Stock Trading" (2021),
 * Cycle of Price Action chapter (pp. 14-27). The rules and tiers are
 * Kell's published criteria, not invented. Page references in each
 * blurb point back to the specific book pages.
 */
import type { KellTab } from './KellSetupTabs';

const TIER_COLOR: Record<string, string> = {
  safe:        '#22c55e',
  safe_mod:    '#84cc16',
  moderate:    '#facc15',
  aggressive:  '#fb923c',
  defensive:   '#ef4444',
  neutral:     '#9aa8c8',
};

type InfoBlock = {
  title:     string;
  tier:      string;
  tierLabel: string;
  blurb:     string;
  entry:     string;
  stop:      string;
  target:    string;
  hold:      string;
  riskNote:  string;
  example?:  string;
};

const INFO: Record<KellTab, InfoBlock> = {
  all: {
    title:     'All Kell setups',
    tier:      'neutral',
    tierLabel: 'COMBINED FEED',
    blurb:     "Every detection across the six Cycle of Price Action scanners. Sorted by R:R within each kind — drill into a specific tab for pattern-specific entry rules.",
    entry:     'Per-card trigger — varies by pattern',
    stop:      'Per-card stop — pattern-specific',
    target:    "Per-card target — Kell's typical first scale",
    hold:      'Pattern-specific',
    riskNote:  "Combined view — each Kell pattern has its own risk profile. Open the per-pattern tab on the left to see the canonical rules and risk notes.",
  },

  base_n_break: {
    title:     "Base n' Break",
    tier:      'safe',
    tierLabel: 'SAFE',
    blurb:     "Kell's lower-risk consolidation breakout. After a confirmed uptrend (10 EMA > 20 EMA > 50 SMA), the stock builds a 5-15 day base ON the 10/20 EMA cluster with volume drying, then breaks the range on >1.3× volume. Book pp. 18-19, 39: 'the first consolidation into the 10/20 EMA … a lower risk area to buy against the moving averages.'",
    entry:     'Base pivot (highest high of the base) + 1¢',
    stop:      'min(20 EMA, base low) − 1¢',
    target:    'Trigger × 1.10 (typical first leg)',
    hold:      '2–10 trading days (short window — already broken out)',
    riskNote:  "Breakout failures cluster — if the stock closes back below the pivot on a subsequent day on rising volume, the breakout failed and you exit immediately. Per pp. 48 'Breakout Day Low' rule: violation of the breakout-day low is the kill switch.",
    example:   "$TWLO Daily (book p. 39 [D/E]) — multi-week consolidations above the 10/20 EMA followed by breakouts on volume",
  },

  ema_crossback: {
    title:     'EMA Crossback / Pullback',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    blurb:     "Kell's lowest-risk add point. Inside an established uptrend (10 EMA rising 10+ days, closes above 10 EMA in 10 of last 15 sessions), price pulls back to tag the 10 or 20 EMA on LIGHT volume and rebounds with a bullish close back above the 10 EMA. Book p. 27 [Q]: 'a low risk-spot to add to the position or raise stops and continue to hold.'",
    entry:     "Today's bar high + 1¢ on confirmation day",
    stop:      'min(20 EMA, last 3-day low) − 1¢',
    target:    'Trigger × 1.08 (typical continuation)',
    hold:      '3–10 trading days',
    riskNote:  "If volume on the pullback is HEAVY (not light), this isn't a constructive pullback — institutions are distributing. Skip. Per pp. 49 '10/20 EMA Trailing Stop': a CLOSE below the 20 EMA invalidates the pullback thesis.",
    example:   "$TSLA Phase 3 (book pp. 26-27 [Q]) — the canonical EMA pullback entry after the $TSLA Wedge Pop on S&P inclusion catalyst",
  },

  wedge_pop: {
    title:     'Wedge Pop',
    tier:      'moderate',
    tierLabel: 'MODERATE',
    blurb:     "Kell's Phase-2 turn — the FIRST reclaim of the 10/20 EMA cluster after a downtrend. Price has been trending down and tightening into the EMAs in a wedge of higher lows; today's bar closes above BOTH EMAs (first such close in 10 sessions). Book pp. 17, 23-24, 26 [O]: 'Price pops back through the 10/20 EMA on the CATALYST … this is a new traditional flat base pattern.'",
    entry:     "Today's bar high + 1¢",
    stop:      'min(lows[−7:]) (wedge floor)',
    target:    "Today's close × 1.10",
    hold:      "1–4 trading days to first base, then re-evaluate as Base n' Break",
    riskNote:  "First reclaims fail often — wait for a confirmed close above both EMAs and size SMALL. Per pp. 47-49 stop-loss canon, if today's low is broken in the next session, the Wedge Pop is failing and you exit.",
    example:   "$TSLA late-2019 S&P inclusion (book p. 26 [O]), $LVGO Mar 2020 from COVID lows (book pp. 32-33)",
  },

  reversal_extension: {
    title:     'Reversal Extension',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    blurb:     "Phase-1 capitulation bottom. After 5+ days of closes below the 10 EMA, price extends ≥5% below the 10 EMA today, then prints a bullish reversal bar on >1.5× volume that either engulfs the prior bar's high or closes in the upper half of range. Book pp. 16, 22-23: the moment supply is exhausted.",
    entry:     'Reversal bar high + 1¢',
    stop:      'Reversal bar low − 1¢',
    target:    "20 EMA (Kell's first profit target — pp. 26-27)",
    hold:      '3–10 days to the 20 EMA',
    riskNote:  "Catching the bottom is the riskiest spot in the entire cycle. Size SMALLER than safer setups and accept that many of these fail. The Wedge Pop (Phase 2) is the cleaner second-chance entry — Kell explicitly recommends waiting for that confirmation if you missed the reversal bar.",
    example:   "$LVGO Mar 2020 (book pp. 32-33 [D/E] — the 2B Reversal that became the $LVGO leadership trade)",
  },

  exhaustion_extension: {
    title:     'Exhaustion Extension · WARNING',
    tier:      'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
    blurb:     "NOT an entry. After an established uptrend (closes above 10 EMA for 20+ of last 30 sessions), today's close is ≥8% above the 10 EMA on >2× volume with a wide-range bar (range > 5% of close) that either closes in the upper half OR is a bearish reversal. Book pp. 19, 25, 40: the 2nd or 3rd such extension is the canonical 'sell into strength' moment.",
    entry:     '— (NO ENTRY — this is a sell signal)',
    stop:      '— (no stop applies)',
    target:    '— (no target — TAKE PROFITS instead)',
    hold:      "— (act now: lighten 1/3 to 1/2 of the position)",
    riskNote:  "FIRST extension can often be held through (Kell p. 40 [F]). SECOND extension is where you START scaling out. THIRD is the canonical lock-in. The `extension_count` field in meta tells you which one this is. Don't try to SHORT — the bounce can be violent before the real top (book p. 53 'To Short or Not to Short').",
    example:   "$TSLA Aug 2020 third extension into the split (book p. 27 [P/S]), GME Jan 2021, NVDA blow-off bars 2024",
  },

  wedge_drop: {
    title:     'Wedge Drop · WARNING',
    tier:      'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
    blurb:     "NOT an entry. CONFIRMATION that the previous Exhaustion Extension was the real top. There was an extension 5-15 sessions ago; since then price wedged higher in a tight range; TODAY price closes below BOTH the 10 EMA and 20 EMA (first such close in 10 sessions) on a bearish bar with >1.3× volume. Book pp. 18, 20, 24, 41 [U/J]: 'officially ending the uptrend cycle.'",
    entry:     '— (NO ENTRY — this is a sell signal)',
    stop:      '— (no stop applies)',
    target:    '— (no target — exit remaining position)',
    hold:      "— (act now: exit any remaining shares from the cycle)",
    riskNote:  "Wedge Drop is the second SELL signal in the cycle — if you already trimmed on Exhaustion Extension, this is the moment to exit the rest. Trying to hold for a bounce 'because the stock had a great run' is how Kell-style trends become buy-and-hope disasters. Per book p. 53, raise cash rather than short.",
    example:   "$TSLA gap-down post-earnings (book p. 27 [U]), $TWLO post-blowoff (book pp. 38-39 [I/J])",
  },
};

interface Props {
  activeTab: KellTab;
}

export function KellSetupInfoPanel({ activeTab }: Props) {
  const info = INFO[activeTab];
  if (!info) return null;
  const color = TIER_COLOR[info.tier] || TIER_COLOR.neutral;
  return (
    <aside
      style={{
        flex:           '0 0 320px',
        position:       'sticky',
        top:            '1rem',
        alignSelf:      'flex-start',
        padding:        '1rem 1.1rem',
        background:     'rgba(20,20,22,0.65)',
        border:         `1px solid ${color}33`,
        borderLeft:     `4px solid ${color}`,
        borderRadius:   8,
        color:          '#cfcfd4',
        fontSize:       '0.84rem',
        lineHeight:     1.55,
      }}
      aria-label={`Kell setup info for ${info.title}`}
    >
      <div
        style={{
          fontSize:       '0.68rem',
          letterSpacing:  '0.1em',
          textTransform:  'uppercase',
          color:          color,
          fontWeight:     700,
          marginBottom:   4,
        }}
      >
        {info.tierLabel}
      </div>
      <h3
        style={{
          margin:    '0 0 0.6rem 0',
          fontSize:  '1.08rem',
          fontWeight: 700,
          color:     '#f3e8c8',
        }}
      >
        {info.title}
      </h3>
      <p style={{ margin: '0 0 0.9rem 0', fontSize: '0.86rem' }}>{info.blurb}</p>

      <Row label="Entry"  value={info.entry} />
      <Row label="Stop"   value={info.stop}   accent="#ef4444" />
      <Row label="Target" value={info.target} accent="#22c55e" />
      <Row label="Hold"   value={info.hold} />

      <div
        style={{
          marginTop:    '0.85rem',
          padding:      '0.5rem 0.65rem',
          background:   'rgba(239,68,68,0.08)',
          border:       '1px solid rgba(239,68,68,0.25)',
          borderRadius: 6,
          fontSize:     '0.76rem',
          color:        '#fca5a5',
        }}
      >
        <strong style={{ color: '#fca5a5' }}>⚠ Risk: </strong>{info.riskNote}
      </div>

      {info.example && (
        <div
          style={{
            marginTop: '0.7rem',
            fontSize:  '0.72rem',
            color:     '#9a9aa3',
            fontStyle: 'italic',
          }}
        >
          Examples: {info.example}
        </div>
      )}
    </aside>
  );
}

function Row({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div
      style={{
        display:        'grid',
        gridTemplateColumns: '64px 1fr',
        gap:            '0.5rem',
        margin:         '0.25rem 0',
        fontSize:       '0.78rem',
      }}
    >
      <span
        style={{
          color:         '#9a9aa3',
          textTransform: 'uppercase',
          fontSize:      '0.66rem',
          letterSpacing: '0.06em',
          paddingTop:    2,
        }}
      >
        {label}
      </span>
      <span style={{ color: accent || '#cfcfd4' }}>{value}</span>
    </div>
  );
}
