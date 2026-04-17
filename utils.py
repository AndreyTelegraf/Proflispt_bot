"""Utility functions for Work in Portugal Bot."""

import re
import unicodedata
from typing import Optional
from urllib.parse import urlparse


def validate_phone_number(phone: str) -> bool:
    """Validate Portuguese phone number format."""
    # Portuguese phone number pattern: +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx, +35196xxxxxxx
    pattern = r'^\+351(91|92|93|96)\d{7}$'
    return bool(re.match(pattern, phone))


def validate_social_media(social_media: str) -> bool:
    """Validate any link (websites, social media, portfolio, etc.)."""
    if not social_media or social_media.lower() in ['нет', 'no', 'none', '']:
        return True
    
    social_media = social_media.strip()
    
    # Паттерны для различных социальных сетей
    patterns = [
        # Instagram
        r'^https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?',
        r'^https?://(?:www\.)?instagr\.am/[a-zA-Z0-9._]+/?',
        r'^@[a-zA-Z0-9._]+$',
        r'^[a-zA-Z0-9._]+$',
        
        # X (Twitter)
        r'^https?://(?:www\.)?x\.com/[a-zA-Z0-9._]+/?',
        r'^https?://(?:www\.)?twitter\.com/[a-zA-Z0-9._]+/?',
        r'^@[a-zA-Z0-9._]+$',
        
        # LinkedIn
        r'^https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9._-]+/?',
        r'^https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9._-]+/?',
        
        # Facebook
        r'^https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._]+/?',
        r'^https?://(?:www\.)?fb\.com/[a-zA-Z0-9._]+/?',
        
        # Threads
        r'^https?://(?:www\.)?threads\.net/@[a-zA-Z0-9._]+/?',
        
        # TikTok
        r'^https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9._]+/?',
        
        # YouTube
        r'^https?://(?:www\.)?youtube\.com/@[a-zA-Z0-9._]+/?',
        r'^https?://(?:www\.)?youtube\.com/channel/[a-zA-Z0-9._-]+/?',
        
        # Telegram
        r'^https?://t\.me/[a-zA-Z0-9._]+/?',
        r'^@[a-zA-Z0-9._]+$',
        
        # WhatsApp Business
        r'^https?://wa\.me/[0-9]+/?',
        
        # Website
        r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/?',
    ]
    
    # Проверяем, соответствует ли ввод хотя бы одному паттерну
    for pattern in patterns:
        if re.match(pattern, social_media):
            return True
    
    return False


def format_phone_number(phone: str) -> str:
    """Format phone number for display."""
    if not phone:
        return ""
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Ensure it starts with +351 and has valid prefix
    if not cleaned.startswith('+351'):
        if cleaned.startswith('351'):
            cleaned = '+' + cleaned
        else:
            # If it's just digits, assume it's missing +351 prefix
            if cleaned.isdigit() and len(cleaned) >= 7:
                cleaned = '+351' + cleaned
            else:
                cleaned = '+351' + cleaned
    
    return cleaned


def format_social_media(social_media: str) -> str:
    """Format any link (websites, social media, portfolio, etc.) for display."""
    if not social_media or social_media.lower() in ['нет', 'no', 'none']:
        return 'нет'
    
    social_media = social_media.strip()
    
    # Если это уже полная ссылка, возвращаем как есть
    if social_media.startswith('http'):
        return social_media
    
    # Убираем @ если есть
    if social_media.startswith('@'):
        social_media = social_media[1:]
    
    # Убираем лишние символы и пробелы
    social_media = re.sub(r'[^\w._]', '', social_media)
    
    # Проверяем, что username не пустой
    if not social_media:
        return 'нет'
    
    # Добавляем @ если его нет
    if not social_media.startswith('@'):
        social_media = '@' + social_media
    
    return social_media


