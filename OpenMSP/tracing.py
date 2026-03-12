from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from impostazioni.models import TracingParametri
from .utils import salva_log

import datetime
from jose.constants import Algorithms
import http.client, urllib.parse
import hashlib
import random
import base64
import uuid
import jwt
import requests
import json
import re

def get_tracing_bearer(parametri_tracing, user_id):
    kid = parametri_tracing.kid
    alg = parametri_tracing.alg
    typ = parametri_tracing.typ
    issuer = parametri_tracing.iss
    subject = parametri_tracing.sub
    aud = parametri_tracing.aud
    purposeid = parametri_tracing.purposeid
    audience = parametri_tracing.audience
    baseurlauth = parametri_tracing.baseurlauth
    target = parametri_tracing.target
    clientid = parametri_tracing.clientid
    private_key = parametri_tracing.private_key
    userid = user_id
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
    
    return voucher, audit


def verifica_status_tracing(request):
    try:
        parametri_tracing = TracingParametri.objects.get(id=1)
    except TracingParametri.DoesNotExist:
        return {"errore": "Parametri non configurati"}
    
    kid = parametri_tracing.kid
    alg = parametri_tracing.alg
    typ = parametri_tracing.typ
    audience = parametri_tracing.audience
    target = parametri_tracing.target
    clientid = parametri_tracing.clientid
    private_key = parametri_tracing.private_key
    purposeid = parametri_tracing.purposeid

    if request and hasattr(request, 'user') and request.user.is_authenticated:
        user_id = request.user.username
    else:
        user_id = 'admin'

    voucher, audit = get_tracing_bearer(parametri_tracing, user_id)

    api_url = f"{target.rstrip('/')}/status"
    
    # prepara il body per la richiesta GET e relativo digest (body vuoto)
    body = ""
    body_digest = hashlib.sha256(body.encode('UTF-8'))
    digest = 'SHA-256=' + base64.b64encode(body_digest.digest()).decode('UTF-8')

    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=43200)
    expire_in = issued + delta

    headers_rsa = {
        "kid": kid,
        "alg": alg,
        "typ": typ
    }

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
            {"digest": digest} # Content-Type e Content-Encoding non necessari per GET
        ]
    }
    signature = jwt.encode(payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)
    
    # effettua chiamata
    headers =  {
        "Accept": "application/json",
        "Digest": digest,
        "Authorization": "Bearer " + voucher,
        "Agid-JWT-TrackingEvidence": audit,
        "Agid-JWT-Signature": signature
    }

    response = requests.get(api_url, headers=headers, verify=False)
    
    if response.status_code in [200, 201]:
        return {"status": "OK", "dettaglio": "Servizio attivo"}
    else:
        return {"errore": f"Status code {response.status_code}", "dettaglio": response.text}


def chiamata_api_tracing(request, method, endpoint, params=None, data=None, files=None):
    """Helper generico per chiamate API Tracing con firma."""
    try:
        parametri_tracing = TracingParametri.objects.get(id=1)
    except TracingParametri.DoesNotExist:
        return {"errore": "Parametri non configurati"}

    user_id = request.user.username if request.user.is_authenticated else 'admin'
    voucher, audit = get_tracing_bearer(parametri_tracing, user_id)
    
    url = f"{parametri_tracing.target.rstrip('/')}{endpoint}"
    
    # Digest e Headers
    body = "" # Per multipart il digest è più complesso, ma spesso richiesto sul file
    # In OpenAPI non vedo digest obbligatorio per multipart/form-data nelle spec fornite, 
    # ma seguiamo il pattern esistente se necessario.
    
    issued = datetime.datetime.utcnow()
    expire_in = issued + datetime.timedelta(minutes=60)
    
    headers_rsa = {"kid": parametri_tracing.kid, "alg": parametri_tracing.alg, "typ": parametri_tracing.typ}
    
    payload = {
        "iss" : parametri_tracing.clientid,
        "aud" : parametri_tracing.audience,
        "purposeId": parametri_tracing.purposeid,
        "sub": parametri_tracing.clientid,
        "jti": str(uuid.uuid4()),
        "iat": issued,
        "nbf" : issued,
        "exp": expire_in,
        "signed_headers": []
    }
    
    signature = jwt.encode(payload, parametri_tracing.private_key, algorithm=Algorithms.RS256, headers=headers_rsa)
    
    headers = {
        "Authorization": f"Bearer {voucher}",
        "Agid-JWT-TrackingEvidence": audit,
        "Agid-JWT-Signature": signature,
        "Accept": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, verify=False)
        elif method == "POST":
            response = requests.post(url, headers=headers, data=data, files=files, verify=False)
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                return {"errore": response.status_code, "dettaglio": response.json()}
            except:
                return {"errore": response.status_code, "dettaglio": response.text}
    except Exception as e:
        return {"errore": "Eccezione", "dettaglio": str(e)}


