from l2l import Lane


class Process1(Lane):
    def process(self, value):
        yield "Hello"
        yield "World"


class Process2(Lane):
    def process(self, value):
        yield value


class Process3(Lane):
    def process(self, value):
        print(value)

        yield value


class Main(Lane):
    use_filename: bool = True

    lanes = {
        1: Process1,
        2: Process2,
        3: Process3,
    }