def get_social_media_name(url: str) -> str:
    """Extract platform name from any URL (websites, social media, portfolio, etc.)."""
    if not url or url.lower() in ['нет', 'no', 'none']:
        return ''
    
    url = url.lower().strip()
    
    # Определяем название социальной сети по URL
    if 'instagram.com' in url or 'instagr.am' in url:
        return 'Instagram'
    elif 'x.com' in url or 'twitter.com' in url:
        return 'X (Twitter)'
    elif 'linkedin.com' in url:
        return 'LinkedIn'
    elif 'facebook.com' in url or 'fb.com' in url:
        return 'Facebook'
    elif 'threads.net' in url:
        return 'Threads'
    elif 'tiktok.com' in url:
        return 'TikTok'
    elif 'youtube.com' in url:
        return 'YouTube'
    elif 't.me' in url:
        return 'Telegram'
    elif 'wa.me' in url:
        return 'WhatsApp'
    else:
        return 'Website'


def clean_text(text: str) -> str:
    """Remove empty lines and normalize text formatting."""
    if not text:
        return ""
    
    # Split into lines and remove empty lines
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove leading/trailing whitespace
        stripped_line = line.strip()
        # Only add non-empty lines
        if stripped_line:
            cleaned_lines.append(stripped_line)
    
    # Join lines back together
    return '\n'.join(cleaned_lines)


def clean_user_input(text: str) -> str:
    """Clean user input by removing empty lines and normalizing formatting."""
    if not text:
        return ""
    
    # Remove empty lines and normalize line breaks
    cleaned = clean_text(text)
    
    # Replace all whitespace sequences with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned


