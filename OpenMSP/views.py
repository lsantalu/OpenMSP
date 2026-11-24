# pyright: reportAttributeAccessIssue=false
# pyright: reportIncompatibleVariableOverride=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
####INUTILI
import json                                 # noqa: I001  (gruppi separati a mano: stile del repo, v. tests.py)

import requests
from django import forms

####FINE INUTILI
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

##from zeep import Client
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from two_factor.views import LoginView as TwoFactorLoginView

from impostazioni.models import (
    GruppiParametri,
    IpaParametri,
    ServiziParametri,
    UtentiParametri,
)

from . import avanzamento
from .anis import anis_verifica_utente
from .anpr import (
    ANPR_GIRO_SESSIONE,
    ANPR_CARTE_SESSIONE,
    ANPR_PARENTELA,
    ANPR_SERVIZI,
    _fine_anpr,
    _riga_anpr,
    anpr_get_request,
    tabella_massiva,
)
from .inad import (_fine_inad, _riga_inad, estrai_mail, inad_get_bearer,
                   inad_verifica_utente)
from .ipa import _fine_ipa, _riga_ipa, ipa_codice
from .registro_imprese import (
    _fine_inipec,
    _riga_inipec,
    registro_imprese_get_bearer,
    registro_imprese_verifica_utente,
)
from .utils import (
    cf_da_file,
    converti_data,
    json_da_response,
    permessi_servizi,
    salva_log,
)
from .verifica_cf import verifica_cf, verifica_cf_azienda


def home(request):
    service_status = {
        servizio.codice_servizio: bool(servizio.attivo)
        for servizio in ServiziParametri.objects.all()
    }

    user_permissions = None
    if request.user.is_authenticated:
        user_permissions = UtentiParametri.objects.filter(id=request.user.id).first()

    home_cards = [
        {
            'title': 'Domicili Digitali',
            # tutti e tre i link puntano alla pagina unificata (come ANPR e ANIS): il primo
            # servizio attivo e consentito vince, e il flag massivo conta quanto il singolo, cosi'
            # la card e il megamenu dicono la stessa cosa (invariante 1)
            'service_links': [
                ('ipa', 'domicili_digitali', ('ipa_singolo', 'ipa_massivo')),
                ('inad', 'domicili_digitali', ('inad_singolo', 'inad_massivo')),
                # non esiste una riga 'inipec' in servizi_parametri: quella che accende INI-PEC e'
                # ancora la stessa usata prima, il gate sull'utente resta sui flag inipec
                ('registro_imprese', 'domicili_digitali', ('inipec_singolo', 'inipec_massivo')),
            ],
            'image': 'images/domicio_digitale.png',
            'alt': 'Domicili Digitali',
            'description': 'Accedi ai domicili digitali iPA, INAD e INI-PEC in modo semplice e veloce.',
        },
        {
            'title': 'Interrogazioni ANPR',
            # tutti i link puntano alla pagina unificata: il primo caso attivo e consentito vince,
            # e il flag massivo conta quanto il singolo (un operatore con solo il massivo deve
            # poter arrivare al servizio dalla home)
            'service_links': [
                ('anpr_c001', 'anpr', ('anpr_C001', 'anpr_C001_massivo')),
                ('anpr_c007', 'anpr', ('anpr_C007', 'anpr_C007_massivo')),
                ('anpr_c015', 'anpr', ('anpr_C015', 'anpr_C015_massivo')),
                ('anpr_c017', 'anpr', ('anpr_C017', 'anpr_C017_massivo')),
                ('anpr_c018', 'anpr', ('anpr_C018', 'anpr_C018_massivo')),
                ('anpr_c020', 'anpr', ('anpr_C020', 'anpr_C020_massivo')),
                ('anpr_c021', 'anpr', ('anpr_C021', 'anpr_C021_massivo')),
            ],
            'image': 'images/anpr.png',
            'alt': 'ANPR',
            'description': 'Verifica i dati anagrafici direttamente dall’Anagrafe Nazionale della Popolazione Residente.',
        },
        {
            'title': 'Comunicazioni App IO',
            'service_links': [('app_io', 'app_io_singolo', ('app_io_singolo',))],
            'image': 'images/app_io.png',
            'alt': 'App IO',
            'description': 'Invia comunicazioni direttamente tramite l’applicazione ufficiale della PA.',
        },
        {
            'title': 'Registro Imprese',
            # un link per modalita', come la card ANPR: vince il primo attivo e consentito,
            # cosi' la card e il megamenu dicono la stessa cosa (invariante 1)
            'service_links': [('registro_imprese', 'registro_imprese', ('registro_imprese',)),
                              ('registro_imprese', 'registro_imprese_massivo', ('registro_imprese_massivo',))],
            'image': 'images/registro_imprese.png',
            'alt': 'CCIAA',
            'description': 'Consulta il Registro delle Imprese e ottieni informazioni aggiornate.',
        },
        {
            'title': 'ANIS e ANIST',
            # tutti e quattro i link puntano alla pagina unificata: il primo servizio attivo e
            # consentito vince, e il flag massivo conta quanto il singolo
            'service_links': [
                ('anis_IFS02', 'istruzione', ('anis_IFS02_singolo', 'anis_IFS02_massivo')),
                ('anis_IFS03', 'istruzione', ('anis_IFS03_singolo', 'anis_IFS03_massivo')),
                ('anist_frequenze', 'istruzione', ('anist_frequenze_singolo', 'anist_frequenze_massivo')),
                ('anist_titoli', 'istruzione', ('anist_titoli_singolo', 'anist_titoli_massivo')),
            ],
            'image': 'images/anis_anist.png',
            'alt': 'ANIS e ANIST',
            'description': 'Interrogazione anagrafe istruzione.',
        },
        {
            'title': 'ANNCSU',
            # un link per e-service, come la card ANPR: vince il primo attivo e consentito,
            # cosi' card e megamenu dicono la stessa cosa (invariante 1). Gli ultimi quattro
            # sono ancora senza client: la pagina risponde, ma rende 'servizio non ancora attivo'.
            'service_links': [
                ('anncsu', 'anncsu', ('anncsu_consultazione_comuni',)),
                ('anncsu_accessi', 'anncsu_accessi', ('anncsu_accessi',)),
                ('anncsu_coordinate', 'anncsu_coordinate', ('anncsu_coordinate',)),
                ('anncsu_odonimi', 'anncsu_odonimi', ('anncsu_odonimi',)),
                ('anncsu_visura', 'anncsu_visura', ('anncsu_visura',)),
            ],
            # icona dedicata in static/images/: in dev Django serve gli statici dal finder, in
            # deploy passa da collectstatic (lo fa gia' l'update script) prima di rendere la home
            'image': 'images/anncsu.png',
            'alt': 'ANNCSU',
            'description': 'Numeri civici e odonimi nell’Archivio Nazionale delle Strade Urbane.',
        },
        {
            'title': 'INPS',
            'service_links': [
                ('inps_isee', 'inps_isee', ('inps_isee',)),
                ('inps_durc', 'inps_durc_singolo', ('inps_durc_singolo',)),
            ],
            'image': 'images/inps.png',
            'alt': 'INPS',
            'description': 'Accedi a ISEE, DURC e altri certificati erogati dall’INPS.',
        },
    ]

    for card in home_cards:
        active_link = ''
        for service_code, url_name, permission_fields in card['service_links']:
            if not service_status.get(service_code, False):
                continue
            if user_permissions and not any(getattr(user_permissions, field, False) for field in permission_fields):
                continue
            active_link = url_name
            break
        card['url_name'] = active_link
        card['enabled'] = bool(active_link)

    return render(request, 'home.html', {'home_cards': home_cards})


