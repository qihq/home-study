from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.child import new_id


class LearningItemAudio(Base):
    __tablename__ = 'learning_item_audio'
    __table_args__ = (UniqueConstraint('learning_item_id', 'config_fingerprint', name='uq_learning_item_audio_fingerprint'),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    learning_item_id: Mapped[str] = mapped_column(ForeignKey('word_items.id', ondelete='CASCADE'))
    speaker_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    voice_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tts_asset_id: Mapped[str] = mapped_column(ForeignKey('tts_assets.id'))
    config_fingerprint: Mapped[str] = mapped_column(String(64))
