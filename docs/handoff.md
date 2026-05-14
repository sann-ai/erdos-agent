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

Targeted literature search can use human-supplied queries:

```bash
python3 -m erdos_agent literature-search 43 \
  --source arxiv \
  --source crossref \
  --limit 5 \
  --query "Sidon sets disjoint difference sets" \
  --query "two Sidon sets disjoint differences"
```

Manual queries replace generated queries unless `--include-generated-queries` is set.

Then approve a candidate only after review:

```bash
python3 -m erdos_agent review-promotion-candidate CANDIDATE_ID
python3 -m erdos_agent preview-promotion-candidate CANDIDATE_ID --queue-limit 3 --queue-min-score 10
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

The next useful workflow step is reviewing the current EP43 candidates:

- `ep0043-r002`: `On Sum Sets of Sidon Sets, 1.`
- `ep0043-r003`: `Popular differences and generalized Sidon sets`

Approve one only if source review shows it is useful for the additive Sidon/difference-set
formulation, then check that approval creates a finding, pivots to similar open problems,
and optionally queues follow-up jobs.

EP43 also has a local exact-computation harness now:

```bash
python3 computations/ep0043/search.py --max-n 20
```

The current small-case result through `N = 20` has maximum unrestricted excess `3` over
`binom(f(N), 2)` and maximum equal-size excess `2`. A good next proof-oriented task is
to convert this into a redacted Blind Solver packet about packing disjoint positive
difference masks.

That packet can be regenerated with:

```bash
python3 -m erdos_agent proof-route-packet 43 --route difference-packing
```

It can be queued for Blind Solver handoff with:

```bash
python3 -m erdos_agent queue-proof-route 43 --route difference-packing
python3 -m erdos_agent run-next-agent --agent blind_solver
```

The local generated artifacts are:

```text
reports/proof_routes/ep0043-difference-packing.md
packets/blind/math-task-b2ab29b556e1-difference-packing.md
data/manifests/math-task-b2ab29b556e1-difference-packing.json
reports/attempts/ep0043-difference_packing-blind-handoff.md
```
