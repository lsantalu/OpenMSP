#!/usr/bin/env bash
# update/temp_update_to_1.5.sh
set -euo pipefail

# Upgrade schema/dati OpenMSP DB fino alla 1.5.0: audience e target di anncsu_parametri passano
# da .../anncsu-consultazione/v1 a .../anncsu-consultazione-comune/v1, e le tre righe degli
# e-service di scrittura (accessi, coordinate, odonimi) vengono create e precompilate.
#
# Incrementale, come i file fratelli: da un DB fermo alla 1.0.0 / 1.1.0 / 1.2.0 / 1.3.0 questo
# script richiama update_to_1.4.sh, che a sua volta richiama il 1.3, il 1.2 e l'1.1. Non serve
# eseguire i passaggi a mano uno per uno.
#
# Perche' serve: la sezione servers: di docs/SpecificaAPI_ANNCSU_Consultazione.yaml pubblica
# .../anncsu-consultazione/v1, ma l'e-service "ANNCSU - Consultazione per i Comuni" risulta
# registrato su PDND come .../anncsu-consultazione-comune/v1. Finche' il target non coincide
# con l'e-service a cui delega la finalita', l'erogatore risponde
# 403 AuthorizationTokenDeny / "Insufficient token claims": il claim aud del voucher lo dice,
# e anncsu_finalita_divergente (OpenMSP/anncsu.py) lo traduce nella pagina /anncsu/.
#
# Allinea anche le versioni e-service ANPR accreditate: C001 v1 -> v2 e C020 v2 -> v3
# (stesso meccanismo di allinea_versioni_anpr in update_to_1.4.sh).
#
# Idempotente: l'UPDATE e' pilotato da un LIKE sull'URL vecchio, quindi un DB gia' sistemato
# a mano (o dalla pagina impostazioni) non viene toccato e non nasce mai
# .../anncsu-consultazione-comune-comune/v1. Ri-eseguibile anche due volte di seguito.
#
# A differenza della 1.4 qui non c'e' nessun passaggio su .env, settings.py o collectstatic:
# e' una correzione di soli dati e anncsu_parametri viene riletto a ogni richiesta, quindi non
# serve riavviare il processo (vale solo per impostazioni_parametri, che riscrive .env: invariante 7).
#
# Usage:
#   ./update/temp_update_to_1.5.sh [path/to/db.sqlite3] [path/to/.env]

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

if [[ -z "$DB_PATH" ]]; then
  prompt_with_default DB_PATH "Percorso file db.sqlite3 da aggiornare" "$(suggest_first_existing_path "db.sqlite3")"
fi

# Serve solo a chi richiama gli script precedenti: la 1.4 riscrive .env e settings.py.
if [[ -z "$ENV_TARGET_PATH" ]]; then
  prompt_with_default ENV_TARGET_PATH "Percorso file .env da aggiornare" "$(suggest_first_existing_path ".env")"
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

table_exists() {
  sqlite3 "$DB_PATH" "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='$1');"
}

# Versioni e-service ANPR allineate a quelle accreditate: C001 v1 -> v2, C020 v2 -> v3.
# Due differenze rispetto a allinea_versioni_anpr della 1.4, entrambe volute:
#   - IN (SELECT ...) al posto di = (SELECT ...): con l'uguale, un DB che ha due righe
#     'C001%' fa morire lo script (subquery returns more than one row);
#   - CAST(ver_eservice AS INTEGER) < N al posto del semplice SET: rende l'operazione idempotente
#     e surtout non retrograda un DB gia' accreditato su una versione piu' alta (declassare
#     un e-service al di sotto di quanto rilasciato dall'ente farebbe fallire le chiamate).
allinea_versioni_anpr() {
  if [[ "$(table_exists anpr_parametri)" != "1" ]]; then
    echo "ATTENZIONE: tabella 'anpr_parametri' non trovata: salto l'allineamento versioni ANPR."
    return 0
  fi

  anpr_da_allineare="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM anpr_parametri WHERE (servizio_id IN (SELECT id FROM anpr_servizi WHERE servizio LIKE 'C001%') AND CAST(COALESCE(ver_eservice,'0') AS INTEGER) < 2) OR (servizio_id IN (SELECT id FROM anpr_servizi WHERE servizio LIKE 'C020%') AND CAST(COALESCE(ver_eservice,'0') AS INTEGER) < 3);")"
  echo "ANPR: $anpr_da_allineare righe sotto la versione accreditata (le altre restano come sono)."

  sqlite3 "$DB_PATH" <<'SQL'
