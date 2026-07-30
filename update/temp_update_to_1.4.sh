#!/usr/bin/env bash
# update/update_to_1.4.sh
set -euo pipefail

# Upgrade schema/data OpenMSP DB from 1.3 to 1.4.
# Fix duplicate MIT service codes introduced in some upgraded production DBs.
# Usage:
#   ./update/update_to_1.4.sh [path/to/db.sqlite3] [path/to/.env]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

suggest_first_existing_path() {
  local candidate
  for candidate in "$@"; do
    if [[ -f "./$candidate" ]]; then
      echo "./$candidate"
      return 0
    fi
  done
  for candidate in "$@"; do
    if [[ -f "$PROJECT_ROOT/$candidate" ]]; then
      echo "$PROJECT_ROOT/$candidate"
      return 0
    fi
  done
  echo "./$1"
}

prompt_with_default() {
  local var_name="$1"
  local label="$2"
  local default_value="$3"
  local input_value=""
  if [[ -t 0 ]]; then
    read -r -p "$label [$default_value]: " input_value
  fi
  if [[ -z "$input_value" ]]; then
    printf -v "$var_name" "%s" "$default_value"
  else
    printf -v "$var_name" "%s" "$input_value"
  fi
}

DB_PATH="${1:-}"
ENV_TARGET_PATH="${2:-}"

if [[ ! -f "$PROJECT_ROOT/db.sqlite3" ]] && [[ ! -f "./db.sqlite3" ]]; then
  echo "Attenzione: nessun file db.sqlite3 trovato nel progetto."
fi

if [[ ! -f "$PROJECT_ROOT/.env" ]] && [[ ! -f "./.env" ]]; then
  echo "Attenzione: nessun file .env trovato nel progetto."
fi

default_db_target="$(suggest_first_existing_path "db.sqlite3")"
if [[ -z "$DB_PATH" ]]; then
  prompt_with_default DB_PATH "Percorso file db.sqlite3 da aggiornare" "$default_db_target"
fi

default_env_target="$(suggest_first_existing_path ".env")"
if [[ -z "$ENV_TARGET_PATH" ]]; then
  prompt_with_default ENV_TARGET_PATH "Percorso file .env da aggiornare" "$default_env_target"
fi

SETTINGS_FILE="${PROJECT_ROOT}/OpenMSP/settings.py"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "INFO: sqlite3 non trovato nel PATH. Installazione in corso..."
  sudo apt update && sudo apt install -y sqlite3
  if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "Errore: installazione di sqlite3 fallita."
    exit 1
  fi
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Errore: database non trovato: $DB_PATH"
  exit 1
fi

table_exists_in_db() {
  local db_path="$1"
  local table_name="$2"
  sqlite3 "$db_path" "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='${table_name}');"
}

table_exists() {
  local table_name="$1"
  table_exists_in_db "$DB_PATH" "$table_name"
}

if [[ "$(table_exists dati_ente)" == "1" ]]; then
  DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
  echo "INFO: Versione database rilevata: '$DB_VERSION'"

  case "$DB_VERSION" in
    "1.4.0")
      echo "Il database è già alla versione 1.4.0. Nessun aggiornamento necessario."
      exit 0
      ;;
    "1.0.0")
      echo "Rilevata versione 1.0.0. Avvio aggiornamento incrementale fino alla 1.3..."
      bash "$SCRIPT_DIR/update_to_1.1.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      bash "$SCRIPT_DIR/update_to_1.2.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      bash "$SCRIPT_DIR/update_to_1.3.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      ;;
    "1.1.0")
      echo "Rilevata versione 1.1.0. Avvio aggiornamento incrementale fino alla 1.3..."
      bash "$SCRIPT_DIR/update_to_1.2.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      bash "$SCRIPT_DIR/update_to_1.3.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      ;;
    "1.2.0")
      echo "Rilevata versione 1.2.0. Avvio aggiornamento incrementale a 1.3..."
      bash "$SCRIPT_DIR/update_to_1.3.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      ;;
    "1.3.0")
      ;;
    *)
      echo "Errore: la versione del database ($DB_VERSION) non è compatibile con questo script di aggiornamento."
      exit 1
      ;;
  esac

  DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
  if [[ "$DB_VERSION" != "1.3.0" ]]; then
    echo "Errore: la versione del database ($DB_VERSION) non è compatibile con questo script di aggiornamento (richiesta 1.3.0)."
    exit 1
  fi
