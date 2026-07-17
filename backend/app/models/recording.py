from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.child import new_id, utc_now


class Recording(Base):
    __tablename__ = 'recordings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey('children.id'))
    reading_date: Mapped[date] = mapped_column(Date)
    language_type: Mapped[str] = mapped_column(String(10))
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='created')
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    source_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_missing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    compressed_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RecordingChunk(Base):
    __tablename__ = 'recording_chunks'
    __table_args__ = (UniqueConstraint('recording_id', 'sequence'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recording_id: Mapped[str] = mapped_column(ForeignKey('recordings.id', ondelete='CASCADE'))
    sequence: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(100))
    path: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
