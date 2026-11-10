# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: request.user e .objects per pyright non esistono)
"""Gate delle tre pagine unificate: domicili_digitali, anpr, istruzione.

Rende i template veri e legge i radio usciti, perche' il bug di ANPR era proprio un nome di
chiave diverso tra vista e template (servizi[].caso contro servizi[].chiave): un test
sull'helper da solo non lo avrebbe visto.

    env/bin/python -m OpenMSP.verifica_selezione_servizi

Nessuna scrittura permanente: i flag di utenti_parametri sono finti e il flag di
servizi_parametri viene spento e poi ripristinato al valore che aveva prima.
"""
import os
import re
import sys
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OpenMSP.settings')

import django

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from impostazioni.context_processors import custom_context  # noqa: E402
from impostazioni.models import ServiziParametri  # noqa: E402
from OpenMSP import anis, anncsu, views  # noqa: E402
from OpenMSP.impostazioni import PERMESSI_UTENTE  # noqa: E402

RIGHE = {
    'tipo_domicilio': (views.domicili_digitali_view,
                       ['ipa', 'inad', 'inipec'],
                       ['ipa_singolo', 'inipec_massivo'],
                       ['ipa', 'inipec'],
                       ['ipa', 'inad', 'registro_imprese']),
    'servizio_anpr': (views.anpr,
                      ['C001', 'C007', 'C015', 'C017', 'C018', 'C020', 'C021'],
                      ['anpr_C001', 'anpr_C015_massivo'],
                      ['C001', 'C015'],
                      ['anpr_c001', 'anpr_c007', 'anpr_c015', 'anpr_c017',
                       'anpr_c018', 'anpr_c020', 'anpr_c021']),
    'servizio_istruzione': (anis.istruzione,
                            ['IFS02', 'IFS03', 'ANIST_FREQ', 'ANIST_TITOLI'],
                            ['anis_IFS02_singolo', 'anist_titoli_massivo'],
                            ['IFS02', 'ANIST_TITOLI'],
                            ['anis_IFS02', 'anis_IFS03', 'anist_frequenze', 'anist_titoli']),
}


class Voce:
    """Riga di utenti_parametri: i flag chiesti sono True, gli altri False."""

    def __init__(self, **bandiere):
        self.__dict__.update(bandiere)

    def __getattr__(self, nome):
        return False


class Tabella:
    """UtentiParametri finta: objects.filter(...).first() restituisce la riga data (o None)."""

    def __init__(self, riga):
        self.objects = self
        self.riga = riga

    def filter(self, **_filtri):
        return self

    def first(self):
        return self.riga


def html_pagina(vista, riga):
    for modulo in (views, anis):
        modulo.UtentiParametri = Tabella(riga)
    richiesta = RequestFactory().get('/')
    richiesta.user = User(username='verificatore', id=1)
    return vista(richiesta).content.decode('utf-8')


def radio_renderizzati(html, nome_form):
    estrazioni = {}
    for radio in re.findall(rf'<input[^>]*name="{nome_form}"[^>]*>', html, re.I):
        valore = re.search(r'value="([^"]*)"', radio)
        if valore is None:
            raise AssertionError(f'radio {nome_form} senza value: il POST non distinguerebbe il servizio')
        estrazioni[valore.group(1)] = 'disabilitato' if 'disabled' in radio else 'attivo'
    return estrazioni


