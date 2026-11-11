/* static/js/comuni.js
   I campi con data-lookup="comuni" si compiano per nome: l'operatore scrive 'rom' e sceglie
   'Roma (H501)'. Il codice si cava dal suffisso (CODICE) solo all'invio, cosi' senza JavaScript
   - o senza lista raggiungibile - il form spedisce esattamente quello che spediva oggi: un
   codice di quattro caratteri, o niente.

   Va caricato PRIMA degli script inline di pagina: il suo listener di submit deve essere il
   primo del form, cosi' puo' impedire all'overlay di caricamento di accendersi su un invio
   che l'operatore ha annullato.
*/
(function () {
  const campi = document.querySelectorAll('input[data-lookup="comuni"]');
  const sorgente = document.querySelector('[data-comuni-json]');
  if (!campi.length || !sorgente) return;

  const CODICE = /\(([A-Z0-9]{4})\)\s*$/;   // 'Roma (H501)' -> H501
  const REGIME = /^[A-Z0-9]{4}$/;
  const MASSIME = 10;
  let voci = null, perCodice = null;

  function normalizza(testo) {
    return String(testo).normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toUpperCase().replace(/[^A-Z0-9]/g, '');
  }

  function codice(valore) {
    const colpo = CODICE.exec(valore);
    return colpo ? colpo[1] : String(valore).trim().toUpperCase();
  }

  fetch(sorgente.dataset.comuniJson)
    .then(function (risposta) { return risposta.json(); })
    .then(function (dati) {
      voci = dati;
      perCodice = {};
      dati.forEach(function (voce) { perCodice[voce.c] = voce.n; });
      // il default arriva dal server in forma di codice: si ritraduce, se il codice si conosce
      Array.prototype.forEach.call(campi, function (campo) {
        const nome = perCodice[codice(campo.value)];
        if (nome) {
          campo.dataset.risolto = codice(campo.value);
          campo.value = nome + ' (' + codice(campo.value) + ')';
        }
      });
    })
    .catch(function () { /* niente lista: i campi restano input di testo come ieri */ });

  Array.prototype.forEach.call(campi, function (campo) {
    const lista = document.createElement('ul');
    lista.className = 'autocomplete-list';
    campo.parentNode.insertBefore(lista, campo.nextSibling);   // stessa posizione del plugin BI

    let proposte = [], sintetica = false;

    function chiudi() {
      lista.classList.remove('autocomplete-list-show');
      proposte = [];
    }

    function scegli(voce) {
      sintetica = true;
      campo.dataset.risolto = voce.c;
      campo.value = voce.n + ' (' + voce.c + ')';
      chiudi();
      campo.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function dipingi() {
      const q = normalizza(campo.value);
      proposte = (!voci || sintetica || q.length < 2) ? [] : voci.filter(function (voce) {
        return normalizza(voce.n).startsWith(q) || voce.c.startsWith(q);
      }).slice(0, MASSIME);
      lista.textContent = '';
      proposte.forEach(function (voce) {
        const voce2 = document.createElement('li'), link = document.createElement('a'),
          testo = document.createElement('span'), nome = document.createElement('span'),
          sigla = document.createElement('em');
        link.href = '#';
        testo.className = 'autocomplete-list-text';
        nome.textContent = voce.n;
        sigla.textContent = ' (' + voce.c + ')';
        testo.append(nome, sigla);
        link.append(testo);
        voce2.append(link);
        link.addEventListener('click', function (evento) {
          evento.preventDefault();
          scegli(voce);
        });
        lista.append(voce2);
      });
      lista.classList.toggle('autocomplete-list-show', proposte.length > 0);
    }

    campo.addEventListener('input', function () {
      if (sintetica) { sintetica = false; return; }
      dipingi();
    });

    campo.addEventListener('keydown', function (evento) {
      if (evento.key === 'Escape') return chiudi();
      if (evento.key.length === 1 && !evento.ctrlKey && !evento.metaKey && CODICE.test(campo.value)) {
        campo.value = '';                    // si ricomincia da capo: la scelta precedente non vale
      }
      if (!proposte.length || (evento.key !== 'ArrowDown' && evento.key !== 'ArrowUp')) return;
      evento.preventDefault();
      let scelto = -1;
      proposte.forEach(function (voce, i) {
        if (campo.value.endsWith('(' + voce.c + ')')) scelto = i;
      });
      scegli(proposte[(scelto + (evento.key === 'ArrowDown' ? 1 : -1) + proposte.length + 1)
                      % proposte.length]);
    });

    // Un nome scritto e basta non esce dal browser: si torna alla scelta precedente, o via.
    // Senza questa regola 'Roma' parte tale e quale, passa il pattern di quattro caratteri e
    // ANNCSU risponde 'Esistenza non verificata' a chi chiedeva un odonimo di Roma.
    function ancora() {
      const colpo = CODICE.exec(campo.value);
      if (colpo) { campo.dataset.risolto = colpo[1]; return; }
      const precedente = perCodice[campo.dataset.risolto];
      campo.value = precedente ? precedente + ' (' + campo.dataset.risolto + ')' : '';
      campo.dataset.risolto = '';
    }

    campo.addEventListener('blur', function () {
      setTimeout(function () { chiudi(); if (perCodice) ancora(); }, 150);
    });

    const form = campo.form;
    if (!form || form.dataset.comuniPronto) return;
    form.dataset.comuniPronto = '1';

    // Il nominativo non esce dal browser: qui il campo torna il codice che l'operatore ha visto,
    // e se un codice non c'e' si resta fermi qui invece di spendere un voucher per niente.
    form.addEventListener('submit', function (evento) {
      Array.prototype.forEach.call(form.querySelectorAll('input[data-lookup="comuni"]'),
        function (campo) {
          const scritto = campo.value, colpo = CODICE.exec(scritto);
          if (colpo) campo.value = colpo[1];                   // 'Roma (H501)' -> 'H501'
          if (!perCodice || !campo.value) return;              // lista assente: come ieri
          if (REGIME.test(campo.value) && perCodice[campo.value]) return;
          window.alert(`«${scritto.trim()}» non è un comune dell’elenco: iniziare a scrivere `
                       + 'il nome e scegliere una delle voci proposte.');
          evento.preventDefault();
          evento.stopImmediatePropagation();                   // invio fermato: niente overlay
        });
    });
  });
}());
