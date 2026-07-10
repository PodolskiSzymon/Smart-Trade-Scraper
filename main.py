import time
import os
import requests
import logging
import math
import sys
from db_management import (
    pobierz_ostatnie_20_id_vinted, zapisz_nowe_id_vinted,
    pobierz_ostatnie_50_id_olx, zapisz_nowe_id_olx
)
from cookies_management import load_olx_cookies
from session_management import (
    make_boot_session, make_main_loop_referer, get_catalog_params, 
    update_sesions_cookies, get_olx_headers, get_olx_payload
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("scraper_unified_debug.log", encoding='utf-8'),
        logging.StreamHandler() 
    ]
)

def run_vinted_cycle(session, target_category, target_stop_ids):
    curr_page = 1
    last_page = 1
    my_order = 'newest_first'
    new_scraped_ids = []

    try:
        while curr_page <= last_page:
            logging.info(f"--- [VINTED] Pobieranie strony {curr_page} z {last_page} ---")
            
            session.headers.update({"Referer": make_main_loop_referer(curr_page)})
            catalog_params = get_catalog_params(category=target_category, page=curr_page, order=my_order)
            
            response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
            
            if response.status_code == 401:
                logging.warning("[VINTED] Ciastko wygasło. Odświeżam...")
                update_sesions_cookies(session)
                response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
            
            page_data = response.json()
            if 'pagination' in page_data:
                last_page = page_data['pagination']['total_pages']
                    
            items = page_data.get('items', [])
            
            if not items:
                if curr_page == 1:
                    logging.warning("[VINTED] Brak ogłoszeń. Możliwy soft-ban. Odświeżam ciastka...")
                    update_sesions_cookies(session)
                    continue
                else:
                    logging.info(f"[VINTED] Koniec wyników na stronie {curr_page}.")
                break
                
            for item in items:
                item_id = item['id']

                # WARUNEK STOPU VINTED
                if item_id in target_stop_ids:
                    logging.info(f"[VINTED] Dotarto do znanego ogłoszenia ({item_id}). Przechodzę dalej.")
                    new_scraped_ids.reverse() # NAPRAWA DLA VINTED
                    return new_scraped_ids 
                    
                new_scraped_ids.append(item_id)
                title = item['title']
                item_url = item.get('url', 'Brak URL')
                logging.info(f"[VINTED] Nowe: {title}")
                
                photos_url = f"https://www.vinted.pl/api/v2/items/{item_id}/photos"
                photo_response = session.get(photos_url)
                
                if photo_response.status_code == 200:
                    photos_data = photo_response.json()
                    photos = photos_data.get('photos', []) if isinstance(photos_data, dict) else photos_data
                    
                    if photos:
                        main_photo_data = photos[0]
                        photo_url = main_photo_data.get('full_size_url') or main_photo_data.get('url')
                        
                        if photo_url:
                            image_response = requests.get(photo_url, stream=True)
                            if image_response.status_code == 200:
                                os.makedirs("zdjecia", exist_ok=True)
                                local_path = os.path.join("zdjecia", f"zdj{item_id}.png")
                                
                                with open(local_path, 'wb') as f:
                                    for chunk in image_response.iter_content(8192):
                                        f.write(chunk)
                                        
                                logging.info(f"[DYSK VINTED] Zapisano plik: {local_path}")
                            else:
                                logging.error(f"[BŁĄD VINTED] CDN odrzucił plik. Status: {image_response.status_code}")
                else:
                    logging.error(f"[BŁĄD VINTED API] Brak JSON zdjęć. Status: {photo_response.status_code}")
                
                time.sleep(1)
                
            curr_page += 1

    except KeyboardInterrupt:
        logging.warning("[!] PRZERWANO RĘCZNIE W TRAKCIE VINTED! Zabezpieczam dane...")
        
    # Wykona się przy przerwaniu i przy zakończeniu pętli
    new_scraped_ids.reverse()
    return new_scraped_ids


