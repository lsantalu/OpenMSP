# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
import datetime
import json

import requests
from django.shortcuts import redirect, render

from impostazioni.models import (
    MitParametri,
    MitServizi,
    ServiziParametri,
    UtentiParametri,
)

from . import agid
from .utils import converti_data, salva_log, svuota_none
from .verifica_cf import verifica_cf

SKEW = 60               # MIT orologia stretta: il token nasce 60 secondi nel passato
SCADENZA_VOUCHER = 5    # e dura 5 minuti, non i 30 giorni del default


def mit_get_request(user_ID, cf, id_caso):
    parametri_mit = MitParametri.objects.get(id=id_caso)

    purposeid = parametri_mit.purposeid
    target = parametri_mit.target
    clientid = parametri_mit.clientid
    if id_caso == 4: ##Targhe
        richiesta_data = {
            "targa": cf,
            "dataOraVerifica": datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),  # noqa: UP017  (datetime.UTC esiste da 3.11, docker/Dockerfile dichiara python:3.10-slim)
            "intervalloDiTolleranza": 0
        }
        richiesta = json.dumps(richiesta_data)
    else:
        richiesta = f'{{"codiceFiscale":"{cf}"}}'

    # MIT e' l'unico servizio con lo skew di clock: il token nasce 60 secondi nel
    # passato e dura 5 minuti, non i 30 giorni del default (MIT orologia stretta).
    emesso = datetime.datetime.utcnow() - datetime.timedelta(seconds=SKEW)  # noqa: DTZ003
    prova, hash_prova = agid.audit(parametri_mit, user_ID, emesso=emesso,
                                   scadenza_minuti=SCADENZA_VOUCHER)
    # `agid.voucher` lascia salire gli errori di rete (e' il contratto del client): HEAD li
    # rendiconta qui come TOKEN_ERR, e un'autority giu' dev'essere una card, non un 500
    try:
        voucher, token_id = agid.voucher(
            parametri_mit, issuer=clientid,
            asserzione=agid.asserzione_client(parametri_mit, digest=hash_prova,
                                             issuer=clientid, subject=clientid, emesso=emesso,
                                             scadenza_minuti=SCADENZA_VOUCHER))
    except requests.RequestException as e:
        return {
            "esito": {
                "codice": "TOKEN_ERR",
                "descrizione": f"Eccezione durante richiesta Token: {str(e)}"
            }
        }, 500, purposeid, None
    if not voucher:
        return {
            "esito": {
                "codice": "TOKEN_ERR",
                "descrizione": "L'autority non ha rilasciato il voucher"
            }
        }, 500, purposeid, None

    digest = agid.digest_body(richiesta)
    # `status_code` nasce vuoto: i due `except` sotto lo rendono nel terzo valore, e se
    # la POST esplode lui non e' mai stato assegnato (a HEAD quel ritorno rendeva 1
    # valore e non ci arrivava mai, percio' il buco era invisibile)
    status_code = None
    response = None
    try:
        response = requests.post(target, data=richiesta.encode(agid.CODIFICA),
                                 headers=agid.intestazioni(parametri_mit, voucher, prova,
                                                          digest, emesso=emesso,
                                                          scadenza_minuti=SCADENZA_VOUCHER),
                                 verify=False, timeout=30)  # noqa: S501
        status_code = response.status_code
        if response.status_code != 200:
            return {
                "esito": {
                    "codice": str(response.status_code),
                    "descrizione": f"Errore API MIT: {response.text[:200]}"
                }
            }, status_code, purposeid, token_id
        return response.json(), status_code, purposeid, token_id
    except json.JSONDecodeError:
        return {
            "esito": {
                "codice": "JSON_ERR",
                "descrizione": f"Risposta non valida dal server (non JSON): "
                               f"{(response.text if response else '')[:200]}"
            }
        }, status_code, purposeid, token_id
    except Exception as e:
        return {
            "esito": {
                "codice": "network_error",
                "descrizione": str(e)
            }
        }, status_code, purposeid, token_id


def mit_dettaglio_cude(request):
    utente_abilitato = False        # un anonimo non deve esplodere in UnboundLocalError
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
                res, status, purp_id, tok_id = mit_get_request(request.user.username, cf, 3)
                data.append(res)
                data = converti_data(data)
                salva_log(request.user, "Verifica MIT - Whitelist", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica MIT - Whitelist", "Verificato utente " + cf)

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
                res, status, purp_id, tok_id = mit_get_request(request.user.username, cf, 2)
                data.append(res)
                data = converti_data(data)
                salva_log(request.user, "Verifica MIT - Lista Veicoli", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica MIT - Lista Veicoli", "Verificato utente " + cf)

            return render(request, 'mit_lista_veicoli.html', {'data': data, 'utente_abilitato': utente_abilitato })

    return render(request, 'mit_lista_veicoli.html', { 'utente_abilitato': utente_abilitato })


def mit_verifica_targa(request):
    utente_abilitato = False        # un anonimo non deve esplodere in UnboundLocalError
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
    svuota_none(parametri_mit)

    if request.method == 'POST':
        active_tab = request.POST.get("active_tab", "").replace("tab", "")

        try:
            active_id = int(active_tab)
        except ValueError:
            active_id = None

        posizione_servizio = list(
            ServiziParametri.objects.filter(gruppo_id=5)
            .order_by('id')
            .values_list('attivo', flat=True)
        )

        ids_to_save = [active_id] if active_id else range(1, MitParametri.objects.count() + 1)

        for i in ids_to_save:
            if i and i <= len(posizione_servizio) and posizione_servizio[i - 1]:
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

        if active_id:
            return redirect(f"{request.path}#tab{active_id}")
        return redirect(request.path)

    return render(request, 'impostazioni_mit.html', { 'servizi_mit': servizi_mit, 'parametri_mit': parametri_mit })
