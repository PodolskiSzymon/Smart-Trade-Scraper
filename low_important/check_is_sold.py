import requests
import json
import os
from playwright.sync_api import sync_playwright

COOKIES_FILE = "cookies.json"

# ==========================================
# MIEJSCE NA TWÓJ TOKEN Z PRZEGLĄDARKI
# Skopiuj to z zakładki Network (nagłówek Authorization)
# Format: "Bearer eyJhbGciOi..."
# ==========================================
BEARER_TOKEN = "Bearer TUTAJ_WKLEJ_SWOJ_TOKEN_Z_PRZEGLADARKI"

def load_cookies_from_file():
    """Wczytuje ciastka z pliku na samym starcie programu."""
    if not os.path.exists(COOKIES_FILE):
        print(f"[DISK] Brak pliku {COOKIES_FILE}. Program ruszy z pustą sesją.")
        return {}
    
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        print(f"[DISK] Wczytano ciasteczka startowe z pliku {COOKIES_FILE}.")
        return json.load(f)
    
def zdobadz_nowe_ciastka():
    print("[AUTH] Uruchamiam Playwright (Chromium)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("[AUTH] Wchodzę na Vinted...")
        page.goto("https://www.vinted.pl")
        page.wait_for_timeout(3000) 
        
        cookies_list = context.cookies()
        gotowe_ciastka = {c['name']: c['value'] for c in cookies_list}
        
        browser.close()
        print("[AUTH] Sukces! Zdobyto świeże ciasteczka.")
        return gotowe_ciastka
    
def update_cookies(session):
    print("\n[WARN] Rozpoczynam procedurę aktualizacji ciasteczek...")
    nowe_ciastka = zdobadz_nowe_ciastka() 
    
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(nowe_ciastka, f, indent=4)
    print(f"[DISK] Zapisano świeże ciasteczka do {COOKIES_FILE}.")
    
    session.cookies.clear()
    session.cookies.update(nowe_ciastka)

def test_mark_as_sold(item_id, session):
    print(f"\n[TEST] Uderzam w endpoint mark_as_sold_item_details dla ID: {item_id}")
    url = f"https://www.vinted.pl/api/v2/mark_as_sold_item_details/{item_id}"
    
    # Specyficzne nagłówki dla tego konkretnego endpointu
    custom_headers = {
        "Authorization": BEARER_TOKEN,
        # Aplikacja mobilna często przedstawia się inaczej niż przeglądarka
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Aktualizujemy nagłówki sesji tylko dla tego zapytania
    session.headers.update(custom_headers)
    
    try:
        resp = session.get(url)
        print(f"[WYNIK] Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            print("[SUKCES] Odpowiedź serwera:")
            print(json.dumps(resp.json(), indent=4))
        elif resp.status_code == 401:
            print("[BŁĄD 401] Brak autoryzacji. Prawdopodobnie zły lub wygasły BEARER_TOKEN.")
            print(resp.text)
        elif resp.status_code == 403:
            print("[BŁĄD 403] Dostęp zabroniony. Endpoint może wymagać podpisu aplikacji mobilnej.")
            print(resp.text)
        elif resp.status_code == 404:
            print("[BŁĄD 404] Nie znaleziono. Może to nie jest Twój przedmiot?")
            print(resp.text)
        else:
            print(f"Nieoczekiwana odpowiedź:\n{resp.text}")
            
    except Exception as e:
        print(f"[WYJĄTEK] Błąd podczas testowania: {e}")

# ==========================================
# GŁÓWNA LOGIKA SKRYPTU
# ==========================================
if __name__ == "__main__":
    cookies = load_cookies_from_file()

    # Bazowe nagłówki (bez twardo wpisanego klucza 'cookie'!)
    headers = {
        'accept': 'application/json,text/plain,*/*,image/webp',
        'accept-language': 'pl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'locale': 'pl-PL',
        'referer': 'https://www.vinted.pl/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0',
        # Poniższe tokeny CSRF i ANON bywają zdradliwe, jeśli nie pasują do ciasteczek
        'x-anon-id': 'e6f5e540-66d2-4848-ac99-c9e08762733f',
        'x-csrf-token': '75f6c9fa-dc8e-4e52-a000-e09dd4084b3e'
    }

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update(headers)

    # Najpierw wchodzimy na stronę główną, żeby zainicjować "legalny" ruch
    session.get("https://www.vinted.pl/")

    # Wybierz ID przedmiotu, który chcesz przetestować. 
    # Najlepiej najpierw spróbować na ID Twojego własnego ogłoszenia, a potem kogoś obcego.
    TEST_ITEM_ID = "9263375456" 
    
    test_mark_as_sold(TEST_ITEM_ID, session)