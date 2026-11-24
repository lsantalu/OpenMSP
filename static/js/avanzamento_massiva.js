/* static/js/avanzamento_massiva.js
 * L'avanzamento vero delle estrazioni massive: un POST per codice e la card dell'overlay
 * dice quanti ne sono arrivati, non un cerchio che gira senza dire niente.
 *
 * La pagina chiama `AvanzamentoMassiva.invia(form)` al submit e `AvanzamentoMassiva.riprendi()`
 * a pagina caricata. Il form parte nativo, non in fetch + innerHTML: il body sostituito con
 * l'HTML del server e' un buco di XSS. Il campo `js` aggiunto qui dice alla vista che il giro
 * lo fa il navigatore, e lei risponde il totale invece di girare i codici da sola.
 * Il codice lo sa la sessione: dal navigatore parte solo l'indice.
 */
(function (global) {
  'use strict';

  function id(n) { return document.getElementById(n); }

  function aggiorna(dati, totale) {
    const fatti = parseInt(String(dati.avanzamento || '0/0').split('/')[0], 10) || 0;
    const pct = totale > 0 ? Math.round(100 * fatti / totale) : 0;
    id('kvFatti').textContent = fatti;
    id('kvTotale').textContent = totale;
    id('kvBarra').style.width = pct + '%';
    id('kvBarraScato').setAttribute('aria-valuenow', pct);
    // L'etichetta e' il codice CHE SI STA CHIEDENDO (`prossimo`), non la risposta: quella la
    // tabella la scrive riga per riga a giro finito, e in mezzo alla card servirebbe a niente.
    // Sull'ultima riga `prossimo` e' null e si torna a `ultimo` (il codice appena finito).
    const etichetta = dati.prossimo || dati.ultimo || ('riga ' + fatti);
    id('kvUltimo').textContent = 'richiesta: ' + etichetta;
  }

  function fermati(testo) {
    const ultimo = id('kvUltimo');
    ultimo.textContent = testo + ' - le righe fatte sono salvate: ';
    const a = document.createElement('a');
    a.href = '?eseguito=1';
    a.className = 'link-primary';
    a.textContent = 'mostra i risultati';
    ultimo.appendChild(a);
  }

  // Un POST per codice, cosi' il conteggio e' di risposte davvero ricevute e non una stima.
  async function gira(nodo, totale) {
    const csrf = (document.querySelector('form [name=csrfmiddlewaretoken]') || {}).value || '';
    for (let i = 1; i <= totale; i++) {
      let risposta;
      try {
        risposta = await fetch(nodo.dataset.url, {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify({ indice: i })
        });
      } catch (e) { fermati('Filo interrotto sulla riga ' + i + ': ' + e.message); return; }
      if (!risposta.ok) { fermati('Risposta ' + risposta.status + ' sulla riga ' + i); return; }
      aggiorna(await risposta.json(), totale);
    }
    window.location.search = '?eseguito=1';   // la tabella la rende il server, come sempre
  }

  global.AvanzamentoMassiva = {
    mostra: function () {
      const overlay = id('loadingOverlay');
      if (overlay) overlay.classList.add('show');
    },
    // Il submit nativo: senza JavaScript il form parte uguale e la vista gira tutto lei.
    invia: function (form) {
      const campo = document.createElement('input');
      campo.type = 'hidden'; campo.name = 'js'; campo.value = '1';
      form.appendChild(campo);
      this.mostra();
    },
    riprendi: function () {
      const nodo = id('avanzamento');
      const totale = nodo ? parseInt(nodo.dataset.totale, 10) || 0 : 0;
      if (!totale) return false;
      id('kvTotale').textContent = totale;
      this.mostra();
      gira(nodo, totale);
      return true;
    }
  };
})(window);
