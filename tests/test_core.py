import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import erdos_agent.core as core
from erdos_agent.core import (
    approve_promotion_candidate,
    build_promotion_candidate_packet,
    build_promotion_candidate_report,
    complete_agent_run,
    create_agent_run,
    create_runs_from_pivot,
    create_runs_from_triage,
    dedupe_literature_results,
    ensure_workspace,
    execute_agent_run,
    execute_next_agent_run,
    extract_keywords,
    filter_literature_results,
    extract_problem_content_from_html,
    extract_problem_statement_from_html,
    github_record_to_problem,
    make_blind_packet,
    normalize_problem_id,
    parse_github_problems_yaml,
    parse_arxiv_results,
    parse_crossref_results,
    pivot_from_literature_finding,
    preview_promotion_candidate,
    promote_literature_search_result,
    quickstart_check,
    record_literature_finding,
    record_math_example,
    record_promotion_candidate_decision,
    redact_solver_facing_text,
    render_anonymous_result_cards,
    render_literature_search_markdown,
    score_problem,
    similarity_score,
    supervisor_step,
    make_search_queries,
    write_json,
)


class CoreTests(unittest.TestCase):
    def test_normalize_problem_id(self):
        self.assertEqual(normalize_problem_id("728"), "ep0728")
        self.assertEqual(normalize_problem_id("ep12"), "ep0012")
        self.assertEqual(normalize_problem_id("#3"), "ep0003")

    def test_blind_packet_hides_metadata(self):
        problem = {
            "number": 728,
            "problem_id": "ep0728",
            "url": "https://example.invalid/728",
            "status_site": "open",
            "statement_raw": "For every integer n >= 2, prove that n^2 >= 2n.",
        }
        task_id, content, manifest = make_blind_packet(problem)
        self.assertTrue(task_id.startswith("math-task-"))
        self.assertNotIn("728", content)
        self.assertNotIn("open", content.lower())
        self.assertEqual(manifest["problem_id"], "ep0728")

    def test_score_recommends_literature_for_sparse_refs(self):
        problem = {
            "number": 1,
            "problem_id": "ep0001",
            "statement_raw": "For every integer n, there exists a finite set with property P.",
            "tags": [],
            "known_references": [],
            "comments_summary": [],
        }
        score = score_problem(problem)
        self.assertIn(score["recommended_next_action"], {"literature_review", "computation"})
        self.assertGreater(score["priority_score"], 0)

    def test_parse_github_problems_yaml(self):
        payload = """
- number: "1"
  prize: "$500"
  status:
    state: "open"
    last_update: "2025-08-31"
  oeis: ["A276661"]
  formalized:
    state: "yes"
    last_update: "2025-08-31"
  tags: ["number theory", "additive combinatorics"]
"""
        records = parse_github_problems_yaml(payload)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["number"], "1")
        self.assertEqual(records[0]["status"]["state"], "open")
        self.assertEqual(records[0]["tags"], ["number theory", "additive combinatorics"])

    def test_github_record_to_problem(self):
        record = {
            "number": "1",
            "prize": "no",
            "status": {"state": "open"},
            "formalized": {"state": "yes"},
            "oeis": ["A276661"],
            "tags": ["number theory"],
        }
        problem = github_record_to_problem(
            record,
            page_data={
                "statement": "Let n be a natural number.",
                "remarks": "Known small cases are easy.",
                "references": ["[Ab24] A. Author, A title."],
            },
        )
        self.assertEqual(problem["problem_id"], "ep0001")
        self.assertEqual(problem["status_site"], "open")
        self.assertIsNone(problem["prize"])
        self.assertEqual(problem["formalization_status"], "yes")
        self.assertEqual(problem["statement_source"], "site_latex")
        self.assertEqual(problem["remarks_raw"], "Known small cases are easy.")
        self.assertEqual(problem["known_references"], ["[Ab24] A. Author, A title."])

    def test_extract_problem_statement_from_html(self):
        html = """
<div class="problem-box">
  <div class="problem-text">
    If $A\\subseteq \\{1,\\ldots,N\\}$ then\\[N \\gg 2^n.\\]
  </div>
  <div class="problem-additional-text">Remarks should not be captured.</div>
</div>
"""
        statement = extract_problem_statement_from_html(html)
        self.assertIn("If $A\\subseteq", statement)
        self.assertNotIn("Remarks", statement)

    def test_extract_problem_content_from_html(self):
        html = """
<div class="problem-box">
  <div class="problem-text"><div id="content">Statement text.</div></div>
  <div class="problem-additional-text">Remark one.<br><br>Remark two.</div>
  <div class="problem-additional-text">
    <h3>References</h3>
    [Ab24] A. Author, <i>A title</i>.
    [Cd25] C. D. Writer, Another title.
  </div>
  <div class="problem-additional-text"><a href="/1">Back to the problem</a></div>
</div>
"""
        content = extract_problem_content_from_html(html)
        self.assertEqual(content["statement"], "Statement text.")
        self.assertIn("Remark one.", content["remarks"])
        self.assertEqual(len(content["references"]), 2)
        self.assertTrue(content["references"][0].startswith("[Ab24]"))

    def test_parse_arxiv_results(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1234.5678v1</id>
    <updated>2024-01-02T00:00:00Z</updated>
    <published>2024-01-01T00:00:00Z</published>
    <title>A short additive basis result</title>
    <summary>We prove a small theorem about primes and powers of two.</summary>
    <author><name>A. Author</name></author>
    <arxiv:primary_category term="math.NT" />
  </entry>
</feed>
"""
        results = parse_arxiv_results(xml)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "arxiv")
        self.assertEqual(results[0]["title"], "A short additive basis result")
        self.assertEqual(results[0]["categories"], ["math.NT"])

    def test_parse_crossref_results_and_render_cards(self):
        payload = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/example",
                        "title": ["A title"],
                        "author": [{"given": "A.", "family": "Author"}],
                        "issued": {"date-parts": [[2024]]},
                        "URL": "https://doi.org/10.1000/example",
                        "container-title": ["Journal"],
                        "abstract": "<jats:p>This proves a theorem about additive bases.</jats:p>",
                    }
                ]
            }
        }
        results = parse_crossref_results(payload)
        self.assertEqual(results[0]["source"], "crossref")
        self.assertEqual(results[0]["year"], "2024")
        search_payload = {
            "problem_id": "ep0001",
            "generated_at": "2026-05-03",
            "queries": ["additive bases"],
            "results": results,
            "errors": [],
        }
        markdown = render_literature_search_markdown(search_payload)
        cards = render_anonymous_result_cards(search_payload)
        self.assertIn("A title", markdown)
        self.assertNotIn("https://doi.org", cards)
        self.assertIn("Content terms", cards)

    def test_anonymous_result_cards_redact_source_and_status_leaks(self):
        search_payload = {
            "problem_id": "ep0001",
            "generated_at": "2026-05-03",
            "queries": ["additive bases"],
            "results": [
                {
                    "source": "arxiv",
                    "title": "A note on Erdos problem #9",
                    "abstract_snippet": "We discuss an open problem of Paul Erdos and a related unsolved case.",
                }
            ],
            "errors": [],
        }
        cards = render_anonymous_result_cards(search_payload)
        lowered = cards.lower()
        self.assertNotIn("erdos", lowered)
        self.assertNotIn("open problem", lowered)
        self.assertNotIn("unsolved", lowered)
        self.assertIn("source-redacted", lowered)

    def test_redact_solver_facing_text_handles_unicode_erdos(self):
        redacted = redact_solver_facing_text("Erdős Problems conjecture 123 is an open problem.")
        lowered = redacted.lower()
        self.assertNotIn("erdős", lowered)
        self.assertNotIn("open problem", lowered)

    def test_make_search_queries_adds_domain_hints(self):
        problem = {
            "statement_raw": "Let A be odd integers not of the form p+2^k+2^l where p is prime.",
            "tags": ["number theory", "additive basis"],
            "known_references": [],
        }
        queries = make_search_queries(problem, extract_keywords(problem["statement_raw"]))
        self.assertEqual(queries[0], "prime powers of two")
        self.assertIn("additive basis number theory", queries)

    def test_filter_literature_results_removes_unrelated_hits(self):
        problem = {
            "statement_raw": "Is every large integer the sum of a prime and powers of two?",
            "tags": ["additive basis", "primes"],
        }
        results = [
            {"title": "Power indices in legislatures", "abstract_snippet": "Voting power in two chambers.", "venue": ""},
            {"title": "Prime powers and zeta functions", "abstract_snippet": "We compute sums over prime powers p^s.", "venue": ""},
            {"title": "Two prime squares and powers of 2", "abstract_snippet": "A Waring-Goldbach result.", "venue": ""},
        ]
        filtered = filter_literature_results(problem, results)
        self.assertEqual(len(filtered), 1)
        self.assertIn("prime", filtered[0]["relevance_terms"])

    def test_similarity_score_uses_tags_terms_and_references(self):
        seed = {
            "tags": ["number theory", "primes"],
            "statement_raw": "Every large integer is a sum of a prime and powers of two.",
            "remarks_raw": "Uses additive basis methods.",
            "known_references": ["[Ab24] A. Author, A title."],
            "oeis": ["A000001"],
            "formalization_status": "yes",
        }
        candidate = {
            "tags": ["number theory", "additive basis"],
            "statement_raw": "Is every large integer a sum of primes and powers?",
            "remarks_raw": "Related additive basis question.",
            "known_references": ["[Ab24] A. Author, A title."],
            "oeis": ["A000001"],
            "formalization_status": "yes",
        }
        score, rationale = similarity_score(seed, candidate)
        self.assertGreater(score, 10)
        self.assertTrue(any("shared tags" in item for item in rationale))
        self.assertTrue(any("shared references" in item for item in rationale))

    def test_literature_finding_can_pivot(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0001.json",
                {
                    "number": 1,
                    "problem_id": "ep0001",
                    "status_site": "solved",
                    "tags": ["number theory", "primes"],
                    "statement_raw": "Every large integer is a sum of a prime and powers of two.",
                    "known_references": [],
                },
            )
            write_json(
                root / "data/problems/ep0002.json",
                {
                    "number": 2,
                    "problem_id": "ep0002",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Can every large integer be represented using a prime and a small additive basis?",
                    "known_references": [],
                },
            )
            finding = record_literature_finding(
                root,
                problem_id=1,
                paper_key="Ab24",
                title="A prime additive basis method",
                summary="Uses primes and additive basis constructions.",
                method_tags=["additive basis"],
                examples=["A small additive basis construction."],
            )
            result = pivot_from_literature_finding(root, finding["finding_id"], status_filter={"open"})
            self.assertEqual(result["items"][0]["problem_id"], "ep0002")

    def test_promote_literature_search_result_creates_finding_and_pivot(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0001.json",
                {
                    "number": 1,
                    "problem_id": "ep0001",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Every large integer is a sum of a prime and powers of two.",
                    "known_references": [],
                },
            )
            write_json(
                root / "data/problems/ep0002.json",
                {
                    "number": 2,
                    "problem_id": "ep0002",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Can every large integer be represented using a prime and a small additive basis?",
                    "known_references": [],
                },
            )
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "generated_at": "2026-05-03",
                    "queries": ["prime additive basis"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "A prime additive basis method",
                            "identifier": "10.1000/example",
                            "url": "https://doi.org/10.1000/example",
                            "year": "2024",
                            "venue": "Journal",
                            "abstract_snippet": "Uses primes and additive basis constructions.",
                            "relevance_terms": ["prime", "additive", "basis"],
                            "relevance_score": 3,
                        }
                    ],
                },
            )
            result = promote_literature_search_result(root, 1, status_filter={"open"}, limit=5)
            finding = result["finding"]
            self.assertEqual(finding["status"], "unreviewed")
            self.assertTrue((root / "reports/literature/findings" / f"{finding['finding_id']}.json").exists())
            self.assertTrue((root / "reports/literature/promotions/ep0001-r001.json").exists())
            self.assertEqual(result["pivot"]["items"][0]["problem_id"], "ep0002")

    def test_build_promotion_candidate_report_skips_promoted_and_ranks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["prime additive basis"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "A strong candidate",
                            "identifier": "10.1000/strong",
                            "abstract_snippet": "A useful abstract.",
                            "relevance_terms": ["prime", "additive", "basis", "integers"],
                            "relevance_score": 4,
                        },
                        {
                            "source": "arxiv",
                            "title": "Weak candidate",
                            "relevance_terms": ["prime"],
                            "relevance_score": 1,
                        },
                    ],
                },
            )
            write_json(root / "reports/literature/promotions/ep0001-r001.json", {"status": "needs_human_review"})
            skipped = build_promotion_candidate_report(root, min_score=1, include_promoted=False)
            self.assertEqual([item["candidate_id"] for item in skipped["items"]], ["ep0001-r002"])
            included = build_promotion_candidate_report(root, min_score=1, include_promoted=True)
            self.assertEqual(included["items"][0]["candidate_id"], "ep0001-r001")
            self.assertTrue((root / "reports/literature/review/promotion_candidates.md").exists())

    def test_dedupe_literature_results_merges_same_title_across_sources(self):
        results = dedupe_literature_results(
            [
                {
                    "source": "arxiv",
                    "title": "The structure of Sidon set systems",
                    "identifier": "2211.14011v2",
                    "url": "http://arxiv.org/abs/2211.14011v2",
                    "venue": "arXiv",
                    "abstract_snippet": "A useful preprint abstract.",
                },
                {
                    "source": "crossref",
                    "title": "The Structure of Sidon Set Systems",
                    "identifier": "10.5817/cz.muni.eurocomb23-114",
                    "url": "https://doi.org/10.5817/cz.muni.eurocomb23-114",
                    "venue": "Proceedings",
                },
            ]
        )

        self.assertEqual(len(results), 1)
        self.assertIn("arxiv", results[0]["alternate_sources"])
        self.assertIn("crossref", results[0]["alternate_sources"])
        self.assertIn("2211.14011v2", results[0]["alternate_identifiers"])
        self.assertIn("10.5817/cz.muni.eurocomb23-114", results[0]["alternate_identifiers"])

    def test_build_promotion_candidate_report_dedupes_same_paper_across_problems(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            for problem_id in ["ep0001", "ep0002"]:
                write_json(
                    root / f"reports/literature/search/{problem_id}.json",
                    {
                        "problem_id": problem_id,
                        "queries": ["sidon systems"],
                        "results": [
                            {
                                "source": "crossref",
                                "title": "The structure of Sidon set systems",
                                "identifier": "10.5817/cz.muni.eurocomb23-114",
                                "abstract_snippet": "A useful abstract.",
                                "relevance_terms": ["sidon", "systems", problem_id],
                                "relevance_score": 4 if problem_id == "ep0001" else 3,
                            }
                        ],
                    },
                )

            report = build_promotion_candidate_report(root, min_score=1)

            self.assertEqual(report["raw_candidate_count"], 2)
            self.assertEqual(report["returned"], 1)
            self.assertEqual(report["items"][0]["duplicate_count"], 1)
            self.assertEqual(report["items"][0]["related_problem_ids"], ["ep0001", "ep0002"])
            self.assertEqual(report["items"][0]["related_candidates"][0]["candidate_id"], "ep0002-r001")
            folded_packet = build_promotion_candidate_packet(root, "ep0002-r001")
            self.assertEqual(folded_packet["packet"]["candidate"]["problem_id"], "ep0002")

    def test_build_promotion_candidate_packet_includes_review_gate_details(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["sidon systems"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "The structure of Sidon set systems",
                            "identifier": "10.5817/cz.muni.eurocomb23-114",
                            "url": "https://doi.org/10.5817/cz.muni.eurocomb23-114",
                            "abstract_snippet": "A useful abstract.",
                            "relevance_terms": ["sidon", "systems"],
                            "relevance_score": 4,
                        }
                    ],
                },
            )
            build_promotion_candidate_report(root, min_score=1)

            packet = build_promotion_candidate_packet(root, "ep0001-r001")

            self.assertEqual(packet["packet"]["candidate_id"], "ep0001-r001")
            self.assertIn("reports/literature/review/packets/ep0001-r001.md", packet["artifacts"])
            content = (root / "reports/literature/review/packets/ep0001-r001.md").read_text(encoding="utf-8")
            self.assertIn("Human Review Checklist", content)
            self.assertIn("Approval records a useful literature finding; it is not a novelty claim.", content)

    def test_preview_promotion_candidate_does_not_create_finding_or_queue(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0001.json",
                {
                    "number": 1,
                    "problem_id": "ep0001",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Every large integer is a sum of a prime and powers of two.",
                    "known_references": [],
                },
            )
            write_json(
                root / "data/problems/ep0002.json",
                {
                    "number": 2,
                    "problem_id": "ep0002",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Can every large integer be represented using a prime and a small additive basis?",
                    "known_references": [],
                },
            )
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["prime additive basis"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "A prime additive basis method",
                            "identifier": "10.1000/example",
                            "url": "https://doi.org/10.1000/example",
                            "abstract_snippet": "Uses primes and additive basis constructions.",
                            "relevance_terms": ["prime", "additive", "basis"],
                            "relevance_score": 3,
                        }
                    ],
                },
            )
            build_promotion_candidate_report(root, min_score=1)

            preview = preview_promotion_candidate(root, "ep0001-r001", status_filter={"open"}, queue_min_score=1)

            self.assertFalse(preview["preview"]["writes"]["creates_literature_finding"])
            self.assertEqual(preview["preview"]["pivot_preview"]["items"][0]["problem_id"], "ep0002")
            self.assertEqual(preview["preview"]["queue_preview"]["items"][0]["problem_id"], "ep0002")
            self.assertFalse(list((root / "reports/literature/findings").glob("*.json")))
            self.assertFalse(list((root / "reports/pivots").glob("*.json")))
            self.assertFalse(list((root / "agent_runs/inbox").glob("*.json")))
            self.assertTrue((root / "reports/literature/review/previews/ep0001-r001.md").exists())

    def test_record_promotion_candidate_decision_hides_decided_by_default(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["prime additive basis"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "A false lead",
                            "identifier": "10.1000/false-lead",
                            "abstract_snippet": "A useful abstract.",
                            "relevance_terms": ["prime", "additive", "basis"],
                            "relevance_score": 3,
                        }
                    ],
                },
            )
            build_promotion_candidate_report(root, min_score=1)

            decision = record_promotion_candidate_decision(
                root,
                "ep0001-r001",
                decision="rejected",
                reviewer="human-a",
                notes=["keyword match only"],
            )
            hidden = build_promotion_candidate_report(root, min_score=1)
            visible = build_promotion_candidate_report(root, min_score=1, include_decided=True)

            self.assertEqual(decision["decision"]["reviewer"], "human-a")
            self.assertEqual(hidden["returned"], 0)
            self.assertEqual(visible["returned"], 1)
            self.assertEqual(visible["items"][0]["status"], "rejected")

    def test_candidate_decision_hides_duplicate_paper_variants(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["sidon systems"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "The structure of Sidon set systems",
                            "identifier": "10.5817/cz.muni.eurocomb23-114",
                            "abstract_snippet": "A useful abstract.",
                            "relevance_terms": ["sidon", "systems"],
                            "relevance_score": 4,
                        },
                        {
                            "source": "arxiv",
                            "title": "The structure of Sidon set systems",
                            "identifier": "2211.14011v2",
                            "abstract_snippet": "A useful abstract.",
                            "relevance_terms": ["sidon", "systems"],
                            "relevance_score": 3,
                        },
                    ],
                },
            )
            build_promotion_candidate_report(root, min_score=1)
            record_promotion_candidate_decision(
                root,
                "ep0001-r001",
                decision="needs_more_reading",
                reviewer="human-a",
                notes=["withdrawn related preprint"],
            )

            hidden = build_promotion_candidate_report(root, min_score=1)
            visible = build_promotion_candidate_report(root, min_score=1, include_decided=True)

            self.assertEqual(hidden["returned"], 0)
            self.assertEqual(visible["returned"], 1)
            self.assertEqual(visible["items"][0]["status"], "needs_more_reading")

    def test_supervisor_step_includes_review_candidate_summary(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["prime additive basis"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "A strong candidate",
                            "identifier": "10.1000/strong",
                            "abstract_snippet": "A useful abstract.",
                            "relevance_terms": ["prime", "additive", "basis", "integers"],
                            "relevance_score": 4,
                        }
                    ],
                },
            )
            build_promotion_candidate_report(root, min_score=1)
            step = supervisor_step(root, limit=3)
            review = step["review_candidates"]
            self.assertTrue(review["available"])
            self.assertEqual(review["candidate_count"], 1)
            self.assertEqual(review["top_candidates"][0]["candidate_id"], "ep0001-r001")

    def test_quickstart_check_runs_safe_local_checks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0001.json",
                {
                    "number": 1,
                    "problem_id": "ep0001",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Every large integer is a sum of a prime and powers of two.",
                    "known_references": [],
                },
            )
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["prime additive basis"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "A strong candidate",
                            "identifier": "10.1000/strong",
                            "abstract_snippet": "A useful abstract.",
                            "relevance_terms": ["prime", "additive", "basis", "integers"],
                            "relevance_score": 4,
                        }
                    ],
                },
            )
            report = quickstart_check(root, status_filter={"open"}, triage_limit=5, review_limit=5, min_review_score=1)
            self.assertTrue(report["safe"])
            self.assertEqual(report["problem_count"], 1)
            self.assertEqual(report["triage"]["returned"], 1)
            self.assertEqual(report["review"]["candidate_count"], 1)
            self.assertTrue((root / "reports/quickstart/check.json").exists())
            self.assertTrue((root / "reports/quickstart/check.md").exists())

    def test_approve_promotion_candidate_promotes_and_queues(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0001.json",
                {
                    "number": 1,
                    "problem_id": "ep0001",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Every large integer is a sum of a prime and powers of two.",
                    "known_references": [],
                },
            )
            write_json(
                root / "data/problems/ep0002.json",
                {
                    "number": 2,
                    "problem_id": "ep0002",
                    "status_site": "open",
                    "tags": ["number theory", "additive basis"],
                    "statement_raw": "Can every large integer be represented using a prime and a small additive basis?",
                    "known_references": [],
                },
            )
            write_json(
                root / "reports/literature/search/ep0001.json",
                {
                    "problem_id": "ep0001",
                    "queries": ["prime additive basis"],
                    "results": [
                        {
                            "source": "crossref",
                            "title": "A prime additive basis method",
                            "identifier": "10.1000/example",
                            "url": "https://doi.org/10.1000/example",
                            "abstract_snippet": "Uses primes and additive basis constructions.",
                            "relevance_terms": ["prime", "additive", "basis"],
                            "relevance_score": 3,
                        }
                    ],
                },
            )
            build_promotion_candidate_report(root)
            approval = approve_promotion_candidate(
                root,
                "ep0001-r001",
                status_filter={"open"},
                queue_pivots=True,
                queue_limit=1,
                queue_min_score=1,
                reviewer="human-a",
                review_notes=["looks relevant enough to pivot"],
            )
            self.assertEqual(approval["approval"]["status"], "approved")
            self.assertEqual(approval["approval"]["reviewer"], "human-a")
            self.assertEqual(approval["approval"]["review_notes"], ["looks relevant enough to pivot"])
            self.assertEqual(len(approval["queued_runs"]), 1)
            self.assertTrue((root / "reports/literature/review/approvals/ep0001-r001.json").exists())
            self.assertTrue((root / "agent_runs/inbox" / f"{approval['queued_runs'][0]['run_id']}.json").exists())

    def test_record_math_example(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            payload = record_math_example(
                root,
                example_id="Toy Example",
                statement="The powers of two have distinct subset sums.",
                tags=["subset sums"],
            )
            self.assertEqual(payload["example_id"], "toy-example")
            self.assertTrue((root / "kb/examples/toy-example.md").exists())

    def test_agent_run_lifecycle(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            run = create_agent_run(
                root,
                agent="literature",
                problem_id=9,
                prompt="Find relevant papers.",
                artifacts=["data/problems/ep0009.json"],
            )
            self.assertTrue((root / "agent_runs/inbox" / f"{run['run_id']}.json").exists())
            step = supervisor_step(root)
            self.assertEqual(step["queued_count"], 1)
            completed = complete_agent_run(
                root,
                run["run_id"],
                status="done",
                summary="Found one paper.",
                artifacts=["reports/literature/findings/example.json"],
            )
            self.assertEqual(completed["status"], "done")
            self.assertFalse((root / "agent_runs/inbox" / f"{run['run_id']}.json").exists())
            self.assertTrue((root / "agent_runs/outbox" / f"{run['run_id']}.json").exists())

    def test_create_agent_run_reuses_existing_queued_run(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            first = create_agent_run(root, agent="literature", problem_id=9)
            second = create_agent_run(root, agent="literature", problem_id="ep0009")
            self.assertEqual(first["run_id"], second["run_id"])

    def test_create_runs_from_triage(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "reports/triage/index.json",
                {
                    "items": [
                        {
                            "problem_id": "ep0009",
                            "priority_score": 37,
                            "recommended_next_action": "computation",
                        },
                        {
                            "problem_id": "ep0025",
                            "priority_score": 43,
                            "recommended_next_action": "literature_review",
                        },
                    ]
                },
            )
            runs = create_runs_from_triage(
                root,
                agent="literature",
                limit=1,
                action_filter={"literature_review"},
            )
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["problem_id"], "ep0025")

    def test_create_runs_from_pivot_uses_auto_agent_mapping(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0002.json",
                {
                    "number": 2,
                    "problem_id": "ep0002",
                    "status_site": "open",
                    "statement_raw": "A problem needing literature.",
                },
            )
            write_json(
                root / "data/problems/ep0003.json",
                {
                    "number": 3,
                    "problem_id": "ep0003",
                    "status_site": "open",
                    "statement_raw": "A problem needing computation.",
                },
            )
            write_json(
                root / "reports/pivots/example-finding.json",
                {
                    "finding_id": "example-finding",
                    "source_problem_id": "ep0001",
                    "paper_key": "Ab24",
                    "items": [
                        {
                            "problem_id": "ep0002",
                            "pivot_score": 10,
                            "recommended_next_action": "literature_review",
                        },
                        {
                            "problem_id": "ep0003",
                            "pivot_score": 9,
                            "recommended_next_action": "computation",
                        },
                        {
                            "problem_id": "ep0004",
                            "pivot_score": 1,
                            "recommended_next_action": "statement_audit",
                        },
                    ],
                },
            )
            runs = create_runs_from_pivot(root, "example-finding", agent="auto", limit=5, min_score=5)
            self.assertEqual([run["agent"] for run in runs], ["literature", "computation"])
            self.assertEqual(runs[0]["metadata"]["source"], "pivot")
            self.assertEqual(runs[0]["metadata"]["finding_id"], "example-finding")
            self.assertIn("reports/pivots/example-finding.json", runs[0]["artifacts"])

    def test_execute_literature_agent_run(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0009.json",
                {
                    "number": 9,
                    "problem_id": "ep0009",
                    "status_site": "open",
                    "tags": ["number theory", "primes"],
                    "url": "https://example.invalid/9",
                    "statement_raw": "Is every large odd integer a prime plus two powers of two?",
                    "statement_source": "test",
                    "remarks_raw": "A useful reference exists.",
                    "known_references": ["[Ab24] A. Author, A title."],
                    "oeis": [],
                    "formalization_status": "yes",
                },
            )
            run = create_agent_run(root, agent="literature", problem_id=9)
            original_search = core.search_literature_for_problem
            try:
                core.search_literature_for_problem = lambda *args, **kwargs: {
                    "artifacts": [],
                    "errors": [],
                    "result_count": 0,
                }
                completed = execute_agent_run(root, run["run_id"])
            finally:
                core.search_literature_for_problem = original_search
            self.assertEqual(completed["status"], "done")
            self.assertTrue((root / "reports/literature/ep0009.md").exists())
            self.assertTrue((root / "agent_runs/outbox" / f"{run['run_id']}.json").exists())

    def test_execute_blind_solver_packet_run_needs_human(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            write_json(
                root / "data/problems/ep0001.json",
                {
                    "number": 1,
                    "problem_id": "ep0001",
                    "statement_raw": "For every integer n >= 2, prove that n^2 >= 2n.",
                },
            )
            run = create_agent_run(root, agent="blind_solver", problem_id=1)
            completed = execute_agent_run(root, run["run_id"])
            self.assertEqual(completed["status"], "needs_human")
            self.assertTrue(completed["result_artifacts"][0].startswith("packets/blind/"))

    def test_execute_next_agent_run_handles_idle_and_agent_filter(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ensure_workspace(root)
            idle = execute_next_agent_run(root)
            self.assertEqual(idle["status"], "idle")
            write_json(
                root / "data/problems/ep0001.json",
                {
                    "number": 1,
                    "problem_id": "ep0001",
                    "statement_raw": "For every integer n >= 2, prove that n^2 >= 2n.",
                    "tags": [],
                    "known_references": [],
                    "oeis": [],
                },
            )
            create_agent_run(root, agent="computation", problem_id=1)
            still_idle = execute_next_agent_run(root, agent="literature")
            self.assertEqual(still_idle["status"], "idle")
            done = execute_next_agent_run(root, agent="computation")
            self.assertEqual(done["status"], "done")
            self.assertTrue((root / "agent_runs/last_run_next.json").exists())


if __name__ == "__main__":
    unittest.main()
