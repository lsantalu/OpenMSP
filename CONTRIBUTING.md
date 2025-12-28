# Contribuire a OpenMSP

Grazie per il tuo interesse nel contribuire a **OpenMSP**!
Questo progetto ha l'obiettivo di supportare la digitalizzazione degli Enti pubblici attraverso l'interoperabilità con la PDND (Piattaforma Digitale Nazionale Dati) e l'integrazione con App IO.

Data la natura dei dati trattati (ANPR, INPS, Domicilio Digitale, ecc.), chiediamo a tutti i collaboratori di attenersi rigorosamente a queste linee guida per garantire sicurezza, stabilità e conformità normativa.

## 📋 Prerequisiti

Prima di iniziare a contribuire, assicurati di avere familiarità con i seguenti concetti:
* **Interoperabilità PDND:** Comprensione dei meccanismi di autenticazione (Voucher, Client Assertion) e gestione delle API REST.
* **Specifiche App IO:** Conoscenza delle API di pagoPA per la gestione dei servizi e l'invio dei messaggi.
* **Privacy & Security:** Consapevolezza nella gestione di PII (Personally Identifiable Information).

## 🛠️ Setup dell'Ambiente di Sviluppo

1.  **Fork & Clone**
    Forka il repository e clona la tua copia locale:
    ```bash
    git clone https://github.com/tuo-username/openmsp.git
    cd openmsp
    ```

2.  **Configurazione Variabili d'Ambiente**
    Copia il file di esempio per configurare le variabili locali:
    ```bash
    cp .env.example .env
    ```
    > **⚠️ IMPORTANTE:** Non utilizzare mai credenziali di produzione (certificati PDND reali) nell'ambiente di sviluppo locale. Utilizza sempre l'ambiente di Test/Sandbox fornito dalla PDND o mock dei servizi.

3.  **Installazione Dipendenze**
    Installa le dipendenze necessarie (es. Python):
    ```bash
     # Esempio per Python
    pip install -r requirements.txt
    ```

## 🔒 Sicurezza e Gestione Dati

OpenMSP interroga dati altamente sensibili (ISEE, Stato di Famiglia, Residenza, dati sanitari/disabilità).
**Regole tassative:**

1.  **Nessun Log di Dati Sensibili:** È severamente vietato stampare nei log (console o file) i dati di risposta delle interrogazioni come importi ISEE, indirizzi o nomi. I log devono contenere solo i dati di chiamata alle API o messaggi di errore generici.
3.  **Credenziali:** Non committare mai chiavi private o token API nel repository.

## 🐛 Segnalazione Bug

Se riscontri un bug, apri una Issue includendo:
* **Modulo interessato:** (es. Connettore ANPR, Invio App IO, Modulo MIT).
* **Descrizione dell'errore:** Cosa è successo vs cosa ti aspettavi.
* **Riproduzione:** I passi esatti per riprodurre il problema.
* **Log:** Allega lo stack trace (assicurandoti di oscurare qualsiasi dato personale).

## ✨ Proposte di Nuove Funzionalità

Per proporre l'integrazione di un nuovo Ente Erogatore (es. una nuova API resa disponibile in PDND):
1.  Apri una Issue con label `enhancement`.
2.  Linka la documentazione OpenAPI dell'e-service PDND.
3.  Descrivi i permessi necessari (ACL) che l'operatore dovrà avere per accedere a questo nuovo dato.

## workflow di Sviluppo

1.  **Branching:** Crea un branch descrittivo per la tua feature o fix:
    * `feature/integrazione-inad`
    * `fix/validazione-cf-minori`
    * `docs/aggiornamento-readme`
2.  **Commit:** Usa messaggi di commit chiari (è gradita la convenzione *Conventional Commits*).
3.  **Test:** Se modifichi connettori API, assicurati di aggiornare o creare i relativi test unitari (mockando le risposte esterne).
4.  **Pull Request:** Invia la PR verso il branch di sviluppo (`develop`).

## 📄 Licenza

Contribuendo a OpenMSP, accetti che il tuo codice sia rilasciato sotto la licenza definita nel file `LICENSE` del progetto.