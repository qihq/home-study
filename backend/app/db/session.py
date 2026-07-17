from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from app.core.config import get_settings


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.close()


@lru_cache
def get_engine() -> Engine:
    engine = create_engine(get_settings().database_url, connect_args={'check_same_thread': False})
    if get_settings().database_url.startswith('sqlite'):
        event.listen(engine, 'connect', _enable_sqlite_foreign_keys)
    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session
