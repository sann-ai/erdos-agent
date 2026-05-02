from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    PROBLEMS_YAML_URL,
    complete_agent_run,
    create_problem,
    create_agent_run,
    create_runs_from_triage,
    ensure_workspace,
    execute_agent_run,
    find_similar_problems,
    ingest_github_problems,
    list_agent_runs,
    load_problem,
    make_blind_packet,
    make_claim_card,
    make_literature_packet,
    make_statement_audit,
    normalize_problem_id,
    pivot_from_literature_finding,
    record_literature_finding,
    record_math_example,
    score_problem,
    supervisor_step,
    triage_all,
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

    ingest_parser = subparsers.add_parser("ingest-github", help="Import teorth/erdosproblems metadata.")
    ingest_parser.add_argument("--url", default=PROBLEMS_YAML_URL)
    ingest_parser.add_argument("--limit", type=int, help="Maximum number of selected records to import.")
    ingest_parser.add_argument("--status", action="append", default=[], help="Repeatable status filter, e.g. open.")
    ingest_parser.add_argument("--fetch-statements", action="store_true", help="Also fetch statement text from erdosproblems.com/latex/<n>.")
    ingest_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing fetched/manual statement text when fetching statements.")

    triage_all_parser = subparsers.add_parser("triage-all", help="Score and rank local problems.")
    triage_all_parser.add_argument("--status", action="append", default=["open"], help="Repeatable status filter. Use 'all' to disable filtering.")
    triage_all_parser.add_argument("--limit", type=int, default=30, help="Number of ranked items to include. Use 0 for all.")

    transfer_parser = subparsers.add_parser("transfer-search", help="Find open problems similar to a solved or promising seed problem.")
    transfer_parser.add_argument("seed_problem_id")
    transfer_parser.add_argument("--status", action="append", default=["open"], help="Repeatable status filter for target problems. Use 'all' to disable filtering.")
    transfer_parser.add_argument("--limit", type=int, default=20)

    finding_parser = subparsers.add_parser("add-finding", help="Record a literature finding and add it to the wiki layer.")
    finding_parser.add_argument("problem_id")
    finding_parser.add_argument("--paper-key", required=True)
    finding_parser.add_argument("--title", required=True)
    finding_parser.add_argument("--url", default="")
    finding_parser.add_argument("--summary", default="")
    finding_parser.add_argument("--method-tag", action="append", default=[])
    finding_parser.add_argument("--example", action="append", default=[])
    finding_parser.add_argument("--relevance", type=int, default=3)

    pivot_parser = subparsers.add_parser("pivot-from-finding", help="Suggest open problems to pivot to from a literature finding.")
    pivot_parser.add_argument("finding_id")
    pivot_parser.add_argument("--status", action="append", default=["open"])
    pivot_parser.add_argument("--limit", type=int, default=20)

    example_parser = subparsers.add_parser("add-example", help="Store a mathematical example in the knowledge base.")
    example_parser.add_argument("example_id")
    example_parser.add_argument("--statement", help="Example statement.")
    example_parser.add_argument("--statement-file", help="Path to a file containing the example statement.")
    example_parser.add_argument("--source", default="")
    example_parser.add_argument("--problem-id")
    example_parser.add_argument("--tag", action="append", default=[])
    example_parser.add_argument("--role", default="example")

    run_parser = subparsers.add_parser("create-run", help="Create agent run job JSON in agent_runs/inbox.")
    run_source = run_parser.add_mutually_exclusive_group(required=True)
    run_source.add_argument("--problem")
    run_source.add_argument("--from-triage", action="store_true")
    run_parser.add_argument("--agent", required=True)
    run_parser.add_argument("--limit", type=int, default=5, help="Used with --from-triage.")
    run_parser.add_argument("--action", action="append", default=[], help="Filter triage recommended_next_action when using --from-triage.")
    run_parser.add_argument("--prompt", default="")
    run_parser.add_argument("--artifact", action="append", default=[])
    run_parser.add_argument("--priority", type=int, default=3)

    list_runs_parser = subparsers.add_parser("list-runs", help="List agent run jobs.")
    list_runs_parser.add_argument("--status", choices=["queued", "done", "blocked", "needs_human", "cancelled"])

    complete_parser = subparsers.add_parser("complete-run", help="Move a queued run from inbox to outbox.")
    complete_parser.add_argument("run_id")
    complete_parser.add_argument("--status", required=True, choices=["done", "blocked", "needs_human", "cancelled"])
    complete_parser.add_argument("--summary", required=True)
    complete_parser.add_argument("--artifact", action="append", default=[])

    supervisor_parser = subparsers.add_parser("supervisor-step", help="Summarize queued and completed agent runs.")
    supervisor_parser.add_argument("--limit", type=int, default=5)

    run_agent_parser = subparsers.add_parser("run-agent", help="Execute one queued agent run with the built-in MVP worker.")
    run_agent_parser.add_argument("run_id")

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

        if args.command == "ingest-github":
            run_ingest_github(root, args)
            return 0

        if args.command == "triage-all":
            run_triage_all(root, args)
            return 0

        if args.command == "transfer-search":
            run_transfer_search(root, args)
            return 0

        if args.command == "add-finding":
            run_add_finding(root, args)
            return 0

        if args.command == "pivot-from-finding":
            run_pivot_from_finding(root, args)
            return 0

        if args.command == "add-example":
            run_add_example(root, args)
            return 0

        if args.command == "create-run":
            run_create_agent_run(root, args)
            return 0

        if args.command == "list-runs":
            run_list_agent_runs(root, args)
            return 0

        if args.command == "complete-run":
            run_complete_agent_run(root, args)
            return 0

        if args.command == "supervisor-step":
            run_supervisor_step(root, args)
            return 0

        if args.command == "run-agent":
            run_execute_agent_run(root, args)
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


