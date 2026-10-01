"""Zarządzanie sesją (Anty-Ban): httpx.AsyncClient za proxy + odświeżanie tokenów przez Playwright.

Ewolucja cookies_management.py / session_management.py: zamiast requests i
sync_playwright mamy w pełni asynchroniczny klient i async API Playwrighta.
"""
import asyncio
import logging
from urllib.parse import unquote, urlsplit

import httpx

from .config import BASE_HEADERS, BASE_URL, USER_AGENT

log = logging.getLogger("sniper.session")

TOKEN_HEADERS = ("x-csrf-token", "x-anon-id")
AUTH_ERRORS = (401, 403)


class SessionExpired(Exception):
    """Vinted odrzucił żądanie (401/403) nawet po odświeżeniu sesji."""


class RateLimited(Exception):
    """Vinted zwrócił 429."""


def playwright_proxy(proxy_url):
    """Zamienia http://USER:PASS@host:port na słownik proxy Playwrighta."""
    if not proxy_url:
        return None
    parts = urlsplit(proxy_url)
    proxy = {"server": f"{parts.scheme}://{parts.hostname}:{parts.port}"}
    if parts.username:
        proxy["username"] = unquote(parts.username)
    if parts.password:
        proxy["password"] = unquote(parts.password)
    return proxy


async def fetch_fresh_tokens(proxy_url=None, wait_ms=15000):
    """Odpala headless Chromium, wchodzi na Vinted i przechwytuje ciastka + nagłówki.

    Zwraca (lista_ciastek_playwrighta, {"x-csrf-token": ..., "x-anon-id": ...}).
    """
    from playwright.async_api import async_playwright

    captured = {}
    api_seen = asyncio.Event()

    def on_request(request):
        if "/api/v2/" not in request.url:
            return
        headers = request.headers
        for name in TOKEN_HEADERS:
            if headers.get(name):
                captured[name] = headers[name]
        if "x-csrf-token" in captured:
            api_seen.set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy=playwright_proxy(proxy_url))
        try:
            context = await browser.new_context(user_agent=USER_AGENT, locale="pl-PL")
            page = await context.new_page()
            page.on("request", on_request)

            log.info("[AUTH] Playwright (headless) wchodzi na Vinted po świeże tokeny...")
            await page.goto(f"{BASE_URL}/catalog", wait_until="domcontentloaded", timeout=wait_ms * 2)

            try:
                await asyncio.wait_for(api_seen.wait(), timeout=wait_ms / 1000)
            except asyncio.TimeoutError:
                log.warning("[AUTH] Nie złapano żądania API z tokenem - próbuję odczytać go ze strony.")

            if "x-csrf-token" not in captured:
                token = await page.evaluate(
                    "() => document.querySelector('meta[name=\"csrf-token\"]')?.content || null"
                )
                if token:
                    captured["x-csrf-token"] = token

            cookies = await context.cookies()
        finally:
            await browser.close()

    if "x-anon-id" not in captured:
        anon = next((c["value"] for c in cookies if c["name"] == "anon_id"), None)
        if anon:
            captured["x-anon-id"] = anon

    log.info(
        "[AUTH] Zdobyto %d ciastek, nagłówki: %s",
        len(cookies), ", ".join(sorted(captured)) or "brak",
    )
    return cookies, captured


class VintedSession:
    """Globalna sesja httpx. Przy 401/403 wstrzymuje wszystkie żądania i odświeża tokeny.

    Każde żądanie czeka na `_ready`. Odświeżanie czyści flagę, więc reszta
    współbieżnych zadań grzecznie stoi, aż Playwright skończy. Licznik
    `_generation` sprawia, że gdy kilka zadań dostanie 401 naraz, przeglądarka
    odpala się tylko raz.
    """

    def __init__(self, proxy_url=None, browser_use_proxy=True, timeout=10.0, browser_wait_ms=15000):
        self._proxy_url = proxy_url or None
        self._browser_proxy = self._proxy_url if browser_use_proxy else None
        self._browser_wait_ms = browser_wait_ms
        self._ready = asyncio.Event()
        self._ready.set()
        self._lock = asyncio.Lock()
        self._generation = 0
        self.client = httpx.AsyncClient(
            proxy=self._proxy_url,
            headers=BASE_HEADERS,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            http2=False,
        )

    async def close(self):
        await self.client.aclose()

    async def refresh(self, seen_generation=None):
        """Odświeża ciastka i tokeny. Pomija, jeśli ktoś inny już to zrobił w międzyczasie."""
        async with self._lock:
            if seen_generation is not None and seen_generation != self._generation:
                return
            self._ready.clear()
            try:
                cookies, tokens = await fetch_fresh_tokens(self._browser_proxy, self._browser_wait_ms)
                self.client.cookies.clear()
                for c in cookies:
                    self.client.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
                for name in TOKEN_HEADERS:
                    self.client.headers.pop(name, None)
                self.client.headers.update(tokens)
                self._generation += 1
                log.info("[AUTH] Sesja httpx zaktualizowana (generacja %d).", self._generation)
            finally:
                self._ready.set()

    async def get_json(self, url, params=None, referer=None):
        """GET z automatycznym odświeżeniem sesji przy 401/403 (jedna ponowna próba)."""
        headers = {"referer": referer} if referer else None
        for attempt in range(2):
            await self._ready.wait()
            generation = self._generation
            response = await self.client.get(url, params=params, headers=headers)

            if response.status_code in AUTH_ERRORS:
                if attempt == 0:
                    log.warning("[AUTH] %s dla %s - wstrzymuję HTTP i odświeżam sesję.", response.status_code, url)
                    await self.refresh(seen_generation=generation)
                    continue
                raise SessionExpired(f"{response.status_code} po odświeżeniu sesji: {url}")
            if response.status_code == 429:
                raise RateLimited(url)
            response.raise_for_status()
            return response.json()
