"""Formatting service for Work in Portugal Bot."""

from typing import List
from models.job_posting import JobPosting
from utils import format_social_media, get_social_media_name, clean_text, clean_user_input, clean_text_advanced, clean_user_input_advanced, get_link_type_and_name, remove_urls_from_text, format_link_as_markdown, format_link_as_html, format_phone_number
from config import Config


def format_job_posting(posting: JobPosting) -> str:
    """Format job posting for publication."""
    lines = []
    
    # 1. Hashtags
    hashtags = []
    for city in posting.cities:
        if city == "online":
            hashtags.append("#online")
        else:
            hashtags.append(f"#{city}")
    
    lines.append(" ".join(hashtags))
    
    # 2. Description (cleaned with advanced cleaning for publication)
    cleaned_description = clean_text_advanced(posting.description)
    
    lines.append(cleaned_description)
    
    # 3. Links (websites, social media, portfolio, etc.)
    if posting.social_media and posting.social_media.lower() not in ['нет', 'no', 'none', '']:
        try:
            import json
            links = json.loads(posting.social_media) if posting.social_media.startswith('[') else [posting.social_media] if posting.social_media != 'нет' else []
            for link in links:
                formatted_link = format_link_as_markdown(link)
                lines.append(formatted_link)
        except (json.JSONDecodeError, AttributeError):
            # Fallback for old format
            formatted_link = format_link_as_markdown(posting.social_media)
            lines.append(formatted_link)
    
    # 4. Telegram username (escape special characters for Markdown v1)
    # Use escape_markdown to properly escape all special characters
    from utils import escape_markdown
    escaped_username = escape_markdown(posting.telegram_username)
    lines.append(escaped_username)
    
    # 5. Phone numbers
    lines.append(format_phone_number(posting.phone_main))
    
    # 6. WhatsApp (only if different from main phone)
    if posting.phone_whatsapp and posting.phone_whatsapp != posting.phone_main:
        if posting.phone_whatsapp.lower() not in ['нет', 'no', 'none', '']:
            lines.append(format_phone_number(posting.phone_whatsapp))
    
    # 7. Name
    lines.append(f"- {posting.name}")
    
    return "\n".join(lines)


def format_job_posting_html(posting: JobPosting) -> str:
    """Format job posting for publication using HTML (fixes underscore in usernames)."""
    def escape_html(text):
        if not text:
            return text
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    lines = []

    # 1. Hashtags
    hashtags = []
    for city in posting.cities:
        if city == "online":
            hashtags.append("#online")
        else:
            hashtags.append(f"#{city}")
    lines.append(" ".join(hashtags))

    # 2. Description
    cleaned_description = clean_text_advanced(posting.description)
    lines.append(escape_html(cleaned_description))

    # 3. Links
    if posting.social_media and posting.social_media.lower() not in ['нет', 'no', 'none', '']:
        try:
            import json
            links = json.loads(posting.social_media) if posting.social_media.startswith('[') else [posting.social_media] if posting.social_media != 'нет' else []
            for link in links:
                formatted_link = format_link_as_html(link)
                lines.append(formatted_link)
        except (json.JSONDecodeError, AttributeError):
            formatted_link = format_link_as_html(posting.social_media)
            lines.append(formatted_link)

    # 4. Telegram username (HTML - no underscore escaping issues)
    telegram_username = posting.telegram_username
    if telegram_username and telegram_username.startswith('@'):
        lines.append(f'<a href="https://t.me/{escape_html(telegram_username[1:])}">{escape_html(telegram_username)}</a>')
    else:
        lines.append(escape_html(telegram_username))

    # 5. Phone numbers
    lines.append(escape_html(format_phone_number(posting.phone_main)))

    # 6. WhatsApp
    if posting.phone_whatsapp and posting.phone_whatsapp != posting.phone_main:
        if posting.phone_whatsapp.lower() not in ['нет', 'no', 'none', '']:
            lines.append(escape_html(format_phone_number(posting.phone_whatsapp)))

    # 7. Name
    lines.append(f"- {escape_html(posting.name)}")

    return "\n".join(lines)


