from __future__ import annotations

from services.schema_bootstrap import build_schema_registry
from services.schema_flow_adapter import SchemaFlowAdapter


def run_smoke() -> None:
    registry = build_schema_registry()
    sections = registry.list_sections()
    assert "Спорт" in sections, sections
    assert "Поговори со мной" in sections, sections

    sport = SchemaFlowAdapter("Спорт")
    assert sport.current_prompt()
    assert sport.accept_answer("да").accepted
    assert sport.accept_answer("lisboa").accepted
    assert sport.accept_answer("персональные тренировки, плавание, йога").accepted
    assert sport.accept_answer("https://instagram.com/example").accepted
    assert sport.accept_answer("+351912345678").accepted
    assert sport.accept_answer("+351912345679").accepted
    assert sport.accept_answer("Andrey Telegraf, Sport Telegraf").accepted
    assert sport.state.is_finished

    talk = SchemaFlowAdapter("Поговори со мной")
    assert talk.current_prompt()
    assert talk.accept_answer("да").accepted
    assert talk.accept_answer("мужчина, 40+, высшее").accepted
    assert talk.accept_answer("русский, португальский; будни 10-18; не говорю о религии").accepted
    assert talk.accept_answer("@telegraf").accepted
    assert talk.accept_answer("").accepted
    assert talk.accept_answer("").accepted
    assert talk.accept_answer("Andrey Telegraf").accepted
    assert talk.state.is_finished


if __name__ == "__main__":
    run_smoke()
    print("SCHEMA_SMOKE=OK")
