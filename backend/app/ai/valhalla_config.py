"""Explicitly allowlisted Valhalla origin resolution for this prototype.

The public demo is not a production SLA. Do not follow HTTP redirects to
unapproved hosts. Only the trusted backend chooses the URL, never a browser.
"""
import os
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPHandler, HTTPSHandler, HTTPRedirectHandler

PUBLIC_ORIGIN = "https://valhalla1.openstreetmap.de"
PUBLIC_HOSTS = {"valhalla1.openstreetmap.de"}


def valhalla_root():
    configured = os.getenv("VALHALLA_URL", "").strip()
    if not configured:
        configured = PUBLIC_ORIGIN
    try:
        url = urlsplit(configured)
        if url.username or url.password or url.query or url.fragment:
            return None
        if url.scheme == "https" and url.hostname in PUBLIC_HOSTS and url.port in (None, 443):
            if url.path not in ("", "/", "/route"):
                return None
            return PUBLIC_ORIGIN
        if url.scheme == "http" and url.hostname in ("127.0.0.1", "localhost") and url.port:
            if url.path not in ("", "/", "/route"):
                return None
            return f"http://{url.hostname}:{url.port}"
    except ValueError:
        return None
    return None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_opener():
    # Disallow HTTP redirects: prevent an allowlisted server from forwarding
    # a request to untrusted networks, including internal services.
    return build_opener(HTTPHandler(), HTTPSHandler(), NoRedirect())
