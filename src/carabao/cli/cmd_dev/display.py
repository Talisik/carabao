import asyncio
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple, Type

from l2l import Lane, Mock
from l2l.types import LaneDictType
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
from textual_slider import Slider

from carabao import form

from ...cfg.secret_cfg import SECRET_CFG
from ...helpers.utils import _str2bool, clean_docstring


@dataclass
class Result:
    lane: Type[Lane]
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
            yield Label("🧪 Test Mode")

        yield Button.error(
            "\\[Esc] Exit",
            id="exit",
        )

    def __compose_form(self):
        with Container(id="form-container"):
            yield Label()

    def compose(self):
        self.forms: Dict[str, Dict[str, Tuple[str, Callable]]] = {}
        self.lanes = {
            lane.first_name(): (
                lane,
                sorted(
                    form._get_fields(lane),
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
                    with TabPane("Info"):
                        yield from self.__compose_info()

                    with TabPane("Form"):
                        yield from self.__compose_form()

            with Horizontal(id="navi-container"):
                yield from self.__compose_navi()

        if (
            self.queue_names
            and self.lane_list.index is not None
            and self.lane_list.index < len(self.queue_names)
        ):
            lane_name = self.queue_names[self.lane_list.index]
            self.__update_info(lane_name)

            asyncio.run(self.__update_form(lane_name))

    def __update_info(self, lane_name: str):
        """
        Update the docstring widget with the selected lane's docstring.
        """
        lane = self.lanes[lane_name][0]

        self.docstring_widget.update(
            clean_docstring(lane.__doc__)
            if lane.__doc__
            else "No documentation available."
        )

        self.name_widget.update(lane.__name__)

        self.queue_names_widget.update(
            ", ".join(lane.name()),
        )

        self.sub_lanes_widget.root.expand_all()

        self.sub_lanes_widget.root.allow_expand = False

        # Build a tree representation of sub-lanes

        self.sub_lanes_widget.clear()

        self.sub_lanes_widget.root.set_label(
            lane.__name__,
        )
        self.build_lane_tree(
            lane.get_lanes(),
            self.sub_lanes_widget.root,
        )

    async def __update_form(
        self,
        lane_name: str,
    ):
        """
        Update the form with the selected lane's fields.
        """
        form_container = self.query_one("#form-container")

        await form_container.remove_children()

        fields = self.lanes[lane_name][1]

        if not fields:
            form_container.mount(
                Label(
                    "Not available. "
                    "You can create one by adding a Form class inside your lane.",
                )
            )

            form_container.mount(
                Markdown(
                    """
```py
class MyLane(Lane):
    class Form:
        example_string: str = "Hello World!"
        example_integer: int = 1
        example_float: float = 1.2
        example_boolean: bool = True

    ...
```
                    """,
                )
            )
            return

        if lane_name not in self.forms:
            _form = SECRET_CFG.get_form(lane_name)
            self.forms[lane_name] = {
                field.name: (
                    (
                        _form[field.name.lower()]
                        if field.name.lower() in _form
                        else str(field.default)
                        if field.default is not None
                        else "",
                        field.cast,
                    )
                )
                for field in fields
            }

        for field in fields:
            value, _ = self.forms[lane_name][field.name]

            form_container.mount(Label(field.name))

            name = f"form-{lane_name}-{field.name}"

            if field.raw_cast is bool:
                form_container.mount(
                    Switch(
                        _str2bool(value),
                        name=name,
                        classes="form-switch",
                    )
                )

            elif field.min_value is not None and field.max_value is not None:
                try:
                    value = int(value)
                except Exception:
                    value = None

                h = Horizontal(
                    classes="slider-container",
                )

                form_container.mount(h)

                slider = Slider(
                    value=value,
                    name=name,
                    min=field.min_value,
                    max=field.max_value,
                    step=field.step,
                )

                h.mount(slider)

                h.mount(
                    Label(
                        str(slider.value),
                        classes=f"{name}-value slider-label",
                    )
                )

            else:
                form_container.mount(
                    Input(
                        value,
                        name=name,
                        type="integer"
                        if field.raw_cast is int
                        else "number"
                        if field.raw_cast is float
                        else "text",
                    )
                )

    def build_lane_node(
        self,
        node: TreeNode,
        name: str,
        priority_number: int,
    ):
        return node.add(
            f"{name + ' ' if name else ''}[dim]{priority_number}[/dim]",
            expand=True,
            allow_expand=False,
        )

    def build_lane_tree(
        self,
        sub_lanes: LaneDictType,
        node: TreeNode,
    ):
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
            if isinstance(sub_lane, str):
                self.build_lane_node(
                    node,
                    sub_lane,
                    priority_number,
                )

            elif isinstance(sub_lane, type):
                self.build_lane_tree(
                    sub_lane.get_lanes(),
                    self.build_lane_node(
                        node,
                        sub_lane.__name__,
                        priority_number,
                    ),
                )

            elif isinstance(sub_lane, dict):
                self.build_lane_tree(
                    sub_lane,
                    self.build_lane_node(
                        node,
                        "",
                        priority_number,
                    ),
                )

            elif isinstance(sub_lane, Mock):
                self.build_lane_tree(
                    sub_lane.lanes,
                    self.build_lane_node(
                        node,
                        "",
                        priority_number,
                    ),
                )
                continue

    def action_exit_app(self):
        """Exit the application."""
        self.exit(None)

    def action_run_lane(self):
        """Run the selected lane."""
        self.on_run()

    @on(Switch.Changed)
    def on_switch_changed(self, event: Switch.Changed):
        name = event.switch.name

        if name is None:
            return

        _, name, field = name.split("-")
        _, cast = self.forms[name][field]
        self.forms[name][field] = str(event.switch.value), cast

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed):
        name = event.input.name

        if name is None:
            return

        _, name, field = name.split("-")
        _, cast = self.forms[name][field]
        self.forms[name][field] = event.input.value, cast

    @on(Slider.Changed)
    def on_slider_changed(self, event: Slider.Changed):
        name = event.slider.name

        if name is None:
            return

        self.query_one(
            f".{name}-value",
            Label,
        ).update(str(event.slider.value))

        _, name, field = name.split("-")
        _, cast = self.forms[name][field]
        self.forms[name][field] = str(event.slider.value), cast

    @on(Button.Pressed, "#exit")
    def on_exit(self):
        self.exit(None)

    @on(Button.Pressed, "#run")
    def on_run(self):
        if self.lane_list.index is None:
            return

        if self.lane_list.index >= len(self.queue_names):
            return

        name = self.queue_names[self.lane_list.index]
        _form = self.forms[name] if name in self.forms else {}

        self.exit(
            Result(
                lane=self.lanes[name][0],
                name=name,
                test_mode=self.test_mode.value,
                form={name: field[1](field[0]) for name, field in _form.items()},
                raw_form={name: field[0] for name, field in _form.items()},
            ),
        )

    async def __update(self, list_view: ListView):
        if list_view.id != "lanes":
            return

        if list_view.index is None:
            return

        if list_view.index >= len(self.queue_names):
            return

        lane_name = self.queue_names[list_view.index]

        self.__update_info(lane_name)
        await self.__update_form(lane_name)

    @on(ListView.Selected)
    async def on_list_view_selected(self, event: ListView.Selected):
        await self.__update(event.list_view)

    @on(ListView.Highlighted)
    async def on_list_view_highlighted(self, event: ListView.Highlighted):
        await self.__update(event.list_view)
