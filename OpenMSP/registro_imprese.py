# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
from django.shortcuts import render                                  # noqa: I001  (gruppi separati: stile del repo, nessuna config ruff)
from impostazioni.models import RegistroImpreseParametri
from impostazioni.models import UtentiParametri

from .utils import salva_log
from .utils import converti_data
from .utils import normalizza_chiavi
from . import avanzamento
from .avanzamento import RIGHE_SESSIONE
from .avanzamento import codici_da_file as _legge_cf     # il lettore di colonna A: uno solo
from .inps import _nome_file_denominazione          # il sanificatore dei nomi e' quello dei PDF DURC

from .verifica_cf import verifica_cf_azienda
from . import agid

##from datetime import datetime, date
import json
import xmltodict
from xml.parsers.expat import ExpatError

import requests
import io
import zipfile
###import re
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from django.http import HttpResponse, JsonResponse


def inipec_export_excel(request):
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
    response['Content-Disposition'] = 'attachment; filename=EsitoDomiciliDigitaliAziende.xlsx'
    return response


def inipec_singola(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inipec_singolo
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            bearer, tok_id_bearer = registro_imprese_get_bearer()
            correttezza_cf_azienda = verifica_cf_azienda(cf)
            if correttezza_cf_azienda == 1:
                elenco_dati_registro, status_code, purp_id, tok_id = registro_imprese_verifica_utente(cf, bearer, tok_id_bearer)
                if elenco_dati_registro:
                    dd = elenco_dati_registro.get('blocchi_impresa').get('dati_identificativi').get('indirizzo_posta_certificata')
                else:
                    dd="Ditta non presente nel Registro Imprese"
                data.append(dd.lower())
                data = converti_data(data)
                salva_log(request.user, "Verifica INI-PEC singolo", "Verificato domicilio impresa " + cf, purposeid=purp_id, resp_status=status_code, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica INI-PEC singolo", "Verificato domicilio impresa " + cf)
            return render(request, 'inipec_singola.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inipec_singola.html', { 'utente_abilitato': utente_abilitato })


def _riga_inipec(request, cf, stato=None):
    """Una riga dell'INI-PEC massiva: `(righe, ultimo, errore)`, e `righe` e' una stringa sola.

    La forma `CF esito PEC` la legge il template con `row.split` e la riscrive l'export Excel.
    Il bearer e' quello in `stato`: uno per file, come nel giro vecchio (`agid.voucher`
    rinegozia a ogni chiamata, richiamarlo per riga vorrebbe dire un voucher per riga).
    `ultimo` e' il codice chiesto e non la PEC trovata: la card dice su quale codice sei
    fermo, la PEC la dice la tabella a giro finito.
    """
    if len(cf) in (8, 9, 10):
        cf = cf.zfill(11)          # le partite IVA corte: l'INI-PEC le vuole a 11 cifre
    esito = verifica_cf_azienda(cf)
    if esito != 1:
        return [f"{cf} {esito} Codice fiscale non corretto"], cf, 'Codice fiscale non corretto'
    bearer, tok_id = (stato or {}).get('token') or registro_imprese_get_bearer()
    dati, resp_status, purp_id, tok_id = registro_imprese_verifica_utente(cf, bearer, tok_id)
    salva_log(request.user, "Verifica INI-PEC massivo", "Verificato CF " + cf,
              purposeid=purp_id, resp_status=resp_status, token_id=tok_id)
    identificativi = _diz(_diz(_diz(dati).get('blocchi_impresa')).get('dati_identificativi'))
    pec = str(identificativi.get('indirizzo_posta_certificata')
              or "Ditta non presente nel Registro Imprese").lower()
    return [f"{cf} 1 {pec}"], cf, ''


def _fine_inipec(request, fatte):
    salva_log(request.user, "Verifica INI-PEC massivo", f"Fine caricamento file: codici n. {fatte}")


def inipec_massiva(request):
    """INI-PEC massiva: CSV/XLSX in colonna (A), un domicilio PEC per partita IVA.

    Il giro dei codici lo comanda il navigatore (`inipec_massiva_riga`), cosi' la card
    dell'overlay dice il vero avanzamento; senza JavaScript `esegui_tutto` fa un giro solo con
    lo stesso worker. Il voucher si minta qui e resta in sessione: e' uno per file, non uno
    per riga.
    """
    contesto = {'utente_abilitato': False}
    if not request.user.id:
        return render(request, 'inipec_massiva.html', contesto)
    contesto['utente_abilitato'] = bool(UtentiParametri.objects.get(id=request.user.id).inipec_massivo)

    if request.method != 'POST':
        if request.GET.get('eseguito'):
            # il navigatore torna qui quando ha finito i giri: la tabella la rende il server
            contesto['data'] = request.session.get(RIGHE_SESSIONE, [])
        return render(request, 'inipec_massiva.html', contesto)

    # Invariante 1: il gate va riverificato nel POST, un segnalibro non basta
    if not contesto['utente_abilitato']:
        contesto['error'] = "L'utente non è abilitato all'utilizzo di questo servizio"
        return render(request, 'inipec_massiva.html', contesto)

    if 'cf_csv' not in request.FILES:
        contesto['error'] = ("Il file non è arrivato: riselezionarlo o trascinarlo di nuovo "
                             "nella zona di caricamento.")
        return render(request, 'inipec_massiva.html', contesto)

    codici, errore = _legge_cf(request.FILES['cf_csv'])
    if errore:
        salva_log(request.user, "Verifica INI-PEC massivo", errore)
        contesto['error'] = errore
        return render(request, 'inipec_massiva.html', contesto)
    if not codici:
        contesto['error'] = 'Nessun codice nel file: la colonna (A) deve contenere i codici fiscali o le partite IVA.'
        return render(request, 'inipec_massiva.html', contesto)

    if request.POST.get('js'):
        avanzamento.avvia(request, codici, registro_imprese_get_bearer())
        contesto['totale'] = len(codici)
    else:
        # senza JavaScript: un giro solo, un voucher solo
        contesto['data'] = avanzamento.esegui_tutto(
            request, codici, _riga_inipec, _fine_inipec,
            stato={'token': registro_imprese_get_bearer()})
    return render(request, 'inipec_massiva.html', contesto)


def inipec_massiva_riga(request):
    """Una riga dell'INI-PEC massiva in corso: il POST porta l'indice, la lista sta in sessione."""
    return avanzamento.risposta_riga(request, 'inipec_massivo', _riga_inipec, _fine_inipec)


def registro_imprese_get_bearer():
    """(voucher, token_id) verso l'autority di Registro Imprese; ('', None) se non risponde.
    Client unico in OpenMSP/agid.py; il traffico e' congelato in OpenMSP/tests.py."""
    return agid.voucher(RegistroImpreseParametri.objects.get(id=1))


def registro_imprese(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.registro_imprese
        if request.method == 'POST':
            testi_registro = [
                ('c_fonte', 'Codice fonte'),
                ('fonte', 'Fonte'),
                ('descrizione_tipo_impresa', 'Tipo Impresa'),
                ('tipo_soggetto', 'Tipo soggetto'),
                ('descrizione_tipo_soggetto', 'Descrizione tipo soggetto'),
                ('tipo_impresa', 'Tipo impresa'),
                ('c_causale_cess', 'Codice causale cessazione/cancellazione'),
                ('dt_iscrizione_ri', 'Data di iscrizione al Registro Imprese'),
                ('dt_iscrizione_rea', 'Data di iscrizione al REA'),
                ('dt_atto_costituzione', 'Data atto di costituzione della società'),
                ('dt_costituzione', 'Data di costituzione dell\'impresa individuale'),
                ('dt_cancellazione', 'Data di cancellazione dal Registro Imprese'),
                ('dt_cessazione', 'Data di cessazione'),
                ('causale_cess', 'Codice causale cessazione/cancellazione'),
                ('denominazione', 'Denominazione dell\'impresa'),
                ('c_fiscale', 'Codice fiscale dell\'impresa'),
                ('partita_iva', 'Partita IVA'),
                ('cciaa', 'Camera di Commercio di iscrizione dell\'impresa'),
                ('n_rea', 'Numero REA dell\'impresa se iscritta al R.I.'),
                ('n_rd', 'Numero Registro Ditte se la ditta è del Registro Ditte'),
                ('stato_impresa', 'Stato impresa'),
                ('indirizzo_posta_certificata', 'Domicilio digitale'),
                ('stato_ditta', 'Stato impresa'),
                ('c_codifica', 'Codifica'),
                ('codifica', 'Tipo Classificazione'),
                ('classificazioni_ateco', 'Classificazioni_ATECO'),
                ('c_importanza', 'Codice_importanza'),
                ('importanza', 'Importanza'),
                ('forma_giuridica', 'Forma_giuridica'),
                ('indirizzo_localizzazione', 'Indirizzo'),
                ('dt_inizio_attivita_impresa', 'Data inizio attività'),
                ('dt_inizio', 'Data inizio attività'),
                ('attivita', 'Attività'),
                ('c_attivita', 'Codice attività'),
                ('c_stato', 'Indicatore stato dell\'attività: I (Inattiva), S (Sospesa)'),
                ('stato', 'Descrizione attributo precedente'),
                ('attivita_prevalente', 'Descrizione dell\'attività prevalente'),
                ('attivita_esercitata', 'Descrizione dell\'attività esercitata'),
                ('attivita_secondaria_esercitata', 'Descrizione attività secondaria esercitata'),
                ('f_presenza_pco_s', 'Presenza di procedure concorsuali in corso o pregresse'),
                ('dt_soci_titolari_al', 'Data di estrazione della visura CAD'),
                ('f_consorzio', 'Elenco di consorziati'),
                ('capitale_sociale', 'Capitale sociale'),
                ('c_valuta', 'Codice valuta'),
                ('valuta', 'Valuta'),
                ('deliberato', 'Deliberato'),
                ('ammontare', 'Ammontare'),
                ('sottoscritto', 'Sottoscritto'),
                ('versato', 'Versato'),
                ('sistema_amministrazione', 'Sistema ammistrazione'),
                ('forme_amministrative', 'Forma di amministrazione'),
                ('soggetto_controllo_contabile', 'Soggetto con controllo stabile'),
                ('collegio_sindacale', 'Collegio sindacale'),
                ('dt_termine', 'Data termine'),
                ('scadenza_esercizi', 'Scadenza esercizi'),
                ('dt_primo_esercizio', 'Data primo esercizio'),
                ('esercizi_successivi', 'Esercizi successivi'),
                ('giorni_proroga_bilancio', 'Giorni di proroga bilancio'),
                ('riquadro', 'Riquadro'),
                ('composizione_quote', 'Composizione quote'),
                ('titolari', 'Titolari'),
                ('titolare', 'Titolare'),
                ('anagrafica_titolare', 'Anagrafica titolare'),
                ('cognome', 'Cognome'),
                ('nome', 'Nome'),
                ('diritto_partecipazione', 'Diritto partecipazione'),
                ('tipo', 'Tipo'),
                ('c_tipo', 'Codice tipo'),
                ('Codice_importanza', 'Codice importanza'),
                ('ruolo_ridotto', 'Ruolo ridotto'),
                ('c_ente_rilascio','Codice ente rilascio'),
                ('ente_rilascio','Ente rilascui'),
                ('data','Data'),
                ('atti_conferimento_cariche', ''),
                ('atto_conferimento_cariche', ''),
                ('cariche', 'Cariche'),
                ('carica', 'Carica'),
                ('c_carica', 'Codice carica'),
                ('poteri_persona', 'Poteri persona'),
                ('p_poteri', 'Codice potere'),
                ('text', 'Testo'),
                ('persona_fisica', 'Persona fisica'),
                ('progressivo', 'Progressivo'),
                ('dt','Data'),
                ('estremi_nascita','Estremi di nascita'),
                ('frazione_numeratore','Frazione numeratore'),
                ('frazione_denominatore','Frazione denominatore'),
                ('valore_nominale', 'Valore nominale'),
                ('f_rappresentante_ri','f_rappresentante_ri'),
                ('dt_apertura','Data apertura'),
                ('comune','Comune'),
                ('provincia','Provincia'),
                ('toponimo','Toponimo'),
                ('cap','CAP'),
                ('Classificazioni_ATECO','Classificazioni ATECO'),
                ('Codice_importanza','Codice importanza'),
                ]
            data = []
            dati_identificativi = ""
            info_attivita = ""
            albi_ruoli_licenze_ridotti = ""
            persone_sede = ""
            localizzazioni = ""
            elenco_soci = ""
            info_statuto = ""
            amministrazione_controllo = ""
            info_patrimoniali_finanziarie = ""
            scritta_pco_s = ""

            cf = request.POST.get('input_CF')
            data.append(cf)
            bearer, tok_id_bearer = registro_imprese_get_bearer()
            correttezza_cf_azienda = verifica_cf_azienda(cf)
            if correttezza_cf_azienda == 1:
                elenco_dati_registro_temp, status_code, purp_id, tok_id = registro_imprese_verifica_utente(cf, bearer, tok_id_bearer)
                if elenco_dati_registro_temp :
                    elenco_dati_registro = sostituisci_chiavi(elenco_dati_registro_temp, testi_registro)
                    elenco_dati_registro = converti_data(elenco_dati_registro)
                    data.append(elenco_dati_registro)
                    if 'dati_identificativi' in elenco_dati_registro['blocchi_impresa'] :
                        dati_identificativi = elenco_dati_registro['blocchi_impresa']['dati_identificativi']
                    if 'info_attivita' in elenco_dati_registro['blocchi_impresa'] :
                        info_attivita = elenco_dati_registro['blocchi_impresa']['info_attivita']
                    if 'albi_ruoli_licenze_ridotti' in elenco_dati_registro['blocchi_impresa'] :
                        albi_ruoli_licenze_ridotti = elenco_dati_registro['blocchi_impresa']['albi_ruoli_licenze_ridotti']
                    if 'persone_sede' in elenco_dati_registro['blocchi_impresa'] :
                        persone_sede = elenco_dati_registro['blocchi_impresa']['persone_sede']
                    if 'localizzazioni' in elenco_dati_registro['blocchi_impresa'] :
                        localizzazioni = elenco_dati_registro['blocchi_impresa']['localizzazioni']
                    if 'elenco_soci' in elenco_dati_registro['blocchi_impresa'] :
                        elenco_soci = elenco_dati_registro['blocchi_impresa']['elenco_soci']
                    if 'info_statuto' in elenco_dati_registro['blocchi_impresa'] :
                        info_statuto = elenco_dati_registro['blocchi_impresa']['info_statuto']
                    if 'amministrazione_controllo' in elenco_dati_registro['blocchi_impresa'] :
                        amministrazione_controllo = elenco_dati_registro['blocchi_impresa']['amministrazione_controllo']
                    if 'info_patrimoniali_finanziarie' in elenco_dati_registro['blocchi_impresa'] :
                        info_patrimoniali_finanziarie = elenco_dati_registro['blocchi_impresa']['info_patrimoniali_finanziarie']
                    if 'scritta_pco_s' in elenco_dati_registro['blocchi_impresa'] :
                        scritta_pco_s = elenco_dati_registro['blocchi_impresa']['scritta_pco_s']
                    salva_log(request.user, "Verifica Registro Imprese", "Verificato azienda " + cf, purposeid=purp_id, resp_status=status_code, token_id=tok_id)
                else:
                    data.append("Ditta non presente")
                    salva_log(request.user, "Verifica Registro Imprese", "Verificato azienda " + cf, purposeid=purp_id, resp_status=status_code, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica Registro Imprese", "Verificato azienda " + cf)
            return render(request, 'registro_imprese.html', {'data': data, 'dati_identificativi' : dati_identificativi, 'info_attivita' : info_attivita, 'albi_ruoli_licenze_ridotti' : albi_ruoli_licenze_ridotti, 'persone_sede' : persone_sede, 'localizzazioni' : localizzazioni, 'elenco_soci' : elenco_soci, 'info_statuto' : info_statuto, 'amministrazione_controllo' : amministrazione_controllo, 'info_patrimoniali_finanziarie' : info_patrimoniali_finanziarie, 'scritta_pco_s' : scritta_pco_s, 'utente_abilitato': utente_abilitato })

    else:
        utente_abilitato = False

    return render(request, 'registro_imprese.html', { 'utente_abilitato': utente_abilitato })


def registro_imprese_verifica_utente(cf, bearer, token_id):
    registro_imprese_parametri = RegistroImpreseParametri.objects.get(id=1)
    purposeid = registro_imprese_parametri.purposeid
    url = registro_imprese_parametri.target + '/dettaglio/codicefiscale' ####da vedere
    #### /ricerca/codicefiscale
    #### /dettaglio/codicefiscale

    headers = {
        "Authorization": f"Bearer {bearer}"
        }
    params = {
        "codiceFiscale": cf
        }
    response = requests.get(url, headers=headers, params=params, timeout=30)
    status_code = response.status_code

    if response.status_code == 200:
        xml_data = response.content
        try:
            parsed_data = xmltodict.parse(xml_data)
        except ExpatError:
            # 200 con body malformato: stesso esito di una risposta errata, niente 500
            return False, status_code, purposeid, token_id
        modified_data = normalizza_chiavi(parsed_data)
        return modified_data, status_code, purposeid, token_id
    else:
        return False, status_code, purposeid, token_id


def sostituisci_chiavi(json_data, mapping_array):
    if isinstance(json_data, dict):
        new_dict = {}
        for chiave, valore in json_data.items():
            if isinstance(valore, dict):
                valore = sostituisci_chiavi(valore, mapping_array)
            elif isinstance(valore, list):
                valore = [sostituisci_chiavi(item, mapping_array) for item in valore]
            for item in mapping_array:
                if chiave == item[0]:
                    chiave = item[1]
                    break
            new_dict[chiave] = valore
        return new_dict
    elif isinstance(json_data, list):
        return [sostituisci_chiavi(item, mapping_array) for item in json_data]
    else:
        return json_data


def impostazioni_registro_imprese(request):
    parametri_registro_imprese = RegistroImpreseParametri.objects.all()
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

        dati = RegistroImpreseParametri(1, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
        dati.save()
        salva_log(request.user,"Impostazioni Registro Imprese", "modifica parametri")
    else:
        parametri_registro_imprese = RegistroImpreseParametri.objects.all()

    return render(request, 'impostazioni_registro_imprese.html', {'parametri_registro_imprese': parametri_registro_imprese})


MASSIMO_RIGHE = 100
STATO_SESSIONE = 'reg_imp_mass_stato'   # estrazione avviata dal navigatore, col token dentro  # shortcut: le risposte restano in sessione (SESSION_ENGINE su DB) e la
                     # riga di sessione la rileggi a ogni richiesta: sopra le ~100 visuri serve
                     # una tabella dedicata, vedi docs/2026-11-18-registro-imprese-massivo-design.md


def registro_imprese_interroga(cf, bearer, parametri):
    """GET di `dettaglio/codicefiscale` sul Registro Imprese: `(risposta grezza, testo JSON, stato)`.

    Diversa da `registro_imprese_verifica_utente` perche' qui la risposta serve due volte:
    normalizzata per la tabella e grezza per il file scaricabile. Il testo JSON e' la
    conversione della risposta (l'API risponde XML), con le chiavi dell'erogatore: le
    etichette italiane di `sostituisci_chiavi` restano un fatto dei template.
    """
    risposta = requests.get(parametri.target + '/dettaglio/codicefiscale',
                            headers={"Authorization": f"Bearer {bearer}"},
                            params={"codiceFiscale": cf}, timeout=30)
    if risposta.status_code != 200:
        return None, '', risposta.status_code
    try:
        dati = xmltodict.parse(risposta.content)
    except ExpatError:
        # 200 con body vuoto o malformato: per la pagina singola e' gia' "Ditta non presente"
        return None, '', risposta.status_code
    if not isinstance(dati, dict):
        return None, '', risposta.status_code
    return dati, json.dumps(dati, ensure_ascii=False, separators=(',', ':')), risposta.status_code


def _diz(dato):
    return dato if isinstance(dato, dict) else {}


def _riga_massiva(cf, bearer, parametri):
    """Una riga della ricerca massiva, gia' vestita per il template.

    `classe` la decide qui e il template la stampa: nei template di questo progetto non si
    puo' mettere un `{% if %}` dentro un tag di apertura.
    """
    riga = {'cf': cf, 'esito': '', 'denominazione': '', 'rea': '',
            'json': '', 'errore': '', 'classe': 'table-warning', 'status': None}
    if verifica_cf_azienda(cf) != 1:
        riga['esito'] = 'CF/PVA non valido'
        riga['errore'] = riga['esito']
        riga['classe'] = 'table-danger'
        return riga

    dati, testo, stato = registro_imprese_interroga(cf, bearer, parametri)
    riga['status'] = stato
    if dati is None:
        riga['esito'] = 'Ditta non presente' if stato == 200 else f'HTTP {stato}'
        riga['errore'] = riga['esito']
        if stato != 200:
            riga['classe'] = 'table-danger'
        return riga

    identificativi = _diz(_diz(normalizza_chiavi(dati).get('blocchi_impresa'))
                          .get('dati_identificativi'))
    riga['denominazione'] = str(identificativi.get('denominazione', '') or '')
    riga['rea'] = str(identificativi.get('n_rea', '') or '')
    riga['esito'] = 'OK'
    riga['json'] = testo
    riga['classe'] = 'table-success'
    return riga


def registro_imprese_massivo(request):
    """Estrazione massiva del Registro Imprese: CSV/XLSX in colonna (A), una visura per codice.

    Un voucher per tutto il file (`agid.SCADENZA_MINUTI` e' 43200, quindi non scade durante
    l'estrazione) e un giro di chiamata per riga, nello stesso ordine del file. Le righe
    finiscono in sessione con dentro il JSON di risposta: e' l'unica copia di quella risposta,
    e il pulsante di download serve quella, non una visura rivuta piu' tardi.
    """
    contesto = {'utente_abilitato': False}
    if not request.user.id:
        return render(request, 'registro_imprese_massivo.html', contesto)

    utente_sessione = UtentiParametri.objects.get(id=request.user.id)
    contesto['utente_abilitato'] = bool(utente_sessione.registro_imprese_massivo)

    if request.method != 'POST':
        if request.GET.get('eseguito'):
            # il navigatore torna qui quando ha finito i giri: la tabella la rende il server
            contesto['data'] = request.session.get('reg_imp_mass', [])
        return render(request, 'registro_imprese_massivo.html', contesto)

    # Invariante 1: il gate va riverificato nel POST, un linkKnown non basta
    if not contesto['utente_abilitato']:
        contesto['error'] = "L'utente non è abilitato all'utilizzo di questo servizio"
        return render(request, 'registro_imprese_massivo.html', contesto)

    if 'cf_csv' not in request.FILES:
        # Un POST senza file e' un errore detto, non la pagina iniziale: senza questa riga la
        # pagina sembra "non fa niente" e l'operatore non sa di non aver caricato niente.
        contesto['error'] = ("Il file non è arrivato: riselezionarlo o trascinarlo di nuovo "
                             "nella zona di caricamento.")
        return render(request, 'registro_imprese_massivo.html', contesto)

    cf_lista, errore = _legge_cf(request.FILES['cf_csv'])
    if errore:
        salva_log(request.user, "Verifica Registro Imprese massivo", errore)
        contesto['error'] = errore
        return render(request, 'registro_imprese_massivo.html', contesto)
    if not cf_lista:
        contesto['error'] = 'Nessun codice nel file: la colonna (A) deve contenere i codici fiscali o le partite IVA.'
        return render(request, 'registro_imprese_massivo.html', contesto)
    if len(cf_lista) > MASSIMO_RIGHE:
        contesto['error'] = (f"Il file porta {len(cf_lista)} codici, il massimo per una sola "
                            f"estrazione e' {MASSIMO_RIGHE}: dividere il file.")
        return render(request, 'registro_imprese_massivo.html', contesto)

    if request.POST.get('js'):
        # Il navigatore gira i codici uno a uno (`registro_imprese_massivo_riga`), cosi' la
        # card dell'avanzamento dice il vero. Il token si minta qui e resta in sessione:
        # `agid.voucher` rinegozia a ogni chiamata, richiamarlo per riga vorrebbe dire un
        # voucher per riga. E' un segreto in meno di quelli che il progetto gia' tiene in
        # chiaro nelle tabelle `*_parametri`, e vive quanto la sessione.
        request.session[STATO_SESSIONE] = {
            'cf': cf_lista, 'token': registro_imprese_get_bearer(), 'fatti': 0}
        contesto['totale'] = len(cf_lista)
        return render(request, 'registro_imprese_massivo.html', contesto)

    contesto['data'] = _esegui_tutto(request, cf_lista)      # senza JavaScript: un giro solo
    return render(request, 'registro_imprese_massivo.html', contesto)


def _esegui_tutto(request, cf_lista):
    """Tutta l'estrazione in un giro solo: il cammino senza JavaScript.

    Stesso corpo e stessi log di `registro_imprese_massivo_riga`: le due strade non sono
    due implementazioni della stessa cosa.
    """
    parametri = RegistroImpreseParametri.objects.get(id=1)
    bearer, tok_id = registro_imprese_get_bearer()
    righe = []
    esatte = 0
    for indice, cf in enumerate(cf_lista, 1):
        riga = _riga_massiva(cf, bearer, parametri)
        salva_log(request.user, "Verifica Registro Imprese massivo", "Verificato azienda " + cf,
                  purposeid=parametri.purposeid, resp_status=riga['status'], token_id=tok_id)
        if riga['json']:
            esatte += 1
        riga['indice'] = indice          # l'URL del download, cosi' il CF non sta nell'URL
        riga.pop('status')               # serve al log, non alla pagina ne' alla sessione
        righe.append(riga)

    request.session['reg_imp_mass'] = righe        # una scrittura sola
    salva_log(request.user, "Verifica Registro Imprese massivo",
              f"Fine caricamento file: righe n. {len(righe)}, risposte n. {esatte}")
    return righe


def _riga_in_sessione(request, riga, totale):
    """Accoda la riga all'estrazione in corso: ritorna `(finito, righe_fatte)`.

    La riga si sostituisce per indice, non si accoda a ogni costo: se il navigatore riprova
    la stessa riga dopo un filo caduto, la sessione non si riempie di duplicati.
    """
    righe = [r for r in request.session.get('reg_imp_mass', [])
             if r.get('indice') != riga['indice']]
    righe.append(riga)
    righe.sort(key=lambda r: r.get('indice', 0))
    request.session['reg_imp_mass'] = righe
    fatti = len(righe)
    finito = fatti >= totale
    stato = request.session.get(STATO_SESSIONE) or {}
    stato['fatti'] = fatti
    if finito:
        request.session.pop(STATO_SESSIONE)     # il token non resta in giro piu' del necessario
        esatte = sum(1 for r in righe if r.get('json'))
        salva_log(request.user, "Verifica Registro Imprese massivo",
                  f"Fine caricamento file: righe n. {fatti}, risposte n. {esatte}")
    else:
        request.session[STATO_SESSIONE] = stato
    return finito, fatti


def registro_imprese_massivo_riga(request):
    """Una riga dell'estrazione in corso: il POST porta l'indice, la lista sta in sessione.

    Il codice fiscale non viene mai dal client, e non ci torna nemmeno nel JSON: stessa
    ragione dei download, un segnalibro non deve poter portare via un codice.
    """
    if request.method != 'POST':
        return JsonResponse({'errore': 'Serve una POST'}, status=405)
    negato = _negato_massivo(request)
    if negato is not None:
        return negato
    stato = request.session.get(STATO_SESSIONE)
    if not stato:
        return JsonResponse({'errore': 'Nessuna estrazione in corso'}, status=400)
    try:
        indice = int(json.loads(request.body).get('indice', 0))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'errore': 'Indice non valido'}, status=400)
    cf_lista = stato['cf']
    if not 1 <= indice <= len(cf_lista):
        return JsonResponse({'errore': 'Indice fuori lista'}, status=400)

    parametri = RegistroImpreseParametri.objects.get(id=1)
    bearer, tok_id = stato['token']
    cf = cf_lista[indice - 1]
    riga = _riga_massiva(cf, bearer, parametri)
    salva_log(request.user, "Verifica Registro Imprese massivo", "Verificato azienda " + cf,
              purposeid=parametri.purposeid, resp_status=riga['status'], token_id=tok_id)
    riga['indice'] = indice
    riga.pop('status')
    finito, fatti = _riga_in_sessione(request, riga, len(cf_lista))
    return JsonResponse({'avanzamento': f"{fatti}/{len(cf_lista)}",
                         'denominazione': riga['denominazione'], 'rea': riga['rea'],
                         'esito': riga['esito'], 'errore': riga['errore'], 'fatto': finito})


def _riga_da_sessione(request, indice):
    """Riga dell'ultima estrazione massiva dall'indice nell'URL, vuota se non nota.

    Il CF non viene mai dall'URL: finirebbe in un Content-Disposition scritto a mano, e qui
    sta gia' in sessione insieme all'indice (stessa ragione di `inps._riga_durc`).
    """
    righe = request.session.get('reg_imp_mass', [])
    if isinstance(indice, int) and 1 <= indice <= len(righe):
        return righe[indice - 1]
    return {}


def _nome_json(riga):
    """`<CF>_<denominazione>.json`: prima il codice, poi la ditta, poi l'estensione.

    La denominazione viene dall'erogatore, percio' passa dal sanificatore dei PDF DURC: un
    `/` o un `"` nel nome vorrebbe dire un file fuori dalla cartella o un Content-Disposition
    spezzato. Senza denominazione (impresa individuale, o risposta senza il blocco) resta il
    solo CF: e' gia' un nome, e 'CF_.json' no.
    """
    ditta = _nome_file_denominazione(riga.get('denominazione', ''))
    cf = riga.get('cf', '')
    return f"{cf}_{ditta}.json" if ditta else f"{cf}.json"


def _nome_unico(nomi, nome):
    """Nome dentro lo ZIP, con il suffisso `-2` quando serve.

    Il CF e' gia' nel nome, ma lo stesso codice puo' essere nel file due volte: due risposte
    con lo stesso nome sarebbero una risposta persa in silenzio.
    """
    contatore = nomi.get(nome, 0) + 1
    nomi[nome] = contatore
    return nome if contatore == 1 else f"{nome[:-5]}-{contatore}.json"


def _zip_dei_json(righe):
    """ZIP dei JSON di un'estrazione: ritorna `(bytes, errori)`.

    Una riga senza risposta non e' un file vuoto dentro lo ZIP ma una riga di `errori.txt`,
    e l'assert finale e' la prova che ogni riga richiesta ci e' finita in un modo o nell'altro.
    """
    output = io.BytesIO()
    errori = []
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archivio:
        nomi = {}
        for riga in righe:
            if riga.get('json'):
                archivio.writestr(_nome_unico(nomi, _nome_json(riga)), riga['json'])
            else:
                errori.append(f"{riga.get('indice', '?')}. {riga.get('cf', '')}: "
                              f"{riga.get('errore') or 'nessuna risposta'}")
        if errori:
            archivio.writestr('errori.txt', '\n'.join(errori))
        assert (sum(1 for nome in archivio.namelist() if nome.endswith('.json'))
                + len(errori) == len(righe))
    return output.getvalue(), errori


def _negato_massivo(request):
    """Risposta 403 se il doppio gate non regge, `None` se si puo' procedere.

    Anche le due rotte di download si riverificano il permesso (invariante 1): un linkKnown
    o un segnalibro non devono bastare a chi non ha piu' il flag.
    """
    if not request.user.id:
        return HttpResponse("Utente non autenticato", status=403)
    if not UtentiParametri.objects.get(id=request.user.id).registro_imprese_massivo:
        return HttpResponse("Utente non abilitato", status=403)
    return None


def registro_imprese_massivo_json(request, riga):
    """Il JSON di risposta di una riga dell'ultima estrazione, cosi' com'era arrivato."""
    negato = _negato_massivo(request)
    if negato:
        return negato
    dati = _riga_da_sessione(request, riga)
    if not dati.get('json'):
        return HttpResponse("Nessun JSON da scaricare per questa riga", status=404)
    risposta = HttpResponse(dati['json'], content_type='application/json')
    # Il CF di questa riga e' passato da verifica_cf_azienda: nel Content-Disposition non
    # puo' finire altro che un codice benformato.
    # Il nome porta spazi (la denominazione e' cosi'): un valore nudo e' fuori RFC e qualche
    # browser lo taglia al primo spazio, percio' va tra le virgolette.
    risposta['Content-Disposition'] = f'attachment; filename="{_nome_json(dati)}"'
    return risposta


def registro_imprese_export_zip(request):
    """ZIP di tutti i JSON dell'ultima estrazione, con `errori.txt` per le righe senza risposta."""
    negato = _negato_massivo(request)
    if negato:
        return negato
    righe = request.session.get('reg_imp_mass', [])
    if not righe:
        return HttpResponse("Nessuna estrazione da scaricare", status=400)
    corpo, errori = _zip_dei_json(righe)
    salva_log(request.user, "Verifica Registro Imprese massivo",
              f"ZIP di {len(righe)} righe, {len(errori)} senza risposta")
    risposta = HttpResponse(corpo, content_type='application/zip')
    risposta['Content-Disposition'] = 'attachment; filename=RegistroImprese_Massiva.zip'
    return risposta
