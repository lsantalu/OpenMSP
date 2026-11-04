"""Client AgID/PDND - unico punto per "asserzione client -> voucher".

Sostituisce le copie che vivevano dentro i moduli servizio (`inad_get_bearer`,
`_get_inps_token`, `registro_imprese_get_bearer`: tre funzioni, ~140 righe,
stesso protocollo). Le copie rimaste negli altri servizi migrano qui una alla
volta; il traffico in uscita di ciascuno e' congelato da `OpenMSP/tests.py`
prima di tagliare.

Perche' questa forma:
  - l'interfaccia e' una funzione e un portaincolla: `parametri` e' qualsiasi
    riga con `kid alg typ iss sub aud purposeid baseurlauth private_key`, cioe'
    qualsiasi tabella `*_parametri` del progetto (le quattro esistenti hanno le
    stesse identiche colonne). Niente `Credenziali` intermedi, niente
    `da_tabella()`: la riga arriva gia' formata dal chiamante, che sa quale
    tabella leggere (`inad_parametri`, `inps_isee_parametri`, ...);
  - nessuna eccezione di rete intrappolata: se l'autority non e' raggiungibile
    l'errore sale al chiamante, come facevano le tre copie. Sono intrappolati
    solo i due guasti che le copie gestivano: risposta non JSON e voucher non
    decodificabile;
  - `client_id` nei campi del form e' `iss`, non la colonna `clientid`: tutte e
    tre le copie lo facevano, e la colonna resta letta altrove per il target.

La famiglia che firma anche la chiamata (anpr, e poi anis, mit, cassa_forense,
tracing, anncsu) passa da qui con i pezzi separati: `audit` -> `asserzione(digest=...)`
-> `voucher(asserzione_client=...)` -> `firma` -> `intestazioni`. Due avvertenze,
perche' quelle sei copie non sono tutte uguali:
  - `verifica` e la scadenza vanno passati espliciti, non lasciati al default:
    `tracing` firma voucher da 15 minuti e `anncsu` e' l'unico che verifica il TLS;
    gli altri cinque chiamano con `verifica=False` (debito ereditato, AGENTS.md r2);
  - prima di migrare una copia, congelarne il filo come fa `OpenMSP/tests.py`.

Esegui: env/bin/python manage.py test OpenMSP
"""

import base64
import datetime
import hashlib
import random
import uuid

import jwt
import requests

SCADENZA_MINUTI = 43200
TIMEOUT = 30
URL_TOKEN = '/token.oauth2'
ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
CONTENT_TYPE = 'application/x-www-form-urlencoded'
CONTENT_TYPE_JSON = 'application/json'
CODIFICA = 'UTF-8'
UBICAZIONE = 'PortaleOpenMSP'
LOA = 'LoA2'


def _testa(parametri):
    """L'intestazione fissa di ogni JWT AgID: dice all'autority con che chiave firmare."""
    return {'kid': parametri.kid, 'alg': parametri.alg, 'typ': parametri.typ}


def _cliente(parametri):
    """La colonna `clientid`: e' l'emittente per la sola famiglia che firma la chiamata.

    La usano `audit` e `firma`, chiamate solo da anpr/anis/mit/cassa_forense/tracing/anncsu;
    la famiglia che prende appena il voucher usa invece la colonna `iss` (vedi
    `asserzione_client`). Le righe oggi hanno i due valori uguali, ma le copie sono scritte
    cosi' e l'autority legge quello: non unificare le due cose perche' oggi coincidono.
    """
    return parametri.clientid or parametri.iss


def asserzione_client(parametri, *, digest=None, issuer=None, subject=None, emesso=None,
                      scadenza_minuti=SCADENZA_MINUTI):
    """Asserzione client da dare a `voucher`: cio' che autorizza a chiedere il token.

    `digest` e' l'hash esadecimale dell'audit, e chiedono solo i servizi che firmano
    anche la chiamata ai dati (`anpr`, `anis`, `mit`, `cassa_forense`, `tracing`, `anncsu`).
    `emesso` in comune fra audit, asserzione e firma: le copie lo usano cosi', e la
    scadenza dei tre JWT deve coincidere.

    `issuer`/`subject` sono chi emette e chi e' soggetto: i default sono le colonne `iss`
    e `sub`, cioe' la famiglia solo-voucher (`inad`, `inps`, `registro_imprese`). Chi migra
    un servizio passato da `audit` passa `clientid` su entrambi, qui e in `issuer` di
    `voucher`: e' cosi' che sono scritte anpr/anis/mit/cassa_forense/tracing/anncsu.
    """
    emesso = emesso or datetime.datetime.utcnow()
    return jwt.encode({
        'iss': issuer or parametri.iss,
        'sub': subject or parametri.sub,
        'aud': parametri.aud,
        'purposeId': parametri.purposeid,
        'jti': str(uuid.uuid4()),
        'iat': emesso,
        'exp': emesso + datetime.timedelta(minutes=scadenza_minuti),
        **({'digest': {'alg': 'SHA256', 'value': digest}} if digest else {}),
    }, parametri.private_key, algorithm='RS256', headers=_testa(parametri))


