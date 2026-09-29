#!/usr/bin/env node
/* 📈 Bonde table density — the real-browser layout check (2026-09-28).
 *
 * Ajay 2026-09-28: "Once done can you fix this table too? so much empty
 * space". jsdom loads no CSS and lays nothing out, so no Vitest can prove the
 * fix. This script can: it renders a snapshot of the REAL BondeBoard (written
 * by BondeBoard.layout.test.tsx under BD_LAYOUT_SNAPSHOT=<prefix>) with ALL of
 * the app's stylesheets, in the order main.tsx imports them, inside the same
 * `.app > main.main > .cm-page` chain the page uses, in headless Chrome at
 * [1440, 1280, 1024, 768, 390] px. Each width is a same-origin `srcdoc`
 * iframe (headless Chrome's own window floor is 500px), loaded one at a time
 * so a 200-row snapshot is not held five times over.
 *
 * Two passes per width: every <details> closed, then every one opened.
 *   C1  page not wider than the viewport (html's overflow-x:hidden would cut it)
 *   C2  each section's .bd-scroll box fits its .bd-section (missing box = FAIL)
 *   C3  NO SPILL — every text line and every sized element sits inside its
 *       cell ±1px, and no cell's scrollWidth exceeds its clientWidth
 *   C4  header texts are pairwise non-overlapping and inside their own cells
 *   C4b every head cell's left/right equals the first body row's cell ±1px
 *   C5  scrolled fully right, the last head ("FCF yield") is reachable
 *   C6  (a) the pinned Ticker cell is OPAQUE and matches the painted ancestor
 *       (computed style — hit-testing cannot prove paint); (b) where the box
 *       scrolls, it holds the box's left edge after a full right scroll
 *   C7  each body row's Today cell sits on the ticker's line
 *   C8  row heights per section; at 1440 the explosive section max ≤ 120px,
 *       and median ≤ 90px when it has ≥ 30 rows
 *   C9  EP head: ≤ 41px where no body row has a pivot, ≥ 111px where one does
 *   C10 every non-empty body text node is painted (open pass)
 *   C11 no mid-word break inside the Ticker cell (both passes; a break after
 *       a hyphen is a legal break point, so tokens split after each '-')
 * The closed pass runs C1-C9 and C11; the open pass runs C1-C3, C10 and C11.
 *
 * Usage: node scripts/bonde-layout-probe.mjs <snap.html> [<snap2.html> …]
 * Env: CHROME=<binary>; BD_PROBE_EXTRA_CSS='<rules>' appended after the app's
 * sheets (mutation checks); BD_PROBE_BUDGET=<virtual ms> (default 600000).
 * Exit 1 on any FAIL, 2 on a harness error (a timeout never passes).
 * docs/sepa/bonde_table_density_2026_09_28.md */
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WIDTHS = [1440, 1280, 1024, 768, 390];
const CHROME = process.env.CHROME
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BUDGET = String(Number(process.env.BD_PROBE_BUDGET) || 600000);

const snaps = process.argv.slice(2);
if (!snaps.length) {
  console.error('usage: node scripts/bonde-layout-probe.mjs <snap.html> [<snap2.html> …]');
  process.exit(2);
}

/* The app's stylesheets, in main.tsx's import order — parsed, not listed. */
const main = readFileSync(join(ROOT, 'src/main.tsx'), 'utf8');
const sheets = [...main.matchAll(/^import\s+'(\.\/[^']+\.css)';/gm)].map((m) => m[1]);
if (!sheets.length) {
  console.error('no stylesheet imports found in src/main.tsx');
  process.exit(2);
}
const css = sheets.map((s) => `/* ${s} */\n${readFileSync(join(ROOT, 'src', s), 'utf8')}`).join('\n');
const extra = process.env.BD_PROBE_EXTRA_CSS || '';

