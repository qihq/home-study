@echo off
set "APP_DATA_DIR=%~dp0..\local-data"
set "APP_DATABASE_URL=sqlite:///%~dp0..\local-data/app.db"
set "APP_ENVIRONMENT=development"
set "APP_FRONTEND_DIR=%~dp0..\frontend\dist"
cd /d "%~dp0..\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
