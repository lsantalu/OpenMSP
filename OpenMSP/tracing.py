from django.shortcuts import render
from impostazioni.models import TracingParametri
from .utils import salva_log

def impostazioni_tracing(request):
    if request.method == 'POST':
        kid = request.POST.get('kid')
        alg = request.POST.get('alg')
        typ = request.POST.get('typ')
        iss = request.POST.get('iss')
        sub = request.POST.get('sub')
        aud = request.POST.get('aud')
        purposeid = request.POST.get('purposeid')
        audience = request.POST.get('audience')
        baseurlauth = request.POST.get('baseurlauth')
        target = request.POST.get('target')
        clientid = request.POST.get('clientid')
        private_key = request.POST.get('private_key')
        ver_eservice = request.POST.get('ver_eservice')

        dati = TracingParametri(1, kid, alg, typ, iss, sub, aud, purposeid, audience, baseurlauth, target, clientid, private_key, ver_eservice)
        dati.save()
        salva_log(request.user, "Impostazioni Tracing", "modifica parametri")
        
    parametri_tracing = TracingParametri.objects.all()

    return render(request, 'impostazioni_tracing.html', {'parametri_tracing': parametri_tracing})
