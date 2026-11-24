/* Due aiuto-funzioni condivise dai template dei servizi, caricate da base.html.

   mostraErroreCf: allerta di validazione del codice fiscale, costruita a codice invece di
   scrivere HTML nei template.
   sostituisciCorpo: le pagine massive aggiornano i risultati con un fetch della pagina gia'
   resa; qui il corpo viene sostituito con nodi importati, come faceva innerHTML, senza il
   rischio di iniettare markup. I <script> del frammento non partono in nessuno dei due casi. */
function mostraErroreCf(contenitore, messaggio) {
  if (!contenitore) {
    return;
  }
  contenitore.replaceChildren();
  const box = document.createElement('div');
  box.className = 'alert alert-danger alert-dismissible fade show';
  box.setAttribute('role', 'alert');
  const titolo = document.createElement('strong');
  titolo.textContent = 'Attenzione';
  const chiusura = document.createElement('button');
  chiusura.type = 'button';
  chiusura.className = 'btn-close';
  chiusura.setAttribute('data-bs-dismiss', 'alert');
  chiusura.setAttribute('aria-label', 'Chiudi avviso');
  box.append(titolo);
  box.append(document.createTextNode(' ' + messaggio));
  box.append(chiusura);
  contenitore.append(box);
}

// Chiamata dai template dei servizi: il global e' voluto, i template non possono importare.
window.mostraErroreCf = mostraErroreCf;

function sostituisciCorpo(html) {
  const documento = new DOMParser().parseFromString(html, 'text/html');
  const nodi = Array.from(documento.body.childNodes).map((nodo) => document.importNode(nodo, true));
  document.body.replaceChildren(...nodi);
}

window.sostituisciCorpo = sostituisciCorpo;

function mostraTabellaDati(visibile) {
  const tabella = document.getElementById('dataTable');
  if (tabella && tabella.parentNode) {
    tabella.parentNode.style.display = visibile ? 'block' : 'none';
  }
}

function mostraJson(valore) {
  const box = document.getElementById('json-display');
  if (!box) {
    return;
  }
  // Il detalle puo' arrivare gia' indentato (una stringa) oppure come oggetto, e a volte
  // arriva doppio incapsulato: JSON.stringify di una stringa che era gia' JSON. Ri-serializzare
  // una stringa e' il modo in cui i \n diventano testo letterale in pagina, quindi qui la
  // stringa la si scarta un giro alla volta, finche' non si trova un oggetto o un testo vero.
  let testo = valore;
  for (let giro = 0; giro < 3; giro++) {
    if (typeof testo === 'string' && /^\s*[[{"]/.test(testo)) {
      try {
        testo = JSON.parse(testo);
        continue;
      } catch (nonEJson) {
        break;
      }
    }
    break;
  }
  box.textContent = typeof testo === 'string' ? testo : JSON.stringify(testo, null, 4);
}

window.mostraTabellaDati = mostraTabellaDati;
window.mostraJson = mostraJson;

function stampaRisultati(finestra, area) {
  if (!finestra || !finestra.document || !area) {
    return;
  }
  const nodi = Array.from(area.childNodes).map((nodo) => finestra.document.importNode(nodo.cloneNode(true), true));
  finestra.document.body.append(...nodi);
}

window.stampaRisultati = stampaRisultati;
