import os

import typer

from ..cfg.secret_cfg import SecretCFG


def should_continue(skip: bool):
    """
    Determine if initialization should continue.

    Args:
        skip: If True, skip confirmation prompts

    Returns:
        bool: True if initialization should continue, False otherwise
    """
    if skip:
        return True

    if not os.path.exists("carabao.cfg"):
        return True

    return typer.confirm(
        typer.style(
            "This directory is already initialized. Moooove forward anyway?",
            fg=typer.colors.YELLOW,
        ),
    )


def use_src(skip: bool):
    """
    Determine if the /src directory should be used.

    Args:
        skip: If True, skip confirmation prompts

    Returns:
        bool: True if /src should be used, False otherwise
    """
    return not skip and typer.confirm(
        typer.style(
            "Use /src?",
            fg=typer.colors.BRIGHT_BLUE,
        ),
        default=False,
    )


def lane_directory(skip: bool, use_src: bool):
    """
    Determine and create the lane directory.

    Args:
        skip: If True, skip confirmation prompts
        use_src: If True, use /src directory structure

    Returns:
        str: Path to the lane directory
    """
    lane_directory: str = "src/lanes" if use_src else "lanes"
    lane_directory = (
        lane_directory
        if skip
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


def new_starter_lane(
    root_path: str,
    lane_directory: str,
):
    """
    Create a new starter lane file.

    Args:
        root_path: Root path of the application
        lane_directory: Directory where lanes are stored
    """
    with open(f"{lane_directory}/starter_lane.py", "wb") as f:
        with open(
            os.path.join(
                root_path,
                "sample_starter.py",
            ),
            "rb",
        ) as f2:
            f.write(f2.read())


def new_settings(
    use_src: bool,
    root_path: str,
    lane_directory: str,
):
    """
    Create a new settings file.

    Args:
        use_src: If True, place settings in src directory
        root_path: Root path of the application
        lane_directory: Directory where lanes are stored
    """
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


def new_cfg(
    use_src: bool,
):
    """
    Create a new configuration file.

    Args:
        use_src: If True, reference settings in src directory
    """
    with open("carabao.cfg", "w") as f:
        f.write(
            f"""[directories]
settings = {"src." if use_src else ""}settings
"""
        )


def new_env():
    """
    Create new environment files if they don't exist.
    """
    if not os.path.exists(".env.development"):
        with open(".env.development", "wb") as f:
            f.write(b"")

    if not os.path.exists(".env.release"):
        with open(".env.release", "wb") as f:
            f.write(b"")


def update_gitignore():
    """
    Update .gitignore to include the secret configuration file.

    Asks for confirmation before updating.
    """
    ok = typer.confirm(
        typer.style(
            "Update .gitignore?",
            fg=typer.colors.BRIGHT_BLUE,
        ),
        default=True,
    )

    if not ok:
        return

    ignore_entry = SecretCFG.filepath

    if not os.path.exists(".gitignore"):
        return

    with open(".gitignore", "r") as f:
        if ignore_entry in f.read():
            return

    with open(".gitignore", "a") as f:
        f.write(f"\n{ignore_entry}")
