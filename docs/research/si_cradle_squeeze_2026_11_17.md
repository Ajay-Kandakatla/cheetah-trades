# 🛏 SI × previous-day highs × cradle — second-half squeeze study (2026-11-17)

Ajay 2026-11-17, verbatim: "Can you do analysis for me if there are cetrain stocks with short interest  on average of certain percentage.. Previous day had highs..  Then they look like cradle pattern, they grow immensely EOD. Due to short squeeze..  I think this is a thing with reversal squeeze but they would usualy grow back second half of the day if they thesis checks out I want you build a new tab but do evaluate this one some previous stocks please"

- Script: `backend/scripts/si_cradle_squeeze_study.py` (`fetch | analyze | render | selftest`), tests `backend/tests/test_si_cradle_squeeze_study.py`.
- Design, results, report: `/Users/ajay/clinet-test/eod-audits/research/2026-11-17_si_cradle_squeeze/` (design sha256 8634c43f…, report.md, out/results.json).
- Verdict: **UNMEASURED-too-small** (OOS 27 dates < 30) with the direction AGAINST the thesis: the top short-interest third (≥ 2.87 % of float) on cradle days lost −3.65 % net to 16:00 [−7.78, −0.09], stop-out 0.29, n 45; the low-SI third made +2.32 %; all 18 pre-registered cells had a negative top-third net; the random-day placebo was not beaten.
- Nothing ships: no tab, gate, push or rule. The tab is HIS CALL #1 in the report.
