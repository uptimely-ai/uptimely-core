"""Entry point for the Uptimely command-line interface."""

import argparse
import logging
import sys

from uptimely.cli import engine, examples, explorer, project, spec

download_examples = examples.download_examples
serve_explorer = explorer.serve_explorer


def main() -> None:
    """Run the Uptimely command-line interface."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
    parser = argparse.ArgumentParser(prog="uptimely")
    commands = parser.add_subparsers(dest="command", required=True)
    examples.configure_parser(commands.add_parser("examples", help="Manage example projects"))
    explorer.configure_parser(
        commands.add_parser("explorer", help="Explore spec, lineage, and execution plans")
    )
    spec.configure_parser(
        commands.add_parser("spec", help="Inspect specs and feature dependencies")
    )
    project.configure_parser(commands.add_parser("project", help="Build project resources"))
    engine.configure_parser(commands.add_parser("engine", help="Run analytics workflows"))
    project.configure_build_parser(
        commands.add_parser("build", help="Build a complete project bundle")
    )
    engine.configure_run_parser(commands.add_parser("run", help="Run an analytics workflow"))
    explorer.configure_serve_parser(
        commands.add_parser("explore", help="Serve the Analytics Explorer website")
    )
    args = parser.parse_args()
    if args.command == "examples":
        examples.run(args, parser)
    elif args.command == "explorer":
        explorer.run(args, parser)
    elif args.command == "spec":
        spec.run(args, parser)
    elif args.command == "project":
        project.run(args, parser)
    elif args.command in ("engine", "run"):
        engine.run(args, parser)
    elif args.command == "build":
        project.run(args, parser)
    elif args.command == "explore":
        explorer.run(args, parser)


if __name__ == "__main__":
    main()
