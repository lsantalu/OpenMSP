# django_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic.base import TemplateView

from .views import profilo_utente
from .views import logout
from .views import pdnd_gateway_service
from .views import CustomPasswordResetView

from .ipa import ipa_singola
from .ipa import ipa_massiva
from .ipa import ipa_export_excel
from .ipa import impostazioni_ipa

from .cassa_forense import cassa_forense
from .cassa_forense import impostazioni_cassa_forense

from .inad import inad_singola
from .inad import inad_massiva
from .inad import inad_export_excel
from .inad import impostazioni_inad

from .app_io import app_io_verifica_utente
from .app_io import app_io_verifica_massivo
from .app_io import app_io_verifica_massivo_export_excel

from .app_io import app_io_singolo
from .app_io import app_io_massivo
from .app_io import app_io_massivo_export_excel

from .app_io import app_io_composer
from .app_io import app_io_composer_conferma
from .app_io import app_io_composer_esito
from .app_io import app_io_composer_export_excel

from .app_io import app_io_storico_messaggi
from .app_io import app_io_storico_pagina_export_excel
from .app_io import app_io_storico_full_export_excel

from .app_io import impostazioni_app_io
from .app_io import impostazioni_app_io_2

from .verifica_cf import verifica_cf_massivo
from .verifica_cf import verifica_cf_export_excel
from .verifica_cf import verifica_cf_aziende_massivo
from .verifica_cf import verifica_cf_aziende_export_excel

from .registro_imprese import inipec_singola
from .registro_imprese import inipec_massiva
from .registro_imprese import inipec_export_excel
from .registro_imprese import impostazioni_registro_imprese
from .registro_imprese import registro_imprese

from .anpr import anpr_notifica
from .anpr import anpr_generalita
from .anpr import anpr_matrimonio
from .anpr import anpr_cittadinanza
from .anpr import anpr_residenza
from .anpr import anpr_stato_famiglia
from .anpr import impostazioni_anpr

from .inps import inps_isee
from .inps import inps_durc_singolo
from .inps import inps_durc_massivo
from .inps import impostazioni_inps_isee
from .inps import impostazioni_inps_durc

from .mit import mit_dettaglio_cude
from .mit import mit_lista_veicoli_cude
from .mit import mit_verifica_targa_cude
from .mit import mit_whitelist
from .mit import impostazioni_mit

from .anis import anis_iscrizioni_singola
from .anis import anis_iscrizioni_massiva
from .anis import anis_iscrizioni_export_excel
from .anis import anis_iscrizioni_export_csv
from .anis import anis_titoli_singola
from .anis import anis_titoli_massiva
from .anis import anis_titoli_export_excel
from .anis import anist_frequenze_singola
from .anis import anist_frequenze_massiva
from .anis import anist_frequenze_export_excel
from .anis import anist_frequenze_export_csv
from .anis import anist_titoli_singola
from .anis import anist_titoli_massiva
from .anis import anist_titoli_export_excel
from .anis import anist_titoli_export_csv
from .anis import impostazioni_anis

from .impostazioni import impostazioni_servizi, impostazioni_servizi_toggle
from .impostazioni import impostazioni_utenti
from .impostazioni import impostazioni_parametri
from .impostazioni import impostazioni_utenti_2
from .impostazioni import impostazioni_upload_stemma
from .impostazioni import impostazioni_clone_user

from .views import register
from .views import debug_openmsp


