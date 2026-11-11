"""Le tile della mappa le chiede il navigatore al portale, non all'erogatore di tile.

Il motivo e' terra terra: `tile.openstreetmap.org` risponde un manifesto con scritto 403
dall'uscita di qua dentro, e da un navigatore non c'e' rimedio possibile, perche' per le
`<img>` non si scegle ne' referer ne' User-Agent. Qui la richiesta la fa il server, con lo
User-Agent del portale, e la riverba. Il disegno sta in `docs/2026-11-11-anncsu-tile-proxy-design.md`.

Due cose che questo file **non** e', e va difeso:
- non e' un mirror: la cache serve gli utenti del portale, con un TTL, non il mondo;
- non e' un proxy aperto: l'host viene **solo** da settings, i tre numeri sono interi, e se il
  quadrato non tocca l'Italia si risponde 404 prima di pensare a uscire.

`salva_log` non gira, di proposito: l'invariante 2 riguarda le interrogazioni agli erogatori
anagrafici, e una tile non domanda nessun dato di una persona.
"""

import math
import time
from pathlib import Path

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound

DIMENSIONE_MINIMA = 200        # il segnalibro che OSM da' a chi non si identifica e' 1x1, 103 byte
DIMENSIONE_MASSIMA = 1_000_000
TEMPO_LIMITE = 10              # secondi: una tile non deve tenere impalata una richiesta
BOX = (6.0, 18.0, 36.0, 47.0)  # la box dei Specifications, la stessa del taglio dei puntini


def _numeri(z, x, y):
    """(z, x, y) come interi, o `None`: arrivano da un converter `int`, ma si ricontrollano."""
    try:
        z, x, y = int(z), int(x), int(y)
    except (TypeError, ValueError):
        return None
    return (z, x, y) if 1 <= z <= 19 and 0 <= x < 2 ** z and 0 <= y < 2 ** z else None


def _latitudine(v, z):
    """Bordo del quadrato `v` alla scala `z`: la proiezione di Web Mercator, al rovescio."""
    n = math.pi - 2 * math.pi * v / 2 ** z
    return math.degrees(math.atan(math.sinh(n)))


def _tocca_l_italia(z, x, y):
    """Vero se il quadrato tocca la box del nostro territorio: il lucchetto contro il globo."""
    ovest, est = x / 2 ** z * 360 - 180, (x + 1) / 2 ** z * 360 - 180
    return (est >= BOX[0] and ovest <= BOX[1]
            and _latitudine(y + 1, z) <= BOX[3] and _latitudine(y, z) >= BOX[2])


def _prendi(z, x, y):
    """I byte della tile, o `None` se quella che arriva non e' una tile.

    Il `Content-Type` e' il pezzo che conta: un filtro che risponde la sua pagina di blocco con
    un 200 sopra, qui diventa un rifiuto, e il navigatore lo vedra' come un carico fallito.
    """
    try:
        risposta = requests.get(settings.TILE_UPSTREAM.format(z=z, x=x, y=y),
                               headers={'User-Agent': settings.TILE_USER_AGENT},
                               timeout=TEMPO_LIMITE)
    except (requests.RequestException, ValueError):
        return None
    if risposta.status_code != 200 or 'image/png' not in risposta.headers.get('Content-Type', ''):
        return None
    corpo = risposta.content
    return corpo if DIMENSIONE_MINIMA <= len(corpo) <= DIMENSIONE_MASSIMA else None


def _fresca(file):
    """Vero se il cache ha la tile e non e' vecchia: `False` se il file non c'e' o non si legge."""
    try:
        return file.exists() and time.time() - file.stat().st_mtime < settings.TILE_CACHE_SECONDS
    except OSError:
        return False


def _salva(file, corpo):
    """Scrive la tile nel cache e rimanda i suoi byte.

    Il cache e' un comodo, il servizio e' la mappa: un deploy con il filesystem in sola lettura,
    o la cartella non montata, non merita un 500 al posto di una tile. Si serve lo stesso, e la
    prossima richiesta la riprende.
    """
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(corpo)
    except OSError:
        pass
    return corpo


def anncsu_tile(request, z, x, y):
    """`/tile/<z>/<x>/<y>.png`: la tile dal cache del portale, o presa e messa via.

    Un 502 non e' un guaio nascosto: e' il modo perche' Leaflet scateni `tileerror` e la pagina
    dell'aggiornamento lo dica all'operatore, invece di mostrargli un manifesto che sembra mappa.
    """
    numeri = _numeri(z, x, y)
    if numeri is None or not _tocca_l_italia(*numeri):
        return HttpResponseNotFound()
    z, x, y = numeri
    chiave = Path(settings.TILE_CACHE_DIR) / str(z) / str(x) / f'{y}.png'
    corpo = chiave.read_bytes() if _fresca(chiave) else None
    if corpo is None:
        corpo = _prendi(z, x, y)
        if corpo is None:
            return HttpResponse(status=502)
        corpo = _salva(chiave, corpo)
    risposta = HttpResponse(corpo, content_type='image/png')
    risposta['Cache-Control'] = f'public, max-age={max(60, settings.TILE_CACHE_SECONDS // 10)}'
    return risposta
