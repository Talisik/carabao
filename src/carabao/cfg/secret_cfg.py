from l2l import Lane

from ..constants import QUEUE_NAME
from .base_cfg import BaseCFG


class SecretCFG(BaseCFG):
    LAST_RUN = "last_run"
    LANES = "lanes"
    QUEUE_NAME = "queue_name"
    PRIMARY = "primary"
    PASSIVE = "passive"

    filepath = ".ignore.carabao.secret.cfg"

    @property
    def last_run_queue_name(self):
        section = self.get_section(self.LAST_RUN)

        return section.get(self.QUEUE_NAME)

    @property
    def primary_lanes(self):
        section = self.get_section(self.LANES)

        active = section.get(self.PRIMARY)

        if active == None:
            return

        active = active.splitlines()

        for queue_name in active:
            queue_name = queue_name.strip()

            if not queue_name:
                continue

            yield queue_name

    def write_last_run(self):
        section = self.get_section(self.LAST_RUN)

        section[self.QUEUE_NAME] = QUEUE_NAME

    def write_lanes(self):
        section = self.get_section(self.LANES)

        lanes = Lane.available_lanes()
        active = set()
        passive = set()

        for lane in lanes:
            names = lane.name()
            active.union(names)

            if lane.primary():
                active.union(names)
            else:
                passive.union(names)

        section[self.PRIMARY] = "\r\n" + "\r\n".join(active)
        section[self.PASSIVE] = "\r\n" + "\r\n".join(passive)