urlpatterns = [
    path("console_openmsp/", admin.site.urls),
    path('register/', register, name='register'),
    path('clone_user/', impostazioni_clone_user, name='clone_user'),
    path("accounts/", include("django.contrib.auth.urls")),
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    ##path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    path('pdnd_gateway/', pdnd_gateway_service, name='pdnd_gateway'),

    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path('logout/', logout, name='logout'),
    path("profilo_utente/", profilo_utente, name="profilo_utente"),

    path("ipa_singola/", ipa_singola, name="ipa_singola"),
    path("ipa_massiva/", ipa_massiva, name="ipa_massiva"),
    path('ipa_export_excel/', ipa_export_excel, name='ipa_export_excel'),

    path("inad_singola/", inad_singola, name="inad_singola"),
    path("inad_massiva/", inad_massiva, name="inad_massiva"),
    path('inad_export_excel/', inad_export_excel, name='inad_export_excel'),

    path("inipec_singola/", inipec_singola, name="inipec_singola"),
    path("inipec_massiva/", inipec_massiva, name="inipec_massiva"),
    path('inipec_export_excel/', inipec_export_excel, name='inipec_export_excel'),

    path("verifica_cf/", verifica_cf_massivo, name="verifica_cf"),
    path("verifica_cf_export_excel/", verifica_cf_export_excel, name="verifica_cf_export_excel"),

    path("verifica_cf_aziende/", verifica_cf_aziende_massivo, name="verifica_cf_aziende"),
    path("verifica_cf_aziende_export_excel/", verifica_cf_aziende_export_excel, name="verifica_cf_aziende_export_excel"),

    path("anpr_notifica/", anpr_notifica, name="anpr_notifica"),
    path("anpr_generalita/", anpr_generalita, name="anpr_generalita"),
    path("anpr_matrimonio/", anpr_matrimonio, name="anpr_matrimonio"),
    path("anpr_cittadinanza/", anpr_cittadinanza, name="anpr_cittadinanza"),
    path("anpr_residenza/", anpr_residenza, name="anpr_residenza"),
    path("anpr_stato_famiglia/", anpr_stato_famiglia, name="anpr_stato_famiglia"),

    path("inps_isee/", inps_isee, name="inps_isee"),
    path("inps_durc_singolo/", inps_durc_singolo, name="inps_durc_singolo"),
    path("inps_durc_massivo/", inps_durc_massivo, name="inps_durc_massivo"),

    path("mit_whitelist/", mit_whitelist, name="mit_whitelist"),
    path("mit_dettaglio_cude/", mit_dettaglio_cude, name="mit_dettaglio_cude"),
    path("mit_lista_veicoli_cude/", mit_lista_veicoli_cude, name="mit_lista_veicoli_cude"),
    path("mit_verifica_targa_cude/", mit_verifica_targa_cude, name="mit_verifica_targa_cude"),

    path("cassa_forense/", cassa_forense, name="cassa_forense"),
    path("registro_imprese/", registro_imprese, name="registro_imprese"),

    path("anis_iscrizioni_singola/", anis_iscrizioni_singola, name="anis_iscrizioni_singola"),
    path("anis_iscrizioni_massiva/", anis_iscrizioni_massiva, name="anis_iscrizioni_massiva"),
    path("anis_iscrizioni_export_excel/", anis_iscrizioni_export_excel, name="anis_iscrizioni_export_excel"),
    path("anis_iscrizioni_export_csv/", anis_iscrizioni_export_csv, name="anis_iscrizioni_export_csv"),
    path("anis_titoli_singola/", anis_titoli_singola, name="anis_titoli_singola"),
    path("anis_titoli_massiva/", anis_titoli_massiva, name="anis_titoli_massiva"),
    path("anis_titoli_export_excel/", anis_titoli_export_excel, name="anis_titoli_export_excel"),
    path("anist_frequenze_singola/", anist_frequenze_singola, name="anist_frequenze_singola"),
    path("anist_frequenze_massiva/", anist_frequenze_massiva, name="anist_frequenze_massiva"),
    path("anist_frequenze_export_excel/", anist_frequenze_export_excel, name="anist_frequenze_export_excel"),
    path("anist_frequenze_export_csv/", anist_frequenze_export_csv, name="anist_frequenze_export_csv"),
    path("anist_titoli_singola/", anist_titoli_singola, name="anist_titoli_singola"),
    path("anist_titoli_massiva/", anist_titoli_massiva, name="anist_titoli_massiva"),
    path("anist_titoli_export_excel/", anist_titoli_export_excel, name="anist_titoli_export_excel"),
    path("anist_titoli_export_csv/", anist_titoli_export_csv, name="anist_titoli_export_csv"),


    path("app_io_verifica_utente/", app_io_verifica_utente, name="app_io_verifica_utente"),
    path("app_io_verifica_massivo/", app_io_verifica_massivo, name="app_io_verifica_massivo"),
    path("app_io_verifica_massivo_export_excel/", app_io_verifica_massivo_export_excel, name="app_io_verifica_massivo_export_excel"),

    path("app_io_singolo/", app_io_singolo, name="app_io_singolo"),
    path("app_io_singolo_conferma/", app_io_singolo, name="app_io_singolo_conferma"),
    path("app_io_singolo_conferma_prev/", app_io_singolo, name="app_io_singolo_conferma_prev"),
    path("app_io_massivo/", app_io_massivo, name="app_io_massivo"),
    path("app_io_massivo_export_excel/", app_io_massivo_export_excel, name="app_io_massivo_export_excel"),

    path("app_io_composer/", app_io_composer, name="app_io_composer"),
    path("app_io_composer_conferma/", app_io_composer_conferma, name="app_io_composer_conferma"),
    path("app_io_composer_esito/", app_io_composer_esito, name="app_io_composer_esito"),
    path("app_io_composer_export_excel/", app_io_composer_export_excel, name="app_io_composer_export_excel"),

    path("app_io_storico_messaggi/", app_io_storico_messaggi, name="app_io_storico_messaggi"),
    path("app_io_storico_pagina_export_excel/", app_io_storico_pagina_export_excel, name="app_io_storico_pagina_export_excel"),
    path("app_io_storico_full_export_excel/", app_io_storico_full_export_excel, name="app_io_storico_full_export_excel"),

    path("impostazioni_utenti/", impostazioni_utenti, name="impostazioni_utenti"),
    path("impostazioni_utenti_2/", impostazioni_utenti_2, name="impostazioni_utenti_2"),
    path("impostazioni_servizi/", impostazioni_servizi, name="impostazioni_servizi"),
    path("impostazioni_servizi_toggle/", impostazioni_servizi_toggle, name="impostazioni_servizi_toggle"),
    path("impostazioni_inad/", impostazioni_inad, name="impostazioni_inad"),
    path("impostazioni_ipa/", impostazioni_ipa, name="impostazioni_ipa"),
    path("impostazioni_registro_imprese/", impostazioni_registro_imprese, name="impostazioni_registro_imprese"),
    path("impostazioni_anpr/", impostazioni_anpr, name="impostazioni_anpr"),
    path("impostazioni_inps_isee/", impostazioni_inps_isee, name="impostazioni_inps_isee"),
    path("impostazioni_inps_durc/", impostazioni_inps_durc, name="impostazioni_inps_durc"),
    path("impostazioni_mit/", impostazioni_mit, name="impostazioni_mit"),
    path("impostazioni_cassa_forense/", impostazioni_cassa_forense, name="impostazioni_cassa_forense"),
    path("impostazioni_anis/", impostazioni_anis, name="impostazioni_anis"),
    path("impostazioni_app_io/", impostazioni_app_io, name="impostazioni_app_io"),
    path("impostazioni_app_io_2/", impostazioni_app_io_2, name="impostazioni_app_io_2"),
    path("impostazioni_parametri/", impostazioni_parametri, name="impostazioni_parametri"),
    path('impostazioni_upload_stemma/', impostazioni_upload_stemma, name='impostazioni_upload_stemma'),
    path('debug_openmsp/', debug_openmsp, name='debug_openmsp'),
]
