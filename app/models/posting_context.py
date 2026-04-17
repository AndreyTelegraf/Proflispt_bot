from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PostingContext:
    section_name: str
    data: dict[str, Any] = field(default_factory=dict)

    def set_value(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get_value(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_name": self.section_name,
            **self.data,
        }
