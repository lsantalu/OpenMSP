import datetime
from random import randint

from apscheduler.schedulers.background import BackgroundScheduler
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone

import pyzipper
import os

from impostazioni.models import Logs


def start():
    scheduler = BackgroundScheduler()
    # 'interval' conta le 24 ore dall'avvio del processo: con `restart: always`, i deploy e i
    # 3 worker di gunicorn lo zero si ripreme ogni volta e il purge non partiva mai (608 righe
    # oltre l'anno ancora a terra). 'date' garantisce un giro a ogni avvio, 'cron' lo tiene
    # quotidiano quando il processo vive piu' di un giorno. Minuto sorteggiato perche' i 3
    # worker non cancellino nello stesso istante sullo stesso SQLite.
    scheduler.add_job(delete_old_logs, 'date', run_date=timezone.now() + datetime.timedelta(seconds=10))
    scheduler.add_job(delete_old_logs, 'cron', hour=2, minute=randint(0, 59))
    scheduler.add_job(send_db_backup, 'cron', hour=1, minute=0)  # Esegui ogni notte alle 1:00
    scheduler.start()


def delete_old_logs():
    cutoff = timezone.now() - datetime.timedelta(days=365)
    deleted_count, _ = Logs.objects.filter(timestamp__lt=cutoff).delete()
    if deleted_count:
        # solo metadati: niente dati anagrafici nei log (invariante 8)
        print(f"Purge logs: rimosse {deleted_count} righe precedenti al {cutoff:%d-%m-%Y}")
    return deleted_count

def send_db_backup():
    if settings.EMAIL_BACKUP_ON:
        # Usa settings.BASE_DIR anche qui per coerenza
        db_path = str(settings.BASE_DIR / 'db.sqlite3')
        zip_filename = str(settings.BASE_DIR / 'db_backup.zip')

        password = settings.EMAIL_BACKUP_PASSWORD
        email_address = settings.EMAIL_BACKUP_ADDRESS
        subject = 'Backup del database di OpenMSP'
        body = 'In allegato trovi il backup del database.'

        try:
            with pyzipper.AESZipFile(zip_filename, 'w', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(password.encode())  # Impostare la password per la cifratura
                zf.write(db_path, os.path.basename(db_path))

            # Crea il messaggio email
            email = EmailMessage(subject, body, to=[email_address])
            email.attach_file(zip_filename)  # Allegare il file ZIP
            email.send()

        except Exception as e:
            # Qui si potrebbe loggare l'errore se necessario
            print(f"Errore durante il backup: {e}")
        finally:
            # Pulisci il file ZIP dopo l'invio o in caso di errore
            if os.path.exists(zip_filename):
                os.remove(zip_filename)
