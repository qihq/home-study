from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.child import new_id, utc_now


class DictionaryEntry(Base):
    __tablename__ = 'dictionary_entries'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    query_hash: Mapped[str] = mapped_column(String(64), unique=True)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)


class DictionaryHistory(Base):
    __tablename__ = 'dictionary_history'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey('children.id', ondelete='CASCADE'))
    entry_id: Mapped[str] = mapped_column(ForeignKey('dictionary_entries.id', ondelete='CASCADE'))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    entry: Mapped[DictionaryEntry] = relationship()
