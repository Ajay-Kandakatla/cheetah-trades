/* GgHighSi — 🩳 the High SI sub on 🚩 Gajjala's 5-min tab (2026-11-23, high SI spec §3.8, WP fe-sub).
 *
 * Ajay 2026-11-23 (voice-typed): "Can you create a tab similarly like Divergent with high charging tested, SHO tag, and low
 * floats similar to what we've done in Divergent tab under Gazilla?" [voice typing: "high charging tested" = high short
 * interest, "Gazilla" = Gajjala] · "New tab like divergence*"
 *
 * GgHighSiPanel — above the cards, drawn from the SERVED block only (high_si.block) on the generic gg-dv* classes. ALWAYS
 * VISIBLE: the served title, his words, the counts line, the adds line, the as-of line, the 🔒 line, the push sentence, the
 * order note, the shown line, the empty line, the listings that drew no card, the served fault line. FOLDED (one <details>,
 * so the header stays short above the cards on a phone): the served rule, the cohort sentence and the three name lists
 * (over the cap · the two float reads disagree · no tier word). The served honesty LAST, always visible.
 * The push sentence is printed as served — the panel knows nothing of the push mode (with the push off it is the 🔕 line).
 * 2026-11-24: on the 🚩 board the whole panel sits inside the sub's closed ⓘ fold (GajjalaBoard); 'always visible'
 * here means outside this panel's own rule fold.
 * The listed names are ordinary served tiles (the house card grid). Information only, never an entry. UNMEASURED.
 * This file types no word and no number except the ⓘ fallback summary; every string passes the servedText guard (a NaN /
 * undefined / number / empty string prints nothing).
 *
 * 2026-11-24 (ggclean spec §3.6) — Ajay: "Collapse all of this too" (the 🩳 panel text). GgHighSiState: the state lines
 * the board prints OUTSIDE the closed sub fold (GgSubState) — the empty line, the listings that drew no card, the served
 * fault line and the ⛔ SSR list's served fault line — drawn by the SAME selector as the panel (`listed`), so the two
 * can never disagree. It prints only while the sub's fold is closed; open, the panel shows the same lines in place.
 *
 * 2026-11-26 (spec sitrack §3.7 B, [OC1]) — Ajay: "I want us to track these patters for future from SI like a track recprd
 * with in SI stocks itself". The served 🏁 SI track record (GgSiTrackSection) is mounted in the PANEL right after the ⛔
 * new-SSR section, on the SAME line (GgSsrNew.test.tsx pins the ⛔ mount as one digit-free line between the faults line and
 * the rule fold) — inside the sub's closed ⓘ fold, never on the landing; GgHighSiState is unchanged. */
import { Link } from 'react-router-dom';
import { ggHref, type GgHighSiBlock } from '../lib/gajjala';
import { GgSsrNewSection } from './GgSsrNew';
import { GgSiTrackSection } from './GgSiTrack';
import { GgSubState, type GgSubStateLine } from './GgFold';
import '../styles/gajjala.css';

/** The board's servedText guard (GajjalaBoard keeps its trailing export line fixed — copied, as GgDiverging does): a served
 *  line prints only when it is a non-empty string — NaN / undefined / null / a number prints nothing. */
function servedText(v: unknown): v is string {
  return typeof v === 'string' && v.trim() !== '';
}

/** One always-visible served line on the gg-dv classes; nothing when the value is not a served string. */
function Line({ v, testid, muted = true }: { v: unknown; testid: string; muted?: boolean }) {
  if (!servedText(v)) return null;
  return <p className={muted ? 'gg-dv-line gg-muted' : 'gg-dv-line'} data-testid={testid}>{v}</p>;
}

/** The ONE chartless filter + empty test, shared by the panel and GgHighSiState (2026-11-24, ggclean §3.6). */
function listed(block: GgHighSiBlock) {
  /* 2026-11-23 refix: the served `text` names the ticker ("🩳 SYM listed · chart not stored"); the served `state_label`
   * ("🩳 High short interest") does not, so it is only the fallback. A line prints when either is served — a name whose
   * read raised (state_label null) still prints its served text. */
  const chartless = (Array.isArray(block.chartless) ? block.chartless : [])
    .filter((c) => !!c && typeof c === 'object' && (servedText(c.text) || servedText(c.state_label)));
  const showEmpty = block.n === 0 && !chartless.length && servedText(block.empty_text);
  return { chartless, showEmpty };
}