@login_required
def ajax_submit_tracing(request):
    if request.method != 'POST':
        return JsonResponse({"errore": "Metodo non consentito"}, status=405)
    
    file_obj = request.FILES.get('file')
    date = request.POST.get('date')
    
    if not file_obj or not date:
        return JsonResponse({"errore": "File e data obbligatori"}, status=400)
    
    files = {'file': (file_obj.name, file_obj.read(), 'text/csv')}
    data = {'date': date}
    
    risultato = chiamata_api_tracing(request, "POST", "/tracings/submit", data=data, files=files)
    return JsonResponse(risultato, safe=False)


@login_required
def ajax_get_tracings(request):
    states = request.GET.get('states')
    offset = request.GET.get('offset', 0)
    limit = request.GET.get('limit', 50)
    
    params = {'offset': offset, 'limit': limit}
    if states:
        params['states'] = states
        
    risultato = chiamata_api_tracing(request, "GET", "/tracings", params=params)
    return JsonResponse(risultato, safe=False)


@login_required
def ajax_get_tracing_errors(request, tracing_id):
    offset = request.GET.get('offset', 0)
    limit = request.GET.get('limit', 50)
    
    params = {'offset': offset, 'limit': limit}
    risultato = chiamata_api_tracing(request, "GET", f"/tracings/{tracing_id}/errors", params=params)
    return JsonResponse(risultato, safe=False)


@login_required
def ajax_recover_tracing(request, tracing_id):
    if request.method != 'POST':
        return JsonResponse({"errore": "Metodo non consentito"}, status=405)
    
    file_obj = request.FILES.get('file')
    if not file_obj:
        return JsonResponse({"errore": "File obbligatorio"}, status=400)
        
    files = {'file': (file_obj.name, file_obj.read(), 'text/csv')}
    risultato = chiamata_api_tracing(request, "POST", f"/tracings/{tracing_id}/recover", files=files)
    return JsonResponse(risultato, safe=False)


@login_required
def ajax_replace_tracing(request, tracing_id):
    if request.method != 'POST':
        return JsonResponse({"errore": "Metodo non consentito"}, status=405)
    
    file_obj = request.FILES.get('file')
    if not file_obj:
        return JsonResponse({"errore": "File obbligatorio"}, status=400)
        
    files = {'file': (file_obj.name, file_obj.read(), 'text/csv')}
    risultato = chiamata_api_tracing(request, "POST", f"/tracings/{tracing_id}/replace", files=files)
    return JsonResponse(risultato, safe=False)



def tracing_page(request):
    """Renderizza la pagina principale del tracing."""
    return render(request, 'tracing.html')

@login_required
def ajax_verifica_status_tracing(request):
    """Endpoint AJAX per la verifica dello status tracing."""
    risultato = verifica_status_tracing(request)
    return JsonResponse(risultato, safe=False)


def impostazioni_tracing(request):
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

        dati = TracingParametri(1, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
        dati.save()
        salva_log(request.user, "Impostazioni Tracing", "modifica parametri")
        
    parametri_tracing = TracingParametri.objects.all()

    return render(request, 'impostazioni_tracing.html', {'parametri_tracing': parametri_tracing})
