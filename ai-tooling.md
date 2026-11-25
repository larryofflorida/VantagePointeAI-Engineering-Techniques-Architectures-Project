# AI tooling

How AI was used to build this project, which AI components run inside it, how outputs were checked, and what is not verified. Written to be read by a reviewer who wants to know *what to trust and why*.

## 1. Summary

| Question | Answer |
|---|---|
| Was AI used to build the project? | **Yes, heavily.** Claude (Anthropic), used through a chat interface with a code sandbox, wrote the code, tests, documents, CI workflow and spreadsheets in this repository, directed step by step by a human. |
| Does AI run inside the product? | **Partly.** The prototype page can ask Claude to write the final answer. Retrieval (BM25) and all MCP tools are ordinary deterministic code. |
| Is the AI-generated *answer quality* measured? | **No.** The build environment had no model access, so no LLM answer-accuracy numbers exist. |
| Is the data real? | **No.** All policies, people and HRIS records are synthetic. |
| What stops AI mistakes from shipping? | Automated tests, an evaluation harness with quality gates, deterministic calculators, and CI. Section 5 lists mistakes these caught. |

## 2. AI used to build the project

### 2.1 Tools and environment

| Tool | Role |
|---|---|
| **Claude (Anthropic), chat interface** | Planned, wrote and revised all code, documentation and tests in response to the human's requests |
| **Code sandbox** (Linux shell, Python 3.12, Node 22, `pdfplumber`, `git`) | Ran every script and test; no network access from the sandbox |
| **Built-in skill instructions** (PDF reading, spreadsheets) | Read before extracting PDF content and before creating the `.xlsx` files |
| **Artifact publishing** | Published the single-file assistant page and declared its `sample` (model-call) capability |

Not used: web search, external APIs, code-completion plugins, or any model other than Claude. The specific Claude model behind the page's `sample` capability is chosen by the host and is not fixed by this project.

### 2.2 Division of work

| Human | AI |
|---|---|
| Set goals, supplied the real inputs (ten VantagePoint policy PDFs and a mock HRIS dataset), chose what to build next | Proposed designs, wrote code and documents, ran tests and reported the results |
| Decides what is acceptable to ship | Flagged gaps and limitations unprompted, such as "no LLM answer accuracy was measured" |
| Reviews and owns the result | Did not independently review its own work beyond the automated checks below |

### 2.3 What AI produced

| Deliverable | Notes |
|---|---|
| Policy corpus (first pass) | A fictional company's 13-document corpus, written from scratch before the real PDFs were supplied |
| PDF → markdown converter | Custom: the source PDFs' text layers run past the page edge and clipped table cells under normal extraction |
| Chunking, retrieval, assistant page | Section-level chunks, in-browser BM25, a cited-answer prompt |
| Tool layer and MCP server | 11 read-only tools, strict schemas, stdio server |
| Evaluation | 91-question gold set, harness, k and chunking study, demo traces |
| CI/CD and docs | GitHub Actions workflow, `Makefile`, 51 tests, `README.md`, `design-and-evaluation.md`, `DEPLOYMENT.md`, two spreadsheets, this file |

## 3. AI inside the product

| Component | AI? | Description |
|---|---|---|
| PDF conversion, chunking | No | Deterministic scripts |
| Retrieval | No | BM25 with stop-words and synonyms; verified identical between the JavaScript and Python implementations on all 91 evaluation questions |
| MCP tools (11) | No | Deterministic lookups and calculators (PTO forfeiture, remaining work-from-anywhere days, notice rules, date math) |
| Answer generation | **Yes** | Claude, called by the page through the host's `sample` capability. It receives the question, the top 6 retrieved passages and the signed-in employee's record |
| Embeddings, vector store, LLM judge | Not built | Planned only; see `design-and-evaluation.md` §1.1 |
| Agent orchestrator | Not built | The prototype is a single retrieve-then-answer call. The multi-step tool loop is a design |

### 3.1 Prompt design (in `assistant/template.html`, the `RULES` constant)

* Answer **only** from the supplied excerpts and employee record.
* Cite every policy claim as `[POL-XXX-NNN §n]` using the excerpt labels, and show arithmetic with an "as of" date.
* If the excerpts don't answer the question, say so and refer to People Operations.
* If excerpts disagree, present both with citations. The prompt lists the known conflicts in the policy set.
* Never reveal other employees' data; no legal advice; be concise.

