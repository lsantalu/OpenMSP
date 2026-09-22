#!/usr/bin/env bash
# update/update_to_1.4.sh
set -euo pipefail

# Upgrade schema/data OpenMSP DB from 1.3 to 1.4.
# Fix duplicate MIT service codes introduced in some upgraded production DBs.
# Aggiunge i sette permessi anpr_Cxxx_massivo a utenti_parametri (interrogazioni ANPR massive).
# Allinea le versioni e-service ANPR: C007 v3 -> v4, C017 v1 -> v2.
# Attiva l'e-service ANNCSU: tabelle anncsu_servizi / anncsu_parametri, gruppo e servizio
#   nei menu, permesso anncsu in utenti_parametri.
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

# Versioni e-service ANPR aggiornate da ANPR: C007 3->4, C017 1->2. Idempotente e
# selettivo (join sul nome servizio, non sull'id), gira anche su un DB gia' a
# 1.4.0: chi ha eseguito questo script prima della modifica si allinea da solo.
allinea_versioni_anpr() {
  sqlite3 "$DB_PATH" <<'SQL'
BEGIN TRANSACTION;
UPDATE anpr_parametri SET ver_eservice = '4'
 WHERE servizio_id = (SELECT id FROM anpr_servizi WHERE servizio LIKE 'C007%');
UPDATE anpr_parametri SET ver_eservice = '2'
 WHERE servizio_id = (SELECT id FROM anpr_servizi WHERE servizio LIKE 'C017%');
COMMIT;
SQL
  sqlite3 -header -column "$DB_PATH" "SELECT s.servizio, p.ver_eservice AS versione FROM anpr_parametri p JOIN anpr_servizi s ON s.id = p.servizio_id WHERE s.servizio LIKE 'C007%' OR s.servizio LIKE 'C017%';"
}

