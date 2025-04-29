from .base_cfg import BaseCFG


class SecretCFG(BaseCFG):
    LAST_RUN = "last_run"
    QUEUE_NAME = "queue_name"

    filepath = ".ignore.carabao.cfg"

    @property
    def last_run_queue_name(self):
        section = self.get_section(self.LAST_RUN)

        return section.get(self.QUEUE_NAME)
