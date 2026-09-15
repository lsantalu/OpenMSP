# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
from django.shortcuts import render, redirect

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import AnprServizi
from impostazioni.models import AnprParametri

from .utils import salva_log
from .utils import svuota_none
from .utils import converti_data
from .verifica_cf import verifica_cf

##from datetime import datetime, date
import datetime
from jose.constants import Algorithms

import http.client, urllib.parse
import hashlib
import random
import base64
import datetime
import io
import uuid
import jwt
import requests
import json
import re

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from django.http import HttpResponse



def anpr_get_request(user_ID, id_anpr, id_caso):
    parametri_anpr = AnprParametri.objects.get(id=id_caso)
    caso = ''
    if id_caso == 1:
        caso = "C001"
    elif id_caso == 2:
        caso = "C007"
    elif id_caso == 3:
        caso = "C015"
    elif id_caso == 4:
        caso = "C017"
    elif id_caso == 5:
        caso = "C018"
    elif id_caso == 6:
        caso = "C020"
    elif id_caso == 7:
        caso = "C021"
    else: ##Recupero idANPR
        caso = "C030"


    kid = parametri_anpr.kid
    alg = parametri_anpr.alg
    typ = parametri_anpr.typ
    issuer = parametri_anpr.iss
    subject = parametri_anpr.sub
    aud = parametri_anpr.aud
    purposeid = parametri_anpr.purposeid
    audience = parametri_anpr.audience
    baseurlauth = parametri_anpr.baseurlauth
    target = parametri_anpr.target
    clientid = parametri_anpr.clientid
    private_key = parametri_anpr.private_key
    userid = user_ID
    location = 'PortaleOpenMSP'
    loa = 'LoA2'
    if id_caso == 8: ##Recupero idANPR
        richiesta = f'{{"idOperazioneClient":"1","criteriRicerca":{{"codiceFiscale":"{id_anpr}"}},' \
            f'"datiRichiesta":{{"dataRiferimentoRichiesta":"{datetime.datetime.utcnow().strftime("%Y-%m-%d")}",' \
            f'"motivoRichiesta":"Verifica_anagrafica","casoUso":"{caso}"}}}}'
    else:
        richiesta = f'{{"idOperazioneClient":"1","criteriRicerca":{{"idANPR":"{id_anpr}"}},' \
            f'"datiRichiesta":{{"dataRiferimentoRichiesta":"{datetime.datetime.utcnow().strftime("%Y-%m-%d")}",' \
            f'"motivoRichiesta":"Verifica_anagrafica","casoUso":"{caso}"}}}}'

    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=43200)
    expire_in = issued + delta
    dnonce = random.randint(1000000000000, 9999999999999)

    headers_rsa = {
        "kid": kid,
        "alg": alg,
        "typ": typ
    }

    jti = uuid.uuid4()
    audit_payload = {
        "userID": userid,
        "userLocation": location,
        "LoA": loa,
        "iss" : clientid,
        "aud" : audience,
        "purposeId": purposeid,
        "dnonce" : dnonce,
        "jti":str(jti),
        "iat": issued,
        "nbf" : issued,
        "exp": expire_in
        }

    audit = jwt.encode(audit_payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)
    audit_hash = hashlib.sha256(audit.encode('UTF-8')).hexdigest()

    jti = uuid.uuid4()
    payload = {
        "iss": clientid,
        "sub": clientid,
        "aud": aud,
        "purposeId": purposeid,
        "jti": str(jti),
        "iat": issued,
        "exp": expire_in,
        "digest": {
            "alg": "SHA256",
            "value": audit_hash
            }
        }

    client_assertion = jwt.encode(payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)

    params = urllib.parse.urlencode({
        'client_id': clientid,
        'client_assertion': client_assertion,
        'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
        'grant_type': 'client_credentials'
        })

    headers = {"Content-type": "application/x-www-form-urlencoded"}
    conn = http.client.HTTPSConnection(re.sub(r'^https?://', '', baseurlauth))
    conn.request("POST", "/token.oauth2", params, headers)
    response = conn.getresponse()
    try:
        voucher = json.loads(response.read())["access_token"]
    except (ValueError, KeyError, TypeError):
        # authority di ANPR non utilizzabile: stesso sentinel usato per le risposte errate
        return 'ZZZZZZZZZ', 502, purposeid, None

    # prepara il body per la richiesta e relativo digest
    body = richiesta
    type = 'application/json'
    encoding = 'UTF-8'
    body_digest = hashlib.sha256(body.encode('UTF-8'))
    digest = 'SHA-256=' + base64.b64encode(body_digest.digest()).decode('UTF-8')

    # crea signature
    jti = uuid.uuid4()
    payload = {
        "iss" : clientid,
        "aud" : audience,
        "purposeId": purposeid,
        "sub": clientid,
        "jti": str(jti),
        "iat": issued,
        "nbf" : issued,
        "exp": expire_in,
        "signed_headers": [
            {"digest": digest},
            {"content-type": type},
            {"content-encoding": encoding}
            ]
        }
    signature = jwt.encode(payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)
    # effettua chiamata
    api_url = target
    headers =  {"Accept":"application/json",
                "Content-Type":type,
                "Content-Encoding":encoding,
                "Digest":digest,
                "Authorization":"Bearer " + voucher,
                "Agid-JWT-TrackingEvidence":audit,
                "Agid-JWT-Signature":signature
                }

    response = requests.post(api_url, data=body.encode('UTF-8'), headers=headers, verify=False, timeout=30)
    
    # Estrae il token_id dal voucher (jti)
    try:
        decoded_token = jwt.decode(voucher, options={"verify_signature": False})
        token_id = decoded_token.get('jti')
    except jwt.PyJWTError:
        token_id = None

    if id_caso == 8:
        aux = response.json()
        if 'listaSoggetti' in aux:
            return aux['listaSoggetti']['datiSoggetto'][0]['identificativi']['idANPR'], response.status_code, purposeid, token_id
        else:
            return 'ZZZZZZZZZ', response.status_code, purposeid, token_id
    else:
        return response.json(), response.status_code, purposeid, token_id

