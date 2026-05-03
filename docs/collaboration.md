# Collaboration Guide

This file is for people joining the project.

## What This Project Is

This is a research workflow tool for Erdős Problems. It is meant to coordinate human review, Codex agents, literature search, computation, and formalization.

It is not a system for automatically posting claimed solutions.

## Repository Policy

The GitHub repository is public.

By default, these generated directories are ignored:

```text
data/
reports/
packets/
agent_runs/
kb/
computations/
lean/
```

Reason:

- They may contain copied problem text, private notes, incomplete claims, or noisy agent output.
- They may reveal source/problem identity for blind-solving experiments.
- They should be reviewed before publication.

Commit generated artifacts only intentionally.

## Contributor Roles

### Supervisor

Owns:

- queue state
- target selection
- human review gates
- source-aware decisions
- pivot approval

Can read:

- everything

Should not:

- treat an AI proof attempt as publishable without review

### Literature Contributor

Owns:

- literature reports
- source-aware findings
- bibliography checks
- pivot candidates

Uses:

```bash
python3 -m erdos_agent run-agent RUN_ID
python3 -m erdos_agent add-finding ...
python3 -m erdos_agent pivot-from-finding ...
```

Should output:

- finding JSON
- wiki paper note
- possible anonymous Result Cards
- novelty risk notes

### Blind Solver Contributor

Owns:

- proof/disproof/partial-attempt generation from redacted packets

Can read:

- `packets/blind/*.md`

Should not read:

- problem number
- URL
- official status
- prize
- forum comments
- source-aware bibliography

Should output:

- exact statement considered
- proof/disproof attempt
- edge cases
- lemmas
- gaps
- formalization target

### Computation Contributor

Owns:

- finite searches
- counterexample searches
- OEIS/small-value reproduction
- executable scripts and logs

Uses:

```bash
python3 -m erdos_agent run-agent RUN_ID
```

Should output:

- `computations/epNNNN/search.py`
- `computations/epNNNN/results.md`
- seeds, bounds, commands, and runtime notes

### Formalization Contributor

Owns:

- Lean statement/proof plans
- theorem statement correspondence checks
- sorry/admit/axiom checks

Should output:

- `lean/epNNNN/README.md`
- theorem statement drafts
- build/check instructions

### Critic / Referee Contributor

Owns:

- rejection attempts
- exact-statement checks
- literature duplication checks
- proof gap reports

Should output:

- `reports/referee/epNNNN.md`

## Standard Workflow

1. Supervisor imports and triages problems.

```bash
python3 -m erdos_agent ingest-github --status open --limit 30 --fetch-statements
python3 -m erdos_agent triage-all --status open --limit 30
```

2. Supervisor creates runs.

```bash
python3 -m erdos_agent create-run --from-triage --agent literature --action literature_review --limit 3
python3 -m erdos_agent create-run --from-triage --agent computation --action computation --limit 2
```

3. Contributors inspect queue.

```bash
python3 -m erdos_agent list-runs --status queued
python3 -m erdos_agent supervisor-step
```

4. Contributor runs or manually handles a job.

```bash
python3 -m erdos_agent run-agent RUN_ID
```

or, after manual work:

```bash
python3 -m erdos_agent complete-run RUN_ID --status done --summary "..." --artifact path/to/output
```

5. Supervisor reviews outbox and decides next jobs.

```bash
python3 -m erdos_agent list-runs
```

## Branch and PR Practice

Use small branches:

```text
codex/literature-agent
codex/computation-harness
codex/lean-gate
```

Keep changes focused:

- code changes separate from generated research artifacts
- one feature per PR
- tests for CLI/core behavior
- no unrelated formatting churn

## Review Expectations

Before merging:

- Run tests.

```bash
python3 -m unittest discover -s tests
python3 -m compileall erdos_agent
```

- Check that generated artifacts are not accidentally staged.

```bash
git status --short
```

- If adding a new command, update README and relevant docs.

## Safety Rules

- Do not auto-post externally.
- Do not claim novelty from an LLM output.
- Do not give source-aware metadata to Blind Solver contributors.
- Do not publish generated notes without review.
- Always record caveats and gaps.
- If a result seems important, create a Claim Card and ask for human review.

