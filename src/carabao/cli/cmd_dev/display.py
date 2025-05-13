import os
from typing import Type

from l2l import Lane
from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Label, ListItem, ListView, Tree
from textual.widgets.tree import TreeNode

from ...cfg.secret_cfg import SecretCFG


class Display(App):
    BINDINGS = [
        Binding("escape", "exit_app", "Exit", priority=True),
        Binding("enter", "run_lane", "Run", priority=True),
    ]

    CSS_PATH = os.path.join(
        os.path.dirname(__file__),
        "display.tcss",
    )

    lane_list: ListView

    def compose(self):
        """Create and arrange widgets."""
        # Main layout container with horizontal arrangement
        with Vertical():
            with Horizontal():
                # ListView for lanes
                self.lanes = {
                    lane.first_name(): lane
                    for lane in Lane.available_lanes()
                    if lane.primary() and not lane.passive()
                }
                self.queue_names = sorted(self.lanes.keys())

                if not self.queue_names:
                    raise Exception("No lanes found!")

                cfg = SecretCFG()
                last_run_queue_name = cfg.last_run_queue_name

                try:
                    initial_index = self.queue_names.index(last_run_queue_name)
                except ValueError:
                    initial_index = 0

                self.lane_list = ListView(
                    *(
                        ListItem(
                            Label(queue_name),
                            id=f"lane-{i}",
                        )
                        for i, queue_name in enumerate(self.queue_names)
                    ),
                    id="lanes",
                    initial_index=initial_index,
                )

                yield self.lane_list

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

                    # self.sub_lanes_widget = Label(
                    #     "",
                    #     classes="info-widget",
                    # )
                    self.sub_lanes_widget = Tree("")
                    # self.sub_lanes_widget.show_root=False

                    yield self.sub_lanes_widget

            # Container for exit button at bottom right
            with Horizontal(id="navi-container"):
                yield Button.success(
                    "\\[Enter] Run",
                    id="run",
                )

                yield Button.error(
                    "\\[Esc] Exit",
                    id="exit",
                )

        # Update docstring for initially selected lane
        if (
            self.queue_names
            and self.lane_list.index is not None
            and self.lane_list.index < len(self.queue_names)
        ):
            self.update_info(self.queue_names[self.lane_list.index])

    def update_info(self, lane_name):
        """Update the docstring widget with the selected lane's docstring."""
        lane = self.lanes[lane_name]

        docstring = lane.__doc__ or "No documentation available."
        docstring = docstring.replace("[", "\\[")

        self.docstring_widget.update(docstring)

        self.name_widget.update(lane.__name__)

        self.queue_names_widget.update(", ".join(lane.name()))

        # self.sub_lanes_widget.show_root = False
        self.sub_lanes_widget.root.expand_all()

        # Build a tree representation of sub-lanes

        self.sub_lanes_widget.clear()

        self.sub_lanes_widget.root.set_label(lane.__name__)
        self.build_lane_tree(
            lane,
            self.sub_lanes_widget.root,
        )

    def build_lane_tree(
        self,
        lane: Type[Lane],
        node: TreeNode,
    ):
        sub_lanes = lane.get_lanes()

        if not sub_lanes:
            return

        for priority_number, sub_lane in sorted(
            (
                (
                    priority_number,
                    sub_lane,
                )
                for priority_number, sub_lane in sub_lanes.items()
                if sub_lane is not None
            ),
            key=lambda x: x[0],
        ):
            is_str = isinstance(sub_lane, str)
            text = sub_lane if is_str else sub_lane.__name__

            sub_node = node.add(
                f"{text} [dim]{priority_number}[/dim]",
                expand=True,
                allow_expand=False,
            )

            if not is_str:
                self.build_lane_tree(
                    sub_lane,
                    sub_node,
                )

    def action_exit_app(self):
        """Exit the application."""
        self.exit(None)

    def action_run_lane(self):
        """Run the selected lane."""
        self.on_run()

    @on(Button.Pressed, "#exit")
    def on_exit(self):
        self.exit(None)

    @on(Button.Pressed, "#run")
    def on_run(self):
        if self.lane_list.index is not None and self.lane_list.index < len(
            self.queue_names
        ):
            self.exit(self.queue_names[self.lane_list.index])

    @on(ListView.Selected)
    def on_list_view_selected(self, event: ListView.Selected):
        if event.list_view.id == "lanes" and event.list_view.index is not None:
            if event.list_view.index < len(self.queue_names):
                self.update_info(self.queue_names[event.list_view.index])

    @on(ListView.Highlighted)
    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if event.list_view.id == "lanes" and event.list_view.index is not None:
            if event.list_view.index < len(self.queue_names):
                self.update_info(self.queue_names[event.list_view.index])