BEGIN TRANSACTION;
UPDATE anpr_parametri SET ver_eservice = '2'
 WHERE servizio_id IN (SELECT id FROM anpr_servizi WHERE servizio LIKE 'C001%')
   AND CAST(COALESCE(ver_eservice,'0') AS INTEGER) < 2;
UPDATE anpr_parametri SET ver_eservice = '3'
 WHERE servizio_id IN (SELECT id FROM anpr_servizi WHERE servizio LIKE 'C020%')
   AND CAST(COALESCE(ver_eservice,'0') AS INTEGER) < 3;
COMMIT;
SQL

  sqlite3 -header -column "$DB_PATH" "SELECT s.servizio, p.ver_eservice AS versione FROM anpr_parametri p JOIN anpr_servizi s ON s.id = p.servizio_id WHERE s.servizio LIKE 'C001%' OR s.servizio LIKE 'C020%' ORDER BY s.servizio;"
}

column_exists() {
  sqlite3 "$DB_PATH" "SELECT EXISTS(SELECT 1 FROM pragma_table_info('$1') WHERE name='$2');"
}

# ANNCSU passa da 1 a 5 e-service. Tre tabelle toccate, perche' il doppio gate (invariante 1)
# legge servizi_parametri.attivo E il flag dell'utente:
#   - utenti_parametri: anncsu -> anncsu_consultazione_comuni (RENAME COLUMN conserva i valori)
#     e 4 nuoviBooleanField, uno per e-service;
#   - anncsu_servizi / anncsu_parametri: una riga di credenziali per e-service, come anpr_parametri
#     (le nuove righe nascono vuote: le credenziali sono dell'ente, invariante 6);
#   - servizi_parametri: una riga per e-service con il suo #tabN, altrimenti la voce non si
#     accende e la pagina impostazioni non ha dove puntare.
# Le credenziali si compilano dalla pagina impostazioni_anncsu (una tab per e-service).
allarga_anncsu() {
  if [[ "$(column_exists utenti_parametri anncsu)" == "1" ]] && [[ "$(column_exists utenti_parametri anncsu_consultazione_comuni)" != "1" ]]; then
    echo "Rinomino utenti_parametri.anncsu in anncsu_consultazione_comuni..."
    sqlite3 "$DB_PATH" "ALTER TABLE utenti_parametri RENAME COLUMN anncsu TO anncsu_consultazione_comuni;"
  fi

  for flag in anncsu_consultazione_comuni anncsu_accessi anncsu_coordinate anncsu_odonimi anncsu_visura; do
    if [[ "$(column_exists utenti_parametri "$flag")" != "1" ]]; then
      echo "Aggiunta colonna $flag a utenti_parametri..."
      sqlite3 "$DB_PATH" "ALTER TABLE utenti_parametri ADD COLUMN $flag BOOLEAN DEFAULT 0"
    fi
  done

  # id|etichetta|codice_servizio|tab   (l'1 esiste gia': e' la riga di sola rinomina)
  while IFS='|' read -r id etichetta codice tab; do
    [[ -z "$id" ]] && continue
    sqlite3 "$DB_PATH" <<SQL
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

INSERT INTO anncsu_servizi (id, servizio)
SELECT $id, '$etichetta' WHERE NOT EXISTS (SELECT 1 FROM anncsu_servizi WHERE id = $id);

INSERT INTO anncsu_parametri
  (id, servizio_id, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
SELECT $id, $id, '', '', '', '', '', '', '', '', '', '', '', '', ''
  WHERE NOT EXISTS (SELECT 1 FROM anncsu_parametri WHERE id = $id);

INSERT INTO servizi_parametri (codice_servizio, descrizione, gruppo_id, attivo, url)
SELECT '$codice', '$etichetta', id, 0, 'impostazioni_anncsu#$tab'
  FROM gruppi_parametri WHERE descrizione = 'ANNCSU'
   AND NOT EXISTS (SELECT 1 FROM servizi_parametri WHERE codice_servizio = '$codice');

COMMIT;
PRAGMA foreign_keys = ON;
SQL
  done <<'DEFINIZIONI'
2|Aggiornamento accessi|anncsu_accessi|tab2
3|Aggiornamento coordinate|anncsu_coordinate|tab3
4|Aggiornamento odonimi|anncsu_odonimi|tab4
5|Estratto di mappa per Visura|anncsu_visura|tab5
DEFINIZIONI

  # La voce che c'era gia' cambia nome (menu, home e pagina impostazioni leggono da qui).
  sqlite3 "$DB_PATH" "UPDATE servizi_parametri SET descrizione = 'Consultazione per i COMUNI',
                   url = 'impostazioni_anncsu#tab1' WHERE codice_servizio = 'anncsu';
                   UPDATE anncsu_servizi SET servizio = 'Consultazione per i COMUNI' WHERE id = 1;"

  # 'Attivazione e-service' stampa il nome del gruppo come intestazione di sezione: la
  # descrizione dell'e-service non deve ripetere il prefisso (come la voce gia' a terra).
  # Idempotente: il WHERE esclude le righe gia' corte.
  sqlite3 "$DB_PATH" "UPDATE servizi_parametri SET descrizione = replace(descrizione, 'ANNCSU - ', '')
                      WHERE codice_servizio LIKE 'anncsu%' AND descrizione LIKE 'ANNCSU - %';"
}

# Le righe 2-4 di anncsu_parametri nascono vuote da allarga_anncsu (le credenziali sono
# dell'ente: invariante 6). Qui si precompila solo quello che la specifica pubblica dice --
# target, audience, autority, alg, typ, versione -- e solo dove la colonna e' vuota, per non
# sovrascrivere cio' che l'ente ha gia' messo dalla pagina impostazioni. Idempotente.
#
# ATENZIONE all'host: le tre specifiche (docs/Specifica API-ANNCSU - Aggiornamento *.yaml)
# dicono modipa.agenziaentrate.it, mentre la riga della Consultazione, che funziona, usa
# modipa.agenziaentrate.gov.it. Se la prima chiamata fallisce per connessione/TLS l'host e' il
# primo indiziato: si corregge da impostazioni_anncsu, e purposeid va comunque messo
# dall'ente perche' arriva dall'accreditamento AgID e non sta in nessuna specifica.
prefilla_anncsu_aggiornamenti() {
  local accessi='https://modipa.agenziaentrate.it/govway/rest/in/AgenziaEntrate/anncsuaccessi/v1'
  local odonimi='https://modipa.agenziaentrate.it/govway/rest/in/AgenziaEntrate-PDND/anncsu-aggiornamento-odonimi/v1'
  local coppia id url
  for coppia in "2|$accessi" "3|$accessi" "4|$odonimi"; do
    id="${coppia%%|*}"
    url="${coppia#*|}"
    sqlite3 "$DB_PATH" <<SQL
UPDATE anncsu_parametri
   SET target        = CASE WHEN COALESCE(target,'')       = '' THEN '$url'  ELSE target        END,
       audience      = CASE WHEN COALESCE(audience,'')     = '' THEN '$url'  ELSE audience      END,
       baseurlauth   = CASE WHEN COALESCE(baseurlauth,'')  = '' THEN 'https://auth.interop.pagopa.it' ELSE baseurlauth END,
       alg           = CASE WHEN COALESCE(alg,'')          = '' THEN 'RS256' ELSE alg           END,
       typ           = CASE WHEN COALESCE(typ,'')          = '' THEN 'JWT'   ELSE typ           END,
       ver_eservice  = CASE WHEN COALESCE(ver_eservice,'') = '' THEN '1'     ELSE ver_eservice  END
 WHERE id = $id;
SQL
  done
}

URL_VECCHIO='/anncsu-consultazione/v1'
URL_NUOVO='/anncsu-consultazione-comune/v1'

if [[ "$(table_exists anncsu_parametri)" == "1" ]]; then
  echo "INFO: stato attuale di anncsu_parametri:"
  sqlite3 -header -column "$DB_PATH" "SELECT id, audience, target FROM anncsu_parametri;"
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${DB_PATH}.bak.${RUN_TS}"
cp -a "$DB_PATH" "$BACKUP_PATH"
echo "Backup DB creato: $BACKUP_PATH"

if [[ "$(table_exists dati_ente)" == "1" ]]; then
  DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
  echo "INFO: Versione database rilevata: '$DB_VERSION'"

  case "$DB_VERSION" in
  "1.5.0")
    echo "Database già alla versione 1.5.0: riallineo le versioni e-service ANPR e ANNCSU."
    allinea_versioni_anpr
    allarga_anncsu
    prefilla_anncsu_aggiornamenti
    exit 0
    ;;
  "1.4.0")
    ;;
  "1.0.0" | "1.1.0" | "1.2.0" | "1.3.0")
    # Un solo richiamo: update_to_1.4.sh contiene gia' la sua catena fino alla 1.0.0.
    echo "Rilevata versione $DB_VERSION. Avvio aggiornamento incrementale fino alla 1.4..."
    bash "$SCRIPT_DIR/update_to_1.4.sh" "$DB_PATH" "$ENV_TARGET_PATH"
    ;;
  *)
    echo "Errore: la versione del database ($DB_VERSION) non è compatibile con questo script di aggiornamento."
    exit 1
    ;;
  esac

  DB_VERSION=$(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;" | xargs echo -n)
  if [[ "$DB_VERSION" != "1.4.0" ]]; then
    echo "Errore: la versione del database ($DB_VERSION) non è compatibile con questo script di aggiornamento (richiesta 1.4.0)."
    exit 1
  fi
else
  echo "Attenzione: tabella 'dati_ente' non trovata. Impossibile verificare la versione."
fi

# Dopo la catena: un DB che arriva alla 1.4.0 ha le due tabelle ANNCSU create dal 1.4.
if [[ "$(table_exists anncsu_parametri)" != "1" ]]; then
  echo "Errore: tabella 'anncsu_parametri' non trovata, nemmeno dopo l'aggiornamento alla 1.4."
  echo "Ripristinare il backup se necessario: $BACKUP_PATH"
  exit 1
fi

echo "Allineamento versioni e-service ANPR (C001 v1 -> v2, C020 v2 -> v3)..."
allinea_versioni_anpr

echo "ANNCSU da 1 a 5 e-service (flag utente, tabelle e servizi di menu)..."
allarga_anncsu

echo "Precompila target/audience dei tre aggiornamenti (solo dove vuoto)..."
prefilla_anncsu_aggiornamenti

da_allineare="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM anncsu_parametri WHERE audience LIKE '%${URL_VECCHIO}%' OR target LIKE '%${URL_VECCHIO}%';")"
if [[ "$da_allineare" == "0" ]]; then
  echo "Nessuna riga da allineare (audience e target non puntano piu' a $URL_VECCHIO): registro solo la versione."
