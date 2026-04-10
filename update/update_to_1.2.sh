#!/usr/bin/env bash
# update/update_to_1.2.sh
set -euo pipefail

# Upgrade schema OpenMSP DB from 1.1 to 1.2 (Implementation of ANPR C007).
# Usage:
#   ./update/update_1_1_to_1_2.sh [path/to/db.sqlite3]

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
  apt update && apt install -y sqlite3
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
  if [[ "$DB_VERSION" == "1.2.0" ]]; then
    echo "Il database è già alla versione 1.2.0. Nessun aggiornamento necessario."
    exit 0
  elif [[ "$DB_VERSION" == "1.0.0" ]]; then
    echo "Rilevata versione 1.0.0. Avvio aggiornamento incrementale a 1.1..."
    if [[ -f "$SCRIPT_DIR/update_to_1.1.sh" ]]; then
      bash "$SCRIPT_DIR/update_to_1.1.sh" "$DB_PATH" "$ENV_TARGET_PATH"
      # Ricarica versione dopo l'aggiornamento precedente
      DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
      echo "INFO: Versione database dopo step 1.1: '$DB_VERSION'"
    else
      echo "Errore: script di aggiornamento a 1.1 non trovato ($SCRIPT_DIR/update_to_1.1.sh)."
      exit 1
    fi
  fi

  if [[ "$DB_VERSION" != "1.1.0" ]]; then
    echo "Errore: la versione del database ($DB_VERSION) non è compatibile con questo script di aggiornamento (richiesta 1.1.0)."
    exit 1
  fi
else
  echo "Attenzione: tabella 'dati_ente' non trovata. Impossibile verificare la versione."
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${DB_PATH}.bak.${RUN_TS}"
cp -a "$DB_PATH" "$BACKUP_PATH"
echo "Backup DB creato: $BACKUP_PATH"

column_exists() {
  local table_name="$1"
  local column_name="$2"
  sqlite3 "$DB_PATH" "SELECT EXISTS(SELECT 1 FROM pragma_table_info('${table_name}') WHERE name='${column_name}');"
}

has_anpr_c007="$(column_exists utenti_parametri anpr_C007)"

if [[ "$has_anpr_c007" == "0" ]]; then
    echo "Migrazione utenti_parametri con riordinamento colonne (anpr_C007)..."
    sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE "utenti_parametri_ordered" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "utente_id" INTEGER NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "ipa_singolo" BOOLEAN DEFAULT 0,
    "ipa_massivo" BOOLEAN DEFAULT 0,
    "inad_singolo" BOOLEAN DEFAULT 0,
    "inad_massivo" BOOLEAN DEFAULT 0,
    "inipec_singolo" BOOLEAN DEFAULT 0,
    "inipec_massivo" BOOLEAN DEFAULT 0,
    "anpr_C001" BOOLEAN DEFAULT 0,
    "anpr_C007" BOOLEAN DEFAULT 0,
    "anpr_C015" BOOLEAN DEFAULT 0,
    "anpr_C017" BOOLEAN DEFAULT 0,
    "anpr_C018" BOOLEAN DEFAULT 0,
    "anpr_C020" BOOLEAN DEFAULT 0,
    "anpr_C021" BOOLEAN DEFAULT 0,
    "anpr_C030" BOOLEAN DEFAULT 0,
    "mit_cude" BOOLEAN DEFAULT 0,
    "mit_veicoli" BOOLEAN DEFAULT 0,
    "mit_whitelist" BOOLEAN DEFAULT 0,
    "mit_targa" BOOLEAN DEFAULT 0,
    "anis_IFS02_singolo" BOOLEAN DEFAULT 0,
    "anis_IFS02_massivo" BOOLEAN DEFAULT 0,
    "anis_IFS03_singolo" BOOLEAN DEFAULT 0,
    "anis_IFS03_massivo" BOOLEAN DEFAULT 0,
    "cassa_forense" BOOLEAN DEFAULT 0,
    "registro_imprese" BOOLEAN DEFAULT 0,
    "inps_isee" BOOLEAN DEFAULT 0,
    "inps_durc_singolo" BOOLEAN DEFAULT 0,
    "inps_durc_massivo" BOOLEAN DEFAULT 0,
    "app_io_verifica_singolo" BOOLEAN DEFAULT 0,
    "app_io_verifica_massivo" BOOLEAN DEFAULT 0,
    "app_io_singolo" BOOLEAN DEFAULT 0,
    "app_io_massivo" BOOLEAN DEFAULT 0,
    "anist_frequenze_singolo" BOOLEAN DEFAULT 0,
    "anist_frequenze_massivo" BOOLEAN DEFAULT 0,
    "anist_titoli_singolo" BOOLEAN DEFAULT 0,
    "anist_titoli_massivo" BOOLEAN DEFAULT 0,
    "app_io_composer" BOOLEAN DEFAULT 0,
    "app_io_storico_messaggi" BOOLEAN DEFAULT 0
);

