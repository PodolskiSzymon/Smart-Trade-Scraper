import time
import requests
import logging
import sys
from session_management import (
    make_boot_session, make_main_loop_referer, get_catalog_params, 
    update_sesions_cookies
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler() 
    ]
)

def run_vinted_debug_cycle(session, target_category):
    curr_page = 1
    my_order = 'newest_first'
    
    logging.info(f"--- [VINTED DEBUG] Pobieranie strony {curr_page} ---")
    
    session.headers.update({"Referer": make_main_loop_referer(curr_page)})
    catalog_params = get_catalog_params(category=target_category, page=curr_page, order=my_order)
    
    response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
    
    if response.status_code == 401:
        logging.warning("[VINTED] Ciastko wygasło. Odświeżam...")
        update_sesions_cookies(session)
        response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
    
    page_data = response.json()
            
    items = page_data.get('items', [])
    
    if not items:
        logging.warning("[VINTED] Brak ogłoszeń. Możliwy soft-ban lub zła kategoria.")
        return
        
    logging.info(f"[VINTED] Znaleziono {len(items)} ogłoszeń na pierwszej stronie. Drukuję zawartość:")
    print("-" * 50)
    
    for index, item in enumerate(items, 1):
        print(f"\n--- OGŁOSZENIE NR {index} ---")
        # To wydrukuje cały, surowy słownik dla danego ogłoszenia
        print(item)
        
    print("\n" + "-" * 50)
    logging.info("[VINTED DEBUG] Koniec drukowania.")


def main():
    cat_vinted = 'karty_pamieci'
    
    logging.info("=== URUCHAMIAM SKRYPT DEBUGUJĄCY VINTED ===")
    
    session = make_boot_session()
    
    try:
        run_vinted_debug_cycle(session, cat_vinted)
    except KeyboardInterrupt:
        logging.info("\n=== ZAMYKAM PROGRAM RĘCZNIE ===")
        sys.exit(0)

if __name__ == "__main__":
    main()