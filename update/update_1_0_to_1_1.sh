#!/usr/bin/env bash
set -euo pipefail

# Upgrade schema OpenMSP DB from 1.0 to 1.1.
# Defaults are resolved from current directory first, then project root.
# Usage:
#   ./update/update_1_0_to_1_1.sh [path/to/db.sqlite3] [path/to/.env]

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
  read -r -p "$label [$default_value]: " input_value
  if [[ -z "$input_value" ]]; then
    printf -v "$var_name" "%s" "$default_value"
  else
    printf -v "$var_name" "%s" "$input_value"
  fi
}

DB_PATH="${1:-}"
ENV_TARGET_PATH="${2:-}"
REF_DB_PATH="$PROJECT_ROOT/db.sqlite3"
ENV_REF_V11_PATH="$PROJECT_ROOT/.env"

default_db_target="$(suggest_first_existing_path "db.sqlite3")"
default_env_target="$(suggest_first_existing_path ".env")"

if [[ -z "$DB_PATH" ]]; then
  prompt_with_default DB_PATH "Percorso file db.sqlite3 da aggiornare" "$default_db_target"
fi
if [[ -z "$ENV_TARGET_PATH" ]]; then
  prompt_with_default ENV_TARGET_PATH "Percorso file .env da aggiornare" "$default_env_target"
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "Errore: sqlite3 non trovato nel PATH."
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Errore: database non trovato: $DB_PATH"
  exit 1
fi

if [[ ! -f "$ENV_TARGET_PATH" ]]; then
  echo "Errore: file .env target non trovato: $ENV_TARGET_PATH"
  exit 1
fi

TARGET_DB_REAL="$(readlink -f "$DB_PATH" 2>/dev/null || echo "$DB_PATH")"
REF_DB_REAL="$(readlink -f "$REF_DB_PATH" 2>/dev/null || echo "$REF_DB_PATH")"
USE_DB_REFERENCE=0
if [[ -f "$REF_DB_PATH" && "$TARGET_DB_REAL" != "$REF_DB_REAL" ]]; then
  USE_DB_REFERENCE=1
fi

TARGET_ENV_REAL="$(readlink -f "$ENV_TARGET_PATH" 2>/dev/null || echo "$ENV_TARGET_PATH")"
REF_ENV_REAL="$(readlink -f "$ENV_REF_V11_PATH" 2>/dev/null || echo "$ENV_REF_V11_PATH")"
USE_ENV_REFERENCE=0
if [[ -f "$ENV_REF_V11_PATH" && "$TARGET_ENV_REAL" != "$REF_ENV_REAL" ]]; then
  USE_ENV_REFERENCE=1
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${DB_PATH}.bak.${RUN_TS}"
cp -a "$DB_PATH" "$BACKUP_PATH"
echo "Backup DB creato: $BACKUP_PATH"

table_exists_in_db() {
  local db_path="$1"
  local table_name="$2"
  sqlite3 "$db_path" "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='${table_name}');"
}

column_exists_in_db() {
  local db_path="$1"
  local table_name="$2"
  local column_name="$3"
  sqlite3 "$db_path" "SELECT EXISTS(SELECT 1 FROM pragma_table_info('${table_name}') WHERE name='${column_name}');"
}

table_exists() {
  local table_name="$1"
  table_exists_in_db "$DB_PATH" "$table_name"
}

column_exists() {
  local table_name="$1"
  local column_name="$2"
  column_exists_in_db "$DB_PATH" "$table_name" "$column_name"
}

has_utenti_parametri="$(table_exists utenti_parametri)"
has_mit_patenti=0
has_mit_whitelist=0

if [[ "$has_utenti_parametri" == "1" ]]; then
  has_mit_patenti="$(column_exists utenti_parametri mit_patenti)"
  has_mit_whitelist="$(column_exists utenti_parametri mit_whitelist)"
fi

sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS "otp_totp_totpdevice" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(64) NOT NULL,
  "confirmed" bool NOT NULL,
  "key" varchar(80) NOT NULL,
  "step" smallint unsigned NOT NULL CHECK ("step" >= 0),
  "t0" bigint NOT NULL,
  "digits" smallint unsigned NOT NULL CHECK ("digits" >= 0),
  "tolerance" smallint unsigned NOT NULL CHECK ("tolerance" >= 0),
  "drift" smallint NOT NULL,
  "last_t" bigint NOT NULL,
  "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
  "throttling_failure_count" integer unsigned NOT NULL CHECK ("throttling_failure_count" >= 0),
  "throttling_failure_timestamp" datetime NULL,
  "created_at" datetime NULL,
  "last_used_at" datetime NULL
);
CREATE INDEX IF NOT EXISTS "otp_totp_totpdevice_user_id_0fb18292" ON "otp_totp_totpdevice" ("user_id");