INSERT INTO "utenti_parametri_ordered" (
    id, utente_id, ipa_singolo, ipa_massivo, inad_singolo, inad_massivo, inipec_singolo, inipec_massivo,
    anpr_C001, anpr_C015, anpr_C017, anpr_C018, anpr_C020, anpr_C021, anpr_C030,
    mit_cude, mit_veicoli, mit_whitelist, mit_targa, anis_IFS02_singolo, anis_IFS02_massivo,
    anis_IFS03_singolo, anis_IFS03_massivo, cassa_forense, registro_imprese, inps_isee,
    inps_durc_singolo, inps_durc_massivo, app_io_verifica_singolo, app_io_verifica_massivo,
    app_io_singolo, app_io_massivo, anist_frequenze_singolo, anist_frequenze_massivo,
    anist_titoli_singolo, anist_titoli_massivo, app_io_composer, app_io_storico_messaggi
)
SELECT
    id, utente_id, ipa_singolo, ipa_massivo, inad_singolo, inad_massivo, inipec_singolo, inipec_massivo,
    anpr_C001, anpr_C015, anpr_C017, anpr_C018, anpr_C020, anpr_C021, anpr_C030,
    mit_cude, mit_veicoli, mit_whitelist, mit_targa, anis_IFS02_singolo, anis_IFS02_massivo,
    anis_IFS03_singolo, anis_IFS03_massivo, cassa_forense, registro_imprese, inps_isee,
    inps_durc_singolo, inps_durc_massivo, app_io_verifica_singolo, app_io_verifica_massivo,
    app_io_singolo, app_io_massivo, anist_frequenze_singolo, anist_frequenze_massivo,
    anist_titoli_singolo, anist_titoli_massivo, app_io_composer, app_io_storico_messaggi
FROM "utenti_parametri";

DROP TABLE "utenti_parametri";
ALTER TABLE "utenti_parametri_ordered" RENAME TO "utenti_parametri";
CREATE INDEX "utenti_parametri_utente_id_47820755" ON "utenti_parametri" ("utente_id");

COMMIT;
PRAGMA foreign_keys = ON;
SQL
else
    echo "Colonna anpr_C007 già presente o tabella già allineata."
fi

# Check if C007 is already in servizi_parametri to avoid duplicates
has_servizio_c007="$(sqlite3 "$DB_PATH" "SELECT EXISTS(SELECT 1 FROM servizi_parametri WHERE codice_servizio='anpr_c007');")"

if [[ "$has_servizio_c007" == "0" ]]; then
    echo "Inserimento anpr_c007 in servizi_parametri con riordino numerico..."
    sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Shifting IDs for servizi_parametri
UPDATE servizi_parametri SET id = id + 1000 WHERE id >= 4;
UPDATE servizi_parametri SET id = id - 999 WHERE id >= 1004;
INSERT INTO servizi_parametri (id, codice_servizio, descrizione, gruppo_id, attivo, url) 
VALUES (4, 'anpr_c007', 'Anagrafe Nazionale Popolazione Residente - Esistenza in vita (C007)', 2, 1, 'impostazioni_anpr/#tab2');

-- Shift tab numbering for ANPR services to accommodate C007 at #tab2
UPDATE servizi_parametri SET url='impostazioni_anpr/#tab3' WHERE codice_servizio='anpr_c015';
UPDATE servizi_parametri SET url='impostazioni_anpr/#tab4' WHERE codice_servizio='anpr_c017';
UPDATE servizi_parametri SET url='impostazioni_anpr/#tab5' WHERE codice_servizio='anpr_c018';
UPDATE servizi_parametri SET url='impostazioni_anpr/#tab6' WHERE codice_servizio='anpr_c020';
UPDATE servizi_parametri SET url='impostazioni_anpr/#tab7' WHERE codice_servizio='anpr_c021';
UPDATE servizi_parametri SET url='impostazioni_anpr/#tab8' WHERE codice_servizio='anpr_c030';

-- Fix MIT services: codice, descrizione e url aggiornati alla produzione
UPDATE servizi_parametri SET codice_servizio='mit_cude',      descrizione='Ministero Trasporti (MIT) - Dettaglio Cude',     url='impostazioni_mit/#tab1' WHERE codice_servizio='mit_patenti';
UPDATE servizi_parametri SET codice_servizio='mit_veicoli',   descrizione='Ministero Trasporti (MIT) - Lista Veicoli',      url='impostazioni_mit/#tab2' WHERE codice_servizio='mit_cude';
UPDATE servizi_parametri SET codice_servizio='mit_whitelist', descrizione='Ministero Trasporti (MIT) - Recupera Whitelist', url='impostazioni_mit/#tab3' WHERE codice_servizio='mit_veicoli';

