"""Validation service for Work in Portugal Bot."""

import re
from typing import List, Tuple
from config import Config


def validate_phone_number(phone: str) -> bool:
    """Validate Portuguese phone number format."""
    return bool(re.match(Config.PHONE_PATTERN, phone))


def validate_username(username: str) -> bool:
    """Validate Telegram username format."""
    if not username.startswith('@'):
        return False
    
    username_part = username[1:]
    
    if len(username_part) < 5 or len(username_part) > 32:
        return False
    
    return bool(re.match(r'^[a-zA-Z0-9_]+$', username_part))


def validate_instagram(instagram: str) -> bool:
    """Validate Instagram link or username."""
    if not instagram or instagram.lower() in ['нет', 'no', 'none', '']:
        return True
    
    instagram = instagram.strip()
    
    # Расширенные паттерны для поддержки всех форматов Instagram
    patterns = [
        # Полные URL с различными протоколами
        r'^https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?$',
        r'^https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?\?.*$',
        r'^https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?#.*$',
        
        # URL без www
        r'^https?://instagram\.com/[a-zA-Z0-9._]+/?$',
        r'^https?://instagram\.com/[a-zA-Z0-9._]+/?\?.*$',
        r'^https?://instagram\.com/[a-zA-Z0-9._]+/?#.*$',
        
        # Короткие URL (instagr.am)
        r'^https?://(?:www\.)?instagr\.am/[a-zA-Z0-9._]+/?$',
        r'^https?://instagr\.am/[a-zA-Z0-9._]+/?$',
        
        # Username с @
        r'^@[a-zA-Z0-9._]+$',
        
        # Username без @ (просто имя пользователя)
        r'^[a-zA-Z0-9._]+$',
        
        # URL с поддоменами
        r'^https?://[a-zA-Z0-9._-]+\.instagram\.com/[a-zA-Z0-9._]+/?$',
        
        # Мобильные ссылки
        r'^https?://m\.instagram\.com/[a-zA-Z0-9._]+/?$',
        
        # Ссылки на посты
        r'^https?://(?:www\.)?instagram\.com/p/[a-zA-Z0-9._]+/?$',
        r'^https?://(?:www\.)?instagram\.com/reel/[a-zA-Z0-9._]+/?$',
        
        # Ссылки на истории
        r'^https?://(?:www\.)?instagram\.com/stories/[a-zA-Z0-9._]+/[a-zA-Z0-9._]+/?$'
    ]
    
    # Проверяем, соответствует ли ввод хотя бы одному паттерну
    for pattern in patterns:
        if re.match(pattern, instagram):
            return True
    
    # Дополнительная проверка: если это просто текст, проверяем, что он похож на username
    if len(instagram) >= 1 and len(instagram) <= 30:
        # Проверяем, что содержит только допустимые символы для Instagram username
        if re.match(r'^[a-zA-Z0-9._]+$', instagram):
            # Instagram username не может быть длиннее 30 символов
            if len(instagram) <= 30:
                return True
    
    return False


def validate_cities(cities: List[str]) -> bool:
    """Validate cities list."""
    if not cities:
        return False
    
    valid_cities = set(Config.CITIES.keys())
    return all(city.lower() in valid_cities for city in cities)


def validate_geotags(geotags: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate geotags for allowed values.
    Returns (is_valid, list_of_invalid_tags)
    """
    invalid_tags = []
    
    # Допустимые геотеги из конфигурации
    allowed_tags = set(Config.CITIES.keys())
    
    for tag in geotags:
        # Убираем # если есть
        clean_tag = tag.strip().lower()
        if clean_tag.startswith('#'):
            clean_tag = clean_tag[1:]
        # Нормализуем пробелы в подчёркивания (Torres Vedras -> torres_vedras)
        clean_tag = clean_tag.replace(" ", "_")
        
        # Проверяем, что тег в списке допустимых
        if clean_tag not in allowed_tags:
            invalid_tags.append(tag)
    
    return len(invalid_tags) == 0, invalid_tags


def validate_description(description: str) -> bool:
    """Validate job description."""
    if not description or len(description.strip()) < 10:
        return False
    
    words = description.strip().split()
    return len(words) >= 3


def validate_description_content(description: str) -> Tuple[bool, List[str]]:
    """
    Validate description content for forbidden elements.
    Returns (is_valid, list_of_violations)
    """
    violations = []
    
    # Проверка на хештеги (#tag)
    hashtags = re.findall(r'#\w+', description)
    if hashtags:
        violations.append(f"хештеги: {', '.join(hashtags)}")
    
    # Проверка на ссылки (http/https)
    urls = re.findall(r'https?://[^\s]+', description)
    if urls:
        violations.append(f"ссылки: {', '.join(urls)}")
    
    # Проверка на Telegram username (@username)
    telegram_usernames = re.findall(r'@[a-zA-Z0-9_]{5,32}', description)
    if telegram_usernames:
        violations.append(f"Telegram username: {', '.join(telegram_usernames)}")
    
    # Проверка на номера телефонов (различные форматы)
    phone_patterns = [
        r'\+351\s*(91|92|93|96)\s*\d{7}',  # +351 91 1234567
        r'\+351\s*(91|92|93|96)\s*\d{3}\s*\d{4}',  # +351 91 123 4567
        r'(91|92|93|96)\s*\d{7}',  # 91 1234567
        r'(91|92|93|96)\s*\d{3}\s*\d{4}',  # 91 123 4567
        r'\+351\s*(91|92|93|96)\s*\d{2}\s*\d{3}\s*\d{2}',  # +351 91 12 345 67
    ]
    
    for pattern in phone_patterns:
        phones = re.findall(pattern, description)
        if phones:
            violations.append(f"номера телефонов: {', '.join(phones)}")
            break
    
    # Проверка на email адреса
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', description)
    if emails:
        violations.append(f"email адреса: {', '.join(emails)}")
    
    # Проверка на Instagram username (@username)
    instagram_usernames = re.findall(r'@[a-zA-Z0-9._]+', description)
    if instagram_usernames:
        violations.append(f"Instagram username: {', '.join(instagram_usernames)}")
    
    # Проверка на другие социальные сети
    social_patterns = [
        r'@[a-zA-Z0-9._]+',  # Общий паттерн для username
        r'facebook\.com/[^\s]+',
        r'linkedin\.com/[^\s]+',
        r'twitter\.com/[^\s]+',
        r'x\.com/[^\s]+',
        r'youtube\.com/[^\s]+',
        r'tiktok\.com/[^\s]+',
    ]
    
    for pattern in social_patterns:
        social_links = re.findall(pattern, description, re.IGNORECASE)
        if social_links:
            violations.append(f"ссылки на соцсети: {', '.join(social_links)}")
            break
    
    return len(violations) == 0, violations


def validate_name(name: str) -> bool:
    """Validate name or company name."""
    if not name or len(name.strip()) < 2:
        return False
    
    words = name.strip().split()
    return len(words) >= 1


def parse_cities_input(cities_input: str) -> List[str]:
    """Parse cities from user input."""
    cities_input = cities_input.strip().lower()
    
    # Support multiple separators
    cities_input = cities_input.replace(" and ", ",").replace(" or ", ",").replace(";", ",")
    cities = [city.strip() for city in cities_input.split(",")]
    cities = [city for city in cities if city]
    
    return cities


# format_phone_number moved to utils.py


# format_instagram removed - using format_social_media from utils.py instead