CREATE TABLE IF NOT EXISTS "otp_static_staticdevice" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(64) NOT NULL,
  "confirmed" bool NOT NULL,
  "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
  "throttling_failure_count" integer unsigned NOT NULL CHECK ("throttling_failure_count" >= 0),
  "throttling_failure_timestamp" datetime NULL,
  "created_at" datetime NULL,
  "last_used_at" datetime NULL
);
CREATE INDEX IF NOT EXISTS "otp_static_staticdevice_user_id_7f9cff2b" ON "otp_static_staticdevice" ("user_id");

CREATE TABLE IF NOT EXISTS "otp_static_statictoken" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "token" varchar(16) NOT NULL,
  "device_id" integer NOT NULL REFERENCES "otp_static_staticdevice" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "otp_static_statictoken_token_d0a51866" ON "otp_static_statictoken" ("token");
CREATE INDEX IF NOT EXISTS "otp_static_statictoken_device_id_74b7c7d1" ON "otp_static_statictoken" ("device_id");

COMMIT;
PRAGMA foreign_keys = ON;
SQL

if [[ "$has_utenti_parametri" == "1" ]]; then
  # Rebuild only if schema is still 1.0-style (mit_patenti present) or partially updated.
  if [[ "$has_mit_patenti" == "1" || "$has_mit_whitelist" == "0" ]]; then
    if [[ "$has_mit_patenti" == "1" ]]; then
      sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE "utenti_parametri_new" (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "utente_id" INTEGER,
  "ipa_singolo" BOOLEAN,
  "ipa_massivo" BOOLEAN,
  "inad_singolo" BOOLEAN,
  "inad_massivo" BOOLEAN,
  "inipec_singolo" BOOLEAN,
  "inipec_massivo" BOOLEAN,
  "anpr_C001" BOOLEAN,
  "anpr_C015" BOOLEAN,
  "anpr_C017" BOOLEAN,
  "anpr_C018" BOOLEAN,
  "anpr_C020" BOOLEAN,
  "anpr_C021" BOOLEAN,
  "anpr_C030" BOOLEAN,
  "mit_cude" BOOLEAN,
  "mit_veicoli" BOOLEAN,
  "mit_whitelist" BOOLEAN,
  "mit_targa" BOOLEAN,
  "anis_IFS02_singolo" BOOLEAN,
  "anis_IFS02_massivo" BOOLEAN,
  "anis_IFS03_singolo" BOOLEAN,
  "anis_IFS03_massivo" BOOLEAN,
  "cassa_forense" BOOLEAN,
  "registro_imprese" BOOLEAN,
  "inps_isee" BOOLEAN,
  "inps_durc_singolo" BOOLEAN,
  "inps_durc_massivo" BOOLEAN,
  "app_io_verifica_singolo" BOOLEAN,
  "app_io_verifica_massivo" BOOLEAN,
  "app_io_singolo" BOOLEAN,
  "app_io_massivo" BOOLEAN,
  "anist_frequenze_singolo" BOOLEAN,
  "anist_frequenze_massivo" BOOLEAN,
  "anist_titoli_singolo" BOOLEAN,
  "anist_titoli_massivo" BOOLEAN,
  "app_io_composer" BOOLEAN,
  "app_io_storico_messaggi" BOOLEAN,
  FOREIGN KEY("utente_id") REFERENCES "auth_user"("id")
);

INSERT INTO "utenti_parametri_new" (
  id, utente_id, ipa_singolo, ipa_massivo, inad_singolo, inad_massivo, inipec_singolo,
  inipec_massivo, anpr_C001, anpr_C015, anpr_C017, anpr_C018, anpr_C020, anpr_C021,
  anpr_C030, mit_cude, mit_veicoli, mit_whitelist, mit_targa, anis_IFS02_singolo,
  anis_IFS02_massivo, anis_IFS03_singolo, anis_IFS03_massivo, cassa_forense,
  registro_imprese, inps_isee, inps_durc_singolo, inps_durc_massivo,
  app_io_verifica_singolo, app_io_verifica_massivo, app_io_singolo, app_io_massivo,
  anist_frequenze_singolo, anist_frequenze_massivo, anist_titoli_singolo,
  anist_titoli_massivo, app_io_composer, app_io_storico_messaggi
)
SELECT
  id, utente_id, ipa_singolo, ipa_massivo, inad_singolo, inad_massivo, inipec_singolo,
  inipec_massivo, anpr_C001, anpr_C015, anpr_C017, anpr_C018, anpr_C020, anpr_C021,
  anpr_C030, mit_cude, mit_veicoli, mit_patenti, mit_targa, anis_IFS02_singolo,
  anis_IFS02_massivo, anis_IFS03_singolo, anis_IFS03_massivo, cassa_forense,
  registro_imprese, inps_isee, inps_durc_singolo, inps_durc_massivo,
  app_io_verifica_singolo, app_io_verifica_massivo, app_io_singolo, app_io_massivo,
  anist_frequenze_singolo, anist_frequenze_massivo, anist_titoli_singolo,
  anist_titoli_massivo, app_io_composer, app_io_storico_messaggi
