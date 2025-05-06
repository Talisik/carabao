import os

import typer

from carabao.helpers.prompter import Prompter

from ..cfg.secret_cfg import SecretCFG


class ShouldContinue(Prompter.Component[bool]):
    """
    Checks if initialization should continue.

    Confirms with the user if a carabao.cfg file already exists,
    otherwise automatically proceeds.
    """

    priority_number = 3

    def _query(self) -> bool:
        if self["skip"]:
            return True

        if not os.path.exists("carabao.cfg"):
            return True

        return typer.confirm(
            typer.style(
                "This directory is already initialized. Moooove forward anyway?",
                fg=typer.colors.YELLOW,
            ),
        )


class UseSrc(Prompter.Component[bool]):
    """
    Determines if the project should use a src directory structure.

    Prompts the user to decide whether to use a /src directory for the project,
    unless skip is enabled.
    """

    priority_number = 2

    def _query(self) -> bool:
        return not self["skip"] and typer.confirm(
            typer.style(
                "Use /src folder as the root directory?",
                fg=typer.colors.BRIGHT_BLUE,
            ),
            default=False,
        )


class LaneDirectory(Prompter.Component[str]):
    """
    Determines the directory where lanes will be stored.

    Creates the lane directory if it doesn't exist.
    """

    priority_number = 1

    def _query(self) -> str:
        lane_directory: str = "src/lanes" if self["use_src"] else "lanes"
        lane_directory = (
            lane_directory
            if self["skip"]
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

        return lane_directory


class NewStarterLane(Prompter.Component):
    """
    Creates a starter lane file in the specified lane directory.

    Copies the sample starter lane file to the project's lane directory.
    """

    def _do(self):
        with open(f"{self['lane_directory']}/my_lane.py", "wb") as f:
            with open(
                os.path.join(
                    self["root_path"],
                    "sample/basic.py",
                ),
                "rb",
            ) as f2:
                f.write(f2.read())

        typer.echo(
            typer.style(
                "Created my_lane.py.",
                fg=typer.colors.GREEN,
            ),
        )


class NewSettings(Prompter.Component):
    """
    Creates a settings.py file for the project.

    Copies the sample settings file and replaces placeholders with
    the appropriate lane directory path.
    """

    def _do(self):
        with open(
            f"{'src/' if self['use_src'] else ''}settings.py",
            "w",
        ) as f:
            with open(
                os.path.join(
                    self["root_path"],
                    "sample.settings.py",
                ),
                "r",
            ) as f2:
                f.write(
                    f2.read().replace(
                        "LANE_DIRECTORY",
                        self["lane_directory"].replace("/", "."),
                    )
                )

        typer.echo(
            typer.style(
                "Created settings.py.",
                fg=typer.colors.GREEN,
            ),
        )


class NewCfg(Prompter.Component):
    """
    Creates a carabao.cfg configuration file.

    Sets up the initial configuration with the appropriate settings path.
    """

    def _do(self):
        settings_path = "src.settings" if self["use_src"] else "settings"

        with open("carabao.cfg", "w") as f:
            with open(
                os.path.join(
                    self["root_path"],
                    "sample.carabao.cfg",
                ),
                "r",
            ) as f2:
                f.write(
                    f2.read().format(
                        SETTINGS_PATH=settings_path,
                    )
                )

        typer.echo(
            typer.style(
                "Created carabao.cfg.",
                fg=typer.colors.GREEN,
            ),
        )


class NewEnv(Prompter.Component):
    """
    Creates environment files for development and release.

    Creates .env.development and .env.release files if they don't exist.
    """

    def _do(self):
        if not os.path.exists(".env.development"):
            with open(".env.development", "wb") as f:
                f.write(b"")

        typer.echo(
            typer.style(
                "Created .env.development.",
                fg=typer.colors.GREEN,
            ),
        )

        if not os.path.exists(".env.release"):
            with open(".env.release", "wb") as f:
                f.write(b"")
        typer.echo(
            typer.style(
                "Created .env.release.",
                fg=typer.colors.GREEN,
            ),
        )


class UpdateGitIgnore(Prompter.Component[bool]):
    """
    Updates the .gitignore file to include the secret configuration file.

    Adds the SecretCFG filepath to .gitignore if it doesn't already exist.
    """

    def _query(self) -> bool:
        return self["skip"] or typer.confirm(
            typer.style(
                "Update .gitignore to include carabao-specific files?",
                fg=typer.colors.BRIGHT_BLUE,
            ),
            default=True,
        )

    def _do(self):
        if not self["update_gitignore"]:
            return

        ignore_entry = SecretCFG.filepath

        if not os.path.exists(".gitignore"):
            return

        with open(".gitignore", "r") as f:
            if ignore_entry in f.read():
                return

        with open(".gitignore", "a") as f:
            f.write(f"\n{ignore_entry}")

        typer.echo(
            typer.style(
                "Updated .gitignore.",
                fg=typer.colors.GREEN,
            ),
        )
