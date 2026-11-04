# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
from django.shortcuts import redirect, render
from django.http import HttpResponse

from impostazioni.models import AnncsuParametri
from impostazioni.models import AnncsuServizi
from impostazioni.models import ServiziParametri
from impostazioni.models import UtentiParametri

from .utils import salva_log
from . import agid

import datetime

import csv
import io
import jwt
import requests
import json
import re
from openpyxl import Workbook
from openpyxl.utils import get_column_letter


# --- i cinque e-service ANNCSU -----------------------------------------------------------
# Unica fonte di verita' per gate, menu, card di home, impostazioni e route: il doppio gate
# (invariante 1) legge servizi_parametri.attivo (chiave `codice`) AND il flag dell'utente
# (chiave `flag`), e la riga di anncsu_parametri ha lo stesso id di anncsu_servizi.
# `implementato` vale True solo per la Consultazione: per gli altri quattro il client AgID non
# e' ancora scritto perche' non c'e' la specifica (docs/ ha solo quella della Consultazione).
ANNCSU_SERVIZI = (
    {'id': 1, 'codice': 'anncsu', 'flag': 'anncsu_consultazione_comuni', 'url': 'anncsu',
     'etichetta': 'Consultazione per i COMUNI', 'tab': 'tab1', 'implementato': True},
    {'id': 2, 'codice': 'anncsu_accessi', 'flag': 'anncsu_accessi', 'url': 'anncsu_accessi',
     'etichetta': 'Aggiornamento accessi', 'tab': 'tab2', 'implementato': False},
    {'id': 3, 'codice': 'anncsu_coordinate', 'flag': 'anncsu_coordinate', 'url': 'anncsu_coordinate',
     'etichetta': 'Aggiornamento coordinate', 'tab': 'tab3', 'implementato': False},
    {'id': 4, 'codice': 'anncsu_odonimi', 'flag': 'anncsu_odonimi', 'url': 'anncsu_odonimi',
     'etichetta': 'Aggiornamento odonimi', 'tab': 'tab4', 'implementato': False},
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
    'codcom': {'etichetta': 'Codice nazionale comune (Belfiore)', 'maxlength': 4,
               'hint': 'Quattro caratteri alfanumerici maiuscoli, es. H501', 'pattern': _CODCOM},
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
    principio di verifica_cf: non si spende un token per una richiesta malformata)."""
    for nome in campi:
        pattern = ANNCSU_CAMPI[nome]['pattern']
        if not re.match(pattern, valori.get(nome, '')):
            return f"{ANNCSU_CAMPI[nome]['etichetta']}: valore non valido o mancante."
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


def anncsu_righe(esito, payload):
    """Risposta -> (intestazioni, righe) con le colonne di ANNCSU_COLONNE[esito]."""
    intestazioni = ANNCSU_COLONNE[esito]
    dati = payload.get('data')
    if isinstance(dati, dict):
        dati = [dati]                      # prognaz*: un solo oggetto, la guida mostra un array
    righe = []
    for item in dati or []:
        if isinstance(item, dict):
            righe.append([_valore(item, chiave) for chiave, _ in intestazioni])
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


def anncsu_richiesta(user_id, operazione, campi, valori):
    """POST {target}/{operazione} con body JSON e firma AgID.

    Ritorna (payload, status_code, purposeid, token_id); payload e' None se l'authority non
    rilascia il voucher o se la risposta non e' JSON (stesso sentinel di anpr_get_request).
    I dati di input viaggiano gia' validati da anncsu_valida.
    """
    # Client AgID unico (OpenMSP/agid.py): questa era la nona copia, ora e' una chiamata.
    # `verifica` resta attivo (default True): ANNCSU e' l'unico servizio che non eredita il
    # debito del verify=False (AGENTS.md r2), e la catena di modipa.agenziaentrate.gov.it e'
    # pubblica. `subject` sull'audit e' proprio di ANNCSU: le altre famiglie non lo mandano.
    parametri = AnncsuParametri.objects.get(id=ANNCSU_CONSULTAZIONE['id'])
    emesso = datetime.datetime.utcnow()
    prova, hash_prova = agid.audit(parametri, user_id, emesso=emesso,
                                   subject=parametri.clientid)
    voucher, token_id = agid.voucher(
        parametri, issuer=parametri.clientid,
        asserzione=agid.asserzione_client(parametri, digest=hash_prova,
                                          issuer=parametri.clientid,
                                          subject=parametri.clientid, emesso=emesso))
    if not voucher:
        return None, 502, parametri.purposeid, None   # authority non utilizzabile

    # un 403 con aud divergente e' quasi sempre purposeid/target disallineati, non un guasto:
    # il claim del voucher se lo legge qui, perche' e' una diagnosi di ANNCSU, non del trasporto
    try:
        aud_voucher = str(jwt.decode(voucher, options={'verify_signature': False})
                          .get('aud') or '')
    except jwt.PyJWTError:
        aud_voucher = ''

    body = json.dumps({'req': operazione, **{nome: valori[nome] for nome in campi}})
    digest = agid.digest_body(body)
    response = requests.post(f"{parametri.target}/{operazione}",
                             data=body.encode(agid.CODIFICA),
                             headers=agid.intestazioni(parametri, voucher, prova, digest,
                                                       emesso=emesso),
                             timeout=30)  # verify attivo: la catena di modipa e' pubblica
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if response.status_code == 403:
        payload = anncsu_finalita_divergente(aud_voucher, parametri.target) or payload
    return payload, response.status_code, parametri.purposeid, token_id


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


def _campi_da_rendere(valori):
    """Un input per ogni campo, non uno per operazione (codcom compare in cinque): il JS
    nasconde quelli che non servono, il POST riceve sempre le stesse chiavi."""
    campi = []
    for nome, conf in ANNCSU_CAMPI.items():
        dove = [chiave for chiave, op in ANNCSU_OPERAZIONI.items() if nome in op['campi']]
        campi.append({'nome': nome, **conf, 'valore': valori.get(nome, ''),
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
                body = {nome: valori[nome] for nome in operazione['campi']}
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


def _anncsu_non_attivo(request, url_name):
    """Pagina di servizio per i quattro e-service ancora senza client.

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
    return _anncsu_non_attivo(request, 'anncsu_accessi')


def anncsu_coordinate(request):
    return _anncsu_non_attivo(request, 'anncsu_coordinate')


def anncsu_odonimi(request):
    return _anncsu_non_attivo(request, 'anncsu_odonimi')


def anncsu_visura(request):
    return _anncsu_non_attivo(request, 'anncsu_visura')


def impostazioni_anncsu(request):
    """Una tab per e-service (pattern impostazioni_anpr): i name dei campi sono suffissati
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
            preso = lambda nome: request.POST.get(f'{nome}{riga}') or ''
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
