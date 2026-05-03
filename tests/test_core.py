import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from erdos_agent.core import (
    complete_agent_run,
    create_agent_run,
    create_runs_from_triage,
    ensure_workspace,
    execute_agent_run,
    execute_next_agent_run,
    extract_problem_content_from_html,
    extract_problem_statement_from_html,
    github_record_to_problem,
    make_blind_packet,
    normalize_problem_id,
    parse_github_problems_yaml,
    pivot_from_literature_finding,
    record_literature_finding,
    record_math_example,
    score_problem,
    similarity_score,
    supervisor_step,
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
            completed = execute_agent_run(root, run["run_id"])
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
