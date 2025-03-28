from abc import ABC, abstractmethod
import curses
from dataclasses import dataclass
from typing import Any, Callable, List, final


@dataclass(frozen=True)
class CursesText:
    text: str
    x: int
    y: int
    pair_number: int


@dataclass(frozen=True)
class CursesButton(CursesText):
    hover_text: str
    hover_pair_number: int
    callback: Callable[[], Any]


class CursesList(ABC):
    @property
    def width(self):
        return self.__stdscr.getmaxyx()[1]

    @property
    def height(self):
        return self.__stdscr.getmaxyx()[0]

    @property
    def stdscr(self):
        return self.__stdscr

    @final
    def exit(self):
        self.__exit = True

    @final
    def run(self):
        return curses.wrapper(self.__run)

    @final
    def add(self, item: CursesText):
        if isinstance(item, CursesButton):
            self.__buttons.append(item)

        else:
            self.__texts.append(item)

    @abstractmethod
    def setup(self):
        pass

    @final
    def __draw(self):
        self.__stdscr.clear()

        for item in self.__texts:
            color_pair = curses.color_pair(item.pair_number)
            self.__stdscr.attron(color_pair)
            self.__stdscr.addstr(
                item.y,
                item.x,
                item.text,
            )
            self.__stdscr.attroff(color_pair)

        for index, item in enumerate(self.__buttons):
            selected = index == self.selected_button_index
            color_pair = curses.color_pair(
                item.hover_pair_number if selected else item.pair_number
            )
            self.__stdscr.attron(color_pair)
            self.__stdscr.addstr(
                item.y,
                item.x,
                item.hover_text if selected else item.text,
            )
            self.__stdscr.attroff(color_pair)

        self.__stdscr.refresh()

    @final
    def __run(self, stdscr: "curses._CursesWindow"):
        self.__stdscr = stdscr
        self.__texts: List[CursesText] = []
        self.__buttons: List[CursesButton] = []
        self.__exit = False

        self.selected_button_index: int = 0

        self.setup()

        length = len(self.__buttons)

        self.__buttons.sort(key=lambda item: item.y)

        self.__draw()

        while True:
            key = stdscr.getch()

            if key == curses.KEY_UP:
                self.selected_button_index = (self.selected_button_index - 1) % length
            elif key == curses.KEY_DOWN:
                self.selected_button_index = (self.selected_button_index + 1) % length
            elif key == ord("\n"):
                button = self.__buttons[self.selected_button_index]

                result = button.callback()

                if self.__exit:
                    break

            self.__draw()

        return result
