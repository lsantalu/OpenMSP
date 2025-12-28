import sqlite3
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.mail import EmailMessage
from django.conf import settings

import pyzipper
import os
import pathlib



def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(delete_old_logs, 'interval', days=1)  # Esegui ogni giorno
    scheduler.add_job(send_db_backup, 'cron', hour=1, minute=0)  # Esegui ogni notte alle 1:00
    scheduler.start()


def delete_old_logs():
    # Usa settings.BASE_DIR per costruire il percorso, garantendo che sia assoluto e corretto
    db_path = str(settings.BASE_DIR / 'db.sqlite3')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365) ### cancella log vecchi un anno

    cursor.execute("""
        DELETE FROM logs
        WHERE timestamp < ?
    """, (one_year_ago,))
        
    conn.commit()
    conn.close()

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
