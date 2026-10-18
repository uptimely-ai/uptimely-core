"""Entry point for the Uptimely command-line interface."""

import argparse

from uptimely.cli import engine, examples, explorer, plan, project, spec

download_examples = examples.download_examples
build_explorer = explorer.build_explorer
serve_explorer = explorer.serve_explorer


def main() -> None:
    """Run the Uptimely command-line interface."""
    parser = argparse.ArgumentParser(prog="uptimely")
    commands = parser.add_subparsers(dest="command", required=True)
    examples.configure_parser(commands.add_parser("examples", help="Manage example projects"))
    explorer.configure_parser(
        commands.add_parser("explorer", help="Explore spec, lineage, and execution plans")
    )
    spec.configure_parser(commands.add_parser("spec", help="Export and inspect spec"))
    plan.configure_parser(commands.add_parser("plan", help="Build execution plans"))
    project.configure_parser(commands.add_parser("project", help="Build project resources"))
    engine.configure_parser(commands.add_parser("engine", help="Run analytics workflows"))
    args = parser.parse_args()
    if args.command == "examples":
        examples.run(args, parser)
    elif args.command == "explorer":
        explorer.run(args, parser)
    elif args.command == "spec":
        spec.run(args, parser)
    elif args.command == "plan":
        plan.run(args, parser)
    elif args.command == "project":
        project.run(args, parser)
    else:
        engine.run(args, parser)


if __name__ == "__main__":
    main()