# Un caso d'uso per riga: id su AnprParametri, i due flag RBAC (singolo e massivo), il titolo
# della card e il nome di audit. Il nome di audit del massivo e' quello del singolo + " Massivo",
# come gia' fanno i domicili digitali e la pagina unificata dell'istruzione.
ANPR_SERVIZI = {
    'C001': {'id_caso': 1, 'label': 'C001 - Servizio notifica', 'titolo': 'Servizio notifica',
             'flag': 'anpr_C001', 'flag_massivo': 'anpr_C001_massivo',
             'log': 'Verifica ANPR - C001 - Notifica'},
    'C007': {'id_caso': 2, 'label': 'C007 - Esistenza in vita', 'titolo': 'Esistenza in vita',
             'flag': 'anpr_C007', 'flag_massivo': 'anpr_C007_massivo',
             'log': 'Verifica ANPR - C007 - Esistenza in vita'},
    'C015': {'id_caso': 3, 'label': 'C015 - Generalita', 'titolo': 'Generalità',
             'flag': 'anpr_C015', 'flag_massivo': 'anpr_C015_massivo',
             'log': 'Verifica ANPR - C015 - Generalità'},
    'C017': {'id_caso': 4, 'label': 'C017 - Matrimonio', 'titolo': 'Matrimonio',
             'flag': 'anpr_C017', 'flag_massivo': 'anpr_C017_massivo',
             'log': 'Verifica ANPR - C017 - Matrimonio'},
    'C018': {'id_caso': 5, 'label': 'C018 - Cittadinanza', 'titolo': 'Cittadinanza',
             'flag': 'anpr_C018', 'flag_massivo': 'anpr_C018_massivo',
             'log': 'Verifica ANPR - C018 - Cittadinanza'},
    'C020': {'id_caso': 6, 'label': 'C020 - Residenza', 'titolo': 'Residenza',
             'flag': 'anpr_C020', 'flag_massivo': 'anpr_C020_massivo',
             'log': 'Verifica ANPR - C020 - Residenza'},
    'C021': {'id_caso': 7, 'label': 'C021 - Stato di famiglia', 'titolo': 'Stato di famiglia',
             'flag': 'anpr_C021', 'flag_massivo': 'anpr_C021_massivo',
             'log': 'Verifica ANPR - C021 - Stato famiglia'},
}

