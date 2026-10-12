import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
MODE = os.environ.get("EXPLORER_MODE", "production")
if MODE not in {"production", "demo"}:
    raise ImproperlyConfigured("EXPLORER_MODE must be production or demo")
DEMO = MODE == "demo"
DEBUG = False
SECRET_KEY = os.environ.get("EXPLORER_SECRET_KEY", "local-synthetic-demo-only-never-use-in-production" if DEMO else "")
if not DEMO and len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Set EXPLORER_SECRET_KEY to a generated secret of at least 50 characters")
ALLOWED_HOSTS = [s.strip() for s in os.environ.get("EXPLORER_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]" if DEMO else "").split(",") if s.strip()]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set exact EXPLORER_ALLOWED_HOSTS; wildcards are not allowed")
NETIDS = frozenset(s.strip().lower() for s in os.environ.get("EXPLORER_NETIDS", "").split(",") if s.strip())
IMPORTERS = frozenset(s.strip().lower() for s in os.environ.get("EXPLORER_IMPORTERS", "").split(",") if s.strip())
AUTH_MODE = os.environ.get("EXPLORER_AUTH_MODE", "netid")
SHARED_PASSWORD_HASH = os.environ.get("EXPLORER_SHARED_PASSWORD_HASH", "")
if AUTH_MODE not in {"netid", "password"}:
    raise ImproperlyConfigured("EXPLORER_AUTH_MODE must be netid or password")
if AUTH_MODE == "password":
    hash_file = os.environ.get("EXPLORER_SHARED_PASSWORD_HASH_FILE", "")
    if hash_file:
        path = Path(hash_file)
        if not path.is_absolute() or "public_html" in [part.lower() for part in path.resolve().parts]:
            raise ImproperlyConfigured("Password hash file must be an absolute private path outside public_html")
        try:
            with path.open("r", encoding="utf-8-sig") as stream:
                SHARED_PASSWORD_HASH = stream.read(1025).strip()
        except (OSError, UnicodeError):
            raise ImproperlyConfigured("Cannot read the configured private password hash file") from None
    # Never call settings-dependent hash helpers while this module is importing:
    # they recursively initialize LazySettings with an incomplete app list.
    import re
    if not re.fullmatch(r"pbkdf2_sha256\$[1-9][0-9]*\$[A-Za-z0-9]+\$[A-Za-z0-9+/]{43}=", SHARED_PASSWORD_HASH):
        raise ImproperlyConfigured("Set EXPLORER_SHARED_PASSWORD_HASH to a Django PBKDF2-SHA256 password hash")
if not DEMO and AUTH_MODE == "netid" and (not NETIDS or not IMPORTERS.issubset(NETIDS)):
    raise ImproperlyConfigured("Set EXPLORER_NETIDS; EXPLORER_IMPORTERS must be a subset")
if any(not s.endswith("@illinois.edu") or len(s.split("@")) != 2 for s in NETIDS):
    raise ImproperlyConfigured("Use full Illinois NetID identities, e.g. netid@illinois.edu")
DATA_DIR = Path(os.environ.get("EXPLORER_DATA_DIR", str(BASE_DIR.parent / "private-data"))).resolve()
if "public_html" in [p.lower() for p in DATA_DIR.parts]:
    raise ImproperlyConfigured("EXPLORER_DATA_DIR must be outside public_html")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "explorer.sqlite3", "OPTIONS": {"timeout": 20}}}
ROOT_URLCONF = "explorer_site.urls"
INSTALLED_APPS = ["django.contrib.staticfiles", "portal"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "portal.middleware.EvaluatorAccess", "django.middleware.csrf.CsrfViewMiddleware"]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.template.context_processors.csrf"]}}]
WSGI_APPLICATION = "passenger_wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
URL_PREFIX = os.environ.get("EXPLORER_URL_PREFIX", "").rstrip("/")
if URL_PREFIX and (not URL_PREFIX.startswith("/") or ".." in URL_PREFIX or "//" in URL_PREFIX):
    raise ImproperlyConfigured("EXPLORER_URL_PREFIX must be a path such as /explorer")
FORCE_SCRIPT_NAME = URL_PREFIX or None
STATIC_URL = URL_PREFIX + "/static/"
STATIC_ROOT = Path(os.environ.get("EXPLORER_STATIC_ROOT", str(BASE_DIR / "static-built")))
SECURE_SSL_REDIRECT = not DEMO
SECURE_HSTS_SECONDS = 3600 if not DEMO else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
CSRF_COOKIE_SECURE = not DEMO
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_PATH = URL_PREFIX + "/"
SESSION_COOKIE_SECURE = not DEMO
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1100  # Up to 1000 saved session checkboxes plus labels.
MAX_BUNDLE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_STORED_BUNDLES = 1000

CACHES = {"default": {"BACKEND": "django.core.cache.backends.filebased.FileBasedCache", "LOCATION": str(DATA_DIR / "login-throttle")}}
