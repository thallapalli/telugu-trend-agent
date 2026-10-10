"""CLI: python -m telugu_agent {generate|generate-heritage|generate-hacks|approvals|dry-run}"""
import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(prog="telugu_agent")
    parser.add_argument("command", choices=["generate", "generate-heritage", "generate-hacks", "approvals", "dry-run"])
    args = parser.parse_args()

    # These must be set before config is imported (it picks the data directory).
    if args.command == "dry-run":
        os.environ["DRY_RUN"] = "1"
        os.environ["AUTO_PUBLISH"] = "1"  # exercise the publish path too (prints only)

    from . import pipeline

    if args.command == "dry-run":
        pipeline.generate_all()
        pipeline.process_approvals()
    elif args.command == "generate":
        pipeline.generate_all()  # both modes
    elif args.command == "generate-heritage":
        pipeline.generate()
    elif args.command == "generate-hacks":
        pipeline.generate_hacks()
    else:
        pipeline.process_approvals()
    return 0


if __name__ == "__main__":
    sys.exit(main())
