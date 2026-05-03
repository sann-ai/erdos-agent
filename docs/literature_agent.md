# Literature Agent

The Literature Agent is source-aware. It may query public metadata APIs and inspect official references, but it must not pass source/status metadata to Blind Solver agents.

## Current Sources

The current MVP supports:

- arXiv API
- Crossref API

It does not yet directly integrate:

- Google Scholar
- MathSciNet
- zbMath
- Semantic Scholar

Those should be added carefully because access policy, authentication, rate limits, and citation quality differ.

## Commands

Create a literature report from local problem data:

```bash
python3 -m erdos_agent run-agent RUN_ID
```

Run external metadata search directly:

```bash
python3 -m erdos_agent literature-search 9 --source arxiv --source crossref --limit 5 --query-limit 3
```

Generated artifacts:

```text
reports/literature/search/epNNNN.json
reports/literature/search/epNNNN.md
reports/literature/result_cards/epNNNN.md
```

Promote a reviewed-enough search result into an unreviewed finding and pivot candidates:

```bash
python3 -m erdos_agent promote-search-result 9 --result-index 1 --status open --limit 20
```

Generated artifacts:

```text
reports/literature/findings/FINDING_ID.json
reports/pivots/FINDING_ID.json
reports/literature/promotions/epNNNN-r001.json
```

## Artifact Boundaries

Supervisor/source-aware artifacts:

- `reports/literature/search/epNNNN.json`
- `reports/literature/search/epNNNN.md`
- `reports/literature/findings/*.json`
- `reports/literature/promotions/*.json`
- `reports/pivots/*.json`
- `kb/wiki/papers/*.md`

Solver-facing artifacts:

- `reports/literature/result_cards/epNNNN.md`

The result cards intentionally omit source URLs, DOIs, authors, venues, and official status. Solver-facing snippets also redact direct source/status phrases such as `Erdos`, `Erdős`, `open problem`, and numbered problem references. They are still not proof of novelty; they are just anonymized mathematical hints for downstream attempts.

## Workflow

1. Create or run a Literature Agent job.
2. Inspect source-aware search results.
3. Convert useful papers or methods into findings. For the semi-automated path:

```bash
python3 -m erdos_agent promote-search-result 9 --result-index 1 --status open --limit 20
```

Or record a finding manually:

```bash
python3 -m erdos_agent add-finding 9 \
  --paper-key "Key24" \
  --title "Paper title" \
  --url "https://..." \
  --summary "Short source-aware note" \
  --method-tag "additive basis" \
  --example "Example or construction"
```

4. If a manually recorded finding suggests another target, pivot:

```bash
python3 -m erdos_agent pivot-from-finding ep0009-key24 --status open --limit 20
```

5. Only pass anonymized Result Cards to a Blind Solver.

## Caveats

- arXiv/Crossref search is a metadata search, not a full literature review.
- Search results can miss relevant older papers.
- Crossref titles and abstracts may be incomplete.
- arXiv results are biased toward recent/preprint literature.
- The current relevance filter is intentionally conservative and heuristic.
- A strong search hit should trigger human reading, not an immediate novelty claim.
