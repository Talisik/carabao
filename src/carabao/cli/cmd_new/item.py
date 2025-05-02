from dataclasses import dataclass


@dataclass
class Item:
    template_name: str
    lane_name: str
    lane_directory: str
    use_filename: bool
