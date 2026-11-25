"""Write a self-contained HTML viewer for a mas_sim JSONL log, and print its path.

Open the HTML file in a browser. Left: the runs, grouped by condition (the config fields
that differ between runs). Right: the selected run's agents as a strip of steps
(click, or the arrow keys); for the selected step, the agent's exact context split into
collapsible sections, its reply (parsed or raw), whose outputs it sees, who sees its
output, and how its output appears in later contexts. "compare with" puts a second run
next to it and marks the context lines that differ; "highlight" marks a word everywhere
and counts it per reply in the step strip.

The page holds a copy of the log: re-run this script after the log changes.

Usage:
  uv run scripts/view_runs.py data/results/authority/smoke.jsonl          # writes smoke.html next to it
  uv run scripts/view_runs.py LOG.jsonl -o viewer.html --pin case a5_plan final_is_b --open
"""

import argparse
import webbrowser
from pathlib import Path

from mas_sim.logs import read_log
from mas_sim.viewer import build_viewer_html


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="output HTML (default: the log path with .html)")
    ap.add_argument("--pin", nargs="*", default=[], help="outcome fields to show under each run in the run list")
    ap.add_argument("--open", action="store_true", help="open the page in the default browser")
    args = ap.parse_args()

    out = args.out or args.log.with_suffix(".html")
    assert out.resolve() != args.log.resolve(), "output would overwrite the log"
    records = read_log(args.log)
    out.write_text(build_viewer_html(records, args.log.name, args.pin), encoding="utf-8")
    n_runs = len({r["run_id"] for r in records})
    print(f"{out}  ({n_runs} runs, {len(records)} records)")
    if args.open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
