"""Sections registry loader for Work in Portugal Bot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class SectionsRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SectionTarget:
    section_name: str
    topic_id: int


class SectionsRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.channel_id: int | None = None
        self._by_name: dict[str, SectionTarget] = {}

    def load(self) -> "SectionsRegistry":
        if not self.path.exists():
            raise SectionsRegistryError(f"sections registry not found: {self.path}")

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        channel_id = raw.get("channel_id")
        sections = raw.get("sections")

        if channel_id is None:
            raise SectionsRegistryError("sections_registry.json missing channel_id")
        if not isinstance(sections, dict) or not sections:
            raise SectionsRegistryError("sections_registry.json missing non-empty sections object")

        self.channel_id = int(channel_id)
        self._by_name = {
            str(name): SectionTarget(section_name=str(name), topic_id=int(topic_id))
            for name, topic_id in sections.items()
        }
        return self

    def get_topic_id(self, section_name: str) -> int:
        try:
            return self._by_name[section_name].topic_id
        except KeyError as exc:
            raise SectionsRegistryError(f"unknown section_name: {section_name}") from exc

    def has_section(self, section_name: str) -> bool:
        return section_name in self._by_name

    def list_sections(self) -> list[str]:
        return sorted(self._by_name.keys())


def load_sections_registry(path: str | Path | None = None) -> SectionsRegistry:
    target = Path(path) if path else Path(__file__).resolve().parent.parent / "sections_registry.json"
    return SectionsRegistry(target).load()
