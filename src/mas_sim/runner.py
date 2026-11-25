"""The run loop. Owns time (round/step); nothing else keeps a counter.

A sweep runs `configs x replicates`. A run id is `{prefix}-{hash(config)}-r{replicate}`,
so the same condition always gets the same ids, and a sweep resumed into the same
log file skips runs that already have a run record (with the LLM cache, re-running
is cheap anyway). Calls from a run that crashed before its run record was written
stay in the log as orphans; analysis uses run records only.

Failure policy:
- An agent reply that fails its output schema marks the run as failed: all calls
  of that step are logged, then a run record with status "failed" is written and
  the sweep continues. Failures are printed loudly and counted in the result.
- Any other exception (API error after retries, bug) aborts the whole sweep.
"""

import asyncio
import dataclasses
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mas_sim.agents import Agent, Context, LLMAgent
from mas_sim.logs import LogWriter, read_log, run_records
from mas_sim.output import ParseError, parse_output
from mas_sim.scenario import Scenario
from mas_sim.transcript import Message, Transcript


def config_dict(config) -> dict:
    assert dataclasses.is_dataclass(config) and not isinstance(config, type), (
        f"config must be a dataclass instance, got {type(config)}"
    )
    return dataclasses.asdict(config)


def config_hash(config) -> str:
    return hashlib.sha256(json.dumps(config_dict(config), sort_keys=True).encode()).hexdigest()[:6]


def make_run_id(prefix: str, config, replicate: int) -> str:
    return f"{prefix}-{config_hash(config)}-r{replicate:02d}"


class _RunFailed(Exception):
    pass


def _assert_distinct_llm_requests(agents: Sequence[Agent], ctxs: Sequence[Context]) -> None:
    """Fail if two LLM agents in one step would send the same request.

    The LLM cache key is (model, normalization, messages, temperature, max_tokens,
    replicate), not the agent id. Two agents with identical requests would therefore
    share one cache entry: a resumed or repeated run would give both the same reply,
    silently turning independent agents into copies. Scenarios must make such contexts
    differ (e.g. by naming the agent in its system prompt).
    """
    seen: dict[str, str] = {}
    for a, ctx in zip(agents, ctxs, strict=True):
        if not isinstance(a, LLMAgent):
            continue
        key = json.dumps([a.model, a.normalization, a.temperature, a.max_tokens, ctx.messages], sort_keys=True)
        assert key not in seen, (
            f"agents {seen.get(key)!r} and {a.id!r} would send identical LLM requests in step {ctx.step} "
            "and share cache entries; make their contexts differ"
        )
        seen[key] = a.id


