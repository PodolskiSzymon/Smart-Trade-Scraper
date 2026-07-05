import os;
from cookies_management import update_cookies, load_cookies_from_file;
import requests;
import time;
import uuid;
import re;

categories={
    'nosniki_pamieci':3063,
    'elektronika':2994,
}

def get_catalog_params(category, order='newest_first', page=1, search_text='', brand_ids='', status_ids='', color_ids='', price_from='', price_to=''):
    catalog_ids = categories[category]
    params = {
        'page': page,
        'per_page': 96,
        'search_text': search_text,
        'price_from': price_from,
        'price_to': price_to,
        'currency': 'PLN',
        'order': order,
        'catalog_ids': catalog_ids,
        'brand_ids': brand_ids,
        'status_ids': status_ids,
        'color_ids': color_ids,
        'time': str(int(time.time())),
        'global_search_session_id': str(uuid.uuid4())
    }
    return params

def format_title(title):
    """Zmienia tytuł w format URL-friendly (slug)."""
    # 1. Zamieniamy na małe litery
    title = title.lower()
    # 2. Usuwamy ukośniki, kropki i inne znaki specjalne, zostawiając litery, cyfry i spacje
    title = re.sub(r'[^a-z0-9\s-]', '', title)
    # 3. Zamieniamy spacje (nawet wielokrotne) na pojedynczy myślnik
    title = re.sub(r'[\s-]+', '-', title)
    # 4. Usuwamy ewentualne myślniki z samego początku lub końca
    return title.strip('-')

def make_main_loop_referer(page=1):
    """Generuje referer dla przeglądania katalogu."""
    if page == 1:
        # Przechodząc w kategorie chcesz mieć podstawowy referer
        return "https://www.vinted.pl/catalog"
    else:
        # Dla kolejnych stron kategorii
        return f"https://www.vinted.pl/catalog?page={page}"

def make_endpoints_referer(item_id, title):
    """Generuje referer udający wejście w szczegóły konkretnego ogłoszenia."""
    # Formatuje tytuł usuwając znaki specjalne 
    clean_title = format_title(title)
    
    # Buduje pełny link do ogłoszenia [cite: 91, 97]
    return f"https://www.vinted.pl/items/{item_id}-{clean_title}?referrer=catalog"

def update_sesions_cookies(session):
    new_cookies= update_cookies()
    session.cookies.update(new_cookies)

def make_boot_session():
    """Tworzy i konfiguruje sesję HTTP do komunikacji z API Vinted."""
    
    # 1. Pobieramy świeże ciastka z Twojego drugiego skryptu
    cookies = load_cookies_from_file()
    
    # 2. Definiujemy nagłówki (udajemy prawdziwą przeglądarkę Edge)
    headers = {
        'accept': 'application/json,text/plain,*/*,image/webp',
        'accept-language': 'pl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'locale': 'pl-PL',
        'priority': 'u=3',
        'sec-ch-ua': '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0',
        # Kluczowe tokeny anty-botowe:
        'x-anon-id': 'e6f5e540-66d2-4848-ac99-c9e08762733f',
        'x-csrf-token': '75f6c9fa-dc8e-4e52-a000-e09dd4084b3e',
    }

    # 3. Tworzymy obiekt Sesji

    session = requests.Session()

    # 4. Wrzucamy do sesji nagłówki i ciastka na stałe
    session.headers.update(headers)
    session.cookies.update(cookies)
    
    # 5. Symulujemy wejście na stronę główną (żeby rozgrzać sesję i referery)
    glowna_url = "https://www.vinted.pl/"
    session.headers.update({"Referer": glowna_url})
    response=session.get(glowna_url) # To ciche zapytanie w tle uwiarygadnia nas przed serwerem
    if response.status_code==401:
        update_cookies()
        session.cookies.update(cookies)
    return session