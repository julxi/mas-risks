# SUMMARY: "Emergent (Social Intelligence) Risks in Generative MAS": workshop vs arXiv v4

**Last updated:** 26-11-21 (comparison done; the arXiv v4 edition was then added to `papers/2603.27771_emergent_mas_risks/` at the user's request)

The user asked to compare two papers:
- OpenReview Jg9BGDTsxt, the ICML 2026 workshop version. The PDF is at the repo root as `68_Emergent_Social_Intelligenc.pdf`.
- arXiv 2603.27771, latest version v4 (29 Oct 2026).

**They are two editions of the same paper** by Huang et al. (Notre Dame et al.), with the same 15 multi-agent risk scenarios, experiments and numbers. [verified: text diff + reading]

**How they differ** [verified]:
- The title dropped "Social Intelligence" in arXiv v3.
- The workshop version has a compressed main text and puts the risk details in the appendix. v4 gives each risk its own section and redraws the figures with exact counts.
- The workshop version has a Related Work section, a Discussion with concrete mechanism-level design proposals, and a Limitations section. **v4 has none of these.**
- v4 links a toolkit: https://github.com/HowieHwong/RiskLab

**Problems found** [verified]:
1. The workshop main text claims agents successfully developed steganography (Risk 4.2). Its own appendix, and v4, report 0 of 10 successful runs.
2. The data in the majority-sway news experiment (Risk 2.1, table identical in both versions) contradicts its interpretation:
   - The final verdict follows the agent majority in only 4 of 9 runs.
   - The text's "only E7 had a false-majority" claim is wrong.
3. For 11 of 15 risks, neither version names the LLM used.
4. Small n (3–10 runs per condition) and no confidence intervals. [concluded]

**Relevance** [assumed]: this is the closest prior work to mas-risks. Its influence manipulations are prompt-only and its agents are closed models, so small open-weight agents with controlled susceptibility to influence would be new relative to it.

LOG: `convos/julian/26-11-21_emergent_mas_risks_versions_LOG.md`
- See also: `convos/julian/26-11-21_papers_library_SUMMARY.md`. The papers library is where these would go if the user later wants them stored.
- See also: `convos/julian/26-11-24_mas_sim_plan_SUMMARY.md` — implementation plan that re-implements three of this paper's experiments; its §6 notes build on the problems found here.
- See also: `convos/julian/26-11-25_majority_sway_SUMMARY.md` — our re-implementation of the majority-sway news experiment; with mistral-small the analysts rejected the claim from prior knowledge, so no false majority formed.
