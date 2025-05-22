from l2l import Lane


class Payloads(Lane):
    def process(self, value):
        yield "The"
        yield "quick"
        yield "brown"
        yield "fox"
        yield "jumps"
        yield "over"
        yield "the"
        yield "lazy"
        yield "dog"


class Process(Lane):
    process_mode = 3

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
