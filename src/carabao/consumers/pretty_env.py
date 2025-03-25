from fun_things.environment import mentioned_keys, pretty_print
from generic_consumer import PassiveConsumer


class PrettyEnv(PassiveConsumer):
    """
    A passive consumer that displays environment variables in a formatted way.
    
    This consumer uses the pretty_print function from fun_things.environment to
    display all environment variables that have been accessed during runtime.
    It runs with a high priority (200) and is always visible in the consumer list.
    
    The consumer doesn't process any payloads directly but instead outputs
    environment information to the console when triggered.
    """
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
