"""Test zapytania do katalogu sposobem ze starego main_vinted.py (requests, bez httpx, bez proxy).

Kroki jak w main_vinted.run_scraper_cycle:
  make_boot_session() -> update_sesions_cookies(session) (Playwright z oknem, świeże ciastka + tokeny)
  -> Referer = make_main_loop_referer(1) -> session.get(CATALOG_URL, params=get_catalog_params(...))

Wysyła kilka wariantów parametrów, żeby wskazać, który parametr powoduje 400 "Invalid request parameters".

Uruchomienie:
    python check_catalog_main_vinted.py                 # kategoria 3580, najpierw Playwright
    python check_catalog_main_vinted.py --cat 3063
    python check_catalog_main_vinted.py --no-refresh    # bez Playwrighta: ciastka/tokeny z vinted_cookies.json / vinted_headers.json
"""
import logging
import sys
import time

from session_management import (
    CATALOG_URL, categories, get_catalog_params, make_boot_session,
    make_main_loop_referer, update_sesions_cookies,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def without_empty(params):
    return {k: v for k, v in params.items() if v != ''}


def report(label, response):
    print(f"\n=== {label}")
    print(f"GET {response.url}")
    print(f"status={response.status_code} server={response.headers.get('server')} content-type={response.headers.get('content-type')}")
    try:
        data = response.json()
    except ValueError:
        print("body:", response.text[:300].replace("\n", " "))
        return
    items = data.get("items") if isinstance(data, dict) else None
    if isinstance(items, list):
        print(f"OK - ofert: {len(items)}")
        for item in items[:3]:
            print(f"  - {item.get('id')} | {item.get('title')} | {item.get('url')}")
    else:
        keys = ", ".join(data) if isinstance(data, dict) else type(data).__name__
        print(f"klucze odpowiedzi: {keys}")
        print("body:", response.text[:300].replace("\n", " "))


def main():
    cat = arg("--cat", "3580")
    # session_management.categories zna tylko nazwy - numer kategorii dopisujemy jako sam siebie
    categories.setdefault(cat, cat)

    session = make_boot_session()
    if "--no-refresh" not in sys.argv:
        update_sesions_cookies(session)
    print("tokeny w sesji:", ", ".join(k for k in ("x-csrf-token", "x-anon-id") if k in session.headers) or "brak")
    print("ciastka w sesji:", len(session.cookies))

    session.headers.update({"Referer": make_main_loop_referer(1)})   # jak main_vinted

    base = get_catalog_params(category=cat, page=1, order='newest_first')
    variants = [
        ("A: main_vinted 1:1 (puste price_from)", base),
        ("B: jak A, bez pustych parametrów", without_empty(base)),
        ("C: jak A, price_from=0", {**base, 'price_from': '0'}),
        ("D: dokładnie URL z przeglądarki (page=2, price_from=2000)",
         get_catalog_params(category=cat, page=2, order='newest_first', price_from='2000')),
    ]
    for label, params in variants:
        response = session.get(CATALOG_URL, params=params)
        report(label, response)
        time.sleep(1)


if __name__ == "__main__":
    main()
