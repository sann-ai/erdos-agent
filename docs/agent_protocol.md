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

1. Record the finding with `promote-search-result` or `add-finding`.
2. Run `pivot-from-finding` when the finding was created manually.
3. Put the top pivot candidates in `agent_runs/outbox/`.
4. Let Supervisor decide whether to switch focus.
