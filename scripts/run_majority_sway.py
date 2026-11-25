"""Run a majority-sway sweep and print the per-condition summary.

Conditions are the cross product of the list-valued options; each gets --n-replicates
runs. Runs already in the log file are skipped, and LLM replies are cached under
data/cache/llm/, so an interrupted sweep can simply be restarted with the same command.
One run with all agents as LLMs is (n_fast + n_deep + 1) x n_rounds calls: 55 by default.

Examples:
  uv run scripts/run_majority_sway.py                                    # 7 fast / 3 deep, 30 replicates
  uv run scripts/run_majority_sway.py --n-replicates 3 --log data/results/majority_sway/smoke.jsonl
  uv run scripts/run_majority_sway.py --show-roles off on                # do role labels change the verdict?
"""

import argparse
import asyncio
import itertools
from pathlib import Path

from mas_sim.llm import NORMALIZATIONS, LLMClient
from mas_sim.runner import run_sweep
from risk_experiments.majority_sway import MajoritySwayConfig, MajoritySwayScenario, summarize
from risk_experiments.utils import DEFAULT_MODEL, LLM_CACHE_DIR, RESULTS_DIR, load_env


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL, help="provider:model for all agents (default %(default)s)")
    ap.add_argument("--n-fast", nargs="+", type=int, default=[7])
    ap.add_argument("--n-deep", nargs="+", type=int, default=[3])
    ap.add_argument("--n-rounds", type=int, default=5)
    ap.add_argument("--show-roles", nargs="+", default=["off"], choices=["off", "on"])
    ap.add_argument("--n-replicates", type=int, default=30)
    ap.add_argument("--analyst-temperature", type=float, default=0.7)
    ap.add_argument("--summary-temperature", type=float, default=0.3)
    ap.add_argument("--normalization", default="none", choices=NORMALIZATIONS)
    ap.add_argument("--log", type=Path, default=RESULTS_DIR / "majority_sway" / "majority_sway_runs.jsonl")
    ap.add_argument("--max-concurrent-runs", type=int, default=2)
    ap.add_argument("--max-concurrent-calls", type=int, default=8)
    args = ap.parse_args()

    load_env()
    configs = [
        MajoritySwayConfig(
            model=args.model,
            n_fast=n_fast,
            n_deep=n_deep,
            n_rounds=args.n_rounds,
            show_roles=show_roles == "on",
            analyst_temperature=args.analyst_temperature,
            summary_temperature=args.summary_temperature,
            normalization=args.normalization,
        )
        for n_fast, n_deep, show_roles in itertools.product(args.n_fast, args.n_deep, args.show_roles)
    ]
    llm = LLMClient(cache_dir=LLM_CACHE_DIR, max_concurrency=args.max_concurrent_calls)
    print(f"{len(configs)} conditions x {args.n_replicates} replicates -> {args.log}")
    asyncio.run(
        run_sweep(
            lambda cfg, rep: MajoritySwayScenario(cfg, rep, llm),
            configs,
            args.n_replicates,
            args.log,
            prefix="ms",
            max_concurrent_runs=args.max_concurrent_runs,
        )
    )
    print(f"LLM calls: {llm.n_api_calls} to the API, {llm.n_cache_hits} from cache\n")
    print(summarize(args.log))


if __name__ == "__main__":
    main()
