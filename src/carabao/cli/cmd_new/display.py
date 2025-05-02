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
            "../samples",
        )
    )
    TEMPLATES = {
        "Basic Lane": {
            "file": os.path.join(
                SAMPLES_FOLDERPATH,
                "basic.py",
            ),
            "description": "A simple lane that processes data sequentially.",
        },
        "Factory Lane": {
            "file": os.path.join(
                SAMPLES_FOLDERPATH,
                "factory.py",
            ),
            "description": "A factory pattern implementation for lane processing.",
        },
        "Passive Lane": {
            "file": os.path.join(
                SAMPLES_FOLDERPATH,
                "passive.py",
            ),
            "description": "A lane that runs in the background.",
        },
        "Subscriber Lane": {
            "file": os.path.join(
                SAMPLES_FOLDERPATH,
                "subscriber.py",
            ),
            "description": "A lane that implements the publisher-subscriber pattern to receive events.",
        },
    }
    TEMPLATE_NAMES = sorted(TEMPLATES.keys())

    def compose(self):
        """Create and arrange widgets."""
        # Main layout container with horizontal arrangement
        with Vertical():
            with Horizontal():
                # Create ListView with template names
                self.template_list = ListView(
                    *(
                        ListItem(Label(template_name))
                        for template_name in self.TEMPLATE_NAMES
                    ),
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

        self.update_info(self.TEMPLATE_NAMES[0])

    def update_info(self, template_name):
        """Update the info widgets with the selected template's information."""
        template = self.TEMPLATES[template_name]

        if self.description_widget:
            self.description_widget.update(template["description"])

        if self.content_widget:
            try:
                with open(template["file"], "r") as f:
                    content = f.read()
                    # Escape brackets for Textual
                    content = content.replace("[", "\\[").replace("]", "\\]")
                    self.content_widget.update(content)
            except Exception:
                self.content_widget.update("Could not load template content.")

    def action_exit_app(self):
        self.exit(None)

    @on(Button.Pressed, "#exit")
    def on_exit(self):
        self.exit(None)

    @on(ListView.Highlighted, "#template-list")
    def on_template_selected(self, event: ListView.Selected):
        self.current_index = event.list_view.index
        template_name = event.item.children[0].render()
        self.update_info(template_name)

    @on(Button.Pressed, "#select")
    def on_select(self):
        self.exit(
            Item(
                template_name=self.TEMPLATE_NAMES[self.template_list.index or 0],
                lane_name=self.name_input.value,
                lane_directory=self.directory_input.value,
                use_filename=self.use_filename.value,
            )
        )