errori = []
for nome_form, (vista, attesi, flag_accesi, abilitati, codici) in RIGHE.items():
    # nessun permesso: la pagina non offre il form, dice di contattare l'amministratore
    html = html_pagina(vista, Voce())
    if radio_renderizzati(html, nome_form):
        errori.append(f'{vista.__name__}: senza alcun permesso il form non va offerto')
    if 'abilitat' not in html.lower():
        errori.append(f"{vista.__name__}: senza permessi manca l'avviso all'operatore")

    # due permessi accesi: la voce c'e' sempre, abilitata solo dove il flag e' attivo
    usciti = radio_renderizzati(html_pagina(vista, Voce(**dict.fromkeys(flag_accesi, True))), nome_form)
    for chiave in attesi:
        voluto = 'attivo' if chiave in abilitati else 'disabilitato'
        if usciti.get(chiave) != voluto:
            errori.append(f"{vista.__name__}/{chiave}: doveva essere {voluto}, "
                          f"e' {usciti.get(chiave)}")

    # eService spento: la voce non deve comparire affatto, nemmeno col permesso acceso
    spento = codici[0]
    # Si ripristina il valore trovato, non True: su un ente che non ha ancora acceso
    # l'eService, una riaccensione incondizionata sarebbe una scrittura permanente.
    comera = bool(ServiziParametri.objects.filter(codice_servizio=spento)
                  .values_list('attivo', flat=True).first())
    ServiziParametri.objects.filter(codice_servizio=spento).update(attivo=False)
    try:
        usciti = radio_renderizzati(
            html_pagina(vista, Voce(**dict.fromkeys(flag_accesi, True))), nome_form)
        if attesi[0] in usciti:
            errori.append(f"{vista.__name__}/{attesi[0]}: con l'eService spento la voce "
                          'non deve comparire')
    finally:
        ServiziParametri.objects.filter(codice_servizio=spento).update(attivo=comera)

    # riga di utenti_parametri assente: la pagina non deve esplodere
    html_pagina(vista, None)


# --- le tre pagine di aggiornamento -------------------------------------------------------
# Stesso scopo del giro di sopra, senza radio di servizi: qui si verifica che le chiavi del
# contesto siano proprio quelle che il template legge. Un nome scritto male, in Django, rende
# una pagina vuota in silenzio: e' esattamente il guasto che questo script e' nato per vedere.
class Attivi:
    """ServiziParametri finta, sempre accesa: il gate dell'ente non deve coprire il controllo."""

    def __init__(self):
        self.objects = self

    def filter(self, *_filtri, **_kw):
        return self

    def values_list(self, *_a, **_kw):
        return self

    def first(self):
        return True


VALIDI = {
    'anncsu_accessi': {'progr_nazionale': '2000449',
                       'operazione_civico': 'R', 'progr_civico': '1370588',
                       'numero': '12', 'metodo': '3'},
    'anncsu_coordinate': {'progr_civico': '1370588',
                          'x': '13.1', 'y': '41.8', 'metodo': '3'},
    'anncsu_odonimi': {'tipo_operazione': 'I', 'dug': 'VIA',
                       'denom_delibera': 'DELLE ORCHIDEE'},
}
# un POST marcio per pagina: non e' piu' codcom, il comune non lo sceglie l'operatore
MARCI = {'anncsu_accessi': {'progr_nazionale': 'X'},
         'anncsu_coordinate': {'metodo': '9'},
         'anncsu_odonimi': {'denom_delibera': ''}}


def html_aggiornamento(vista, flag, post=None, altri=()):
    bandiere = {flag: True}
    bandiere.update(dict.fromkeys(altri, True))
    anncsu.UtentiParametri = Tabella(Voce(**bandiere) if flag else Voce())
    anncsu.ServiziParametri = Attivi()
    richiesta = (RequestFactory().post('/', post) if post else RequestFactory().get('/'))
    richiesta.user = User(username='verificatore', id=1)
    return vista(richiesta).content.decode('utf-8')


# su un ente la cui citta' non e' un colpo unico le tre pagine non possono funzionare affatto:
# meglio dirlo qui che vedere dodici errori incomprensibili
DEFAULT = anncsu.anncsu_comune_ente()
ETICHETTA = anncsu._etichetta_comune(DEFAULT)      # 'Roma (H501)': cosi' lo vede l'operatore
if not DEFAULT:
    errori.append("aggiornamenti: il codice Belfiore non si ricava da dati_ente.citta, "
                  'le tre pagine di aggiornamento non possono funzionare')


