from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.child import new_id, utc_now


class UnknownItem(Base):
    __tablename__ = 'unknown_items'
    __table_args__ = (
        Index(
            'uq_unknown_items_active', 'child_id', 'source_language', 'target_language', 'normalized_text',
            unique=True, sqlite_where=text("status = 'unknown'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey('children.id', ondelete='CASCADE'))
    dictionary_entry_id: Mapped[str | None] = mapped_column(ForeignKey('dictionary_entries.id'), nullable=True)
    item_type: Mapped[str] = mapped_column(String(20))
    source_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(10))
    target_language: Mapped[str] = mapped_column(String(10))
    translation_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='unknown')
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
