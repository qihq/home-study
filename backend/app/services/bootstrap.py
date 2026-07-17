from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.child import Child


def bootstrap_default_child(session: Session, display_name: str, timezone: str) -> Child:
    existing = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if existing is not None:
        return existing
    child = Child(display_name=display_name, slug='default-child', timezone=timezone)
    session.add(child)
    session.commit()
    session.refresh(child)
    return child