fi

sqlite3 "$DB_PATH" <<SQL
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- replace() e' idempotente per costruzione: sull'URL gia' corretto la $URL_VECCHIO
-- non compare piu', e il WHERE esclude comunque le righe gia' allineate.
UPDATE anncsu_parametri
   SET audience = replace(audience, '${URL_VECCHIO}', '${URL_NUOVO}'),
       target   = replace(target,   '${URL_VECCHIO}', '${URL_NUOVO}')
 WHERE audience LIKE '%${URL_VECCHIO}%'
    OR target   LIKE '%${URL_VECCHIO}%';

COMMIT;
PRAGMA foreign_keys = ON;
SQL

# Verifica: le tre righe di scrittura devono avere un target, altrimenti le pagine dicono
# solo 'authorith non utilizzabile' e l'operatore non capisce che mancano i parametri.
scoperte="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM anncsu_parametri WHERE id IN (2,3,4) AND COALESCE(target,'') = '';")"
if [[ "$scoperte" != "0" ]]; then
  echo "Errore: $scoperte righe di anncsu_parametri (2-4) sono ancora senza target."
  echo "Ripristinare il backup se necessario: $BACKUP_PATH"
  exit 1
fi

# Bump in una chiamata separata: se dati_ente non c'e', il UPDATE fa fallire l'intero
# heredoc e il ROLLBACK si porterebbe via anche la correzione di audience/target.
if [[ "$(table_exists dati_ente)" == "1" ]]; then
  sqlite3 "$DB_PATH" "UPDATE dati_ente SET versione = '1.5.0';"
fi

# Verifica a terra, come per la normalizzazione MIT della 1.4: se resta una riga sull'URL
# vecchio lo script esce 1 invece di dichiararsi a posto.
residue="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM anncsu_parametri WHERE audience LIKE '%${URL_VECCHIO}%' OR target LIKE '%${URL_VECCHIO}%';")"
doppi="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM anncsu_parametri WHERE audience LIKE '%-comune-comune%' OR target LIKE '%-comune-comune%';")"
if [[ "$residue" != "0" || "$doppi" != "0" ]]; then
  echo "Errore: allineamento incompleto (righe sull'URL vecchio: $residue, URL con doppio suffisso: $doppi)."
  echo "Ripristinare il backup: $BACKUP_PATH"
  exit 1
fi

echo "INFO: stato dopo l'aggiornamento:"
sqlite3 -header -column "$DB_PATH" "SELECT id, audience, target FROM anncsu_parametri;"
if [[ "$(table_exists dati_ente)" == "1" ]]; then
  echo "Versione database: $(sqlite3 "$DB_PATH" "SELECT versione FROM dati_ente LIMIT 1;")"
fi
echo "Upgrade struttura e dati DB alla versione 1.5 completato ($da_allineare righe allineate, backup: $BACKUP_PATH)."
