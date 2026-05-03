from django.shortcuts import render
from django.http import HttpResponse

from impostazioni.models import UtentiParametri
from impostazioni.models import InpsIseeParametri
from impostazioni.models import InpsDurcParametri
from impostazioni.models import DatiEnte

from .utils import salva_log
from .utils import converti_data
from .verifica_cf import verifica_cf
from .verifica_cf import verifica_cf_azienda

import xmltodict
import urllib.parse
import base64
import datetime
import uuid
import jwt
import subprocess
import requests
import json
import io
import csv
import sys
import openpyxl

def _get_inps_token(parametri):
    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=43200)
    expire_in = issued + delta
    jti = uuid.uuid4()
    
    headers_rsa = {
        "kid": parametri.kid,
        "alg": parametri.alg,
        "typ": parametri.typ
    }

    payload = {
        "iss": parametri.iss,
        "sub": parametri.sub,
        "aud": parametri.aud,
        "purposeId": parametri.purposeid,
        "jti": str(jti),
        "iat": issued,
        "exp": expire_in
    }

    asserzione = jwt.encode(payload, parametri.private_key, algorithm="RS256", headers=headers_rsa)

    curl_command = (
        f"curl --location --silent --request POST {parametri.baseurlauth}/token.oauth2 "
        f"--header 'Content-Type: application/x-www-form-urlencoded' "
        f"--data-urlencode 'client_id={parametri.iss}' "
        f"--data-urlencode 'client_assertion={asserzione}' "
        "--data-urlencode 'client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer' "
        "--data-urlencode 'grant_type=client_credentials'"
    )

    if not sys.platform.startswith('linux'):
        curl_command = curl_command.replace("'", '"')

    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        voucher = data.get('access_token', '')
    except json.JSONDecodeError:
        voucher = ""
    
    # Estrae il token_id (jti) dal voucher
    try:
        decoded_token = jwt.decode(voucher, options={"verify_signature": False})
        token_id = decoded_token.get('jti')
    except:
        token_id = None
        
    return voucher, token_id


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
                bearer, tok_id = inps_isee_get_bearer()
                res_data, status, purp_id = RichiestaIsee(cf, bearer)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica INPS - ISEE", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica INPS - ISEE", "Verificato utente " + cf)

            return render(request, 'inps_isee.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_isee.html', { 'utente_abilitato': utente_abilitato })


def inps_isee_get_bearer():
    parametri_inps_isee = InpsIseeParametri.objects.get(id=1)
    return _get_inps_token(parametri_inps_isee)


def RichiestaIsee(cf, bearer):
    parametri_inps_isee = InpsIseeParametri.objects.get(id=1)
    url = parametri_inps_isee.target
    dati_ente = DatiEnte.objects.first()

    # SOAP Action dalla specifica WSDL
    soap_action = "http://inps.it/ConsultazioneISEE/ISvcConsultazione/ConsultazioneAttestazioneResidenti"

    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{soap_action}"',
        "INPS-Identity-UserId": dati_ente.cf,
        "INPS-Identity-CodiceUfficio": "001"
    }

    # Costruzione dell'inviluppo SOAP basato sull'XSD e sull'XML di esempio fornito
    body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:con="http://inps.it/ConsultazioneISEE">
   <soapenv:Header>
      <inps:Identity xmlns:inps="http://inps.it/">
         <UserId>{dati_ente.cf}</UserId>
         <CodiceUfficio>001</CodiceUfficio>
      </inps:Identity>
   </soapenv:Header>
   <soapenv:Body>
      <con:ConsultazioneAttestazioneResidenti>
         <con:request>
            <con:RicercaCF>
               <con:CodiceFiscale>{cf}</con:CodiceFiscale>
               <con:PrestazioneDaErogare>A1.01</con:PrestazioneDaErogare>
               <con:ProtocolloDomandaEnteErogatore>OpenMSP-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}</con:ProtocolloDomandaEnteErogatore>
               <con:StatodomandaPrestazione>Da Erogare</con:StatodomandaPrestazione>
            </con:RicercaCF>
         </con:request>
      </con:ConsultazioneAttestazioneResidenti>
   </soapenv:Body>
