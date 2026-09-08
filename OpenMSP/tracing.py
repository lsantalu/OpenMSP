from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from impostazioni.models import TracingParametri
from impostazioni.models import Logs
from .utils import salva_log
from django.db.models import Count

import datetime
from django.conf import settings
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
import urllib3
import csv


def get_tracing_bearer(parametri_tracing, user_id):
    kid = parametri_tracing.kid
    alg = parametri_tracing.alg
    typ = parametri_tracing.typ
    aud = parametri_tracing.aud
    purposeid = parametri_tracing.purposeid
    # tracing_audience è l'aud corretto per la tracing API (es. att.interop.pagopa.it/tracing)
    # audience è per gli e-service normali (eservices.att.interop.pagopa.it)
    tracing_audience = parametri_tracing.tracing_audience or parametri_tracing.audience
    baseurlauth = parametri_tracing.baseurlauth
    clientid = parametri_tracing.clientid
    private_key = parametri_tracing.private_key
    location = 'PortaleOpenMSP'
    loa = 'LoA2'

    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=15)
    expire_in = issued + delta
    dnonce = random.randint(1000000000000, 9999999999999)

    headers_rsa = {"kid": kid, "alg": alg, "typ": typ}

    # Costruisce l'audit con tracing_audience (aud per la tracing API)
    jti_audit = uuid.uuid4()
    audit_payload = {
        "userID": user_id,
        "userLocation": location,
        "LoA": loa,
        "iss": clientid,
        "sub": clientid,
        "aud": tracing_audience,
        "purposeId": purposeid,
        "dnonce": dnonce,
        "jti": str(jti_audit),
        "iat": issued,
        "nbf": issued,
        "exp": expire_in
    }
    audit = jwt.encode(audit_payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)
    audit_hash = hashlib.sha256(audit.encode('UTF-8')).hexdigest()

    # Costruisce la client_assertion con l'hash dell'audit
    jti_ca = uuid.uuid4()
    client_assertion_payload = {
        "iss": clientid,
        "sub": clientid,
        "aud": aud,
        "purposeId": purposeid,
        "jti": str(jti_ca),
        "iat": issued,
        "exp": expire_in,
        "digest": {"alg": "SHA256", "value": audit_hash}
    }
    client_assertion = jwt.encode(client_assertion_payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)

    params = urllib.parse.urlencode({
        'client_id': clientid,
        'client_assertion': client_assertion,
        'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
        'grant_type': 'client_credentials'
    })
    headers = {"Content-type": "application/x-www-form-urlencoded"}
    conn = http.client.HTTPSConnection(re.sub(r'^https?://', '', baseurlauth), timeout=30)
    conn.request("POST", "/token.oauth2", params, headers)
    corpo = conn.getresponse().read()
    conn.close()
    try:
        voucher = json.loads(corpo)["access_token"]
    except Exception as e:
        # authority guasta: un errore leggibile qui evita un 500 nudo chiamante
        raise RuntimeError(f"Authority tracing non ha rilasciato un voucher: {corpo[:200]!r}") from e

    return voucher, audit