/** 🩳 the state lines outside the closed sub fold (GgSubState): empty → chartless → faults → the ⛔ SSR fault, in the
 *  panel's own order and under the panel's own rules. A null / absent block draws nothing. */
export function GgHighSiState({ block }: { block: GgHighSiBlock | null | undefined }) {
  if (!block || typeof block !== 'object') return null;
  const { chartless, showEmpty } = listed(block);
  const lines: GgSubStateLine[] = [];
  if (showEmpty && servedText(block.empty_text)) lines.push({ kind: 'empty', key: 'empty', text: block.empty_text });
  chartless.forEach((c, i) => {
    const words = servedText(c.text) ? c.text : c.state_label;
    if (servedText(words)) {
      lines.push({ kind: 'chartless', key: servedText(c.symbol) ? c.symbol : String(i), text: words, href: c.href });
    }
  });
  if (servedText(block.faults_text)) lines.push({ kind: 'faults', key: 'faults', text: block.faults_text });
  const ssr = block.ssr_new && typeof block.ssr_new === 'object' ? block.ssr_new.fault_text : null;
  if (servedText(ssr)) lines.push({ kind: 'fault', key: 'ssr', text: ssr });
  return <GgSubState lines={lines} />;
}

/** 🩳 the panel above the cards. A null / absent block (an older API, or a read fault — the board's served empty note says
 *  so) draws nothing. */
export function GgHighSiPanel({ block }: { block: GgHighSiBlock | null | undefined }) {
  if (!block || typeof block !== 'object') return null;
  const { chartless, showEmpty } = listed(block);
  const folded = [block.rule_text, block.cohort_text, block.excluded_text, block.disagree_text, block.no_tier_text]
    .some(servedText);
  return (
    <section className="gg-dv" data-testid="gg-hs">
      {servedText(block.title) ? <h3 className="gg-dv-title" data-testid="gg-hs-title">{block.title}</h3> : null}
      {servedText(block.ask_text) ? (
        <blockquote className="gg-dv-ask gg-muted" data-testid="gg-hs-ask">{block.ask_text}</blockquote>
      ) : null}
      <Line v={block.counts_text} testid="gg-hs-counts" />
      {/* 🩳 2026-11-24 (spec sidilute §3.6 / §3.7 [C7]): the served line naming the names that were High / EXTREME on the
       * float on file but are not tiered (that float is stale or across a split) — printed as served, right after the counts. */}
      <Line v={block.basis_text} testid="gg-hs-basis" />
      <Line v={block.adds_text} testid="gg-hs-adds" />
      <Line v={block.asof_text} testid="gg-hs-asof" />
      <Line v={block.sho_text} testid="gg-hs-sho" />
      <Line v={block.push_text} testid="gg-hs-push" />
      <Line v={block.order_note} testid="gg-hs-order" />
      <Line v={block.shown_text} testid="gg-hs-shown" />
      {showEmpty ? <p className="gg-dv-line" data-testid="gg-hs-empty">{block.empty_text}</p> : null}
      {chartless.map((c, i) => {
        const href = ggHref(c.href);
        const key = servedText(c.symbol) ? c.symbol : String(i);
        const words = servedText(c.text) ? c.text : c.state_label;
        return (
          <p key={`${key}-${i}`} className="gg-dv-line gg-dv-chartless" data-testid={`gg-hs-chartless-${key}`}>
            {href ? <Link to={href}>{words}</Link> : words}
          </p>
        );
      })}
      {servedText(block.faults_text) ? <p className="gg-dv-line cm-note" data-testid="gg-hs-faults">{block.faults_text}</p> : null}
      <GgSsrNewSection block={block.ssr_new} /><GgSiTrackSection block={block.si_track} />
      {folded ? (
        <details className="gg-dv-rule" data-testid="gg-hs-rule">
          <summary>{servedText(block.rule_label) ? block.rule_label : 'ⓘ'}</summary>
          {servedText(block.rule_text) ? <p className="gg-dv-line" data-testid="gg-hs-rule-text">{block.rule_text}</p> : null}
          <Line v={block.cohort_text} testid="gg-hs-cohort" />
          <Line v={block.excluded_text} testid="gg-hs-excluded" />
          <Line v={block.disagree_text} testid="gg-hs-disagree" />
          <Line v={block.no_tier_text} testid="gg-hs-notier" />
        </details>
      ) : null}
      {servedText(block.honesty) ? <p className="gg-dv-line gg-muted" data-testid="gg-hs-honesty">{block.honesty}</p> : null}
    </section>
  );
}