FROM "utenti_parametri";

DROP TABLE "utenti_parametri";
ALTER TABLE "utenti_parametri_new" RENAME TO "utenti_parametri";

COMMIT;
PRAGMA foreign_keys = ON;
SQL
    else
      sqlite3 "$DB_PATH" <<'SQL'
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE "utenti_parametri_new" (
  "id" INTEGER PRIMARY KEY AUTOINCREMENT,
  "utente_id" INTEGER,
  "ipa_singolo" BOOLEAN,
  "ipa_massivo" BOOLEAN,
  "inad_singolo" BOOLEAN,
  "inad_massivo" BOOLEAN,
  "inipec_singolo" BOOLEAN,
  "inipec_massivo" BOOLEAN,
  "anpr_C001" BOOLEAN,
  "anpr_C015" BOOLEAN,
  "anpr_C017" BOOLEAN,
  "anpr_C018" BOOLEAN,
  "anpr_C020" BOOLEAN,
  "anpr_C021" BOOLEAN,
  "anpr_C030" BOOLEAN,
  "mit_cude" BOOLEAN,
  "mit_veicoli" BOOLEAN,
  "mit_whitelist" BOOLEAN,
  "mit_targa" BOOLEAN,
  "anis_IFS02_singolo" BOOLEAN,
  "anis_IFS02_massivo" BOOLEAN,
  "anis_IFS03_singolo" BOOLEAN,
  "anis_IFS03_massivo" BOOLEAN,
  "cassa_forense" BOOLEAN,
  "registro_imprese" BOOLEAN,
  "inps_isee" BOOLEAN,
  "inps_durc_singolo" BOOLEAN,
  "inps_durc_massivo" BOOLEAN,
  "app_io_verifica_singolo" BOOLEAN,
  "app_io_verifica_massivo" BOOLEAN,
  "app_io_singolo" BOOLEAN,
  "app_io_massivo" BOOLEAN,
  "anist_frequenze_singolo" BOOLEAN,
  "anist_frequenze_massivo" BOOLEAN,
  "anist_titoli_singolo" BOOLEAN,
  "anist_titoli_massivo" BOOLEAN,
  "app_io_composer" BOOLEAN,
  "app_io_storico_messaggi" BOOLEAN,
  FOREIGN KEY("utente_id") REFERENCES "auth_user"("id")
);

INSERT INTO "utenti_parametri_new" (
  id, utente_id, ipa_singolo, ipa_massivo, inad_singolo, inad_massivo, inipec_singolo,
  inipec_massivo, anpr_C001, anpr_C015, anpr_C017, anpr_C018, anpr_C020, anpr_C021,
  anpr_C030, mit_cude, mit_veicoli, mit_whitelist, mit_targa, anis_IFS02_singolo,
  anis_IFS02_massivo, anis_IFS03_singolo, anis_IFS03_massivo, cassa_forense,
  registro_imprese, inps_isee, inps_durc_singolo, inps_durc_massivo,
  app_io_verifica_singolo, app_io_verifica_massivo, app_io_singolo, app_io_massivo,
  anist_frequenze_singolo, anist_frequenze_massivo, anist_titoli_singolo,
  anist_titoli_massivo, app_io_composer, app_io_storico_messaggi
)
SELECT
  id, utente_id, ipa_singolo, ipa_massivo, inad_singolo, inad_massivo, inipec_singolo,
  inipec_massivo, anpr_C001, anpr_C015, anpr_C017, anpr_C018, anpr_C020, anpr_C021,
  anpr_C030, mit_cude, mit_veicoli, mit_whitelist, mit_targa, anis_IFS02_singolo,
  anis_IFS02_massivo, anis_IFS03_singolo, anis_IFS03_massivo, cassa_forense,
  registro_imprese, inps_isee, inps_durc_singolo, inps_durc_massivo,
  app_io_verifica_singolo, app_io_verifica_massivo, app_io_singolo, app_io_massivo,
  anist_frequenze_singolo, anist_frequenze_massivo, anist_titoli_singolo,
  anist_titoli_massivo, app_io_composer, app_io_storico_messaggi
