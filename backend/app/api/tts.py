import struct
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import DbSession, require_resource_owner, require_user
from app.models.tts_asset import TtsAsset
from app.models.user import User
from app.services.mimo_speech import detect_language, resolve_voice
from app.services.mimo_tts import MimoTtsClient, MimoTtsError
from app.services.tts_config import api_key, get_tts_config

router = APIRouter(tags=['tts'])

SAMPLE_RATE = 24_000
# RIFF/WAVE header with placeholder sizes: browsers accept streaming WAV bodies
# whose size fields are 0xFFFFFFFF (unknown length).
WAV_STREAM_HEADER = (
    b'RIFF' + struct.pack('<I', 0xFFFFFFFF) + b'WAVE'
    + b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
    + b'data' + struct.pack('<I', 0xFFFFFFFF)
)


@router.get('/tts-assets/{asset_id}/audio')
def audio(asset_id: str, session: DbSession, user: Annotated[User, Depends(require_user)]):
    asset = session.get(TtsAsset, asset_id)
    if asset is None:
        raise HTTPException(404, detail={'code': 'TTS_ASSET_NOT_FOUND', 'message': '语音文件不存在'})
    require_resource_owner(session, asset.owner_user_id, user)
    path = Path(asset.path)
    if not path.is_file():
        raise HTTPException(404, detail={'code': 'TTS_AUDIO_MISSING', 'message': '语音文件缺失'})
    media_type = 'audio/mpeg' if path.suffix == '.mp3' else 'audio/ogg' if path.suffix == '.ogg' else 'audio/wav'
    return FileResponse(path, media_type=media_type)


@router.get('/tts/stream')
def stream(
    session: DbSession,
    user: Annotated[User, Depends(require_user)],
    text: str = Query(min_length=1, max_length=500),
) -> StreamingResponse:
    """Low-latency streaming synthesis for sentences/phrases (MiMo TTS)."""
    config = get_tts_config(session)
    if config is None or not config.api_key_encrypted:
        raise HTTPException(409, detail={'code': 'TTS_NOT_CONFIGURED', 'message': '英语发音服务未配置'})
    if config.protocol != 'mimo':
        raise HTTPException(409, detail={'code': 'TTS_STREAM_UNSUPPORTED', 'message': '当前协议不支持流式朗读'})
    language = detect_language(text)
    voice = resolve_voice(config.voice, config.voice_zh, language)
    client = MimoTtsClient(api_key(config), config.base_url, config.model, voice, config.speed)

    def generate():
        yield WAV_STREAM_HEADER
        try:
            for chunk in client.stream(text):
                yield chunk
        except MimoTtsError:
            return

    return StreamingResponse(generate(), media_type='audio/wav')
