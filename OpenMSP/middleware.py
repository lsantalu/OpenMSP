from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from two_factor.utils import default_device

class LoginRequiredMiddleware:
    """Un solo punto perche' nessun endpoint, presente o futuro, sia raggiungibile in anonimo.
    Le uniche URL pubbliche sono quelle di login/password/admin e il gateway REST (che usa la propria API key)."""

    # NOTE: '/register/' non e' pubblica: il modulo e' raggiungibile solo dalla pagina di
    # amministrazione degli utenti, quindi chi la vede deve gia' avere una sessione.
    # NOTE: '/admin/' resta pubblica perche' l'admin di Django ha il proprio flusso di login
    # (/admin/login/ con ?next=): dirottarlo altrove romperebbe il rimbalzo.
    # La dashboard '/console_openmsp/' NON e' pubblica: elenca i servizi configurati.
    PUBBLICHE = ('/accounts/', '/account/', '/password_reset/', '/reset/', '/logout/',
                 '/admin/', '/pdnd_gateway/')

    def __init__(self, get_response):
        self.get_response = get_response
        # STATIC_URL/MEDIA_URL vanno filtrati: il default di Django per MEDIA_URL e' '/',
        # e startswith('/') lascerebbe passare qualunque path.
        extra = tuple(u for u in (settings.STATIC_URL, settings.MEDIA_URL) if u and u != "/")
        self.esenti = tuple(self.PUBBLICHE) + extra

    def __call__(self, request):
        path = request.path_info or request.path or '/'
        # La root '/' resta pubblica: e' la homepage richiesta dal comportamento originale
        # (LOGIN_REDIRECT_URL = "home"), quindi chi non ha una sessione la vede e poi logga.
        if request.user.is_authenticated or path == '/' or path.startswith(self.esenti):
            return self.get_response(request)
        return redirect(settings.LOGIN_URL)

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
