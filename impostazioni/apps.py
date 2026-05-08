from django.apps import AppConfig


class ImpostazioniConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'impostazioni'

    def ready(self):
        from .scheduler import start
        start()