for chiave, vista in (('anncsu_accessi', anncsu.anncsu_accessi),
                     ('anncsu_coordinate', anncsu.anncsu_coordinate),
                     ('anncsu_odonimi', anncsu.anncsu_odonimi)):
    specifica, voce = anncsu.ANNCSU_AGGIORNAMENTI[chiave], anncsu.ANNCSU_PER_URL[chiave]
    flag = voce['flag']
    html = html_aggiornamento(vista, '')
    if 'abilitat' not in html.lower():
        errori.append(f'{chiave}: senza permesso manca l\'avviso all\'operatore')
    if 'name="codcom"' in html:
        errori.append(f'{chiave}: senza permesso il form non va offerto')

    html = html_aggiornamento(vista, flag)
    # il foglio di stile e il titolo arrivano solo se si rende la pagina, non il corpo: una
    # render del partial darebbe una pagina nuda e il gate, fino a qui, non lo diceva
    if 'bootstrap-italia' not in html:
        errori.append(f'{chiave}: pagina senza Bootstrap Italia, si rende il partial')
    if f'<title>{voce["etichetta"]}' not in html:
        errori.append(f'{chiave}: titolo della pagina non nel <head>')
    for campo in specifica['campi']:
        if f'name="{campo["nome"]}"' not in html:
            errori.append(f'{chiave}: il campo {campo["nome"]} non arriva al template')
    if specifica['operazione'] and f'name="{specifica["operazione"]}"' not in html:
        errori.append(f"{chiave}: manca la scelta dell'operazione")
    # la * deve stare nel label del campo che il descrittore dice obbligatorio sempre: non basta
    # che il conto torni, un asterisco sul campo sbagliato fuorvia l'operatore
    for campo in specifica['campi']:
        if campo['nome'] == specifica['operazione']:
            continue                                  # reso dal radiogruppo, non come campo
        etichetta = re.search(rf'for="(?:in|sl)_{campo["nome"]}"[^>]*>(.*?)</label>',
                              html, re.S)
        if etichetta is None:
            continue                                  # gia' detto sopra: il campo non c'e'
        stella = re.search(r'<span class="anncsu-obbl"([^>]*)>', etichetta.group(1))
        voluto = campo['req'] == anncsu._SEMPRE
        if stella is None:
            errori.append(f"{chiave}: {campo['nome']} non ha nessuna * nel suo label")
        elif ('hidden' in stella.group(1)) == voluto:  # la stella si vede se non e' hidden
            errori.append(f"{chiave}: {campo['nome']} "
                          + ('nasconde la * che il descrittore vuole'
                             if voluto else 'mostra una * su un campo non obbligatorio'))
    for campo in specifica['campi']:
        if not campo['scelte']:
            continue
        tendina = re.search(rf'<select id="sl_{campo["nome"]}".*?</select>', html, re.S)
        if tendina is None:
            errori.append(f"{chiave}: {campo['nome']} non e' un menu a tendina")
            continue
        for valore, dicitura in campo['scelte']:
            if f'<option value="{valore}"' not in tendina.group(0) or \
                    dicitura[:18] not in tendina.group(0):
                errori.append(f"{chiave}: {campo['nome']} non ha la voce {valore}")
    # il campo dell'operazione esiste anche nel descrittore: se il template lo rende, vince lui
    # sul radiogruppo (stesso name, e il POST tiene l'ultimo arrivato)
    for input in re.findall(rf'<input[^>]*name="{specifica["operazione"]}"[^>]*>', html):
        if 'type="text"' in input:
            errori.append(f"{chiave}: l'operazione ha anche un campo di testo")

    # un POST valido non scrive: rende il riepilogo e chiede la conferma esplicita
    html = html_aggiornamento(vista, flag, dict(VALIDI[chiave], azione='verifica'))
    if 'Conferma' not in html:
        errori.append(f'{chiave}: un POST valido deve chiedere la conferma, non Offerirla')
    if 'alert-danger' in html:
        errori.append(f'{chiave}: il POST di prova risulta invalido: {VALIDI[chiave]}')

    # e un POST marcio deve dirlo, senza arrivare al riepilogo
    html = html_aggiornamento(vista, flag, {**VALIDI[chiave], **MARCI[chiave],
                                           'azione': 'verifica'})
    if 'alert-danger' not in html or 'Conferma e invia' in html:
        errori.append(f'{chiave}: una richiesta malformata non dice niente all\'operatore')

    # nessuna riga di utente: la pagina non deve esplodere
    html_aggiornamento(vista, None)


