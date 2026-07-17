from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiProviderConfig(Base):
    __tablename__ = 'ai_provider_config'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    protocol: Mapped[str] = mapped_column(String(32), default='openai_chat_compatible')
    display_name: Mapped[str] = mapped_column(String(100), default='OpenCode Go')
    base_url: Mapped[str] = mapped_column(Text)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(200))
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=45)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SpellingOcrConfig(Base):
    __tablename__ = 'spelling_ocr_config'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    source: Mapped[str] = mapped_column(String(16), default='dictionary')
    protocol: Mapped[str] = mapped_column(String(32), default='openai_chat_compatible')
    display_name: Mapped[str] = mapped_column(String(100), default='Spelling OCR AI')
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=45)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
