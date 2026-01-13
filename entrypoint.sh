#!/bin/bash
set -e

# 1. AUTO-CREAZIONE .ENV
# Se .env non esiste, lo crea copiando .env_example
if [ ! -f "/app/.env" ] && [ -f "/app/.env_example" ]; then
    echo "--> .env non trovato. Creazione automatica da .env_example..."
    cp /app/.env_example /app/.env
fi

# 2. GESTIONE DATABASE (Con la logica del symlink che ti ho dato prima)
DATA_DIR="/app/db_data"
DB_FILE="$DATA_DIR/db.sqlite3"
LINK_FILE="/app/db.sqlite3"

mkdir -p "$DATA_DIR"

if [ ! -f "$DB_FILE" ]; then
    if [ -f "db_example.sqlite3" ]; then
        echo "--> Inizializzazione DB da esempio..."
        cp db_example.sqlite3 "$DB_FILE"
    else
        echo "--> Creazione DB vuoto..."
        touch "$DB_FILE"
    fi
fi

# Crea il collegamento simbolico
if [ -L "$LINK_FILE" ] || [ -f "$LINK_FILE" ]; then
    rm "$LINK_FILE"
fi
ln -s "$DB_FILE" "$LINK_FILE"

# 3. AVVIO
echo "--> Migrazioni..."
python manage.py migrate
echo "--> Static files..."
python manage.py collectstatic --noinput
echo "--> Start Server..."
exec gunicorn OpenMSP.wsgi:application --bind 0.0.0.0:8000 --workers 3