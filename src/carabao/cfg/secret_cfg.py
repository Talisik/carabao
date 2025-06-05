from .base_cfg import BaseCFG


class SecretCFG(BaseCFG):
    LAST_RUN = "last_run"
    QUEUE_NAME = "queue_name"
    TEST_MODE = "test_mode"
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

    def get_form(self, lane_name: str):
        return dict(
            self.get_section(
                f"{lane_name}{self.FORM}",
            ).items()
        )


SECRET_CFG = SecretCFG()
