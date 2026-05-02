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

1. Record the finding with `add-finding`.
2. Run `pivot-from-finding`.
3. Put the top pivot candidates in `agent_runs/outbox/`.
4. Let Supervisor decide whether to switch focus.

