import os
import re
import sys
from typing import Annotated

from l2l import Lane
from typer import Argument, Typer

from ..core import Core
from ..settings import Settings
from .display import Display

app = Typer()


@app.command()
def run(
    queue_name: Annotated[
        str,
        Argument(
            is_eager=False,
        ),
    ] = "",
):
    sys.path.insert(0, os.getcwd())

    if queue_name.strip() != "":
        os.environ["QUEUE_NAME"] = queue_name

        Core.start()
        return

    _ = [
        lane
        for lane_directory in Settings.get().lane_directories
        for lane in Lane.load(lane_directory)
    ]

    # Draw the display.

    queue_name = Display().run()

    if not queue_name:
        return

    # Run the program again.

    os.environ["QUEUE_NAME"] = queue_name

    Core.start()


@app.command()
def init():
    os.mkdir("lanes")

    with open("lanes/lane.py", "wb") as f:
        with open("./example_starter.py", "rb") as f2:
            f.write(f2.read())


@app.command()
def new(name: str):
    lane_directories = [*Settings.get().lane_directories]

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

        with open("lane_filepath", "w") as f:
            with open("./example_lane.py", "r") as f2:
                f.write(
                    f2.read().replace(
                        "LANE_NAME",
                        name,
                    )
                )

        return

    raise Exception(f"Lane '{name}' already exists!")
