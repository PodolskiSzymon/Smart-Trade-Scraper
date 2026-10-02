# Sniper – moduł Zwiadowcy (Scout)

Asynchroniczny (asyncio + httpx) zwiadowca, który co kilka sekund skanuje najnowsze
oferty w katalogu Vinted przez rotacyjne proxy, odrzuca duplikaty i sprzedane
ogłoszenia, wyciąga dane gotowe do wysyłki do modelu AI i wysyła alert e-mail.

## Struktura

| Plik | Rola |
|---|---|
| `config.py` | Konfiguracja z env / `sniper/.env` (proxy, SMTP, kategoria, tempo). |
| `dedup.py` | `RecentIds` – `deque(maxlen=20)` + `set` w RAM zamiast PostgreSQL. |
| `proxy_relay.py` | Lokalny przekaźnik proxy dla Chromium – dokleja `Proxy-Authorization` (Chromium nie obsługuje loginu/hasła do proxy przy HTTPS: `ERR_PROXY_AUTH_UNSUPPORTED`). |
| `session.py` | `VintedSession` – `httpx.AsyncClient` za proxy; przy 401/403 wstrzymuje wszystkie żądania i odświeża ciastka oraz `x-csrf-token` / `x-anon-id` przez Playwright (async, `headless=True`). |
| `extractor.py` | Czyste parsowanie JSON-ów: `details/sidebar`, `shipping_details` → `Offer`. |
| `notifier.py` | Alert e-mail przez `aiosmtplib` (smtp.poczta.onet.pl:465, SSL), wysyłany w tle. |
| `scout.py` | Główna, nieskończona pętla. |

## Przepływ jednej oferty

1. `GET https://api.vinted.pl/svc-catalogue/items` – parametry i nagłówki 1:1 z działającego zapytania
   przeglądarki (cURL z F12): `page`, `per_page=96`, `search_text`, `price_from`, `currency=PLN`, `order=newest_first`,
   `attribute_ids[catalog]` / `[brand]` / `[brand_collection]` / `[status]`. Nagłówki `config.CATALOG_HEADERS`
   (m.in. `origin`, `sec-fetch-site: same-site`, `platform: web`, `x-next-app: marketplace-web`, Edge 154),
   plus świeże `x-csrf-token` / `x-anon-id`. Nowe ID = spoza `RecentIds`.
2. Równolegle: `GET /api/v2/items/{id}/details/sidebar` + `GET /api/v2/items/{id}/shipping_details`
3. Plugin `item_status`: `item_closing_action == "sold"` → oferta ignorowana. Przechodzą tylko
   oferty aktywne (`item_closing_action: null`, a także nie zamknięte, nie zarezerwowane, nie ukryte).
4. `Offer.to_dict()` trafia do `scout.offers` (`asyncio.Queue` dla przyszłego modułu AI),
   a mail leci w tle – pętla skanująca nie czeka na SMTP.

Zdjęcia **nie są pobierane** – w ofercie jest tylko lista `full_size_url`.

### Kształt danych oferty

```json
{
  "id": 9238023547,
  "url": "https://www.vinted.pl/items/9238023547-...",
  "title": "Samsung pro ultimate 512GB",
  "price": 261.08, "currency": "PLN",
  "description": "...",
  "photo_urls": ["https://images1.vinted.net/tc/.../1782210267.webp?s=..."],
  "seller": {"id": 148344250, "name": "skestenyte.ska", "country": "Litwa", "country_code": "LT",
             "feedback_count": 7, "feedback_reputation": 1.0, "stars": 5.0, "business": false},
  "shipping": {"price": 13.27, "currency": "PLN", "free_shipping": false,
               "pickup_only": false, "multiple_options": true, "discount": null},
  "total_price": 274.35,
  "brand": "Samsung", "condition": "Nowy z metką",
  "detected_at": "2026-10-01T18:00:00+00:00"
}
```

`stars` = `feedback_reputation` (0–1 z API) × 5.

## Uruchomienie

```bash
pip install -r sniper/requirements.txt
playwright install chromium
cp sniper/.env.example sniper/.env      # uzupełnij proxy i hasło do Onetu
python -m sniper                         # z katalogu głównego repo
```

Testy (na prawdziwych odpowiedziach API z `api.docx`):

```bash
pip install pytest
python -m pytest sniper/tests
```

