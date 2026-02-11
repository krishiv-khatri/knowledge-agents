from typing import Dict
from sqlalchemy import JSON, String
from db.models import Base
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column


class OpenAISetting(Base):

    # The table name in the database
    __tablename__ = "openai_settings"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    """
    The name of setting

    Since
    --------
    0.0.1
    """
    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    """
    The provider of the OpenAI setting

    Since
    --------
    0.0.1
    """
    model: Mapped[str] = mapped_column(String(256))
    """
    The model name

    Since
    --------
    0.0.1
    """
    api_key: Mapped[str] = mapped_column(String(256))
    """
    The openai API key
    
    Since
    --------
    0.0.1
    """
    chat_timeout_in_seconds: Mapped[int] = mapped_column(default=60)
    """
    Chatgpt Timeout in seconds

    Since
    --------
    0.0.1
    """
    extra_configs: Mapped[Dict] = mapped_column(JSON)
    """
    Extra configuration necessary for creating the GPT service
    
    Since 
    ---------
    0.0.1
    """
    default: Mapped[bool] = mapped_column(default=False)
    """
    Whether this setting is considered as default setting when something want to use GPT service.
    
    Since 
    ---------
    0.0.1
    """
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    """
    When is the setting is created        

    Since 
    ---------
    0.0.1
    """
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
    """
    When is the setting updated

    Since 
    ---------
    0.0.1
    """
