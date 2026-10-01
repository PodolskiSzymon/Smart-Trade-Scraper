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
        if path == "/api/v2/catalog/items":
            calls["catalog"] += 1
            items = [{"id": 1, "user": {}}] if calls["catalog"] == 1 else [
                {"id": 1, "user": {}},
                {"id": SOLD_ID, "user": {"id": 170581459}},
                {"id": ACTIVE_ID, "user": {"id": 148344250}, "url": "https://www.vinted.pl/items/9238023547"},
            ]
            return httpx.Response(200, json={"items": items})
        if path == f"/api/v2/items/{ACTIVE_ID}/details/sidebar":
            return httpx.Response(200, json=FIX["sidebar_active"])
        if path == f"/api/v2/items/{SOLD_ID}/details/sidebar":
            return httpx.Response(200, json=FIX["sidebar_sold"])
        if path.endswith("/shipping_details"):
            return httpx.Response(200, json=FIX["shipping_active"])
        if path.startswith("/api/v2/users/"):
            return httpx.Response(200, json={"user": {"country_title": "Litwa", "country_iso_code": "LT"}})
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
