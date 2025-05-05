from typing import Any

from l2l import Lane


class Main(Lane):
    use_filename: bool = True

    @classmethod
    def passive(cls) -> bool:
        return True

    @classmethod
    def primary(cls) -> bool:
        return True

    @classmethod
    def max_run_count(cls) -> int:
        return 1

    @classmethod
    def priority_number(cls) -> float:
        return -100

    @classmethod
    def condition(cls, name: str):
        return True

    def process(self, value: Any):
        print("Hello World!")
