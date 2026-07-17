from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.recordings import router as recordings_router
from app.api.stats import router as stats_router
from app.api.word_lists import router as word_lists_router
from app.api.learning_lists import router as learning_lists_router
from app.api.dictionary import router as dictionary_router
from app.api.unknown_items import router as unknown_items_router
from app.api.speakers import router as speakers_router
from app.api.voice_packages import router as voice_packages_router
from app.api.dictation import router as dictation_router
from app.api.imports import router as imports_router
from app.api.settings import router as settings_router
from app.api.tts import router as tts_router
from app.db.base import Base
from app.db.session import get_engine
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title='Family Learning API', version='0.1.0')
    Base.metadata.create_all(get_engine())
    app.include_router(health_router, prefix='/api')
    app.include_router(auth_router, prefix='/api')
    app.include_router(recordings_router, prefix='/api')
    app.include_router(stats_router, prefix='/api')
    app.include_router(word_lists_router, prefix='/api')
    app.include_router(learning_lists_router, prefix='/api')
    app.include_router(dictionary_router, prefix='/api')
    app.include_router(unknown_items_router, prefix='/api')
    app.include_router(speakers_router, prefix='/api')
    app.include_router(voice_packages_router, prefix='/api')
    app.include_router(dictation_router, prefix='/api')
    app.include_router(imports_router, prefix='/api')
    app.include_router(settings_router, prefix='/api')
    app.include_router(tts_router, prefix='/api')
    frontend = get_settings().frontend_dir
    if frontend.is_dir() and (frontend / 'index.html').is_file():
        assets = frontend / 'assets'
        if assets.is_dir():
            app.mount('/assets', StaticFiles(directory=assets), name='assets')

        animal_island = frontend / 'animal-island'
        if animal_island.is_dir():
            app.mount('/animal-island', StaticFiles(directory=animal_island), name='animal-island')

        @app.get('/service-worker.js', include_in_schema=False)
        def service_worker() -> FileResponse:
            return FileResponse(frontend / 'service-worker.js', media_type='application/javascript')

        @app.get('/{path:path}', include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.split('/', 1)[0] in {'uploads', 'voice-samples'}:
                raise HTTPException(status_code=404, detail='Not Found')
            return FileResponse(frontend / 'index.html')
    return app


app = create_app()
