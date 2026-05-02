from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_DIRS = [
    "data/problems",
    "data/raw",
    "data/references",
    "data/manifests",
    "notes",
    "reports/triage",
    "reports/literature",
    "reports/statement_audits",
    "reports/attempts",
    "reports/referee",
    "packets/blind",
    "packets/literature",
    "computations",
    "lean",
]

AMBIGUITY_TERMS = [
    "sufficiently large",
    "large enough",
    "small enough",
    "almost all",
    "density",
    "positive density",
    "constant",
    "absolute constant",
    "bounded",
    "approximately",
    "asymptotic",
    "random",
    "generic",
    "typical",
    "nontrivial",
]

FINITE_SEARCH_TERMS = [
    "integer",
    "integers",
    "natural number",
    "finite",
    "graph",
    "sequence",
    "set",
    "subset",
    "permutation",
    "coloring",
    "partition",
    "matrix",
    "prime",
]

FORMALIZATION_TERMS = [
    "for all",
    "there exists",
    "if and only if",
    "iff",
    "let",
    "prove",
    "show",
    "integer",
    "natural",
    "finite",
]

EXPERT_TAG_TERMS = [
    "analytic",
    "ergodic",
    "probabilistic",
    "algebraic geometry",
    "model theory",
    "operator",
    "functional analysis",
    "automorphic",
]

LEAK_TERMS = [
    r"\berd[őo]s\b",
    r"\bpaul erd[őo]s\b",
    r"\berdosproblems\b",
    r"\berdős problems\b",
    r"\berdos problems\b",
    r"\bopen problem\b",
    r"\bunsolved\b",
    r"\bconjecture\s+\d+\b",
    r"\bproblem\s+#?\d+\b",
    r"#\d+",
]


@dataclass(frozen=True)
class WriteResult:
    path: Path
    content: str


def ensure_workspace(root: Path) -> None:
    for directory in DEFAULT_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)


def normalize_problem_id(problem_id: str | int) -> str:
    raw = str(problem_id).strip().lower()
    if raw.startswith("ep"):
        raw = raw[2:]
    raw = raw.lstrip("#")
    if not raw.isdigit():
        raise ValueError(f"Problem id must be numeric or epNNNN, got: {problem_id!r}")
    return f"ep{int(raw):04d}"


def problem_path(root: Path, problem_id: str | int) -> Path:
    return root / "data" / "problems" / f"{normalize_problem_id(problem_id)}.json"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> WriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8")
    return WriteResult(path=path, content=content)


def write_text(path: Path, content: str) -> WriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return WriteResult(path=path, content=content)


def create_problem(
    root: Path,
    number: int,
    statement: str,
    *,
    title: str = "",
    url: str = "",
    tags: list[str] | None = None,
    status_site: str = "unknown",
) -> WriteResult:
    problem_id = normalize_problem_id(number)
    payload = {
        "number": number,
        "problem_id": problem_id,
        "title": title,
        "url": url,
        "status_site": status_site,
        "status_local": "not_started",
        "tags": tags or [],
        "prize": None,
        "statement_raw": statement.strip(),
        "statement_latex": "",
        "known_references": [],
        "comments_summary": [],
        "literature_status": "not_started",
        "statement_risk": "unknown",
        "formalization_status": "none",
        "attempts": [],
        "review_labels": [],
        "last_checked": date.today().isoformat(),
    }
    return write_json(root / "data" / "problems" / f"{problem_id}.json", payload)


def load_problem(root: Path, problem_id: str | int) -> dict[str, Any]:
    path = problem_path(root, problem_id)
    if not path.exists():
        raise FileNotFoundError(f"No problem JSON found at {path}")
    return read_json(path)


def task_id_for_statement(statement: str) -> str:
    digest = hashlib.sha256(statement.strip().encode("utf-8")).hexdigest()[:12]
    return f"math-task-{digest}"


def redaction_leaks(text: str) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for pattern in LEAK_TERMS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            found.append(pattern)
    return found


