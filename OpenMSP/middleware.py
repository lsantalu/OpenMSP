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
            exempt_urls = [
                reverse('two_factor:setup'),
                reverse('two_factor:login'),
                reverse('two_factor:backup_tokens'),
                reverse('two_factor:profile'),
                reverse('logout'),
                reverse('login'), 
                '/account/login/', 
                '/account/two_factor/setup/',
            ]
            
            # Se siamo già in una URL esente (usando startswith per coprire i vari step del wizard) o in una URL statica
            current_path = request.path
            if any(current_path.startswith(url) for url in exempt_urls) or current_path.startswith(settings.STATIC_URL):
                return self.get_response(request)

            # Se l'utente non ha la 2FA verificata
            if not request.user.is_verified():
                device = default_device(request.user)
                if device:
                    return redirect('two_factor:login')
                else:
                    return redirect('two_factor:setup')

        return self.get_response(request)
