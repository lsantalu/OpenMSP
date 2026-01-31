from django.shortcuts import render

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import MitServizi
from impostazioni.models import MitParametri

from .utils import salva_log
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
import uuid
import jwt
import requests
import json
import re
import sys
import subprocess


def mit_get_request(user_ID, cf, id_caso):
    parametri_mit = MitParametri.objects.get(id=id_caso)
    caso = ''
    if id_caso == 1: ##CUDE
        caso = "CUDE"
    elif id_caso == 2: ##Lista veicoli
        caso = "LISTA_VEICOLI"
    elif id_caso == 3: ##Whitelist
        caso = "WHITELIST"
    else: ##Targhe
        caso = "TARGHE"

    kid = parametri_mit.kid
    alg = parametri_mit.alg
    typ = parametri_mit.typ
    issuer = parametri_mit.iss
    subject = parametri_mit.sub
    aud = parametri_mit.aud
    purposeid = parametri_mit.purposeid
    audience = parametri_mit.audience
    baseurlauth = parametri_mit.baseurlauth
    target = parametri_mit.target
    clientid = parametri_mit.clientid
    private_key = parametri_mit.private_key

    ##issued = datetime.datetime.utcnow()
    issued = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) - 60
    expire_in = issued + 180
    jti = uuid.uuid4()
    headers_rsa = {
        "kid": kid,
        "alg": alg,
        "typ": typ
    }

    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": aud,
        "purposeId": purposeid,
        "jti": str(jti),
        "iat": issued,
        "exp": expire_in
    }
    
    asserzione = jwt.encode(payload, private_key, algorithm="RS256", headers=headers_rsa)

    curl_command = (
        f"curl --location --silent --request POST {baseurlauth}/token.oauth2 "
        f"--header 'Content-Type: application/x-www-form-urlencoded' "
        f"--data-urlencode 'client_id={clientid}' "
        f"--data-urlencode 'client_assertion={asserzione}' "
        "--data-urlencode 'client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer' "
        "--data-urlencode 'grant_type=client_credentials'"
    )

    if not sys.platform.startswith('linux'):
        curl_command=curl_command.replace("'", '"')

    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    voucher =  data['access_token']

    url = target + '/status'
    curl_command = (
        f'curl --silent --request GET '
        f"--url '{audience}' "
        f"--header 'Authorization: Bearer {voucher}'"
        )
    if not sys.platform.startswith('linux'):
        curl_command=curl_command.replace("'", '"')    
            
    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True) 
    return json.loads(result.stdout)



def mit_dettaglio_cude(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_cude
    return render(request, 'mit_dettaglio_cude.html', { 'utente_abilitato': utente_abilitato })


def mit_whitelist(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_whitelist
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
            salva_log(request.user,"Verifica MIT - Whitelist", "Verificato utente " + cf)

            return render(request, 'mit_whitelist.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'mit_whitelist.html', { 'utente_abilitato': utente_abilitato })


def mit_lista_veicoli_cude(request):
    utente_abilitato = False
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_veicoli

        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                # id_caso = 2 per "Lista veicoli" come definito in mit_get_request
                response = mit_get_request(request.user.username, cf, 2)
                data.append(response)
                data = converti_data(data)
                # Gestione errori eventuale o formattazione se necessaria
            else:
                data.append("Codice fiscale non corretto")
            
            salva_log(request.user, "Verifica MIT - Lista Veicoli", "Verificato utente " + cf)
            return render(request, 'mit_lista_veicoli_cude.html', {'data': data, 'utente_abilitato': utente_abilitato })

    return render(request, 'mit_lista_veicoli_cude.html', { 'utente_abilitato': utente_abilitato })


def mit_verifica_targa_cude(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_targa
    return render(request, 'mit_verifica_targa_cude.html', { 'utente_abilitato': utente_abilitato })


def impostazioni_mit(request):
    servizi_mit = MitServizi.objects.all()
    parametri_mit = MitParametri.objects.all()

    service_active = ServiziParametri.objects.all()
    i_serv=0
    service_desc = ["" for _ in range(ServiziParametri.objects.count())]
    for servizio in service_active:
        service_desc[i_serv]= (servizio.attivo)
        i_serv += 1

    if request.method == 'POST':
        posizione_servizio = ServiziParametri.objects.filter(gruppo_id=5).values_list('id', flat=True)
        for i in range(1, MitParametri.objects.count()+1):
            if service_desc[posizione_servizio[i-1]-1]:
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
                dati = MitParametri(i, i, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
                dati.save()
        salva_log(request.user,"Impostazioni MIT", "modifica parametri")

    return render(request, 'impostazioni_mit.html', { 'servizi_mit': servizi_mit, 'parametri_mit': parametri_mit })