def format_description_for_preview(description: str, max_length: int = 100) -> str:
    """Format description for preview with proper truncation."""
    if not description:
        return ""
    
    # Clean the description
    cleaned = clean_user_input(description)
    
    # Truncate if too long
    if len(cleaned) > max_length:
        # Try to truncate at word boundary
        truncated = cleaned[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.7:  # If we can find a space in the last 30%
            truncated = truncated[:last_space]
        return truncated + '...'
    
    return cleaned


def is_emoji(character: str) -> bool:
    """Check if a character is an emoji."""
    return unicodedata.category(character) == 'So' or character in [
        # Common emoji categories that might not be caught by unicodedata
        '\U0001F600', '\U0001F601', '\U0001F602', '\U0001F603', '\U0001F604',
        '\U0001F605', '\U0001F606', '\U0001F607', '\U0001F608', '\U0001F609',
        '\U0001F60A', '\U0001F60B', '\U0001F60C', '\U0001F60D', '\U0001F60E',
        '\U0001F60F', '\U0001F610', '\U0001F611', '\U0001F612', '\U0001F613',
        '\U0001F614', '\U0001F615', '\U0001F616', '\U0001F617', '\U0001F618',
        '\U0001F619', '\U0001F61A', '\U0001F61B', '\U0001F61C', '\U0001F61D',
        '\U0001F61E', '\U0001F61F', '\U0001F620', '\U0001F621', '\U0001F622',
        '\U0001F623', '\U0001F624', '\U0001F625', '\U0001F626', '\U0001F627',
        '\U0001F628', '\U0001F629', '\U0001F62A', '\U0001F62B', '\U0001F62C',
        '\U0001F62D', '\U0001F62E', '\U0001F62F', '\U0001F630', '\U0001F631',
        '\U0001F632', '\U0001F633', '\U0001F634', '\U0001F635', '\U0001F636',
        '\U0001F637', '\U0001F638', '\U0001F639', '\U0001F63A', '\U0001F63B',
        '\U0001F63C', '\U0001F63D', '\U0001F63E', '\U0001F63F', '\U0001F640',
        '\U0001F641', '\U0001F642', '\U0001F643', '\U0001F644', '\U0001F645',
        '\U0001F646', '\U0001F647', '\U0001F648', '\U0001F649', '\U0001F64A',
        '\U0001F64B', '\U0001F64C', '\U0001F64D', '\U0001F64E', '\U0001F64F',
        # Hearts and symbols
        '❤️', '💙', '💚', '💛', '🧡', '💜', '🖤', '🤍', '🤎', '💔', '❣️', '💕',
        '💖', '💗', '💘', '💝', '💞', '💟', '♥️', '💯', '💢', '💫', '💦', '💨',
        # Common symbols
        '⭐', '✨', '🌟', '💥', '🔥', '✅', '❌', '⚠️', '🚀', '🎉', '🎊'
    ]


def remove_emojis(text: str) -> str:
    """Remove emojis from text."""
    if not text:
        return ""
    
    # Remove using regex patterns for emoji ranges
    emoji_patterns = [
        r'[\U0001F600-\U0001F64F]',  # emoticons
        r'[\U0001F300-\U0001F5FF]',  # symbols & pictographs
        r'[\U0001F680-\U0001F6FF]',  # transport & map symbols
        r'[\U0001F1E0-\U0001F1FF]',  # flags (iOS)
        r'[\U00002600-\U000027BF]',  # misc symbols
        r'[\U0001f926-\U0001f937]',  # additional emoticons
        r'[\U00010000-\U0010ffff]',  # supplementary multilingual plane
        r'[\u2600-\u27bf]',          # misc symbols
        r'[\u2b50]',                 # star
        r'[\u2705]',                 # check mark
        r'[\u274c]',                 # cross mark
        r'[\u26a0]',                 # warning sign
        r'[\u2764]',                 # heart
        r'[\u2728]',                 # sparkles
        r'[\u2b55]',                 # heavy large circle
        r'[\u274e]',                 # negative squared cross mark
        r'[\u2757]',                 # heavy exclamation mark
        r'[\u27a1]',                 # black rightwards arrow
        r'[\u2b06]',                 # upwards black arrow
        r'[\u2b07]',                 # downwards black arrow
        r'[\u2b05]',                 # leftwards black arrow
        r'[\u25b6]',                 # black right-pointing triangle
        r'[\u25c0]',                 # black left-pointing triangle
        r'[\u23ea]',                 # black left-pointing double triangle
        r'[\u23e9]',                 # black right-pointing double triangle
    ]
    
    cleaned = text
    for pattern in emoji_patterns:
        cleaned = re.sub(pattern, '', cleaned)
    
    # Also remove variation selectors (emoji modifiers)
    cleaned = re.sub(r'[\ufe0e\ufe0f]', '', cleaned)
    
    # Remove text-based "emojis" like !! and similar patterns
    text_emoji_patterns = [
        r'!!+',                     # Multiple exclamation marks
        r'\?\?+',                   # Multiple question marks
        r'!{2,}',                   # Two or more exclamation marks
        r'\?{2,}',                  # Two or more question marks
        r'[!?]{3,}',                # Three or more mixed ! and ?
    ]
    
    for pattern in text_emoji_patterns:
        cleaned = re.sub(pattern, '', cleaned)
    
    return cleaned


def remove_formatting(text: str) -> str:
    """Remove Telegram formatting markup from text."""
    if not text:
        return ""
    
    # Remove Telegram formatting
    formatting_patterns = [
        r'\*\*(.*?)\*\*',      # **bold**
        r'__(.*?)__',          # __italic__
        r'`(.*?)`',            # `code`
        r'```(.*?)```',        # ```code block```
        r'~~(.*?)~~',          # ~~strikethrough~~
        r'\[(.*?)\]\(.*?\)',   # [text](link)
        r'@(\w+)',             # @mentions (keep the username part)
        r'#(\w+)',             # #hashtags (keep the hashtag part)
    ]
    
    cleaned = text
    
    # Replace formatted text with just the text content
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)  # bold
    cleaned = re.sub(r'__(.*?)__', r'\1', cleaned)      # italic
    cleaned = re.sub(r'`(.*?)`', r'\1', cleaned)        # code
    cleaned = re.sub(r'```(.*?)```', r'\1', cleaned)    # code block
    cleaned = re.sub(r'~~(.*?)~~', r'\1', cleaned)      # strikethrough
    cleaned = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', cleaned)  # links
    
    # Keep mentions and hashtags but clean them
    cleaned = re.sub(r'@(\w+)', r'@\1', cleaned)  # mentions
    cleaned = re.sub(r'#(\w+)', r'#\1', cleaned)  # hashtags
    
    return cleaned


