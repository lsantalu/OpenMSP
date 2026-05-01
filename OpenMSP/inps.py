from django.shortcuts import render
from django.http import HttpResponse

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import GruppiParametri
from impostazioni.models import InpsIseeParametri
from impostazioni.models import InpsDurcParametri
from impostazioni.models import DatiEnte

from .utils import salva_log
from .utils import converti_data
from .verifica_cf import verifica_cf
from .verifica_cf import verifica_cf_azienda

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
import sys
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
        "aud": aud,
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
    voucher = data['access_token']
    
    # Estrae il token_id (jti) dal voucher
    try:
        decoded_token = jwt.decode(voucher, options={"verify_signature": False})
        token_id = decoded_token.get('jti')
    except:
        token_id = None
        
    return voucher, token_id


def inps_durc_singolo(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_durc_singolo
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            
            if len(cf) == 11:
                correttezza_cf = verifica_cf_azienda(cf)
            else:
                correttezza_cf = verifica_cf(cf)

            if correttezza_cf == 1 or correttezza_cf == 2:
                bearer, tok_id = inps_durc_get_bearer()
                res_data, status, purp_id = inps_durc_verifica_impresa(cf, bearer)
                if res_data and 'del' in res_data:
                    try:
                        date_str = res_data['del'].split('T')[0]
                        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        scadenza = date_obj + datetime.timedelta(days=120)
                        res_data['scadenza'] = scadenza.strftime('%Y-%m-%d')
                    except Exception as e:
                        pass
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica INPS - DURC", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica INPS - DURC", "Verificato utente " + cf)

            return render(request, 'inps_durc_singolo.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_durc_singolo.html', { 'utente_abilitato': utente_abilitato })


def inps_durc_massivo(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_durc_massivo
        if request.method == 'POST' and 'cf_csv' in request.FILES:
            csv_file = request.FILES['cf_csv']
            data = []
            cfs = []
            
            # Lettura CF dal file
            if csv_file.name.lower().endswith('.csv'):
                try:
                    csv_file_text = io.TextIOWrapper(csv_file.file, encoding='utf-8')
                    csv_reader = csv.reader(csv_file_text)
                    for row in csv_reader:
                        if row and row[0]:
                            cfs.append(row[0].strip().upper())
                except Exception as e:
                    return render(request, 'inps_durc_massivo.html', {'error': f"Errore lettura CSV: {str(e)}", 'utente_abilitato': utente_abilitato})
            elif csv_file.name.lower().endswith('.xlsx'):
                try:
                    wb = openpyxl.load_workbook(csv_file)
                    sheet = wb.active
                    for row in sheet.iter_rows(min_row=1, values_only=True):
                        if row and row[0]:
                            cfs.append(str(row[0]).strip().upper())
                except Exception as e:
                    return render(request, 'inps_durc_massivo.html', {'error': f"Errore lettura Excel: {str(e)}", 'utente_abilitato': utente_abilitato})
            
            if cfs:
                bearer, tok_id = inps_durc_get_bearer()
                for cf in cfs:
                    if len(cf) == 11:
                        correttezza_cf = verifica_cf_azienda(cf)
                    else:
                        correttezza_cf = verifica_cf(cf)
                    
                    item = {'cf': cf, 'correttezza_cf': correttezza_cf}
                    
                    if correttezza_cf == 1 or correttezza_cf == 2:
                        res_data, status, purp_id = inps_durc_verifica_impresa(cf, bearer)
                        if res_data:
                            # Calcolo scadenza come in singolo
                            if 'del' in res_data:
                                try:
                                    date_str = res_data['del'].split('T')[0]
                                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                                    scadenza = date_obj + datetime.timedelta(days=120)
                                    res_data['scadenza'] = scadenza.strftime('%Y-%m-%d')
                                except:
                                    pass
                            item['res_data'] = res_data
                            salva_log(request.user, "Verifica INPS - DURC massivo", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
                        else:
                            item['error'] = "Dati non disponibili o errore API"
                    else:
                        item['error'] = "Codice fiscale non corretto"
                    
                    data.append(item)
                
            return render(request, 'inps_durc_massivo.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_durc_massivo.html', { 'utente_abilitato': utente_abilitato })


def inps_durc_verifica_impresa(cf, bearer):
    inps_durc_parametri = InpsDurcParametri.objects.get(id=1)
    url = inps_durc_parametri.target + '/getDurcInCorsoDiValidita'
    dati_ente = DatiEnte.objects.first()


    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json" ,
        "INPS-Identity-UserId": dati_ente.cf ,
        "INPS-Identity-CodiceUfficio": "001"
        }
    data = {
        "codicefiscale": cf
        }

    ### FINO A QUA TUTTO BENE MA DOPO VA IN TIMEOUT
    response = requests.post(url, headers=headers, json=data)
    status_code = response.status_code
    purposeid = inps_durc_parametri.purposeid

    if response.status_code == 200:
        json_data = response.json()
        return json_data, status_code, purposeid
    else:
        return False, status_code, purposeid


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


def inps_durc_download(request, protocollo):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        if utente_sessione.inps_durc_singolo or utente_sessione.inps_durc_massivo:
            bearer, tok_id = inps_durc_get_bearer()
            inps_durc_parametri = InpsDurcParametri.objects.get(id=1)
            dati_ente = DatiEnte.objects.first()
            
            # Costruzione URL per il download secondo specifica YAML
            safe_protocollo = urllib.parse.quote(protocollo)
            url = f"{inps_durc_parametri.target}/downloadDURC/{safe_protocollo}/ITA"
            
            headers = {
                "Authorization": f"Bearer {bearer}",
                "INPS-Identity-UserId": dati_ente.cf,
                "INPS-Identity-CodiceUfficio": "001"
            }
            
            try:
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    res_json = response.json()
                    base64_data = res_json.get('base64')
                    
                    if base64_data:
                        # Decodifica dei dati base64 in binario
                        pdf_content = base64.b64decode(base64_data)
                        
                        file_name = f"DURC_{protocollo}.pdf"
                        django_response = HttpResponse(pdf_content, content_type='application/pdf')
                        django_response['Content-Disposition'] = f'attachment; filename="{file_name}"'
                        
                        salva_log(request.user, "Download DURC", f"Scaricato PDF per protocollo {protocollo}", purposeid=inps_durc_parametri.purposeid, resp_status=response.status_code, token_id=tok_id)
                        return django_response
                    else:
                        return HttpResponse("Dati PDF non trovati nella risposta", status=500)
                else:
                    return HttpResponse(f"Errore API INPS: {response.status_code}", status=response.status_code)
            except Exception as e:
                return HttpResponse(f"Eccezione durante il download: {str(e)}", status=500)
    
    return HttpResponse("Non autorizzato", status=403)




