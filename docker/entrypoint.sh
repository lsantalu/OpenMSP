#!/bin/bash
set -e

# 1. GESTIONE .ENV PERSISTENTE
# Il file .env deve risiedere nel volume persistente (mapped to /app/db_data)
ENV_PERSISTENT="/app/db_data/.env"
ENV_LINK="/app/.env"

# Assicuriamoci che la directory dati esista (creata anche dopo per il DB, ma serve ora)
mkdir -p "/app/db_data"

if [ ! -f "$ENV_PERSISTENT" ]; then
    echo "--> .env persistente non trovato in $ENV_PERSISTENT"
    # Se esiste un .env pre-esistente (es. copiato nell'immagine), usalo come base
    if [ -f "/app/.env" ] && [ ! -L "/app/.env" ]; then
         echo "--> Trovato .env nell'immagine, lo sposto nel volume..."
         mv /app/.env "$ENV_PERSISTENT"
    elif [ -f "/app/.env_example" ]; then
         echo "--> Creazione da .env_example..."
         cp /app/.env_example "$ENV_PERSISTENT"
    else
         echo "--> ATTENZIONE: Nessun .env o .env_example trovato!"
         touch "$ENV_PERSISTENT"
    fi
else
    echo "--> .env persistente trovato."
fi

# Crea il link simbolico
if [ -L "$ENV_LINK" ] || [ -f "$ENV_LINK" ]; then
    rm -rf "$ENV_LINK"
fi
ln -s "$ENV_PERSISTENT" "$ENV_LINK"

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