# e-service ANNCSU (Archivio Nazionale Numeri Civici Strade Urbane, Agenzia Entrate).
# Idempotente: gira sia su un DB alla 1.3.0 sia su uno gia' a 1.4.0, come allinea_versioni_anpr.
# Le due tabelle ricalcano anpr_servizi / anpr_parametri (1 riga servizio + 1 riga parametri,
# 8 operazioni = path sul target). kid qui e' VARCHAR(64): il KID di ANNCSU e' 43 caratteri e
# VARCHAR(42) lo troncava al passaggio su mysql (vedi nota in cima a impostazioni/models.py).
# La private_key resta vuota, e come in anpr_parametri/resto delle tabelle parametri di
# db_example restano vuoti anche kid, iss, sub, purposeid e clientid: sono i dati del singolo
# ente (invariante 6: le credenziali AgID vivono nel DB, non nel repository). Si compilano
# dalla pagina impostazioni_anncsu. Riempiono invece le costanti di protocollo e gli URL,
# che sono pubblici perche' pubblicati sulla specifica dell'erogatore.
attiva_anncsu() {
  sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS "anncsu_servizi" (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "servizio" VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS "anncsu_parametri" (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "servizio_id" INTEGER,
  "kid" VARCHAR(64),
  "alg" VARCHAR(10),
  "typ" VARCHAR(10),
  "iss" VARCHAR(36),
  "sub" VARCHAR(36),
  "aud" VARCHAR(150),
  "purposeid" VARCHAR(36),
  "audience" VARCHAR(150),
  "baseurlauth" VARCHAR(150),
  "target" VARCHAR(150),
  "clientid" VARCHAR(50),
  "private_key" VARCHAR(2500),
  "ver_eservice" TEXT DEFAULT 1,
  FOREIGN KEY("servizio_id") REFERENCES "anncsu_servizi"("id")
);

INSERT INTO gruppi_parametri (descrizione)
SELECT 'ANNCSU' WHERE NOT EXISTS (SELECT 1 FROM gruppi_parametri WHERE descrizione = 'ANNCSU');

INSERT INTO servizi_parametri (codice_servizio, descrizione, gruppo_id, attivo, url)
SELECT 'anncsu', 'Consultazione ANNCSU', id, 0, 'impostazioni_anncsu'
  FROM gruppi_parametri WHERE descrizione = 'ANNCSU'
   AND NOT EXISTS (SELECT 1 FROM servizi_parametri WHERE codice_servizio = 'anncsu');

INSERT INTO anncsu_servizi (id, servizio)
SELECT 1, 'Consultazione ANNCSU' WHERE NOT EXISTS (SELECT 1 FROM anncsu_servizi WHERE id = 1);

INSERT INTO anncsu_parametri
  (id, servizio_id, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
SELECT 1, 1,
       '', 'RS256', 'JWT',
       '', '',
       'auth.interop.pagopa.it/client-assertion',
       '',
       'https://modipa.agenziaentrate.gov.it/govway/rest/in/AgenziaEntrate-PDND/anncsu-consultazione/v1',
       'https://auth.interop.pagopa.it',
       'https://modipa.agenziaentrate.gov.it/govway/rest/in/AgenziaEntrate-PDND/anncsu-consultazione/v1',
       '', '', '1'
  WHERE NOT EXISTS (SELECT 1 FROM anncsu_parametri WHERE id = 1);

COMMIT;
PRAGMA foreign_keys = ON;
SQL

  if [[ "$(sqlite3 "$DB_PATH" "SELECT EXISTS(SELECT 1 FROM pragma_table_info('utenti_parametri') WHERE name='anncsu');")" == "0" ]]; then
    echo "Aggiunta colonna anncsu a utenti_parametri..."
    sqlite3 "$DB_PATH" "ALTER TABLE utenti_parametri ADD COLUMN anncsu BOOLEAN DEFAULT 0"
  else
    echo "Colonna anncsu gia' presente, la salto."
  fi
}

RUN_TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${DB_PATH}.bak.${RUN_TS}"
cp -a "$DB_PATH" "$BACKUP_PATH"
echo "Backup DB creato: $BACKUP_PATH"

if [[ "$(table_exists dati_ente)" == "1" ]]; then
  DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
  echo "INFO: Versione database rilevata: '$DB_VERSION'"

  case "$DB_VERSION" in
  "1.4.0")
    echo "Database già alla versione 1.4.0: applico allineamento versioni e-service ANPR e ANNCSU."
    allinea_versioni_anpr
    attiva_anncsu
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

column_exists_in_db() {
  local db_path="$1"
  local table_name="$2"
  local column_name="$3"
  sqlite3 "$db_path" "SELECT EXISTS(SELECT 1 FROM pragma_table_info('${table_name}') WHERE name='${column_name}');"
}

# Identificatore dell'e-service di tracing: serve a verifica_status_tracing per
# accorgersi che il client ha risolto una finalita' diversa da quella configurata
# (in quel caso l'RS risponde 401 'Invalid token' e dal codice non si puo' correggere).
if [[ "$(table_exists tracing_parametri)" == "1" ]] && [[ "$(column_exists_in_db "$DB_PATH" tracing_parametri eservice_id)" == "0" ]]; then
  echo "Aggiunta colonna eservice_id a tracing_parametri..."
  sqlite3 "$DB_PATH" "ALTER TABLE tracing_parametri ADD COLUMN eservice_id TEXT DEFAULT ''"
fi

# Interrogazioni ANPR massive: un permesso massivo per ogni caso d'uso, accanto a quello singolo
# gia' presente. Nessuna tabella nuova e nessuna riga in servizi_parametri: il gate del megamenu
# resta la riga anpr_c0xx gia' usata dal singolo (come ANIS IFS02 singolo/massivo).
for caso in C001 C007 C015 C017 C018 C020 C021; do
  colonna="anpr_${caso}_massivo"
  if [[ "$(column_exists_in_db "$DB_PATH" utenti_parametri "$colonna")" == "0" ]]; then
    echo "Aggiunta colonna $colonna a utenti_parametri..."
    sqlite3 "$DB_PATH" "ALTER TABLE utenti_parametri ADD COLUMN $colonna BOOLEAN DEFAULT 0"
  else
    echo "Colonna $colonna gia' presente, la salto."
  fi
done

echo "Attivazione e-service ANNCSU..."
attiva_anncsu

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

echo "Allineamento versioni e-service ANPR..."
allinea_versioni_anpr

echo "Pulizia e reset dell'array app_io_catalogo_servizi..."
sqlite3 "$DB_PATH" <<'SQL'
DELETE FROM app_io_catalogo_servizi;
SQL

echo "Aggiornamento configurazione .env per versione 1.4..."

if [[ -f "$ENV_TARGET_PATH" ]]; then
  BACKUP_ENV_PATH="${ENV_TARGET_PATH}.bak.${RUN_TS}"
  cp -a "$ENV_TARGET_PATH" "$BACKUP_ENV_PATH"
  echo "Backup .env creato: $BACKUP_ENV_PATH"

  # un .env copiato da un .env_example vecchio puo' non finire con a capo: senza, gli echo >> sottostanti
  # incollassero la nuova variabile sull'ultima riga, corrompendo il file
  if [[ -s "$ENV_TARGET_PATH" && -n "$(tail -c 1 "$ENV_TARGET_PATH")" ]]; then
    echo "" >>"$ENV_TARGET_PATH"
  fi

  ENV_CONTENT=$(cat "$ENV_TARGET_PATH")

  if [[ ! "$ENV_CONTENT" =~ "ALLOWED_HOSTS.*=" ]]; then
    echo "Aggiornamento ALLOWED_HOSTS in .env..."
    sed -i 's/^\(ALLOWED_HOSTS\s*=\s*\).*$/ALLOWED_HOSTS = openmsp.example.local,localhost,127.0.0.1/' "$ENV_TARGET_PATH" 2>/dev/null || true
  fi

  if [[ ! "$ENV_CONTENT" =~ "CSRF_TRUSTED_ORIGINS.*=" ]]; then
    echo "Aggiunta CSRF_TRUSTED_ORIGINS in .env..."
    echo "CSRF_TRUSTED_ORIGINS = https://openmsp.example.local,http://localhost:8000" >>"$ENV_TARGET_PATH"
  fi

  if [[ ! "$ENV_CONTENT" =~ "SECURE_PROXY_SSL_HEADER.*=" ]]; then
    echo "Aggiunta SECURE_PROXY_SSL_HEADER in .env..."
    echo "SECURE_PROXY_SSL_HEADER = HTTP_X_FORWARDED_PROTO,https" >>"$ENV_TARGET_PATH"
  fi

  if [[ ! "$ENV_CONTENT" =~ "USE_X_FORWARDED_HOST.*=" ]]; then
    echo "Aggiunta USE_X_FORWARDED_HOST in .env..."
    echo "USE_X_FORWARDED_HOST = True" >>"$ENV_TARGET_PATH"
  fi

  if [[ ! "$ENV_CONTENT" =~ "AUTH_LDAP_GLOBAL_OPTIONS.*=" ]]; then
    echo "Aggiunta AUTH_LDAP_GLOBAL_OPTIONS in .env..."
    echo "AUTH_LDAP_GLOBAL_OPTIONS = {}" >>"$ENV_TARGET_PATH"
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

    # Issue #14: senza questo blocco AUTH_LDAP_GLOBAL_OPTIONS nel .env viene ignorata.
    # Appeso in fondo al file: config() e ldap sono gia importati all'inizio.
    if ! grep -q "^AUTH_LDAP_GLOBAL_OPTIONS" "$SETTINGS_FILE"; then
      echo "Aggiunta AUTH_LDAP_GLOBAL_OPTIONS in settings.py..."
      cat >>"$SETTINGS_FILE" <<'GLOBAL_LDAP_EOF'

_raw_ldap_global_options = config(
    "AUTH_LDAP_GLOBAL_OPTIONS",
    cast=json.loads,
    default="{}",
)

if not _raw_ldap_global_options:
    _raw_ldap_global_options = {}
elif not isinstance(_raw_ldap_global_options, dict):
    raise ValueError('AUTH_LDAP_GLOBAL_OPTIONS deve essere un oggetto JSON, es. {"OPT_X_TLS_CACERTFILE": "/app/ca/ente.pem"}')

AUTH_LDAP_GLOBAL_OPTIONS = {
    getattr(ldap, key): value
    for key, value in _raw_ldap_global_options.items()
}
GLOBAL_LDAP_EOF
    fi
  fi
fi

if [[ -f "$PROJECT_ROOT/manage.py" ]]; then
  echo "Esecuzione migrazioni Django..."

  # manage.py va eseguito con il python dell'ambiente virtualenv del progetto:
  # il python3 di sistema non ha Django ne' le dipendenze di requirements.txt.
  VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/env}"
  source "$VENV_DIR/bin/activate"
  echo "Ambiente attivato: $VIRTUAL_ENV"

  python "$PROJECT_ROOT/manage.py" collectstatic --noinput
  python "$PROJECT_ROOT/manage.py" migrate
fi

echo "Upgrade struttura e dati DB alla versione 1.4 completato."