# Unica copia della lista: prima era duplicata tra views.py e anpr.py
ANPR_PARENTELA = [
    ('1', 'Intestatario Scheda'), ('2', 'Marito / Moglie'), ('3', 'Figlio / Figlia'),
    ('4', 'Nipote (discendente)'), ('5', 'Pronipote (discendente)'), ('6', 'Padre / Madre'),
    ('7', 'Nonno / Nonna'), ('8', 'Bisnonno / Bisnonna'), ('9', 'Fratello / Sorella'),
    ('10', 'Nipote (collaterale)'), ('11', 'Zio / Zia (Collaterale)'), ('12', 'Cugino / Cugina'),
    ('13', 'Altro Parente'), ('14', 'Figliastro / Figliastra'), ('15', 'Patrigno / Matrigna'),
    ('16', 'Genero / Nuora'), ('17', 'Suocero / Suocera'), ('18', 'Cognato / Cognata'),
    ('19', 'Fratellastro / Sorellastra'), ('20', 'Nipote (Affine)'), ('21', 'Zio / Zia (Affine)'),
    ('22', 'Altro Affine'), ('23', 'Convivente (con vincoli di adozione o affettivi)'),
    ('24', 'Responsabile della convivenza non affettiva'), ('25', 'Convivente in convivenza non affettiva'),
    ('26', 'Tutore'), ('28', 'Unito civilmente'), ('80', 'Adottato'), ('81', 'Nipote'),
    ('99', 'Non definito/comunicato'),
]

ANPR_STATO_CIVILE = {
    '1': 'Celibe / Nubile', '2': 'Coniugato / Coniugata', '3': 'Vedovo / Vedova',
    '4': 'Divorziato / Divorziata', '6': 'Unito civilmente',
    '7': 'Stato libero per decesso della parte unita civilmente',
    '8': "Stato libero per scioglimento dell'unione",
}

# Stesse colonne a schermo e nell'export: la tabella della pagina massiva e il XLSX sono la
# stessa lista di liste, l'export rilegge session['multi_data'] e non deve knoware nient'altro.
ANPR_COLONNE = ['CF', 'Esito', 'Cognome', 'Nome', 'Sesso', 'Data nascita', 'Luogo nascita',
                'Comune di residenza', 'Provincia', 'Stato civile', 'Cittadinanza', 'AIRE',
                'Data decesso', 'Legame', 'idANPR']


def _piattino(soggetto):
    """generalita' + identificativi + infoSoggettoEnte in una mappa sola: l'ANPR ha reso in due
    forme (struttura annidata e lista chiave/valore) e chi legge non deve saperlo."""
    piatto = {}
    for fonte in (soggetto.get('generalita'), soggetto.get('identificativi')):
        for chiave, valore in (fonte or {}).items():
            if not isinstance(valore, (dict, list)) and valore not in (None, ''):
                piatto.setdefault(chiave, valore)
    informazioni = soggetto.get('infoSoggettoEnte') or []
    if isinstance(informazioni, dict):
        informazioni = [informazioni]
    for informazione in informazioni:
        if isinstance(informazione, dict):
            valore = (informazione.get('valoreTesto') or informazione.get('valoreData')
                      or informazione.get('valore'))
            if valore not in (None, ''):
                piatto.setdefault(informazione.get('chiave'), valore)
    return piatto


def _luogo_nascita(generalita):
    luogo = generalita.get('luogoNascita') or {}
    comune = luogo.get('comune') or {}
    if comune.get('nomeComune'):
        provincia = comune.get('siglaProvinciaIstat') or comune.get('stato') or ''
        return f"{comune['nomeComune']} ({provincia})" if provincia else comune['nomeComune']
    localita = luogo.get('localita') or {}
    if localita.get('descrizioneLocalita'):
        return f"{localita['descrizioneLocalita']} ({localita.get('descrizioneStato', '')})"
    return ''


def _residenza(soggetto):
    scheda = (soggetto.get('residenza') or [{}])[0]
    indirizzo = scheda.get('indirizzo') or {}
    comune = indirizzo.get('comune') or {}
    estera = ((scheda.get('localitaEstera') or {}).get('indirizzoEstero') or {})
    return (comune.get('nomeComune')
            or ((estera.get('localita') or {}).get('descrizioneLocalita'))
            or ((estera.get('toponimo') or {}).get('denominazione')) or '')


