from session_management import make_boot_session, make_main_loop_referer, make_endpoints_referer, get_catalog_params, update_sesions_cookies 
from db_management import pobierz_ostatnie_20_id_vinted, zapisz_nowe_id_vinted
import time
import os
import requests
import logging

# Konfiguracja loggera - zapisuje i do pliku, i wyświetla w konsoli
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("scraper_debug.log", encoding='utf-8'),
        logging.StreamHandler() # To sprawia, że nadal widzisz wszystko w terminalu
    ]
)

def run_scraper_cycle(session, target_category, target_stop_ids):
    curr_page = 1
    last_page = 1
    my_order = 'newest_first'
    
    # Zbieramy wszystkie NOWE ID z tego cyklu
    new_scraped_ids = []

    while curr_page <= last_page:
        logging.info(f"--- Pobieranie strony {curr_page} z {last_page} ---")
        
        session.headers.update({"Referer": make_main_loop_referer(curr_page)})
        catalog_params = get_catalog_params(category=target_category, page=curr_page, order=my_order)
        
        response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
        
        if response.status_code == 401:
            logging.warning("[!] Ciastko wygasło. Odświeżam...")
            update_sesions_cookies(session)
            response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
        
        page_data = response.json()
        if 'pagination' in page_data:
            last_page = page_data['pagination']['total_pages']
                
        items = page_data.get('items', [])
        
        if not items:
            if curr_page == 1:
                logging.warning("[!] Brak ogłoszeń już na pierwszej stronie! Możliwy soft-ban. Odświeżam ciastka...")
                update_sesions_cookies(session)
                continue
            else:
                logging.info(f"Koniec wyników na stronie {curr_page}. Zamykam cykl.")
            break
            
        for item in items:
            item_id = item['id']

            # ZMIANA: Sprawdzamy czy ID jest na liście znanych 20 ogłoszeń
            if item_id in target_stop_ids:
                logging.info(f"Dotarto do znanego ogłoszenia ({item_id}). Kończę cykl.")
                return new_scraped_ids # Zwracamy listę nowych ID, żeby zapisać je do bazy
                
            # Dodajemy ID do listy nowości (aby na koniec wylądowało w Postgresie)
            new_scraped_ids.append(item_id)

            title = item['title']
            item_url = item.get('url', 'Brak URL ogłoszenia')
            logging.info(f"Pobieram nowe: {title}")
            
            # --- START LOGIKI POBIERANIA GŁÓWNEGO ZDJĘCIA ---
            photos_url = f"https://www.vinted.pl/api/v2/items/{item_id}/photos"
            photo_response = session.get(photos_url)
            
            if photo_response.status_code == 200:
                photos_data = photo_response.json()
                photos = photos_data.get('photos', []) if isinstance(photos_data, dict) else photos_data
                
                # Upewniamy się, że ogłoszenie ma w ogóle jakieś zdjęcia
                if photos:
                    # Bierzemy tylko główne (pierwsze) zdjęcie
                    main_photo_data = photos[0]
                    photo_url = main_photo_data.get('full_size_url') or main_photo_data.get('url')
                    
                    if photo_url:
                        # stream=True jest niezbędne, aby nie zapchać RAMu i użyć iter_content
                        image_response = requests.get(photo_url, stream=True)
                        
                        if image_response.status_code == 200:
                            # Tworzymy folder docelowy
                            os.makedirs("zdjecia", exist_ok=True)
                            
                            file_name = f"zdj{item_id}.png"
                            local_path = os.path.join("zdjecia", file_name)
                            
                            with open(local_path, 'wb') as f:
                                for chunk in image_response.iter_content(8192):
                                    f.write(chunk)
                                    
                            # TUTAJ LOGUJEMY PEŁNE INFORMACJE O SUKCESIE I URL-ach
                            logging.info(f"[DYSK] Zapisano plik: {local_path} | URL Ogłoszenia: {item_url} | URL Zdjęcia: {photo_url}")
                        else:
                            logging.error(f"[BŁĄD CDN] Serwer odrzucił plik graficzny dla ID {item_id} (Status: {image_response.status_code}) | URL: {photo_url}")
                else:
                    logging.info(f"[INFO] Brak zdjęć w ogłoszeniu ({item_id}).")
            else:
                logging.error(f"[BŁĄD API] Nie udało się pobrać JSON ze zdjęciami dla ID {item_id} (Status: {photo_response.status_code})")
            # --- KONIEC LOGIKI POBIERANIA GŁÓWNEGO ZDJĘCIA ---
            
            time.sleep(1)
            
        curr_page += 1

    return new_scraped_ids


def main():
    session = make_boot_session()
    target_category = 'karty_pamieci'
    
    logging.info("=== URUCHAMIAM GŁÓWNY HARMONOGRAM SCRAPERA ===")
    
    while True:
        # POBIERAMY Z BAZY LISTĘ 20 PUNKTÓW STOPU
        punkty_stopu = pobierz_ostatnie_20_id_vinted()
        
        # Opcja dla pierwszego uruchomienia (gdy baza jest pusta)
        if not punkty_stopu: 
            punkty_stopu = [0] 
            
        logging.info(f"\n[HARMONOGRAM] Start. Aktywne punkty stopu: {punkty_stopu}")
        
        # Cykl zwraca nam teraz pełną listę wszystkich NOWYCH przedmiotów
        nowo_pobrane_id = run_scraper_cycle(session, target_category, target_stop_ids=punkty_stopu)
        
        # Zapisujemy nowości do bazy (odkurzacz sam usunie to co starsze niż 20)
        if nowo_pobrane_id:
            zapisz_nowe_id_vinted(nowo_pobrane_id)
            logging.info(f"[BAZA] Przekazano {len(nowo_pobrane_id)} nowych ID do zapisu w buforze.")
            
        logging.info("[HARMONOGRAM] Cykl zakończony. Zasypiam na godzinę.")
        time.sleep(3600)

if __name__ == "__main__":
    main()