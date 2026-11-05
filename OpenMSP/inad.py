# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
from django.shortcuts import render
from impostazioni.models import InadParametri
from impostazioni.models import UtentiParametri

from .utils import salva_log
from .verifica_cf import verifica_cf
from . import agid

import requests
import json
import io
import csv
import re
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Alignment
from openpyxl.utils import get_column_letter

from django.http import HttpResponse


def inad_export_excel(request):
    data = request.session.get("multi_data", [])  # Oppure recuperalo come preferisci
    wb = Workbook()
    ws = wb.active or wb.create_sheet()
    intestazione = ["#", "CF", "Verifica", "Domicilio digitale"]
    ws.append(intestazione)

    # Dizionario per la larghezza massima di ogni colonna
    max_lengths = [len(str(x)) for x in intestazione]  # Larghezze iniziali: l'intestazione e' gia' in mano
    
    if not data:
        return HttpResponse("Nessun dato disponibile per l'esportazione", status=400)
    
    for i, row in enumerate(data, 1):
        split_row = row.split()
        stato = split_row[1]
        color = "FFFFFF"  # default bianco

        if stato == "1" and "@" in split_row[2]:
            color = "C6EFCE"  # verde chiaro
        elif stato == "2":
            color = "FFEB9C"  # giallo
        else:
            color = "FFC7CE"  # rosso

        fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

        ws.append([i, split_row[0], split_row[1], " ".join(split_row[2:])])
        for col in ws.iter_rows(min_row=ws.max_row, max_row=ws.max_row):
            for i, cell in enumerate(col):
                cell.fill = fill
                value_length = len(str(cell.value)) if cell.value else 0
                if len(max_lengths) <= i:
                    max_lengths.append(value_length)
                else:
                    max_lengths[i] = max(max_lengths[i], value_length)

    # Imposta larghezza colonne
    for i, width in enumerate(max_lengths, 1):
        col_letter = get_column_letter(i)
        ws.column_dimensions[col_letter].width = width

    # Scrive l'Excel su un buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=EsitoDomiciliDigitaliPF.xlsx'
    return response


def inad_get_bearer():
    """(voucher, token_id) verso l'autority di INAD; ('', None) se non risponde.
    Client unico in OpenMSP/agid.py; il traffico e' congelato in OpenMSP/tests.py."""
    return agid.voucher(InadParametri.objects.get(id=1))


