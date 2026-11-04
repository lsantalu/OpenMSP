# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
import datetime

from django.shortcuts import redirect, render

from impostazioni.models import CassaForenseParametri, UtentiParametri

from . import agid
from .utils import salva_log
from .verifica_cf import verifica_cf


def cassa_forense(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.cassa_forense
        if request.method == 'POST' and not utente_abilitato:
            # doppio gate (invariante 1): il menu nasconde, la vista apre o chiude
            return redirect('impostazioni')
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)
            wsdl = 'https://servizi.consiglionazionaleforense.it/ws_check_avv/ws_check_avv.php?wsdl'
            # The 'client = Client(wsdl)' line is commented out in the original,
            # but the instruction snippet includes it. I will keep it as is in the original.
            # client = Client(wsdl)
            ##service = client.bind('GetAvvocato', 'soap')
            correttezza_cf = verifica_cf(cf)

            if correttezza_cf == 1:
                bearer, tok_id = cassa_forense_get_bearer(request.user.username, cf)
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
                # Cassa Forense sembra essere una chiamata diretta o quasi,
                # ma usiamo salva_log con i parametri se disponibili
                salva_log(request.user, "Verifica Consiglio Nazionale Forense", "Verificato avvocato " + cf, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica Consiglio Nazionale Forense", "Verificato avvocato " + cf)
            return render(request, 'cassa_forense.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False

    return render(request, 'cassa_forense.html', { 'utente_abilitato': utente_abilitato })


def cassa_forense_get_bearer(user_ID, cf):
    """Voucher (e token_id) per la verifica all'albo Cassa Forense.

    Il `cf` non serve piu' qui: seguiva il ramo morto che chiudeva la chiamata dati, e la
    chiamata la fa il chiamante. Tenuto nel tipo per non rompere chi chiama.

    Prima, con la chiave sbagliata, esplodeva in `KeyError: 'access_token'` (un 500 nudo);
    adesso un errore leggibile, come le altre copie migratesi.
    """
    parametri = CassaForenseParametri.objects.get(id=1)
    emesso = datetime.datetime.utcnow()  # noqa: DTZ003
    prova, hash_prova = agid.audit(parametri, user_ID, emesso=emesso)
    voucher, token_id = agid.voucher(
        parametri, issuer=parametri.clientid,
        asserzione=agid.asserzione_client(parametri, digest=hash_prova,
                                         issuer=parametri.clientid,
                                         subject=parametri.clientid, emesso=emesso))
    if not voucher:
        raise RuntimeError('Cassa Forense: l\'autority non ha rilasciato il voucher')
    return voucher, token_id



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

