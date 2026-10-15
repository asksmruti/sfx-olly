"""CLI entry point: `sfx-olly <command>` or `python -m sfx_olly <command>`."""

from __future__ import annotations

import argparse
import logging
import sys

from pydantic import ValidationError

from sfx_olly import __version__
from sfx_olly.cli import alerts, data, help_cmd, metadata, webhook
from sfx_olly.cli.output import print_error
from sfx_olly.config import get_logging_settings, known_secrets
from sfx_olly.exceptions import SplunkOllyError
from sfx_olly.logging_config import setup_logging

logger = logging.getLogger(__name__)

COMMAND_MODULES = (metadata, data, alerts, webhook, help_cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sfx-olly",
        description="Splunk Observability Cloud (SignalFx) CLI: metrics, SignalFlow, alerts, webhooks.",
        epilog="Run 'sfx-olly help' for guides, or 'sfx-olly <command> -h' for options.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-o", "--output", choices=["table", "json"], default="table", help="output format"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print API endpoints, request bodies and timings"
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    for module in COMMAND_MODULES:
        module.register(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 0

    try:
        if getattr(args, "needs_logging", True):
            log = get_logging_settings()
            setup_logging(log.level, log.format, known_secrets())
            if args.verbose:
                logging.getLogger("sfx_olly.requests").setLevel(logging.DEBUG)
        return args.handler(args)
    except ValidationError as exc:
        print_error(_format_config_error(exc))
        return 2
    except ValueError as exc:
        print_error(f"Invalid input: {exc}")
        return 2
    except SplunkOllyError as exc:
        print_error(str(exc))
        return 1
    except KeyboardInterrupt:
        return 130


def _format_config_error(exc: ValidationError) -> str:
    # Never include `input` values: they may contain secrets.
    lines = [f"Configuration error in {exc.title}:"]
    for error in exc.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in error["loc"]) or "settings"
        lines.append(f"  - {location}: {error['msg']}")
    lines.append("Check your environment variables or .env file ('sfx-olly help config').")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