class login_2fa(TwoFactorLoginView):
    template_name = 'registration/login_2fa.html'


def Api_C001(codice_fiscale, api_key):
    return anpr_get_request(api_key, anpr_get_request(api_key, codice_fiscale,7), 1)

def Api_C015(codice_fiscale, api_key):
    return anpr_get_request(api_key, anpr_get_request(api_key, codice_fiscale,7), 2)

def Api_C017(codice_fiscale, api_key):
    return anpr_get_request(api_key, anpr_get_request(api_key, codice_fiscale,7), 3)

def Api_C018(codice_fiscale, api_key):
    return anpr_get_request(api_key, anpr_get_request(api_key, codice_fiscale,7), 4)

def Api_C020(codice_fiscale, api_key):
    return anpr_get_request(api_key, anpr_get_request(api_key, codice_fiscale,7), 5)

def Api_C021(codice_fiscale, api_key):
    return anpr_get_request(api_key, anpr_get_request(api_key, codice_fiscale,7), 6)

def Api_inad(codice_fiscale, api_key):
    """Ritorna (dato, meta): meta contiene cio' che serve a salva_log, ed e' vuoto se
    l'erogatore non e' stato interrogato (CF scartato a priori). L'audit lo fa la vista."""
    bearer, token_id = inad_get_bearer()
    correttezza_cf = verifica_cf(codice_fiscale)
    if correttezza_cf == 1:
        parsed_output, status, purp_id = inad_verifica_utente(codice_fiscale, bearer)
        return estrai_mail(json.dumps(parsed_output)), {"purposeid": purp_id, "resp_status": status, "token_id": token_id}
    if correttezza_cf == 2:
        # Non e' un codice sbagliato: e' un divieto d'interrogazione, e la tabella lo giallo
        # (stesso testo della pagina gemella inad_massiva).
        return "Codice fiscale di persona minorenne", {}
    return "Codice fiscale non corretto", {}

