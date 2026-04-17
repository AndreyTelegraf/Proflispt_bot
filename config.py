"""Configuration module for Work in Portugal Bot."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for the bot."""
    
    # Bot token
    BOT_TOKEN: str = os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or ""
    
    # Channel and topic IDs
    CHANNEL_ID: int = int(os.getenv("CHANNEL_ID", "-1001788799608"))
    JOB_SEEKING_TOPIC_ID: int = int(os.getenv("JOB_SEEKING_TOPIC_ID", "9039"))
    JOB_OFFERING_TOPIC_ID: int = int(os.getenv("JOB_OFFERING_TOPIC_ID", "9040"))
    
    # Features
    ENABLE_EDITING: bool = True
    ENABLE_DELETION: bool = True
    AUTO_EXPIRE_DAYS: int = 30
    MAX_POSTINGS_PER_USER: int = 3
    POSTING_COOLDOWN_DAYS: int = 30

    # Admins
    ADMIN_IDS = [
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "336224597").split(",")
        if x.strip()
    ]
    
    # Cities and locations
    CITIES = {
        # Основные города
        "lisboa": "Lisboa",
        "porto": "Porto", 
        "coimbra": "Coimbra",
        "braga": "Braga",
        "faro": "Faro",
        "leiria": "Leiria",
        "sintra": "Sintra",
        "cascais": "Cascais",
        "madeira": "Madeira",
        "azores": "Açores",
        
        # Регионы
        "algarve": "Algarve",
        "alentejo": "Alentejo",
        "centro": "Centro",
        "norte": "Norte",
        "lisboa_region": "Região de Lisboa",
        
        # Другие крупные города
        "amadora": "Amadora",
        "almada": "Almada",
        "barreiro": "Barreiro",
        "beja": "Beja",
        "castelo_branco": "Castelo Branco",
        "evora": "Évora",
        "funchal": "Funchal",
        "guarda": "Guarda",
        "loule": "Loulé",
        "maia": "Maia",
        "matosinhos": "Matosinhos",
        "odivelas": "Odivelas",
        "ponta_delgada": "Ponta Delgada",
        "portalegre": "Portalegre",
        "santarem": "Santarém",
        "setubal": "Setúbal",
        "tavira": "Tavira",
        "vila_franca_de_xira": "Vila Franca de Xira",
        "vila_nova_de_famalicao": "Vila Nova de Famalicão",
        "vila_nova_de_gaia": "Vila Nova de Gaia",
        "viseu": "Viseu",
        
        # Популярные туристические города
        "albufeira": "Albufeira",
        "aveiro": "Aveiro",
        "batalha": "Batalha",
        "bom_jesus": "Bom Jesus",
        "caldas_da_rainha": "Caldas da Rainha",
        "caminha": "Caminha",
        "castro_marim": "Castro Marim",
        "chaves": "Chaves",
        "covilha": "Covilhã",
        "elvas": "Elvas",
        "espinho": "Espinho",
        "estremoz": "Estremoz",
        "figueira_da_foz": "Figueira da Foz",
        "guimaraes": "Guimarães",
        "lagos": "Lagos",
        "lamego": "Lamego",
        "marinha_grande": "Marinha Grande",
        "mirandela": "Mirandela",
        "monchique": "Monchique",
        "montijo": "Montijo",
        "nazare": "Nazaré",
        "obidos": "Óbidos",
        "olhao": "Olhão",
        "palmela": "Palmela",
        "peniche": "Peniche",
        "pombal": "Pombal",
        "portimao": "Portimão",
        "quarteira": "Quarteira",
        "rio_maior": "Rio Maior",
        "sagres": "Sagres",
        "sao_joao_da_madeira": "São João da Madeira",
        "silves": "Silves",
        "tomar": "Tomar",
        "torres_vedras": "Torres Vedras",
        "torresvedras": "Torres Vedras",
        "valenca": "Valença",
        "viana_do_castelo": "Viana do Castelo",
        "vila_real": "Vila Real",
        "vila_real_de_santo_antonio": "Vila Real de Santo António",
        
        # Специальные теги
        "online": "Online",
        "europe": "Europe",
        "remote": "Remote",
        "worldwide": "Worldwide"
    }
    
    # Validation patterns
    PHONE_PATTERN = r'^\+351(91|92|93|96)\d{7}$'
    USERNAME_PATTERN = r'^@[a-zA-Z0-9_]{5,32}$'
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        if not cls.CHANNEL_ID:
            raise ValueError("CHANNEL_ID is required")
        return True
