"""Catalog mode registry helpers."""


def get_catalog_mode_slugs() -> set[str]:
    return set(MODE_TO_SECTION_NAME)


def get_catalog_section_name(mode: str) -> str | None:
    return MODE_TO_SECTION_NAME.get(mode)


MODE_TO_SECTION_NAME = {
    "accountants": "Бухгалтеры",
    "animals": "Животные",
    "art": "Искусство",
    "auto_service": "Автосервис",
    "beauty": "Красота",
    "car_rental": "Аренда авто",
    "cargo_transport": "Грузоперевозки",
    "cleaning": "Клининг",
    "construction_repair": "Стройка и ремонт",
    "cooking": "Кулинария",
    "device_repair": "Ремонт техники",
    "furniture": "Мебель",
    "health": "Здоровье",
    "home_repair": "Домашний ремонт",
    "home_staff": "Домашний персонал",
    "insurance": "Страхование",
    "it_smm": "IT / SMM",
    "leisure": "Досуг",
    "marketing": "Маркетинг",
    "medicine": "Медицина",
    "money_credit": "Деньги и кредиты",
    "passenger_transport": "Пассажирские перевозки",
    "photo_video": "Фото и видео",
    "printing": "Полиграфия",
    "realtors": "Риэлторы",
    "residence_lawyers": "Юристы по легализации",
    "sport": "Спорт",
    "tailoring": "Пошив и ремонт одежды",
    "teaching": "Обучение",
    "tourism": "Туризм",
    "translators": "Переводчики",
}
