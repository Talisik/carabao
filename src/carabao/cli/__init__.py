import argparse

from ..core import Core
from . import run


def cli():
    Core.startup = "DISABLED"  # Disable startup.
    Core.config = "DISABLED"  # Disable config.

    parser = argparse.ArgumentParser(
        description="Carabao.",
    )
    subparsers = parser.add_subparsers(
        dest="cli",
    )

    run.do(subparsers)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
        return

    parser.print_help()
