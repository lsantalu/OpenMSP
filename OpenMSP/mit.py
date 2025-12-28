from django.shortcuts import render

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import MitServizi
from impostazioni.models import MitParametri

from .utils import salva_log
from .utils import converti_data
from .verifica_cf import verifica_cf

##from datetime import datetime, date
import datetime
from jose.constants import Algorithms
import http.client, urllib.parse
import hashlib
import random
import base64
import datetime
import uuid
import jwt
import subprocess
import requests
import json
import io
import csv
import re
import openpyxl


def mit_dettaglio_cude(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_cude
    return render(request, 'mit_dettaglio_cude.html', { 'utente_abilitato': utente_abilitato })


def mit_lista_patenti(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_patenti
    return render(request, 'mit_lista_patenti.html', { 'utente_abilitato': utente_abilitato })


def mit_lista_veicoli_cude(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_veicoli
    return render(request, 'mit_lista_veicoli_cude.html', { 'utente_abilitato': utente_abilitato })


def mit_verifica_targa_cude(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.mit_targa
    return render(request, 'mit_verifica_targa_cude.html', { 'utente_abilitato': utente_abilitato })


def impostazioni_mit(request):
    servizi_mit = MitServizi.objects.all()
    parametri_mit = MitParametri.objects.all()

    service_active = ServiziParametri.objects.all()
    i_serv=0
    service_desc = ["" for _ in range(ServiziParametri.objects.count())]
    for servizio in service_active:
        service_desc[i_serv]= (servizio.attivo)
        i_serv += 1

    if request.method == 'POST':
        posizione_servizio = ServiziParametri.objects.filter(gruppo_id=5).values_list('id', flat=True)
        for i in range(1, MitParametri.objects.count()+1):
            if service_desc[posizione_servizio[i-1]-1]:
                kid = request.POST.get('kid' + str(i))
                alg = request.POST.get('alg' + str(i))
                typ = request.POST.get('typ' + str(i))
                iss = request.POST.get('iss' + str(i))
                sub = request.POST.get('sub' + str(i))
                aud = request.POST.get('aud' + str(i))
                purposeid = request.POST.get('purposeid' + str(i))
                audience = request.POST.get('audience' + str(i))
                baseurlauth = request.POST.get('baseurlauth' + str(i))
                target = request.POST.get('target' + str(i))
                clientid = request.POST.get('clientid' + str(i))
                private_key = request.POST.get('private_key' + str(i))
                ver_eservice = request.POST.get('ver_eservice' + str(i))
                dati = MitParametri(i, i, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
                dati.save()
        salva_log(request.user,"Impostazioni MIT", "modifica parametri")

    return render(request, 'impostazioni_mit.html', { 'servizi_mit': servizi_mit, 'parametri_mit': parametri_mit })

