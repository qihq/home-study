import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.child import new_id, utc_now


class DictationSession(Base):
    __tablename__ = 'dictation_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey('children.id'))
    word_list_version_id: Mapped[str] = mapped_column(ForeignKey('word_list_versions.id'))
    mode: Mapped[str] = mapped_column(String(20))
    ordered_item_ids_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='in_progress')
    speaker_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    voice_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    speaker_profile_name_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voice_version_name_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def ordered_item_ids(self) -> list[str]:
        return json.loads(self.ordered_item_ids_json)


class DictationResult(Base):
    __tablename__ = 'dictation_results'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey('dictation_sessions.id', ondelete='CASCADE'))
    word_item_id: Mapped[str] = mapped_column(ForeignKey('word_items.id'))
    sequence: Mapped[int] = mapped_column(Integer)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(20), default='unscored')
    answer_revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    item_type_snapshot: Mapped[str] = mapped_column(String(20), default='word')
