"""Testy na prawdziwych odpowiedziach API z api.docx. Uruchom: python -m pytest sniper/tests"""
import asyncio
import json
from pathlib import Path

import httpx

from sniper.config import ScoutConfig, SmtpConfig
from sniper.dedup import RecentIds
from sniper.extractor import build_offer, inactive_reason
from sniper.notifier import EmailNotifier, build_message
from sniper.scout import Scout
from sniper.session import VintedSession, playwright_proxy

FIX = json.loads(Path(__file__).with_name("fixtures.json").read_text(encoding="utf-8"))
ACTIVE_ID = 9238023547
SOLD_ID = 9272936873


def test_dedup_deque_and_floor():
    seen = RecentIds(maxlen=3)
    assert all(seen.add(i) for i in (1, 2, 3))
    assert not seen.add(2)
    assert seen.add(4)            # wypycha 1
    assert 1 in seen              # poniżej progu -> nadal "stare"
    assert seen.snapshot() == [2, 3, 4]


def test_sold_and_active_status():
    assert inactive_reason(FIX["sidebar_sold"]) == "sold"
    assert inactive_reason(FIX["sidebar_active"]) is None


def test_build_offer_from_sidebar():
    catalog_item = {"id": ACTIVE_ID, "url": "https://www.vinted.pl/items/9238023547-samsung",
                    "user": {"id": 148344250, "login": "skestenyte.ska", "country_title": "Litwa"}}
    offer = build_offer(ACTIVE_ID, FIX["sidebar_active"], FIX["shipping_active"], catalog_item)
    d = offer.to_dict()
    assert d["title"] == "Samsung pro ultimate 512GB"
    assert d["price"] == 261.08 and d["currency"] == "PLN"
    assert d["description"] == "Naujas, nenaudotas."
    assert len(d["photo_urls"]) == 3 and all("/tc/" in u for u in d["photo_urls"])
    assert d["seller"]["name"] == "skestenyte.ska"
    assert d["seller"]["country"] == "Litwa"
    assert d["seller"]["feedback_count"] == 7 and d["seller"]["stars"] == 5.0
    assert d["shipping"]["price"] == 13.27 and not d["shipping"]["free_shipping"]
    assert d["total_price"] == 274.35
    assert d["url"].endswith("9238023547-samsung")
    msg = build_message(offer, "a@onet.pl", "b@onet.pl")
    assert "Samsung pro ultimate 512GB" in msg["Subject"] and "13.27 PLN" in msg["Subject"]
    assert offer.url in msg.get_content()


def test_playwright_proxy_parsing():
    p = playwright_proxy("http://USER:HASLO_country-pl@geo.iproyal.com:12321")
    assert p == {"server": "http://geo.iproyal.com:12321", "username": "USER", "password": "HASLO_country-pl"}


def test_scout_end_to_end(monkeypatch):
    """Katalog -> 401 -> odświeżenie -> detale; sprzedana pominięta, aktywna złapana."""
    calls = {"refresh": 0, "catalog": 0}

    async def fake_tokens(proxy_url=None, wait_ms=0):
        calls["refresh"] += 1
        return ([{"name": "anon_id", "value": "abc", "domain": ".vinted.pl", "path": "/"}],
                {"x-csrf-token": "tok", "x-anon-id": "abc"})

    monkeypatch.setattr("sniper.session.fetch_fresh_tokens", fake_tokens)

    def handler(request):
        if request.headers.get("x-csrf-token") != "tok" or "anon_id=abc" not in request.headers.get("cookie", ""):
            return httpx.Response(401)
        path = request.url.path
        if request.url.host == "api.vinted.pl" and path == "/svc-catalogue/items":
            calls["catalog"] += 1
            items = [{"id": 1, "user": {}}] if calls["catalog"] == 1 else [
                {"id": 1, "user": {}},
                {"id": SOLD_ID, "user": {"id": 170581459}},
                {"id": ACTIVE_ID, "url": "https://www.vinted.pl/items/9238023547",
                 "user": {"id": 148344250, "country_title": "Litwa", "country_iso_code": "LT"}},
            ]
            return httpx.Response(200, json={"items": items})
        if path == f"/api/v2/items/{ACTIVE_ID}/details/sidebar":
            return httpx.Response(200, json=FIX["sidebar_active"])
        if path == f"/api/v2/items/{SOLD_ID}/details/sidebar":
            return httpx.Response(200, json=FIX["sidebar_sold"])
        if path.endswith("/shipping_details"):
            return httpx.Response(200, json=FIX["shipping_active"])
        return httpx.Response(404)

    async def scenario():
        cfg = ScoutConfig(smtp=SmtpConfig(username="", password=""))
        session = VintedSession()
        session.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=session.client.headers)
        scout = Scout(cfg, session, EmailNotifier(cfg.smtp))
        session.client.headers.pop("x-csrf-token", None)

        await scout.poll_catalog()                 # 401 -> refresh -> rozgrzewka (bez alertów)
        assert calls["refresh"] == 1
        await scout.poll_catalog()                 # dwie nowe oferty
        await asyncio.gather(*scout._tasks)
        await session.close()
        return scout

    scout = asyncio.run(scenario())
    assert scout.offers.qsize() == 1
    offer = scout.offers.get_nowait()
    assert offer["id"] == ACTIVE_ID
    assert offer["seller"]["country"] == "Litwa" and offer["seller"]["country_code"] == "LT"


