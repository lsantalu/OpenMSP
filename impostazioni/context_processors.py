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
    service_active = ServiziParametri.objects.all()
    utenti = User.objects.all()

    i_serv=0
    service_desc = ["" for _ in range(ServiziParametri.objects.count())]
    for servizio in service_active:
        service_desc[i_serv]= (servizio.codice_servizio, servizio.id,servizio.descrizione, servizio.gruppo_id, servizio.attivo)
        i_serv += 1

    descrizioni_eservices = [ ##per automatizzare diritti
        ('ipa_singolo', 'iPA Singolo', service_desc[0][3], service_desc[0][4]),
        ('ipa_massivo', 'iPA Massivo', service_desc[0][3], service_desc[0][4]),
        ('inad_singolo', 'INAD Singolo', service_desc[1][3], service_desc[1][4]),
        ('inad_massivo', 'INAD Massivo', service_desc[1][3], service_desc[1][4]),
        ('inipec_singolo', 'INI-PEC Singolo', service_desc[10][3], service_desc[10][4]),
        ('inipec_massivo', 'INI-PEC Massivo', service_desc[10][3], service_desc[10][4]),
        ('anpr_C001', 'ANPR - C001', service_desc[2][3], service_desc[2][4]),
        ('anpr_C007', 'ANPR - C007', service_desc[3][3], service_desc[3][4]),
        ('anpr_C015', 'ANPR - C015', service_desc[4][3], service_desc[4][4]),
        ('anpr_C017', 'ANPR - C017', service_desc[5][3], service_desc[5][4]),
        ('anpr_C018', 'ANPR - C018', service_desc[6][3], service_desc[6][4]),
        ('anpr_C020', 'ANPR - C020', service_desc[7][3], service_desc[7][4]),
        ('anpr_C021', 'ANPR - C021', service_desc[8][3], service_desc[8][4]),
        ('anpr_C030', 'ANPR - C030', service_desc[9][3], service_desc[9][4]),
        ('inps_isee', 'INPS ISEE Residenti', service_desc[18][3], service_desc[18][4]),
        ('inps_durc_singolo', 'INPS DURC Singolo', service_desc[19][3], service_desc[19][4]),
        ('inps_durc_massivo', 'INPS DURC Massivo', service_desc[19][3], service_desc[19][4]),
        ('registro_imprese', 'Registro imprese', service_desc[10][3], service_desc[10][4]),
        ('mit_cude', 'MIT - Dettaglio Cude', service_desc[11][3], service_desc[11][4]),
        ('mit_veicoli', 'MIT - Lista Veicoli', service_desc[12][3], service_desc[12][4]),
        ('mit_whitelist', 'MIT - Recupera Whitelist', service_desc[13][3], service_desc[13][4]),
        ('mit_targa', 'MIT - Verifica Targa', service_desc[14][3], service_desc[14][4]),
        ('anis_IFS02_singolo', 'ANIS IFS02 Singolo', service_desc[15][3], service_desc[15][4]),
        ('anis_IFS02_massivo', 'ANIS IFS02 Massivo', service_desc[15][3], service_desc[15][4]),
        ('anis_IFS03_singolo', 'ANIS IFS03 Singolo', service_desc[16][3], service_desc[16][4]),
        ('anis_IFS03_massivo', 'ANIS IFS03 Massivo', service_desc[16][3], service_desc[16][4]),
        ('cassa_forense', 'Consiglio Nazionale Forense', service_desc[17][3], service_desc[17][4]),
        ('app_io_verifica_singolo', 'App IO Verifica Singolo', service_desc[20][3], service_desc[20][4]),
        ('app_io_verifica_massivo', 'App IO Verifica Massivo', service_desc[20][3], service_desc[20][4]),
        ('app_io_singolo', 'App IO Singolo', service_desc[20][3], service_desc[20][4]),
        ('app_io_massivo', 'App IO Massivo', service_desc[20][3], service_desc[20][4]),
        ('anist_frequenze_singolo', 'ANIST Frequenze Singolo', service_desc[21][3], service_desc[21][4]),
        ('anist_frequenze_massivo', 'ANIST Frequenze Massivo', service_desc[21][3], service_desc[21][4]),
        ('anist_titoli_singolo', 'ANIST Titoli Singolo', service_desc[22][3], service_desc[22][4]),
        ('anist_titoli_massivo', 'ANIST Titoli Massivo', service_desc[22][3], service_desc[22][4]),
        ('app_io_composer', 'App IO Composer', service_desc[20][3], service_desc[20][4]),
        ('app_io_storico_messaggi', 'App IO Storico Messaggi', service_desc[20][3], service_desc[20][4]),
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
