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
    'anncsu_accessi': {'codcom': 'A062', 'progr_nazionale': '2000449',
                       'operazione_civico': 'R', 'progr_civico': '1370588',
                       'numero': '12', 'metodo': '3'},
    'anncsu_coordinate': {'codcom': 'A062', 'progr_civico': '1370588',
                          'x': '13.1', 'y': '41.8', 'metodo': '3'},
    'anncsu_odonimi': {'codcom': 'A062', 'tipo_operazione': 'I', 'dug': 'VIA',
                       'denom_delibera': 'DELLE ORCHIDEE'},
}


def html_aggiornamento(vista, flag, post=None):
    anncsu.UtentiParametri = Tabella(Voce(**{flag: True}) if flag else Voce())
    anncsu.ServiziParametri = Attivi()
    richiesta = (RequestFactory().post('/', post) if post else RequestFactory().get('/'))
    richiesta.user = User(username='verificatore', id=1)
    return vista(richiesta).content.decode('utf-8')


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

    # un POST valido non scrive: rende il riepilogo e chiede la conferma esplicita
    html = html_aggiornamento(vista, flag, dict(VALIDI[chiave], azione='verifica'))
    if 'Conferma' not in html:
        errori.append(f'{chiave}: un POST valido deve chiedere la conferma, non Offerirla')
    if 'alert-danger' in html:
        errori.append(f'{chiave}: il POST di prova risulta invalido: {VALIDI[chiave]}')

    # e un POST marcio deve dirlo, senza arrivare al riepilogo
    html = html_aggiornamento(vista, flag, dict(VALIDI[chiave], codcom='X'))
    if 'alert-danger' not in html or 'Conferma e invia' in html:
        errori.append(f'{chiave}: una richiesta malformata non dice niente all\'operatore')

    # nessuna riga di utente: la pagina non deve esplodere
    html_aggiornamento(vista, None)



# --- il ramo elenco: due pulsanti, due destini --------------------------------------------
# Il form dell'elenco e' multipart e l'esito esce come file: e' l'unico punto del portale dove
# una POST non rende una pagina. Va girato qui, perche' nessun test sulla funzione pura si
# accorge di un nome di campo sbagliato fra template e vista.
from types import SimpleNamespace  # noqa: E402
from unittest import mock  # noqa: E402

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

INTESTAZIONE = b'codcom;tipo_operazione;progr_nazionale;dug;denom_delibera\n'
CSV = INTESTAZIONE + b'A062;I;;VIA;DELLE ORCHIDEE\n' + b'H501;X;2000449;VIA;TOPA\n'
CSV_PULITO = INTESTAZIONE + b'A062;I;;VIA;DELLE ORCHIDEE\n'


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
if 'H501' not in html or 'NON INVIATA' not in html or 'tipo_operazione' not in html:
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
