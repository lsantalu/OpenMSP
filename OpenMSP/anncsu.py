# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
from django.shortcuts import redirect, render

from impostazioni.models import AnncsuParametri
from impostazioni.models import UtentiParametri

from .utils import salva_log


# Le 8 operazioni di ANNCSU - Consultazione, nell'ordine della guida tecnica (§2).
# Qui stanno solo come testo: la pagina rende la descrizione del servizio, non interroga
# ancora nulla. Quando si scrive il client diventano i path da appendere a
# AnncsuParametri.target (POST JSON: `denom`/`denomparz` in chiaro, il base64 serve solo in GET).
ANNCSU_OPERAZIONI = [
    ('esisteodonimo', 'Esistenza di un odonimo nello stradario del Comune', 'codcom, denom'),
    ('esisteaccesso', 'Esistenza di un accesso per l\'odonimo indicato', 'codcom, denom, accesso'),
    ('elencoodonimi', 'Aree di circolazione per denominazione anche parziale', 'codcom, denomparz'),
    ('elencoaccessi', 'Accessi di un\'area di circolazione, anche per valori parziali', 'codcom, denom, accparz'),
    ('elencoodonimiprog', 'Odonimi del Comune con i progressivi nazionali', 'codcom, denomparz'),
    ('elencoaccessiprog', 'Accessi di un\'area di circolazione con progressivo nazionale', 'prognaz, accparz'),
    ('prognazarea', 'Dati di un\'area di circolazione dal progressivo nazionale', 'prognaz'),
    ('prognazacc', 'Dati di un accesso dal progressivo nazionale', 'prognazacc'),
]


def anncsu_consultazione(request):
    """Pagina di servizio: al momento solo la descrizione dell'e-service.

    Nessun salva_log: la vista non interroga l'erogatore (invariante 2: una riga in logs
    per ogni interrogazione, non per ogni apertura di pagina).
    """
    utente_abilitato = False
    if request.user.id:
        # filter().first(): un utente senza riga in utenti_parametri non deve mandare in errore la pagina
        utente_abilitato = bool(UtentiParametri.objects.filter(id=request.user.id)
                                .values_list('anncsu', flat=True).first())
    return render(request, 'anncsu.html', {'utente_abilitato': utente_abilitato,
                                          'operazioni': ANNCSU_OPERAZIONI})


def impostazioni_anncsu(request):
    parametri_anncsu = AnncsuParametri.objects.all()
    if request.method == 'POST':
        # Gli id delle FK si possono passare solo per posizione: il campo si chiama servizio_id
        # quanto la colonna, quindi il descrittore si interpone e per keyword pretende
        # l'istanza AnncsuServizi (ValueError). MitParametri/AnprParametri fanno cosi'.
        valori = [request.POST.get(c) for c in
                  ('kid', 'alg', 'typ', 'iss', 'sub', 'aud', 'purposeid', 'audience',
                   'baseurlauth', 'target', 'clientid')]
        # una textarea lasciata vuota non deve cancellare la chiave gia' configurata
        chiave = request.POST.get('private_key') or \
            AnncsuParametri.objects.filter(id=1).values_list('private_key', flat=True).first() or ''
        AnncsuParametri(1, 1, *valori, chiave, request.POST.get('ver_eservice')).save()
        salva_log(request.user, "Impostazioni ANNCSU", "modifica parametri")
        return redirect(request.path)
    return render(request, 'impostazioni_anncsu.html', {'parametri_anncsu': parametri_anncsu})
