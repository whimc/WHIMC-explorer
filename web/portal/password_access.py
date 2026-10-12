"""Optional shared evaluator access; worker authentication remains separate."""
import hashlib
import hmac
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

COOKIE = 'explorer_access'
SALT = 'explorer.shared-access.v1'
AGE = 8 * 60 * 60


def fingerprint():
    return hashlib.sha256(settings.SHARED_PASSWORD_HASH.encode()).hexdigest()


def authenticated(request):
    try:
        value = signing.loads(request.COOKIES.get(COOKIE, ''), salt=SALT, max_age=AGE)
        return isinstance(value, str) and hmac.compare_digest(value, fingerprint())
    except signing.BadSignature:
        return False


@require_http_methods(['GET', 'POST'])
def login(request):
    if settings.AUTH_MODE != 'password' or settings.DEMO:
        return HttpResponseForbidden('Password access is not enabled.')
    error, status = '', 200
    if request.method == 'POST':
        # Shared file cache spans Passenger processes. Do not trust forwarded IPs.
        key = 'login-' + hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
        attempts = cache.get(key, 0)
        if attempts >= 10:
            error, status = 'Too many attempts. Try again in one minute.', 429
        else:
            cache.set(key, attempts + 1, 60)
            password = request.POST.get('password', '')
            if len(password) <= 256 and check_password(password, settings.SHARED_PASSWORD_HASH):
                cache.delete(key)
                rotate_token(request)
                response = redirect('index')
                response.set_cookie(COOKIE, signing.dumps(fingerprint(), salt=SALT),
                                    max_age=AGE, secure=True, httponly=True,
                                    samesite='Strict', path=settings.URL_PREFIX + '/')
                return response
            error, status = 'Incorrect password.', 403
    return render(request, 'portal/login.html', {'error': error}, status=status)


@require_POST
def logout(request):
    response = redirect('login')
    response.delete_cookie(COOKIE, path=settings.URL_PREFIX + '/', samesite='Strict')
    return response
