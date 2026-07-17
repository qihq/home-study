def test_application_metadata_registers_core_tables() -> None:
    from app.db.base import Base
    import app.models  # noqa: F401

    assert {'users', 'user_sessions', 'children', 'jobs', 'recordings', 'recording_chunks'} <= set(Base.metadata.tables)
