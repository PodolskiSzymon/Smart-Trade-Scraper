"""Test: czy svc-catalogue respektuje per_page i ile transferu kosztuje jeden skan.

Sposób jak w main_vinted.py: requests + make_boot_session() + update_sesions_cookies() (Playwright),
domowe IP, bez proxy. Dla każdej wartości per_page:
  * status, liczba ofert w odpowiedzi, pierwsze/ostatnie ID,
  * transfer: bajty skompresowane (to płacisz w proxy) i po rozpakowaniu,
  * surowy JSON -> per_page_test/per_page_<n>.json,
  * podsumowanie -> per_page_test/summary.json (+ tabela w konsoli).

Uruchomienie:
    python check_per_page.py                    # kategoria 3580, price_from=100
    python check_per_page.py --cat 3580 --price-from 100 --no-refresh
"""
import gzip
import json
import os
import sys
import time
import zlib

from session_management import (
    CATALOG_URL, categories, get_catalog_params, make_boot_session, update_sesions_cookies,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "per_page_test")
VARIANTS = [96, 48, 20, 10, 5, None]   # None = bez parametru per_page


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def decode(raw, encoding):
    encoding = (encoding or "").lower()
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        return zlib.decompress(raw)
    return raw


def main():
    cat = arg("--cat", "3580")
    price_from = arg("--price-from", "100")
    categories.setdefault(cat, cat)
    os.makedirs(OUT, exist_ok=True)

    session = make_boot_session()
    if "--no-refresh" not in sys.argv:
        update_sesions_cookies(session)
    # Tylko gzip, żeby dało się policzyć bajty "na kablu" i rozpakować bez dodatkowych bibliotek.
    session.headers["accept-encoding"] = "gzip, deflate"

    summary = []
    for per_page in VARIANTS:
        params = get_catalog_params(category=cat, page=1, order='newest_first', price_from=price_from)
        if per_page is None:
            params.pop('per_page')
        else:
            params['per_page'] = per_page
        label = per_page if per_page is not None else "brak"

        resp = session.get(CATALOG_URL, params=params, stream=True, timeout=30)
        raw = resp.raw.read(decode_content=False)
        body = decode(raw, resp.headers.get("content-encoding"))
        row = {"per_page": label, "status": resp.status_code, "wire_bytes": len(raw), "json_bytes": len(body),
               "encoding": resp.headers.get("content-encoding", "brak"), "url": resp.url}
        try:
            data = json.loads(body)
            items = data.get("items") or []
            row.update(items=len(items), first_id=items[0]["id"] if items else None,
                       last_id=items[-1]["id"] if items else None,
                       top_keys=sorted(data) if isinstance(data, dict) else None,
                       pagination=data.get("pagination"))
            with open(os.path.join(OUT, f"per_page_{label}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except ValueError:
            row.update(items=None, body=body[:300].decode("utf-8", "replace"))
        summary.append(row)
        time.sleep(1.5)

    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'per_page':>8} {'status':>6} {'ofert':>6} {'transfer':>10} {'JSON':>10}  pierwsze ID / ostatnie ID")
    for r in summary:
        print(f"{r['per_page']!s:>8} {r['status']:>6} {r.get('items')!s:>6} "
              f"{r['wire_bytes'] / 1024:>8.1f}KB {r['json_bytes'] / 1024:>8.1f}KB  "
              f"{r.get('first_id')} / {r.get('last_id')}")
    if summary and summary[0].get("pagination"):
        print("\npagination (per_page=96):", summary[0]["pagination"])
    print(f"\nZapisano: {os.path.join(OUT, 'summary.json')} oraz per_page_<n>.json")
    print("Żeby Claude mógł to przeczytać bez wklejania: git add per_page_test/summary.json && git commit -m 'per_page test' && git push")


if __name__ == "__main__":
    main()
