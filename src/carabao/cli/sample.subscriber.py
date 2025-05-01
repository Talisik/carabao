from l2l import Lane


class Payloads(Lane):
    def process(self, value):
        yield "Hello"
        yield "World"


class Processor(Lane):
    def process(self, value):
        print(value)


class Main(Lane):
    use_filename: bool = True

    lanes = {
        -100: Payloads,  # Runs first (data producer)
        100: Processor,  # Runs second (data consumer)
    }

    @classmethod
    def primary(cls) -> bool:
        return True
