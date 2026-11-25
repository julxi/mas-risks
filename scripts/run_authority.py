"""Run an authority-deference sweep and print the per-condition summary.

Conditions are the cross product of the list-valued options; each gets
--n-replicates runs, spread evenly over the case variants. Runs already in the log
file are skipped, and LLM replies are cached under data/cache/llm/, so an
interrupted sweep can simply be restarted with the same command.

Examples:
  uv run scripts/run_authority.py                                  # paper replication: cue none vs authority
  uv run scripts/run_authority.py --cue none authority neutral authority_on_a2 --a3-mode llm scripted
  uv run scripts/run_authority.py --n-replicates 2 --log data/results/authority/smoke.jsonl
  uv run scripts/run_authority.py --case-set pending gram_negative  # Gram stain pending vs Gram-negative rods
"""

import argparse
import asyncio
import itertools
from pathlib import Path

from mas_sim.llm import NORMALIZATIONS, LLMClient
from mas_sim.runner import run_sweep
from risk_experiments.authority import (
    CUES,
    MODES,
    VISIBILITIES,
    AuthorityConfig,
    AuthorityScenario,
    load_content,
    summarize,
)
from risk_experiments.utils import DEFAULT_MODEL, LLM_CACHE_DIR, RESULTS_DIR, load_env


def main() -> None:
    case_sets = load_content()["case_sets"]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL, help="provider:model for all agents (default %(default)s)")
    ap.add_argument("--cue", nargs="+", default=["none", "authority"], choices=CUES)
    ap.add_argument("--visibility", nargs="+", default=["full_chain"], choices=VISIBILITIES)
    ap.add_argument("--a2-mode", nargs="+", default=["llm"], choices=MODES)
    ap.add_argument("--a3-mode", nargs="+", default=["llm"], choices=MODES)
    ap.add_argument(
        "--case-set",
        nargs="+",
        default=["pending"],
        choices=sorted(case_sets),
        help="named case sets from the scenario YAML (default %(default)s)",
    )
    ap.add_argument("--n-replicates", type=int, default=30)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--normalization", default="none", choices=NORMALIZATIONS)
    ap.add_argument("--log", type=Path, default=RESULTS_DIR / "authority" / "authority_runs.jsonl")
    ap.add_argument("--max-concurrent-runs", type=int, default=4)
    ap.add_argument("--max-concurrent-calls", type=int, default=8)
    args = ap.parse_args()

    load_env()
    configs = [
        AuthorityConfig(
            model=args.model,
            cue=cue,
            visibility=vis,
            a2_mode=a2,
            a3_mode=a3,
            cases=tuple(case_sets[case_set]),
            temperature=args.temperature,
            normalization=args.normalization,
        )
        for cue, vis, a2, a3, case_set in itertools.product(
            args.cue, args.visibility, args.a2_mode, args.a3_mode, args.case_set
        )
    ]
    llm = LLMClient(cache_dir=LLM_CACHE_DIR, max_concurrency=args.max_concurrent_calls)
    print(f"{len(configs)} conditions x {args.n_replicates} replicates -> {args.log}")
    asyncio.run(
        run_sweep(
            lambda cfg, rep: AuthorityScenario(cfg, rep, llm),
            configs,
            args.n_replicates,
            args.log,
            prefix="au",
            max_concurrent_runs=args.max_concurrent_runs,
        )
    )
    print(f"LLM calls: {llm.n_api_calls} to the API, {llm.n_cache_hits} from cache\n")
    print(summarize(args.log))


if __name__ == "__main__":
    main()
