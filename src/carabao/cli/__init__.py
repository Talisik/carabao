import os
import sys

from l2l import Lane
from typer import Typer

from ..core import Core
from ..settings import Settings
from .display import Display

app = Typer()


@app.command()
def run(
    queue_name: str = "",
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
