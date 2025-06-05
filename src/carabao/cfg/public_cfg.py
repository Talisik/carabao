from .base_cfg import BaseCFG


class PublicCFG(BaseCFG):
    filepath = "carabao.cfg"

    @property
    def settings(self):
        section = self.get_section("directories")

        return section.get(
            "settings",
            fallback="settings",
        )

    @property
    def form(self):
        section = self.get_section("directories")

        return section.get(
            "form",
            fallback="form",
        )


PUBLIC_CFG = PublicCFG()
