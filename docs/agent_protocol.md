# Agent Protocol

This project is designed so Codex automations can run several agents without sharing more context than needed.

## Agent Roles

- Supervisor: status-aware coordinator. Knows problem ids, source URLs, official status, manifests, and review state.
- Ingest Agent: imports official metadata and page text into `data/`.
- Triage Agent: writes `reports/triage/*.json` and `reports/triage/index.json`.
- Literature Agent: writes source-aware findings to `reports/literature/findings/` and wiki pages to `kb/wiki/papers/`.
- Blind Solver: receives only `packets/blind/*.md`.
- Computation Agent: owns `computations/epNNNN/`.
- Formalization Agent: owns `lean/epNNNN/`.
- Critic/Referee Agent: reads attempts, literature, computation, and Lean outputs, then writes `reports/referee/`.

## Information Boundaries

- Blind Solver must not receive problem number, official URL, open/solved status, prize, or forum context.
- Literature Agent may know sources, but solver-facing output should be anonymous Result Cards.
- Supervisor keeps the de-redaction map in `data/manifests/`.
- No agent posts externally without a human gate.

## Automation Shape

Codex automations should exchange files rather than hidden chat state:

- Inputs: `agent_runs/inbox/*.json`
- Outputs: `agent_runs/outbox/*.json`
- Durable artifacts: `data/`, `reports/`, `packets/`, `kb/`, `computations/`, `lean/`

Create queued jobs with:

```bash
python3 -m erdos_agent create-run --problem 25 --agent literature
python3 -m erdos_agent create-run --from-triage --agent literature --action literature_review --limit 5
```

Inspect and complete jobs with:

```bash
python3 -m erdos_agent list-runs --status queued
python3 -m erdos_agent supervisor-step --limit 5
python3 -m erdos_agent run-agent RUN_ID
python3 -m erdos_agent run-next-agent
python3 -m erdos_agent complete-run RUN_ID --status done --summary "short result" --artifact reports/literature/findings/foo.json
```

`run-agent` currently uses deterministic MVP workers. It creates structured artifacts for literature, computation, statement audit, formalization, critic, or blind packet handoff; later Codex automations can replace these workers with live model-driven agents while preserving the same inbox/outbox contract.

`supervisor-step` writes `agent_runs/supervisor_step.json`. In addition to queued and completed run counts, it includes `review_candidates` from `reports/literature/review/promotion_candidates.json` when a review list exists.

Each output should include:

```json
{
  "agent": "literature",
  "task_id": "string",
  "problem_id": "epNNNN or null",
  "status": "done | blocked | needs_human",
  "artifacts": ["path"],
  "summary": "short human-readable result"
}
```

## Pivot Rule

If a Literature Agent finds a paper, construction, example, or method that looks more useful for a different open problem than the current one, it should:

1. Build a review list with `review-search-results`.
2. Build a source-aware packet with `review-promotion-candidate`.
3. Preview approval effects with `preview-promotion-candidate`.
4. Approve a reviewed candidate with `approve-promotion-candidate`, mark it with `mark-promotion-candidate`, or record a manual finding with `add-finding`.
5. Run `pivot-from-finding` when the finding was created manually.
6. Queue approved top pivot candidates with `queue-pivots`.
7. Let Supervisor decide whether to run the queued jobs or change focus.

```bash
python3 -m erdos_agent review-search-results --limit 20 --min-score 7
python3 -m erdos_agent review-promotion-candidate CANDIDATE_ID
python3 -m erdos_agent preview-promotion-candidate CANDIDATE_ID --queue-limit 3 --queue-min-score 10
python3 -m erdos_agent approve-promotion-candidate CANDIDATE_ID --reviewer YOUR_NAME --note "brief reason" --pivot-limit 20
```

```bash
python3 -m erdos_agent queue-pivots FINDING_ID --agent auto --limit 3 --min-score 10
```

With `--agent auto`, the queue step maps `recommended_next_action` to an agent role:

```text
literature_review -> literature
statement_audit -> statement_auditor
computation / counterexample_search -> computation
lean_formalization -> formalization
proof_attempt -> blind_solver
```
