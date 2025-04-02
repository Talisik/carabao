import curses
import os
from argparse import _SubParsersAction

from l2l import Lane

from ..cfg.secret_cfg import SecretCFG
from ..core import Core
from ..curses import CursesButton, CursesList, CursesText
from ..settings import Settings


class Display(CursesList):
    def __add_item(
        self,
        index: int,
        queue_name: str,
        selected: bool,
    ):
        def callback():
            self.exit()

            return queue_name

        self.add(
            CursesButton(
                text=f"  {queue_name}",
                hover_text=f"> {queue_name}",
                x=2,
                y=3 + index,
                pair_number=2,
                hover_pair_number=3,
                callback=callback,
            )
        )

        if selected:
            self.selected_button_index = index

    def setup(self):
        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_RED)
        self.stdscr.bkgd(" ", curses.color_pair(1))

        self.add(
            CursesText(
                text="Carabao",
                x=2,
                y=1,
                pair_number=1,
            )
        )

        cfg = SecretCFG()

        queue_names = [*cfg.primary_lanes]

        if not any(queue_names):
            raise Exception("No lanes found!")

        last_run_queue_name = cfg.last_run_queue_name

        for index, queue_name in enumerate(queue_names):
            self.__add_item(
                index,
                queue_name,
                queue_name == last_run_queue_name,
            )

        self.add(
            CursesButton(
                text="  Exit",
                hover_text="> Exit",
                x=2,
                y=self.height - 2,
                pair_number=4,
                hover_pair_number=5,
                callback=self.exit,
            )
        )


def _main(args):
    queue_name: str = args.queue_name

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
