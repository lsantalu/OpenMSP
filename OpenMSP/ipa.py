# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
import io

import requests
from django.http import HttpResponse
from django.shortcuts import render
from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter

from impostazioni.models import IpaParametri, UtentiParametri

from . import avanzamento
from .avanzamento import RIGHE_SESSIONE, codici_da_file
from .utils import json_da_response, salva_log
from .verifica_cf import verifica_cf_azienda

URL_RICERCA_ENTI = "https://www.indicepa.gov.it:443/ws/WS16DESAMMServices/api/WS16_DES_AMM"


def ipa_export_excel(request):
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
        if isinstance(row, dict) and isinstance(row.get('data'), dict):
            # Caso in cui row è un dizionario singolo
            Ente = row['data']['denominazione']
            Verifica = "1"
            Domicilio = row['data'].get('pec', 'Domicilio digitale non trovato')

        elif isinstance(row, dict) and isinstance(row.get('data'), list):
            # Caso in cui row è un dizionario con una lista di dati
            Ente = row['data'][0]['denominazione']  # Prendi il valore di Ente dalla prima voce della lista
            Verifica = "1"
            pec_list = [sub_row.get('pec', '') for sub_row in row['data'] if sub_row.get('pec')]
            if pec_list:
                Domicilio = chr(10).join(pec_list)  # Usa newline per a capo nella stessa cella
                # Pulizia opzionale: rimuovi newline extra o spazi iniziali/fine per ogni PEC
                Domicilio = '\n'.join(pec.strip() for pec in Domicilio.split('\n') if pec.strip())
            else:
                Domicilio = "Domicilio digitale non trovato"

        else:
            Ente = str(row) if row else "Ente non trovato"
            Verifica = "-1"
            Domicilio = "Domicilio digitale non trovato"

        color = "FFFFFF"  # default bianco

        if Verifica == "1":
            color = "C6EFCE"  # verde chiaro
        else:
            color = "FFC7CE"  # rosso

        fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

        # Append senza normalizzare: preserva i newline in Domicilio
        riga = [i, Ente, Verifica, Domicilio]
        ws.append(riga)

        # Applica fill a tutta la riga corrente
        current_row = ws.max_row
        for col in ws.iter_rows(min_row=current_row, max_row=current_row):
            for cell in col:
                cell.fill = fill

        # Calcola larghezze: per Domicilio, stima la larghezza orizzontale ignorando newline (solo per colonne)
        for j, valore in enumerate(riga):
            value_str = str(valore) if valore is not None else ""
            # Per colonna D (indice 3), usa join con spazio per stimare larghezza max lineare
            if j == 3:  # Colonna Domicilio
                value_length = len(' '.join(value_str.split()))  # Ignora newline per larghezza orizzontale
            else:
                value_length = len(value_str)

            if len(max_lengths) <= j:
                max_lengths.append(value_length)
            else:
                max_lengths[j] = max(max_lengths[j], value_length)

    # Imposta larghezza colonne
    for col_idx, width in enumerate(max_lengths, 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = min(width + 2, 50)  # Limita a 50 per non esagerare, +2 per padding

    # Allineamento wrap text per colonna D (Domicilio)
    wrap_alignment = Alignment(wrap_text=True, vertical='top', horizontal='left')  # Aggiunto horizontal='left' per chiarezza
    ws.column_dimensions['D'].alignment = wrap_alignment

    # Applica esplicitamente l'allineamento a tutte le celle della colonna D (per robustezza)
    for row in ws.iter_rows(min_row=2):  # Dal row 2 (dati, escludi intestazione)
        if len(row) >= 4:  # Assicura che ci sia la colonna D
            row[3].alignment = wrap_alignment  # Applica a cella D

    # Imposta altezze righe dinamicamente per gestire multipli newline in Domicilio
    for row_num in range(2, ws.max_row + 1):  # Dal row 2 in poi
        cell_d = ws.cell(row=row_num, column=4)  # Colonna D
        value_str = str(cell_d.value) if cell_d.value is not None else ""
        num_lines = len(value_str.split('\n'))  # Conta approssimativa delle righe (basata su newline)
        row_height = max(15, num_lines * 15)  # Altezza minima 15 per riga virtuale; max per multipli
        ws.row_dimensions[row_num].height = min(row_height, 200)  # Limita a 200 per non esagerare

    # Scrive l'Excel su un buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=EsitoDomiciliDigitaliPA.xlsx'
    return response


def ipa_singola(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.ipa_singolo
        ipa_parametri = IpaParametri.objects.get(id=1)
        auth_id = ipa_parametri.auth_id
        codice_ipa = ""
        if request.method == 'POST':
            data = []
            occorrenze = ""
            testo_log = ""
            descrizione = request.POST.get('input_descrizione_ente')
            cf = request.POST.get('input_CF')
            codice_ipa = request.POST.get('input_codice_ente')
            if (descrizione is not None): ##inserisco descrizione (anche più di una)
                testo_log = descrizione
                url = "https://www.indicepa.gov.it:443/ws/WS16DESAMMServices/api/WS16_DES_AMM"
                payload = {
                    "AUTH_ID": auth_id,
                    "DESCR": descrizione
                    }
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded'
                    }
                response = requests.post(url, data=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    temp_data = json_da_response(response)
                    occorrenze = temp_data.get('result', {}).get('num_items', 0)
                    if occorrenze:
                        for indice in range(occorrenze):
                            codice_ipa = temp_data['data'][indice]['cod_amm']
                            response = ipa_codice(auth_id, codice_ipa)
                            if response.status_code == 200:
                                risultato = response.json()
                            else:
                                risultato = {"error": f"Request failed with status code {response.status_code}"}
                            data.append(risultato)
                    else:
                        response = ipa_codice(auth_id, "999999")
                        risultato = response.json()
                        data.append(risultato)


            elif (cf is not None): ##inserisco CF
                testo_log = cf
                verifica_cf_ipa = verifica_cf_azienda(cf)
                if verifica_cf_ipa == 1:
                    url = "https://www.indicepa.gov.it:443/ws/WS23DOMDIGCFServices/api/WS23_DOM_DIG_CF"
                    payload = {
                        "AUTH_ID": auth_id,
                        "CF": cf
                        }
                    headers = {
                        'Content-Type': 'application/x-www-form-urlencoded'
                        }
                    response = requests.post(url, data=payload, headers=headers, timeout=30)
                    if response.status_code == 200:
                        temp_data = json_da_response(response)
                        # corpo vuoto o 200 non JSON: lo stesso "non trovato" del ramo descrizione
                        dati = temp_data.get('data') or [{}]
                        codice_ipa = dati[0].get('cod_amm', '999999')
                        response = ipa_codice(auth_id, codice_ipa)
                        if response.status_code == 200:
                            risultato = response.json()
                        else:
                            risultato = {"error": f"Request failed with status code {response.status_code}"}
                        data.append(risultato)
                else:
                    data.append("Codice fiscale non corretto")
            else: ##inserisco codice ipa
                response = ipa_codice(auth_id, codice_ipa)
                if response.status_code == 200:
                    risultato = response.json()
                else:
                    risultato = {"error": f"Request failed with status code {response.status_code}"}
                data.append(risultato)

            status_code = 200 # Default se arriviamo qui con dati
            salva_log(request.user, "Verifica IndicePA", "Verificato domicilio ente " + testo_log, resp_status=status_code)
            return render(request, 'ipa_singola.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'ipa_singola.html', { 'utente_abilitato': utente_abilitato })


def _riga_ipa(request, ente, stato=None):
    """Una riga dell'IPA massiva: `(righe, ultimo, errore)`, e `righe` puo' essere lunga pi' di uno.

    Un nome di ente porta una o pi' amministrazioni, e ognuna finisce in lista col proprio
    dizionale di WS20_PEC: e' la forma che il template e `ipa_export_excel` si aspettano. Il
    contatore della card conta i nomi del file, non le amministrazioni trovate.
    `ultimo` porta il nome dell'ente (dato pubblico di Indice PA), non un dato di una persona.
    Ogni interrogazione lascia la sua riga in `logs` (invariante 2): il giro vecchio ne
    scriveva una sola in fondo al file.
    """
    auth_id = IpaParametri.objects.get(id=1).auth_id
    intestazioni = {'Content-Type': 'application/x-www-form-urlencoded'}
    risposta = requests.post(URL_RICERCA_ENTI, data={'AUTH_ID': auth_id, 'DESCR': ente},
                            headers=intestazioni, timeout=30)
    salva_log(request.user, "Verifica Ipa massivo", "Cercato ente " + ente,
              resp_status=risposta.status_code)
    if risposta.status_code != 200:
        return [ente], ente, f'HTTP {risposta.status_code}'
    dati = json_da_response(risposta)
    if not (dati.get('result') or {}).get('num_items', 0):
        return [ente], ente, 'Ente non trovato'
    righe = []
    for amministrazione in (dati.get('data') or []):
        pec = ipa_codice(auth_id, amministrazione['cod_amm'])
        salva_log(request.user, "Verifica Ipa massivo",
                  "Domicilio di " + amministrazione['cod_amm'], resp_status=pec.status_code)
        righe.append(json_da_response(pec) if pec.status_code == 200
                     else {"error": f"Request failed with status code {pec.status_code}"})
    return righe, ente, ''


def _fine_ipa(request, fatte):
    salva_log(request.user, "Verifica Ipa massivo", f"Fine caricamento file: codici n. {fatte}")


def ipa_massiva(request):
    """IPA massiva: CSV/XLSX in colonna (A), i nomi degli enti, un domicilio per ente.

    Il giro dei codici lo comanda il navigatore (`ipa_massiva_riga`), cosi' la card
    dell'overlay dice il vero avanzamento; senza JavaScript `esegui_tutto` fa un giro solo
    con lo stesso worker. In `multi_data` finiscono stringhe (ente non trovato) e dizionali
    di WS20_PEC, come ci sono sempre finite: l'export Excel rilegge quelli.
    """
    contesto = {'utente_abilitato': False}
    if not request.user.id:
        return render(request, 'ipa_massiva.html', contesto)
    contesto['utente_abilitato'] = bool(UtentiParametri.objects.get(id=request.user.id).ipa_massivo)

    if request.method != 'POST':
        if request.GET.get('eseguito'):
            # il navigatore torna qui quando ha finito i giri: la tabella la rende il server
            contesto['data'] = request.session.get(RIGHE_SESSIONE, [])
        return render(request, 'ipa_massiva.html', contesto)

    # Invariante 1: il gate va riverificato nel POST, un segnalibro non basta
    if not contesto['utente_abilitato']:
        contesto['error'] = "L'utente non è abilitato all'utilizzo di questo servizio"
        return render(request, 'ipa_massiva.html', contesto)

    if 'cf_csv' not in request.FILES:
        contesto['error'] = ("Il file non è arrivato: riselezionarlo o trascinarlo di nuovo "
                             "nella zona di caricamento.")
        return render(request, 'ipa_massiva.html', contesto)

    codici, errore = codici_da_file(request.FILES['cf_csv'])
    if errore:
        salva_log(request.user, "Verifica Ipa massivo", errore)
        contesto['error'] = errore
        return render(request, 'ipa_massiva.html', contesto)
    if not codici:
        contesto['error'] = 'Nessun codice nel file: la colonna (A) deve contenere i nomi degli enti.'
        return render(request, 'ipa_massiva.html', contesto)

    if request.POST.get('js'):
        avanzamento.avvia(request, codici)
        contesto['totale'] = len(codici)
    else:
        # senza JavaScript: un giro solo
        contesto['data'] = avanzamento.esegui_tutto(request, codici, _riga_ipa, _fine_ipa)
    return render(request, 'ipa_massiva.html', contesto)


def ipa_massiva_riga(request):
    """Una riga dell'IPA massiva in corso: il POST porta l'indice, la lista sta in sessione."""
    return avanzamento.risposta_riga(request, 'ipa_massivo', _riga_ipa, _fine_ipa)


def ipa_codice(auth_id, codice_ipa):
    url = "https://www.indicepa.gov.it:443/ws/WS20PECServices/api/WS20_PEC"
    payload = {
        "AUTH_ID": auth_id,
        "COD_AMM": codice_ipa
        }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
        }
    return requests.post(url, data=payload, headers=headers, timeout=30)


def impostazioni_ipa(request):
    parametri_ipa = IpaParametri.objects.all()
    if request.method == 'POST':
        auth_id = request.POST.get('auth_id')
        dati = IpaParametri(1, auth_id)
        dati.save()
        salva_log(request.user,"Impostazioni IPA", "modifica parametri")
    else:
        parametri_ipa = IpaParametri.objects.all()

    return render(request, 'impostazioni_ipa.html', {'parametri_ipa': parametri_ipa})

