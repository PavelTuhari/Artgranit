"""RO: clientul Ultra B2B — comportamentul la limitarea de ritm (429)."""
import io
import urllib.error
from unittest import mock

from modules.partner import ultra


def _http_error(code, body=b"{}", headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    return urllib.error.HTTPError("https://eshop.ultra.md/api/changes", code, "err",
                                  h, io.BytesIO(body))


def _ok(body=b'{"changes": [], "has_more": false}'):
    r = mock.MagicMock()
    r.read.return_value = body
    r.__enter__.return_value = r
    return r


def test_429_waits_and_retries_then_succeeds(monkeypatch):
    """RO: la 22.09.2026 /changes a picat cu «Too Many Attempts» dupa doua saptamini
    fara sincronizare. Acum: pauza (Retry-After sau crescatoare) si aceeasi cerere din nou."""
    c = ultra.UltraClient("https://eshop.ultra.md/api", "u", "p")
    c._token = "t"
    calls = [_http_error(429, b'{"message":"Too Many Attempts."}', {"Retry-After": "7"}),
             _http_error(429, b'{"message":"Too Many Attempts."}'),
             _ok()]
    dormit = []
    monkeypatch.setattr(ultra.time, "sleep", lambda s: dormit.append(s))
    monkeypatch.setattr(ultra.urllib.request, "urlopen",
                        lambda req, timeout=0: (_ for _ in ()).throw(calls.pop(0))
                        if isinstance(calls[0], Exception) else calls.pop(0))
    r = c._req("GET", "/changes", params={"since": "x"})
    assert r["success"] is True
    assert dormit == [7, ultra.BACKOFF_S[1]]          # Retry-After, apoi pauza a doua din grafic


def test_429_gives_up_after_schedule(monkeypatch):
    """RO: nu asteptam la nesfirsit — dupa toate pauzele din BACKOFF_S se intoarce eroarea."""
    c = ultra.UltraClient("https://eshop.ultra.md/api", "u", "p")
    c._token = "t"
    monkeypatch.setattr(ultra.time, "sleep", lambda s: None)
    monkeypatch.setattr(ultra.urllib.request, "urlopen",
                        lambda req, timeout=0: (_ for _ in ()).throw(_http_error(429, b"limit")))
    r = c._req("GET", "/changes")
    assert r["success"] is False and r["status"] == 429


def test_non_429_errors_are_not_retried(monkeypatch):
    c = ultra.UltraClient("https://eshop.ultra.md/api", "u", "p")
    c._token = "t"
    n = {"k": 0}

    def boom(req, timeout=0):
        n["k"] += 1
        raise _http_error(500, b"server")
    monkeypatch.setattr(ultra.urllib.request, "urlopen", boom)
    r = c._req("GET", "/product")
    assert r["success"] is False and n["k"] == 1
