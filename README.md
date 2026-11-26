# mas-risks

This project builds small open-weight agents whose susceptibility to influence is controlled, then runs them in multi-agent risk scenarios. Julian and Ankush work on it.

This project uses the [Epistemic Memory](https://github.com/FlorianDietz/EpistemicMemory) conventions: all project memory lives in LOG/SUMMARY file pairs under `convos/`, governed by [CLAUDE.md](CLAUDE.md). Human guide: [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md). Open ideas and deferred items: [FUTURE_WORK.md](FUTURE_WORK.md). Workflow problems and lessons: [FEEDBACK.md](FEEDBACK.md).

**Papers:** papers relevant to the project are stored as agent-readable markdown under [papers/](papers/README.md), one folder per paper. Each folder holds the converted text and, where we have one, a separate notes file with our own comments. The index and the procedure for adding a paper are in `papers/README.md`.

## Team

- Julian Bitterlich — `convos/julian/` (git user.name: `Julian Bitterlich`). Researcher B of the research plan (simulations S1–S3 and instrumental hooks); assumed by elimination, not yet confirmed by Julian.
- Ankush — `convos/ankush/` (git user.name: `Ankush7890`). Researcher A of the research plan (model organisms and their evals).

**Identifying the current user:** match `git config user.name` against this list. If it doesn't match anyone or the match is ambiguous, ask before proceeding.

## Current status and goals

The research plan is [docs/research_agenda.md](docs/research_agenda.md): four research questions, three simulations, two researchers, about 8 part-time weeks.

As of 26-11-25: the shared Python environment installs with `uv sync` on Python 3.14 and `make check` passes on it (one Linux machine with an NVIDIA GPU; no model loaded yet). Researcher A's work on the susceptibility eval, steering vectors and LoRAs is at the design-proposal stage, with no code written (see the model-organisms topic in the index below).

Project setup completed 26-11-21. First code (26-11-24): the `mas_sim` simulation library and the authority-deference experiment (re-implemented from Huang et al., arXiv 2603.27771v4) are implemented and tested without API calls; live smoke runs worked with three models (26-11-24/25). Julian decided (26-11-25) to leave the authority experiment as it is: in its current single-pass form it reduces to single-agent tests, so it is not really a multi-agent risk. The majority-sway experiment is implemented and smoke-tested (26-11-25), but with mistral-small no false majority formed, so it needs a different claim before it measures anything. The plan DRAFT was deleted at Julian's request on 26-11-26 (last version in git commit a99f591); its history is in `convos/julian/26-11-24_mas_sim_plan_SUMMARY.md`.

**Open for Julian:** three points need his agreement before code is written: the shared environment, a shared code package, and content reserved for his simulations. They are in [convos/ankush/26-11-24_note_for_julian.md](convos/ankush/26-11-24_note_for_julian.md).

## Environment

One Python environment at the repository root serves all code, so both researchers run the same library versions. `pyproject.toml` lists the direct dependencies, `uv.lock` pins every package, and `requirements.txt` is exported from the lock. Python 3.14 or newer (the simulation code relies on 3.14 behaviour; uv downloads it if missing); a Linux machine with an NVIDIA GPU for anything that loads a model.

With [uv](https://docs.astral.sh/uv/) (preferred, installs exactly what the lock says):

```bash
uv sync                      # creates .venv with runtime and dev packages
source .venv/bin/activate
```

With plain pip:

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Check that the GPU is visible:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

To add or upgrade a dependency, edit `pyproject.toml`, then regenerate the other files and commit all of them together:

```bash
uv lock                      # add --upgrade to move everything to the newest versions
uv export --frozen --no-hashes --no-dev   --format requirements-txt -o requirements.txt
uv export --frozen --no-hashes --only-dev --format requirements-txt -o requirements-dev.txt
```

Keys such as a Hugging Face token go in a `.env` file at the repository root, which git ignores.

## Maintenance

Recurring tasks:

| Task | Last run | Due when | Notes |
|------|----------|----------|-------|
| Sync (LOG/SUMMARY drift) | — | After many LOG changes, or ~monthly | `!sync`; procedure: `docs/procedures/sync.md` |
| LLM-ism checklist refresh | — | ~Monthly while you publish regularly; otherwise before any high-stakes submission | Update the checklist and Known-screening sections of `docs/procedures/outward_text.md` from full primary sources (see the file's refresh rule); bump its refresh date |

## Conversation Index

All discussions live in `convos/{user}/`. **When starting a new topic, add a row here.** Read the SUMMARY first; open the LOG only if the SUMMARY is insufficient. Status cells describe current state only — rewrite them on update, don't append.

| Date | User | Topic | Status | SUMMARY | LOG |
|------|------|-------|--------|---------|-----|
| 26-11-21 | julian | Project setup (template configuration) | Done | [SUMMARY](convos/julian/26-11-21_project_setup_SUMMARY.md) | [LOG](convos/julian/26-11-21_project_setup_LOG.md) |
| 26-11-21 | julian | Papers library (`papers/` folder, conventions, converter) | Set up; 2 papers added | [SUMMARY](convos/julian/26-11-21_papers_library_SUMMARY.md) | [LOG](convos/julian/26-11-21_papers_library_LOG.md) |
| 26-11-21 | julian | Emergent MAS risks paper: workshop (OpenReview) vs arXiv v4 | Compared; v4 stored in papers/ | [SUMMARY](convos/julian/26-11-21_emergent_mas_risks_versions_SUMMARY.md) | [LOG](convos/julian/26-11-21_emergent_mas_risks_versions_LOG.md) |
| 26-11-24 | julian | Implementation plan: `mas_sim` library + three risk experiments | Milestone 1 implemented; authority experiment frozen as-is (smoke-tested with three models; judged not really a MAS risk in its current form); no full sweep | [SUMMARY](convos/julian/26-11-24_mas_sim_plan_SUMMARY.md) | [LOG](convos/julian/26-11-24_mas_sim_plan_LOG.md) |
| 26-11-24 | julian | Repo layout: where the code lives | Decided and set up: one root pyproject, packages under `src/` | [SUMMARY](convos/julian/26-11-24_repo_layout_SUMMARY.md) | [LOG](convos/julian/26-11-24_repo_layout_LOG.md) |
| 26-11-24 | julian | Code-quality tooling (`make check`: ruff, pyright, pytest) | Implemented, `make check` green; pre-commit/CI open | [SUMMARY](convos/julian/26-11-24_clean_code_SUMMARY.md) | [LOG](convos/julian/26-11-24_clean_code_LOG.md) |
| 26-11-24 | julian | Run viewer: HTML page to step through mas_sim run logs | Built (`scripts/view_runs.py`); interactions not yet hand-tested | [SUMMARY](convos/julian/26-11-24_run_viewer_SUMMARY.md) | [LOG](convos/julian/26-11-24_run_viewer_LOG.md) |
| 26-11-24 | ankush | Local setup on Ankush's machine (clone, tool checks, git user.name) | Done | [SUMMARY](convos/ankush/26-11-24_local_setup_SUMMARY.md) | [LOG](convos/ankush/26-11-24_local_setup_LOG.md) |
| 26-11-24 | ankush | Model organisms: susceptibility eval, steering vectors, naive and discerning LoRAs; also the research plan and the shared environment | Plan and environment added; eval and data design settled on Ankush's side; waiting for Julian's answers; no code yet | [SUMMARY](convos/ankush/26-11-24_model_organisms_SUMMARY.md) | [LOG](convos/ankush/26-11-24_model_organisms_LOG.md) |
| 26-11-25 | julian | Majority-sway experiment (Risk 2.1): implementation and smoke run | Implemented, smoke run 0/3 "true"; no false majority formed (model's prior rejects the claim); claim choice open | [SUMMARY](convos/julian/26-11-25_majority_sway_SUMMARY.md) | [LOG](convos/julian/26-11-25_majority_sway_LOG.md) |
