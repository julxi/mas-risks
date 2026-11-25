"""Plumbing tests for mas_sim with toy scenarios. No network, no API keys."""

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from mas_sim.agents import Context, LLMAgent, ReplayAgent, ScriptedAgent
from mas_sim.llm import LLMClient, normalize_messages
from mas_sim.logs import format_run, read_log, run_records
from mas_sim.output import OutputSchema, ParseError, extract_json_text, parse_output
from mas_sim.runner import make_run_id, run_sweep
from mas_sim.scenario import Scenario, Step
from mas_sim.transcript import Message, Transcript

SRC = Path(__file__).resolve().parents[2] / "src"


# --- toy scenario ----------------------------------------------------------------


class Say(OutputSchema):
    text: str
    n_visible: int


def counting_policy(ctx: Context) -> str:
    return json.dumps({"text": f"{ctx.agent_id} r{ctx.round}", "n_visible": len(ctx.visible)})


@dataclass(frozen=True)
class EchoConfig:
    n_rounds: int = 2
    tag: str = "a"


class EchoScenario(Scenario[EchoConfig]):
    """Agents x and y speak in parallel each round and see all messages of earlier rounds."""

    name = "echo"

    def __init__(self, config: EchoConfig, replicate: int, agents=None):
        super().__init__(config, replicate)
        self.agents = agents or {
            "x": ScriptedAgent("x", Say, counting_policy, "count"),
            "y": ScriptedAgent("y", Say, counting_policy, "count"),
        }
        self.built_contexts: list[tuple[str, int, int]] = []  # (agent, step, transcript length)

    def schedule(self):
        for r in range(self.config.n_rounds):
            yield Step(round=r, index=r, agents=(self.agents["x"], self.agents["y"]))

    def build_context(self, agent, step, transcript, run_id):
        visible = tuple(transcript.before_step(step.index))
        self.built_contexts.append((agent.id, step.index, len(transcript)))
        msgs = [{"role": "system", "content": f"You are {agent.id}."}]
        msgs.append({"role": "user", "content": "\n".join(m.raw for m in visible) or "(nothing yet)"})
        return Context(run_id, self.replicate, step.round, step.index, agent.id, msgs, visible)

    def after_step(self, step, transcript):
        return {"n_messages": len(transcript)}

    def outcome(self, transcript):
        return {"texts": [m.parsed_as(Say).text for m in transcript]}


def run(coro):
    return asyncio.run(coro)


# --- runner ----------------------------------------------------------------------


def test_parallel_step_isolation_and_log(tmp_path):
    log = tmp_path / "log.jsonl"
    scenarios = []

    def make(cfg, rep):
        s = EchoScenario(cfg, rep)
        scenarios.append(s)
        return s

    res = run(run_sweep(make, [EchoConfig()], 1, log, "echo", verbose=False))
    assert len(res.run_records) == 1 and not res.failed
    # Both contexts of a step were built while the transcript held only earlier steps.
    assert scenarios[0].built_contexts == [("x", 0, 0), ("y", 0, 0), ("x", 1, 2), ("y", 1, 2)]
    recs = read_log(log)
    calls = [r for r in recs if r["type"] == "call"]
    assert [(c["agent"], c["step"]) for c in calls] == [("x", 0), ("y", 0), ("x", 1), ("y", 1)]
    assert [c["parsed"]["n_visible"] for c in calls] == [0, 0, 2, 2]
    assert calls[2]["visible"] == [[0, 0, "x"], [0, 0, "y"]]
    assert all(c["agent_kind"] == "scripted" and c["policy"] == "count" for c in calls)
    assert [r["data"] for r in recs if r["type"] == "env"] == [{"n_messages": 2}, {"n_messages": 4}]
    (run_rec,) = run_records(recs)
    assert run_rec["status"] == "ok"
    assert run_rec["outcome"] == {"texts": ["x r0", "y r0", "x r1", "y r1"]}
    assert run_rec["config"] == {"n_rounds": 2, "tag": "a"}
    text = format_run(recs, run_rec["run_id"])
    assert "<<<<< message 0: system >>>>>" in text and "RUN" in text


def test_resume_skips_logged_runs(tmp_path):
    log = tmp_path / "log.jsonl"
    make = lambda cfg, rep: EchoScenario(cfg, rep)  # noqa: E731
    run(run_sweep(make, [EchoConfig()], 2, log, "echo", verbose=False))
    res = run(run_sweep(make, [EchoConfig(), EchoConfig(tag="b")], 2, log, "echo", verbose=False))
    assert res.n_skipped == 2 and len(res.run_records) == 2
    ids = [r["run_id"] for r in run_records(read_log(log))]
    assert len(ids) == len(set(ids)) == 4
    assert make_run_id("echo", EchoConfig(), 1) in ids


