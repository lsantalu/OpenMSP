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
###from .inad import inad_get_bearer, inad_verifica_utente
from .verifica_cf import verifica_cf, verifica_cf_azienda
from .registro_imprese import registro_imprese_get_bearer, registro_imprese_verifica_utente
###from .anis import anis_get_bearer, anis_verifica_utente


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
    bearer = inad_get_bearer()
    correttezza_cf = verifica_cf(codice_fiscale)
    if correttezza_cf == 1:
        ###salva_log(api_key,"Verifica INAD singolo", "Verificato domicilio utente " + codice_fiscale )
        return inad_verifica_utente(codice_fiscale, bearer)

def Api_ipa(codice_fiscale, api_key):
    ipa_parametri = IpaParametri.objects.get(id=1)
    auth_id = ipa_parametri.auth_id

    testo_log = codice_fiscale
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
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            content_str = response.content.decode('utf-8')
            ###salva_log(api_key,"Verifica IndicePA", "Verificato domicilio ente " + testo_log )
            return json.loads(content_str)

def Api_ini_pec(codice_fiscale, api_key):
    bearer = registro_imprese_get_bearer()
    correttezza_cf_azienda = verifica_cf_azienda(codice_fiscale)
    if correttezza_cf_azienda == 1:
        elenco_dati_registro =  registro_imprese_verifica_utente(codice_fiscale, bearer)
        dd = elenco_dati_registro.get('blocchi_impresa').get('dati_identificativi').get('indirizzo_posta_certificata')
        ###salva_log(api_key,"Verifica INI-PEC singolo", "Verificato domicilio impresa " + codice_fiscale )
        return dd


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
    if tipo_servizio == "C018" :
        risultato = Api_C018(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "C020" :
        risultato = Api_C020(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "C021" :
        risultato = Api_C021(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "inad" :
        risultato = Api_inad(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "ipa" :
        risultato = Api_ipa(codice_fiscale, chiave_autenticazione)
    if tipo_servizio == "ini_pec" :
        risultato = Api_ini_pec(codice_fiscale, chiave_autenticazione)

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
    user_id = request.user.id if request.user.is_authenticated else None
    utente_attivo = get_object_or_404(User, id=user_id)
    if not utente_attivo.is_active :
        messages.error(request, 'L\'utente è disabilitato. Contatta l\'amministratore di sistema')
    auth_logout(request)
    return redirect('home')
    

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
            response = requests.post(url, data=payload, headers=headers)
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
            bearer = registro_imprese_get_bearer()
            elenco_dati_registro =  registro_imprese_verifica_utente(cf, bearer)
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
            bearer = anis_get_bearer(1)
            data_temp.append(anis_verifica_utente(cf, bearer, 1))
            data = json.dumps(data_temp, indent=1)
        elif id_servizio == '16':  #OK anis IFS03
            data_temp = []
            bearer = anis_get_bearer(2)
            data_temp.append(anis_verifica_utente(cf, bearer, 2))
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
