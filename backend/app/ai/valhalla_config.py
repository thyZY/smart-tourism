"""Explicitly allowlisted Valhalla origin resolution for this prototype.

The public demo is not a production SLA. Do not follow HTTP redirects to
unapproved hosts. Only the trusted backend chooses the URL, never a browser.
"""
import os
from urllib.parse import urlsplit
from urllib.request import (
    build_opener,
    HTTPHandler,
    HTTPSHandler,
    HTTPRedirectHandler,
    ProxyHandler,
)

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
    """Build the Valhalla-only opener with explicit proxy policy.

    The local machine's configured HTTP(S) proxy has been observed to time out
    for the allowlisted public Valhalla endpoint while a direct HTTPS request
    succeeds. Direct access is therefore the default for this routing client.
    Set VALHALLA_USE_ENV_PROXY=1 to opt back into Python's environment proxy
    settings on networks that require an outbound proxy.
    """
    use_env_proxy = os.getenv("VALHALLA_USE_ENV_PROXY", "").strip().lower() in {
        "1", "true", "yes", "on"
    }
    proxy_handler = ProxyHandler() if use_env_proxy else ProxyHandler({})
    # Disallow redirects: do not allow an allowlisted server to forward requests
    # to unapproved hosts or internal services.
    return build_opener(proxy_handler, HTTPHandler(), HTTPSHandler(), NoRedirect())
