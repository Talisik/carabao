import os
from dataclasses import dataclass
from typing import Any, Type

from l2l import Lane
from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Switch,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.tree import TreeNode

from carabao.form import Form

from ...cfg.secret_cfg import SECRET_CFG
from ...helpers.utils import _str2bool, clean_docstring


@dataclass
class Result:
    name: str
    test_mode: bool
    form: dict[str, Any]
    raw_form: dict[str, str]


class Display(App[Result]):
    BINDINGS = [
        Binding("escape", "exit_app", "Exit", priority=True),
        Binding("enter", "run_lane", "Run", priority=True),
    ]

    CSS_PATH = os.path.join(
        os.path.dirname(__file__),
        "display.tcss",
    )

    lane_list: ListView

    def __compose_lane_list(self):
        try:
            initial_index = self.queue_names.index(
                SECRET_CFG.last_run_queue_name,
            )
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

    def __compose_info(self):
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

            self.docstring_widget = Markdown(
                "",
                id="docstring",
                classes="info-widget",
            )

            yield self.docstring_widget
            yield Label(
                "Process Tree",
                classes="info-label",
            )

            self.sub_lanes_widget = Tree("")

            yield self.sub_lanes_widget

    def __compose_navi(self):
        yield Button.success(
            "\\[Enter] Run",
            id="run",
        )

        with Horizontal(
            classes="switch",
        ):
            self.test_mode = Switch(
                SECRET_CFG.test_mode,
            )

            yield self.test_mode
            yield Label("Test Mode")

        yield Button.error(
            "\\[Esc] Exit",
            id="exit",
        )

    def __compose_form(self):
        self.fields = {}

        with Container(id="form-container"):
            yield Label()

    def compose(self):
        self.lanes = {
            lane.first_name(): (
                lane,
                sorted(
                    Form.get_fields(lane),
                    key=lambda field: field.name,
                ),
            )
            for lane in Lane.available_lanes()
            if lane.primary() and not lane.passive()
        }
        self.queue_names = sorted(self.lanes.keys())

        if not self.queue_names:
            raise Exception("No lanes found!")

        yield Footer()

        with Vertical():
            with Horizontal():
                yield from self.__compose_lane_list()

                with TabbedContent():
                    with TabPane("Form"):
                        yield from self.__compose_form()

                    with TabPane("Info"):
                        yield from self.__compose_info()

            with Horizontal(id="navi-container"):
                yield from self.__compose_navi()

        if (
            self.queue_names
            and self.lane_list.index is not None
            and self.lane_list.index < len(self.queue_names)
        ):
            lane_name = self.queue_names[self.lane_list.index]
            self.update_info(lane_name)
            self.update_form(lane_name)

    def update_info(self, lane_name: str):
        """
        Update the docstring widget with the selected lane's docstring.
        """
        lane = self.lanes[lane_name]

        self.docstring_widget.update(
            clean_docstring(lane.__doc__)
            if lane.__doc__
            else "No documentation available."
        )

        self.name_widget.update(lane[0].__name__)

        self.queue_names_widget.update(", ".join(lane[0].name()))

        self.sub_lanes_widget.root.allow_expand = False

        self.sub_lanes_widget.root.expand_all()

        # Build a tree representation of sub-lanes

        self.sub_lanes_widget.clear()

        self.sub_lanes_widget.root.set_label(lane[0].__name__)
        self.build_lane_tree(
            lane[0],
            self.sub_lanes_widget.root,
        )

    def update_form(
        self,
        lane_name: str,
    ):
        """
        Update the form with the selected lane's fields.
        """
        form_container = self.query_one("#form-container")
        form_container.remove_children()

        form = SECRET_CFG.get_form(lane_name)

        fields = self.lanes[lane_name][1]

        for field in fields:
            value = form.get(field.name, str(field.default))

            form_container.mount(Label(field.name))

            if field.raw_cast is bool:
                form_container.mount(
                    Switch(
                        _str2bool(value),
                        classes="form-switch",
                    )
                )
            else:
                form_container.mount(Input(value))

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
            self.exit(
                Result(
                    name=self.queue_names[self.lane_list.index],
                    test_mode=self.test_mode.value,
                    form={
                        name: field[1](field[0].value)
                        for name, field in self.fields.items()
                        if field[0].value is not None
                    },
                    raw_form={
                        name: field[0].value
                        for name, field in self.fields.items()
                        if field[0].value is not None
                    },
                ),
            )

    def __update(self, list_view: ListView):
        if list_view.id != "lanes":
            return

        if list_view.index is None:
            return

        if list_view.index >= len(self.queue_names):
            return

        lane_name = self.queue_names[list_view.index]
        self.update_info(lane_name)
        self.update_form(lane_name)

    @on(ListView.Selected)
    def on_list_view_selected(self, event: ListView.Selected):
        self.__update(event.list_view)

    @on(ListView.Highlighted)
    def on_list_view_highlighted(self, event: ListView.Highlighted):
        self.__update(event.list_view)
