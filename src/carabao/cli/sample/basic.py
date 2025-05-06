from l2l import Lane


class Main(Lane):
    use_filename: bool = True

    @classmethod
    def primary(cls) -> bool:
        return True

    def process(self, value):
        pass
