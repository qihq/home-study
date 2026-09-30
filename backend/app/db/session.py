from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from app.core.config import get_settings

# Explicit pool sizing: the defaults (5 + 10 overflow, 30s wait) let a burst of parallel
# chunk uploads turn into 30-second stalls and HTTP 500s instead of a quick failure.
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_TIMEOUT_SECONDS = 10.0
DB_POOL_RECYCLE_SECONDS = 1800
SQLITE_BUSY_TIMEOUT_MS = 15_000


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.execute('PRAGMA journal_mode=WAL')
    # Wait for a concurrent writer instead of failing the request immediately with
    # "database is locked".
    cursor.execute(f'PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}')
    cursor.close()


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().database_url
    if not database_url.startswith('sqlite'):
        return create_engine(database_url)
    engine = create_engine(
        database_url,
        connect_args={'check_same_thread': False},
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_timeout=DB_POOL_TIMEOUT_SECONDS,
        pool_recycle=DB_POOL_RECYCLE_SECONDS,
    )
    event.listen(engine, 'connect', _configure_sqlite_connection)
    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session