FROM "utenti_parametri";

DROP TABLE "utenti_parametri";
ALTER TABLE "utenti_parametri_new" RENAME TO "utenti_parametri";

COMMIT;
PRAGMA foreign_keys = ON;
SQL
    fi
    echo "Tabella utenti_parametri migrata alla struttura 1.1."
  else
    echo "Tabella utenti_parametri gia' allineata alla struttura 1.1."
  fi
else
  echo "Tabella utenti_parametri non trovata: nessuna migrazione colonne da applicare."
fi

if [[ "$USE_DB_REFERENCE" == "1" ]]; then
  PARAM_TABLES=(
    anis_parametri
    anpr_parametri
    cassa_forense_parametri
    inad_parametri
    inps_durc_parametri
    inps_isee_parametri
    mit_parametri
    registro_imprese_parametri
  )

  PARAM_COLUMNS=(alg typ aud audience baseurlauth target ver_eservice)

  REF_DB_PATH_ESCAPED="${REF_DB_PATH//\'/''}"
  sql_sync_file="$(mktemp /tmp/openmsp_sync_params.XXXXXX.sql)"
  {
    echo "PRAGMA foreign_keys = OFF;"
    echo "BEGIN TRANSACTION;"
    echo "ATTACH DATABASE '${REF_DB_PATH_ESCAPED}' AS refdb;"
  } >"$sql_sync_file"
  sync_count=0
  catalogo_argomenti_synced=0
  gruppi_parametri_synced=0
  servizi_parametri_synced=0

  for table_name in "${PARAM_TABLES[@]}"; do
    if [[ "$(table_exists_in_db "$DB_PATH" "$table_name")" != "1" ]]; then
      continue
    fi
    if [[ "$(table_exists_in_db "$REF_DB_PATH" "$table_name")" != "1" ]]; then
      continue
    fi
    for col_name in "${PARAM_COLUMNS[@]}"; do
      if [[ "$(column_exists_in_db "$DB_PATH" "$table_name" "$col_name")" != "1" ]]; then
        continue
      fi
      if [[ "$(column_exists_in_db "$REF_DB_PATH" "$table_name" "$col_name")" != "1" ]]; then
        continue
      fi
      cat >>"$sql_sync_file" <<SQL
UPDATE "$table_name" AS dst
SET "$col_name" = (
  SELECT src."$col_name"
  FROM refdb."$table_name" AS src
  WHERE src.id = dst.id
)
WHERE EXISTS (
  SELECT 1
  FROM refdb."$table_name" AS src
  WHERE src.id = dst.id
);
SQL
      sync_count=$((sync_count + 1))
    done
  done

  if [[ "$(table_exists_in_db "$DB_PATH" "app_io_catalogo_argomenti")" == "1" ]] && \
     [[ "$(table_exists_in_db "$REF_DB_PATH" "app_io_catalogo_argomenti")" == "1" ]]; then
    cat >>"$sql_sync_file" <<'SQL'
DELETE FROM "app_io_catalogo_argomenti";
INSERT INTO "app_io_catalogo_argomenti" ("id", "argomento")
SELECT "id", "argomento"
FROM refdb."app_io_catalogo_argomenti";
SQL
    catalogo_argomenti_synced=1
  fi

  if [[ "$(table_exists_in_db "$DB_PATH" "gruppi_parametri")" == "1" ]] && \
     [[ "$(table_exists_in_db "$REF_DB_PATH" "gruppi_parametri")" == "1" ]]; then
    cat >>"$sql_sync_file" <<'SQL'
DELETE FROM "gruppi_parametri";
INSERT INTO "gruppi_parametri" ("id", "descrizione")
SELECT "id", "descrizione"
FROM refdb."gruppi_parametri";
SQL
    gruppi_parametri_synced=1
  fi

  if [[ "$(table_exists_in_db "$DB_PATH" "servizi_parametri")" == "1" ]] && \
     [[ "$(table_exists_in_db "$REF_DB_PATH" "servizi_parametri")" == "1" ]]; then
    cat >>"$sql_sync_file" <<'SQL'
DROP TABLE IF EXISTS temp_servizi_parametri_attivo;
CREATE TEMP TABLE temp_servizi_parametri_attivo AS
SELECT id, attivo
FROM "servizi_parametri";

