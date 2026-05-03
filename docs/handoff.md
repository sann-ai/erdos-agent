# Handoff

Short context for resuming after conversation compaction.

## Repository

- Local path: `/Users/san/Documents/New project`
- GitHub: `https://github.com/sann-ai/erdos-agent`
- Branch: `main`
- Generated research artifacts are ignored by Git: `data/`, `reports/`, `agent_runs/`, `kb/`, `packets/`, `computations/`, `lean/`

## Current System

The tracked CLI can:

- ingest Erdős Problems metadata and statements
- triage local problems
- create and drain file-based agent runs
- run deterministic MVP workers for literature, computation, audit, formalization, critic, and blind solver packet generation
- search arXiv/Crossref metadata
- create source-aware literature review candidates
- approve reviewed candidates into findings and pivots
- queue follow-up jobs from approved pivots
- report queued work and pending review candidates through `supervisor-step`

## Safety Boundaries

- No automatic external posting.
- No novelty claims without human review.
- Blind Solver receives only redacted packets or anonymous Result Cards.
- Source-aware literature artifacts stay on the Supervisor side.
- Review candidates are not auto-approved.

## Resume Checklist

```bash
git status -sb
python3 -m unittest discover -s tests
python3 -m erdos_agent quickstart-check
python3 -m erdos_agent supervisor-step --limit 5
```

If the queue is empty but `review_candidates.available` is true, inspect:

```bash
reports/literature/review/promotion_candidates.md
```

Then approve a candidate only after review:

```bash
python3 -m erdos_agent review-promotion-candidate CANDIDATE_ID
python3 -m erdos_agent approve-promotion-candidate CANDIDATE_ID --reviewer YOUR_NAME --note "brief reason" --pivot-limit 20
```

Or mark it as reviewed but not approved:

```bash
python3 -m erdos_agent mark-promotion-candidate CANDIDATE_ID --decision rejected --reviewer YOUR_NAME --note "keyword match only"
```

To approve and queue follow-up jobs in one step:

```bash
python3 -m erdos_agent approve-promotion-candidate CANDIDATE_ID --reviewer YOUR_NAME --note "brief reason" --queue-pivots --queue-limit 3 --queue-min-score 10
```

## Next Good Step

Use `quickstart-check` as the safe local smoke test:

```bash
python3 -m erdos_agent quickstart-check
```

The next useful workflow step is reviewing one deduplicated candidate, approving it if it looks useful, and checking that approval creates a finding, pivots to similar open problems, and optionally queues follow-up jobs.
