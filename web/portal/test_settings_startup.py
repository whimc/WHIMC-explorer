"""Exercise actual settings import; override_settings cannot catch recursion."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from django.test import SimpleTestCase
from django.contrib.auth.hashers import make_password


class SettingsStartupTests(SimpleTestCase):
    def test_password_mode_fresh_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, EXPLORER_MODE='production',
                       EXPLORER_AUTH_MODE='password',
                       EXPLORER_SECRET_KEY='startup-test-only-' * 5,
                       EXPLORER_SHARED_PASSWORD_HASH=make_password('startup-test'),
                       EXPLORER_ALLOWED_HOSTS='localhost', EXPLORER_NETIDS='',
                       EXPLORER_IMPORTERS='', EXPLORER_DATA_DIR=folder,
                       DJANGO_SETTINGS_MODULE='explorer_site.settings')
            code = """
import django
django.setup()
from django.conf import settings
from django.core.management import get_commands, call_command
assert 'django.contrib.staticfiles' in settings.INSTALLED_APPS
assert 'portal' in settings.INSTALLED_APPS
assert 'collectstatic' in get_commands()
assert 'portal.middleware.EvaluatorAccess' in settings.MIDDLEWARE
call_command('collectstatic', interactive=False, dry_run=True, verbosity=0)
"""
            result = subprocess.run([sys.executable, '-c', code], env=env,
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

            hash_path = Path(folder) / 'access-hash.txt'
            hash_path.write_text(env['EXPLORER_SHARED_PASSWORD_HASH'], encoding='utf-8')
            env['EXPLORER_SHARED_PASSWORD_HASH_FILE'] = str(hash_path)
            env['EXPLORER_SHARED_PASSWORD_HASH'] = 'altered-environment'
            result = subprocess.run([sys.executable, '-c', code], env=env,
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            hash_path.write_text('invalid', encoding='utf-8')
            result = subprocess.run([sys.executable, '-c', code], env=env,
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