def make_blind_packet(problem: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    task_id = task_id_for_statement(statement)
    leaks = redaction_leaks(statement)
    content = f"""# Mathematical Task {task_id}

## Statement

{statement.strip()}

## Work Request

Prove or disprove the statement above. If a full solution is not available, produce the strongest useful partial progress you can.

## Required Process

- Check small, degenerate, and boundary cases before attempting a proof.
- State the exact claim being proved or refuted.
- Separate rigorous arguments from heuristics.
- If using a lemma, state it precisely and indicate whether it is proved here or assumed.
- Try to produce counterexamples as actively as proofs.
- Do not make any novelty, publication, or priority claim.

## Output Contract

Return the result in these sections:

1. Exact statement considered
2. Edge cases and counterexample search
3. Main proof or disproof attempt
4. Lemmas used
5. Gaps or uncertain steps
6. Suggested formalization target
"""
    manifest = {
        "task_id": task_id,
        "problem_id": problem.get("problem_id") or normalize_problem_id(problem["number"]),
        "hidden_fields": [
            "number",
            "problem_id",
            "url",
            "status_site",
            "status_local",
            "title",
            "prize",
            "known_references",
            "comments_summary",
        ],
        "statement_leak_patterns": leaks,
        "created_at": date.today().isoformat(),
    }
    return task_id, content, manifest


def make_literature_packet(problem: dict[str, Any]) -> tuple[str, str]:
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    task_id = task_id_for_statement(statement)
    keywords = extract_keywords(statement)
    content = f"""# Anonymous Literature Search Packet {task_id}

## Mathematical Statement

{statement.strip()}

## Search Goal

Find known theorems, equivalent formulations, special cases, counterexamples, and computational data related to the statement. Do not assume the statement is new.

## Suggested Keyword Fragments

{chr(10).join(f"- {keyword}" for keyword in keywords)}

## Result Card Format

For each relevant result, return:

- Anonymous result id
- Precise mathematical statement
- Assumptions
- Relation to target: implies / nearly implies / special case / obstruction / unrelated
- Method summary
- Confidence

Keep source metadata in a separate supervisor-only bibliography. The solver should receive only anonymized result cards.
"""
    return task_id, content


def extract_keywords(statement: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", statement)
    stop = {
        "that",
        "with",
        "there",
        "then",
        "where",
        "such",
        "from",
        "have",
        "show",
        "prove",
        "every",
        "exists",
        "integer",
        "integers",
        "number",
        "numbers",
    }
    counts: dict[str, int] = {}
    for word in words:
        key = word.lower()
        if key not in stop:
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts, key=lambda item: (-counts[item], item))
    return ranked[:limit] or ["exact statement keywords"]


def score_problem(problem: dict[str, Any]) -> dict[str, Any]:
    statement = (problem.get("statement_raw") or problem.get("statement_latex") or "").lower()
    tags = [str(tag).lower() for tag in problem.get("tags", [])]
    references = problem.get("known_references") or []
    comments = problem.get("comments_summary") or []

    checkability = bounded_score(count_terms(statement, FINITE_SEARCH_TERMS) + count_terms(statement, FORMALIZATION_TERMS), 0, 5)
    literature_gap = 3 if len(references) == 0 else 2 if len(references) <= 2 else 1 if len(references) <= 5 else 0
    statement_ambiguity = bounded_score(count_terms(statement, AMBIGUITY_TERMS), 0, 4)
    finite_searchability = bounded_score(count_terms(statement, FINITE_SEARCH_TERMS), 0, 4)
    formalization_readiness = estimate_formalization_readiness(statement, statement_ambiguity)
    forum_activity = 2 if len(comments) >= 5 else 1 if comments else 0
    domain_fit = 1
    famous_acorn_risk = 2 if problem.get("prize") else 0
    expert_dependency = bounded_score(count_terms(" ".join(tags) + " " + statement, EXPERT_TAG_TERMS), 0, 3)
    social_media_hype = 0

    priority_score = (
        3 * checkability
        + 3 * literature_gap
        + 2 * statement_ambiguity
        + 2 * finite_searchability
        + 2 * formalization_readiness
        + forum_activity
        + domain_fit
        - 3 * famous_acorn_risk
        - 2 * expert_dependency
        - 2 * social_media_hype
    )

    components = {
        "checkability": checkability,
        "literature_gap": literature_gap,
        "statement_ambiguity": statement_ambiguity,
        "finite_searchability": finite_searchability,
        "formalization_readiness": formalization_readiness,
        "forum_activity": forum_activity,
        "domain_fit": domain_fit,
        "famous_acorn_risk": famous_acorn_risk,
        "expert_dependency": expert_dependency,
        "social_media_hype": social_media_hype,
    }

    return {
        "problem_id": problem.get("problem_id") or normalize_problem_id(problem["number"]),
        "priority_score": priority_score,
        "components": components,
        "recommended_next_action": recommend_next_action(components),
        "caveats": make_triage_caveats(problem, components),
        "generated_at": date.today().isoformat(),
    }


def count_terms(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def bounded_score(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def estimate_formalization_readiness(statement: str, statement_ambiguity: int) -> int:
    base = count_terms(statement, FORMALIZATION_TERMS)
    if len(statement) < 300:
        base += 1
    if len(statement) > 1500:
        base -= 1
    base -= min(statement_ambiguity, 2)
    return bounded_score(base, 0, 4)


def recommend_next_action(components: dict[str, int]) -> str:
    if components["statement_ambiguity"] >= 2:
        return "statement_audit"
    if components["literature_gap"] >= 2:
        return "literature_review"
    if components["finite_searchability"] >= 2:
        return "computation"
    if components["formalization_readiness"] >= 2:
        return "lean_formalization"
    if components["expert_dependency"] >= 2:
        return "needs_domain_expert"
    return "blind_proof_attempt"


def make_triage_caveats(problem: dict[str, Any], components: dict[str, int]) -> list[str]:
    caveats: list[str] = []
    if components["literature_gap"] >= 2:
        caveats.append("known_references is sparse; do not make novelty claims before a real literature pass.")
    if components["statement_ambiguity"] >= 2:
        caveats.append("statement contains ambiguity markers; audit quantifiers and edge cases before solving.")
    if components["expert_dependency"] >= 2:
        caveats.append("tags or wording suggest domain expertise may be needed for review.")
    if redaction_leaks(problem.get("statement_raw", "")):
        caveats.append("statement itself may leak source/status context; consider manual redaction before blind solving.")
    return caveats


def make_statement_audit(problem: dict[str, Any]) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    return f"""# Statement Audit for {problem_id}

## Raw Statement

{statement.strip()}

## Literal Formalization

TODO

## Intended Formulation

TODO

## Quantifier Order

- TODO: identify all variables and dependencies.

## Edge Cases

- n = 0:
- n = 1:
- empty set:
- equality case:
- smallest nontrivial example:

## Trivial Solution or Counterexample Check

TODO

## Redaction Risk

- Does the statement itself reveal that this is an Erdős problem?
- Does it contain a problem number, source phrase, or "open problem" wording?

## Misstatement Risk

low / medium / high

## Recommendation

TODO
"""


def make_claim_card(problem: dict[str, Any], task_id: str) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    return f"""# Claim Card for {problem_id}

## Blind Task

{task_id}

## Claim

TODO

## Type

full solution / counterexample / partial result / literature rediscovery / computation / formalization

## Exact Statement Proved

TODO

## Difference from Original Problem

TODO

## Proof Sketch

TODO

## Dependencies

TODO

## Known Literature Comparison

TODO

## Verification

- human check:
- computation:
- Lean:
- critic agents:

## Failure Modes

TODO

## Recommendation

do_not_post / ask_expert / post_comment / prepare_pdf / submit_pr
"""