def Api_ipa(codice_fiscale, api_key):
    ipa_parametri = IpaParametri.objects.get(id=1)
    auth_id = ipa_parametri.auth_id

    verifica_cf_ipa = verifica_cf_azienda(codice_fiscale)
    if verifica_cf_ipa == 1:
        url = "https://www.indicepa.gov.it:443/ws/WS23DOMDIGCFServices/api/WS23_DOM_DIG_CF"
        payload = {
            "AUTH_ID": auth_id,
            "CF": codice_fiscale
            }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
            }
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            temp_data = json_da_response(response)
            if 'data' in temp_data and temp_data['data']:
                codice_ipa = temp_data['data'][0]['cod_amm']
                response_pec = ipa_codice(auth_id, codice_ipa)
                if response_pec.status_code == 200:
                    risultato = response_pec.json()
                    if 'data' in risultato and isinstance(risultato['data'], list) and len(risultato['data']) > 0:
                        return risultato['data'][0].get('pec', 'Domicilio non trovato').lower()
                    elif 'data' in risultato and isinstance(risultato['data'], dict):
                        return risultato['data'].get('pec', 'Domicilio non trovato').lower()
            return "Domicilio digitale non trovato"
    return "Codice fiscale non corretto"

def Api_ini_pec(codice_fiscale, api_key):
    """Ritorna (dato, meta) come Api_inad: prima il ramo con CF non valido non aveva return
    e lasciava None (shim difettoso)."""
    bearer, token_id = registro_imprese_get_bearer()
    correttezza_cf_azienda = verifica_cf_azienda(codice_fiscale)
    if correttezza_cf_azienda == 1:
        elenco_dati_registro, status_code, purp_id, tok_id = registro_imprese_verifica_utente(codice_fiscale, bearer, token_id)
        if elenco_dati_registro:
            dd = elenco_dati_registro.get('blocchi_impresa', {}).get('dati_identificativi', {}).get('indirizzo_posta_certificata', 'Dato non disponibile')
        else:
            dd = "Ditta non presente nel Registro Imprese"
        return dd.lower(), {"purposeid": purp_id, "resp_status": status_code, "token_id": tok_id}
    return "Codice fiscale non corretto", {}


