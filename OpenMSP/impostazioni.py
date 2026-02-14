from django.http import HttpResponse, JsonResponse
import json
from django.shortcuts import render
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.core.mail import send_mail
from django.contrib import messages
import os
import re

from django.db import models
from impostazioni.forms import CloneUserForm

from .utils import salva_log

from PIL import Image
import base64
import io

from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri
from impostazioni.models import GruppiParametri
from impostazioni.models import DatiEnte
from impostazioni.scheduler import send_db_backup
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import devices_for_user


def impostazioni_parametri(request):
    dati_ente = DatiEnte.objects.get(id=1)
    email_host = settings.EMAIL_HOST
    email_port = settings.EMAIL_PORT
    email_use = ""
    email_use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
    email_use_tls = getattr(settings, 'EMAIL_USE_TLS', False)
    if email_use_ssl:
        email_use = "ssl"
    elif email_use_tls:
        email_use = "tls"
    else:
        email_use = "none"

    email_host_user = settings.EMAIL_HOST_USER
    email_host_password = settings.EMAIL_HOST_PASSWORD
    email_default = settings.DEFAULT_FROM_EMAIL
    email_backup = settings.EMAIL_BACKUP_ADDRESS
    email_backup_password = settings.EMAIL_BACKUP_PASSWORD
    backup_on = settings.EMAIL_BACKUP_ON
    debug_mode = settings.DEBUG

    if request.method == 'POST':
        action_type = request.POST.get('action')

        if action_type == 'test':
            to_email = request.user.email
            subject = "Messaggio di TEST OpenMSP"
            message = "Messaggio di test generato dal portale OpenMSP"
            try:
                send_mail(
                    subject,  # Oggetto
                    message,  # Corpo del messaggio
                    settings.DEFAULT_FROM_EMAIL,  # Indirizzo email del mittente
                    [to_email],  # Destinatario
                    fail_silently=False,
                )
            except Exception as e:
                raise

        elif action_type == 'test_backup':
            send_db_backup()

        elif action_type == 'salva':
            email_host = request.POST.get('smtp')
            email_port = request.POST.get('port')
            email_use = request.POST.get('ssl_group')

            email_host_user = request.POST.get('user')
            email_host_password = request.POST.get('password')
            email_default = request.POST.get('email_send')
            email_backup = request.POST.get('email_backup_visibile')
            email_backup_visibile = request.POST.get('email_backup_visibile')
            email_backup_password = request.POST.get('email_backup_password_visibile')
            email_backup_password_visibile = request.POST.get('email_backup_password_visibile')

            debug_val = request.POST.get('toggle_debug', '')
            debug_mode = str(debug_val).capitalize() == 'True'

            backup_val = request.POST.get('toggle_backup', '')
            backup_on = str(backup_val).capitalize() == 'True'

            settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

            env_updates = {
                "EMAIL_HOST_USER": f"'{email_host_user}'",
                "EMAIL_HOST": f"'{email_host}'",
                "EMAIL_PORT": f"{email_port}",
                "DEFAULT_FROM_EMAIL": f"'{email_default}'",
                "DEBUG": f"{debug_mode}",
                "EMAIL_BACKUP_ON": f"{backup_on}",
            }

            env_updates["EMAIL_HOST_PASSWORD"] = f"'{email_host_password}'"
            env_updates["EMAIL_BACKUP_ADDRESS"] = f"'{email_backup}'"
            env_updates["EMAIL_BACKUP_PASSWORD"] = f"'{email_backup_password}'"

            if email_use == "ssl":
                env_updates["EMAIL_USE_SSL"] = "True"
                env_updates["EMAIL_USE_TLS"] = "False"
            elif email_use == "tls":
                env_updates["EMAIL_USE_SSL"] = "False"
                env_updates["EMAIL_USE_TLS"] = "True"
            else:
                env_updates["EMAIL_USE_SSL"] = "False"
                env_updates["EMAIL_USE_TLS"] = "False"

            try:
                with open(settings_path, 'r') as file:
                    lines = file.readlines()
            except FileNotFoundError:
                lines = []

            new_lines = []
            processed_keys = set()

            for line in lines:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    if key in env_updates:
                        new_lines.append(f"{key} = {env_updates[key]}\n")
                        processed_keys.add(key)
                        continue
                new_lines.append(line)

            keys_to_add = ["EMAIL_USE_SSL", "EMAIL_USE_TLS"]
            if any(k not in processed_keys for k in keys_to_add):
                insert_index = len(new_lines)
                for i, line in enumerate(new_lines):
                    if line.strip().startswith("EMAIL_PORT"):
                        insert_index = i + 1
                        break

                if "EMAIL_USE_TLS" not in processed_keys:
                    new_lines.insert(insert_index, f"EMAIL_USE_TLS = {env_updates['EMAIL_USE_TLS']}\n")
                if "EMAIL_USE_SSL" not in processed_keys:
                    new_lines.insert(insert_index, f"EMAIL_USE_SSL = {env_updates['EMAIL_USE_SSL']}\n")

            with open(settings_path, 'w') as file:
                file.writelines(new_lines)

            dati_ente.nome = request.POST.get('nome_ente')
            dati_ente.cf = request.POST.get('cf_ente')
            dati_ente.piva = request.POST.get('piva_ente')
            dati_ente.via = request.POST.get('via_ente')
            dati_ente.cap = request.POST.get('cap_ente')
            dati_ente.citta = request.POST.get('citta_ente')
            dati_ente.telefono = request.POST.get('telefono_ente')
            dati_ente.mail = request.POST.get('mail_ente')
            dati_ente.pec = request.POST.get('pec_ente')
            dati_ente.save()
            salva_log(request.user, "Impostazioni Parametri", "modifica parametri")

    dati_ente = DatiEnte.objects.all()

    context = {
        'dati_ente': dati_ente,
        'email_host': email_host,
        'email_port': email_port,
        'email_use': email_use,
        'email_host_user': email_host_user,
        'email_host_password': email_host_password,
        'email_default': email_default,
        'email_backup': email_backup,
        'email_backup_password': email_backup_password,
        'backup_on': backup_on,
        'debug_mode': debug_mode,
        }

    return render(request, 'impostazioni_parametri.html', context)