# --- il campo del comune -------------------------------------------------------------------
# Sulla Consultazione `codcom` si compila per nome (static/js/comuni.js): si verifica il markup
# che la JS aspetta. Sui tre aggiornamenti invece il comune non e' una scelta: viene da
# dati_ente.citta, il campo e' disabilitato e un POST che ne porta un altro deve vedersi
# restituire quello dell'ente.
PAGINE_COMUNI = (('anncsu', 'anncsu_consultazione_comuni', None),
                 ('anncsu_accessi', 'anncsu_accessi', 'A062'),
                 ('anncsu_coordinate', 'anncsu_coordinate', 'A062'),
                 ('anncsu_odonimi', 'anncsu_odonimi', 'A062'))


def input_comune(html):
    colpo = re.search(r'<input[^>]*name="codcom"[^>]*>', html, re.I)
    if colpo is None:
        return None
    return colpo.group(0)


for chiave, flag, inviato in PAGINE_COMUNI:
    html = html_aggiornamento(getattr(anncsu, 'anncsu_consultazione' if chiave == 'anncsu' else chiave),
                              flag,
                              dict(VALIDI[chiave], codcom=inviato, azione='verifica') if inviato
                              else None)
    campo = input_comune(html)
    if '{#' in html or '{%' in html:
        errori.append(f'{chiave}: markup del template nella pagina, '
                      'i commenti multiriga Django non li toglie')
    if campo is None:
        errori.append(f'{chiave}: nessun input name="codcom"')
        continue
    if chiave == 'anncsu':
        if 'data-lookup="comuni"' not in campo:
            errori.append(f'{chiave}: il campo del comune non porta data-lookup, la JS non lo vede')
        if 'maxlength' in campo:
            errori.append(f"{chiave}: il campo del comune ha ancora il maxlength: un nome non ci entra")
    else:
        if 'disabled' not in campo:
            errori.append(f"{chiave}: il campo del comune non e' disabilitato")
        if 'data-lookup' in campo:
            errori.append(f'{chiave}: il campo del comune fisso porta ancora data-lookup')
        if inviato and 'value="A062"' in campo:
            errori.append(f"{chiave}: il codcom del POST vince su quello dell'ente")
        if DEFAULT:
            if f'value="{ETICHETTA}"' not in campo:
                errori.append(f"{chiave}: il comune dell'ente non arriva al campo "
                              f'(voleva value="{ETICHETTA}")')
            if f'value="{DEFAULT}"' in campo:
                errori.append(f'{chiave}: il campo del comune mostra il solo Belfiore, no il nome')




# --- la ricerca del civico nella pagina delle coordinate -------------------------------------
# E' l'unico punto del portale dove una pagina di scrittura legge: i nomi delle due azioni, del
# campo di ricerca e dei data-attributi devono coincidere fra vista, template e JS, e qui sotto
# si chiama davvero l'erogatore (finto) per vedere cosa parte e cosa arriva in logs.
AREE_FINTE = {'data': [{'prognaz': '2000449', 'dug': 'VIA', 'denomuff': 'MARIO CARUCCI'}]}
ACCESSI_FINTE = {'data': [{'prognazacc': '1370588', 'civico': '12', 'esp': 'B', 'specif': 'ROSSO',
                          'coord': '{"type":"Point","coordinates":[12.48, 41.79]}',
                          'quota': '28', 'metodo': '3'},
                         {'prognazacc': '1370589', 'metrico': '300'}]}


