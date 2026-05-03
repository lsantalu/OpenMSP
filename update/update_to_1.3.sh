#!/usr/bin/env bash
# update/update_to_1.3.sh
set -euo pipefail

# Upgrade schema OpenMSP DB from 1.2 to 1.3 (PDND Parameters alignment and AppIO cleanup).
# Usage:
#   ./update/update_to_1.3.sh [path/to/db.sqlite3]

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

default_db_target="$(suggest_first_existing_path "db.sqlite3")"

if [[ -z "$DB_PATH" ]]; then
  prompt_with_default DB_PATH "Percorso file db.sqlite3 da aggiornare" "$default_db_target"
fi
default_env_target="$(suggest_first_existing_path ".env")"
if [[ -z "$ENV_TARGET_PATH" ]]; then
  prompt_with_default ENV_TARGET_PATH "Percorso file .env da aggiornare" "$default_env_target"
fi

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

# Verifica versione database e concatenamento
if [[ "$(table_exists dati_ente)" == "1" ]]; then
  DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
  echo "INFO: Versione database rilevata: '$DB_VERSION'"
  if [[ "$DB_VERSION" == "1.3.0" ]]; then
    echo "Il database è già alla versione 1.3.0. Nessun aggiornamento necessario."
    exit 0
  elif [[ "$DB_VERSION" == "1.1.0" ]]; then
    echo "Rilevata versione 1.1.0. Avvio aggiornamento incrementale a 1.2..."
    if [[ -f "$SCRIPT_DIR/update_to_1.2.sh" ]]; then
      bash "$SCRIPT_DIR/update_to_1.2.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      # Ricarica versione dopo l'aggiornamento precedente
      DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
      echo "INFO: Versione database dopo step 1.2: '$DB_VERSION'"
    else
      echo "Errore: script di aggiornamento a 1.2 non trovato ($SCRIPT_DIR/update_to_1.2.sh)."
      exit 1
    fi
  fi

  if [[ "$DB_VERSION" != "1.2.0" ]]; then
    echo "Errore: la versione del database ($DB_VERSION) non è compatibile con questo script di aggiornamento (richiesta 1.2.0)."
    exit 1
  fi
else
  echo "Attenzione: tabella 'dati_ente' non trovata. Impossibile verificare la versione."
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${DB_PATH}.bak.${RUN_TS}"
cp -a "$DB_PATH" "$BACKUP_PATH"
echo "Backup DB creato: $BACKUP_PATH"

echo "Allineamento parametri PDND e aggiornamento servizi..."

sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 1. Aggiornamento specifici URL e Versioni
-- INPS ISEE v2
UPDATE inps_isee_parametri SET 
    ver_eservice='2', 
    target='https://api.inps.it/pdnd/soap/ConsultazioneISEE/v2/ConsultazioneAttestazioneResidenti' 
WHERE id=1;

-- INPS DURC
UPDATE inps_durc_parametri SET 
    target='https://api.inps.it/pdnd/rest/ConsultazioneDURC/v1' 
WHERE id=1;

-- MIT Parametri (allineamento target senza duplicazione endpoint base se presente audience)
UPDATE mit_parametri SET target='https://gw.servizidt.it/rest/in/MCTC/DettaglioCude/v1/cude/' WHERE id=1;
UPDATE mit_parametri SET target='https://gw.servizidt.it/rest/in/MCTC/ListaVeicoliCude/v1/cude/listaVeicoli' WHERE id=2;
UPDATE mit_parametri SET target='https://gw.servizidt.it/rest/in/MCTC/WhiteListCompletaCude/v1/cude/whitelist/completa/recupera' WHERE id=3;
UPDATE mit_parametri SET target='https://gw.servizidt.it/rest/in/MCTC/VerificaTargaCude/v1/cude/verificaTarga' WHERE id=4;


-- 2. Aggiornamento versione
UPDATE dati_ente SET versione = '1.3.0';

COMMIT;
PRAGMA foreign_keys = ON;
SQL

echo "Aggiornamento dati completato."

if [[ -f "$PROJECT_ROOT/manage.py" ]]; then
  echo "Esecuzione migrazioni Django..."
  python3 "$PROJECT_ROOT/manage.py" makemigrations
  python3 "$PROJECT_ROOT/manage.py" migrate
fi

echo "Upgrade struttura e dati DB alla versione 1.3 completato."
