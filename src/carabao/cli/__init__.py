import os
import re
import sys
from typing import Annotated

import typer

from ..core import Core
from ..settings import Settings
from .display import Display

app = typer.Typer()


@app.command(
    help="Run the pipeline in development mode.",
)
def dev(
    name: Annotated[
        str,
        typer.Argument(
            help="The name of the lane to run.",
            is_eager=False,
        ),
    ] = "",
):
    sys.path.insert(0, os.getcwd())

    if name.strip() != "":
        os.environ["QUEUE_NAME"] = name

        Core.start()
        return

    Core.load_lanes(Settings.get())

    # Draw the display.

    name = Display().run()

    if not name:
        return

    # Run the program again.

    os.environ["QUEUE_NAME"] = name

    Core.start()


@app.command(
    help="Run the pipeline in production mode.",
)
def run():
    sys.path.insert(0, os.getcwd())
    Core.start()


@app.command(
    help="Initialize the project.",
)
def init(
    skip: Annotated[
        bool,
        typer.Option(
            "--skip",
            "-s",
            help="Skip all prompts.",
        ),
    ] = False,
):
    if not skip and os.path.exists("carabao.cfg"):
        if not typer.confirm(
            typer.style(
                "This directory is already initialized. Moooove forward anyway?",
                fg=typer.colors.YELLOW,
            ),
        ):
            return

    use_src = not skip and typer.confirm(
        typer.style(
            "Use /src?",
            fg=typer.colors.BRIGHT_BLUE,
        ),
        default=False,
    )

    lane_directory: str = "src/lanes" if use_src else "lanes"
    lane_directory = (
        lane_directory
        if not skip
        else typer.prompt(
            typer.style(
                "Lane Directory",
                fg=typer.colors.BRIGHT_BLUE,
            ),
            default=lane_directory,
        )
    )

    if not os.path.exists(lane_directory):
        os.makedirs(lane_directory)

    root_path = os.path.dirname(__file__)

    with open(f"{lane_directory}/starter_lane.py", "wb") as f:
        with open(
            os.path.join(
                root_path,
                "sample_starter.py",
            ),
            "rb",
        ) as f2:
            f.write(f2.read())

    with open(f"{'src/' if use_src else ''}settings.py", "w") as f:
        with open(
            os.path.join(
                root_path,
                "sample_settings.py",
            ),
            "r",
        ) as f2:
            f.write(
                f2.read().replace(
                    "LANE_DIRECTORY",
                    lane_directory.replace("/", "."),
                )
            )

    with open("carabao.cfg", "w") as f:
        f.write(
            f"""[directories]
settings = {"src." if use_src else ""}settings
"""
        )

    typer.echo(
        typer.style(
            "Carabao initialized.",
            fg=typer.colors.GREEN,
        )
    )


@app.command(
    help="Create a new lane.",
)
def new(
    name: Annotated[
        str,
        typer.Argument(help="The name of the lane to create."),
    ],
):
    lane_directories = [
        *Settings.get().value_of("LANE_DIRECTORIES"),
    ]

    if not lane_directories:
        raise Exception("Lane directory not found!")

    filename = re.sub(
        r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z0-9])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)",
        "_",
        name,
    ).lower()
    name = "".join(word.capitalize() for word in filename.split("_"))

    for lane_directory in lane_directories:
        if not os.path.exists(lane_directory):
            os.makedirs(lane_directory)

        lane_filepath = os.path.join(
            lane_directory,
            f"{filename}.py",
        )

        if os.path.exists(lane_filepath):
            continue

        with open(lane_filepath, "w") as f:
            with open(
                os.path.join(
                    os.path.dirname(__file__),
                    "sample_lane.py",
                ),
                "r",
            ) as f2:
                f.write(
                    f2.read().replace(
                        "LANE_NAME",
                        name,
                    )
                )

        return

    raise Exception(f"Lane '{name}' already exists!")
