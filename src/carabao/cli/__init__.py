import os
import re
import sys

import typer
from typing_extensions import Annotated

from carabao import form

from ..cfg.secret_cfg import SECRET_CFG
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
    test_mode: Annotated[
        bool,
        typer.Option(
            "--test-mode",
            "-t",
            help="Run the pipeline in testing mode.",
        ),
    ] = None,  # type: ignore
):
    """
    Run the pipeline in development mode.

    If a lane name is provided, runs that specific lane.
    Otherwise, displays a UI to select a lane to run.

    Args:
        name: The name of the lane to run.
    """
    sys.path.insert(0, os.getcwd())

    cfg_test_mode = test_mode if test_mode is not None else SECRET_CFG.test_mode

    if name.strip() != "":
        Core.start(
            name=name,
            dev_mode=True,
            test_mode=cfg_test_mode,
        )
        return

    Core.initialize(
        name=name,
        dev_mode=True,
        test_mode=cfg_test_mode,
    )

    Core.load_lanes(Settings.get())

    # Draw the display.

    result = cmd_dev.Display().run()

    if result is None:
        return

    SECRET_CFG.write(
        section=SECRET_CFG.LAST_RUN,
        key=SECRET_CFG.QUEUE_NAME,
        value=result.name,
    )

    SECRET_CFG.write(
        section=SECRET_CFG.TEST_MODE,
        key=SECRET_CFG.TEST_MODE,
        value=str(result.test_mode),
    )

    for key, value in result.raw_form.items():
        SECRET_CFG.write(
            section=f"{result.name}{SECRET_CFG.FORM}",
            key=key,
            value=str(value),
        )

    SECRET_CFG.save()

    _form = form._get_form(result.lane)

    if _form is not None:
        for key, value in result.form.items():
            setattr(_form, key, value)
            setattr(form.F, key, value)

    # Run the program again.

    Core.start(
        name=result.name,
        dev_mode=True,
        test_mode=result.test_mode,
    )


@app.command(
    help="Run the pipeline in production mode.",
)
def run(
    name: Annotated[
        str,
        typer.Argument(
            help="The name of the lane to run.",
            is_eager=False,
        ),
    ] = "",
):
    """
    Run the pipeline in production mode.

    This starts the Core with the default settings suitable for production.
    """
    sys.path.insert(0, os.getcwd())
    Core.start(
        name=name if name else None,
        dev_mode=False,
    )


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
    Create a new lane with the given name.

    This command guides the user through creating a new lane by:
    1. Checking for valid lane directories from settings
    2. Prompting for lane name and directory if not provided
    3. Converting the lane name to appropriate filename and class name formats
    4. Creating the lane file with template content

    If no lane directories are configured, the command will display an error.
    """
    sys.path.insert(0, os.getcwd())

    lane_directories = [
        *map(
            lambda x: x.replace(".", "/"),
            Settings.get().value_of("LANE_DIRECTORIES"),
        ),
    ]

    if not lane_directories:
        typer.secho(
            "No lane directories found!",
            fg=typer.colors.RED,
        )
        return
        # raise Exception("Lane directory not found!")

    display = cmd_new.Display()
    display.default_lane_name = name.strip() or "MyLane"
    display.default_lane_directory = lane_directories[0]

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

    typer.secho(
        f"Lane '{class_name}' already exists!",
        fg=typer.colors.RED,
    )
    # raise Exception(f"Lane '{class_name}' already exists!")