</soapenv:Envelope>"""

    try:
        response = requests.post(url, headers=headers, data=body.encode('utf-8'))
        status_code = response.status_code
        purposeid = parametri_inps_isee.purposeid

        if response.status_code == 200:
            try:
                # Parsing della risposta XML
                dict_data = xmltodict.parse(response.content)
                # Estrazione del risultato dal body SOAP
                envelope = dict_data.get('s:Envelope', {}) or dict_data.get('soapenv:Envelope', {}) or dict_data.get('SOAP-ENV:Envelope', {})
                body = envelope.get('s:Body', {}) or envelope.get('soapenv:Body', {}) or envelope.get('SOAP-ENV:Body', {})
                response_node = body.get('ConsultazioneAttestazioneResidentiResponse', {})
                result = response_node.get('ConsultazioneAttestazioneResidentiResult', {})
                
                # Se il risultato è vuoto, proviamo con altri prefissi possibili
                if not result:
                   for key in response_node.keys():
                       if key.endswith('ConsultazioneAttestazioneResidentiResult'):
                           result = response_node[key]
                           break

                # Decodifica dell'XML base64 se presente (contiene i dati reali dell'attestazione)
                xml_base64 = result.get('XmlEsitoAttestazione')
                if xml_base64:
                    try:
                        decoded_xml = base64.b64decode(xml_base64).decode('utf-8')
                        attestazione_dict = xmltodict.parse(decoded_xml)
                        
                        # Estrazione dei dati per il template
                        # L'XML decodificato ha come root <Attestazione>
                        att = attestazione_dict.get('Attestazione', {})
                        
                        # Mappatura campi per il template
                        result['ProtocolloMittente'] = att.get('@ProtocolloMittente')
                        result['DataSottoscrizione'] = att.get('@DataPresentazione')
                        result['DataScadenza'] = att.get('@DataScadenzaDSUCorrente')
                        
                        # Ricerca del valore ISEE (può essere in Ordinario, Ridotto, etc.)
                        ordinario = att.get('Ordinario', {})
                        isee_ord = ordinario.get('ISEEOrdinario', {})
                        valori = isee_ord.get('Valori', {})
                        result['ValoreISEE'] = valori.get('@ISEE')
                        
                    except Exception as e:
                        result['error_parsing_attestazione'] = str(e)

                return result, status_code, purposeid
            except Exception as e:
                return {"error": f"Errore nel parsing XML: {str(e)}"}, status_code, purposeid
        else:
            return False, status_code, purposeid
    except Exception as e:
        return {"error": f"Errore nella richiesta: {str(e)}"}, 500, parametri_inps_isee.purposeid


def inps_durc_get_bearer():
    parametri_inps_durc = InpsDurcParametri.objects.get(id=1)
    return _get_inps_token(parametri_inps_durc)


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

    response = requests.post(url, headers=headers, json=data)
    status_code = response.status_code
    purposeid = inps_durc_parametri.purposeid

    if response.status_code == 200:
        json_data = response.json()
        return json_data, status_code, purposeid
    else:
        return False, status_code, purposeid


def _salva_impostazioni_inps(request, modello, nome_servizio):
    if request.method == 'POST':
        campi = ['kid', 'alg', 'typ', 'iss', 'sub', 'aud', 'purposeid', 'audience', 'baseurlauth', 'target', 'clientid', 'private_key', 'ver_eservice']
        dati_post = {campo: request.POST.get(campo) for campo in campi}
        dati = modello(id=1, **dati_post)
        dati.save()
        salva_log(request.user, f"Impostazioni INPS - {nome_servizio}", "modifica parametri")


def impostazioni_inps_durc(request):
    _salva_impostazioni_inps(request, InpsDurcParametri, "DURC")
    parametri_inps_durc = InpsDurcParametri.objects.all()
    return render(request, 'impostazioni_inps_durc.html', {'parametri_inps_durc': parametri_inps_durc})


def impostazioni_inps_isee(request):
    _salva_impostazioni_inps(request, InpsIseeParametri, "ISEE")
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

