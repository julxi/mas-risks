# SUMMARY: Model organisms (susceptibility eval, steering vectors, LoRAs)

**Last updated:** 26-11-24 (design settled on Ankush's side; waiting for Julian's answers to the note; no code yet)

**Roles.** Ankush is Researcher A of the research plan: he builds the model organisms (agents whose susceptibility to influence is set by a prompt, a steering vector or a LoRA adapter) and the evals that measure them. [decided] Julian is then Researcher B (simulations S1–S3) [assumed: not confirmed by Julian].

**Research plan.** `docs/research_agenda.md` holds Ankush's plan, converted from his Word document; it is the working copy. The three numbers I checked against the papers in `papers/` match. [verified: 26-11-24] Three points raised for discussion: the Risk 2.1 result the plan cites fits an answer bias as well as conformity (per Julian's paper notes), "no API costs" conflicts with GPT-4o as a judge option, and the "RL vs RLHF" wording is confounded in the source paper.

**Environment.** One shared environment at the repository root [decided], which departs from the per-project layout in `docs/CODING.md` so that both researchers run identical library versions; Julian has not been asked [assumed]. `pyproject.toml` lists direct dependencies, `uv.lock` pins all 91 packages, `requirements.txt` and `requirements-dev.txt` are exported from the lock for pip. Main versions: torch 2.15.0, transformers 5.24.0, peft 0.22.0. **Nothing has been installed or imported anywhere**; the environment is to be created on the 24 GB GPU machine [decided], whose GPU model and driver are unknown. Install instructions: README.md, section "Environment". Left out on purpose: vLLM, an OpenAI client, trl, Unsloth, interpretability libraries, Jupyter (reasons in the LOG, section 2).

**Design** (LOG sections 3, 5 and 6):
- Eval: three turns per item (answer, pushback, final answer) in the simulations' JSON format; six pushback conditions including a neutral control. [assumed]
- Items are script-generated questions about an invented document with one passage withheld. [decided] We chose this over filtering an existing dataset because the research plan's rule "keep only items the base model solves" cannot measure evidence sensitivity: no valid argument exists against a correct answer.
- One pool of about 500 items, pushed in both directions. [decided] Proposed mechanism: every item exists in two versions that differ only in the withheld passage, one where the default first answer is correct and one where it is wrong. [assumed]
- Repetition is held out from all training as a pushback type. [decided]
- Qwen3-4B-Instruct-2507 first, the Thinking model later. [decided]
- Shared code [decided], read as one installable package `src/mas_risks/` for both researchers [assumed: my reading; Julian not asked].
- Releases go to the Hugging Face user account `Ankush7890` [verified: whoami endpoint, 26-11-24]; whether its token may write repositories is unchecked.
- Details of the 24 GB machine are set aside for now [decided], so the environment remains untested.
- Steering: mean activation difference between forced "hold" and forced "yield" replies; strength in units of that difference's norm. [assumed]
- LoRAs: naive holds under everything (including when its first answer is wrong); discerning holds under pressure, updates on valid arguments and legitimate operator instructions. Three seeds each; checkpoints and adapter scaling to get pairs matched on pressure sensitivity. [assumed]

**Held-out data plan** (LOG sections 6 and 7; proposed at Ankush's request; [assumed] except where marked):
- Five sets: dev (generator tuning, discarded), train (steering extraction and LoRA training), val (all selection), test-seen and test-unseen (reported numbers only). Sizes in items: 100, about 1,000 and 150 [assumed]; 250 and 250 for the two test sets [decided], chosen over 350/150 so the unseen-family comparison is as precise as the seen-family one (about ±6.2 points at a rate near 50%).
- Four levels of holding out: new items everywhere; pushback wordings and fillers used only in test; four of about twelve item families used only in test-unseen; repetition only in test, not even in val.
- Pressure messages must carry no information (the prompt says the other agents saw the same partial document), and valid and misleading arguments differ only in whether the inference holds. An earlier idea, a misleading argument that misquotes the withheld passage, was dropped because the model cannot detect it.
- Reserved: anything resembling Researcher B's simulation content (to be agreed with Julian), and all stop instructions [decided], so the corrigibility check is a held-out instruction type.
- Two Anthropic models write the pushback wordings, one for dev, train and val and the other for test [decided]; proposed: Claude Sonnet 5.5 and Claude Opus 5.5 [assumed]. Two models of one family share a style, so the held-out-wording claim is weaker than with two families.
- Arguments are assembled by the item generator and only rephrased by a model [decided]. Code checks on every rephrasing (numbers, names and quoted passage unchanged; length band; side-by-side log) guard against the model changing an argument's logic.
- Split specification committed before data is generated; base-model filter applied identically to all sets; seven automated leak checks; hashed manifest; a log of every run on a test set.

**Item families** (LOG section 8; accepted by Ankush [decided]): twelve families, each a document type with a question type, e.g. leave policy × entitlement, print-shop price list × total cost. Eight are seen in training; four (train timetable, grant budget, greenhouse sensor log, parcel sorting) appear only in test. One item is worked through with all six pushback messages. In the pressure and neutral conditions the two versions of an item are the same prompt, so they run once per item, and this eval cannot score over-resistance to a correct majority; only the simulations can.

**Cost of the wordings** (LOG sections 11 and 13; rough, from assumed token counts, possibly off by a factor of two): about $22 at standard prices or about $11 through the Batch API for rephrasing about 5,250 arguments with Sonnet 5.5 on the training side and Opus 5.5 on test, plus under $5 for the item-independent messages. This is a one-time exception to the research plan's "no API costs".

**Open:** Julian's answers to `convos/ankush/26-11-24_note_for_julian.md` (shared environment, shared package, content reserved for his simulations); Ankush's confirmation of the two model names; an Anthropic API key and the `anthropic` package when wording generation is implemented; the 24 GB machine's details. Proposed first implementation step (LOG section 14): item generator for the twelve families, split specification and leak checks, which need no GPU.

See also:
- `papers/2603.27771_emergent_mas_risks/notes.md` — Julian's check of the Risk 2.1 data, which bears on how the S1 baseline is read.
- `papers/2502.12206_paperclip_maximizer/notes.md` — caveats on the 43% vs 21% figure the plan cites.
- `convos/ankush/26-11-24_local_setup_SUMMARY.md` — the clone and first setup on Ankush's laptop.

LOG: `convos/ankush/26-11-24_model_organisms_LOG.md`
