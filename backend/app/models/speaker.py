from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.child import new_id, utc_now


class SpeakerProfile(Base):
    __tablename__ = 'speaker_profiles'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_color: Mapped[str] = mapped_column(String(30), default='blue')
    default_voice_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class VoiceVersion(Base):
    __tablename__ = 'voice_versions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    speaker_profile_id: Mapped[str] = mapped_column(ForeignKey('speaker_profiles.id', ondelete='CASCADE'))
    display_name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(40), default='mimo')
    model: Mapped[str] = mapped_column(String(100), default='mimo-v2.5-tts-voiceclone')
    reference_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    style_instruction: Mapped[str] = mapped_column(
        Text, default='标准美式英语，清晰、自然，适合儿童默写，速度稍慢'
    )
    status: Mapped[str] = mapped_column(String(20), default='processing')
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