else
  echo "Attenzione: tabella 'dati_ente' non trovata. Impossibile verificare la versione."
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${DB_PATH}.bak.${RUN_TS}"
cp -a "$DB_PATH" "$BACKUP_PATH"
echo "Backup DB creato: $BACKUP_PATH"

echo "Verifica e normalizzazione servizi MIT in servizi_parametri..."

duplicate_codes_before="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM (SELECT codice_servizio FROM servizi_parametri GROUP BY codice_servizio HAVING COUNT(*) > 1);")"
if [[ "$duplicate_codes_before" != "0" ]]; then
  echo "INFO: Trovati codici servizio duplicati prima della correzione:"
  sqlite3 -header -column "$DB_PATH" "SELECT codice_servizio, COUNT(*) AS occorrenze, GROUP_CONCAT(id) AS ids FROM servizi_parametri GROUP BY codice_servizio HAVING COUNT(*) > 1 ORDER BY codice_servizio;"
fi

sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Canonical MIT services after 1.3:
-- 12 -> mit_cude
-- 13 -> mit_veicoli
-- 14 -> mit_whitelist
-- 15 -> mit_targa
--
-- Some upgraded production databases contain ids 12,13,14 all renamed to
-- mit_whitelist because update_to_1.2.sh applied sequential UPDATE statements
-- using codice_servizio as selector. Here we restore the canonical mapping.
UPDATE servizi_parametri
SET codice_servizio = 'mit_cude',
    descrizione = 'Ministero Trasporti (MIT) - Dettaglio Cude',
    gruppo_id = 5,
    url = 'impostazioni_mit/#tab1'
WHERE id = 12;

UPDATE servizi_parametri
SET codice_servizio = 'mit_veicoli',
    descrizione = 'Ministero Trasporti (MIT) - Lista Veicoli',
    gruppo_id = 5,
    url = 'impostazioni_mit/#tab2'
WHERE id = 13;

UPDATE servizi_parametri
SET codice_servizio = 'mit_whitelist',
    descrizione = 'Ministero Trasporti (MIT) - Recupera Whitelist',
    gruppo_id = 5,
    url = 'impostazioni_mit/#tab3'
WHERE id = 14;

UPDATE servizi_parametri
SET codice_servizio = 'mit_targa',
    descrizione = 'Ministero Trasporti (MIT) - Targhe contrassegno',
    gruppo_id = 5,
    url = 'impostazioni_mit/#tab4'
WHERE id = 15;

UPDATE dati_ente SET versione = '1.4.0';

COMMIT;
PRAGMA foreign_keys = ON;
SQL

duplicate_codes_after="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM (SELECT codice_servizio FROM servizi_parametri GROUP BY codice_servizio HAVING COUNT(*) > 1);")"
if [[ "$duplicate_codes_after" != "0" ]]; then
  echo "Errore: sono ancora presenti codici duplicati in servizi_parametri dopo la normalizzazione."
  sqlite3 -header -column "$DB_PATH" "SELECT codice_servizio, COUNT(*) AS occorrenze, GROUP_CONCAT(id) AS ids FROM servizi_parametri GROUP BY codice_servizio HAVING COUNT(*) > 1 ORDER BY codice_servizio;"
  exit 1
fi

sqlite3 "$DB_PATH" "CREATE UNIQUE INDEX IF NOT EXISTS servizi_parametri_codice_servizio_uniq ON servizi_parametri(codice_servizio);"

echo "Servizi MIT normalizzati correttamente."

