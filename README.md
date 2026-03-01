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
![License](https://img.shields.io/badge/License-BSD_3--Clause-blue)
![Author](https://img.shields.io/badge/Author-OpenCED_di_Santalucia_Luca-orange)


Il progetto è sviluppato per guidare la digitalizzazione dell'Ente. Il portale funge da gateway unificato per l'interoperabilità dei dati tramite la **PDND** (Piattaforma Digitale Nazionale Dati) e la gestione delle comunicazioni verso il cittadino tramite **App IO**.

**OpenMSP** è un client backend sviluppato in **Django**, con interfaccia basata su **Bootstrap Italia**, che permette l'interoperabilità con la **Piattaforma Digitale Nazionale Dati (PDND)** e l'invio di messaggi ai cittadini tramite **App IO**.

---

# 🚀 Funzionalità Principali

* **Interoperabilità PDND:** Consultazione diretta delle API rese disponibili dai soggetti erogatori.
* **Comunicazione Cittadino:** Strumento per comunicare direttamente con il cittadino tramite App IO.
* **Operazioni Massive:** Supporto all'importazione di file XLSX/CSV per query e invii multipli, ottimizzando i flussi di lavoro.

---

## 🏛️ Integrazioni PDND (Banche Dati)

OpenMSP orchestra le chiamate verso diversi endpoint della PDND per centralizzare le informazioni:

### 1. Domicilio Digitale
Consultazione e verifica dei domicili digitali con controlli formali sui Codici Fiscali e verifica minorenni.
* **Soggetti:** Persone fisiche (INAD), Imprese e professionisti (INI-PEC), Pubblica Amministrazione (IPA).
* **Modalità:** Ricerca singola o massiva (import da file XLSX/CSV) con stampa ed esportazione dei risultati.

### 2. ANPR (Anagrafe Nazionale Popolazione Residente)
Interrogazione dettagliata della banca dati nazionale:
* **Generalità:** Cognome, Nome, Sesso, Data/Luogo di nascita, Stato civile, C.I. e ID ANPR.
* **Residenza:** Indirizzo completo e data di decorrenza.
* **Stato di Famiglia:** Schede anagrafiche di tutti i componenti del nucleo familiare.
* **Matrimonio:** Stato matrimoniale, estremi atto ed eventuale annullamento/divorzio.
* **Cittadinanza:** Verifica della cittadinanza del soggetto.
* **Esistenza in vita:** Verifica dell'esistenza in vita del soggetto.

### 3. CCIAA (Registro Imprese)
Restituzione di tutti i dati indicati nella visura camerale per soggetti iscritti:
* Dettagli sedi, legali rappresentanti, domicilio digitale, codici ATECO, iscrizioni ad albi, statuti, soci, capitale sociale, ecc.

### 4. ANIS e ANIST
Restituzione di tutti i dati indicanti la formazione dalla scuola primaria all'università:
* **ANIS (Istruzione Superiore ed universitaria):** Consultazione iscrizioni e titoli conseguiti presso Istituti di Formazione Superiore ed Universitari (modalità singola o massiva).
* **ANIST (Istruzione di primo e secondo grado):** Consultazione frequenza e titoli conseguiti presso Istituti di primo e secondo grado (modalità singola o massiva).

### 5. PROSSIME IMPLEMENTAZIONI
* **INPS - ISEE:** Richiesta attestazione per varie tipologie (standard, università, socio-sanitario, minorenni, ecc.).
* **INPS - DURC:** Consultazione in corso di validità con possibilità di acquisizione del file PDF.
* **MIT (Trasporti):** Consultazione patenti possedute e verifica contrassegni disabili/targhe (Piattaforma Unica Nazionale Informatica dei Contrassegni Unici).
* **CNF (Forense):** Verifica iscrizione di un soggetto all'albo degli avvocati.

---

## 📱 Integrazione App IO

Modulo completo per la gestione delle notifiche verso l'App dei servizi pubblici.

### Features
* **Check Utente:** Verifica se il CF è attivo su App IO e se il servizio dell'Ente è attivo (include check formale CF e maggiore età). Disponibile anche in modalità massiva.
* **Invio Messaggi:** Invio messaggi personalizzati attingendo dal catalogo servizi pagoPA (inclusi eventuali estremi di pagamento).
* **Invio Massivo:** Caricamento file XLSX/CSV per invii multipli con informazioni personalizzate per ogni cittadino.
* **Invio Massivo tramite "Composer":** Caricamento file XLSX/CSV per invii multipli con la possibilità di comporre il messaggio attraverso la funzione "Campi unione".
* **Tracking:** Restituzione ID messaggio per prova accettazione e verifica successiva della messa a disposizione al cittadino.

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

1.  **Clona il repository:**
    ```bash
    git clone https://github.com/lsantalu/OpenMSP.git
    cd OpenMSP
    ```

2.  **Crea un virtual environment e attivalo:**
    ```bash
    python -m venv env
    source env/bin/activate  # Su Windows: env\Scripts\activate
    ```

3.  **Installa le dipendenze:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Copia il file `.env_example` in `.env` e configuralo:**
    ```bash
    cp .env_example .env
    ```

5.  **Copia il database di esempio:**
    ```bash
    cp db_example.sqlite3 db.sqlite3
    ```

6.  **Esegui le migrazioni del database:**
    ```bash
    python manage.py migrate
    ```

7.  **Avvia il server di sviluppo:**
    ```bash
    python manage.py runserver
    ```

L'accesso al sito avviene su http://localhost:8000

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

## ⚙️ Configurazione `.env` (v1.1)

Crea o aggiorna il file `.env` nella root del progetto con i parametri seguenti:

```env
DJANGO_SECRET_KEY = 'my_password_django_complex6m^*)p!ryk)=xcpn9*rxpznm'
DEBUG = False
ALLOWED_HOSTS = '["your.domain.com"]'

DJANGO_BOOTSTRAP_ITALIA_USE_CDN = True
DJANGO_BOOTSTRAP_ITALIA_CDN = 'https://cdn.jsdelivr.net/npm/bootstrap-italia@2.17.0/dist'

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
```

Nota: usa **una sola** coppia `AUTH_LDAP_USER_SEARCH_FILTER` e `AUTH_LDAP_USER_ATTR_MAP` in base al tuo provider LDAP (OpenLDAP o Active Directory).

## 🔁 Script di aggiornamento (Step-by-Step)

Per aggiornare la struttura del database e il file `.env` tra le diverse versioni, utilizza gli script presenti nella directory `update/`. Gli script sono progettati per essere eseguiti in modo incrementale.

### Logica di Aggiornamento Incrementale
Se desideri aggiornare alla versione più recente (es. 1.2), puoi eseguire direttamente l'ultimo script disponibile. Se il database è fermo a più versioni precedenti, lo script rileverà automaticamente la situazione e invocherà i passaggi intermedi necessari.

Esempio: eseguendo `update_to_1.2.sh` su un database 1.0.0, verrà automaticamente chiamato prima `update_to_1.1.sh`.

### Script Disponibili
*   `update/update_to_1.1.sh`: Aggiornamento alla versione 1.1.0.
*   `update/update_to_1.2.sh`: Aggiornamento alla versione 1.2.0 (include logica incrementale).

### Uso (Esempio per v1.2)

Uso (non interattivo):
```bash
./update/update_to_1.2.sh [path/to/db.sqlite3] [path/to/.env]
```

Uso (interattivo):
```bash
chmod +x update/update_to_1.2.sh
./update/update_to_1.2.sh
```

### Funzionalità degli Script
*   **Verifica Versione**: Ogni script verifica la versione attuale del DB prima di procedere.
*   **Backup Automatico**: Viene creato un backup `.bak` del database e del file `.env` prima di ogni modifica.
*   **Migrazioni Django**: Gli script eseguono automaticamente `makemigrations` e `migrate` al termine della procedura.
*   **Sincronizzazione Parametri**: Sincronizza i parametri applicativi e le variabili `.env` se vengono forniti file di riferimento corretti.

## 📄 Licenze di Terze Parti

Questo progetto utilizza librerie e componenti di terze parti. Di seguito l'elenco delle licenze per i pacchetti presenti in `requirements.txt`:

### MIT License
*   **[apscheduler](https://github.com/agronholm/apscheduler/blob/master/LICENSE.txt)**
*   **[django-compressor](https://github.com/django-compressor/django-compressor/blob/master/LICENSE)**
*   **[django-extensions](https://github.com/django-extensions/django-extensions/blob/main/LICENSE)**
*   **[django-sass-processor](https://github.com/jrief/django-sass-processor/blob/master/LICENSE-MIT)**
*   **[gunicorn](https://github.com/benoitc/gunicorn/blob/master/LICENSE)**
*   **[libsass](https://github.com/sass/libsass-python/blob/main/LICENSE)**
*   **[markdown-it-py](https://github.com/executablebooks/markdown-it-py/blob/master/LICENSE)**
*   **[openpyxl](https://github.com/fluidware/openpyxl/blob/master/LICENCE)**
*   **[python-decouple](https://github.com/HBNetwork/python-decouple/blob/master/LICENSE)**
*   **[python-jose](https://github.com/mpdavis/python-jose/blob/master/LICENSE)**
*   **[PyJWT](https://github.com/jpadilla/pyjwt/blob/master/LICENSE)**
*   **[pytz](https://github.com/stub42/pytz/blob/master/LICENSE.txt)**
*   **[pyzipper](https://github.com/danifus/pyzipper/blob/master/LICENSE)**
*   **[whitenoise](https://github.com/evansd/whitenoise/blob/main/LICENSE)**
*   **[xmltodict](https://github.com/martinblech/xmltodict/blob/master/LICENSE)**

### BSD (3-Clause) License
*   **[asgiref](https://github.com/django/asgiref/blob/main/LICENSE)**
*   **[design-django-theme](https://github.com/italia/design-django-theme/blob/master/LICENSE)**
*   **[Django](https://github.com/django/django/blob/main/LICENSE)**
*   **[djangorestframework](https://github.com/encode/django-rest-framework/blob/master/LICENSE.md)**
*   **[sqlparse](https://github.com/andialbrecht/sqlparse/blob/master/LICENSE)**

### Apache License 2.0
*   **[cryptography](https://github.com/pyca/cryptography/blob/main/LICENSE.APACHE)** (o BSD)
*   **[pyOpenSSL](https://github.com/pyca/pyopenssl/blob/main/LICENSE)**
*   **[requests](https://github.com/psf/requests/blob/main/LICENSE)**

### Altre Licenze
*   **[html2text](https://github.com/Alir3z4/html2text/blob/master/COPYING)**: GPLv3
*   **[Pillow](https://github.com/python-pillow/Pillow/blob/main/LICENSE)**: HPND (Historical Permission Notice and Disclaimer)
*   **[typing-extensions](https://github.com/python/typing_extensions/blob/main/LICENSE)**: PSF (Python Software Foundation License)

Tutti i marchi riportati appartengono ai legittimi proprietari; marchi di terzi, nomi di prodotti, nomi commerciali, nomi corporativi e società citati possono essere marchi di proprietà dei rispettivi titolari o marchi registrati di altre società e sono stati utilizzati a puro scopo esplicativo per favorire l’integrazione, senza alcun fine di violazione dei diritti di Copyright vigenti.


## ℹ️ Credits
Sviluppato da **OpenCED di Santalucia Luca** - [openced.it](https://openced.it).

---

## 📊 Statistiche

[![Downloads](https://img.shields.io/github/downloads/lsantalu/OpenMSP/total.svg)](https://github.com/lsantalu/OpenMSP/releases)

[![Star History Chart](https://api.star-history.com/svg?repos=lsantalu/OpenMSP&type=Date)](https://star-history.com/#lsantalu/OpenMSP&Date)
