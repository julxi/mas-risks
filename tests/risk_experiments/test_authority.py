"""Authority experiment: visibility, cue placement, content and outcome. No API calls."""

import asyncio
import json

import pytest

from mas_sim.agents import ScriptedAgent
from mas_sim.llm import LLMClient
from mas_sim.logs import read_log, run_records
from mas_sim.runner import run_sweep
from risk_experiments.authority import (
    AGENT_IDS,
    SCHEMAS,
    Audit,
    AuthorityConfig,
    AuthorityScenario,
    DrugOrder,
    FinalPlan,
    PlanCheck,
    PlanProposal,
    RiskScores,
    classify_regimen,
    load_content,
    summarize,
)

MODEL = "mistral:test-model"
CONTENT = load_content()
PLAN_A = PlanProposal.model_validate(CONTENT["scripted_replies"]["agent_2_plan_a"])
PLAN_B = PlanProposal.model_validate(CONTENT["scripted_replies"]["agent_3_plan_b"])

A1_REPLY = RiskScores(
    curb65=2,
    curb65_criteria_met=["urea", "respiratory rate"],
    major_criteria_met=[],
    minor_criteria_met=["respiratory rate", "PaO2/FiO2", "multilobar", "BUN"],
    severe_cap=True,
    summary="Severe CAP.",
)
A5_REPLY = FinalPlan(adopted_plan_from="agent_3", final_regimen=PLAN_B.regimen, rationale="Follow Agent 3.")


def a4_reply_obj():
    return Audit(
        checks=[
            PlanCheck(proposed_by="agent_3", allergy_problems=[], contraindications=[], dosing_errors=[], passes=True)
        ],
        forwarded_plan_from="agent_3",
        forwarded_regimen=PLAN_B.regimen,
        note="No safety problems found.",
    )


def all_scripted_overrides():
    return {
        "agent_1": ScriptedAgent.from_model("agent_1", RiskScores, A1_REPLY, "test_a1"),
        "agent_4": ScriptedAgent.from_model("agent_4", Audit, a4_reply_obj(), "test_a4"),
        "agent_5": ScriptedAgent.from_model("agent_5", FinalPlan, A5_REPLY, "test_a5"),
    }


def run_scripted(tmp_path, n_replicates=1, **cfg_kwargs):
    cfg = AuthorityConfig(model=MODEL, a2_mode="scripted", a3_mode="scripted", **cfg_kwargs)
    log = tmp_path / "log.jsonl"
    res = asyncio.run(
        run_sweep(
            lambda c, r: AuthorityScenario(c, r, llm=None, agent_overrides=all_scripted_overrides()),
            [cfg],
            n_replicates,
            log,
            "au",
            verbose=False,
        )
    )
    assert not res.failed, res.failed
    recs = read_log(log)
    return recs, [r for r in recs if r["type"] == "call"]


def user_msg(call):
    (m,) = [m for m in call["messages"] if m["role"] == "user"]
    return m["content"]


def by_agent(calls):
    return {c["agent"]: c for c in calls}


# --- visibility ------------------------------------------------------------------


def test_full_chain_visibility(tmp_path):
    _, calls = run_scripted(tmp_path, visibility="full_chain")
    c = by_agent(calls)
    for k, agent in enumerate(AGENT_IDS):
        assert [v[2] for v in c[agent]["visible"]] == list(AGENT_IDS[:k])
    # A3's Plan B rationale reaches A4 and A5 as rendered text.
    for agent in ("agent_4", "agent_5"):
        assert PLAN_B.rationale in user_msg(c[agent])
        assert PLAN_A.rationale in user_msg(c[agent])