echo "Pulizia e reset dell'array app_io_catalogo_servizi..."
sqlite3 "$DB_PATH" <<'SQL'
DELETE FROM app_io_catalogo_servizi;
SQL

echo "Aggiornamento configurazione .env per versione 1.4..."

if [[ -f "$ENV_TARGET_PATH" ]]; then
    BACKUP_ENV_PATH="${ENV_TARGET_PATH}.bak.${RUN_TS}"
    cp -a "$ENV_TARGET_PATH" "$BACKUP_ENV_PATH"
    echo "Backup .env creato: $BACKUP_ENV_PATH"

    ENV_CONTENT=$(cat "$ENV_TARGET_PATH")

    if [[ ! "$ENV_CONTENT" =~ "ALLOWED_HOSTS.*=" ]]; then
        echo "Aggiornamento ALLOWED_HOSTS in .env..."
        sed -i 's/^\(ALLOWED_HOSTS\s*=\s*\).*$/ALLOWED_HOSTS = openmsp.example.local,localhost,127.0.0.1/' "$ENV_TARGET_PATH" 2>/dev/null || true
    fi

    if [[ ! "$ENV_CONTENT" =~ "CSRF_TRUSTED_ORIGINS.*=" ]]; then
        echo "Aggiunta CSRF_TRUSTED_ORIGINS in .env..."
        echo "CSRF_TRUSTED_ORIGINS = https://openmsp.example.local,http://localhost:8000" >> "$ENV_TARGET_PATH"
    fi

    if [[ ! "$ENV_CONTENT" =~ "SECURE_PROXY_SSL_HEADER.*=" ]]; then
        echo "Aggiunta SECURE_PROXY_SSL_HEADER in .env..."
        echo "SECURE_PROXY_SSL_HEADER = HTTP_X_FORWARDED_PROTO,https" >> "$ENV_TARGET_PATH"
    fi

    if [[ ! "$ENV_CONTENT" =~ "USE_X_FORWARDED_HOST.*=" ]]; then
        echo "Aggiunta USE_X_FORWARDED_HOST in .env..."
        echo "USE_X_FORWARDED_HOST = True" >> "$ENV_TARGET_PATH"
    fi

    echo "Aggiornamento bootstrap-italia-cdn in .env..."
    sed -i 's|bootstrap-italia@[0-9]*\.[0-9]*\.[0-9]*/dist|bootstrap-italia@2.18.2/dist|' "$ENV_TARGET_PATH" 2>/dev/null || true

    if [[ -f "$SETTINGS_FILE" ]]; then
        echo "Aggiornamento di settings.py per supportare reverse proxy..."

        if ! grep -q "from decouple import AutoConfig, Csv" "$SETTINGS_FILE"; then
            sed -i 's/^from decouple import AutoConfig$/from decouple import AutoConfig, Csv/' "$SETTINGS_FILE"
        fi

        sed -i 's/^ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=list)/ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())/' "$SETTINGS_FILE"

        if ! grep -q "^CSRF_TRUSTED_ORIGINS" "$SETTINGS_FILE"; then
            sed -i '/^ALLOWED_HOSTS =/a\CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())' "$SETTINGS_FILE"
        fi

        if ! grep -q "^SECURE_PROXY_SSL_HEADER" "$SETTINGS_FILE"; then
            sed -i '/^CSRF_TRUSTED_ORIGINS =/a\SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")' "$SETTINGS_FILE"
        fi

        if ! grep -q "^USE_X_FORWARDED_HOST" "$SETTINGS_FILE"; then
            sed -i '/^SECURE_PROXY_SSL_HEADER =/a\USE_X_FORWARDED_HOST = True' "$SETTINGS_FILE"
        fi
    fi
fi

if [[ -f "$PROJECT_ROOT/manage.py" ]]; then
    echo "Esecuzione migrazioni Django..."
    python3 "$PROJECT_ROOT/manage.py" collectstatic --noinput
    python3 "$PROJECT_ROOT/manage.py" migrate
fi

echo "Upgrade struttura e dati DB alla versione 1.4 completato."
