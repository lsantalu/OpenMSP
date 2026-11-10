# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
import csv
import datetime
import io
import json
import re
import unicodedata
from itertools import zip_longest

import jwt
import requests
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import redirect, render
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from impostazioni.models import (
    AnncsuParametri,
    AnncsuServizi,
    DatiEnte,
    ServiziParametri,
    UtentiParametri,
)

from . import agid
from .utils import converti_data, normalizza_data, salva_log

# --- i cinque e-service ANNCSU -----------------------------------------------------------
# Unica fonte di verita' per gate, menu, card di home, impostazioni e route: il doppio gate
# (invariante 1) legge servizi_parametri.attivo (chiave `codice`) AND il flag dell'utente
# (chiave `flag`), e la riga di anncsu_parametri ha lo stesso id di anncsu_servizi.
# `implementato` vale False solo per la Visura: per i restanti tre la specifica c'e' (docs/)
# e il client e' scritto qui sotto; la Visura resta lo stub `anncsu_non_attivo`.
ANNCSU_SERVIZI = (
    {'id': 1, 'codice': 'anncsu', 'flag': 'anncsu_consultazione_comuni', 'url': 'anncsu',
     'etichetta': 'Consultazione per i COMUNI', 'tab': 'tab1', 'implementato': True},
    {'id': 2, 'codice': 'anncsu_accessi', 'flag': 'anncsu_accessi', 'url': 'anncsu_accessi',
     'etichetta': 'Aggiornamento accessi', 'tab': 'tab2', 'implementato': True},
    {'id': 3, 'codice': 'anncsu_coordinate', 'flag': 'anncsu_coordinate', 'url': 'anncsu_coordinate',
     'etichetta': 'Aggiornamento coordinate', 'tab': 'tab3', 'implementato': True},
    {'id': 4, 'codice': 'anncsu_odonimi', 'flag': 'anncsu_odonimi', 'url': 'anncsu_odonimi',
     'etichetta': 'Aggiornamento odonimi', 'tab': 'tab4', 'implementato': True},
    {'id': 5, 'codice': 'anncsu_visura', 'flag': 'anncsu_visura', 'url': 'anncsu_visura',
     'etichetta': 'Estratto di mappa per Visura', 'tab': 'tab5', 'implementato': False},
)

ANNCSU_PER_URL = {servizio['url']: servizio for servizio in ANNCSU_SERVIZI}
ANNCSU_CONSULTAZIONE = ANNCSU_PER_URL['anncsu']


# --- cosa offre l'e-service -------------------------------------------------------------
# Le 8 operazioni di ANNCSU - Consultazione, nell'ordine della guida tecnica (docs/
# ANNCSU_Consultazione.pdf, §2). `campi` sono le chiavi di ANNCSU_CAMPI e, insieme a `req`,
# sono anche il body della POST: non serve una mappatura separata.
# `esito` dice che forma ha la risposta: 'bool' (data vero/falso) o una chiave di
# ANNCSU_COLONNE. `descrizione` e` usata nella tabella della pagina e nel radiogruppo.
_CODCOM = r'^[A-Z0-9]{4}$'
_TESTO = r"^[A-Z0-9À-ſ .,'&/()-]{1,100}$"
_VALORE = r"^[A-Z0-9 .,'&/()-]{1,20}$"
_NUMERO = r'^[0-9]{1,12}$'

ANNCSU_CAMPI = {
    'codcom': {'etichetta': 'Comune', 'maxlength': 4, 'lookup': 'comuni',
               'hint': 'Nome del comune o codice Belfiore, es. Roma o H501', 'pattern': _CODCOM},
    'denom': {'etichetta': 'Denominazione completa dell\'odonimo', 'maxlength': 100,
              'hint': 'Es. VIA MARIO CARUCCI',
              'pattern': _TESTO},
    'denomparz': {'etichetta': 'Denominazione dell\'odonimo, anche parziale', 'maxlength': 100,
                  'hint': 'Es. VIA MARIO CAR', 'pattern': _TESTO},
    'accesso': {'etichetta': 'Civico o metrico, con eventuali esponente e specificità',
                'maxlength': 20, 'hint': 'Valore completo, es. 85 oppure 85-A-ROSSO',
                'pattern': _VALORE},
    'accparz': {'etichetta': 'Civico o metrico, anche parziale', 'maxlength': 20,
                'hint': 'Es. 9 (valori parziali)', 'pattern': _VALORE},
    'prognaz': {'etichetta': 'Progressivo nazionale dell\'area di circolazione', 'maxlength': 12,
                'hint': 'Solo cifre, es. 917092', 'pattern': _NUMERO},
    'prognazacc': {'etichetta': 'Progressivo nazionale dell\'accesso', 'maxlength': 12,
                   'hint': 'Solo cifre, es. 33051027', 'pattern': _NUMERO},
}

ANNCSU_OPERAZIONI = {
    'esisteodonimo': {'titolo': 'Esistenza di un odonimo', 'esito': 'bool',
                      'descrizione': 'Esistenza di un odonimo nello stradario del Comune',
                      'campi': ('codcom', 'denom')},
    'esisteaccesso': {'titolo': 'Esistenza di un accesso', 'esito': 'bool',
                      'descrizione': 'Esistenza di un accesso per l\'odonimo indicato',
                      'campi': ('codcom', 'denom', 'accesso')},
    'elencoodonimi': {'titolo': 'Aree di circolazione', 'esito': 'area',
                      'descrizione': 'Aree di circolazione per denominazione anche parziale',
                      'campi': ('codcom', 'denomparz')},
    'elencoaccessi': {'titolo': 'Accessi di un\'area', 'esito': 'accesso',
                      'descrizione': 'Accessi di un\'area di circolazione, anche per valori parziali',
                      'campi': ('codcom', 'denom', 'accparz')},
    'elencoodonimiprog': {'titolo': 'Odonimi con progressivo', 'esito': 'area_prog',
                          'descrizione': 'Odonimi del Comune con i progressivi nazionali',
                          'campi': ('codcom', 'denomparz')},
    'elencoaccessiprog': {'titolo': 'Accessi con progressivo', 'esito': 'accesso_prog',
                          'descrizione': 'Accessi di un\'area di circolazione con progressivo nazionale',
                          'campi': ('prognaz', 'accparz')},
    'prognazarea': {'titolo': 'Area dal progressivo', 'esito': 'area_prog',
                    'descrizione': 'Dati di un\'area di circolazione dal progressivo nazionale',
                    'campi': ('prognaz',)},
    'prognazacc': {'titolo': 'Accesso dal progressivo', 'esito': 'accesso_completo',
                   'descrizione': 'Dati di un accesso dal progressivo nazionale',
                   'campi': ('prognazacc',)},
}

# --- come arriva la risposta ------------------------------------------------------------
# Le colonne da mostrare, per famiglia di risposta. OpenAPI e guida tecnica non concordano
# (denomuff vs duf, coord GeoJSON vs coordX/coordY, denomloc a volte array): l'elenco qui
# e' quello della guida §2.3.2-§2.8, _valore() accetta entrambe le forme.
_ODOCIME = (('dug', 'DUG (tipo area)'), ('denomuff', 'Denominazione ufficiale'),
            ('denomloc', 'Denominazione località'), ('denomlingua1', 'Lingua 1'),
            ('denomlingua2', 'Lingua 2'))
_ACCESSI = (('civico', 'Numero civico'), ('esp', 'Esponente'), ('specif', 'Specificità'),
            ('metrico', 'Valore metrico'))
_PROG_AREA = (('prognaz', 'Progressivo nazionale area'),
              ('cododocomunale', 'Codice comunale area'))
_PROG_ACC = (('prognazacc', 'Progressivo nazionale accesso'),
             ('codacccomunale', 'Codice comunale accesso'))
_TOPO = (('coord', 'Coordinate (long, lat)'), ('quota', 'Quota'), ('metodo', 'Metodo di rilievo'))

ANNCSU_COLONNE = {
    'area': _ODOCIME,
    'area_prog': _PROG_AREA + _ODOCIME,
    'accesso': _ACCESSI,
    'accesso_prog': _PROG_ACC + _ACCESSI + _TOPO,
    'accesso_completo': _PROG_AREA + _ODOCIME + _PROG_ACC + _ACCESSI + _TOPO,
}


