from playwright.sync_api import sync_playwright
import os
import json
import logging

COOKIES_FILE = "vinted_cookies.json"
# Ten sam UA co w session_management.make_boot_session() - cf_clearance/datadome są wiązane z UA
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"
HEADERS_FILE = "vinted_headers.json"

def load_vinted_data_from_file():
    """Wczytuje ciastka i tokeny z plików na starcie programu."""
    cookies, headers = {}, {}
    
    if not os.path.exists(COOKIES_FILE):
        logging.info(f"[DISK] Brak pliku {COOKIES_FILE}.")
    else:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            logging.info(f"[DISK] Wczytano ciasteczka startowe z pliku {COOKIES_FILE}.")
            
    if not os.path.exists(HEADERS_FILE):
        logging.info(f"[DISK] Brak pliku {HEADERS_FILE}.")
    else:
        with open(HEADERS_FILE, "r", encoding="utf-8") as f:
            headers = json.load(f)
            logging.info(f"[DISK] Wczytano headery startowe z pliku {HEADERS_FILE}.")
            
    return cookies, headers

def load_olx_cookies(file_path="olx_cookies.json"):
    """Wczytuje ciastka OLX z zewnętrznego pliku JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            logging.info("[OLX] Pomyślnie załadowano ciastka z pliku.")
            return cookies
    except FileNotFoundError:
        logging.error(f"[OLX BŁĄD] Nie znaleziono pliku: {file_path}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"[OLX BŁĄD] Plik {file_path} jest uszkodzony. {e}")
        return {}

def zdobadz_nowe_ciastka_i_headery():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(user_agent=BROWSER_USER_AGENT)
        page = context.new_page()
        
        przechwycone_headery = {}
        
        # Przechwytujemy ruch sieciowy przeglądarki - stare API (www.vinted.pl/api/v2)
        # i nowe (api.vinted.pl/svc-catalogue/...)
        def intercept_request(request):
            if "api/v2" in request.url or "api.vinted.pl" in request.url:
                przechwycone_headery.update(request.headers)

        page.on("request", intercept_request)
        
        logging.info("[AUTH] Wchodzę na Vinted i nasłuchuję tokenów...")
        page.goto("https://www.vinted.pl/catalog")
        
        # Dajemy czas na załadowanie zasobów i strzały API w tle
        page.wait_for_timeout(4000) 
        
        cookies_list = context.cookies()
        gotowe_ciastka = {c['name']: c['value'] for c in cookies_list}
        
        wazne_headery = {}
        if 'x-csrf-token' in przechwycone_headery:
            wazne_headery['x-csrf-token'] = przechwycone_headery['x-csrf-token']
        if 'x-anon-id' in przechwycone_headery:
            wazne_headery['x-anon-id'] = przechwycone_headery['x-anon-id']

        # Zapas, gdy żadne zapytanie API nie niosło tokenów: csrf z <meta>, anon-id z ciastka anon_id
        if 'x-csrf-token' not in wazne_headery:
            token = page.evaluate("() => document.querySelector('meta[name=\"csrf-token\"]')?.content || null")
            if token:
                wazne_headery['x-csrf-token'] = token
        if 'x-anon-id' not in wazne_headery and gotowe_ciastka.get('anon_id'):
            wazne_headery['x-anon-id'] = gotowe_ciastka['anon_id']

        browser.close()
        logging.info(f"[AUTH] Sukces! Zdobyto {len(gotowe_ciastka)} ciastek i nagłówki: {', '.join(sorted(wazne_headery)) or 'brak'}.")
        return gotowe_ciastka, wazne_headery

def update_cookies_and_headers():
    """Zdobywa nowe pakiety bezpieczeństwa i zapisuje je na dysk."""
    nowe_ciastka, nowe_headery = zdobadz_nowe_ciastka_i_headery() 
    
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(nowe_ciastka, f, indent=4)
        
    with open(HEADERS_FILE, "w", encoding="utf-8") as f:
        json.dump(nowe_headery, f, indent=4)
        
    return nowe_ciastka, nowe_headery