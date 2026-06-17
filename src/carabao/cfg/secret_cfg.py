from .base_cfg import BaseCFG


class SecretCFG(BaseCFG):
    LAST_RUN = "last_run"
    QUEUE_NAME = "queue_name"
    TEST_MODE = "test_mode"
    UI = "ui"
    LOG_FILE = "log_file"
    SINGLE_RUN = "single_run"
    SLEEP_MIN = "sleep_min"
    SLEEP_MAX = "sleep_max"
    PROCESSES = "processes"
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

    @property
    def single_run(self):
        section = self.get_section(self.SINGLE_RUN)
        value = section.get(self.SINGLE_RUN)

        if value is not None:
            return value == "True"

        # Unset → fall back to the effective SINGLE_RUN setting (env, default
        # True), so the toggle starts reflecting the actual run behavior.
        try:
            from carabao.constants import C

            return bool(C.SINGLE_RUN)
        except Exception:
            return True

    def __value_setting(self, key: str, const: str, default):
        """Stored value for a numeric setting, else the effective env value.

        Returned as a string for display in the selector inputs; an empty
        string means "use the setting/env default" (e.g. PROCESSES unset).
        """

        value = self.get_section(key).get(key)

        if value is not None:
            return value

        try:
            from carabao.constants import C

            effective = getattr(C, const)
        except Exception:
            effective = default

        return "" if effective is None else str(effective)

    @property
    def sleep_min(self):
        return self.__value_setting(self.SLEEP_MIN, "SLEEP_MIN", 3)

    @property
    def sleep_max(self):
        return self.__value_setting(self.SLEEP_MAX, "SLEEP_MAX", 5)

    @property
    def processes(self):
        return self.__value_setting(self.PROCESSES, "PROCESSES", None)

    def get_form(self, lane_name: str):
        return dict(
            self.get_section(
                f"{lane_name}{self.FORM}",
            ).items()
        )


SECRET_CFG = SecretCFG()
