"""Command-line orchestration for building generated project resources."""

import argparse
import pathlib

from uptimely import project
from uptimely.cli import analytics, common, plan


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the project build action."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build",
        help="Build analytics JSON and compile an execution plan without running analytics",
    )
    analytics.configure_build_source_arguments(build)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build analytics followed by the execution plan, reporting stage failures."""
    root = args.project_root or pathlib.Path.cwd()
    analytics_path = common.project_path(None, args.project_root, project.ANALYTICS_JSON_FILE)
    plan_path = common.project_path(None, args.project_root, project.EXECUTION_PLAN_FILE)
    try:
        written_analytics = analytics.build_analytics(
            args.entrypoint, analytics_path, root, source=args.analytics
        )
    except (OSError, ValueError, ImportError, AttributeError, TypeError, SyntaxError) as error:
        parser.exit(1, f"uptimely: error: Analytics build failed: {error}\n")
    print(f"Analytics written to {written_analytics}")
    try:
        execution_plan = plan.compile_plan(analytics_path, root)
        written_plan = execution_plan.export_json(plan_path)
    except (OSError, ValueError, ImportError, AttributeError, TypeError, SyntaxError) as error:
        parser.exit(1, f"uptimely: error: Execution plan build failed: {error}\n")
    print(f"Compiled {len(execution_plan.callables)} callables")
    print(f"Execution plan: {written_plan}")
