from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from models.posting_context import PostingContext
from services.fsm_schema_registry import CategorySchema, StepDefinition


class SchemaEngineError(RuntimeError):
    pass


@dataclass
class StepResult:
    accepted: bool
    done: bool
    stored_field_name: str | None = None
    stored_value: Any = None
    error_message: str | None = None
    stop_flow: bool = False


class SchemaEngine:
    def __init__(self, schema: CategorySchema):
        self.schema = schema

    def get_step(self, index: int) -> StepDefinition:
        if index < 0 or index >= len(self.schema.steps):
            raise SchemaEngineError(f"step index out of range: {index}")
        return self.schema.steps[index]

    def is_finished(self, index: int) -> bool:
        return index >= len(self.schema.steps)

    def process_answer(self, step: StepDefinition, answer: Any, ctx: PostingContext) -> StepResult:
        if step.kind == "info":
            return StepResult(accepted=True, done=True)

        if step.kind == "choice":
            normalized = str(answer).strip().lower()
            matched = None
            for option in step.options:
                aliases = [str(x).strip().lower() for x in option.get("aliases", [])]
                value = str(option.get("value", "")).strip().lower()
                if normalized == value or normalized in aliases:
                    matched = option
                    break

            if not matched:
                return StepResult(False, False, error_message="Некорректный вариант ответа.")

            selected_value = matched.get("value")
            if step.store_value and step.field_name:
                ctx.set_value(step.field_name, selected_value)

            stop_flow = bool(step.stop_if_negative and str(selected_value).lower() in {"no", "нет"})
            return StepResult(
                accepted=True,
                done=True,
                stored_field_name=step.field_name,
                stored_value=selected_value,
                stop_flow=stop_flow,
            )

        if step.kind in {"text", "location_or_text"}:
            value = str(answer).strip()
            if step.required and not value:
                return StepResult(False, False, error_message="Поле обязательно.")

            max_len = step.validation.get("max_len")
            if max_len and len(value) > int(max_len):
                return StepResult(False, False, error_message=f"Слишком длинный ответ. Максимум {int(max_len)} символов.")

            if step.field_name:
                ctx.set_value(step.field_name, value)

            return StepResult(True, True, stored_field_name=step.field_name, stored_value=value)

        if step.kind == "phone":
            value = str(answer).strip()

            if not value:
                if step.required:
                    return StepResult(False, False, error_message="Поле обязательно.")
                if step.field_name:
                    ctx.set_value(step.field_name, "")
                return StepResult(True, True, stored_field_name=step.field_name, stored_value="")

            pattern = step.validation.get("regex") or r"^\+351\d{9}$"
            if not re.match(pattern, value):
                return StepResult(False, False, error_message="Неверный формат номера. Используйте формат +351XXXXXXXXX.")

            if step.field_name:
                ctx.set_value(step.field_name, value)

            return StepResult(True, True, stored_field_name=step.field_name, stored_value=value)

        raise SchemaEngineError(f"unsupported step kind: {step.kind}")
