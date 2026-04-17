from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class SectionCatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogGroup:
    key: str
    title: str
    sections: list[str]


class SectionCatalog:
    def __init__(self, groups: list[CatalogGroup]):
        self.groups = groups
        self._by_key = {g.key: g for g in groups}

    def get_group(self, key: str) -> CatalogGroup:
        try:
            return self._by_key[key]
        except KeyError as exc:
            raise SectionCatalogError(f"unknown catalog group: {key}") from exc

    def list_groups(self) -> list[CatalogGroup]:
        return self.groups


def load_section_catalog() -> SectionCatalog:
    project_root = Path(__file__).resolve().parent.parent
    groups_path = project_root / "config" / "section_groups.json"
    registry_path = project_root / "sections_registry.json"

    if not groups_path.exists():
        raise SectionCatalogError(f"missing section_groups.json: {groups_path}")
    if not registry_path.exists():
        raise SectionCatalogError(f"missing sections_registry.json: {registry_path}")

    raw_groups = json.loads(groups_path.read_text(encoding="utf-8"))
    raw_registry = json.loads(registry_path.read_text(encoding="utf-8"))

    registry_sections = set((raw_registry.get("sections") or {}).keys())
    groups_raw = raw_groups.get("groups")
    if not isinstance(groups_raw, list) or not groups_raw:
        raise SectionCatalogError("section_groups.json must contain non-empty groups list")

    groups: list[CatalogGroup] = []
    seen_group_keys: set[str] = set()
    covered_sections: set[str] = set()

    for item in groups_raw:
        key = str(item["key"])
        title = str(item["title"])
        sections = [str(x) for x in item["sections"]]

        if key in seen_group_keys:
            raise SectionCatalogError(f"duplicate group key: {key}")
        seen_group_keys.add(key)

        for section in sections:
            if section not in registry_sections:
                raise SectionCatalogError(f"section not found in registry: {section}")
            covered_sections.add(section)

        groups.append(CatalogGroup(key=key, title=title, sections=sections))

    missing = registry_sections - covered_sections
    if missing:
        raise SectionCatalogError(f"registry sections missing from catalog: {sorted(missing)}")

    return SectionCatalog(groups)
