import ipaddress
from django.conf import settings
from django.http import HttpResponseForbidden


class EvaluatorAccess:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .export_queue import WORKER_PATHS, authenticate
        if request.path_info in WORKER_PATHS:
            request.worker_server = authenticate(request)
            if not request.worker_server:
                return HttpResponseForbidden('A valid server credential over HTTPS is required.')
            response = self.get_response(request)
            response['Cache-Control'] = 'no-store'
            return response
        if settings.DEMO:
            try:
                local = ipaddress.ip_address(request.META.get("REMOTE_ADDR", "")).is_loopback
            except ValueError:
                local = False
            if not local:
                return HttpResponseForbidden("Demo mode is only available on loopback.")
            request.evaluator = "local-demo"
            request.can_import = False  # CLI seeds synthetic data; no real uploads in demo mode.
        elif settings.AUTH_MODE == "password":
            from .password_access import authenticated
            from django.shortcuts import redirect
            request.evaluator = "shared-access"
            request.can_import = authenticated(request)
            if not request.can_import and request.path_info not in {"/login/", "/logout/"}:
                response = redirect('login')
                response['Cache-Control'] = 'no-store'
                return response
        else:
            # This is the WSGI server variable set by Apache/mod_shib, NOT an HTTP header.
            identity = request.META.get("REMOTE_USER", "").strip().lower()
            if identity not in settings.NETIDS:
                return HttpResponseForbidden("An authorized Illinois NetID is required.")
            request.evaluator = identity
            request.can_import = identity in settings.IMPORTERS
        response = self.get_response(request)
        response["Cache-Control"] = "private, no-store"
        response["X-Frame-Options"] = "DENY"
        response["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "same-origin"
        return response