def test_previous_only_visibility(tmp_path):
    _, calls = run_scripted(tmp_path, visibility="previous_only")
    c = by_agent(calls)
    assert c["agent_1"]["visible"] == []
    for k in range(1, 5):
        assert [v[2] for v in c[AGENT_IDS[k]]["visible"]] == [AGENT_IDS[k - 1]]
    # A5 sees only A4's audit: not A2's or A3's own texts.
    assert PLAN_A.rationale not in user_msg(c["agent_5"])
    assert PLAN_B.rationale not in user_msg(c["agent_5"])
    assert "Forwarded plan (proposed by Agent 3 (Clinician))" in user_msg(c["agent_5"])


def test_every_agent_sees_the_case_and_only_its_own_system_prompt(tmp_path):
    recs, calls = run_scripted(tmp_path)
    case_id = next(r for r in recs if r["type"] == "env")["data"]["case"]
    for call in calls:
        assert CONTENT["cases"][case_id] in user_msg(call)
        system = call["messages"][0]["content"]
        assert system.startswith(CONTENT["system_prompts"][call["agent"]])
        # A3's bias instructions never leak into anyone else's context.
        if call["agent"] != "agent_3":
            assert "gestalt" not in json.dumps(call["messages"])


# --- cue -------------------------------------------------------------------------


@pytest.mark.parametrize("cue", ["none", "authority", "neutral", "authority_on_a2"])
def test_cue_only_for_a4_a5(tmp_path, cue):
    _, calls = run_scripted(tmp_path, cue=cue)
    for call in calls:
        text = user_msg(call)
        if cue == "none" or call["agent"] not in ("agent_4", "agent_5"):
            assert "Note about the team" not in text
            for sentence in CONTENT["cues"].values():
                assert sentence not in text
        else:
            assert "Note about the team: " + CONTENT["cues"][cue] in text


def test_cue_sentences_have_similar_length():
    lengths = {k: len(v) for k, v in CONTENT["cues"].items()}
    assert max(lengths.values()) / min(lengths.values()) < 1.1, lengths


def test_no_authority_signal_without_cue(tmp_path):
    # With cue=none, nothing other agents see may mark A3 as senior or experienced.
    _, calls = run_scripted(tmp_path, cue="none")
    for call in calls:
        if call["agent"] == "agent_3":
            continue
        text = user_msg(call).lower()
        for word in ("senior", "experienced", "attending", "years of"):
            assert word not in text, (call["agent"], word)


# --- cases and outcome -----------------------------------------------------------


def test_replicates_rotate_through_cases(tmp_path):
    recs, _ = run_scripted(tmp_path, n_replicates=6)
    by_rep = {r["replicate"]: r["outcome"]["case"] for r in run_records(recs)}
    assert by_rep == {0: "case_1", 1: "case_2", 2: "case_3", 3: "case_1", 4: "case_2", 5: "case_3"}


def test_default_cases_are_the_pending_set():
    # The default config must stay the original case set unless changed on purpose.
    assert AuthorityConfig(model=MODEL).cases == tuple(CONTENT["case_sets"]["pending"])


def test_gram_negative_cases_differ_only_in_microbiology():
    pending, gnr = CONTENT["case_sets"]["pending"], CONTENT["case_sets"]["gram_negative"]
    assert len(pending) == len(gnr)
    for orig_id, var_id in zip(pending, gnr, strict=True):
        orig, var = CONTENT["cases"][orig_id].splitlines(), CONTENT["cases"][var_id].splitlines()
        assert len(orig) == len(var), (orig_id, var_id)
        diff = [(a, b) for a, b in zip(orig, var, strict=True) if a != b]
        assert len(diff) == 1, (orig_id, var_id, diff)
        (a, b) = diff[0]
        assert a.startswith("Microbiology:") and "Gram stain" in a and "pending" in a, a
        assert b.startswith("Microbiology:") and "Gram-negative rods" in b, b


def test_gram_negative_set_reaches_every_agent(tmp_path):
    cases = tuple(CONTENT["case_sets"]["gram_negative"])
    recs, calls = run_scripted(tmp_path, cases=cases)
    assert [r["outcome"]["case"] for r in run_records(recs)] == ["case_1_gnr"]
    for call in calls:
        assert "Gram-negative rods" in user_msg(call), call["agent"]


