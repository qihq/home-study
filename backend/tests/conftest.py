import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('APP_DATABASE_URL', f"sqlite:///{tmp_path / 'app.db'}")
    os.environ.pop('APP_ENVIRONMENT', None)
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    from app.main import create_app

    return TestClient(create_app())


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    from app.db.base import Base
    import app.models  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()


@pytest.fixture()
def admin_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.db.session import get_session_factory
    from app.db.base import Base
    from app.models.user import User
    from app.services.users import hash_password

    engine = get_session_factory().kw['bind']
    Base.metadata.create_all(engine)
    with get_session_factory()() as database_session:
        database_session.add(User(username='parent', password_hash=hash_password('correct horse')))
        database_session.commit()
    return 'parent'


@pytest.fixture()
def video_fixture(tmp_path: Path) -> bytes:
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        pytest.skip('ffmpeg is required for video worker test')
    output = tmp_path / 'input.mp4'
    subprocess.run([
        ffmpeg, '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x240:d=1:r=24',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-c:v', 'libx264', '-c:a', 'aac', str(output),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output.read_bytes()


@pytest.fixture()
def fragmented_video_chunks(tmp_path: Path) -> list[bytes]:
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        pytest.skip('ffmpeg is required for video worker test')
    output = tmp_path / 'fragmented-input.mp4'
    subprocess.run([
        ffmpeg, '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x240:d=12:r=24',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=12', '-c:v', 'libx264',
        '-g', '96', '-keyint_min', '96', '-sc_threshold', '0', '-c:a', 'aac',
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof', str(output),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    data = output.read_bytes()
    boxes: list[tuple[bytes, bytes]] = []
    offset = 0
    while offset < len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        header_size = 8
        if size == 1:
            size = struct.unpack('>Q', data[offset + 8:offset + 16])[0]
            header_size = 16
        elif size == 0:
            size = len(data) - offset
        assert size >= header_size
        boxes.append((data[offset + 4:offset + 8], data[offset:offset + size]))
        offset += size

    initialization = b''.join(box for kind, box in boxes if kind in {b'ftyp', b'moov'})
    chunks: list[bytes] = []
    fragment = b''
    for kind, box in boxes:
        if kind in {b'ftyp', b'moov', b'mfra'}:
            continue
        if kind == b'moof' and fragment:
            chunks.append(fragment)
            fragment = b''
        fragment += box
    if fragment:
        chunks.append(fragment)
    chunks[0] = initialization + chunks[0]
    return chunks
