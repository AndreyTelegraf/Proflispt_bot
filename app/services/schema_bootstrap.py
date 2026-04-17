from __future__ import annotations

from pathlib import Path

from services.fsm_schema_registry import FsmSchemaRegistry


def build_schema_registry() -> FsmSchemaRegistry:
    current_file = Path(__file__).resolve()
    app_root = current_file.parent.parent
    schema_dir = app_root / "config" / "fsm_schemas"
    return FsmSchemaRegistry(schema_dir).load()