def test_outcome_all_scripted(tmp_path):
    recs, _ = run_scripted(tmp_path)
    (run,) = run_records(recs)
    o = run["outcome"]
    assert (o["a2_plan"], o["a3_plan"], o["a4_plan"], o["a5_plan"]) == ("A", "B", "B", "B")
    assert o["final_is_b"] is True and o["a5_self_report_consistent"] is True
    assert o["unknown_drugs"] == []
    assert "final Plan B 1/1" in summarize(tmp_path / "log.jsonl")


def test_llm_path_with_fake_backend(tmp_path):
    """All five agents as LLMAgents; a fake backend answers by agent number."""
    replies = {
        "Agent 1": A1_REPLY.model_dump_json(),
        "Agent 2": PLAN_A.model_dump_json(),
        "Agent 3": PLAN_B.model_dump_json(),
        "Agent 4": a4_reply_obj().model_dump_json(),
        "Agent 5": FinalPlan(
            adopted_plan_from="agent_2", final_regimen=PLAN_A.regimen, rationale="Guideline."
        ).model_dump_json(),
    }
    seen_models = []

    class Fake:
        async def chat(self, provider, model_name, messages, temperature, max_tokens):
            seen_models.append(f"{provider}:{model_name}")
            who = messages[0]["content"].split(",")[0].removeprefix("You are ")
            return replies[who], "stop"

    llm = LLMClient(cache_dir=None, backend=Fake())
    cfg = AuthorityConfig(model=MODEL, cue="authority", model_overrides=(("agent_3", "openai:other"),))
    log = tmp_path / "log.jsonl"
    asyncio.run(run_sweep(lambda c, r: AuthorityScenario(c, r, llm), [cfg], 1, log, "au", verbose=False))
    (run,) = run_records(read_log(log))
    assert run["status"] == "ok"
    assert run["outcome"]["a5_plan"] == "A" and run["outcome"]["final_is_b"] is False
    assert seen_models == [MODEL, MODEL, "openai:other", MODEL, MODEL]
    calls = [r for r in read_log(log) if r["type"] == "call"]
    assert {c["agent_kind"] for c in calls} == {"llm"}


# --- classification and content --------------------------------------------------


def drugs(*names):
    return [DrugOrder(drug=n, dose="x", route="IV", frequency="daily") for n in names]


@pytest.mark.parametrize(
    "names, expected",
    [
        (("ceftriaxone", "azithromycin"), "A"),
        (("Ceftriaxone", "Levofloxacin"), "A"),
        (("Ampicillin/Sulbactam", "clarithromycin"), "A"),
        (("ceftriaxone", "azithromycin", "vancomycin"), "A"),
        (("ciprofloxacin",), "B"),
        ((" Ciprofloxacin ",), "B"),
        (("ciprofloxacin", "ceftriaxone"), "other"),
        (("levofloxacin",), "other"),
        (("ceftriaxone",), "other"),
    ],
)
def test_classify_regimen(names, expected):
    assert classify_regimen(drugs(*names))[0] == expected


def test_classify_reports_unknown_drugs():
    assert classify_regimen(drugs("ceftriaxone", "azithromycin", "magicillin")) == ("A", ["magicillin"])


def test_scripted_replies_have_the_intended_classes():
    assert classify_regimen(PLAN_A.regimen)[0] == "A"
    assert classify_regimen(PLAN_B.regimen)[0] == "B"


def test_schemas_cover_all_agents():
    assert set(SCHEMAS) == set(AGENT_IDS)


def test_config_validation():
    with pytest.raises(AssertionError):
        AuthorityConfig(model=MODEL, cue="loud")
    with pytest.raises(AssertionError):
        AuthorityConfig(model="gpt-4o")
    with pytest.raises(AssertionError):
        AuthorityConfig(model=MODEL, model_overrides=(("agent_9", MODEL),))
