from l2l import Lane
from textual.app import App, AutopilotCallbackType
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Button, Static

from ..cfg.secret_cfg import SecretCFG


class DisplayTextual(App):
    """A Textual app to display and select lanes."""

    selected_lane = reactive(None)

    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self):
        """Create and arrange widgets."""
        yield Static("Carabao", id="title")

        # Container for lane buttons
        with Container(id="lanes-container"):
            cfg = SecretCFG()
            last_run_queue_name = cfg.last_run_queue_name

            queue_names = [
                lane.first_name()
                for lane in Lane.available_lanes()
                if lane.primary() and not lane.hidden()
            ]

            if not any(queue_names):
                raise Exception("No lanes found!")

            for queue_name in queue_names:
                yield Button(
                    f"{queue_name}",
                    id=f"lane-{queue_name}",
                    classes="lane-button",
                    variant="success"
                    if queue_name == last_run_queue_name
                    else "default",
                )

        yield Button("Exit", id="exit-button", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id is None:
            self.exit()
            return

        if button_id == "exit-button":
            self.result = None
            self.exit()
            return

        if button_id.startswith("lane-"):
            queue_name = button_id[5:]  # Remove "lane-" prefix
            self.result = queue_name
            self.exit()
            return

    def run(self, *args, **kwargs):
        """Run the app and return the selected lane name."""
        super().run(*args, **kwargs)

        return self.result