def cerca(post, corpo, consultazione=True, accessi=False):
    """Una POST di ricerca con authorita' e log finti: (pagina, corpi inviati, righe di log)."""
    class _Token:
        objects = SimpleNamespace(get=lambda **_kw: SimpleNamespace(
            id=1, kid='k', alg='RS256', typ='JWT', iss='i', sub='s', aud='a', purposeid='p',
            audience='https://erogatore.test/anncsu/v1',
            target='https://erogatore.test/anncsu/v1', baseurlauth='https://auth.test',
            clientid='c', private_key='niente'))

    class _Risposta:
        status_code = 200
        text = ''

        def json(self):
            return corpo

    inviati, loggate = [], []

    def finta(_url, data=None, **_opt):
        inviati.append(data.decode('utf-8') if isinstance(data, bytes) else str(data))
        return _Risposta()

    anncsu.UtentiParametri = Tabella(Voce(anncsu_coordinate=True,
                                          anncsu_consultazione_comuni=consultazione,
                                          anncsu_accessi=accessi))
    anncsu.ServiziParametri = Attivi()
    richiesta = RequestFactory().post('/', post)
    richiesta.user = User(username='verificatore', id=1)
    with mock.patch.object(anncsu, 'AnncsuParametri', _Token()), \
            mock.patch('requests.post', side_effect=finta), \
            mock.patch.object(anncsu, 'agid', SimpleNamespace(
                audit=lambda *a, **kw: ('audit', 'digest'),
                asserzione_client=lambda *a, **kw: 'asserzione',
                voucher=lambda *a, **kw: ('voucher', 'token'),
                digest_body=lambda _corpo: 'digest', intestazioni=lambda *a, **kw: {},
                CODIFICA='UTF-8')), \
            mock.patch.object(anncsu, 'salva_log',
                             lambda _rich, servizio, operazione, **_kw:
                             loggate.append((servizio, operazione))):
        pagina = anncsu.anncsu_coordinate(richiesta).content.decode('utf-8')
    return pagina, inviati, loggate


if anncsu.ANNCSU_AGGIORNAMENTI['anncsu_coordinate'].get('cerca'):
    pagina = html_aggiornamento(anncsu.anncsu_coordinate, 'anncsu_coordinate',
                               altri=('anncsu_consultazione_comuni',))
    if 'Ricerca il civico' not in pagina or 'name="denomparz"' not in pagina:
        errori.append('ricerca: il riquadro della ricerca non c''e\' o non ha il campo del nome')
    # la mappa deve chiamare la stessa funzione del pulsante, non una seconda copia: il vincolo
    # si ferma qui, perche' sul JS nessun test python puo' dire di piu' di cosi'
    if 'window.anncsuUsa = function' not in pagina:
        errori.append('ricerca: il pulsante Usa non e\' una funzione: la mappa non avra\' '
                      'nulla da chiamare e la logica verra\' copiata')
    # Leaflet si paga solo dove serve: 130 KB che le altre due pagine di aggiornamento non
    # devono scaricare per una mappa che non hanno
    # il blocco extra_head del child non deve schiacciare quello di base: li' c'e' marked.min.js
    if 'marked.min.js' not in pagina:
        errori.append('coordinate: il blocco extra_head ha perso il contenuto di base')
    for resa, dove, voluta in ((pagina, 'coordinate', True),
                              (html_aggiornamento(anncsu.anncsu_accessi, 'anncsu_accessi'),
                               'accessi', False),
                              (html_aggiornamento(anncsu.anncsu_odonimi, 'anncsu_odonimi'),
                               'odonimi', False)):
        if ('plugins/leaflet/leaflet.js' in resa) != voluta:
            errori.append('leaflet: caricata male su ' + dove
                          + (' (manca)' if voluta else ' (non serve qua)'))
    # il JS della mappa nessun test python lo esegue: qui si verifica almeno che chiami la
    # funzione del pulsante (non una seconda copia) e che il numero del civico - che viene
    # dall'erogatore - non finisca in un innerHTML
    percorso_js = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'static', 'js', 'anncsu_mappa.js')
    try:
        with open(percorso_js, encoding='utf-8') as sorgente:
            codice_js = sorgente.read()
    except OSError:
        codice_js = ''
        errori.append('mappa: manca static/js/anncsu_mappa.js')
    for voluto in ('window.anncsuUsa', 'progr_nazionale', 'prognazacc', 'tileerror',
                   'textContent', 'tile.openstreetmap.org'):
        if voluto not in codice_js:
            errori.append('mappa: nel JS manca ' + voluto)
    if 'innerHTML' in codice_js:
        errori.append('mappa: il numero dei civici viene dall\'erogatore: testo, non HTML')

    pagina, inviati, loggate = cerca({'azione': 'cerca', 'denomparz': 'via carucci'},
                                     AREE_FINTE)
    if 'name="prognaz"' not in pagina or 'VIA MARIO CARUCCI' not in pagina:
        errori.append('ricerca: il primo passo non rende la scelta del progressivo nazionale')
    if not inviati or 'elencoodonimiprog' not in inviati[0] or DEFAULT not in inviati[0]:
        errori.append('ricerca: la prima chiamata non chiede le aree col comune dell\'ente')
    if loggate != [(anncsu.LOG_RICERCA, 'elencoodonimiprog')]:
        errori.append(f'ricerca: vuole una riga in logs col servizio della ricerca, vista {loggate}')

    pagina, inviati, _ = cerca({'azione': 'accessi', 'prognaz': '2000449'}, ACCESSI_FINTE)
    if 'elencoaccessiprog' not in (inviati[0] if inviati else ''):
        errori.append('ricerca: il secondo passo non chiama elencoaccessiprog')
    if 'anncsu-usa' not in pagina or 'data-usa=' not in pagina:
        errori.append('ricerca: i civici non offrono il pulsante che compila il form')
    # la tabella dei civici non c'e' piu', quindi "longitudine e latitudine separate" si verifica
    # sul blob che scende al JS: e' li' che deve arrivare, non piu' su un attributo del pulsante
    if 'id="anncsu-accessi"' not in pagina:
        errori.append('mappa: gli accessi con un punto non scendono al JS come JSON')
    if '"punto": [41.79, 12.48]' not in pagina:
        errori.append('mappa: nel blob longitudine e latitudine non sono un punto [lat, lon]')
    if '2 accessi, 1 in mappa, 1 senza coordinate' not in pagina:
        errori.append("mappa: il conto fra civici in mappa e senza coordinate non c'e'")
    if 'data-sopprimi="1"' in pagina:
        errori.append('mappa: la soppressione si offre a chi non ha il flag degli accessi')
    pagina = cerca({'azione': 'accessi', 'prognaz': '2000449'}, ACCESSI_FINTE, accessi=True)[0]
    if 'data-sopprimi="1"' not in pagina:
        errori.append('mappa: col flag degli accessi il collegamento alla soppressione manca')

    pagina, inviati, loggate = cerca({'azione': 'cerca', 'denomparz': 'Via Carucci'}, AREE_FINTE,
                                    consultazione=False)
    if 'Ricerca il civico' in pagina or inviati or loggate:
        errori.append('ricerca: senza permesso di Consultazione non si offre e non si chiama')


