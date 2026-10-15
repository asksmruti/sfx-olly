from __future__ import annotations

import argparse

from sfx_olly import help as help_topics


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("help", help="Show detailed help topics")
    p.add_argument("topic", nargs="?", choices=help_topics.topic_names(), metavar="topic",
                   help=f"one of: {', '.join(help_topics.topic_names())}")
    p.set_defaults(handler=show_help, needs_logging=False)


def show_help(args: argparse.Namespace) -> int:
    help_topics.show(args.topic)
    return 0
