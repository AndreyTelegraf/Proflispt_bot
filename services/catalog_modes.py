"""Catalog mode registry helpers."""


def get_catalog_mode_slugs() -> set[str]:
    return set(MODE_TO_SECTION_NAME)


def get_catalog_section_name(mode: str) -> str | None:
    return MODE_TO_SECTION_NAME.get(mode)


def get_catalog_topic_id(mode: str) -> int | None:
    section_name = get_catalog_section_name(mode)
    if not section_name:
        return None

    from services.sections_registry import load_sections_registry
    registry = load_sections_registry()
    return int(registry.get_topic_id(section_name))


MODE_TO_SECTION_NAME = {
    "job_seeker":           "Ищу работу",
    "job_offer":            "Предлагаю работу",
    "realtors":             "Риелторы",
    "construction_repair":  "Строительство и ремонт",
    "home_repair":          "Бытовой ремонт и обустройство",
    "device_repair":        "Ремонт техники",
    "furniture":            "Мебель изготовление",
    "cleaning":             "Клининг",
    "home_staff":           "Домашний персонал",
    "tailoring":            "Пошив одежды",
    "cooking":              "Кулинария",
    "passenger_transport":  "Пассажирские перевозки",
    "cargo_transport":      "Грузовые перевозки",
    "car_rental":           "Прокат авто",
    "auto_service":         "Автосервис",
    "translators":          "Переводчики",
    "residence_lawyers":    "ВНЖ/Юристы",
    "marketing":            "Маркетинг",
    "it_smm":               "IT/SMM",
    "money_credit":         "Деньги/кредиты",
    "insurance":            "Страхование",
    "accountants":          "Бухгалтеры",
    "printing":             "Полиграфия",
    "health":               "Здоровье",
    "medicine":             "Медицина",
    "beauty":               "Красота",
    "teaching":             "Преподавание",
    "sport":                "Спорт",
    "animals":              "Животные",
    "restaurants":          "Рестораны",
    "leisure":              "Отдых",
    "tourism":              "Туризм",
    "photo_video":          "Фото/видео",
    "art":                  "Искусство",
}