def confronta_identificatori(claims, parametri_tracing):
    """Confronta gli identificatori timbrati dall'Authorization Server con quelli
    configurati. L'AS meticol l'audience dell'e-service a cui la finalita' punta: se
    non e' l'URL dell'API di tracing l'e-service risponde 401 'Invalid token' e dal
    codice non e' correggibile. Ritorna la lista dei disallineamenti (vuota = ok)."""
    difetti = []
    if claims.get("purposeId") and parametri_tracing.purposeid and claims["purposeId"] != parametri_tracing.purposeid:
        difetti.append(f"purposeId del voucher {claims['purposeId']} != configurato {parametri_tracing.purposeid}")
    atteso = getattr(parametri_tracing, "eservice_id", "") or ""
    if atteso and claims.get("eserviceId") and claims["eserviceId"] != atteso:
        difetti.append(f"eserviceId del voucher {claims['eserviceId']} != configurato {atteso}")
    return difetti


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

    try:
        voucher, audit = get_tracing_bearer(parametri_tracing, user_id)
    except Exception as e:
        return {"errore": "Voucher non ottenuto", "dettaglio": str(e)}

    # solo metadati della chiamata (invariante 8): nessun dato anagrafico, nessun token
    claims = jwt.decode(voucher, options={"verify_signature": False})
    difetti = confronta_identificatori(claims, parametri_tracing)

    api_url = f"{target.rstrip('/')}/status"
    # prepara il body per la richiesta GET e relativo digest (body vuoto)
    body = ""
    body_digest = hashlib.sha256(body.encode('UTF-8'))
    digest = 'SHA-256=' + base64.b64encode(body_digest.digest()).decode('UTF-8')

    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=15)
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

    response = requests.get(api_url, headers=headers, verify=False, timeout=30)

    if response.status_code not in [200, 201]:
        return {"errore": f"Status code {response.status_code}", "dettaglio": response.text}

    # /status e' pubblico (security: [] nella OpenAPI del tracing): risponde 200 anche senza
    # Authorization. Da solo non prova nulla, quindi si verifica anche un endpoint autenticato.
    verifica_voucher = chiamata_api_tracing(request, "GET", "/tracings", params={"offset": 0, "limit": 1})
    if "errore" in verifica_voucher:
        # il JS della pagina mostra solo 'dettaglio', quindi qui va la diagnosi completa
        messaggi = [str(verifica_voucher.get("dettaglio"))]
        messaggi.append(f"aud del voucher: {claims.get('aud')} - l'API di tracing accetta solo la "
                        f"audience dichiarata dal proprio descrittore")
        messaggi += difetti
        return {
            "errore": f"Servizio raggiungibile ma voucher rifiutato ({verifica_voucher['errore']})",
            "dettaglio": "  |  ".join(messaggi),
        }

    return {"status": "OK", "dettaglio": "Servizio attivo, voucher accettato"}


def chiamata_api_tracing(request, method, endpoint, params=None, data=None, files=None):
    """Helper generico per chiamate API Tracing con firma."""
    try:
        parametri_tracing = TracingParametri.objects.get(id=1)
    except TracingParametri.DoesNotExist:
        return {"errore": "Parametri non configurati"}

    user_id = request.user.username if request.user.is_authenticated else 'admin'
    voucher, audit = get_tracing_bearer(parametri_tracing, user_id)

    url = f"{parametri_tracing.target.rstrip('/')}{endpoint}"

    kid = parametri_tracing.kid
    alg = parametri_tracing.alg
    typ = parametri_tracing.typ
    clientid = parametri_tracing.clientid
    audience = parametri_tracing.audience
    purposeid = parametri_tracing.purposeid
    private_key = parametri_tracing.private_key

    tracing_audience = parametri_tracing.tracing_audience or parametri_tracing.audience

    issued = datetime.datetime.utcnow()
    expire_in = issued + datetime.timedelta(minutes=15)
    headers_rsa = {"kid": kid, "alg": alg, "typ": typ}

    try:
        if method == "GET":
            # body vuoto per GET
            body = ""
            body_digest = hashlib.sha256(body.encode('UTF-8'))
            digest = 'SHA-256=' + base64.b64encode(body_digest.digest()).decode('UTF-8')

            payload = {
                "iss": clientid,
                "aud": tracing_audience,   # aud del voucher, non dell'e-service
                "purposeId": purposeid,
                "sub": clientid,
                "jti": str(uuid.uuid4()),
                "iat": issued,
                "nbf": issued,
                "exp": expire_in,
                "signed_headers": [{"digest": digest}]
            }
            signature = jwt.encode(payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)

            headers = {
                "Accept": "application/json",
                "Digest": digest,
                "Authorization": "Bearer " + voucher,
                "Agid-JWT-TrackingEvidence": audit,
                "Agid-JWT-Signature": signature
            }
            response = requests.get(url, headers=headers, params=params, verify=False, timeout=30)

        else:  # POST multipart
            session = requests.Session()
            req = requests.Request(
                method="POST",
                url=url,
                data=data,
                files=files,
                headers={}
            )
            prepared = session.prepare_request(req)

            body_bytes = prepared.body if prepared.body is not None else b""
            if isinstance(body_bytes, str):
                body_bytes = body_bytes.encode("utf-8")

            body_digest = hashlib.sha256(body_bytes)
            digest = 'SHA-256=' + base64.b64encode(body_digest.digest()).decode('UTF-8')

            signed_headers = [{"digest": digest}]
            content_type = prepared.headers.get("Content-Type")
            if content_type:
                signed_headers.append({"content-type": content_type})

            payload = {
                "iss": clientid,
                "aud": tracing_audience,   # aud del voucher, non dell'e-service
                "purposeId": purposeid,
                "sub": clientid,
                "jti": str(uuid.uuid4()),
                "iat": issued,
                "nbf": issued,
                "exp": expire_in,
                "signed_headers": signed_headers
            }
            signature = jwt.encode(payload, private_key, algorithm=Algorithms.RS256, headers=headers_rsa)

            prepared.headers.update({
                "Authorization": f"Bearer {voucher}",
                "Agid-JWT-TrackingEvidence": audit,
                "Agid-JWT-Signature": signature,
                "Accept": "application/json",
                "Digest": digest
            })
            response = session.send(prepared, verify=False, timeout=120)

        try:
            token_id = jwt.decode(voucher, options={"verify_signature": False}).get("jti")
        except Exception:
            token_id = None
        salva_log(request.user, "Tracing", f"{method} {endpoint}", purposeid, response.status_code, token_id)

        if response.status_code == 200:
            return response.json()
        else:
            try:
                errore_api = response.json()
            except Exception:
                errore_api = response.text
            if not settings.DEBUG:
                # invariante 8: fuori dal debug vanno solo i metadati della chiamata
                return {"errore": response.status_code, "dettaglio": errore_api}
            # Debug: decodifica JWT senza verifica firma per ispezionare i claim
            try:
                voucher_claims = jwt.decode(voucher, options={"verify_signature": False})
            except Exception as ex:
                voucher_claims = f"(non decodificabile: {ex})"
            try:
                audit_claims = jwt.decode(audit, options={"verify_signature": False})
            except Exception as ex:
                audit_claims = f"(non decodificabile: {ex})"
            try:
                signature_claims = jwt.decode(signature, options={"verify_signature": False})
            except Exception as ex:
                signature_claims = f"(non decodificabile: {ex})"

            return {
                "errore": response.status_code,
                "dettaglio": errore_api,
                "debug": {
                    "url": url,
                    "method": method,
                    "digest": digest,
                    "voucher_claims": voucher_claims,
                    "audit_claims": audit_claims,
                    "signature_claims": signature_claims,
                }
            }

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