def impostazioni_servizi(request):
    servizi_impostazioni = ServiziParametri.objects.all()
    gruppi_parametri = GruppiParametri.objects.all()

    if request.method == 'POST':
        for servizio in servizi_impostazioni:
            servizio_code = servizio.codice_servizio
            is_checked = f'toggle_{servizio_code}' in request.POST
            servizio.attivo = 1 if is_checked else 0
            servizio.save()
        salva_log(request.user,"Impostazioni Servizi", "modifica servizi attivi")

    return render(request, 'impostazioni_servizi.html', { 'servizi_impostazioni': servizi_impostazioni, 'gruppi_parametri': gruppi_parametri })


def impostazioni_servizi_toggle(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            service_code = data.get('service_code')
            active = data.get('active')

            if service_code is not None and active is not None:
                servizio = ServiziParametri.objects.get(codice_servizio=service_code)
                servizio.attivo = 1 if active else 0
                servizio.save()
                
                # Log dell'operazione
                status_text = "attivato" if active else "disattivato"
                salva_log(request.user, "Impostazioni Servizi", f"Servizio {service_code} {status_text}")
                
                return JsonResponse({'status': 'success', 'message': f'Servizio {status_text}'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Dati mancanti'}, status=400)
        except ServiziParametri.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Servizio non trovato'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Metodo non consentito'}, status=405)


def impostazioni_utenti_2(request):
    utenti_impostazioni = UtentiParametri.objects.all()
    utenti = User.objects.all()
    num_utenti_permessi = UtentiParametri.objects.count()
    num_utenti=User.objects.count()
    num_utenti_ultimo=User.objects.last().id

    if num_utenti_permessi < num_utenti:
        existing_ids_utenti_permessi = set(UtentiParametri.objects.values_list('utente_id', flat=True))
        existing_ids_utenti= set(User.objects.values_list('id', flat=True))

        for i in range (1, num_utenti_ultimo+1):
            if i not in existing_ids_utenti_permessi and i in existing_ids_utenti:
                UtentiParametri.objects.create(id=i, utente_id=User.objects.get(id=i), ipa_singolo=False, ipa_massivo=False, inad_singolo=False, inad_massivo=False, inipec_singolo=False, inipec_massivo=False, anpr_C001=False, anpr_C015=False, anpr_C017=False, anpr_C018=False, anpr_C020=False, anpr_C021=False, anpr_C030=False, mit_cude=False, mit_veicoli=False, mit_whitelist=False, mit_targa=False, anis_IFS02_singolo=False, anis_IFS02_massivo=False, anis_IFS03_singolo=False, anis_IFS03_massivo=False, cassa_forense=False, registro_imprese=False, inps_isee=False, inps_durc_singolo=False, inps_durc_massivo=False,app_io_verifica_singolo=False, app_io_verifica_massivo=False, app_io_singolo=False, app_io_massivo=False, anist_frequenze_singolo=False, anist_frequenze_massivo=False, anist_titoli_singolo=False, anist_titoli_massivo =False, app_io_composer=False, app_io_storico_messaggi=False)

    if request.method == 'POST':
        if 'trova_utente' in request.POST:
            utente_selezionato = request.POST.get('scegliUtente')
        elif 'disattiva_utente' in request.POST:
            utente_selezionato = request.POST.get('scegliUtente')
            utente_attivo = get_object_or_404(User, id=int(utente_selezionato))
            utente_attivo.is_active = not utente_attivo.is_active
            utente_attivo.save()
        else:
            utente_selezionato = request.POST.get('utente_selezionato')
            array_permessi = request.POST.get('array_permessi')
            ipa_singolo = (True if 'ipa_singolo' in array_permessi else False)
            ipa_massivo = (True if 'ipa_massivo' in array_permessi else False)
            inad_singolo = (True if 'inad_singolo' in array_permessi else False)
            inad_massivo = (True if 'inad_massivo' in array_permessi else False)
            inipec_singolo = (True if 'inipec_singolo' in array_permessi else False)
            inipec_massivo = (True if 'inipec_massivo' in array_permessi else False)
            anpr_C001 = (True if 'anpr_C001' in array_permessi else False)
            anpr_C015 = (True if 'anpr_C015' in array_permessi else False)
            anpr_C017 = (True if 'anpr_C017' in array_permessi else False)
            anpr_C018 = (True if 'anpr_C018' in array_permessi else False)
            anpr_C020 = (True if 'anpr_C020' in array_permessi else False)
            anpr_C021 = (True if 'anpr_C021' in array_permessi else False)
            anpr_C030 = (True if 'anpr_C030' in array_permessi else False)
            mit_cude = (True if 'mit_cude' in array_permessi else False)
            mit_veicoli = (True if 'mit_veicoli' in array_permessi else False)
            mit_whitelist = (True if 'mit_whitelist' in array_permessi else False)
            mit_targa = (True if 'mit_targa' in array_permessi else False)
            anis_IFS02_singolo = (True if 'anis_IFS02_singolo' in array_permessi else False)
            anis_IFS02_massivo = (True if 'anis_IFS02_massivo' in array_permessi else False)
            anis_IFS03_singolo = (True if 'anis_IFS03_singolo' in array_permessi else False)
            anis_IFS03_massivo = (True if 'anis_IFS03_massivo' in array_permessi else False)
            cassa_forense = (True if 'cassa_forense' in array_permessi else False)
            registro_imprese = (True if 'registro_imprese' in array_permessi else False)
            inps_isee = (True if 'inps_isee' in array_permessi else False)
            inps_durc_singolo = (True if 'inps_durc_singolo' in array_permessi else False)
            inps_durc_massivo = (True if 'inps_durc_massivo' in array_permessi else False)
            app_io_verifica_singolo = (True if 'app_io_verifica_singolo' in array_permessi else False)
            app_io_verifica_massivo = (True if 'app_io_verifica_massivo' in array_permessi else False)
            app_io_singolo = (True if 'app_io_singolo' in array_permessi else False)
            app_io_massivo = (True if 'app_io_massivo' in array_permessi else False)
            anist_frequenze_singolo = (True if 'anist_frequenze_singolo' in array_permessi else False)
            anist_frequenze_massivo = (True if 'anist_frequenze_massivo' in array_permessi else False)
            anist_titoli_singolo = (True if 'anist_titoli3_singolo' in array_permessi else False)
            anist_titoli_massivo = (True if 'anist_titoli_massivo' in array_permessi else False)
            app_io_composer = (True if 'app_io_composer' in array_permessi else False)
            app_io_storico_messaggi = (True if 'app_io_storico_messaggi' in array_permessi else False)

            dati = UtentiParametri(int(utente_selezionato), int(utente_selezionato), ipa_singolo=ipa_singolo, ipa_massivo=ipa_massivo,  inad_singolo=inad_singolo, inad_massivo=inad_massivo, inipec_singolo=inipec_singolo, inipec_massivo=inipec_massivo, anpr_C001=anpr_C001, anpr_C015=anpr_C015, anpr_C017=anpr_C017, anpr_C018=anpr_C018, anpr_C020=anpr_C020, anpr_C021=anpr_C021, anpr_C030=anpr_C030, mit_cude = mit_cude, mit_veicoli = mit_veicoli, mit_whitelist=mit_whitelist, mit_targa = mit_targa, anis_IFS02_singolo=anis_IFS02_singolo, anis_IFS02_massivo=anis_IFS02_massivo, anis_IFS03_singolo=anis_IFS03_singolo, anis_IFS03_massivo=anis_IFS03_massivo, cassa_forense=cassa_forense, registro_imprese=registro_imprese, inps_isee=inps_isee, inps_durc_singolo=inps_durc_singolo, inps_durc_massivo=inps_durc_massivo, app_io_verifica_singolo=app_io_verifica_singolo, app_io_verifica_massivo=app_io_verifica_massivo, app_io_singolo=app_io_singolo, app_io_massivo=app_io_massivo, anist_frequenze_singolo=anist_frequenze_singolo, anist_frequenze_massivo=anist_frequenze_massivo, anist_titoli_singolo=anist_titoli_singolo, anist_titoli_massivo=anist_titoli_massivo, app_io_composer=app_io_composer, app_io_storico_messaggi=app_io_storico_messaggi)
            dati.save()
            salva_log(request.user,"Impostazioni Utenti", "modifica parametri")

        servizi_utente = UtentiParametri.objects.get(id=utente_selezionato)
        numero_servizi = len(utenti_impostazioni[0]._meta.fields)-1
        utente_adm = (1 if User.objects.get(id=utente_selezionato).is_superuser else 0)
        numero_servizi_attivi = servizi_attivi_utente(utente_selezionato) + utente_adm
        numero_servizi_disattivi = numero_servizi - numero_servizi_attivi

        return render(request, 'impostazioni_utenti_2.html', { 'utenti': utenti, 'utente_selezionato': int(utente_selezionato), 'servizi_utente': servizi_utente, 'numero_servizi_attivi': numero_servizi_attivi, 'numero_servizi_disattivi': numero_servizi_disattivi, 'utenti_impostazioni': utenti_impostazioni })


    return render(request, 'impostazioni_utenti_2.html', { 'utenti_impostazioni': utenti_impostazioni, 'utenti': utenti})


def impostazioni_clone_user(request):

    utenti = User.objects.all()

    if request.method == 'POST':
        form = CloneUserForm(request.POST)
        if form.is_valid():
            # Crea nuovo utente
            nuovo_utente = form.save()
            
            # Leggi ID dell’utente da clonare
            utente_origine_id = request.POST.get('scegliUtente')

            # Clona i permessi personalizzati
            if utente_origine_id:
                try:
                    originale = UtentiParametri.objects.get(utente_id=utente_origine_id)
                    # Create new parameters linked to the new user
                    # Assuming UtentiParametri.id should match User.id based on other code
                    nuovo_parametri = UtentiParametri(id=nuovo_utente.id, utente_id=nuovo_utente)

                    for field in UtentiParametri._meta.fields:
                        if field.name not in ['id', 'utente_id'] and isinstance(field, models.BooleanField):
                            setattr(nuovo_parametri, field.name, getattr(originale, field.name))

                    nuovo_parametri.save()
                except UtentiParametri.DoesNotExist:
                    messages.warning(request, "Utente di origine senza permessi associati.")
            
            messages.success(request, "Utente clonato correttamente.")
            return redirect('impostazioni_utenti')
        else:
            messages.error(request, "Errore nella compilazione del form. Controlla i dati inseriti.")
    else:
        form = CloneUserForm()

    return render(request, 'registration/clone_user.html', {'utenti': utenti, 'form': form})





def impostazioni_utenti(request):
    utenti_impostazioni = UtentiParametri.objects.all()
    utenti = User.objects.all()
    num_utenti_permessi = UtentiParametri.objects.count()
    num_utenti=User.objects.count()
    num_utenti_ultimo=User.objects.last().id
    servizi_impostazioni = ServiziParametri.objects.all()
    gruppi_parametri = GruppiParametri.objects.all()


    if num_utenti_permessi < num_utenti:
        existing_ids_utenti_permessi = set(UtentiParametri.objects.values_list('utente_id', flat=True))
        existing_ids_utenti= set(User.objects.values_list('id', flat=True))

        for i in range (1, num_utenti_ultimo+1):
            if i not in existing_ids_utenti_permessi and i in existing_ids_utenti:
                UtentiParametri.objects.create(id=i, utente_id=User.objects.get(id=i), ipa_singolo=False, ipa_massivo=False, inad_singolo=False, inad_massivo=False, inipec_singolo=False, inipec_massivo=False, anpr_C001=False, anpr_C015=False, anpr_C017=False, anpr_C018=False, anpr_C020=False, anpr_C021=False, anpr_C030=False,  mit_cude=False, mit_veicoli=False, mit_whitelist=False, mit_targa=False, anis_IFS02_singolo=False, anis_IFS02_massivo=False, anis_IFS03_singolo=False, anis_IFS03_massivo=False, cassa_forense=False, registro_imprese=False, inps_isee=False, inps_durc_singolo=False, inps_durc_massivo=False,app_io_verifica_singolo=False, app_io_verifica_massivo=False, app_io_singolo=False, app_io_massivo=False, anist_frequenze_singolo=False, anist_frequenze_massivo=False, anist_titoli_singolo=False, anist_titoli_massivo =False, app_io_composer=False, app_io_storico_messaggi=False)

    if request.method == 'POST':
        if 'trova_utente' in request.POST:
            utente_selezionato = request.POST.get('scegliUtente')
        elif 'disattiva_utente' in request.POST:
            utente_selezionato = request.POST.get('scegliUtente')
            utente_attivo = get_object_or_404(User, id=int(utente_selezionato))
            utente_attivo.is_active = not utente_attivo.is_active
            utente_attivo.save()
        elif 'reset_2fa' in request.POST:
            utente_selezionato = request.POST.get('scegliUtente')
            utente_target = get_object_or_404(User, id=int(utente_selezionato))
            for device in devices_for_user(utente_target):
                device.delete()
            messages.success(request, f"2FA resettata per l'utente {utente_target.username}.")
        else:
            utente_selezionato = request.POST.get('utente_selezionato')
            array_permessi = request.POST.get('array_permessi')
            ipa_singolo = (True if 'ipa_singolo' in array_permessi else False)
            ipa_massivo = (True if 'ipa_massivo' in array_permessi else False)
            inad_singolo = (True if 'inad_singolo' in array_permessi else False)
            inad_massivo = (True if 'inad_massivo' in array_permessi else False)
            inipec_singolo = (True if 'inipec_singolo' in array_permessi else False)
            inipec_massivo = (True if 'inipec_massivo' in array_permessi else False)
            anpr_C001 = (True if 'anpr_C001' in array_permessi else False)
            anpr_C015 = (True if 'anpr_C015' in array_permessi else False)
            anpr_C017 = (True if 'anpr_C017' in array_permessi else False)
            anpr_C018 = (True if 'anpr_C018' in array_permessi else False)
            anpr_C020 = (True if 'anpr_C020' in array_permessi else False)
            anpr_C021 = (True if 'anpr_C021' in array_permessi else False)
            anpr_C030 = (True if 'anpr_C030' in array_permessi else False)
            mit_cude = (True if 'mit_cude' in array_permessi else False)
            mit_veicoli = (True if 'mit_veicoli' in array_permessi else False)
            mit_whitelist = (True if 'mit_whitelist' in array_permessi else False)
            mit_targa = (True if 'mit_targa' in array_permessi else False)
            anis_IFS02_singolo = (True if 'anis_IFS02_singolo' in array_permessi else False)
            anis_IFS02_massivo = (True if 'anis_IFS02_massivo' in array_permessi else False)
            anis_IFS03_singolo = (True if 'anis_IFS03_singolo' in array_permessi else False)
            anis_IFS03_massivo = (True if 'anis_IFS03_massivo' in array_permessi else False)
            cassa_forense = (True if 'cassa_forense' in array_permessi else False)
            registro_imprese = (True if 'registro_imprese' in array_permessi else False)
            inps_isee = (True if 'inps_isee' in array_permessi else False)
            inps_durc_singolo = (True if 'inps_durc_singolo' in array_permessi else False)
            inps_durc_massivo = (True if 'inps_durc_massivo' in array_permessi else False)
            app_io_verifica_singolo = (True if 'app_io_verifica_singolo' in array_permessi else False)
            app_io_verifica_massivo = (True if 'app_io_verifica_massivo' in array_permessi else False)
            app_io_singolo = (True if 'app_io_singolo' in array_permessi else False)
            app_io_massivo = (True if 'app_io_massivo' in array_permessi else False)
            anist_frequenze_singolo = (True if 'anist_frequenze_singolo' in array_permessi else False)
            anist_frequenze_massivo = (True if 'anist_frequenze_massivo' in array_permessi else False)
            anist_titoli_singolo = (True if 'anist_titoli_singolo' in array_permessi else False)
            anist_titoli_massivo = (True if 'anist_titoli_massivo' in array_permessi else False)
            app_io_composer = (True if 'app_io_composer' in array_permessi else False)
            app_io_storico_messaggi = (True if 'app_io_storico_messaggi' in array_permessi else False)
            dati = UtentiParametri(int(utente_selezionato), int(utente_selezionato), ipa_singolo=ipa_singolo, ipa_massivo=ipa_massivo,  inad_singolo=inad_singolo, inad_massivo=inad_massivo, inipec_singolo=inipec_singolo, inipec_massivo=inipec_massivo, anpr_C001=anpr_C001, anpr_C015=anpr_C015, anpr_C017=anpr_C017, anpr_C018=anpr_C018, anpr_C020=anpr_C020, anpr_C021=anpr_C021, anpr_C030=anpr_C030, mit_cude = mit_cude, mit_veicoli = mit_veicoli, mit_whitelist=mit_whitelist, mit_targa = mit_targa, anis_IFS02_singolo=anis_IFS02_singolo, anis_IFS02_massivo=anis_IFS02_massivo, anis_IFS03_singolo=anis_IFS03_singolo, anis_IFS03_massivo=anis_IFS03_massivo, cassa_forense=cassa_forense, registro_imprese=registro_imprese, inps_isee=inps_isee, inps_durc_singolo=inps_durc_singolo, inps_durc_massivo=inps_durc_massivo, app_io_verifica_singolo=app_io_verifica_singolo, app_io_verifica_massivo=app_io_verifica_massivo, app_io_singolo=app_io_singolo, app_io_massivo=app_io_massivo, anist_frequenze_singolo=anist_frequenze_singolo, anist_frequenze_massivo=anist_frequenze_massivo, anist_titoli_singolo=anist_titoli_singolo, anist_titoli_massivo=anist_titoli_massivo, app_io_composer=app_io_composer, app_io_storico_messaggi=app_io_storico_messaggi)
            dati.save()
            salva_log(request.user,"Impostazioni Utenti", "modifica parametri")

        servizi_utente = UtentiParametri.objects.get(id=utente_selezionato)
        numero_servizi = len(utenti_impostazioni[0]._meta.fields)-1
        utente_adm = (1 if User.objects.get(id=utente_selezionato).is_superuser else 0)
        numero_servizi_attivi = servizi_attivi_utente(utente_selezionato) + utente_adm
        numero_servizi_disattivi = numero_servizi - numero_servizi_attivi

        return render(request, 'impostazioni_utenti.html', { 'utenti': utenti, 'utente_selezionato': int(utente_selezionato), 'servizi_utente': servizi_utente, 'numero_servizi_attivi': numero_servizi_attivi, 'numero_servizi_disattivi': numero_servizi_disattivi, 'utenti_impostazioni': utenti_impostazioni, 'servizi_impostazioni': servizi_impostazioni, 'gruppi_parametri': gruppi_parametri })


    return render(request, 'impostazioni_utenti.html', { 'utenti_impostazioni': utenti_impostazioni, 'utenti': utenti, 'servizi_impostazioni': servizi_impostazioni, 'gruppi_parametri': gruppi_parametri})


def impostazioni_upload_stemma(request):
    ente = get_object_or_404(DatiEnte)

    if request.method == 'POST':
        new_stemma = request.FILES.get('new_stemma')

        if new_stemma:
            img = Image.open(new_stemma).convert("RGBA")
            r, g, b, a = img.split()
            ### gray_img = img.convert("L")
            ### img = Image.merge("RGBA", (gray_img, gray_img, gray_img, a))
            img.thumbnail((200, 200))
            square_img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            x_offset = (200 - img.width) // 2
            y_offset = (200 - img.height) // 2
            square_img.paste(img, (x_offset, y_offset))
            buffer = io.BytesIO()
            square_img.save(buffer, format="PNG")
            buffer.seek(0)
            base64_stemma = base64.b64encode(buffer.read()).decode('utf-8')
            ente.stemma = base64_stemma
            ente.save()

            return HttpResponse("""
                <script type="text/javascript">
                    window.opener.location.reload();
                    window.close();
                </script>
            """)

    return render(request, 'impostazioni_upload_stemma.html', {'ente': ente})


def servizi_attivi_utente(utente_id):
    servizi_utente = UtentiParametri.objects.get(id=utente_id)
    servizi_attivi_utente = servizi_utente.somma_servizi_attivi()
    return servizi_attivi_utente
