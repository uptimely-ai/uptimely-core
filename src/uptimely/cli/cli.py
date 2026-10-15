"""Entry point for the Uptimely command-line interface."""

import argparse

from uptimely.cli import analytics, engine, examples, explorer, plan

download_examples = examples.download_examples
build_explorer = explorer.build_explorer
serve_explorer = explorer.serve_explorer


def main() -> None:
    """Run the Uptimely command-line interface."""
    parser = argparse.ArgumentParser(prog="uptimely")
    commands = parser.add_subparsers(dest="command", required=True)
    examples.configure_parser(commands.add_parser("examples", help="Manage example projects"))
    explorer.configure_parser(
        commands.add_parser(
            "explorer", help="Explore analytics specifications, lineage, and execution plans"
        )
    )
    analytics.configure_parser(
        commands.add_parser("analytics", help="Export and inspect analytics")
    )
    plan.configure_parser(commands.add_parser("plan", help="Build execution plans"))
    engine.configure_parser(commands.add_parser("engine", help="Run analytics workflows"))
    args = parser.parse_args()
    if args.command == "examples":
        examples.run(args, parser)
    elif args.command == "explorer":
        explorer.run(args, parser)
    elif args.command == "analytics":
        analytics.run(args, parser)
    elif args.command == "plan":
        plan.run(args, parser)
    else:
        engine.run(args, parser)


if __name__ == "__main__":
    main()
