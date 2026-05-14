# Experiment 003: EP43 Targeted Literature Search

Date: 2026-05-14

Seed problem: `ep0043`

Goal: after the multiplicative Sidon false lead, run targeted additive/difference-set
queries and check that the review gate can surface new candidates without inheriting
old decisions from unstable result-index IDs.

## Commands Run

```bash
python3 -m erdos_agent literature-search 43 \
  --source arxiv \
  --source crossref \
  --limit 5 \
  --query "Sidon sets disjoint difference sets" \
  --query "two Sidon sets disjoint differences" \
  --query "Erdos Sidon sets disjoint difference sets"

python3 -m erdos_agent review-search-results --limit 20 --min-score 7
python3 -m erdos_agent review-search-results --limit 20 --min-score 0 --include-decided
python3 -m erdos_agent review-promotion-candidate ep0043-r002
python3 -m erdos_agent preview-promotion-candidate ep0043-r002 --queue-limit 3 --queue-min-score 10
python3 -m erdos_agent review-promotion-candidate ep0043-r003
python3 -m erdos_agent preview-promotion-candidate ep0043-r003 --queue-limit 3 --queue-min-score 10
python3 -m erdos_agent quickstart-check --triage-limit 10 --review-limit 10 --min-review-score 7
python3 -m erdos_agent supervisor-step --limit 10
```

## Local Results

The default review list now has two visible candidates:

| candidate | title | DOI | score | status |
|---|---|---|---:|---|
| `ep0043-r002` | On Sum Sets of Sidon Sets, 1. | `10.1006/jnth.1994.1040` | 7 | candidate |
| `ep0043-r003` | Popular differences and generalized Sidon sets | `10.1016/j.jnt.2017.09.016` | 7 | candidate |

The include-decided review list still shows the previously reviewed 2023 `The structure
of Sidon set systems` cluster as `needs_more_reading`, but that decision now follows the
stable paper title/arXiv/Crossref keys rather than the old result-index candidate ID.

## Bug Fixed During Experiment

Search-result IDs such as `ep0043-r002` are position-based. When a search artifact is
regenerated, the same ID can point to a different paper. The review decision matcher
previously allowed direct candidate-ID matching, which could incorrectly apply an old
decision to a new paper at the same result index.

Fix:

- decision lookup now uses stable paper keys only
- stable keys include DOI, arXiv identifier, URL, and canonical title
- duplicate paper variants remain suppressed across arXiv/Crossref/title matches
- a regression test covers reused result-index IDs

## Current State

```text
queued runs: 0
completed runs: 19
default review candidates: 2
```

No candidate was approved in this experiment. The next human step is to source-check
`ep0043-r002` and `ep0043-r003`; if one is genuinely useful background for the additive
Sidon/difference-set problem, approve it and queue the top three pivot jobs.
