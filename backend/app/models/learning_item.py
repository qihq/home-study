from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.child import new_id, utc_now


class LearningList(Base):
    __tablename__ = 'word_lists'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey('children.id'))
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default='draft')
    current_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default='paste')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningListVersion(Base):
    __tablename__ = 'word_list_versions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    word_list_id: Mapped[str] = mapped_column(ForeignKey('word_lists.id', ondelete='CASCADE'))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LearningItem(Base):
    __tablename__ = 'word_items'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    word_list_version_id: Mapped[str] = mapped_column(ForeignKey('word_list_versions.id', ondelete='CASCADE'))
    position: Mapped[int] = mapped_column(Integer)
    item_type: Mapped[str] = mapped_column(String(20), default='word')
    display_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(10), default='en')
    target_language: Mapped[str] = mapped_column(String(10), default='zh')
    translation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dictionary_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_asset_id: Mapped[str | None] = mapped_column(ForeignKey('tts_assets.id'), nullable=True)
    pronunciation_source: Mapped[str] = mapped_column(String(20), default='default')
