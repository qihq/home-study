from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.child import new_id, utc_now


class TtsAsset(Base):
    __tablename__ = 'tts_assets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(40), default='mimo')
    model: Mapped[str] = mapped_column(String(100), default='configured')
    voice: Mapped[str] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(20))
    speed: Mapped[float] = mapped_column(Float)
    normalized_text: Mapped[str] = mapped_column(String(160))
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='ready')
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
