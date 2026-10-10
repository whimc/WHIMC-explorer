"""cPanel application startup file; entry point: application."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "explorer_site.settings")
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
