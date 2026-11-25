"""Majority-sway experiment: visibility, private information, display names and outcome.
No API calls (scripted agents, or LLM agents on a fake backend)."""

import asyncio
import json

from mas_sim.agents import Context, ScriptedAgent
from mas_sim.llm import LLMClient
from mas_sim.logs import read_log, run_records
from mas_sim.runner import run_sweep
from risk_experiments.majority_sway import (
    SUMMARY_ID,
    AnalystMessage,
    MajoritySwayConfig,
    MajoritySwayScenario,
    Verdict,
    load_content,
    summarize,
)

MODEL = "mistral:test-model"
CONTENT = load_content()
RETRACTION_MARKER = "key experimental data cannot be reliably reproduced"


def tag(agent_id: str, round_: int) -> str:
    """Marker in a scripted reply. Deliberately not the raw agent id, so that the
    id-hiding test can check that no agent id leaks into any context."""
    return f"{agent_id.replace('_', '#')} r{round_}"


def analyst_policy(ctx: Context) -> str:
    """fast: always true. deep: true in round 0, fake once it has seen the withdrawal."""
    judgment = "fake" if ctx.agent_id.startswith("deep") and ctx.round >= 1 else "true"
    return AnalystMessage(
        judgment=judgment, confidence=0.8, reasoning=tag(ctx.agent_id, ctx.round), evidence=["x"]
    ).model_dump_json()


def summary_policy(ctx: Context) -> str:
    """Counts the visible judgments and follows the majority (true on ties)."""
    js = [m.parsed_as(AnalystMessage).judgment for m in ctx.visible]
    n_true = js.count("true")
    return Verdict(
        true_count=n_true,
        fake_count=len(js) - n_true,
        verdict="true" if n_true >= len(js) - n_true else "fake",
        justification="majority",
        confidence=0.5,
    ).model_dump_json()


def scripted_agents(cfg: MajoritySwayConfig):
    agents = {a: ScriptedAgent(a, AnalystMessage, analyst_policy, "test_analyst") for a in cfg.analyst_ids()}
    agents[SUMMARY_ID] = ScriptedAgent(SUMMARY_ID, Verdict, summary_policy, "test_summary")
    return agents


def run_scripted(tmp_path, n_replicates=1, **cfg_kwargs):
    cfg = MajoritySwayConfig(model=MODEL, **cfg_kwargs)
    log = tmp_path / "log.jsonl"
    res = asyncio.run(
        run_sweep(
            lambda c, r: MajoritySwayScenario(c, r, llm=None, agent_overrides=scripted_agents(c)),
            [cfg],
            n_replicates,
            log,
            "ms",
            verbose=False,
        )
    )
    assert not res.failed, res.failed
    recs = read_log(log)
    return recs, [r for r in recs if r["type"] == "call"]


def text_of(call: dict) -> str:
    return "\n".join(m["content"] for m in call["messages"])


def test_withdrawal_notice_reaches_deep_analysts_only(tmp_path):
    _, calls = run_scripted(tmp_path)
    for c in calls:
        has = RETRACTION_MARKER in text_of(c)
        should = c["agent"].startswith("deep") and c["round"] >= 1
        assert has == should, (c["agent"], c["round"])
    # It arrives as a new user message in round 1 exactly once, then stays in the history.
    deep_r1 = next(c for c in calls if c["agent"] == "deep_1" and c["round"] == 1)
    assert sum(RETRACTION_MARKER in m["content"] for m in deep_r1["messages"]) == 1
    assert RETRACTION_MARKER in deep_r1["messages"][-1]["content"]


def test_summary_sees_exactly_the_current_round(tmp_path):
    _, calls = run_scripted(tmp_path)
    summaries = [c for c in calls if c["agent"] == SUMMARY_ID]
    assert [c["round"] for c in summaries] == [0, 1, 2, 3, 4]
    for c in summaries:
        assert len(c["visible"]) == 10
        assert {(r, s) for r, s, _ in c["visible"]} == {(c["round"], 2 * c["round"])}
        assert len(c["messages"]) == 2  # no memory of earlier rounds
        assert "=== NEWS ===" not in text_of(c)
        assert text_of(c).count("--- Analyst ") == 10


def test_analyst_history_and_peer_messages(tmp_path):
    _, calls = run_scripted(tmp_path)
    c = next(c for c in calls if c["agent"] == "fast_3" and c["round"] == 3)
    roles = [m["role"] for m in c["messages"]]
    assert roles == ["system", "user", "assistant", "user", "assistant", "user", "assistant", "user"]
    own = [m["content"] for m in c["messages"] if m["role"] == "assistant"]
    assert [json.loads(o)["reasoning"] for o in own] == [tag("fast_3", r) for r in range(3)]
    # Each round's user message shows the 9 OTHER analysts of the previous round, never the summary.
    for r in (1, 2, 3):
        user = c["messages"][2 * r + 1]["content"]
        assert user.count("--- Analyst ") == 9
        assert tag("fast_3", r - 1) not in user and tag("deep_1", r - 1) in user
        assert "Verdict" not in user and "majority" not in user
    assert all(s == 2 * r for r, s, sender in c["visible"]) and len(c["visible"]) == 30
    assert all(sender != SUMMARY_ID for _, _, sender in c["visible"])
    # Parallel step isolation: nobody sees its own round's messages.
    for call in calls:
        assert all(r < call["round"] or call["agent"] == SUMMARY_ID for r, _, _ in call["visible"])


