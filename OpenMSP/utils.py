import re
import datetime
from datetime import date
import pytz
from impostazioni.models import Logs

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

def salva_log(utente, servizio, richiesta):
    log = Logs( utente_id=utente, servizio=servizio, richiesta=richiesta, )
    log.save();
