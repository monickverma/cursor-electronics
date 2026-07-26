@echo off
REM ============================================================
REM Circuit OS — one-click local startup (Windows)
REM Opens 3 terminal windows: backend, celery worker, frontend.
REM Postgres + Redis run in Docker in the background.
REM ============================================================

cd /d "%~dp0"

echo [1/4] Starting Postgres + Redis (Docker)...
docker-compose up -d db redis
if errorlevel 1 (
    echo.
    echo ERROR: docker-compose failed. Is Docker Desktop running?
    pause
    exit /b 1
)

echo [2/4] Waiting for Postgres to become healthy...
timeout /t 6 /nobreak >nul

echo [3/4] Launching backend, celery worker, and PCB engine...
start "Circuit OS - Backend"    cmd /k "cd /d %~dp0backend & uvicorn main:app --reload --port 8000"
REM --pool=solo is required on Windows / Python 3.13
start "Circuit OS - Celery"     cmd /k "cd /d %~dp0backend & celery -A worker.app worker --loglevel=info --pool=solo"
start "Circuit OS - PCB Engine" cmd /k "cd /d %~dp0pcb & python compile_board.py --serve 8001"

echo [4/4] Launching frontend...
start "Circuit OS - Frontend"   cmd /k "cd /d %~dp0frontend & npm run dev"

echo.
echo ============================================================
echo   Circuit OS starting up.
echo.
echo   Frontend:    http://localhost:3000
echo   Backend:     http://localhost:8000/docs
echo   PCB Engine:  http://localhost:8001
echo   Login:       test@circuitos.dev / TestPass123!
echo.
echo   Give it ~15s, then open http://localhost:3000
echo   Close the 4 spawned windows to stop. Then: docker-compose down
echo ============================================================
echo.
pause