# --- il ramo elenco: due pulsanti, due destini --------------------------------------------
# Il form dell'elenco e' multipart e l'esito esce come file: e' l'unico punto del portale dove
# una POST non rende una pagina. Va girato qui, perche' nessun test sulla funzione pura si
# accorge di un nome di campo sbagliato fra template e vista.
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

INTESTAZIONE = b'codcom;tipo_operazione;progr_nazionale;dug;denom_delibera\n'
# la prima riga non indica il comune: lo mette il portale; la seconda ne indica uno altr
CSV = INTESTAZIONE + b';I;;VIA;DELLE ORCHIDEE\n' + b'ZZZZ;I;2000449;VIA;TOPA\n'
CSV_PULITO = INTESTAZIONE + b';I;;VIA;DELLE ORCHIDEE\n'


class _Risposta:
    status_code = 200

    def json(self):
        return {'idRichiesta': '1', 'esito': '0', 'messaggio': 'OK', 'dati': []}


def elenco(vista, chiave, azione, csv=CSV):
    """Una POST multipart sulla pagina di aggiornamento, con authorita' e log finti."""
    class _Token:
        objects = SimpleNamespace(get=lambda **kw: SimpleNamespace(
            id=4, kid='k', alg='RS256', typ='JWT', iss='i', sub='s', aud='a',
            purposeid='p', audience='https://erogatore.test/anncsu-aggiornamento-odonimi/v1',
            target='https://erogatore.test/anncsu-aggiornamento-odonimi/v1',
            baseurlauth='https://auth.test', clientid='c', private_key='niente'))

    richiesta = RequestFactory().post('/', {'azione': azione})
    # RequestFactory codifica il multipart ma non popola FILES: lo si attacca a mano, come nei
    # test Django, altrimenti la vista non vede l'allegato e prende il ramo elemento singolo.
    richiesta.FILES['allegato'] = SimpleUploadedFile('a.csv', csv)
    richiesta.user = User(username='verificatore', id=1)
    anncsu.UtentiParametri = Tabella(Voce(anncsu_odonimi=True))
    anncsu.ServiziParametri = Attivi()
    chiamata = []

    def finta_post(url, data=None, headers=None, **opt):
        chiamata.append((url, data))
        return _Risposta()

    with mock.patch.object(anncsu, 'AnncsuParametri', _Token()), \
            mock.patch('requests.post', side_effect=finta_post), \
            mock.patch.object(anncsu, 'agid', SimpleNamespace(
                audit=lambda *a, **kw: ('audit', 'digest'),
                asserzione_client=lambda *a, **kw: 'asserzione',
                voucher=lambda *a, **kw: ('voucher', 'token'),
                digest_body=lambda corpo: 'digest',
                intestazioni=lambda *a, **kw: {},
                CODIFICA='UTF-8')), \
            mock.patch.object(anncsu, 'salva_log'):
        return vista(richiesta), chiamata