def format_preview(posting: JobPosting) -> str:
    """Format job posting preview - shows full posting text like in premium posts."""
    lines = []
    
    # 1. Header
    lines.append("📋 Предварительный просмотр")
    
    # 2. Hashtags
    hashtags = []
    for city in posting.cities:
        if city == "online":
            hashtags.append("#online")
        else:
            hashtags.append(f"#{city}")
    
    lines.append(" ".join(hashtags))
    
    # 3. Description (cleaned with advanced cleaning for publication)
    cleaned_description = clean_text_advanced(posting.description)
    lines.append(cleaned_description)
    
    # 4. Links (websites, social media, portfolio, etc.)
    if posting.social_media and posting.social_media.lower() not in ['нет', 'no', 'none', '']:
        try:
            import json
            links = json.loads(posting.social_media) if posting.social_media.startswith('[') else [posting.social_media] if posting.social_media != 'нет' else []
            for link in links:
                formatted_link = format_link_as_markdown(link)
                lines.append(formatted_link)
        except (json.JSONDecodeError, AttributeError):
            # Fallback for old format
            formatted_link = format_link_as_markdown(posting.social_media)
            lines.append(formatted_link)
    
    # 5. Telegram username (escape special characters for Markdown v1)
    # Use escape_markdown to properly escape all special characters
    from utils import escape_markdown
    escaped_username = escape_markdown(posting.telegram_username)
    lines.append(escaped_username)
    
    # 6. Phone numbers
    lines.append(format_phone_number(posting.phone_main))
    
    # 7. WhatsApp (only if different from main phone)
    if posting.phone_whatsapp and posting.phone_whatsapp != posting.phone_main:
        if posting.phone_whatsapp.lower() not in ['нет', 'no', 'none', '']:
            lines.append(format_phone_number(posting.phone_whatsapp))
    
    # 8. Name
    lines.append(f"- {posting.name}")
    
    return "\n".join(lines)


def format_user_postings_list(postings: List[JobPosting]) -> str:
    """Format list of user's postings."""
    if not postings:
        return "У вас пока нет опубликованных объявлений."
    
    result = "📋 *Ваши объявления:*\n\n"
    
    for i, posting in enumerate(postings, 1):
        mode_emoji = "🔍" if posting.mode == "seeking" else "💼"
        mode_text = "Ищу работу" if posting.mode == "seeking" else "Предлагаю работу"
        cities_text = ", ".join([Config.CITIES.get(city, city) for city in posting.cities])
        
        # Clean description for list view
        cleaned_description = clean_user_input_advanced(posting.description)
        
        list_description = cleaned_description[:50] + ('...' if len(cleaned_description) > 50 else '')
        
        # Escape special characters for MarkdownV2
        def escape_markdown(text):
            if not text:
                return text
            return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
        
        result += f"{i}\\. {mode_emoji} *{mode_text}*\n"
        result += f"   📍 {escape_markdown(cities_text)}\n"
        result += f"   📝 {escape_markdown(list_description)}\n"
        result += f"   📅 {escape_markdown(posting.created_at.strftime('%d.%m.%Y') if posting.created_at else 'N/A')}\n"
        result += f"   🆔 ID: {posting.id}\n\n"
    
    return result