def test_proxy_relay_injects_auth():
    """Przekaźnik dla Chromium dokleja Proxy-Authorization (fix ERR_PROXY_AUTH_UNSUPPORTED)."""
    import base64
    from sniper.proxy_relay import ProxyRelay

    expected = b"Proxy-Authorization: Basic " + base64.b64encode(b"USER:HASLO_country-pl")
    heads = []

    async def upstream(reader, writer):
        heads.append(await reader.readuntil(b"\r\n\r\n"))
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        writer.write(await reader.read(5))   # echo po zestawieniu tunelu
        await writer.drain()
        writer.close()

    async def scenario():
        server = await asyncio.start_server(upstream, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with ProxyRelay(f"http://USER:HASLO_country-pl@127.0.0.1:{port}") as relay:
            host, rport = relay.server.rsplit("/", 1)[1].split(":")
            reader, writer = await asyncio.open_connection(host, int(rport))
            writer.write(b"CONNECT www.vinted.pl:443 HTTP/1.1\r\nHost: www.vinted.pl:443\r\n\r\n")
            await writer.drain()
            status = await reader.readuntil(b"\r\n\r\n")
            writer.write(b"hello")
            await writer.drain()
            echoed = await reader.readexactly(5)
            writer.close()
        server.close()
        return status, echoed

    status, echoed = asyncio.run(scenario())
    assert status.startswith(b"HTTP/1.1 200")
    assert echoed == b"hello"
    assert heads[0].startswith(b"CONNECT www.vinted.pl:443") and expected in heads[0]


def test_iproyal_proxy_from_env(monkeypatch):
    """SNIPER_PROXY_HOST + SNIPER_PROXY_AUTH -> oficjalny słownik proxies IPRoyal."""
    import requests
    from sniper.config import build_proxy_url, requests_proxies

    monkeypatch.setenv("SNIPER_PROXY_HOST", "geo.iproyal.com:12321")
    monkeypatch.setenv("SNIPER_PROXY_AUTH", "LOGIN:HASLO_country-pl")
    monkeypatch.setenv("SNIPER_PROXY_URL", "http://ignored@example:1")
    proxy, proxy_auth = "geo.iproyal.com:12321", "LOGIN:HASLO_country-pl"
    official = {"http": f"http://{proxy_auth}@{proxy}", "https": f"http://{proxy_auth}@{proxy}"}

    assert build_proxy_url() == official["https"]
    assert requests_proxies() == official
    session = requests.Session()
    session.proxies.update(requests_proxies())
    assert session.proxies == official
    assert ScoutConfig().proxy_url == official["https"]

    # requests odczytuje login/hasło dokładnie takie, jak w .env
    from requests.utils import get_auth_from_url
    assert get_auth_from_url(session.proxies["https"]) == ("LOGIN", "HASLO_country-pl")

    # Znaki specjalne w haśle są bezpiecznie kodowane, a requests je odkodowuje.
    monkeypatch.setenv("SNIPER_PROXY_AUTH", "LOGIN:p@ss:word")
    assert get_auth_from_url(build_proxy_url()) == ("LOGIN", "p@ss:word")

    # Fallback na gotowy URL
    monkeypatch.delenv("SNIPER_PROXY_HOST")
    assert build_proxy_url() == "http://ignored@example:1"


def test_require_proxy_blocks_direct_traffic(monkeypatch):
    """Bez proxy w .env Zwiadowca nie może wyjść bezpośrednio."""
    import pytest
    from sniper.config import ProxyNotConfigured, requests_proxies

    for name in ("SNIPER_PROXY_HOST", "SNIPER_PROXY_AUTH", "SNIPER_PROXY_URL", "SNIPER_REQUIRE_PROXY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ProxyNotConfigured):
        requests_proxies()
    monkeypatch.setenv("SNIPER_REQUIRE_PROXY", "false")
    assert requests_proxies() == {}


def test_catalog_request_identical_to_session_management(monkeypatch):
    """Zapytanie do katalogu = 1:1 jak w session_management.py (parametry, kolejność, nagłówki)."""
    import pytest

    sm = pytest.importorskip("session_management")
    from sniper.config import BROWSER_USER_AGENT, CATALOG_HEADERS, get_catalog_params, make_main_loop_referer
    from sniper.scout import catalog_params

    for kwargs in (
        dict(category="karty_pamieci", page=1, order="newest_first"),
        dict(category="elektronika", page=3, order="relevance", search_text="ssd", price_from="10"),
    ):
        ours, theirs = get_catalog_params(**kwargs), sm.get_catalog_params(**kwargs)
        assert list(ours.items()) == list(theirs.items())
    from sniper.config import CATALOG_URL
    assert CATALOG_URL == sm.CATALOG_URL == "https://api.vinted.pl/svc-catalogue/items"
    assert make_main_loop_referer(1) == sm.make_main_loop_referer(1)
    assert make_main_loop_referer(2) == sm.make_main_loop_referer(2)

    # Zwiadowca woła to tak samo jak main_vinted.run_scraper_cycle
    cfg = ScoutConfig(category="karty_pamieci", search_text="", price_from="")
    assert list(catalog_params(cfg).items()) == list(sm.get_catalog_params(category="karty_pamieci", page=1, order="newest_first").items())
    # Kategoria spoza słownika (np. laptopy 3580) idzie wprost jako attribute_ids[catalog]
    assert get_catalog_params(category="3580")["attribute_ids[catalog]"] == "3580"

    # Nagłówki = make_boot_session() (bez dynamicznych tokenów i ciastek z dysku)
    monkeypatch.setattr(sm, "load_vinted_data_from_file", lambda: ({}, {}))
    boot = sm.make_boot_session()
    assert {k.lower(): v for k, v in CATALOG_HEADERS.items()} == {
        k.lower(): v for k, v in boot.headers.items()
        if k.lower() not in ("accept-encoding", "connection")  # domyślne nagłówki requests
    }

    # Request httpx z tymi parametrami ma ten sam query string co requests
    import requests
    params = sm.get_catalog_params(category="karty_pamieci")
    ours_url = httpx.Request("GET", sm.CATALOG_URL, params=params).url
    theirs_url = requests.Request("GET", sm.CATALOG_URL, params=params).prepare().url
    assert str(ours_url) == theirs_url

    # Playwright przedstawia się tak samo jak httpx (cf_clearance/datadome są wiązane z UA)
    assert BROWSER_USER_AGENT == CATALOG_HEADERS["user-agent"]


# Działające zapytanie z przeglądarki (cURL od użytkownika, 2026-10-02) - bez ciastek i tokenów.
CURL_URL = ("https://api.vinted.pl/svc-catalogue/items?page=2&per_page=96&search_text=&price_from=2000"
            "&currency=PLN&order=newest_first&attribute_ids%5Bcatalog%5D=3580&attribute_ids%5Bbrand%5D="
            "&attribute_ids%5Bbrand_collection%5D=&attribute_ids%5Bstatus%5D=")
CURL_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
    "platform": "web",
    "priority": "u=1, i",
    "referer": "https://www.vinted.pl/",
    "sec-ch-ua": '"Chromium";v="154", "Microsoft Edge";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0",
    "x-next-app": "marketplace-web",
}


def test_catalog_request_matches_browser_curl():
    """URL i nagłówki zapytania do katalogu = znak w znak jak w działającym cURL z przeglądarki."""
    import requests
    from sniper.config import CATALOG_HEADERS, CATALOG_ONLY_HEADERS, CATALOG_URL, BASE_HEADERS, get_catalog_params

    params = get_catalog_params(category="3580", page=2, order="newest_first", price_from="2000")
    assert str(httpx.Request("GET", CATALOG_URL, params=params).url) == CURL_URL
    assert requests.Request("GET", CATALOG_URL, params=params).prepare().url == CURL_URL
    assert CATALOG_HEADERS == CURL_HEADERS

    # Zwiadowca: nagłówki klienta + dodatki dla katalogu + Referer = komplet z cURL
    sent = {**BASE_HEADERS, **CATALOG_ONLY_HEADERS, "referer": "https://www.vinted.pl/"}
    assert sent == CURL_HEADERS


def test_scout_sends_curl_headers_to_catalog(monkeypatch):
    """Zwiadowca wysyła do api.vinted.pl dokładnie nagłówki z cURL, a do www.vinted.pl/api/v2 - same-origin."""
    seen = {}

    def handler(request):
        seen[request.url.host] = dict(request.headers)
        if request.url.host == "api.vinted.pl":
            return httpx.Response(200, json={"items": [{"id": 1, "user": {}}]})
        return httpx.Response(200, json={})

    async def scenario():
        session = VintedSession()
        session.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=session.client.headers)
        scout = Scout(ScoutConfig(category="3580", search_text="", price_from=""), session, EmailNotifier(SmtpConfig()))
        await scout.poll_catalog()
        await session.get_json("https://www.vinted.pl/api/v2/items/1/shipping_details", referer="https://www.vinted.pl/items/1")
        await session.close()

    asyncio.run(scenario())
    api = seen["api.vinted.pl"]
    for name, value in CURL_HEADERS.items():
        assert api.get(name) == value, name
    www = seen["www.vinted.pl"]
    assert "origin" not in www and www["sec-fetch-site"] == "same-origin"

