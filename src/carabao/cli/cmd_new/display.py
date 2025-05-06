import os

from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Switch

from carabao.cli.cmd_new.item import Item


class Display(App):
    lane_name: str = "MyLane"
    lane_directory: str = "lanes"

    DEFAULT_LANE_NAME = "MyLane"
    DEFAULT_LANE_DIRECTORY = "lanes"

    BINDINGS = [
        Binding("escape", "exit_app", "Exit"),
    ]

    CSS_PATH = os.path.join(
        os.path.dirname(__file__),
        "display.tcss",
    )

    SAMPLES_FOLDERPATH = os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../sample",
        )
    )
    TEMPLATES = sorted(
        [
            {
                "name": "Basic Lane",
                "file": os.path.join(
                    SAMPLES_FOLDERPATH,
                    "basic.py",
                ),
                "description": "A simple lane that processes data sequentially.",
            },
            {
                "name": "Factory Lane",
                "file": os.path.join(
                    SAMPLES_FOLDERPATH,
                    "factory.py",
                ),
                "description": "A factory pattern implementation for lane processing.",
            },
            {
                "name": "Passive Lane",
                "file": os.path.join(
                    SAMPLES_FOLDERPATH,
                    "passive.py",
                ),
                "description": "A lane that runs in the background.",
            },
            {
                "name": "Subscriber Lane",
                "file": os.path.join(
                    SAMPLES_FOLDERPATH,
                    "subscriber.py",
                ),
                "description": "A lane that implements the publisher-subscriber pattern to receive events.",
            },
        ],
        key=lambda x: x["name"],
    )

    def compose(self):
        """Create and arrange widgets."""
        # Main layout container with horizontal arrangement
        with Vertical():
            with Horizontal():
                # Create ListView with template names
                self.template_list = ListView(
                    *(ListItem(Label(template["name"])) for template in self.TEMPLATES),
                    id="template-list",
                )

                yield self.template_list

                # Vertical container for inputs and info
                with Vertical(id="right-container"):
                    # Text inputs section
                    with Container(id="inputs-container"):
                        yield Label(
                            "Name",
                            classes="input-label",
                        )
                        self.name_input = Input(
                            value=self.lane_name,
                            placeholder=self.DEFAULT_LANE_NAME,
                        )
                        yield self.name_input

                        yield Label(
                            "Directory",
                            classes="input-label",
                        )
                        self.directory_input = Input(
                            value=self.lane_directory,
                            placeholder=self.DEFAULT_LANE_DIRECTORY,
                        )

                        yield self.directory_input

                        with Horizontal(
                            classes="switch",
                        ):
                            self.use_filename = Switch(True)
                            yield self.use_filename
                            yield Label("Use Filename as Name?")

                    # Container for template content
                    with Container(id="info-container"):
                        yield Label(
                            "Description",
                            classes="info-label",
                        )

                        self.description_widget = Label(
                            "",
                            classes="info-widget",
                        )

                        yield self.description_widget
                        yield Label(
                            "Content Preview",
                            classes="info-label",
                        )

                        self.content_widget = Label(
                            "",
                            id="content",
                            classes="info-widget",
                        )

                        yield self.content_widget

            # Container for action buttons at bottom
            with Horizontal(id="navi-container"):
                yield Button.success(
                    "\\[Enter] Create",
                    id="select",
                )

                yield Button.error(
                    "\\[Esc] Cancel",
                    id="exit",
                )

        self.update(0)

    def update(self, index: int):
        self.update_item(index)
        self.update_info(index)

    def update_item(self, index: int):
        template = self.TEMPLATES[index]

        with open(template["file"], "r") as f:
            content = f.read()

        if not self.use_filename.value:
            content = content.replace(
                "class Main(Lane):",
                f"class {self.name_input.value}(Lane):",
            ).replace(
                "use_filename: bool = True",
                "use_filename: bool = False",
            )

        self.__item = Item(
            lane_name=self.name_input.value,
            lane_directory=self.directory_input.value,
            use_filename=self.use_filename.value,
            content=content,
        )

    def update_info(self, index: int):
        template = self.TEMPLATES[index]

        self.description_widget.update(template["description"])

        try:
            self.content_widget.update(
                self.__item.content.replace(
                    "[",
                    "\\[",
                ).replace(
                    "]",
                    "\\]",
                )
            )
        except Exception:
            self.content_widget.update(
                "Could not load template content.",
            )

    def action_exit_app(self):
        self.exit(None)

    @on(Input.Changed, "#name-input")
    def on_name_input_changed(self, event: Input.Changed):
        self.update_item(self.template_list.index or 0)

    @on(Button.Pressed, "#exit")
    def on_exit(self):
        self.exit(None)

    @on(ListView.Highlighted, "#template-list")
    def on_template_selected(self, event: ListView.Selected):
        self.update(event.list_view.index or 0)

    @on(Button.Pressed, "#select")
    def on_select(self):
        self.exit(self.__item)
