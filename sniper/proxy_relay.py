"""Lokalny przekaźnik proxy dla Playwrighta.

Chromium nie potrafi wysłać loginu/hasła do proxy przy tunelowaniu HTTPS
(błąd net::ERR_PROXY_AUTH_UNSUPPORTED). Dlatego przeglądarka łączy się z
lokalnym proxy bez hasła na 127.0.0.1, a ten przekaźnik dokleja nagłówek
Proxy-Authorization i przekazuje ruch do właściwego proxy (np. IPRoyal).
"""
import asyncio
import base64
import logging
import threading
from contextlib import contextmanager
from urllib.parse import unquote, urlsplit

log = logging.getLogger("sniper.proxy_relay")

_HEADER_LIMIT = 64 * 1024


async def _pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


class ProxyRelay:
    """Użycie: `async with ProxyRelay(url) as relay: ... relay.server ...`"""

    def __init__(self, upstream_url):
        parts = urlsplit(upstream_url)
        self._host = parts.hostname
        self._port = parts.port or 80
        credentials = f"{unquote(parts.username or '')}:{unquote(parts.password or '')}"
        self._auth = b"Proxy-Authorization: Basic " + base64.b64encode(credentials.encode()) + b"\r\n"
        self._server = None
        self._connections = set()

    @property
    def server(self):
        port = self._server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    async def __aenter__(self):
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        for task in list(self._connections):
            task.cancel()
        await asyncio.gather(*self._connections, return_exceptions=True)
        await self._server.wait_closed()

    async def _handle(self, client_reader, client_writer):
        task = asyncio.current_task()
        self._connections.add(task)
        upstream_writer = None
        try:
            head = await client_reader.readuntil(b"\r\n\r\n")
            if len(head) > _HEADER_LIMIT:
                return
            # Usuwamy ewentualny Proxy-Authorization od przeglądarki i wstawiamy własny.
            lines = head.split(b"\r\n")
            kept = [l for l in lines[1:] if l and not l.lower().startswith(b"proxy-authorization:")]
            new_head = lines[0] + b"\r\n" + b"".join(l + b"\r\n" for l in kept) + self._auth + b"\r\n"

            upstream_reader, upstream_writer = await asyncio.open_connection(self._host, self._port)
            upstream_writer.write(new_head)
            await upstream_writer.drain()

            await asyncio.gather(
                _pipe(client_reader, upstream_writer),
                _pipe(upstream_reader, client_writer),
            )
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError, OSError) as exc:
            log.debug("[RELAY] Połączenie przerwane: %r", exc)
        finally:
            for w in (client_writer, upstream_writer):
                if w is not None:
                    try:
                        w.close()
                    except Exception:
                        pass
            self._connections.discard(task)


class _ThreadedRelay:
    """ProxyRelay we własnym wątku z pętlą asyncio - dla kodu synchronicznego (sync_playwright)."""

    def __init__(self, upstream_url):
        self._relay = ProxyRelay(upstream_url)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="proxy-relay", daemon=True)

    def start(self):
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._relay.__aenter__(), self._loop).result(10)
        return self._relay.server

    def stop(self):
        try:
            asyncio.run_coroutine_threadsafe(self._relay.__aexit__(None, None, None), self._loop).result(10)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(5)
            self._loop.close()


@contextmanager
def browser_proxy(proxy_url=None):
    """Synchroniczny kontekst dla Playwrighta: zwraca słownik `proxy=` dla chromium.launch().

        with browser_proxy() as proxy:
            browser = p.chromium.launch(headless=False, proxy=proxy)

    Proxy brane z sniper/.env (require_proxy_url). Gdy ma login/hasło, przeglądarka
    dostaje lokalny przekaźnik 127.0.0.1, który dokleja Proxy-Authorization.
    """
    if proxy_url is None:
        from .config import require_proxy_url

        proxy_url = require_proxy_url()
    if not proxy_url:
        yield None
        return
    parts = urlsplit(proxy_url)
    if not (parts.username or parts.password):
        yield {"server": proxy_url}
        return
    relay = _ThreadedRelay(proxy_url)
    server = relay.start()
    try:
        yield {"server": server}
    finally:
        relay.stop()
