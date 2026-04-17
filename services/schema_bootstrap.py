from __future__ import annotations

from pathlib import Path

from services.fsm_schema_registry import FsmSchemaRegistry


def build_schema_registry() -> FsmSchemaRegistry:
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    schema_dir = project_root / "config" / "fsm_schemas"
    return FsmSchemaRegistry(schema_dir).load()