def run_olx_cycle(target_category, target_stop_ids):
    curr_page = 1
    last_page = 1 
    limit = 40
    new_scraped_ids = []
    
    olx_cookies = load_olx_cookies()
    headers = get_olx_headers(target_category)
    api_url = 'https://www.olx.pl/apigateway/graphql'

    try:
        while curr_page <= last_page:
            current_offset = (curr_page - 1) * limit
            json_data = get_olx_payload(current_offset, limit, target_category)
            
            response = requests.post(api_url, cookies=olx_cookies, headers=headers, json=json_data)
            
            if response.status_code != 200:
                logging.error(f"[OLX BŁĄD] Serwer zwrócił kod {response.status_code}.")
                break
                
            response_json = response.json()
            
            try:
                listings_data = response_json['data']['clientCompatibleListings']
                if listings_data['__typename'] == 'ListingSuccess':
                    items = listings_data['data']
                    total_elements = listings_data['metadata']['total_elements']
                    last_page = math.ceil(total_elements / limit)
                    logging.info(f"--- [OLX] Pobieranie strony {curr_page} z {last_page} | Ofert: {total_elements} ---")
                else:
                    logging.warning(f"[OLX BŁĄD GraphQL] Wystąpił błąd: {listings_data}")
                    break
            except KeyError as e:
                logging.error(f"[OLX BŁĄD JSON] Brakuje klucza: {e}")
                break
            
            if not items:
                logging.info(f"[OLX] Brak wyników na stronie {curr_page}.")
                break
            
            for item in items:
                item_id = int(item['id'])
                
                # WARUNEK STOPU OLX
                if item_id in target_stop_ids:
                    logging.info(f"[OLX] Dotarto do znanego ogłoszenia ({item_id}). Przechodzę dalej.")
                    new_scraped_ids.reverse()
                    return new_scraped_ids
                    
                new_scraped_ids.append(item_id)
                title = item.get('title', 'Brak tytułu')
                logging.info(f"[OLX] Nowe: {title}")
                
                photos = item.get('photos', [])
                if photos:
                    raw_link = photos[0].get('link')
                    if raw_link:
                        photo_url = raw_link.replace('{width}', '525').replace('{height}', '700')
                        img_response = requests.get(photo_url, stream=True)
                        if img_response.status_code == 200:
                            folder_docelowy = os.path.join("zdjecia_olx", target_category)
                            os.makedirs(folder_docelowy, exist_ok=True)
                            local_path = os.path.join(folder_docelowy, f"olx_{item_id}.png")
                            
                            with open(local_path, 'wb') as f:
                                for chunk in img_response.iter_content(8192):
                                    f.write(chunk)
                            logging.info(f"[DYSK OLX] Zapisano plik: {local_path}")
                        else:
                            logging.error(f"[BŁĄD CDN OLX] Status {img_response.status_code} dla {item_id}.")
                else:
                    logging.info(f"[INFO OLX] Brak zdjęć dla {item_id}.")
                
                time.sleep(1)
                
            curr_page += 1

    except KeyboardInterrupt:
        logging.warning("[!] PRZERWANO RĘCZNIE W TRAKCIE OLX! Zabezpieczam dane...")
    except requests.exceptions.RequestException as e:
        logging.error(f"[OLX BŁĄD SIECI] {e}")

    new_scraped_ids.reverse()
    return new_scraped_ids


def main():
    # Inicjujemy przeglądarkę dla Vinted tylko raz przy starcie
    session = make_boot_session()
    
    logging.info("=== URUCHAMIAM ZINTEGROWANY HARMONOGRAM (TYLKO MICROSD) ===")
    logging.info("Wskazówka: Możesz bezpiecznie użyć Ctrl+C, program zapisze postępy w DB!")
    
    try:
        while True:
            # 1. KROK: VINTED (Używamy klucza 'karty_pamieci' dla ID 3063)
            logging.info(f"\n[{time.strftime('%H:%M:%S')}] ---> START VINTED <---")
            punkty_stopu_vinted = pobierz_ostatnie_20_id_vinted() or [0]
            
            # Wpisujemy wartość bezpośrednio jako argument funkcji
            nowe_vinted = run_vinted_cycle(session, 'karty_pamieci', target_stop_ids=punkty_stopu_vinted)
            
            if nowe_vinted:
                zapisz_nowe_id_vinted(nowe_vinted)
                logging.info(f"[BAZA VINTED] Zapisano {len(nowe_vinted)} ogłoszeń do historii.")
            
            # 2. KROK: OLX (Używamy query 'microsd')
            logging.info(f"\n[{time.strftime('%H:%M:%S')}] ---> START OLX <---")
            punkty_stopu_olx = pobierz_ostatnie_50_id_olx('microsd') or [0]
            
            # Wpisujemy wartość bezpośrednio jako argument funkcji
            nowe_olx = run_olx_cycle('microsd', punkty_stopu_olx)
            
            if nowe_olx:
                zapisz_nowe_id_olx('microsd', nowe_olx)
                logging.info(f"[BAZA OLX] Zapisano {len(nowe_olx)} ogłoszeń do historii.")
            
            # 3. SEN
            logging.info("\n=== PEŁEN CYKL ZAKOŃCZONY. ZASYPIAM NA GODZINĘ ===")
            time.sleep(3600)
            
    except KeyboardInterrupt:
        logging.info("\n=== ZAMYKAM PROGRAM BEZPIECZNIE. DO ZOBACZENIA! ===")
        sys.exit(0)

if __name__ == "__main__":
    main()
