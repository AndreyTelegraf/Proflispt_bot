from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SchemaRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    kind: str
    field_name: str | None
    prompt: str
    required: bool
    validation: dict[str, Any]
    options: list[dict[str, Any]]
    stop_if_negative: bool
    store_value: bool
    meta: dict[str, Any]


@dataclass(frozen=True)
class CategorySchema:
    schema_id: str
    section_name: str
    version: int
    steps: list[StepDefinition]


class FsmSchemaRegistry:
    def __init__(self, schema_dir: str | Path):
        self.schema_dir = Path(schema_dir)
        self._by_section: dict[str, CategorySchema] = {}
        self._by_id: dict[str, CategorySchema] = {}

    def load(self) -> "FsmSchemaRegistry":
        if not self.schema_dir.exists():
            raise SchemaRegistryError(f"schema dir not found: {self.schema_dir}")

        json_files = sorted(self.schema_dir.glob("*.json"))
        if not json_files:
            raise SchemaRegistryError(f"no schema json files found in: {self.schema_dir}")

        by_section: dict[str, CategorySchema] = {}
        by_id: dict[str, CategorySchema] = {}

        for path in json_files:
            raw = json.loads(path.read_text(encoding="utf-8"))
            schema = self._parse_schema(raw, path)
            if schema.section_name in by_section:
                raise SchemaRegistryError(f"duplicate section_name: {schema.section_name}")
            if schema.schema_id in by_id:
                raise SchemaRegistryError(f"duplicate schema_id: {schema.schema_id}")
            by_section[schema.section_name] = schema
            by_id[schema.schema_id] = schema

        self._by_section = by_section
        self._by_id = by_id
        return self

    def get_by_section(self, section_name: str) -> CategorySchema:
        try:
            return self._by_section[section_name]
        except KeyError as exc:
            raise SchemaRegistryError(f"unknown section_name: {section_name}") from exc

    def has_section(self, section_name: str) -> bool:
        return section_name in self._by_section

    def list_sections(self) -> list[str]:
        return sorted(self._by_section.keys())

    def _parse_schema(self, raw: dict[str, Any], path: Path) -> CategorySchema:
        required_top = ["schema_id", "section_name", "version", "steps"]
        for key in required_top:
            if key not in raw:
                raise SchemaRegistryError(f"{path}: missing top-level key: {key}")

        if not isinstance(raw["steps"], list) or not raw["steps"]:
            raise SchemaRegistryError(f"{path}: steps must be non-empty list")

        seen_ids: set[str] = set()
        steps: list[StepDefinition] = []
        for idx, item in enumerate(raw["steps"], start=1):
            step_id = item.get("step_id")
            if not step_id or not isinstance(step_id, str):
                raise SchemaRegistryError(f"{path}: step #{idx} missing valid step_id")
            if step_id in seen_ids:
                raise SchemaRegistryError(f"{path}: duplicate step_id: {step_id}")
            seen_ids.add(step_id)

            kind = item.get("kind")
            if kind not in {"choice", "text", "phone", "info", "location_or_text"}:
                raise SchemaRegistryError(f"{path}: invalid kind for step {step_id}: {kind}")

            field_name = item.get("field_name")
            prompt = item.get("prompt", "")
            if not isinstance(prompt, str) or not prompt.strip():
                raise SchemaRegistryError(f"{path}: empty prompt in step {step_id}")

            required = bool(item.get("required", False))
            validation = item.get("validation") or {}
            options = item.get("options") or []
            stop_if_negative = bool(item.get("stop_if_negative", False))
            store_value = bool(item.get("store_value", kind not in {"info"}))
            meta = item.get("meta") or {}

            if kind == "choice" and not options:
                raise SchemaRegistryError(f"{path}: choice step {step_id} requires options")

            steps.append(
                StepDefinition(
                    step_id=step_id,
                    kind=kind,
                    field_name=field_name,
                    prompt=prompt,
                    required=required,
                    validation=validation,
                    options=options,
                    stop_if_negative=stop_if_negative,
                    store_value=store_value,
                    meta=meta,
                )
            )

        return CategorySchema(
            schema_id=str(raw["schema_id"]),
            section_name=str(raw["section_name"]),
            version=int(raw["version"]),
            steps=steps,
        )
