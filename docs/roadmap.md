# Roadmap

This roadmap describes the next likely steps from the current MVP toward a multi-agent Erdős Problems research workflow.

Last updated: 2026-05-03.

## Current Capability

The project can:

- ingest official metadata from `teorth/erdosproblems`
- optionally fetch statements and remarks from `erdosproblems.com/latex/<n>`
- rank local problems with `triage-all`
- produce blind solver packets
- produce literature packets
- create statement audits and claim cards
- search for transfer candidates from a seed problem
- store literature findings and examples
- create and execute local agent-run jobs through inbox/outbox JSON files

## Near-Term Plan

### Phase 1: Make the Local Workflow Comfortable

Goal: make it easy for a contributor to reproduce the baseline state.

Tasks:

- Add a `make` or script wrapper for common commands.
- Add a sample end-to-end workflow in `docs/quickstart.md`.
- Add schema examples for problem JSON, run JSON, finding JSON, example JSON, and claim cards.
- Add `--dry-run` to commands that write many artifacts.
- Add better reporting for skipped/failed statement fetches.

Success criteria:

- A new contributor can clone the repo, run one documented command sequence, and produce triage results for a small batch.

### Phase 2: Literature Agent MVP

Goal: move from query suggestions to useful source-aware literature reports.

Tasks:

- Add a `literature-search` command that reads local problem data and writes source-aware search artifacts.
- Generate source-specific query plans for arXiv, OEIS, Google Scholar-style search, and general web search.
- Implemented first external metadata search pass for arXiv and Crossref.
- Store findings with `add-finding`.
- Add `promote-search-result` to convert a search result into an unreviewed finding and pivot candidates.
- Add `queue-pivots` to turn approved pivot candidates into follow-up agent runs.
- Generate anonymous Result Cards for solver-facing use.
- Add pivot logic so a strong finding can suggest changing the target problem.

Design rule:

- Literature Agent may know sources.
- Blind Solver receives only anonymized mathematical Result Cards.

Success criteria:

- For one problem, the system can create a literature report, at least one finding, and a pivot candidate list without manual file editing.

### Phase 3: Computation Harness

Goal: make computation jobs reproducible.

Tasks:

- Create `computations/epNNNN/search.py` templates.
- Add `results.md` logging conventions.
- Add standard fields for parameters, seeds, bounds, hardware/runtime, and verification.
- Support finite search/counterexample search plans.
- Support OEIS small-value reproduction where appropriate.

Success criteria:

- A computation agent can run a bounded search and produce a reproducible artifact that a critic can inspect.

### Phase 4: Real Multi-Agent Automation

Goal: connect the file-based job queue to Codex automations.

Tasks:

- Define one automation prompt per agent role.
- Have automations read `agent_runs/inbox/*.json`.
- Have automations write artifacts and call `complete-run`.
- Add `claim-card` generation as a required output for proof-like attempts.
- Add Supervisor rules for pivot approval.

Success criteria:

- A batch of jobs can be processed asynchronously without losing provenance or leaking source metadata to blind solver runs.

### Phase 5: Lean/Formalization Gate

Goal: introduce formal verification without misformalization.

Tasks:

- Detect local Lean/lake availability.
- Add theorem statement templates under `lean/epNNNN/`.
- Add checks for `sorry`, `admit`, `axiom`, and unsafe constructs.
- Add informal-to-formal statement correspondence reports.
- Separate theorem-statement authoring from proof generation.

Success criteria:

- At least one simple known/solved statement can be formalized or inspected with a documented build/check path.

### Phase 6: Referee Gate and Submission Packager

Goal: prepare human-reviewed outputs only.

Tasks:

- Add `referee-gate` command.
- Require literature status, statement audit, computation/Lean checks where relevant, and human-readable proof sketch.
- Generate forum/comment/PDF/GitHub package drafts.
- Include mandatory AI-use disclosure.
- Keep posting as a human-only action.

Success criteria:

- The system can say `do_not_post`, `needs_human`, `ask_expert`, or `prepare_package` with clear reasons.

## Medium-Term Research Features

### Method Cards

When a problem is solved or a strong partial method appears, create a reusable Method Card:

```text
source problem
exact claim solved
method summary
key lemmas
examples/extremizers
failure modes
nearby open problems
formalization notes
```

Then run:

```bash
python3 -m erdos_agent transfer-search SEED
```

or pivot from the corresponding finding.

### Example Bank

Examples should be stored even when they do not solve a problem.

Important example types:

- extremal constructions
- counterexamples
- small cases
- model examples
- sharpness examples
- OEIS initial values
- Lean sanity-check examples

### Problem Family Clustering

The current `transfer-search` is simple. Later versions should cluster problems by:

- tags
- statement embeddings
- reference graphs
- method cards
- examples
- OEIS sequences
- formalization dependencies

## Open Design Questions

- Should generated `data/` and `reports/` remain local-only, or should selected artifacts be published in a separate private repo?
- Which external literature APIs should be integrated first?
- Should Blind Solver execution be local Codex only, or also model-API driven?
- How should human review approvals be represented in files?
- How strict should public artifact redaction be?

## Recommended Immediate Next Step

Create a small contributor-facing quickstart:

```bash
python3 -m erdos_agent ingest-github --status open --limit 10 --fetch-statements
python3 -m erdos_agent triage-all --status open --limit 10
python3 -m erdos_agent create-run --from-triage --agent literature --action literature_review --limit 2
python3 -m erdos_agent supervisor-step
```

Then have one contributor run a Literature Agent job manually and record the result as a finding.
