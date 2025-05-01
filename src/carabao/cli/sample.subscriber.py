from l2l import Lane


class Payloads(Lane):
    def process(self, value):
        yield "Hello"
        yield "World"


class Process(Lane):
    def process(self, value):
        print(value)


class Main(Lane):
    use_filename: bool = True

    lanes = {
        1: Payloads,
        2: Process,
    }

    @classmethod
    def primary(cls) -> bool:
        return True