def anpr_righe(cf, risposta, esito_forzato=None):
    """Righe dell'interrogazione massiva, una per soggetto restituito (lo stato di famiglia ne
    rende piu' d'uno), gia' appiattite su ANPR_COLONNE. esito_forzato e' il messaggio per i CF
    scartati prima della chiamata o per l'ANSIA senza idANPR."""
    def riga(esito, soggetto=None):
        valori = dict.fromkeys(ANPR_COLONNE, '')
        valori['CF'], valori['Esito'] = cf, esito
        if soggetto:
            piatto = _piattino(soggetto)
            stato_civile = ((soggetto.get('statoCivile') or {}).get('statoCivile')
                            or piatto.get('statoCivile') or '')
            legame = ((soggetto.get('legameSoggetto') or {}).get('codiceLegame')
                      or piatto.get('codiceLegame') or '')
            aire = piatto.get('soggettoAIRE') or ''
            valori.update({
                'Cognome': piatto.get('cognome', ''), 'Nome': piatto.get('nome', ''),
                'Sesso': piatto.get('sesso', ''), 'Data nascita': piatto.get('dataNascita', ''),
                'Luogo nascita': _luogo_nascita(soggetto.get('generalita') or {})
                                 or piatto.get('comuneNascita', ''),
                'Comune di residenza': _residenza(soggetto) or piatto.get('comuneResidenza', ''),
                'Provincia': (((soggetto.get('residenza') or [{}])[0].get('indirizzo') or {})
                              .get('comune') or {}).get('siglaProvinciaIstat', ''),
                'Stato civile': ANPR_STATO_CIVILE.get(str(stato_civile), str(stato_civile)),
                'Cittadinanza': ((soggetto.get('cittadinanza') or [{}])[0]
                                 .get('descrizioneStato')) or piatto.get('cittadinanza', ''),
                'AIRE': {'S': 'Si', 'N': 'No'}.get(str(aire), str(aire)),
                'Data decesso': piatto.get('dataDecesso', ''),
                'Legame': dict(ANPR_PARENTELA).get(str(legame), str(legame)),
                'idANPR': piatto.get('idANPR', ''),
            })
        return [valori[colonna] for colonna in ANPR_COLONNE]

    if esito_forzato:
        return [riga(esito_forzato)]
    if not isinstance(risposta, dict):
        return [riga('Risposta non leggibile')]
    if risposta.get('listaErrori'):
        errori = risposta['listaErrori']
        testo = errori[0] if isinstance(errori, list) and errori else str(errori)
        return [riga(f"Nessun risultato: {str(testo)[:160]}")]
    soggetti = (risposta.get('listaSoggetti') or {}).get('datiSoggetto') or []
    if isinstance(soggetti, dict):
        soggetti = [soggetti]
    if not soggetti:
        return [riga('Nessun risultato: la richiesta non produce alcun soggetto')]
    return [riga('Trovato', soggetto) for soggetto in soggetti]


def anpr_export_excel(request):
    """XLSX dell'ultima estrazione massiva: legge session['multi_data'] come la pagina."""
    righe = request.session.get('multi_data') or []
    if not righe:
        return HttpResponse("Nessun dato disponibile per l'esportazione", status=400)

    wb = Workbook()
    ws = wb.worksheets[0]
    ws.append(ANPR_COLONNE)
    larghezze = [len(str(colonna)) for colonna in ANPR_COLONNE]

    for riga in righe:
        ws.append(list(riga))
        colore = 'C6EFCE' if str(riga[1]).startswith('Trovato') else 'FFC7CE'
        riempimento = PatternFill(start_color=colore, end_color=colore, fill_type='solid')
        # openpyxl: iter_rows al posto di ws[riga], che sui fogli in scrittura non e' indicizzabile
        for indice, cell in enumerate(next(ws.iter_rows(min_row=ws.max_row, max_row=ws.max_row))):
            cell.fill = riempimento
            larghezza = len(str(cell.value or ''))
            if len(larghezze) <= indice:
                larghezze.append(larghezza)
            else:
                larghezze[indice] = max(larghezze[indice], larghezza)

    for indice, larghezza in enumerate(larghezze, 1):
        ws.column_dimensions[get_column_letter(indice)].width = min(larghezza + 2, 60)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=EsitoAnprMassivo.xlsx'
    return response


