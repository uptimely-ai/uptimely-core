"""Command-line orchestration for building generated project resources."""

import argparse
import pathlib

from uptimely import project
from uptimely.cli import common, plan, spec


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the project build action."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build",
        help="Build spec JSON and compile an execution plan without running spec",
    )
    spec.configure_build_source_arguments(build)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build spec followed by the execution plan, reporting stage failures."""
    root = args.project_root or pathlib.Path.cwd()
    spec_path = common.project_path(None, args.project_root, project.SPEC_JSON_FILE)
    plan_path = common.project_path(None, args.project_root, project.EXECUTION_PLAN_FILE)
    try:
        written_spec = spec.build_spec(args.entrypoint, spec_path, root, source=args.spec)
    except (OSError, ValueError, ImportError, AttributeError, TypeError, SyntaxError) as error:
        parser.exit(1, f"uptimely: error: Spec build failed: {error}\n")
    print(f"Spec written to {written_spec}")
    try:
        execution_plan = plan.compile_plan(spec_path, root)
        written_plan = execution_plan.export_json(plan_path)
    except (OSError, ValueError, ImportError, AttributeError, TypeError, SyntaxError) as error:
        parser.exit(1, f"uptimely: error: Execution plan build failed: {error}\n")
    print(f"Compiled {len(execution_plan.callables)} callables")
    print(f"Execution plan: {written_plan}")
