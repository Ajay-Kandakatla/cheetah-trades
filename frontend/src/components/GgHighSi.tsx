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
 * The listed names are ordinary served tiles (the house card grid). Information only, never an entry. UNMEASURED.
 * This file types no word and no number except the ⓘ fallback summary; every string passes the servedText guard (a NaN /
 * undefined / number / empty string prints nothing). */
import { Link } from 'react-router-dom';
import { ggHref, type GgHighSiBlock } from '../lib/gajjala';
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

/** 🩳 the panel above the cards. A null / absent block (an older API, or a read fault — the board's served empty note says
 *  so) draws nothing. */
export function GgHighSiPanel({ block }: { block: GgHighSiBlock | null | undefined }) {
  if (!block || typeof block !== 'object') return null;
  /* 2026-11-23 refix: the served `text` names the ticker ("🩳 SYM listed · chart not stored"); the served `state_label`
   * ("🩳 High short interest") does not, so it is only the fallback. A line prints when either is served — a name whose
   * read raised (state_label null) still prints its served text. */
  const chartless = (Array.isArray(block.chartless) ? block.chartless : [])
    .filter((c) => !!c && typeof c === 'object' && (servedText(c.text) || servedText(c.state_label)));
  const showEmpty = block.n === 0 && !chartless.length && servedText(block.empty_text);
  const folded = [block.rule_text, block.cohort_text, block.excluded_text, block.disagree_text, block.no_tier_text]
    .some(servedText);
  return (
    <section className="gg-dv" data-testid="gg-hs">
      {servedText(block.title) ? <h3 className="gg-dv-title" data-testid="gg-hs-title">{block.title}</h3> : null}
      {servedText(block.ask_text) ? (
        <blockquote className="gg-dv-ask gg-muted" data-testid="gg-hs-ask">{block.ask_text}</blockquote>
      ) : null}
      <Line v={block.counts_text} testid="gg-hs-counts" />
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