def test_parse_failure_marks_run_failed_and_sweep_continues(tmp_path):
    log = tmp_path / "log.jsonl"

    def make(cfg, rep):
        agents = None
        if rep == 0:
            agents = {
                "x": ScriptedAgent.fixed("x", Say, "not json", "broken"),
                "y": ScriptedAgent("y", Say, counting_policy, "count"),
            }
        return EchoScenario(cfg, rep, agents)

    res = run(run_sweep(make, [EchoConfig()], 2, log, "echo", verbose=False))
    assert len(res.failed) == 1
    recs = read_log(log)
    failed = res.failed[0]
    assert failed["outcome"] is None and "agent x at step 0" in failed["error"]
    # Both calls of the failing step are logged, nothing after it.
    calls = [r for r in recs if r["type"] == "call" and r["run_id"] == failed["run_id"]]
    assert [(c["agent"], c["parse_error"] is None) for c in calls] == [("x", False), ("y", True)]
    ok = [r for r in run_records(recs) if r["status"] == "ok"]
    assert len(ok) == 1


def test_duplicate_configs_rejected(tmp_path):
    with pytest.raises(AssertionError):
        run(run_sweep(lambda c, r: EchoScenario(c, r), [EchoConfig(), EchoConfig()], 1, tmp_path / "l.jsonl", "e"))


def test_replay_agent_reproduces_source_run(tmp_path):
    log = tmp_path / "log.jsonl"
    run(run_sweep(lambda c, r: EchoScenario(c, r), [EchoConfig()], 1, log, "echo", verbose=False))
    src_id = make_run_id("echo", EchoConfig(), 0)
    log2 = tmp_path / "log2.jsonl"

    def make(cfg, rep):
        agents = {
            "x": ReplayAgent("x", Say, log, src_id),
            "y": ScriptedAgent.fixed("y", Say, json.dumps({"text": "fixed", "n_visible": -1}), "fixed"),
        }
        return EchoScenario(cfg, rep, agents)

    run(run_sweep(make, [EchoConfig(tag="replay")], 1, log2, "echo", verbose=False))
    calls = [r for r in read_log(log2) if r["type"] == "call"]
    assert [c["raw"] for c in calls if c["agent"] == "x"] == [
        r["raw"] for r in read_log(log) if r["type"] == "call" and r["agent"] == "x"
    ]
    assert {c["agent_kind"] for c in calls if c["agent"] == "x"} == {"replay"}


# --- LLM agent with a fake backend -----------------------------------------------


class FakeBackend:
    def __init__(self):
        self.calls = []

    async def chat(self, provider, model_name, messages, temperature, max_tokens):
        self.calls.append((provider, model_name, messages, temperature))
        return json.dumps({"text": f"call {len(self.calls)}", "n_visible": 0}), "stop"


def test_llm_agent_sends_context_and_caches(tmp_path):
    backend = FakeBackend()
    client = LLMClient(cache_dir=tmp_path / "cache", backend=backend)
    agent = LLMAgent("x", Say, "mistral:some-model", 0.7, client)
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    ctx = Context("run", 0, 0, 0, "x", msgs, ())
    out1 = run(agent.respond(ctx))
    out2 = run(agent.respond(ctx))
    assert backend.calls == [("mistral", "some-model", msgs, 0.7)]
    assert out1.raw == out2.raw and out1.cache_hit is False and out2.cache_hit is True
    assert out1.sent_messages == msgs and out1.kind == "llm" and out1.model == "mistral:some-model"
    # A different replicate is an independent sample.
    run(agent.respond(Context("run", 1, 0, 0, "x", msgs, ())))
    assert len(backend.calls) == 2
    assert client.n_api_calls == 2 and client.n_cache_hits == 1


class SameContextScenario(EchoScenario):
    """Both agents get the same messages: with LLM agents they would share cache entries."""

    def build_context(self, agent, step, transcript, run_id):
        msgs = [{"role": "system", "content": "You are an agent."}, {"role": "user", "content": "go"}]
        return Context(run_id, self.replicate, step.round, step.index, agent.id, msgs, ())


def test_identical_llm_requests_in_one_step_rejected(tmp_path):
    client = LLMClient(cache_dir=None, backend=FakeBackend())
    agents = {a: LLMAgent(a, Say, "mistral:m", 0.7, client) for a in ("x", "y")}
    with pytest.raises(ExceptionGroup) as ei:
        run(run_sweep(lambda c, r: SameContextScenario(c, r, agents), [EchoConfig()], 1, tmp_path / "l.jsonl", "e"))
    assert "identical LLM requests" in str(ei.value.exceptions[0])
    # Scripted agents never touch the cache, so identical contexts are fine for them.
    scripted = {a: ScriptedAgent(a, Say, counting_policy, "count") for a in ("x", "y")}
    res = run(run_sweep(lambda c, r: SameContextScenario(c, r, scripted), [EchoConfig()], 1, tmp_path / "s.jsonl", "e"))
    assert not res.failed


