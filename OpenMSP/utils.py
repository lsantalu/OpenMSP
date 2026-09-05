# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
import re
import datetime
from datetime import date
import pytz
from django.db import connection
from impostazioni.models import Logs

_LOGS_COLUMNS = None


TABELLA_LOGS = "logs"   # db_table del modello Logs, letterale: niente SQL costruito a runtime


def _get_logs_columns():
    """Colonne realmente presenti in logs (lo schema puo' divergere dal modello)."""
    global _LOGS_COLUMNS
    if _LOGS_COLUMNS is None:
        with connection.cursor() as cursor:
            _LOGS_COLUMNS = {
                col.name for col in connection.introspection.get_table_description(
                    cursor, TABELLA_LOGS
                )
            }
    return _LOGS_COLUMNS


# Le colonne del DB possono divergere dal modello (storia: tocken_id). Ogni variante ha la
# sua istruzione LETTERALE, cosi' nell'SQL non finisce nulla costruito a runtime.
AGGIORNA_LOG = {
    "purposeid":   "UPDATE logs SET purposeid = %s WHERE id = %s",
    "purpose_id":  "UPDATE logs SET purpose_id = %s WHERE id = %s",
    "resp_status": "UPDATE logs SET resp_status = %s WHERE id = %s",
    "respStatus":  'UPDATE logs SET "respStatus" = %s WHERE id = %s',
    "token_id":    "UPDATE logs SET token_id = %s WHERE id = %s",
    "tocken_id":   "UPDATE logs SET tocken_id = %s WHERE id = %s",
}
for _colonna in AGGIORNA_LOG:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", _colonna):
        raise RuntimeError(f"chiave non valida in AGGIORNA_LOG: {_colonna!r}")  # non assert: -O lo salterebbe

def converti_data(data):
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = converti_data(value)
    elif isinstance(data, list):
        for i in range(len(data)):
            data[i] = converti_data(data[i])
    elif isinstance(data, str):
        if date_pattern.match(data):
            # Convertire la data nel formato DD-MM-YYYY
            date_obj = datetime.datetime.strptime(data, '%Y-%m-%d')
            return date_obj.strftime('%d-%m-%Y')
    return data

def normalizza_data(data_input):
    if isinstance(data_input, date):
        return data_input
    else:
        try:
            data_input = re.sub(r'[-.]', '/', data_input)
            parts = data_input.split('/')
            if len(parts[0]) == 4:
                anno, mese, giorno = map(int, parts)
            elif len(parts[0]) == 2 and len(data_input) == 10 :
                giorno, mese, anno = map(int, parts)
            elif len(data_input) == 8 :
                parts[2] = "20"+parts[2]
                giorno, mese, anno = map(int, parts)
            else:
                # nessun formato riconosciuto: meglio None che UnboundLocalError su date()
                return None
            parsed_date = date(anno, mese, giorno)
            return parsed_date
        except (ValueError, AttributeError, TypeError, IndexError):
            # qui cadono tutti gli input marcio: None, numeri, date spezzate, formato ignoto
            return None

def is_daylight_saving(date, timezone):
    tz = pytz.timezone(timezone)
    aware_date = tz.localize(datetime.datetime.combine(date, datetime.datetime.min.time()), is_dst=None)
    return aware_date.dst() != datetime.timedelta(0)

def _status_log(valore):
    """resp_status e' una IntegerField: qualche chiamante passa testo (es. res.text[:256]).

    Senza normalizzazione l'INSERT solleva ValueError e la richiesta finisce 500.
    """
    try:
        return int(valore)
    except (TypeError, ValueError):
        return None


def salva_log(utente, servizio, richiesta, purposeid=None, resp_status=None, token_id=None):
    resp_status = _status_log(resp_status)
    log = Logs(
        utente_id=utente,
        servizio=servizio,
        richiesta=richiesta,
        purposeid=purposeid,
        resp_status=resp_status,
        token_id=token_id,
    )
    log.save()

    # Aggiorna direttamente le colonne presenti nel DB per coprire
    # eventuali differenze di naming tra modello e schema reale.
    updates = {}
    columns = _get_logs_columns()

    if purposeid is not None:
        if "purposeid" in columns:
            updates["purposeid"] = str(purposeid)
        elif "purpose_id" in columns:
            updates["purpose_id"] = str(purposeid)

    if resp_status is not None:
        if "resp_status" in columns:
            updates["resp_status"] = resp_status
        elif "respStatus" in columns:
            updates["respStatus"] = resp_status

    if token_id is not None:
        if "token_id" in columns:
            updates["token_id"] = str(token_id)
        elif "tocken_id" in columns:
            updates["tocken_id"] = str(token_id)

    with connection.cursor() as cursor:
        for colonna, valore in updates.items():
            cursor.execute(AGGIORNA_LOG[colonna], [valore, log.pk])


def svuota_none(oggetti):
    """None -> '' sui campi testo, perche' il filtro `| default:\'\'` non copre gli `if`.

    I parametri salvati prima della migrazione dei campi non-nullable arrivano come None
    e i template li mostrano come 'None' (issue #12).
    """
    da_pulire = [f.name for f in oggetti.model._meta.fields
                 if f.get_internal_type() in ("CharField", "TextField")]
    for o in oggetti:
        for nome in da_pulire:
            if getattr(o, nome, None) is None:
                setattr(o, nome, "")
    return oggetti
