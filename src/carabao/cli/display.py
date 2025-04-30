import inspect
import os

from l2l import Lane
from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Label

from ..cfg.secret_cfg import SecretCFG


class Display(App):
    """A Textual app to display and select lanes."""

    BINDINGS = [
        Binding("up", "focus_previous", "Move up"),
        Binding("down", "focus_next", "Move down"),
        Binding("escape", "exit_app", "Exit"),
    ]

    CSS_PATH = os.path.join(
        os.path.dirname(__file__),
        "display.tcss",
    )

    def __init__(self):
        super().__init__()
        self.current_index = 0
        self.lane_buttons = []
        self.lanes = {}
        self.docstring_widget = None

    def compose(self):
        """Create and arrange widgets."""
        # Main layout container with horizontal arrangement
        with Vertical():
            with Horizontal():
                # Scrollable container for lane buttons
                with ScrollableContainer(id="lanes-container"):
                    self.lanes = {
                        lane.first_name(): lane
                        for lane in Lane.available_lanes()
                        if lane.primary() and not lane.hidden()
                    }
                    queue_names = sorted(self.lanes.keys())

                    if not any(queue_names):
                        raise Exception("No lanes found!")

                    cfg = SecretCFG()
                    last_run_queue_name = cfg.last_run_queue_name

                    for i, queue_name in enumerate(queue_names):
                        button = Button(
                            queue_name,
                            classes="lane-button",
                            id=f"lane-{i}",
                        )

                        if queue_name == last_run_queue_name:
                            self.current_index = i
                            button.focus()

                        self.lane_buttons.append(button)
                        yield button

                # Container for docstring (side by side with lanes)
                with Container(id="info-container"):
                    yield Label(
                        "Name",
                        classes="info-label",
                    )

                    self.name_widget = Label(
                        "",
                        classes="info-widget",
                    )

                    yield self.name_widget
                    yield Label(
                        "Queue Names",
                        classes="info-label",
                    )

                    self.queue_names_widget = Label(
                        "",
                        classes="info-widget",
                    )

                    yield self.queue_names_widget
                    yield Label(
                        "Documentation",
                        classes="info-label",
                    )

                    self.docstring_widget = Label(
                        "",
                        id="docstring",
                        classes="info-widget",
                    )

                    yield self.docstring_widget
                    yield Label(
                        "Process Tree",
                        classes="info-label",
                    )

                    self.sub_lanes_widget = Label(
                        "",
                        classes="info-widget",
                    )

                    yield self.sub_lanes_widget

            # Container for exit button at bottom right
            with Horizontal(id="navi-container"):
                yield Button(
                    "\\[Enter] Run",
                    id="run",
                )

                yield Button(
                    "\\[Esc] Exit",
                    id="exit",
                )

        # Update docstring for initially focused button
        if self.lane_buttons and self.current_index < len(self.lane_buttons):
            self.update_info(self.lane_buttons[self.current_index].label)

    def update_info(self, lane_name):
        """Update the docstring widget with the selected lane's docstring."""
        lane = self.lanes[lane_name]

        if self.docstring_widget:
            docstring = inspect.getdoc(lane) or "No documentation available."
            self.docstring_widget.update(docstring)

        if self.name_widget:
            self.name_widget.update(lane.__name__)

        if self.queue_names_widget:
            self.queue_names_widget.update(", ".join(lane.name()))

        if self.sub_lanes_widget:
            # Build a tree representation of sub-lanes
            self.sub_lanes_widget.update(
                "\n".join(
                    self._build_lane_tree(lane),
                ),
            )

    def _build_lane_tree(
        self,
        lane_class: type[Lane],
        indent: str = "",
    ):
        """Build a tree representation of the lane and its sub-lanes."""
        # Try to get sub-lanes from the lane class
        try:
            # First attempt to access lanes directly or through lane inheritance
            sub_lanes = lane_class.get_lanes()

            if not sub_lanes:
                return

            items = sorted(
                (
                    (
                        "+" if priority_number >= 0 else "-",
                        abs(priority_number),
                        priority_number,
                        sub_lane,
                    )
                    for priority_number, sub_lane in sub_lanes.items()
                    if sub_lane is not None
                ),
                key=lambda x: x[2],
            )
            equal_signs = all(v[0] == "+" for v in items) or all(
                v[0] == "-" for v in items
            )
            offset = max(
                map(
                    lambda x: len(str(x[1])),
                    items,
                )
            )

            # Build the tree structure
            for i, (
                sign,
                priority_number,
                _,
                sub_lane,
            ) in enumerate(items):
                if sub_lane is None:
                    continue

                last = i == len(items) - 1
                prefix = "└─" if last else "├─"
                is_str = isinstance(sub_lane, str)
                text = sub_lane if is_str else sub_lane.__name__

                if equal_signs:
                    sign = ""

                priority_number_str = f"{sign}{priority_number:>0{offset}}"

                yield f"{indent}{prefix}\\[{priority_number_str}] {text}"

                if not is_str:
                    yield from self._build_lane_tree(
                        sub_lane,
                        indent + "  " if last else indent + "│ ",
                    )

        except Exception:
            pass

    def action_focus_next(self):
        """Focus the next button in the list."""
        if not self.lane_buttons:
            return

        max_len = len(self.lane_buttons)
        self.current_index = (self.current_index + 1) % max_len
        button = self.lane_buttons[self.current_index]
        button.focus()
        self.update_info(button.label)

    def action_focus_previous(self):
        """Focus the previous button in the list."""
        if not self.lane_buttons:
            return

        max_len = len(self.lane_buttons)
        self.current_index = (self.current_index - 1) % max_len
        button = self.lane_buttons[self.current_index]
        button.focus()
        self.update_info(button.label)

    def action_exit_app(self):
        """Exit the application."""
        self.exit(None)

    @on(Button.Pressed, "#exit")
    def on_exit(self):
        self.exit(None)

    @on(Button.Pressed, "#run")
    def on_run(self):
        self.exit(str(self.lane_buttons[self.current_index].label))

    @on(Button.Pressed, ".lane-button")
    def lane_button_pressed(self, event: Button.Pressed):
        if self.lane_buttons[self.current_index] != event.button:
            self.current_index = self.lane_buttons.index(event.button)

            self.lane_buttons[self.current_index].focus()
            self.update_info(
                self.lane_buttons[self.current_index].label,
            )
            return

        self.exit(str(event.button.label))
