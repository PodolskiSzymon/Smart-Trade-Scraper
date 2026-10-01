import time
import os
import requests
import logging
import math
import sys
from db_management import pobierz_ostatnie_20_id_olx, zapisz_nowe_id_olx
from cookies_management import load_olx_cookies

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("olx_scraper_debug.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

GRAPHQL_QUERY = """query ListingSearchQuery(
  $searchParameters: [SearchParameter!] = []
) {
  clientCompatibleListings(searchParameters: $searchParameters) {
    __typename
    ... on ListingSuccess {
      __typename
      data {
        id
        title
        url
        photos {
          link
        }
      }
      metadata {
        total_elements
      }
    }
    ... on ListingError {
      __typename
      error {
        code
        detail
        status
        title
      }
    }
  }
}"""

def run_olx_scraper_cycle(target_category, target_stop_ids):
    curr_page = 1
    last_page = 1 
    limit = 40
    new_scraped_ids = []
    
    olx_cookies = load_olx_cookies()
    
    headers = {
        'accept': 'application/json',
        'accept-language': 'pl',
        'content-type': 'application/json',
        'origin': 'https://www.olx.pl',
        'referer': f'https://www.olx.pl/elektronika/q-{target_category}/?courier=1&search%5Bphotos%5D=1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0',
        'x-client': 'DESKTOP',
    }

    api_url = 'https://www.olx.pl/apigateway/graphql'

    # ZABEZPIECZENIE: Obejmujemy całą pętlę blokiem TRY
    try:
        while curr_page <= last_page:
            
            current_offset = (curr_page - 1) * limit
            
            json_data = {
                'query': GRAPHQL_QUERY,
                'variables': {
                    'searchParameters': [
                        {'key': 'offset', 'value': str(current_offset)},
                        {'key': 'limit', 'value': str(limit)},
                        {'key': 'query', 'value': target_category}, 
                        {'key': 'category_id', 'value': '2906'}, 
                        {'key': 'photos', 'value': 'true'},
                        {'key': 'courier', 'value': 'true'},
                        {'key': 'sort_by', 'value': 'created_at:desc'},
                    ]
                },
            }
            
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
                    logging.info(f"--- [OLX] Pobieranie strony {curr_page} z {last_page} | Kategoria: {target_category} | Łącznie ofert: {total_elements} ---")
                else:
                    logging.warning(f"[OLX BŁĄD GraphQL] Wystąpił błąd ListingError: {listings_data}")
                    break
            except KeyError as e:
                logging.error(f"[OLX BŁĄD] Niespodziewana struktura JSON. Brakuje klucza: {e}")
                break
            
            if not items:
                logging.info(f"[OLX] Brak ogłoszeń na stronie {curr_page} z {last_page}. Koniec wyników.")
                break
            
            for item in items:
                item_id = int(item['id'])
                
                if item_id in target_stop_ids:
                    logging.info(f"[OLX] Dotarto do znanego ogłoszenia ({item_id}). Kończę cykl.")
                    new_scraped_ids.reverse()
                    return new_scraped_ids
                    
                new_scraped_ids.append(item_id)
                
                title = item.get('title', 'Brak tytułu')
                item_url = item.get('url', 'Brak URL')
                logging.info(f"[OLX] Pobieram: {title}")
                
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
                    logging.info(f"[INFO] Brak zdjęć dla oferty {item_id}.")
                
                time.sleep(1)
                
            curr_page += 1

    # Przechwycenie momentu, w którym wciskasz Ctrl+C
    except KeyboardInterrupt:
        logging.warning("[!] PRZERWANO RĘCZNIE (Ctrl+C) W TRAKCIE POBIERANIA!")
        logging.info("[RATUNEK DANYCH] Trwa zabezpieczanie zebranych do tej pory ogłoszeń przed zamknięciem...")
    
    except requests.exceptions.RequestException as e:
        logging.error(f"[OLX BŁĄD SIECI] {e}")

    # To wykona się zawsze, niezależnie czy pętla doszła do końca, czy nacisnąłeś Ctrl+C.
    # Program odwraca to co zdążył zebrać (nawet te 30 sztuk) i zwraca do funkcji głównej!
    new_scraped_ids.reverse()
    return new_scraped_ids


def main():
    target_category = 'microsd'
    logging.info(f"=== URUCHAMIAM HARMONOGRAM SCRAPERA OLX DLA: {target_category.upper()} ===")
    logging.info("Wskazówka: Możesz przerwać program wciskając Ctrl+C, a on i tak zapisze postęp!")
    
    try:
        while True:
            punkty_stopu = pobierz_ostatnie_20_id_olx(target_category)
            if not punkty_stopu:
                punkty_stopu = [0]
                
            logging.info(f"\n[HARMONOGRAM OLX] Start. Aktywne punkty stopu: {punkty_stopu}")    
                
            nowo_pobrane_id = run_olx_scraper_cycle(target_category, punkty_stopu)
            
            # W tym miejscu program dostaje uratowaną listę (np. 30 sztuk) i zapisuje do bazy!
            if nowo_pobrane_id:
                zapisz_nowe_id_olx(target_category, nowo_pobrane_id)
                logging.info(f"[BAZA OLX] Uratowano i zapisano {len(nowo_pobrane_id)} ID do bufora.")
                
            logging.info("\n[HARMONOGRAM OLX] Cykl zakończony. Zasypiam na godzinę.")
            time.sleep(3600)
            
    # Drugie przechwycenie Ctrl+C, żeby program zakończył się bez czerwonego komunikatu o błędzie.
    except KeyboardInterrupt:
        logging.info("\n=== ZAMYKAM PROGRAM BEZPIECZNIE. DO ZOBACZENIA! ===")
        sys.exit(0)

if __name__ == "__main__":
    main()