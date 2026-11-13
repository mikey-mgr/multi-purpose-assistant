@echo off
setlocal
title Mukana WhatsApp Webhook
cd /d "%~dp0.."
rem app/config.py loads .env itself via python-dotenv, which strips quotes correctly.
rem Do not `for /f` the .env file here: it would keep the surrounding quotes and break
rem WHATSAPP_ALLOWED_NUMBERS, causing every inbound message to be filtered.
set "SKIP_PREFECT_BLOCKS=1"
set "WEBHOOK_HOST=127.0.0.1"
set "WEBHOOK_PORT=8055"
set "PYTHONUNBUFFERED=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "WEB_INGEST_URL=https://mukana.mikeyverse.co.zw/api/whatsapp/ingest"
"C:\Users\mmash\.conda\envs\prefect_env\python.exe" -m app.webhook_server
pause