@csrf_exempt
@api_view(['POST'])
def pdnd_gateway_service(request):
    # Controlla se il payload contiene le chiavi richieste
    try:
        chiave_autenticazione = request.data['chiave_autenticazione']
        tipo_servizio = request.data['tipo_servizio']
        codice_fiscale = request.data['codice_fiscale']
    except KeyError:
        return Response({"error": "Parametri mancanti"}, status=status.HTTP_400_BAD_REQUEST)

    # Puoi aggiungere una logica per validare la chiave di autenticazione qui
    if chiave_autenticazione != "CHIAVE1234":
        return Response({"error": "Chiave di autenticazione non valida"}, status=status.HTTP_403_FORBIDDEN)


    if tipo_servizio == "C001" :
        risultato = Api_C001(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "C015" :
        risultato = Api_C015(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "C017" :
        risultato = Api_C017(codice_fiscale, chiave_autenticazione)
    risultato = None
    if tipo_servizio == "C018" :
        risultato = Api_C018(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "C020" :
        risultato = Api_C020(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "C021" :
        risultato = Api_C021(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "inad" :
        risultato, _meta = Api_inad(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "ipa" :
        risultato = Api_ipa(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "ini_pec" :
        risultato, _meta = Api_ini_pec(codice_fiscale, chiave_autenticazione)

    if risultato is None:
        # nessun tipo_servizio riconosciuto: prima era un NameError (500) su un endpoint pubblico
        return Response({"error": f"tipo_servizio non supportato: {tipo_servizio}"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(risultato, status=status.HTTP_200_OK)



def profilo_utente(request):
    return render(request, 'profilo_utente.html' )


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('impostazioni_utenti')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def logout(request):
    ### trova id utente da request
    utente = request.user
    if utente.is_authenticated:
        utente_attivo = get_object_or_404(User, pk=utente.pk)
        if not utente_attivo.is_active :
            messages.error(request, 'L\'utente è disabilitato. Contatta l\'amministratore di sistema')
    auth_logout(request)
    return redirect('home')


# La pagina unificata ANPR vive qui per storia; la tabella dei casi d'uso e il client AgID sono
# in OpenMSP/anpr.py, insieme all'export Excel che rilegge session['multi_data'].
def anpr(request):
    """Un form, sette casi d'uso, singola o massiva. La scelta del servizio e il caricamento del
    file seguono la stessa logica della pagina dei domicili digitali: doppio gate (invariante 1)
    ri-validato nel POST, un caso d'uso spento in servizi_parametri non viene offerto, uno attivo
    ma senza permesso su utenti_parametri viene offerto disabilitato."""
    utente = (UtentiParametri.objects.filter(id=request.user.id).first()
              if request.user.is_authenticated else None)
    servizi, permessi, utente_abilitato = permessi_servizi(utente, ANPR_SERVIZI)

    data = None
    righe = []
    carte = {}
    error = None
    totale = 0
    servizio_scelto = None
    modalita_scelta = None
    if request.method == 'GET' and request.GET.get('eseguito'):
        # Il navigatore torna qui quando ha finito i giri: la tabella la rende il server, cosi' non
        # c'e' innerHTML di mezzo e la pagina e' la stessa del giro senza JavaScript.
        righe = request.session.get('multi_data') or []
        carte = request.session.get(ANPR_CARTE_SESSIONE) or {}
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

    if request.method == 'POST':
        servizio_scelto = request.POST.get('servizio_anpr') or None
        modalita_scelta = request.POST.get('modalita') or None
        conf = ANPR_SERVIZI.get(servizio_scelto or '')
        if (conf is None or modalita_scelta not in ('singola', 'massiva')
                or not permessi.get(servizio_scelto, {}).get(modalita_scelta, False)):
            error = 'Non sei abilitato per questa tipologia di ricerca.'
        else:
            errore_file = ''
            if modalita_scelta == 'singola':
                codici = [request.POST.get('input_CF', '').strip().upper()]
            else:
                # `codici_da_file` e' l'helper del filo: stessa lettura (colonna A di CSV/XLSX) e un
                # errore che dice se il file e' illeggibile o solo senza codici
                codici, errore_file = avanzamento.codici_da_file(request.FILES.get('file_massivo'))

            if errore_file:
                salva_log(request.user, conf['log'] + ' Massivo', errore_file)
                error = errore_file
            elif not codici or codici == ['']:
                error = ('Inserisci un codice fiscale.' if modalita_scelta == 'singola'
                         else 'Nessun codice nel file: la colonna (A) deve contenere i codici '
                              'fiscali.')
            elif modalita_scelta == 'singola':
                # identico alle sette viste dedicate: stessa forma di `data`, stesso nome di audit
                cf = codici[0]
                data = [cf]
                if verifica_cf(cf) in (1, 2):
                    id_anpr = anpr_get_request(request.user.username, cf, 8)[0]
                    res_data, status, purp_id, tok_id = anpr_get_request(
                        request.user.username, id_anpr, conf['id_caso'])
                    data.append(res_data)
                    data = converti_data(data)
                    salva_log(request.user, conf['log'], "Verificato utente " + cf,
                              purposeid=purp_id, resp_status=status, token_id=tok_id)
                else:
                    data.append("Codice fiscale non corretto")
                    salva_log(request.user, conf['log'], "Verificato utente " + cf)
            else:
                # Il giro dei codici lo comanda il navigatore (`anpr_massiva_riga`), percio' la carta
                # dell'overlay dice il vero avanzamento e non un cerchio che gira. Il caso d'uso va in
                # sessione DENTRO lo stato del filo: e' l'unica cosa che il POST per riga legge per
                # sapere che permesso chiedere (invariante 1), che worker chiamare e che nome mettere
                # nel riepilogo; dal client viene solo l'indice (invariante 8).
                request.session[ANPR_GIRO_SESSIONE] = servizio_scelto
                request.session[ANPR_CARTE_SESSIONE] = {}
                if request.POST.get('js'):
                    avanzamento.avvia(request, codici)
                    stato = request.session[avanzamento.STATO_SESSIONE]
                    stato['chiave'] = servizio_scelto
                    request.session[avanzamento.STATO_SESSIONE] = stato
                    totale = len(codici)
                else:
                    # senza JavaScript: un giro solo, stesso worker del navigatore
                    righe = avanzamento.esegui_tutto(request, codici, _riga_anpr, _fine_anpr,
                                                     stato={'chiave': servizio_scelto})
                    carte = request.session.get(ANPR_CARTE_SESSIONE) or {}

    righe, dettagli = tabella_massiva(righe, carte)
    return render(request, 'anpr.html', {
        'utente_abilitato': utente_abilitato,
        'servizi': servizi,
        'permessi': permessi,
        'data': data,
        'righe': righe,
        'dettagli': dettagli,
        'totale': totale,
        'error': error,
        'servizio_scelto': servizio_scelto,
        'modalita_scelta': modalita_scelta,
        'cessazione': cessazione_matrimonio_choices,
        'parentela': ANPR_PARENTELA,
    })


def debug_openmsp(request):
    servizi_impostazioni = ServiziParametri.objects.all()
    gruppi_parametri = GruppiParametri.objects.all()

    if request.method == 'POST':
        cf = request.POST.get('input_CF')
        id_servizio = request.POST.get('sceltaServizio')
        data = ""
        if id_servizio == '1': #OK ipa
            ipa_parametri = IpaParametri.objects.get(id=4)
            auth_id = ipa_parametri.auth_id
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
                if temp_data.get('data') is not None :
                    codice_ipa = temp_data['data'][0]['cod_amm']
                    response = ipa_codice(auth_id, codice_ipa)
                    if response.status_code == 200:
                        data_temp = response.json()
                    else:
                        data_temp = {"error": f"Request failed with status code {response.status_code}"}
                else:
                    data_temp = "CF non trovato"
            else:
                data_temp = "Codice fiscale non corretto"
            salva_log(request.user,"Debug verifica IndicePA", "Debug verificato domicilio ente " + cf )
            data = json.dumps(data_temp, indent=1)
        elif id_servizio == '2': #OK inad
            bearer = inad_get_bearer()
            data_temp = (inad_verifica_utente(cf, bearer))
            data = json.dumps(data_temp, indent=4)
        elif id_servizio == '3': #OK anpr c001
            data_temp = []
            data_temp.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 1))
            data = json.dumps(data_temp, indent=2)
        elif id_servizio == '4':  #OK anpr c001
            data_temp = []
            data_temp.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 2))
            data = json.dumps(data_temp, indent=2)
        elif id_servizio == '5':  #OK anpr c017
            data_temp = []
            data_temp.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 3))
            data = json.dumps(data_temp, indent=2)
        elif id_servizio == '6':  #OK anpr c018
            data_temp = []
            data_temp.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 4))
            data = json.dumps(data_temp, indent=2)
        elif id_servizio == '7':  #OK anpr c020
            data_temp = []
            data_temp.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 5))
            data = json.dumps(data_temp, indent=2)
        elif id_servizio == '8':  #OK anpr c021
            data_temp = []
            data_temp.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 6))
            data = json.dumps(data_temp, indent=2)
        elif id_servizio == '9':  #OK anpr c030
            data_temp = []
            data_temp.append(anpr_get_request(request.user.username, cf,7))
            data = json.dumps(data_temp, indent=2)
        elif id_servizio == '10':  #OK registro imprese
            data_temp = []
            # get_bearer restituisce (bearer, token_id) e verifica_utente ne vuole entrambi
            bearer, token_id = registro_imprese_get_bearer()
            elenco_dati_registro, status_code, purp_id, tok_id = registro_imprese_verifica_utente(cf, bearer, token_id)
            data_temp.append(elenco_dati_registro)
            data = json.dumps(data_temp, indent=1)
        elif id_servizio == '11':  #mit patenti
            data = "Hai scelto il numero 11"
        elif id_servizio == '12':  #mit cude
            data = "Hai scelto il numero 12"
        elif id_servizio == '13':  #mit veicoli
            data = "Hai scelto il numero 13"
        elif id_servizio == '14':  #mit targa
            data = "Hai scelto il numero 14"
        elif id_servizio == '15':  #OK anis IFS02
            data_temp = []
            # anis_verifica_utente prende (user_ID, cf, id_caso) e si prende il voucher da se'
            data_temp.append(anis_verifica_utente(request.user.username, cf, 1))
            data = json.dumps(data_temp, indent=1)
        elif id_servizio == '16':  #OK anis IFS03
            data_temp = []
            data_temp.append(anis_verifica_utente(request.user.username, cf, 2))
            data = json.dumps(data_temp, indent=1)
        elif id_servizio == '17':  #cassa forense
            data = "Hai scelto il numero 17"
        elif id_servizio == '18':  #inps isee
            data = "Hai scelto il numero 18"
        elif id_servizio == '19':  #inps durc
            data = "Hai scelto il numero 19"
        elif id_servizio == '20':  #app IO
            data = "Hai scelto il numero 20"
        else:
            data = "Errore selezione e-service"

        return render(request, 'debug_openmsp.html', { 'servizi_impostazioni': servizi_impostazioni, 'gruppi_parametri': gruppi_parametri, 'data': data } )

    return render(request, 'debug_openmsp.html', { 'servizi_impostazioni': servizi_impostazioni, 'gruppi_parametri': gruppi_parametri })


