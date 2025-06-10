from l2l import Lane

from carabao.form import F, Field


class Main(Lane):
    class Form:
        value_1: str
        value_2: int
        value_3: float
        value_4: bool
        value_5 = Field(
            cast=int,
            min_value=0,
            max_value=10,
            step=2,
        )

    use_filename: bool = True

    @classmethod
    def primary(cls) -> bool:
        return True

    def process(self, value):
        print("Value 1:", F.value_1)
        print("Value 2:", F.value_2)
        print("Value 3:", F.value_3)
        print("Value 4:", F.value_4)
        print("Value 5:", F.value_5)
