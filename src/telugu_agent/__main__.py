"""CLI: python -m telugu_agent {generate|approvals|dry-run}"""
import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="telugu_agent")
    parser.add_argument("command", choices=["generate", "approvals", "dry-run"])
    args = parser.parse_args()

    # These must be set before config is imported (it picks the data directory).
    if args.command == "dry-run":
        os.environ["DRY_RUN"] = "1"
        os.environ["AUTO_PUBLISH"] = "1"  # exercise the publish path too (prints only)

    from . import pipeline

    if args.command == "dry-run":
        pipeline.generate()
        pipeline.process_approvals()
    elif args.command == "generate":
        pipeline.generate()
    else:
        pipeline.process_approvals()
    return 0


if __name__ == "__main__":
    sys.exit(main())
