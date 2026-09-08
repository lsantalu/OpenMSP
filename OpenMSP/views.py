# pyright: reportAttributeAccessIssue=false
# pyright: reportIncompatibleVariableOverride=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
####INUTILI
from django.http import HttpResponse
from django.http import JsonResponse
##from zeep import Client
from PIL import Image
from impostazioni.models import UtentiParametri
import jwt
import subprocess
import uuid
import xmltodict
from jose.constants import Algorithms
import http.client, urllib.parse
import hashlib
import random
import base64
import csv
import io
import os
import shutil
import zipfile
import openpyxl
from markdown_it import MarkdownIt
####FINE INUTILI

from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.models import User
from datetime import datetime, date
import datetime


from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.shortcuts import redirect
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives

from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User

from .ipa import ipa_codice
from .anpr import anpr_get_request
from .inad import inad_get_bearer, inad_verifica_utente, estrai_mail
from .verifica_cf import verifica_cf, verifica_cf_azienda
from .registro_imprese import registro_imprese_get_bearer, registro_imprese_verifica_utente
from .anis import anis_verifica_utente


from .utils import converti_data, salva_log

from impostazioni.models import IpaParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import GruppiParametri

from impostazioni.models import Logs
from impostazioni.models import DatiEnte

import datetime
import pytz
import requests
import json
import re

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth.views import LoginView
from two_factor.views import LoginView as TwoFactorLoginView


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
            'service_links': [
                ('ipa', 'ipa_singola', ('ipa_singolo',)),
                ('inad', 'inad_singola', ('inad_singolo',)),
                ('registro_imprese', 'registro_imprese', ('registro_imprese',)),
            ],
            'image': 'images/domicio_digitale.png',
            'alt': 'Domicili Digitali',
            'description': 'Accedi ai domicili digitali iPA, INAD e INI-PEC in modo semplice e veloce.',
        },
        {
            'title': 'Interrogazioni ANPR',
            'service_links': [
                ('anpr_c001', 'anpr_notifica', ('anpr_C001',)),
                ('anpr_c007', 'anpr_esistenza_in_vita', ('anpr_C007',)),
                ('anpr_c015', 'anpr_generalita', ('anpr_C015',)),
                ('anpr_c017', 'anpr_matrimonio', ('anpr_C017',)),
                ('anpr_c018', 'anpr_cittadinanza', ('anpr_C018',)),
                ('anpr_c020', 'anpr_residenza', ('anpr_C020',)),
                ('anpr_c021', 'anpr_stato_famiglia', ('anpr_C021',)),
                ('anpr_c030', 'anpr_notifica', ('anpr_C030',)),
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
            'service_links': [('registro_imprese', 'registro_imprese', ('registro_imprese',))],
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
            temp_data = json.loads(response.content.decode('utf-8'))
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


# Nomi di audit: identici a quelli delle viste singole (OpenMSP/anpr.py), cosi' la pagina
# dei log e i suoi filtri non si biforcano tra le due generazioni di UI.
ANPR_LOG = {
    'C001': 'Verifica ANPR - C001 - Notifica',
    'C007': 'Verifica ANPR - C007 - Esistenza in vita',
    'C015': 'Verifica ANPR - C015 - Generalità',
    'C017': 'Verifica ANPR - C017 - Matrimonio',
    'C018': 'Verifica ANPR - C018 - Cittadinanza',
    'C020': 'Verifica ANPR - C020 - Residenza',
    'C021': 'Verifica ANPR - C021 - Stato famiglia',
}


def anpr(request):
    utente_abilitato = False
    data = None
    error = None
    service_options = [
        {'value': 'C001', 'label': 'C001 - Servizio notifica'},
        {'value': 'C007', 'label': 'C007 - Esistenza in vita'},
        {'value': 'C015', 'label': 'C015 - Generalita'},
        {'value': 'C017', 'label': 'C017 - Matrimonio'},
        {'value': 'C018', 'label': 'C018 - Cittadinanza'},
        {'value': 'C020', 'label': 'C020 - Residenza'},
        {'value': 'C021', 'label': 'C021 - Stato di famiglia'},
    ]

    utente_sessione = None
    if request.user.is_authenticated:
        utente_sessione = UtentiParametri.objects.filter(id=request.user.id).first()
        if utente_sessione:
            utente_abilitato = any([
                utente_sessione.anpr_C001,
                utente_sessione.anpr_C007,
                utente_sessione.anpr_C015,
                utente_sessione.anpr_C017,
                utente_sessione.anpr_C018,
                utente_sessione.anpr_C020,
                utente_sessione.anpr_C021,
                utente_sessione.anpr_C030,
            ])

    servizio_scelto = None
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
    parentela_choices = [
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

    if request.method == 'POST':
        cf = request.POST.get('input_CF', '').strip().upper()
        servizio = request.POST.get('servizio_anpr')
        servizio_scelto = servizio
        service_map = {
            'C001': ('anpr_C001', 1, True),
            'C007': ('anpr_C007', 2, True),
            'C015': ('anpr_C015', 3, True),
            'C017': ('anpr_C017', 4, True),
            'C018': ('anpr_C018', 5, True),
            'C020': ('anpr_C020', 6, True),
            'C021': ('anpr_C021', 7, True),
            # C030 non e' qui di proposito: e' strumentale alla risoluzione del CF in idANPR,
            # non e' una interrogazione utente. Cablato a id 9 era un DoesNotExist (500).
        }

        if servizio not in service_map:
            error = 'Servizio ANPR non valido.'
        elif not utente_abilitato:
            error = 'Non sei abilitato per questa tipologia di ricerca.'
        elif not cf:
            error = 'Inserisci un codice fiscale.'
        else:
            perm_attr, service_id, needs_idanpr = service_map[servizio]
            if not getattr(utente_sessione, perm_attr, False):
                error = 'Non sei abilitato per questa tipologia di ricerca.'
            else:
                correttezza_cf = verifica_cf(cf)
                data = []
                data.append(cf)
                if correttezza_cf in (1, 2):
                    # prima chiamata (id 8 = C030): trasforma il CF in idANPR, serve a tutte le modalita'
                    id_anpr, status_id, purp_id, tok_id = anpr_get_request(request.user.username, cf, 8)
                    res_data, status, purp_id, tok_id = anpr_get_request(request.user.username, id_anpr, service_id)
                    data.append(res_data)
                    data = converti_data(data)
                    salva_log(request.user, ANPR_LOG[servizio], "Verificato utente " + cf,
                              purposeid=purp_id, resp_status=status, token_id=tok_id)
                else:
                    data.append("Codice fiscale non corretto")
                    salva_log(request.user, ANPR_LOG[servizio], "Verificato utente " + cf)

    return render(request, 'anpr.html', {
        'utente_abilitato': utente_abilitato,
        'service_options': service_options,
        'data': data,
        'error': error,
        'servizio_scelto': servizio_scelto,
        'cessazione': cessazione_matrimonio_choices,
        'parentela': parentela_choices,
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
                content_str = response.content.decode('utf-8')
                temp_data = json.loads(content_str)
                if temp_data['data'] != None :
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

def domicili_digitali_view(request):
    results = None
    search_context = {}
    utente_abilitato = False
    allowed_searches = {
        'ipa': {'singola': False, 'massiva': False},
        'inad': {'singola': False, 'massiva': False},
        'inipec': {'singola': False, 'massiva': False},
    }

    if request.user.is_authenticated:
        utente_sessione = UtentiParametri.objects.filter(id=request.user.id).first()
        if utente_sessione:
            allowed_searches = {
                'ipa': {
                    'singola': bool(utente_sessione.ipa_singolo),
                    'massiva': bool(utente_sessione.ipa_massivo),
                },
                'inad': {
                    'singola': bool(utente_sessione.inad_singolo),
                    'massiva': bool(utente_sessione.inad_massivo),
                },
                'inipec': {
                    'singola': bool(utente_sessione.inipec_singolo),
                    'massiva': bool(utente_sessione.inipec_massivo),
                },
            }
            utente_abilitato = any(
                mode_enabled
                for service_modes in allowed_searches.values()
                for mode_enabled in service_modes.values()
            )

    if request.method == 'POST':
        if not utente_abilitato:
            return render(request, 'domicili_digitali.html', {
                'results': results,
                'search_context': search_context,
                'utente_abilitato': utente_abilitato,
                'allowed_searches': allowed_searches,
                    'allowed_searches_json': json.dumps(allowed_searches),
            })

        tipo = request.POST.get('tipo_domicilio')
        modalita = request.POST.get('modalita')
        api_key = "DEFAULT_KEY"

        if tipo not in allowed_searches or modalita not in allowed_searches[tipo] or not allowed_searches[tipo][modalita]:
            return render(request, 'domicili_digitali.html', {
                'results': results,
                'search_context': {'tipo': tipo, 'modalita': modalita},
                'utente_abilitato': utente_abilitato,
                'allowed_searches': allowed_searches,
                    'allowed_searches_json': json.dumps(allowed_searches),
                'error': "Non sei abilitato per questa tipologia di ricerca.",
            })

        results = []
        search_context = {'tipo': tipo, 'modalita': modalita}

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
                        temp_data = json.loads(response.content.decode('utf-8'))
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
                            temp_data = json.loads(response.content.decode('utf-8'))
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
                cf_list = []
                filename = file_obj.name
                if filename.endswith('.csv'):
                    decoded_file = file_obj.read().decode('utf-8').splitlines()
                    reader = csv.reader(decoded_file)
                    for row in reader:
                        if row:
                            cf_list.append(row[0])
                elif filename.endswith('.xlsx') or filename.endswith('.xls'):
                    wb = openpyxl.load_workbook(file_obj, data_only=True)
                    sheet = wb.active
                    for row in sheet.iter_rows(values_only=True):
                        if row[0]:
                            cf_list.append(str(row[0]))

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
                            temp_data = json.loads(response.content.decode('utf-8'))
                            occorrenze = temp_data.get('result', {}).get('num_items', 0)
                            if occorrenze:
                                for indice in range(0, occorrenze):
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

    return render(request, 'domicili_digitali.html', {
        'results': results,
        'search_context': search_context,
        'utente_abilitato': utente_abilitato,
        'allowed_searches': allowed_searches,
                    'allowed_searches_json': json.dumps(allowed_searches),
    })
