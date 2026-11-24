# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
from django.shortcuts import render, redirect  # noqa: I001 -- i blocchi sotto sono divisi a mano: framework, modelli, progetto

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import AnprServizi
from impostazioni.models import AnprParametri

from .utils import salva_log
from .utils import svuota_none
from .utils import converti_data
from .verifica_cf import verifica_cf
from . import agid
from . import avanzamento

##from datetime import datetime, date
import datetime

import io
import requests
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from django.http import HttpResponse
from django.http import JsonResponse



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


    purposeid = parametri_anpr.purposeid
    target = parametri_anpr.target
    if id_caso == 8: ##Recupero idANPR
        richiesta = f'{{"idOperazioneClient":"1","criteriRicerca":{{"codiceFiscale":"{id_anpr}"}},' \
            f'"datiRichiesta":{{"dataRiferimentoRichiesta":"{datetime.datetime.utcnow().strftime("%Y-%m-%d")}",' \
            f'"motivoRichiesta":"Verifica_anagrafica","casoUso":"{caso}"}}}}'
    else:
        richiesta = f'{{"idOperazioneClient":"1","criteriRicerca":{{"idANPR":"{id_anpr}"}},' \
            f'"datiRichiesta":{{"dataRiferimentoRichiesta":"{datetime.datetime.utcnow().strftime("%Y-%m-%d")}",' \
            f'"motivoRichiesta":"Verifica_anagrafica","casoUso":"{caso}"}}}}'

    # Client AgID unico (OpenMSP/agid.py): audit -> asserzione(col digest) -> voucher ->
    # firma -> POST. `emesso` e' uno solo per i tre JWT, come nelle copie gia' migratesi.
    # Il token ora passa da requests (prima http.client, senza alcun timeout): verify e'
    # attivo, quindi il TLS dell'autority resta controllato come prima.
    emesso = datetime.datetime.utcnow()
    prova, hash_prova = agid.audit(parametri_anpr, user_ID, emesso=emesso)
    voucher, token_id = agid.voucher(
        parametri_anpr,
        # famiglia firmata: emittente e soggetto sono `clientid`, qui e nel voucher
        issuer=parametri_anpr.clientid,
        asserzione=agid.asserzione_client(parametri_anpr, digest=hash_prova,
                                          issuer=parametri_anpr.clientid,
                                          subject=parametri_anpr.clientid, emesso=emesso))
    if not voucher:
        # authority di ANPR non utilizzabile: stesso sentinel usato per le risposte errate
        return 'ZZZZZZZZZ', 502, purposeid, token_id

    digest = agid.digest_body(richiesta)
    # ponytail: verify=False e' debito ereditato (AGENTS.md r2), non lo tolgo qui perche'
    # cambierebbe il comportamento TLS del handshake AgID gia' a terra: S501 silenziato,
    # upgrade = CA verificata in anpr_parametri.
    response = requests.post(target, data=richiesta.encode(agid.CODIFICA),
                             headers=agid.intestazioni(parametri_anpr, voucher, prova,
                                                       digest, emesso=emesso),
                             verify=False, timeout=30)  # noqa: S501


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
# `codice`/`flag`/`flag_massivo` sono le chiavi che permessi_servizi() (utils.py) usa per il
# doppio gate: tabella servizi_parametri per l'attivazione, utenti_parametri per il permesso.
ANPR_SERVIZI = {
    'C001': {'id_caso': 1, 'codice': 'anpr_c001', 'label': 'C001 - Servizio notifica',
             'titolo': 'Servizio notifica',
             'flag': 'anpr_C001', 'flag_massivo': 'anpr_C001_massivo',
             'log': 'Verifica ANPR - C001 - Notifica'},
    'C007': {'id_caso': 2, 'codice': 'anpr_c007', 'label': 'C007 - Esistenza in vita',
             'titolo': 'Esistenza in vita',
             'flag': 'anpr_C007', 'flag_massivo': 'anpr_C007_massivo',
             'log': 'Verifica ANPR - C007 - Esistenza in vita'},
    'C015': {'id_caso': 3, 'codice': 'anpr_c015', 'label': 'C015 - Generalita',
             'titolo': 'Generalità',
             'flag': 'anpr_C015', 'flag_massivo': 'anpr_C015_massivo',
             'log': 'Verifica ANPR - C015 - Generalità'},
    'C017': {'id_caso': 4, 'codice': 'anpr_c017', 'label': 'C017 - Matrimonio',
             'titolo': 'Matrimonio',
             'flag': 'anpr_C017', 'flag_massivo': 'anpr_C017_massivo',
             'log': 'Verifica ANPR - C017 - Matrimonio'},
    'C018': {'id_caso': 5, 'codice': 'anpr_c018', 'label': 'C018 - Cittadinanza',
             'titolo': 'Cittadinanza',
             'flag': 'anpr_C018', 'flag_massivo': 'anpr_C018_massivo',
             'log': 'Verifica ANPR - C018 - Cittadinanza'},
    'C020': {'id_caso': 6, 'codice': 'anpr_c020', 'label': 'C020 - Residenza',
             'titolo': 'Residenza',
             'flag': 'anpr_C020', 'flag_massivo': 'anpr_C020_massivo',
             'log': 'Verifica ANPR - C020 - Residenza'},
    'C021': {'id_caso': 7, 'codice': 'anpr_c021', 'label': 'C021 - Stato di famiglia',
             'titolo': 'Stato di famiglia',
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


def _soggetti(risposta):
    """I soggetti di una risposta, lista sempre: l'ANPR ne rende uno solo come dizionario e la
    carta deve farne una riga per testa come la tabella. Vuoto se la risposta non e' leggibile."""
    if not isinstance(risposta, dict):
        return []
    soggetti = (risposta.get('listaSoggetti') or {}).get('datiSoggetto') or []
    if isinstance(soggetti, dict):
        soggetti = [soggetti]
    return [s for s in soggetti if isinstance(s, dict)]


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
    def _voce_riga(esito, soggetto=None):
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
        return [_voce_riga(esito_forzato)]
    if not isinstance(risposta, dict):
        return [_voce_riga('Risposta non leggibile')]
    if risposta.get('listaErrori'):
        errori = risposta['listaErrori']
        testo = errori[0] if isinstance(errori, list) and errori else str(errori)
        return [_voce_riga(f"Nessun risultato: {str(testo)[:160]}")]
    soggetti = _soggetti(risposta)
    if not soggetti:
        return [_voce_riga('Nessun risultato: la richiesta non produce alcun soggetto')]
    return [_voce_riga('Trovato', soggetto) for soggetto in soggetti]


# La carta del pulsante `Informazioni` della tabella massiva deve rendere LE STESSE informazioni
# della card della ricerca singola: la riga piatta di `ANPR_COLONNE` non porta il dettaglio della
# residenza (indirizzo, civico, CAP), ne' l'ID scheda, ne' la data di decorrenza, percio' la carta
# si legge dalla risposta cruda. `ANPR_CARTE_SESSIONE` le tiene per codice fiscale: allineare per CF
# e non per indice regge anche se un POST per riga si perde per strada (una carta sconnessa non
# finisce mai sull'anagrafica di un altro cittadino).
ANPR_CARTE_SESSIONE = 'anpr_carte'


def _bocco(risposta, *percorso):
    """Percorso dentro la risposta annidata: `None` a ogni salto (lista = primo elemento), perche'
    un campo assente non e' un errore: la carta lo mostra vuoto, come fa la ricerca singola."""
    nodo = risposta
    for nome in percorso:
        if isinstance(nodo, dict):
            nodo = nodo.get(nome)
        elif isinstance(nodo, list) and nodo:
            nodo = nodo[0]
        else:
            return None
    return nodo


def _testo(valore):
    return str(valore).strip() if valore not in (None, '') else ''


def _voce(soggetto, piatto, etichetta, foglia, *percorso):
    """Una riga `Etichetta: valore`, colta da entrambe le forme che l'ANPR rende: la struttura
    annidata (`generalita.cognome`) o la lista chiave/valore `infoSoggettoEnte` (`cognome`)."""
    return [etichetta, _testo(_bocco(soggetto, *percorso)) or _testo(piatto.get(foglia)) or '—']


def _carta_residenza(soggetto, piatto, decorrenza=False):
    """Il blocco Residenza della card, identico alla ricerca singola: indirizzo in Italia (toponimo,
    civico, interno, CAP, comune, provincia) o localita estera (consolato, stato, anno espatrio)."""
    estera = _bocco(soggetto, 'residenza', 0, 'localitaEstera')
    if estera:
        indirizzo = _bocco(estera, 'indirizzoEstero') or {}
        voci = [['Indirizzo', _testo(_bocco(indirizzo, 'toponimo', 'denominazione')) or '—'],
                ['Località', _testo(_bocco(indirizzo, 'localita', 'descrizioneLocalita')) or '—'],
                ['Consolato', _testo(_bocco(estera, 'consolato', 'descrizioneConsolato')) or '—'],
                ['Stato', _testo(_bocco(indirizzo, 'localita', 'descrizioneStato')) or '—'],
                ['Anno espatrio', _testo(piatto.get('annoEspatrio')) or '—']]
    else:
        indirizzo = _bocco(soggetto, 'residenza', 0, 'indirizzo') or {}
        civico = _bocco(indirizzo, 'numeroCivico') or {}
        lettera = _testo(civico.get('lettera'))
        voci = [
            ['Indirizzo', (_testo(_bocco(indirizzo, 'toponimo', 'specie')) + ' '
                           + _testo(_bocco(indirizzo, 'toponimo', 'denominazioneToponimo'))).strip()
             or _testo(piatto.get('indirizzoResidenza')) or '—'],
            ['Civico', (_testo(civico.get('numero')) + ('/' + lettera if lettera else '')) or '—'],
            ['CAP', _testo(indirizzo.get('cap')) or _testo(piatto.get('capResidenza')) or '—'],
            ['Comune', _testo(_bocco(indirizzo, 'comune', 'nomeComune'))
             or _testo(piatto.get('comuneResidenza')) or '—'],
            ['Provincia', _testo(_bocco(indirizzo, 'comune', 'siglaProvinciaIstat')) or '—'],
        ]
        interno = _testo(_bocco(civico, 'civicoInterno', 'interno1'))
        if interno:
            voci.insert(2, ['Interno', interno])
    if decorrenza:
        voci.append(['Data decorrenza',
                     _testo(_bocco(soggetto, 'residenza', 0, 'dataDecorrenzaResidenza')) or '—'])
    return [['Residenza']] + voci


# Le voci della carta, per caso d'uso: stessi blocchi e stesso ordine delle card di
# `templates/anpr.html`, cosi' chi ha davanti C018 non deve reimparare la schermata sul massivo.
# `coda` sono le etichette di coda, colte da `ANPR_CODA`.
ANPR_CARTE = {
    'C001': (['generalita', 'residenza'], ['Soggetto AIRE', 'Soggetto in vita']),
    'C007': (['generalita', 'vita'], ['Data decesso', 'Soggetto AIRE']),
    'C015': (['generalita'], []),
    'C017': (['generalita', 'matrimonio'], ['Data decesso', 'Soggetto AIRE']),
    'C018': (['cittadinanza', 'generalita'], ['Soggetto AIRE']),
    'C020': (['residenza', 'generalita'], ['Soggetto AIRE']),
    'C021': (['generalita'], ['Legame', 'Data decesso']),
}


def _carta_generalita(soggetto, piatto):
    return [_voce(soggetto, piatto, 'Cognome', 'cognome', 'generalita', 'cognome'),
            _voce(soggetto, piatto, 'Nome', 'nome', 'generalita', 'nome'),
            _voce(soggetto, piatto, 'Sesso', 'sesso', 'generalita', 'sesso'),
            _voce(soggetto, piatto, 'Data Nascita', 'dataNascita', 'generalita', 'dataNascita'),
            ['Luogo nascita', _luogo_nascita(soggetto.get('generalita') or {})
             or _testo(piatto.get('comuneNascita')) or '—'],
            _voce(soggetto, piatto, 'idANPR', 'idANPR', 'identificativi', 'idANPR'),
            _voce(soggetto, piatto, 'ID scheda ANPR', 'idSchedaSoggettoANPR',
                  'generalita', 'idSchedaSoggettoANPR')]


def _si_no(valore):
    return {'S': 'Sì', 'N': 'No'}.get(str(valore).strip().upper(), '—')


def _in_vita(soggetto, piatto):
    """La bandiera `Soggetto in vita`: l'ANSIA la rende come primo valore di `infoSoggettoEnte`
    (la ricerca singola la legge cosi') o come voce `esistenzaInVita`."""
    valore = (_bocco(soggetto, 'infoSoggettoEnte', 0, 'valore')
              or piatto.get('esistenzaInVita')
              or piatto.get('Verifica esistenza in vita'))
    return 'No' if 'N' in str(valore or '') else ('Sì' if valore else '—')


def _carta_voci(soggetto, chiave):
    """Le voci della carta di `soggetto` per il caso d'uso `chiave`. Con un campo che l'ANPR non ha
    reso rende `—` e non lo salta: una cella muta si legge come un guasto della pagina."""
    piatto = _piattino(soggetto)
    blocchi, coda = ANPR_CARTE.get(chiave, ANPR_CARTE['C015'])
    voci = []
    for blocco in blocchi:
        if blocco == 'generalita':
            voci += _carta_generalita(soggetto, piatto)
        elif blocco == 'residenza':
            voci += _carta_residenza(soggetto, piatto, decorrenza=(chiave == 'C020'))
        elif blocco == 'cittadinanza':
            voci.append(_voce(soggetto, piatto, 'Cittadinanza', 'cittadinanza',
                              'cittadinanza', 0, 'descrizioneStato'))
        elif blocco == 'vita':
            voci.append(['Soggetto in vita', _in_vita(soggetto, piatto)])
        elif blocco == 'matrimonio':
            voci += [_voce(soggetto, piatto, 'Data matrimonio', 'dataCelebramento',
                           'matrimonio', 0, 'dataCelebramento'),
                     _voce(soggetto, piatto, 'Registrato a', 'comune',
                           'matrimonio', 0, 'atto', 'comune', 'nomeComune')]
    for etichetta in coda:
        if etichetta == 'Data decesso':
            voci.append(_voce(soggetto, piatto, etichetta, 'dataDecesso', 'generalita', 'dataDecesso'))
        elif etichetta == 'Soggetto AIRE':
            voci.append([etichetta, _si_no(piatto.get('soggettoAIRE'))])
        elif etichetta == 'Soggetto in vita':
            voci.append([etichetta, _in_vita(soggetto, piatto)])
        elif etichetta == 'Legame':
            legame = (_bocco(soggetto, 'legameSoggetto', 'codiceLegame')
                      or piatto.get('codiceLegame') or '')
            voci.append([etichetta, dict(ANPR_PARENTELA).get(str(legame), str(legame)) or '—'])
    return voci


def carte_da_risposta(risposta, chiave):
    """Una carta per soggetto restituito (lo stato di famiglia ne rende piu' d'uno), o `[]` se la
    risposta non e' leggibile: in quel caso la carta si limita a CF ed esito della riga."""
    if chiave not in ANPR_SERVIZI or risposta.get('listaErrori'):
        return []
    return [_carta_voci(s, chiave) for s in _soggetti(risposta)]


# Il massivo della pagina unificata sale sul filo delle card (`OpenMSP/avanzamento.py`): un POST
# per codice, la carta dice su quale codice sei fermo, la tabella la rende il server a giro finito.
# `ANPR_GIRO_SESSIONE` e' il caso d'uso in corso: `risposta_riga` poppa lo stato del filo prima di
# chiamare il riepilogo, e il nome di audit del riepilogo dipende da quel caso (la pagina logs non
# si deve biforcare).
ANPR_GIRO_SESSIONE = 'anpr_giro'


def _accoda_carte(request, cf, carte):
    """Le carte di un codice in sessione, chiave per chiave: un CF riscritto (ripetizione dello
    stesso codice nel file) sostituisce le sue carte, non si somma."""
    if not carte:
        return
    carte_sessione = dict(request.session.get(ANPR_CARTE_SESSIONE) or {})
    carte_sessione[cf] = carte
    request.session[ANPR_CARTE_SESSIONE] = carte_sessione


def _riga_anpr(request, cf, stato=None):
    """Una riga dell'ANPR massiva: `(righe, ultimo, errore)`, `righe` gia' appiattite su ANPR_COLONNE.

    Due interrogazioni per codice, identiche al ciclo che stava in `views.anpr`: idANPR (caso 8) e
    il caso d'uso scelto, che viene da `stato['chiave']` (la sessione, mai dal client). `verifica_cf`
    scarta prima di spendere il secondo voucher (invariante 3) e `logs` riceve una riga per codice
    sola, coi metadati dell'ultima chiamata (invarianti 2 e 8). `ultimo` e' il codice chiesto: la
    carta deve dire SU QUALE codice sei fermo, il dato lo dice la tabella. La carta di dettaglio
    della riga viene dalla risposta cruda (`carte_da_risposta`), non dalla riga piatta.
    """
    chiave = (stato or {}).get('chiave') or ''
    conf = ANPR_SERVIZI.get(chiave)
    if not conf:
        errore = "Nessun caso d'uso in corso: riavviare la ricerca"
        return anpr_righe(cf, None, errore), cf, errore
    nome_log = conf['log'] + ' Massivo'
    if verifica_cf(cf) not in (1, 2):
        salva_log(request.user, nome_log, "Verificato utente " + cf)
        return (anpr_righe(cf, None, 'Codice fiscale non corretto'), cf,
                'Codice fiscale non corretto')
    id_anpr, resp, purp, tok = anpr_get_request(request.user.username, cf, 8)
    if id_anpr == 'ZZZZZZZZZ':
        righe, errore = anpr_righe(cf, None, 'Soggetto non presente in ANPR'), 'Soggetto non presente in ANPR'
    else:
        risposta, resp, purp, tok = anpr_get_request(request.user.username, id_anpr, conf['id_caso'])
        risposta = converti_data(risposta)
        righe, errore = anpr_righe(cf, risposta), ''
        _accoda_carte(request, cf, carte_da_risposta(risposta, chiave))
    salva_log(request.user, nome_log, "Verificato utente " + cf,
              purposeid=purp, resp_status=resp, token_id=tok)
    return righe, cf, errore


def _fine_anpr(request, fatte):
    conf = ANPR_SERVIZI.get(request.session.get(ANPR_GIRO_SESSIONE) or '')
    nome_log = (conf['log'] if conf else 'Verifica ANPR') + ' Massivo'
    salva_log(request.user, nome_log,
              "Fine elaborazione CSV - n. " + str(fatte) + " CF")


def anpr_massiva_riga(request):
    """Una riga dell'ANPR massiva in corso: l'indice dal navigatore, caso d'uso e codici in sessione.

    `/anpr/riga/` e' una URL sola per sette casi d'uso, percio' il gate (invariante 1) non puo' essere
    un nome fisso: e' il `flag_massivo` del caso che sta in sessione, come sui domicili digitali.
    """
    chiave = (request.session.get(avanzamento.STATO_SESSIONE) or {}).get('chiave')
    if chiave not in ANPR_SERVIZI:
        return JsonResponse({'errore': 'Nessuna estrazione ANPR in corso'}, status=400)
    return avanzamento.risposta_riga(request, ANPR_SERVIZI[chiave]['flag_massivo'],
                                    _riga_anpr, _fine_anpr)


# Le cinque colonne fisse della tabella massiva: sono le stesse per tutti e sette i casi d'uso,
# cosi' l'operatore legge la tabella senza dover sapere cosa restituisce C017 e cosa C021. Il
# dato specifico della risposta interrogata va nella carta del pulsante `Informazioni`, che rende
# tutte le colonne di ANPR_COLONNE con un valore (stessa lista anche nell'export CSV).
ANPR_TABELLA = ('CF', 'Esito', 'Cognome', 'Nome', 'Data nascita')


def tabella_massiva(righe, carte=None):
    """Le righe piatte di `multi_data` vestite per la pagina: `(celle, dettagli)`.

    `multi_data` resta la lista di liste che `anpr_export_excel` si aspetta (invariante 5): la
    vestizione vive quanto il render. Le righe che liste non sono (la chiave della sessione e'
    condivisa fra i servizi: un giro INAD fatto prima non deve buttare giu' la pagina) si scartano.
    `dettagli` e' il dizionario che il template rende con `json_script`: unica fonte della carta
    e dell'export CSV, cosi' le colonne finite fuori dalla tabella non si perdono. `carte` e' il
    `{CF: [voci]}` di `ANPR_CARTE_SESSIONE`: la carta di una riga e' la terza voce del blob,
    allineata per codice fiscale; se manca (CF scartato prima della chiamata, o estrazione di prima
    che le carte non le lasciava) la carta si riduce a CF ed esito.
    """
    righe = [r for r in righe if isinstance(r, (list, tuple)) and len(r) == len(ANPR_COLONNE)]
    celle = []
    dettagli = {'colonne': list(ANPR_COLONNE),
                'righe': [dict(zip(ANPR_COLONNE, r, strict=True)) for r in righe],
                'carte': []}
    consumate = {}
    for indice, riga in enumerate(righe):
        v = dict(zip(ANPR_COLONNE, riga, strict=True))
        celle.append({
            'cf': v['CF'], 'esito': v['Esito'], 'cognome': v['Cognome'],
            'nome': v['Nome'], 'nascita': v['Data nascita'],
            'classe': 'table-success' if v['Esito'] == 'Trovato' else 'table-danger',
            'indice': indice,
        })
        sue = (carte or {}).get(v['CF']) or []
        consumate[v['CF']] = n = consumate.get(v['CF'], 0) + 1
        dettagli['carte'].append({'cf': v['CF'], 'esito': v['Esito'],
                                 'voci': sue[n - 1] if n <= len(sue)
                                 else [['CF', v['CF']], ['Esito', v['Esito']]]})
    return celle, dettagli


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
