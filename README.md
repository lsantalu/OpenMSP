<p align="center">
  <a href="" rel="noopener">
 <img width=300px height=64px src="https://openced.it/logo.png" alt="Project logo"></a>
</p>

<h3 align="center">OpenMSP - Multi Services Portal</h3>

---

<p align="center"> Il portale per accedere alla PDND e 
inviare messaggi tramite la App IO<br> 
</p>

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Django](https://img.shields.io/badge/Django-3.2%2B-green)
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

### 3. CCIAA (Registro Imprese)
Restituzione di tutti i dati indicati nella visura camerale per soggetti iscritti:
* Dettagli sedi, legali rappresentanti, domicilio digitale, codici ATECO, iscrizioni ad albi, statuti, soci, capitale sociale, ecc.

### 4. ANIS e ANIST
Restituzione di tutti i dati indicati la formazione dalla scuola primaria all'università:
* **ANIS (Istruzione Superiore ed univesitaria):** Consultazione iscrizioni e titoli conseguiti presso Istituti di Formazione Superiore ed Universitari (modalità singola o massiva).
* **ANIST (Istruzione primo e secondo grado):** Consultazione frequenza e titoli conseguiti presso Istituti di primo e secondo grado (modalità singola o massiva).

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
* **Invio Massivo tramite "Composer":** Caricamento file XLSX/CSV per invii multipli con informazioni personalizzate per ogni cittadino.
* **Tracking:** Restituzione ID messaggio per prova accettazione e verifica successiva della messa a disposizione al cittadino.

---

## ⚙️ Configurazione e Sicurezza

* **Gestione Connettori:** Configurazione parametri di interconnessione per le API attivate.
* **Permessi Operatori:** Gestione granulare delle abilitazioni per singolo operatore (permesso/diniego consultazione banche dati o invio messaggi).

---

## 🛠️ Requisiti

* Python 3.8+
* Django 3.2+
* design-django-theme (Bootstrap Italia)
* Librerie crittografiche (per la firma dei voucher PDND)
* Accesso sviluppatore su [Self Care PagoPA](https://selfcare.pagopa.it/)

## 🚀 Installazione

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

4.  **Rinomina il file .env.example in .env e configuralo con i tuoi parametri:**
    ```bash
    cp .env_example .env
    ```

5.  **Rinomina il file db_example.sqlite3 in db.sqlite3:**
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
    

## ⚙️ Configurazione

Crea un file `.env` nella root del progetto inserendo le chiavi ottenute dal portale sviluppatori:

```env
# DJANGO SETTINGS
DEBUG=True
DJANGO_BOOTSTRAP_ITALIA_USE_CDN = True
DJANGO_BOOTSTRAP_ITALIA_CDN = 'https://cdn.jsdelivr.net/npm/bootstrap-italia@2.17.0/dist'

# PARAMETRI MAIL 
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
```

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

Tutti i marchi riportati appartengono ai legittimi proprietari; marchi di terzi, nomi di prodotti, nomi commerciali, nomi corporativi e società citati possono essere marchi di proprietà dei rispettivi titolari o marchi registrati d’altre società e sono stati utilizzati a puro scopo esplicativo per favorire l’integrazione, senza alcun fine di violazione dei diritti di Copyright vigenti.


## ℹ️ Credits
Sviluppato da **OpenCED di Santalucia Luca** - [openced.it](https://openced.it).

---

## 📊 Statistiche

[![Downloads](https://img.shields.io/github/downloads/lsantalu/OpenMSP/total.svg)](https://github.com/lsantalu/OpenMSP/releases)

[![Star History Chart](https://api.star-history.com/svg?repos=lsantalu/OpenMSP&type=Date)](https://star-history.com/#lsantalu/OpenMSP&Date)