def inad_singola(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inad_singolo
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            # bearer ottenuto internamente se correttezza_cf == 1
            correttezza_cf = verifica_cf(cf) 
            if correttezza_cf == 1:
                bearer, tok_id = inad_get_bearer()
                parsed_output, status, purp_id = inad_verifica_utente(cf, bearer)
                data.append(estrai_mail(json.dumps(parsed_output)) if status == 200 else "Interrogazione INAD non riuscita (HTTP " + str(status) + ")")
                salva_log(request.user, "Verifica INAD singolo", "Verificato domicilio utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
            elif correttezza_cf == 2:
                data.append("Codice fiscale di persona minorenne")
                salva_log(request.user, "Verifica INAD singolo", "Verificato domicilio utente " + cf)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica INAD singolo", "Verificato domicilio utente " + cf)
            return render(request, 'inad_singola.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else: 
        utente_abilitato = False
    return render(request, 'inad_singola.html', { 'utente_abilitato': utente_abilitato })


def inad_massiva(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inad_massivo
        if request.method == 'POST':
            csv_file = request.FILES['cf_csv']
            data = []
            contatore = 0
            # bearer ottenuto per ogni riga valida
            if csv_file.name.endswith('.csv'):
                csv_file_text = io.TextIOWrapper(csv_file.file, encoding='utf-8')
                csv_reader = csv.reader(csv_file_text)
                for row in csv_reader:
                    if row[0]:  # Se row[0] non è vuoto o None
                        correttezza_cf = verifica_cf(row[0].strip().upper())
                        if correttezza_cf == 1:
                            bearer, tok_id = inad_get_bearer()
                            parsed_output, status, purp_id = inad_verifica_utente(row[0].strip().upper(), bearer)
                            data.append(row[0].strip().upper() + " " + str(correttezza_cf) + " " + estrai_mail(json.dumps(parsed_output)))
                            salva_log(request.user, "Verifica INAD massivo - riga CSV", "Verificato CF " + row[0], purposeid=purp_id, resp_status=status, token_id=tok_id)
                        elif correttezza_cf == 2:
                            data.append(row[0].strip().upper() + " " + str(correttezza_cf) + " Codice fiscale di persona minorenne")
                        else:
                            data.append(row[0].strip().upper() + " " + str(correttezza_cf) + " Codice fiscale non corretto")               
                        contatore += 1
                salva_log(request.user, "Verifica INAD massivo", "Fine elaborazione CSV - n. " + str(contatore) + " CF")
                request.session["multi_data"] = data  # <--- Salva i dati nella sessione
                return render(request, 'inad_massiva.html', {'data': data, 'utente_abilitato': utente_abilitato })
            elif csv_file.name.endswith('.xlsx') or csv_file.name.endswith('.XLSX') or csv_file.name.endswith('.Xlsx'):
                wb = openpyxl.load_workbook(csv_file)
                sheet = wb.active
                if sheet is None:
                    return HttpResponse("Foglio vuoto nel file XLSX", status=400)
                for row in sheet.iter_rows(min_row=1, values_only=True):
                    if row[0]:
                        correttezza_cf = verifica_cf(row[0].strip().upper())
                        if correttezza_cf == 1:
                            bearer, tok_id = inad_get_bearer()
                            parsed_output, status, purp_id = inad_verifica_utente(row[0].strip().upper(), bearer)
                            data.append(row[0].strip().upper() + " " + str(correttezza_cf) + " " + estrai_mail(json.dumps(parsed_output)))
                        elif correttezza_cf == 2:
                            data.append(row[0].strip().upper() + " " + str(correttezza_cf) + " Codice fiscale di persona minorenne")
                        else:
                            data.append(row[0].strip().upper() + " " + str(correttezza_cf) + " Codice fiscale non corretto")               
                        contatore += 1
                salva_log(request.user,"Verifica INAD massivo", "Verificati n. " + str(contatore) + " CF")
                request.session["multi_data"] = data  # <--- Salva i dati nella sessione
                return render(request, 'inad_massiva.html', {'data': data, 'utente_abilitato': utente_abilitato })           
            else:
                salva_log(request.user,"Verifica INAD massivo", "Errore caricamento file CSV")
                return render(request, 'inad_massiva.html', {'error': 'Il file non è un CSV', 'utente_abilitato': utente_abilitato })
    else: 
        utente_abilitato = False
    return render(request, 'inad_massiva.html', { 'utente_abilitato': utente_abilitato })


def inad_verifica_utente(cf, bearer):
    inad_parametri = InadParametri.objects.get(id=1)
    purposeid = inad_parametri.purposeid
    url = inad_parametri.target + '/extract'
    risposta = requests.get(
        url + '/' + cf,
        params={"practicalReference": "ABC123"},
        headers={"Authorization": "Bearer " + bearer},
        timeout=30,
        )
    try:
        response_data = risposta.json()
    except ValueError:
        response_data = {}
    return response_data, risposta.status_code, purposeid


def impostazioni_inad(request):
    parametri_inad = InadParametri.objects.all()
    if request.method == 'POST':
        kid = request.POST.get('kid')
        alg = request.POST.get('alg')
        typ = request.POST.get('typ')
        iss = request.POST.get('iss')
        sub = request.POST.get('sub')
        aud = request.POST.get('aud')
        purposeid = request.POST.get('purposeid')
        audience = request.POST.get('audience')
        baseurlauth = request.POST.get('baseurlauth')
        target = request.POST.get('target')
        clientid = request.POST.get('clientid')
        private_key = request.POST.get('private_key')
        ver_eservice = request.POST.get('ver_eservice')
        
        
        
        dati = InadParametri(1, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
        dati.save()
        salva_log(request.user,"Impostazioni INAD", "modifica parametri")
    else:
        parametri_inad = InadParametri.objects.all()
            
    return render(request, 'impostazioni_inad.html', {'parametri_inad': parametri_inad})

def estrai_mail(indirizzo):
    if "NOT_FOUND" in indirizzo:
        return "Domicilio non presente"
    else:
        regex_email = r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}'
        indirizzi = re.findall(regex_email, indirizzo, re.IGNORECASE)
        return indirizzi[0] if indirizzi else "Domicilio non reperibile"