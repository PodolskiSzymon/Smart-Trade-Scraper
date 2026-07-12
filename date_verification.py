import time
import requests
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import psycopg2
from session_management import (
    make_boot_session, make_main_loop_referer, get_catalog_params, update_sesions_cookies
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

DB_PARAMS = {
    "dbname": "Postgre_Trade_Scraper", "user": "postgres", "password": "1221", "host": "localhost", "port": "5432"
}

def parse_vinted_date(time_str):
    """
    Tłumaczy polskie frazy Vinted na widełki czasowe (min_date, max_date).
    Zwraca datetime objects. Dodano manewry błędu dla cache'u Vinted.
    """
    tz = ZoneInfo("Europe/Warsaw")
    now = datetime.now(tz)
    time_str = time_str.lower().strip()

    # Wyciągamy liczbę, jeśli istnieje
    num_match = re.search(r'\d+', time_str)
    num = int(num_match.group()) if num_match else 1

    if "teraz" in time_str:
        return now - timedelta(hours=1), now + timedelta(hours=1)
        
    elif "min." in time_str or "minut" in time_str:
        return now - timedelta(minutes=num+5), now - timedelta(minutes=num-5)
        
    elif "godziny" in time_str or "godzinę" in time_str or "godz." in time_str:
        return now - timedelta(hours=num+3, minutes=5), now - timedelta(hours=num-3, minutes=-5)
        
    elif "wczoraj" in time_str:
        wczoraj = now - timedelta(days=1)
        # MANEWR CACHE: Cofamy dolną granicę o dodatkowe 24h (do przedwczoraj 00:00).
        # Łapie to ogłoszenia, którym Vinted zapomniało zmienić etykiety po północy.
        przedwczoraj = wczoraj - timedelta(days=1)
        return przedwczoraj.replace(hour=0, minute=0, second=0), wczoraj.replace(hour=23, minute=59, second=59)
        
    elif "dni" in time_str or "dzień" in time_str:
        start = now - timedelta(days=num)
        # MANEWR CACHE: Podobnie dla dni, cofamy dolną granicę o dodatkowe 24h.
        dolna_granica = start - timedelta(days=1)
        return dolna_granica.replace(hour=0, minute=0, second=0), start.replace(hour=23, minute=59, second=59)
        
    elif "tydzień" in time_str or "tygodnia" in time_str:
        return now - timedelta(days=14), now - timedelta(days=7)
        
    elif "tyg." in time_str:
        return now - timedelta(days=(num+1)*7), now - timedelta(days=num*7)
        
    elif "mies." in time_str or "miesiąc" in time_str:
        return now - timedelta(days=(num+1)*30), now - timedelta(days=num*30)
        
    elif "lat" in time_str or "rok" in time_str:
        return now - timedelta(days=(num+1)*365), now - timedelta(days=num*365)
    
    return now - timedelta(days=3650), now

def get_sidebar_info(session, item_id, item_url):
    url = f"https://www.vinted.pl/api/v2/items/{item_id}/details/sidebar"
    session.headers.update({"Referer": item_url})
    
    resp = session.get(url)
    
    if resp.status_code in [401, 403, 404]:
        logging.warning(f"[WERYFIKATOR] Vinted odrzuciło dostęp (Status {resp.status_code}). Kradnę nowe ciastka i tokeny z Playwrighta...")
        update_sesions_cookies(session)
        session.headers.update({"Referer": item_url})
        resp = session.get(url)
        
    if resp.status_code == 200:
        try:
            json_data = resp.json()
            item_data = json_data.get('item', json_data)
            plugins = item_data.get('plugins', [])
            
            # szybkie szukanie w strukturze "plugins -> attributes -> upload_date"
            attr_plugin = next((p for p in plugins if p.get('name') == 'attributes'), {})
            attributes_list = attr_plugin.get('data', {}).get('attributes', [])
            upload_date_attr = next((a for a in attributes_list if a.get('code') == 'upload_date'), {})
            
            znaleziona_data = upload_date_attr.get('data', {}).get('value', 'Brak')
            
            return znaleziona_data.strip() if znaleziona_data != 'Brak' else 'Brak'
            
        except Exception as e:
            logging.error(f"[WERYFIKATOR] Błąd parsowania {item_id}: {e}")
            
    else:
        logging.error(f"[WERYFIKATOR BŁĄD] Ostateczna odpowiedź {resp.status_code} dla ID {item_id}")
        
    time.sleep(0.5)
    return "Brak"

def extract_oldest_photo_ts(item):
    oldest_ts = None
    photos = item.get('photos', [])
    for p in photos:
        ts = p.get('high_resolution', {}).get('timestamp')
        if ts:
            if oldest_ts is None or ts < oldest_ts:
                oldest_ts = ts
    return oldest_ts

def save_verification_to_db(url, sidebar_str, ts_date, min_date, max_date, is_match, kraj):
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        with conn.cursor() as cur:
            # Dodaliśmy 'kraj_pochodzenia'
            cur.execute("""
                INSERT INTO vinted_weryfikacja_dat 
                (url, data_z_sidebar, timestamp_z_json, obliczona_data_poczatkowa, obliczona_data_koncowa, czy_zgodne, kraj_pochodzenia)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            """, (url, sidebar_str, ts_date, min_date, max_date, is_match, kraj))
        conn.commit()
    except Exception as e:
        logging.error(f"[DB ERROR] {e}")
    finally:
        if conn: conn.close()

def run_verification_cycle(session, target_category):
    tz = ZoneInfo("Europe/Warsaw")
    curr_page = 1
    
    logging.info(f"--- [WERYFIKATOR] Pobieranie katalogu ---")
    session.headers.update({"Referer": make_main_loop_referer(curr_page)})
    catalog_params = get_catalog_params(category=target_category, page=curr_page, order='newest_first')
    
    response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
    if response.status_code == 401:
        update_sesions_cookies(session)
        response = session.get('https://www.vinted.pl/api/v2/catalog/items', params=catalog_params)
        
    items = response.json().get('items', [])
    
    if not items:
        logging.warning("[WERYFIKATOR] Brak ogłoszeń w katalogu.")
        return

    logging.info(f"Pobrano {len(items)} ogłoszeń z katalogu. Rozpoczynam weryfikację sidebaru dla każdego z nich...")

    # Pętla po KAŻDYM przedmiocie z pobranej strony katalogu
    for idx, item in enumerate(items, 1):
        item_id = item['id']
        url = item.get('url')
        
        # 0. WYCIĄGAMY KRAJ SPRZEDAWCY (Zabezpieczone przez użycie bezpiecznego .get())
        kraj_sprzedawcy = item.get('user', {}).get('country_title', 'Nieznany')
        
        # 1. Pobierz twardy timestamp ze zdjęcia
        ts_raw = extract_oldest_photo_ts(item)
        exact_date = datetime.fromtimestamp(ts_raw, tz) if ts_raw else None
        
        # 2. Strzał do API sidebaru
        sidebar_str = get_sidebar_info(session, item_id, url)
        
        # 3. Przetworzenie na widełki czasowe
        min_date, max_date = parse_vinted_date(sidebar_str)
        
        # 4. Sprawdzenie zgodności
        zgodnosc = False
        if exact_date and min_date and max_date:
            if "teraz" in sidebar_str.lower():
                zgodnosc = True
            else:
                zgodnosc = min_date <= exact_date <= max_date
            
        logging.info(f"[{idx}/{len(items)}] Kraj: {kraj_sprzedawcy} | Sidebar: '{sidebar_str}' | Zgodne: {zgodnosc}")
        
        if not zgodnosc and exact_date and "brak" not in sidebar_str.lower():
            logging.warning(f"  -> Rozbieżność! Zdjęcie z {exact_date.strftime('%Y-%m-%d %H:%M')}, widełki to {min_date.strftime('%Y-%m-%d %H:%M')} - {max_date.strftime('%Y-%m-%d %H:%M')}")
            
        # 5. ZAPISUJEMY KRAJ DO BAZY
        save_verification_to_db(url, sidebar_str, exact_date, min_date, max_date, zgodnosc, kraj_sprzedawcy)
        
        time.sleep(1)

def main():
    session = make_boot_session()
    logging.info("=== START WERYFIKATORA DAT VINTED ===")
    
    try:
        run_verification_cycle(session, 'karty_pamieci')
        logging.info("=== ZAKOŃCZONO WERYFIKACJĘ ===")
    except KeyboardInterrupt:
        logging.info("Przerwano ręcznie.")

if __name__ == "__main__":
    main()