# Note for Julian: three things that need your agreement

26-11-24, written by Claude Fable 5.2 on Ankush's behalf. Ankush asked for this note; the wording and the recommendations are the agent's. Please answer inline with `C:` comments and sign them with your name, since this file is in Ankush's folder, or tell Ankush directly.

**Background you need.** The research plan is now in the repo as `docs/research_agenda.md`. Ankush is its Researcher A: he builds the "model organisms", versions of Qwen3-4B-Instruct whose tendency to give in to other agents is set by a prompt, a steering vector or a LoRA adapter, and the eval that measures them. That makes you Researcher B, who builds the simulations S1–S3 and the instrumental hooks; this is an assumption from the plan, so correct it if it is wrong. His variants plug into your simulations at the plan's week-4 gate. The three points below were settled on his side on 26-11-24 without you, and each constrains your work.

## 1. One shared Python environment at the repository root

**What was done.** `pyproject.toml`, `uv.lock` and an exported `requirements.txt` sit at the repo root and define one environment for all code. Main versions: torch 2.15.0, transformers 5.24.0, peft 0.22.0. Install with `uv sync` (README, section "Environment"). It has not been installed or tested on any machine yet.

**Why it concerns you.** `docs/CODING.md` prescribes a separate `pyproject.toml` per project under `projects/<name>/`. The shared environment departs from that so that an adapter trained by Ankush is loaded in your simulations by the same library versions that trained it.

**What it costs you.** Any dependency you add goes into the shared file and must resolve together with torch and transformers. vLLM was left out for that reason: it pins its own torch version. If you want a batched inference server, it would live in a separate environment used only for serving.

**Asked of you:** agree, or say which dependencies you need that would not fit.

C: (Julian) agreed

## 2. One shared code package

**Proposal.** Shared code goes into one installable package `src/mas_risks/` with a subpackage each for the model organisms and the simulations, and common modules for loading a model variant, parsing agent output, and logging. Nothing has been written yet.

**Why it concerns you.** Two interfaces have to be the same on both sides, and it is cheaper to fix them now than at week 4:
- **Loading a variant.** One function that takes a variant name (base, prompt persona, steering at a given strength, naive LoRA, discerning LoRA) and returns something your simulation can call to generate a reply.
- **Agent output.** The plan's JSON format (decision, confidence 0–100, a reason of at most 60 words, optionally one action). Ankush's eval will use the same format and the same parser as your simulations.

**Asked of you:** agree to the single package, or say that you prefer separate `projects/` folders that share only the environment. If you agree, say what your simulations need from the variant-loading function (single replies or batches, chat messages or raw text).

C: (Julian) Yes to shared code, but with the current layout instead of a single mas_risks package: one root pyproject.toml, sibling packages under src/. Details and reasoning: convos/julian/26-11-24_repo_layout_SUMMARY.md

## 3. Content reserved for your simulations

**The problem.** The LoRA adapters are trained on short dialogues in which a model answers a question about a document and is then pushed to change its answer. If those training documents resemble what your simulations show the agents, a good simulation result would only show that the adapter had seen similar material, not that a trained disposition carries over to a new setting. The second is what the plan claims.

**What Ankush's side will keep out of all training and validation data:**
- access policies and access requests (your S2),
- fact-check claims of the FEVER kind (your S1),
- task boards with tips and planted instructions (your S3),
- the title "senior admin" for an authority figure (your S2),
- stop instructions of any kind (they are held out for the corrigibility check and for your `ignore_stop` hook),
- pressure by plain repetition (held out as a test-only kind of pressure).

**Asked of you:**
- Add anything else your scenarios use that should be reserved: document types, role titles, action names, the wording of the operator channel.
- Share the system prompt your simulation agents get once it exists. It will be used as the held-out system prompt of the eval and kept out of training.
- Tell Ankush if a scenario changes later in a way that touches this list.

C: (Julian) Ok, fine with me

## Two smaller points from the plan, in your lane

- The plan says "no API costs" and also offers GPT-4o as a judge. One of the two has to give.  
C (Julian): There's always some cost. If we host a model ourselves or pay an API.
- Your notes on the Risk 2.1 data (`papers/2603.27771_emergent_mas_risks/notes.md`: the Summary agent said TRUE in four runs where most panel agents said FAKE) matter for the S1 baseline. A base model that gets S1 wrong may be biased toward one verdict, not conforming, and only the stances-hidden condition separates the two.  
C (Julian): if base results are irreproducible we have to dicsuss what to do then

Full reasoning and the data plan: `convos/ankush/26-11-24_model_organisms_SUMMARY.md`.
