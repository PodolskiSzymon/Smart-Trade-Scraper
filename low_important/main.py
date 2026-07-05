from session_management import make_boot_session, make_main_loop_referer, make_endpoints_referer, get_catalog_params, update_sesions_cookies 
import time

session = make_boot_session()

category = 'nosniki_pamieci'
curr_page = 1
last_page = 1  # Ustawiamy na 1 startowo, zaktualizujemy z API za moment

# Pętla kręci się tylko do momentu osiągnięcia limitu stron z API
while curr_page <= last_page:
    print(f"--- Pobieranie strony {curr_page} z {last_page} ---")
    
    session.headers.update({"Referer": make_main_loop_referer(curr_page)})
    catalog_params = get_catalog_params(category=category, page=curr_page)
    
    response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
    
    if response.status_code == 401:
        print("[!] Ciastko wygasło. Odświeżam...")
        update_sesions_cookies(session)
        response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
    
    page_data = response.json()
    
    # ---------------------------------------------------------
    # MAGICZNY PUNKT: Aktualizacja limitu stron z bloku pagination
    # ---------------------------------------------------------
    if 'pagination' in page_data:
        last_page = page_data['pagination']['total_pages']
        # Aktualizujemy też print, żeby w pierwszej iteracji od razu pokazał poprawny max
        if curr_page == 1:
            print(f"[INFO] Wykryto łącznie {last_page} stron ogłoszeń do przetworzenia.")
            
    items = page_data.get('items', [])
    
    if not items:
        print("Brak ogłoszeń na tej stronie. Przechodzę do końca.")
        break
        
    for przedmiot in items:
        id_przedmiotu = przedmiot['id']
        tytul = przedmiot['title']
        
        session.headers.update({"Referer": make_endpoints_referer(id_przedmiotu, tytul)})
        
        # Pobieranie szczegółów (URL zdjęć bezpośrednio z API ogłoszenia)
        zdjecia_url = f"https://www.vinted.pl/api/v2/items/{id_przedmiotu}/photos"
        response_zdjecia = session.get(zdjecia_url)
        
        # ... (Twoja logika wysyłania do GCS i bazy PostgreSQL) ...
        
        time.sleep(1) 
        
    curr_page += 1

print("Scraping zakończony sukcesem!")