# Work History

This document records the project state so new collaborators can join without reading the full chat history.

Last updated: 2026-05-03.

## Project Goal

Build a Codex-based research operations system for Erdős Problems.

The goal is not to claim automatic solutions. The system should help humans and agents:

- ingest official problem metadata
- triage promising targets
- hide open-problem/source metadata from Blind Solver agents
- run literature, computation, formalization, and critic workflows
- store reusable examples and methods
- create auditable packages before any human-facing claim

## Guiding Principles

- Do not auto-post to Erdős Problems or GitHub issues.
- Do not claim novelty without literature review.
- Keep Blind Solver agents source-blind.
- Keep Supervisor/status-aware review separate from solver attempts.
- Treat Lean as a verification aid, not as proof that the original informal statement was captured correctly.
- Prefer small, reviewable artifacts over broad autonomous claims.

## Implemented Milestones

### Initial MVP

Commit: `e797b70 Initial Erdos agent MVP`

Added:

- package skeleton
- CLI entry point
- local problem JSON schema
- blind solver packet generation
- literature packet generation
- statement audit template
- claim card template
- tests for core packet behavior

Main commands:

```bash
python3 -m erdos_agent init
python3 -m erdos_agent new 728 --statement-file statement.txt
python3 -m erdos_agent pipeline 728
```

### GitHub Ingest and Triage Ranking

Commit: `fb4cec0 Add GitHub ingest and triage ranking`

Added:

- import from `teorth/erdosproblems` `data/problems.yaml`
- optional statement fetch from `https://www.erdosproblems.com/latex/<n>`
- local conversion into `data/problems/epNNNN.json`
- `triage-all` ranking
- statement-present checks before blind packet generation

Main commands:

```bash
python3 -m erdos_agent ingest-github --status open --limit 30 --fetch-statements
python3 -m erdos_agent triage-all --status open --limit 30
```

### Transfer and Knowledge Base Workflows

Commit: `2e3a6ab Add transfer and knowledge base workflows`

Added:

- `transfer-search`
- `add-finding`
- `pivot-from-finding`
- `add-example`
- Karpathy-style LLM Wiki-inspired knowledge base layout
- first-class mathematical example storage
- multi-agent protocol documentation

Purpose:

- When a problem is solved or a promising method is found, search for similar open problems.
- If literature search finds a more promising target, allow Supervisor to pivot.
- Store examples, constructions, counterexamples, and method notes as reusable research assets.

### Agent Run Queue

Commit: `0d4c970 Add agent run queue`

Added:

- `agent_runs/inbox/*.json`
- `agent_runs/outbox/*.json`
- `create-run`
- `list-runs`
- `complete-run`
- `supervisor-step`

Purpose:

- Make Codex automations and multiple human/agent contributors coordinate through durable JSON jobs.
- Avoid relying on hidden chat state.

### Built-in Agent Run Workers

Commit: `2059603 Add built-in agent run workers`

Added:

- `run-agent RUN_ID`
- deterministic MVP workers for:
  - `literature`
  - `computation`
  - `statement_auditor`
  - `formalization`
  - `critic`
  - `blind_solver`

Current behavior:

- `literature` writes `reports/literature/epNNNN.md`
- `computation` writes `computations/epNNNN/README.md`
- `statement_auditor` writes `reports/statement_audits/epNNNN.md`
- `formalization` writes `lean/epNNNN/README.md`
- `critic` writes `reports/referee/epNNNN.md`
- `blind_solver` prepares `packets/blind/*.md` and a manifest, then marks the run as `needs_human`

### External Literature Search

Commit: `1cf5fb3 Add external literature metadata search`

Added:

- `literature-search`
- arXiv and Crossref metadata search
- source-aware search artifacts under `reports/literature/search/`
- solver-facing anonymous Result Cards under `reports/literature/result_cards/`
- redaction for direct source/status leaks in solver-facing snippets

### Queue-to-Pivot Literature Trial

Added:

- `promote-search-result`
- `review-search-results`
- `approve-promotion-candidate`
- `supervisor-step` review candidate summary
- promotion artifacts under `reports/literature/promotions/`
- Supervisor review artifacts under `reports/literature/review/`
- search-result promotion into `unreviewed` findings
- automatic `pivot-from-finding` execution after promotion
- `queue-pivots` for turning top pivot candidates into follow-up agent runs

Trial commands:

```bash
python3 -m erdos_agent create-run --from-triage --agent literature --action literature_review --limit 3
python3 -m erdos_agent run-next-agent
python3 -m erdos_agent review-search-results --limit 10 --min-score 7
python3 -m erdos_agent promote-search-result 14 --result-index 1 --status open --limit 10
python3 -m erdos_agent queue-pivots ep0014-crossref-10-1142-s179304211550116x --agent auto --limit 3 --min-score 19
```

Observed locally:

