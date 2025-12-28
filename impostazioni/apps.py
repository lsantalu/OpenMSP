from django.apps import AppConfig
from .scheduler import start


class ImpostazioniConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'impostazioni'

    def ready(self):
        start()