/* Runs inside the iframe's parent, once per width. Returns plain data. */
function probe(frame, width) {
  const out = { width, ok: true, fails: [], err: null };
  const fail = (m, first = false) => {
    out.ok = false;
    if (first) out.fails.unshift(m); else if (out.fails.length < 60) out.fails.push(m);
  };
  const doc = frame.contentDocument;
  const win = frame.contentWindow;
  const R = (e) => e.getBoundingClientRect();
  const TOL = 1;
  const sized = (r) => r.width > 0 || r.height > 0;
  const inside = (r, c) => r.left >= c.left - TOL && r.right <= c.right + TOL
    && r.top >= c.top - TOL && r.bottom <= c.bottom + TOL;
  const over = (r, c) => Math.max(c.left - r.left, r.right - c.right, c.top - r.top, r.bottom - c.bottom);
  const cls = (e) => (e && e.className && typeof e.className === 'string')
    ? e.className.split(' ')[0] : (e ? e.tagName.toLowerCase() : '?');
  const slice = (s) => s.replace(/\s+/g, ' ').trim().slice(0, 40);
  /* Content of a CLOSED <details> (its summary excepted) is not painted, but
     Chrome still lays it out when asked for geometry — so the closed pass
     must skip it, or it measures what nobody can see. */
  const unpaintedFold = (n) => {
    for (let e = n.nodeType === 1 ? n : n.parentElement; e; e = e.parentElement) {
      if (e.tagName === 'SUMMARY') return false;
      if (e.tagName === 'DETAILS' && !e.open) return true;
    }
    return false;
  };
  const textNodes = (el) => {
    const w = doc.createTreeWalker(el, 4 /* SHOW_TEXT */);
    const a = [];
    for (let t = w.nextNode(); t; t = w.nextNode()) {
      if ((t.textContent || '').trim() && !unpaintedFold(t)) a.push(t);
    }
    return a;
  };
  const rng = doc.createRange();
  const textRects = (t, a = 0, b = t.length) => {
    rng.setStart(t, a); rng.setEnd(t, b);
    return [...rng.getClientRects()].filter(sized);
  };
  const alpha = (c) => {
    if (!c || c === 'transparent') return 0;
    const m = /\(([^)]*)\)/.exec(c);
    if (!m) return 1;
    const body = m[1];
    if (body.includes('/')) return parseFloat(body.split('/')[1]);
    const parts = body.split(/[\s,]+/).filter(Boolean);
    return parts.length >= 4 && /^rgba?|^hsla?/.test(c) ? parseFloat(parts[3]) : 1;
  };
  const cellsOf = (row) => {
    const out2 = [];
    for (const c of row.children) {
      if (c.classList.contains('bd-metrics')) out2.push(...c.querySelectorAll(':scope > .bd-m'));
      else out2.push(c);
    }
    return out2;
  };
  const med = (a) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor((s.length - 1) / 2)] : null; };

  const secs = [...doc.querySelectorAll('section.bd-section')].filter((s) => s.querySelector('.bd-rows'));
  out.sections = secs.length;
  if (!secs.length) { fail('no section with .bd-rows'); return out; }

  const setDetails = (open) => { for (const d of doc.querySelectorAll('details')) d.open = open; void doc.body.offsetHeight; };
  const counters = () => ({ spill: 0, spillEx: [], headEx: [], midword: 0, midEx: [], unpainted: 0, unEx: [] });

  function commonChecks(tag, cnt) {
    // C1
    const pageW = doc.documentElement.scrollWidth;
    out.page = pageW;
    if (pageW > win.innerWidth) fail(`C1 [${tag}] page ${pageW} wider than viewport ${win.innerWidth} — html would cut it`);
    for (const sec of secs) {
      const key = (sec.querySelector('.bd-h')?.firstChild?.textContent || '?').trim().slice(0, 14);
      // C2
      const box = sec.querySelector('.bd-scroll');
      const scs = win.getComputedStyle(sec);
      const secContent = sec.clientWidth - parseFloat(scs.paddingLeft) - parseFloat(scs.paddingRight);
      if (!box) fail(`C2 [${tag}] ${key}: no scroll box`);
      else if (R(box).width > secContent + TOL) fail(`C2 [${tag}] ${key}: box ${Math.round(R(box).width)} wider than section ${Math.round(secContent)}`);
      // C3
      for (const row of sec.querySelectorAll('.bd-row')) {
        for (const cell of cellsOf(row)) {
          const cr = R(cell);
          let bad = null;
          for (const t of textNodes(cell)) {
            for (const r of textRects(t)) if (!inside(r, cr)) { bad = bad || [slice(t.textContent), over(r, cr)]; }
          }
          for (const e of cell.querySelectorAll('*')) {
            if (unpaintedFold(e)) continue;
            const r = R(e);
            if (sized(r) && !inside(r, cr)) { bad = bad || [`<${cls(e)}>`, over(r, cr)]; }
          }
          if (cell.scrollWidth > cell.clientWidth + TOL && cell.clientWidth > 0) {
            bad = bad || [`scrollWidth ${cell.scrollWidth} > ${cell.clientWidth}`, cell.scrollWidth - cell.clientWidth];
          }
          if (bad) {
            cnt.spill += 1;
            const ex = `"${bad[0]}" in .${cls(cell)} +${Math.round(bad[1])}px`;
            if (row.classList.contains('bd-hdr')) { if (cnt.headEx.length < 2) cnt.headEx.push(`head ${ex}`); }
            else if (cnt.spillEx.length < 3) cnt.spillEx.push(ex);
          }
        }
      }
    }
  }

  function midWord(tag, cnt) {
    // C11
    for (const sym of doc.querySelectorAll('.bd-row:not(.bd-hdr) > .bd-sym')) {
      const cs = win.getComputedStyle(sym);
      const content = sym.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      for (const t of textNodes(sym)) {
        const s = t.textContent;
        // Tokens end AFTER a hyphen: a line break after '-' is a normal
        // browser break point ("2007-03-", "fiscal-"), not a broken word.
        const re = /[^\s-]+-?/g;
        let m;
        while ((m = re.exec(s))) {
          if (m[0].length < 2) continue;
          const rs = textRects(t, m.index, m.index + m[0].length);
          if (!rs.length) continue;
          const w = rs.reduce((k, r) => k + r.width, 0);
          if (w > content) continue;                 // wider than the cell: has to break
          const tops = rs.map((r) => r.top);
          if (Math.max(...tops) - Math.min(...tops) > 2) {
            cnt.midword += 1;
            if (cnt.midEx.length < 3) cnt.midEx.push(`"${m[0].slice(0, 24)}" in .${cls(t.parentElement)} ${Math.round(w)}px`);
          }
        }
      }
    }
  }

  try {
    // ── closed pass
    setDetails(false);
    const c1 = counters();
    commonChecks('closed', c1);
    midWord('closed', c1);

    const ex = secs.find((s) => /Explosive/.test(s.querySelector('.bd-h')?.textContent || '')) || secs[0];
    const exBox = ex.querySelector('.bd-scroll') || ex.querySelector('.bd-rows');
    out.box = exBox.clientWidth;
    out.content = exBox.scrollWidth;
    out.scrolls = exBox.scrollWidth > exBox.clientWidth + 1;
    out.heights = {};
    out.overlaps = 0; out.cellsOff = 0; out.reach = true; out.ep = {}; out.firstLine = 0;
    out.pinBg = 'ok'; out.stickyDx = null;

    for (const sec of secs) {
      const label = (sec.querySelector('.bd-h')?.firstChild?.textContent || '?').trim();
      const key = label.slice(0, 14);
      const rowsEl = sec.querySelector('.bd-rows');
      const hdr = rowsEl.querySelector('.bd-row.bd-hdr');
      const body = [...rowsEl.querySelectorAll('.bd-row:not(.bd-hdr)')];
      // C8
      const hs = body.map((r) => R(r).height);
      out.heights[key] = [Math.round(med(hs)), Math.round(Math.max(...hs)), body.length];
      if (width === 1440 && sec === ex) {
        if (Math.max(...hs) > 120) fail(`C8 ${key}: max row ${Math.round(Math.max(...hs))}px > 120 at 1440`);
        if (body.length >= 30 && med(hs) > 90) fail(`C8 ${key}: median row ${Math.round(med(hs))}px > 90 at 1440 (${body.length} rows)`);
      }
      // C4
      if (hdr) {
        const heads = cellsOf(hdr);
        const rectsOf = heads.map((h) => textNodes(h).flatMap((t) => textRects(t)));
        heads.forEach((h, i) => {
          for (const r of rectsOf[i]) if (!inside(r, R(h))) { out.cellsOff += 1; fail(`C4 ${key}: head "${slice(h.textContent)}" text outside its cell by ${Math.round(over(r, R(h)))}px`); break; }
        });
        for (let i = 0; i < heads.length; i++) for (let j = i + 1; j < heads.length; j++) {
          const hit = rectsOf[i].some((a) => rectsOf[j].some((b) =>
            Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5
            && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5));
          if (hit) { out.overlaps += 1; fail(`C4 ${key}: head "${slice(heads[i].textContent)}" overlaps "${slice(heads[j].textContent)}"`); }
        }
        // C4b
        if (body[0]) {
          const hc = [...hdr.children, ...hdr.querySelectorAll('.bd-metrics > .bd-m')];
          const bc = [...body[0].children, ...body[0].querySelectorAll('.bd-metrics > .bd-m')];
          hc.forEach((h, i) => {
            const b = bc[i];
            if (!b) return;
            const dl = Math.abs(R(h).left - R(b).left); const dr = Math.abs(R(h).right - R(b).right);
            if (dl > TOL || dr > TOL) { out.cellsOff += 1; fail(`C4b ${key}: head .${cls(h)} "${slice(h.textContent)}" [${Math.round(R(h).left)},${Math.round(R(h).right)}] vs cell [${Math.round(R(b).left)},${Math.round(R(b).right)}]`); }
          });
        }
        // C9
        const ph = hdr.querySelector('.bd-pivot');
        if (ph) {
          const pw = Math.round(R(ph).width);
          out.ep[key] = pw;
          const hasPivot = body.some((r) => (r.querySelector('.bd-pivot')?.textContent || '').trim() !== '—');
          if (hasPivot && pw < 111) fail(`C9 ${key}: a row has a pivot but the EP head is ${pw}px (< 111)`);
          if (!hasPivot && pw > 41) fail(`C9 ${key}: no row has a pivot but the EP head is ${pw}px (> 41)`);
        }
      }
      // C7
      for (const r of body) {
        const a = r.querySelector('.bd-sym a.tk-link') || r.querySelector('.bd-sym a');
        const td = r.querySelector('.bd-today');
        if (!a || !td) continue;
        const ar = R(a); const tr = R(td);
        if (Math.min(ar.bottom, tr.bottom) - Math.max(ar.top, tr.top) <= 0) {
          out.firstLine += 1;
          if (out.firstLine <= 3) fail(`C7 ${key}: ${a.textContent} Today at y ${Math.round(tr.top)}, ticker at y ${Math.round(ar.top)}`);
        }
      }
      // C6(a)
      for (const sym of rowsEl.querySelectorAll('.bd-row > .bd-sym')) {
        const bg = win.getComputedStyle(sym).backgroundColor;
        let anc = sym.parentElement; let abg = null;
        while (anc) { const c = win.getComputedStyle(anc).backgroundColor; if (alpha(c) > 0) { abg = c; break; } anc = anc.parentElement; }
        if (alpha(bg) < 1 || bg !== abg) {
          if (out.pinBg === 'ok') fail(`C6a ${key}: pinned Ticker background ${bg} vs painted ancestor ${abg}`);
          out.pinBg = 'NO';
          break;
        }
      }
      // C5 + C6(b)
      const box = sec.querySelector('.bd-scroll');
      const scroller = box || rowsEl;
      const br = R(scroller);
      const visL = br.left + scroller.clientLeft;
      const visR = Math.min(visL + scroller.clientWidth, win.innerWidth);
      const scrolls = scroller.scrollWidth > scroller.clientWidth + 1;
      if (box) { box.scrollLeft = box.scrollWidth; void box.offsetWidth; }
      const lastHead = hdr && hdr.querySelector('.bd-metrics > .bd-m:last-child');
      if (lastHead) {
        const lr = R(lastHead);
        if (lr.right > visR + TOL || lr.right > win.innerWidth + TOL) {
          out.reach = false;
          fail(`C5 ${key}: last head "${slice(lastHead.textContent)}" ends at ${Math.round(lr.right)}, box ${Math.round(visR)}, viewport ${win.innerWidth}`);
        }
      }
      if (box && scrolls) {
        let worst = 0;
        for (const sym of rowsEl.querySelectorAll('.bd-row > .bd-sym')) {
          const dx = Math.abs(R(sym).left - visL);
          worst = Math.max(worst, dx);
        }
        out.stickyDx = Math.max(out.stickyDx ?? 0, Math.round(worst));
        if (worst > TOL) fail(`C6b ${key}: pinned Ticker drifts ${Math.round(worst)}px from the box's left edge after a full right scroll`);
      }
      if (box) { box.scrollLeft = 0; void box.offsetWidth; }
    }

    // ── open pass
    setDetails(true);
    const c2 = counters();
    commonChecks('open', c2);
    midWord('open', c2);
    // C10
    for (const row of doc.querySelectorAll('.bd-row:not(.bd-hdr)')) {
      for (const t of textNodes(row)) {
        if (!textRects(t).some((r) => r.width > 0 && r.height > 0)) {
          c2.unpainted += 1;
          if (c2.unEx.length < 3) c2.unEx.push(`"${slice(t.textContent)}" in .${cls(t.parentElement)}`);
        }
      }
    }
    setDetails(false);

    out.spill = `${c1.spill}/${c2.spill}`;
    out.midword = `${c1.midword}/${c2.midword}`;
    out.unpainted = c2.unpainted;
    if (c1.spill) fail(`C3 [closed] ${c1.spill} cell(s) spill: ${[...c1.spillEx, ...c1.headEx].join('; ')}`, true);
    if (c2.spill) fail(`C3 [open] ${c2.spill} cell(s) spill: ${[...c2.spillEx, ...c2.headEx].join('; ')}`, true);
    if (c1.midword) fail(`C11 [closed] ${c1.midword} mid-word break(s): ${c1.midEx.join('; ')}`, true);
    if (c2.midword) fail(`C11 [open] ${c2.midword} mid-word break(s): ${c2.midEx.join('; ')}`, true);
    if (c2.unpainted) fail(`C10 ${c2.unpainted} unpainted text node(s): ${c2.unEx.join('; ')}`, true);
  } catch (e) {
    out.ok = false;
    out.err = `probe threw: ${e && e.message}`;
  }
  return out;
}

