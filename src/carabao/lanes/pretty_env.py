from fun_things.environment import mentioned_keys, pretty_print
from l2l import Lane


class PrettyEnv(Lane):
    """
    A passive lane that displays environment variables in a formatted way.

    This lane uses the pretty_print function from fun_things.environment to
    display all environment variables that have been accessed during runtime.
    It runs with a high priority (200) and is always visible in the lane list.

    The lane doesn't process any payloads directly but instead outputs
    environment information to the console when triggered.
    """

    @classmethod
    def passive(cls) -> bool:
        return True

    @classmethod
    def primary(cls) -> bool:
        return True

    @classmethod
    def priority_number(cls):
        return -2000

    @classmethod
    def max_run_count(cls) -> int:
        return 1

    @classmethod
    def condition(cls, name: str):
        return True

    def process(self, value):
        pretty_print(
            keys=mentioned_keys.keys(),
            confidential_keywords=[],
        )