def anncsu_valida(campi, valori):
    """Campi obbligatori e formato, PRIMA di chiedere un voucher (invariante 3, lo stesso
    principio di verifica_cf: non si spende un token per una richiesta malformata).

    Su `codcom` il formato non basta: quattro maiuscole a caso passano, e ANNCSU risponde 'data:
    false' a un comune che non conosce. La Consultazione lo mostrerebbe come 'Esistenza non
    verificata', cioe' come una risposta dell'anagrafe invece che come una richiesta senza senso.
    """
    for nome in campi:
        conf = ANNCSU_CAMPI[nome]
        valore = valori.get(nome, '')
        if not re.match(conf['pattern'], valore):
            return f"{conf['etichetta']}: valore non valido o mancante."
        codici = _lista_comuni()[2] if conf.get('lookup') == 'comuni' else set()
        if codici and valore not in codici:
            return (f"{conf['etichetta']}: '{valore}' non e' il codice di un comune. "
                    f"{conf['hint']}.")
    return None


def _coord(item):
    """Coordinate: GeoJSON in stringa (guida §2.6.2) o coordX/coordY (OpenAPI)."""
    coord = item.get('coord')
    if isinstance(coord, str) and coord.strip():
        try:
            return ', '.join(str(c) for c in json.loads(coord)['coordinates'])
        except (ValueError, KeyError, TypeError):
            return coord.strip()          # non GeoJSON: la mostro com'e', non la scarto
    if item.get('coordX') or item.get('coordY'):
        return f"{item.get('coordX') or ''}, {item.get('coordY') or ''}".strip(', ')
    return ''


def _valore(item, chiave):
    if chiave == 'denomuff':
        valore = item.get('denomuff') or item.get('duf') or ''
    elif chiave == 'coord':
        return _coord(item)
    else:
        valore = item.get(chiave, '')
    if isinstance(valore, list):           # la guida mostra denomloc come [""]
        valore = ', '.join(str(v) for v in valore)
    return '' if valore is None else str(valore).strip()


def _dati_consultazione(payload):
    """`data` della risposta di Consultazione: la guida mostra un array, l'OpenAPI un oggetto."""
    dati = payload.get('data')
    if isinstance(dati, dict):
        dati = [dati]                      # prognaz*: un solo oggetto, la guida mostra un array
    return [item for item in (dati or []) if isinstance(item, dict)]


def anncsu_righe(esito, payload):
    """Risposta -> (intestazioni, righe) con le colonne di ANNCSU_COLONNE[esito]."""
    intestazioni = ANNCSU_COLONNE[esito]
    righe = [[_valore(item, chiave) for chiave, _ in intestazioni]
             for item in _dati_consultazione(payload)]
    return [etichetta for _, etichetta in intestazioni], righe


def anncsu_positivo(payload):
    """La guida §2.1.2 dice data:"true" (stringa), l'OpenAPI dice booleano: valgono entrambi."""
    return str(payload.get('data')).strip().lower() == 'true'


def anncsu_finalita_divergente(aud_voucher, target):
    """Il voucher dice a quale e-service la finalita' e' delegata (claim `aud`). Se non e'
    quello invocato, il 403 'Insufficient token claims' di GovWay e' la conseguenza e la
    causa e' la coppia purposeid/target: senza questo controllo l'operatore legge solo la
    claim tecnica e non capisce quale dei due campi correggere (vedi confronta_identificatori
    in tracing.py, stesso guasto sulla tracing API)."""
    if not aud_voucher or aud_voucher.rstrip('/') == target.rstrip('/'):
        return None
    return {'title': 'Finalità non coerente col target',
            'detail': (f'la purposeid delega l’e-service {aud_voucher}, il target configurato '
                       f'è {target}: correggi il target nelle impostazioni di ANNCSU')}


def _problema(payload, status):
    """application/problem+json (400/404/405/422/500) -> una riga leggibile per l'operatore."""
    if isinstance(payload, dict):
        dettaglio = ' '.join(str(payload.get(chiave, '')).strip()
                             for chiave in ('title', 'detail')).strip()
        if dettaglio:
            return f"ANNCSU ha risposto {status}: {dettaglio}"
    return f"ANNCSU ha risposto {status} senza dettagli."


def anncsu_abilitato(utente, codice='anncsu'):
    """Doppio gate (invariante 1): attivo in servizi_parametri AND il flag dell'utente per
    quell'e-service. `codice` e' quello di servizi_parametri, non il nome del flag: la
    mappatura sta in ANNCSU_SERVIZI e il flag va rinominato li' se cambia in anncsu_servizi."""
    servizio = next((s for s in ANNCSU_SERVIZI if s['codice'] == codice), None)
    if servizio is None:
        return False
    attivo = bool(ServiziParametri.objects.filter(codice_servizio=codice)
                  .values_list('attivo', flat=True).first())
    return attivo and bool(utente) and bool(getattr(utente, servizio['flag'], False))


# --- il comune dell'ente come default ------------------------------------------------------
# `dati_ente.citta` e' testo libero compilato nel backoffice e vale 'Roma (RM)': il token fra
# parentesi va tolto prima di confrontarlo coi nomi della lista. La lista vive in
# static/comuni.json (7894 comuni, fonte e rinnovo in docs/): e' dati pubblici di sola
# lettura, una tabella nel DB avrebbe chiesto update/*.sh e bump di versione per niente.
_COMUNI = None


def _lista_comuni():
    """(lista, indice, codici, nomi) da static/comuni.json, una volta sola.

    L'indice e' il nome normalizzato (per il default dell'ente), `codici` e' l'insieme dei
    Belfiore validi: serve a `anncsu_valida`, perche' il solo pattern ammette ogni sequenza di
    quattro caratteri maiuscoli, 'ROMA' compreso. `nomi` e' il codice -> nome, per rendere il
    campo del comune dell'ente leggibile (`_etichetta_comune`).
    """
    global _COMUNI
    if _COMUNI is None:
        try:
            percorso = str(finders.find('comuni.json') or '')
            with open(percorso, encoding='utf-8') as file:
                lista = json.load(file)
        except (TypeError, OSError, ValueError):
            lista = []            # file assente o rotto: i campi restano input di testo
        indice, codici, nomi = {}, set(), {}
        for voce in lista:
            indice.setdefault(_chiave_comune(voce['n']), []).append(voce['c'])
            codici.add(voce['c'])
            nomi[voce['c']] = voce['n']
        _COMUNI = (lista, indice, codici, nomi)
    return _COMUNI


def _chiave_comune(nome):
    """Il nome come lo si confronta: maiuscolo, senza accenti, punteggiatura o spazi."""
    senza = re.sub(r'\s*\([A-Za-z]{2}\)\s*$', '', nome or '')   # 'Roma (RM)' -> 'Roma'
    senza = unicodedata.normalize('NFKD', senza)
    senza = ''.join(c for c in senza if not unicodedata.combining(c)).upper()
    return re.sub(r'[^A-Z0-9]', '', senza)


def anncsu_comune_ente():
    """Codice Belfiore del comune dell'ente, e solo se il suo nome e' un colpo unico.

    E' il default del campo `codcom`: se `citta` e' una frazione, un indirizzo o un nome ambiguo
    il default non c'e' e l'operatore sceglie. Non si tira a indovinare: scrivere nell'ANCSU
    costa una scrittura irreversibile.
    """
    ente = DatiEnte.objects.first()
    chiave = _chiave_comune(ente.citta if ente else '')
    if not chiave:
        return ''
    colpi = _lista_comuni()[1].get(chiave, [])
    return colpi[0] if len(colpi) == 1 else ''


def _etichetta_comune(codice):
    """'Roma (H501)' dal Belfiore: il nome lo legge l'operatore, il codice e' quello che parte.

    Un codice che non e' nell'elenco se rende da solo: il campo e' disabilitato, un nome
    inventato sarebbe peggio di niente.
    """
    nome = _lista_comuni()[3].get(codice)
    return f'{nome} ({codice})' if nome else codice


