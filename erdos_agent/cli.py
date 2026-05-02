from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    create_problem,
    ensure_workspace,
    load_problem,
    make_blind_packet,
    make_claim_card,
    make_literature_packet,
    make_statement_audit,
    normalize_problem_id,
    score_problem,
    write_json,
    write_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erdos-agent",
        description="MVP CLI for redacted Erdős problem triage and Codex solver packets.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Workspace root. Defaults to the current directory.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create the local research workspace directories.")

    new_parser = subparsers.add_parser("new", help="Create a problem JSON from a statement.")
    new_parser.add_argument("number", type=int)
    new_parser.add_argument("--statement", help="Statement text.")
    new_parser.add_argument("--statement-file", help="Path to a file containing the statement.")
    new_parser.add_argument("--title", default="")
    new_parser.add_argument("--url", default="")
    new_parser.add_argument("--status-site", default="unknown")
    new_parser.add_argument("--tag", action="append", default=[], help="Repeatable tag.")

    triage_parser = subparsers.add_parser("triage", help="Score one local problem.")
    triage_parser.add_argument("problem_id")

    redact_parser = subparsers.add_parser("redact", help="Generate a blind solver packet.")
    redact_parser.add_argument("problem_id")

    lit_parser = subparsers.add_parser("literature-packet", help="Generate an anonymous literature search packet.")
    lit_parser.add_argument("problem_id")

    audit_parser = subparsers.add_parser("audit", help="Generate a statement audit template.")
    audit_parser.add_argument("problem_id")

    claim_parser = subparsers.add_parser("claim-card", help="Generate a claim card template.")
    claim_parser.add_argument("problem_id")

    pipeline_parser = subparsers.add_parser("pipeline", help="Run triage, redaction, literature packet, audit, and claim card.")
    pipeline_parser.add_argument("problem_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.command == "init":
            ensure_workspace(root)
            print(f"Initialized workspace at {root}")
            return 0

        ensure_workspace(root)

        if args.command == "new":
            statement = read_statement_arg(args.statement, args.statement_file)
            result = create_problem(
                root,
                args.number,
                statement,
                title=args.title,
                url=args.url,
                tags=args.tag,
                status_site=args.status_site,
            )
            print(f"Wrote {result.path}")
            return 0

        if args.command == "triage":
            run_triage(root, args.problem_id)
            return 0

        if args.command == "redact":
            run_redact(root, args.problem_id)
            return 0

        if args.command == "literature-packet":
            run_literature_packet(root, args.problem_id)
            return 0

        if args.command == "audit":
            run_audit(root, args.problem_id)
            return 0

        if args.command == "claim-card":
            run_claim_card(root, args.problem_id)
            return 0

        if args.command == "pipeline":
            task_id = run_redact(root, args.problem_id)
            run_triage(root, args.problem_id)
            run_literature_packet(root, args.problem_id)
            run_audit(root, args.problem_id)
            run_claim_card(root, args.problem_id, task_id=task_id)
            return 0

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unhandled command: {args.command}")
    return 2


def read_statement_arg(statement: str | None, statement_file: str | None) -> str:
    if bool(statement) == bool(statement_file):
        raise ValueError("Provide exactly one of --statement or --statement-file.")
    if statement_file:
        return Path(statement_file).read_text(encoding="utf-8").strip()
    return statement.strip()


def run_triage(root: Path, problem_id: str) -> None:
    problem = load_problem(root, problem_id)
    score = score_problem(problem)
    path = root / "reports" / "triage" / f"{normalize_problem_id(problem_id)}.json"
    write_json(path, score)
    print(f"Wrote {path}")
    print(f"Recommended next action: {score['recommended_next_action']}")


def run_redact(root: Path, problem_id: str) -> str:
    problem = load_problem(root, problem_id)
    task_id, content, manifest = make_blind_packet(problem)
    packet_path = root / "packets" / "blind" / f"{task_id}.md"
    manifest_path = root / "data" / "manifests" / f"{task_id}.json"
    write_text(packet_path, content)
    write_json(manifest_path, manifest)
    print(f"Wrote {packet_path}")
    print(f"Wrote {manifest_path}")
    if manifest["statement_leak_patterns"]:
        print("warning: statement may leak source/status context; review manifest before blind solving.")
    return task_id


def run_literature_packet(root: Path, problem_id: str) -> str:
    problem = load_problem(root, problem_id)
    task_id, content = make_literature_packet(problem)
    path = root / "packets" / "literature" / f"{task_id}.md"
    write_text(path, content)
    print(f"Wrote {path}")
    return task_id


def run_audit(root: Path, problem_id: str) -> None:
    problem = load_problem(root, problem_id)
    content = make_statement_audit(problem)
    path = root / "reports" / "statement_audits" / f"{normalize_problem_id(problem_id)}.md"
    write_text(path, content)
    print(f"Wrote {path}")


def run_claim_card(root: Path, problem_id: str, *, task_id: str | None = None) -> None:
    problem = load_problem(root, problem_id)
    if task_id is None:
        task_id, _, _ = make_blind_packet(problem)
    content = make_claim_card(problem, task_id)
    path = root / "reports" / "attempts" / f"{normalize_problem_id(problem_id)}.claim.md"
    write_text(path, content)
    print(f"Wrote {path}")


if __name__ == "__main__":
    raise SystemExit(main())

