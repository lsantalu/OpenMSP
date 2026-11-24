<p align="center">
  <a href="" rel="noopener">
 <img width=300px height=64px src="https://openced.it/logo.png" alt="Project logo"></a>
</p>

<h3 align="center">OpenMSP - Multi Services Portal</h3>

---

<p align="center"> Il portale per accedere alla PDND e
inviare messaggi tramite la App IO<br>
</p>

![Python](https://img.shields.io/badge/Python-3.13%2B-blue)
![Django](https://img.shields.io/badge/Django-5.2%2B-green)
![Version](https://img.shields.io/badge/Version-1.5.0-brightgreen)
![License](https://img.shields.io/badge/License-BSD_3--Clause-blue)
![Author](https://img.shields.io/badge/Author-OpenCED_di_Santalucia_Luca-orange)

Il progetto è sviluppato per guidare la digitalizzazione dell'Ente. Il portale funge da gateway unificato per l'interoperabilità dei dati tramite la **PDND** (Piattaforma Digitale Nazionale Dati) e la gestione delle comunicazioni verso il cittadino tramite **App IO**.

**OpenMSP** è un client backend sviluppato in **Django**, con interfaccia basata su **Bootstrap Italia**, che permette l'interoperabilità con la **Piattaforma Digitale Nazionale Dati (PDND)** e l'invio di messaggi ai cittadini tramite **App IO**.

---

# 🆕 Novità

## Release 1.5.0

* **Estrazione massiva del Registro Imprese:** file CSV/XLSX con i codici in colonna (A), una visura per riga nello stesso ordine del file, un solo voucher per tutto il file, card di avanzamento e download **ZIP** di tutti i JSON.
* **ANNCSU - fase Beta:** consultazione per i Comuni e i tre aggiornamenti in scrittura (accessi, coordinate, odonimi), con validazione locale dei campi e scrittura solo dopo il doppio passo **Verifica** → **Invia**.
* **Ricerca del civico su mappa** nella pagina di aggiornamento coordinate: i civici posizionati diventano punti su una mappa Leaflet/OpenStreetMap e il pulsante **Usa** riporta progressivo, coordinate e metodo di rilievo nel form.
* **Download massivo DURC:** ZIP di tutti i PDF dell'ultima estrazione.
* **Schema e file:** nuovo permesso `utenti_parametri.registro_imprese_massivo` e quattro nuove chiavi `.env` (`TILE_UPSTREAM`, `TILE_USER_AGENT`, `TILE_CACHE_DIR`, `TILE_CACHE_SECONDS`).

## Release 1.4.0

* **Pagine unificate:** *Cerca domicilio digitale* (iPA, INAD e INI-PEC in un solo form) e *Interroga ANPR* (sette casi d'uso, singola o massiva); *Istruzione* unifica anche ANIS e ANIST.
* **ANPR in modalità massiva:** sette nuovi permessi `anpr_Cxxx_massivo`, import da file CSV/XLSX, tabella dei risultati ed esportazione XLSX.
* **Deployment dietro reverse proxy:** `USE_X_FORWARDED_HOST`, `SECURE_PROXY_SSL_HEADER` e `CSRF_TRUSTED_ORIGINS` (issue #10).
* **LDAP:** `AUTH_LDAP_GLOBAL_OPTIONS` per la verifica del certificato su LDAPS (issue #14).
* **ISEE:** motivazione della prestazione richiesta.


---

# 🚀 Funzionalità Principali

* **Interoperabilità PDND:** Consultazione diretta delle API rese disponibili dai soggetti erogatori.
* **Comunicazione Cittadino:** Strumento per comunicare direttamente con il cittadino tramite App IO.
* **Operazioni Massive:** Supporto all'importazione di file XLSX/CSV per query e invii multipli, ottimizzando i flussi di lavoro.
* **Pagine unificate:** Un solo form per interrogare più eService della stessa famiglia (domicili digitali, ANPR, istruzione), con un riepilogo dei risultati e l'esportazione comune.
* **Card di avanzamento:** Nelle interrogazioni massive una card dice quanti codici sono stati lavorati e su quale codice si è fermi, al posto di un indicatore a cerchio.
* **Audit:** Ogni interrogazione a un erogatore lascia una riga in `logs` (utente, servizio, purposeId, stato HTTP, token id), senza dati anagrafici nel log.

---

## 🏛️ Integrazioni PDND (Banche Dati)

OpenMSP orchestra le chiamate verso diversi endpoint della PDND per centralizzare le informazioni:

### 1. Domicili Digitali (iPA, INAD, INI-PEC) - pagina unificata

Una sola pagina, `/domicili_digitali/`, per interrogare tutti e tre gli indici dei domicili digitali: un form con un radiogruppo che sceglie l'indice e un secondo che sceglie singola o massiva. Un eService spento in `servizi_parametri` non viene offerto; uno attivo ma senza permesso su `utenti_parametri` viene offerto disabilitato.

* **Soggetti:** Pubblica Amministrazione (iPA), persone fisiche (INAD), imprese e professionisti (INI-PEC).
* **Controlli formali:** Verifica della correttezza del Codice Fiscale e dei minorenni prima di ogni interrogazione, che così non spende un voucher.
* **Massiva con card di avanzamento:** CSV o XLSX con i codici in colonna (A), un giro di interrogazione per codice comandato dal browser, tabella renderizzata dal server a giro finito.
* **Esiti:** Tabella comune ai tre servizi con dettaglio per riga, stampa ed esportazione XLSX.

Le pagine dedicate di prima generazione (`/ipa_singola/`, `/inad_massiva/`, `/inipec_singola/` e sorelle) restano raggiungibili.

### 2. ANPR (Anagrafe Nazionale Popolazione Residente) - pagina unificata

Una sola pagina, `/anpr/` (nel menu e' marcata **Beta**), per tutti e sette i casi d'uso: un form, sette casi d'uso, singola o massiva. Il caso d'uso scelto resta in sessione e il gate dei permessi viene riverificato a ogni giro.

* **Casi d'uso:** C001 Servizio notifica, C007 Esistenza in vita, C015 Generalità, C017 Matrimonio, C018 Cittadinanza, C020 Residenza, C021 Stato di famiglia.
* **Generalità:** Cognome, Nome, Sesso, Data/Luogo di nascita, Stato civile, C.I. e ID ANPR.
* **Residenza:** Indirizzo completo e data di decorrenza.
* **Stato di Famiglia:** Schede anagrafiche di tutti i componenti del nucleo familiare, con il legame di parentela.
* **Matrimonio:** Stato matrimoniale, estremi atto ed eventuale annullamento/divorzio, con il tipo di cessazione.
* **Cittadinanza:** Verifica della cittadinanza del soggetto.
* **Esistenza in vita:** Verifica dell'esistenza in vita del soggetto.
* **Massiva:** import da file XLSX/CSV con card di avanzamento, tabella con dettaglio per riga ed esportazione XLSX; il caso d'uso resta in sessione, dal navigatore arriva solo l'indice della riga.

### 3. CCIAA (Registro Imprese)

Restituzione di tutti i dati indicati nella visura camerale per soggetti iscritti:

* Dettagli sedi, legali rappresentanti, domicilio digitale, codici ATECO, iscrizioni ad albi, statuti, soci, capitale sociale, ecc.
* **Ricerca singola** con visura renderizzata e JSON originale scaricabile.
* **Estrazione massiva** (`/registro_imprese_massivo/`, dalla versione 1.5.0): CSV/XLSX con i codici in colonna (A), una visura per riga nello stesso ordine del file con un solo voucher per tutto il file; card di avanzamento, JSON della singola riga scaricabile e **ZIP** di tutti i JSON dell'estrazione, con `errori.txt` per le righe rimaste senza risposta. Le risposte restano in sessione, nessun file su disco.

### 4. ANIS e ANIST

Restituzione di tutti i dati indicanti la formazione dalla scuola primaria all'università, raccolti nella pagina unificata *Istruzione* (`/istruzione/`):

* **ANIS (Istruzione Superiore ed universitaria):** Consultazione iscrizioni e titoli conseguiti presso Istituti di Formazione Superiore ed Universitari (modalità singola o massiva).
* **ANIST (Istruzione di primo e secondo grado):** Consultazione frequenza e titoli conseguiti presso Istituti di primo e secondo grado (modalità singola o massiva).

### 5. INPS

* **INPS - ISEE:** Richiesta attestazione ISEE per residenti, con motivazione della prestazione richiesta.
* **INPS - DURC:** Consultazione DURC in corso di validità in modalità singola e massiva, con acquisizione del file PDF e, dalla versione 1.5.0, download **ZIP** di tutti i PDF dell'ultima estrazione.


### 7. ANNCSU (Archivio Nazionale Numeri Civici e Strade Urbane)

Disponibile dalla versione 1.4.0 e marcato **Beta** nel menu: cinque eService, quattro con il client scritto, ognuno con un permesso a testa e una riga di impostazioni propria.

| eService | Che cosa fa | Permesso |
|---|---|---|
| **Consultazione per i Comuni** | Otto operazioni su odonimi, accessi e progressivi nazionali: esistenza di un odonimo o di un accesso, aree di circolazione e accessi anche per valori parziali, dati di un'area o di un accesso dal progressivo nazionale. | `anncsu_consultazione_comuni` |
| **Aggiornamento accessi** | Inserimento, variazione e soppressione di un accesso di un'area di circolazione. | `anncsu_accessi` |
| **Aggiornamento coordinate** | Posizionamento di un civico con il suo metodo di rilievo. | `anncsu_coordinate` |
| **Aggiornamento odonimi** | Inserimento, variazione e soppressione di un'area di circolazione. | `anncsu_odonimi` |
| **Estratto di mappa per Visura** | Pagina e permesso presenti, client non ancora scritto: la pagina lo dice. | `anncsu_visura` |

* **Esiti ed esportazioni:** Risultato a tabella con esportazione XLSX e CSV (delimitatore `;`), o risposta secca per le operazioni di esistenza.
* **Scrittura solo a doppio passo:** un POST valido rende il riepilogo di ciò che verrà scritto; l'aggiornamento parte con **Invia**, perché inserimenti, variazioni e soppressioni non sono reversibili dal portale. La validazione locale anticipa i codici errore della specifica (55/60/80 per gli accessi, 105/110/115/125/130/135 per le coordinate, 200/210/235/260/270/325 per gli odonimi) prima di spendere un voucher.
* **Ricerca del civico in due passi** (aggiornamento coordinate): prima le aree di circolazione, poi i civici dell'area, resi come **mappa** con un punto per civico posizionato; il pulsante **Usa** riporta progressivo, coordinate e metodo di rilievo nel form. Sotto la mappa c'è sempre l'elenco completo di tutte le righe, che resta il cammino quando le tile non arrivano o il JavaScript è spento.
* **Comune compilato per nome:** dove il campo comune serve, si compila per nome (`Roma (H501)`) e spedisce il codice Belfiore; un nome non scelto nell'elenco non parte.
* **Privacy e rete:** le tile di mappa le chiede il portale (`/tile/<z>/<x>/<y>.png`) con cache su disco, non il navigatore; l'indirizzo IP dell'operatore non arriva all'erogatore di tile.


---

## 📱 Integrazione App IO

Modulo completo per la gestione delle notifiche verso l'App dei servizi pubblici.

### Features

* **Check Utente:** Verifica se il CF è attivo su App IO e se il servizio dell'Ente è attivo (include check formale CF e maggiore età). Disponibile anche in modalità massiva.
* **Invio Messaggi:** Invio messaggi personalizzati attingendo dal catalogo servizi pagoPA (inclusi eventuali estremi di pagamento).
* **Invio Massivo:** Caricamento file XLSX/CSV per invii multipli con informazioni personalizzate per ogni cittadino.
* **Invio Massivo tramite "Composer":** Caricamento file XLSX/CSV per invii multipli con la possibilità di comporre il messaggio attraverso la funzione "Campi unione".

---

## ⚙️ Configurazione e Sicurezza

* **Gestione Connettori:** Configurazione parametri di interconnessione per le API attivate.
* **Permessi Operatori:** Gestione granulare delle abilitazioni per singolo operatore (permesso/diniego consultazione banche dati o invio messaggi).

---

## 🛠️ Requisiti

* Python 3.12+
* Django 5.2+
* design-django-theme (Bootstrap Italia)
* Librerie crittografiche (per la firma dei voucher PDND)
* Accesso sviluppatore su [Self Care PagoPA](https://selfcare.pagopa.it/)

## 🚀 Installazione (locale)

1. **Clona il repository:**

    ```bash
    git clone https://github.com/lsantalu/OpenMSP.git
    cd OpenMSP
    ```

2. **Crea un virtual environment e attivalo:**

    ```bash
    python -m venv env
    source env/bin/activate  # Su Windows: env\Scripts\activate
    ```

3. **Installa le dipendenze:**

    ```bash
    pip install -r requirements.txt
    ```

4. **Copia il file `.env_example` in `.env` e configuralo:**

    ```bash
    cp .env_example .env
    ```

5. **Copia il database di esempio:**

    ```bash
    cp db_example.sqlite3 db.sqlite3
    ```

6. **Esegui le migrazioni del database:**

    ```bash
    python manage.py migrate
    ```

7. **Avvia il server di sviluppo:**

    ```bash
    python manage.py runserver
    ```

L'accesso al sito avviene su <http://localhost:8000>

* Utente: **admin**
* Password: **Admin123+**

## 🐳 Esecuzione con Container

Il progetto include configurazione Docker in `docker/Dockerfile`, `docker/docker-compose.yml` e `docker/entrypoint.sh`.

Avvio:

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

Dettagli principali:

* `container_name`: `openmsp_container`
* Porta esposta: `8000:8000`
* Volume persistente: `sqlite_data:/app/db_data`
* Il file `.env` viene reso persistente nel volume come `/app/db_data/.env`
* Il database viene reso persistente nel volume come `/app/db_data/db.sqlite3`

Comandi utili:

```bash
docker compose -f docker/docker-compose.yml logs -f
docker compose -f docker/docker-compose.yml down
```

Esempio di 2 istanze separate (porte, container e volume persistente distinti):

```bash
# Istanza 1
CONTAINER_NAME=openmsp_1 HOST_PORT=8001 SQLITE_VOLUME_NAME=openmsp_1_sqlite_data \
docker compose -p openmsp1 -f docker/docker-compose.yml up -d --build

# Istanza 2
CONTAINER_NAME=openmsp_2 HOST_PORT=8002 SQLITE_VOLUME_NAME=openmsp_2_sqlite_data \
docker compose -p openmsp2 -f docker/docker-compose.yml up -d --build
```

## ⚙️ Configurazione `.env` (v1.5.0)

Crea o aggiorna il file `.env` nella root del progetto a partire da `.env_example`, con i parametri seguenti:

```env
DJANGO_SECRET_KEY = 'my_password_django_complex6m^*)p!ryk)=xcpn9*rxpznm'
DEBUG = False
ALLOWED_HOSTS = openmsp.example.local,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS = https://openmsp.example.local

DJANGO_BOOTSTRAP_ITALIA_USE_CDN = True
DJANGO_BOOTSTRAP_ITALIA_CDN = 'https://cdn.jsdelivr.net/npm/bootstrap-italia@2.18.3/dist'

EMAIL_HOST = 'mail.host.com'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_HOST_USER = 'noreply@host.com'
EMAIL_HOST_PASSWORD = 'my_password'
DEFAULT_FROM_EMAIL = 'noreply@host.com'
EMAIL_BACKUP_ADDRESS = 'info@host.com'
EMAIL_BACKUP_PASSWORD = 'my_backup_password'
EMAIL_BACKUP_ON = True

AUTH_2FA = True
TWO_FACTOR_ISSUER = 'OpenMSP'

AUTH_LDAP_SERVER_URI = 'ldap://example.com:389'
AUTH_LDAP_BIND_DN = 'cn=my_binding_username,ou=my_ou,dc=example.com'
AUTH_LDAP_BIND_PASSWORD = 'my_secret'
AUTH_LDAP_USER_SEARCH_BASEDN = 'ou=my_ou,dc=example.com'

### per OpenLDAP
AUTH_LDAP_USER_SEARCH_FILTER = '(uid=%(user)s)'
AUTH_LDAP_USER_ATTR_MAP = {"first_name": "givenName","last_name": "sn","email": "mail",}
### per Active Directory
AUTH_LDAP_USER_SEARCH_FILTER = '(sAMAccountName=%(user)s)'
AUTH_LDAP_USER_ATTR_MAP = {"first_name": "givenName","last_name": "sn","email": "userPrincipalName"}

AUTH_LDAP_NO_NEW_USERS = True
AUTH_LDAP_CONNECTION_OPTIONS = {"OPT_PROTOCOL_VERSION": 3, "OPT_REFERRALS": 0}

### Opzioni globali ldap_set_option(), servono ad esempio per la verifica TLS su LDAPS
AUTH_LDAP_GLOBAL_OPTIONS = {}

### Mettere un contatto nello User-Agent e' cio' che la policy delle tile chiede.
TILE_UPSTREAM = https://tile.openstreetmap.org/{z}/{x}/{y}.png
TILE_USER_AGENT = OpenMSP/1.0 (portale ANNCSU; +mailto:anagrafe@comune.example.it)
TILE_CACHE_DIR = /var/lib/openmsp/tilecache
TILE_CACHE_SECONDS = 604800
```

Le quattro chiavi `TILE_*` (novità 1.5.0) servono solo alla mappa dell'aggiornamento coordinate ANNCSU: le tile le chiede il portale, non il navigatore, e le tiene in cache su disco. Senza egresso verso l'erogatore di tile la mappa resta vuota e la pagina lo scrive; l'elenco sotto la mappa funziona comunque.

Se il login via LDAPS fallisce con `certificate verify failed`, indica in `AUTH_LDAP_GLOBAL_OPTIONS` il file della CA che firma il certificato LDAP (`{"OPT_X_TLS_CACERTFILE": "/app/ca/ca-ente.pem"}`, con il file montato nel container) invece di disattivare la verifica (`{"OPT_X_TLS_REQUIRE_CERT": 0}`, ammissibile solo in staging o rete interna controllata).

Se il deploy sta dietro un reverse proxy HTTPS, `USE_X_FORWARDED_HOST` e `SECURE_PROXY_SSL_HEADER` sono già attivi in `settings.py` (novità 1.4.0, issue #10): resta da dichiarare l'origine pubblica in `CSRF_TRUSTED_ORIGINS`.

Nota: usa **una sola** coppia `AUTH_LDAP_USER_SEARCH_FILTER` e `AUTH_LDAP_USER_ATTR_MAP` in base al tuo provider LDAP (OpenLDAP o Active Directory).

## 🔁 Script di aggiornamento (Step-by-Step)

Per aggiornare la struttura del database e, quando previsto, il file `.env` tra le diverse versioni, utilizza gli script presenti nella directory `update/`. Gli script sono progettati per essere eseguiti in modo incrementale.

### Logica di Aggiornamento Incrementale

Se desideri aggiornare alla versione più recente (es. 1.5), puoi eseguire direttamente l'ultimo script disponibile. Se il database è fermo a più versioni precedenti, lo script rileverà automaticamente la situazione e invocherà i passaggi intermedi necessari.

Esempio: eseguendo `update_to_1.5.sh` su un database 1.2.0, verranno chiamati prima `update_to_1.3.sh` e poi `update_to_1.4.sh`.

### Script Disponibili

* `update/update_to_1.1.sh`: Aggiornamento alla versione 1.1.0.
* `update/update_to_1.2.sh`: Aggiornamento alla versione 1.2.0 (include logica incrementale).
* `update/update_to_1.3.sh`: Aggiornamento alla versione 1.3.0 (include logica incrementale).
* `update/update_to_1.4.sh`: Aggiornamento alla versione 1.4.0 (permessi ANPR massive, tabelle e permessi ANNCSU, `.env` e `settings.py` per il reverse proxy, `AUTH_LDAP_GLOBAL_OPTIONS`).
* `update/update_to_1.5.sh`: Aggiornamento alla versione 1.5.0 (target ANNCSU `.../consultazione-comune/v1`, righe dei tre eService di scrittura, rinomina del permesso `anncsu` in `anncsu_consultazione_comuni`, colonna `utenti_parametri.registro_imprese_massivo`, `migrate` per la tabella `django_session`, chiavi `TILE_*` nel `.env`).

### Uso (Esempio per v1.5)

Uso (non interattivo):

```bash
./update/update_to_1.5.sh [path/to/db.sqlite3] [path/to/.env]
```

Uso (interattivo):

```bash
chmod +x update/update_to_1.5.sh
./update/update_to_1.5.sh
```

### Funzionalità degli Script

* **Verifica Versione**: Ogni script verifica la versione attuale del DB prima di procedere.
* **Backup Automatico**: Viene creato un backup `.bak` del database prima di ogni modifica; il backup del file `.env` dipende dallo script eseguito e dalle sincronizzazioni previste per quella versione.
* **Migrazioni Django**: Gli script eseguono automaticamente `makemigrations` e `migrate` al termine della procedura.
* **Sincronizzazione Parametri**: Alcuni script sincronizzano parametri applicativi e variabili `.env` se previsti per quella versione.

## 📄 Licenze di Terze Parti

Questo progetto utilizza librerie e componenti di terze parti. Di seguito l'elenco delle licenze per i pacchetti presenti in `requirements.txt`:

### MIT License

* **[apscheduler](https://github.com/agronholm/apscheduler/blob/master/LICENSE.txt)**
* **[django-compressor](https://github.com/django-compressor/django-compressor/blob/master/LICENSE)**
* **[django-extensions](https://github.com/django-extensions/django-extensions/blob/main/LICENSE)**
* **[django-sass-processor](https://github.com/jrief/django-sass-processor/blob/master/LICENSE-MIT)**
* **[gunicorn](https://github.com/benoitc/gunicorn/blob/master/LICENSE)**
* **[libsass](https://github.com/sass/libsass-python/blob/main/LICENSE)**
* **[markdown-it-py](https://github.com/executablebooks/markdown-it-py/blob/master/LICENSE)**
* **[openpyxl](https://github.com/fluidware/openpyxl/blob/master/LICENCE)**
* **[python-decouple](https://github.com/HBNetwork/python-decouple/blob/master/LICENSE)**
* **[python-jose](https://github.com/mpdavis/python-jose/blob/master/LICENSE)**
* **[PyJWT](https://github.com/jpadilla/pyjwt/blob/master/LICENSE)**
* **[pytz](https://github.com/stub42/pytz/blob/master/LICENSE.txt)**
* **[pyzipper](https://github.com/danifus/pyzipper/blob/master/LICENSE)**
* **[whitenoise](https://github.com/evansd/whitenoise/blob/main/LICENSE)**
* **[xmltodict](https://github.com/martinblech/xmltodict/blob/master/LICENSE)**

### BSD (3-Clause) License

* **[asgiref](https://github.com/django/asgiref/blob/main/LICENSE)**
* **[design-django-theme](https://github.com/italia/design-django-theme/blob/master/LICENSE)**
* **[Django](https://github.com/django/django/blob/main/LICENSE)**
* **[djangorestframework](https://github.com/encode/django-rest-framework/blob/master/LICENSE.md)**
* **[sqlparse](https://github.com/andialbrecht/sqlparse/blob/master/LICENSE)**

### Apache License 2.0

* **[cryptography](https://github.com/pyca/cryptography/blob/main/LICENSE.APACHE)** (o BSD)
* **[pyOpenSSL](https://github.com/pyca/pyopenssl/blob/main/LICENSE)**
* **[requests](https://github.com/psf/requests/blob/main/LICENSE)**

### Altre Licenze

* **[Leaflet 1.9.4](https://github.com/Leaflet/Leaflet/blob/main/LICENSE)**: BSD-2-Clause (JS e CSS committati in `static/plugins/leaflet/`)
* **[Bootstrap Italia](https://github.com/italia/bootstrap-italia)**: BSD-3-Clause (CSS/JS della interfaccia, via CDN o copia a terra in `static/css/`)
* **Tile di mappa** da `tile.openstreetmap.org`, dominate da [OpenStreetMap](https://www.openstreetmap.org/) e usate secondo la [tile usage policy](https://operations.osmfoundation.org/policies/tiles/): le chiede il portale con un `User-Agent` contenente un contatto, e le tiene in cache su disco.
* **[html2text](https://github.com/Alir3z4/html2text/blob/master/COPYING)**: GPLv3
* **[Pillow](https://github.com/python-pillow/Pillow/blob/main/LICENSE)**: HPND (Historical Permission Notice and Disclaimer)
* **[typing-extensions](https://github.com/python/typing_extensions/blob/main/LICENSE)**: PSF (Python Software Foundation License)

Tutti i marchi riportati appartengono ai legittimi proprietari; marchi di terzi, nomi di prodotti, nomi commerciali, nomi corporativi e società citati possono essere marchi di proprietà dei rispettivi titolari o marchi registrati di altre società e sono stati utilizzati a puro scopo esplicativo per favorire l’integrazione, senza alcun fine di violazione dei diritti di Copyright vigenti.

## ℹ️ Credits

Sviluppato da **OpenCED di Santalucia Luca** - [openced.it](https://openced.it).

---

## 📊 Statistiche

[![Downloads](https://img.shields.io/github/downloads/lsantalu/OpenMSP/total.svg)](https://github.com/lsantalu/OpenMSP/releases)

[![Star History Chart](https://api.star-history.com/svg?repos=lsantalu/OpenMSP&type=Date)](https://star-history.com/#lsantalu/OpenMSP&Date)
