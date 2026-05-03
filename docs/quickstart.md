# Quickstart

This guide runs a small local workflow from ingest to review-gated literature promotion.

It is intentionally conservative:

- generated research artifacts stay in ignored directories
- no external posting happens
- search results become review candidates before they become findings
- Blind Solver inputs remain separate from source-aware literature artifacts

## 0. Check The Workspace

```bash
git status -sb
python3 -m unittest discover -s tests
python3 -m erdos_agent init
```

Expected:

- Git should be clean or only show intentional local edits.
- Tests should pass.
- `init` should create any missing local artifact directories.

You can also run the safe local checker at any point:

```bash
python3 -m erdos_agent quickstart-check
```

It may update triage and review summaries, but it does not approve candidates, queue pivots, or post externally.

## 1. Import A Small Batch

Fetch a small open-problem sample with statements:

```bash
python3 -m erdos_agent ingest-github --status open --limit 10 --fetch-statements
```

Generated local artifacts:

```text
data/problems/epNNNN.json
data/raw/
```

These are ignored by Git by default.

## 2. Triage The Batch

```bash
python3 -m erdos_agent triage-all --status open --limit 10
```

Inspect:

```bash
reports/triage/index.json
```

The index ranks candidates and gives each one a `recommended_next_action`.

## 3. Queue Literature Jobs

Create a few Literature Agent jobs from triage:

```bash
python3 -m erdos_agent create-run --from-triage --agent literature --action literature_review --limit 2
python3 -m erdos_agent list-runs --status queued
```

Generated local artifacts:

```text
agent_runs/inbox/*.json
```

## 4. Run The Queue

Process one queued job:

```bash
python3 -m erdos_agent run-next-agent
```

Repeat until the queue is empty:

```bash
python3 -m erdos_agent list-runs --status queued
```

The Literature worker writes:

```text
reports/literature/epNNNN.md
reports/literature/search/epNNNN.json
reports/literature/search/epNNNN.md
reports/literature/result_cards/epNNNN.md
```

The `search/` files are source-aware Supervisor artifacts. The `result_cards/` files are solver-facing and omit source metadata.

## 5. Build Review Candidates

Create a source-aware review list from all local search results:

```bash
python3 -m erdos_agent review-search-results --limit 20 --min-score 7
```

Inspect:

```bash
reports/literature/review/promotion_candidates.md
```

This is the human review gate. Do not approve a candidate just because it scored highly.

For one candidate, generate a source-aware review packet:

```bash
python3 -m erdos_agent review-promotion-candidate CANDIDATE_ID
```

Inspect:

```bash
reports/literature/review/packets/CANDIDATE_ID.md
```

Preview what approval would do without creating findings, pivots, or queued runs:

```bash
python3 -m erdos_agent preview-promotion-candidate CANDIDATE_ID --queue-limit 3 --queue-min-score 10
```

Inspect:

```bash
reports/literature/review/previews/CANDIDATE_ID.md
```

If a candidate is not useful, mark the decision so it does not keep resurfacing:

```bash
python3 -m erdos_agent mark-promotion-candidate CANDIDATE_ID --decision rejected --reviewer YOUR_NAME --note "keyword match only"
```

## 6. Let Supervisor Summarize The State

```bash
python3 -m erdos_agent supervisor-step --limit 5
```

Inspect:

```bash
agent_runs/supervisor_step.json
```

If `queued_count` is `0` but `review_candidates.available` is `true`, the next action is review, not autonomous promotion.

## 7. Approve Only After Review

After a human checks a candidate in `promotion_candidates.md`, approve it:

```bash
python3 -m erdos_agent approve-promotion-candidate CANDIDATE_ID --reviewer YOUR_NAME --note "brief reason" --pivot-limit 20
```

This creates:

```text
reports/literature/findings/FINDING_ID.json
reports/literature/promotions/epNNNN-rNNN.json
reports/literature/review/approvals/CANDIDATE_ID.json
reports/pivots/FINDING_ID.json
kb/wiki/papers/FINDING_ID.md
```

To approve and queue follow-up jobs from the pivot candidates:

```bash
python3 -m erdos_agent approve-promotion-candidate CANDIDATE_ID --reviewer YOUR_NAME --note "brief reason" --queue-pivots --queue-limit 3 --queue-min-score 10
```

## 8. Continue Or Stop

Check the state:

```bash
python3 -m erdos_agent quickstart-check
python3 -m erdos_agent supervisor-step --limit 5
git status --short
```

Expected:

- generated artifacts remain ignored by Git
- new queued runs appear only if you approved a candidate with `--queue-pivots`
- no public claim has been made

## Safety Checklist

Before sharing or publishing anything:

- Do not claim novelty from metadata search alone.
- Do not send source-aware literature artifacts to Blind Solver.
- Do not auto-post to Erdős Problems, GitHub issues, arXiv, or forums.
- Convert serious mathematical progress into a Claim Card.
- Run Critic/Referee and human review before any external-facing claim.
