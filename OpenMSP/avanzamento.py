# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: per pyright .objects e ._meta non esistono)
"""Filo comune delle estrazioni massive guidate dal navigatore (IPA, INAD, INI-PEC).

Il giro lo comanda il navigatore: un POST per codice, cosi' la card dell'overlay dice il
vero avanzamento e un file da cento codici non resta dietro un cerchio che gira senza dire
niente. La lista dei codici e il token stanno in sessione, il codice non viene dal client e
non ci torna (invariante 8: nelle risposte solo metadati).

`registro_imprese_massivo` ha il suo giro scritto nel suo modulo perche' le sue righe portano
l'indice e il JSON scaricabile; questo file e' lo stesso filo per i tre servizi la cui
risposta e' una lista di stringhe (o di dizionali IPA) che gli export rileggono gia' oggi.
"""
import json

from django.http import JsonResponse

from impostazioni.models import UtentiParametri

from .utils import cf_da_file

STATO_SESSIONE = 'estrazione_massiva'   # estrazione avviata dal navigatore, coi codici dentro
RIGHE_SESSIONE = 'multi_data'           # chiave gia' in uso: i tre export rileggono questa


def codici_da_file(allegato):
    """`(codici, errore)` dalla colonna A del file: `utils.cf_da_file` non ha un canale d'errore
    tutto suo (ritorna `None` su formato illeggibile e lascia passare l'eccezione su un XLSX
    corrotto), e la pagina ha bisogno di dire all'operatore quale dei due e' successo."""
    nome = (allegato.name or '').lower()
    formato = 'XLSX' if nome.endswith('.xlsx') else 'CSV'
    try:
        codici = cf_da_file(allegato)
    except Exception as errore:                       # noqa: BLE001 (openpyxl e csv alzano di tutto)
        return [], f"Il {formato} non e' leggibile: {errore}"
    if codici is None:
        return [], 'Il file non è un XLSX o CSV'
    return codici, ''


def avvia(request, codici, token=None):
    """Apre l'estrazione guidata dal navigatore: codici e (se il servizio ne ha uno) token.

    Il token e' un segreto in meno di quelli che il progetto gia' tiene in chiaro nelle
    tabelle `*_parametri`: vive quanto la sessione e `risposta_riga` lo butta a giro finito.

    `multi_data` si azzera qui, non a meta' giro: e' una chiave condivisa fra servizi (e fra
    le due generazioni di pagine) e `risposta_riga` appende. Senza azzeramento il giro prima
    resta in mezzo alla tabella: righe raddoppiate, e le prime vuote e rosse perche' il
    template di un servizio fa `row.split` su un dizionario dell'altro.
    """
    request.session[STATO_SESSIONE] = {'codici': list(codici), 'token': token,
                                       'fatti': 0, 'ultimo': ''}
    request.session[RIGHE_SESSIONE] = []


def esegui_tutto(request, codici, worker, fine, stato=None):
    """Tutta l'estrazione in un giro solo: il cammino senza JavaScript.

    Stesso `worker` e stesso `fine` del giro per righe: le due strade non sono due
    implementazioni della stessa estrazione.
    """
    righe = []
    for codice in codici:
        fatte, _, _ = worker(request, codice, stato)
        righe += list(fatte)
    request.session[RIGHE_SESSIONE] = righe
    fine(request, len(codici))
    return righe


def risposta_riga(request, permesso, worker, fine):
    """Una riga dell'estrazione in corso: il POST porta l'indice, la lista sta in sessione.

    `permesso` e' il nome del flag su `utenti_parametri` e il gate va riverificato qui
    (invariante 1): un segnalibro non deve bastare a chi non ha piu' il flag.
    `worker(request, codice, stato)` interrogazione dell'erogatore, che risponde
    `(righe, ultimo, errore)` e lascia da se' la propria riga in `logs` (invariante 2);
    `ultimo` e' l'etichetta della card e un modulo non ci mette un dato sensibile piu' di
    quanti il template non stampi gia' riga per riga; `prossimo` e' il codice della riga dopo,
    quello che il navigatore sta per chiedere: l'operatore guarda la card per sapere SU QUALE
    codice e', e la risposta la legge nella tabella, non in mezzo all'overlay.
    `fine(request, fatte)` il riepilogo.
    """
    if request.method != 'POST':
        return JsonResponse({'errore': 'Serve una POST'}, status=405)
    if not request.user.id or not getattr(UtentiParametri.objects.get(id=request.user.id), permesso):
        return JsonResponse({'errore': 'Utente non abilitato'}, status=403)
    estrazione = request.session.get(STATO_SESSIONE)
    if not estrazione:
        return JsonResponse({'errore': 'Nessuna estrazione in corso'}, status=400)
    try:
        indice = int(json.loads(request.body).get('indice', 0))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'errore': 'Indice non valido'}, status=400)
    codici = estrazione['codici']
    totale = len(codici)
    if not 1 <= indice <= totale:
        return JsonResponse({'errore': 'Indice fuori lista'}, status=400)
    if indice <= estrazione['fatti']:
        # filo caduto e il navigatore riprova una riga gia' fatta: l'erogatore non si interroga
        # due volte e la sessione non si riempie di duplicati
        return JsonResponse({'avanzamento': f"{estrazione['fatti']}/{totale}",
                             'ultimo': estrazione['ultimo'], 'fatto': estrazione['fatti'] >= totale})
    righe, ultimo, errore = worker(request, codici[indice - 1], estrazione)
    request.session[RIGHE_SESSIONE] = list(request.session.get(RIGHE_SESSIONE, [])) + list(righe)
    estrazione['fatti'] = indice
    estrazione['ultimo'] = ultimo
    finito = indice >= totale
    if finito:
        request.session.pop(STATO_SESSIONE)      # il token non resta in giro piu' del necessario
        fine(request, indice)
    else:
        request.session[STATO_SESSIONE] = estrazione
    return JsonResponse({'avanzamento': f"{indice}/{totale}", 'ultimo': ultimo,
                         'prossimo': codici[indice] if indice < totale else None,
                         'errore': errore, 'fatto': finito})
