"""Offline checks for the fixed Valhalla demo allowlist and proxy policy."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.ai.valhalla_config import PUBLIC_ORIGIN, valhalla_root, request_opener


class ValhallaConfigTests(unittest.TestCase):
    def test_public_demo_default_and_explicit_public_route(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(valhalla_root(), PUBLIC_ORIGIN)
        with patch.dict(os.environ, {"VALHALLA_URL": PUBLIC_ORIGIN + "/route"}):
            self.assertEqual(valhalla_root(), PUBLIC_ORIGIN)

    def test_loopback_and_rejected_origins(self):
        for value, expected in (
            ("http://127.0.0.1:8002", "http://127.0.0.1:8002"),
            ("http://localhost:8002/route", "http://localhost:8002"),
            ("https://evil.example/route", None),
            ("http://valhalla1.openstreetmap.de", None),
            ("https://valhalla1.openstreetmap.de.evil.example", None),
            ("https://valhalla1.openstreetmap.de:444", None),
            ("http://127.0.0.1:8002@evil.example/route", None),
            ("http://127.0.0.1:8002/evil", None),
            ("http://localhost:8002/route?url=http://169.254.169.254", None),
        ):
            with self.subTest(value=value), patch.dict(os.environ, {"VALHALLA_URL": value}):
                self.assertEqual(valhalla_root(), expected)

    def test_environment_proxy_is_bypassed_by_default(self):
        with patch.dict(os.environ, {
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "http://127.0.0.1:7890",
            "VALHALLA_USE_ENV_PROXY": "",
        }):
            opener = request_opener()
        proxy_handler = next(
            h for h in opener.handlers if isinstance(h, ProxyHandler)
        )
        self.assertEqual(proxy_handler.proxies, {})

    def test_environment_proxy_can_be_enabled_explicitly(self):
        with patch.dict(os.environ, {
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "http://127.0.0.1:7890",
            "VALHALLA_USE_ENV_PROXY": "1",
        }):
            opener = request_opener()
        proxy_handler = next(
            h for h in opener.handlers if isinstance(h, ProxyHandler)
        )
        self.assertEqual(proxy_handler.proxies.get("https"), "http://127.0.0.1:7890")

    def test_redirects_are_not_followed(self):
        opener = request_opener()
        request = Request("https://valhalla1.openstreetmap.de/route")
        redirect = next(h for h in opener.handlers if type(h).__name__ == "NoRedirect")
        self.assertIsNone(redirect.redirect_request(
            request, None, 302, "redirect", {}, "http://127.0.0.1/admin"))


if __name__ == "__main__":
    unittest.main()
