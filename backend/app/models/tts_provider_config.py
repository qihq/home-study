from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TtsProviderConfig(Base):
    __tablename__ = 'tts_provider_config'

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    protocol: Mapped[str] = mapped_column(String(32), default='mimo')
    base_url: Mapped[str] = mapped_column(Text)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(200))
    voice: Mapped[str] = mapped_column(String(200))
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    pronunciation_source: Mapped[str] = mapped_column(String(20), default='configured')
    voice_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