const attr = (s) => JSON.stringify(s).replace(/<\//g, '<\\/');
let failed = 0;
let harness = 0;
console.log(`stylesheets (main.tsx order): ${sheets.join(', ')}${extra ? `\nextra CSS: ${extra}` : ''}`);
for (const snapPath of snaps) {
  const snapshot = readFileSync(snapPath, 'utf8');
  const child = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>${css}\n${extra}</style></head><body>
<div class="app"><main class="main"><div class="cm-page">${snapshot}</div></main></div>
</body></html>`;
  const parent = `<!doctype html><html><head><meta charset="utf-8"><script>
${probe.toString()}
const CHILD = ${attr(child)};
const WIDTHS = ${JSON.stringify(WIDTHS)};
window.__res = [];
function finish() {
  document.getElementById('out').textContent = JSON.stringify(window.__res);
  document.getElementById('state').textContent = 'DONE';
}
function next() {
  const w = WIDTHS[window.__res.length];
  if (w == null) { finish(); return; }
  const f = document.createElement('iframe');
  f.width = String(w); f.height = '1200'; f.style.border = '0'; f.style.display = 'block';
  f.onload = () => {
    let r;
    try { r = probe(f, w); } catch (e) { r = { width: w, ok: false, fails: [], err: 'probe threw: ' + e.message }; }
    window.__res.push(r);
    f.remove();
    setTimeout(next, 0);
  };
  f.srcdoc = CHILD;
  document.body.appendChild(f);
}
window.addEventListener('load', next);
</script></head><body><pre id="state">RUNNING</pre><pre id="out">[]</pre></body></html>`;

  const dir = mkdtempSync(join(tmpdir(), 'bd-probe-'));
  const page = join(dir, 'probe.html');
  writeFileSync(page, parent, 'utf8');
  let dom;
  try {
    dom = execFileSync(CHROME, [
      '--headless=new', '--disable-gpu', '--hide-scrollbars=false',
      '--window-size=1600,1000', `--virtual-time-budget=${BUDGET}`,
      '--dump-dom', `file://${page}`,
    ], { encoding: 'utf8', timeout: 900000, maxBuffer: 1024 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
  } catch (e) {
    console.error(`headless Chrome failed on ${snapPath}: ${e.message}`);
    harness += 1;
    continue;
  }
  const state = /<pre id="state">([^<]*)<\/pre>/.exec(dom)?.[1];
  const m = /<pre id="out">([\s\S]*?)<\/pre>/.exec(dom);
  const unesc = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&');
  const res = m ? JSON.parse(unesc(m[1])) : [];
  console.log(`\n### ${basename(snapPath)}${state !== 'DONE' ? ' — HARNESS: did not finish (raise BD_PROBE_BUDGET)' : ''}`);
  console.log('| viewport | box / content | scrolls | page | spill (closed/open) | head overlaps | heads over cells | last head reachable | pin bg / sticky Δpx | EP px | row h median / max (explosive) | first line | unpainted | mid-word (closed/open) | result |');
  console.log('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|');
  for (const r of res) {
    const exKey = Object.keys(r.heights || {}).find((k) => /Explosive/.test(k)) || Object.keys(r.heights || {})[0];
    const h = r.heights?.[exKey];
    const ep = Object.values(r.ep || {}).join('/');
    console.log(`| ${r.width} | ${r.box} / ${r.content} | ${r.scrolls ? 'yes' : 'no'} | ${r.page} | ${r.spill} | ${r.overlaps} | ${r.cellsOff === 0 ? 'yes' : `NO (${r.cellsOff})`} | ${r.reach ? 'yes' : 'NO'} | ${r.pinBg} / ${r.stickyDx ?? 'n/a'} | ${ep} | ${h ? `${h[0]} / ${h[1]}` : '—'} | ${r.firstLine === 0 ? 'yes' : `NO (${r.firstLine})`} | ${r.unpainted} | ${r.midword} | ${r.ok ? 'PASS' : 'FAIL'} |`);
  }
  for (const r of res) {
    const per = Object.entries(r.heights || {}).map(([k, v]) => `${k} ${v[0]}/${v[1]} (n=${v[2]})`).join(' · ');
    console.log(`  ${r.width}: row h median/max — ${per}`);
    if (r.err) console.log(`    ✗ ${r.err}`);
    for (const f of r.fails || []) console.log(`    ✗ ${f}`);
  }
  const missing = WIDTHS.filter((w) => !res.some((r) => r.width === w));
  if (missing.length || state !== 'DONE') {
    console.log(`    ✗ HARNESS: no result for ${missing.join(', ') || '(state)'} px`);
    harness += 1;
  }
  if (res.some((r) => r.err)) harness += 1;
  failed += res.filter((r) => !r.ok).length;
}
if (harness) { console.error(`\nharness error on ${harness} snapshot(s)`); process.exit(2); }
if (failed) { console.error(`\n${failed} width-run(s) FAILED`); process.exit(1); }
console.log('\nall widths passed on every snapshot');
