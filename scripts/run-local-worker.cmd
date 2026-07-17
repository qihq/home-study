@echo off
set "APP_DATA_DIR=%~dp0..\local-data"
set "APP_DATABASE_URL=sqlite:///%~dp0..\local-data/app.db"
set "APP_ENVIRONMENT=development"
cd /d "%~dp0..\backend"
python -m app.workers.runner
