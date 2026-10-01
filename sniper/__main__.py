"""Uruchomienie: python -m sniper  (z katalogu głównego repozytorium)."""
import asyncio
import logging

from .config import ScoutConfig
from .notifier import EmailNotifier
from .scout import Scout
from .session import VintedSession


def setup_logging(log_file):
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def main():
    cfg = ScoutConfig()
    setup_logging(cfg.log_file)

    session = VintedSession(
        proxy_url=cfg.proxy_url,
        browser_use_proxy=cfg.browser_use_proxy,
        timeout=cfg.request_timeout,
        browser_wait_ms=cfg.browser_wait_ms,
    )
    notifier = EmailNotifier(cfg.smtp)
    scout = Scout(cfg, session, notifier)
    try:
        await scout.run()
    finally:
        await scout.shutdown()
        await notifier.drain()
        await session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("sniper").info("=== ZWIADOWCA ZATRZYMANY RĘCZNIE ===")
