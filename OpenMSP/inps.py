from django.shortcuts import render

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import GruppiParametri
from impostazioni.models import InpsIseeParametri
from impostazioni.models import InpsDurcParametri

from .utils import salva_log
from .utils import converti_data
from .verifica_cf import verifica_cf
import xmltodict


##from datetime import datetime, date
import datetime
from jose.constants import Algorithms
import http.client, urllib.parse
import hashlib
import random
import base64
import datetime
import uuid
import jwt
import subprocess
import requests
import json
import io
import csv
import re
import openpyxl



def inps_isee(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_isee
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                data.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 1))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")
            salva_log(request.user,"Verifica INPS - ISEE", "Verificato utente " + cf)

            return render(request, 'inps_isee.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_isee.html', { 'utente_abilitato': utente_abilitato })


def inps_durc_get_bearer():
    parametri_inps_durc = InpsDurcParametri.objects.get(id=1)

    kid = parametri_inps_durc.kid
    alg = parametri_inps_durc.alg
    typ = parametri_inps_durc.typ
    issuer = parametri_inps_durc.iss
    subject = parametri_inps_durc.sub
    aud = parametri_inps_durc.aud
    purposeId = parametri_inps_durc.purposeid
    audience = parametri_inps_durc.audience
    baseurlauth = parametri_inps_durc.baseurlauth
    target = parametri_inps_durc.target
    clientid = parametri_inps_durc.clientid
    private_key = parametri_inps_durc.private_key


    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=43200)
    expire_in = issued + delta
    jti = uuid.uuid4()
    headers_rsa = {
        "kid": kid,
        "alg": alg,
        "typ": typ
    }

    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "purposeId": purposeId,
        "jti": str(jti),
        "iat": issued,
        "exp": expire_in
    }

    asserzione = jwt.encode(payload, private_key, algorithm="RS256", headers=headers_rsa)

    curl_command = (
        f"curl --location --silent --request POST {baseurlauth}/token.oauth2 "
        f"--header 'Content-Type: application/x-www-form-urlencoded' "
        f"--data-urlencode 'client_id={issuer}' "
        f"--data-urlencode 'client_assertion={asserzione}' "
        "--data-urlencode 'client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer' "
        "--data-urlencode 'grant_type=client_credentials'"
    )

    if not sys.platform.startswith('linux'):
        curl_command=curl_command.replace("'", '"')

    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return data['access_token']


def inps_durc_singolo(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_durc_singolo
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                bearer = inps_durc_get_bearer()
                data.append(inps_durc_verifica_impresa(cf, bearer))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")
            salva_log(request.user,"Verifica INPS - DURC", "Verificato utente " + cf)

            return render(request, 'inps_durc_singolo.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_durc_singolo.html', { 'utente_abilitato': utente_abilitato })


def inps_durc_massivo(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_durc_massivo
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                bearer = inps_durc_get_bearer()
                data.append(inps_durc_verifica_impresa(cf, bearer))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")
            salva_log(request.user,"Verifica INPS - DURC", "Verificato utente " + cf)

            return render(request, 'inps_durc_massivo.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_durc_massivo.html', { 'utente_abilitato': utente_abilitato })


def inps_durc_verifica_impresa(cf, bearer):
    inps_durc_parametri = InpsDurcParametri.objects.get(id=1)
    url = inps_durc_parametri.api_url + '/getDurcInCorsoDiValidita'


    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json" ,
        "INPS-Identity-UserId": "00360180269" ,
        "INPS-Identity-CodiceUfficio": "001"
        }
    data = {
        "codicefiscale": cf
        }
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        xml_data = response.content
        parsed_data = xmltodict.parse(xml_data)
        return parsed_data
    else:
        return False


def impostazioni_inps_durc(request):
    parametri_inps_durc = InpsDurcParametri.objects.all()
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
        dati = InpsDurcParametri(1, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
        dati.save()
        salva_log(request.user,"Impostazioni INPS - DURC", "modifica parametri")
    else:
        parametri_inps_durc = InpsDurcParametri.objects.all()

    return render(request, 'impostazioni_inps_durc.html', {'parametri_inps_durc': parametri_inps_durc})


def impostazioni_inps_isee(request):
    parametri_inps_isee = InpsIseeParametri.objects.all()
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

        dati = InpsIseeParametri(1, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
        dati.save()
        salva_log(request.user,"Impostazioni INPS - ISEE", "modifica parametri")
    else:
        parametri_inps_isee = InpsIseeParametri.objects.all()

    return render(request, 'impostazioni_inps_isee.html', {'parametri_inps_isee': parametri_inps_isee})



