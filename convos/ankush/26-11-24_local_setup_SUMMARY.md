# SUMMARY: Local setup on Ankush's machine

**Last updated:** 26-11-24 (clone and checks done; git user.name set to `Ankush7890`)

Ankush asked for the repository to be cloned and set up on his machine.

- Cloned to `/home/ankush/Documents/mai_risks/mas-risks`, branch `main`. [verified: `git status -sb`, 26-11-24]
- Ankush's git user.name for this repository is `Ankush7890` [decided] (his chat reply, transcribed in the LOG), recorded in the README team list. It is set in the repository's own git config; the machine's global name is `acheckervarty7890`, which I had first recorded before he corrected it. A fresh clone on this machine therefore needs `git config user.name "Ankush7890"` again, or agents won't match him to the team list.
- The repository has no experiment code yet, so no environment was built. The paper converter (`papers/tools/arxiv_html2md.py`) needs beautifulsoup4, curl, pdftotext and Firefox; all are installed. [verified: import and `which` checks, 26-11-24; converter not run]
- Not created: `.env` (no code reads keys yet), `.venv` (no dependencies beyond the system Python yet).

See also: `convos/julian/26-11-21_project_setup_SUMMARY.md` — the original template configuration, which left Ankush's git user.name to be filled in on his first session.

LOG: `convos/ankush/26-11-24_local_setup_LOG.md`
