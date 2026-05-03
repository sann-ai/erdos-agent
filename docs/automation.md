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

When the queue is empty, a Supervisor can inspect pending review work:

```bash
python3 -m erdos_agent supervisor-step --limit 5
```

`agent_runs/supervisor_step.json` includes `review_candidates`. If `review_candidates.available` is true, automation should report the top candidates and wait for human approval rather than promoting them automatically.

## Suggested Schedule

Start conservative:

```text
every hour
```

This is enough for queue draining while the workers are deterministic MVP workers. Once model-driven or external-search workers are added, keep a human review gate and consider whether the cadence should stay hourly.

## Active Codex Automation

Created on 2026-05-03:

```text
id: drain-erdos-agent-queue
name: Drain Erdos Agent Queue
schedule: hourly
workspace: /Users/san/Documents/New project
command intent: python3 -m erdos_agent run-next-agent
```

The automation is intentionally conservative:

- it processes at most one queued job per run
- it exits cleanly when the queue is empty
- it summarizes `agent_runs/last_run_next.json`
- it does not post externally
- it does not commit generated research artifacts

## Queue Creation

The automation only drains jobs. A Supervisor still creates jobs explicitly:

```bash
python3 -m erdos_agent create-run --from-triage --agent literature --action literature_review --limit 3
python3 -m erdos_agent create-run --from-triage --agent computation --action computation --limit 2
python3 -m erdos_agent review-search-results --limit 20 --min-score 7
python3 -m erdos_agent approve-promotion-candidate CANDIDATE_ID --queue-pivots --queue-limit 3 --queue-min-score 10
```

## Safety

- Automation must not auto-post to Erdős Problems, GitHub issues, arXiv, or any external forum.
- Blind Solver jobs should use only redacted packet artifacts.
- Generated artifacts remain ignored by Git by default.
- Important claims require Claim Card, Critic, literature review, and human approval.
