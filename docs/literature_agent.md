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

Run targeted manual queries instead of generated queries:

```bash
python3 -m erdos_agent literature-search 43 \
  --source arxiv \
  --source crossref \
  --limit 5 \
  --query "Sidon sets disjoint difference sets" \
  --query "two Sidon sets disjoint differences"
```

If `--query` is present, generated queries are skipped by default. Add
`--include-generated-queries` when the manual query set should be prepended to the
generated query plan.

Generated artifacts:

```text
reports/literature/search/epNNNN.json
reports/literature/search/epNNNN.md
reports/literature/result_cards/epNNNN.md
```

Promote a reviewed-enough search result into an unreviewed finding and pivot candidates:

```bash
python3 -m erdos_agent review-search-results --limit 20 --min-score 7
python3 -m erdos_agent review-promotion-candidate ep0009-r001
python3 -m erdos_agent preview-promotion-candidate ep0009-r001 --queue-limit 3 --queue-min-score 10
python3 -m erdos_agent approve-promotion-candidate ep0009-r001 --reviewer YOUR_NAME --note "brief reason" --pivot-limit 20
```

If a reviewed candidate is a false lead or should wait, record a decision instead of approving it:

```bash
python3 -m erdos_agent mark-promotion-candidate ep0009-r001 --decision rejected --reviewer YOUR_NAME --note "keyword match only"
```

The review list deduplicates likely identical papers across arXiv/Crossref and across multiple seed problems. Folded matches remain visible as `related_candidates` and `related_problem_ids`, so a human can still see that one paper may matter for several problems without reviewing the same title repeatedly.

The review list also carries source/context risk flags. For example, multiplicative Sidon papers are scored down when the local problem is about additive Sidon or difference-set structure.

Review decisions are matched back to future candidates by stable paper keys such as DOI,
arXiv identifier, URL, and canonical title. They are not matched by result-index IDs such
as `ep0043-r002`, because those IDs can point to a different paper after a search artifact
is regenerated.

Direct promotion is also available for one-off local trials:

```bash
python3 -m erdos_agent promote-search-result 9 --result-index 1 --status open --limit 20
```

Generated artifacts:

```text
reports/literature/findings/FINDING_ID.json
reports/pivots/FINDING_ID.json
reports/literature/promotions/epNNNN-r001.json
reports/literature/review/promotion_candidates.json
reports/literature/review/promotion_candidates.md
reports/literature/review/packets/epNNNN-r001.md
reports/literature/review/previews/epNNNN-r001.md
reports/literature/review/decisions/epNNNN-r001.json
reports/literature/review/approvals/epNNNN-r001.json
```

Queue top pivot candidates as follow-up agent runs:

```bash
python3 -m erdos_agent queue-pivots FINDING_ID --agent auto --limit 3 --min-score 10
```

## Artifact Boundaries

Supervisor/source-aware artifacts:

- `reports/literature/search/epNNNN.json`
- `reports/literature/search/epNNNN.md`
- `reports/literature/findings/*.json`
- `reports/literature/promotions/*.json`
- `reports/literature/review/*.json`
- `reports/literature/review/*.md`
- `reports/literature/review/approvals/*.json`
- `reports/pivots/*.json`
- `kb/wiki/papers/*.md`

Solver-facing artifacts:

- `reports/literature/result_cards/epNNNN.md`

The result cards intentionally omit source URLs, DOIs, authors, venues, and official status. Solver-facing snippets also redact direct source/status phrases such as `Erdos`, `Erdős`, `open problem`, and numbered problem references. They are still not proof of novelty; they are just anonymized mathematical hints for downstream attempts.

## Workflow

1. Create or run a Literature Agent job.
2. Inspect source-aware search results.
3. Build a Supervisor review list:

```bash
python3 -m erdos_agent review-search-results --limit 20 --min-score 7
```

4. Approve a reviewed candidate:

```bash
python3 -m erdos_agent review-promotion-candidate ep0009-r001
python3 -m erdos_agent preview-promotion-candidate ep0009-r001 --queue-limit 3 --queue-min-score 10
python3 -m erdos_agent approve-promotion-candidate ep0009-r001 --reviewer YOUR_NAME --note "brief reason" --pivot-limit 20
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

5. If a manually recorded finding suggests another target, pivot:

```bash
python3 -m erdos_agent pivot-from-finding ep0009-key24 --status open --limit 20
```

6. Queue approved pivot candidates:

```bash
python3 -m erdos_agent queue-pivots ep0009-key24 --agent auto --limit 3 --min-score 10
```

7. Only pass anonymized Result Cards to a Blind Solver.

## Caveats

- arXiv/Crossref search is a metadata search, not a full literature review.
- Search results can miss relevant older papers.
- Crossref titles and abstracts may be incomplete.
- arXiv results are biased toward recent/preprint literature.
- The current relevance filter is intentionally conservative and heuristic.
- A strong search hit should trigger human reading, not an immediate novelty claim.