def _valore_da_rendere(campo, valori):
    """Cosa finirebbe nell'input: il valore invocato, o il comune dell'ente se il campo non c'era.

    La distinzione e' fra `non c'era` (GET, prima resa) e `c'era ed e' vuoto` (POST): un campo
    che l'operatore ha svuotato non deve riempirsi di nuovo prima del `azione=invia`.
    Un campo fisso invece non ha un valore invocato: e' sempre il comune dell'ente, reso col
    nome perche' a un campo spento l'operatore deve capire cosa guarda.
    """
    nome = campo['nome']
    if campo.get('fisso'):
        return _etichetta_comune(anncsu_comune_ente())
    if valori.get(nome):
        return valori[nome]
    if campo.get('lookup') == 'comuni' and nome not in valori:
        return anncsu_comune_ente()
    return ''


def _campi_da_rendere(valori):
    """Un input per ogni campo, non uno per operazione (codcom compare in cinque): il JS
    nasconde quelli che non servono, il POST riceve sempre le stesse chiavi."""
    campi = []
    for nome, conf in ANNCSU_CAMPI.items():
        dove = [chiave for chiave, op in ANNCSU_OPERAZIONI.items() if nome in op['campi']]
        campo = {'nome': nome, **conf}
        campi.append({**campo, 'valore': _valore_da_rendere(campo, valori),
                      'operazioni': ' '.join(dove)})
    return campi


def _operazioni_da_rendere():
    return [{'chiave': chiave, 'titolo': op['titolo'], 'descrizione': op['descrizione'],
             'input': ', '.join(op['campi'])} for chiave, op in ANNCSU_OPERAZIONI.items()]


def anncsu_consultazione(request):
    """Pagina di servizio: descrizione dell'e-service + form di interrogazione.

    Lo stato dell'ultima estrazione va in sessione (invariante 5), niente file su disco.
    """
    utente = (UtentiParametri.objects.filter(id=request.user.id).first()
              if request.user.is_authenticated else None)
    utente_abilitato = anncsu_abilitato(utente)

    valori = {nome: (request.POST.get(nome) or '').strip().upper() for nome in ANNCSU_CAMPI} \
        if request.method == 'POST' else {}
    operazione_scelta = request.POST.get('operazione', '') if request.method == 'POST' else ''
    risultati = {'tipo': None, 'titolo': '', 'positivo': False, 'intestazioni': [], 'righe': []}
    error = None

    if request.method == 'POST' and utente_abilitato:
        operazione = ANNCSU_OPERAZIONI.get(operazione_scelta)
        if operazione is None:
            error = 'Interrogazione non valida.'
        else:
            error = anncsu_valida(operazione['campi'], valori)
            if error is None:
                payload, status, purp_id, tok_id = anncsu_richiesta(
                    request.user.username, operazione_scelta, operazione['campi'], valori)
                # invarianti 2 e 8: una riga in logs per interrogazione, solo metadati
                salva_log(request.user, "Consultazione ANNCSU", operazione_scelta,
                          purposeid=purp_id, resp_status=status, token_id=tok_id)
                if payload is None:
                    error = (f"Il servizio ha risposto {status} senza un JSON interpretabile."
                             if status != 502 else "L'authority non ha rilasciato un voucher.")
                elif status != 200:
                    error = _problema(payload, status)
                elif operazione['esito'] == 'bool':
                    risultati = {'tipo': 'bool', 'titolo': operazione['titolo'],
                                 'positivo': anncsu_positivo(payload),
                                 'intestazioni': [], 'righe': []}
                else:
                    intestazioni, righe = anncsu_righe(operazione['esito'], payload)
                    if not righe:
                        error = 'Nessun risultato.'
                    else:
                        risultati = {'tipo': 'tabella', 'titolo': operazione['titolo'],
                                     'positivo': True, 'intestazioni': intestazioni,
                                     'righe': righe}
                        request.session['anncsu_export'] = {
                            'operazione': operazione_scelta, 'titolo': operazione['titolo'],
                            'intestazioni': intestazioni, 'righe': righe}

    return render(request, 'anncsu.html', {
        'utente_abilitato': utente_abilitato,
        'operazioni': _operazioni_da_rendere(),
        'campi': _campi_da_rendere(valori),
        'operazione_scelta': operazione_scelta,
        'risultati': risultati,
        'error': error})


def _export_sessione(request):
    """(stop, dati): il gate dei due export in un punto solo (invariante 1) e l'ultima
    estrazione. `stop` e' una HttpResponse di errore gia' pronta; `dati` e' sempre un dict,
    vuoto se l'utente non ha ancora fatto un'interrogazione a elenco."""
    utente = (UtentiParametri.objects.filter(id=request.user.id).first()
              if request.user.is_authenticated else None)
    if not anncsu_abilitato(utente):
        return HttpResponse('Utente non abilitato', status=403), {}
    return None, request.session.get('anncsu_export') or {}


def anncsu_export_excel(request):
    """XLSX dell'ultima interrogazione con risultato a elenco.

    Chiave di sessione propria, non multi_data: le view di export dei moduli fratelli
    (inad, anpr, anis) leggono multi_data nella stessa sessione e si scambierebbero i dati.
    """
    stop, dati = _export_sessione(request)
    if stop is not None:
        return stop
    righe = dati.get('righe') or []
    if not righe:
        return HttpResponse("Nessun dato disponibile per l'esportazione", status=400)

    wb = Workbook()
    ws = wb.worksheets[0]
    intestazioni = dati['intestazioni']
    ws.append(list(intestazioni))
    larghezze = [len(str(colonna)) for colonna in intestazioni]
    for riga in righe:
        ws.append(list(riga))
        for indice, cell in enumerate(next(ws.iter_rows(min_row=ws.max_row, max_row=ws.max_row))):
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
    response['Content-Disposition'] = f"attachment; filename=EsitoAnncsu{dati.get('operazione', '')}.xlsx"
    return response


def anncsu_export_csv(request):
    """CSV a ';' dell'ultima interrogazione: stessi dati e stesso gate dell'XLSX.
    Delimitatore ';' come cf_da_file (utils.py), che legge i CSV esportati da Excel."""
    stop, dati = _export_sessione(request)
    if stop is not None:
        return stop
    righe = dati.get('righe') or []
    if not righe:
        return HttpResponse("Nessun dato disponibile per l'esportazione", status=400)

    response = HttpResponse(content_type='text/csv',
                            headers={'Content-Disposition':
                                     f"attachment; filename=EsitoAnncsu{dati.get('operazione', '')}.csv"})
    scrittore = csv.writer(response, delimiter=';')
    scrittore.writerow(dati['intestazioni'])
    scrittore.writerows(righe)
    return response


# --- i tre servizi di aggiornamento ------------------------------------------------------
# POST {target}{percorso} con body {"richiesta": {...}}: un solo elemento per richiesta (tutti e
# tre i PDF: 'Ogni richiesta ... riferita ad un unico elemento'). Risposta {idRichiesta, esito,
# messaggio, dati} sul successo, {id, codice, messaggio} sul rifiuto: `codice` e' quello dei PDF.
#
# L'endpoint NON e' una colonna: accessi e coordinate condividono la base URL (cambia solo il
# path) e `target` deve restare la base, perche' e' li' che punta il claim `aud` del voucher e
# anncsu_finalita_divergente confronta proprio lui: un target col path dentro farebbe scattare
# il falso allarme 'Finalita' non coerente' su ogni chiamata.
#
# `path` e' il punto del body (separato da .), `req` quando il campo e' obbligatorio, `solo` le
# operazioni che lo ammettono: vengono dalle note dell'OpenAPI e dai codici errore dei PDF
# (55/60/80 accessi, 105/110/115/125/130/135 coordinate, 200/210/235/260/270/325 odonimi).
# Form, validazione ed elenco CSV leggono tutti questa tabella: non possono divergere.

_OPS = ('I', 'R', 'S')
_SEMPRE = '*'
_OPC = r'^[IRS]$'
_DATA = r'^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
_METODO = r'^[1-4]$'
_FLAG = r'^[0-4]$'

# Le quattro diciture vengono dalle Specifiche tecniche ANCSU (8/11/2026): nei PDF e negli YAML
# di docs/ si dice solo "valori ammessi da 1 a 4" (errore 130), percio' stanno qui e non nel
# template. Il menu a tendina le mostra, il filo e il CSV continuano a portare il solo codice.
ANNCSU_METODI = (
    ('1', 'Rilevazione strumentale sul campo, con accuratezza < 5 m'),
    ('2', 'Rilevazione strumentale sul campo, con accuratezza ≥ 5 m'),
    ('3', 'Derivazione indiretta da base dati territoriale, con accuratezza stimabile < 5 m'),
    ('4', 'Derivazione indiretta da base dati territoriale, con accuratezza stimabile ≥ 5 m'),
)