async def run_one(scenario: Scenario[Any], run_id: str, log: LogWriter) -> dict:
    """Run one scenario instance to completion. Returns the run record (also logged)."""
    tr = Transcript()
    status, error, outcome = "ok", None, None
    try:
        for expected_index, step in enumerate(scenario.schedule()):
            assert step.index == expected_index, f"step index {step.index}, expected {expected_index}"
            # All contexts are built before anyone replies: agents in a parallel
            # step must not see each other's current-step output.
            ctxs = [scenario.build_context(a, step, tr, run_id) for a in step.agents]
            for a, ctx in zip(step.agents, ctxs, strict=True):
                assert (ctx.agent_id, ctx.round, ctx.step, ctx.run_id) == (a.id, step.round, step.index, run_id), (
                    f"build_context returned a context for {(ctx.agent_id, ctx.round, ctx.step, ctx.run_id)}"
                )
                assert ctx.replicate == scenario.replicate, (ctx.replicate, scenario.replicate)
            _assert_distinct_llm_requests(step.agents, ctxs)
            outs = await asyncio.gather(*(a.respond(ctx) for a, ctx in zip(step.agents, ctxs, strict=True)))
            new_msgs: list[Message] = []
            failure = None
            for a, ctx, out in zip(step.agents, ctxs, outs, strict=True):
                try:
                    parsed, parse_error = parse_output(out.raw, a.schema), None
                except ParseError as e:
                    parsed, parse_error = None, str(e)
                    if failure is None:
                        failure = f"agent {a.id} at step {step.index}: {e}"
                log.write(
                    {
                        "type": "call",
                        "run_id": run_id,
                        "round": step.round,
                        "step": step.index,
                        "agent": a.id,
                        "agent_kind": out.kind,
                        "model": out.model,
                        "temperature": out.temperature,
                        "max_tokens": out.max_tokens,
                        "normalization": out.normalization,
                        "policy": out.policy,
                        "cache_hit": out.cache_hit,
                        "finish_reason": out.finish_reason,
                        "messages": out.sent_messages,
                        "visible": [list(m.ref()) for m in ctx.visible],
                        "raw": out.raw,
                        "parsed": parsed.model_dump() if parsed is not None else None,
                        "parse_error": parse_error,
                    }
                )
                if parsed is not None:
                    new_msgs.append(Message(step.round, step.index, a.id, out.raw, parsed))
            if failure is not None:
                raise _RunFailed(failure)
            for m in new_msgs:
                tr.append(m)
            data = scenario.after_step(step, tr)
            if data is not None:
                log.write({"type": "env", "run_id": run_id, "round": step.round, "step": step.index, "data": data})
        outcome = scenario.outcome(tr)
        assert isinstance(outcome, dict), type(outcome)
    except _RunFailed as e:
        status, error = "failed", str(e)
    record = {
        "type": "run",
        "run_id": run_id,
        "experiment": scenario.name,
        "config": config_dict(scenario.config),
        "replicate": scenario.replicate,
        "status": status,
        "outcome": outcome,
        "error": error,
    }
    log.write(record)
    return record


@dataclass
class SweepResult:
    run_records: list[dict]  # records of the runs executed in this call
    n_skipped: int  # runs already in the log

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.run_records if r["status"] == "failed"]


async def run_sweep[C](
    make_scenario: Callable[[C, int], Scenario[C]],
    configs: Sequence[C],
    n_replicates: int,
    log_path: Path,
    prefix: str,
    max_concurrent_runs: int = 4,
    verbose: bool = True,
) -> SweepResult:
    """Run every config `n_replicates` times (replicates 0..n-1), logging to `log_path`."""
    assert n_replicates >= 1, n_replicates
    assert len(configs) >= 1, "no configs"
    hashes = [config_hash(c) for c in configs]
    assert len(set(hashes)) == len(hashes), "duplicate configs in sweep"
    done_ids = {r["run_id"] for r in run_records(read_log(log_path))} if log_path.exists() else set()
    jobs = [(c, rep, make_run_id(prefix, c, rep)) for c in configs for rep in range(n_replicates)]
    todo = [j for j in jobs if j[2] not in done_ids]
    sem = asyncio.Semaphore(max_concurrent_runs)
    records: list[dict] = []

    async def one(config: C, rep: int, run_id: str, log: LogWriter) -> None:
        async with sem:
            rec = await run_one(make_scenario(config, rep), run_id, log)
        records.append(rec)
        if rec["status"] == "failed":
            print(f"!!! RUN FAILED {run_id}: {rec['error']}", file=sys.stderr, flush=True)
        elif verbose:
            print(f"[{len(records)}/{len(todo)}] {run_id} ok", flush=True)

    with LogWriter(log_path) as log:
        async with asyncio.TaskGroup() as tg:
            for c, rep, rid in todo:
                tg.create_task(one(c, rep, rid, log))
    result = SweepResult(run_records=records, n_skipped=len(jobs) - len(todo))
    if verbose:
        print(
            f"sweep done: {len(records)} runs executed ({len(result.failed)} failed), "
            f"{result.n_skipped} skipped as already logged; log: {log_path}",
            flush=True,
        )
    return result