### 3.2 What happens to data when the model is called

The question, retrieved policy text and the selected employee's record are sent to the model provider through the host. With synthetic data that is harmless. With real data it would need a data-processing agreement, a no-training or zero-retention setting, and data minimization. The tool layer already omits compensation unless asked, but the prototype page still sends the full record and embeds all 13 synthetic employees in its source.

## 4. Checking AI output

| Check | What it covers | Result |
|---|---|---|
| Unit, start-up, MCP and build tests | Tool logic, schema strictness, server start-up, MCP discovery and calls, conversion regressions | 51 tests pass |
| Evaluation gates | Retrieval thresholds, JS/Python parity, tool values, guardrails, MCP protocol | Hit@1 80.2%, Hit@6 97.5%, all answer facts in top 6 91.4% |
| Mutation checks | Deliberately breaking the code to confirm gates fail | 5 breakages tried; 1 initially slipped through and was fixed |
| Label validation | Gold answers checked against the source text | Found one wrong label before results were reported |
| **Not checked** | Generated-answer accuracy, faithfulness, refusal behavior, prompt-injection resistance of the model | See `design-and-evaluation.md` §9.7 for the rubric and scoring script |

The numbers above are not a measure of how good the model's answers are; they cover retrieval and tooling only.

## 5. Mistakes AI made that were caught

Listed because they show which checks are doing real work.

| Mistake | How it was caught | Fix |
|---|---|---|
| A gold label expected text that wasn't in the source chunk (question P11) | Label-validation step in the evaluation harness | Label corrected before any result was reported |
| Six "must-include" answer literals were stricter than the AI's own expected answers | Scorer self-test | Literals relaxed |
| The MCP smoke test counted tools but not names, so renaming a tool passed | Mutation check | Test now asserts the exact tool names |
| The Python server ran Node.js at import time and crashed without Node | Cold-start review for the deployment document | Parameters exported at build time; a test starts the server with no Node on `PATH` |
| The expected Demo A answer states a date ("eligible about Jan 10, 2027") that no tool call produced | Review of the demo trace | Date confirmed with `date_math` (90 days); the trace still needs that call added |
| First-pass holiday text was muddled | Self-review before delivery | Rewritten |
| Early PDF extraction clipped table cells | Visual and character-level inspection | Custom converter plus regression tests |

## 6. Risks and limits of AI use here

* **Hallucination.** The model can state policy or numbers that aren't in the excerpts. Mitigations: grounding rules, mandatory citations, calculators. The planned verifier that rejects uncited or ungrounded numbers is not built.
* **Silent conflicts.** The source policies contradict each other in places (e.g., 2-hour vs 30-minute lost-device reporting). Retrieval sometimes returns only one side; this was measured, not fixed.
* **Prompt injection.** Policy and ticket text is labeled untrusted and the corpus is scanned for injection phrases (none found), but the model's resistance has not been tested.
* **Non-determinism.** Model answers can vary between runs; only deterministic components have reproducible tests.
* **Evaluation bias.** The question set was written by the same AI that built the retrieval, after reading the corpus, so retrieval numbers are optimistic for real traffic.
* **Over-trust.** A fluent, cited answer is not proof of correctness. Anything affecting pay, leave or employment should be confirmed with People Operations.

## 7. Guidance for people extending this project

1. Treat AI-written code like any other contribution: review it and keep the test suite green (`make test`).
2. Run the evaluation (`python evaluation/run_eval.py`) after any change to chunking, synonyms, prompts or tools, and don't tune on the same questions you report on; split off a held-out set first.
3. Before enabling generated answers for real users, run the answer-quality suite with an independent judge plus human spot-checks, and set release thresholds.
4. Keep authorization in code (the session-bound tools), never in the prompt.
5. Record the exact model and prompt version used for any measured result, since answers depend on both.

## 8. Reproducing and auditing

```bash
make PY=python3 build check-generated import-check smoke-mcp test   # build and verify everything deterministic
python evaluation/run_eval.py                                       # evaluation results (evaluation/results.json)
python evaluation/demo_traces.py                                    # the two scripted tool-call demos
python scripts/measure_cold_start.py                                # start-up timings (current server median: 20.2 ms)
```

Related documents: `design-and-evaluation.md` (architecture, guardrails, evaluation), `DEPLOYMENT.md` (deployment status, environment variables, cold start), `README.md` (setup and CI).