def _num(lunghezza):
    return rf'^[0-9]{{1,{lunghezza}}}$'


def _txt(lunghezza, maiuscole=True):
    intervallo = 'A-Z0-9À-ſ' if maiuscole else 'A-Za-z0-9À-ſ'
    return '^[' + intervallo + rf" .,'&/()-]{{1,{lunghezza}}}$"


_COORD = r'^-?[0-9]{1,3}(\.[0-9]{1,12})?$'
_QUOTA = r'^-?[0-9]{1,7}$'
_PROTOCOLLO = _txt(70, False)


def _campo(nome, path, etichetta, hint, pattern, maxlength, req=(), solo=(), lookup=None,
           fisso=False, scelte=None):
    """Descrittore di un campo del body, usato identico dal form, dalla validazione dal CSV.

    `lookup`, `fisso` e `scelte` sono le sole chiavi lette dal template: la prima rende il campo
    una ricerca sul nome (static/js/comuni.js), la seconda lo rende disabilitato perche' il
    valore lo decide il portale (`_fissi`), la terza lo rende un menu a tendina. `lookup` e
    `scelte` il validatore le ignora, `fisso` no.
    """
    return {'nome': nome, 'path': path, 'etichetta': etichetta, 'hint': hint,
            'pattern': pattern, 'maxlength': maxlength, 'req': req, 'solo': solo,
            'lookup': lookup, 'fisso': fisso, 'scelte': scelte}


_CAMPI_ACCESSI = (
    _campo('codcom', 'codcom', 'Comune', "Comune dell'ente, dai dati anagrafici: non si cambia",
           _CODCOM, 4, req=_SEMPRE, lookup='comuni', fisso=True),
    _campo('progr_nazionale', 'progr_nazionale', "Progressivo nazionale dell'area",
           'Solo cifre, es. 2000449', _num(10), 10, req=_SEMPRE),
    _campo('operazione_civico', 'accesso.operazione_civico', "Operazione sull'accesso",
           'I=inserimento, R=aggiornamento, S=soppressione', _OPC, 1, req=_SEMPRE),
    _campo('progr_civico', 'accesso.progr_civico', "Progressivo nazionale dell'accesso",
           'Solo cifre; obbligatorio per R e S, mai per I', _num(15), 15,
           req=('R', 'S'), solo=('R', 'S')),
    _campo('codice_civico_comunale', 'accesso.codice_civico_comunale',
           "Codice dell'accesso assegnato dal comune", 'Massimo 30 caratteri',
           _txt(30, False), 30, solo=('I', 'R')),
    _campo('numero', 'accesso.numero', 'Numero civico',
           'Sistema ordinale: si usa in alternativa al valore metrico', _num(5), 5,
           req=('I', 'R'), solo=('I', 'R')),
    _campo('metrico', 'accesso.metrico', 'Valore metrico',
           'Sistema metrico: si usa in alternativa al numero civico', _num(6), 6,
           solo=('I', 'R')),
    _campo('esponente', 'accesso.esponente', 'Esponente', 'Es. A', _txt(15), 15,
           solo=('I', 'R')),
    _campo('specificita', 'accesso.specificita', 'Specificita', 'Es. ROSSO', _txt(5), 5,
           solo=('I', 'R')),
    _campo('sezione_censimento', 'accesso.sezione_censimento', 'Sezione di censimento',
           'Solo cifre, deve esistere tra quelle del comune', _num(13), 13, solo=('I', 'R')),
    _campo('isolato', 'accesso.isolato', 'Codice isolato', 'Massimo 4 caratteri', _txt(4), 4,
           solo=('I', 'R')),
    _campo('x', 'accesso.coordinate.x', 'Longitudine', 'Sessagesimale col punto, da 6 a 18',
           _COORD, 12, solo=('I', 'R')),
    _campo('y', 'accesso.coordinate.y', 'Latitudine', 'Sessagesimale col punto, da 36 a 47',
           _COORD, 12, solo=('I', 'R')),
    _campo('z', 'accesso.coordinate.z', 'Quota', 'Metri sul livello, solo con le coordinate',
           _QUOTA, 7, solo=('I', 'R')),
    _campo('metodo', 'accesso.coordinate.metodo', 'Metodo di rilevazione',
           'Obbligatorio quando le coordinate c sono', _METODO, 1, solo=('I', 'R'),
           scelte=ANNCSU_METODI),
    _campo('data_valid_amm', 'accesso.data_valid_amm', "Data di validita' amministrativa",
           'gg/mm/aaaa; vuota = data corrente; per S e la fine validita', _DATA, 10),
)

_CAMPI_COORDINATE = (
    _campo('codcom', 'accesso.codcom', 'Comune', "Comune dell'ente, dai dati anagrafici: non si cambia",
           _CODCOM, 4, req=_SEMPRE, lookup='comuni', fisso=True),
    _campo('progr_civico', 'accesso.progr_civico', "Progressivo nazionale dell'accesso",
           "L'accesso dell'indirizzario a cui appartengono le coordinate", _num(15), 15,
           req=_SEMPRE),
    _campo('x', 'accesso.coordinate.x', 'Longitudine', 'Sessagesimale col punto, da 6 a 18',
           _COORD, 12, req=_SEMPRE),
    _campo('y', 'accesso.coordinate.y', 'Latitudine', 'Sessagesimale col punto, da 36 a 47',
           _COORD, 12, req=_SEMPRE),
    _campo('z', 'accesso.coordinate.z', 'Quota', 'Metri sul livello, solo con le coordinate',
           _QUOTA, 7),
    _campo('metodo', 'accesso.coordinate.metodo', 'Metodo di rilevazione',
           'Come è stato rilevato il posizionamento', _METODO, 1, req=_SEMPRE,
           scelte=ANNCSU_METODI),
)

# Un'unica tipologia di operazione: il posizionamento existente non viene storicizzato, ma
# sovrascritto (PDF coordinate, Introduzione). Per questo qui non c'e' campo operazione.

_CAMPI_ODONIMI = (
    _campo('codcom', 'codcom', 'Comune', "Comune dell'ente, dai dati anagrafici: non si cambia",
           _CODCOM, 4, req=_SEMPRE, lookup='comuni', fisso=True),
    _campo('tipo_operazione', 'tipo_operazione', "Operazione sull'odonimo",
           'I=inserimento, R=aggiornamento, S=soppressione', _OPC, 1, req=_SEMPRE),
    _campo('progr_nazionale', 'progr_nazionale', "Progressivo nazionale dell'area",
           'Obbligatorio per R e S, mai per I (codice errore 325)', _num(10), 10,
           req=('R', 'S'), solo=('R', 'S')),
    _campo('codice_comunale', 'codice_comunale', "Codice dell'area assegnato dal comune",
           'Massimo 30 caratteri, il maiuscolo non viene applicato', _txt(30, False), 30,
           solo=('I', 'R')),
    _campo('dug', 'dug', 'DUG', 'Es. VIA; obbligatoria per I e R, non ammessa per S',
           _txt(30), 30, req=('I', 'R'), solo=('I', 'R')),
    _campo('denom_delibera', 'denom_delibera', 'Denominazione da delibera',
           'Massimo 120 caratteri, senza la DUG', _txt(120), 120, req=('I', 'R'),
           solo=('I', 'R')),
    _campo('denom_in_lingua_1', 'denom_in_lingua_1', 'Odonimo in prima lingua',
           'Solo per comuni bi/tri lingue; comprende la DUG', _txt(150), 150, solo=('I', 'R')),
    _campo('denom_in_lingua_2', 'denom_in_lingua_2', 'Odonimo in seconda lingua',
           'Solo per comuni tri lingue; comprende la DUG', _txt(150), 150, solo=('I', 'R')),
    _campo('denom_localita', 'denom_localita', 'Denominazione localita',
           'Massimo 151 caratteri', _txt(151), 151, solo=('I', 'R')),
    _campo('flag_delibera', 'provvedimento.flag_delibera', 'Flag delibera',
           'Da 0 a 4; con 0 o 1 data e protocollo del provvedimento diventano obbligatori',
           _FLAG, 1, solo=('I', 'R')),
    _campo('data_prov', 'provvedimento.data', 'Data del provvedimento',
           'gg/mm/aaaa, non successiva a oggi', _DATA, 10, solo=('I', 'R')),
    _campo('protocollo', 'provvedimento.protocollo', 'Protocollo del provvedimento',
           'Massimo 70 caratteri, il maiuscolo non viene applicato', _PROTOCOLLO, 70,
           solo=('I', 'R')),
    _campo('data_pref', 'aut_prefettura.data_pref', 'Data autorizzazione di Prefettura',
           'gg/mm/aaaa, in coppia col protocollo', _DATA, 10, solo=('I', 'R')),
    _campo('protocollo_pref', 'aut_prefettura.protocollo_pref',
           'Protocollo autorizzazione di Prefettura', 'In coppia con la data', _PROTOCOLLO, 70,
           solo=('I', 'R')),
    _campo('data_valid_amm', 'data_valid_amm', "Data di validita' amministrativa",
           'gg/mm/aaaa; per S e la data conclusiva, non puo essere futura', _DATA, 10),
)

