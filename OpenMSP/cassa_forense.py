from django.shortcuts import render

from .utils import salva_log
from .verifica_cf import verifica_cf

from impostazioni.models import CassaForenseParametri
from impostazioni.models import UtentiParametri
import datetime
### import subprocess
import base64
import uuid
import random
import re
from jose.constants import Algorithms
import http.client, urllib.parse
import hashlib

import json
import requests
##from zeep import Client
##from zeep.helpers import serialize_object
import jwt

##import zeep


def cassa_forense(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.cassa_forense
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            wsdl = 'https://servizi.consiglionazionaleforense.it/ws_check_avv/ws_check_avv.php?wsdl'
            client = Client(wsdl)
            ##service = client.bind('GetAvvocato', 'soap')
            bearer = cassa_forense_get_bearer(request.user.username, cf)
            correttezza_cf = verifica_cf(cf)

            if correttezza_cf == 1:
                request_data = {
                    'key': bearer,
                    'codfisc': cf
                    }
                ##try:
                ##    response = service.getAvvocato(**request_data)
                ##    response_data = serialize_object(response)
                ##    data.append(response_data)
                ##    return response_data
                ##except zeep.exceptions.Fault as e:
                ##    print(f"Errore durante la chiamata SOAP: {e}")
                ##    return None

            else:
                data.append("Codice fiscale non corretto")

            salva_log(request.user,"Verifica Consiglio Nazionale Foresne", "Verificato avvocato " + cf)
            return render(request, 'cassa_forense.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False

    return render(request, 'cassa_forense.html', { 'utente_abilitato': utente_abilitato })


def cassa_forense_get_bearer(user_ID, cf):
    parametri_cassa_forense = CassaForenseParametri.objects.get(id=1)
    kid = parametri_cassa_forense.kid
    alg = parametri_cassa_forense.alg
    typ = parametri_cassa_forense.typ
    issuer = parametri_cassa_forense.iss
    subject = parametri_cassa_forense.sub
    aud = parametri_cassa_forense.aud
    purposeid = parametri_cassa_forense.purposeid
    audience = parametri_cassa_forense.audience
    baseurlauth = parametri_cassa_forense.baseurlauth
    target = parametri_cassa_forense.target
    clientid = parametri_cassa_forense.clientid
    private_key = parametri_cassa_forense.private_key
    userid = user_ID
    location = 'PortaleOpenMSP'
    loa = 'LoA2'

    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=43200)
    expire_in = issued + delta
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
    conn = http.client.HTTPSConnection(re.sub(r'^https?://', '', baseurlauth))
    conn.request("POST", "/token.oauth2", params, headers)
    response = conn.getresponse()
    voucher = json.loads(response.read())["access_token"]
    ####return voucher


    request_data = {
        'key': voucher,
        'codfisc': cf
    }

    body = json.dumps(request_data)

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

    response = requests.post(api_url, data=body.encode('UTF-8'), headers=headers, verify=False)
    return response.json()


def impostazioni_cassa_forense(request):
    parametri_cassa_forense = CassaForenseParametri.objects.all()
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

        dati = CassaForenseParametri(1, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
        dati.save()
        salva_log(request.user,"Impostazioni Consiglio Nazionale Forense", "modifica parametri")
    else:
        parametri_cassa_forense = CassaForenseParametri.objects.all()

    return render(request, 'impostazioni_cassa_forense.html', {'parametri_cassa_forense': parametri_cassa_forense})

