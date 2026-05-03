# Codex Automation

This project can be driven by Codex automations through the file-based run queue.

## Core Command

Use:

```bash
python3 -m erdos_agent run-next-agent
```

This command:

- reads the highest-priority queued job from `agent_runs/inbox/`
- runs the deterministic MVP worker for that agent
- writes the result to `agent_runs/outbox/`
- writes a short status file to `agent_runs/last_run_next.json`
- exits successfully when the queue is empty

You can restrict execution to one agent type:

```bash
python3 -m erdos_agent run-next-agent --agent literature
python3 -m erdos_agent run-next-agent --agent computation
```

## Recommended Automation Prompt

```text
In /Users/san/Documents/New project, run `python3 -m erdos_agent run-next-agent`.
Then inspect `agent_runs/last_run_next.json` and summarize whether a job was processed, idle, blocked, or needs human review.
Do not post externally. Do not commit generated research artifacts unless explicitly asked.
```

## Suggested Schedule

Start conservative:

```text
every 30 minutes
```

This is enough for queue draining while the workers are deterministic MVP workers. Once model-driven or external-search workers are added, keep a human review gate and consider running less frequently.

## Queue Creation

The automation only drains jobs. A Supervisor still creates jobs explicitly:

```bash
python3 -m erdos_agent create-run --from-triage --agent literature --action literature_review --limit 3
python3 -m erdos_agent create-run --from-triage --agent computation --action computation --limit 2
```

## Safety

- Automation must not auto-post to Erdős Problems, GitHub issues, arXiv, or any external forum.
- Blind Solver jobs should use only redacted packet artifacts.
- Generated artifacts remain ignored by Git by default.
- Important claims require Claim Card, Critic, literature review, and human approval.

