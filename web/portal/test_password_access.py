from django.test import TestCase, Client, override_settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core import signing
from .password_access import COOKIE, SALT, fingerprint, AGE
from unittest.mock import patch


@override_settings(DEMO=False, AUTH_MODE='password', ALLOWED_HOSTS=['testserver'],
                   SHARED_PASSWORD_HASH=make_password('test-access'),
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PasswordAccessTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_gate_and_login_logout(self):
        for path in ('/', '/api/sessions/', '/import/', '/request-exports/'):
            self.assertEqual(self.client.get(path, secure=True).status_code, 302)
        self.assertEqual(self.client.post('/login/', {'password': 'wrong'}, secure=True).status_code, 403)
        response = self.client.post('/login/', {'password': 'test-access'}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.cookies[COOKIE]['secure'])
        self.assertTrue(response.cookies[COOKIE]['httponly'])
        self.assertEqual(self.client.get('/', secure=True).status_code, 200)
        self.assertEqual(self.client.get('/import/', secure=True).status_code, 200)
        self.assertEqual(self.client.post('/api/worker/poll/', '{}', content_type='application/json', secure=True).status_code, 403)
        self.client.post('/logout/', secure=True)
        self.assertEqual(self.client.get('/api/sessions/', secure=True).status_code, 302)

    def test_cookie_tampering_expiry_and_rotation(self):
        self.client.cookies[COOKIE] = 'forged'
        self.assertEqual(self.client.get('/', secure=True).status_code, 302)
        import time
        with patch('django.core.signing.time.time', return_value=time.time()-AGE-10):
            self.client.cookies[COOKIE] = signing.dumps(fingerprint(), salt=SALT)
        self.assertEqual(self.client.get('/', secure=True).status_code, 302)
        self.client.cookies[COOKIE] = signing.dumps(fingerprint(), salt=SALT)
        with override_settings(SHARED_PASSWORD_HASH=make_password('replacement')):
            self.assertEqual(self.client.get('/', secure=True).status_code, 302)

    def test_csrf_and_throttle(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/login/', {'password': 'test-access'}, secure=True).status_code, 403)
        for _ in range(10):
            self.client.post('/login/', {'password': 'wrong'}, secure=True)
        self.assertEqual(self.client.post('/login/', {'password': 'test-access'}, secure=True).status_code, 429)