# Colonne di RispostaOperazione.dati: e' quello che l'archivio contiene dopo l'aggiornamento,
# e il template lo mostra com'e' (invariante 4: le date le passa converti_data).
_COLONNE_ESITO_ACCESSO = (
    ('progr_civico', 'Progressivo civico'), ('codice_civico_comunale', 'Codice comunale'),
    ('numero', 'Numero civico'), ('esponente', 'Esponente'), ('specificita', 'Specificita'),
    ('metrico', 'Metrico'), ('sez_censimento', 'Sezione di censimento'),
    ('progr_nazionale', 'Progressivo nazionale'), ('codcom', 'Codice comune'),
    ('coordinata_x_comune', 'Longitudine'), ('coordinata_y_comune', 'Latitudine'),
    ('coordinata_z_comune', 'Quota'), ('metodo', 'Metodo'), ('isolato', 'Isolato'),
    ('data_inizio', 'Data inizio'), ('data_fine', 'Data fine'),
    ("data_ini_valid_amm", 'Inizio validita amministrativa'),
    ("data_fine_valid_amm", 'Fine validita amministrativa'),
)
_COLONNE_ESITO_ODO = (
    ('codcom', 'Codice comune'), ('progr_nazionale', 'Progressivo nazionale'),
    ('codice_comunale', 'Codice comunale'), ('dug', 'DUG'),
    ('denom_delibera', 'Denominazione da delibera'), ('denom_in_lingua_1', 'Lingua 1'),
    ('denom_in_lingua_2', 'Lingua 2'), ('data_inizio', 'Data inizio'), ('data_fine', 'Data fine'),
    ("data_ini_valid_amm", 'Inizio validita amministrativa'),
    ("data_fine_valid_amm", 'Fine validita amministrativa'),
)


def _coordinato(valore):
    try:
        return float(valore)
    except (TypeError, ValueError):
        return None


def _coordinate_coerenti(valori):
    """Le sei regole dei PDF (105/110/115/125/130/135) in un punto solo, per i due servizi."""
    x, y = _coordinato(valori.get('x')), _coordinato(valori.get('y'))
    if valori.get('x') and x is None:
        return ['Longitudine: valore numerico decimale col punto come separatore.']
    if valori.get('y') and y is None:
        return ['Latitudine: valore numerico decimale col punto come separatore.']
    if bool(x) != bool(y):
        return ['Longitudine e latitudine si indicano in coppia: il servizio non accetta '
                'l\'una senza l\'altra.']
    if valori.get('z') and x is None:
        return ['Quota: si indica solo insieme a longitidine e latitudine.']
    if x is not None and not valori.get('metodo'):
        return ['Metodo di rilevazione: obbligatorio quando le coordinate c sono.']
    if x is not None and y is not None and not (6.0 <= x <= 18.0 and 36.0 <= y <= 47.0):
        return ['Longitudine e latitudine indicate individuano un punto fuori dall Italia.']
    return []


def _non_futura(valori, nome, etichetta):
    """Formato e coerenza della data: l'erogatore vuole dd/mm/yyyy e non la vuole futura."""
    data = normalizza_data(valori.get(nome, ''))
    if data is None:
        return [f'{etichetta}: formato non riconosciuto, serve dd/mm/yyyy.']
    if data > datetime.date.today():
        return [f'{etichetta}: non puo essere successiva alla data corrente.']
    return []


def _regole_accessi(valori):
    errori = _coordinate_coerenti(valori)
    if valori.get('operazione_civico') in ('I', 'R') and \
            bool(valori.get('numero')) == bool(valori.get('metrico')):
        errori.append('Numero civico e valore metrico: l\'accesso si identifica con l\'uno '
                      'o con l\'altro, non con entrambi e non senza nessuno dei due.')
    if valori.get('data_valid_amm'):
        errori += _non_futura(valori, 'data_valid_amm', "Data di validita' amministrativa")
    return errori


def _regole_odonimi(valori):
    errori = []
    if valori.get('flag_delibera') in ('0', '1') and \
            not (valori.get('data_prov') and valori.get('protocollo')):
        errori.append('Con flag delibera 0 o 1 la data e il protocollo del provvedimento '
                      'sono obbligatori.')
    if bool(valori.get('data_pref')) != bool(valori.get('protocollo_pref')):
        errori.append("Data e protocollo dell'autorizzazione di Prefettura si indicano "
                      'entrambi, o nessuno dei due.')
    for nome, etichetta in (('data_prov', 'Data del provvedimento'),
                            ('data_pref', "Data autorizzazione di Prefettura"),
                            ('data_valid_amm', "Data di validita' amministrativa")):
        if valori.get(nome):
            errori += _non_futura(valori, nome, etichetta)
    return errori


ANNCSU_AGGIORNAMENTI = {
    'anncsu_accessi': {'id': 2, 'percorso': '/accessi', 'operazione': 'operazione_civico',
                       'servizio': 'Aggiornamento accessi ANNCSU', 'campi': _CAMPI_ACCESSI,
                       'regole': _regole_accessi, 'colonne': _COLONNE_ESITO_ACCESSO},
    # le coordinate non hanno operazione: un solo modo di aggiornare, il posizionamento si
    # sovrascrive (PDF coordinate, Introduzione)
    'anncsu_coordinate': {'id': 3, 'percorso': '/gestionecoordinate', 'operazione': '',
                          'servizio': 'Aggiornamento coordinate ANNCSU',
                          'campi': _CAMPI_COORDINATE, 'regole': _coordinate_coerenti,
                          'colonne': _COLONNE_ESITO_ACCESSO,
                          # le coordinate si sovrascrivono: senza vedere cosa c'e' gia' in ANNCSU
                          # si scrive alla cieca, e l'aggiornamento non ha operazioni di lettura
                          'cerca': True},
    'anncsu_odonimi': {'id': 4, 'percorso': '/odonimi', 'operazione': 'tipo_operazione',
                       'servizio': 'Aggiornamento odonimi ANNCSU', 'campi': _CAMPI_ODONIMI,
                       'regole': _regole_odonimi, 'colonne': _COLONNE_ESITO_ODO},
}


def _nidifica(corpo, path, valore):
    """Mette `valore` al punto `path` di `corpo`, creando i rami che mancano."""
    parti = path.split('.')
    nodo = corpo
    for parte in parti[:-1]:
        nodo = nodo.setdefault(parte, {})
    nodo[parti[-1]] = valore


def anncsu_corpo(specifica, valori):
    """Body {"richiesta": {...}} con i soli campi valorizzati.

    Un campo vuoto si omette del tutto, non si manda come stringa vuota: l'erogatore lo
    leggerebbe come un valore indicato a vuoto e risponderebbe 400 su un modulo incompleto.
    """
    richiesta = {}
    for campo in specifica['campi']:
        if valori.get(campo['nome']):
            _nidifica(richiesta, campo['path'], valori[campo['nome']])
    return {'richiesta': richiesta}