def test_display_names_hide_ids_and_roles_by_default(tmp_path):
    recs, calls = run_scripted(tmp_path)
    for c in calls:
        for m in c["messages"]:
            assert "fast_" not in m["content"] and "deep_" not in m["content"], (c["agent"], c["round"])
            assert "retrieval)" not in m["content"] and "verification)" not in m["content"]
    (env,) = [r for r in recs if r["type"] == "env"]
    names = env["data"]["display_names"]
    assert sorted(names.values()) == sorted(f"Analyst {k}" for k in range(1, 11))
    # Each analyst is told its own display name.
    for c in calls:
        if c["agent"] != SUMMARY_ID:
            assert f"You are {names[c['agent']]}," in c["messages"][0]["content"]


def test_show_roles_labels(tmp_path):
    _, calls = run_scripted(tmp_path, show_roles=True)
    summary = next(c for c in calls if c["agent"] == SUMMARY_ID)
    assert text_of(summary).count("(fast retrieval) ---") == 7
    assert text_of(summary).count("(deep verification) ---") == 3


def test_display_names_paired_across_conditions_and_vary_across_replicates():
    def make(cfg, rep):
        return MajoritySwayScenario(cfg, rep, llm=None, agent_overrides=scripted_agents(cfg))

    a = make(MajoritySwayConfig(model=MODEL), 3)
    b = make(MajoritySwayConfig(model=MODEL, show_roles=True), 3)
    assert a.display_order == b.display_order
    orders = {tuple(make(MajoritySwayConfig(model=MODEL), r).display_order) for r in range(5)}
    assert len(orders) > 1


def test_outcome(tmp_path):
    recs, _ = run_scripted(tmp_path)
    (run,) = run_records(recs)
    o = run["outcome"]
    assert o["n_true_fast_by_round"] == [7] * 5
    assert o["n_true_deep_by_round"] == [3, 0, 0, 0, 0]
    assert o["majority_by_round"] == ["true"] * 5
    assert o["verdicts"] == ["true"] * 5 and o["final_is_true"] is True and o["final_follows_majority"] is True
    assert o["summary_miscount_rounds"] == []
    assert o["stances"]["deep_2"] == ["true", "fake", "fake", "fake", "fake"]


def test_tie_and_summary(tmp_path):
    recs, _ = run_scripted(tmp_path, n_replicates=2, n_fast=3, n_deep=3)
    o = run_records(recs)[0]["outcome"]
    assert o["majority_by_round"] == ["true", "tie", "tie", "tie", "tie"]
    assert o["final_follows_majority"] is None
    text = summarize(tmp_path / "log.jsonl")
    assert "final verdict TRUE 2/2" in text and "0 yes, 0 no, 2 tie" in text


class FakeBackend:
    """Valid replies for either schema; tells them apart by the system prompt."""

    def __init__(self):
        self.n = 0

    async def chat(self, provider, model_name, messages, temperature, max_tokens):
        self.n += 1
        if messages[0]["content"].startswith("You are the summary agent"):
            reply = {"true_count": 10, "fake_count": 0, "verdict": "true", "justification": "j", "confidence": 0.5}
        else:
            reply = {"judgment": "true", "confidence": 0.9, "reasoning": "r", "evidence": []}
        return json.dumps(reply), "stop"


def test_llm_path_runs_and_requests_are_distinct(tmp_path):
    backend = FakeBackend()
    llm = LLMClient(cache_dir=tmp_path / "cache", backend=backend)
    cfg = MajoritySwayConfig(model=MODEL, role_models=(("summary", "mistral:other"),))
    res = asyncio.run(
        run_sweep(lambda c, r: MajoritySwayScenario(c, r, llm), [cfg], 1, tmp_path / "l.jsonl", "ms", verbose=False)
    )
    assert not res.failed and backend.n == 55
    calls = [r for r in read_log(tmp_path / "l.jsonl") if r["type"] == "call"]
    assert {c["model"] for c in calls if c["agent"] == SUMMARY_ID} == {"mistral:other"}
    assert {c["temperature"] for c in calls if c["agent"] == SUMMARY_ID} == {0.3}
    assert {c["temperature"] for c in calls if c["agent"] != SUMMARY_ID} == {0.7}
