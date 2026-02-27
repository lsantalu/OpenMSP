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
    userid= user_ID

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
    location = 'PortaleOpenMSP'
    loa = 'LoA2'
    if id_caso == 4: ##Targhe
        richiesta_data = {
            "targa": cf,
            "dataOraVerifica": datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "intervalloDiTolleranza": 0
        }
        richiesta = json.dumps(richiesta_data)
    else:
        richiesta = f'{{"codiceFiscale":"{cf}"}}'

    ##issued = datetime.datetime.utcnow()
    issued = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) - 60
    expire_in = issued + 300
    dnonce = random.randint(1000000000000, 9999999999999)


    headers_rsa = {
        "kid": kid,
        "alg": alg,
        "typ": typ
    }

    jti = uuid.uuid4()
    audit_payload = {
        "userID": userid,
        "userLocation": location,
        "LoA": loa,
        "iss" : clientid,
        "aud" : audience,
        "purposeId": purposeid,
        "dnonce" : dnonce,
        "jti":str(jti),
        "iat": issued,
        "nbf" : issued,
        "exp": expire_in
    }

    audit = jwt.encode(audit_payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)
    audit_hash = hashlib.sha256(audit.encode('UTF-8')).hexdigest()

    jti = uuid.uuid4()
    payload = {
        "iss": clientid,
        "sub": clientid,
        "aud": aud,
        "purposeId": purposeid,
        "jti": str(jti),
        "iat": issued,
        "exp": expire_in,
        "digest": {
            "alg": "SHA256",
            "value": audit_hash
            }
        }


    client_assertion = jwt.encode(payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)

    params = urllib.parse.urlencode({
        'client_id': clientid,
        'client_assertion': client_assertion,
        'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
        'grant_type': 'client_credentials'
        })

    headers = {"Content-type": "application/x-www-form-urlencoded"}
    try:
        conn = http.client.HTTPSConnection(re.sub(r'^https?://', '', baseurlauth))
        conn.request("POST", "/token.oauth2", params, headers)
        response = conn.getresponse()
        resp_data = response.read()
        if response.status == 200:
            voucher = json.loads(resp_data)["access_token"]
        else:
            return {
                "esito": {
                    "codice": str(response.status),
                    "descrizione": f"Errore richiesta Token: {resp_data.decode('UTF-8')[:200]}"
                }
            }
    except Exception as e:
        return {
            "esito": {
                "codice": "TOKEN_ERR",
                "descrizione": f"Eccezione durante richiesta Token: {str(e)}"
            }
        }

    # prepara il body per la richiesta e relativo digest
    body = richiesta
    type = 'application/json'
    encoding = 'UTF-8'
    body_digest = hashlib.sha256(body.encode('UTF-8'))
    digest = 'SHA-256=' + base64.b64encode(body_digest.digest()).decode('UTF-8')

    # crea signature
    jti = uuid.uuid4()
    payload = {
        "iss" : clientid,
        "aud" : audience,
        "purposeId": purposeid,
        "sub": clientid,
        "jti": str(jti),
        "iat": issued,
        "nbf" : issued,
        "exp": expire_in,
        "signed_headers": [
            {"digest": digest},
            {"content-type": type},
            {"content-encoding": encoding}
            ]
        }
    signature = jwt.encode(payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)
    # effettua chiamata
    api_url = target
    headers =  {"Accept":"application/json",
                "Content-Type":type,
                "Content-Encoding":encoding,
                "Digest":digest,
                "Authorization":"Bearer " + voucher,
                "Agid-JWT-TrackingEvidence":audit,
                "Agid-JWT-Signature":signature
                }

    try:
        response = requests.post(api_url, data=body.encode('UTF-8'), headers=headers, verify=False)
        if response.status_code != 200:
            return {
                "esito": {
                    "codice": str(response.status_code),
                    "descrizione": f"Errore API MIT: {response.text[:200]}"
                }
            }
        return response.json()
    except json.JSONDecodeError:
        return {
            "esito": {
                "codice": "JSON_ERR",
                "descrizione": f"Risposta non valida dal server (non JSON): {response.text[:200]}"
            }
        }
    except Exception as e:
        return {
            "esito": {
                "codice": "network_error",
                "descrizione": str(e)
            }
        }


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
                # id_caso = 2 per "Lista veicoli" come definito in mit_get_request
                response = mit_get_request(request.user.username, cf, 3)
                data.append(response)
                data = converti_data(data)
                # Gestione errori eventuale o formattazione se necessaria
            else:
                data.append("Codice fiscale non corretto")

            salva_log(request.user,"Verifica MIT - Whitelist", "Verificato utente " + cf)

            return render(request, 'mit_whitelist.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'mit_whitelist.html', { 'utente_abilitato': utente_abilitato })


def mit_lista_veicoli(request):
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
            return render(request, 'mit_lista_veicoli.html', {'data': data, 'utente_abilitato': utente_abilitato })

    return render(request, 'mit_lista_veicoli.html', { 'utente_abilitato': utente_abilitato })


def mit_verifica_targa(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_targa

        if request.method == 'POST':
            data = []
            targa = request.POST.get('input_targa')
            data.append(targa)
            response = mit_get_request(request.user.username, targa, 4)
            data.append(response)
            data = converti_data(data)
            # Gestione errori eventuale o formattazione se necessaria

            salva_log(request.user, "Verifica MIT - Verifica Targa", "Verificato targa " + targa)
            return render(request, 'mit_verifica_targa.html', {'data': data, 'utente_abilitato': utente_abilitato })


    return render(request, 'mit_verifica_targa.html', { 'utente_abilitato': utente_abilitato })


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
