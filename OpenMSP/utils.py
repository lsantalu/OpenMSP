import re
import datetime
from datetime import date
import pytz
from django.db import connection
from impostazioni.models import Logs

_LOGS_COLUMNS = None


def _get_logs_columns():
    global _LOGS_COLUMNS
    if _LOGS_COLUMNS is None:
        with connection.cursor() as cursor:
            _LOGS_COLUMNS = {
                col.name for col in connection.introspection.get_table_description(
                    cursor, Logs._meta.db_table
                )
            }
    return _LOGS_COLUMNS

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
            parsed_date = date(anno, mese, giorno)
            return parsed_date
        except (ValueError, AttributeError):
            return None

def is_daylight_saving(date, timezone):
    tz = pytz.timezone(timezone)
    aware_date = tz.localize(datetime.datetime.combine(date, datetime.datetime.min.time()), is_dst=None)
    return aware_date.dst() != datetime.timedelta(0)

def salva_log(utente, servizio, richiesta, purposeid=None, resp_status=None, token_id=None):
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
            updates["resp_status"] = int(resp_status)
        elif "respStatus" in columns:
            updates["respStatus"] = int(resp_status)

    if token_id is not None:
        if "token_id" in columns:
            updates["token_id"] = str(token_id)
        elif "tocken_id" in columns:
            updates["tocken_id"] = str(token_id)

    if updates:
        table = connection.ops.quote_name(Logs._meta.db_table)
        set_clause = ", ".join(
            f"{connection.ops.quote_name(col)} = %s" for col in updates.keys()
        )
        sql = f"UPDATE {table} SET {set_clause} WHERE {connection.ops.quote_name('id')} = %s"
        with connection.cursor() as cursor:
            cursor.execute(sql, list(updates.values()) + [log.pk])