COMMIT;
PRAGMA foreign_keys = ON;
SQL
    echo "Aggiornamento servizi_parametri completato."
else
    echo "Servizio C007 già presente in servizi_parametri."
fi

# Check independently if C007 is in anpr_servizi (missing in db_example and older reference syncs)
has_anpr_servizio_c007="$(sqlite3 "$DB_PATH" "SELECT EXISTS(SELECT 1 FROM anpr_servizi WHERE servizio LIKE 'C007%');")"
if [[ "$has_anpr_servizio_c007" == "0" ]]; then
    echo "Aggiornamento tabelle anpr_servizi e anpr_parametri per C007 con riordino numerico..."
    sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Shifting IDs for anpr_servizi
UPDATE anpr_servizi SET id = id + 1000 WHERE id >= 2;
UPDATE anpr_servizi SET id = id - 999 WHERE id >= 1002;
INSERT INTO anpr_servizi (id, servizio) VALUES (2, 'C007 Esistenza in vita');

-- Shifting IDs for anpr_parametri and inserting copy for C007 (id=2, servizio_id=2)
UPDATE anpr_parametri SET id = id + 1000, servizio_id = servizio_id + 1000 WHERE id >= 2;
UPDATE anpr_parametri SET id = id - 999, servizio_id = servizio_id - 999 WHERE id >= 1002;

-- Insert parameters for C007 taking C001 as reference (id=1) but injecting the correct C007 audience, target and ver_eservice
INSERT INTO anpr_parametri (id, servizio_id, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice) 
SELECT 2, 2, kid, alg, typ, iss, sub, aud, purposeid, 'https://modipa.anpr.interno.it/govway/rest/in/MinInternoPortaANPR/C007-servizioVerificaDichEsistenzaVita/v1', baseurlauth, 'https://modipa.anpr.interno.it/govway/rest/in/MinInternoPortaANPR-PDND/C007-servizioVerificaDichEsistenzaVita/v1/anpr-service-e002', clientid, private_key, '3' 
FROM anpr_parametri WHERE id = 1;

COMMIT;
PRAGMA foreign_keys = ON;
SQL
    echo "Aggiornamento anpr_servizi e anpr_parametri completato."
else
    echo "Servizio C007 già presente in anpr_servizi."
fi


# Aggiornamento logs
has_audit_purposeid="$(column_exists logs purposeid)"

if [[ "$has_audit_purposeid" == "0" ]]; then
    echo "Aggiornamento colonna purposeid in tabella logs..."
    sqlite3 "$DB_PATH" <<'SQL'
ALTER TABLE logs ADD COLUMN purposeid VARCHAR(36);
ALTER TABLE logs ADD COLUMN resp_status INTEGER;
ALTER TABLE logs ADD COLUMN token_id VARCHAR(36);
SQL
else
    echo "Tabella logs già allineata."
fi

# Aggiunta tracing PDND
has_tracing_parametri="$(table_exists tracing_parametri)"

if [[ "$has_tracing_parametri" == "0" ]]; then
    echo "Creazione tabella tracing_parametri e inserimento dati di base..."
    sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE tracing_parametri (
    id INTEGER PRIMARY KEY,
    kid VARCHAR(42),
    alg VARCHAR(10),
    typ VARCHAR(10),
    iss VARCHAR(36),
    sub VARCHAR(36),
    aud VARCHAR(150),
    purposeid VARCHAR(36),
    audience VARCHAR(150),
    baseurlauth VARCHAR(150),
    target VARCHAR(150),
    clientid VARCHAR(50),
    private_key VARCHAR(2500),
    ver_eservice VARCHAR(10),
    tracing_audience TEXT DEFAULT 'att.interop.pagopa.it/tracing'
);

INSERT OR IGNORE INTO tracing_parametri (id) VALUES (1);
INSERT OR IGNORE INTO gruppi_parametri (id, descrizione) VALUES (0, 'Tracing PDND');
INSERT OR IGNORE INTO servizi_parametri (id, codice_servizio, descrizione, gruppo_id, attivo, url) VALUES (0, 'tracing_pdnd', 'Tracing PDND', 0, 1, 'impostazioni_tracing');

COMMIT;
PRAGMA foreign_keys = ON;
SQL
else
    echo "Tabella tracing_parametri già presente."
fi

# Aggiunta colonna tracing_audience se mancante (tabella potrebbe essere precedente alla 1.2)
has_tracing_audience="$(column_exists tracing_parametri tracing_audience)"
if [[ "$has_tracing_audience" == "0" ]]; then
    echo "Aggiunta colonna tracing_audience a tracing_parametri..."
    sqlite3 "$DB_PATH" "ALTER TABLE tracing_parametri ADD COLUMN tracing_audience TEXT DEFAULT 'att.interop.pagopa.it/tracing';"