def anncsu_valida_aggiornamento(specifica, valori):
    """Lista di errori, vuota = si puo' spendere un voucher (invariante 3).

    Forma, obbligatori e regole incrociate: un campo malformato qui costa un messaggio
    all'operatore, dal erogatore costa un token e un codice numerico da cercare sui PDF.
    """
    errori = []
    op = valori.get(specifica['operazione']) or ''
    if specifica['operazione'] and op not in _OPS:
        errori.append('Operazione non valida: scegliere inserimento, aggiornamento o '
                      'soppressione.')
    for campo in specifica['campi']:
        valore = valori.get(campo['nome'], '')
        # un campo fisso non lo sceglie l'operatore: se manca la colpa e' dei dati dell'ente,
        # e lo dice `_fissi`, non un 'obbligatorio' che invita a compilare un campo spento
        obbligatorio = not campo['fisso'] and (
            campo['req'] == _SEMPRE or (campo['req'] and op in campo['req']))
        if obbligatorio and not valore:
            errori.append(f"{campo['etichetta']}: obbligatorio.")
            continue
        if not valore:
            continue
        if campo['solo'] and op not in campo['solo']:
            errori.append(f"{campo['etichetta']}: non ammesso per l'operazione scelta "
                          f"(ammessa per {', '.join(campo['solo'])}).")
        elif not re.match(campo['pattern'], valore):
            errori.append(f"{campo['etichetta']}: valore non valido ({campo['hint']}).")
    return errori + specifica['regole'](valori)


def _presentazione(campo, valore):
    """Cosa il template aggiunge al tag del campo, deciso una volta sola nel codice.

    Sono testo di attributo (`disabled`, `data-lookup="comuni"`, `selected`, `hidden`): i
    `{% if %}` dentro un tag di apertura rompono chiunque lo legga come HTML, validatore del
    repo compreso. Nessun valore digitato dall'operatore ci entra, percio' il template li stampa
    senza scapparli. L'`id` cambia prefisso fra input e tendina perche' lo stesso id su due tag
    alternativi viene letto come duplicato.
    """
    if campo['fisso']:
        attri = 'disabled'
    elif campo['scelte']:
        attri = ''
    elif campo['lookup']:
        attri = f'data-lookup="{campo["lookup"]}"'
    else:
        attri = f'maxlength="{campo["maxlength"]}"'
    return {'attri': attri,
            'id': ('sl_' if campo['scelte'] else 'in_') + campo['nome'],
            'sempre': '1' if campo['req'] == _SEMPRE else '',
            'stella': '' if campo['req'] == _SEMPRE else 'hidden',
            'opzioni': [{'valore': v, 'etichetta': e,
                         'selezione': 'selected' if v == valore else ''}
                        for v, e in (campo['scelte'] or ())]}


def _fissi(specifica, valori):
    """Mette i campi fissi e dice cosa non tornava: errori, vuoto = si puo' procedere.

    Il comune dell'ente non e' una scelta dell'operatore: l'input e' disabilitato e quindi non
    parte nel POST, e un elenco potrebbe portarne un altro. Qui il valore lo decide il portale
    (su un'anagrafe nazionale si scrive solo il proprio comune) e il contrasto con cio' che
    arrive e' un errore detto, non un campo sostituito in silenzio.
    """
    errori = []
    for campo in specifica['campi']:
        if not campo['fisso']:
            continue
        codice = anncsu_comune_ente()
        indicato = valori.get(campo['nome'], '')
        if not codice:
            errori.append(f"{campo['etichetta']}: il codice Belfiore non si ricava dal campo "
                          "'citta' dell'ente: correggere i dati anagrafici dell'ente.")
        elif indicato and indicato != codice:
            errori.append(f"{campo['etichetta']}: {indicato} non e' il comune dell'ente "
                          f"({codice}): qui si scrive solo quello.")
        valori[campo['nome']] = codice
    return errori


def _post_firmata(parametri, url, corpo, user_id):
    """Audit -> asserzione(digest) -> voucher -> POST firmata: la sequenza AgID di ANNCSU.

    Una copia sola, condivisa fra la Consultazione e i tre aggiornamenti (AGENTS.md: una decima
    copia e' fuori questione). Ritorna (payload, status, purposeid, token_id); payload e' None
    se l'authority non rilascia il voucher (502) o se la risposta non e' JSON.
    """
    emesso = datetime.datetime.utcnow()
    prova, hash_prova = agid.audit(parametri, user_id, emesso=emesso, subject=parametri.clientid)
    voucher, token_id = agid.voucher(
        parametri, issuer=parametri.clientid,
        asserzione=agid.asserzione_client(parametri, digest=hash_prova,
                                          issuer=parametri.clientid,
                                          subject=parametri.clientid, emesso=emesso))
    if not voucher:
        return None, 502, parametri.purposeid, None      # authority non utilizzabile

    # un 403 con aud divergente e' quasi sempre purposeid/target disallineati, non un guasto
    try:
        aud_voucher = str(jwt.decode(voucher, options={'verify_signature': False})
                          .get('aud') or '')
    except jwt.PyJWTError:
        aud_voucher = ''

    response = requests.post(url, data=corpo.encode(agid.CODIFICA),
                             headers=agid.intestazioni(parametri, voucher, prova,
                                                      agid.digest_body(corpo), emesso=emesso),
                             timeout=30)                 # verify attivo: la catena e' pubblica
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if response.status_code == 403:
        payload = anncsu_finalita_divergente(aud_voucher, parametri.target) or payload
    return payload, response.status_code, parametri.purposeid, token_id


def anncsu_richiesta(user_id, operazione, campi, valori):
    """POST {target}/{operazione} della Consultazione, con body JSON e firma AgID.

    Client AgID unico (OpenMSP/agid.py): questa era la nona copia, ora e' una chiamata.
    `verifica` resta attivo (default True): ANNCSU e' l'unico servizio che non eredita il
    debito del verify=False (AGENTS.md r2), e la catena di modipa.agenziaentrate.gov.it e'
    pubblica. `subject` sull'audit e' proprio di ANNCSU: le altre famiglie non lo mandano.
    """
    parametri = AnncsuParametri.objects.get(id=ANNCSU_CONSULTAZIONE['id'])
    corpo = json.dumps({'req': operazione, **{nome: valori[nome] for nome in campi}})
    return _post_firmata(parametri, f'{parametri.target}/{operazione}', corpo, user_id)


def anncsu_aggiorna(request, chiave, valori):
    """Una richiesta di aggiornamento: POST firmata, una riga in logs, esito da rendere.

    Un elemento per chiamata, come lo chiedono i tre PDF: la modalita' massiva della pagina e'
    una coda di chiamate singole, non un body con piu' elementi.
    """
    specifica = ANNCSU_AGGIORNAMENTI[chiave]
    parametri = AnncsuParametri.objects.get(id=specifica['id'])
    payload, status, purp_id, tok_id = _post_firmata(
        parametri, parametri.target + specifica['percorso'],
        json.dumps(anncsu_corpo(specifica, valori)), request.user.username)
    # invarianti 2 e 8: una riga per richiesta, e solo metadati (quale operazione, con che esito)
    salva_log(request.user, specifica['servizio'],
              valori.get(specifica['operazione'], '') or specifica['percorso'].strip('/'),
              purposeid=purp_id, resp_status=status, token_id=tok_id)
    return anncsu_esito(payload, status, specifica)


def anncsu_esito(payload, status, specifica):
    """Risposta dell'erogatore -> {positivo, titoli, messaggi, colonne, righe} per il template.

    `esito` '0' e' il successo; `codice` arriva sui 400/404/500 ed e' il numero che l'operatore
    deve leggere, perche' e' lo stesso dei PDF di specifica.
    """
    if payload is None:
        return {'positivo': False, 'titolo': 'Nessuna risposta',
                'messaggi': ["L'authority non ha rilasciato un voucher, oppure l'erogatore ha "
                             'risposto senza un JSON interpretabile.']}
    if not isinstance(payload, dict):
        return {'positivo': False, 'titolo': 'Risposta non leggibile',
                'messaggi': [_problema(payload, status)]}

    if status != 200 or payload.get('codice'):
        messaggio = str(payload.get('messaggio') or '').strip() or _problema(payload, status)
        if payload.get('codice'):
            messaggio = f"Codice errore {payload['codice']}: {messaggio}"
        return {'positivo': False, 'titolo': 'Aggiornamento rifiutato', 'messaggi': [messaggio]}

    esito = str(payload.get('esito', '')).strip()
    messaggi = []
    if esito not in ('', '0'):
        messaggi.append(str(payload.get('messaggio') or 'Esito negativo').strip())
    righe = []
    for riga in _dati(payload):
        normalizzato = converti_data({str(k).lower(): v for k, v in riga.items()})
        righe.append([_valore(normalizzato, chiave) for chiave, _ in specifica['colonne']])
    return {'positivo': not messaggi,
            'titolo': f"Aggiornamento eseguito, id richiesta {payload.get('idRichiesta', '')}",
            'messaggi': messaggi, 'colonne': [e for _, e in specifica['colonne']],
            'righe': righe}