class CustomPasswordResetView(PasswordResetView):
    email_template_name = 'registration/password_reset_email.txt'
    html_email_template_name = 'registration/password_reset_email.html'

    def get_email_options(self):
        context_pw = super().get_email_options()
        context_pw['extra_context'] = {
            'custom_message': 'Hai richiesto la reimpostazione della password per il tuo account su OpenMSP.'
        }
        return context_pw


class CustomUserCreationForm(UserCreationForm):

    email = forms.EmailField(required=True)
    is_active = forms.BooleanField(required=False)
    is_superuser = forms.BooleanField(required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2', 'is_active', 'is_superuser')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Questo indirizzo email è già in uso.")
        return email

# Come ANPR_SERVIZI e ANIS_SERVIZI: `codice` e' la riga di servizi_parametri che accende il
# servizio, i due flag sono i permessi su utenti_parametri. INI-PEC vive sotto `registro_imprese`
# (stessa mappatura gia' usata dal megamenu e da context_processors).
DOMICILI_SERVIZI = {
    'ipa': {'codice': 'ipa', 'flag': 'ipa_singolo', 'flag_massivo': 'ipa_massivo',
            'label': 'iPA (Amministrazioni)'},
    'inad': {'codice': 'inad', 'flag': 'inad_singolo', 'flag_massivo': 'inad_massivo',
             'label': 'INAD (Persone Fisiche)'},
    'inipec': {'codice': 'registro_imprese', 'flag': 'inipec_singolo', 'flag_massivo': 'inipec_massivo',
               'label': 'INI-PEC (Persone Giuridiche)'},
}


# Il massivo della pagina unificata sale sul filo delle tre card (`OpenMSP/avanzamento.py`): un
# POST per codice, la carta dice il codice in volo, la tabella la rende il server a giro finito.
# Qui stanno SOLO worker e riepilogo: il permesso viene gia' da `flag_massivo` di DOMICILI_SERVIZI
# (una fonte, non due) e gli exporter scelgono la propria URL nel template. I `_riga_*` sono i
# worker dei moduli di servizio - la pagina unificata e' il secondo chiamante legittimo: copiare
# il giro sarebbe la decima copia dello stesso filo.
DOMICILI_MASSIVI = {
    'ipa': {'worker': _riga_ipa, 'fine': _fine_ipa},
    'inad': {'worker': _riga_inad, 'fine': _fine_inad},
    'inipec': {'worker': _riga_inipec, 'fine': _fine_inipec},
}
GIRO_SESSIONE = 'domicili_giro'              # quale dei tre si sta girando
RISULTATI_SESSIONE = 'domicili_risultati'    # righe gia' vestite per il template


def _render_righe(tipo, codice, righe):
    """Le righe del filo (forma export) montate come le vuole la tabella unificata.

    Il filo scrive `multi_data` perche' li' leggono gli `*_export_excel`, e la tabella unificata
    vuole dizionali (`res.cf` / `res.raw`): una forma sola non puo' servire tutte e due, percio'
    i dizionali stanno in `domicili_risultati` e `veste_riga` ci passa sopra come sul giro vecchio.
    """
    if tipo == 'ipa':
        return [{'tipo': 'ipa', 'cf': codice, 'raw': riga} if isinstance(riga, dict) and 'error' not in riga
                else {'tipo': 'standard', 'cf': codice,
                      'dato': ('Errore interrogazione iPA' if isinstance(riga, dict)
                               else 'Domicilio digitale non trovato')}
                for riga in righe]
    return [{'tipo': 'standard', 'cf': str(riga).split(' ')[0],
             'dato': (str(riga).split(' ', 2) + ['', ''])[2]} for riga in righe]


def _worker_unificato(tipo):
    """Il worker del servizio, che in piu' mette la riga vestita nella sessione del render."""
    modulo = DOMICILI_MASSIVI[tipo]['worker']

    def una_riga(request, codice, stato=None):
        righe, ultimo, errore = modulo(request, codice, stato)
        request.session[RISULTATI_SESSIONE] = (request.session.get(RISULTATI_SESSIONE)
                                              or []) + _render_righe(tipo, codice, righe)
        return righe, ultimo, errore
    return una_riga


def domicili_massiva_riga(request):
    """Una riga del massivo unificato: l'indice dal navigatore, tipo e codici dalla sessione.

    `/domicili_digitali/riga/` e' una URL sola per tre servizi, percio' il gate (invariante 1)
    non puo' essere un nome fisso: e' il `flag_massivo` del tipo che sta in sessione.
    """
    tipo = (request.session.get(avanzamento.STATO_SESSIONE) or {}).get('tipo')
    if tipo not in DOMICILI_MASSIVI:
        return JsonResponse({'errore': 'Nessun giro di domicili digitali in corso'}, status=400)
    return avanzamento.risposta_riga(request, DOMICILI_SERVIZI[tipo]['flag_massivo'],
                                    _worker_unificato(tipo), DOMICILI_MASSIVI[tipo]['fine'])


def veste_riga(riga):
    """Colore, esito e icona di una riga della tabella: regola unica qui, il template stampa.

    Il giallo e' solo per il minorenne (un codice giusto che non si puo' interrogare), il
    rosso per ogni esito negativo: un codice scartato a priori non e' un avviso, e nelle
    pagine gemelle inad_massiva / inipec_massiva e' rosso da -1. Ritorna la riga stessa.
    """
    dato = riga.get('dato', '')
    if '@' in dato:
        esito = '1'
    elif 'minorenne' in dato:
        esito = '2'
    else:
        esito = '-1'
    riga['esito'] = esito
    riga['icona'] = {'1': 'it-check', '2': 'it-warning-circle', '-1': 'it-close-big'}[esito]
    riga['classe'] = {'1': 'table-success', '2': 'table-warning', '-1': 'table-danger'}[esito]
    return riga


def domicili_digitali_view(request):
    """Unica pagina per iPA / INAD / INI-PEC, singola o massiva. Un eService spento non viene
    offerto; attivo ma senza permesso viene offerto disabilitato (invariante 1: doppio gate
    servizi_parametri AND utenti_parametri, ri-validato nel POST)."""
    results = None
    search_context = {}
    error = None
    utente = (UtentiParametri.objects.filter(id=request.user.id).first()
              if request.user.is_authenticated else None)
    servizi, permessi, utente_abilitato = permessi_servizi(utente, DOMICILI_SERVIZI)
    contesto = {'results': results, 'search_context': search_context,
                'utente_abilitato': utente_abilitato, 'servizi': servizi, 'error': error}

    if request.method == 'GET' and request.GET.get('eseguito'):
        # il navigatore torna qui quando ha finito i giri: la tabella la rende il server, cosi'
        # non c'e' innerHTML di mezzo (e la pagina e' la stessa del giro senza JavaScript).
        tipo_giro = request.session.get(GIRO_SESSIONE)
        if tipo_giro in DOMICILI_MASSIVI:
            search_context = {'tipo': tipo_giro, 'modalita': 'massiva'}
            contesto['search_context'] = search_context
            results = request.session.get(RISULTATI_SESSIONE, [])
            contesto['results'] = results

    if request.method == 'POST':
        tipo = request.POST.get('tipo_domicilio')
        modalita = request.POST.get('modalita')
        api_key = "DEFAULT_KEY"
        search_context = {'tipo': tipo, 'modalita': modalita}
        contesto['search_context'] = search_context

        if not permessi.get(tipo, {}).get(modalita, False):
            contesto['error'] = "Non sei abilitato per questa tipologia di ricerca."
            return render(request, 'domicili_digitali.html', contesto)

        results = []
        contesto['results'] = results

        if modalita == 'singola':
            if tipo == 'ipa':
                descrizione = request.POST.get('input_descrizione_ente')
                cf_ipa = request.POST.get('input_CF')
                codice_ipa = request.POST.get('input_codice_ente')

                ipa_parametri = IpaParametri.objects.get(id=1)
                auth_id = ipa_parametri.auth_id

                codici_amm = []
                cf_display = ""

                if descrizione:
                    cf_display = descrizione
                    url = "https://www.indicepa.gov.it:443/ws/WS16DESAMMServices/api/WS16_DES_AMM"
                    response = requests.post(url, data={"AUTH_ID": auth_id, "DESCR": descrizione}, headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=30)
                    if response.status_code == 200:
                        temp_data = json_da_response(response)
                        occorrenze = temp_data.get('result', {}).get('num_items', 0)
                        if occorrenze:
                            for idx in range(occorrenze):
                                codici_amm.append(temp_data['data'][idx]['cod_amm'])
                elif cf_ipa:
                    cf_display = cf_ipa
                    if verifica_cf_azienda(cf_ipa) == 1:
                        url = "https://www.indicepa.gov.it:443/ws/WS23DOMDIGCFServices/api/WS23_DOM_DIG_CF"
                        response = requests.post(url, data={"AUTH_ID": auth_id, "CF": cf_ipa}, headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=30)
                        if response.status_code == 200:
                            temp_data = json_da_response(response)
                            if 'data' in temp_data and temp_data['data']:
                                codici_amm.append(temp_data['data'][0]['cod_amm'])
                elif codice_ipa:
                    cf_display = codice_ipa
                    codici_amm.append(codice_ipa)

                if not codici_amm:
                    results.append({'cf': cf_display, 'dato': "Nessun ente trovato"})
                    salva_log(request.user, "Verifica IndicePA", "Nessun ente per " + (cf_display or "(nessun criterio)"))
                else:
                    esito_ipa = None
                    for cod in codici_amm:
                        response = ipa_codice(auth_id, cod)
                        esito_ipa = response.status_code
                        if response.status_code == 200:
                            risultato = response.json()
                            results.append({'tipo': 'ipa', 'raw': risultato})
                        else:
                            results.append({'tipo': 'error', 'cf': cod, 'dato': 'Errore interrogazione iPA'})
                    salva_log(request.user, "Verifica IndicePA", "Verificato domicilio ente " + cf_display,
                              resp_status=esito_ipa)
            else:
                cf = request.POST.get('cf_singolo')
                if cf:
                    if tipo == 'inad':
                        dato, meta = Api_inad(cf, api_key)
                        nome, riga = "Verifica INAD singolo", "Verificato domicilio utente " + cf
                    else:
                        dato, meta = Api_ini_pec(cf, api_key)
                        nome, riga = "Verifica INI-PEC singolo", "Verificato domicilio impresa " + cf
                    results.append({'tipo': 'standard', 'cf': cf, 'dato': dato})
                    salva_log(request.user, nome, riga, **meta)

        elif modalita == 'massiva':
            file_obj = request.FILES.get('file_massivo')
            if file_obj:
                # stessa lettura dell'ANPR massiva: colonna A, CSV con il ';' di Excel
                cf_list = cf_da_file(file_obj) or []

                if request.POST.get('js') and cf_list:
                    # il giro dei codici lo comanda il navigatore (`domicili_massiva_riga`), cosi'
                    # la carta dell'overlay dice il vero avanzamento e non un cerchio che gira.
                    # Il tipo va in sessione DENTRO lo stato del filo: e' l'unica cosa che il POST
                    # per riga legge per sapere che permesso chiedere e che worker chiamare.
                    avanzamento.avvia(request, cf_list)
                    stato = request.session[avanzamento.STATO_SESSIONE]
                    stato['tipo'] = tipo
                    request.session[avanzamento.STATO_SESSIONE] = stato
                    request.session[GIRO_SESSIONE] = tipo
                    request.session[RISULTATI_SESSIONE] = []
                    contesto['totale'] = len(cf_list)
                    return render(request, 'domicili_digitali.html', contesto)

                ipa_auth_id = None
                ipa_search_url = "https://www.indicepa.gov.it:443/ws/WS16DESAMMServices/api/WS16_DES_AMM"
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                export_data = []
                if tipo == 'ipa':
                    ipa_auth_id = IpaParametri.objects.get(id=1).auth_id

                for cf in cf_list:
                    dato = None
                    if tipo == 'ipa':
                        ente = cf.strip().upper()
                        response = requests.post(ipa_search_url, data={"AUTH_ID": ipa_auth_id, "DESCR": ente}, headers=headers, timeout=30)
                        if response.status_code == 200:
                            temp_data = json_da_response(response)
                            occorrenze = temp_data.get('result', {}).get('num_items', 0)
                            if occorrenze:
                                for indice in range(occorrenze):
                                    codice_ipa = temp_data['data'][indice]['cod_amm']
                                    response_pec = ipa_codice(ipa_auth_id, codice_ipa)
                                    if response_pec.status_code == 200:
                                        risultato = response_pec.json()
                                        export_data.append(risultato)
                                        results.append({'tipo': 'ipa', 'cf': ente, 'raw': risultato})
                                    else:
                                        export_data.append(ente)
                                        results.append({'tipo': 'standard', 'cf': ente, 'dato': 'Errore interrogazione iPA'})
                                salva_log(request.user, "Verifica Ipa massivo - riga CSV", "Verificato CF " + ente,
                                          resp_status=response.status_code)
                                continue
                        dato = "Domicilio digitale non trovato"
                        export_data.append(ente)
                        salva_log(request.user, "Verifica Ipa massivo - riga CSV", "Verificato CF " + ente,
                                  resp_status=response.status_code)
                    elif tipo == 'inad':
                        dato, meta = Api_inad(cf, api_key)
                        stato = verifica_cf(cf)
                        export_data.append(f"{cf.strip().upper()} {stato} {dato}")
                        salva_log(request.user, "Verifica INAD massivo - riga CSV", "Verificato CF " + cf.strip().upper(), **meta)
                    elif tipo == 'inipec':
                        dato, meta = Api_ini_pec(cf, api_key)
                        stato = verifica_cf_azienda(cf)
                        export_data.append(f"{cf.strip().upper()} {stato} {dato}")
                        salva_log(request.user, "Verifica INI-PEC massivo - riga CSV", "Verificato CF " + cf.strip().upper(), **meta)
                    results.append({'tipo': 'standard', 'cf': cf, 'dato': dato})

                if tipo in ['ipa', 'inad', 'inipec']:
                    request.session['multi_data'] = export_data
                    riepilogo = {
                        'ipa': ("Verifica Ipa massivo", "Verificati n. " + str(len(cf_list)) + " CF"),
                        'inad': ("Verifica INAD massivo", "Fine elaborazione CSV - n. " + str(len(cf_list)) + " CF"),
                        'inipec': ("Verifica INI-PEC massivo", "Fine caricamento CSV verificati n. " + str(len(cf_list)) + " CF"),
                    }
                    salva_log(request.user, riepilogo[tipo][0], riepilogo[tipo][1])

    # Classe, esito e icona della riga: regola unica in `veste_riga`, il template stampa.
    # Il dizionario `esportazioni` che stava qui era morto: i tre pulsanti di export scelgono
    # la propria URL nel template, e nessuno leggeva `search_context['export']`.
    for riga in results or []:
        veste_riga(riga)

    return render(request, 'domicili_digitali.html', contesto)
