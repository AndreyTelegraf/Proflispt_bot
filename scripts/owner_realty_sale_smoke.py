import json
from pathlib import Path

from services.catalog_specialized_renderers import render_housing_listing_html

owner_schema = json.loads(Path("config/fsm_schemas/owner_real_estate.json").read_text(encoding="utf-8"))
wanted_schema = json.loads(Path("config/fsm_schemas/housing_wanted.json").read_text(encoding="utf-8"))

def option_values(schema):
    for step in schema["steps"]:
        if step.get("step_id") == "rental_term":
            return [opt.get("value") for opt in step.get("options", [])]
    raise AssertionError("rental_term step not found")

owner_values = option_values(owner_schema)
wanted_values = option_values(wanted_schema)

assert "sale" in owner_values, owner_values
assert "sale" not in wanted_values, wanted_values

html = render_housing_listing_html({
    "geo_tags": "#lisboa",
    "rental_term": "sale",
    "description": "Apartamento T2",
    "social_links": "",
    "telegram": "@owner",
    "phone_main": "+351912345678",
    "phone_whatsapp": "",
    "contact_name": "Andrey",
})

assert "#продажа" in html, html
assert "#долгосрок" not in html, html
assert "#короткосрок" not in html, html

print("OWNER_REALTY_SALE_SMOKE_OK")
