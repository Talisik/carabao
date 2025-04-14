from ..constants import QUEUE_NAME
from .base_cfg import BaseCFG


class SecretCFG(BaseCFG):
    LAST_RUN = "last_run"
    QUEUE_NAME = "queue_name"

    filepath = ".ignore.carabao.secret.cfg"

    @property
    def last_run_queue_name(self):
        section = self.get_section(self.LAST_RUN)

        return section.get(self.QUEUE_NAME)

    def write_last_run(self):
        section = self.get_section(self.LAST_RUN)

        section[self.QUEUE_NAME] = QUEUE_NAME
