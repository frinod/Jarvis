@echo off
title JARVIS OS — Full Stack Launch
color 0B

echo.
echo  ============================================================
echo   J.A.R.V.I.S  OS  —  FULL STACK LAUNCH
echo  ============================================================
echo.

set KIRO_CLI=C:\Users\edxxfri\AppData\Local\Kiro-Cli\kiro-cli.exe
set PROJECT_ROOT=%~dp0
set BACKEND=%PROJECT_ROOT%backend
set FRONTEND=%PROJECT_ROOT%frontend

echo  [1/3] Starting Kiro CLI serve on port 8082...
start "Kiro Serve" cmd /k "%KIRO_CLI% serve --port 8082"
timeout /t 2 /nobreak >nul

echo  [2/3] Starting FastAPI backend on port 8000...
start "JARVIS Backend" cmd /k "cd /d %BACKEND% && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul

echo  [3/3] Starting Next.js frontend on port 3000...
start "JARVIS Frontend" cmd /k "cd /d %FRONTEND% && npm run dev"

echo.
echo  ============================================================
echo   All services launching in separate windows:
echo.
echo   Kiro serve  →  ws://localhost:8082
echo   Backend     →  http://localhost:8000
echo   Frontend    →  http://localhost:3000
echo   API docs    →  http://localhost:8000/docs
echo   Kiro status →  http://localhost:8000/api/kiro/status
echo  ============================================================
echo.
echo  Press any key to exit this launcher (services keep running)
pause >nul