- Literature jobs for #14, #25, and #51 completed from the queue.
- Each job produced a literature report, source-aware search JSON/Markdown, and anonymous Result Cards.
- Promoting the first result for #14 produced an `unreviewed` finding and 10 pivot candidates.
- Top #14 pivots included #42, #43, #30, #41, and #44.
- Queueing the top #14 pivots produced Literature jobs for #42 and #43 and a Computation job for #30.
- Running those queued jobs completed the next-hop literature/computation artifacts locally.
- A later review gate trial produced 5 source-aware promotion candidates without auto-approving them.
- `supervisor-step` now reports those pending review candidates even when the queue is empty.

### Contributor Quickstart

Added:

- `docs/quickstart.md`
- `quickstart-check`
- README link to the quickstart
- handoff note pointing future agents to the quickstart

### Review Candidate Deduplication

Added:

- shared literature result dedupe keys for DOI, arXiv IDs, URLs, and normalized titles
- merge metadata for duplicate arXiv/Crossref search results
- promotion review deduplication across multiple seed problems
- `duplicate_count`, `related_candidates`, and `related_problem_ids` in review artifacts

This keeps the Supervisor review page focused when the same paper appears from several searches, while preserving enough provenance for a human to decide which candidate to approve.

### Candidate Review Packets

Added:

- `review-promotion-candidate CANDIDATE_ID`
- `preview-promotion-candidate CANDIDATE_ID`
- `mark-promotion-candidate CANDIDATE_ID --decision rejected|deferred|needs_more_reading`
- source-aware human review packets under `reports/literature/review/packets/`
- dry-run approval previews under `reports/literature/review/previews/`
- human review decisions under `reports/literature/review/decisions/`
- approval metadata fields for `reviewer`, `review_notes`, and a candidate snapshot

This makes approval auditable for multi-person work without weakening the no-auto-posting/no-novelty-claim rule.

### Experiment 001 Candidate Review

Added:

- `docs/experiments/001_ep0043_r002_review.md`
- duplicate-aware decision matching so a decision on one paper variant also suppresses equivalent arXiv/Crossref/title variants

Outcome:

- `ep0043-r002` was not approved.
- Public source review found that the corresponding arXiv record `2211.14011` was withdrawn because of a flaw in the main argument.
- The local decision for `ep0043-r002` is `needs_more_reading`.
- The default review list now suppresses the same-paper arXiv duplicate and leaves `ep0043-r001` as the next visible candidate.

### Experiment 001 Manual Finding Run

Added:

- `docs/experiments/001_csw20_manual_finding_run.md`

Outcome:

- Recorded the 2020 `Sidon set systems` paper as manual finding `ep0043-csw20-sidon-set-systems`.
- Generated 13 pivot candidates.
- Queued and completed 5 follow-up jobs: computation for `ep0030`, `ep0039`, `ep0041`, and literature for `ep0042`, `ep0044`.
- Queue ended empty.
- The next visible promotion candidate is `ep0043-r001`.

### Computation Harness Upgrade

Added:

- computation worker generation of `computations/epNNNN/search.py`
- computation worker generation of `computations/epNNNN/results.md`
- runnable dependency-free small-case harnesses for:
  - `sidon_max_exact`
  - `greedy_sidon_prefix`
  - `b3_max_exact`

Outcome:

- Re-ran computation jobs for `ep0030`, `ep0039`, and `ep0041`.
- `ep0030` now has exact small `h(N)` data through `N=24`.
- `ep0039` now has a greedy infinite Sidon prefix table.
- `ep0041` now has exact small B3/triple-sum data through `N=14`.

Purpose:

- Give new contributors a small local workflow from ingest through review-gated literature promotion.
- Keep approval and external publication as explicit human actions.
- Provide a safe smoke-test command that refreshes triage/review summaries without approving candidates.

## Local State From Trial Runs

The repository ignores generated research artifacts by default:

```text
data/
reports/
packets/
agent_runs/
kb/
computations/
lean/
```

This is intentional because the GitHub repository is public. Commit generated artifacts only after deciding they should be shared.

During local trials:

- 30 open problems were imported with statements.
- triage ranking was generated.
- #9 was used as a transfer seed.
- #10 appeared as a top transfer/pivot candidate.
- sample queue jobs were created and processed.
- #14, #25, and #51 literature jobs were processed from the queue.
- sample search results were promoted to unreviewed findings and pivot candidates.
- #14 pivot candidates were queued and processed as follow-up agent jobs.

These local artifacts may exist on the working machine but are not tracked in Git.

## Current Repository Status

Public GitHub repository:

```text
https://github.com/sann-ai/erdos-agent
```

Current default branch:

```text
main
```

The tracked code is a local CLI and workflow substrate. It can call arXiv and Crossref metadata APIs. It does not yet call the OpenAI API, Lean, Semantic Scholar, MathSciNet, zbMath, or Google Scholar directly.
