"""Zwiadowca (Scout) - nieskończona, asynchroniczna pętla skanująca katalog Vinted.

Ewolucja main_vinted.py:
  * requests -> httpx.AsyncClient za rotacyjnym proxy,
  * PostgreSQL -> deque w RAM (RecentIds),
  * zero pobierania zdjęć na dysk - tylko URL-e,
  * weryfikacja item_closing_action (sold -> ignoruj) i koszt wysyłki,
  * alert e-mail w tle (aiosmtplib).
"""
import asyncio
import json
import logging
import random
import time

import httpx

from .config import CATALOG_ONLY_HEADERS, CATALOG_URL, SHIPPING_URL, SIDEBAR_URL, ScoutConfig, get_catalog_params
from .dedup import RecentIds
from .extractor import build_offer, inactive_reason, item_url, unwrap_sidebar
from .notifier import EmailNotifier
from .session import RateLimited, SessionExpired, VintedSession

log = logging.getLogger("sniper.scout")


def catalog_params(cfg):
    """Strona 1, najnowsze - parametry 1:1 z działającego zapytania do svc-catalogue (patrz config.get_catalog_params)."""
    return get_catalog_params(
        category=cfg.category,
        page=1,
        order='newest_first',
        search_text=cfg.search_text,
        price_from=cfg.price_from,
    )


class Scout:
    def __init__(self, cfg: ScoutConfig, session: VintedSession, notifier: EmailNotifier):
        self.cfg = cfg
        self.session = session
        self.notifier = notifier
        self.seen = RecentIds(cfg.dedup_size)
        # Kolejka "złapanych" ofert dla przyszłego modułu AI (słowniki z Offer.to_dict()).
        self.offers = asyncio.Queue(maxsize=200)
        self._detail_slots = asyncio.Semaphore(cfg.max_concurrent_details)
        self._tasks = set()
        self._first_batch = cfg.skip_initial_batch
        self._stats = {"polls": 0, "errors": 0, "new": 0, "caught": 0, "last_size": 0, "newest_id": None}
        self._last_heartbeat = time.monotonic()

    # ------------------------------------------------------------------ katalog
    async def poll_catalog(self):
        data = await self.session.get_json(
            CATALOG_URL, params=catalog_params(self.cfg),
            referer="https://www.vinted.pl/", extra_headers=CATALOG_ONLY_HEADERS,  # jak w cURL z przeglądarki
        )
        items = data.get("items") or []
        self._stats["polls"] += 1
        self._stats["last_size"] = len(items)
        if items:
            self._stats["newest_id"] = max(it["id"] for it in items)
        if not items:
            log.warning("[SCOUT] Pusty katalog (klucze odpowiedzi: %s) - możliwy soft-ban. Odświeżam sesję.",
                        ", ".join(data) if isinstance(data, dict) else type(data).__name__)
            await self.session.refresh()
            return

        # Rosnąco po ID, żeby RecentIds wypychał najstarsze oferty jako pierwsze.
        fresh = [it for it in sorted(items, key=lambda it: it["id"]) if self.seen.add(it["id"])]

        if self._first_batch:
            self._first_batch = False
            log.info("[SCOUT] Rozgrzewka: zapamiętano %d ofert bez alertów.", len(fresh))
            return

        self._stats["new"] += len(fresh)
        for item in fresh:
            self._spawn(self.inspect(item))
        if fresh:
            log.info("[SCOUT] Nowe ogłoszenia: %s", [it["id"] for it in fresh])

    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # ------------------------------------------------------------------ detale
    async def inspect(self, item):
        item_id = item["id"]
        referer = item_url(item_id, item)  # jak date_verification.get_sidebar_info: Referer = item['url']

        async with self._detail_slots:
            sidebar, shipping = await asyncio.gather(
                self.session.get_json(SIDEBAR_URL.format(item_id=item_id), referer=referer),
                self.session.get_json(SHIPPING_URL.format(item_id=item_id), referer=referer),
                return_exceptions=True,
            )

        if isinstance(sidebar, Exception):
            log.error("[SCOUT] Brak detali dla %s: %r", item_id, sidebar)
            return
        if isinstance(shipping, Exception):
            log.warning("[SCOUT] Brak shipping_details dla %s: %r", item_id, shipping)
            shipping = None

        sidebar = unwrap_sidebar(sidebar)
        reason = inactive_reason(sidebar)
        if reason:
            log.info("[SCOUT] Pomijam %s - status: %s", item_id, reason)
            return

        offer = build_offer(item_id, sidebar, shipping, catalog_item=item)
        self.emit(offer)

    def emit(self, offer):
        payload = offer.to_dict()
        log.info("[ZŁAPANO] %s | %s %s | %s", offer.title, offer.price, offer.currency, offer.url)
        log.debug(json.dumps(payload, ensure_ascii=False))

        self._stats["caught"] += 1
        if self.offers.full():
            self.offers.get_nowait()  # nikt jeszcze nie konsumuje - wyrzucamy najstarszą
        self.offers.put_nowait(payload)
        self.notifier.notify(offer)

    # ------------------------------------------------------------------ pętla
    async def run(self):
        log.info("=== ZWIADOWCA START | kategoria=%s (%s) | proxy=%s ===",
                 self.cfg.category, self.cfg.catalog_id, "TAK" if self.cfg.proxy_url else "NIE")
        backoff = 0.0
        needs_refresh = True
        while True:
            try:
                if needs_refresh:
                    await self.session.refresh()
                    needs_refresh = False
                await self.poll_catalog()
                backoff = 0.0
            except RateLimited:
                backoff = min(max(backoff * 2, 10.0), 120.0)
                log.warning("[SCOUT] 429 Too Many Requests - czekam %.0fs.", backoff)
            except SessionExpired as exc:
                backoff = 30.0
                log.error("[SCOUT] %s - czekam %.0fs.", exc, backoff)
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                # Błąd proxy/sieci/JSON - przy rotacyjnym proxy następne żądanie pójdzie z innego IP.
                backoff = min(max(backoff * 2, 2.0), 30.0)
                log.warning("[SCOUT] Błąd skanu: %r - ponawiam za %.0fs.", exc, backoff)
                self._stats["errors"] += 1
            except Exception:
                # Nieprzewidziany błąd nie może zatrzymać pętli - logujemy pełny traceback i jedziemy dalej.
                backoff = min(max(backoff * 2, 5.0), 60.0)
                log.exception("[SCOUT] Nieoczekiwany błąd - ponawiam za %.0fs.", backoff)
                self._stats["errors"] += 1

            self._heartbeat()
            await asyncio.sleep(backoff or self.cfg.poll_interval + random.uniform(0, self.cfg.poll_jitter))

    def _heartbeat(self):
        """Co heartbeat_interval sekund jedna linia "żyję" - żeby cisza w logu nie wyglądała na zawieszenie."""
        interval = self.cfg.heartbeat_interval
        if not interval or time.monotonic() - self._last_heartbeat < interval:
            return
        s = self._stats
        log.info("[SCOUT] Żyję: %d skanów, %d błędów, nowych %d, złapanych %d w ostatnich %.0fs | "
                 "katalog: %d ofert, najnowsze ID %s",
                 s["polls"], s["errors"], s["new"], s["caught"], interval, s["last_size"], s["newest_id"])
        for key in ("polls", "errors", "new", "caught"):
            s[key] = 0
        self._last_heartbeat = time.monotonic()

    async def shutdown(self):
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
