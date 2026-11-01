/* LukPlaybook — 🥇 Luk's 📓 Playbook (2026-11-01, luk spec §3.10). The served sections → items, each with its served
 * `cite_text` and a link when the item carries a `url`. The item `kind` (his | mine | external | his_call |
 * consideration | paraphrase) is a class hook only — the served text says what it is. Every word is SERVED. */
import { lukText, type LukPlaybook as LukPlaybookBlock } from '../lib/luk';

export function LukPlaybook({ playbook }: { playbook?: LukPlaybookBlock | null }) {
  if (!playbook) return null;
  return (
    <div className="luk-playbook" data-testid="luk-playbook">
      {lukText(playbook.title) ? <h3 className="luk-h" data-testid="luk-playbook-title">{playbook.title}</h3> : null}
      {(playbook.sections ?? []).map((sec) => (
        <section key={sec.key} className="luk-pb-section" data-testid={`luk-pb-${sec.key}`}>
          <h4 className="luk-h4">{sec.title}</h4>
          <ul className="luk-pb-items">
            {(sec.items ?? []).map((it, i) => (
              <li key={i} className={`luk-pb-item luk-pb-${(it.kind || 'his').replace(/[^a-z_]/gi, '')}`}
                  data-testid={`luk-pb-item-${sec.key}-${i}`}>
                <span className="luk-pb-text">{it.text}</span>
                {lukText(it.cite_text) ? (
                  <>{' '}{lukText(it.url) ? (
                    <a className="luk-cite" href={it.url!} target="_blank" rel="noopener noreferrer">{it.cite_text}</a>
                  ) : <span className="luk-cite">{it.cite_text}</span>}</>
                ) : lukText(it.url) ? (
                  <>{' '}<a className="luk-cite" href={it.url!} target="_blank" rel="noopener noreferrer">{it.url}</a></>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export default LukPlaybook;
