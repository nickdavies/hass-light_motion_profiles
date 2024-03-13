from typing import Any


class DataSource:
    value: Any

    def __init__(self, value: Any):
        self.value = value


class TriggerSource:
    value: str
