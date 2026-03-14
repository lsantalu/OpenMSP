from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings

from impostazioni.models import DatiEnte
from impostazioni.models import UtentiParametri
from impostazioni.models import ServiziParametri


def custom_context(request):

    try:
        user_perms = UtentiParametri.objects.get(id=request.user.id)
    except:
        user_perms = None

    dati_comune = DatiEnte.objects.first()
    service_active = ServiziParametri.objects.all().order_by('id')
    utenti = User.objects.all()

    services_dict = {servizio.codice_servizio: servizio for servizio in service_active}

    i_serv = 0
    service_desc = ["" for _ in range(ServiziParametri.objects.count())]
    for servizio in service_active:
        service_desc[i_serv]= (servizio.codice_servizio, servizio.id,servizio.descrizione, servizio.gruppo_id, servizio.attivo)
        i_serv += 1

    # Funzione helper per recuperare lo stato di un servizio in modo sicuro
    def get_service_status(code):
        service = services_dict.get(code)
        return (service.gruppo_id, service.attivo) if service else (None, False)

    descrizioni_eservices = [
        ('tracing_pdnd', 'Tracing PDND', *get_service_status('tracing_pdnd')),
        ('ipa_singolo', 'iPA Singolo', *get_service_status('ipa')),
        ('ipa_massivo', 'iPA Massivo', *get_service_status('ipa')),
        ('inad_singolo', 'INAD Singolo', *get_service_status('inad')),
        ('inad_massivo', 'INAD Massivo', *get_service_status('inad')),
        ('inipec_singolo', 'INI-PEC Singolo', *get_service_status('registro_imprese')),
        ('inipec_massivo', 'INI-PEC Massivo', *get_service_status('registro_imprese')),
        ('anpr_C001', 'ANPR - C001', *get_service_status('anpr_c001')),
        ('anpr_C007', 'ANPR - C007', *get_service_status('anpr_c007')),
        ('anpr_C015', 'ANPR - C015', *get_service_status('anpr_c015')),
        ('anpr_C017', 'ANPR - C017', *get_service_status('anpr_c017')),
        ('anpr_C018', 'ANPR - C018', *get_service_status('anpr_c018')),
        ('anpr_C020', 'ANPR - C020', *get_service_status('anpr_c020')),
        ('anpr_C021', 'ANPR - C021', *get_service_status('anpr_c021')),
        ('anpr_C030', 'ANPR - C030', *get_service_status('anpr_c030')),
        ('inps_isee', 'INPS ISEE Residenti', *get_service_status('inps_isee')),
        ('inps_durc_singolo', 'INPS DURC Singolo', *get_service_status('inps_durc')),
        ('inps_durc_massivo', 'INPS DURC Massivo', *get_service_status('inps_durc')),
        ('registro_imprese', 'Registro imprese', *get_service_status('registro_imprese')),
        ('mit_cude', 'MIT - Dettaglio Cude', *get_service_status('mit_cude')),
        ('mit_veicoli', 'MIT - Lista Veicoli', *get_service_status('mit_veicoli')),
        ('mit_whitelist', 'MIT - Recupera Whitelist', *get_service_status('mit_whitelist')),
        ('mit_targa', 'MIT - Verifica Targa', *get_service_status('mit_targa')),
        ('anis_IFS02_singolo', 'ANIS IFS02 Singolo', *get_service_status('anis_IFS02')),
        ('anis_IFS02_massivo', 'ANIS IFS02 Massivo', *get_service_status('anis_IFS02')),
        ('anis_IFS03_singolo', 'ANIS IFS03 Singolo', *get_service_status('anis_IFS03')),
        ('anis_IFS03_massivo', 'ANIS IFS03 Massivo', *get_service_status('anis_IFS03')),
        ('cassa_forense', 'Consiglio Nazionale Forense', *get_service_status('cassa_forense')),
        ('app_io_verifica_singolo', 'App IO Verifica Singolo', *get_service_status('app_io')),
        ('app_io_verifica_massivo', 'App IO Verifica Massivo', *get_service_status('app_io')),
        ('app_io_singolo', 'App IO Singolo', *get_service_status('app_io')),
        ('app_io_massivo', 'App IO Massivo', *get_service_status('app_io')),
        ('anist_frequenze_singolo', 'ANIST Frequenze Singolo', *get_service_status('anist_frequenze')),
        ('anist_frequenze_massivo', 'ANIST Frequenze Massivo', *get_service_status('anist_frequenze')),
        ('anist_titoli_singolo', 'ANIST Titoli Singolo', *get_service_status('anist_titoli')),
        ('anist_titoli_massivo', 'ANIST Titoli Massivo', *get_service_status('anist_titoli')),
        ('app_io_composer', 'App IO Composer', *get_service_status('app_io')),
        ('app_io_storico_messaggi', 'App IO Storico Messaggi', *get_service_status('app_io')),
    ]
    
    user_has_2fa = False
    if request.user.is_authenticated:
        from two_factor.utils import default_device
        user_has_2fa = default_device(request.user) is not None

    return {
            'AUTH_2FA': settings.AUTH_2FA,
            'user_has_2fa': user_has_2fa,
            'utenti': utenti,
            'user_perms': user_perms,
            'service_active': service_active,
            'services_dict': services_dict,
            'service_desc' : service_desc,
            'descrizioni_eservices': descrizioni_eservices,
            'my_ente': dati_comune.nome,
            'my_cf': dati_comune.cf,
            'my_piva': dati_comune.piva,
            'my_via': dati_comune.via,
            'my_cap': dati_comune.cap,
            'my_citta': dati_comune.citta,
            'my_telefono': dati_comune.telefono,
            'my_mail': dati_comune.mail,
            'my_pec': dati_comune.pec,
            'my_version': dati_comune.versione,
            'my_logo': dati_comune.stemma
            }
