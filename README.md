# mas-risks

This project builds small open-weight agents whose susceptibility to influence is controlled, then runs them in multi-agent risk scenarios. Julian and Ankush work on it.

This project uses the [Epistemic Memory](https://github.com/FlorianDietz/EpistemicMemory) conventions: all project memory lives in LOG/SUMMARY file pairs under `convos/`, governed by [CLAUDE.md](CLAUDE.md). Human guide: [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md). Open ideas and deferred items: [FUTURE_WORK.md](FUTURE_WORK.md). Workflow problems and lessons: [FEEDBACK.md](FEEDBACK.md).

**Papers:** papers relevant to the project are stored as agent-readable markdown under [papers/](papers/README.md), one folder per paper. Each folder holds the converted text and, where we have one, a separate notes file with our own comments. The index and the procedure for adding a paper are in `papers/README.md`.

## Team

- Julian Bitterlich — `convos/julian/` (git user.name: `Julian Bitterlich`)
- Ankush — `convos/ankush/` (git user.name: not yet recorded; add it here on Ankush's first session)

**Identifying the current user:** match `git config user.name` against this list. If it doesn't match anyone or the match is ambiguous, ask before proceeding.

## Current status and goals

Project setup completed 26-11-21. First code (26-11-24): the `mas_sim` simulation library and the authority-deference experiment (re-implemented from Huang et al., arXiv 2603.27771v4) are implemented and tested without API calls; the first live run waits for `.env`. Plan: `convos/julian/26-11-24_mas_sim_plan_DRAFT.md`.

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
| 26-11-24 | julian | Implementation plan: `mas_sim` library + three risk experiments | Milestone 1 implemented (mas_sim core + authority experiment); live run pending `.env` | [SUMMARY](convos/julian/26-11-24_mas_sim_plan_SUMMARY.md) | [LOG](convos/julian/26-11-24_mas_sim_plan_LOG.md) |
| 26-11-24 | julian | Repo layout: where the code lives | Decided and set up: one root pyproject, packages under `src/` | [SUMMARY](convos/julian/26-11-24_repo_layout_SUMMARY.md) | [LOG](convos/julian/26-11-24_repo_layout_LOG.md) |
| 26-11-24 | julian | Code-quality tooling (`make check`: ruff, pyright, pytest) | Implemented, `make check` green; pre-commit/CI open | [SUMMARY](convos/julian/26-11-24_clean_code_SUMMARY.md) | [LOG](convos/julian/26-11-24_clean_code_LOG.md) |
| 26-11-24 | julian | Run viewer: HTML page to step through mas_sim run logs | Built (`scripts/view_runs.py`); interactions not yet hand-tested | [SUMMARY](convos/julian/26-11-24_run_viewer_SUMMARY.md) | [LOG](convos/julian/26-11-24_run_viewer_LOG.md) |
