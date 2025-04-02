from .base_cfg import BaseCFG


class CFG(BaseCFG):
    filepath = "carabao.cfg"

    @property
    def settings(self):
        section = self.get_section("directories")

        return section.get(
            "settings",
            fallback="settings",
        )