def format_premium_posting(post: dict) -> str:
    """Format premium posting for publication."""
    # Escape special characters for MarkdownV2
    def escape_markdown(text):
        if not text:
            return text
        return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
    
    lines = []
    
    # 1. Hashtags (like in regular posts)
    hashtags = []
    cities = post.get('cities', ['online'])  # Default to online if not specified
    for city in cities:
        if city == "online":
            hashtags.append("#online")
        else:
            hashtags.append(f"#{city}")
    
    lines.append(" ".join(hashtags))
    
    # 2. Premium badge and section
    section_emoji = "🔍" if post['mode'] == 'job_seeker' else "💰"
    section_text = "Ищу работу" if post['mode'] == 'job_seeker' else "Предлагаю работу"
    lines.append(f"💎 {section_emoji} *{section_text}*")
    
    # 3. Description (cleaned for publication)
    from utils import clean_text_advanced
    cleaned_description = clean_text_advanced(post['description'])
    lines.append(escape_markdown(cleaned_description))
    
    # 4. Social media (formatted as links)
    if post['social_media'] and post['social_media'].lower() not in ['нет', 'no', 'none', '']:
        try:
            import json
            links = json.loads(post['social_media']) if post['social_media'].startswith('[') else [post['social_media']] if post['social_media'] != 'нет' else []
            for link in links:
                formatted_link = format_link_as_markdown(link)
                lines.append(formatted_link)
        except (json.JSONDecodeError, AttributeError):
            # Fallback for old format
            formatted_link = format_link_as_markdown(post['social_media'])
            lines.append(formatted_link)
    
    # 5. Telegram username
    lines.append(escape_markdown(post['telegram_username']))
    
    # 6. Phone numbers
    lines.append(escape_markdown(post['phone_main']))
    
    # 7. WhatsApp (only if different from main phone)
    if post['phone_whatsapp'] and post['phone_whatsapp'] != post['phone_main']:
        if post['phone_whatsapp'].lower() not in ['нет', 'no', 'none', '']:
            lines.append(escape_markdown(post['phone_whatsapp']))
    
    # 8. Name
    lines.append(f"\\- {escape_markdown(post['name'])}")
    
    return "\n".join(lines)


def format_premium_posting_html(post: dict) -> str:
    """Format premium posting for publication using HTML."""
    # HTML escape function
    def escape_html(text):
        if not text:
            return text
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    lines = []
    
    # 1. Hashtags (like in regular posts)
    hashtags = []
    cities = post.get('cities', ['online'])  # Default to online if not specified
    for city in cities:
        if city == "online":
            hashtags.append("#online")
        else:
            hashtags.append(f"#{city}")
    
    lines.append(" ".join(hashtags))
    
    # 2. Premium badge and section
    section_emoji = "🔍" if post['mode'] == 'job_seeker' else "💰"
    section_text = "Ищу работу" if post['mode'] == 'job_seeker' else "Предлагаю работу"
    lines.append(f"💎 {section_emoji} <b>{section_text}</b>")
    
    # 3. Description (cleaned for publication)
    from utils import clean_text_advanced
    cleaned_description = clean_text_advanced(post['description'])
    lines.append(escape_html(cleaned_description))
    
    # 4. Social media (formatted as HTML links)
    if post['social_media'] and post['social_media'].lower() not in ['нет', 'no', 'none', '']:
        try:
            import json
            links = json.loads(post['social_media']) if post['social_media'].startswith('[') else [post['social_media']] if post['social_media'] != 'нет' else []
            for link in links:
                formatted_link = format_link_as_html(link)
                lines.append(formatted_link)
        except (json.JSONDecodeError, AttributeError):
            # Fallback for old format
            formatted_link = format_link_as_html(post['social_media'])
            lines.append(formatted_link)
    
    # 5. Telegram username (make it clickable if it starts with @)
    telegram_username = post['telegram_username']
    if telegram_username and telegram_username.startswith('@'):
        # Make it a clickable link
        lines.append(f'<a href="https://t.me/{telegram_username[1:]}">{escape_html(telegram_username)}</a>')
    else:
        lines.append(escape_html(telegram_username))
    
    # 6. Phone numbers
    lines.append(escape_html(post['phone_main']))
    
    # 7. WhatsApp (only if different from main phone)
    if post['phone_whatsapp'] and post['phone_whatsapp'] != post['phone_main']:
        if post['phone_whatsapp'].lower() not in ['нет', 'no', 'none', '']:
            lines.append(escape_html(post['phone_whatsapp']))
    
    # 8. Name
    lines.append(f"- {escape_html(post['name'])}")
    
    return "\n".join(lines)
