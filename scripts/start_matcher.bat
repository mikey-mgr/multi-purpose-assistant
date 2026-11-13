@echo off
setlocal
title Mukana Matcher
cd /d "%~dp0..\containers\matcher"
rem The matcher needs the trigger secret and a database URL. app/config.py loads
rem ..\.env for the rest; these two must be present before uvicorn starts.
for /f "usebackq tokens=1,* delims==" %%A in ("%USERPROFILE%\Desktop\Projects\Automated Job Application Assistant\.env") do (
  if /i "%%A"=="MATCH_TRIGGER_SECRET" set "MATCH_TRIGGER_SECRET=%%~B"
  if /i "%%A"=="GEMINI_API_KEY" set "GEMINI_API_KEY=%%~B"
)
for /f "usebackq tokens=1,* delims==" %%A in ("%USERPROFILE%\Desktop\Projects\Automated Job Application Assistant\web\.env") do (
  if /i "%%A"=="DATABASE_URL" set "DATABASE_URL=%%~B"
)
set "PYTHONUNBUFFERED=1"
"C:\Users\mmash\.conda\envs\prefect_env\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8090
pause
