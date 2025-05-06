import os
import re
import sys

import typer
from typing_extensions import Annotated

from ..cfg.secret_cfg import SecretCFG
from ..constants import C
from ..core import Core
from ..helpers.prompter import Prompter
from ..settings import Settings
from . import cmd_dev, cmd_new, init_prompter

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
    """
    Run the pipeline in development mode.

    If a lane name is provided, runs that specific lane.
    Otherwise, displays a UI to select a lane to run.

    Args:
        name: The name of the lane to run.
    """
    print("\033[93m⚠️ Development Mode ⚠️\033[0m\n")

    sys.path.insert(0, os.getcwd())

    if name.strip() != "":
        C._dev_mode(name)

        Core.start()
        return

    C._dev_mode("")

    Core.load_lanes(Settings.get())

    # Draw the display.

    name = cmd_dev.Display().run()  # type: ignore

    if not name:
        return

    cfg = SecretCFG()

    cfg.write(
        section=cfg.LAST_RUN,
        key=cfg.QUEUE_NAME,
        value=name,
    )
    cfg.save()

    # Run the program again.

    C._dev_mode(name)

    Core.start()


@app.command(
    help="Run the pipeline in production mode.",
)
def run():
    """
    Run the pipeline in production mode.

    This starts the Core with the default settings suitable for production.
    """
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
    """
    Initialize a new carabao project.

    Creates the necessary directory structure and sample files.

    Args:
        skip: Whether to skip all interactive prompts.
    """
    prompter = Prompter()

    prompter.set("skip", skip)
    prompter.set("root_path", os.path.dirname(__file__))

    prompter.add(
        "should_continue",
        init_prompter.ShouldContinue(),
    )

    prompter.add(
        "use_src",
        init_prompter.UseSrc(),
    )

    prompter.add(
        "lane_directory",
        init_prompter.LaneDirectory(),
    )

    prompter.add(
        "new_starter_lane",
        init_prompter.NewStarterLane(),
    )

    prompter.add(
        "new_settings",
        init_prompter.NewSettings(),
    )

    prompter.add(
        "new_cfg",
        init_prompter.NewCfg(),
    )

    prompter.add(
        "new_env",
        init_prompter.NewEnv(),
    )

    prompter.add(
        "update_gitignore",
        init_prompter.UpdateGitIgnore(),
    )

    prompter.query()
    prompter.do()

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
    ] = "",
):
    """
    Create a new lane from a template.

    Creates a new lane Python file using the provided name. The name will be
    converted to snake_case for the filename and PascalCase for the class name.
    If no name is provided, displays a UI to select a template type first.

    Args:
        name: The name of the lane to create.

    Raises:
        Exception: If lane directories are not found or the lane already exists.
    """
    sys.path.insert(0, os.getcwd())

    lane_directories = [
        *map(
            lambda x: x.replace(".", "/"),
            Settings.get().value_of("LANE_DIRECTORIES"),
        ),
    ]

    if not lane_directories:
        raise Exception("Lane directory not found!")

    display = cmd_new.Display()
    display.lane_name = name
    display.lane_directory = lane_directories[0]

    result: cmd_new.Item = display.run()  # type: ignore

    if not result:
        return

    lane_directories = [result.lane_directory]
    filename = re.sub(
        r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z0-9])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)",
        "_",
        result.lane_name,
    ).lower()
    class_name = "".join(word.capitalize() for word in filename.split("_"))

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
            f.write(result.content)

        typer.echo(
            typer.style(
                f"Lane '{class_name}' created successfully!",
                fg=typer.colors.GREEN,
            )
        )
        return

    raise Exception(f"Lane '{class_name}' already exists!")
