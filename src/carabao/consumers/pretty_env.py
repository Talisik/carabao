from generic_consumer import PassiveConsumer
from fun_things.environment import pretty_print, mentioned_keys


class PrettyEnv(PassiveConsumer):
    @classmethod
    def hidden(cls):
        return False

    @classmethod
    def priority_number(cls):
        return 200

    def process(self, payloads: list):
        pretty_print(
            keys=mentioned_keys.keys(),
            confidential_keywords=[],
        )