def run_ingest_github(root: Path, args: argparse.Namespace) -> None:
    summary = ingest_github_problems(
        root,
        source_url=args.url,
        limit=args.limit,
        status_filter=parse_status_filter(args.status),
        fetch_statements=args.fetch_statements,
        overwrite=args.overwrite,
    )
    print(f"Imported {summary['written']} problems from {summary['source_url']}")
    if summary["errors"]:
        print(f"Statement fetch errors: {len(summary['errors'])}")


def run_triage_all(root: Path, args: argparse.Namespace) -> None:
    limit = None if args.limit == 0 else args.limit
    index = triage_all(root, status_filter=parse_status_filter(args.status), limit=limit)
    print(f"Wrote {root / 'reports' / 'triage' / 'index.json'}")
    print(f"Ranked {index['returned']} of {index['considered']} considered problems")
    for item in index["items"][:10]:
        statement_mark = "statement" if item["statement_present"] else "no-statement"
        print(
            f"{item['problem_id']} score={item['priority_score']} "
            f"next={item['recommended_next_action']} {statement_mark}"
        )


def parse_status_filter(values: list[str]) -> set[str] | None:
    cleaned = {value.strip().lower() for value in values if value.strip()}
    if not cleaned or "all" in cleaned:
        return None
    return cleaned


def run_transfer_search(root: Path, args: argparse.Namespace) -> None:
    result = find_similar_problems(
        root,
        args.seed_problem_id,
        status_filter=parse_status_filter(args.status),
        limit=args.limit,
    )
    path = root / "reports" / "analogies" / f"{result['seed_problem_id']}.json"
    print(f"Wrote {path}")
    print(f"Found {result['returned']} similar problems")
    for item in result["items"][:10]:
        print(
            f"{item['problem_id']} similarity={item['similarity_score']} "
            f"next={item['recommended_next_action']}"
        )


def run_add_finding(root: Path, args: argparse.Namespace) -> None:
    finding = record_literature_finding(
        root,
        problem_id=args.problem_id,
        paper_key=args.paper_key,
        title=args.title,
        url=args.url,
        summary=args.summary,
        method_tags=args.method_tag,
        examples=args.example,
        relevance=args.relevance,
    )
    path = root / "reports" / "literature" / "findings" / f"{finding['finding_id']}.json"
    print(f"Wrote {path}")
    print(f"Finding id: {finding['finding_id']}")


def run_pivot_from_finding(root: Path, args: argparse.Namespace) -> None:
    result = pivot_from_literature_finding(
        root,
        args.finding_id,
        status_filter=parse_status_filter(args.status),
        limit=args.limit,
    )
    path = root / "reports" / "pivots" / f"{args.finding_id}.json"
    print(f"Wrote {path}")
    print(f"Found {result['returned']} pivot candidates")
    for item in result["items"][:10]:
        print(
            f"{item['problem_id']} pivot={item['pivot_score']} "
            f"next={item['recommended_next_action']}"
        )


def run_add_example(root: Path, args: argparse.Namespace) -> None:
    statement = read_statement_arg(args.statement, args.statement_file)
    payload = record_math_example(
        root,
        example_id=args.example_id,
        statement=statement,
        source=args.source,
        problem_id=args.problem_id,
        tags=args.tag,
        role=args.role,
    )
    path = root / "kb" / "examples" / f"{payload['example_id']}.json"
    print(f"Wrote {path}")


def run_create_agent_run(root: Path, args: argparse.Namespace) -> None:
    if args.from_triage:
        runs = create_runs_from_triage(
            root,
            agent=args.agent,
            limit=args.limit,
            action_filter=set(args.action) if args.action else None,
        )
        print(f"Created {len(runs)} runs")
        for run in runs:
            print(f"{run['run_id']} {run['agent']} {run.get('problem_id')}")
        return

    run = create_agent_run(
        root,
        agent=args.agent,
        problem_id=args.problem,
        prompt=args.prompt,
        artifacts=args.artifact,
        priority=args.priority,
        metadata={"source": "manual"},
    )
    path = root / "agent_runs" / "inbox" / f"{run['run_id']}.json"
    print(f"Wrote {path}")


def run_list_agent_runs(root: Path, args: argparse.Namespace) -> None:
    runs = list_agent_runs(root, status=args.status)
    for run in runs:
        print(
            f"{run['run_id']} status={run['status']} agent={run['agent']} "
            f"problem={run.get('problem_id')} priority={run.get('priority')}"
        )
    print(f"Total: {len(runs)}")


def run_complete_agent_run(root: Path, args: argparse.Namespace) -> None:
    run = complete_agent_run(
        root,
        args.run_id,
        status=args.status,
        summary=args.summary,
        artifacts=args.artifact,
    )
    path = root / "agent_runs" / "outbox" / f"{run['run_id']}.json"
    print(f"Wrote {path}")


def run_supervisor_step(root: Path, args: argparse.Namespace) -> None:
    result = supervisor_step(root, limit=args.limit)
    print(f"Wrote {root / 'agent_runs' / 'supervisor_step.json'}")
    print(f"Queued: {result['queued_count']} Completed: {result['completed_count']}")
    for run in result["next_runs"]:
        print(f"{run['run_id']} {run['agent']} {run.get('problem_id')}")


def run_execute_agent_run(root: Path, args: argparse.Namespace) -> None:
    run = execute_agent_run(root, args.run_id)
    print(f"Completed {run['run_id']} status={run['status']}")
    for artifact in run.get("result_artifacts", []):
        print(f"artifact: {artifact}")


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