def anpr_esistenza_in_vita(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C007
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                idANPR, status_id_anpr, purp_id_anpr, tok_id_anpr = anpr_get_request(request.user.username, cf, 8)
                res_data, status_final, purp_final, tok_final = anpr_get_request(request.user.username, idANPR, 2)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica ANPR - C007 - Esistenza in vita", "Verificato utente " + cf, purposeid=purp_final, resp_status=status_final, token_id=tok_final)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica ANPR - C007 - Esistenza in vita", "Verificato utente " + cf)
            return render(request, 'anpr_esistenza_in_vita.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_esistenza_in_vita.html', { 'utente_abilitato': utente_abilitato })


def anpr_cittadinanza(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C018
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                idANPR, status_id_anpr, purp_id_anpr, tok_id_anpr = anpr_get_request(request.user.username, cf, 8)
                res_data, status_final, purp_final, tok_final = anpr_get_request(request.user.username, idANPR, 5)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica ANPR - C018 - Cittadinanza", "Verificato utente " + cf, purposeid=purp_final, resp_status=status_final, token_id=tok_final)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica ANPR - C018 - Cittadinanza", "Verificato utente " + cf)
            return render(request, 'anpr_cittadinanza.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_cittadinanza.html', { 'utente_abilitato': utente_abilitato })


def anpr_generalita(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C015
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                idANPR, status_id_anpr, purp_id_anpr, tok_id_anpr = anpr_get_request(request.user.username, cf, 8)
                res_data, status_final, purp_final, tok_final = anpr_get_request(request.user.username, idANPR, 3)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica ANPR - C015 - Generalità", "Verificato utente " + cf, purposeid=purp_final, resp_status=status_final, token_id=tok_final)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica ANPR - C015 - Generalità", "Verificato utente " + cf)
            return render(request, 'anpr_generalita.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_generalita.html', { 'utente_abilitato': utente_abilitato })