def test_llm_agent_normalization_is_what_gets_sent(tmp_path):
    backend = FakeBackend()
    client = LLMClient(cache_dir=None, backend=backend)
    agent = LLMAgent("x", Say, "vllm:m", 0.5, client, normalization="merge_fold_system")
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "A"}, {"role": "user", "content": "B"}]
    out = run(agent.respond(Context("run", 0, 0, 0, "x", msgs, ())))
    assert out.sent_messages == [{"role": "user", "content": "S\n\nA\n\nB"}]
    assert backend.calls[0][2] == out.sent_messages


def test_non_string_reply_rejected_and_not_cached(tmp_path):
    class ChunkBackend:
        async def chat(self, provider, model_name, messages, temperature, max_tokens):
            return [{"type": "thinking", "thinking": "..."}], "length"

    # The fake breaks the Backend protocol on purpose: real SDK replies can do the same.
    client = LLMClient(cache_dir=tmp_path / "cache", backend=ChunkBackend())  # pyright: ignore[reportArgumentType]
    msgs = [{"role": "user", "content": "hi"}]
    with pytest.raises(TypeError, match="list content"):
        run(client.complete("mistral:m", msgs, 0.7, 100, replicate=0))
    assert not list((tmp_path / "cache").rglob("*.json"))


def test_unknown_provider_rejected():
    with pytest.raises(AssertionError):
        LLMAgent("x", Say, "nosuch:m", 0.5, LLMClient(cache_dir=None, backend=FakeBackend()))


# --- normalization ---------------------------------------------------------------


def test_normalize_merge():
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "c"},
        {"role": "user", "content": "d"},
    ]
    assert normalize_messages(msgs, "none") == msgs
    assert normalize_messages(msgs, "merge") == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "a\n\nb"},
        {"role": "assistant", "content": "c"},
        {"role": "user", "content": "d"},
    ]
    assert normalize_messages(msgs, "merge_fold_system")[0] == {"role": "user", "content": "S\n\na\n\nb"}


def test_normalize_rejects_bad_input():
    with pytest.raises(AssertionError):
        normalize_messages([{"role": "user", "content": "a"}, {"role": "system", "content": "S"}], "none")
    with pytest.raises(AssertionError):
        normalize_messages([{"role": "assistant", "content": "a"}], "merge")
    with pytest.raises(AssertionError):
        normalize_messages([{"role": "user", "content": "  "}], "none")


# --- output parsing --------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        '{"text": "a", "n_visible": 1}',
        '  ```json\n{"text": "a", "n_visible": 1}\n```\n',
        '```\n{"text": "a", "n_visible": 1}\n```',
    ],
)
def test_parse_accepts(raw):
    assert parse_output(raw, Say) == Say(text="a", n_visible=1)


@pytest.mark.parametrize(
    "raw",
    [
        'Here you go: {"text": "a", "n_visible": 1}',
        '```python\n{"text": "a", "n_visible": 1}\n```',
        '```json\n{"text": "a", "n_visible": 1}\n``` extra',
        '{"text": "a"}',
        '{"text": "a", "n_visible": 1, "extra": 2}',
        '{"text": "a", "n_visible": 1}\n{"text": "b", "n_visible": 2}',
    ],
)
def test_parse_rejects(raw):
    with pytest.raises(ParseError):
        parse_output(raw, Say)


def test_extract_rejects_two_fences():
    with pytest.raises(ParseError):
        extract_json_text('```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```')


# --- transcript ------------------------------------------------------------------


class Other(OutputSchema):
    x: int


def test_typed_access_checks_the_schema():
    tr = Transcript()
    tr.append(Message(0, 0, "a", "{}", Say(text="hi", n_visible=0)))
    assert tr.last_parsed("a", Say).text == "hi"
    with pytest.raises(AssertionError, match="not"):
        tr.last_parsed("a", Other)


# --- package boundary ------------------------------------------------------------


def test_mas_sim_never_imports_risk_experiments():
    pattern = re.compile(r"^\s*(from|import)\s+risk_experiments\b|importlib.*risk_experiments", re.M)
    files = list((SRC / "mas_sim").rglob("*.py"))
    assert len(files) >= 6, files
    offenders = [p for p in files if pattern.search(p.read_text())]
    assert not offenders, f"mas_sim must not import risk_experiments: {offenders}"
