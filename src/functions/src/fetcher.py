"""Fetch a page and return its body together with a small metadata dict."""
import urllib.request


def _via_requests(url, timeout):
    import requests  # bundled into the deployment archive

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text, getattr(response, "status_code", 200)


def _via_stdlib(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": "scheduled-web-scraper/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace"), response.status


def fetch(url, timeout=10, opener=None):
    """Fetch with an injected opener when supplied, otherwise with urllib.

    The bundled HTTP client is preferred when available; the standard library
    fallback keeps the handler importable in a minimal local environment.
    """
    if opener is not None:
        return opener(url, timeout)
    try:
        return _via_requests(url, timeout)
    except ImportError:
        return _via_stdlib(url, timeout)