def anpr_matrimonio(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C017
        if request.method == 'POST':
            cessazione_matrimonio_choices = [
                ('1', 'Cessazione effetti civili'),
                ('2', 'Annullamento'),
                ('3', 'Scioglimento'),
                ('4', 'Nullità'),
                ('5', 'Separazione'),
                ('6', 'Cessazione effetti civili - D.L. 12 settembre 2014'),
                ('7', 'Scioglimento D.L. 12 settembre 2014, n. 132'),
                ('8', 'Separazione - D.L. 12 settembre 2014, n. 132'),
                ('9', 'Delibazione (estero)'),
                ('10', 'Notaio (estero)'),
                ('22', 'Altro tipo di cessazione / scioglimento'),
            ]

            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                idANPR, status_id_anpr, purp_id_anpr, tok_id_anpr = anpr_get_request(request.user.username, cf, 8)
                res_data, status_final, purp_final, tok_final = anpr_get_request(request.user.username, idANPR, 4)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica ANPR - C017 - Matrimonio", "Verificato utente " + cf, purposeid=purp_final, resp_status=status_final, token_id=tok_final)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica ANPR - C017 - Matrimonio", "Verificato utente " + cf)
            return render(request, 'anpr_matrimonio.html', {'data': data, 'cessazione': cessazione_matrimonio_choices, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_matrimonio.html', { 'utente_abilitato': utente_abilitato })


def anpr_notifica(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C001
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                idANPR, status_id_anpr, purp_id_anpr, tok_id_anpr = anpr_get_request(request.user.username, cf, 8)
                res_data, status_final, purp_final, tok_final = anpr_get_request(request.user.username, idANPR, 1)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica ANPR - C001 - Notifica", "Verificato utente " + cf, purposeid=purp_final, resp_status=status_final, token_id=tok_final)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica ANPR - C001 - Notifica", "Verificato utente " + cf)
            return render(request, 'anpr_notifica.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_notifica.html', { 'utente_abilitato': utente_abilitato })


def anpr_residenza(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C020
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                idANPR, status_id_anpr, purp_id_anpr, tok_id_anpr = anpr_get_request(request.user.username, cf, 8)
                res_data, status_final, purp_final, tok_final = anpr_get_request(request.user.username, idANPR, 6)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica ANPR - C020 - Residenza", "Verificato utente " + cf, purposeid=purp_final, resp_status=status_final, token_id=tok_final)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica ANPR - C020 - Residenza", "Verificato utente " + cf)
            return render(request, 'anpr_residenza.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_residenza.html', { 'utente_abilitato': utente_abilitato })


def anpr_stato_famiglia(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C021
        if request.method == 'POST':
            parentela_choices = [
                ('1', 'Intestatario Scheda'),
                ('2', 'Marito / Moglie'),
                ('3', 'Figlio / Figlia'),
                ('4', 'Nipote (discendente)'),
                ('5', 'Pronipote (discendente)'),
                ('6', 'Padre / Madre'),
                ('7', 'Nonno / Nonna'),
                ('8', 'Bisnonno / Bisnonna'),
                ('9', 'Fratello / Sorella'),
                ('10', 'Nipote (collaterale)'),
                ('11', 'Zio / Zia (Collaterale)'),
                ('12', 'Cugino / Cugina'),
                ('13', 'Altro Parente'),
                ('14', 'Figliastro / Figliastra'),
                ('15', 'Patrigno / Matrigna'),
                ('16', 'Genero / Nuora'),
                ('17', 'Suocero / Suocera'),
                ('18', 'Cognato / Cognata'),
                ('19', 'Fratellastro / Sorellastra'),
                ('20', 'Nipote (Affine)'),
                ('21', 'Zio / Zia (Affine)'),
                ('22', 'Altro Affine'),
                ('23', 'Convivente (con vincoli di adozione o affettivi)'),
                ('24', 'Responsabile della convivenza non affettiva'),
                ('25', 'Convivente in convivenza non affettiva'),
                ('26', 'Tutore'),
                ('28', 'Unito civilmente'),
                ('80', 'Adottato'),
                ('81', 'Nipote'),
                ('99', 'Non definito/comunicato'),
            ]

            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                idANPR, status_id_anpr, purp_id_anpr, tok_id_anpr = anpr_get_request(request.user.username, cf, 8)
                res_data, status_final, purp_final, tok_final = anpr_get_request(request.user.username, idANPR, 7)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica ANPR - C021 - Stato famiglia", "Verificato utente " + cf, purposeid=purp_final, resp_status=status_final, token_id=tok_final)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica ANPR - C021 - Stato famiglia", "Verificato utente " + cf)
            return render(request, 'anpr_stato_famiglia.html', {'data': data, 'parentela':parentela_choices, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_stato_famiglia.html', { 'utente_abilitato': utente_abilitato })


def impostazioni_anpr(request):
    servizi_anpr = AnprServizi.objects.all()
    parametri_anpr = AnprParametri.objects.all()
    svuota_none(parametri_anpr)

    service_active = ServiziParametri.objects.all()
    i_serv=0
    service_desc = ["" for _ in range(ServiziParametri.objects.count())]
    for servizio in service_active:
        service_desc[i_serv]= (servizio.attivo)
        i_serv += 1

    if request.method == 'POST':
        active_tab = request.POST.get("active_tab", "").replace("tab", "")

        try:
            active_id = int(active_tab)
        except ValueError:
            active_id = None

        posizione_servizio = list(
            ServiziParametri.objects.filter(gruppo_id=2)
            .order_by('id')
            .values_list('attivo', flat=True)
        )

        ids_to_save = [active_id] if active_id else range(1, AnprParametri.objects.count() + 1)

        for i in ids_to_save:
            if i and i <= len(posizione_servizio) and posizione_servizio[i - 1]:
                kid = request.POST.get('kid' + str(i))
                alg = request.POST.get('alg' + str(i))
                typ = request.POST.get('typ' + str(i))
                iss = request.POST.get('iss' + str(i))
                sub = request.POST.get('sub' + str(i))
                aud = request.POST.get('aud' + str(i))
                purposeid = request.POST.get('purposeid' + str(i))
                audience = request.POST.get('audience' + str(i))
                baseurlauth = request.POST.get('baseurlauth' + str(i))
                target = request.POST.get('target' + str(i))
                clientid = request.POST.get('clientid' + str(i))
                private_key = request.POST.get('private_key' + str(i))
                ver_eservice = request.POST.get('ver_eservice' + str(i))

                dati = AnprParametri(i, i, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
                dati.save()
        salva_log(request.user,"Impostazioni ANPR", "modifica parametri")

        if active_id:
            return redirect(f"{request.path}#tab{active_id}")
        return redirect(request.path)

    return render(request, 'impostazioni_anpr.html', { 'servizi_anpr': servizi_anpr, 'parametri_anpr': parametri_anpr })
