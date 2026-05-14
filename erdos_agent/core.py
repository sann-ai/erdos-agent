from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from itertools import combinations_with_replacement
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROBLEMS_YAML_URL = "https://raw.githubusercontent.com/teorth/erdosproblems/main/data/problems.yaml"
ERDOS_PROBLEMS_BASE_URL = "https://www.erdosproblems.com"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
CROSSREF_API_URL = "https://api.crossref.org/works"


DEFAULT_DIRS = [
    "data/problems",
    "data/raw",
    "data/references",
    "data/manifests",
    "notes",
    "reports/triage",
    "reports/analogies",
    "reports/quickstart",
    "reports/literature",
    "reports/literature/findings",
    "reports/literature/promotions",
    "reports/literature/review",
    "reports/literature/review/approvals",
    "reports/literature/review/decisions",
    "reports/literature/review/packets",
    "reports/literature/review/previews",
    "reports/literature/search",
    "reports/literature/result_cards",
    "reports/pivots",
    "reports/statement_audits",
    "reports/attempts",
    "reports/referee",
    "reports/proof_routes",
    "packets/blind",
    "packets/literature",
    "agent_runs",
    "agent_runs/inbox",
    "agent_runs/outbox",
    "kb/raw/papers",
    "kb/wiki/problems",
    "kb/wiki/papers",
    "kb/wiki/methods",
    "kb/examples",
    "kb/method_cards",
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
    ensure_seed_file(root / "kb" / "index.md", "# Knowledge Base Index\n\n")
    ensure_seed_file(root / "kb" / "log.md", "# Knowledge Base Log\n\n")
    ensure_seed_file(
        root / "kb" / "schema.md",
        """# Knowledge Base Schema

This knowledge base follows a compiled-wiki pattern:

- `raw/`: immutable source material.
- `wiki/`: maintained markdown summaries and cross-links.
- `examples/`: mathematical examples, constructions, counterexamples, and small cases.
- `method_cards/`: reusable proof/computation/formalization patterns.
- `index.md`: content-oriented navigation.
- `log.md`: append-only chronological activity log.

Agents may read all layers. Agents must not modify raw sources.
""",
    )


def ensure_seed_file(path: Path, content: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


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


def fetch_text(url: str, *, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "erdos-agent/0.1 (+https://github.com/sann-ai/erdos-agent)",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def fetch_json(url: str, *, timeout: int = 30) -> dict[str, Any]:
    return json.loads(fetch_text(url, timeout=timeout))


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


def list_problem_paths(root: Path) -> list[Path]:
    return sorted((root / "data" / "problems").glob("ep*.json"))


def ingest_github_problems(
    root: Path,
    *,
    yaml_text: str | None = None,
    source_url: str = PROBLEMS_YAML_URL,
    limit: int | None = None,
    status_filter: set[str] | None = None,
    fetch_statements: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    if yaml_text is None:
        yaml_text = fetch_text(source_url)
    write_text(root / "data" / "raw" / "problems.yaml", yaml_text)

    records = parse_github_problems_yaml(yaml_text)
    written: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []
    selected = 0

    for record in records:
        status = nested_state(record, "status", default="unknown").lower()
        if status_filter and status not in status_filter:
            continue
        selected += 1
        if limit is not None and selected > limit:
            break

        problem_id = normalize_problem_id(record["number"])
        existing = read_json(problem_path(root, problem_id)) if problem_path(root, problem_id).exists() else None
        page_data: dict[str, Any] = {}
        if fetch_statements:
            try:
                page_data = fetch_problem_page_data(int(record["number"]))
            except Exception as exc:
                errors.append({"problem_id": problem_id, "error": str(exc)})

        payload = github_record_to_problem(
            record,
            existing=existing,
            page_data=page_data,
            overwrite=overwrite,
            source_url=source_url,
        )
        write_json(root / "data" / "problems" / f"{problem_id}.json", payload)
        written.append(problem_id)

    summary = {
        "source_url": source_url,
        "records_seen": len(records),
        "written": len(written),
        "skipped": len(skipped),
        "errors": errors,
        "fetch_statements": fetch_statements,
        "status_filter": sorted(status_filter) if status_filter else [],
        "last_checked": date.today().isoformat(),
    }
    write_json(root / "data" / "raw" / "ingest_summary.json", summary)
    return summary


def parse_github_problems_yaml(yaml_text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section: str | None = None

    for raw_line in yaml_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        if raw_line.startswith("- "):
            if current is not None:
                records.append(current)
            current = {}
            section = None
            remainder = raw_line[2:].strip()
            if remainder:
                key, value = parse_yaml_key_value(remainder)
                current[key] = parse_yaml_value(value)
            continue

        if current is None:
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 2:
            key, value = parse_yaml_key_value(line)
            if value == "":
                current[key] = {}
                section = key
            else:
                current[key] = parse_yaml_value(value)
                section = None
        elif indent == 4 and section:
            key, value = parse_yaml_key_value(line)
            section_payload = current.setdefault(section, {})
            if isinstance(section_payload, dict):
                section_payload[key] = parse_yaml_value(value)

    if current is not None:
        records.append(current)
    return records


def parse_yaml_key_value(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ValueError(f"Expected key: value line, got: {line!r}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def parse_yaml_value(value: str) -> Any:
    if value == "":
        return ""
    if value in {"null", "Null", "NULL", "~"}:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    if value.startswith("[") and value.endswith("]"):
        return [part.strip().strip('"').strip("'") for part in value[1:-1].split(",") if part.strip()]
    if value.isdigit():
        return int(value)
    return value.strip('"').strip("'")


def github_record_to_problem(
    record: dict[str, Any],
    *,
    existing: dict[str, Any] | None = None,
    statement: str = "",
    page_data: dict[str, Any] | None = None,
    overwrite: bool = False,
    source_url: str = PROBLEMS_YAML_URL,
) -> dict[str, Any]:
    number = int(record["number"])
    problem_id = normalize_problem_id(number)
    status = nested_state(record, "status", default="unknown")
    formalized = nested_state(record, "formalized", default="unknown")
    existing = existing or {}
    page_data = page_data or {}
    statement = str(page_data.get("statement") or statement)
    existing_statement = existing.get("statement_raw", "")
    statement_raw = statement.strip() if statement.strip() and (overwrite or not existing_statement) else existing_statement
    statement_source = "site_latex" if statement.strip() and (overwrite or not existing_statement) else existing.get("statement_source", "not_fetched")
    remarks = str(page_data.get("remarks") or "")
    existing_remarks = existing.get("remarks_raw", "")
    remarks_raw = remarks.strip() if remarks.strip() and (overwrite or not existing_remarks) else existing_remarks
    references = page_data.get("references") or []
    known_references = references if references and (overwrite or not existing.get("known_references")) else existing.get("known_references", [])
    prize = normalize_prize(record.get("prize"))

    return {
        "number": number,
        "problem_id": problem_id,
        "title": existing.get("title", ""),
        "url": f"{ERDOS_PROBLEMS_BASE_URL}/{number}",
        "status_site": status,
        "status_local": existing.get("status_local", "not_started"),
        "tags": ensure_list(record.get("tags")),
        "prize": prize,
        "oeis": ensure_list(record.get("oeis")),
        "formalized": record.get("formalized", {}),
        "statement_raw": statement_raw,
        "statement_latex": existing.get("statement_latex", ""),
        "statement_source": statement_source,
        "remarks_raw": remarks_raw,
        "known_references": known_references,
        "comments_summary": existing.get("comments_summary", []),
        "literature_status": existing.get("literature_status", "not_started"),
        "statement_risk": existing.get("statement_risk", "unknown"),
        "formalization_status": formalized,
        "attempts": existing.get("attempts", []),
        "review_labels": existing.get("review_labels", []),
        "source_metadata": {
            "github_yaml_url": source_url,
            "github_record": record,
        },
        "last_checked": date.today().isoformat(),
    }


def nested_state(record: dict[str, Any], key: str, *, default: str) -> str:
    value = record.get(key)
    if isinstance(value, dict):
        return str(value.get("state", default))
    if value is None:
        return default
    return str(value)


def normalize_prize(prize: Any) -> str | None:
    if prize is None:
        return None
    prize_text = str(prize).strip()
    if prize_text.lower() in {"", "no", "none", "n/a"}:
        return None
    return prize_text


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def fetch_problem_statement(number: int) -> str:
    statement = fetch_problem_page_data(number)["statement"]
    if not statement:
        raise ValueError(f"Could not extract statement for problem {number}")
    return statement


def fetch_problem_page_data(number: int) -> dict[str, Any]:
    html_text = fetch_text(f"{ERDOS_PROBLEMS_BASE_URL}/latex/{number}")
    content = extract_problem_content_from_html(html_text)
    if not content["statement"]:
        raise ValueError(f"Could not extract statement for problem {number}")
    return content


def extract_problem_statement_from_html(html_text: str) -> str:
    return extract_problem_content_from_html(html_text)["statement"]


def extract_problem_content_from_html(html_text: str) -> dict[str, Any]:
    statement_parser = FirstClassDivTextParser("problem-text")
    statement_parser.feed(html_text)

    additional_parser = ClassDivTextCollector("problem-additional-text")
    additional_parser.feed(html_text)
    additional_sections = [clean_html_text(text) for text in additional_parser.texts]
    additional_sections = [text for text in additional_sections if text]

    references_section = ""
    remarks_sections: list[str] = []
    for section in additional_sections:
        lowered = section.lower()
        if lowered.startswith("references"):
            references_section = section
        elif "back to the problem" not in lowered:
            remarks_sections.append(section)

    remarks = "\n\n".join(remarks_sections).strip()
    return {
        "statement": clean_html_text(statement_parser.text),
        "remarks": remarks,
        "references": parse_reference_entries(references_section),
    }


def parse_reference_entries(text: str) -> list[str]:
    references: list[str] = []
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower() == "references":
            continue
        if re.match(r"^\[[^\]]+\]", stripped):
            if current:
                references.append(current.strip())
            current = stripped
        elif current:
            current = f"{current} {stripped}"
    if current:
        references.append(current.strip())
    return references


class ClassDivTextCollector(HTMLParser):
    def __init__(self, class_name: str) -> None:
        super().__init__()
        self.class_name = class_name
        self.depth = 0
        self.capturing = False
        self.current_parts: list[str] = []
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.capturing:
            if tag == "br":
                self.current_parts.append("\n")
                return
            self.depth += 1
            return
        if tag != "div":
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        classes = attrs_dict.get("class", "").split()
        if self.class_name in classes:
            self.capturing = True
            self.depth = 1
            self.current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if not self.capturing:
            return
        self.depth -= 1
        if self.depth <= 0:
            self.capturing = False
            self.texts.append("".join(self.current_parts))
            self.current_parts = []

    def handle_data(self, data: str) -> None:
        if self.capturing:
            self.current_parts.append(data)


class FirstClassDivTextParser(HTMLParser):
    def __init__(self, class_name: str) -> None:
        super().__init__()
        self.class_name = class_name
        self.depth = 0
        self.capturing = False
        self.parts: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.capturing:
            if tag == "br":
                self.parts.append("\n")
                return
            self.depth += 1
            return
        if tag != "div":
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        classes = attrs_dict.get("class", "").split()
        if self.class_name in classes:
            self.capturing = True
            self.depth = 1

    def handle_endtag(self, tag: str) -> None:
        if not self.capturing:
            return
        self.depth -= 1
        if self.depth <= 0:
            self.capturing = False

    def handle_data(self, data: str) -> None:
        if self.capturing:
            self.parts.append(data)


def clean_html_text(text: str) -> str:
    unescaped = html.unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in unescaped.splitlines()]
    return "\n".join(line for line in lines if line).strip()


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
    if not statement.strip():
        problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
        raise ValueError(f"{problem_id} has no statement text; fetch or add a statement before redaction.")
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


def make_difference_packing_proof_route(root: Path, problem_id: str | int) -> dict[str, Any]:
    problem = load_problem(root, problem_id)
    normalized = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    task_content = difference_packing_blind_task()
    task_id = task_id_for_statement(task_content)
    source_content = render_difference_packing_source_note(problem, task_id=task_id)
    manifest = {
        "task_id": task_id,
        "problem_id": normalized,
        "route": "difference_packing",
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
            "source_literature",
        ],
        "statement_leak_patterns": redaction_leaks(task_content),
        "created_at": date.today().isoformat(),
        "source_statement_digest": hashlib.sha256(statement.strip().encode("utf-8")).hexdigest()[:12],
    }
    source_path = root / "reports" / "proof_routes" / f"{normalized}-difference-packing.md"
    packet_path = root / "packets" / "blind" / f"{task_id}-difference-packing.md"
    manifest_path = root / "data" / "manifests" / f"{task_id}-difference-packing.json"
    write_text(source_path, source_content)
    write_text(packet_path, task_content)
    write_json(manifest_path, manifest)
    append_log(root, f"proof_route_packet | {normalized} | difference_packing | {task_id}")
    return {
        "task_id": task_id,
        "problem_id": normalized,
        "route": "difference_packing",
        "artifacts": [
            str(source_path.relative_to(root)),
            str(packet_path.relative_to(root)),
            str(manifest_path.relative_to(root)),
        ],
    }


def difference_packing_blind_task() -> str:
    return """# Mathematical Task: Difference Packing for Sidon Sets

## Definitions

For a finite set S of integers, define

```text
D+(S) = {x-y : x, y in S and x > y}.
```

Call S a Sidon set if every positive difference in D+(S) occurs from at most one
ordered pair x > y in S. Equivalently, |D+(S)| = binom(|S|, 2).

For N >= 1, let f(N) be the maximum size of a Sidon subset of {1, ..., N}.

## Main Question

Let A, B be Sidon subsets of {1, ..., N} such that

```text
D+(A) cap D+(B) = empty.
```

Is it true that

```text
binom(|A|, 2) + binom(|B|, 2) <= binom(f(N), 2) + O(1)?
```

## Equal-Size Variant

If |A| = |B|, is there an absolute constant c > 0 such that

```text
binom(|A|, 2) + binom(|B|, 2)
  <= (1 - c + o(1)) binom(f(N), 2)?
```

## Suggested Attack Surface

- Treat D+(A) and D+(B) as two disjoint packed difference masks inside {1, ..., N-1}.
- Try to prove upper bounds from the fact that each mask comes from a Sidon set, not an arbitrary difference set.
- Look for an injection, compression, or transformation that converts the two disjoint masks into the difference mask of one large Sidon set, losing only O(1) differences.
- Try hard to disprove the first inequality by constructing two medium-sized Sidon sets with unusually complementary difference masks.
- For the equal-size variant, look for a density or energy obstruction that prevents two large equal Sidon sets from having disjoint difference masks.

## Output Contract

Return:

1. Exact formal statement considered
2. Edge cases and small examples
3. A proof attempt or counterexample family
4. Any lemma that would imply the main question
5. Known gaps or suspected false steps
6. A finite statement suitable for later formalization
"""


def render_difference_packing_source_note(problem: dict[str, Any], *, task_id: str) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    return f"""# Proof Route: Difference Packing for {problem_id}

Generated: {date.today().isoformat()}

This is a source-aware Supervisor note. Do not pass this file to Blind Solver.

## Original Statement

{statement or 'TODO'}

## Derived Blind Task

- task id: `{task_id}`
- blind packet: `packets/blind/{task_id}-difference-packing.md`

The blind task rewrites the problem as a finite difference-mask packing question for
Sidon sets and omits problem number, official status, source URL, references, and
literature metadata.

## Computation Signal

The current local exact harness is:

```bash
python3 computations/{problem_id}/search.py --max-n 20
```

In the latest local run through `N = 20`, the maximum observed unrestricted excess over
`binom(f(N), 2)` was `3`, and the maximum observed equal-size excess was `2`.

## Supervisor Notes

- This is not a proof or novelty claim.
- The route is currently proof-search material because small cases do not show a large
  counterexample signal.
- Literature candidates about popular differences or generalized Sidon sets are
  source-aware and should stay outside the blind packet unless manually anonymized.
"""


def make_literature_packet(problem: dict[str, Any]) -> tuple[str, str]:
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    if not statement.strip():
        problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
        raise ValueError(f"{problem_id} has no statement text; fetch or add a statement before literature packets.")
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
        "lvert",
        "rvert",
        "ldots",
        "subseteq",
        "mathbb",
        "geq",
        "leq",
        "epsilon",
        "frac",
        "left",
        "right",
        "backslash",
        "cite",
        "oeis",
        "possible",
    }
    counts: dict[str, int] = {}
    for word in words:
        key = word.lower()
        if re.fullmatch(r"a\d+", key):
            continue
        if key not in stop:
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts, key=lambda item: (-counts[item], item))
    return ranked[:limit] or ["exact statement keywords"]


def score_problem(problem: dict[str, Any]) -> dict[str, Any]:
    statement = (problem.get("statement_raw") or problem.get("statement_latex") or "").lower()
    tags = [str(tag).lower() for tag in problem.get("tags", [])]
    references = problem.get("known_references") or []
    comments = problem.get("comments_summary") or []
    oeis = [str(item).lower() for item in problem.get("oeis", [])]
    formalization_status = str(problem.get("formalization_status") or "").lower()
    has_statement = bool(statement.strip())

    checkability = bounded_score(count_terms(statement, FINITE_SEARCH_TERMS) + count_terms(statement, FORMALIZATION_TERMS), 0, 5)
    literature_gap = 3 if len(references) == 0 else 2 if len(references) <= 2 else 1 if len(references) <= 5 else 0
    statement_ambiguity = bounded_score(count_terms(statement, AMBIGUITY_TERMS), 0, 4)
    finite_searchability = bounded_score(count_terms(statement, FINITE_SEARCH_TERMS), 0, 4)
    formalization_readiness = estimate_formalization_readiness(statement, statement_ambiguity)
    if any(item.startswith("a") or item == "possible" for item in oeis):
        finite_searchability = bounded_score(finite_searchability + 1, 0, 4)
        checkability = bounded_score(checkability + 1, 0, 5)
    if formalization_status == "yes":
        formalization_readiness = bounded_score(formalization_readiness + 2, 0, 4)
        checkability = bounded_score(checkability + 1, 0, 5)
    elif formalization_status == "no" and has_statement:
        formalization_readiness = bounded_score(formalization_readiness + 1, 0, 4)
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
        "number": int(problem["number"]),
        "status_site": problem.get("status_site", "unknown"),
        "statement_present": has_statement,
        "priority_score": priority_score,
        "components": components,
        "recommended_next_action": recommend_next_action(components),
        "caveats": make_triage_caveats(problem, components),
        "generated_at": date.today().isoformat(),
    }


def triage_all(
    root: Path,
    *,
    status_filter: set[str] | None = None,
    limit: int | None = 30,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    considered = 0

    for path in list_problem_paths(root):
        problem = read_json(path)
        status = str(problem.get("status_site", "unknown")).lower()
        if status_filter and status not in status_filter:
            continue
        considered += 1
        score = score_problem(problem)
        write_json(root / "reports" / "triage" / f"{score['problem_id']}.json", score)
        items.append(
            {
                "problem_id": score["problem_id"],
                "number": score["number"],
                "status_site": score["status_site"],
                "url": problem.get("url", ""),
                "tags": problem.get("tags", []),
                "prize": problem.get("prize"),
                "oeis": problem.get("oeis", []),
                "formalization_status": problem.get("formalization_status", "unknown"),
                "statement_present": score["statement_present"],
                "priority_score": score["priority_score"],
                "recommended_next_action": score["recommended_next_action"],
                "components": score["components"],
                "caveats": score["caveats"],
            }
        )

    items.sort(key=lambda item: (-item["priority_score"], item["number"]))
    ranked_items = items if limit is None else items[:limit]
    index = {
        "generated_at": date.today().isoformat(),
        "status_filter": sorted(status_filter) if status_filter else [],
        "considered": considered,
        "returned": len(ranked_items),
        "items": ranked_items,
    }
    write_json(root / "reports" / "triage" / "index.json", index)
    return index


def find_similar_problems(
    root: Path,
    seed_problem_id: str | int,
    *,
    status_filter: set[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    seed = load_problem(root, seed_problem_id)
    seed_id = seed.get("problem_id") or normalize_problem_id(seed["number"])
    items: list[dict[str, Any]] = []
    problem_paths = list_problem_paths(root)
    common_refs = common_reference_keys(problem_paths)

    for path in problem_paths:
        candidate = read_json(path)
        candidate_id = candidate.get("problem_id") or normalize_problem_id(candidate["number"])
        if candidate_id == seed_id:
            continue
        status = str(candidate.get("status_site", "unknown")).lower()
        if status_filter and status not in status_filter:
            continue
        score, rationale = similarity_score(seed, candidate, ignored_reference_keys=common_refs)
        if score <= 0:
            continue
        items.append(
            {
                "problem_id": candidate_id,
                "number": int(candidate["number"]),
                "status_site": candidate.get("status_site", "unknown"),
                "url": candidate.get("url", ""),
                "tags": candidate.get("tags", []),
                "statement_present": bool(candidate.get("statement_raw") or candidate.get("statement_latex")),
                "similarity_score": score,
                "rationale": rationale,
                "recommended_next_action": score_problem(candidate)["recommended_next_action"],
            }
        )

    items.sort(key=lambda item: (-item["similarity_score"], item["number"]))
    items = items[:limit]
    result = {
        "generated_at": date.today().isoformat(),
        "seed_problem_id": seed_id,
        "seed_status": seed.get("status_site", "unknown"),
        "seed_url": seed.get("url", ""),
        "status_filter": sorted(status_filter) if status_filter else [],
        "ignored_reference_keys": sorted(common_refs),
        "returned": len(items),
        "items": items,
    }
    write_json(root / "reports" / "analogies" / f"{seed_id}.json", result)
    return result


def record_literature_finding(
    root: Path,
    *,
    problem_id: str | int,
    paper_key: str,
    title: str,
    url: str = "",
    summary: str = "",
    method_tags: list[str] | None = None,
    examples: list[str] | None = None,
    relevance: int = 3,
) -> dict[str, Any]:
    normalized_problem_id = normalize_problem_id(problem_id)
    finding_id = slugify(f"{normalized_problem_id}-{paper_key}")[:80]
    payload = {
        "finding_id": finding_id,
        "problem_id": normalized_problem_id,
        "paper_key": paper_key,
        "title": title,
        "url": url,
        "summary": summary,
        "method_tags": method_tags or [],
        "examples": examples or [],
        "relevance": relevance,
        "status": "unreviewed",
        "created_at": date.today().isoformat(),
    }
    write_json(root / "reports" / "literature" / "findings" / f"{finding_id}.json", payload)
    append_log(root, f"literature_finding | {finding_id} | {title}")
    write_finding_wiki_page(root, payload)
    return payload


def write_finding_wiki_page(root: Path, finding: dict[str, Any]) -> None:
    examples_text = "\n".join(f"- {example}" for example in finding.get("examples", [])) or "- TODO"
    tags_text = ", ".join(finding.get("method_tags", [])) or "none"
    content = f"""# {finding['paper_key']}: {finding['title']}

Problem: [[{finding['problem_id']}]]

URL: {finding.get('url') or 'TODO'}

Method tags: {tags_text}

## Summary

{finding.get('summary') or 'TODO'}

## Examples

{examples_text}

## Pivot Notes

TODO: identify which open problems may admit the same method, construction, obstruction, or computation.
"""
    write_text(root / "kb" / "wiki" / "papers" / f"{finding['finding_id']}.md", content)
    update_kb_index(root, f"papers/{finding['finding_id']}.md", finding["title"])


def pivot_from_literature_finding(
    root: Path,
    finding_id: str,
    *,
    status_filter: set[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    finding_path = root / "reports" / "literature" / "findings" / f"{finding_id}.json"
    if not finding_path.exists():
        raise FileNotFoundError(f"No literature finding found at {finding_path}")
    finding = read_json(finding_path)
    source_problem_id = finding.get("problem_id")
    items = pivot_items_for_finding(root, finding, status_filter=status_filter, limit=limit)
    result = {
        "generated_at": date.today().isoformat(),
        "finding_id": finding_id,
        "source_problem_id": source_problem_id,
        "paper_key": finding.get("paper_key", ""),
        "title": finding.get("title", ""),
        "status_filter": sorted(status_filter) if status_filter else [],
        "returned": len(items),
        "items": items,
    }
    write_json(root / "reports" / "pivots" / f"{finding_id}.json", result)
    append_log(root, f"pivot_from_finding | {finding_id} | returned={len(items)}")
    return result


def pivot_items_for_finding(
    root: Path,
    finding: dict[str, Any],
    *,
    status_filter: set[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    source_problem_id = finding.get("problem_id")
    items: list[dict[str, Any]] = []
    query_tokens = math_tokens(" ".join([
        finding.get("title", ""),
        finding.get("summary", ""),
        " ".join(finding.get("method_tags", [])),
        " ".join(finding.get("examples", [])),
    ]))
    method_tags = {str(tag).lower() for tag in finding.get("method_tags", [])}

    for path in list_problem_paths(root):
        problem = read_json(path)
        problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
        if problem_id == source_problem_id:
            continue
        status = str(problem.get("status_site", "unknown")).lower()
        if status_filter and status not in status_filter:
            continue

        problem_tokens = math_tokens(problem_search_text(problem))
        shared_tokens = sorted(query_tokens & problem_tokens)
        problem_tags = {str(tag).lower() for tag in problem.get("tags", [])}
        shared_tags = sorted(method_tags & problem_tags)
        score = min(24, 2 * len(shared_tokens)) + 5 * len(shared_tags)
        if score <= 0:
            continue
        rationale = []
        if shared_tags:
            rationale.append(f"method tags match problem tags: {', '.join(shared_tags)}")
        if shared_tokens:
            rationale.append(f"finding/problem shared terms: {', '.join(shared_tokens[:12])}")
        items.append(
            {
                "problem_id": problem_id,
                "number": int(problem["number"]),
                "status_site": problem.get("status_site", "unknown"),
                "url": problem.get("url", ""),
                "tags": problem.get("tags", []),
                "pivot_score": score,
                "recommended_next_action": score_problem(problem)["recommended_next_action"],
                "rationale": rationale,
            }
        )

    items.sort(key=lambda item: (-item["pivot_score"], item["number"]))
    return items[:limit]


def promote_literature_search_result(
    root: Path,
    problem_id: str | int,
    *,
    result_index: int = 1,
    status_filter: set[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    normalized_problem_id = normalize_problem_id(problem_id)
    search_path = root / "reports" / "literature" / "search" / f"{normalized_problem_id}.json"
    if not search_path.exists():
        raise FileNotFoundError(f"No literature search results found at {search_path}")

    search_payload = read_json(search_path)
    results = search_payload.get("results", [])
    if result_index < 1 or result_index > len(results):
        raise IndexError(f"Result index {result_index} is outside 1..{len(results)}")

    problem = load_problem(root, normalized_problem_id)
    result = results[result_index - 1]
    paper_key = paper_key_from_search_result(result, result_index=result_index)
    finding = record_literature_finding(
        root,
        problem_id=normalized_problem_id,
        paper_key=paper_key,
        title=result.get("title") or f"Search result {result_index}",
        url=result.get("url", ""),
        summary=finding_summary_from_search_result(search_payload, result, result_index=result_index),
        method_tags=method_tags_from_search_result(problem, result),
        examples=[],
        relevance=int(result.get("relevance_score") or 3),
    )
    pivot = pivot_from_literature_finding(
        root,
        finding["finding_id"],
        status_filter=status_filter,
        limit=limit,
    )
    promotion = {
        "generated_at": date.today().isoformat(),
        "problem_id": normalized_problem_id,
        "search_path": str(search_path.relative_to(root)),
        "result_index": result_index,
        "finding_id": finding["finding_id"],
        "finding_path": f"reports/literature/findings/{finding['finding_id']}.json",
        "pivot_path": f"reports/pivots/{finding['finding_id']}.json",
        "pivot_returned": pivot["returned"],
        "top_pivots": pivot["items"][:5],
        "status": "needs_human_review",
    }
    promotion_path = root / "reports" / "literature" / "promotions" / f"{normalized_problem_id}-r{result_index:03d}.json"
    write_json(promotion_path, promotion)
    append_log(root, f"promote_search_result | {normalized_problem_id} | r{result_index:03d} | {finding['finding_id']}")
    return {
        "finding": finding,
        "pivot": pivot,
        "promotion": promotion,
        "artifacts": [
            promotion["finding_path"],
            promotion["pivot_path"],
            str(promotion_path.relative_to(root)),
        ],
    }


def paper_key_from_search_result(result: dict[str, Any], *, result_index: int) -> str:
    identifier = normalize_space(result.get("identifier", ""))
    if identifier:
        return f"{result.get('source', 'result')}-{slugify(identifier)[:40]}"
    title = normalize_space(result.get("title", ""))
    if title:
        return f"{result.get('source', 'result')}-{slugify(title)[:40]}"
    return f"{result.get('source', 'result')}-r{result_index:03d}"


def finding_summary_from_search_result(
    search_payload: dict[str, Any],
    result: dict[str, Any],
    *,
    result_index: int,
) -> str:
    parts = [
        f"Promoted from literature search result R{result_index:03d}.",
        f"Source: {result.get('source', 'unknown')}.",
    ]
    if result.get("year"):
        parts.append(f"Year: {result['year']}.")
    if result.get("venue"):
        parts.append(f"Venue: {result['venue']}.")
    if result.get("relevance_terms"):
        parts.append(f"Relevance terms: {', '.join(result['relevance_terms'])}.")
    if search_payload.get("queries"):
        parts.append(f"Search queries: {'; '.join(search_payload['queries'])}.")
    if result.get("abstract_snippet"):
        parts.append(f"Abstract snippet: {result['abstract_snippet']}")
    return " ".join(parts)


def method_tags_from_search_result(problem: dict[str, Any], result: dict[str, Any]) -> list[str]:
    tags = []
    tags.extend(str(tag).lower() for tag in problem.get("tags", []))
    tags.extend(str(term).lower() for term in result.get("relevance_terms", []))
    tags.extend(str(category).lower() for category in result.get("categories", []))
    return dedupe_strings([tag for tag in tags if tag])


def build_promotion_candidate_report(
    root: Path,
    *,
    limit: int = 20,
    min_score: int = 1,
    include_promoted: bool = False,
    include_decided: bool = False,
) -> dict[str, Any]:
    raw_candidates: list[dict[str, Any]] = []
    decision_index = promotion_candidate_decision_index(root)
    for search_path in sorted((root / "reports" / "literature" / "search").glob("ep*.json")):
        search_payload = read_json(search_path)
        problem_id = normalize_problem_id(search_payload.get("problem_id", search_path.stem))
        queries = search_payload.get("queries", [])
        for index, result in enumerate(search_payload.get("results", []), start=1):
            candidate = promotion_candidate_from_search_result(
                root,
                search_path=search_path,
                problem_id=problem_id,
                queries=queries,
                result=result,
                result_index=index,
            )
            candidate_id = candidate["candidate_id"]
            promotion_path = root / candidate["promotion_path"]
            already_promoted = promotion_path.exists()
            if already_promoted and not include_promoted:
                continue
            decision = find_promotion_candidate_decision(candidate, decision_index)
            if decision is not None and not include_decided:
                continue
            candidate["status"] = "already_promoted" if already_promoted else "candidate"
            if decision is not None:
                candidate["status"] = decision["decision"]
                candidate["decision"] = decision
            review_score = int(candidate["review_score"])
            if review_score < min_score:
                continue
            raw_candidates.append(
                candidate
            )

    candidates = dedupe_promotion_candidates(raw_candidates)
    candidates.sort(key=lambda item: (-item["review_score"], item["problem_id"], item["result_index"]))
    deduped_candidate_count = len(candidates)
    candidates = candidates[:limit]
    report = {
        "generated_at": date.today().isoformat(),
        "min_score": min_score,
        "include_promoted": include_promoted,
        "include_decided": include_decided,
        "raw_candidate_count": len(raw_candidates),
        "deduped_candidate_count": deduped_candidate_count,
        "returned": len(candidates),
        "items": candidates,
    }
    json_path = root / "reports" / "literature" / "review" / "promotion_candidates.json"
    md_path = root / "reports" / "literature" / "review" / "promotion_candidates.md"
    write_json(json_path, report)
    write_text(md_path, render_promotion_candidate_report(report))
    append_log(root, f"promotion_candidate_report | returned={len(candidates)} | min_score={min_score}")
    return report


def promotion_candidate_from_search_result(
    root: Path,
    *,
    search_path: Path,
    problem_id: str,
    queries: list[str],
    result: dict[str, Any],
    result_index: int,
) -> dict[str, Any]:
    candidate_id = f"{problem_id}-r{result_index:03d}"
    promotion_path = root / "reports" / "literature" / "promotions" / f"{candidate_id}.json"
    dedupe_keys = literature_result_dedupe_keys(result)
    problem = read_problem_if_available(root, problem_id)
    risk_flags = promotion_candidate_risk_flags(problem, result)
    risk_penalty = promotion_candidate_risk_penalty(risk_flags)
    base_review_score = promotion_review_score(result)
    return {
        "candidate_id": candidate_id,
        "problem_id": problem_id,
        "result_index": result_index,
        "review_score": max(0, base_review_score - risk_penalty),
        "base_review_score": base_review_score,
        "risk_penalty": risk_penalty,
        "risk_flags": risk_flags,
        "relevance_score": int(result.get("relevance_score") or 0),
        "source": result.get("source", ""),
        "title": result.get("title", ""),
        "year": result.get("year", ""),
        "identifier": result.get("identifier", ""),
        "url": result.get("url", ""),
        "venue": result.get("venue", ""),
        "relevance_terms": result.get("relevance_terms", []),
        "queries": queries,
        "abstract_snippet": result.get("abstract_snippet", ""),
        "search_path": str(search_path.relative_to(root)),
        "promotion_path": str(promotion_path.relative_to(root)),
        "status": "already_promoted" if promotion_path.exists() else "candidate",
        "review_command": f"python3 -m erdos_agent review-promotion-candidate {candidate_id}",
        "approve_command": f"python3 -m erdos_agent approve-promotion-candidate {candidate_id} --reviewer YOUR_NAME --note \"brief reason\"",
        "dedupe_key": dedupe_keys[0] if dedupe_keys else f"candidate:{candidate_id}",
        "_dedupe_keys": dedupe_keys,
    }


def read_problem_if_available(root: Path, problem_id: str | int) -> dict[str, Any]:
    path = problem_path(root, problem_id)
    if not path.exists():
        return {}
    return read_json(path)


def promotion_review_score(result: dict[str, Any]) -> int:
    relevance_score = int(result.get("relevance_score") or 0)
    term_bonus = min(3, len(result.get("relevance_terms", [])) // 2)
    abstract_bonus = 1 if result.get("abstract_snippet") else 0
    identifier_bonus = 1 if result.get("identifier") else 0
    return relevance_score + term_bonus + abstract_bonus + identifier_bonus


def promotion_candidate_risk_flags(problem: dict[str, Any], result: dict[str, Any]) -> list[str]:
    result_text = " ".join(
        str(part)
        for part in [
            result.get("title", ""),
            result.get("abstract_snippet", ""),
            result.get("venue", ""),
            " ".join(str(item) for item in result.get("categories", [])),
        ]
    ).lower()
    problem_text = problem_search_text(problem).lower() if problem else ""
    flags: list[str] = []

    additive_sidon_problem = (
        "sidon" in problem_text
        and "multiplicative" not in problem_text
        and (
            "additive" in problem_text
            or "difference" in problem_text
            or "a-a" in problem_text
            or "sum" in problem_text
        )
    )
    if additive_sidon_problem and "multiplicative" in result_text and "sidon" in result_text:
        flags.append("context_mismatch_multiplicative_sidon")
    if additive_sidon_problem and "completely sidon" in result_text and "operator" not in problem_text:
        flags.append("context_mismatch_completely_sidon")
    if additive_sidon_problem and ("algebraic geometry" in result_text or "jacobian" in result_text):
        flags.append("context_mismatch_algebraic_geometry_sidon")
    if "withdrawn" in result_text:
        flags.append("source_risk_withdrawn")
    return dedupe_strings(flags)


def promotion_candidate_risk_penalty(flags: list[str]) -> int:
    penalties = {
        "context_mismatch_multiplicative_sidon": 8,
        "context_mismatch_completely_sidon": 6,
        "context_mismatch_algebraic_geometry_sidon": 4,
        "source_risk_withdrawn": 10,
    }
    return sum(penalties.get(flag, 0) for flag in flags)


def dedupe_promotion_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    deduped: list[dict[str, Any]] = []
    ranked = sorted(candidates, key=lambda item: (-item["review_score"], item["problem_id"], item["result_index"]))

    for candidate in ranked:
        keys = candidate.get("_dedupe_keys") or [candidate.get("dedupe_key", "")]
        keys = [str(key) for key in keys if key]
        duplicate_index = next((seen[key] for key in keys if key in seen), None)
        if duplicate_index is None:
            cleaned = dict(candidate)
            cleaned.pop("_dedupe_keys", None)
            cleaned["duplicate_count"] = 0
            cleaned["related_candidates"] = []
            cleaned["related_problem_ids"] = [cleaned["problem_id"]]
            cleaned["all_sources"] = dedupe_strings([cleaned.get("source", "")])
            cleaned["all_identifiers"] = dedupe_strings([cleaned.get("identifier", "")])
            cleaned["all_urls"] = dedupe_strings([cleaned.get("url", "")])
            deduped.append(cleaned)
            current_index = len(deduped) - 1
            for key in keys:
                seen[key] = current_index
            continue

        representative = deduped[duplicate_index]
        representative["duplicate_count"] = int(representative.get("duplicate_count", 0)) + 1
        representative["related_candidates"].append(promotion_candidate_reference(candidate))
        representative["related_problem_ids"] = dedupe_strings(
            representative.get("related_problem_ids", []) + [candidate["problem_id"]]
        )
        representative["all_sources"] = dedupe_strings(
            representative.get("all_sources", []) + [candidate.get("source", "")]
        )
        representative["all_identifiers"] = dedupe_strings(
            representative.get("all_identifiers", []) + [candidate.get("identifier", "")]
        )
        representative["all_urls"] = dedupe_strings(
            representative.get("all_urls", []) + [candidate.get("url", "")]
        )
        for key in keys:
            seen[key] = duplicate_index

    return deduped


def promotion_candidate_reference(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "problem_id": candidate.get("problem_id"),
        "result_index": candidate.get("result_index"),
        "review_score": candidate.get("review_score"),
        "source": candidate.get("source", ""),
        "identifier": candidate.get("identifier", ""),
        "search_path": candidate.get("search_path", ""),
        "review_command": candidate.get("review_command", ""),
        "approve_command": candidate.get("approve_command", ""),
    }


def render_promotion_candidate_report(report: dict[str, Any]) -> str:
    lines = [
        "# Promotion Candidate Review",
        "",
        f"Generated: {report['generated_at']}",
        f"Returned: {report['returned']}",
        f"Raw candidates: {report.get('raw_candidate_count', report['returned'])}",
        f"After dedupe: {report.get('deduped_candidate_count', report['returned'])}",
        "",
        "These are source-aware Supervisor candidates. Review before promotion.",
        "",
    ]
    for item in report.get("items", []):
        lines.extend(
            [
                f"## {item['candidate_id']}",
                "",
                f"- status: {item['status']}",
                f"- problem: {item['problem_id']}",
                f"- result index: {item['result_index']}",
                f"- review score: {item['review_score']}",
                f"- base review score: {item.get('base_review_score', item['review_score'])}",
                f"- risk penalty: {item.get('risk_penalty', 0)}",
                f"- risk flags: {', '.join(item.get('risk_flags', [])) or 'none'}",
                f"- source: {item['source']}",
                f"- year: {item['year']}",
                f"- title: {item['title'] or 'Untitled'}",
                f"- id: {item['identifier']}",
                f"- url: {item['url']}",
                f"- relevance terms: {', '.join(item.get('relevance_terms', []))}",
                f"- duplicate matches folded in: {item.get('duplicate_count', 0)}",
                f"- related problems: {', '.join(item.get('related_problem_ids', []))}",
                f"- review packet: `{item.get('review_command', '')}`",
                f"- approve: `{item['approve_command']}`",
                "",
            ]
        )
        for related in item.get("related_candidates", []):
            lines.append(
                f"- related candidate: {related['candidate_id']} "
                f"({related['problem_id']}, score {related['review_score']}, {related['source']}): "
                f"`{related.get('review_command') or ('python3 -m erdos_agent review-promotion-candidate ' + related['candidate_id'])}`"
            )
        if item.get("related_candidates"):
            lines.append("")
        if item.get("abstract_snippet"):
            lines.extend([item["abstract_snippet"], ""])
    return "\n".join(lines).rstrip() + "\n"


def load_promotion_candidate(root: Path, candidate_id: str) -> dict[str, Any]:
    report_path = root / "reports" / "literature" / "review" / "promotion_candidates.json"
    if not report_path.exists():
        raise FileNotFoundError("No promotion candidate report found; run review-search-results first.")
    report = read_json(report_path)
    candidate = next((item for item in report.get("items", []) if item.get("candidate_id") == candidate_id), None)
    if candidate is not None:
        return candidate

    for item in report.get("items", []):
        related = next(
            (related_item for related_item in item.get("related_candidates", []) if related_item.get("candidate_id") == candidate_id),
            None,
        )
        if related is not None:
            return load_promotion_candidate_from_search_path(root, related)

    raise ValueError(f"Candidate {candidate_id!r} was not found in {report_path}")


def load_promotion_candidate_from_search_path(root: Path, related: dict[str, Any]) -> dict[str, Any]:
    search_path = root / related["search_path"]
    search_payload = read_json(search_path)
    problem_id = normalize_problem_id(search_payload.get("problem_id", search_path.stem))
    result_index = int(related["result_index"])
    results = search_payload.get("results", [])
    if result_index < 1 or result_index > len(results):
        raise IndexError(f"Result index {result_index} is outside 1..{len(results)} for {search_path}")
    candidate = promotion_candidate_from_search_result(
        root,
        search_path=search_path,
        problem_id=problem_id,
        queries=search_payload.get("queries", []),
        result=results[result_index - 1],
        result_index=result_index,
    )
    candidate.pop("_dedupe_keys", None)
    candidate["folded_under"] = related.get("folded_under", "")
    return candidate


def read_promotion_candidate_decision(root: Path, candidate_id: str) -> dict[str, Any] | None:
    path = root / "reports" / "literature" / "review" / "decisions" / f"{candidate_id}.json"
    if not path.exists():
        return None
    return read_json(path)


def promotion_candidate_decision_index(root: Path) -> dict[str, Any]:
    decisions = []
    keys: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "reports" / "literature" / "review" / "decisions").glob("*.json")):
        decision = read_json(path)
        decisions.append(decision)
        for key in decision_match_keys(decision.get("candidate_snapshot", {})):
            keys[key] = decision
    return {
        "decisions": decisions,
        "keys": keys,
    }


def find_promotion_candidate_decision(candidate: dict[str, Any], decision_index: dict[str, Any]) -> dict[str, Any] | None:
    key_index = decision_index.get("keys", {})
    for key in decision_match_keys(candidate):
        if key in key_index:
            return key_index[key]
    return None


def decision_match_keys(candidate: dict[str, Any]) -> list[str]:
    keys = []
    keys.extend(str(key) for key in candidate.get("_dedupe_keys", []) if key)
    if candidate.get("dedupe_key"):
        keys.append(str(candidate["dedupe_key"]))
    keys.extend(literature_result_dedupe_keys(candidate))
    return dedupe_strings([key for key in keys if key])


def record_promotion_candidate_decision(
    root: Path,
    candidate_id: str,
    *,
    decision: str,
    reviewer: str = "",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    if decision not in {"rejected", "deferred", "needs_more_reading"}:
        raise ValueError("decision must be one of: rejected, deferred, needs_more_reading")
    candidate = load_promotion_candidate(root, candidate_id)
    payload = {
        "generated_at": date.today().isoformat(),
        "candidate_id": candidate_id,
        "decision": decision,
        "reviewer": reviewer,
        "notes": notes or [],
        "candidate_snapshot": candidate,
    }
    path = root / "reports" / "literature" / "review" / "decisions" / f"{candidate_id}.json"
    write_json(path, payload)
    append_log(root, f"promotion_candidate_decision | {candidate_id} | decision={decision}")
    return {
        "decision": payload,
        "artifacts": [str(path.relative_to(root))],
    }


def build_promotion_candidate_packet(root: Path, candidate_id: str) -> dict[str, Any]:
    candidate = load_promotion_candidate(root, candidate_id)
    packet = {
        "generated_at": date.today().isoformat(),
        "candidate_id": candidate_id,
        "candidate": candidate,
        "review_checks": [
            "Open the source URL/DOI/arXiv page and confirm the title, authors, and venue.",
            "Read enough of the abstract or paper to decide whether the match is mathematical, not only keyword overlap.",
            "Compare the result with the local problem statement and note whether it is a solution, partial result, method, or false lead.",
            "Check whether related folded candidates point to the same paper or to nearby variants.",
            "Only approve if a human reviewer is comfortable recording this as an unreviewed finding for pivoting.",
        ],
        "suggested_commands": {
            "preview": f"python3 -m erdos_agent preview-promotion-candidate {candidate_id} --queue-limit 3 --queue-min-score 10",
            "approve_only": f"python3 -m erdos_agent approve-promotion-candidate {candidate_id} --reviewer YOUR_NAME --note \"brief reason\"",
            "approve_and_queue": f"python3 -m erdos_agent approve-promotion-candidate {candidate_id} --reviewer YOUR_NAME --note \"brief reason\" --queue-pivots --queue-limit 3 --queue-min-score 10",
        },
        "safety_notes": [
            "This packet is source-aware and must not be passed to Blind Solver.",
            "Approval records a useful literature finding; it is not a novelty claim.",
            "External posting remains a separate human-only action.",
        ],
    }
    json_path = root / "reports" / "literature" / "review" / "packets" / f"{candidate_id}.json"
    md_path = root / "reports" / "literature" / "review" / "packets" / f"{candidate_id}.md"
    write_json(json_path, packet)
    write_text(md_path, render_promotion_candidate_packet(packet))
    append_log(root, f"promotion_candidate_packet | {candidate_id}")
    return {
        "packet": packet,
        "artifacts": [str(json_path.relative_to(root)), str(md_path.relative_to(root))],
    }


def render_promotion_candidate_packet(packet: dict[str, Any]) -> str:
    candidate = packet["candidate"]
    lines = [
        f"# Promotion Candidate Packet: {packet['candidate_id']}",
        "",
        f"Generated: {packet['generated_at']}",
        "",
        "This is a source-aware human review packet. Do not pass it to Blind Solver.",
        "",
        "## Candidate",
        "",
        f"- status: {candidate.get('status', '')}",
        f"- problem: {candidate.get('problem_id', '')}",
        f"- result index: {candidate.get('result_index', '')}",
        f"- review score: {candidate.get('review_score', '')}",
        f"- base review score: {candidate.get('base_review_score', candidate.get('review_score', ''))}",
        f"- risk penalty: {candidate.get('risk_penalty', 0)}",
        f"- risk flags: {', '.join(candidate.get('risk_flags', [])) or 'none'}",
        f"- source: {candidate.get('source', '')}",
        f"- year: {candidate.get('year', '')}",
        f"- title: {candidate.get('title') or 'Untitled'}",
        f"- id: {candidate.get('identifier', '')}",
        f"- url: {candidate.get('url', '')}",
        f"- venue: {candidate.get('venue', '')}",
        f"- relevance terms: {', '.join(candidate.get('relevance_terms', []))}",
        f"- search artifact: {candidate.get('search_path', '')}",
        "",
    ]
    if candidate.get("queries"):
        lines.extend(["## Search Queries", ""])
        lines.extend(f"- {query}" for query in candidate["queries"])
        lines.append("")
    if candidate.get("related_candidates"):
        lines.extend(["## Folded Related Candidates", ""])
        for related in candidate["related_candidates"]:
            lines.append(
                f"- {related['candidate_id']} ({related['problem_id']}, score {related['review_score']}, "
                f"{related['source']}): `{related.get('review_command') or ('python3 -m erdos_agent review-promotion-candidate ' + related['candidate_id'])}`"
            )
        lines.append("")
    if candidate.get("abstract_snippet"):
        lines.extend(["## Abstract Snippet", "", candidate["abstract_snippet"], ""])
    lines.extend(["## Human Review Checklist", ""])
    lines.extend(f"- [ ] {check}" for check in packet["review_checks"])
    lines.extend(["", "## Suggested Commands", ""])
    lines.append(f"- preview: `{packet['suggested_commands']['preview']}`")
    lines.append(f"- approve only: `{packet['suggested_commands']['approve_only']}`")
    lines.append(f"- approve and queue: `{packet['suggested_commands']['approve_and_queue']}`")
    lines.extend(["", "## Safety Notes", ""])
    lines.extend(f"- {note}" for note in packet["safety_notes"])
    return "\n".join(lines).rstrip() + "\n"


def preview_promotion_candidate(
    root: Path,
    candidate_id: str,
    *,
    status_filter: set[str] | None = None,
    pivot_limit: int = 20,
    queue_limit: int = 3,
    queue_min_score: int = 10,
    agent: str = "auto",
) -> dict[str, Any]:
    candidate = load_promotion_candidate(root, candidate_id)
    finding = promotion_candidate_finding_preview(root, candidate)
    pivot_items = pivot_items_for_finding(root, finding, status_filter=status_filter, limit=pivot_limit)
    queue_preview = preview_runs_from_pivot_items(
        root,
        finding_id=finding["finding_id"],
        pivot_items=pivot_items,
        agent=agent,
        limit=queue_limit,
        min_score=queue_min_score,
    )
    preview = {
        "generated_at": date.today().isoformat(),
        "candidate_id": candidate_id,
        "status": "preview_only",
        "writes": {
            "creates_literature_finding": False,
            "creates_pivot_report": False,
            "creates_agent_runs": False,
            "posts_externally": False,
        },
        "candidate": candidate,
        "finding_preview": finding,
        "pivot_preview": {
            "source_problem_id": finding["problem_id"],
            "status_filter": sorted(status_filter) if status_filter else [],
            "returned": len(pivot_items),
            "items": pivot_items,
        },
        "queue_preview": {
            "agent": agent,
            "queue_limit": queue_limit,
            "queue_min_score": queue_min_score,
            "returned": len(queue_preview),
            "items": queue_preview,
        },
        "approval_command": (
            f"python3 -m erdos_agent approve-promotion-candidate {candidate_id} "
            f"--reviewer YOUR_NAME --note \"brief reason\" --queue-pivots "
            f"--queue-limit {queue_limit} --queue-min-score {queue_min_score}"
        ),
    }
    json_path = root / "reports" / "literature" / "review" / "previews" / f"{candidate_id}.json"
    md_path = root / "reports" / "literature" / "review" / "previews" / f"{candidate_id}.md"
    write_json(json_path, preview)
    write_text(md_path, render_promotion_candidate_preview(preview))
    return {
        "preview": preview,
        "artifacts": [str(json_path.relative_to(root)), str(md_path.relative_to(root))],
    }


def promotion_candidate_finding_preview(root: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    problem_id = normalize_problem_id(candidate["problem_id"])
    problem = load_problem(root, problem_id)
    paper_key = paper_key_from_search_result(candidate, result_index=int(candidate["result_index"]))
    finding_id = slugify(f"{problem_id}-{paper_key}")[:80]
    summary_parts = [
        f"Preview from promotion candidate {candidate['candidate_id']}.",
        f"Source: {candidate.get('source', 'unknown')}.",
    ]
    if candidate.get("year"):
        summary_parts.append(f"Year: {candidate['year']}.")
    if candidate.get("venue"):
        summary_parts.append(f"Venue: {candidate['venue']}.")
    if candidate.get("relevance_terms"):
        summary_parts.append(f"Relevance terms: {', '.join(candidate['relevance_terms'])}.")
    if candidate.get("queries"):
        summary_parts.append(f"Search queries: {'; '.join(candidate['queries'])}.")
    if candidate.get("abstract_snippet"):
        summary_parts.append(f"Abstract snippet: {candidate['abstract_snippet']}")
    return {
        "finding_id": finding_id,
        "problem_id": problem_id,
        "paper_key": paper_key,
        "title": candidate.get("title") or "Untitled",
        "url": candidate.get("url", ""),
        "summary": " ".join(summary_parts),
        "method_tags": method_tags_from_search_result(problem, candidate),
        "examples": [],
        "relevance": int(candidate.get("relevance_score") or 3),
        "status": "preview_only",
        "created_at": date.today().isoformat(),
    }


def preview_runs_from_pivot_items(
    root: Path,
    *,
    finding_id: str,
    pivot_items: list[dict[str, Any]],
    agent: str = "auto",
    limit: int = 3,
    min_score: int = 10,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for item in pivot_items:
        pivot_score = int(item.get("pivot_score") or 0)
        if pivot_score < min_score:
            continue
        recommended_next_action = item.get("recommended_next_action", "")
        run_agent = agent_for_pivot_action(recommended_next_action) if agent == "auto" else agent
        artifacts = default_run_artifacts(root, run_agent, item["problem_id"])
        runs.append(
            {
                "agent": run_agent,
                "problem_id": item["problem_id"],
                "priority": 2,
                "prompt": default_run_prompt(run_agent, item["problem_id"], recommended_next_action),
                "artifacts": artifacts,
                "metadata": {
                    "source": "pivot_preview",
                    "finding_id": finding_id,
                    "pivot_score": pivot_score,
                    "recommended_next_action": recommended_next_action,
                },
            }
        )
        if len(runs) >= limit:
            break
    return runs


def render_promotion_candidate_preview(preview: dict[str, Any]) -> str:
    candidate = preview["candidate"]
    finding = preview["finding_preview"]
    pivot = preview["pivot_preview"]
    queue = preview["queue_preview"]
    lines = [
        f"# Promotion Candidate Preview: {preview['candidate_id']}",
        "",
        f"Generated: {preview['generated_at']}",
        "",
        "This is a dry-run preview. It does not create findings, pivot reports, queued runs, or external posts.",
        "",
        "## Candidate",
        "",
        f"- problem: {candidate.get('problem_id', '')}",
        f"- title: {candidate.get('title') or 'Untitled'}",
        f"- review score: {candidate.get('review_score', '')}",
        f"- risk flags: {', '.join(candidate.get('risk_flags', [])) or 'none'}",
        f"- source: {candidate.get('source', '')}",
        f"- id: {candidate.get('identifier', '')}",
        f"- url: {candidate.get('url', '')}",
        "",
        "## Would Create Finding",
        "",
        f"- finding id: {finding['finding_id']}",
        f"- paper key: {finding['paper_key']}",
        f"- method tags: {', '.join(finding.get('method_tags', [])) or 'none'}",
        "",
        "## Pivot Preview",
        "",
        f"- returned: {pivot['returned']}",
        f"- status filter: {', '.join(pivot.get('status_filter', [])) or 'none'}",
        "",
    ]
    for item in pivot.get("items", [])[:10]:
        lines.extend(
            [
                f"### {item['problem_id']}",
                "",
                f"- pivot score: {item['pivot_score']}",
                f"- next action: {item['recommended_next_action']}",
                f"- tags: {', '.join(item.get('tags', [])) or 'none'}",
                f"- rationale: {'; '.join(item.get('rationale', [])) or 'none'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Queue Preview",
            "",
            f"- returned: {queue['returned']}",
            f"- agent mode: {queue['agent']}",
            f"- min score: {queue['queue_min_score']}",
            "",
        ]
    )
    for item in queue.get("items", []):
        lines.extend(
            [
                f"- {item['problem_id']}: {item['agent']} "
                f"(score {item['metadata']['pivot_score']}, {item['metadata']['recommended_next_action']})",
            ]
        )
    if queue.get("items"):
        lines.append("")
    lines.extend(["## Approval Command", "", f"`{preview['approval_command']}`"])
    return "\n".join(lines).rstrip() + "\n"


def approve_promotion_candidate(
    root: Path,
    candidate_id: str,
    *,
    status_filter: set[str] | None = None,
    pivot_limit: int = 20,
    queue_pivots: bool = False,
    queue_limit: int = 3,
    queue_min_score: int = 10,
    agent: str = "auto",
    reviewer: str = "",
    review_notes: list[str] | None = None,
) -> dict[str, Any]:
    candidate = load_promotion_candidate(root, candidate_id)

    promotion_result = promote_literature_search_result(
        root,
        candidate["problem_id"],
        result_index=int(candidate["result_index"]),
        status_filter=status_filter,
        limit=pivot_limit,
    )
    queued_runs: list[dict[str, Any]] = []
    if queue_pivots:
        queued_runs = create_runs_from_pivot(
            root,
            promotion_result["finding"]["finding_id"],
            agent=agent,
            limit=queue_limit,
            min_score=queue_min_score,
        )
    approval = {
        "generated_at": date.today().isoformat(),
        "candidate_id": candidate_id,
        "status": "approved",
        "reviewer": reviewer,
        "review_notes": review_notes or [],
        "candidate_snapshot": candidate,
        "finding_id": promotion_result["finding"]["finding_id"],
        "promotion_artifacts": promotion_result["artifacts"],
        "queued_run_ids": [run["run_id"] for run in queued_runs],
        "queued_runs": [
            {
                "run_id": run["run_id"],
                "agent": run["agent"],
                "problem_id": run.get("problem_id"),
                "priority": run.get("priority"),
            }
            for run in queued_runs
        ],
    }
    approval_path = root / "reports" / "literature" / "review" / "approvals" / f"{candidate_id}.json"
    write_json(approval_path, approval)
    append_log(root, f"approve_promotion_candidate | {candidate_id} | finding={approval['finding_id']} | queued={len(queued_runs)}")
    return {
        "candidate": candidate,
        "promotion": promotion_result,
        "queued_runs": queued_runs,
        "approval": approval,
        "artifacts": [str(approval_path.relative_to(root)), *promotion_result["artifacts"]],
    }


def quickstart_check(
    root: Path,
    *,
    status_filter: set[str] | None = None,
    triage_limit: int = 10,
    review_limit: int = 20,
    min_review_score: int = 7,
    run_triage: bool = True,
    build_review: bool = True,
) -> dict[str, Any]:
    ensure_workspace(root)
    problem_paths = list_problem_paths(root)
    search_paths = sorted((root / "reports" / "literature" / "search").glob("ep*.json"))
    checks: list[dict[str, Any]] = []
    artifacts: list[str] = []

    checks.append(
        {
            "name": "local_problem_data",
            "status": "ok" if problem_paths else "warn",
            "detail": f"{len(problem_paths)} local problem files found.",
            "next_action": "Run ingest-github with a small limit." if not problem_paths else "",
        }
    )

    triage_summary: dict[str, Any] = {
        "ran": False,
        "available": False,
        "path": "reports/triage/index.json",
        "returned": 0,
        "considered": 0,
    }
    if run_triage and problem_paths:
        triage_index = triage_all(root, status_filter=status_filter, limit=triage_limit)
        triage_summary.update(
            {
                "ran": True,
                "available": True,
                "returned": triage_index.get("returned", 0),
                "considered": triage_index.get("considered", 0),
                "top_problem_ids": [item["problem_id"] for item in triage_index.get("items", [])[:5]],
            }
        )
        artifacts.append("reports/triage/index.json")
    elif (root / "reports" / "triage" / "index.json").exists():
        triage_index = read_json(root / "reports" / "triage" / "index.json")
        triage_summary.update(
            {
                "available": True,
                "returned": triage_index.get("returned", 0),
                "considered": triage_index.get("considered", 0),
                "top_problem_ids": [item["problem_id"] for item in triage_index.get("items", [])[:5]],
            }
        )

    checks.append(
        {
            "name": "triage_index",
            "status": "ok" if triage_summary["available"] and triage_summary["returned"] else "warn",
            "detail": f"{triage_summary['returned']} ranked problems available.",
            "next_action": "Run triage-all after importing problems." if not triage_summary["available"] else "",
        }
    )

    checks.append(
        {
            "name": "literature_search_results",
            "status": "ok" if search_paths else "warn",
            "detail": f"{len(search_paths)} literature search result files found.",
            "next_action": "Run Literature Agent jobs or literature-search." if not search_paths else "",
        }
    )

    review_summary: dict[str, Any] = {
        "ran": False,
        "available": False,
        "path": "reports/literature/review/promotion_candidates.json",
        "candidate_count": 0,
    }
    if build_review and search_paths:
        review_report = build_promotion_candidate_report(root, limit=review_limit, min_score=min_review_score)
        review_summary.update(
            {
                "ran": True,
                "available": True,
                "candidate_count": review_report.get("returned", 0),
                "top_candidate_ids": [item["candidate_id"] for item in review_report.get("items", [])[:5]],
            }
        )
        artifacts.extend(
            [
                "reports/literature/review/promotion_candidates.json",
                "reports/literature/review/promotion_candidates.md",
            ]
        )
    elif (root / "reports" / "literature" / "review" / "promotion_candidates.json").exists():
        review_report = read_json(root / "reports" / "literature" / "review" / "promotion_candidates.json")
        review_summary.update(
            {
                "available": True,
                "candidate_count": review_report.get("returned", 0),
                "top_candidate_ids": [item["candidate_id"] for item in review_report.get("items", [])[:5]],
            }
        )

    checks.append(
        {
            "name": "review_candidates",
            "status": "ok" if review_summary["available"] else "warn",
            "detail": f"{review_summary['candidate_count']} review candidates available.",
            "next_action": "Run review-search-results after Literature Agent search results exist." if not review_summary["available"] else "",
        }
    )

    supervisor = supervisor_step(root, limit=5)
    artifacts.append("agent_runs/supervisor_step.json")
    report = {
        "generated_at": date.today().isoformat(),
        "safe": True,
        "side_effects": [
            "may write reports/triage/index.json",
            "may write reports/literature/review/promotion_candidates.*",
            "writes agent_runs/supervisor_step.json",
            "does not approve candidates",
            "does not post externally",
        ],
        "problem_count": len(problem_paths),
        "search_result_count": len(search_paths),
        "triage": triage_summary,
        "review": review_summary,
        "supervisor": {
            "queued_count": supervisor.get("queued_count", 0),
            "completed_count": supervisor.get("completed_count", 0),
            "review_candidates": supervisor.get("review_candidates", {}),
        },
        "checks": checks,
        "artifacts": dedupe_strings(artifacts),
    }
    write_json(root / "reports" / "quickstart" / "check.json", report)
    write_text(root / "reports" / "quickstart" / "check.md", render_quickstart_check(report))
    return report


def render_quickstart_check(report: dict[str, Any]) -> str:
    lines = [
        "# Quickstart Check",
        "",
        f"Generated: {report['generated_at']}",
        f"Safe: {report['safe']}",
        "",
        "## Checks",
        "",
    ]
    for check in report.get("checks", []):
        lines.append(f"- {check['status']}: {check['name']} - {check['detail']}")
        if check.get("next_action"):
            lines.append(f"  next: {check['next_action']}")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- local problems: {report.get('problem_count', 0)}",
            f"- search result files: {report.get('search_result_count', 0)}",
            f"- triage returned: {report.get('triage', {}).get('returned', 0)}",
            f"- review candidates: {report.get('review', {}).get('candidate_count', 0)}",
            f"- queued runs: {report.get('supervisor', {}).get('queued_count', 0)}",
            "",
            "## Artifacts",
            "",
        ]
    )
    lines.extend(f"- {artifact}" for artifact in report.get("artifacts", []))
    lines.extend(["", "## Safety", ""])
    lines.extend(f"- {item}" for item in report.get("side_effects", []))
    return "\n".join(lines).rstrip() + "\n"


def record_math_example(
    root: Path,
    *,
    example_id: str,
    statement: str,
    source: str = "",
    problem_id: str | int | None = None,
    tags: list[str] | None = None,
    role: str = "example",
) -> dict[str, Any]:
    normalized_id = slugify(example_id)
    payload = {
        "example_id": normalized_id,
        "problem_id": normalize_problem_id(problem_id) if problem_id is not None else None,
        "source": source,
        "role": role,
        "tags": tags or [],
        "statement": statement,
        "created_at": date.today().isoformat(),
    }
    write_json(root / "kb" / "examples" / f"{normalized_id}.json", payload)
    content = f"""# Example: {normalized_id}

Role: {role}

Problem: {payload['problem_id'] or 'none'}

Source: {source or 'TODO'}

Tags: {', '.join(tags or []) or 'none'}

## Statement

{statement}

## Reuse Notes

TODO: explain which methods, conjectures, or counterexample searches this example should inform.
"""
    write_text(root / "kb" / "examples" / f"{normalized_id}.md", content)
    update_kb_index(root, f"examples/{normalized_id}.md", f"Example: {normalized_id}")
    append_log(root, f"example | {normalized_id} | {role}")
    return payload


def append_log(root: Path, entry: str) -> None:
    log_path = root / "kb" / "log.md"
    ensure_seed_file(log_path, "# Knowledge Base Log\n\n")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"## [{date.today().isoformat()}] {entry}\n\n")


def update_kb_index(root: Path, relative_path: str, summary: str) -> None:
    index_path = root / "kb" / "index.md"
    ensure_seed_file(index_path, "# Knowledge Base Index\n\n")
    existing = index_path.read_text(encoding="utf-8")
    line = f"- [[{relative_path}]] - {summary}\n"
    if line not in existing:
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "item"


RUN_STATUSES = {"queued", "done", "blocked", "needs_human", "cancelled"}
AGENT_KINDS = {"literature", "blind_solver", "computation", "formalization", "critic", "statement_auditor"}


def create_agent_run(
    root: Path,
    *,
    agent: str,
    problem_id: str | int | None = None,
    prompt: str = "",
    artifacts: list[str] | None = None,
    priority: int = 3,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if agent not in AGENT_KINDS:
        raise ValueError(f"Unknown agent {agent!r}. Expected one of: {', '.join(sorted(AGENT_KINDS))}")
    normalized_problem_id = normalize_problem_id(problem_id) if problem_id is not None else None
    existing = find_existing_queued_run(root, agent=agent, problem_id=normalized_problem_id)
    if existing is not None:
        return existing
    run_id = make_run_id(agent, normalized_problem_id)
    payload = {
        "run_id": run_id,
        "agent": agent,
        "problem_id": normalized_problem_id,
        "status": "queued",
        "priority": priority,
        "prompt": prompt,
        "artifacts": artifacts or [],
        "metadata": metadata or {},
        "created_at": date.today().isoformat(),
        "updated_at": date.today().isoformat(),
    }
    write_json(agent_run_inbox_path(root, run_id), payload)
    append_log(root, f"agent_run_created | {run_id} | {agent} | {normalized_problem_id or 'none'}")
    return payload


def queue_proof_route_run(root: Path, problem_id: str | int, *, route: str = "difference-packing") -> dict[str, Any]:
    if route != "difference-packing":
        raise ValueError(f"Unsupported proof route: {route}")
    route_result = make_difference_packing_proof_route(root, problem_id)
    packet_artifacts = [artifact for artifact in route_result["artifacts"] if artifact.startswith("packets/blind/")]
    run = create_agent_run(
        root,
        agent="blind_solver",
        problem_id=route_result["problem_id"],
        prompt="Use only the attached redacted proof-route packet. Return a proof, counterexample, or gap-labeled lemma attempt.",
        artifacts=route_result["artifacts"],
        priority=1,
        metadata={
            "source": "proof_route",
            "route": route,
            "task_id": route_result["task_id"],
            "blind_packet_artifacts": packet_artifacts,
        },
    )
    return {
        "route": route_result,
        "run": run,
        "artifacts": route_result["artifacts"],
    }


def find_existing_queued_run(root: Path, *, agent: str, problem_id: str | None) -> dict[str, Any] | None:
    for path in sorted((root / "agent_runs" / "inbox").glob("*.json")):
        payload = read_json(path)
        if payload.get("status") == "queued" and payload.get("agent") == agent and payload.get("problem_id") == problem_id:
            return payload
    return None


def create_runs_from_triage(
    root: Path,
    *,
    agent: str,
    limit: int = 5,
    action_filter: set[str] | None = None,
) -> list[dict[str, Any]]:
    index_path = root / "reports" / "triage" / "index.json"
    if not index_path.exists():
        raise FileNotFoundError("reports/triage/index.json is missing; run triage-all first.")
    index = read_json(index_path)
    runs: list[dict[str, Any]] = []
    for item in index.get("items", []):
        if action_filter and item.get("recommended_next_action") not in action_filter:
            continue
        prompt = default_run_prompt(agent, item["problem_id"], item.get("recommended_next_action", ""))
        artifacts = default_run_artifacts(root, agent, item["problem_id"])
        runs.append(
            create_agent_run(
                root,
                agent=agent,
                problem_id=item["problem_id"],
                prompt=prompt,
                artifacts=artifacts,
                priority=3,
                metadata={
                    "source": "triage",
                    "priority_score": item.get("priority_score"),
                    "recommended_next_action": item.get("recommended_next_action"),
                },
            )
        )
        if len(runs) >= limit:
            break
    return runs


def create_runs_from_pivot(
    root: Path,
    finding_id: str,
    *,
    agent: str = "auto",
    limit: int = 5,
    min_score: int = 1,
) -> list[dict[str, Any]]:
    pivot_path = root / "reports" / "pivots" / f"{finding_id}.json"
    if not pivot_path.exists():
        raise FileNotFoundError(f"No pivot report found at {pivot_path}")
    pivot = read_json(pivot_path)
    runs: list[dict[str, Any]] = []
    for item in pivot.get("items", []):
        pivot_score = int(item.get("pivot_score") or 0)
        if pivot_score < min_score:
            continue
        recommended_next_action = item.get("recommended_next_action", "")
        run_agent = agent_for_pivot_action(recommended_next_action) if agent == "auto" else agent
        prompt = default_run_prompt(run_agent, item["problem_id"], recommended_next_action)
        artifacts = default_run_artifacts(root, run_agent, item["problem_id"])
        artifacts.append(str(pivot_path.relative_to(root)))
        runs.append(
            create_agent_run(
                root,
                agent=run_agent,
                problem_id=item["problem_id"],
                prompt=prompt,
                artifacts=dedupe_strings(artifacts),
                priority=2,
                metadata={
                    "source": "pivot",
                    "finding_id": finding_id,
                    "source_problem_id": pivot.get("source_problem_id"),
                    "paper_key": pivot.get("paper_key"),
                    "pivot_score": pivot_score,
                    "recommended_next_action": recommended_next_action,
                },
            )
        )
        if len(runs) >= limit:
            break
    append_log(root, f"queue_pivots | {finding_id} | created={len(runs)} | agent={agent}")
    return runs


def agent_for_pivot_action(recommended_next_action: str) -> str:
    mapping = {
        "literature_review": "literature",
        "statement_audit": "statement_auditor",
        "computation": "computation",
        "counterexample_search": "computation",
        "lean_formalization": "formalization",
        "proof_attempt": "blind_solver",
    }
    return mapping.get(recommended_next_action, "literature")


def list_agent_runs(root: Path, *, status: str | None = None) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for directory in [root / "agent_runs" / "inbox", root / "agent_runs" / "outbox"]:
        for path in sorted(directory.glob("*.json")):
            payload = read_json(path)
            if status and payload.get("status") != status:
                continue
            payload["_path"] = str(path)
            runs.append(payload)
    runs.sort(key=lambda run: (run.get("status") != "queued", run.get("priority", 999), run.get("created_at", ""), run.get("run_id", "")))
    return runs


def complete_agent_run(
    root: Path,
    run_id: str,
    *,
    status: str,
    summary: str,
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    if status not in RUN_STATUSES - {"queued"}:
        raise ValueError(f"Completion status must be one of: {', '.join(sorted(RUN_STATUSES - {'queued'}))}")
    inbox_path = agent_run_inbox_path(root, run_id)
    if not inbox_path.exists():
        raise FileNotFoundError(f"No queued run found at {inbox_path}")
    payload = read_json(inbox_path)
    payload["status"] = status
    payload["summary"] = summary
    payload["result_artifacts"] = artifacts or []
    payload["updated_at"] = date.today().isoformat()
    outbox_path = agent_run_outbox_path(root, run_id)
    write_json(outbox_path, payload)
    inbox_path.unlink()
    append_log(root, f"agent_run_completed | {run_id} | {status}")
    return payload


def execute_agent_run(root: Path, run_id: str) -> dict[str, Any]:
    inbox_path = agent_run_inbox_path(root, run_id)
    if not inbox_path.exists():
        raise FileNotFoundError(f"No queued run found at {inbox_path}")
    run = read_json(inbox_path)
    agent = run.get("agent")
    problem_id = run.get("problem_id")
    if not problem_id:
        return complete_agent_run(
            root,
            run_id,
            status="blocked",
            summary="Run has no problem_id.",
            artifacts=[],
        )

    if agent == "literature":
        result = run_literature_worker(root, problem_id)
    elif agent == "computation":
        result = run_computation_worker(root, problem_id)
    elif agent == "statement_auditor":
        result = run_statement_auditor_worker(root, problem_id)
    elif agent == "formalization":
        result = run_formalization_worker(root, problem_id)
    elif agent == "critic":
        result = run_critic_worker(root, problem_id)
    elif agent == "blind_solver":
        result = run_blind_solver_packet_worker(root, problem_id, run=run)
    else:
        result = {
            "status": "blocked",
            "summary": f"Unsupported agent: {agent}",
            "artifacts": [],
        }

    return complete_agent_run(
        root,
        run_id,
        status=result["status"],
        summary=result["summary"],
        artifacts=result["artifacts"],
    )


def execute_next_agent_run(root: Path, *, agent: str | None = None) -> dict[str, Any]:
    if agent is not None and agent not in AGENT_KINDS:
        raise ValueError(f"Unknown agent {agent!r}. Expected one of: {', '.join(sorted(AGENT_KINDS))}")
    queued = list_agent_runs(root, status="queued")
    if agent is not None:
        queued = [run for run in queued if run.get("agent") == agent]
    if not queued:
        result = {
            "status": "idle",
            "summary": "No queued agent runs.",
            "agent_filter": agent,
            "generated_at": date.today().isoformat(),
        }
        write_json(root / "agent_runs" / "last_run_next.json", result)
        return result
    result = execute_agent_run(root, queued[0]["run_id"])
    write_json(
        root / "agent_runs" / "last_run_next.json",
        {
            "status": result["status"],
            "summary": result.get("summary", ""),
            "run_id": result.get("run_id"),
            "agent": result.get("agent"),
            "problem_id": result.get("problem_id"),
            "result_artifacts": result.get("result_artifacts", []),
            "generated_at": date.today().isoformat(),
        },
    )
    return result


def run_literature_worker(root: Path, problem_id: str | int) -> dict[str, Any]:
    problem = load_problem(root, problem_id)
    normalized = problem.get("problem_id") or normalize_problem_id(problem["number"])
    content = make_literature_report(problem)
    path = root / "reports" / "literature" / f"{normalized}.md"
    write_text(path, content)
    search_result = search_literature_for_problem(root, normalized, sources=["arxiv", "crossref"], limit=3, query_limit=2)
    update_kb_index(root, f"wiki/problems/{normalized}.md", f"Problem {normalized} literature status")
    write_problem_wiki_stub(root, problem)
    artifacts = [str(path.relative_to(root))]
    artifacts.extend(search_result.get("artifacts", []))
    return {
        "status": "done",
        "summary": f"Created literature report and external search artifacts for {normalized}.",
        "artifacts": artifacts,
    }


def make_literature_report(problem: dict[str, Any]) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    references = problem.get("known_references", [])
    remarks = problem.get("remarks_raw", "")
    keywords = extract_keywords(statement, limit=16)
    reference_text = "\n".join(f"- {reference}" for reference in references) or "- No references captured locally."
    query_text = "\n".join(f"- {query}" for query in make_search_queries(problem, keywords))
    return f"""# Literature Report for {problem_id}

## Status

- site status: {problem.get('status_site', 'unknown')}
- tags: {', '.join(problem.get('tags', [])) or 'none'}
- references captured: {len(references)}
- statement source: {problem.get('statement_source', 'unknown')}

## Statement

{statement or 'TODO: fetch or add statement.'}

## Remarks Snapshot

{remarks or 'No remarks captured locally.'}

## Captured References

{reference_text}

## Search Queries

{query_text}

## Result Card Targets

- Known theorem that directly implies the statement.
- Special case or obstruction.
- Construction, counterexample, or extremal example.
- Computation-ready sequence or finite search formulation.
- Related solved problem whose method may transfer.

## Pivot Instructions

If a paper or method appears more useful for another open problem, record it with `add-finding`, then run `pivot-from-finding`.

## Novelty Risk

TODO: low / medium / high

## What Remains Open

TODO
"""


def make_search_queries(problem: dict[str, Any], keywords: list[str]) -> list[str]:
    tags = [str(tag) for tag in problem.get("tags", [])]
    hints = domain_query_hints(problem)
    base_terms = " ".join(keywords[:6])
    queries = []
    queries.extend(hints)
    if base_terms:
        queries.append(base_terms)
    if tags and base_terms:
        queries.append(f"{base_terms} {' '.join(tags[:2])}")
    for reference in problem.get("known_references", [])[:3]:
        key_match = re.match(r"^\[([^\]]+)\]\s*(.*)", str(reference))
        if key_match:
            queries.append(key_match.group(2)[:160])
    return dedupe_strings([query for query in queries if query.strip()])


def domain_query_hints(problem: dict[str, Any]) -> list[str]:
    statement = (problem.get("statement_raw") or problem.get("statement_latex") or "").lower()
    tags = " ".join(str(tag).lower() for tag in problem.get("tags", []))
    hints: list[str] = []
    if "2^" in statement and "prime" in statement:
        hints.append("prime powers of two")
    if "subset sum" in statement or "subset sums" in statement:
        hints.append("distinct subset sums")
    if "sidon" in statement or "sidon" in tags:
        hints.append("Sidon set additive combinatorics")
    if "additive basis" in tags:
        hints.append("additive basis number theory")
    if "practical" in statement:
        hints.append("practical numbers divisors")
    if "covering systems" in tags:
        hints.append("covering systems residue classes")
    return hints


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = normalize_space(value).lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(value)
    return deduped


def search_literature_for_problem(
    root: Path,
    problem_id: str | int,
    *,
    sources: list[str] | None = None,
    limit: int = 5,
    query_limit: int = 3,
    manual_queries: list[str] | None = None,
    include_generated_queries: bool = False,
) -> dict[str, Any]:
    problem = load_problem(root, problem_id)
    normalized = problem.get("problem_id") or normalize_problem_id(problem["number"])
    sources = sources if sources is not None else ["arxiv", "crossref"]
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    keywords = extract_keywords(statement, limit=16)
    generated_queries = make_search_queries(problem, keywords)[:query_limit]
    manual_queries = dedupe_strings([query for query in manual_queries or [] if query.strip()])
    if manual_queries and not include_generated_queries:
        queries = manual_queries
    else:
        queries = dedupe_strings([*manual_queries, *generated_queries])
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for query in queries:
        for source in sources:
            try:
                if source == "arxiv":
                    results.extend(search_arxiv(query, limit=limit))
                elif source == "crossref":
                    results.extend(search_crossref(query, limit=limit))
                else:
                    errors.append({"source": source, "query": query, "error": "unsupported source"})
            except Exception as exc:
                errors.append({"source": source, "query": query, "error": str(exc)})

    deduped = filter_literature_results(problem, dedupe_literature_results(results))
    payload = {
        "problem_id": normalized,
        "generated_at": date.today().isoformat(),
        "sources": sources,
        "queries": queries,
        "manual_queries": manual_queries,
        "generated_queries": generated_queries,
        "include_generated_queries": include_generated_queries,
        "result_count": len(deduped),
        "results": deduped,
        "errors": errors,
    }
    json_path = root / "reports" / "literature" / "search" / f"{normalized}.json"
    md_path = root / "reports" / "literature" / "search" / f"{normalized}.md"
    cards_path = root / "reports" / "literature" / "result_cards" / f"{normalized}.md"
    write_json(json_path, payload)
    write_text(md_path, render_literature_search_markdown(payload))
    write_text(cards_path, render_anonymous_result_cards(payload))
    return {
        "status": "done",
        "problem_id": normalized,
        "result_count": len(deduped),
        "errors": errors,
        "artifacts": [
            str(json_path.relative_to(root)),
            str(md_path.relative_to(root)),
            str(cards_path.relative_to(root)),
        ],
    }


def search_arxiv(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    params = urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    xml_text = fetch_text(f"{ARXIV_API_URL}?{params}")
    return parse_arxiv_results(xml_text)


def parse_arxiv_results(xml_text: str) -> list[dict[str, Any]]:
    namespace = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(xml_text)
    results: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", namespace):
        title = normalize_space(entry.findtext("atom:title", default="", namespaces=namespace))
        summary = normalize_space(entry.findtext("atom:summary", default="", namespaces=namespace))
        url = normalize_space(entry.findtext("atom:id", default="", namespaces=namespace))
        published = normalize_space(entry.findtext("atom:published", default="", namespaces=namespace))
        authors = [
            normalize_space(author.findtext("atom:name", default="", namespaces=namespace))
            for author in entry.findall("atom:author", namespace)
        ]
        primary_category = ""
        primary = entry.find("arxiv:primary_category", namespace)
        if primary is not None:
            primary_category = primary.attrib.get("term", "")
        results.append(
            {
                "source": "arxiv",
                "title": title,
                "authors": [author for author in authors if author],
                "year": published[:4] if published else "",
                "url": url,
                "identifier": url.rsplit("/", 1)[-1] if url else "",
                "venue": "arXiv",
                "categories": [primary_category] if primary_category else [],
                "abstract_snippet": truncate_words(summary, 80),
            }
        )
    return results


def search_crossref(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    params = urlencode({
        "query.bibliographic": query,
        "rows": limit,
        "select": "DOI,title,author,published-print,published-online,issued,URL,container-title,abstract",
    })
    payload = fetch_json(f"{CROSSREF_API_URL}?{params}")
    return parse_crossref_results(payload)


def parse_crossref_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in payload.get("message", {}).get("items", []):
        title = normalize_space(first_or_empty(item.get("title")))
        authors = []
        for author in item.get("author", [])[:8]:
            name = normalize_space(" ".join(part for part in [author.get("given", ""), author.get("family", "")] if part))
            if name:
                authors.append(name)
        year = extract_crossref_year(item)
        abstract = normalize_space(strip_tags(item.get("abstract", "")))
        doi = normalize_space(item.get("DOI", ""))
        url = normalize_space(item.get("URL", ""))
        results.append(
            {
                "source": "crossref",
                "title": title,
                "authors": authors,
                "year": year,
                "url": url,
                "identifier": doi,
                "venue": normalize_space(first_or_empty(item.get("container-title"))),
                "categories": [],
                "abstract_snippet": truncate_words(abstract, 80),
            }
        )
    return results


def extract_crossref_year(item: dict[str, Any]) -> str:
    for key in ["published-print", "published-online", "issued"]:
        date_parts = item.get(key, {}).get("date-parts", [])
        if date_parts and date_parts[0]:
            return str(date_parts[0][0])
    return ""


def dedupe_literature_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    deduped: list[dict[str, Any]] = []
    for result in results:
        keys = literature_result_dedupe_keys(result)
        duplicate_index = next((seen[key] for key in keys if key in seen), None)
        if duplicate_index is not None:
            deduped[duplicate_index] = merge_literature_results(deduped[duplicate_index], result)
            for key in keys:
                seen[key] = duplicate_index
            continue
        if not keys:
            keys = [f"result:{len(deduped)}"]
        deduped.append(result)
        current_index = len(deduped) - 1
        for key in keys:
            seen[key] = current_index
    return deduped


def literature_result_dedupe_keys(result: dict[str, Any]) -> list[str]:
    keys = [
        canonical_literature_identifier(result.get("identifier", "")),
        canonical_literature_identifier(result.get("url", "")),
    ]
    title_key = canonical_literature_title(result.get("title", ""))
    if title_key:
        keys.append(f"title:{title_key}")
    return dedupe_strings([key for key in keys if key])


def canonical_literature_identifier(value: Any) -> str:
    text = normalize_space(str(value or "")).lower().rstrip(".")
    if not text:
        return ""
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    if re.match(r"^10\.\d{4,9}/\S+$", text):
        return f"doi:{text}"
    arxiv_match = re.search(r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?([a-z.-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", text)
    if arxiv_match:
        return f"arxiv:{arxiv_match.group(1)}"
    if len(text) >= 6:
        return f"id:{text}"
    return ""


def canonical_literature_title(value: Any) -> str:
    title = normalize_space(strip_tags(str(value or ""))).lower()
    title = re.sub(r"\\[a-zA-Z]+", " ", title)
    title = re.sub(r"[^a-z0-9]+", " ", title)
    title = normalize_space(title)
    if len(title) < 16 or len(title.split()) < 3:
        return ""
    return title


def merge_literature_results(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    primary, secondary = left, right
    if literature_result_quality(right) > literature_result_quality(left):
        primary, secondary = right, left

    merged = dict(primary)
    for field in ["title", "year", "url", "identifier", "venue", "abstract_snippet"]:
        if not merged.get(field) and secondary.get(field):
            merged[field] = secondary[field]
    if len(str(secondary.get("abstract_snippet", ""))) > len(str(merged.get("abstract_snippet", ""))):
        merged["abstract_snippet"] = secondary["abstract_snippet"]
    for field in ["authors", "categories", "relevance_terms"]:
        merged[field] = dedupe_strings(list(merged.get(field, [])) + list(secondary.get(field, [])))
    merged["alternate_sources"] = dedupe_strings(
        list(left.get("alternate_sources", []))
        + list(right.get("alternate_sources", []))
        + [left.get("source", ""), right.get("source", "")]
    )
    merged["alternate_identifiers"] = dedupe_strings(
        list(left.get("alternate_identifiers", []))
        + list(right.get("alternate_identifiers", []))
        + [left.get("identifier", ""), right.get("identifier", "")]
    )
    merged["alternate_urls"] = dedupe_strings(
        list(left.get("alternate_urls", []))
        + list(right.get("alternate_urls", []))
        + [left.get("url", ""), right.get("url", "")]
    )
    return merged


def literature_result_quality(result: dict[str, Any]) -> int:
    score = 0
    identifier = canonical_literature_identifier(result.get("identifier", ""))
    if identifier.startswith("doi:"):
        score += 4
    elif identifier:
        score += 2
    if result.get("abstract_snippet"):
        score += 2
    if result.get("venue"):
        score += 1
    if result.get("url"):
        score += 1
    score += min(2, len(result.get("authors", [])) // 2)
    return score


def filter_literature_results(problem: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_terms = literature_relevance_terms(problem)
    if not target_terms:
        return results
    filtered: list[dict[str, Any]] = []
    for result in results:
        result_text = " ".join([
            result.get("title", ""),
            result.get("abstract_snippet", ""),
            result.get("venue", ""),
        ])
        if not result_matches_required_context(problem, result_text):
            continue
        result_terms = math_tokens(result_text)
        shared = sorted(target_terms & result_terms)
        if not shared:
            continue
        enriched = dict(result)
        enriched["relevance_terms"] = shared[:12]
        enriched["relevance_score"] = len(shared)
        risk_flags = promotion_candidate_risk_flags(problem, enriched)
        enriched["risk_flags"] = risk_flags
        enriched["risk_penalty"] = promotion_candidate_risk_penalty(risk_flags)
        enriched["adjusted_relevance_score"] = max(0, enriched["relevance_score"] - enriched["risk_penalty"])
        filtered.append(enriched)
    filtered.sort(
        key=lambda item: (
            -item.get("adjusted_relevance_score", item.get("relevance_score", 0)),
            -item.get("relevance_score", 0),
            item.get("source", ""),
            item.get("title", ""),
        )
    )
    return filtered


def result_matches_required_context(problem: dict[str, Any], result_text: str) -> bool:
    statement = (problem.get("statement_raw") or problem.get("statement_latex") or "").lower()
    mentions_powers_of_two = "2^" in statement or "powers of two" in statement or "power of two" in statement
    if mentions_powers_of_two and "prime" in statement:
        return bool(re.search(r"\btwo\b|\bpowers?\s+of\s+2\b|2\^", result_text, flags=re.IGNORECASE))
    return True


def literature_relevance_terms(problem: dict[str, Any]) -> set[str]:
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    tags = " ".join(str(tag) for tag in problem.get("tags", []))
    hints = " ".join(domain_query_hints(problem))
    return math_tokens(" ".join([statement, tags, hints]))


def render_literature_search_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Literature Search for {payload['problem_id']}",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Queries",
        "",
    ]
    lines.extend(f"- {query}" for query in payload.get("queries", []))
    lines.extend(["", "## Results", ""])
    for index, result in enumerate(payload.get("results", []), start=1):
        authors = ", ".join(result.get("authors", [])[:4])
        if len(result.get("authors", [])) > 4:
            authors += ", et al."
        lines.extend([
            f"### {index}. {result.get('title') or 'Untitled'}",
            "",
            f"- source: {result.get('source', '')}",
            f"- year: {result.get('year', '')}",
            f"- authors: {authors or 'unknown'}",
            f"- venue: {result.get('venue', '')}",
            f"- id: {result.get('identifier', '')}",
            f"- url: {result.get('url', '')}",
            f"- relevance terms: {', '.join(result.get('relevance_terms', []))}",
            f"- relevance score: {result.get('relevance_score', '')}",
            f"- adjusted relevance score: {result.get('adjusted_relevance_score', result.get('relevance_score', ''))}",
            f"- risk flags: {', '.join(result.get('risk_flags', [])) or 'none'}",
        ])
        if result.get("abstract_snippet"):
            lines.extend(["", result["abstract_snippet"]])
        lines.append("")
    if payload.get("errors"):
        lines.extend(["## Errors", ""])
        lines.extend(f"- {error['source']} / {error['query']}: {error['error']}" for error in payload["errors"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_anonymous_result_cards(payload: dict[str, Any]) -> str:
    lines = [
        f"# Anonymous Result Cards for {payload['problem_id']}",
        "",
        "These cards are solver-facing. They omit source URLs and bibliographic metadata.",
        "",
    ]
    for index, result in enumerate(payload.get("results", []), start=1):
        solver_text = redact_solver_facing_text(" ".join([result.get("title", ""), result.get("abstract_snippet", "")]))
        content_terms = ", ".join(extract_keywords(solver_text, limit=8))
        lines.extend([
            f"## R{index:03d}",
            "",
            f"Content terms: {content_terms or 'TODO'}",
            "",
            "Relation to target: TODO: implies / nearly implies / special case / obstruction / unrelated",
            "",
        ])
        snippet = redact_solver_facing_text(result.get("abstract_snippet", ""))
        if snippet:
            lines.extend(["Summary snippet:", "", snippet, ""])
        lines.extend(["Method tags: TODO", "", "Confidence: TODO", ""])
    return "\n".join(lines).rstrip() + "\n"


def redact_solver_facing_text(text: str) -> str:
    replacements = [
        (r"\bpaul erd[őo]s\b", "source-redacted"),
        (r"\berd[őo]s(?:\s+problems?)?\b", "source-redacted"),
        (r"\berdosproblems\b", "source-redacted"),
        (r"\bopen problem\b", "question"),
        (r"\bunsolved\b", "status-unspecified"),
        (r"\bconjecture\s+\d+\b", "numbered conjecture"),
        (r"\bproblem\s+#?\d+\b", "numbered question"),
        (r"#\d+", "numbered question"),
    ]
    redacted = str(text)
    for pattern, replacement in replacements:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    return normalize_space(redacted)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(text))).strip()


def first_or_empty(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", str(text))


def truncate_words(text: str, limit: int) -> str:
    words = normalize_space(text).split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + " ..."


def write_problem_wiki_stub(root: Path, problem: dict[str, Any]) -> None:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    content = f"""# {problem_id}

Status: {problem.get('status_site', 'unknown')}

Tags: {', '.join(problem.get('tags', [])) or 'none'}

Official URL: {problem.get('url', '')}

## Statement

{problem.get('statement_raw') or problem.get('statement_latex') or 'TODO'}

## Local Artifacts

- [[../../reports/literature/{problem_id}.md]]
- [[../../reports/triage/{problem_id}.json]]

## Notes

TODO
"""
    write_text(root / "kb" / "wiki" / "problems" / f"{problem_id}.md", content)


def run_computation_worker(root: Path, problem_id: str | int) -> dict[str, Any]:
    problem = load_problem(root, problem_id)
    normalized = problem.get("problem_id") or normalize_problem_id(problem["number"])
    computation_dir = root / "computations" / normalized
    readme_path = computation_dir / "README.md"
    script_path = computation_dir / "search.py"
    results_path = computation_dir / "results.md"
    mode = computation_mode(problem)
    write_text(readme_path, make_computation_plan(problem, mode=mode))
    write_text(script_path, make_computation_script(problem, mode=mode))
    write_text(results_path, make_computation_results(problem, mode=mode))
    return {
        "status": "done",
        "summary": f"Created runnable computation harness for {normalized} ({mode}).",
        "artifacts": [
            str(readme_path.relative_to(root)),
            str(script_path.relative_to(root)),
            str(results_path.relative_to(root)),
        ],
    }


def computation_mode(problem: dict[str, Any]) -> str:
    statement = (problem.get("statement_raw") or problem.get("statement_latex") or "").lower()
    tags = " ".join(str(tag).lower() for tag in problem.get("tags", []))
    if "sidon" in statement and "a-a" in statement and "b-b" in statement:
        return "sidon_pair_disjoint_diffs_exact"
    if "triple sums" in statement or "a+b+c" in statement:
        return "b3_max_exact"
    if "infinite sidon" in statement or ("infinite" in statement and "sidon" in statement):
        return "greedy_sidon_prefix"
    if "sidon" in statement or "sidon" in tags:
        return "sidon_max_exact"
    return "finite_subset_sanity"


def make_computation_plan(problem: dict[str, Any], *, mode: str | None = None) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    keywords = extract_keywords(statement, limit=12)
    selected_mode = mode or computation_mode(problem)
    return f"""# Computation Plan for {problem_id}

## Statement

{statement or 'TODO'}

## Signals

- tags: {', '.join(problem.get('tags', [])) or 'none'}
- OEIS: {', '.join(str(item) for item in problem.get('oeis', [])) or 'none'}
- keywords: {', '.join(keywords)}
- mode: {selected_mode}

## Candidate Experiments

- Identify finite parameters and smallest nontrivial cases.
- Search for counterexamples before trying to support the conjecture.
- Reproduce any known small values from OEIS or remarks.
- Log seeds, bounds, and exact commands for every run.

## Files

- `search.py`: runnable bounded search harness.
- `results.md`: first deterministic run from the harness.

## Completion Criteria

- Exact input domain is stated.
- Small cases are reproducible.
- Any counterexample candidate is independently checked.
"""


def make_computation_script(problem: dict[str, Any], *, mode: str | None = None) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    selected_mode = mode or computation_mode(problem)
    max_n = computation_default_max_n(selected_mode)
    return f'''#!/usr/bin/env python3
"""Bounded computation harness for {problem_id}.

This script is intentionally small and dependency-free. It is not a proof; it
produces reproducible small-case data for human review.
"""

from __future__ import annotations

from itertools import combinations_with_replacement
import argparse


MODE = "{selected_mode}"
DEFAULT_MAX_N = {max_n}


def is_sidon(values: list[int]) -> bool:
    diffs: set[int] = set()
    for i, x in enumerate(values):
        for y in values[:i]:
            diff = x - y
            if diff in diffs:
                return False
            diffs.add(diff)
    return True


def sidon_max_exact(n: int) -> tuple[int, list[int]]:
    best: list[int] = []

    def backtrack(start: int, chosen: list[int], diffs: set[int]) -> None:
        nonlocal best
        if len(chosen) + (n - start + 1) <= len(best):
            return
        if len(chosen) > len(best):
            best = chosen[:]
        for x in range(start, n + 1):
            new_diffs = {{x - y for y in chosen}}
            if new_diffs & diffs:
                continue
            chosen.append(x)
            backtrack(x + 1, chosen, diffs | new_diffs)
            chosen.pop()

    backtrack(1, [], set())
    return len(best), best


def is_b3(values: list[int]) -> bool:
    seen: set[int] = set()
    for triple in combinations_with_replacement(values, 3):
        total = sum(triple)
        if total in seen:
            return False
        seen.add(total)
    return True


def b3_max_exact(n: int) -> tuple[int, list[int]]:
    best: list[int] = []

    def backtrack(start: int, chosen: list[int]) -> None:
        nonlocal best
        if len(chosen) + (n - start + 1) <= len(best):
            return
        if len(chosen) > len(best):
            best = chosen[:]
        for x in range(start, n + 1):
            candidate = chosen + [x]
            if not is_b3(candidate):
                continue
            backtrack(x + 1, candidate)

    backtrack(1, [])
    return len(best), best


def binom2(size: int) -> int:
    return size * (size - 1) // 2


def sidon_subsets_with_diff_masks(n: int) -> list[tuple[int, list[int], int]]:
    subsets: list[tuple[int, list[int], int]] = []

    def backtrack(start: int, chosen: list[int], mask: int) -> None:
        subsets.append((len(chosen), chosen[:], mask))
        for x in range(start, n + 1):
            new_mask = 0
            ok = True
            for y in chosen:
                bit = 1 << (x - y)
                if mask & bit or new_mask & bit:
                    ok = False
                    break
                new_mask |= bit
            if not ok:
                continue
            chosen.append(x)
            backtrack(x + 1, chosen, mask | new_mask)
            chosen.pop()

    backtrack(1, [], 0)
    subsets.sort(key=lambda item: (binom2(item[0]), item[0], item[1]), reverse=True)
    return subsets


def sidon_pair_disjoint_diffs_exact(n: int, *, equal_size: bool = False) -> dict[str, object]:
    subsets = sidon_subsets_with_diff_masks(n)
    f_size = max((size for size, _, _ in subsets), default=0)
    baseline = binom2(f_size)
    best_score = -1
    best_balance = -1
    best_min_size = -1
    best_a: list[int] = []
    best_b: list[int] = []

    for size_a, set_a, mask_a in subsets:
        score_a = binom2(size_a)
        for size_b, set_b, mask_b in subsets:
            if equal_size and size_a != size_b:
                continue
            score = score_a + binom2(size_b)
            if score < best_score:
                continue
            if mask_a & mask_b:
                continue
            balance = min(score_a, binom2(size_b))
            min_size = min(size_a, size_b)
            if (
                score > best_score
                or (score == best_score and (balance, min_size) > (best_balance, best_min_size))
                or (
                    score == best_score
                    and (balance, min_size) == (best_balance, best_min_size)
                    and (set_a, set_b) < (best_a, best_b)
                )
            ):
                best_score = score
                best_balance = balance
                best_min_size = min_size
                best_a = set_a[:]
                best_b = set_b[:]

    return {{
        "value": best_score,
        "A": best_a,
        "B": best_b,
        "f_N": f_size,
        "baseline": baseline,
        "excess": best_score - baseline,
    }}


def greedy_sidon(limit: int) -> list[int]:
    values: list[int] = []
    x = 1
    while len(values) < limit:
        candidate = values + [x]
        if is_sidon(candidate):
            values.append(x)
        x += 1
    return values


def run_table(max_n: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if MODE == "greedy_sidon_prefix":
        values = greedy_sidon(max_n)
        checkpoints = [10, 25, 50, 100, 250, 500]
        rows.append({{"n": "terms", "value": len(values), "witness": values}})
        for bound in checkpoints:
            rows.append({{
                "n": bound,
                "value": sum(1 for value in values if value <= bound),
                "witness": [value for value in values if value <= bound],
            }})
        return rows

    if MODE == "sidon_pair_disjoint_diffs_exact":
        for n in range(1, max_n + 1):
            full = sidon_pair_disjoint_diffs_exact(n)
            equal = sidon_pair_disjoint_diffs_exact(n, equal_size=True)
            rows.append({{
                "n": n,
                "value": full["value"],
                "witness": {{
                    "A": full["A"],
                    "B": full["B"],
                    "f_N": full["f_N"],
                    "baseline": full["baseline"],
                    "excess": full["excess"],
                    "equal_size_value": equal["value"],
                    "equal_size_A": equal["A"],
                    "equal_size_B": equal["B"],
                    "equal_size_excess": equal["excess"],
                }},
            }})
        return rows

    for n in range(1, max_n + 1):
        if MODE == "b3_max_exact":
            value, witness = b3_max_exact(n)
        else:
            value, witness = sidon_max_exact(n)
        rows.append({{"n": n, "value": value, "witness": witness}})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-n", type=int, default=DEFAULT_MAX_N)
    args = parser.parse_args()
    print(f"# mode={{MODE}} max_n={{args.max_n}}")
    for row in run_table(args.max_n):
        print(f"{{row['n']}}\\t{{row['value']}}\\t{{row['witness']}}")


if __name__ == "__main__":
    main()
'''


def make_computation_results(problem: dict[str, Any], *, mode: str | None = None) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    selected_mode = mode or computation_mode(problem)
    max_n = computation_default_max_n(selected_mode)
    rows = computation_rows(selected_mode, max_n)
    lines = [
        f"# Computation Results for {problem_id}",
        "",
        f"Generated: {date.today().isoformat()}",
        f"Mode: `{selected_mode}`",
        f"Bound: `{max_n}`",
        "",
        "This is bounded experimental data, not a proof.",
        "",
        "| n | value | witness |",
        "|---|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['n']} | {row['value']} | `{row['witness']}` |")
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            f"python3 computations/{problem_id}/search.py --max-n {max_n}",
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def computation_default_max_n(mode: str) -> int:
    if mode == "sidon_pair_disjoint_diffs_exact":
        return 14
    if mode == "b3_max_exact":
        return 14
    if mode == "greedy_sidon_prefix":
        return 64
    if mode == "sidon_max_exact":
        return 24
    return 16


def computation_rows(mode: str, max_n: int) -> list[dict[str, Any]]:
    if mode == "greedy_sidon_prefix":
        values = greedy_sidon_values(max_n)
        rows = [{"n": "terms", "value": len(values), "witness": values}]
        for bound in [10, 25, 50, 100, 250, 500]:
            rows.append(
                {
                    "n": bound,
                    "value": sum(1 for value in values if value <= bound),
                    "witness": [value for value in values if value <= bound],
                }
            )
        return rows

    if mode == "sidon_pair_disjoint_diffs_exact":
        rows = []
        for n in range(1, max_n + 1):
            full = sidon_pair_disjoint_diffs_exact_values(n)
            equal = sidon_pair_disjoint_diffs_exact_values(n, equal_size=True)
            rows.append(
                {
                    "n": n,
                    "value": full["value"],
                    "witness": {
                        "A": full["A"],
                        "B": full["B"],
                        "f_N": full["f_N"],
                        "baseline": full["baseline"],
                        "excess": full["excess"],
                        "equal_size_value": equal["value"],
                        "equal_size_A": equal["A"],
                        "equal_size_B": equal["B"],
                        "equal_size_excess": equal["excess"],
                    },
                }
            )
        return rows

    rows = []
    for n in range(1, max_n + 1):
        if mode == "b3_max_exact":
            value, witness = b3_max_exact_values(n)
        else:
            value, witness = sidon_max_exact_values(n)
        rows.append({"n": n, "value": value, "witness": witness})
    return rows


def sidon_max_exact_values(n: int) -> tuple[int, list[int]]:
    best: list[int] = []

    def backtrack(start: int, chosen: list[int], diffs: set[int]) -> None:
        nonlocal best
        if len(chosen) + (n - start + 1) <= len(best):
            return
        if len(chosen) > len(best):
            best = chosen[:]
        for x in range(start, n + 1):
            new_diffs = {x - y for y in chosen}
            if new_diffs & diffs:
                continue
            chosen.append(x)
            backtrack(x + 1, chosen, diffs | new_diffs)
            chosen.pop()

    backtrack(1, [], set())
    return len(best), best


def b3_max_exact_values(n: int) -> tuple[int, list[int]]:
    best: list[int] = []

    def backtrack(start: int, chosen: list[int]) -> None:
        nonlocal best
        if len(chosen) + (n - start + 1) <= len(best):
            return
        if len(chosen) > len(best):
            best = chosen[:]
        for x in range(start, n + 1):
            candidate = chosen + [x]
            if not is_b3_values(candidate):
                continue
            backtrack(x + 1, candidate)

    backtrack(1, [])
    return len(best), best


def is_b3_values(values: list[int]) -> bool:
    seen: set[int] = set()
    for triple in combinations_with_replacement(values, 3):
        total = sum(triple)
        if total in seen:
            return False
        seen.add(total)
    return True


def binom2_values(size: int) -> int:
    return size * (size - 1) // 2


def sidon_subsets_with_diff_masks_values(n: int) -> list[tuple[int, list[int], int]]:
    subsets: list[tuple[int, list[int], int]] = []

    def backtrack(start: int, chosen: list[int], mask: int) -> None:
        subsets.append((len(chosen), chosen[:], mask))
        for x in range(start, n + 1):
            new_mask = 0
            ok = True
            for y in chosen:
                bit = 1 << (x - y)
                if mask & bit or new_mask & bit:
                    ok = False
                    break
                new_mask |= bit
            if not ok:
                continue
            chosen.append(x)
            backtrack(x + 1, chosen, mask | new_mask)
            chosen.pop()

    backtrack(1, [], 0)
    subsets.sort(key=lambda item: (binom2_values(item[0]), item[0], item[1]), reverse=True)
    return subsets


def sidon_pair_disjoint_diffs_exact_values(n: int, *, equal_size: bool = False) -> dict[str, Any]:
    subsets = sidon_subsets_with_diff_masks_values(n)
    f_size = max((size for size, _, _ in subsets), default=0)
    baseline = binom2_values(f_size)
    best_score = -1
    best_balance = -1
    best_min_size = -1
    best_a: list[int] = []
    best_b: list[int] = []

    for size_a, set_a, mask_a in subsets:
        score_a = binom2_values(size_a)
        for size_b, set_b, mask_b in subsets:
            if equal_size and size_a != size_b:
                continue
            score = score_a + binom2_values(size_b)
            if score < best_score:
                continue
            if mask_a & mask_b:
                continue
            balance = min(score_a, binom2_values(size_b))
            min_size = min(size_a, size_b)
            if (
                score > best_score
                or (score == best_score and (balance, min_size) > (best_balance, best_min_size))
                or (
                    score == best_score
                    and (balance, min_size) == (best_balance, best_min_size)
                    and (set_a, set_b) < (best_a, best_b)
                )
            ):
                best_score = score
                best_balance = balance
                best_min_size = min_size
                best_a = set_a[:]
                best_b = set_b[:]

    return {
        "value": best_score,
        "A": best_a,
        "B": best_b,
        "f_N": f_size,
        "baseline": baseline,
        "excess": best_score - baseline,
    }


def greedy_sidon_values(limit: int) -> list[int]:
    values: list[int] = []
    x = 1
    while len(values) < limit:
        candidate = values + [x]
        if is_sidon_values(candidate):
            values.append(x)
        x += 1
    return values


def is_sidon_values(values: list[int]) -> bool:
    diffs: set[int] = set()
    for i, x in enumerate(values):
        for y in values[:i]:
            diff = x - y
            if diff in diffs:
                return False
            diffs.add(diff)
    return True


def run_statement_auditor_worker(root: Path, problem_id: str | int) -> dict[str, Any]:
    problem = load_problem(root, problem_id)
    normalized = problem.get("problem_id") or normalize_problem_id(problem["number"])
    path = root / "reports" / "statement_audits" / f"{normalized}.md"
    write_text(path, make_statement_audit(problem))
    return {
        "status": "done",
        "summary": f"Created statement audit template for {normalized}.",
        "artifacts": [str(path.relative_to(root))],
    }


def run_formalization_worker(root: Path, problem_id: str | int) -> dict[str, Any]:
    problem = load_problem(root, problem_id)
    normalized = problem.get("problem_id") or normalize_problem_id(problem["number"])
    path = root / "lean" / normalized / "README.md"
    write_text(path, make_formalization_plan(problem))
    return {
        "status": "done",
        "summary": f"Created formalization plan for {normalized}.",
        "artifacts": [str(path.relative_to(root))],
    }


def make_formalization_plan(problem: dict[str, Any]) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    return f"""# Formalization Plan for {problem_id}

## Informal Statement

{statement or 'TODO'}

## Lean Target

TODO: write the exact theorem statement before attempting a proof.

## Statement Correspondence Checklist

- Variables and domains match.
- Quantifier order matches.
- No stronger assumptions.
- No weaker conclusion.
- Edge cases documented.
- No `sorry`, `admit`, new axioms, or unsafe escape hatches in final proof.
"""


def run_critic_worker(root: Path, problem_id: str | int) -> dict[str, Any]:
    problem = load_problem(root, problem_id)
    normalized = problem.get("problem_id") or normalize_problem_id(problem["number"])
    path = root / "reports" / "referee" / f"{normalized}.md"
    write_text(path, make_referee_report(problem))
    return {
        "status": "done",
        "summary": f"Created referee checklist for {normalized}.",
        "artifacts": [str(path.relative_to(root))],
    }


def make_referee_report(problem: dict[str, Any]) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    return f"""# Referee Report for {problem_id}

## Artifacts Reviewed

- TODO

## Rejection Checklist

- Does the attempt prove the exact intended statement?
- Are quantifiers correct?
- Are small cases and degenerate cases handled?
- Is any lemma false in small cases?
- Does the argument rely on an unstated asymptotic or genericity assumption?
- Is it already known from captured references or nearby literature?
- Does any Lean statement weaken the original problem?

## Verdict

do_not_post / needs_human / ask_expert / continue
"""


def run_blind_solver_packet_worker(root: Path, problem_id: str | int, *, run: dict[str, Any] | None = None) -> dict[str, Any]:
    route_packet_artifacts = blind_packet_artifacts_from_run(run or {})
    if route_packet_artifacts:
        return run_blind_solver_route_handoff(root, problem_id, run or {}, route_packet_artifacts)

    problem = load_problem(root, problem_id)
    task_id, content, manifest = make_blind_packet(problem)
    packet_path = root / "packets" / "blind" / f"{task_id}.md"
    manifest_path = root / "data" / "manifests" / f"{task_id}.json"
    write_text(packet_path, content)
    write_json(manifest_path, manifest)
    return {
        "status": "needs_human",
        "summary": "Blind solver packet is ready; hand it to a blind solver agent without metadata.",
        "artifacts": [str(packet_path.relative_to(root)), str(manifest_path.relative_to(root))],
    }


def blind_packet_artifacts_from_run(run: dict[str, Any]) -> list[str]:
    artifacts = [str(artifact) for artifact in run.get("artifacts", [])]
    metadata_artifacts = [str(artifact) for artifact in run.get("metadata", {}).get("blind_packet_artifacts", [])]
    return dedupe_strings(
        [
            artifact
            for artifact in [*metadata_artifacts, *artifacts]
            if artifact.startswith("packets/blind/") and artifact.endswith(".md")
        ]
    )


def run_blind_solver_route_handoff(
    root: Path,
    problem_id: str | int,
    run: dict[str, Any],
    packet_artifacts: list[str],
) -> dict[str, Any]:
    normalized = normalize_problem_id(problem_id)
    route = str(run.get("metadata", {}).get("route", "proof-route")).replace("-", "_")
    handoff_path = root / "reports" / "attempts" / f"{normalized}-{route}-blind-handoff.md"
    content = f"""# Blind Solver Handoff: {normalized} / {route}

Generated: {date.today().isoformat()}

This is an internal handoff. Give the solver only the redacted packet listed below,
not this source-aware handoff file.

## Redacted Packet

{chr(10).join(f"- `{artifact}`" for artifact in packet_artifacts)}

## Requested Solver Output

Ask the solver to write a proof, disproof, or gap-labeled partial attempt in:

```text
reports/attempts/{normalized}-{route}-attempt.md
```

The attempt should include:

1. Exact statement considered
2. Edge cases and small examples
3. Main proof or disproof attempt
4. Lemmas used or proposed
5. Gaps or uncertain steps
6. Suggested formalization target

## Safety

- Do not give the solver source-aware literature files.
- Do not claim novelty.
- Do not post externally.
"""
    write_text(handoff_path, content)
    return {
        "status": "needs_human",
        "summary": "Redacted proof-route packet is queued for a blind solver attempt.",
        "artifacts": [*packet_artifacts, str(handoff_path.relative_to(root))],
    }


def supervisor_step(root: Path, *, limit: int = 5) -> dict[str, Any]:
    queued = [run for run in list_agent_runs(root, status="queued")]
    completed = [run for run in list_agent_runs(root) if run.get("status") in {"done", "needs_human", "blocked"}]
    next_runs = queued[:limit]
    review_candidates = review_candidate_summary(root, limit=limit)
    result = {
        "generated_at": date.today().isoformat(),
        "queued_count": len(queued),
        "completed_count": len(completed),
        "review_candidates": review_candidates,
        "next_runs": [
            {
                "run_id": run["run_id"],
                "agent": run["agent"],
                "problem_id": run.get("problem_id"),
                "priority": run.get("priority"),
                "prompt": run.get("prompt", ""),
                "artifacts": run.get("artifacts", []),
            }
            for run in next_runs
        ],
    }
    write_json(root / "agent_runs" / "supervisor_step.json", result)
    return result


def review_candidate_summary(root: Path, *, limit: int = 5) -> dict[str, Any]:
    report_path = root / "reports" / "literature" / "review" / "promotion_candidates.json"
    relative_path = "reports/literature/review/promotion_candidates.json"
    if not report_path.exists():
        return {
            "available": False,
            "candidate_count": 0,
            "path": relative_path,
            "top_candidates": [],
            "next_action": "python3 -m erdos_agent review-search-results --limit 20 --min-score 7",
        }

    report = read_json(report_path)
    top_candidates = [
        {
            "candidate_id": item.get("candidate_id"),
            "problem_id": item.get("problem_id"),
            "result_index": item.get("result_index"),
            "review_score": item.get("review_score"),
            "status": item.get("status"),
            "source": item.get("source"),
            "title": item.get("title", ""),
            "duplicate_count": item.get("duplicate_count", 0),
            "related_problem_ids": item.get("related_problem_ids", []),
            "approve_command": item.get("approve_command"),
        }
        for item in report.get("items", [])[:limit]
    ]
    return {
        "available": True,
        "generated_at": report.get("generated_at"),
        "candidate_count": report.get("returned", len(report.get("items", []))),
        "path": relative_path,
        "top_candidates": top_candidates,
        "next_action": "Review top_candidates, then run approve-promotion-candidate for selected candidate ids.",
    }


def make_run_id(agent: str, problem_id: str | None) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    seed = f"{agent}:{problem_id or 'none'}:{stamp}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    base = f"{date.today().isoformat()}-{agent}"
    if problem_id:
        base = f"{base}-{problem_id}"
    return f"{base}-{digest}"


def agent_run_inbox_path(root: Path, run_id: str) -> Path:
    return root / "agent_runs" / "inbox" / f"{run_id}.json"


def agent_run_outbox_path(root: Path, run_id: str) -> Path:
    return root / "agent_runs" / "outbox" / f"{run_id}.json"


def default_run_prompt(agent: str, problem_id: str, recommended_next_action: str = "") -> str:
    if agent == "literature":
        return f"Prepare a literature report for {problem_id}. Record useful findings with add-finding and pivot if a better target appears."
    if agent == "blind_solver":
        return f"Use only the blind packet for {problem_id}. Produce a proof, disproof, or gap-labeled partial attempt."
    if agent == "computation":
        return f"Design and run a focused computation or counterexample search for {problem_id}."
    if agent == "formalization":
        return f"Create or inspect a Lean formalization target for {problem_id}."
    if agent == "critic":
        return f"Review the current attempt artifacts for {problem_id} and try to reject them."
    if agent == "statement_auditor":
        return f"Audit the exact statement, quantifiers, edge cases, and redaction risk for {problem_id}."
    return f"Handle {recommended_next_action} for {problem_id}."


def default_run_artifacts(root: Path, agent: str, problem_id: str) -> list[str]:
    artifacts: list[str] = []
    normalized = normalize_problem_id(problem_id)
    problem_file = root / "data" / "problems" / f"{normalized}.json"
    if problem_file.exists() and agent != "blind_solver":
        artifacts.append(str(problem_file.relative_to(root)))
    if agent == "blind_solver":
        manifest_paths = sorted((root / "data" / "manifests").glob("math-task-*.json"))
        for manifest_path in manifest_paths:
            manifest = read_json(manifest_path)
            if manifest.get("problem_id") == normalized:
                artifacts.append(str((root / "packets" / "blind" / f"{manifest['task_id']}.md").relative_to(root)))
                break
    triage_file = root / "reports" / "triage" / f"{normalized}.json"
    if triage_file.exists():
        artifacts.append(str(triage_file.relative_to(root)))
    return artifacts


def common_reference_keys(problem_paths: list[Path]) -> set[str]:
    frequencies: dict[str, int] = {}
    for path in problem_paths:
        problem = read_json(path)
        for key in reference_keys(problem.get("known_references", [])):
            frequencies[key] = frequencies.get(key, 0) + 1
    if not problem_paths:
        return set()
    threshold = max(3, len(problem_paths) // 10)
    return {key for key, count in frequencies.items() if count > threshold}


def similarity_score(
    seed: dict[str, Any],
    candidate: dict[str, Any],
    *,
    ignored_reference_keys: set[str] | None = None,
) -> tuple[int, list[str]]:
    rationale: list[str] = []
    score = 0
    ignored_reference_keys = ignored_reference_keys or set()

    seed_tags = {str(tag).lower() for tag in seed.get("tags", [])}
    candidate_tags = {str(tag).lower() for tag in candidate.get("tags", [])}
    shared_tags = sorted(seed_tags & candidate_tags)
    if shared_tags:
        tag_score = 5 * len(shared_tags)
        score += tag_score
        rationale.append(f"shared tags: {', '.join(shared_tags)} (+{tag_score})")

    seed_tokens = math_tokens(problem_search_text(seed))
    candidate_tokens = math_tokens(problem_search_text(candidate))
    shared_tokens = sorted(seed_tokens & candidate_tokens)
    if shared_tokens:
        token_score = min(20, 2 * len(shared_tokens))
        score += token_score
        rationale.append(f"shared math terms: {', '.join(shared_tokens[:12])} (+{token_score})")

    seed_refs = reference_keys(seed.get("known_references", []))
    candidate_refs = reference_keys(candidate.get("known_references", []))
    shared_refs = sorted((seed_refs & candidate_refs) - ignored_reference_keys)
    if shared_refs:
        ref_score = 4 * len(shared_refs)
        score += ref_score
        rationale.append(f"shared references: {', '.join(shared_refs)} (+{ref_score})")

    seed_oeis = {str(item).lower() for item in seed.get("oeis", []) if str(item).lower() not in {"n/a", "possible"}}
    candidate_oeis = {str(item).lower() for item in candidate.get("oeis", []) if str(item).lower() not in {"n/a", "possible"}}
    shared_oeis = sorted(seed_oeis & candidate_oeis)
    if shared_oeis:
        oeis_score = 3 * len(shared_oeis)
        score += oeis_score
        rationale.append(f"shared OEIS entries: {', '.join(shared_oeis)} (+{oeis_score})")

    if seed.get("formalization_status") == "yes" and candidate.get("formalization_status") == "yes":
        score += 1
        rationale.append("both have formalization metadata (+1)")

    return score, rationale


def problem_search_text(problem: dict[str, Any]) -> str:
    return " ".join(
        str(problem.get(key, ""))
        for key in ["statement_raw", "statement_latex"]
    )


def math_tokens(text: str) -> set[str]:
    stop = {
        "there",
        "which",
        "where",
        "every",
        "large",
        "such",
        "that",
        "with",
        "from",
        "then",
        "than",
        "this",
        "also",
        "does",
        "some",
        "have",
        "many",
        "can",
        "all",
        "for",
        "the",
        "and",
        "are",
        "is",
        "ldots",
        "one",
        "two",
    }
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text)
        if token.lower() not in stop
    }
    return tokens


def reference_keys(references: list[Any]) -> set[str]:
    keys: set[str] = set()
    for reference in references:
        match = re.match(r"^\[([^\]]+)\]", str(reference).strip())
        if match:
            keys.add(match.group(1))
    return keys


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
    if not (problem.get("statement_raw") or problem.get("statement_latex")):
        caveats.append("statement is not fetched yet; run ingest-github with --fetch-statements or add it manually before solver use.")
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
