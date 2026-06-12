from .base_cfg import BaseCFG


class SecretCFG(BaseCFG):
    LAST_RUN = "last_run"
    QUEUE_NAME = "queue_name"
    TEST_MODE = "test_mode"
    UI = "ui"
    LOG_FILE = "log_file"
    FORM = "_form"

    filepath = ".ignore.carabao.cfg"

    @property
    def last_run_queue_name(self):
        section = self.get_section(self.LAST_RUN)

        return section.get(self.QUEUE_NAME)

    @property
    def test_mode(self):
        section = self.get_section(self.TEST_MODE)

        return section.get(self.TEST_MODE) == "True"

    @property
    def ui(self):
        section = self.get_section(self.UI)

        # Default on when unset.
        return section.get(self.UI, "True") == "True"

    @property
    def log_file(self):
        section = self.get_section(self.LOG_FILE)

        # Default off when unset.
        return section.get(self.LOG_FILE) == "True"

    def get_form(self, lane_name: str):
        return dict(
            self.get_section(
                f"{lane_name}{self.FORM}",
            ).items()
        )


SECRET_CFG = SecretCFG()
