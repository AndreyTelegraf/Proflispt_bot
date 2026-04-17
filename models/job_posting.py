"""Job posting model for Work in Portugal Bot."""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class JobPosting:
    """Job posting data model."""
    
    id: Optional[int] = None
    user_id: Optional[int] = None
    mode: str = ""  # 'seeking' or 'offering'
    cities: List[str] = None
    description: str = ""
    social_media: Optional[str] = None  # JSON string of links (websites, social media, portfolio, etc.)
    telegram_username: str = ""
    phone_main: str = ""
    phone_whatsapp: Optional[str] = None
    name: str = ""
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    topic_id: Optional[int] = None
    status: str = "active"  # 'active', 'deleted', 'expired'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.cities is None:
            self.cities = []
    
    @classmethod
    def from_dict(cls, data: dict) -> 'JobPosting':
        """Create JobPosting from dictionary."""
        # Handle cities JSON string
        cities = data.get('cities', [])
        if isinstance(cities, str):
            try:
                cities = json.loads(cities)
            except json.JSONDecodeError:
                cities = []
        
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id'),
            mode=data.get('mode', ''),
            cities=cities,
            description=data.get('description', ''),
            social_media=data.get('social_media'),
            telegram_username=data.get('telegram_username', ''),
            phone_main=data.get('phone_main', ''),
            phone_whatsapp=data.get('phone_whatsapp'),
            name=data.get('name', ''),
            message_id=data.get('message_id'),
            chat_id=data.get('chat_id'),
            topic_id=data.get('topic_id'),
            status=data.get('status', 'active'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'mode': self.mode,
            'cities': json.dumps(self.cities),
            'description': self.description,
            'social_media': self.social_media,
            'telegram_username': self.telegram_username,
            'phone_main': self.phone_main,
            'phone_whatsapp': self.phone_whatsapp,
            'name': self.name,
            'message_id': self.message_id,
            'chat_id': self.chat_id,
            'topic_id': self.topic_id,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def is_valid(self) -> bool:
        """Check if posting is valid."""
        return (
            self.mode in ['seeking', 'offering'] and
            self.cities and
            len(self.description) >= 10 and
            self.telegram_username and
            self.phone_main and
            self.name and
            self.status in ['active', 'deleted', 'expired']
        )
