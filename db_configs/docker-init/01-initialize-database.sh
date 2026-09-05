#!/bin/sh
set -eu

# The existing migration creates ai_assistant and switches to it with \c.
psql --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname postgres \
  --file /opt/app/migrations/init.sql

# Docker executes each init file in a fresh psql session, so explicitly target
# ai_assistant for the optional relationship/referral schema.
psql --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname ai_assistant \
  --file /opt/app/migrations/add_relationship_tables.sql
