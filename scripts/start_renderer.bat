@echo off
setlocal
title Mukana Renderer
cd /d "C:\Users\mmash\Desktop\Projects\Automated Job Application Assistant"
set /p RENDER_SECRET=<%USERPROFILE%\.mukana\render.secret
set "PYTHONUNBUFFERED=1"
set "PYTHONUTF8=1"
"C:\Users\mmash\.conda\envs\prefect_env\python.exe" -m uvicorn renderer.app:app --host 127.0.0.1 --port 8091
pause
