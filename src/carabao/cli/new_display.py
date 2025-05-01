import os

from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Label


class NewDisplay(App):
    """A Textual app to display and select sample lane templates."""

    BINDINGS = [
        Binding("up", "focus_previous", "Move up"),
        Binding("down", "focus_next", "Move down"),
        Binding("escape", "exit_app", "Exit"),
    ]

    CSS_PATH = os.path.join(
        os.path.dirname(__file__),
        "new_display.tcss",
    )

    def __init__(self):
        super().__init__()
        self.current_index = 0
        self.template_buttons = []
        self.templates = {}
        self.content_widget = None

    def compose(self):
        """Create and arrange widgets."""
        # Main layout container with horizontal arrangement
        with Vertical():
            with Horizontal():
                # Scrollable container for template buttons
                with ScrollableContainer(id="templates-container"):
                    self.templates = {
                        "Basic Lane": {
                            "file": "sample.lane.py",
                            "description": "A simple lane that processes data sequentially.",
                        },
                        "Starter Lane": {
                            "file": "sample.starter.py",
                            "description": "A lane that initiates a processing pipeline.",
                        },
                        "Factory Lane": {
                            "file": "sample.factory.py",
                            "description": "A lane that creates and returns other lanes.",
                        },
                        "Passive Lane": {
                            "file": "sample.passive.py",
                            "description": "A lane that runs in the background and doesn't process data directly.",
                        },
                        "Subscriber Lane": {
                            "file": "sample.subscriber.py",
                            "description": "A lane that subscribes to events from other lanes.",
                        },
                    }
                    template_names = sorted(self.templates.keys())

                    if not any(template_names):
                        raise Exception("No templates found!")

                    for i, template_name in enumerate(template_names):
                        button = Button(
                            template_name,
                            classes="template-button",
                            id=f"template-{i}",
                        )

                        self.template_buttons.append(button)
                        yield button

                    # Set initial focus
                    if self.template_buttons:
                        self.template_buttons[0].focus()

                # Container for template content (side by side with templates)
                with Container(id="info-container"):
                    yield Label(
                        "Template Type",
                        classes="info-label",
                    )

                    self.name_widget = Label(
                        "",
                        classes="info-widget",
                    )

                    yield self.name_widget
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
                yield Button(
                    "\\[Enter] Select",
                    id="select",
                )

                yield Button(
                    "\\[Esc] Cancel",
                    id="exit",
                )

        # Update info for initially focused button
        if self.template_buttons:
            self.update_info(self.template_buttons[0].label)

    def update_info(self, template_name):
        """Update the info widgets with the selected template's information."""
        template = self.templates[template_name]

        if self.name_widget:
            self.name_widget.update(template_name)

        if self.description_widget:
            self.description_widget.update(template["description"])

        if self.content_widget:
            try:
                with open(
                    os.path.join(
                        os.path.dirname(__file__),
                        template["file"],
                    ),
                    "r",
                ) as f:
                    content = f.read()
                    # Escape brackets for Textual
                    content = content.replace("[", "\\[").replace("]", "\\]")
                    self.content_widget.update(content)
            except Exception:
                self.content_widget.update("Could not load template content.")

    def action_focus_next(self):
        """Focus the next button in the list."""
        if not self.template_buttons:
            return

        max_len = len(self.template_buttons)
        self.current_index = (self.current_index + 1) % max_len
        button = self.template_buttons[self.current_index]
        button.focus()
        self.update_info(button.label)

    def action_focus_previous(self):
        """Focus the previous button in the list."""
        if not self.template_buttons:
            return

        max_len = len(self.template_buttons)
        self.current_index = (self.current_index - 1) % max_len
        button = self.template_buttons[self.current_index]
        button.focus()
        self.update_info(button.label)

    def action_exit_app(self):
        """Exit the application."""
        self.exit(None)

    @on(Button.Pressed, "#exit")
    def on_exit(self):
        self.exit(None)

    @on(Button.Pressed, "#select")
    def on_select(self):
        self.exit(str(self.template_buttons[self.current_index].label))

    @on(Button.Pressed, ".template-button")
    def template_button_pressed(self, event: Button.Pressed):
        if self.template_buttons[self.current_index] != event.button:
            self.current_index = self.template_buttons.index(event.button)

            self.template_buttons[self.current_index].focus()
            self.update_info(
                self.template_buttons[self.current_index].label,
            )
            return

        self.exit(str(event.button.label))