def audit(parametri, user_id, *, emesso=None, scadenza_minuti=SCADENZA_MINUTI,
          ubicazione=UBICAZIONE, loa=LOA, subject=None, audience=None):
    """Audit JWT (header `Agid-JWT-TrackingEvidence`) e il suo digest, da dare ad `asserzione_client`.

    Dice chi ha interrogato e perche', ed e' la parte che l'erogatore vuole indipendente
    dal voucher: per questo ha `audience` (l'e-service) e non `aud` (l'autority), e un
    `dnonce` suo. Ritorna `(audit, hash_esadecimale)`.

    `subject` e' il claim `sub`, e lo chiede solo ANNCSU (`sub` = `clientid`): anpr, anis,
    mit, cassa_forense e tracing l'audit lo mandano senza, e un `sub` messo per default
    sarebbe traffica nuova su servizi gia' a terra.

    `audience` scavalca la colonna `audience`: tracing la usa diversa, perche' la tracing
    API sta su un altro aud (`tracing_audience`) rispetto agli e-service normali.
    """
    emesso = emesso or datetime.datetime.utcnow()
    prova = jwt.encode({
        'userID': user_id,
        'userLocation': ubicazione,
        'LoA': loa,
        'iss': _cliente(parametri),
        **({'sub': subject} if subject else {}),
        'aud': audience or parametri.audience,
        'purposeId': parametri.purposeid,
        'dnonce': random.randint(1000000000000, 9999999999999),
        'jti': str(uuid.uuid4()),
        'iat': emesso,
        'nbf': emesso,
        'exp': emesso + datetime.timedelta(minutes=scadenza_minuti),
    }, parametri.private_key, algorithm='RS256', headers=_testa(parametri))
    return prova, hashlib.sha256(prova.encode(CODIFICA)).hexdigest()


def digest_body(corpo):
    """Header `Digest` della chiamata ai dati: `SHA-256=<base64>` sul body gia' codificato."""
    return 'SHA-256=' + base64.b64encode(
        hashlib.sha256(corpo.encode(CODIFICA)).digest()).decode()


def firma(parametri, digest, *, content_type=CONTENT_TYPE_JSON, content_encoding=CODIFICA,
          emesso=None, scadenza_minuti=SCADENZA_MINUTI):
    """Header `Agid-JWT-Signature`: firma il Digest e i due header che lo accompagnano."""
    emesso = emesso or datetime.datetime.utcnow()
    return jwt.encode({
        'iss': _cliente(parametri),
        'aud': parametri.audience,
        'purposeId': parametri.purposeid,
        'sub': _cliente(parametri),
        'jti': str(uuid.uuid4()),
        'iat': emesso,
        'nbf': emesso,
        'exp': emesso + datetime.timedelta(minutes=scadenza_minuti),
        'signed_headers': [
            {'digest': digest},
            {'content-type': content_type},
            {'content-encoding': content_encoding},
        ],
    }, parametri.private_key, algorithm='RS256', headers=_testa(parametri))


def intestazioni(parametri, voucher, prova, digest, *, content_type=CONTENT_TYPE_JSON,
                 content_encoding=CODIFICA, accettazione='application/json', emesso=None,
                 scadenza_minuti=SCADENZA_MINUTI):
    """Gli header della chiamata dati firmata: `Agid-JWT-Signature` sopra, voucher in mezzo.

    `emesso` va passato e va condiviso con audit e asserzione: sono tre JWT della stessa
    transazione e la loro scadenza deve coincidere. Vale anche per `scadenza_minuti`, che
    chi ha token corti (mit: 5 minuti) deve poter dire anche alla firma.
    """
    return {
        'Accept': accettazione,
        'Content-Type': content_type,
        'Content-Encoding': content_encoding,
        'Digest': digest,
        'Authorization': 'Bearer ' + voucher,
        'Agid-JWT-TrackingEvidence': prova,
        'Agid-JWT-Signature': firma(parametri, digest, content_type=content_type,
                                    content_encoding=content_encoding, emesso=emesso,
                                    scadenza_minuti=scadenza_minuti),
    }


def https(valore):
    """Host senza schema in tabella: le copie a terra usavano `HTTPSConnection`, che lo
    intendeva da se'. Con `requests` lo schema serve, e `tracing.baseurlauth` e' proprio
    `auth.att.interop.pagopa.it` senza nulla davanti: senza questa normalizzazione il
    client unico avrebbe rotto tracing su tutti i deploy esistenti.
    """
    testo = str(valore or '')
    return testo if '://' in testo else 'https://' + testo


def voucher(parametri, *, asserzione=None, issuer=None, scadenza_minuti=SCADENZA_MINUTI,
            timeout=TIMEOUT, verifica=True):
    """Ritorna `(voucher, token_id)` per un servizio AgID/PDND.

    `token_id` e' il `jti` del voucher: serve all'audit (`utils.salva_log`), che
    resta responsabilita' del chiamante, non del trasporto.

    Ritorna `('', None)` se l'autority non emette il voucher o risponde in un
    formato che non e' JSON; `(voucher, None)` se il voucher non e' decodificabile.
    Le eccezioni di rete non sono intercettate.
    """
    emesso = datetime.datetime.utcnow()
    asserzione = asserzione or asserzione_client(parametri, emesso=emesso, issuer=issuer,
                                                 scadenza_minuti=scadenza_minuti)

    risposta = requests.post(
        https(parametri.baseurlauth) + URL_TOKEN,
        data={
            'client_id': issuer or parametri.iss,
            'client_assertion': asserzione,
            'client_assertion_type': ASSERTION_TYPE,
            'grant_type': 'client_credentials',
        },
        headers={'Content-Type': CONTENT_TYPE},
        timeout=timeout,
        verify=verifica,
    )

    try:
        corpo = risposta.json()
    except ValueError:
        # autority non utilizzabile: il chiamante rendiconto l'errore invece di esplodere
        return '', None

    token = corpo.get('access_token', '')
    try:
        return token, jwt.decode(token, options={'verify_signature': False}).get('jti')
    except jwt.PyJWTError:
        return token, None
