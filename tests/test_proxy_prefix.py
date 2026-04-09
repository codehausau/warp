import os
import unittest
from unittest import mock

import werkzeug

from warp import create_app


class ProxyPrefixTests(unittest.TestCase):

    def setUp(self):
        self.env_patcher = mock.patch.dict(
            os.environ,
            {
                "WARP_SECRET_KEY": "test-secret",
                "WARP_DATABASE": "sqlite:///:memory:",
            },
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def _create_client(self, use_proxy_fix):
        env = {"WARP_USE_PROXY_FIX": "true" if use_proxy_fix else "false"}

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch("warp.db.init"), \
             mock.patch("warp.admin_cli.init"), \
             mock.patch.object(werkzeug, "__version__", "3", create=True):
            app = create_app()
            app.testing = True
            return app.test_client()

    def test_login_page_uses_forwarded_prefix_in_generated_urls(self):
        client = self._create_client(use_proxy_fix=True)

        response = client.get(
            "/login",
            headers={"X-Forwarded-Prefix": "/warp"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('action="/warp/login"', body)
        self.assertIn('/warp/static/images/logo.png', body)
        self.assertIn('/warp/static/dist/', body)

    def test_session_redirect_uses_forwarded_prefix(self):
        client = self._create_client(use_proxy_fix=True)

        response = client.get(
            "/",
            headers={"X-Forwarded-Prefix": "/warp"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/warp/login")

    def test_session_redirect_stays_root_relative_without_proxy_fix(self):
        client = self._create_client(use_proxy_fix=False)

        response = client.get(
            "/",
            headers={"X-Forwarded-Prefix": "/warp"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")


if __name__ == "__main__":
    unittest.main()