@login_required
def ajax_export_tracing_csv(request):
    if request.method != 'GET':
        return JsonResponse({"errore": "Metodo non consentito"}, status=405)

    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({"errore": "Data obbligatoria"}, status=400)

    try:
        selected_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({"errore": "Formato data non valido (YYYY-MM-DD)"}, status=400)

    logs = (
        Logs.objects.filter(timestamp__date=selected_date)
        .exclude(purposeid__isnull=True)
        .exclude(purposeid__exact="")
        .exclude(resp_status__isnull=True)
        .exclude(token_id__isnull=True)
        .exclude(token_id__exact="")
        .values('purposeid', 'resp_status', 'token_id')
        .annotate(requests_count=Count('id'))
        .order_by('purposeid', 'resp_status', 'token_id')
    )

    filename = f"Tracing_{selected_date.isoformat()}.csv"
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename=\"{filename}\"'},
    )

    writer = csv.writer(response, delimiter=',')
    writer.writerow(['date', 'purpose_id', 'status', 'token_id', 'requests_count'])

    for row in logs:
        writer.writerow([
            selected_date.isoformat(),
            row.get('purposeid') or '',
            row.get('resp_status') if row.get('resp_status') is not None else '',
            row.get('token_id') or '',
            row.get('requests_count') or 0,
        ])

    return response



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
        tracing_audience = request.POST.get('tracing_audience') or ''
        baseurlauth = request.POST.get('baseurlauth')
        target = request.POST.get('target')
        clientid = request.POST.get('clientid')
        private_key = request.POST.get('private_key')
        ver_eservice = request.POST.get('ver_eservice')
        eservice_id = request.POST.get('eservice_id') or ''

        # solo parole chiave: i campi positional finiscono fuori di uno da quando
        # tracing_audience e' stato inserito nel modello prima di baseurlauth
        dati = TracingParametri(
            id=1, kid=kid, alg=alg, typ=typ, iss=iss, sub=sub, aud=aud,
            purposeid=purposeid, audience=audience, tracing_audience=tracing_audience,
            baseurlauth=baseurlauth, target=target, clientid=clientid,
            private_key=private_key, ver_eservice=ver_eservice, eservice_id=eservice_id,
        )
        dati.save()
        salva_log(request.user, "Impostazioni Tracing", "modifica parametri")
        
    parametri_tracing = TracingParametri.objects.all()

    return render(request, 'impostazioni_tracing.html', {'parametri_tracing': parametri_tracing})