risposta, chiamate = elenco(anncsu.anncsu_odonimi, 'anncsu_odonimi', 'simula')
html = risposta.content.decode('utf-8')
if risposta.status_code != 200 or 'DA INVIARE' not in html:
    errori.append('elenco/simula: deve rendere il report riga per riga')
if chiamate:
    errori.append('elenco/simula: deve solo controllare, nessuna chiamata all\'erogatore')
if 'ZZZZ' not in html or 'NON INVIATA' not in html or 'tipo_operazione' not in html:
    errori.append('elenco/simula: una riga marcia deve dirlo')

risposta, chiamate = elenco(anncsu.anncsu_odonimi, 'anncsu_odonimi', 'invia')
if risposta.status_code != 200 or 'non inviato' not in risposta.content.decode('utf-8'):
    errori.append('elenco/invia: con righe non valide non si scrive e va detto')

risposta, chiamate = elenco(anncsu.anncsu_odonimi, 'anncsu_odonimi', 'invia', CSV_PULITO)
if risposta.get('Content-Disposition', '').startswith('attachment'):
    if risposta['Content-Type'].startswith('application/vnd.openxmlformats'):
        if len(chiamate) != 1:
            errori.append(f'elenco/invia: una chiamata per riga attesa, viste '
                 f'{len(chiamate)}')
    else:
        errori.append('elenco/invia: il resoconto non esce come XLSX')
else:
    errori.append('elenco/invia: il resoconto non arriva come file allegato')



# --- i toggle dei permessi -----------------------------------------------------------------
# Un eService senza la sua voce nel foglio dei permessi non e' attivabile a nessun utente: la
# voce di menu resta spenta per sempre, e il doppio gate (invariante 1) si rompe dal lato
# sbagliato. Il nome del campo deve essere un BooleanField di UtentiParametri, perche'
# salva_permessi scrive solo quelli e il template legge con `getattribute`: il nome vecchio
# della Consultazione ('anncsu') non esiste, e il toggle non si accendeva mai.

richiesta_contesti = RequestFactory().get('/')
richiesta_contesti.user = User(username='verificatore', id=1)
toggle = {voce[0]: voce for voce in custom_context(richiesta_contesti)['descrizioni_eservices']}
for sigla, codice in (('anncsu_consultazione_comuni', 'anncsu'),
                      ('anncsu_accessi', 'anncsu_accessi'),
                      ('anncsu_coordinate', 'anncsu_coordinate'),
                      ('anncsu_odonimi', 'anncsu_odonimi'),
                      ('anncsu_visura', 'anncsu_visura')):
    if sigla not in toggle:
        errori.append(f'permessi: manca il toggle di {codice}')
    elif sigla not in PERMESSI_UTENTE:
        errori.append(f'permessi: {sigla} non e' + chr(233) + ' un campo di UtentiParametri, '
                  'il salvataggio lo perde')
    elif toggle[sigla][2] is None:
        errori.append(f'permessi: {codice} senza gruppo, il toggle non entra in nessun riquadro')


print('\n'.join(errori) if errori else
      'ok - le pagine offrono solo gli eService attivi, disabilitano quelli senza permesso,\n'
      '     girano il doppio passo di conferma, validano senza scrivere in modalita elenco,\n'
      '     e hanno tutti il loro toggle nel foglio dei permessi')
sys.exit(1 if errori else 0)
