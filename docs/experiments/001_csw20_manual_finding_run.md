# Experiment 001 Run: CSW20 Manual Finding

Date: 2026-05-04

Seed finding: `ep0043-csw20-sidon-set-systems`

Paper:

- Javier Cilleruelo, Oriol Serra, Maximilian Woetzel, Sidon set systems,
  Revista Matematica Iberoamericana 36 (2020), 1527-1548.
- DOI: https://doi.org/10.4171/RMI/1174
- EMS page: https://ems.press/journals/rmi/articles/16730

## Goal

Run the first end-to-end research-operations loop using a safer background paper
instead of the withdrawn 2023 `The structure of Sidon set systems` candidate.

This experiment does not attempt to solve a problem. It checks whether the system can:

- record a reviewed manual literature finding
- pivot to related open problems
- queue follow-up agent jobs
- run those jobs without automation
- leave auditable artifacts and next review candidates

## Commands Run

```bash
python3 -m erdos_agent add-finding 43 \
  --paper-key "CSW20-sidon-set-systems" \
  --title "Sidon set systems" \
  --url "https://doi.org/10.4171/RMI/1174" \
  --summary "Background paper on Sidon systems: families of k-subsets with distinct pairwise sumsets; provides bounds, terminology, and examples relevant to Sidon-system-style pivots, but does not directly solve EP43." \
  --method-tag "sidon sets" \
  --method-tag "additive combinatorics" \
  --method-tag "distinct sumsets" \
  --relevance 3

python3 -m erdos_agent pivot-from-finding ep0043-csw20-sidon-set-systems --status open --limit 20
python3 -m erdos_agent queue-pivots ep0043-csw20-sidon-set-systems --agent auto --limit 5 --min-score 10
python3 -m erdos_agent run-next-agent
python3 -m erdos_agent run-next-agent
python3 -m erdos_agent run-next-agent
python3 -m erdos_agent run-next-agent
python3 -m erdos_agent run-next-agent
python3 -m erdos_agent review-search-results --limit 20 --min-score 7
python3 -m erdos_agent supervisor-step --limit 10
python3 -m erdos_agent quickstart-check --triage-limit 10 --review-limit 10 --min-review-score 7
```

## Artifacts Produced

Manual finding and pivot:

- `reports/literature/findings/ep0043-csw20-sidon-set-systems.json`
- `kb/wiki/papers/ep0043-csw20-sidon-set-systems.md`
- `reports/pivots/ep0043-csw20-sidon-set-systems.json`

Completed follow-up jobs:

- `computations/ep0030/README.md`
- `computations/ep0039/README.md`
- `computations/ep0041/README.md`
- `reports/literature/ep0042.md`
- `reports/literature/search/ep0042.json`
- `reports/literature/search/ep0042.md`
- `reports/literature/result_cards/ep0042.md`
- `reports/literature/ep0044.md`
- `reports/literature/search/ep0044.json`
- `reports/literature/search/ep0044.md`
- `reports/literature/result_cards/ep0044.md`

These generated research artifacts are intentionally local-only under the current
`.gitignore`; this document records the shared experiment history.

## Pivot Results

`pivot-from-finding` returned 13 candidates. With `--limit 5 --min-score 10`, the
system queued:

| problem | agent | reason |
|---|---|---|
| `ep0030` | computation | Sidon maximum-size problem with OEIS links |
| `ep0039` | computation | infinite Sidon set density question |
| `ep0041` | computation | distinct triple-sum/Sidon-like growth question |
| `ep0042` | literature | Sidon set plus disjoint difference condition |
| `ep0044` | literature | Sidon subset existence/size question |

All five jobs completed.

## Observations

The good news:

- The manual finding path works.
- Pivot generation produced a coherent Sidon cluster.
- `--agent auto` mapped computation/literature follow-ups correctly.
- Queue draining worked manually while automation stayed paused.
- The queue was empty at the end.

The weaker news:

- Computation workers currently only create plan stubs; they do not yet write runnable
  `search.py` scripts or results tables.
- Literature search for `ep0042` and `ep0044` still surfaced the withdrawn 2023
  `The structure of Sidon set systems` result as the top hit, even though the
  `ep0043-r002` decision suppresses the same-paper duplicate in the promotion
  review list.
- Crossref/arXiv keyword search also returns off-topic hits such as functional
  analysis Sidon sets, algebraic geometry Sidon sets, and unrelated Crossref matches.

## Current State After Experiment

```text
queued runs: 0
completed runs: 16
review candidates: 1
visible candidate: ep0043-r001
```

`quickstart-check` reports:

```text
local problem files: 30
literature search result files: 7
review candidates: 1
queued: 0
```

## Assessment

Experiment 001 succeeded as an operations test.

It did not produce mathematical progress yet, but it demonstrated the intended loop:

```text
reviewed background paper -> manual finding -> pivot -> queued jobs -> completed artifacts -> renewed review gate
```

The most important product of the run is actually negative information:

- the 2023 structure paper should not be used as an approved finding without separating
  safe background content from the withdrawn main argument
- the literature search needs stronger suppression/penalty for known-risk paper clusters
- computation workers need to move from plan stubs to runnable scripts

## Recommended Next Step

Review `ep0043-r001` next:

- title: `An improved upper bound for the size of the multiplicative 3-Sidon sets`
- reason: it is now the only visible promotion candidate
- risk: it may be about multiplicative Sidon sets rather than the additive/difference
  structure needed for `ep0043`

Suggested commands:

```bash
python3 -m erdos_agent review-promotion-candidate ep0043-r001
python3 -m erdos_agent preview-promotion-candidate ep0043-r001 --queue-limit 3 --queue-min-score 10
```

If it is off-topic, mark it:

```bash
python3 -m erdos_agent mark-promotion-candidate ep0043-r001 \
  --decision rejected \
  --reviewer san \
  --note "Appears to concern multiplicative Sidon sets rather than the additive/difference Sidon-set setting needed for EP43."
```

Then improve either:

- risk-aware literature search filtering, or
- computation workers for `ep0030`, `ep0039`, and `ep0041`.
