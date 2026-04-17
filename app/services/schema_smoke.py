from __future__ import annotations

from services.schema_bootstrap import build_schema_registry
from services.schema_flow_adapter import SchemaFlowAdapter


def run_smoke() -> None:
    registry = build_schema_registry()
    sections = registry.list_sections()
    assert "Рестораны" in sections, sections
    assert "Поговори" in sections, sections

    restaurants = SchemaFlowAdapter("Рестораны")
    assert restaurants.current_prompt()
    assert restaurants.accept_answer("да").accepted
    assert restaurants.accept_answer("Cafe Telegraf, Lisboa").accepted
    assert restaurants.accept_answer("кофе, завтраки, десерты").accepted
    assert restaurants.accept_answer("https://instagram.com/example").accepted
    assert restaurants.accept_answer("@telegraf").accepted
    assert restaurants.accept_answer("+351912345678").accepted
    assert restaurants.accept_answer("+351912345679").accepted
    assert restaurants.accept_answer("Andrey Telegraf, Cafe Telegraf").accepted
    assert restaurants.state.is_finished

    talk = SchemaFlowAdapter("Поговори")
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
