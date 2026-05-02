import unittest

from erdos_agent.core import (
    extract_problem_statement_from_html,
    github_record_to_problem,
    make_blind_packet,
    normalize_problem_id,
    parse_github_problems_yaml,
    score_problem,
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
        problem = github_record_to_problem(record, statement="Let n be a natural number.")
        self.assertEqual(problem["problem_id"], "ep0001")
        self.assertEqual(problem["status_site"], "open")
        self.assertIsNone(problem["prize"])
        self.assertEqual(problem["formalization_status"], "yes")
        self.assertEqual(problem["statement_source"], "site_latex")

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


if __name__ == "__main__":
    unittest.main()
