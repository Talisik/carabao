from l2l import Lane


class MyPayloads(Lane):
    """
    A simple data source lane that generates example payloads.

    This starter lane demonstrates how to create a data producer
    that yields multiple values to be processed by downstream lanes.
    """

    def process(self, value):
        yield "Hello"
        yield "World"


class MyPipeline(Lane):
    """
    A simple consumer lane that processes incoming payloads.

    This starter lane demonstrates how to create a processor
    that consumes data from upstream lanes.
    """

    def process(self, value):
        print(value)


class MyLane(Lane):
    """
    A primary lane that demonstrates a basic pipeline structure.

    This starter lane shows how to:
    1. Configure a pipeline with multiple lanes
    2. Set execution priority using numeric keys
    3. Mark a lane as primary

    Lanes with lower priority numbers run first, followed by
    lanes with higher priority numbers.
    """

    lanes = {
        -100: MyPayloads,  # Runs first (data producer)
        100: MyPipeline,  # Runs second (data consumer)
    }

    @classmethod
    def primary(cls) -> bool:
        return True