def _dati(payload):
    """RispostaOperazione.dati: la guida mostra un array, l'OpenAPI puo' rispondere un oggetto."""
    dati = payload.get('dati')
    if isinstance(dati, dict):
        return [dati]
    return [riga for riga in (dati or []) if isinstance(riga, dict)]

MAX_RIGHE = 200
# shortcut: una POST per riga con 30 secondi di timeout l'una; oltre ~200 righe il worker
# gunicorn muore prima della fine. Se serve di piu', serve un lavoro in coda, non un numero
# piu' grande scritto qui.


def _valori(specifica, dati):
    """Pulisce l'input: maiuscolo dove l'erogatore lo applica, date in dd/mm/yyyy, spazi via.

    Il maiuscolo non si forza dove la specifica dice 'non viene applicato l'uppercase' (il
    pattern del campo lo ammette): sono i codici comunali e i protocolli, e forzarlo vorrebbe
    dire mandare un valore diverso da quello indicato dall'operatore.
    """
    valori = {}
    for campo in specifica['campi']:
        valore = (dati.get(campo['nome']) or '').strip()
        if valore and 'A-Za-z' not in campo['pattern']:
            valore = valore.upper()
        if valore and campo['pattern'] == _DATA:
            data = normalizza_data(valore)          # accetta il yyyy-mm-dd del type=date
            if data:
                valore = data.strftime('%d/%m/%Y')
        valori[campo['nome']] = valore
    return valori


def anncsu_leggi(allegato, specifica):
    """(righe, errore): l'elenco normalizzato, o il perche' non si puo' usare.

    Stessa convenzione di utils.cf_da_file (';', utf-8-sig, XLSX sul primo foglio); qui pero'
    le colonne sono piu' d'una, quindi l'intestazione serve e una colonna sconosciuta e' un
    errore: ignorarla vorrebbe dire saltare un campo in silenzio.
    """
    nome = allegato.name.lower()
    if nome.endswith('.csv'):
        letture = list(csv.reader(io.TextIOWrapper(allegato.file, encoding='utf-8-sig'),
                                  delimiter=';'))
    elif nome.endswith('.xlsx'):
        letture = [[('' if cella is None else str(cella)) for cella in riga]
                   for riga in load_workbook(allegato).worksheets[0].iter_rows(values_only=True)]
    else:
        return [], 'Formato non supportato: caricare un CSV delimitato da punti e virgole o un XLSX.'
    if len(letture) < 2:
        return [], 'L\'elenco non ha righe: la prima deve essere l\'intestazione delle colonne.'

    chiavi = {c['nome'] for c in specifica['campi']}
    intestazione = [str(t).strip().lower() for t in letture[0]]
    sconosciute = [t for t in intestazione if t and t not in chiavi]
    if sconosciute:
        return [], ('Colonne non riconosciute: ' + ', '.join(sconosciute) +
                    '. Le colonne si chiamano come i campi del formulario.')
    if len(letture) - 1 > MAX_RIGHE:
        return [], (f'Troppe righe: {len(letture) - 1}, il massimo per un invio e {MAX_RIGHE} '
                    '(l\'erogatore processa un elemento per richiesta).')

    righe = []
    for numero, lettura in enumerate(letture[1:], start=2):
        # una riga corta (Excel ne scrive cosi', le celle vuote in coda cadono) si completa
        # di vuoti: non e' un errore, e' un elemento con quei campi non indicati
        cella = dict(zip_longest(intestazione, lettura, fillvalue=''))
        if not any(str(v or '').strip() for v in cella.values()):
            continue                                      # riga vuota di Excel: non e' un elemento
        valori = _valori(specifica, cella)
        valori['riga'] = numero
        righe.append(valori)
    return righe, None


def _riga_report(valori, specifica, esito=None, errori=None):
    """Una riga di resoconto: la vede l'operatore in pagina e la ritrova nell'XLSX."""
    return {'riga': valori['riga'],
            'operazione': valori.get(specifica['operazione'], '') or 'R',
            'esito': (('OK' if esito['positivo'] else 'RIFIUTATO') if esito else
                      # in simulazione una riga valida non e' rifiutata: non e' proprio partita
                      ('NON INVIATA' if errori else 'DA INVIARE')),
            'messaggi': errori or (esito.get('messaggi') if esito else []) or [],
            'codice': (esito or {}).get('codice', ''),
            'id_richiesta': (esito or {}).get('id_richiesta', ''),
            'progressivo': esito['righe'][0][0] if esito and esito.get('righe') else ''}


def _xlsx(nome, intestazioni, righe):
    """XLSX in memoria: niente disco (invariante 5), il file esce nella risposta."""
    wb = Workbook()
    foglio = wb.worksheets[0]
    foglio.append(list(intestazioni))
    for riga in righe:
        foglio.append(list(riga))
    for indice in range(1, len(intestazioni) + 1):
        foglio.column_dimensions[get_column_letter(indice)].width = 22
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument'
                                             '.spreadsheetml.sheet',
                        headers={'Content-Disposition': f'attachment; filename={nome}.xlsx'})


def _anncsu_elenco(request, chiave, specifica):
    """Elenco: 'Simula' valida e basta, 'Invia' esegue una POST per riga e risponde il XLSX.

    Ritorna un HttpResponse (il file) oppure (errore, report) da rendere nella pagina. Fra i due
    pulsanti non c'e' nulla da tenere in sessione: le sessioni di Django qui sono cookie
    (`settings.py` non imposta `SESSION_ENGINE`) e non conterrebbero ne l'elenco ne gli esiti.
    """
    righe, errore = anncsu_leggi(request.FILES['allegato'], specifica)
    if errore:
        return errore, None

    report, invalida = [], 0
    for valori in righe:
        errori = _fissi(specifica, valori) + anncsu_valida_aggiornamento(specifica, valori)
        invalida += bool(errori)
        report.append(_riga_report(valori, specifica, errori=errori))
    if request.POST.get('azione') == 'simula':
        return None, report
    if invalida or not righe:
        return ('Elenco non inviato: ' + (f'{invalida} righe non valide, usare Simula prima.'
                                         if invalida else 'nessuna riga da inviare.')), report

    esiti = []
    for valori in righe:
        esiti.append(_riga_report(valori, specifica, anncsu_aggiorna(request, chiave, valori)))
    return _xlsx(f'Esiti{chiave}',
                 ('Riga', 'Operazione', 'Esito', 'Messaggio', 'Codice', 'Id richiesta',
                  'Progressivo'),
                 [[r['riga'], r['operazione'], r['esito'], '; '.join(r['messaggi']), r['codice'],
                   r['id_richiesta'], r['progressivo']] for r in esiti]), None


# --- la ricerca del civico dentro l'aggiornamento coordinate ---------------------------------
# Il posizionamento si sovrascrive senza storicizzarlo, e l'aggiornamento coordinate non ha
# nessuna operazione di lettura (docs/…coordinate.yml: solo POST /gestionecoordinate): le uniche
# due operazioni che dicono cosa c'e' gia' in ANNCSU sono di Consultazione, e sono due perche'
# 'elencoaccessiprog' parte dal progressivo nazionale dell'area, non dal nome della via.
LOG_RICERCA = 'Consultazione ANNCSU (da Aggiornamento coordinate)'


def _righe_ricerca(payload):
    """Un dict per elemento della risposta, con le chiavi che legge il template della ricerca.

    `anncsu_righe()` fonde longitudine e latitudine in una cella sola perche' cosi' si mostrano
    nella Consultazione; qui servono separate per scrivere nei due campi del form, e il resto e'
    lo stesso lavoro di `_valore()` (array, maiuscole, GeoJSON in stringa).
    """
    chiavi = ('prognaz', 'prognazacc', 'dug', 'denomuff', 'civico', 'esp', 'specif',
              'metrico', 'quota', 'metodo')
    righe = []
    for item in _dati_consultazione(payload):
        lungo, _, largo = _coord(item).partition(', ')
        righe.append(dict({chiave: _valore(item, chiave) for chiave in chiavi},
                          x=lungo.strip(), y=largo.strip()))
    return righe


