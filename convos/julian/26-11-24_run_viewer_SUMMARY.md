# SUMMARY: HTML viewer for mas_sim run logs

**Last updated:** 26-11-24 (built; render checked by screenshot, interactions not yet tested by hand)

Julian asked for a page to inspect runs step by step after the first authority smoke run: click through steps, expand/collapse replies, see who sees what.

Built [verified: `make check` green, 52 tests; headless-Firefox screenshots of normal and compare views 26-11-24]:
- `scripts/view_runs.py LOG.jsonl [-o OUT.html] [--pin FIELD ...] [--open]` writes a self-contained HTML page (default: next to the log, `.html`). Code: `src/mas_sim/viewer.py` + `src/mas_sim/viewer_template.html`; tests: `tests/mas_sim/test_viewer.py`.
- Example: `uv run scripts/view_runs.py data/results/authority/smoke.jsonl --pin case a5_plan final_is_b --open`
- The page embeds a copy of the log: regenerate after the log changes. Dropping a `.jsonl` onto the page also loads it.

Page contents: runs grouped by condition (config fields that differ between runs); a step strip that marks, for the selected agent, whose outputs it sees (blue) and who sees its output (green); a visibility matrix from the logged `visible` lists; each agent's exact context in collapsible sections, with each "--- NAME ---" block labelled by the agent/step it came from; the reply as parsed fields or raw; how the reply appears to later agents; a highlight term counted per reply; side-by-side comparison of two runs with differing context lines marked (this is how the cue sentence shows up). Keys ←/→ step, ↑/↓ run.

Design [concluded]: generic, so it lives in `mas_sim` and knows nothing about the authority experiment; booleans are coloured neutrally because the viewer can't tell which value is risky.

Not verified: clicks, collapsing, keyboard, drag-drop, pinning (no interactive browser available to me). JavaScript errors show in a red box at the top of the page.

LOG: `convos/julian/26-11-24_run_viewer_LOG.md`
- See also: `convos/julian/26-11-24_mas_sim_plan_SUMMARY.md` — the `mas_sim` library and log format the viewer reads, and the smoke-run findings (A1 fabricating findings, A4's QT objections) that the viewer makes easy to trace.
- See also: `convos/julian/26-11-25_majority_sway_SUMMARY.md` — majority-sway smoke log viewed with it (`data/results/majority_sway/smoke.html`, 6 MB page for 3 runs).
