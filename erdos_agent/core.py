from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


PROBLEMS_YAML_URL = "https://raw.githubusercontent.com/teorth/erdosproblems/main/data/problems.yaml"
ERDOS_PROBLEMS_BASE_URL = "https://www.erdosproblems.com"


DEFAULT_DIRS = [
    "data/problems",
    "data/raw",
    "data/references",
    "data/manifests",
    "notes",
    "reports/triage",
    "reports/analogies",
    "reports/literature",
    "reports/literature/findings",
    "reports/pivots",
    "reports/statement_audits",
    "reports/attempts",
    "reports/referee",
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
    items = items[:limit]
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
        result = run_blind_solver_packet_worker(root, problem_id)
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
    update_kb_index(root, f"wiki/problems/{normalized}.md", f"Problem {normalized} literature status")
    write_problem_wiki_stub(root, problem)
    return {
        "status": "done",
        "summary": f"Created literature report for {normalized}.",
        "artifacts": [str(path.relative_to(root))],
    }


def make_literature_report(problem: dict[str, Any]) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    references = problem.get("known_references", [])
    remarks = problem.get("remarks_raw", "")
    keywords = extract_keywords(" ".join([statement, remarks]), limit=16)
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
    base_terms = " ".join(keywords[:6])
    queries = []
    if base_terms:
        queries.append(base_terms)
    if tags and base_terms:
        queries.append(f"{base_terms} {' '.join(tags[:2])}")
    for reference in problem.get("known_references", [])[:3]:
        key_match = re.match(r"^\[([^\]]+)\]\s*(.*)", str(reference))
        if key_match:
            queries.append(key_match.group(2)[:160])
    return [query for query in queries if query.strip()]


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
    path = root / "computations" / normalized / "README.md"
    write_text(path, make_computation_plan(problem))
    return {
        "status": "done",
        "summary": f"Created computation plan for {normalized}.",
        "artifacts": [str(path.relative_to(root))],
    }


def make_computation_plan(problem: dict[str, Any]) -> str:
    problem_id = problem.get("problem_id") or normalize_problem_id(problem["number"])
    statement = problem.get("statement_raw") or problem.get("statement_latex") or ""
    keywords = extract_keywords(statement, limit=12)
    return f"""# Computation Plan for {problem_id}

## Statement

{statement or 'TODO'}

## Signals

- tags: {', '.join(problem.get('tags', [])) or 'none'}
- OEIS: {', '.join(str(item) for item in problem.get('oeis', [])) or 'none'}
- keywords: {', '.join(keywords)}

## Candidate Experiments

- Identify finite parameters and smallest nontrivial cases.
- Search for counterexamples before trying to support the conjecture.
- Reproduce any known small values from OEIS or remarks.
- Log seeds, bounds, and exact commands for every run.

## Files

- `search.py`: TODO
- `results.md`: TODO

## Completion Criteria

- Exact input domain is stated.
- Small cases are reproducible.
- Any counterexample candidate is independently checked.
"""


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


def run_blind_solver_packet_worker(root: Path, problem_id: str | int) -> dict[str, Any]:
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


def supervisor_step(root: Path, *, limit: int = 5) -> dict[str, Any]:
    queued = [run for run in list_agent_runs(root, status="queued")]
    completed = [run for run in list_agent_runs(root) if run.get("status") in {"done", "needs_human", "blocked"}]
    next_runs = queued[:limit]
    result = {
        "generated_at": date.today().isoformat(),
        "queued_count": len(queued),
        "completed_count": len(completed),
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
