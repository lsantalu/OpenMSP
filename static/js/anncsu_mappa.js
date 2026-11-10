// static/js/anncsu_mappa.js
// I civici di una via sopra la mappa: il puntino rosso porta il numero del civico, un click
// seleziona, e dal pannello si scrive nel form (stessa funzione del pulsante Usa) o si chiede
// la soppressione all'unico eService che la sa fare: Aggiornamento accessi.
// shortcut: ~600 marker, oltre: leaflet.markercluster
(function () {
  "use strict";

  // la dicitura del metodo di rilievo non viene duplicata qui: e' gia' nelle option del tendina
  function dizionarioMetodi() {
    const tendina = document.getElementById("sl_metodo");
    const dizionario = {};
    if (tendina) {
      Array.prototype.forEach.call(tendina.options, function (voce) {
        dizionario[voce.value] = voce.textContent.trim();
      });
    }
    return dizionario;
  }

  function avviarsi() {
    const riquadro = document.getElementById("anncsu-mappa");
    const blob = document.getElementById("anncsu-accessi");
    // niente Leaflet o niente blob: la pagina resta il form, nessun errore in console
    if (!riquadro || !blob || typeof window.L === "undefined") return;

    function avvisa(testo) {
      const avviso = document.createElement("p");
      avviso.className = "form-note text-danger";
      avviso.textContent = testo;
      riquadro.parentNode.insertBefore(avviso, riquadro);
    }

    let accessi;
    try {
      accessi = JSON.parse(blob.textContent || "[]");
    } catch (blobMalformato) {
      avvisa("L'elenco dei civici non si e' letto (" + blobMalformato.name
             + "): la mappa non si disegna, il form resta utilizzabile.");
      return;
    }
    if (!Array.isArray(accessi)) return;
    const puoSopprimere = riquadro.dataset.sopprimi === "1";   // lo decide la vista, non il JS
    const urlAccessi = riquadro.dataset.urlAccessi;
    const metodi = dizionarioMetodi();
    const mappa = L.map(riquadro, {
      maxZoom: 19,
      maxBounds: L.latLngBounds([[36, 6], [47, 18]]),   // la scatola d'Italia dello YAML
      maxBoundsViscosity: 1.0
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                {maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"}).addTo(mappa);

    const pannello = document.createElement("div");
    pannello.className = "anncsu-pannello";
    pannello.hidden = true;
    riquadro.parentNode.insertBefore(pannello, riquadro);

    let attivo = null, tileMancate = false;

    function mostra(accesso) {
      pannello.textContent = "";                       // si ricomincia da vuoti: niente HTML
      const titolo = document.createElement("strong");
      titolo.textContent = accesso.numero || "(civico senza numero)";
      const dettagli = document.createElement("span");
      dettagli.textContent = "  " + (accesso.x || "—") + ", " + (accesso.y || "—")
                           + "  quota " + (accesso.quota || "n.d.")
                           + "  metodo " + (accesso.metodo || "n.d.")
                           + (metodi[accesso.metodo] ? " — " + metodi[accesso.metodo] : "");
      pannello.appendChild(titolo);
      pannello.appendChild(dettagli);
      const usa = document.createElement("button");
      usa.type = "button";
      usa.className = "btn btn-sm btn-outline-primary ms-3";
      usa.textContent = "Usa nel form";
      usa.addEventListener("click", function () {
        // il blob chiama quota il campo che nel form si chiama z
        window.anncsuUsa({progr_civico: accesso.prognazacc, x: accesso.x, y: accesso.y,
                          z: accesso.quota, metodo: accesso.metodo});
      });
      pannello.appendChild(usa);
      // un id vuoto aprirebbe una pagina di scrittura prefillata di niente
      if (puoSopprimere && accesso.prognazacc) {
        const sopprimi = document.createElement("a");
        sopprimi.className = "btn btn-sm btn-outline-danger ms-2";
        sopprimi.textContent = "Sopprimi";
        // l'altro eService vuole progr_nazionale, che qui arriva come prognazacc
        sopprimi.href = urlAccessi + "?progr_nazionale=" + encodeURIComponent(accesso.prognazacc)
                      + "&operazione_civico=S";
        pannello.appendChild(sopprimi);
      }
      pannello.hidden = false;
    }

    function seleziona(marker, accesso) {
      if (attivo && attivo !== marker) {
        const vecchio = attivo.getElement();
        if (vecchio) vecchio.classList.remove("attivo");
      }
      attivo = marker;
      const elemento = marker.getElement();
      if (elemento) elemento.classList.add("attivo");
      mostra(accesso);
    }

    const marker = [];
    accessi.forEach(function (accesso) {
      const icona = L.divIcon({html: "<i></i>", className: "anncsu-puntino",
                               iconSize: [26, 26], iconAnchor: [13, 13]});
      const punto = L.marker(accesso.punto, {icon: icona, title: accesso.numero}).addTo(mappa);
      punto.on("add", function () {
        const etichetta = punto.getElement() && punto.getElement().firstChild;
        if (etichetta) etichetta.textContent = accesso.numero;   // dall'erogatore: testo
      });
      punto.on("click", function () { seleziona(punto, accesso); });
      marker.push(punto);
    });
    if (marker.length) mappa.fitBounds(L.featureGroup(marker).getBounds().pad(0.15));

    // il deploy puo` stare dietro un egresso chiuso: la mappa grigia non deve nascondere il resto
    mappa.on("tileerror", function () {
      if (tileMancate) return;
      tileMancate = true;
      riquadro.classList.add("senza-tile");
      avvisa("Le tile di OpenStreetMap non arrivano: la mappa resta vuota, l'elenco qui sotto "
             + "e il pulsante Usa funzionano lo stesso.");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", avviarsi);
  } else {
    avviarsi();
  }
})();
