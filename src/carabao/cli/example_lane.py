from l2l import Lane


class LANE_NAME(Lane):
    @classmethod
    def primary(cls) -> bool:
        return True

    def process(self, value):
        pass
