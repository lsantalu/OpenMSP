from django.shortcuts import render

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import AnprServizi
from impostazioni.models import AnprParametri

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



def anpr_get_request(user_ID, id_anpr, id_caso):
    parametri_anpr = AnprParametri.objects.get(id=id_caso)
    caso = ''
    if id_caso == 1:
        caso = "C001"
    elif id_caso == 2:
        caso = "C015"
    elif id_caso == 3:
        caso = "C017"
    elif id_caso == 4:
        caso = "C018"
    elif id_caso == 5:
        caso = "C020"
    elif id_caso == 6:
        caso = "C021"
    else: ##Recupero idANPR
        caso = "C030"


    kid = parametri_anpr.kid
    alg = parametri_anpr.alg
    typ = parametri_anpr.typ
    issuer = parametri_anpr.iss
    subject = parametri_anpr.sub
    aud = parametri_anpr.aud
    purposeid = parametri_anpr.purposeid
    audience = parametri_anpr.audience
    baseurlauth = parametri_anpr.baseurlauth
    target = parametri_anpr.target
    clientid = parametri_anpr.clientid
    private_key = parametri_anpr.private_key
    userid = user_ID
    location = 'PortaleOpenMSP'
    loa = 'LoA2'
    if id_caso == 7: ##Recupero idANPR
        richiesta = f'{{"idOperazioneClient":"1","criteriRicerca":{{"codiceFiscale":"{id_anpr}"}},' \
            f'"datiRichiesta":{{"dataRiferimentoRichiesta":"{datetime.datetime.utcnow().strftime("%Y-%m-%d")}",' \
            f'"motivoRichiesta":"Verifica_anagrafica","casoUso":"{caso}"}}}}'
    else:
        richiesta = f'{{"idOperazioneClient":"1","criteriRicerca":{{"idANPR":"{id_anpr}"}},' \
            f'"datiRichiesta":{{"dataRiferimentoRichiesta":"{datetime.datetime.utcnow().strftime("%Y-%m-%d")}",' \
            f'"motivoRichiesta":"Verifica_anagrafica","casoUso":"{caso}"}}}}'

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

    response = requests.post(api_url, data=body.encode('UTF-8'), headers=headers, verify=False)
    if id_caso == 7:
        aux = response.json()
        if 'listaSoggetti' in aux:
            return aux['listaSoggetti']['datiSoggetto'][0]['identificativi']['idANPR']
        else:
            return 'ZZZZZZZZZ'
    else:
        return response.json()


def anpr_cittadinanza(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C018
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                data.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 4))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")
            salva_log(request.user,"Verifica ANPR - C018 - Cittadinanza", "Verificato utente " + cf )
            return render(request, 'anpr_cittadinanza.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_cittadinanza.html', { 'utente_abilitato': utente_abilitato })


def anpr_generalita(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C015
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                data.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 2))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")
            salva_log(request.user,"Verifica ANPR - C015 - Generalità", "Verificato utente " + cf)

            return render(request, 'anpr_generalita.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_generalita.html', { 'utente_abilitato': utente_abilitato })


def anpr_matrimonio(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C017
        if request.method == 'POST':
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

            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                data.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 3))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")

            salva_log(request.user,"Verifica ANPR - C017 - Matrimonio", "Verificato utente " + cf)
            return render(request, 'anpr_matrimonio.html', {'data': data, 'cessazione': cessazione_matrimonio_choices, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_matrimonio.html', { 'utente_abilitato': utente_abilitato })


def anpr_notifica(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C001
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
            salva_log(request.user,"Verifica ANPR - C001 - Notifica", "Verificato utente " + cf)

            return render(request, 'anpr_notifica.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_notifica.html', { 'utente_abilitato': utente_abilitato })


def anpr_residenza(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C020
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                data.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf,7), 5))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")
            salva_log(request.user,"Verifica ANPR - C020 - Residenza", "Verificato utente " + cf )
            return render(request, 'anpr_residenza.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_residenza.html', { 'utente_abilitato': utente_abilitato })


def anpr_stato_famiglia(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.anpr_C021
        if request.method == 'POST':
            parentela_choices = [
                ('1', 'Intestatario Scheda'),
                ('2', 'Marito / Moglie'),
                ('3', 'Figlio / Figlia'),
                ('4', 'Nipote (discendente)'),
                ('5', 'Pronipote (discendente)'),
                ('6', 'Padre / Madre'),
                ('7', 'Nonno / Nonna'),
                ('8', 'Bisnonno / Bisnonna'),
                ('9', 'Fratello / Sorella'),
                ('10', 'Nipote (collaterale)'),
                ('11', 'Zio / Zia (Collaterale)'),
                ('12', 'Cugino / Cugina'),
                ('13', 'Altro Parente'),
                ('14', 'Figliastro / Figliastra'),
                ('15', 'Patrigno / Matrigna'),
                ('16', 'Genero / Nuora'),
                ('17', 'Suocero / Suocera'),
                ('18', 'Cognato / Cognata'),
                ('19', 'Fratellastro / Sorellastra'),
                ('20', 'Nipote (Affine)'),
                ('21', 'Zio / Zia (Affine)'),
                ('22', 'Altro Affine'),
                ('23', 'Convivente (con vincoli di adozione o affettivi)'),
                ('24', 'Responsabile della convivenza non affettiva'),
                ('25', 'Convivente in convivenza non affettiva'),
                ('26', 'Tutore'),
                ('28', 'Unito civilmente'),
                ('80', 'Adottato'),
                ('81', 'Nipote'),
                ('99', 'Non definito/comunicato'),
            ]

            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            correttezza_cf = verifica_cf(cf)
            if correttezza_cf == 1 or correttezza_cf == 2:
                data.append(anpr_get_request(request.user.username, anpr_get_request(request.user.username, cf, 7), 6))
                data = converti_data(data)
            else:
                data.append("Codice fiscale non corretto")
            salva_log(request.user,"Verifica ANPR - C021 - Stato famiglia", "Verificato utente " + cf )
            return render(request, 'anpr_stato_famiglia.html', {'data': data, 'parentela':parentela_choices, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'anpr_stato_famiglia.html', { 'utente_abilitato': utente_abilitato })


def impostazioni_anpr(request):
    servizi_anpr = AnprServizi.objects.all()
    parametri_anpr = AnprParametri.objects.all()

    service_active = ServiziParametri.objects.all()
    i_serv=0
    service_desc = ["" for _ in range(ServiziParametri.objects.count())]
    for servizio in service_active:
        service_desc[i_serv]= (servizio.attivo)
        i_serv += 1

    if request.method == 'POST':
        posizione_servizio = ServiziParametri.objects.filter(gruppo_id=2).values_list('id', flat=True)
        for i in range(1, AnprParametri.objects.count()+1):
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

                dati = AnprParametri(i, i, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
                dati.save()
        salva_log(request.user,"Impostazioni ANPR", "modifica parametri")

    return render(request, 'impostazioni_anpr.html', { 'servizi_anpr': servizi_anpr, 'parametri_anpr': parametri_anpr })

