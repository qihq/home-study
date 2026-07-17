from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import DbSession, require_resource_owner, require_user
from app.models.tts_asset import TtsAsset
from app.models.user import User

router = APIRouter(tags=['tts'])


@router.get('/tts-assets/{asset_id}/audio')
def audio(asset_id: str, session: DbSession, user: Annotated[User, Depends(require_user)]):
    asset = session.get(TtsAsset, asset_id)
    if asset is None:
        raise HTTPException(404, detail={'code': 'TTS_ASSET_NOT_FOUND', 'message': '语音文件不存在'})
    require_resource_owner(session, asset.owner_user_id, user)
    path = Path(asset.path)
    if not path.is_file():
        raise HTTPException(404, detail={'code': 'TTS_AUDIO_MISSING', 'message': '语音文件缺失'})
    return FileResponse(path, media_type='audio/wav')
