from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from two_factor.utils import default_device

class Force2FAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.AUTH_2FA:
            return self.get_response(request)

        if request.user.is_authenticated:
            # Escludiamo le pagine necessarie per completare il setup o il login 2FA
            # Aggiungiamo anche il logout per permettere all'utente di uscire
            exempt_urls = [
                reverse('two_factor:setup'),
                reverse('two_factor:login'),
                reverse('two_factor:backup_tokens'),
                reverse('two_factor:profile'),
                reverse('logout'),
            ]
            
            # Aggiungiamo i path statici e media se necessario (solitamente gestiti da altri middleware, ma meglio essere sicuri)
            if any(request.path.startswith(url) for url in exempt_urls) or request.path.startswith(settings.STATIC_URL):
                return self.get_response(request)

            # Se l'utente non ha la 2FA verificata
            if not request.user.is_verified():
                device = default_device(request.user)
                if device:
                    # Ha un dispositivo ma non è verificato (è nella sessione di login ma non ha inserito l'OTP)
                    # Nota: In teoria two_factor gestisce già questo se la sessione non è verificata, 
                    # ma se vogliamo forzarlo ovunque:
                    return redirect('two_factor:login')
                else:
                    # Non ha proprio un dispositivo configurato
                    return redirect('two_factor:setup')

        return self.get_response(request)
