"""Asynchroniczne alerty e-mail przez SMTP Onetu (aiosmtplib, SSL na porcie 465)."""
import asyncio
import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import aiosmtplib

log = logging.getLogger("sniper.notifier")


def _fmt_money(amount, currency):
    return f"{amount:.2f} {currency}" if amount is not None else "brak danych"


def shipping_text(offer):
    ship = offer.shipping
    if ship is None:
        return "brak danych"
    if ship.free_shipping:
        return "darmowa"
    if ship.pickup_only:
        return "tylko odbiór osobisty"
    return _fmt_money(ship.price, ship.currency or offer.currency)


def build_message(offer, sender, recipient):
    price = _fmt_money(offer.price, offer.currency)
    shipping = shipping_text(offer)

    msg = EmailMessage()
    msg["Subject"] = f"[Sniper] {offer.title} | {price} + wysyłka {shipping}"
    msg["From"] = sender
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="sniper.local")

    seller = offer.seller
    stars = f"{seller.stars:.1f}/5" if seller.stars is not None else "brak"
    photos = "\n".join(f"  - {u}" for u in offer.photo_urls) or "  (brak)"
    total = _fmt_money(offer.total_price, offer.currency)

    msg.set_content(
        f"Złapano okazję na Vinted!\n\n"
        f"Tytuł:     {offer.title}\n"
        f"Cena:      {price}\n"
        f"Wysyłka:   {shipping}\n"
        f"Razem:     {total}\n"
        f"Link:      {offer.url}\n\n"
        f"Sprzedawca: {seller.name or '?'} ({seller.country or 'kraj nieznany'}), "
        f"ocena {stars}, opinii: {seller.feedback_count if seller.feedback_count is not None else '?'}\n\n"
        f"Opis:\n{offer.description or '(brak)'}\n\n"
        f"Zdjęcia:\n{photos}\n"
    )
    return msg


class EmailNotifier:
    """Wysyła maile w tle - główna pętla tylko tworzy zadanie i leci dalej."""

    def __init__(self, smtp_config):
        self.cfg = smtp_config
        self._tasks = set()
        if not self.cfg.enabled:
            log.warning("[MAIL] Brak SNIPER_SMTP_USER/SNIPER_SMTP_PASSWORD - alerty e-mail wyłączone.")

    def notify(self, offer):
        """Nieblokujące: planuje wysyłkę i natychmiast wraca."""
        if not self.cfg.enabled:
            return
        task = asyncio.create_task(self._send(offer), name=f"mail-{offer.id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _send(self, offer):
        message = build_message(offer, self.cfg.sender, self.cfg.recipient)
        try:
            await aiosmtplib.send(
                message,
                hostname=self.cfg.host,
                port=self.cfg.port,
                username=self.cfg.username,
                password=self.cfg.password,
                use_tls=True,          # SSL od początku połączenia (port 465)
                timeout=self.cfg.timeout,
            )
            log.info("[MAIL] Wysłano alert dla %s -> %s", offer.id, self.cfg.recipient)
        except Exception as exc:
            log.error("[MAIL] Nie udało się wysłać alertu dla %s: %s", offer.id, exc)

    async def drain(self, timeout=15.0):
        """Przy zamykaniu programu - daje szansę dokończyć wysyłkę maili w locie."""
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=timeout)
