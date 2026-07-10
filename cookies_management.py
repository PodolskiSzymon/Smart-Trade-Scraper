from playwright.sync_api import sync_playwright;
import os;
import json;
import logging;

COOKIES_FILE = "vinted_cookies.json"

def load_vinted_cookies_from_file():
    """Wczytuje ciastka z pliku na samym starcie programu."""
    if not os.path.exists(COOKIES_FILE):
        print(f"[DISK] Brak pliku {COOKIES_FILE}. Program ruszy z pustą sesją.")
        return {}
    
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        print(f"[DISK] Wczytano ciasteczka startowe z pliku {COOKIES_FILE}.")
        return json.load(f)

def load_olx_cookies(file_path="olx_cookies.json"):
    """
    Wczytuje ciastka OLX z zewnętrznego pliku JSON.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            logging.info("[OLX] Pomyślnie załadowano ciastka z pliku.")
            return cookies
    except FileNotFoundError:
        logging.error(f"[OLX BŁĄD] Nie znaleziono pliku: {file_path}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"[OLX BŁĄD] Plik {file_path} ma uszkodzony format JSON: {e}")
        return {}

def zdobadz_nowe_ciastka():
    #print("[AUTH] Uruchamiam Playwright (Chromium)...")
    with sync_playwright() as p:
        # Launch w trybie headed=False pozwoli Ci ręcznie przeklikać Cloudflare, jeśli zajdzie potrzeba
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        #print("[AUTH] Wchodzę na Vinted...")
        page.goto("https://www.vinted.pl")
        
        # Dajemy czas na załadowanie wszystkiego
        page.wait_for_timeout(3000) 
        
        # Pobieramy ciasteczka w formacie, który 'requests' połknie bez problemu
        cookies_list = context.cookies()
        gotowe_ciastka = {c['name']: c['value'] for c in cookies_list}
        
        browser.close()
        #print("[AUTH] Sukces! Zdobyto świeże ciasteczka.")
        return gotowe_ciastka
    
def update_cookies():
    """
    Kombajn 3w1 wywoływany, gdy Vinted zwróci 401:
    1. Odpala Playwright i zdobywa świeże ciastka.
    2. Zapisuje je trwale na dysk (nadpisuje stary plik).
    3. Podmienia ciastka w obecnej sesji requests.
    """
    #print("\n[WARN] Rozpoczynam procedurę aktualizacji ciasteczek...")
    
    # 1. Pobieranie nowych ciastek Twoją funkcją z Playwrightem
    nowe_ciastka = zdobadz_nowe_ciastka() 
    
    # 2. Zapis do pliku JSON
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(nowe_ciastka, f, indent=4)
    return nowe_ciastka
    #print(f"[DISK] Zapisano świeże ciasteczka do {COOKIES_FILE}.") 