def remove_media_references(text: str) -> str:
    """Remove media file references and URLs from text."""
    if not text:
        return ""
    
    # Remove URLs
    url_patterns = [
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        r'ftp://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    ]
    
    cleaned = text
    for pattern in url_patterns:
        cleaned = re.sub(pattern, '', cleaned)
    
    # Remove common media file extensions
    media_patterns = [
        r'\S+\.(jpg|jpeg|png|gif|bmp|svg|webp|ico)',  # images
        r'\S+\.(mp4|avi|mov|wmv|flv|mkv|webm)',       # videos
        r'\S+\.(mp3|wav|flac|aac|ogg|m4a)',           # audio
        r'\S+\.(pdf|doc|docx|xls|xlsx|ppt|pptx)',     # documents
        r'\S+\.(zip|rar|7z|tar|gz)',                  # archives
    ]
    
    for pattern in media_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    return cleaned


def clean_user_input_advanced(text: str) -> str:
    """Advanced cleaning of user input - removes emojis, formatting, media references, and URLs."""
    if not text:
        return ""
    
    # Start with basic cleaning
    cleaned = clean_user_input(text)
    
    # Remove emojis
    cleaned = remove_emojis(cleaned)
    
    # Remove formatting
    cleaned = remove_formatting(cleaned)
    
    # Remove URLs from text since they will be added separately as links
    cleaned = remove_urls_from_text(cleaned)
    
    # Final cleanup - remove extra spaces and empty lines
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned


def clean_user_input_for_links(text: str) -> str:
    """Clean user input for links - removes emojis and formatting but preserves URLs."""
    if not text:
        return ""
    
    # Start with basic cleaning
    cleaned = clean_user_input(text)
    
    # Remove emojis
    cleaned = remove_emojis(cleaned)
    
    # Remove formatting
    cleaned = remove_formatting(cleaned)
    
    # Final cleanup - remove extra spaces and empty lines
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned


def clean_text_advanced(text: str) -> str:
    """Advanced cleaning that preserves line breaks but removes emojis, formatting, and URLs."""
    if not text:
        return ""
    
    # Start with basic line cleaning
    cleaned = clean_text(text)
    
    # Remove emojis
    cleaned = remove_emojis(cleaned)
    
    # Remove formatting
    cleaned = remove_formatting(cleaned)
    
    # Remove URLs from text since they will be added separately as links
    cleaned = remove_urls_from_text(cleaned)
    
    return cleaned


def remove_urls_from_text(text: str) -> str:
    """Remove URLs from text while preserving other content."""
    if not text:
        return ""
    
    # Remove full URLs (http/https) with optional trailing punctuation
    text = re.sub(r'https?://[^\s,]+(?:\s|,|$)', ' ', text)
    
    # Remove www URLs with optional trailing punctuation
    text = re.sub(r'www\.[^\s,]+(?:\s|,|$)', ' ', text)
    
    # Remove domain-only URLs (like example.com) with optional trailing punctuation
    # More comprehensive pattern that handles various domain formats
    text = re.sub(r'\b[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.([a-zA-Z]{2,})\b(?:\s|,|$)', ' ', text)
    
    # Additional pattern for domains that might not be caught by the above
    text = re.sub(r'\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}\b(?:\s|,|$)', ' ', text)
    
    # Clean up extra whitespace and punctuation artifacts
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*,\s*', ', ', text)  # Fix comma spacing
    text = re.sub(r'\s*\.\s*', '. ', text)  # Fix period spacing
    text = text.strip()
    
    return text


def extract_domain_from_url(url: str) -> str:
    """Extract domain name from URL."""
    if not url:
        return ""
    
    try:
        # If URL doesn't start with protocol, add one for parsing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Parse URL
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Check if we got a valid domain
        if not domain or '.' not in domain:
            return ""
        
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        return domain
    except Exception:
        return ""


def format_link_with_domain(url: str) -> str:
    """Format link with domain name as label."""
    if not url or url.lower() in ['нет', 'no', 'none', '']:
        return 'нет'
    
    # Clean the URL
    url = clean_user_input(url.strip())
    
    # Extract domain
    domain = extract_domain_from_url(url)
    
    if not domain:
        # If we can't extract domain, return the original URL
        return url
    
    # Format as "Domain: URL"
    return f"{domain}: {url}"


def validate_any_link(link: str) -> bool:
    """Validate any type of link (website, social media, etc.)."""
    if not link or link.lower() in ['нет', 'no', 'none', '']:
        return True
    
    link = link.strip()
    
    # Basic URL patterns
    url_patterns = [
        r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'^www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    ]
    
    # Social media patterns
    social_patterns = [
        r'^@[a-zA-Z0-9._]+$',  # @username
        r'^[a-zA-Z0-9._]+$',   # username only
    ]
    
    # Check URL patterns
    for pattern in url_patterns:
        if re.match(pattern, link):
            return True
    
    # Check social media patterns
    for pattern in social_patterns:
        if re.match(pattern, link):
            return True
    
    return False


def get_short_domain_name(url: str) -> str:
    """Extract short domain name from URL (e.g., 'instagram' from 'instagram.com')."""
    if not url or url.lower() in ['нет', 'no', 'none', '']:
        return 'нет'
    
    url = url.strip()
    domain = extract_domain_from_url(url)
    
    if not domain:
        return url
    
    # Remove www. prefix if present
    if domain.startswith('www.'):
        domain = domain[4:]
    
    # Special handling for short domains
    short_domain_mapping = {
        't.me': 'telegram',
        'wa.me': 'whatsapp',
        'fb.com': 'facebook',
        'instagr.am': 'instagram',
    }
    
    # Check for exact domain match first
    if domain in short_domain_mapping:
        return short_domain_mapping[domain]
    
    # Split by dots and take the main part (before first dot)
    parts = domain.split('.')
    if parts:
        return parts[0]
    
    return domain


def format_link_as_markdown(url: str) -> str:
    """Format URL as Markdown link with short domain name as text."""
    if not url or url.lower() in ['нет', 'no', 'none', '']:
        return 'нет'
    
    url = url.strip()
    domain = extract_domain_from_url(url)
    
    # Handle usernames (like @username)
    if url.startswith('@') and not domain:
        return url
    
    if not domain:
        return url
    
    # Get short domain name for display
    short_name = get_short_domain_name(url)
    
    # Escape only the short_name text for Markdown (not the URL - URLs should not be escaped)
    # For Markdown v1, we only need to escape special characters in the text part
    escaped_short_name = escape_markdown(short_name)
    
    # Format as Markdown link: [text](url)
    # URL should NOT be escaped - Telegram Markdown parser handles URLs correctly
    return f"[{escaped_short_name}]({url})"


def format_link_as_html(url: str) -> str:
    """Format URL as HTML link with short domain name as text."""
    if not url or url.lower() in ['нет', 'no', 'none', '']:
        return 'нет'
    
    url = url.strip()
    domain = extract_domain_from_url(url)
    
    # Handle usernames (like @username)
    if url.startswith('@') and not domain:
        return url
    
    if not domain:
        return url
    
    # Get short domain name for display
    short_name = get_short_domain_name(url)
    
    # HTML escape function
    def escape_html(text):
        if not text:
            return text
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Escape both the short_name and URL for HTML
    escaped_short_name = escape_html(short_name)
    escaped_url = escape_html(url)
    
    # Format as HTML link: <a href="url">text</a>
    return f'<a href="{escaped_url}">{escaped_short_name}</a>'


def get_link_type_and_name(url: str) -> tuple[str, str]:
    """Get link type and formatted name from URL."""
    if not url or url.lower() in ['нет', 'no', 'none', '']:
        return 'нет', 'нет'
    
    url = url.strip()
    domain = extract_domain_from_url(url)
    
    # Handle usernames (like @username)
    if url.startswith('@') and not domain:
        return 'Username', url
    
    if not domain:
        return 'website', url
    
    # Get short domain name for display
    short_name = get_short_domain_name(url)
    
    # Map common domains to readable names
    domain_mapping = {
        'instagram.com': 'Instagram',
        'instagr.am': 'Instagram',
        'facebook.com': 'Facebook',
        'fb.com': 'Facebook',
        'twitter.com': 'X (Twitter)',
        'x.com': 'X (Twitter)',
        'linkedin.com': 'LinkedIn',
        'youtube.com': 'YouTube',
        'tiktok.com': 'TikTok',
        'threads.net': 'Threads',
        't.me': 'Telegram',
        'wa.me': 'WhatsApp',
        'github.com': 'GitHub',
        'medium.com': 'Medium',
        'reddit.com': 'Reddit',
        'pinterest.com': 'Pinterest',
        'snapchat.com': 'Snapchat',
        'discord.com': 'Discord',
        'telegram.org': 'Telegram',
        'whatsapp.com': 'WhatsApp',
    }
    
    # Check for exact domain match
    if domain in domain_mapping:
        return domain_mapping[domain], f"{short_name}: {url}"
    
    # Check for subdomain matches
    for known_domain, name in domain_mapping.items():
        if domain.endswith('.' + known_domain) or domain == known_domain:
            return name, f"{short_name}: {url}"
    
    # If no match found, use short domain name for regular websites
    return 'Website', f"{short_name}: {url}"


def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown (v1) - only escape _, *, `, [."""
    if not text:
        return text
    return text.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')


def get_first_words(text: str, max_words: int = 5) -> str:
    """
    Get first N words from text, cleaned and formatted.
    
    Args:
        text: Input text
        max_words: Maximum number of words to return
        
    Returns:
        String with first N words, or empty string if no text
    """
    if not text:
        return ""
    
    # Clean the text
    cleaned = clean_text_advanced(text)
    if not cleaned:
        return ""
    
    # Split into words and take first N
    words = cleaned.split()[:max_words]
    
    # Join words and limit total length
    result = " ".join(words)
    if len(result) > 50:  # Limit to 50 characters
        result = result[:47] + "..."
    
    return result


def format_posting_card(posting: dict) -> str:
    """
    Format posting as a full card with exact same format as published post (excluding contacts).
    
    Args:
        posting: Dictionary with posting data
        
    Returns:
        Formatted string for posting card
    """
    if not posting:
        return "Объявление не найдено"
    
    lines = []
    
    # 1. Hashtags (exactly like in published posts)
    hashtags = []
    cities = posting.get('cities', '')
    if cities:
        # Parse cities if it's a JSON string
        if isinstance(cities, str) and cities.startswith('['):
            try:
                import json
                cities_list = json.loads(cities)
            except:
                cities_list = []
        else:
            cities_list = [cities] if cities else []
    else:
        cities_list = []
    
    for city in cities_list:
        if city == "online":
            hashtags.append("#online")
        else:
            hashtags.append(f"#{city}")
    
    if hashtags:
        lines.append(" ".join(hashtags))
    
    # 2. Description (cleaned with advanced cleaning for publication)
    description = posting.get('description', '')
    if description:
        cleaned_description = clean_text_advanced(description)
        lines.append(cleaned_description)
    
    # 3. Links (websites, social media, portfolio, etc.)
    social_media = posting.get('social_media', '')
    if social_media and social_media.lower() not in ['нет', 'no', 'none', '']:
        try:
            import json
            links = json.loads(social_media) if social_media.startswith('[') else [social_media] if social_media != 'нет' else []
            for link in links:
                formatted_link = format_link_as_markdown(link)
                lines.append(formatted_link)
        except (json.JSONDecodeError, AttributeError):
            # Fallback for old format
            formatted_link = format_link_as_markdown(social_media)
            lines.append(formatted_link)
    
    # Note: We exclude contacts (telegram_username, phone_main, phone_whatsapp, name)
    # as requested by user
    
    return "\n".join(lines)
