from dataclasses import dataclass


@dataclass
class Item:
    lane_name: str
    lane_directory: str
    use_filename: bool
    content: str
