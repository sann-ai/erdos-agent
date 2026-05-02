import unittest

from erdos_agent.core import make_blind_packet, normalize_problem_id, score_problem


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


if __name__ == "__main__":
    unittest.main()