DELETE FROM "servizi_parametri";
INSERT INTO "servizi_parametri" (
  "id", "codice_servizio", "descrizione", "gruppo_id", "attivo", "url"
)
SELECT
  ref."id",
  ref."codice_servizio",
  ref."descrizione",
  ref."gruppo_id",
  old."attivo",
  ref."url"
FROM refdb."servizi_parametri" AS ref
LEFT JOIN temp_servizi_parametri_attivo AS old ON old.id = ref.id;
SQL
    servizi_parametri_synced=1
  fi

  {
    echo "COMMIT;"
    echo "DETACH DATABASE refdb;"
    echo "PRAGMA foreign_keys = ON;"
  } >>"$sql_sync_file"

  sqlite3 "$DB_PATH" <"$sql_sync_file"
  rm -f "$sql_sync_file"
  echo "Aggiornamento parametri eseguito (regole applicate: $sync_count)."
  if [[ "$catalogo_argomenti_synced" == "1" ]]; then
    echo "Tabella app_io_catalogo_argomenti aggiornata dal DB di riferimento 1.1."
  else
    echo "Tabella app_io_catalogo_argomenti non sincronizzata (non presente in uno dei due DB)."
  fi
  if [[ "$gruppi_parametri_synced" == "1" ]]; then
    echo "Tabella gruppi_parametri aggiornata dal DB di riferimento 1.1."
  else
    echo "Tabella gruppi_parametri non sincronizzata (non presente in uno dei due DB)."
  fi
  if [[ "$servizi_parametri_synced" == "1" ]]; then
    echo "Tabella servizi_parametri aggiornata dal DB di riferimento 1.1 (colonna attivo preservata)."
  else
    echo "Tabella servizi_parametri non sincronizzata (non presente in uno dei due DB)."
  fi
else
  echo "Riferimento DB 1.1 non disponibile o coincide con il target: aggiornamenti dati avanzati saltati."
fi

declare -A env_target
declare -A env_v11
declare -A env_replacements

parse_env_to_map() {
  local file_path="$1"
  local -n out_map="$2"
  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      value="${value#"${value%%[![:space:]]*}"}"
      value="${value%"${value##*[![:space:]]}"}"
      out_map["$key"]="$value"
    fi
  done <"$file_path"
}

parse_env_to_map "$ENV_TARGET_PATH" env_target
if [[ "$USE_ENV_REFERENCE" == "1" ]]; then
  parse_env_to_map "$ENV_REF_V11_PATH" env_v11
fi

env_tmp_file="$(mktemp /tmp/openmsp_env_merge.XXXXXX.env)"
env_replaced_count=0

while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]]; then
    key="${BASH_REMATCH[1]}"
    if [[ -v env_replacements["$key"] ]]; then
      echo "$key = ${env_replacements[$key]}" >>"$env_tmp_file"
      env_replaced_count=$((env_replaced_count + 1))
      continue
    fi
  fi
  echo "$line" >>"$env_tmp_file"
done <"$ENV_TARGET_PATH"

new_env_keys=()
if [[ "$USE_ENV_REFERENCE" == "1" ]]; then
  for key in "${!env_v11[@]}"; do
    if [[ ! -v env_target["$key"] ]]; then
      new_env_keys+=("$key")
    fi
  done
fi

env_added_count=0
if [[ "${#new_env_keys[@]}" -gt 0 ]]; then
  mapfile -t new_env_keys < <(printf '%s\n' "${new_env_keys[@]}" | sort)
  echo "" >>"$env_tmp_file"
  echo "# Added by OpenMSP update_1_0_to_1_1.sh" >>"$env_tmp_file"
  for key in "${new_env_keys[@]}"; do
    echo "$key = ${env_v11[$key]}" >>"$env_tmp_file"
    env_added_count=$((env_added_count + 1))
  done
fi

ENV_BACKUP_PATH="${ENV_TARGET_PATH}.bak.${RUN_TS}"
cp -a "$ENV_TARGET_PATH" "$ENV_BACKUP_PATH"
mv "$env_tmp_file" "$ENV_TARGET_PATH"
echo "Backup .env creato: $ENV_BACKUP_PATH"
echo "Aggiornamento .env completato (valori aggiornati: $env_replaced_count, variabili aggiunte: $env_added_count)."
if [[ "$USE_ENV_REFERENCE" != "1" ]]; then
  echo "Riferimento .env 1.1 non disponibile o coincide con il target: nessuna sincronizzazione valori effettuata."
fi

echo "Upgrade struttura DB completato."