else
    echo "Colonna tracing_audience già presente."
fi

# Aggiornamento parametri generali di configurazione del servizio Tracing (non dati personali)
echo "Aggiornamento parametri generali tracing_parametri (endpoint e configurazione)..."
sqlite3 "$DB_PATH" <<'SQL'
UPDATE tracing_parametri SET
    alg       = CASE WHEN (alg IS NULL OR alg = '') THEN 'RS256' ELSE alg END,
    typ       = CASE WHEN (typ IS NULL OR typ = '') THEN 'JWT'   ELSE typ END,
    aud       = CASE WHEN (aud IS NULL OR aud = '' OR aud = 'att.interop.pagopa.it/tracing')
                     THEN 'auth.att.interop.pagopa.it/client-assertion' ELSE aud END,
    audience  = CASE WHEN (audience IS NULL OR audience = '')
                     THEN 'eservices.att.interop.pagopa.it' ELSE audience END,
    baseurlauth = CASE WHEN (baseurlauth IS NULL OR baseurlauth = '' OR baseurlauth = 'https://auth.interop.pagopa.it')
                       THEN 'auth.att.interop.pagopa.it' ELSE baseurlauth END,
    target    = CASE WHEN (target IS NULL OR target = '' OR target LIKE 'http://eservices%')
                     THEN 'https://api.att.tracing.interop.pagopa.it' ELSE target END,
    ver_eservice = CASE WHEN (ver_eservice IS NULL OR ver_eservice = '')
                        THEN '1' ELSE ver_eservice END
WHERE id = 1;
SQL

# Aggiornamento mit_servizi: allinea le voci alla versione corrente
echo "Aggiornamento voci mit_servizi..."
sqlite3 "$DB_PATH" <<'SQL'
UPDATE mit_servizi SET servizio='Dettaglio Cude'     WHERE id=1 AND servizio != 'Dettaglio Cude';
UPDATE mit_servizi SET servizio='Lista Veicoli'      WHERE id=2 AND servizio != 'Lista Veicoli';
UPDATE mit_servizi SET servizio='Recupera Whitelist' WHERE id=3 AND servizio != 'Recupera Whitelist';
SQL

# Aggiornamento mit_parametri: allinea endpoint e versioni (dati generali)
echo "Aggiornamento parametri generali mit_parametri..."
sqlite3 "$DB_PATH" <<'SQL'
UPDATE mit_parametri SET 
    audience='https://gw.servizidt.it/rest/in/MCTC/DettaglioCude/v1', 
    target='https://gw.servizidt.it/rest/in/MCTC/DettaglioCude/v1/cude/', 
    ver_eservice='1' 
WHERE id=1 AND (audience LIKE 'https://1111%' OR audience IS NULL OR audience = '');

UPDATE mit_parametri SET 
    audience='https://gw.servizidt.it/rest/in/MCTC/ListaVeicoliCude/v1', 
    target='https://gw.servizidt.it/rest/in/MCTC/ListaVeicoliCude/v1/cude/listaVeicoli', 
    ver_eservice='2' 
WHERE id=2 AND (audience LIKE 'https://2222%' OR audience IS NULL OR audience = '');

UPDATE mit_parametri SET 
    audience='https://gw.servizidt.it/rest/in/MCTC/WhiteListCompletaCude/v1', 
    target='https://gw.servizidt.it/rest/in/MCTC/WhiteListCompletaCude/v1/cude/whitelist/completa/recupera', 
    ver_eservice='2' 
WHERE id=3 AND (audience LIKE 'https://3333%' OR audience IS NULL OR audience = '');

UPDATE mit_parametri SET 
    audience='https://gw.servizidt.it/rest/in/MCTC/VerificaTargaCude/v1', 
    target='https://gw.servizidt.it/rest/in/MCTC/VerificaTargaCude/v1/cude/verificaTarga', 
    ver_eservice='2' 
WHERE id=4 AND (audience LIKE 'https://4444%' OR audience IS NULL OR audience = '');
SQL

# Upgrade completato

if [[ "$(table_exists dati_ente)" == "1" ]]; then
  sqlite3 "$DB_PATH" "UPDATE dati_ente SET versione = '1.2.0' WHERE versione = '1.1.0';"
  echo "Versione in dati_ente aggiornata a 1.2.0 (se era 1.1.0)."
fi

if [[ -f "$PROJECT_ROOT/manage.py" ]]; then
  echo "Esecuzione migrazioni Django..."
  python "$PROJECT_ROOT/manage.py" makemigrations
  python "$PROJECT_ROOT/manage.py" migrate
fi

echo "Upgrade struttura DB alla versione 1.2 completato."
