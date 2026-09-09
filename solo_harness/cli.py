"""Command-line orchestration for the ARC-Bench entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent import CodingAgent
from .model import OpenAIChatClient
from .requirements import RequirementBundle, load_requirements
from .runtime import Runtime
from .validation import Validator
from .workspace import Workspace, scaffold_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jianxian Solo ARC-Bench Harness")
    parser.add_argument("requirements", nargs="?", help="requirement directory or YAML file")
    parser.add_argument("--output-dir", help="generated project directory")
    parser.add_argument("--type", dest="application_type", default="web")
    parser.add_argument("--web-port", type=int)
    parser.add_argument(
        "--smoke-port",
        type=int,
        default=0,
        help="local validation port; 0 chooses an available non-evaluator port",
    )
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime: Runtime | None = None
    try:
        if args.application_type != "web":
            raise ValueError("only --type web is supported")
        requirement_value = args.requirements or os.environ.get("ARCBENCH_TASK_DIR", "")
        output_value = (
            args.output_dir
            or os.environ.get("ARCBENCH_TEMPLATE_DIR", "")
            or os.environ.get("ARCBENCH_OUTPUT_DIR", "")
        )
        if not requirement_value:
            raise ValueError("requirements path is required")
        if not output_value:
            raise ValueError("--output-dir or ARCBENCH_TEMPLATE_DIR is required")

        bundle = load_requirements(requirement_value)
        output_dir = Path(output_value).expanduser().resolve()
        web_port = args.web_port or int(os.environ.get("ARCBENCH_WEB_PORT", "3000"))
        if args.smoke_port and args.smoke_port == web_port:
            raise ValueError("smoke port cannot equal the evaluator web port")

        runtime = Runtime(output_dir)
        runtime.runner_state("running", "Jianxian Solo Harness started")
        runtime.store_requirement_tree(bundle.root)
        runtime.trace(
            "run_started",
            requirements=str(bundle.source),
            output_dir=str(output_dir),
            web_port=web_port,
            dry_run=args.dry_run,
            runtime_backend=runtime.backend,
        )

        template_root = Path(__file__).resolve().parent.parent / "templates" / "web"
        created = scaffold_project(template_root, output_dir)
        runtime.trace("scaffold_ready", created=list(created))
        runtime.checkpoint("scaffold: initialize generated web app")

        validator = Validator(output_dir, smoke_port=args.smoke_port)
        if args.dry_run:
            report = validator.validate()
            runtime.trace("dry_run_validation", report=report.as_dict())
            state = "completed" if report.passed else "failed"
            runtime.runner_state(state, report.summary)
            print(report.summary)
            return 0 if report.passed else 1

        node_ids = [_node_id(node) for node in bundle.actionable_nodes]
        for node_id in node_ids:
            runtime.requirement_state(node_id, "design", "running")
            runtime.requirement_state(node_id, "implement", "running")

        client = OpenAIChatClient.from_env()
        agent = CodingAgent(
            client,
            Workspace(output_dir),
            validator,
            runtime,
            max_turns=max(1, min(args.max_turns, 20)),
        )
        outcome = agent.run(bundle.root)
        _finish_requirement_states(runtime, node_ids, outcome.passed, outcome.report.summary)
        runtime.trace(
            "run_finished",
            passed=outcome.passed,
            turns=outcome.turns,
            changed_files=list(outcome.changed_files),
            report=outcome.report.as_dict(),
            summary=outcome.summary,
        )
        runtime.checkpoint("agent: implement and validate requirements")
        runtime.runner_state(
            "completed" if outcome.passed else "failed", outcome.report.summary
        )
        print(outcome.report.summary)
        return 0 if outcome.passed else 1
    except Exception as exc:  # the runner needs one concise, non-secret failure
        if runtime is not None:
            runtime.trace("run_error", error=str(exc))
            runtime.runner_state("failed", str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _node_id(node: dict) -> str:
    return str(node.get("id") or node.get("req_id") or "").strip()


def _finish_requirement_states(
    runtime: Runtime, node_ids: list[str], passed: bool, message: str
) -> None:
    for node_id in node_ids:
        if passed:
            runtime.requirement_state(node_id, "design", "completed")
            runtime.requirement_state(node_id, "implement", "completed")
            runtime.requirement_state(node_id, "test", "passed", message)
        else:
            runtime.requirement_state(node_id, "implement", "failed", message)
            runtime.requirement_state(node_id, "test", "failed", message)
