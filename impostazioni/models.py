from django.db import models
from django.contrib.auth.models import User


# NOTE: convertire da sqlite3 a mysql

class Logs(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    utente_id = models.ForeignKey(User, models.DO_NOTHING, db_column='utente_id')
    servizio = models.CharField(max_length=50)
    richiesta = models.CharField(max_length=150, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'logs'


class UtentiParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    utente_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column='utente_id')
    ipa_singolo = models.BooleanField(default=False)
    ipa_massivo = models.BooleanField(default=False)
    inad_singolo = models.BooleanField(default=False)
    inad_massivo = models.BooleanField(default=False)
    inipec_singolo = models.BooleanField(default=False)
    inipec_massivo = models.BooleanField(default=False)
    anpr_C001 = models.BooleanField(default=False)
    anpr_C007 = models.BooleanField(default=False)
    anpr_C015 = models.BooleanField(default=False)
    anpr_C017 = models.BooleanField(default=False)
    anpr_C018 = models.BooleanField(default=False)
    anpr_C020 = models.BooleanField(default=False)
    anpr_C021 = models.BooleanField(default=False)
    anpr_C030 = models.BooleanField(default=False)
    mit_cude = models.BooleanField(default=False)
    mit_veicoli = models.BooleanField(default=False)
    mit_whitelist = models.BooleanField(default=False)
    mit_targa = models.BooleanField(default=False)
    anis_IFS02_singolo = models.BooleanField(default=False)
    anis_IFS02_massivo = models.BooleanField(default=False)
    anis_IFS03_singolo = models.BooleanField(default=False)
    anis_IFS03_massivo = models.BooleanField(default=False)
    cassa_forense = models.BooleanField(default=False)
    registro_imprese = models.BooleanField(default=False)
    inps_isee = models.BooleanField(default=False)
    inps_durc_singolo = models.BooleanField(default=False)
    inps_durc_massivo = models.BooleanField(default=False)
    app_io_verifica_singolo = models.BooleanField(default=False)
    app_io_verifica_massivo = models.BooleanField(default=False)
    app_io_singolo = models.BooleanField(default=False)
    app_io_massivo = models.BooleanField(default=False)
    anist_frequenze_singolo = models.BooleanField(default=False)
    anist_frequenze_massivo = models.BooleanField(default=False)
    anist_titoli_singolo = models.BooleanField(default=False)
    anist_titoli_massivo = models.BooleanField(default=False)
    app_io_composer = models.BooleanField(default=False)
    app_io_storico_messaggi = models.BooleanField(default=False)
    def somma_servizi_attivi(self):
        total_true = sum([getattr(self, field.name) for field in self._meta.fields if isinstance(field, models.BooleanField) and getattr(self, field.name)])
        return total_true

    class Meta:
        managed = False
        db_table = 'utenti_parametri'


class GruppiParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    descrizione = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = 'gruppi_parametri'


class ServiziParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    codice_servizio = models.CharField(max_length=50)
    descrizione = models.CharField(max_length=150)
    gruppo_id = models.ForeignKey(GruppiParametri, models.DO_NOTHING, db_column='gruppo_id')
    attivo = models.BooleanField(default=False)
    url = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = 'servizi_parametri'


class AppIoParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    api_url = models.CharField(max_length=150)
    api_key_master = models.CharField(max_length=32)

    class Meta:
        managed = False
        db_table = 'app_io_parametri'


class AppIoCatalogoArgomenti(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    argomento = models.CharField(blank=True, null=True, max_length=100)

    class Meta:
        managed = False
        db_table = 'app_io_catalogo_argomenti'


class AppIoCatalogoServizi(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    argomento_id = models.ForeignKey(AppIoCatalogoArgomenti, on_delete=models.CASCADE, db_column='argomento_id' )
    servizio = models.CharField(max_length=100)
    codice_catalogo = models.CharField(max_length=8)
    id_servizio = models.CharField(max_length=26)
    chiave_api = models.CharField(max_length=32)


    class Meta:
        managed = False
        db_table = 'app_io_catalogo_servizi'


class AppIoElencoMessaggi(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    utente_id = models.ForeignKey(User, models.DO_NOTHING, db_column='utente_id')
    servizio_id = models.ForeignKey(AppIoCatalogoServizi, on_delete=models.CASCADE, db_column='servizio_id' )
    cf_destinatario = models.CharField(max_length=16)
    titolo = models.CharField(max_length=120)
    messaggio = models.CharField(max_length=10000)
    iuv = models.CharField(max_length=22)
    scadenza = models.CharField(max_length=10)
    mezzo1 = models.CharField(max_length=4)
    testoBottone1 = models.CharField(max_length=100)
    comando1 = models.CharField(max_length=1000)
    mezzo2 = models.CharField(max_length=10)
    testoBottone2 = models.CharField(max_length=100)
    comando2 = models.CharField(max_length=1000)
    esito = models.CharField(max_length=26)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'app_io_storico_messaggi'


class RegistroImpreseParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'registro_imprese_parametri'


class InadParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'inad_parametri'


class InpsDurcParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'inps_durc_parametri'


class InpsIseeParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'inps_isee_parametri'


class IpaParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    auth_id = models.CharField(max_length=6)

    class Meta:
        managed = False
        db_table = 'ipa_parametri'


class AnisServizi(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    servizio = models.CharField(blank=True, null=True, max_length=100)

    class Meta:
        managed = False
        db_table = 'anis_servizi'


class AnisParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    servizio_id = models.ForeignKey(AnisServizi, models.DO_NOTHING, db_column='servizio_id')
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'anis_parametri'


class AnprServizi(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    servizio = models.CharField(blank=True, null=True, max_length=100)

    class Meta:
        managed = False
        db_table = 'anpr_servizi'


class AnprParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    servizio_id = models.ForeignKey(AnprServizi, models.DO_NOTHING, db_column='servizio_id')
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'anpr_parametri'


class CassaForenseParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'cassa_forense_parametri'



class MitServizi(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    servizio = models.CharField(blank=True, null=True, max_length=100)

    class Meta:
        managed = False
        db_table = 'mit_servizi'


class MitParametri(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    servizio_id = models.ForeignKey(MitServizi, models.DO_NOTHING, db_column='servizio_id')
    kid = models.CharField(max_length=42)
    alg = models.CharField(max_length=10)
    typ = models.CharField(max_length=10)
    iss = models.CharField(max_length=36)
    sub = models.CharField(max_length=36)
    aud = models.CharField(max_length=150)
    purposeid = models.CharField(max_length=36)
    audience = models.CharField(max_length=150)
    baseurlauth = models.CharField(max_length=150)
    target = models.CharField(max_length=150)
    clientid = models.CharField(max_length=50)
    private_key = models.CharField(max_length=2500)
    ver_eservice = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'mit_parametri'


class DatiEnte(models.Model):
    id = models.IntegerField(blank=True, primary_key=True)
    nome = models.CharField(max_length=150)
    cf = models.CharField(max_length=11)
    piva = models.CharField(max_length=11)
    via = models.CharField(max_length=50)
    cap = models.CharField(max_length=5)
    citta = models.CharField(max_length=50)
    telefono = models.CharField(max_length=25)
    mail = models.CharField(max_length=60)
    pec  = models.CharField(max_length=60)
    versione = models.CharField(max_length=30)
    stemma = models.TextField()

    class Meta:
        managed = False
        db_table = 'dati_ente'

