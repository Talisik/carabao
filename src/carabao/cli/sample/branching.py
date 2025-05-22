from typing import Any

from l2l import Lane


class Payloads(Lane):
    def process(self, value):
        yield "Hello"
        yield "World"
        yield "Foo"
        yield "Bar"


class ProcessA(Lane):
    def process(self, value):
        print("Hello from A!", value)


class ProcessB(Lane):
    def process(self, value: Any):
        print("Hello from B!", value)


class Crossroad(Lane):
    def process(self, value: Any):
        yield from self.goto(ProcessA, value)
        yield from self.goto(ProcessB, value)


class Main(Lane):
    use_filename: bool = True

    lanes = {
        1: Payloads,
        2: Crossroad,
    }

    @classmethod
    def primary(cls) -> bool:
        return True
