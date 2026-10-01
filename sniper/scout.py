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
import uuid

import httpx

from .config import CATALOG_URL, SHIPPING_URL, SIDEBAR_URL, USER_URL, BASE_URL, ScoutConfig
from .dedup import RecentIds
from .extractor import build_offer, inactive_reason, item_url, unwrap_sidebar
from .notifier import EmailNotifier
from .session import RateLimited, SessionExpired, VintedSession

log = logging.getLogger("sniper.scout")


def catalog_params(cfg):
    return {
        "page": 1,
        "per_page": cfg.per_page,
        "search_text": cfg.search_text,
        "price_from": cfg.price_from,
        "price_to": cfg.price_to,
        "currency": "PLN",
        "order": "newest_first",
        "catalog_ids": cfg.catalog_id,
        "time": str(int(time.time())),
        "global_search_session_id": str(uuid.uuid4()),
    }


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

    # ------------------------------------------------------------------ katalog
    async def poll_catalog(self):
        data = await self.session.get_json(
            CATALOG_URL, params=catalog_params(self.cfg), referer=f"{BASE_URL}/catalog"
        )
        items = data.get("items") or []
        if not items:
            log.warning("[SCOUT] Pusty katalog - możliwy soft-ban. Odświeżam sesję.")
            await self.session.refresh()
            return

        # Rosnąco po ID, żeby RecentIds wypychał najstarsze oferty jako pierwsze.
        fresh = [it for it in sorted(items, key=lambda it: it["id"]) if self.seen.add(it["id"])]

        if self._first_batch:
            self._first_batch = False
            log.info("[SCOUT] Rozgrzewka: zapamiętano %d ofert bez alertów.", len(fresh))
            return

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
        referer = item_url(item_id, item)
        seller_id = (item.get("user") or {}).get("id")
        need_profile = (
            self.cfg.fetch_seller_profile
            and seller_id
            and not (item.get("user") or {}).get("country_title")
        )

        async with self._detail_slots:
            requests = [
                self.session.get_json(SIDEBAR_URL.format(item_id=item_id), referer=referer),
                self.session.get_json(SHIPPING_URL.format(item_id=item_id), referer=referer),
            ]
            if need_profile:
                requests.append(self.session.get_json(USER_URL.format(user_id=seller_id), referer=referer))
            results = await asyncio.gather(*requests, return_exceptions=True)

        sidebar, shipping = results[0], results[1]
        profile = results[2] if need_profile else None

        if isinstance(sidebar, Exception):
            log.error("[SCOUT] Brak detali dla %s: %r", item_id, sidebar)
            return
        if isinstance(shipping, Exception):
            log.warning("[SCOUT] Brak shipping_details dla %s: %r", item_id, shipping)
            shipping = None
        if isinstance(profile, Exception):
            log.debug("[SCOUT] Brak profilu sprzedawcy %s: %r", seller_id, profile)
            profile = None

        sidebar = unwrap_sidebar(sidebar)
        reason = inactive_reason(sidebar)
        if reason:
            log.info("[SCOUT] Pomijam %s - status: %s", item_id, reason)
            return

        offer = build_offer(item_id, sidebar, shipping, catalog_item=item, user_profile=profile)
        self.emit(offer)

    def emit(self, offer):
        payload = offer.to_dict()
        log.info("[ZŁAPANO] %s | %s %s | %s", offer.title, offer.price, offer.currency, offer.url)
        log.debug(json.dumps(payload, ensure_ascii=False))

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

            await asyncio.sleep(backoff or self.cfg.poll_interval + random.uniform(0, self.cfg.poll_jitter))

    async def shutdown(self):
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