def _cerca(request, operazione, obbligatori, valori):
    """Una interrogazione di Consultazione dalla pagina di aggiornamento: (righe, errore).

    Stessa firma, stesso voucher, stessa riga in logs della pagina di Consultazione (invarianti
    2 e 8: metadati, le coordinate non salgono nel log). Cambia solo dove finisce il risultato:
    nella risposta, mai in sessione, che qui e' un cookie da 4 KB (invariante 5).
    """
    errore = anncsu_valida(obbligatori, valori)
    if errore:
        return [], errore
    payload, status, purp_id, tok_id = anncsu_richiesta(
        request.user.username, operazione, ANNCSU_OPERAZIONI[operazione]['campi'], valori)
    salva_log(request.user, LOG_RICERCA, operazione, purposeid=purp_id, resp_status=status,
              token_id=tok_id)
    if payload is None:
        return [], ("L'authority non ha rilasciato un voucher." if status == 502 else
                    f'Il servizio ha risposto {status} senza un JSON interpretabile.')
    if status != 200:
        return [], _problema(payload, status)
    righe = _righe_ricerca(payload)
    return righe, (None if righe else 'Nessun risultato: controllare la denominazione.')


def _ricerca_accessi(request):
    """I due passi della ricerca: prima le aree per denominazione, poi i civici dell'area.

    I valori digitati tornano indietro nel contesto anche quando la chiamata va male: l'utente
    deve vedere cosa ha cercato, non una pagina ripulita.
    """
    if request.POST.get('azione') == 'accessi':
        prov = (request.POST.get('prognaz') or '').strip()
        parz = (request.POST.get('accparz') or '').strip().upper()
        nome = (request.POST.get('denomparz') or '').strip().upper()
        righe, errore = _cerca(request, 'elencoaccessiprog', ('prognaz',),
                               {'prognaz': prov, 'accparz': parz})
        return ({'passo': 'accessi', 'prognaz': prov, 'accparz': parz,
                 'denomparz': nome, 'righe': righe}, errore)
    nome = (request.POST.get('denomparz') or '').strip().upper()
    righe, errore = _cerca(request, 'elencoodonimiprog', ('codcom', 'denomparz'),
                           {'codcom': anncsu_comune_ente(), 'denomparz': nome})
    return {'passo': 'aree', 'denomparz': nome, 'righe': righe}, errore


def _anncsu_aggiornamento(request, chiave):
    """Pagina dei tre aggiornamenti: form, riepilogo di conferma, esito ed elenco.

    Il primo POST non chiama nessuno: se i campi passano i controlli rende il riepilogo e chiede
    una conferma esplicita (sono scritture su un'anagrafe nazionale, e un click su 'sopprimi'
    non puo bastare); il POST con azione=invia e' quello che parla all'erogatore.
    """
    servizio = ANNCSU_PER_URL[chiave]
    specifica = ANNCSU_AGGIORNAMENTI[chiave]
    utente = (UtentiParametri.objects.filter(id=request.user.id).first()
              if request.user.is_authenticated else None)
    utente_abilitato = anncsu_abilitato(utente, servizio['codice'])

    valori, errori, esito, report, conferma = {}, [], None, None, False
    cerca = bool(specifica.get('cerca')) and anncsu_abilitato(utente)
    ricerca = None
    campi = []
    for c in specifica['campi']:
        valore = _valore_da_rendere(c, valori)      # una resa sola: `anncsu_comune_ente()` legge il DB
        campi.append(dict(c, valore=valore,
                          operazioni=' '.join(c['solo'] or _OPS),
                          richiesti=' '.join(c['req'] if isinstance(c['req'], tuple) else _OPS),
                          **_presentazione(c, valore)))
    if request.method == 'POST' and utente_abilitato:
        if cerca and request.POST.get('azione') in ('cerca', 'accessi'):
            ricerca, errore = _ricerca_accessi(request)
            errori = [errore] if errore else []
        elif request.FILES.get('allegato'):
            risposta = _anncsu_elenco(request, chiave, specifica)
            if isinstance(risposta[0], HttpResponse):
                return risposta[0]
            errore, report = risposta
            errori = [errore] if errore else []
        else:
            valori = _valori(specifica, request.POST)
            errori = _fissi(specifica, valori) + anncsu_valida_aggiornamento(specifica, valori)
            if not errori and request.POST.get('azione') == 'invia':
                esito = anncsu_aggiorna(request, chiave, valori)
            elif not errori:
                conferma = True

    # si rende la pagina (che estende base.html), non il corpo condiviso: renderando il partial
    # escono i soli contenuti nudi, senza <head> ne Bootstrap Italia
    return render(request, f'{chiave}.html', {
        'servizio': servizio,
        'utente_abilitato': utente_abilitato,
        'operazione': specifica['operazione'],
        'operazioni': (('I', 'Inserimento'), ('R', 'Aggiornamento'), ('S', 'Soppressione'))
                      if specifica['operazione'] else (),
        'campi': campi,
        'cerca': cerca,
        'ricerca': ricerca,
        'valore_op': valori.get(specifica['operazione'], ''),
        'conferma': conferma,
        'errori': errori,
        'esito': esito,
        'report': report,
        'max_righe': MAX_RIGHE,
        'url_name': chiave,
    })

def _anncsu_non_attivo(request, url_name):
    """Pagina di servizio per l'e-service ancora senza client (Visura: nessuna specifica in docs/).

    Il gate gira uguale (invariante 1): l'operatore autorizzato vede 'servizio non ancora
    attivo', chi non lo e' vede lo stesso avviso di 'non abilitato' della pagina di
    consultazione, non un 404 che lascerebbe pensare a un menu rotto.
    """
    servizio = ANNCSU_PER_URL[url_name]
    utente = (UtentiParametri.objects.filter(id=request.user.id).first()
              if request.user.is_authenticated else None)
    return render(request, 'anncsu_non_attivo.html', {
        'servizio': servizio,
        'utente_abilitato': anncsu_abilitato(utente, servizio['codice']),
    })


def anncsu_accessi(request):
    return _anncsu_aggiornamento(request, 'anncsu_accessi')


def anncsu_coordinate(request):
    return _anncsu_aggiornamento(request, 'anncsu_coordinate')


def anncsu_odonimi(request):
    return _anncsu_aggiornamento(request, 'anncsu_odonimi')


def anncsu_visura(request):
    return _anncsu_non_attivo(request, 'anncsu_visura')


def impostazioni_anncsu(request):
    """Una tab per e-service
    dall'id della riga, e il POST salva solo la riga della tab attiva.

    Gli id delle FK si passano solo per posizione: il campo si chiama servizio_id quanto la
    colonna, quindi il descrittore si interpone e per keyword pretende l'istanza
    AnncsuServizi (ValueError). MitParametri/AnprParametri fanno cosi'.
    """
    if request.method == 'POST':
        try:
            riga = int(request.POST.get('active_tab', '').replace('tab', ''))
        except ValueError:
            riga = None
        if any(s['id'] == riga for s in ANNCSU_SERVIZI):
            def preso(nome):
                return request.POST.get(f'{nome}{riga}') or ''
            valori = [preso(c) for c in
                      ('kid', 'alg', 'typ', 'iss', 'sub', 'aud', 'purposeid', 'audience',
                       'baseurlauth', 'target', 'clientid')]
            # una textarea lasciata vuota non deve cancellare la chiave gia' configurata
            chiave = preso('private_key') or \
                AnncsuParametri.objects.filter(id=riga).values_list('private_key', flat=True).first() or ''
            AnncsuParametri(riga, riga, *valori, chiave, preso('ver_eservice')).save()
            salva_log(request.user, "Impostazioni ANNCSU", f"modifica parametri {riga}")
        return redirect(request.path)

    return render(request, 'impostazioni_anncsu.html', {
        'servizi_anncsu': AnncsuServizi.objects.all().order_by('id'),
        'parametri_anncsu': AnncsuParametri.objects.all().order_by('id'),
    })
