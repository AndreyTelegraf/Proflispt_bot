from __future__ import annotations

from dataclasses import dataclass

from models.posting_context import PostingContext
from services.schema_bootstrap import build_schema_registry
from services.schema_engine import SchemaEngine, StepResult


@dataclass
class FlowState:
    section_name: str
    step_index: int = 0
    is_finished: bool = False
    is_stopped: bool = False


class SchemaFlowAdapter:
    def __init__(self, section_name: str):
        registry = build_schema_registry()
        schema = registry.get_by_section(section_name)
        self.engine = SchemaEngine(schema)
        self.ctx = PostingContext(section_name=section_name)
        self.state = FlowState(section_name=section_name)

    def current_prompt(self) -> str:
        if self.state.is_finished or self.state.is_stopped:
            return ""
        step = self.engine.get_step(self.state.step_index)
        return step.prompt

    def accept_answer(self, answer: str) -> StepResult:
        if self.state.is_finished or self.state.is_stopped:
            raise RuntimeError("flow already completed")

        step = self.engine.get_step(self.state.step_index)
        result = self.engine.process_answer(step, answer, self.ctx)

        if not result.accepted:
            return result

        self.state.step_index += 1

        if result.stop_flow:
            self.state.is_stopped = True
            return result

        while not self.engine.is_finished(self.state.step_index):
            next_step = self.engine.get_step(self.state.step_index)
            if next_step.kind != "info":
                break
            _ = self.engine.process_answer(next_step, "", self.ctx)
            self.state.step_index += 1

        if self.engine.is_finished(self.state.step_index):
            self.state.is_finished = True

        return result

    def export_context(self) -> dict:
        return self.ctx.as_dict()
