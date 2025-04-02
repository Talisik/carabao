from argparse import _SubParsersAction

from ..core import Core


def _main(args):
    pass


def do(subparsers: _SubParsersAction):
    parser = subparsers.add_parser(
        "run",
        help="Starts the framework.",
    )
    parser.add_argument(
        "queue_name",
        type=str,
        default="",
        nargs="?",
    )
    parser.set_defaults(func=_main)

    Core.start()
