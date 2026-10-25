# pyright: reportAttributeAccessIssue=false
# (Django 6 non pubblica py.typed: request.user e .objects per pyright non esistono)
"""Gate delle tre pagine unificate: domicili_digitali, anpr, istruzione.

Rende i template veri e legge i radio usciti, perche' il bug di ANPR era proprio un nome di
chiave diverso tra vista e template (servizi[].caso contro servizi[].chiave): un test
sull'helper da solo non lo avrebbe visto.

    env/bin/python verifica_selezione_servizi.py

Nessuna scrittura permanente: i flag di utenti_parametri sono finti e il flag di
servizi_parametri viene solo spento e riacceso.
"""
import os
import re
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OpenMSP.settings')

import django

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from impostazioni.models import ServiziParametri  # noqa: E402
from OpenMSP import anis, views  # noqa: E402

RIGHE = {
    'tipo_domicilio': (views.domicili_digitali_view,
                       ['ipa', 'inad', 'inipec'],
                       ['ipa_singolo', 'inipec_massivo'],
                       ['ipa', 'inipec'],
                       ['ipa', 'inad', 'registro_imprese']),
    'servizio_anpr': (views.anpr,
                      ['C001', 'C007', 'C015', 'C017', 'C018', 'C020', 'C021'],
                      ['anpr_C001', 'anpr_C015_massivo'],
                      ['C001', 'C015'],
                      ['anpr_c001', 'anpr_c007', 'anpr_c015', 'anpr_c017',
                       'anpr_c018', 'anpr_c020', 'anpr_c021']),
    'servizio_istruzione': (anis.istruzione,
                            ['IFS02', 'IFS03', 'ANIST_FREQ', 'ANIST_TITOLI'],
                            ['anis_IFS02_singolo', 'anist_titoli_massivo'],
                            ['IFS02', 'ANIST_TITOLI'],
                            ['anis_IFS02', 'anis_IFS03', 'anist_frequenze', 'anist_titoli']),
}


class Voce:
    """Riga di utenti_parametri: i flag chiesti sono True, gli altri False."""

    def __init__(self, **bandiere):
        self.__dict__.update(bandiere)

    def __getattr__(self, nome):
        return False


class Tabella:
    """UtentiParametri finta: objects.filter(...).first() restituisce la riga data (o None)."""

    def __init__(self, riga):
        self.objects = self
        self.riga = riga

    def filter(self, **_filtri):
        return self

    def first(self):
        return self.riga


def html_pagina(vista, riga):
    for modulo in (views, anis):
        modulo.UtentiParametri = Tabella(riga)
    richiesta = RequestFactory().get('/')
    richiesta.user = User(username='verificatore', id=1)
    return vista(richiesta).content.decode('utf-8')


def radio_renderizzati(html, nome_form):
    estrazioni = {}
    for radio in re.findall(rf'<input[^>]*name="{nome_form}"[^>]*>', html, re.I):
        valore = re.search(r'value="([^"]*)"', radio)
        if valore is None:
            raise AssertionError(f'radio {nome_form} senza value: il POST non distinguerebbe il servizio')
        estrazioni[valore.group(1)] = 'disabilitato' if 'disabled' in radio else 'attivo'
    return estrazioni


errori = []
for nome_form, (vista, attesi, flag_accesi, abilitati, codici) in RIGHE.items():
    # nessun permesso: la pagina non offre il form, dice di contattare l'amministratore
    html = html_pagina(vista, Voce())
    if radio_renderizzati(html, nome_form):
        errori.append(f'{vista.__name__}: senza alcun permesso il form non va offerto')
    if 'abilitat' not in html.lower():
        errori.append(f"{vista.__name__}: senza permessi manca l'avviso all'operatore")

    # due permessi accesi: la voce c'e' sempre, abilitata solo dove il flag e' attivo
    usciti = radio_renderizzati(html_pagina(vista, Voce(**dict.fromkeys(flag_accesi, True))), nome_form)
    for chiave in attesi:
        voluto = 'attivo' if chiave in abilitati else 'disabilitato'
        if usciti.get(chiave) != voluto:
            errori.append(f"{vista.__name__}/{chiave}: doveva essere {voluto}, "
                          f"e' {usciti.get(chiave)}")

    # eService spento: la voce non deve comparire affatto, nemmeno col permesso acceso
    spento = codici[0]
    ServiziParametri.objects.filter(codice_servizio=spento).update(attivo=False)
    try:
        usciti = radio_renderizzati(
            html_pagina(vista, Voce(**dict.fromkeys(flag_accesi, True))), nome_form)
        if attesi[0] in usciti:
            errori.append(f"{vista.__name__}/{attesi[0]}: con l'eService spento la voce "
                          'non deve comparire')
    finally:
        ServiziParametri.objects.filter(codice_servizio=spento).update(attivo=True)

    # riga di utenti_parametri assente: la pagina non deve esplodere
    html_pagina(vista, None)

print('\n'.join(errori) if errori else
      'ok - le tre pagine offrono solo gli eService attivi, disabilitano quelli senza permesso')
sys.exit(1 if errori else 0)
