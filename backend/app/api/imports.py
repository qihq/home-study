import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import require_user
from app.core.config import get_settings
from app.models.user import User
from app.services.imports import ParserUnavailable, parse_import_file

router = APIRouter(tags=['imports'])
MAX_IMPORT_BYTES = 20 * 1024 * 1024
ALLOWED_SUFFIXES = {'.txt', '.csv', '.xlsx', '.docx', '.pdf'}


@router.post('/imports', status_code=status.HTTP_201_CREATED)
async def upload_import(
    file: Annotated[UploadFile, File()],
    _user: Annotated[User, Depends(require_user)],
) -> dict:
    suffix = Path(file.filename or '').suffix.casefold()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(422, detail={'code': 'UNSUPPORTED_IMPORT_TYPE', 'message': '仅支持 TXT、XLSX、DOCX 和 PDF'})
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(413, detail={'code': 'IMPORT_TOO_LARGE', 'message': '导入文件不能超过 20 MB'})
    import_id = str(uuid.uuid4())
    target_dir = get_settings().uploads_dir / 'imports' / import_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f'source{suffix}'
    target.write_bytes(content)
    try:
        parsed = parse_import_file(target, file.content_type)
    except ParserUnavailable:
        return {'id': import_id, 'status': 'parser_unavailable', 'items': [], 'warnings': ['当前服务缺少该文件类型的解析组件。']}
    except ValueError:
        raise HTTPException(422, detail={'code': 'UNSUPPORTED_IMPORT_TYPE', 'message': '无法识别该文件类型'})
    return {'id': import_id, 'status': 'parsed', 'items': parsed.items, 'warnings': parsed.warnings}
