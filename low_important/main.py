from session_management import make_boot_session, make_main_loop_referer, make_endpoints_referer, get_catalog_params, update_sesions_cookies
import time

# 1. Odpalamy jedyną, główną sesję (ciastka + nagłówki + autoryzacja)
session = make_boot_session()

current_page = 1
category = 'nosniki_pamieci'

# START PĘTLI GŁÓWNEJ (Katalog stron)
while True:
    print(f"--- Pobieranie strony {current_page} ---")
    
    # 2. Ustawiamy referer dla katalogu
    session.headers.update({"Referer": make_main_loop_referer(current_page)})
    
    # 3. Generujemy parametry tylko dla tego konkretnego strzału
    catalog_params = get_catalog_params(category=category, page=current_page)
    
    # 4. STRZAŁ W KATALOG (Z PARAMETRAMI)
    # Zauważ: params podajemy bezpośrednio w funkcji get()!
    response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
    
    # Zabezpieczenie przed błędem 401 w trakcie pętli (gdy ciastko wygaśnie)
    if response.status_code == 401:
        print("[!] Ciastko wygasło w trakcie pracy. Odświeżam...")
        update_sesions_cookies(session)
        response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
    
    dane_strony = response.json()
    items = dane_strony.get('items', [])
    
    if not items:
        print("Brak kolejnych ogłoszeń. Kończę.")
        break
        
    # START PĘTLI WEWNĘTRZNEJ (Szczegóły konkretnego ogłoszenia)
    for przedmiot in items:
        id_przedmiotu = przedmiot['id']
        tytul = przedmiot['title']
        
        # 5. Zmieniamy referer na URL tego ogłoszenia
        session.headers.update({"Referer": make_endpoints_referer(id_przedmiotu, tytul)})
        
        # 6. STRZAŁ W SZCZEGÓŁY / ZDJĘCIA (BEZ PARAMETRÓW!)
        # Ponieważ nie ma tu argumentu "params=...", zapytanie leci "czyste"
        zdjecia_url = f"https://www.vinted.pl/api/v2/items/{id_przedmiotu}/photos"
        response_zdjecia = session.get(zdjecia_url)
        
        dane_zdjec = response_zdjecia.json()
        print(f"Pobrano {len(dane_zdjec)} zdjęć dla {tytul}")
        
        # Tutaj wyciągasz URL zdjęć i wysyłasz do chmury / postgresa
        
        time.sleep(1) # Złota zasada scrapingu: nie zabij serwera
        
    current_page += 1   