## Alerty e-mail

Każda złapana oferta (na razie bez filtrowania) idzie mailem przez Onet (`smtp.poczta.onet.pl:465`, SSL).
Mail ma wersję tekstową i HTML: tytuł, cena, wysyłka, suma, stan, marka, przycisk do ogłoszenia,
miniatury + linki do zdjęć (`full_size_url`), pełny opis i sprzedawca (nazwa, kraj, ocena, liczba opinii,
typ konta, link do profilu).

W `sniper/.env` ustaw `SNIPER_SMTP_USER` (pełny adres @onet.pl) i `SNIPER_SMTP_PASSWORD`;
`SNIPER_EMAIL_TO` opcjonalnie (domyślnie ten sam adres). Test bez czekania na ogłoszenie:

```bash
python -m sniper.notifier
```

## Logi

* `sniper/logs/sniper.log` – wszystko, co widać w konsoli, plus szczegóły (pełny JSON złapanych ofert,
  tracebacki). Nowy plik co północ, poprzednie jako `sniper.log.RRRR-MM-DD`, trzymane 30 dni.
* `sniper/logs/offers.jsonl` – każda złapana oferta jako jedna linia JSON (dane dla modułu AI).
* Folder zmienisz przez `SNIPER_LOG_DIR`. `sniper/logs/` jest w `.gitignore`.

## Uwagi

* **Proxy IPRoyal – tylko Zwiadowca**: w `sniper/.env` ustaw `SNIPER_PROXY_HOST=geo.iproyal.com:12321` i
  `SNIPER_PROXY_AUTH=LOGIN:HASLO_country-pl`. `config.build_proxy_url()` składa z tego
  `http://{proxy_auth}@{proxy}`. Przez proxy idzie wyłącznie kod z folderu `sniper/`:
  httpx Zwiadowcy, jego Playwright (przez przekaźnik `ProxyRelay`) i `python -m sniper.diagnose`.
  Bez skonfigurowanego proxy Zwiadowca rzuca `ProxyNotConfigured` zamiast wyjść bezpośrednio
  (`SNIPER_REQUIRE_PROXY=true`, domyślnie). Pozostałe skrypty w repozytorium (`main*.py`, OLX,
  `low_important/` itd.) nie korzystają z proxy i działają z domowego IP.
* **Filtry**: `SNIPER_CATALOG` (numer kategorii, np. `3580`; nazwa z `config.CATEGORIES` też działa, stare `SNIPER_CATEGORY` jako zapas),
  `SNIPER_PRICE_FROM` / `SNIPER_PRICE_TO` (PLN, puste = bez limitu). Cena jest dodatkowo sprawdzana po pobraniu szczegółów.
* **Playwright i proxy z hasłem**: przeglądarka łączy się z `127.0.0.1` (przekaźnik), a ten z IPRoyal z Twoim loginem i hasłem.
* **Proxy i ciastka anty-botowe**: `cf_clearance` / `datadome` są wiązane z IP i User-Agentem.
  Dlatego Playwright też idzie przez proxy, a UA jest identyczny w obu klientach.
  Jeśli po odświeżeniu sesji wciąż lecą 403, rozważ sesję „sticky” w IPRoyal (stały IP przez kilka minut)
  zamiast zmiany IP przy każdym żądaniu.
* **Rozgrzewka**: pierwszy skan tylko zapamiętuje obecne oferty (bez alertów). Wyłączysz to przez
  `SNIPER_SKIP_INITIAL_BATCH=false`.
* **Duplikaty**: pamięć ostatnich 500 ID (`deque` + `set`, minimum 500 – katalog zwraca 96 ofert na stronę).
  Bez progu „niższe ID = stare”: Vinted nadaje ID przy tworzeniu ogłoszenia, więc szkic opublikowany później ma niższe ID.
* **Heartbeat** (co `SNIPER_HEARTBEAT` s): skany, błędy, nowe/złapane/pominięte (z powodem), maile wysłane/błędy
  i 5 pierwszych ofert z katalogu (kolejność Vinted) z linkami – do porównania z przeglądarką.
* **Onet SMTP**: w ustawieniach skrzynki Onet musi być włączony dostęp przez programy pocztowe (SMTP).
  Hasło podawaj tylko przez `sniper/.env` (plik jest w `.gitignore`).
